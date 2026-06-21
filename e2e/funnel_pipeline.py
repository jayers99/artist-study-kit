"""End-to-end exercise of the funnel pipeline on a real artist (live AIC discovery).

Drives the REAL skill scripts and on-disk artifacts. The only simulated part is the
browser funnel clicks (Next/Commit) — we synthesize the exact three JSON files the
gallery JS would download, then run the real ingest/resolve/record path and assert
the Spec-B invariants on disk.

Run:  UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run python e2e/funnel_pipeline.py "Claude Monet"
"""
import json
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill"))

from scripts.paths import scaffold
from scripts.state import PackageState
from scripts.museum_search import search_aic
from scripts.image_download import cache_thumbnails
from scripts.gallery import build_thumbnail_gallery
from scripts.selection import load_selection, ingest_selection, load_study_set, selected_rows
from scripts.resolve import resolve_selection

ARTIST = sys.argv[1] if len(sys.argv) > 1 else "Claude Monet"
BASE = Path("/tmp/funnel-e2e-studies")
FINDINGS = []


def check(label, cond, detail=""):
    print(f"  [{'PASS' if cond else 'FAIL'}] {label}" + (f" — {detail}" if detail else ""))
    if not cond:
        FINDINGS.append(label + (f" ({detail})" if detail else ""))
    return cond


print(f"\n=== Funnel e2e: {ARTIST} ===\n")

# 1. Live discovery -------------------------------------------------------------
cands = search_aic(ARTIST)
print(f"1. Live AIC discovery: {len(cands)} candidates")
cands = cands[:12]
print(f"   trimmed to {len(cands)} for the board")
if not cands:
    print("   no candidates — pick a public-domain artist with AIC holdings")
    sys.exit(1)

# 2. Scaffold + merge + cache thumbnails (LIVE fetch) ---------------------------
sp = scaffold(BASE, ARTIST)
st = PackageState.load(sp.state_json, ARTIST)
run = st.record_run("aic", *st.merge_candidates(cands, "run-1"), total=len(cands))
added = len(st.candidates)
print(f"\n2. Package scaffolded at {sp.root}")
print(f"   merged {added} candidates (run {run.id})")
cached = cache_thumbnails(st.candidates, sp.candidates_dir)
st.save(sp.state_json)
print(f"   cached {cached} thumbnails locally")
check("every candidate got a local thumbnail_path",
      all(c.thumbnail_path for c in st.candidates),
      f"{sum(1 for c in st.candidates if c.thumbnail_path)}/{added}")
check("cached thumb files exist on disk + non-zero bytes",
      all((sp.root / c.thumbnail_path).is_file() and (sp.root / c.thumbnail_path).stat().st_size > 0
          for c in st.candidates if c.thumbnail_path))

# 3. Build the funnel gallery (REAL) --------------------------------------------
html = build_thumbnail_gallery(st.candidates, ARTIST, package_root=sp.root)
sp.gallery_html.write_text(html, encoding="utf-8")
print(f"\n3. Built funnel gallery.html ({len(html)} bytes)")
for marker in ('id="next"', 'id="commit"', "MAX_STUDY", "wideCut", "renderZoom",
               "study-set.json", "seedStars", "data-select"):
    check(f"funnel HTML contains {marker}", marker in html)

payload = json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
rows = payload["candidates"]
check("payload carries full_url for every card", all(r.get("full_url") for r in rows))
check("full_url swaps IIIF size to 843 (real URLs)",
      all("/full/843," in r["full_url"] for r in rows),
      f"{sum(1 for r in rows if '/full/843,' in r['full_url'])}/{len(rows)}")
check("image_rel prefers the local cached thumb",
      all(r["image_rel"].startswith("images/candidates/") for r in rows))
check("every card starts unselected (per-session)", all(r["selected"] is False for r in rows))

# 4. Simulate the browser funnel clicks -----------------------------------------
toks = [r["iiif_token"] for r in rows]
wids = {r["iiif_token"]: r["work_id"] for r in rows}
wide_tokens = toks[:6]               # frozen on "Next"
narrow_tokens = wide_tokens[:3]      # still-selected at "Commit" (tokens 3,4,5 dropped at zoom)
dropped_at_zoom = wide_tokens[3]
star_map = {rows[0]["work_id"]: 5, rows[1]["work_id"]: 1, rows[7]["work_id"]: 4}
print("\n4. Simulating funnel: wide cut = 6, narrow study set = 3 (1 wide work dropped at zoom)")

