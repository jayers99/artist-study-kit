# Socratic Curation Interview — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the gallery's three typed rationale fields with a new resumable pipeline stage whose output is a structured `study-briefs.{json,md}`, produced by an AI-led Socratic interview (the dialogue is SKILL.md prose; only queueing/serialization/validation are scripted).

**Architecture:** Split curation into visual rating (`gallery.html` → `selection.json`, rationale fields removed) and a new `curation_interview` stage between `image_discovery` and `preference_synthesis`. New pure module `scripts/curation_interview.py` owns the testable core: build an ordered interview queue (merging study→final pairs), (de)serialize study briefs, write the artifacts, and gate completeness. Downstream stages consume `study-briefs.json` instead of the old gate fields.

**Tech Stack:** Python 3.12, uv, pytest. Frozen dataclasses with tuple collection fields. Obsidian-native markdown via `scripts._md.frontmatter`.

**Spec:** `docs/superpowers/specs/2026-06-20-socratic-curation-interview-design.md`.

## Global Constraints

- Venv lives **outside iCloud**: prefix Python/pytest commands with `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit"`.
- Tests run from the repo root: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest <path> -v`. `pyproject.toml` sets `pythonpath=["skill"]` and `testpaths=["tests"]`, so imports are `from scripts.<name> import ...`.
- Frozen dataclasses only; collection fields are **tuples**, not lists (frozen-safe).
- Markdown is Obsidian-native: each paragraph/list-item on a single physical line (no hard-wrapping); kebab-case filenames.
- Interview dialogue contract (SKILL.md, Task 9): the AI asks questions and reflects only — it **must not state the lesson** for the human. Friction is the feature.
- Out of scope (separate specs): WDQS resilience (F1), reproduction/posthumous attribution filter (F3), zero-PD board notice (F5).
- Commits: brief single-line messages, focused on why.

---

### Task 1: Insert the `curation_interview` stage into pipeline state

**Files:**
- Modify: `skill/scripts/state.py:9-24`
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `STAGES` now contains `"curation_interview"` at index 5 (between `"image_discovery"` and `"preference_synthesis"`); `PAUSE_GATES` has a `"curation_interview"` entry, and `"preference_synthesis"`'s gate text changes to reference study briefs.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
from scripts.state import PipelineState, STAGES, PAUSE_GATES


def test_curation_interview_sits_between_discovery_and_synthesis():
    i = STAGES.index("curation_interview")
    assert STAGES[i - 1] == "image_discovery"
    assert STAGES[i + 1] == "preference_synthesis"


def test_curation_interview_is_gated_on_selection_json():
    assert "selection.json" in PAUSE_GATES["curation_interview"]


def test_preference_synthesis_gate_now_references_study_briefs():
    assert "study-briefs.json" in PAUSE_GATES["preference_synthesis"]


def test_next_stage_reaches_curation_interview_after_discovery():
    s = PipelineState(artist="X", completed=[
        "background", "source_grading", "style_definition",
        "works_inventory", "image_discovery",
    ])
    assert s.next_stage == "curation_interview"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -v`
Expected: FAIL (`curation_interview` not in STAGES; KeyError on PAUSE_GATES).

- [ ] **Step 3: Edit `skill/scripts/state.py`**

Replace the `STAGES` tuple and `PAUSE_GATES` dict (lines 9-24) with:

