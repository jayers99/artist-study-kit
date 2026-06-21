# Narrowing Funnel + Skip-Discovery — Design Spec

> Spec B of raw/19 Thrust 3. Spec A (persistent board stars) shipped 2026-06-20 and
> is the funnel's first stage. This spec adds the progressive-zoom narrowing flow and
> the skip-discovery entry switch.

**Date:** 2026-06-20
**Source:** `raw/19-stateful-runs-custom-images-staged-analysis.md` §(a)/(b)
**Builds on:** Spec A (persistent stars, local thumbnail cache, explicit `selected` flag),
Thrust 1 (multi-session `state.json`), the F6 Socratic interview (`curation_interview`).

---

## 1. Goal

Restructure curation as a **progressive-zoom narrowing funnel** that bounds the expensive
Socratic interview to a handful of works, and add a **skip-discovery** entry so a study
session can run over an already-collected board without re-collecting.

One sentence: *scan wide on the small-thumb board, zoom into the selected few at ~2-wide
with full-size images, cut to ≤4, then interview only those.*

## 2. Why now

Spec A made the board persistent and gave selection its own explicit axis. The board can
now grow large across runs, and deep visual analysis + the Socratic interview are expensive
enough to cap at ~3–4 works per session (raw/19 §(b)). A staged zoom — images grow and
dwell time grows as the cut narrows — both enforces that cap and matches how real curation
feels (fast wide scan → slow close looking). Skip-discovery (raw/19 §(a)) decouples "study"
from "collect" so one collected board feeds many study sessions.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Funnel shape | **One self-contained page**, superseding the Spec-A board. No skill round-trip mid-flow. |
| Stage 2 layout | **Same grid, zoomed** to ~2-wide, filtered to the selected set. Not a different layout — a zoom level. |
| Stage count | **Two** stages: board (small, many cols) → zoom (~2-wide, selected only). |
| Zoom image | **Full-size where available**, hotlinked display-only for the selected few; cached thumb as fallback. |
| Cap | **≤4** (constant `MAX_STUDY = 4`). Hard-enforced in JS (Commit disabled outside 1..MAX) and validated on ingest. |
| Narrow cut | Exported as `study-set.json`; becomes the session `study_set`. **Everything expensive — high-res resolve + visual analysis + interview — runs on this set only.** |
| Wide cut | Snapshotted on **Next** (frozen, not mutated by stage-2 narrowing); exported as Spec A's `selection.json`; recorded as the session `selected`. It is a session *record* of what was considered, not what gets high-res. |
| Skip-discovery | A **study mode** that skips `image_discovery` when `state.candidates` is non-empty. |

## 4. The funnel page (`gallery.py`)

The Spec-A board template (`_THUMB_TEMPLATE`, built by `build_thumbnail_gallery`) **evolves
into the funnel**. Stage 1 is unchanged in behavior (stars/filter/sort/select). Two
additions:

- **Stage transition.** A **Next →** button (enabled once ≥1 work is selected) **snapshots
  the wide cut** — `wideCut = candidates.filter(c => selected[c])` is frozen into a separate
  list — then re-renders the grid as the **zoom stage**: CSS grid `minmax` raised so cells
  are ~2-wide, the card list filtered to `wideCut`, each card showing its full-size image.
  A **← Back** returns to the full board with state intact (the snapshot is discarded on
  Back; re-taken on the next Next).
- **Narrowing on stage 2.** The `select` toggle still works; **de-selecting** a card removes
  it from the live narrow set (`studySet = wideCut ∩ still-selected`). You only ever narrow
  *within* the snapshot — stage 2 shows only `wideCut` works. The wide snapshot is not
  mutated by this.
- **Commit.** Enabled only when the live narrow count is in `1..MAX_STUDY`. Commit downloads
  three files: `stars.json` (Spec A, every candidate); `selection.json` (Spec A shape, with
  `selected = true` for every work in the frozen **wideCut** — the session record); and
  **`study-set.json`** = `{artist, study_set: [work_id, …]}` (the works still selected at
  commit — the narrow cut, `studySet ⊆ wideCut`, `len ≤ MAX_STUDY`). A status line names the
  three files.

`MAX_STUDY` is a single JS constant (4). The zoom-stage `<img>` uses each candidate's
`full_url` (see §7) with `onerror` falling back to the local `image_rel` (cached thumb).

> File-size note: `_THUMB_TEMPLATE` is already large. If adding the second stage pushes
> `gallery.py` past comfortable size, split the board template/JS into a sibling module
> (`gallery_board.py`) during implementation; do not pre-split.

## 5. Narrow-cut data (`selection.py`)

```python
def parse_study_set(data: dict, *, max_study: int = 4) -> list[str]:
    """Read study-set.json -> the ordered narrow-cut work_ids.
    Truncates to max_study (a >MAX board can't silently over-fill the interview)."""
```

