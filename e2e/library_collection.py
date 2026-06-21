"""Live e2e — library collection mode on the Cezanne seed. NOT a pytest test.

Run:  UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run python e2e/library_collection.py
Hits the real network (Wikidata/AIC + image downloads). Operates in a temp study
dir; the seed at studies/cezanne/images/user is copied in, never mutated here.

Exit code 0 = PASS, non-zero = failure.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill"))

from scripts.paths import scaffold
from scripts.image_manifest import Manifest
from scripts import library, wikidata, museum_search, image_download
from scripts.resolve import default_resolve_url
from scripts.state import PackageState

FINDINGS: list[str] = []


def check(label: str, cond: bool, detail: str = "") -> bool:
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        FINDINGS.append(label + (f" ({detail})" if detail else ""))
    return cond


def main() -> int:
    seed = Path(__file__).resolve().parents[1] / "studies" / "cezanne" / "images" / "user"
    if not seed.is_dir() or not any(seed.iterdir()):
        print("SKIP: seed studies/cezanne/images/user is empty")
        return 0

    seed_files = [f for f in seed.iterdir() if f.is_file()]
    n_seed_files = len(seed_files)
    print(f"\n=== Library Collection e2e: Paul Cézanne ===\n")
    print(f"seed dir has {n_seed_files} files")

    work = Path(tempfile.mkdtemp(prefix="cezanne-lib-"))
    sp = scaffold(work, "Cezanne")
    man = Manifest()

    print("\n--- Step 1: seed_import ---")
    s = library.seed_import(seed, sp, man, run_id="seed")
    print(f"seed_import: added={s.added}  merged_kept={s.merged_kept}  merged_replaced={s.merged_replaced}")

    seed_entries = len(man.entries)
    print(f"seed library entries: {seed_entries} (deduped from {n_seed_files} files)")
    collapsed = n_seed_files - seed_entries
    if collapsed > 0:
        print(f"  → {collapsed} duplicate(s) collapsed during seed_import")

    check("seed produced at least one library entry", seed_entries > 0,
          f"entries={seed_entries}")
    check("user/ is empty after seed_import (files moved to library/)",
          not any(sp.user_images_dir.iterdir()),
          f"user_dir={sp.user_images_dir}")
    check("external seed dir is untouched (still has all original files)",
          len([f for f in seed.iterdir() if f.is_file()]) == n_seed_files,
          f"expected={n_seed_files}")

    # Known duplicate pairs:
    #   cezannepotsouptureen.jpg  ↔  cezannepotsouptureen (1).jpg  (byte-identical)
    #   Paul_Cézanne_-_Madame_Cézanne_in_a_Red_Armchair_...jpg  ↔  ...psd  (same image, different format)
    # These should collapse: seeds_files=30 → entries < 30
    check("known dup pairs collapsed (seed_entries < n_seed_files)",
          seed_entries < n_seed_files,
          f"seed_entries={seed_entries}  seed_files={n_seed_files}")

    # --- Step 2: live discovery ---
    print("\n--- Step 2: live discovery ---")
    wikidata_ok = True
    aic_ok = True
    cands: list = []

    try:
        wd_cands, _works, _amb = wikidata.search_wikidata("Paul Cézanne")
        cands = list(wd_cands)
        print(f"wikidata: {len(cands)} candidates")
    except Exception as exc:
        wikidata_ok = False
        print(f"wikidata degraded: {exc}")

    try:
        aic_cands = list(museum_search.search_aic("Paul Cézanne"))
        cands = cands + aic_cands
        print(f"AIC: {len(aic_cands)} candidates  (total so far: {len(cands)})")
    except Exception as exc:
        aic_ok = False
        print(f"AIC degraded: {exc}")

    if not wikidata_ok:
        print("  [NOTE] Wikidata degraded — AIC-only run")
    if not aic_ok:
        print("  [NOTE] AIC degraded")

    print(f"discovered {len(cands)} candidates total")

    if not cands:
        print("  [WARN] no discovered candidates — skipping download/build_library steps")
    else:
        # Cap to a reasonable number to keep the e2e from running too long
        cap = 20
        if len(cands) > cap:
            print(f"  capping to {cap} candidates for download")
            cands = cands[:cap]

        # --- Step 3: download_library ---
        print(f"\n--- Step 3: download_library ({len(cands)} candidates) ---")
        dls = image_download.download_library(
            cands, sp.incoming_dir,
            resolve_url=default_resolve_url,
            min_interval=0.5,
        )
        got = [d for d in dls if d.path is not None]
        errors = [d for d in dls if d.status == "error"]
        no_image = [d for d in dls if d.status == "no-image"]
        print(f"download_library: {len(got)} downloaded  "
              f"{len(errors)} errors  {len(no_image)} no-image  "
              f"(of {len(dls)} total)")

        # --- Step 4: build_library ---
        print("\n--- Step 4: build_library ---")
        inc = [library.make_incoming(d.path, source="discovered") for d in got if d.path]
        inc_valid = [x for x in inc if x is not None]
        print(f"make_incoming: {len(inc_valid)} valid incoming images (of {len(got)} downloaded)")
        s2 = library.build_library(inc_valid, man, sp, run_id="collect")
        print(f"build_library: added={s2.added}  merged_kept={s2.merged_kept}  "
              f"merged_replaced={s2.merged_replaced}")

    # --- Step 5: sync_candidates ---
    print("\n--- Step 5: sync_candidates ---")
    st = PackageState(artist="Cezanne")
    n = library.sync_candidates(man, st, run_id="collect")
    print(f"sync_candidates: {n} entries synced to board")

    final_entries = len(man.entries)
    board_cands = len(st.candidates)

    check("final library has at least as many entries as seed",
          final_entries >= seed_entries,
          f"final={final_entries}  seed={seed_entries}")
    check("board candidate count matches manifest entries",
          board_cands == final_entries,
          f"board={board_cands}  manifest={final_entries}")
    check("sync_candidates returned correct count",
          n == final_entries,
          f"returned={n}  manifest={final_entries}")
    check("user/ still empty after full pipeline",
          not any(sp.user_images_dir.iterdir()))
    check("seed external dir still untouched at end",
          len([f for f in seed.iterdir() if f.is_file()]) == n_seed_files,
          f"expected={n_seed_files}")

    # Print summary
    print(f"\n=== RESULT ===")
    print(f"seed files: {n_seed_files}")
    print(f"seed library entries (after dedup): {seed_entries}  ({collapsed} dup(s) collapsed)")
    if cands or True:
        print(f"wikidata: {'UP' if wikidata_ok else 'DEGRADED'}  "
              f"AIC: {'UP' if aic_ok else 'DEGRADED'}")
        if cands:
            print(f"discovered (capped): {len(cands)}")
            print(f"downloaded: {len(got) if 'got' in dir() else 'N/A'}")
    print(f"final library entries: {final_entries}")
    print(f"board candidates synced: {board_cands}")
    print(f"temp study dir: {work}")

    if FINDINGS:
        print(f"\n{len(FINDINGS)} invariant(s) FAILED:")
        for f in FINDINGS:
            print(f"  - {f}")
        return 1

    print("\nPASS: all library-collection invariants held on real data + real artifacts.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
