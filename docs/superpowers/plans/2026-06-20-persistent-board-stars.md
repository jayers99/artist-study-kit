# Persistent Board Stars Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the curation board persistent — star ratings live on the candidate and survive every session/run, thumbnails cache locally, the board filters/sorts, and selection-for-advancement is fully decoupled from stars.

**Architecture:** Two new persistent fields on `BoardCandidate` (`stars`, `thumbnail_path`); a collect-time thumbnail cache in `image_download.py`; a star-seeding/filter/sort/select-toggle gallery; and a `selected`-driven selection path that replaces every `liked()` (rating-threshold) call in `selection.py` and `resolve.py`. Spec: `docs/superpowers/specs/2026-06-20-persistent-board-stars-design.md`.

**Tech Stack:** Python 3.12, dataclasses, pytest, uv. No new dependencies.

## Global Constraints

- **Test command:** `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest` from the repo root. Imports resolve as `from scripts.x import y` (pythonpath = `skill`).
- **Stars ⊥ selection — the invariant:** nothing in the selection or resolve path may read a star value. Selection comes only from the explicit `selected` flag. Rating never selects; selecting never rates.
- **Stars persist:** per-candidate, 0 = unrated, range 0–5. New candidates arrive unstarred. Out-of-range or unknown-work_id star updates are silently ignored.
- **Selection is per-session:** never seeded into the board; the gallery always starts with `selected=false`. Stars ARE seeded (pre-filled from persistent state).
- **Two export files:** `stars.json` (every candidate's stars) + `selection.json` (this session's `selected` rows). Never one combined file.
- **Local images:** the board prefers `thumbnail_path` (local) and falls back to `thumbnail_url` (remote) on cache miss. Thumbnail caching never raises; failure → no local path, remote fallback.
- **No version bump / no migration step:** old `state.json` and `selection.json` files must load unchanged (new fields default).
- **Commits:** `git commit --no-gpg-sign`; stage only the named files (never `git add -A`); end the message body with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- **Quote shell paths**; the repo lives in iCloud.

---

## File Structure

- `skill/scripts/state.py` — add `BoardCandidate.stars` / `.thumbnail_path`; add `PackageState.ingest_stars`. (Tasks 1, 2)
- `skill/scripts/dates.py` — **new**: `parse_year` date→sort-year helper. (Task 3)
- `skill/scripts/image_download.py` — add `cache_thumbnail` + `cache_thumbnails`. (Task 4)
- `skill/scripts/selection.py` — `Rating.selected`/`.stars`, `selected_rows`, decoupled `ingest_selection`/`apply_selection`. (Task 5)
- `skill/scripts/resolve.py` — `resolve_selection` resolves selected (not liked) rows. (Task 5)
- `skill/scripts/gallery.py` — `build_thumbnail_gallery` payload (stars/bytes/year/selected/local src) + `_THUMB_TEMPLATE` (seed/filter/sort/select/two-file export). (Tasks 6, 7)
- `skill/SKILL.md` — document caching, two-file export, `ingest_stars`, decoupled selection. (Task 8)
- Tests: `tests/test_state.py`, `tests/test_dates.py` (new), `tests/test_image_download.py`, `tests/test_selection.py`, `tests/test_resolve.py`, `tests/test_gallery.py`, `tests/test_skill_md.py`.

---

### Task 1: Persistent fields on BoardCandidate

