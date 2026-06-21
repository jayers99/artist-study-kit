# Narrowing Funnel + Skip-Discovery Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a two-stage progressive-zoom curation funnel (board → ~2-wide zoom of the selected set with full-size images → cut to ≤4 → interview only those) plus a skip-discovery study mode.

**Architecture:** The Spec-A board template evolves into a two-stage funnel: stage 1 is the existing board; "Next" freezes the wide cut and re-renders a zoomed grid of just those works at full size; "Commit" exports a new `study-set.json` (≤4) alongside Spec-A's `stars.json`/`selection.json`. Downstream high-res resolution and the Socratic interview are bounded to the study_set via an `only` filter; a `has_candidates` guard lets a study session skip discovery. Spec: `docs/superpowers/specs/2026-06-20-narrowing-funnel-skip-discovery-design.md`.

**Tech Stack:** Python 3.12, dataclasses, pytest, uv, self-contained HTML/JS. No new dependencies.

## Global Constraints

- **Test command:** `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest` from the repo root. Imports resolve as `from scripts.x import y` (pythonpath = `skill`).
- **The cap:** `MAX_STUDY = 4`. Commit is enabled only when the live narrow count is in `1..MAX_STUDY`; ingest truncates a study_set to `max_study` (default 4).
- **Wide vs narrow:** the wide cut is **frozen on Next** (a session record → `selection.json`/`selected`); the narrow cut is the live still-selected subset at Commit (→ `study-set.json`/`study_set`, `⊆` wide, `len ≤ MAX_STUDY`). Everything expensive — high-res resolve + visual analysis + interview — runs on the **study_set only**.
- **Stars ⊥ selection still holds** (Spec A): the funnel never reads a star to decide selection or the study set.
- **Full-size at zoom is display-only:** hotlinked, rights-agnostic (same rule as thumbnail browsing); it is NOT the rights-gated download in `resolve.py`.
- **Two stages only** (no third/adaptive zoom). Stage 2 shows only the wide-cut works.
- **No new deps. Backward-compat:** new function params are optional and default to Spec-A behavior; existing callers/tests must keep passing.
- **Commits:** `git commit --no-gpg-sign`; stage only the named files (never `git add -A`); end the message body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Quote shell paths** (repo is in iCloud).

---

## File Structure

- `skill/scripts/museum_search.py` — add `display_url(candidate)` (best-effort full-size display URL). (Task 1)
- `skill/scripts/state.py` — add `PackageState.has_candidates()`. (Task 2)
- `skill/scripts/paths.py` + `skill/scripts/selection.py` — `study_set_json` path + `parse_study_set`/`load_study_set`. (Task 3)
- `skill/scripts/resolve.py` + `skill/scripts/selection.py` — `only=` filter on `resolve_selection` and `apply_selection`. (Task 4)
- `skill/scripts/gallery.py` — `build_thumbnail_gallery` payload gains `full_url`. (Task 5)
- `skill/scripts/gallery.py` — `_THUMB_TEMPLATE` two-stage funnel (Next/zoom/Commit, wide snapshot, cap, `study-set.json`). (Task 6)
- `skill/SKILL.md` — funnel flow, study_set-bounded downstream, skip-discovery mode. (Task 7)
- Tests: `tests/test_museum_search.py`, `tests/test_state.py`, `tests/test_paths.py`, `tests/test_selection.py`, `tests/test_resolve.py`, `tests/test_gallery.py`, `tests/test_skill_md.py`.

---

### Task 1: display_url — best-effort full-size display image

**Files:**
- Modify: `skill/scripts/museum_search.py` (add `import re` + the function)
- Test: `tests/test_museum_search.py`

**Interfaces:**
- Consumes: a candidate with attrs `thumbnail_url`, and optionally `origin`/`local_path` (read via `getattr`).
- Produces: `display_url(candidate) -> str` — for an IIIF URL (`…/full/<size>/<rot>/default.<ext>`) returns the same URL with the size segment swapped to `843,`; for `origin=="user"` with a `local_path` returns that; otherwise returns `thumbnail_url` unchanged.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_museum_search.py`:

```python
def test_display_url_swaps_iiif_size_segment():
    from scripts.museum_search import display_url, ThumbnailCandidate
    c = ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="https://www.artic.edu/iiif/2/c969-aaa/full/400,/0/default.jpg",
        source_url="https://www.artic.edu/artworks/10018", date="1922", rights="in_copyright")
    assert display_url(c) == "https://www.artic.edu/iiif/2/c969-aaa/full/843,/0/default.jpg"