```python
STAGES: tuple[str, ...] = (
    "background",
    "source_grading",
    "style_definition",
    "works_inventory",
    "image_discovery",
    "curation_interview",
    "preference_synthesis",
    "visual_analysis",
    "study_retention",
)

# Stages that cannot start until the human supplies an artifact.
PAUSE_GATES: dict[str, str] = {
    "curation_interview": "curation complete: selection.json present",
    "preference_synthesis": "study briefs ready: study-briefs.json present",
    "visual_analysis": "study set chosen from the ranked funnel",
}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -v`
Expected: PASS (all, including pre-existing state tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit -m "feat: add curation_interview stage between discovery and synthesis"
```

---

### Task 2: Migrate `selection.py` — drop rationale fields, add title/date/medium

**Files:**
- Modify: `skill/scripts/selection.py:1-77`
- Test: `tests/test_selection.py`

**Interfaces:**
- Produces: `Rating` no longer has `thesis`/`anchor_trait`/`handoff_note`; it gains `title: str = ""`, `date: str = ""`, `medium: str = ""`. `validate_selection` checks only rating range (0-5) and `work_id` presence. `parse_selection` reads `title`/`date`/`medium` and ignores any stale gate keys.
- Consumes: nothing new.

- [ ] **Step 1: Write the failing test**

Replace gate-related tests in `tests/test_selection.py` with these (delete any test asserting gate-text validation errors):

```python
from scripts.selection import Rating, Selection, parse_selection, validate_selection


def test_liked_work_needs_no_rationale():
    sel = Selection(artist="X", ratings=[Rating(work_id="w", iiif_token="t", image_rel="r", rating=5)])
    assert validate_selection(sel) == []  # gate removed: a liked work with no rationale is valid


def test_rating_out_of_range_still_flagged():
    sel = Selection(artist="X", ratings=[Rating(work_id="w", iiif_token="t", image_rel="r", rating=7)])
    assert any("out of range" in e for e in validate_selection(sel))


def test_missing_work_id_still_flagged():
    sel = Selection(artist="X", ratings=[Rating(work_id="", iiif_token="t", image_rel="r", rating=2)])
    assert any("missing work_id" in e for e in validate_selection(sel))


def test_parse_reads_title_date_medium_ignores_stale_gate():
    data = {"artist": "X", "ratings": [{
        "work_id": "w", "iiif_token": "t", "image_rel": "r", "rating": 5,
        "title": "Senecio", "date": "1922", "medium": "oil on gauze",
        "thesis": "stale", "anchor_trait": "stale",  # must be ignored, not error
    }]}
    r = parse_selection(data).ratings[0]
    assert (r.title, r.date, r.medium) == ("Senecio", "1922", "oil on gauze")
    assert not hasattr(r, "thesis")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_selection.py -v`
Expected: FAIL (Rating still has gate fields / validate still gates).

- [ ] **Step 3: Edit `skill/scripts/selection.py`**

Update the module docstring's schema line to drop the gate fields and add title/date/medium. Replace the `_GATE_FIELDS` constant, `Rating`, `parse_selection`, and `validate_selection`:

Delete line 17 (`_GATE_FIELDS = (...)`).

Replace `Rating` (lines 20-33) with:

```python
@dataclass(frozen=True)
class Rating:
    work_id: str
    iiif_token: str
    image_rel: str
    rating: int
    title: str = ""
    date: str = ""
    medium: str = ""
    qid: str = ""
    source_url: str = ""
    museum: str = ""
    rights: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
```

Replace `parse_selection`'s per-rating construction (the `Rating(...)` block, lines 45-58) with:

```python
        Rating(
            work_id=str(r.get("work_id", "")),
            iiif_token=str(r.get("iiif_token", "")),
            image_rel=str(r.get("image_rel", "")),
            rating=int(r.get("rating", 0)),
            title=str(r.get("title", "")),
            date=str(r.get("date", "")),
            medium=str(r.get("medium", "")),
            qid=str(r.get("qid", "")),
            source_url=str(r.get("source_url", "")),
            museum=str(r.get("museum", "")),
            rights=str(r.get("rights", "")),
            inst_ids=tuple((str(p[0]), str(p[1])) for p in r.get("inst_ids", []) if len(p) == 2),
        )
```

Replace `validate_selection` (lines 64-77) with:

```python
def validate_selection(sel: Selection) -> list[str]:
    """Return human-readable errors; empty list means the selection is valid.

    Rationale (thesis/anchor/handoff) is no longer gated here — it is produced by the
    curation_interview stage as study-briefs.json. This validates only the visual export.
    """
    errors: list[str] = []
    for r in sel.ratings:
        label = r.work_id or r.iiif_token or "<unknown>"
        if not (0 <= r.rating <= 5):
            errors.append(f"{label}: rating {r.rating} out of range 0-5")
        if not r.work_id:
            errors.append(f"{label}: missing work_id")
    return errors
```

- [ ] **Step 4: Update any other Rating constructions that pass removed fields**

Run: `rg -n "thesis=|anchor_trait=|handoff_note=" tests/ skill/scripts/`
For each hit constructing a `Rating(...)`, delete those keyword args. (Expected: a few in `tests/test_selection.py` already handled above; check `tests/test_resolve.py`.)

- [ ] **Step 5: Run the affected suites**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_selection.py tests/test_resolve.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/selection.py tests/test_selection.py tests/test_resolve.py
git commit -m "feat: selection.json carries title/date/medium, no rationale gate"
```

---

### Task 3: Capture `medium` on discovery candidates (AIC)

**Files:**
- Modify: `skill/scripts/museum_search.py:22,26-36,80-108`
- Test: `tests/test_museum_search.py`

**Interfaces:**
- Produces: `ThumbnailCandidate` gains `medium: str = ""`; `parse_aic_search` fills it from AIC `medium_display`; `AIC_FIELDS` requests `medium_display`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_museum_search.py`. First extend the `AIC_WORKS` fixture's first data row with a medium, then assert:

```python
def test_aic_candidate_carries_medium():
    payload = {
        "data": [{"id": 7, "title": "Senecio", "image_id": "abc", "date_display": "1922",
                  "is_public_domain": False, "artist_title": "Paul Klee",
                  "medium_display": "Oil on gauze"}],
        "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
    }
    from scripts.museum_search import parse_aic_search
    assert parse_aic_search(payload)[0].medium == "Oil on gauze"


def test_aic_fields_request_medium():
    from scripts.museum_search import AIC_FIELDS
    assert "medium_display" in AIC_FIELDS
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_museum_search.py -v`
Expected: FAIL (`medium` attribute missing; `medium_display` not in AIC_FIELDS).

- [ ] **Step 3: Edit `skill/scripts/museum_search.py`**

Line 22 — add `medium_display` to the fields string:

```python
AIC_FIELDS = "id,title,image_id,date_display,is_public_domain,artist_title,medium_display"
```

In `ThumbnailCandidate` (the dataclass at lines 26-36), add a `medium` field with a default, placed before `qid` so existing positional/keyword callers are unaffected:

```python
    rights: str  # public_domain | in_copyright | unknown
    medium: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
```

In `parse_aic_search`, add `medium=` to the `ThumbnailCandidate(...)` built at lines 96-106:

```python
                rights="public_domain" if d.get("is_public_domain") else "in_copyright",
                medium=str(d.get("medium_display") or ""),
                inst_ids=(("aic", str(d.get("id"))),),
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_museum_search.py tests/test_wikidata.py -v`
Expected: PASS. (Wikidata's `to_thumbnail_candidates` builds `ThumbnailCandidate` without `medium`, relying on the `""` default — confirm `test_wikidata.py` still passes.)

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/museum_search.py tests/test_museum_search.py
git commit -m "feat: capture medium on AIC thumbnail candidates"
```

---

### Task 4: Strip rationale fields from the gallery; export title/date/medium

**Files:**
- Modify: `skill/scripts/gallery.py` (board: `build_thumbnail_gallery:85-101` + `_THUMB_TEMPLATE:256-398`; legacy: `_TEMPLATE` gate at 125-147 and 142-147, export at 231-247)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Produces: `build_thumbnail_gallery` payload includes `"medium"`; the board's Export writes `title`/`date`/`medium` and **no** `thesis`/`anchor_trait`/`handoff_note`; the board has no gate inputs.
- Consumes: `ThumbnailCandidate.medium` (Task 3).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gallery.py`:

```python
from scripts.museum_search import ThumbnailCandidate
from scripts.gallery import build_thumbnail_gallery


def _cand():
    return ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="http://x/t.jpg", source_url="http://x/9",
        date="1922", rights="in_copyright", medium="Oil on gauze",
        qid="Q1", inst_ids=(("aic", "9"),),
    )