sp.root.joinpath("stars.json").write_text(json.dumps({
    "artist": ARTIST,
    "stars": [{"work_id": r["work_id"], "stars": star_map.get(r["work_id"], 0)} for r in rows],
}), encoding="utf-8")

wide_set = set(wide_tokens)
sp.selection_json.write_text(json.dumps({
    "artist": ARTIST,
    "ratings": [{
        "work_id": r["work_id"], "iiif_token": r["iiif_token"], "image_rel": r["image_rel"],
        "title": r["title"], "date": r["date"], "medium": r["medium"],
        "source_url": r["source_url"], "museum": r["museum"], "rights": r["rights"],
        "qid": r["qid"], "inst_ids": r["inst_ids"],
        "selected": r["iiif_token"] in wide_set, "stars": star_map.get(r["work_id"], 0),
    } for r in rows],
}), encoding="utf-8")

sp.study_set_json.write_text(json.dumps({
    "artist": ARTIST, "study_set": [wids[t] for t in narrow_tokens],
}), encoding="utf-8")

# 5. Real ingest / resolve / record path (per SKILL.md) -------------------------
print("\n5. Running the real ingest -> resolve(only=study_set) -> record path")
st = PackageState.load(sp.state_json, ARTIST)
stars_in = json.loads(sp.root.joinpath("stars.json").read_text())
updated = st.ingest_stars({row["work_id"]: row["stars"] for row in stars_in["stars"]})
sel = load_selection(sp.selection_json, ARTIST)
selected_ids, _ = ingest_selection(sel)
study_set = load_study_set(sp.study_set_json, ARTIST)
resolved = resolve_selection(
    sel, sp.selected_dir,
    resolvers=[lambda e: SimpleNamespace(work_id=e.work_id, image_url="u", license="", institution="aic")],
    download=lambda cand, d: SimpleNamespace(status="downloaded", image_path=d / f"{cand.work_id}.jpg"),
    only=set(study_set),
)
sess = st.record_session("seascapes", "subject", selected_ids, study_set,
                         outputs={"study_briefs": "study-briefs.json"})
st.save(sp.state_json)
queue_rows = [r for r in selected_rows(sel) if r.work_id in study_set]

# 6. Spec-B invariants ----------------------------------------------------------
print("\n6. Invariants")
check("ingest_stars applied every exported entry (gallery exports all candidates)",
      updated == len(rows), f"updated {updated}/{len(rows)}")
_re = PackageState.load(sp.state_json, ARTIST)
check("the rated works got their exact stars; the rest stayed 0",
      _re.candidate(rows[0]["work_id"]).stars == 5 and _re.candidate(rows[1]["work_id"]).stars == 1
      and _re.candidate(rows[7]["work_id"]).stars == 4 and _re.candidate(rows[2]["work_id"]).stars == 0)
check("study_set is <= MAX_STUDY (4)", len(study_set) <= 4, f"len={len(study_set)}")
check("study_set is a subset of the wide selected cut", set(study_set) <= set(selected_ids))
check("wide cut is bigger than study_set (record, not the study set)",
      len(selected_ids) > len(study_set), f"wide={len(selected_ids)} narrow={len(study_set)}")
check("work dropped at zoom stayed in selection.json (wide) ...", wids[dropped_at_zoom] in selected_ids)
check("... but is ABSENT from study-set.json (narrow)", wids[dropped_at_zoom] not in study_set)
check("resolve ran ONLY on the study_set (only= bound held)",
      sorted(r.work_id for r in resolved) == sorted(study_set))
check("interview queue bounded to the study_set",
      sorted(r.work_id for r in queue_rows) == sorted(study_set))
check("session records BOTH cuts",
      set(sess.selected) == set(selected_ids) and set(sess.study_set) == set(study_set))
one_star_wid = rows[1]["work_id"]
check("stars _|_ selection: a 1-star work is in the wide cut",
      star_map.get(one_star_wid) == 1 and one_star_wid in selected_ids)
check("has_candidates() true after a collect (skip-discovery would study this board)",
      st.has_candidates())

print("\n=== RESULT ===")
if FINDINGS:
    print(f"{len(FINDINGS)} finding(s):")
    for f in FINDINGS:
        print("  -", f)
    sys.exit(1)
print("All funnel-pipeline invariants held on real data + real artifacts.")
print(f"Artifacts: {sp.root}")