def test_display_url_non_iiif_falls_back_to_thumbnail():
    from scripts.museum_search import display_url, ThumbnailCandidate
    c = ThumbnailCandidate(
        work_id="w", title="T", museum="x", thumbnail_url="https://x/plain/thumb.jpg",
        source_url="https://x/1", date="", rights="unknown")
    assert display_url(c) == "https://x/plain/thumb.jpg"


def test_display_url_user_origin_uses_local_path():
    from scripts.museum_search import display_url
    from scripts.state import BoardCandidate
    c = BoardCandidate(work_id="mine", title="", date="", museum="", thumbnail_url="",
                       source_url="", rights="", origin="user", local_path="images/user/mine.jpg")
    assert display_url(c) == "images/user/mine.jpg"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_museum_search.py -k display_url -v`
Expected: FAIL — `ImportError: cannot import name 'display_url'`.

- [ ] **Step 3: Implement the function**

In `skill/scripts/museum_search.py`, add `import re` to the import block (after `import unicodedata`). Then add near the other module-level helpers (e.g. after `_fold`):

```python
# IIIF Image API URL: {id}/{region}/{size}/{rotation}/{quality}.{fmt}; swap the size.
_IIIF_SIZE = re.compile(r"(/full/)[^/]+(/\d+/default\.\w+)$")
_DISPLAY_SIZE = "843,"


def display_url(candidate) -> str:
    """Best-effort largest *display* image for close looking (hotlinked, display-only).

    IIIF sources -> swap the thumbnail size segment for ~843px; user images -> their
    local file; everything else -> the thumbnail URL unchanged. No network."""
    if getattr(candidate, "origin", "discovered") == "user":
        local = getattr(candidate, "local_path", "")
        if local:
            return local
    url = getattr(candidate, "thumbnail_url", "") or ""
    if _IIIF_SIZE.search(url):
        return _IIIF_SIZE.sub(rf"\g<1>{_DISPLAY_SIZE}\g<2>", url)
    return url
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_museum_search.py -v`
Expected: PASS (all, including pre-existing museum_search tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/museum_search.py tests/test_museum_search.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: display_url — full-size IIIF image for the zoom stage

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PackageState.has_candidates (skip-discovery guard)

**Files:**
- Modify: `skill/scripts/state.py` (add a method to `PackageState`)
- Test: `tests/test_state.py`

**Interfaces:**
- Produces: `PackageState.has_candidates() -> bool` — `True` when `candidates` is non-empty.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
def test_has_candidates_reflects_board():
    st = PackageState(artist="x")
    assert st.has_candidates() is False
    st.candidates = [BoardCandidate(work_id="a", title="", date="", museum="",
                                    thumbnail_url="", source_url="", rights="")]
    assert st.has_candidates() is True
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -k has_candidates -v`
Expected: FAIL — `AttributeError: 'PackageState' object has no attribute 'has_candidates'`.

- [ ] **Step 3: Implement the method**

In `skill/scripts/state.py`, add to `PackageState` (after `studied_work_ids`):

```python
    def has_candidates(self) -> bool:
        """True when the board already holds candidates (skip-discovery can study it)."""
        return bool(self.candidates)
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: PackageState.has_candidates (skip-discovery guard)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: study-set.json — path + parse/load

**Files:**
- Modify: `skill/scripts/paths.py` (add `study_set_json` property)
- Modify: `skill/scripts/selection.py` (add `parse_study_set` + `load_study_set`)
- Test: `tests/test_paths.py`, `tests/test_selection.py`

**Interfaces:**
- Produces:
  - `StudyPaths.study_set_json -> Path` = `root / "study-set.json"`.
  - `parse_study_set(data: dict, *, max_study: int = 4) -> list[str]` — `data["study_set"]` as work_ids, truncated to `max_study`.
  - `load_study_set(path, artist, *, max_study: int = 4) -> list[str]` — read the file, check `artist`, return ids (raise `ValueError` on artist mismatch).

- [ ] **Step 1: Write the failing path test**

Add to `tests/test_paths.py`:

```python
def test_study_set_json_path():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.study_set_json == sp.root / "study-set.json"
```

- [ ] **Step 2: Write the failing selection tests**

Add to `tests/test_selection.py`:

```python
def test_parse_study_set_returns_ids_truncated_to_max():
    from scripts.selection import parse_study_set
    data = {"artist": "x", "study_set": ["a", "b", "c", "d", "e"]}
    assert parse_study_set(data) == ["a", "b", "c", "d"]            # default max 4
    assert parse_study_set(data, max_study=2) == ["a", "b"]