def test_board_payload_includes_medium():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    assert '"medium": "Oil on gauze"' in html


def test_board_has_no_rationale_gate():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    assert "data-gate" not in html
    assert "thesis" not in html
    assert "anchor_trait" not in html
    assert "handoff_note" not in html


def test_board_export_carries_title_date_medium():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    # export object source in the embedded template
    assert "title: c.title" in html
    assert "date: c.date" in html
    assert "medium: c.medium" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: FAIL (medium not in payload; `data-gate`/`thesis` still present).

- [ ] **Step 3: Add `medium` to the board payload**

In `build_thumbnail_gallery` (lines 85-99), add `"medium": c.medium,` to the payload dict (e.g. after the `"date"` line):

```python
            "title": c.title,
            "museum": c.museum,
            "date": c.date,
            "medium": c.medium,
            "rights": c.rights,
```

- [ ] **Step 4: Remove the gate from `_THUMB_TEMPLATE`**

In `_THUMB_TEMPLATE`:

1. Delete the gate CSS rules (lines 281-284):
```css
  .gate { display: none; margin-top: 4px; }
  .card.liked .gate { display: block; }
  .gate input, .gate textarea { width: 100%; box-sizing: border-box; background: #222;
           color: #eee; border: 1px solid #444; font-size: 11px; margin-top: 3px; }
```

2. In the `card.innerHTML` assignment (render()), delete the gate block (the `'<div class="gate">' … '</div>' +` lines, 341-345) so the card ends after the `source` anchor:
```javascript
        '<a class="src" href="' + c.source_url + '" target="_blank">source \\u2197</a>' +
      '</div>';
```

