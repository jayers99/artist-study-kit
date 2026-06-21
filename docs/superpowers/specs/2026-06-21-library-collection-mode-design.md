# Library Collection Mode + SKILL Wiring — Design Spec

> **Spec B** of the duplicate-handling-on-re-query feature. Consumes the built **Spec A**
> engine (`image_similarity` + `image_manifest` + `dedup`, merged `b593c8e`). Spec A decides;
> Spec B downloads, executes the file moves/deletes, syncs the curation board, and wires the
> new mode into `SKILL.md`. Engine spec: `2026-06-21-image-dedup-engine-design.md`.

**Date:** 2026-06-21
**Builds on:** Spec A (dedup engine + `manifest.json`), Thrust 1 stateful `state.json`,
Thrust 2 `images/user/` + `origin`/`local_path`, Thrust 3 funnel/gallery/curation.

---

## 1. Goal

Add a **library collection mode**: collection eagerly downloads full-res images, deduplicates
each against an accumulating on-disk library (the user's seeded images + everything collected
on prior runs), keeps the best copy, augments/cleans metadata, and maintains the provenance
manifest — then feeds the deduped library straight into the existing curation funnel
**unchanged**. A one-time seed-import folds the user's external collection in first.

One sentence: *seed my collection, collect more, keep one best copy of each work with merged
metadata in `images/library/`, and curate it with the funnel I already have.*

## 2. Why now

Spec A built the pure decision engine but it touches no files. Without Spec B the engine does
nothing end-to-end. The user's workflow — start from a pre-collected folder, collect more,
never re-add a work they already have, clean up un-named/metadata-less seed images — needs the
download + file-execution + board-sync layer. The Cezanne seed (30 images with real duplicate
pairs) is the validation bed.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Scope | Spec B: download + execute `DedupAction` + manifest↔board sync + seed-import + SKILL wiring + Cezanne e2e. The decision logic is Spec A (already built); this spec does not re-implement it. |
| Library ↔ board | **Sync to `state.candidates`**: one manifest entry → one `BoardCandidate` (`local_path`/`thumbnail_path` → library file). The existing funnel/gallery/star/select/study-set/interview flow runs **unchanged**. |
| Collection mode | **New mode, coexists** with the current thumbnail-only board collect. Selected per run; the old lightweight flow is untouched. |
| Seed-import | **Explicit one-time step**: `artist` + external collection path → copy to `images/user/` → fold into the library. |
| Seed file handling | **Move, not copy**: `images/user/` is a transient landing zone; files are moved into `images/library/` as folded in, so the library is the single canonical home and `user/` ends empty. The external original is never touched (the real archive). |
| "Better" copy / threshold / merge | Inherited from Spec A: largest pixel area → bytes → existing wins; metadata fills empty fields; **stars preserved**; `DUP_THRESHOLD = 0.90`; only-same-full-image. |
| Download breadth | Eager full-res for every discovered work **that exposes a fetchable image** (resolver chain: Commons full / AIC IIIF). Works exposing only a webpage have nothing to fetch — the seed copy fills that gap. Rights **recorded, not gated** (user-authorized, private study). |
| Cross-run | The persisted `manifest.json` is the dedup index; a later collect dedups against it. |
| E2E | **Full live Cezanne run** (real discovery + downloads), in `e2e/` (outside pytest). |
| Atomicity | Winner is placed at its library path via temp + `os.replace`; the loser is deleted **only after** the winner is safely in place. Never delete an external original. |

## 4. Paths (extend `scripts/paths.py`)

```python
LIBRARY_REL  = "images/library"     # canonical deduped masters (matches Spec A dedup.LIBRARY_REL)
INCOMING_REL = "images/incoming"    # transient: freshly downloaded images await dedup
MANIFEST_REL = "images/manifest.json"
```

- `StudyPaths` gains `library_dir`, `incoming_dir`, `manifest_json` properties.
- `_SCAFFOLD_DIRS` gains `images/library` and `images/incoming`.
- `images/user/` (already scaffolded) is the seed landing zone, consumed by seed-import.

## 5. Module: `scripts/library.py` (new) — executor + orchestration

Pure-ish: all filesystem effects go through injected `move`/`delete`/`copy` seams (default
`shutil`), so the logic is unit-testable on `tmp_path` with no real images required where hashes
are injected.