**Files:**
- Modify: `skill/scripts/state.py` (the `BoardCandidate` dataclass — fields, `to_dict`, `from_dict`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `BoardCandidate.stars: int = 0`, `BoardCandidate.thumbnail_path: str = ""`, both round-tripped by `to_dict`/`from_dict`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_state.py`:

```python
def test_board_candidate_stars_and_thumbnail_path_round_trip():
    bc = BoardCandidate(
        work_id="senecio", title="Senecio", date="1922", museum="aic",
        thumbnail_url="https://x/t.jpg", source_url="https://x/1", rights="in_copyright",
        stars=4, thumbnail_path="images/candidates/senecio/thumb.jpg",
    )
    d = bc.to_dict()
    assert d["stars"] == 4
    assert d["thumbnail_path"] == "images/candidates/senecio/thumb.jpg"
    back = BoardCandidate.from_dict(d)
    assert back.stars == 4
    assert back.thumbnail_path == "images/candidates/senecio/thumb.jpg"


def test_board_candidate_defaults_unstarred_and_no_thumbnail():
    bc = BoardCandidate(work_id="w", title="", date="", museum="", thumbnail_url="",
                        source_url="", rights="")
    assert bc.stars == 0
    assert bc.thumbnail_path == ""


def test_old_state_dict_loads_with_new_field_defaults():
    # a candidate dict written before this feature (no stars / thumbnail_path keys)
    legacy = {"work_id": "w", "title": "T", "date": "1900", "museum": "met",
              "thumbnail_url": "u", "source_url": "s", "rights": "public_domain"}
    bc = BoardCandidate.from_dict(legacy)
    assert bc.stars == 0
    assert bc.thumbnail_path == ""
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -k "stars or thumbnail_path or new_field" -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'stars'`.

- [ ] **Step 3: Add the fields**

In `skill/scripts/state.py`, in the `BoardCandidate` dataclass, after `local_path: str = ""`:

```python
    stars: int = 0
    thumbnail_path: str = ""
```

- [ ] **Step 4: Round-trip the fields**

In `BoardCandidate.to_dict`, add to the returned dict (after `"local_path": self.local_path,`):

```python
            "stars": self.stars,
            "thumbnail_path": self.thumbnail_path,
```

In `BoardCandidate.from_dict`, add to the `cls(...)` call (after `local_path=d.get("local_path", ""),`):

```python
            stars=int(d.get("stars", 0)),
            thumbnail_path=d.get("thumbnail_path", ""),
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -v`
Expected: PASS (all, including the pre-existing state tests).

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: persistent stars + thumbnail_path on BoardCandidate

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 2: PackageState.ingest_stars

**Files:**
- Modify: `skill/scripts/state.py` (add a method to `PackageState`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `BoardCandidate.stars` (Task 1).
- Produces: `PackageState.ingest_stars(self, stars_map: dict[str, int]) -> int` — applies `{work_id: stars}` onto candidates, returns count updated; ignores unknown work_ids and values outside 0–5.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_state.py`:

```python
def test_ingest_stars_applies_known_ignores_unknown_and_out_of_range():
    st = PackageState(artist="x")
    st.candidates = [
        BoardCandidate(work_id="a", title="", date="", museum="", thumbnail_url="",
                       source_url="", rights=""),
        BoardCandidate(work_id="b", title="", date="", museum="", thumbnail_url="",
                       source_url="", rights=""),
    ]
    updated = st.ingest_stars({"a": 5, "b": 9, "ghost": 3})
    assert updated == 1                      # only "a" applied
    assert st.candidate("a").stars == 5
    assert st.candidate("b").stars == 0      # 9 out of range → ignored
    assert st.candidate("ghost") is None


def test_ingest_stars_clears_to_zero_and_persists():
    st = PackageState(artist="x")
    st.candidates = [BoardCandidate(work_id="a", title="", date="", museum="",
                                    thumbnail_url="", source_url="", rights="", stars=4)]
    assert st.ingest_stars({"a": 0}) == 1
    assert st.candidate("a").stars == 0
    # survives a state.json round-trip
    assert PackageState.from_dict(st.to_dict()).candidate("a").stars == 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -k ingest_stars -v`
Expected: FAIL — `AttributeError: 'PackageState' object has no attribute 'ingest_stars'`.

- [ ] **Step 3: Implement the method**

In `skill/scripts/state.py`, add to `PackageState` (after `merge_user_candidate`):

```python
    def ingest_stars(self, stars_map: dict[str, int]) -> int:
        """Apply {work_id: stars} onto candidates. Returns count updated.
        Ignores unknown work_ids and values outside 0..5 (selection is untouched)."""
        by_id = {c.work_id: c for c in self.candidates}
        updated = 0
        for work_id, raw in stars_map.items():
            cand = by_id.get(work_id)
            if cand is None:
                continue
            try:
                n = int(raw)
            except (TypeError, ValueError):
                continue
            if not (0 <= n <= 5):
                continue
            cand.stars = n
            updated += 1
        return updated
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_state.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: PackageState.ingest_stars (persist board stars from gallery)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 3: parse_year date helper

**Files:**
- Create: `skill/scripts/dates.py`
- Test: `tests/test_dates.py`

**Interfaces:**
- Consumes: nothing.
- Produces: `parse_year(date: str) -> int | None` — first 4-digit run as the sort year; `None` when absent/unparseable.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_dates.py`:

```python
from scripts.dates import parse_year


def test_parse_year_plain():
    assert parse_year("1889") == 1889


def test_parse_year_circa():
    assert parse_year("c. 1889") == 1889
    assert parse_year("circa 1880s") == 1880


def test_parse_year_range_takes_start():
    assert parse_year("1889–90") == 1889
    assert parse_year("1889-1890") == 1889


def test_parse_year_month_prefix():
    assert parse_year("May 1889") == 1889


def test_parse_year_unknown_is_none():
    assert parse_year("") is None
    assert parse_year("n.d.") is None
    assert parse_year("oil on canvas") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_dates.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.dates'`.

- [ ] **Step 3: Implement the module**

Create `skill/scripts/dates.py`:

```python
"""Date-string helpers for sorting the curation board."""

from __future__ import annotations

import re

_YEAR = re.compile(r"\d{4}")


def parse_year(date: str) -> int | None:
    """First 4-digit run in the string as the sort year; None if none present.

    Handles "1889", "c. 1889", ranges ("1889-1890" -> 1889), and month prefixes
    ("May 1889" -> 1889). "" / "n.d." / non-numeric -> None (sorts last)."""
    if not date:
        return None
    match = _YEAR.search(date)
    return int(match.group()) if match else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_dates.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/dates.py tests/test_dates.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: parse_year date helper for board year-sort

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 4: Thumbnail caching on collect

**Files:**
- Modify: `skill/scripts/image_download.py` (add two functions)
- Test: `tests/test_image_download.py`

**Interfaces:**
- Consumes: `default_fetch` (existing, `fetch(url) -> (status, content_type, bytes)`); `BoardCandidate.thumbnail_path` (Task 1).
- Produces:
  - `cache_thumbnail(work_id: str, thumbnail_url: str, candidates_dir, *, fetch=default_fetch) -> tuple[str, int]` — writes `<candidates_dir>/<work_id>/thumb.jpg`, idempotent; returns `(rel_path, byte_size)` or `("", 0)` on failure/empty URL.
  - `cache_thumbnails(candidates, candidates_dir, *, fetch=default_fetch, sleep=time.sleep, min_interval=1.0) -> int` — caches every candidate lacking a `thumbnail_path` (mutates it in place), maps `origin=="user"` candidates to their existing `local_path` without fetching, throttles between real fetches; returns count newly cached.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_image_download.py`:

```python
def test_cache_thumbnail_writes_and_returns_size(tmp_path):
    from scripts.image_download import cache_thumbnail
    body = b"\xff\xd8\xff\xe0thumbnailbytes"
    rel, size = cache_thumbnail("senecio", "https://x/t.jpg", tmp_path,
                                fetch=lambda u: (200, "image/jpeg", body))
    assert rel == "images/candidates/senecio/thumb.jpg"
    assert size == len(body)
    assert (tmp_path / "senecio" / "thumb.jpg").read_bytes() == body


def test_cache_thumbnail_is_idempotent(tmp_path):
    from scripts.image_download import cache_thumbnail
    body = b"\xff\xd8\xff\xe0bytes"
    cache_thumbnail("w", "https://x/t.jpg", tmp_path, fetch=lambda u: (200, "image/jpeg", body))

    def _boom(url):
        raise AssertionError("must not re-fetch when cached")

    rel, size = cache_thumbnail("w", "https://x/t.jpg", tmp_path, fetch=_boom)
    assert rel == "images/candidates/w/thumb.jpg"
    assert size == len(body)


def test_cache_thumbnail_failure_returns_empty(tmp_path):
    from scripts.image_download import cache_thumbnail
    assert cache_thumbnail("w", "https://x/t.jpg", tmp_path,
                           fetch=lambda u: (404, "text/html", b"")) == ("", 0)
    assert cache_thumbnail("w", "", tmp_path,
                           fetch=lambda u: (200, "image/jpeg", b"x")) == ("", 0)


def test_cache_thumbnails_batch_sets_paths_and_skips_user_local(tmp_path):
    from scripts.image_download import cache_thumbnails
    from scripts.state import BoardCandidate
    disc = BoardCandidate(work_id="senecio", title="", date="", museum="",
                          thumbnail_url="https://x/t.jpg", source_url="", rights="")
    user = BoardCandidate(work_id="mine", title="", date="", museum="",
                          thumbnail_url="", source_url="", rights="", origin="user",
                          local_path="images/user/mine.jpg")
    already = BoardCandidate(work_id="done", title="", date="", museum="",
                             thumbnail_url="https://x/d.jpg", source_url="", rights="",
                             thumbnail_path="images/candidates/done/thumb.jpg")
    cached = cache_thumbnails([disc, user, already], tmp_path,
                              fetch=lambda u: (200, "image/jpeg", b"jpegbytes"),
                              sleep=lambda s: None)
    assert cached == 1                                            # only disc fetched
    assert disc.thumbnail_path == "images/candidates/senecio/thumb.jpg"
    assert user.thumbnail_path == "images/user/mine.jpg"          # mapped, not fetched
    assert already.thumbnail_path == "images/candidates/done/thumb.jpg"  # untouched
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_image_download.py -k cache_thumbnail -v`
Expected: FAIL — `ImportError: cannot import name 'cache_thumbnail'`.

- [ ] **Step 3: Implement the functions**

In `skill/scripts/image_download.py`, add after `download_candidates` (the module already imports `json`, `time`, `Path`):

```python
def cache_thumbnail(
    work_id: str,
    thumbnail_url: str,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
) -> tuple[str, int]:
    """Download a board thumbnail to <candidates_dir>/<work_id>/thumb.jpg.

    Idempotent (skip if present). Returns (rel_path, byte_size); ("", 0) on
    empty URL or any fetch failure. Never raises."""
    work_dir = Path(candidates_dir) / work_id
    dest = work_dir / "thumb.jpg"
    rel = f"images/candidates/{work_id}/thumb.jpg"
    if dest.is_file():
        return rel, dest.stat().st_size
    if not thumbnail_url:
        return "", 0
    try:
        status_code, content_type, content = fetch(thumbnail_url)
    except Exception:
        return "", 0
    if status_code != 200 or not content_type.startswith("image/") or not content:
        return "", 0
    work_dir.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel, len(content)


def cache_thumbnails(
    candidates,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> int:
    """Cache thumbnails for candidates missing a thumbnail_path; set it in place.

    origin=="user" candidates already have a local file (local_path) — map it,
    don't fetch. Throttles between real fetches. Returns count newly cached."""
    cached = 0
    fetched = False
    for cand in candidates:
        if getattr(cand, "thumbnail_path", ""):
            continue
        if getattr(cand, "origin", "") == "user" and getattr(cand, "local_path", ""):
            cand.thumbnail_path = cand.local_path
            continue
        if fetched:
            sleep(min_interval)
        rel, _size = cache_thumbnail(
            cand.work_id, getattr(cand, "thumbnail_url", ""), candidates_dir, fetch=fetch
        )
        if rel:
            cand.thumbnail_path = rel
            cached += 1
            fetched = True
    return cached
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_image_download.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/image_download.py tests/test_image_download.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: cache board thumbnails locally on collect

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 5: Decouple selection from stars (selection.py + resolve.py)

**Files:**
- Modify: `skill/scripts/selection.py` (`Rating`, `parse_selection`, new `selected_rows`, `ingest_selection`, `apply_selection`)
- Modify: `skill/scripts/resolve.py` (import + `resolve_selection` loop + docstring)
- Test: `tests/test_selection.py`, `tests/test_resolve.py` (update existing rating-threshold tests)

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `Rating.selected: bool = False`, `Rating.stars: int = 0` (read by `parse_selection`).
  - `selected_rows(sel: Selection) -> list[Rating]` — `[r for r in sel.ratings if r.selected]`.
  - `ingest_selection(sel: Selection) -> tuple[list[str], list[str]]` — `selected_ids` from `selected_rows`; `study_set` defaults equal. **No `liked_only` param.**
  - `apply_selection(sel, candidates_dir, selected_dir) -> list[Path]` — copies `selected_rows`. **No `threshold` param.**
  - `resolve.resolve_selection` resolves `selected_rows`, not `liked`.

  `liked()` and `LIKED_THRESHOLD` remain defined (used by `state.migrate_legacy`) but are no longer called by `ingest_selection`/`apply_selection`/`resolve_selection`.

- [ ] **Step 1: Update the existing rating-threshold tests to the new `selected` semantics**

In `tests/test_selection.py`, **replace** the two ingest tests:

```python
def test_ingest_selection_returns_selected_ids_and_defaults_study_set():
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", selected=True),
        Rating(work_id="b", iiif_token="", image_rel="u", selected=False),
        Rating(work_id="c", iiif_token="", image_rel="u", selected=True),
    ])
    selected, study_set = ingest_selection(sel)
    assert selected == ["a", "c"]
    assert study_set == ["a", "c"]