3. In `bind()`, delete the entire `document.querySelectorAll("[data-gate]")...` block (lines 361-368). Keep the `.star` binding.

4. In the comment on line 304, change `// token -> {rating, thesis, anchor_trait, handoff_note}` to `// token -> {rating}`.

5. Replace the Export ratings map (lines 375-384) with one that carries title/date/medium and drops the gate fields:
```javascript
  const ratings = DATA.candidates.map(c => {
    const s = state[c.iiif_token] || {rating: 0};
    return {
      work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
      title: c.title, date: c.date, medium: c.medium,
      source_url: c.source_url, museum: c.museum, rights: c.rights,
      qid: c.qid, inst_ids: c.inst_ids, rating: s.rating || 0,
    };
  });
```

- [ ] **Step 5: Remove the gate from the legacy `_TEMPLATE` (consistency)**

In `_TEMPLATE`:

1. Delete the `#gate` CSS (lines 125-127).
2. Delete the `<div id="gate"> … </div>` block (lines 142-147).
3. Delete the `renderGate()` function (lines 200-212) and both calls to it (in `openDetail`, line 182; in `rate`, line 219).
4. Change the state comment (line 153) to `// key -> {rating}`.
5. Replace the Export ratings map (lines 232-239) with:
```javascript
  const ratings = DATA.candidates.map(c => {
    const s = state[key(c)] || {rating: 0};
    return {
      work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
      rating: s.rating || 0,
    };
  });
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: PASS. (If a pre-existing test asserted gate markup, delete it — the gate is intentionally gone.)

- [ ] **Step 7: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit -m "feat: gallery is visual-only; export carries title/date/medium"
```

---

### Task 5: New module — `StudyTarget` + `build_queue`

**Files:**
- Create: `skill/scripts/curation_interview.py`
- Test: `tests/test_curation_interview.py`

**Interfaces:**
- Consumes: `scripts.selection.Rating` (has `work_id`, `rating`, `title`, `date`, `medium`, `source_url`).
- Produces: `StudyTarget(work_id, title, year, medium, cluster, source_url, members: tuple[str,...])`; `build_queue(liked_ratings: list[Rating], work_meta: dict[str, dict]) -> list[StudyTarget]`. `work_meta` maps `work_id -> {"cluster": str, "studyability": int, "study_for": str}`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_curation_interview.py`:

```python
from scripts.selection import Rating
from scripts.curation_interview import StudyTarget, build_queue


def _r(work_id, date="1930", title=None):
    return Rating(work_id=work_id, iiif_token="t", image_rel="r", rating=5,
                  title=title or work_id, date=date, source_url=f"http://x/{work_id}")


def test_queue_orders_by_cluster_then_studyability_desc():
    liked = [_r("a"), _r("b"), _r("c")]
    meta = {
        "a": {"cluster": "grid", "studyability": 3},
        "b": {"cluster": "grid", "studyability": 5},
        "c": {"cluster": "line", "studyability": 4},
    }
    ids = [t.work_id for t in build_queue(liked, meta)]
    assert ids == ["b", "a", "c"]  # grid (5 then 3), then line


def test_study_for_pair_is_merged_into_one_target():
    liked = [_r("exotics"), _r("sales-woman")]
    meta = {
        "exotics": {"cluster": "late", "studyability": 4},
        "sales-woman": {"cluster": "late", "studyability": 4, "study_for": "exotics"},
    }
    queue = build_queue(liked, meta)
    assert [t.work_id for t in queue] == ["exotics"]
    assert queue[0].members == ("exotics", "sales-woman")


def test_work_without_meta_sorts_last_without_crashing():
    liked = [_r("known"), _r("orphan")]
    meta = {"known": {"cluster": "grid", "studyability": 2}}
    queue = build_queue(liked, meta)
    assert [t.work_id for t in queue] == ["known", "orphan"]
    assert queue[-1].cluster == ""


def test_target_carries_display_facts():
    liked = [_r("senecio", date="1922", title="Senecio")]
    queue = build_queue(liked, {"senecio": {"cluster": "grid", "studyability": 5}})
    t = queue[0]
    assert (t.title, t.year, t.cluster, t.source_url) == ("Senecio", "1922", "grid", "http://x/senecio")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Create `skill/scripts/curation_interview.py`**