def test_load_study_set_reads_file_and_checks_artist(tmp_path):
    import json as _json
    from scripts.selection import load_study_set
    p = tmp_path / "study-set.json"
    p.write_text(_json.dumps({"artist": "x", "study_set": ["a", "b"]}), encoding="utf-8")
    assert load_study_set(p, "x") == ["a", "b"]


def test_load_study_set_artist_mismatch_raises(tmp_path):
    import json as _json
    import pytest
    from scripts.selection import load_study_set
    p = tmp_path / "study-set.json"
    p.write_text(_json.dumps({"artist": "other", "study_set": ["a"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_study_set(p, "x")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_paths.py tests/test_selection.py -k "study_set" -v`
Expected: FAIL — `AttributeError: 'StudyPaths' object has no attribute 'study_set_json'` / `ImportError`.

- [ ] **Step 4: Add the path property**

In `skill/scripts/paths.py`, add to `StudyPaths` (after the `selection_json` property):

```python
    @property
    def study_set_json(self) -> Path:
        return self.root / "study-set.json"
```

- [ ] **Step 5: Add the parse/load functions**

In `skill/scripts/selection.py`, add after `load_selection` (the module already imports `json` and `Path`):

```python
def parse_study_set(data: dict, *, max_study: int = 4) -> list[str]:
    """The ordered narrow-cut work_ids from study-set.json, truncated to max_study."""
    ids = [str(w) for w in data.get("study_set", [])]
    return ids[:max_study]


def load_study_set(path: Path, artist: str, *, max_study: int = 4) -> list[str]:
    """Load study-set.json; raise ValueError on artist mismatch."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if str(data.get("artist", "")) != artist:
        raise ValueError(f"study-set.json artist {data.get('artist')!r} != requested {artist!r}")
    return parse_study_set(data, max_study=max_study)
```

- [ ] **Step 6: Run the tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_paths.py tests/test_selection.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add skill/scripts/paths.py skill/scripts/selection.py tests/test_paths.py tests/test_selection.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: study-set.json path + parse/load (narrow cut, capped at MAX_STUDY)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Bound resolve/apply to the study set (`only=` filter)

**Files:**
- Modify: `skill/scripts/resolve.py` (`resolve_selection` gains `only=`)
- Modify: `skill/scripts/selection.py` (`apply_selection` gains `only=`)
- Test: `tests/test_resolve.py`, `tests/test_selection.py`

**Interfaces:**
- Consumes: `selected_rows` (existing).
- Produces:
  - `resolve_selection(sel, selected_dir, *, resolvers=RESOLVERS, download=download_candidate, only: set | None = None)` — when `only` is given, resolve only `selected_rows` whose `work_id ∈ only`; `None` resolves all selected (Spec-A behavior).
  - `apply_selection(sel, candidates_dir, selected_dir, *, only: set | None = None)` — same filter.

- [ ] **Step 1: Write the failing resolve test**

Add to `tests/test_resolve.py` (mirrors the existing manifest test's wiring):

```python
def test_resolve_selection_only_filters_to_study_set(tmp_path):
    sel = Selection(artist="paul-klee", ratings=[
        _entry(work_id="fish-magic", selected=True, inst_ids=(("commons_file", "Fish.jpg"),)),
        _entry(work_id="senecio", selected=True, inst_ids=(("commons_file", "Sen.jpg"),)),
    ])

    def fake_download(cand, sel_dir):
        return SimpleNamespace(status="downloaded", image_path=sel_dir / f"{cand.work_id}.jpg")

    out = resolve_selection(sel, tmp_path, resolvers=[lambda e: _cand(e.work_id)],
                            download=fake_download, only={"fish-magic"})
    assert [r.work_id for r in out] == ["fish-magic"]   # senecio excluded by `only`
```

- [ ] **Step 2: Write the failing apply test**

Add to `tests/test_selection.py`:

```python
def test_apply_selection_only_filters_to_study_set(tmp_path):
    cdir = tmp_path / "candidates"
    for wid in ("a", "b"):
        (cdir / wid).mkdir(parents=True)
        (cdir / wid / "t.jpg").write_bytes(b"img")
    sdir = tmp_path / "selected"
    sel = parse_selection({"artist": "x", "ratings": [
        {"work_id": "a", "iiif_token": "t", "image_rel": "images/candidates/a/t.jpg", "selected": True},
        {"work_id": "b", "iiif_token": "t", "image_rel": "images/candidates/b/t.jpg", "selected": True},
    ]})
    out = apply_selection(sel, cdir, sdir, only={"a"})
    assert len(out) == 1 and out[0].name.startswith("a-")
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_resolve.py tests/test_selection.py -k only -v`
Expected: FAIL — `TypeError: ... got an unexpected keyword argument 'only'`.

- [ ] **Step 4: Add `only=` to `resolve_selection`**

In `skill/scripts/resolve.py`, change the signature and the loop:

```python
def resolve_selection(sel, selected_dir, *, resolvers=RESOLVERS, download=download_candidate,
                      only: set | None = None) -> list[Resolved]:
    """Resolve every explicitly-selected work (optionally bounded to `only` work_ids);
    write selected_dir/resolved.json; return the results."""
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Resolved] = []
    for rating in selected_rows(sel):
        if only is not None and rating.work_id not in only:
            continue
        out.append(resolve_selected(rating, selected_dir, resolvers=resolvers, download=download))
```

(Leave the manifest-writing tail and `return out` unchanged.)

- [ ] **Step 5: Add `only=` to `apply_selection`**

In `skill/scripts/selection.py`, change `apply_selection`:

```python
def apply_selection(
    sel: Selection,
    candidates_dir: Path | str,
    selected_dir: Path | str,
    *,
    only: set | None = None,
) -> list[Path]:
    """Copy explicitly-selected images into selected_dir (optionally bounded to `only`
    work_ids); idempotent."""
    candidates_dir = Path(candidates_dir)
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for r in selected_rows(sel):
        if only is not None and r.work_id not in only:
            continue
        src = candidates_dir / r.work_id / Path(r.image_rel).name
        if not src.is_file():
            continue
        dst = selected_dir / f"{r.work_id}-{Path(r.image_rel).name}"
        if not dst.is_file():
            shutil.copy2(src, dst)
        out.append(dst)
    return out
```

- [ ] **Step 6: Run the tests to verify they pass (and Spec-A callers still pass)**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_resolve.py tests/test_selection.py -v`
Expected: PASS, including the existing `only=None` resolve/apply tests (default behavior unchanged).

- [ ] **Step 7: Commit**

```bash
git add skill/scripts/resolve.py skill/scripts/selection.py tests/test_resolve.py tests/test_selection.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: bound resolve/apply to the study set via optional only= filter

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Gallery payload — full_url for the zoom stage

**Files:**
- Modify: `skill/scripts/gallery.py` (`build_thumbnail_gallery` payload + import)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: `display_url` (Task 1), the existing Task-6-from-Spec-A payload loop.
- Produces: each payload row gains `full_url := display_url(c)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gallery.py`:

```python
def test_thumbnail_gallery_payload_carries_full_url():
    import json as _json
    from scripts.museum_search import ThumbnailCandidate
    cand = ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="https://www.artic.edu/iiif/2/c969/full/400,/0/default.jpg",
        source_url="https://x/1", date="1922", rights="in_copyright")
    html = build_thumbnail_gallery([cand], "X")
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    assert data["candidates"][0]["full_url"] == \
        "https://www.artic.edu/iiif/2/c969/full/843,/0/default.jpg"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -k full_url -v`
Expected: FAIL — `KeyError: 'full_url'`.

- [ ] **Step 3: Add the import and payload field**

In `skill/scripts/gallery.py`, add the import (next to `from scripts.dates import parse_year`):

```python
from scripts.museum_search import display_url
```

In `build_thumbnail_gallery`, add to the per-row payload dict (alongside `"bytes": size,`):

```python
            "full_url": display_url(c),
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: PASS (all gallery tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: gallery payload carries full_url for the zoom stage

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Funnel template — Next / zoom / Commit (wide snapshot, cap, study-set.json)

**Files:**
- Modify: `skill/scripts/gallery.py` (`_THUMB_TEMPLATE` only)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: the Task-5 payload (`full_url`) and Spec-A payload keys (`stars`, `selected`, `year`, `bytes`, `image_rel`).
- Produces: a two-stage funnel board. New markers present in the HTML: `id="next"`, `id="commit"`, `MAX_STUDY`, `wideCut`, `study-set.json`, `renderZoom`, and the zoom `<img>` uses `full_url`. All Spec-A markers remain (`seedStars`, `data-select`, `id="star-filter"`, `id="sort"`, `stars.json`, `selection.json`, `data-star`).

This task replaces one large HTML/JS string. The tests assert on **marker substrings**; keep the exact tokens above present.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_gallery.py`:

```python
def test_funnel_template_has_two_stage_controls_and_study_set_export():
    from scripts.state import BoardCandidate
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    # stage controls
    assert 'id="next"' in html
    assert 'id="commit"' in html
    # the cap constant + the wide-cut snapshot variable
    assert "MAX_STUDY" in html
    assert "wideCut" in html
    # zoom render path + the third export file
    assert "renderZoom" in html
    assert "study-set.json" in html
    # the zoom image uses the full-size url
    assert "full_url" in html


def test_funnel_template_keeps_spec_a_markers():
    from scripts.state import BoardCandidate
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    for marker in ("seedStars", "data-select", 'id="star-filter"', 'id="sort"',
                   "stars.json", "selection.json", "data-star"):
        assert marker in html, marker
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -k "funnel_template" -v`
Expected: FAIL — `id="next"` / `MAX_STUDY` markers absent.

- [ ] **Step 3: Replace `_THUMB_TEMPLATE`**

Replace the entire `_THUMB_TEMPLATE = """..."""` string in `skill/scripts/gallery.py` with:

```python
_THUMB_TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Curation board — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 0; background: #111; color: #eee; }
  header { padding: 0.75rem 1rem; background: #1c1c1c; position: sticky; top: 0; z-index: 5;
           display: flex; align-items: center; gap: 1rem; flex-wrap: wrap; }
  header strong { font-size: 1.05rem; }
  #controls label { font-size: 12px; color: #bbb; margin-right: 0.5rem; }
  #controls select { font-size: 12px; }
  #grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(190px, 1fr));
          gap: 10px; padding: 1rem; }
  #grid.zoom { grid-template-columns: repeat(auto-fill, minmax(620px, 1fr)); gap: 18px; }
  .card { background: #1c1c1c; border: 2px solid transparent; border-radius: 4px; overflow: hidden; }
  .card.selected { border-color: #4a90ff; }
  .card img { width: 100%; height: 200px; object-fit: contain; background: #000; display: block; }
  #grid.zoom .card img { height: 70vh; }
  .meta { padding: 6px 8px; font-size: 12px; }
  .meta .title { font-weight: 600; }
  .meta .sub { color: #999; font-size: 11px; margin: 2px 0; }
  .badge { font-size: 10px; padding: 1px 5px; border-radius: 3px; }
  .badge.pd { background: #1d5e2a; color: #d7ffd9; }
  .badge.copy { background: #5e1d1d; color: #ffd7d7; }
  .badge.user { background: #5b3; color: #042; }
  .stars .star { font-size: 1.25rem; cursor: pointer; color: #555; }
  .stars .star.on { color: gold; }
  .selbox { font-size: 12px; cursor: pointer; color: #9bf; user-select: none; }
  a.src { color: #7aa7ff; font-size: 11px; }
  button { font-size: 0.95rem; padding: 0.4rem 0.9rem; cursor: pointer; }
  button:disabled { opacity: 0.4; cursor: not-allowed; }
</style>
</head>
<body>
<header>
  <strong>Curation board — __ARTIST__</strong>
  <span id="count"></span>
  <span id="controls">
    <label>stars
      <select id="star-filter">
        <option value="all">all</option>
        <option value="unstarred">unstarred</option>
        <option value="1">&ge;1</option>
        <option value="2">&ge;2</option>
        <option value="3">&ge;3</option>
        <option value="4">&ge;4</option>
        <option value="5">5</option>
      </select>
    </label>
    <label><input type="checkbox" id="only-pd"> public-domain only</label>
    <label>sort
      <select id="sort">
        <option value="year">year &uarr;</option>
        <option value="stars">stars &darr;</option>
        <option value="bytes">file size</option>
      </select>
    </label>
  </span>
  <button id="export">Export stars + selection</button>
  <button id="next">Next &rarr; zoom</button>
  <button id="back" style="display:none">&larr; Back</button>
  <button id="commit" style="display:none" disabled>Commit study set</button>
  <span id="status"></span>
</header>
<div id="grid"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
const MAX_STUDY = 4;
// Persistent star axis (seeded) and per-session selection axis (starts empty) — orthogonal.
const stars = {};
const selected = {};
function seedStars() {
  DATA.candidates.forEach(c => { stars[c.iiif_token] = c.stars || 0; });
}
seedStars();

let stage = 1;          // 1 = board (wide scan), 2 = zoom (close look)
let wideCut = [];       // tokens frozen on Next — the session record, not mutated in stage 2

const starFilter = document.getElementById("star-filter");
const onlyPd = document.getElementById("only-pd");
const sortBy = document.getElementById("sort");
const grid = document.getElementById("grid");
const nextBtn = document.getElementById("next");
const backBtn = document.getElementById("back");
const commitBtn = document.getElementById("commit");
const exportBtn = document.getElementById("export");

function passStarFilter(c) {
  const v = starFilter.value;
  const s = stars[c.iiif_token] || 0;
  if (v === "all") return true;
  if (v === "unstarred") return s === 0;
  return s >= parseInt(v, 10);
}

function boardRows() {
  let rows = DATA.candidates.filter(c => {
    if (!passStarFilter(c)) return false;
    if (onlyPd.checked && c.rights !== "public_domain") return false;
    return true;
  });
  const mode = sortBy.value;
  rows = rows.slice().sort((a, b) => {
    if (mode === "stars") return (stars[b.iiif_token]||0) - (stars[a.iiif_token]||0);
    if (mode === "bytes") return (b.bytes||0) - (a.bytes||0);
    const ay = a.year == null ? Infinity : a.year;
    const by = b.year == null ? Infinity : b.year;
    return ay - by;
  });
  return rows;
}

function cardHtml(c, zoom) {
  const tok = c.iiif_token;
  const s = stars[tok] || 0;
  const pd = c.rights === "public_domain";
  const src = zoom ? c.full_url : c.image_rel;
  const fallback = zoom ? ' onerror="this.onerror=null;this.src=\\'' + c.image_rel + '\\'"' : '';
  let starHtml = "";
  for (let n = 1; n <= 5; n++)
    starHtml += '<span class="star' + (n <= s ? " on" : "") +
             '" data-star="' + n + '" data-tok="' + tok + '">\\u2605</span>';
  return '<img loading="lazy" src="' + src + '"' + fallback + ' alt="">' +
    '<div class="meta">' +
      '<div class="title">' + c.title + '</div>' +
      '<div class="sub">' + c.museum + ' \\u00b7 ' + (c.date || "n.d.") + ' ' +
        '<span class="badge ' + (pd ? "pd" : "copy") + '">' + (pd ? "PD" : "\\u00a9") + '</span>' +
        (c.origin === "user" ? '<span class="badge user">USER</span>' : '') + '</div>' +
      '<div class="stars">' + starHtml + '</div>' +
      '<label class="selbox"><input type="checkbox" data-select="' + tok + '"' +
        (selected[tok] ? " checked" : "") + '> select</label>' +
      '<a class="src" href="' + c.source_url + '" target="_blank">source \\u2197</a>' +
    '</div>';
}

function renderBoard() {
  grid.className = "";
  grid.innerHTML = "";
  const shown = boardRows();
  const selCount = Object.values(selected).filter(Boolean).length;
  document.getElementById("count").textContent =
    DATA.candidates.length + " works \\u00b7 " + selCount + " selected \\u00b7 " + shown.length + " shown";
  shown.forEach(c => {
    const card = document.createElement("div");
    card.className = "card" + (selected[c.iiif_token] ? " selected" : "");
    card.innerHTML = cardHtml(c, false);
    grid.appendChild(card);
  });
  bind();
}

function renderZoom() {
  grid.className = "zoom";
  grid.innerHTML = "";
  const rows = DATA.candidates.filter(c => wideCut.includes(c.iiif_token));
  const narrow = rows.filter(c => selected[c.iiif_token]).length;
  document.getElementById("count").textContent =
    "zoom \\u00b7 " + wideCut.length + " in wide cut \\u00b7 " + narrow + " study set (max " + MAX_STUDY + ")";
  rows.forEach(c => {
    const card = document.createElement("div");
    card.className = "card" + (selected[c.iiif_token] ? " selected" : "");
    card.innerHTML = cardHtml(c, true);
    grid.appendChild(card);
  });
  commitBtn.disabled = !(narrow >= 1 && narrow <= MAX_STUDY);
  bind();
}

function render() { stage === 2 ? renderZoom() : renderBoard(); }

function bind() {
  document.querySelectorAll(".star").forEach(el => {
    el.onclick = () => { stars[el.dataset.tok] = parseInt(el.dataset.star, 10); render(); };
  });
  document.querySelectorAll("[data-select]").forEach(el => {
    el.onchange = () => { selected[el.dataset.select] = el.checked; render(); };
  });
}

starFilter.onchange = render;
onlyPd.onchange = render;
sortBy.onchange = render;

nextBtn.onclick = () => {
  wideCut = DATA.candidates.filter(c => selected[c.iiif_token]).map(c => c.iiif_token);
  if (!wideCut.length) { document.getElementById("status").textContent = " select at least one work first"; return; }
  stage = 2;
  nextBtn.style.display = "none"; exportBtn.style.display = "none";
  backBtn.style.display = ""; commitBtn.style.display = "";
  render();
};

backBtn.onclick = () => {
  stage = 1; wideCut = [];
  backBtn.style.display = "none"; commitBtn.style.display = "none";
  nextBtn.style.display = ""; exportBtn.style.display = "";
  render();
};

function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

function exportStars() {
  const rows = DATA.candidates.map(c => ({work_id: c.work_id, stars: stars[c.iiif_token] || 0}));
  download("stars.json", {artist: DATA.artist, stars: rows});
}

function exportSelection(selectedTokens) {
  const set = new Set(selectedTokens);
  const ratings = DATA.candidates.map(c => ({
    work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
    title: c.title, date: c.date, medium: c.medium,
    source_url: c.source_url, museum: c.museum, rights: c.rights,
    qid: c.qid, inst_ids: c.inst_ids,
    selected: set.has(c.iiif_token), stars: stars[c.iiif_token] || 0,
  }));
  download("selection.json", {artist: DATA.artist, ratings});
}

exportBtn.onclick = () => {
  const live = DATA.candidates.filter(c => selected[c.iiif_token]).map(c => c.iiif_token);
  exportStars();
  exportSelection(live);
  document.getElementById("status").textContent = " saved stars.json + selection.json";
};

commitBtn.onclick = () => {
  // wide cut = frozen snapshot (session record); narrow = still-selected within it (<= MAX_STUDY).
  const narrowTokens = wideCut.filter(t => selected[t]);
  if (!(narrowTokens.length >= 1 && narrowTokens.length <= MAX_STUDY)) return;
  const tokenToWid = {};
  DATA.candidates.forEach(c => { tokenToWid[c.iiif_token] = c.work_id; });
  exportStars();
  exportSelection(wideCut);
  download("study-set.json", {artist: DATA.artist, study_set: narrowTokens.map(t => tokenToWid[t])});
  document.getElementById("status").textContent =
    " saved stars.json + selection.json + study-set.json (" + narrowTokens.length + " to study)";
};

render();
</script>
</body>
</html>
"""
```

- [ ] **Step 4: Run the tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: PASS — both new funnel tests and every pre-existing gallery test (Spec-A markers + payload tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: two-stage funnel template — Next/zoom/Commit, wide snapshot, study-set.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: SKILL.md — funnel flow, study_set-bounded downstream, skip-discovery

**Files:**
- Modify: `skill/SKILL.md`
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: `has_candidates` (T2), `load_study_set` (T3), `resolve_selection(only=)` (T4), the funnel template (T6).
- Produces: SKILL.md prose wiring the funnel + skip-discovery; `test_skill_md.py` continues to pass (existing tokens retained; new tokens asserted).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_skill_md.py`:

```python
def test_skill_md_documents_funnel_and_skip_discovery():
    text = SKILL_MD.read_text(encoding="utf-8")
    for token in ("study-set.json", "load_study_set", "has_candidates", "skip-discovery"):
        assert token in text, f"SKILL.md does not wire {token}"
    # downstream is bounded to the study set
    assert "only=" in text
    # the interview/resolve runs on the study_set, not the full wide selection
    assert "study_set" in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_skill_md.py -k funnel_and_skip -v`
Expected: FAIL — tokens absent.

- [ ] **Step 3: Document the funnel in the curation prose**

In `skill/SKILL.md`, in the Human Pause 1 / curation section (the `gallery.html` paragraph that currently describes rating + the two-file export), append a description of the funnel. Add this sentence after the existing export description:

```markdown
> **Narrowing funnel.** The board is stage 1 (wide scan). **Next → zoom** freezes the
> current selection as the **wide cut** and re-renders only those works at ~2-wide with
> full-size images for close looking; narrow there to **≤4** and **Commit** — which writes
> `stars.json`, `selection.json` (the frozen wide cut), and **`study-set.json`** (the ≤4
> narrow cut). The wide cut is the session record; the **study_set is what gets studied**.
```

- [ ] **Step 4: Wire study_set-bounded downstream**

In `skill/SKILL.md`, in the same curation/return wiring, replace the resolve/ingest description so downstream is bounded to the study set. Use this exact prose:

```markdown
> On return, persist stars (`state.ingest_stars(...)`), then read both cuts:
> `sel = load_selection(sp.selection_json, '<ARTIST>')`; `selected_ids, _ = ingest_selection(sel)`
> (the wide cut) and `study_set = load_study_set(sp.study_set_json, '<ARTIST>')` (≤4 narrow).
> Resolve high-res for the study set only —
> `resolve.resolve_selection(sel, sp.selected_dir, only=set(study_set))` — and record the
> session with both cuts:
> `state.record_session(theme, grouping, selected=selected_ids, study_set=study_set, outputs={...})`.
> Everything downstream (visual analysis, interview) runs on the **study_set**.
```

- [ ] **Step 5: Wire the interview to the study_set**

In `skill/SKILL.md`, in the curation_interview stage wiring (the `build_queue(selected_rows(sel), work_meta)` line from Spec A), change it to bound the queue to the study set. Replace that line with:

```markdown
   - `study_set = load_study_set(sp.study_set_json, '<ARTIST>')`;
     `rows = [r for r in selected_rows(sel) if r.work_id in study_set]`;
     `queue = build_queue(rows, work_meta)`. The interview is bounded to the ≤4 study set.
```

- [ ] **Step 6: Document the skip-discovery study mode**

In `skill/SKILL.md`, in the image_discovery stage prose (where discovery is described), add a paragraph:

```markdown
   **Skip-discovery (study mode).** A study session can skip collecting (`skip-discovery`):
   if the human asks to "study" / "skip-discovery" and `state.has_candidates()` is true,
   **skip `image_discovery`** and go straight to building the funnel board over `state.candidates`
   (a prior collect or a Thrust-2 import). If `has_candidates()` is false, there is nothing
   to study — run discovery first. This decouples study from collect: one collected board
   feeds many study sessions.
```

- [ ] **Step 7: Run the test + full suite to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_skill_md.py -v`
Expected: PASS — including the pre-existing skill_md tests (`ingest_selection`, `ingest_stars`, `build_queue(selected_rows(sel)`, etc. all still present).

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest -q`
Expected: PASS — full suite green.

- [ ] **Step 8: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
docs: wire narrowing funnel, study_set-bounded downstream, skip-discovery in SKILL.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

## Final verification

After all tasks:

```bash
UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest -q
```

Expected: full suite passes. Spot-check the funnel invariants end-to-end:
- `study-set.json` carries ≤ `MAX_STUDY` work_ids; `study_set ⊆ selection.json` selected.
- `resolve_selection(only=set(study_set))` resolves only study-set works; `only=None` (non-funnel callers) still resolves all selected.
- A work in the wide cut but dropped at the zoom stage stays in `selection.json`/`selected` but is absent from `study-set.json`/`study_set`.
- Stars still play no role in selection or the study set (Spec-A orthogonality intact).