def test_ingest_selection_ignores_stars_entirely():
    # orthogonality: a 5-star work that is NOT selected stays out; a 1-star
    # SELECTED work goes in. Stars never drive selection.
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="hi", iiif_token="", image_rel="u", stars=5, selected=False),
        Rating(work_id="lo", iiif_token="", image_rel="u", stars=1, selected=True),
    ])
    selected, _ = ingest_selection(sel)
    assert selected == ["lo"]
```

In `tests/test_selection.py`, **replace** the `apply_selection` test body so the rated row is explicitly selected. Change `test_apply_selection_copies_liked_images` to:

```python
def test_apply_selection_copies_selected_images(tmp_path):
    cdir = tmp_path / "candidates"
    (cdir / "wheat-field").mkdir(parents=True)
    (cdir / "wheat-field" / "12345.jpg").write_bytes(b"img")
    sdir = tmp_path / "selected"
    sel = parse_selection({
        "artist": "x",
        "ratings": [{"work_id": "wheat-field", "iiif_token": "12345",
                     "image_rel": "images/candidates/wheat-field/12345.jpg",
                     "selected": True}],
    })
    out = apply_selection(sel, cdir, sdir)
    assert len(out) == 1 and out[0].is_file()
    assert apply_selection(sel, cdir, sdir) == out   # idempotent