```python
"""Curation-interview stage: turn rated works into ordered study targets and briefs.

The Socratic interview itself is SKILL.md prose (the AI is the interviewer). This module
owns the deterministic, testable parts: order the interview queue (merging study->final
pairs), (de)serialize the resulting study briefs, write the artifacts, and gate that every
queued target has a complete brief before the stage closes.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.selection import Rating

_NO_CLUSTER = "~"  # sentinel: works without a cluster sort after named clusters


@dataclass(frozen=True)
class StudyTarget:
    work_id: str          # the primary (final) work
    title: str
    year: str
    medium: str
    cluster: str
    source_url: str
    members: tuple[str, ...]  # (work_id, *merged_study_ids); len > 1 = merged pair


def build_queue(liked_ratings: list[Rating], work_meta: dict[str, dict]) -> list[StudyTarget]:
    """Order liked works for the interview, merging study->final pairs.

    `work_meta[work_id]` may carry `cluster` (str), `studyability` (int), and `study_for`
    (the work_id this one is a preparatory study for). When a work's `study_for` names
    another liked work, the two collapse into one target (final first).
    """
    liked_ids = {r.work_id for r in liked_ratings}
    merged_into: dict[str, list[str]] = {}
    is_merged: set[str] = set()
    for r in liked_ratings:
        final = (work_meta.get(r.work_id) or {}).get("study_for") or ""
        if final and final in liked_ids and final != r.work_id:
            merged_into.setdefault(final, []).append(r.work_id)
            is_merged.add(r.work_id)

    targets: list[StudyTarget] = []
    for r in liked_ratings:
        if r.work_id in is_merged:
            continue
        meta = work_meta.get(r.work_id) or {}
        studies = tuple(sorted(merged_into.get(r.work_id, [])))
        targets.append(StudyTarget(
            work_id=r.work_id,
            title=r.title,
            year=r.date,
            medium=r.medium,
            cluster=meta.get("cluster", "") or "",
            source_url=r.source_url,
            members=(r.work_id, *studies),
        ))

    def sort_key(t: StudyTarget):
        studyability = (work_meta.get(t.work_id) or {}).get("studyability", -1)
        return (t.cluster or _NO_CLUSTER, -studyability, t.work_id)

    return sorted(targets, key=sort_key)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/curation_interview.py tests/test_curation_interview.py
git commit -m "feat: build ordered interview queue with study->final pair merge"
```

---

### Task 6: `StudyBrief` + serialize/parse round-trip

**Files:**
- Modify: `skill/scripts/curation_interview.py`
- Test: `tests/test_curation_interview.py`

**Interfaces:**
- Produces: `StudyStep(step: str, success_test: str = "")`; `StudyBrief(work_id, title, year, members: tuple[str,...], cluster, source_url, thesis, anchor_trait, study_plan: tuple[StudyStep,...])`; `serialize_briefs(artist: str, briefs: list[StudyBrief]) -> dict`; `parse_briefs(data: dict) -> list[StudyBrief]`. Empty `success_test` serializes to JSON `null` and parses back to `""`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_curation_interview.py`:

```python
from scripts.curation_interview import StudyBrief, StudyStep, serialize_briefs, parse_briefs


def _brief():
    return StudyBrief(
        work_id="exotics", title="Exotics", year="1939",
        members=("exotics", "sales-woman"), cluster="late",
        source_url="http://x/exotics", thesis="facial economy as the dial",
        anchor_trait="economy of facial information",
        study_plan=(
            StudyStep("copy the ink study"),
            StudyStep("variation drill", success_test="reads warm / tense / uneasy"),
        ),
    )


def test_brief_round_trips_through_json_shape():
    briefs = [_brief()]
    assert parse_briefs(serialize_briefs("Paul Klee", briefs)) == briefs


def test_empty_success_test_serializes_to_null():
    data = serialize_briefs("X", [_brief()])
    assert data["briefs"][0]["study_plan"][0]["success_test"] is None
    assert data["artist"] == "X"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: FAIL (names not defined).

- [ ] **Step 3: Add to `skill/scripts/curation_interview.py`**

Append:

```python
@dataclass(frozen=True)
class StudyStep:
    step: str
    success_test: str = ""


@dataclass(frozen=True)
class StudyBrief:
    work_id: str
    title: str
    year: str
    members: tuple[str, ...]
    cluster: str
    source_url: str
    thesis: str
    anchor_trait: str
    study_plan: tuple[StudyStep, ...]


def serialize_briefs(artist: str, briefs: list[StudyBrief]) -> dict:
    """Build the study-briefs.json payload (empty success_test -> null)."""
    return {
        "artist": artist,
        "briefs": [
            {
                "work_id": b.work_id,
                "title": b.title,
                "year": b.year,
                "members": list(b.members),
                "cluster": b.cluster,
                "source_url": b.source_url,
                "thesis": b.thesis,
                "anchor_trait": b.anchor_trait,
                "study_plan": [
                    {"step": s.step, "success_test": s.success_test or None}
                    for s in b.study_plan
                ],
            }
            for b in briefs
        ],
    }


def parse_briefs(data: dict) -> list[StudyBrief]:
    """Parse a study-briefs.json payload back into StudyBriefs (null test -> '')."""
    out: list[StudyBrief] = []
    for d in data.get("briefs", []):
        steps = tuple(
            StudyStep(step=str(s.get("step", "")), success_test=str(s.get("success_test") or ""))
            for s in d.get("study_plan", [])
        )
        out.append(StudyBrief(
            work_id=str(d.get("work_id", "")),
            title=str(d.get("title", "")),
            year=str(d.get("year", "")),
            members=tuple(str(m) for m in d.get("members", [])),
            cluster=str(d.get("cluster", "")),
            source_url=str(d.get("source_url", "")),
            thesis=str(d.get("thesis", "")),
            anchor_trait=str(d.get("anchor_trait", "")),
            study_plan=steps,
        ))
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/curation_interview.py tests/test_curation_interview.py
git commit -m "feat: study brief model with json round-trip"
```

---

### Task 7: Paths + write the study-briefs artifacts

**Files:**
- Modify: `skill/scripts/paths.py` (add two properties near line 65)
- Modify: `skill/scripts/curation_interview.py`
- Test: `tests/test_curation_interview.py`

**Interfaces:**
- Produces: `StudyPaths.study_briefs_json` (`root/"study-briefs.json"`), `StudyPaths.study_briefs_md` (`root/"study-briefs.md"`); `write_study_briefs_json(artist, briefs, path)`; `write_study_briefs_md(artist, briefs, path)`.
- Consumes: `serialize_briefs` (Task 6), `scripts._md.frontmatter`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_curation_interview.py`:

```python
from scripts.curation_interview import write_study_briefs_json, write_study_briefs_md


def test_write_json_then_parse_recovers_briefs(tmp_path):
    p = tmp_path / "study-briefs.json"
    write_study_briefs_json("Paul Klee", [_brief()], p)
    import json
    assert parse_briefs(json.loads(p.read_text())) == [_brief()]


def test_write_md_renders_thesis_anchor_and_steps(tmp_path):
    p = tmp_path / "study-briefs.md"
    write_study_briefs_md("Paul Klee", [_brief()], p)
    text = p.read_text()
    assert "> [!example] Exotics (1939)" in text
    assert "facial economy as the dial" in text
    assert "1. copy the ink study" in text
    assert "*Test:* reads warm / tense / uneasy" in text


def test_study_briefs_paths():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.study_briefs_json.name == "study-briefs.json"
    assert sp.study_briefs_md.name == "study-briefs.md"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: FAIL (writers + path properties not defined).

- [ ] **Step 3: Add path properties to `skill/scripts/paths.py`**

After the `selection_json` property (around line 65), add:

```python
    @property
    def study_briefs_json(self) -> Path:
        return self.root / "study-briefs.json"

    @property
    def study_briefs_md(self) -> Path:
        return self.root / "study-briefs.md"
```

- [ ] **Step 4: Add the writers to `skill/scripts/curation_interview.py`**

Add the import at the top (with the other imports):

```python
import json
from pathlib import Path

from scripts._md import frontmatter
```

Append:

```python
def write_study_briefs_json(artist: str, briefs: list[StudyBrief], path: Path | str) -> Path:
    """Persist the machine-readable study briefs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialize_briefs(artist, briefs), indent=2) + "\n", encoding="utf-8")
    return path


def write_study_briefs_md(artist: str, briefs: list[StudyBrief], path: Path | str) -> Path:
    """Write the Obsidian-native study briefs (one callout per study target)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = frontmatter("study/curation-briefs", artist) + [f"# Study briefs — {artist}", ""]
    for b in briefs:
        lines += [
            f"> [!example] {b.title} ({b.year})",
            f"> **Thesis:** {b.thesis}",
            f"> **Anchor trait:** {b.anchor_trait}",
            "> **Study plan:**",
        ]
        for i, s in enumerate(b.study_plan, 1):
            lines.append(f"> {i}. {s.step}")
            if s.success_test:
                lines.append(f">    *Test:* {s.success_test}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/paths.py skill/scripts/curation_interview.py tests/test_curation_interview.py
git commit -m "feat: write study-briefs.json and study-briefs.md"
```

---

### Task 8: Resume + completeness gate — `pending_targets`, `validate_briefs`

