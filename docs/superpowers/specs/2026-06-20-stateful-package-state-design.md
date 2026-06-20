# Stateful Package State — Design Spec

**Date:** 2026-06-20
**Status:** approved (design) → ready for implementation plan
**Source feedback:** `raw/19-stateful-runs-custom-images-staged-analysis.md`, **Thrust 1** (persistent state + multiple runs). Thrust 1 is the backbone the doc says to "design first."
**Related stages:** every stage reads/writes state; closest to [[stage-image-discovery]] (discovery runs) and [[stage-curation]] / [[stage-curation-interview]] (study sessions).

## Motivation

Today the skill is a single linear pass. `state.json` records only `{artist, completed:[stages]}` — which stages have run, nothing about *what they produced*. The board of candidate images is never persisted as data: image discovery renders it into `gallery.html`, and it only becomes structured data in `selection.json` *after* the human exports their picks. There is no accumulating, mergeable candidate set.

A real study practice is iterative and spread across sessions: *collect images Monday, study three Tuesday, study three more — grouped a different way — next week.* That requires the package to **keep state across runs**:

- **Re-runnable discovery** — run discovery again later (after a Wikidata outage clears, or to add a source) and have new candidates **merge into** the existing board instead of replacing it.
- **Repeatable study** — return to the same artist on another day and study a different subset, **including works already studied**, grouped along a new dimension (subject, media, technique).

This spec defines that persistent state model and the operations over it. It is the foundation the other two raw/19 thrusts build on.

## Goals

- A durable per-artist **package state** that records the accumulating candidate board, the history of discovery runs, and the history of study sessions.
- Discovery becomes **idempotent and mergeable**: re-running merges new candidates by stable key, never duplicating or clobbering.
- Study sessions are **first-class and repeatable**: a work may be studied many times, each session grouped along its own dimension, with per-session outputs that never overwrite a prior study.
- **Backward compatible**: existing `{artist, completed}` packages (Klee, Miró) load and migrate without manual surgery.
- Keep the existing resumable per-stage flow (`completed[]` + pause gates) intact.

## Non-goals (separate specs)

