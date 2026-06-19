# artist-study-kit — Curation + Study Implementation Plan (Plan 3)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the curation + study half of the pipeline — the `gallery.html` generator, the `selection.json` round-trip, preference-synthesis ranking, the analysis/study/drill emitters, and the SKILL.md wiring that threads stages 5–8 into the orchestration.

**Architecture:** A single orchestrator skill (`skill/SKILL.md`) drives Claude through the stages conversationally; deterministic, importable Python in `skill/scripts/` (a package) does the mechanical/IO/serialization work while Claude does the art-historical judgment. New scripts follow the existing pattern: pure where possible, every network/time boundary dependency-injected, LLM-supplied judgment passed in as data and serialized to Obsidian-native markdown (mirrors `scripts/source_grades.py`). This plan completes the spec; Plans 1–2 already built the spine (`paths`, `state`, `frontmatter`) and the research tooling (`firecrawl_fetch`, `source_signals`, `source_grades`, `iiif`, `image_download`).

**Tech Stack:** Python 3 managed with **uv**; `pytest` (+ `pytest-bdd` available); `pyyaml`, `httpx`. Standalone HTML+JS for the gallery (no build step, no JS deps). Venv lives OUTSIDE iCloud at `~/.venvs/artist-study-kit`; repo `.venv` is a symlink. Run everything with `uv run pytest` from the repo root.

## Global Constraints

- **TDD always** — write the failing test first, watch it fail, implement minimal code, watch it pass, commit. (CLAUDE.md global stack.)
- **Run tests from the repo root** with `uv run pytest`. `pyproject.toml` sets `pythonpath = ["skill"]`, so `import scripts.X` works; tests live in repo-root `tests/`, fixtures in `tests/fixtures/`.
- **0 warnings policy** — Plan 2 ended at 74 tests, 0 warnings. Keep it clean (`filterwarnings` already ignores the firecrawl UserWarning).
- **Scripts are a package** — `skill/scripts/__init__.py` exists; import siblings as `from scripts.X import Y`.
- **Inject every IO/time boundary** — any function that fetches, sleeps, or reads the clock takes the boundary as a keyword argument with a real default, so tests use fakes and never touch live endpoints/disk-timing. (Pattern: `image_download.download_candidate(..., fetch=default_fetch, sleep=time.sleep)`.)
- **Frozen dataclasses** for value objects (`@dataclass(frozen=True)`); `from __future__ import annotations` at the top of every module.
- **Obsidian-native markdown outputs** — YAML frontmatter (`type:`, `artist:`, `tags:`), `[[wikilinks]]`, tag taxonomy (`#artist/`, `#technique/`, `#source-grade/`), study callouts (`> [!tip]`, `> [!warning]`, `> [!example]`). When emitting `tags:` containing `#`, use a **block-style YAML list with quoted items** so `#` doesn't break the parser (copy the pattern in `source_grades.write_source_grades_md`).
- **Round-trip every emitter in tests** with `scripts.frontmatter.parse_frontmatter` to prove the frontmatter is valid YAML.
- **MVP depth only** — spec §9 defers full FSRS deck generation, gapped-worksheet generators, richer gallery (overlay markup / compare view), palette extraction, OCR, LLM-as-judge. Do **not** build those; emit the thin version and leave structure for Claude's prose.
- **Slug everywhere** — artist directories use `scripts.paths.slugify`; never hand-roll a slug.
- **Stage ids are the resume contract** (verbatim, ordered): `background`, `source_grading`, `style_definition`, `works_inventory`, `image_discovery`, `preference_synthesis`, `visual_analysis`, `study_retention`. Pause gates (`scripts.state.PAUSE_GATES`): `preference_synthesis` needs `selection.json`; `visual_analysis` needs a chosen study set.

---

## File Structure

**Create:**
- `skill/scripts/selection.py` — `selection.json` schema, parse/validate, liked-set filter, copy ≥4★ into `images/selected/`.
- `skill/scripts/gallery.py` — read candidate sidecars → generate the standalone `gallery.html` contact sheet (grid → detail → star → curatorial gate → export `selection.json`).
- `skill/scripts/preference_synthesis.py` — score study-set candidates (pattern-fit + studyability), rank, emit `preference-synthesis.md`.
- `skill/scripts/analysis.py` — emit `analysis.md` (5-stage formal analysis, study set only) from LLM-supplied per-work content.
- `skill/scripts/study_retention.py` — emit `study-notes.md` (faded aids), `review-schedule.md`, and `drills/discrimination-cards.md`.
- `tests/test_selection.py`, `tests/test_gallery.py`, `tests/test_preference_synthesis.py`, `tests/test_analysis.py`, `tests/test_study_retention.py` — one test module per script.

**Modify:**
- `skill/scripts/image_download.py` — carry-forward hardening: `USER_AGENT` constant + fetch-exception handling.
- `tests/test_image_download.py` — add the exception-path test.
- `skill/SKILL.md` — wire stages 5–8 to the new scripts; mark stages complete via `PipelineState`.
- `tests/test_skill_md.py` — assert the new scripts are referenced.

**Consume (already built — do not rebuild):**
- `scripts.paths`: `slugify`, `study_paths(base, artist) -> StudyPaths`, `scaffold`. `StudyPaths` props used here: `candidates_dir`, `selected_dir`, `gallery_html`, `selection_json`, `preference_synthesis_md`, `analysis_md`, `study_notes_md`, `drills_dir`, `review_schedule_md`, `state_json`, `root`.
- `scripts.state`: `PipelineState`, `STAGES`, `PAUSE_GATES`.
- `scripts.frontmatter`: `parse_frontmatter(text) -> dict`.
- `scripts.iiif`: `ImageCandidate` (`work_id, institution, label, iiif_id, image_url, width, height, license, rights_status`).
- `scripts.image_download`: writes a per-image sidecar at `<candidates_dir>/<work_id>/<token>.json` = `dataclasses.asdict(ImageCandidate)`, alongside `<token>.jpg`, where `token = iiif_id.rstrip('/').rsplit('/',1)[-1]`. **`gallery.py` reads these sidecars.**

---

### Task 1: image_download carry-forward hardening

Folds in the Plan-2 carry-forward logged in `.git/sdd/progress.md`: `default_fetch` had no custom User-Agent and no exception handling, so a timeout/connection error propagated uncaught instead of becoming `status="error"`. Harden the live download path now that it gets exercised in Run A.

**Files:**
- Modify: `skill/scripts/image_download.py`
- Test: `tests/test_image_download.py`

**Interfaces:**
- Consumes: existing `download_candidate`, `ImageCandidate`, `validate_candidate`.
- Produces: `USER_AGENT` (module constant, str); `download_candidate` now returns `status="error"` when the injected `fetch` raises (instead of propagating).

- [ ] **Step 1: Write the failing test** — append to `tests/test_image_download.py`:

```python
from scripts.image_download import USER_AGENT


def test_user_agent_is_descriptive():
    assert "artist-study-kit" in USER_AGENT


def test_download_candidate_handles_fetch_exception(tmp_path):
    def _boom(url):
        raise ConnectionError("connection reset")

    res = download_candidate(_candidate(), tmp_path, fetch=_boom, sleep=lambda s: None)
    assert res.status == "error"
    assert res.image_path is None
    assert "connection reset" in res.note
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_image_download.py::test_download_candidate_handles_fetch_exception tests/test_image_download.py::test_user_agent_is_descriptive -v`
Expected: FAIL — `ImportError: cannot import name 'USER_AGENT'` (and the exception would propagate).

- [ ] **Step 3: Add the User-Agent constant + harden `default_fetch`** in `skill/scripts/image_download.py`. Replace the `default_fetch` function with:

```python
USER_AGENT = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"


def default_fetch(url: str) -> tuple[int, str, bytes]:
    """Real fetcher (httpx). Not exercised in tests. Network errors → (0, "", b"")."""
    import httpx

    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=60.0,
            headers={"User-Agent": USER_AGENT},
        )
    except httpx.HTTPError:
        return 0, "", b""
    return resp.status_code, resp.headers.get("content-type", ""), resp.content
```

- [ ] **Step 4: Wrap the injected `fetch` call** in `download_candidate` so any fetcher exception becomes `status="error"`. Replace the fetch line:

```python
    try:
        status_code, content_type, content = fetch(candidate.image_url)
    except Exception as exc:  # network errors must not crash the batch
        return DownloadResult(candidate, None, None, "error", str(exc))
    if status_code != 200 or not content_type.startswith("image/") or not content:
        return DownloadResult(
            candidate, None, None, "error", f"status={status_code} type={content_type}"
        )
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_image_download.py -v`
Expected: PASS (all prior image_download tests + the two new ones).

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/image_download.py tests/test_image_download.py
git commit -m "fix: harden image download — User-Agent + fetch-exception handling"
```

---

### Task 2: selection.json schema + round-trip

The human output of Human Pause 1: per-candidate star rating plus the curatorial-gate text for works rated ≥4★. Run B ingests it. Build the data model, parse/validate, the liked-set filter, and the copy-into-`images/selected/` action. This task defines the schema the gallery (Task 3) must emit.

**Files:**
- Create: `skill/scripts/selection.py`
- Test: `tests/test_selection.py`

**Interfaces:**
- Consumes: nothing from sibling scripts (stdlib + `pathlib`).
- Produces:
  - `Rating` (frozen dataclass): `work_id: str`, `iiif_token: str`, `image_rel: str`, `rating: int`, `thesis: str = ""`, `anchor_trait: str = ""`, `handoff_note: str = ""`.
  - `Selection` (frozen dataclass): `artist: str`, `ratings: list[Rating]`.
  - `LIKED_THRESHOLD: int = 4`.
  - `parse_selection(data: dict) -> Selection`.
  - `validate_selection(sel: Selection) -> list[str]` (returns human-readable error strings; empty = valid).
  - `load_selection(path: Path, artist: str) -> Selection` (raises `ValueError` on artist mismatch — mirrors `state.load`).
  - `liked(sel: Selection, threshold: int = LIKED_THRESHOLD) -> list[Rating]`.
  - `apply_selection(sel, candidates_dir: Path, selected_dir: Path, threshold=LIKED_THRESHOLD) -> list[Path]` (copies liked images into `selected_dir`, idempotent; returns the destination paths).
  - The JSON shape (the contract the gallery emits and `parse_selection` reads):
    ```json
    {"artist": "vincent-van-gogh",
     "ratings": [
       {"work_id": "wheat-field", "iiif_token": "12345",
        "image_rel": "images/candidates/wheat-field/12345.jpg",
        "rating": 5, "thesis": "...", "anchor_trait": "...", "handoff_note": "..."}
     ]}
    ```

- [ ] **Step 1: Write the failing tests** — `tests/test_selection.py`:

```python
import json
from pathlib import Path

import pytest

from scripts.selection import (
    LIKED_THRESHOLD,
    Rating,
    Selection,
    apply_selection,
    liked,
    load_selection,
    parse_selection,
    validate_selection,
)


def _data(rating=5, **gate):
    fields = {"thesis": "studies broken color", "anchor_trait": "warm/cool value split",
              "handoff_note": "look at the sky"}
    fields.update(gate)
    return {
        "artist": "vincent-van-gogh",
        "ratings": [
            {"work_id": "wheat-field", "iiif_token": "12345",
             "image_rel": "images/candidates/wheat-field/12345.jpg",
             "rating": rating, **(fields if rating >= LIKED_THRESHOLD else {})},
        ],
    }


def test_parse_selection_reads_ratings():
    sel = parse_selection(_data())
    assert isinstance(sel, Selection)
    assert sel.artist == "vincent-van-gogh"
    assert sel.ratings[0].rating == 5
    assert sel.ratings[0].thesis == "studies broken color"


def test_parse_selection_defaults_missing_gate_fields():
    sel = parse_selection(_data(rating=2))
    assert sel.ratings[0].anchor_trait == ""


def test_validate_passes_clean_selection():
    assert validate_selection(parse_selection(_data())) == []


def test_validate_rejects_out_of_range_rating():
    sel = parse_selection(_data(rating=9))
    errs = validate_selection(sel)
    assert any("rating" in e for e in errs)


def test_validate_requires_gate_fields_when_liked():
    sel = parse_selection(_data(rating=4, thesis="", anchor_trait="", handoff_note=""))
    errs = validate_selection(sel)
    assert any("thesis" in e for e in errs)


def test_liked_filters_by_threshold():
    data = _data(rating=5)
    data["ratings"].append({"work_id": "irises", "iiif_token": "9", "image_rel": "x.jpg", "rating": 2})
    sel = parse_selection(data)
    assert [r.work_id for r in liked(sel)] == ["wheat-field"]


def test_load_selection_rejects_artist_mismatch(tmp_path):
    p = tmp_path / "selection.json"
    p.write_text(json.dumps(_data()), encoding="utf-8")
    with pytest.raises(ValueError):
        load_selection(p, "claude-monet")


def test_apply_selection_copies_liked_images(tmp_path):
    cdir = tmp_path / "candidates"
    (cdir / "wheat-field").mkdir(parents=True)
    (cdir / "wheat-field" / "12345.jpg").write_bytes(b"\xff\xd8\xffJPEG")
    sdir = tmp_path / "selected"
    sel = parse_selection(_data(rating=5))
    out = apply_selection(sel, cdir, sdir)
    assert out and out[0].is_file()
    assert out[0].read_bytes().startswith(b"\xff\xd8\xff")
    # idempotent: second run does not raise and returns the same path set
    assert apply_selection(sel, cdir, sdir) == out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_selection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.selection'`.

- [ ] **Step 3: Implement `skill/scripts/selection.py`:**