- Returns `data["study_set"]` as a list of work_ids, truncated to `max_study`.
- A loader `load_study_set(path, artist, *, max_study=4) -> list[str]` reads the file,
  checks `artist`, returns the ids (raises on artist mismatch, mirroring `load_selection`).

The session records both cuts (fields already on `StudySession`):
`record_session(theme, grouping, selected=<wide>, study_set=<narrow>, outputs=...)`.

## 6. Downstream bounded to the study set (SKILL.md + a `resolve` filter)

Everything expensive after the funnel runs on the **study_set** (≤4), not the wide cut.
The wide `selected` is a session record; the study_set is what we actually study.

```python
sel = load_selection(sp.selection_json, "<ARTIST>")            # wide cut (record)
study_set = load_study_set(sp.study_set_json, "<ARTIST>")      # narrow cut (≤4)
rows = [r for r in selected_rows(sel) if r.work_id in study_set]

# high-res resolution: bounded to the study set
resolve_selection(sel, sp.selected_dir, only=set(study_set))
# interview: bounded to the study set
queue = build_queue(rows, work_meta)
```

- `resolve_selection` gains an optional `only: set[str] | None = None`; when given, it
  resolves only `selected_rows` whose `work_id ∈ only`. `None` preserves Spec A behavior
  (resolve all selected) for callers that don't use the funnel.
- `apply_selection` (legacy local path) takes the same `only` filter for symmetry.
- `build_queue` is unchanged — the caller just hands it the study_set rows.
- The session records both: `selected` = wide cut, `study_set` = narrow cut.

## 7. Full-size display URL (`museum_search.py`)

```python
def display_url(candidate) -> str:
    """Best-effort largest display image for close looking (hotlinked, display-only).
    IIIF sources -> swap the thumbnail size segment for a full/large size;
    otherwise fall back to thumbnail_url."""
```

- For IIIF museums (AIC, Met, etc.), derive from the existing `thumbnail_url` by replacing
  the IIIF size segment (e.g. `/full/400,/0/default.jpg` → `/full/843,/0/default.jpg`).
  843 (not `full`) keeps the fetch bounded while still crisp at ~2-wide.
- For non-IIIF / `origin:"user"` candidates, return `local_path` (user) or `thumbnail_url`.
- Pure string derivation, no network; the browser does the hotlink. Rights-agnostic:
  this is display, not the rights-gated download in `resolve.py`.

The funnel payload (`build_thumbnail_gallery`) gains `full_url := display_url(c)` per card.

## 8. Skip-discovery switch (SKILL.md + `state.py` guard)

- The skill gains a **study mode** (entered by the human asking to "study"/"skip
  discovery", or re-entering an artist whose package already has candidates).
- Guard: `PackageState.has_candidates() -> bool` (true when `candidates` non-empty).
- Orchestration (SKILL.md): in study mode, if `has_candidates()`, **skip `image_discovery`**
  and go straight to building the funnel over `state.candidates`; if empty, tell the human
  there's nothing to study and run discovery first.
- This is additive: the normal collect→curate flow is unchanged; study mode is an entry
  that starts at the funnel.

## 9. Paths (`paths.py`)

Add `study_set_json` → `root / "study-set.json"` (parallel to `selection_json`).

## 10. Testing (TDD, pytest)

- `display_url`: IIIF size-segment swap for AIC/Met thumbnail URLs; non-IIIF/user
  fallback to `local_path`/`thumbnail_url`.
- `parse_study_set` / `load_study_set`: returns ordered ids; truncates to `max_study`;
  artist-mismatch raises.
- Interview rows filtered to study_set: a `selected` row NOT in study_set is excluded from
  the queue; the ≤4 in study_set are included.
- `resolve_selection(only=…)`: resolves only study_set works; `only=None` resolves all
  selected (Spec A behavior unchanged). Same for `apply_selection(only=…)`.
- Session records both cuts (`selected` wide ⊇ `study_set` narrow); a work in the wide cut
  but dropped at stage 2 stays in `selection.json`/`selected` but is absent from
  `study-set.json`/`study_set`.
- `has_candidates()` true/false; skip-discovery guard picks funnel vs collect.
- Funnel template markers: `Next`, `Commit`, the zoom-stage grid sizing, `study-set.json`,
  the `MAX_STUDY` cap gate, `full_url` used on the zoom `<img>` with thumb fallback.
- `study_set_json` path resolves under the package root.

## 11. Out of scope / deferred

- **Re-query duplicate handling** (already logged in `TODO.md`).
- **"Additional research needed" → NotebookLM loop** (raw/19 §(b).4 open question): the
  interview's study briefs already capture "what research is needed"; wiring that back into
  the deep-research loop is a future hook, not built here.
- No third/adaptive zoom stage (locked to two).
- No change to the rights-gated `resolve.py` download path (full-size here is display-only).