**Files:**
- Modify: `skill/scripts/curation_interview.py`
- Test: `tests/test_curation_interview.py`

**Interfaces:**
- Produces: `pending_targets(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[StudyTarget]` (targets with no brief yet); `validate_briefs(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[str]` (empty = every target has a brief with non-empty thesis, anchor_trait, and study_plan).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_curation_interview.py`:

```python
from scripts.curation_interview import pending_targets, validate_briefs


def _target(work_id):
    return StudyTarget(work_id=work_id, title=work_id, year="1930", medium="",
                       cluster="c", source_url="u", members=(work_id,))


def _full_brief(work_id):
    return StudyBrief(work_id=work_id, title=work_id, year="1930", members=(work_id,),
                      cluster="c", source_url="u", thesis="t", anchor_trait="a",
                      study_plan=(StudyStep("do it"),))


def test_pending_targets_excludes_briefed_works():
    queue = [_target("a"), _target("b")]
    assert [t.work_id for t in pending_targets(queue, [_full_brief("a")])] == ["b"]


def test_validate_passes_when_every_target_has_a_full_brief():
    queue = [_target("a")]
    assert validate_briefs(queue, [_full_brief("a")]) == []


def test_validate_flags_missing_brief():
    queue = [_target("a")]
    assert any("no study brief" in e for e in validate_briefs(queue, []))