```python
@dataclass(frozen=True)
class LibrarySummary:
    added: int          # new works placed in the library
    merged_kept: int    # dup found, existing copy kept (incoming deleted)
    merged_replaced: int  # dup found, incoming was larger (old library file replaced)

def execute_action(action: DedupAction, paths: StudyPaths, *,
                   move=shutil.move, delete=os.remove) -> ManifestEntry:
    """Execute one Spec-A DedupAction. Places action.keep_path at
    paths.root/LIBRARY_REL/action.canonical_name (temp + os.replace), then removes
    action.delete_path IFF set and different from the final library path. Returns the
    (already-built) action.entry, with entry.path normalized to the realized library path.
    Never touches files outside the study package."""

def build_library(incoming: list[IncomingImage], manifest: Manifest, paths: StudyPaths,
                  run_id: str, *, threshold=DUP_THRESHOLD,
                  move=shutil.move, delete=os.remove) -> LibrarySummary:
    """For each incoming image: dedup.resolve(inc, manifest, run_id) -> execute_action ->
    manifest.upsert(entry). Returns counts. Caller saves the manifest + records the run.
    Order matters: process the batch sequentially so two incoming copies of the same work
    dedup against each other (the first lands, the second merges)."""

def make_incoming(path, *, source, source_url, rights, title="", date="", qid="",
                  inst_ids=(), medium="", hash_for=perceptual_hashes,
                  dims_for=image_dims) -> IncomingImage | None:
    """Hash + measure a downloaded/seed file into a Spec-A IncomingImage. Returns None
    (fail-open) when the file can't be hashed/measured — caller skips it (never added)."""

def sync_candidates(manifest: Manifest, state: PackageState, run_id: str) -> int:
    """Upsert one BoardCandidate per manifest entry so the curation board mirrors the
    library. local_path = thumbnail_path = entry.path (board renders offline from the
    library file); origin = "user" when any entry.origins record has source=="user-seed"
    (so the USER badge shows for works the user supplied), else "discovered"; stars carried
    from the entry. Matches by work_id (idempotent; re-sync after a later run updates in
    place). Returns count upserted."""
```

Key behaviors:
- **execute_action ordering** (the final-review hazard): build the winner at a temp path in
  `library_dir`, `os.replace` it onto `LIBRARY_REL/canonical_name`, *then* delete the loser if
  its path differs. If the winner already **is** the existing library file and the name is
  unchanged (no-churn existing-wins), it's a no-op — no delete, no move.
- **manifest is authoritative** for collision avoidance — `dedup.canonical_name` de-collides
  against manifest filenames; `build_library` writes only under `library_dir`.

## 6. Seed-import (in `scripts/library.py`)

```python
def seed_import(external_dir, paths: StudyPaths, manifest: Manifest, run_id: str,
                *, copy=shutil.copy2, move=shutil.move, delete=os.remove,
                hash_for=perceptual_hashes, dims_for=image_dims) -> LibrarySummary:
    """1. Copy every image file in external_dir -> images/user/ (external NEVER modified).
       2. make_incoming for each (source="user-seed", rights="unknown", title from filename
          stem as a fallback so canonical naming has something; qid empty).
       3. build_library(those, manifest, paths, run_id) — folding moves each from
          images/user/ into images/library/, so images/user/ ends empty.
       Returns the summary. Caller saves manifest + records the run + sync_candidates."""
```

- Idempotent re-run: the manifest already holds the seed's hashes, so a second seed-import of
  the same folder dedups to "merged_kept" and re-empties `user/` — no duplication.
- Discovery later **augments** these seed entries' empty metadata (Spec A merge fills gaps).

## 7. Eager download (extend `scripts/image_download.py`)

```python
def download_library(candidates, incoming_dir, *, resolve_url, fetch=default_fetch,
                     sleep=time.sleep, min_interval=1.0) -> list[DownloadResult]:
    """For each board candidate, resolve_url(candidate) -> best fetchable full-res URL
    (None if the work exposes no image, e.g. webpage-only in-copyright). Download to
    incoming_dir/<work_id>.<ext>, idempotent, throttled, robots-aware. Reuses the existing
    fetch seam and DownloadResult shape. Candidates with no URL are skipped (status
    'no-image'), to be backfilled by the seed."""
```

- `resolve_url` default wraps the existing resolver chain (`resolve.commons_resolver` /
  `aic_resolver` → the URL each would fetch) so we reuse, not duplicate, source logic.
- Rights from the candidate are carried onto the `IncomingImage` and recorded; not a gate.

## 8. SKILL.md — new "library collection" mode (Phase A)

A new branch in the collection stage, selected when the human asks to **build/seed a library**
(or provides a collection path). Steps Claude runs:

1. **Seed (once, if a path is given):** `library.seed_import(path, sp, manifest, run_id)` →
   save manifest, `record_run("seed-import", …)`, `sync_candidates`.