- **Thrust 2 — custom image injection** (user's own folder → reverse-image-search → metadata enrichment). This spec only reserves the seam: every candidate carries `origin: "discovered" | "user"`. No ingestion is built here; nothing sets `origin:"user"` yet.
- **Thrust 3 — narrowing funnel + gallery changes** (progressive-zoom two-cut funnel, drop star ratings for binary select, year-sort, skip-discovery switch, the precise per-session output-file layout). This spec records what the funnel *produces* (`selected` wide cut, `study_set` narrow cut, `grouping`) but does not build the funnel UX. Star `rating` stays untouched so the in-flight F6 build is not pre-broken.
- No change to *how* any stage does its work — only to what it persists and reads.

## Decisions (locked)

| Decision | Choice | Rationale |
| --- | --- | --- |
| State location | **One fat `state.json`** holding `{artist, completed, runs[], candidates[], sessions[]}` | User's call: fewer files. Code still models `BoardCandidate`/`DiscoveryRun`/`StudySession` as separate dataclasses serialized into the one file, so modules stay focused. |
| `selection.json` role | **Transient export/handoff, ingested into state** | The gallery writes `selection.json`; the skill ingests it into a session record. `state.json` is the source of truth. |
| "Studied" semantics | **Derived badge, never a gate** | A work is "studied" iff it appears in any past session's `study_set`. Selection is never constrained; a work can be studied repeatedly along different dimensions. GUI shows a ✓ badge with zero workflow effect. |
| Rating/selection ownership | **Per-session, not per-candidate** | The same image can be picked into many sessions and grouped differently each time, so a permanent `rating` on the candidate would be clobbered. The candidate persists only identity + metadata + origin. |
| Merge key | **QID primary, `inst_ids` fallback** | Reuses the dedup rule already proven in `wikidata.merge_boards`: a candidate with a QID dedups only against QIDs; without one, dedups by institution id. |
| Output layout | **Per-session pointers** (`sessions/<id>/…`) | Re-studying a work along a new dimension must not overwrite the prior brief/analysis. State holds only the pointers; Thrust 3 fixes the on-disk layout. |

## Architecture

### `state.json` schema

```json
{
  "artist": "Paul Klee",
  "completed": ["background", "source_grading", "style_definition",
                "works_inventory", "image_discovery"],
  "runs": [
    { "id": "run-1", "at": "2026-06-20T14:02:00", "source": "wikidata+aic",
      "added": 92, "merged": 0, "total": 92, "degraded": false }
  ],
  "candidates": [
    { "work_id": "exotics", "title": "Exotics", "date": "1939", "museum": "aic",
      "thumbnail_url": "https://www.artic.edu/iiif/2/edac.../full/400,/0/default.jpg",
      "source_url": "https://www.artic.edu/artworks/134057",
      "rights": "in_copyright", "medium": "", "qid": "",
      "inst_ids": [["aic", "134057"]],
      "origin": "discovered", "first_run": "run-1" }
  ],
  "sessions": [
    { "id": "sess-1", "at": "2026-06-21T09:00:00", "kind": "study",
      "theme": "facial economy & line", "grouping": "technique",
      "selected": ["exotics", "women-harvesting", "mosaic-like", "der-paukenspieler"],
      "study_set": ["exotics", "women-harvesting", "mosaic-like"],
      "outputs": { "study_briefs": "study-briefs.json", "analysis": "analysis.md" } }
  ]
}
```

### Components

**A. `scripts/state.py` (rewrite the dataclass layer; keep `STAGES`/`PAUSE_GATES`).**

- `STAGES` and `PAUSE_GATES` are unchanged. The stage-completion API (`next_stage`, `is_complete`, `mark_complete`, `gate_for`) is preserved on the new aggregate so SKILL.md's existing one-liners keep working.
- New dataclasses:
  - `BoardCandidate` — persistent identity + metadata: `work_id, title, date, museum, thumbnail_url, source_url, rights, medium, qid, inst_ids, origin, first_run`. Field set mirrors `museum_search.ThumbnailCandidate` plus `origin` (default `"discovered"`) and `first_run`.
  - `DiscoveryRun` — `id, at, source, added, merged, total, degraded`.
  - `StudySession` — `id, at, kind, theme, grouping, selected, study_set, outputs`. `grouping ∈ {"subject","media","technique","other"}`; `kind` defaults `"study"`.
  - `PackageState` — aggregate: `artist, completed, runs, candidates, sessions`, plus the operations below and `to_dict`/`from_dict`/`save`/`load`.

- Operations on `PackageState`:
  - `merge_candidates(new: list[ThumbnailCandidate], run_id: str) -> tuple[int, int]` — merge a discovery board into `candidates[]` by the QID/`inst_ids` rule; returns `(added, merged)`. New entries get `first_run=run_id` and `origin="discovered"`; existing entries are left as-is (idempotent — re-running the same discovery adds 0). Pure; no I/O.
  - `record_run(source, added, merged, total, *, degraded=False, now=None) -> DiscoveryRun` — append a run with id `run-{n}` and timestamp (`now` injectable for tests; defaults to `datetime.now().isoformat(timespec="seconds")`).
  - `record_session(theme, grouping, selected, study_set, outputs, *, kind="study", now=None) -> StudySession` — append a session with id `sess-{n}`.
  - `studied_work_ids() -> set[str]` — derived: `{wid for s in sessions for wid in s.study_set}`. Drives the gallery ✓ badge.
  - `candidate(work_id) -> BoardCandidate | None` — lookup helper.

**B. `scripts/selection.py` (add ingest, no schema break).** Add
`ingest_selection(selection, *, liked_only=True) -> tuple[list[str], list[str]]` returning `(selected_ids, study_set_ids)` from an exported `selection.json`: `selected_ids` = all liked (rating ≥ 4, reusing `liked()`), `study_set_ids` defaults equal to `selected_ids` (Thrust 3's narrowing later supplies a smaller `study_set`). The existing `Rating`/`validate_selection`/`liked` stay as the F6 spec leaves them — this spec does not touch star fields.

**C. `scripts/paths.py` (extend).** Add `sessions_dir` → `root/"sessions"`, a `session_dir(session_id)` helper → `root/"sessions"/session_id`, and include `"sessions"` in `_SCAFFOLD_DIRS`. The per-session output files (`study-briefs.json`, `analysis.md`, etc.) keep their existing leaf names; Thrust 3 decides when they move under `sessions/<id>/`. State stores whatever pointer the stage reports.

**D. Migration — `scripts/state.py::migrate_legacy`.**
`migrate_legacy(state_dict, selection_dict|None) -> PackageState`:
- A legacy `{artist, completed}` (no `runs/candidates/sessions`) loads via `from_dict` with those three lists empty — so old packages open without error even with no migration step.
- When a `selection.json` is also present, `migrate_legacy` seeds `candidates[]` from its rows (one `BoardCandidate` per `Rating`, `origin="discovered"`, `first_run="run-0"`) and records a synthetic `run-0` (`source="legacy-import"`). Liked rows seed one `sess-0` so prior study work is represented. This is opt-in (run once per old package), not automatic on load.

**E. `SKILL.md` (modify).** Document the multi-run mental model and wire the operations:
- **Image discovery** — after building the merged board, call `PackageState.merge_candidates(board, run_id)` then `record_run(...)`, save state. Re-entry: if `candidates[]` is non-empty the board already exists; a fresh discovery merges into it rather than starting over. Record `degraded=True` when Wikidata is unavailable (F1 hook) so a later re-run can upgrade.
- **Study session** — when the human exports `selection.json`, `ingest_selection` it, then `record_session(theme, grouping, selected, study_set, outputs)`. The skill asks the human for the session's grouping dimension + theme label. The gallery marks `studied_work_ids()` with a ✓ badge but never filters them out.
- State the explicit shift: the skill is no longer one linear `run` but a set of **re-enterable operations** (discover · select · study) over a persisted package.

### Data flow

```
discovery run ──► merge_candidates() ──► candidates[]      record_run() ──► runs[]
                                            │
human opens gallery.html (rendered from candidates[], ✓ badge from studied_work_ids())
                                            │
exports selection.json ──► ingest_selection() ──► (selected, study_set)
                                            │
                                  record_session(theme, grouping, …) ──► sessions[]
                                            │
            curation_interview / visual_analysis / study_retention
            read the session's study_set, write per-session outputs,
            session.outputs records the pointers
```

## Error handling & resume

- **Back-compat load:** a legacy `state.json` lacking the new keys loads cleanly (empty `runs/candidates/sessions`); `artist`-mismatch still raises as today.
- **Idempotent discovery:** re-running discovery with the same board yields `(added=0, merged=N)` and appends a run with `added=0` — no duplicate candidates, no clobbered metadata.
- **Empty board:** `merge_candidates([])` is a no-op returning `(0, 0)`.
- **Atomic save:** `save()` writes the whole file (same as today); the candidate array is small (≤ ~200 rows) so full rewrite is fine.
- **Unknown grouping:** `record_session` rejects a `grouping` outside the allowed set with a clear `ValueError`.
- **Studied work re-selected:** fully supported — appears in a new session's `study_set`, gets a second per-session output, shows the ✓ badge. No dedup, no block.

## Testing

pytest on the pure units (no network, no LLM):

- `merge_candidates`: QID dedup; `inst_ids` fallback when no QID; idempotent re-merge (`added=0`); two distinct works sharing title+year but different QIDs both kept; `first_run`/`origin` set on new entries only.
- `record_run` / `record_session`: monotonic ids (`run-1`, `run-2`…; `sess-1`…), injected `now`, `grouping` validation.
- `studied_work_ids`: union across multiple sessions; a work in two sessions appears once.
- `to_dict`/`from_dict` round-trip including `runs/candidates/sessions` and tuple-shaped `inst_ids`.
- Back-compat: a legacy `{artist, completed}` dict loads with empty new lists; `next_stage`/`mark_complete` still behave.
- `migrate_legacy`: seeds candidates + `run-0` from a `selection.json`; liked rows seed `sess-0`; no `selection.json` → empty board.
- `ingest_selection`: liked filter, `study_set` defaults to `selected`.
- `paths`: `sessions_dir` / `session_dir` resolve and scaffold.

## Worked example — Klee across two sessions

1. **Run 1 (today):** discovery merges 92 AIC candidates → `candidates[]` (92), `runs:[run-1 added=92]`.
2. **Session 1 (Tue):** human likes 6, narrows to 3 (*Exotics*, *Women Harvesting*, *Mosaic-Like*), grouping `technique`. `sessions:[sess-1 study_set=[…3]]`; those three now carry the ✓ badge.
3. **Run 2 (Wed):** Wikidata is back; re-run discovery adds 14 Commons PD candidates → `merge_candidates` returns `(14, 78)`, `runs:[…, run-2 added=14]`. No duplicates.
4. **Session 2 (next week):** human regroups by `subject` ("gardens"), picks 4 including the already-studied *Mosaic-Like* again — a second brief is written under `sessions/sess-2/`, the first is untouched.