def test_validate_flags_empty_thesis_anchor_or_plan():
    queue = [_target("a")]
    bad = StudyBrief(work_id="a", title="a", year="1930", members=("a",), cluster="c",
                     source_url="u", thesis="  ", anchor_trait="", study_plan=())
    errs = validate_briefs(queue, [bad])
    assert any("thesis" in e for e in errs)
    assert any("anchor_trait" in e for e in errs)
    assert any("study_plan" in e for e in errs)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_curation_interview.py -v`
Expected: FAIL (names not defined).

- [ ] **Step 3: Add to `skill/scripts/curation_interview.py`**

Append:

```python
def pending_targets(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[StudyTarget]:
    """Targets that do not yet have a study brief (resume support)."""
    done = {b.work_id for b in briefs}
    return [t for t in queue if t.work_id not in done]


def validate_briefs(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[str]:
    """Return errors; empty means every queued target has a complete brief."""
    by_id = {b.work_id: b for b in briefs}
    errors: list[str] = []
    for t in queue:
        b = by_id.get(t.work_id)
        if b is None:
            errors.append(f"{t.work_id}: no study brief")
            continue
        if not b.thesis.strip():
            errors.append(f"{t.work_id}: empty thesis")
        if not b.anchor_trait.strip():
            errors.append(f"{t.work_id}: empty anchor_trait")
        if not b.study_plan:
            errors.append(f"{t.work_id}: empty study_plan")
    return errors
```

- [ ] **Step 4: Run the full suite**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest -q`
Expected: PASS (all tests, including the pre-existing suite).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/curation_interview.py tests/test_curation_interview.py
git commit -m "feat: resume + completeness gate for study briefs"
```

---

### Task 9: Wire the stage into SKILL.md

**Files:**
- Modify: `skill/SKILL.md` (stage list line 47-49; Run A stage 5 / Human Pause 1 at 62-71; Run B stage 6 at 73-85; Output contract at 100-104)

**Interfaces:**
- Consumes: everything above — `curation_interview` module API, the new `study-briefs.{json,md}` artifacts, the visual-only gallery.

- [ ] **Step 1: Update the stage-id list**

Change the ordered stage list (lines 47-49) to insert `curation_interview` after `image_discovery`:

```markdown
Stage ids, in order: `background`, `source_grading`, `style_definition`,
`works_inventory`, `image_discovery`, `curation_interview`,
`preference_synthesis`, `visual_analysis`, `study_retention`.
```

- [ ] **Step 2: Trim Human Pause 1 to visual-only**

Replace the Human Pause 1 callout (lines 68-71) so it no longer mentions the curatorial gate:

```markdown
> [!info] Human Pause 1 — visual rating
> The user opens `gallery.html` (a board of many thumbnails), star-rates works, ticks the
> filters (liked-only / PD-only), and exports `selection.json`. Rating is purely visual —
> the study rationale is drawn out next, in the `curation_interview` stage. See
> [[stage-curation]].
```

In Run A stage 5 (line 62-66), delete the phrase about filling "the curatorial gate" from the Phase A description if present (the gallery no longer collects it).

- [ ] **Step 3: Document the new `curation_interview` stage**

Insert a new "Run B — Socratic curation interview (stage 6)" section before the existing synthesis section, and renumber. Body:

```markdown
## Run B — Socratic curation interview (stage 6)

6. **curation_interview** — gated on `selection.json`. Build the interview queue, then
   interview the human **one study target at a time** to produce each work's study brief.

   - Load ratings: `sel = load_selection(sp.selection_json, '<ARTIST>')`; `from scripts.selection import liked`.
   - Assemble `work_meta` from your `works.md` clusters: a dict `work_id -> {"cluster", "studyability", "study_for"}` (`study_for` set when one liked work is a preparatory study for another).
   - `from scripts.curation_interview import build_queue, pending_targets, parse_briefs, write_study_briefs_json, write_study_briefs_md, validate_briefs, StudyBrief, StudyStep`.
   - `queue = build_queue(liked(sel), work_meta)`. If a `study-briefs.json` already exists, `parse_briefs(json.load(...))` it and interview only `pending_targets(queue, briefs)` (resume).
   - **For each pending target, run the interview** (see below), appending a `StudyBrief` as each is confirmed; re-write `study-briefs.json` after each so progress survives interruption.
   - When `pending_targets` is empty, `validate_briefs(queue, briefs)` must return `[]`; if not, print the errors and STOP. Then `write_study_briefs_md(...)`, mark the stage complete, save state.

   **The interview (per target), AI-led, friction-bearing — the AI asks and reflects, never states the lesson:**
   1. Present **neutral facts only** — title, year, medium, cluster, and the `source_url` link. Do **not** describe what the picture looks like (let the human's eyes lead; metadata can mislead).
   2. **Observe** — ask what the eye does; description before interpretation.
   3. **Hypothesize the rule** — push for the mechanism, not a feature catalog.
   4. **Redirect narrative → technique** — if the human drifts into story/iconography, reflect their own formal observation back as the bridge to a practiceable rule.
   5. **Commit + design the drill** — "if you copy this to steal that one rule, what are you practicing, and what's the test that proves you learned it?" — this yields the study plan.
   6. **Confirm + record** — crystallize thesis / anchor_trait / ordered `study_plan` (each step an optional `success_test`) from the human's words; on confirmation, append the `StudyBrief`.
   7. **Coverage** — steer later targets toward lessons that do not overlap those already confirmed.
```

- [ ] **Step 4: Point synthesis at the briefs**

In the (now stage 7) `preference_synthesis` section, change its input from the selection gate fields to the briefs: it is gated on `study-briefs.json`; it still runs `validate_selection` + `apply_selection` on `selection.json` for the image copy, but reads `parse_briefs(...)` (thesis / anchor_trait / study_plan) as the per-work rationale for pattern analysis.

- [ ] **Step 5: Update the Output contract**

In the Output contract (lines 100-104), add `study-briefs.json`, `study-briefs.md` to the listed artifacts.

- [ ] **Step 6: Verify the wiring**

Run: `rg -n "curation_interview|study-briefs" skill/SKILL.md`
Expected: the stage id appears in the ordered list, the new stage section, and the output contract; `study-briefs.json`/`.md` appear in Run B and the contract.

- [ ] **Step 7: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs: wire curation_interview stage into SKILL.md"
```

---

## Self-Review

**Spec coverage:**
- New `curation_interview` stage between image_discovery and preference_synthesis → Task 1, Task 9.
- Output `study-briefs.{json,md}`, structured study plan → Tasks 6, 7.
- Gallery field removal + title/date/medium export (F2) → Tasks 2, 3, 4.
- `validate_selection` gate removed → Task 2.
- Queue ordering by cluster/studyability + study→final merge → Task 5.
- Resume (idempotent) + completeness gate → Task 8, Task 9 (resume loop).
- Interview procedure + AI-asks-never-answers contract + neutral-facts/no-misframe + narrative→technique redirect + coverage steering → Task 9.
- Downstream consumes briefs → Task 9 step 4.
- Testing surface (build_queue, round-trip, validate_briefs, validate_selection, gallery export) → covered across tasks.
- Non-goals F1/F3/F5 → explicitly excluded (Global Constraints).

**Type consistency:** `StudyTarget` (T5), `StudyStep`/`StudyBrief` (T6), `serialize_briefs`/`parse_briefs` (T6), `write_study_briefs_json`/`write_study_briefs_md` (T7), `pending_targets`/`validate_briefs` (T8) names match across the SKILL.md import line in Task 9. `Rating` gains title/date/medium (T2) consumed by `build_queue` (T5) and gallery export (T4). `ThumbnailCandidate.medium` (T3) consumed by gallery payload (T4).

**No placeholders:** every code step contains complete code; every run step names the command + expected result.