```python
"""Human Pause 1 output: parse/validate selection.json and materialize the liked set.

selection.json is produced by gallery.html (star ratings + curatorial-gate text) and
ingested by Run B. The schema: {"artist", "ratings": [{work_id, iiif_token, image_rel,
rating, thesis, anchor_trait, handoff_note}]}. Works rated >= LIKED_THRESHOLD must carry
gate text and are copied into images/selected/.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

LIKED_THRESHOLD = 4
_GATE_FIELDS = ("thesis", "anchor_trait", "handoff_note")


@dataclass(frozen=True)
class Rating:
    work_id: str
    iiif_token: str
    image_rel: str
    rating: int
    thesis: str = ""
    anchor_trait: str = ""
    handoff_note: str = ""


@dataclass(frozen=True)
class Selection:
    artist: str
    ratings: list[Rating] = field(default_factory=list)


def parse_selection(data: dict) -> Selection:
    """Build a Selection from the gallery's JSON payload (missing gate fields → '')."""
    ratings = [
        Rating(
            work_id=str(r.get("work_id", "")),
            iiif_token=str(r.get("iiif_token", "")),
            image_rel=str(r.get("image_rel", "")),
            rating=int(r.get("rating", 0)),
            thesis=str(r.get("thesis", "")),
            anchor_trait=str(r.get("anchor_trait", "")),
            handoff_note=str(r.get("handoff_note", "")),
        )
        for r in data.get("ratings", [])
    ]
    return Selection(artist=str(data["artist"]), ratings=ratings)


def validate_selection(sel: Selection) -> list[str]:
    """Return human-readable errors; empty list means the selection is valid."""
    errors: list[str] = []
    for r in sel.ratings:
        label = r.work_id or r.iiif_token or "<unknown>"
        if not (0 <= r.rating <= 5):
            errors.append(f"{label}: rating {r.rating} out of range 0-5")
        if not r.work_id:
            errors.append(f"{label}: missing work_id")
        if r.rating >= LIKED_THRESHOLD:
            for gate in _GATE_FIELDS:
                if not getattr(r, gate).strip():
                    errors.append(f"{label}: liked (>={LIKED_THRESHOLD}*) but {gate} is empty")
    return errors


def load_selection(path: Path, artist: str) -> Selection:
    """Load + validate selection.json; raise ValueError on artist mismatch."""
    sel = parse_selection(json.loads(Path(path).read_text(encoding="utf-8")))
    if sel.artist != artist:
        raise ValueError(f"selection.json artist {sel.artist!r} != requested {artist!r}")
    return sel


def liked(sel: Selection, threshold: int = LIKED_THRESHOLD) -> list[Rating]:
    return [r for r in sel.ratings if r.rating >= threshold]


def apply_selection(
    sel: Selection,
    candidates_dir: Path | str,
    selected_dir: Path | str,
    threshold: int = LIKED_THRESHOLD,
) -> list[Path]:
    """Copy liked images from candidates_dir into selected_dir; idempotent."""
    candidates_dir = Path(candidates_dir)
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for r in liked(sel, threshold):
        src = candidates_dir / r.work_id / f"{r.iiif_token}.jpg"
        if not src.is_file():
            continue
        dst = selected_dir / f"{r.work_id}-{r.iiif_token}.jpg"
        if not dst.is_file():
            shutil.copy2(src, dst)
        out.append(dst)
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_selection.py -v`
Expected: PASS (9 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/selection.py tests/test_selection.py
git commit -m "feat: selection.json schema, validation, and liked-set materialization"
```

---

### Task 3: gallery.html generator

Build the standalone static HTML+JS contact sheet (Human Pause 1). It reads the candidate sidecars written by `image_download`, embeds them as JSON, and renders: a thumbnail grid grouped by work with inline decision metadata; a detail view with a 5-star control that auto-advances; a curatorial gate (thesis / anchor-trait / handoff-note) revealed at ≥4★; and an Export button that downloads `selection.json` in the Task-2 schema. MVP only — defer overlay markup and compare view (spec §9).

**Files:**
- Create: `skill/scripts/gallery.py`
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: candidate sidecars at `<candidates_dir>/<work_id>/<token>.json` (= `asdict(ImageCandidate)`) with sibling `<token>.jpg`. Token derivation matches `image_download`.
- Produces:
  - `CandidateView` (frozen dataclass): `work_id: str`, `token: str`, `image_rel: str`, `meta: dict`.
  - `load_candidate_sidecars(candidates_dir: Path) -> list[CandidateView]` (sorted by work_id then token; only sidecars with a sibling `.jpg`).
  - `build_gallery_html(views: list[CandidateView], artist: str) -> str`.
  - `write_gallery(candidates_dir: Path, artist: str, out_path: Path) -> Path`.
  - The exported JSON shape matches `selection.parse_selection` (Task 2): `{artist, ratings:[{work_id, iiif_token, image_rel, rating, thesis, anchor_trait, handoff_note}]}`.

- [ ] **Step 1: Write the failing tests** — `tests/test_gallery.py`:

```python
import json
from pathlib import Path

from scripts.gallery import (
    CandidateView,
    build_gallery_html,
    load_candidate_sidecars,
    write_gallery,
)


def _sidecar(cdir: Path, work_id="wheat-field", token="12345", width=4000):
    wdir = cdir / work_id
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / f"{token}.jpg").write_bytes(b"\xff\xd8\xffJPEG")
    meta = {
        "work_id": work_id, "institution": "met", "label": "recto",
        "iiif_id": f"https://images.metmuseum.org/iiif/{token}",
        "image_url": "x", "width": width, "height": 3000,
        "license": "Public Domain", "rights_status": "public_domain",
    }
    (wdir / f"{token}.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def test_load_sidecars_pairs_json_with_image(tmp_path):
    _sidecar(tmp_path)
    views = load_candidate_sidecars(tmp_path)
    assert len(views) == 1
    assert views[0].work_id == "wheat-field"
    assert views[0].token == "12345"
    assert views[0].image_rel == "images/candidates/wheat-field/12345.jpg"
    assert views[0].meta["institution"] == "met"


def test_load_sidecars_ignores_json_without_image(tmp_path):
    wdir = tmp_path / "orphan"
    wdir.mkdir()
    (wdir / "9.json").write_text("{}", encoding="utf-8")
    assert load_candidate_sidecars(tmp_path) == []


def test_build_html_embeds_candidate_data_and_controls():
    view = CandidateView(
        work_id="wheat-field", token="12345",
        image_rel="images/candidates/wheat-field/12345.jpg",
        meta={"institution": "met", "width": 4000, "height": 3000,
              "rights_status": "public_domain", "license": "Public Domain", "label": "recto"},
    )
    html = build_gallery_html([view], "Vincent van Gogh")
    assert "<!DOCTYPE html>" in html
    assert "Vincent van Gogh" in html
    # candidate data is embedded as JSON for the JS
    assert "wheat-field" in html
    assert "images/candidates/wheat-field/12345.jpg" in html
    # decision metadata surfaced inline
    assert "met" in html and "4000" in html
    # star control + curatorial-gate fields + export present
    assert 'data-star' in html
    for gate in ("thesis", "anchor_trait", "handoff_note"):
        assert gate in html
    assert "selection.json" in html


def test_write_gallery_writes_file(tmp_path):
    cdir = tmp_path / "images" / "candidates"
    _sidecar(cdir)
    out = tmp_path / "gallery.html"
    result = write_gallery(cdir, "Vincent van Gogh", out)
    assert result == out
    assert out.is_file()
    assert "wheat-field" in out.read_text(encoding="utf-8")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_gallery.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.gallery'`.

- [ ] **Step 3: Implement `skill/scripts/gallery.py`.** The HTML/JS template is a module constant with a single `__DATA__` / `__ARTIST__` substitution point (no f-string, to avoid brace-escaping the JS):

```python
"""Generate the standalone gallery.html contact sheet for Human Pause 1.

Reads candidate sidecars written by image_download (<candidates_dir>/<work_id>/<token>.json
with a sibling <token>.jpg), embeds them as JSON, and renders a self-contained HTML+JS
page: grid grouped by work -> detail view with a 5-star auto-advancing control -> a
curatorial gate revealed at >=4* -> Export button that downloads selection.json in the
scripts.selection schema. MVP: no overlay markup / compare view (spec section 9).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

LIKED_THRESHOLD = 4


@dataclass(frozen=True)
class CandidateView:
    work_id: str
    token: str
    image_rel: str
    meta: dict


def load_candidate_sidecars(candidates_dir: Path | str) -> list[CandidateView]:
    """Pair every <work>/<token>.json sidecar with its sibling .jpg; sorted, stable."""
    candidates_dir = Path(candidates_dir)
    views: list[CandidateView] = []
    for meta_path in sorted(candidates_dir.glob("*/*.json")):
        image_path = meta_path.with_suffix(".jpg")
        if not image_path.is_file():
            continue
        work_id = meta_path.parent.name
        token = meta_path.stem
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        views.append(
            CandidateView(
                work_id=work_id,
                token=token,
                image_rel=f"images/candidates/{work_id}/{token}.jpg",
                meta=meta,
            )
        )
    return views


def build_gallery_html(views: list[CandidateView], artist: str) -> str:
    """Render the self-contained gallery page from candidate views."""
    payload = [
        {
            "work_id": v.work_id,
            "iiif_token": v.token,
            "image_rel": v.image_rel,
            "institution": v.meta.get("institution", ""),
            "label": v.meta.get("label", ""),
            "width": v.meta.get("width", 0),
            "height": v.meta.get("height", 0),
            "license": v.meta.get("license", ""),
            "rights_status": v.meta.get("rights_status", ""),
        }
        for v in views
    ]
    data_json = json.dumps({"artist": artist, "candidates": payload}, indent=2)
    return _TEMPLATE.replace("__ARTIST__", _escape(artist)).replace("__DATA__", data_json)


def write_gallery(candidates_dir: Path | str, artist: str, out_path: Path | str) -> Path:
    """Build the gallery from sidecars and write it to out_path."""
    out_path = Path(out_path)
    views = load_candidate_sidecars(candidates_dir)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(build_gallery_html(views, artist), encoding="utf-8")
    return out_path


def _escape(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Curation gallery — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  header { padding: 1rem; background: #1c1c1c; position: sticky; top: 0; }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px; padding: 1rem; }
  .card { background: #1c1c1c; border: 2px solid transparent; cursor: pointer; }
  .card.liked { border-color: gold; }
  .card img { width: 100%; display: block; }
  .meta { font-size: 11px; padding: 4px; color: #aaa; }
  #detail { display: none; padding: 1rem; }
  #detail img { max-height: 70vh; display: block; margin: 0 auto; }
  .star { font-size: 2rem; cursor: pointer; color: #555; }
  .star.on { color: gold; }
  #gate { display: none; margin-top: 1rem; }
  #gate label { display: block; margin: 0.5rem 0; }
  #gate input, #gate textarea { width: 100%; background: #222; color: #eee; border: 1px solid #444; }
  button { font-size: 1rem; padding: 0.5rem 1rem; margin: 0.25rem; }
</style>
</head>
<body>
<header>
  <strong>Curation gallery — __ARTIST__</strong>
  <button id="export">Export selection.json</button>
  <span id="status"></span>
</header>
<div id="grid"></div>
<div id="detail">
  <button id="back">&larr; Back to grid</button>
  <img id="detail-img" alt="">
  <div id="stars"></div>
  <div id="gate">
    <p>Rated 4&#9733;+ — record the curatorial gate before this work joins the study set:</p>
    <label>thesis (why study this)<textarea data-gate="thesis" rows="2"></textarea></label>
    <label>anchor_trait (the trait to study)<input data-gate="anchor_trait"></label>
    <label>handoff_note (note for analysis)<textarea data-gate="handoff_note" rows="2"></textarea></label>
  </div>
</div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const LIKED = 4;
const state = {};  // key -> {rating, thesis, anchor_trait, handoff_note}
let current = 0;

function key(c) { return c.work_id + "/" + c.iiif_token; }

function renderGrid() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  DATA.candidates.forEach((c, i) => {
    const s = state[key(c)] || {rating: 0};
    const card = document.createElement("div");
    card.className = "card" + (s.rating >= LIKED ? " liked" : "");
    card.innerHTML =
      '<img src="' + c.image_rel + '" loading="lazy" alt="">' +
      '<div class="meta">' + c.work_id + ' &middot; ' + c.institution +
      ' &middot; ' + c.width + '&times;' + c.height +
      ' &middot; ' + c.rights_status + ' &middot; ' + (s.rating || 0) + '&#9733;</div>';
    card.onclick = () => openDetail(i);
    grid.appendChild(card);
  });
}

function openDetail(i) {
  current = i;
  document.getElementById("grid").style.display = "none";
  document.getElementById("detail").style.display = "block";
  const c = DATA.candidates[i];
  document.getElementById("detail-img").src = c.image_rel;
  renderStars();
  renderGate();
}

function renderStars() {
  const c = DATA.candidates[current];
  const s = state[key(c)] || {rating: 0};
  const box = document.getElementById("stars");
  box.innerHTML = "";
  for (let n = 1; n <= 5; n++) {
    const star = document.createElement("span");
    star.className = "star" + (n <= s.rating ? " on" : "");
    star.dataset.star = n;
    star.textContent = "\\u2605";
    star.onclick = () => rate(n);
    box.appendChild(star);
  }
}

function renderGate() {
  const c = DATA.candidates[current];
  const s = state[key(c)] || {rating: 0};
  const gate = document.getElementById("gate");
  gate.style.display = s.rating >= LIKED ? "block" : "none";
  gate.querySelectorAll("[data-gate]").forEach(el => { el.value = s[el.dataset.gate] || ""; });
  gate.querySelectorAll("[data-gate]").forEach(el => {
    el.oninput = () => {
      const st = state[key(c)] || (state[key(c)] = {rating: s.rating});
      st[el.dataset.gate] = el.value;
    };
  });
}

function rate(n) {
  const c = DATA.candidates[current];
  const st = state[key(c)] || (state[key(c)] = {});
  st.rating = n;
  renderStars();
  renderGate();
  if (n < LIKED && current < DATA.candidates.length - 1) {
    setTimeout(() => openDetail(current + 1), 200);  // auto-advance below the gate
  }
}

document.getElementById("back").onclick = () => {
  document.getElementById("detail").style.display = "none";
  document.getElementById("grid").style.display = "grid";
  renderGrid();
};

document.getElementById("export").onclick = () => {
  const ratings = DATA.candidates.map(c => {
    const s = state[key(c)] || {rating: 0};
    return {
      work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
      rating: s.rating || 0, thesis: s.thesis || "",
      anchor_trait: s.anchor_trait || "", handoff_note: s.handoff_note || "",
    };
  });
  const blob = new Blob([JSON.stringify({artist: DATA.artist, ratings}, null, 2)],
                        {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = "selection.json";
  a.click();
  document.getElementById("status").textContent = " saved selection.json";
};

renderGrid();
</script>
</body>
</html>
"""
```

> Note on the `\\u2605` in the template: inside the Python triple-quoted string a single backslash would be a Python escape; `\\u2605` lands in the file as the JS string-escape `★` (★). The test asserts `data-star` and the gate field names, not the glyph, so this stays robust.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gallery.py -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Sanity-check the generated HTML parses** (catch template/brace bugs early):

Run: `uv run python -c "from scripts.gallery import build_gallery_html, CandidateView; print(len(build_gallery_html([], 'Test')))"`
Expected: prints a positive integer (no exception).

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit -m "feat: standalone gallery.html generator (grid/detail/star/gate/export)"
```

---

### Task 4: preference-synthesis ranking + emitter

Stage 6 (NEW stage; extends `wiki/stage-curation.md`). After curation, Claude finds patterns across the liked set (period clustering, recurring formal traits, subject matter, palette gravitation) — that's judgment, supplied as prose. This script does the deterministic plumbing: score each study-set candidate on **pattern-fit + studyability**, rank, and emit `preference-synthesis.md` (the "what you're drawn to" insight note + the ranked funnel list).

**Files:**
- Create: `skill/scripts/preference_synthesis.py`
- Test: `tests/test_preference_synthesis.py`

**Interfaces:**
- Consumes: `scripts.frontmatter.parse_frontmatter` (tests only).
- Produces:
  - `PREFERENCE_WEIGHTS: dict[str, int] = {"pattern_fit": 50, "studyability": 50}`.
  - `StudyCandidate` (frozen dataclass): `work_id: str`, `title: str`, `pattern_fit: int`, `studyability: int`, `rationale: str`.
  - `combined_score(c: StudyCandidate) -> int` (weighted average, 0–100).
  - `rank_candidates(cands: list[StudyCandidate]) -> list[StudyCandidate]` (descending by combined score, stable).
  - `write_preference_synthesis_md(insight: str, cands, artist: str, path: Path, *, shortlist_cap: int = 8) -> None`.

- [ ] **Step 1: Write the failing tests** — `tests/test_preference_synthesis.py`:

```python
from scripts.frontmatter import parse_frontmatter
from scripts.preference_synthesis import (
    PREFERENCE_WEIGHTS,
    StudyCandidate,
    combined_score,
    rank_candidates,
    write_preference_synthesis_md,
)


def _c(work_id, title, pf, st, rationale="fits the palette pattern"):
    return StudyCandidate(work_id=work_id, title=title, pattern_fit=pf, studyability=st, rationale=rationale)


def test_weights_sum_to_100():
    assert sum(PREFERENCE_WEIGHTS.values()) == 100


def test_combined_score_is_weighted_average():
    assert combined_score(_c("a", "A", 80, 60)) == 70


def test_rank_orders_descending():
    ranked = rank_candidates([_c("a", "A", 40, 40), _c("b", "B", 90, 90), _c("c", "C", 70, 50)])
    assert [c.work_id for c in ranked] == ["b", "c", "a"]


def test_emitter_is_obsidian_native(tmp_path):
    p = tmp_path / "preference-synthesis.md"
    cands = [_c("wheat-field", "Wheat Field", 90, 85), _c("irises", "Irises", 60, 70)]
    write_preference_synthesis_md("You gravitate to high-chroma rural scenes.", cands, "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/preference-synthesis"
    assert fm["artist"] == "Vincent van Gogh"
    assert "You gravitate to high-chroma rural scenes." in text
    assert "Wheat Field" in text
    # ranked list is ordered: Wheat Field (87) before Irises (65)
    assert text.index("Wheat Field") < text.index("Irises")


def test_emitter_respects_shortlist_cap(tmp_path):
    p = tmp_path / "preference-synthesis.md"
    cands = [_c(f"w{i}", f"Work {i}", 90 - i, 80) for i in range(12)]
    write_preference_synthesis_md("insight", cands, "Artist", p, shortlist_cap=8)
    text = p.read_text(encoding="utf-8")
    assert "Work 0" in text and "Work 7" in text
    # capped: the 9th-ranked work is noted as below the cap, not in the ranked table rows
    assert "shortlist cap" in text.lower()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_preference_synthesis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.preference_synthesis'`.

- [ ] **Step 3: Implement `skill/scripts/preference_synthesis.py`:**

```python
"""Stage 6 plumbing: score + rank study-set candidates and emit preference-synthesis.md.

Claude supplies the cross-set pattern insight (prose) and per-candidate pattern-fit /
studyability scores (0-100, the art-historical judgment); this module computes the
combined score, ranks the funnel, and serializes the Obsidian-native note.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

PREFERENCE_WEIGHTS: dict[str, int] = {"pattern_fit": 50, "studyability": 50}


@dataclass(frozen=True)
class StudyCandidate:
    work_id: str
    title: str
    pattern_fit: int
    studyability: int
    rationale: str


def combined_score(c: StudyCandidate) -> int:
    """Weighted average of pattern-fit + studyability, rounded to 0-100."""
    total = c.pattern_fit * PREFERENCE_WEIGHTS["pattern_fit"] + c.studyability * PREFERENCE_WEIGHTS["studyability"]
    return round(total / 100)


def rank_candidates(cands: list[StudyCandidate]) -> list[StudyCandidate]:
    """Descending by combined score; stable for ties."""
    return sorted(cands, key=combined_score, reverse=True)


def write_preference_synthesis_md(
    insight: str,
    cands: list[StudyCandidate],
    artist: str,
    path: Path | str,
    *,
    shortlist_cap: int = 8,
) -> None:
    """Emit the 'what you're drawn to' note + the ranked funnel (capped)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ranked = rank_candidates(cands)
    lines = [
        "---",
        "type: study/preference-synthesis",
        f"artist: {artist}",
        "tags:",
        "  - 'study/preference-synthesis'",
        "---",
        "",
        f"# What you're drawn to — {artist}",
        "",
        "> [!tip] Pattern across your liked set",
        f"> {insight}",
        "",
        "## Ranked study-set candidates",
        "",
        "Scored on pattern-fit + studyability. Pick your final small study set from the top.",
        "",
        "| Rank | Work | Score | Pattern-fit | Studyability | Why |",
        "| ---- | ---- | ----- | ----------- | ------------ | --- |",
    ]
    for i, c in enumerate(ranked[:shortlist_cap], start=1):
        lines.append(
            f"| {i} | [[{c.work_id}\\|{c.title}]] | {combined_score(c)} | "
            f"{c.pattern_fit} | {c.studyability} | {c.rationale} |"
        )
    if len(ranked) > shortlist_cap:
        dropped = len(ranked) - shortlist_cap
        lines += [
            "",
            f"> [!note] {dropped} more candidate(s) fell below the shortlist cap "
            f"({shortlist_cap}) and are omitted from the ranked table.",
        ]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_preference_synthesis.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/preference_synthesis.py tests/test_preference_synthesis.py
git commit -m "feat: preference-synthesis ranking + Obsidian note emitter (stage 6)"
```

---

### Task 5: visual-analysis emitter (analysis.md)

Stage 7. On the funnel-selected study set only, Claude runs the formal-analysis 5-stage instruction set per work; this script serializes that judgment into one `analysis.md` (a section per work) from a reusable template, including the technique-imitation checklist and a predict-then-reveal callout. MVP — the prose is Claude's; the script enforces the template + Obsidian formatting.

**Files:**
- Create: `skill/scripts/analysis.py`
- Test: `tests/test_analysis.py`

**Interfaces:**
- Consumes: `scripts.frontmatter.parse_frontmatter` (tests only).
- Produces:
  - `WorkAnalysis` (frozen dataclass): `work_id: str`, `title: str`, `structural_skeleton: str`, `notan: str`, `palette: str`, `layering: str`, `traps: str`, `grammar_crosscheck: str`, `imitation_checklist: list[str]`, `predict_then_reveal: str`.
  - `ANALYSIS_STAGES: tuple[str, ...]` — the five stage labels in order.
  - `write_analysis_md(works: list[WorkAnalysis], artist: str, path: Path) -> None`.

- [ ] **Step 1: Write the failing tests** — `tests/test_analysis.py`:

```python
from scripts.analysis import ANALYSIS_STAGES, WorkAnalysis, write_analysis_md
from scripts.frontmatter import parse_frontmatter


def _work(work_id="wheat-field", title="Wheat Field"):
    return WorkAnalysis(
        work_id=work_id, title=title,
        structural_skeleton="low horizon, golden-section path",
        notan="3-value: bright field / mid sky / dark cypress",
        palette="cad yellow + ultramarine shadow",
        layering="impasto over thin underpainting",
        traps="don't outline the wheat",
        grammar_crosscheck="confirms warm-light/cool-shadow; surprise: flat sky",
        imitation_checklist=["block 3 values first", "mix the shadow string"],
        predict_then_reveal="Guess the light direction before reading the notan.",
    )


def test_analysis_stages_are_the_five_set():
    assert len(ANALYSIS_STAGES) == 5


def test_emitter_is_obsidian_native_with_all_stages(tmp_path):
    p = tmp_path / "analysis.md"
    write_analysis_md([_work()], "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/analysis"
    assert fm["artist"] == "Vincent van Gogh"
    for stage in ANALYSIS_STAGES:
        assert stage in text
    assert "Wheat Field" in text
    assert "[!example]" in text  # predict-then-reveal callout
    assert "block 3 values first" in text  # checklist item rendered


def test_emitter_renders_each_work_section(tmp_path):
    p = tmp_path / "analysis.md"
    write_analysis_md([_work("a", "Alpha"), _work("b", "Beta")], "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert "## Alpha" in text and "## Beta" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_analysis.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.analysis'`.

- [ ] **Step 3: Implement `skill/scripts/analysis.py`:**

```python
"""Stage 7 emitter: serialize the 5-stage formal analysis of the study set to analysis.md.

Claude does the deep-reading (the WorkAnalysis content); this module enforces the reusable
template + Obsidian formatting (predict-then-reveal as an [!example] callout, the
technique-imitation checklist as a job aid). One file, one section per study-set work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# The formal-analysis 5-stage instruction set (spec stage 7).
ANALYSIS_STAGES: tuple[str, ...] = (
    "Structural skeleton",
    "Notan mapping",
    "Palette archaeology",
    "Technical layering hypothesis",
    "Traps & misconceptions",
)


@dataclass(frozen=True)
class WorkAnalysis:
    work_id: str
    title: str
    structural_skeleton: str
    notan: str
    palette: str
    layering: str
    traps: str
    grammar_crosscheck: str
    imitation_checklist: list[str]
    predict_then_reveal: str


def write_analysis_md(works: list[WorkAnalysis], artist: str, path: Path | str) -> None:
    """Emit analysis.md: one section per work, all five formal-analysis stages."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: study/analysis",
        f"artist: {artist}",
        "tags:",
        "  - 'study/analysis'",
        "---",
        "",
        f"# Visual analysis — {artist}",
        "",
    ]
    for w in works:
        body = {
            "Structural skeleton": w.structural_skeleton,
            "Notan mapping": w.notan,
            "Palette archaeology": w.palette,
            "Technical layering hypothesis": w.layering,
            "Traps & misconceptions": w.traps,
        }
        lines += [f"## {w.title}", f"`work: [[{w.work_id}]]`", ""]
        lines += ["> [!example] Predict, then reveal", f"> {w.predict_then_reveal}", ""]
        for stage in ANALYSIS_STAGES:
            lines += [f"### {stage}", body[stage], ""]
        lines += ["### Grammar cross-check", w.grammar_crosscheck, ""]
        lines += ["### Technique-imitation checklist"]
        lines += [f"- [ ] {item}" for item in w.imitation_checklist]
        lines += [""]
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_analysis.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/analysis.py tests/test_analysis.py
git commit -m "feat: visual-analysis emitter — 5-stage analysis.md (stage 7)"
```

---

### Task 6: study & retention emitters

Stage 8. Emit `study-notes.md` (faded aids: cheat-sheet → checklist → bare prompt), `review-schedule.md` (spaced + interleaved), and a `drills/discrimination-cards.md` (A-vs-not-A). MVP per spec §9 — defer full FSRS deck generation and gapped-worksheet generators; emit the thin, structured versions.

**Files:**
- Create: `skill/scripts/study_retention.py`
- Test: `tests/test_study_retention.py`

**Interfaces:**
- Consumes: `scripts.frontmatter.parse_frontmatter` (tests only).
- Produces:
  - `StudyNote` (frozen dataclass): `work_id: str`, `title: str`, `notice_first: str`, `decisions_to_imitate: list[str]`, `traps: list[str]`, `exercises: list[str]`.
  - `DiscriminationCard` (frozen dataclass): `trait: str`, `is_a: str`, `not_a: str`.
  - `ReviewItem` (frozen dataclass): `day: int`, `focus: str`, `mode: str`.
  - `write_study_notes_md(notes: list[StudyNote], artist: str, path) -> None`.
  - `write_discrimination_cards_md(cards: list[DiscriminationCard], artist: str, path) -> None`.
  - `write_review_schedule_md(items: list[ReviewItem], artist: str, path) -> None`.

- [ ] **Step 1: Write the failing tests** — `tests/test_study_retention.py`:

```python
from scripts.frontmatter import parse_frontmatter
from scripts.study_retention import (
    DiscriminationCard,
    ReviewItem,
    StudyNote,
    write_discrimination_cards_md,
    write_review_schedule_md,
    write_study_notes_md,
)


def test_study_notes_is_obsidian_native_with_faded_aids(tmp_path):
    p = tmp_path / "study-notes.md"
    note = StudyNote(
        work_id="wheat-field", title="Wheat Field",
        notice_first="the value of the sky vs field",
        decisions_to_imitate=["limit to 3 values", "warm the lights"],
        traps=["don't outline"],
        exercises=["10-min value thumbnail"],
    )
    write_study_notes_md([note], "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/notes"
    assert "Wheat Field" in text
    # faded aids: cheat sheet -> checklist -> bare prompt
    assert "Cheat sheet" in text and "Checklist" in text and "Bare prompt" in text
    assert "[!warning]" in text  # traps callout
    assert "limit to 3 values" in text


def test_discrimination_cards_render_a_vs_not_a(tmp_path):
    p = tmp_path / "discrimination-cards.md"
    cards = [DiscriminationCard(trait="lost edges", is_a="edge dissolves into shadow",
                                not_a="edge stays crisp in shadow")]
    write_discrimination_cards_md(cards, "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert parse_frontmatter(text)["type"] == "study/drills"
    assert "lost edges" in text
    assert "edge dissolves into shadow" in text
    assert "edge stays crisp in shadow" in text


def test_review_schedule_is_spaced_table(tmp_path):
    p = tmp_path / "review-schedule.md"
    items = [ReviewItem(day=1, focus="Wheat Field value map", mode="reconstruct"),
             ReviewItem(day=3, focus="interleave: edges across works", mode="discriminate")]
    write_review_schedule_md(items, "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert parse_frontmatter(text)["type"] == "study/review-schedule"
    assert "Day 1" in text and "Day 3" in text
    assert "reconstruct" in text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_study_retention.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.study_retention'`.

- [ ] **Step 3: Implement `skill/scripts/study_retention.py`:**

```python
"""Stage 8 emitters: study-notes.md (faded aids), discrimination cards, review schedule.

MVP (spec section 9 defers full FSRS deck + gapped-worksheet generators). Claude supplies
the pedagogy content; this module serializes the Obsidian-native artifacts with the
faded-aids structure (cheat sheet -> checklist -> bare prompt) and study callouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class StudyNote:
    work_id: str
    title: str
    notice_first: str
    decisions_to_imitate: list[str]
    traps: list[str]
    exercises: list[str]


@dataclass(frozen=True)
class DiscriminationCard:
    trait: str
    is_a: str
    not_a: str


@dataclass(frozen=True)
class ReviewItem:
    day: int
    focus: str
    mode: str


def _frontmatter(doc_type: str, artist: str) -> list[str]:
    return ["---", f"type: {doc_type}", f"artist: {artist}", "tags:",
            f"  - '{doc_type}'", "---", ""]


def write_study_notes_md(notes: list[StudyNote], artist: str, path: Path | str) -> None:
    """Per-work notes as faded aids: cheat sheet -> checklist -> bare prompt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/notes", artist) + [f"# Study notes — {artist}", ""]
    for n in notes:
        lines += [f"## {n.title}", f"`work: [[{n.work_id}]]`", ""]
        # Aid 1 — cheat sheet (most support)
        lines += ["### Cheat sheet", f"> [!tip] Notice first", f"> {n.notice_first}", ""]
        lines += ["Decisions to imitate:"]
        lines += [f"- {d}" for d in n.decisions_to_imitate]
        lines += ["", "> [!warning] Traps"]
        lines += [f"> - {t}" for t in n.traps]
        lines += [""]
        # Aid 2 — checklist (less support)
        lines += ["### Checklist", "Before you call the study done:"]
        lines += [f"- [ ] {d}" for d in n.decisions_to_imitate]
        lines += [""]
        # Aid 3 — bare prompt (no support)
        lines += ["### Bare prompt",
                  f"> [!example] From memory", f"> {n.exercises[0] if n.exercises else 'Reproduce the value structure from memory.'}",
                  ""]
        if len(n.exercises) > 1:
            lines += ["Further exercises:"] + [f"- {e}" for e in n.exercises[1:]] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_discrimination_cards_md(cards: list[DiscriminationCard], artist: str, path: Path | str) -> None:
    """A-vs-not-A perceptual discrimination set (interleaving drill)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/drills", artist) + [
        f"# Discrimination cards — {artist}", "",
        "| Trait | Is (A) | Is not (not-A) |",
        "| ----- | ------ | -------------- |",
    ]
    for c in cards:
        lines.append(f"| {c.trait} | {c.is_a} | {c.not_a} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_schedule_md(items: list[ReviewItem], artist: str, path: Path | str) -> None:
    """Spaced + interleaved review plan."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/review-schedule", artist) + [
        f"# Review schedule — {artist}", "",
        "Spaced + interleaved across works and styles.", "",
        "| When | Focus | Mode |",
        "| ---- | ----- | ---- |",
    ]
    for it in sorted(items, key=lambda x: x.day):
        lines.append(f"| Day {it.day} | {it.focus} | {it.mode} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_study_retention.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/study_retention.py tests/test_study_retention.py
git commit -m "feat: study & retention emitters — notes/cards/schedule (stage 8)"
```

---

### Task 7: SKILL.md wiring + final verification

Thread the new scripts into the Stage 5–8 narrative so the orchestrator actually invokes them and marks stages complete via `PipelineState`. Plans 1–2 left SKILL.md as a skeleton; this connects the tooling. Also resolve the deferred Stage-2 LLM-routing note from the carry-forward (document the routing decision in SKILL.md prose) and update the SKILL.md test to assert the new scripts are referenced.

**Files:**
- Modify: `skill/SKILL.md`
- Modify: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: every script built in Tasks 2–6, plus `scripts.state.PipelineState`.
- Produces: SKILL.md prose referencing `scripts.gallery`, `scripts.selection`, `scripts.preference_synthesis`, `scripts.analysis`, `scripts.study_retention`, and a stage-completion convention.

- [ ] **Step 1: Write the failing test** — append to `tests/test_skill_md.py`:

```python
def test_skill_md_references_plan3_scripts():
    text = SKILL_MD.read_text(encoding="utf-8")
    for module in ("scripts.gallery", "scripts.selection", "scripts.preference_synthesis",
                   "scripts.analysis", "scripts.study_retention"):
        assert module in text, f"SKILL.md does not wire {module}"


def test_skill_md_documents_stage_completion():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "mark_complete" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: FAIL — `assert 'scripts.gallery' in text` fails.

- [ ] **Step 3: Wire the stages in `skill/SKILL.md`.** Replace the "Run A" stage-5 bullet, the Run B / Run C sections, and add a stage-completion convention. Update stage 5 (line ~44) to:

```markdown
5. **image_discovery** — see `wiki/stage-image-discovery.md`. Download high-res
   candidates to `images/candidates/<work>/` with `scripts.image_download`, then
   generate the contact sheet:
   `uv run python -c "from scripts.gallery import write_gallery; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); write_gallery(sp.candidates_dir, '<ARTIST>', sp.gallery_html)"`
   Mark the stage complete, save state, and STOP for Human Pause 1.
```

- [ ] **Step 4: Replace Run B (stage 6) section** with:

```markdown
## Run B — synthesis + funnel (stage 6)

6. **preference_synthesis** — gated on `selection.json`. First validate the human's
   curation:
   `uv run python -c "from scripts.selection import load_selection, validate_selection, apply_selection; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); sel=load_selection(sp.selection_json,'<ARTIST>'); print(validate_selection(sel) or 'ok'); apply_selection(sel, sp.candidates_dir, sp.selected_dir)"`
   If validation returns errors, print them and STOP. Otherwise analyze the liked set
   for patterns (your judgment), score each study-set candidate on pattern-fit +
   studyability, and emit the note with `scripts.preference_synthesis.write_preference_synthesis_md`.
   Then mark the stage complete, save state, and STOP for Human Pause 2.
```

- [ ] **Step 5: Replace Run C (stages 7–8) section** with:

```markdown
## Run C — study (stages 7–8)

7. **visual_analysis** — gated on a chosen study set. See
   `wiki/stage-visual-analysis.md`. Run the 5-stage formal-analysis instruction set
   per study-set work, cross-check against the artist grammar, then serialize with
   `scripts.analysis.write_analysis_md` → `analysis.md`. Mark complete and save state.
8. **study_retention** — see `wiki/stage-study-retention.md`. Emit the faded-aids
   `study-notes.md`, the `drills/discrimination-cards.md`, and `review-schedule.md`
   via `scripts.study_retention` (`write_study_notes_md`, `write_discrimination_cards_md`,
   `write_review_schedule_md`). Mark complete and save state.
```

- [ ] **Step 6: Add a stage-completion convention** to the "How to run" section (after the existing step 3, around line 26). Append:

```markdown
4. **Mark a stage complete** after its outputs are written, before moving on:
   `uv run python -c "from scripts.state import PipelineState; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); s=PipelineState.load(sp.state_json,'<ARTIST>'); s.mark_complete('<STAGE_ID>'); s.save(sp.state_json)"`
   Stages are idempotent — re-running overwrites their own outputs without corrupting
   prior stages.

> [!note] Stage-2 source routing
> `scripts.source_signals.needs_llm_review` flags `borderline`-band pages for rubric
> scoring. Also route any **high-value** page (seed domains: Smarthistory, Met, CAA;
> or a page a later stage will cite) through the rubric even if its band is `high`, so
> trust scores on load-bearing sources are confirmed, not assumed.
```

- [ ] **Step 7: Run the full test suite to verify everything passes**

Run: `uv run pytest -v`
Expected: PASS — all prior tests (74 from Plan 2) plus the new modules (selection 9 + gallery 4 + preference 5 + analysis 3 + study_retention 3 + image_download 2 + skill_md 2 ≈ 28 new). 0 warnings.

- [ ] **Step 8: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit -m "feat: wire stages 5-8 + stage-completion + source-routing note into SKILL.md"
```

---

## Self-Review

**1. Spec coverage** (spec §4 stages 6–8, §5, §6):
- §5 gallery (grid / detail / star auto-advance / curatorial gate ≥4★ / export + selected/ copy) → Task 3 (gallery) + Task 2 (`apply_selection` copies the liked set). ✓
- `selection.json` round-trip (parse + validation) → Task 2. ✓
- §4 Stage 6 preference synthesis (insight note + pattern-fit/studyability ranked funnel) → Task 4. ✓
- §4 Stage 7 visual analysis (5-stage set, grammar cross-check, predict-then-reveal, imitation checklist) → Task 5. ✓
- §4 Stage 8 study/retention (faded-aids notes, discrimination cards, review schedule) → Task 6. ✓
- §6 output contract files (`gallery.html`, `selection.json`, `preference-synthesis.md`, `analysis.md`, `study-notes.md`, `drills/`, `review-schedule.md`, `images/selected/`) → emitted across Tasks 2–6. ✓
- §7 resume/idempotency → Task 7 stage-completion convention (uses existing `PipelineState`). ✓
- Carry-forward (`default_fetch` UA + exceptions) → Task 1; Stage-2 routing note → Task 7. ✓
- `prompts/` population: scaffolded by Plan 1 (`prompts_dir`); spec §6 lists it but no §4 stage emits it programmatically — it's populated by Claude copying reusable prompts during the run, not a script. Left as a SKILL.md-driven copy, no dedicated task. (Noted, not a gap.)
- Deferred (spec §9), correctly NOT built: full FSRS deck, gapped-worksheet generator, overlay markup / compare view, palette extraction, OCR, LLM-as-judge. ✓

**2. Placeholder scan:** No "TBD"/"add error handling"/"similar to Task N" — every code step shows complete code; every command shows expected output. ✓

**3. Type consistency:** `selection.parse_selection` output shape == the JSON the gallery JS exports (work_id, iiif_token, image_rel, rating, thesis, anchor_trait, handoff_note). `LIKED_THRESHOLD`/`LIKED=4` consistent across `selection.py` and the gallery template. `combined_score`/`rank_candidates`/`write_preference_synthesis_md` signatures match their tests. `ANALYSIS_STAGES` (5 labels) used identically in `analysis.py` and its test. Emitter `type:` frontmatter values (`study/preference-synthesis`, `study/analysis`, `study/notes`, `study/drills`, `study/review-schedule`) match their assertions. ✓

## Execution Handoff

Process notes carried from Plans 1–2 (for whoever executes): fresh implementer subagent per task, two-stage review (spec ✅ + quality) after each, broad whole-branch review at the end, then **superpowers:finishing-a-development-branch**. Durable ledger at `$(git rev-parse --git-path sdd)/progress.md` — check it after any resume/compaction. Branch convention: `feature/skill-curation-study` → `--no-ff` merge to `main`.
</content>
</invoke>