```

Add an orthogonality test for `parse_selection`:

```python
def test_parse_selection_reads_selected_and_stars():
    r = parse_selection({"artist": "x", "ratings": [
        {"work_id": "w", "iiif_token": "t", "image_rel": "r", "selected": True, "stars": 3},
    ]}).ratings[0]
    assert r.selected is True
    assert r.stars == 3
```

- [ ] **Step 2: Update the resolve test to `selected` semantics**

In `tests/test_resolve.py`, change `_entry` default and the selection test. Replace `_entry`:

```python
def _entry(**kw):
    base = dict(work_id="fish-magic", iiif_token="t", image_rel="r", selected=True,
                source_url="https://www.wikidata.org/wiki/Q1", inst_ids=())
    base.update(kw)
    return Rating(**base)
```

Replace `test_resolve_selection_resolves_liked_and_writes_manifest` with (same resolver/download wiring as the original; only `rating=`→`selected=` and the "liked"→"selected" comments change):

```python
def test_resolve_selection_resolves_selected_and_writes_manifest(tmp_path):
    sel = Selection(artist="paul-klee", ratings=[
        _entry(work_id="fish-magic", selected=True, inst_ids=(("commons_file", "Fish.jpg"),)),
        _entry(work_id="meh", selected=False),  # not selected → skipped
    ])

    def fake_download(cand, sel_dir):
        return SimpleNamespace(status="downloaded", image_path=sel_dir / f"{cand.work_id}.jpg")

    out = resolve_selection(sel, tmp_path,
                            resolvers=[lambda e: _cand(e.work_id)], download=fake_download)
    assert [r.work_id for r in out] == ["fish-magic"]   # only selected
    manifest = json.loads((tmp_path / "resolved.json").read_text(encoding="utf-8"))
    assert manifest[0]["work_id"] == "fish-magic"
    assert manifest[0]["image"] == "fish-magic.jpg"
    assert manifest[0]["rights"] == "public_domain"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_selection.py tests/test_resolve.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'selected'` (and the removed `liked_only`).

- [ ] **Step 4: Add the `selected`/`stars` fields and `selected_rows`**

In `skill/scripts/selection.py`, in the `Rating` dataclass, after `inst_ids: tuple[tuple[str, str], ...] = ()`:

```python
    selected: bool = False
    stars: int = 0
