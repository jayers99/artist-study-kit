# Custom Image Injection — Design Spec

**Date:** 2026-06-20
**Status:** approved (design) → ready for implementation plan
**Source feedback:** `raw/19-stateful-runs-custom-images-staged-analysis.md`, **Thrust 2** (inject the user's own image collection).
**Builds on:** the now-built stateful package state (`docs/superpowers/specs/2026-06-20-stateful-package-state-design.md`) — Thrust 1 reserved the `origin: "discovered" | "user"` seam on `BoardCandidate`; this spec is the first writer of `origin:"user"`.
**Related stages:** closest to [[stage-image-discovery]] (a new candidate source) and [[stage-visual-analysis]] (reads the user's full-res pixels directly).

## Motivation

The skill's own discovery is limited to what museum APIs and Wikidata expose — heavily public-domain, often missing in-copyright works. But the user has a large personal collection of paintings (photos, scans, downloads) spanning many artists. Thrust 2 lets that collection become first-class study material: the user points the skill at a folder, and each image is identified and enriched to the **same metadata shape as a discovered candidate** so it flows through curation and analysis identically.

The key insight: the skill already runs inside a multimodal model. Rather than wire an external reverse-image-search API (no clean Google API; paid/brittle scraping), **Claude looks at each image and proposes an identity, and the existing discovery pipeline verifies and enriches it.** Identification reuses code we already have; the pipeline is the trust anchor (mirroring F3 — never silently trust auto-derived provenance).

## Goals

- A new re-enterable **import** operation: a folder of images → `origin:"user"` candidates in the existing `state.json` board.
- Each image is identified by Claude vision and **verified against the existing pipeline** (`wikidata` / `museum_search`), recovering authoritative `title/date/qid/museum/source_url/rights` when corroborated.
- A **human trust gate** before anything reaches the board: a transient import-review artifact the user confirms/edits/rejects.
- User images carry their **full-resolution local file**; visual analysis reads it directly (no rights-gated re-download).
- **Overlap is enrichment, not duplication:** a user image that matches an existing discovered work enriches that one card with the local file rather than adding a second.

## Non-goals (separate specs / chosen out)

- **External reverse-image-search API** (SerpAPI/Google Lens/TinEye). Chosen out in brainstorming: Claude-vision-first, pipeline-verified, no API key or per-call cost. A work Claude cannot name lands as `unidentified` rather than triggering an external lookup.
- **Multi-artist auto-routing.** One import targets one artist study. Images identified as a different artist are set aside (`off_artist`), not routed to or used to create other studies.
- **Thrust 3** — narrowing funnel, gallery rework, year-sort, drop-stars. User cards appear on the existing gallery with an origin badge; that's all.
- **Thumbnail-generation pipeline / Pillow dependency.** User cards render the local copy CSS-scaled in the gallery. No downscaled-derivative step.
- No change to how any *other* stage works — only a new candidate source plus one schema field.

## Decisions (locked)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Identification | **Claude vision → pipeline verify** | The skill already runs in a multimodal model. Claude proposes `{artist, title, date}`; the existing `wikidata`/`museum_search` lookups corroborate. No external API, reuses code, pipeline is the trust anchor. |
| Folder → artist | **One folder = one artist** | Each import targets the current/named study. `off_artist` images are set aside, never silently studied or routed elsewhere. Matches the per-artist package model. |
| Trust gate | **Batch review before board** | Import emits a transient `import-review` (json + html); the human confirms/edits/rejects in one pass. Only confirmed rows reach `candidates[]`. Nothing untrusted touches the board. Mirrors the `selection.json` handoff pattern. |
| Files & rights | **Copy in, use directly, inherit rights** | The user already owns the pixels: copy into `images/user/`, analysis reads the local file (no resolver, no rights-gated download). `rights` inherited from the corroborating record on confirm, else `"unknown"`. Private-study posture, never redistributed. |
| Overlap | **Enrich existing with local file** | A user image that dedups against a discovered candidate (QID → inst_ids → work_id) enriches that one card: set its `local_path`, keep its `origin`/provenance. One card, now backed by full-res pixels — no visible duplicate. |
| Confidence persistence | **Transient only** | Confidence (`confirmed`/`proposed`/`off_artist`/`unidentified`) lives in `import-review`, not on `candidates[]`. Once the human confirms, the candidate is trusted; the review file is disposable like `selection.json`. |

## Architecture

### Schema delta

One new field on `BoardCandidate` (`scripts/state.py`):

```python
local_path: str = ""   # package-relative path to the user's copied file; "" = no user copy
```

`local_path != ""` is the single signal that user-supplied pixels exist on disk (whether the candidate is `origin:"user"` or an enriched `origin:"discovered"` one). `to_dict`/`from_dict`/`from_thumbnail` extend to carry it (default `""`, so all existing packages load unchanged).

### Identity split — LLM vs. testable code

- **Claude (agent, documented in `SKILL.md`)** — the only vision step. For each image file, Claude emits a structured guess `{filename, artist, title, date}` (or a null guess if it cannot identify the work). Not unit-tested.
- **`scripts/user_import.py` (pure, fully testable)** — everything downstream: verification, review-file build, ingestion.

### Components

**A. `scripts/user_import.py` (new module).**

- `ImportRow` dataclass — one row per image: `filename, source_path, state, artist, title, date, qid, museum, source_url, rights, work_id`. `state ∈ {"confirmed","proposed","off_artist","unidentified"}`. `to_dict`/`from_dict` for the review round-trip.
- `verify_identification(guess: dict, study_artist: str, *, lookup) -> ImportRow` — given Claude's guess and the study's artist, corroborate via `lookup` (a small seam over the existing `wikidata`/`museum_search` search, injectable for tests):
  - no guess / no title → `unidentified`.
  - guess artist resolves to a different artist than `study_artist` → `off_artist` (set aside).
  - `lookup` returns a matching record → `confirmed`; fill `title/date/qid/museum/source_url/rights` from the record.
  - guess present but `lookup` finds nothing → `proposed`; keep the guessed `title/date`, `rights="unknown"`, empty `qid/source_url`.
- `build_review(rows) -> (json_obj, html_str)` — render the import-review table; html shows each image, its state badge, and editable proposed metadata.
- `parse_review(json_obj) -> list[ImportRow]` — read back the human-edited/confirmed review (only rows the human kept and marked confirm).
- `slug_work_id(title, filename, existing: set[str]) -> str` — stable `work_id` from confirmed title, filename fallback, with a `-2`/`-3` suffix on collision.
- `ingest_import_review(rows, state, run_id, *, copy_file) -> tuple[int, int]` — for each confirmed row, `copy_file(source_path, dest)` into `images/user/`, then merge into `state.candidates[]`:
  - **dedup match** (the row's `qid`/`inst_ids`/`work_id` hits an existing candidate via the existing `dedup_key` rule) → **enrich**: set that candidate's `local_path`; leave `origin` and provenance untouched. Counts as `enriched`.
  - **new work** → append `BoardCandidate(origin="user", local_path=<rel>, first_run=run_id, …)`. Counts as `added`.
  - returns `(added, enriched)`. Pure aside from the injected `copy_file`.

**B. `scripts/state.py` (extend).** Add `local_path` to `BoardCandidate` (above). Add a helper for the user-merge path so `merge_candidates`'s discovered-only assumption stays intact — either `PackageState.merge_user_candidate(bc) -> "added"|"enriched"` or fold the enrich-vs-append logic into `ingest_import_review` using the existing `candidate(work_id)` / `dedup_key` lookups. Discovered-path `merge_candidates` is unchanged.

**C. `scripts/paths.py` (extend).** Add `user_images_dir` → `root/"images"/"user"`, included in scaffold dirs. The import-review artifact lives at the package root (`import-review.json` / `import-review.html`), transient like `selection.json`.

**D. `scripts/gallery.py` (extend).** Render `origin:"user"` candidates from `local_path` (CSS-scaled `<img>`, no derivative). Show an origin badge so the human can tell user images from discovered ones. The `studied ✓` badge (Thrust 1) composes unchanged.

**E. `SKILL.md` (modify).** Document **import** as a re-enterable operation beside discover/select/study:
1. User points the skill at a folder for the current artist study.
2. Claude views each image, emits `{filename, artist, title, date}` guesses.
3. `verify_identification` per image → `build_review` → write `import-review.{json,html}`. **Pause:** human reviews, edits proposed rows, confirms/rejects.
4. `parse_review` → `ingest_import_review` → candidates merged (`origin:"user"` or enriched), `record_run(source="user-import")`, save state.
5. From here the user images are indistinguishable from discovered ones in curation/analysis — except analysis reads their local full-res file.

### Data flow

```
folder ──Claude vision──► {filename,artist,title,date} guesses
                                   │
                  verify_identification (lookup = wikidata/museum_search)
                                   │
        ImportRows: confirmed | proposed | off_artist | unidentified
                                   │
            build_review ──► import-review.{json,html}
                                   │
              human confirms / edits / rejects   ◄── PAUSE
                                   │
                       parse_review (kept + confirmed rows)
                                   │
   ingest_import_review: copy_file → images/user/,  candidates[]:
        dedup match → enrich existing (set local_path)
        new work   → append origin:"user"
                       record_run(source="user-import")
                                   │
        gallery (origin badge) · curation · visual_analysis (local file)
```

## Error handling

- **Empty / unreadable folder** → clear error, no state change.
- **Non-image files** in the folder → skipped (logged), not rows.
- **Image Claude cannot open / identify** → `unidentified`, set aside.
- **`off_artist`** → listed in the review, never ingested; surfaced so the user knows which images were skipped and why.
- **`work_id` collision** → `slug_work_id` appends a numeric suffix; never overwrites an existing candidate.
- **Idempotent re-import** — re-importing the same folder dedups (by matched key / existing `local_path`); already-present works enrich or no-op, `added=0`. Re-running is safe.
- **Partial confirm** — the human may confirm a subset; only kept+confirmed rows are ingested. Rejected/edited-to-empty rows are dropped.
- **Back-compat** — `local_path` defaults `""`; every existing package and discovered candidate loads and round-trips unchanged.

## Testing

pytest on the pure units (no network, no LLM; `lookup` and `copy_file` injected):

- `verify_identification`: `confirmed` when `lookup` corroborates (metadata pulled from record); `proposed` when guess present but no record (`rights="unknown"`, kept guess); `off_artist` when artist differs; `unidentified` on null/empty guess.
- `ingest_import_review`: new row → `origin:"user"` + `local_path` set + `first_run`; dedup match → existing candidate enriched (`local_path` set, `origin`/provenance unchanged, **no** duplicate row); `record_run(source="user-import")` appended; `(added, enriched)` counts correct.
- `slug_work_id`: title-derived; filename fallback when untitled; numeric suffix on collision.
- `ImportRow` / review `to_dict`↔`from_dict` round-trip; `parse_review` keeps only confirmed rows.
- Idempotent re-import → second pass `added=0`.
- `BoardCandidate` round-trip including `local_path`; legacy candidate without the field loads with `local_path=""`.
- `paths.user_images_dir` resolves and scaffolds.

## Worked example — three personal Klee photos

1. **Import** `~/my-klee-pics/` into the Klee study (3 files).
2. **Claude vision:** `senecio.jpg → {Klee, "Senecio", 1922}`, `barn.jpg → {Klee, untitled, ?}`, `miro-misfile.jpg → {Miró, …}`.
3. **Verify:** `senecio` → pipeline corroborates (QID, AIC record, rights) → **confirmed**; `barn` → no record → **proposed** (`rights:"unknown"`); `miro-misfile` → **off_artist**, set aside.
4. **Review:** human opens `import-review.html`, confirms `senecio`, edits `barn`'s title to "Farmhouse study" and confirms it, leaves `miro-misfile` out.
5. **Ingest:** `senecio` already on the board from discovery → **enriched** (its card gains `local_path`, now analyzed from the user's full-res photo); `barn` is new → appended as `origin:"user"`. `runs:[…, run-k source="user-import" added=1 …]`.
6. In the next study session both flow through curation identically; `barn`'s analysis reads `images/user/barn.jpg` directly.