2. **Collect:** existing discovery (`search_wikidata` + `search_aic` + `merge_boards`) to get
   the candidate list → `image_download.download_library(cands, sp.incoming_dir,
   resolve_url=…)` → `library.make_incoming` per downloaded file →
   `library.build_library(incoming, manifest, sp, run_id)` → save manifest,
   `record_run("library:wikidata+aic", …)`, `sync_candidates(manifest, state, run_id)`.
3. **Curate:** unchanged — `cache_thumbnails` is a no-op for library cards (they already have
   `thumbnail_path` = the library file), then `build_thumbnail_gallery` / the funnel run
   exactly as today over `state.candidates`.

The existing thumbnail-only collect path stays as the default mode; library mode is additive.

## 9. Components & boundaries (summary)

| Unit | Responsibility | Depends on |
|---|---|---|
| `library.execute_action` | one DedupAction → files on disk + normalized entry | Spec A `DedupAction`, paths, fs seams |
| `library.build_library` | batch dedup+execute+upsert | `dedup.resolve`, `execute_action`, `Manifest` |
| `library.make_incoming` | file → `IncomingImage` (fail-open) | `image_similarity` |
| `library.sync_candidates` | manifest → curation board | `state.BoardCandidate` |
| `library.seed_import` | external → user/ → library | `build_library` |
| `image_download.download_library` | resolve+download full-res → incoming/ | resolver chain, fetch seam |
| `paths` additions | library/incoming/manifest paths | — |
| `SKILL.md` Phase-A branch | orchestrate the mode | all of the above |

## 10. Error handling

- **Un-hashable download / seed file** → `make_incoming` returns `None` → skipped, never added
  (fail-open, Spec A posture). Logged in the summary.
- **Download failure / no image URL** → `DownloadResult` status `error`/`no-image`; the work
  stays curatable via its seed copy or thumbnail; never crashes the batch (existing posture).
- **Interrupted run:** `images/incoming/` is transient; a re-run re-downloads (idempotent) and
  re-dedups against the persisted manifest. Partial library writes are safe (atomic replace).
- **External original safety:** seed-import only ever reads the external dir; a test asserts the
  source dir is byte-for-byte unchanged after import.

## 11. Testing

Offline `pytest` (one `test_<module>.py` per module; injected `move`/`delete`/`fetch`/`hash`
seams — no network, real images only where pixel behavior is under test):

`tests/test_library.py`:
- `execute_action` add → file at `images/library/<cn>`, no delete, entry.path normalized.
- `execute_action` merge incoming-wins → old library file deleted, winner placed, entry updated.
- `execute_action` merge existing-wins → incoming deleted, library file untouched (no-op move).
- `execute_action` never deletes a path outside the package (assert delete seam called only
  with library/incoming paths).
- `build_library` batch: two incoming of the same work collapse (1 added + 1 merged); cross-run
  against a pre-populated manifest merges; summary counts correct.
- `make_incoming` fail-open → `None` on garbage file.
- `sync_candidates`: one `BoardCandidate` per entry, `local_path`==`thumbnail_path`==entry.path,
  stars carried, `origin` user-seed→"user"; idempotent on re-sync.
- `seed_import`: copies all images to `user/`, folds into `library/`, **`user/` ends empty**,
  external dir unchanged; idempotent re-run doesn't duplicate.

`tests/test_image_download.py` (additions):
- `download_library` writes resolved URLs to `incoming/` (injected fetch), skips no-URL works
  (`no-image`), idempotent, throttles.

`tests/test_skill_md.py` (additions, matching the existing skill_md test style):
- the library-collection branch documents seed_import → download_library → build_library →
  sync_candidates → unchanged funnel, and notes the thumbnail-only mode still exists.

`e2e/` (live, outside pytest):
- `e2e/library_collection.py` — full Cezanne run: `seed_import` the 30 `studies/cezanne/`
  images, live discovery + `download_library`, `build_library`, assert the known dup pairs
  collapse (`cezannepotsouptureen.jpg` ↔ `(1).jpg`; Madame Cézanne JPG ↔ 60 MB PSD → larger
  wins), metadata augmented on matched seeds, `user/` emptied, manifest provenance recorded,
  `sync_candidates` yields a curatable board.

## 12. Out of scope

Discovery-board (remote-thumbnail) perceptual dedup; pHash-bucket optimization; watermark
detection; QID-authoritative metadata override (Spec A merge is existing-non-empty-wins — a
later spec if needed); retiring the thumbnail-only collect mode; the Thrust-2 Claude-vision
import flow (untouched — library seed-import is the lighter content-dedup path).