```

In `parse_selection`, inside the `Rating(...)` construction, after the `inst_ids=...` line:

```python
            selected=bool(r.get("selected", False)),
            stars=int(r.get("stars", 0)),
```

Add a new function after `liked`:

```python
def selected_rows(sel: "Selection") -> list[Rating]:
    """The explicitly selected works (the per-session pick).

    Orthogonal to stars: this reads only the `selected` flag, never a rating."""
    return [r for r in sel.ratings if r.selected]
```

- [ ] **Step 5: Rewrite `ingest_selection` and `apply_selection` to use `selected_rows`**

Replace `ingest_selection`:

```python
def ingest_selection(sel: "Selection") -> tuple[list[str], list[str]]:
    """Resolve an exported selection into (selected_ids, study_set_ids) for a session.

    selected_ids are the works the human explicitly selected on the board; study_set
    defaults equal to it — the Thrust-3 funnel (Spec B) narrows study_set to <=4 later.
    Stars play no part here (stars persist on the candidate, orthogonally)."""
    rows = selected_rows(sel)
    selected_ids = [r.work_id for r in rows]
    return selected_ids, list(selected_ids)
```

Replace `apply_selection` (drop the `threshold` parameter; iterate `selected_rows`):

```python
def apply_selection(
    sel: Selection,
    candidates_dir: Path | str,
    selected_dir: Path | str,
) -> list[Path]:
    """Copy explicitly-selected images from candidates_dir into selected_dir; idempotent."""
    candidates_dir = Path(candidates_dir)
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for r in selected_rows(sel):
        src = candidates_dir / r.work_id / Path(r.image_rel).name
        if not src.is_file():
            continue
        dst = selected_dir / f"{r.work_id}-{Path(r.image_rel).name}"
        if not dst.is_file():
            shutil.copy2(src, dst)
        out.append(dst)
    return out
```

Also update the module docstring line 5: change `Works rated >= LIKED_THRESHOLD are copied into images/selected/.` to `Explicitly selected works are copied into images/selected/ (rating is orthogonal).`

- [ ] **Step 6: Point `resolve_selection` at selected rows**

In `skill/scripts/resolve.py`:
- Change the import `from scripts.selection import liked` to `from scripts.selection import selected_rows`.
- In `resolve_selection`, change `for rating in liked(sel):` to `for rating in selected_rows(sel):`.
- Change the docstring `"""Resolve every liked work; ...` to `"""Resolve every explicitly-selected work; write selected_dir/resolved.json; return the results."""`.

- [ ] **Step 7: Run the tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_selection.py tests/test_resolve.py -v`
Expected: PASS.

- [ ] **Step 8: Run the full suite (these modules are widely imported)**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest -q`
Expected: PASS. If `test_skill_md.py` fails on a removed token, that is fixed in Task 8 — note it and proceed; do not modify SKILL.md here.

- [ ] **Step 9: Commit**

```bash
git add skill/scripts/selection.py skill/scripts/resolve.py tests/test_selection.py tests/test_resolve.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: drive selection + resolve from explicit `selected`, not star threshold

Stars and selection are now orthogonal: nothing in the selection/resolve path
reads a rating. liked()/LIKED_THRESHOLD remain only for legacy migration.

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 6: Gallery payload — stars, bytes, year, selected, local src

**Files:**
- Modify: `skill/scripts/gallery.py` (`build_thumbnail_gallery` payload + imports)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: `BoardCandidate.stars` / `.thumbnail_path` (Task 1), `dates.parse_year` (Task 3).
- Produces: `build_thumbnail_gallery` payload rows gain `stars`, `bytes`, `year`, `selected`, and `image_rel` prefers `thumbnail_path` over `thumbnail_url`. Reads candidate attrs via `getattr` so it still accepts `ThumbnailCandidate` (no stars/thumbnail_path) and `BoardCandidate` alike.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_gallery.py`:

```python
def test_thumbnail_gallery_payload_carries_stars_year_selected_and_local_src(tmp_path):
    import json as _json
    pkg = tmp_path
    thumb = pkg / "images" / "candidates" / "senecio" / "thumb.jpg"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"012345678")  # 9 bytes
    cand = BoardCandidate(
        work_id="senecio", title="Senecio", date="c. 1922", museum="aic",
        thumbnail_url="https://x/remote.jpg", source_url="https://x/1", rights="in_copyright",
        stars=4, thumbnail_path="images/candidates/senecio/thumb.jpg",
    )
    html = build_thumbnail_gallery([cand], "Paul Klee", package_root=pkg)
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    row = data["candidates"][0]
    assert row["stars"] == 4
    assert row["year"] == 1922
    assert row["selected"] is False                       # never seeded
    assert row["image_rel"] == "images/candidates/senecio/thumb.jpg"   # local preferred
    assert row["bytes"] == 9


def test_thumbnail_gallery_falls_back_to_remote_url_without_cache():
    import json as _json
    cand = BoardCandidate(
        work_id="w", title="T", date="", museum="met",
        thumbnail_url="https://x/remote.jpg", source_url="https://x/1", rights="public_domain",
    )
    html = build_thumbnail_gallery([cand], "X")
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    row = data["candidates"][0]
    assert row["image_rel"] == "https://x/remote.jpg"     # remote fallback
    assert row["year"] is None
    assert row["bytes"] == 0
```

(`BoardCandidate` is already imported in `tests/test_gallery.py`.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -k "payload or fallback" -v`
Expected: FAIL — `TypeError: build_thumbnail_gallery() got an unexpected keyword argument 'package_root'` / missing keys.

- [ ] **Step 3: Implement the payload changes**

In `skill/scripts/gallery.py`, add the import near the top (after `from pathlib import Path`):

```python
from scripts.dates import parse_year
```

Replace `build_thumbnail_gallery` with (signature gains optional `package_root` for byte sizing; the per-row dict gains the new keys):

```python
def build_thumbnail_gallery(cands, artist: str, *, package_root: Path | str | None = None) -> str:
    """Render a browse *board* of museum thumbnails (local-cached preferred) with rating,
    selection, filter, and sort. Stars are seeded from each candidate (persistent axis);
    `selected` always starts false (per-session). Export writes stars.json + selection.json.

    package_root, when given, is used to stat local thumbnails for the file-size sort.
    """
    root = Path(package_root) if package_root else None
    payload = []
    for i, c in enumerate(cands):
        thumb_path = getattr(c, "thumbnail_path", "")
        image_rel = thumb_path or c.thumbnail_url
        size = 0
        if thumb_path and root is not None:
            fp = root / thumb_path
            if fp.is_file():
                size = fp.stat().st_size
        payload.append({
            "work_id": c.work_id,
            "iiif_token": f"{c.museum}-{i}",
            "image_rel": image_rel,
            "source_url": c.source_url,
            "title": c.title,
            "museum": c.museum,
            "date": c.date,
            "medium": c.medium,
            "rights": c.rights,
            "qid": c.qid,
            "inst_ids": [list(pair) for pair in c.inst_ids],
            "origin": getattr(c, "origin", "discovered"),
            "stars": getattr(c, "stars", 0),
            "selected": False,
            "year": parse_year(getattr(c, "date", "") or ""),
            "bytes": size,
        })
    data_json = json.dumps({"artist": artist, "candidates": payload}, indent=2)
    return _THUMB_TEMPLATE.replace("__ARTIST__", _escape(artist)).replace("__DATA__", data_json)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: PASS (including the pre-existing `test_thumbnail_gallery_renders_remote_thumbnails_and_controls`, which still finds `data-star` and the remote URL via fallback).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: gallery payload carries stars/year/selected/bytes + local thumb src

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 7: Gallery template — seed stars, select toggle, filter, sort, two-file export

**Files:**
- Modify: `skill/scripts/gallery.py` (`_THUMB_TEMPLATE` only — CSS + HTML controls + JS)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: the Task-6 payload keys (`stars`, `selected`, `year`, `bytes`).
- Produces: a board template that seeds stars from the payload, has a per-card select toggle independent of stars, a star filter + sort selector, and an Export that downloads **two** files (`stars.json`, `selection.json`).

This task edits one large HTML/JS string. The tests assert on **marker substrings** (not full rendering), so keep these exact tokens present: `id="sort"`, `id="star-filter"`, `data-select`, `seedStars`, `stars.json`, `selection.json`.

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_gallery.py`:

```python
def test_thumbnail_template_has_seed_select_filter_sort_and_two_exports():
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    # stars seeded from payload (persistent axis), not hardcoded zero
    assert "seedStars" in html
    # selection is a separate control from stars
    assert "data-select" in html
    # filter + sort controls
    assert 'id="star-filter"' in html
    assert 'id="sort"' in html
    # two distinct export files
    assert "stars.json" in html
    assert "selection.json" in html


def test_thumbnail_template_export_keys_selected_and_stars():
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    # the selection.json builder emits an explicit `selected` field per row
    assert "selected:" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -k "template_has_seed or export_keys" -v`
Expected: FAIL — markers absent.

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
  .card { background: #1c1c1c; border: 2px solid transparent; border-radius: 4px; overflow: hidden; }
  .card.selected { border-color: #4a90ff; }
  .card img { width: 100%; height: 200px; object-fit: contain; background: #000; display: block; }
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
  <button id="export">Export stars.json + selection.json</button>
  <span id="status"></span>
</header>
<div id="grid"></div>
<script id="data" type="application/json">__DATA__</script>
<script>
const DATA = JSON.parse(document.getElementById("data").textContent);
// Two orthogonal axes, keyed by iiif_token:
//   stars[tok]    persistent rating (seeded from the candidate)
//   selected[tok] per-session pick (always starts empty)
const stars = {};
const selected = {};
function seedStars() {
  DATA.candidates.forEach(c => { stars[c.iiif_token] = c.stars || 0; });
}
seedStars();

const starFilter = document.getElementById("star-filter");
const onlyPd = document.getElementById("only-pd");
const sortBy = document.getElementById("sort");

function passStarFilter(c) {
  const v = starFilter.value;
  const s = stars[c.iiif_token] || 0;
  if (v === "all") return true;
  if (v === "unstarred") return s === 0;
  return s >= parseInt(v, 10);
}

function visible() {
  let rows = DATA.candidates.filter(c => {
    if (!passStarFilter(c)) return false;
    if (onlyPd.checked && c.rights !== "public_domain") return false;
    return true;
  });
  const mode = sortBy.value;
  rows = rows.slice().sort((a, b) => {
    if (mode === "stars") return (stars[b.iiif_token]||0) - (stars[a.iiif_token]||0);
    if (mode === "bytes") return (b.bytes||0) - (a.bytes||0);
    // year ascending, unknown (null) last
    const ay = a.year == null ? Infinity : a.year;
    const by = b.year == null ? Infinity : b.year;
    return ay - by;
  });
  return rows;
}

function render() {
  const grid = document.getElementById("grid");
  grid.innerHTML = "";
  const shown = visible();
  const selCount = Object.values(selected).filter(Boolean).length;
  document.getElementById("count").textContent =
    DATA.candidates.length + " works \\u00b7 " + selCount + " selected \\u00b7 " + shown.length + " shown";
  shown.forEach(c => {
    const tok = c.iiif_token;
    const s = stars[tok] || 0;
    const card = document.createElement("div");
    card.className = "card" + (selected[tok] ? " selected" : "");
    const pd = c.rights === "public_domain";
    let starHtml = "";
    for (let n = 1; n <= 5; n++)
      starHtml += '<span class="star' + (n <= s ? " on" : "") +
               '" data-star="' + n + '" data-tok="' + tok + '">\\u2605</span>';
    card.innerHTML =
      '<img loading="lazy" src="' + c.image_rel + '" alt="">' +
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
    grid.appendChild(card);
  });
  bind();
}

function bind() {
  document.querySelectorAll(".star").forEach(el => {
    el.onclick = () => {                     // edits the persistent star axis only
      stars[el.dataset.tok] = parseInt(el.dataset.star, 10);
      render();
    };
  });
  document.querySelectorAll("[data-select]").forEach(el => {
    el.onchange = () => {                     // edits the per-session selection axis only
      selected[el.dataset.select] = el.checked;
      render();
    };
  });
}

starFilter.onchange = render;
onlyPd.onchange = render;
sortBy.onchange = render;

function download(name, obj) {
  const blob = new Blob([JSON.stringify(obj, null, 2)], {type: "application/json"});
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = name;
  a.click();
}

document.getElementById("export").onclick = () => {
  const starRows = DATA.candidates.map(c => ({work_id: c.work_id, stars: stars[c.iiif_token] || 0}));
  download("stars.json", {artist: DATA.artist, stars: starRows});
  const ratings = DATA.candidates.map(c => ({
    work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
    title: c.title, date: c.date, medium: c.medium,
    source_url: c.source_url, museum: c.museum, rights: c.rights,
    qid: c.qid, inst_ids: c.inst_ids,
    selected: !!selected[c.iiif_token], stars: stars[c.iiif_token] || 0,
  }));
  download("selection.json", {artist: DATA.artist, ratings});
  document.getElementById("status").textContent = " saved stars.json + selection.json";
};

render();
</script>
</body>
</html>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_gallery.py -v`
Expected: PASS (the pre-existing `test_thumbnail_gallery_renders_remote_thumbnails_and_controls` still passes — `data-star` is present, the remote URL embeds via fallback).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
feat: board template seeds stars, adds select toggle, filter/sort, two-file export

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>
EOF
)"
```

---

### Task 8: SKILL.md — document caching, two-file export, ingest_stars, decoupled selection

**Files:**
- Modify: `skill/SKILL.md` (image_discovery + curation wiring)
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: `cache_thumbnails` (Task 4), `ingest_stars` (Task 2), the two-file export (Task 7), decoupled `ingest_selection` (Task 5).
- Produces: SKILL.md prose that wires the new operations; `test_skill_md.py` continues to pass (the `ingest_selection` token is retained; new tokens asserted).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_skill_md.py`:

```python
def test_skill_md_documents_persistent_stars():
    text = SKILL_MD.read_text(encoding="utf-8")
    for token in ("cache_thumbnails", "ingest_stars", "stars.json"):
        assert token in text, f"SKILL.md does not wire {token}"
    # selection is documented as decoupled from stars
    low = text.lower()
    assert "orthogonal" in low or "decoupl" in low
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_skill_md.py -k persistent_stars -v`
Expected: FAIL — tokens absent.

- [ ] **Step 3: Update SKILL.md — image_discovery (collect caches thumbnails)**

In `skill/SKILL.md`, find the image_discovery / board-building prose (near the `build_thumbnail_gallery` + `merge_candidates` wiring around line 60). Add a sentence after candidates are merged:

```markdown
   After merging a discovery run's candidates, cache their thumbnails locally so the board never re-pulls and works offline: `scripts.image_download.cache_thumbnails(state.candidates, sp.candidates_dir)` — it sets each candidate's `thumbnail_path` (mapping `origin:"user"` images to their existing `local_path`), then save state. Build the board with `build_thumbnail_gallery(state.candidates, '<ARTIST>', package_root=sp.root)` so the file-size sort can stat local thumbnails.
```

- [ ] **Step 4: Update SKILL.md — curation (two-file export + ingest_stars + decoupled selection)**

Find the curation wiring (the line describing `ingest_selection(load_selection(...))`, around line 68). Replace that sentence's export/ingest description with:

```markdown
> The user opens `gallery.html` (a board of locally-cached thumbnails; works studied in a prior session carry a **studied ✓ badge** but stay selectable), **rates** works with 1–5 stars (a persistent annotation that survives every session and run) and **selects** works for this session with a separate checkbox. **Stars and selection are orthogonal** — rating never selects and selecting never rates. Export downloads **two files**: `stars.json` (persistent, every candidate) and `selection.json` (this session's picks). On return, the skill persists stars with `state.ingest_stars({row['work_id']: row['stars'] for row in json.load(open(sp.root/'stars.json'))['stars']})`, then resolves the session with `selected, study_set = ingest_selection(load_selection(sp.selection_json, '<ARTIST>'))` (driven by the explicit `selected` flag, **not** a star threshold), asks the human for the session's grouping dimension (`subject` / `media` / `technique` / `other`) and a short theme label, then `state.record_session(theme, grouping, selected, study_set, outputs={...})` and saves state. See [[stage-curation]].
```

- [ ] **Step 5: Run the test + full suite to verify they pass**

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest tests/test_skill_md.py -v`
Expected: PASS (including `test_skill_md_documents_multi_run_state`, which still finds `ingest_selection`).

Run: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest -q`
Expected: PASS — full suite green.

- [ ] **Step 6: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit --no-gpg-sign -m "$(cat <<'EOF'
docs: wire thumbnail caching, persistent stars, two-file export in SKILL.md

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

Expected: the full suite passes (≈250+ tests). Spot-check the orthogonality invariant is honored end-to-end: a `selection.json` row with `stars: 5, selected: false` must NOT appear in `ingest_selection`'s output, and a row with `stars: 0, selected: true` MUST.
