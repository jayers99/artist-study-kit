# Custom Image Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a user inject a folder of their own painting images as first-class `origin:"user"` study candidates, identified by Claude vision, verified against the existing discovery pipeline, gated by a human review, and merged into the existing `state.json` board.

**Architecture:** A new pure module `scripts/user_import.py` owns identification-verification, the import-review artifact, and ingestion. `scripts/state.py` gains one field (`BoardCandidate.local_path`) and one helper (`PackageState.merge_user_candidate`). `scripts/paths.py` gains `images/user/` + review-file paths. `scripts/gallery.py` renders user cards from their local file with an origin badge. `SKILL.md` documents **import** as a re-enterable operation. Vision (Claude looking at images) lives in `SKILL.md`; every line of logic below it is pure and unit-tested with injected `lookup`/`copy_file` seams, exactly like the existing `query=`/`fetch=` pattern.

**Tech Stack:** Python 3 (stdlib only — `dataclasses`, `pathlib`, `shutil`, `json`), pytest. Run tests with `uv run pytest` (pythonpath includes `skill/`). No new dependencies.

## Global Constraints

- **No new dependencies.** Stdlib + existing modules only. No Pillow / no image-derivative step — user cards render the copied file CSS-scaled.
- **One new `BoardCandidate` field only:** `local_path: str = ""`. Everything else reuses existing fields. All existing packages must load unchanged (`local_path` defaults `""`).
- **`origin` values are exactly `"discovered" | "user"`.** This plan is the first writer of `"user"`.
- **`ImportRow.state` is exactly one of `"confirmed" | "proposed" | "off_artist" | "unidentified"`.**
- **Confidence is transient.** It lives only in the import-review artifact, never on `BoardCandidate`/`candidates[]`.
- **Discovered-path `merge_candidates` is untouched.** User merging goes through the new `merge_user_candidate`.
- **Dedup key is the existing `BoardCandidate.dedup_key()`:** QID → sorted `inst_ids` → `work_id`. Overlap with a discovered candidate **enriches** (sets `local_path`, leaves `origin`/provenance), never duplicates or replaces.
- **`rights` for user images:** inherited from the corroborating record on `confirmed`, else `"unknown"`.
- **Run source string is exactly `"user-import"`.**
- **Commits:** use `git commit --no-gpg-sign` (no signing key in agent). End commit messages with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Stage only the named files — never `git add -A`.
- **Tests are pure:** no network, no LLM, no real filesystem walks of user folders — inject `lookup`/`copy_file` and use `tmp_path`.

---

## File Structure

- `skill/scripts/paths.py` — **modify**: add `images/user/` dir + import-review file paths.
- `skill/scripts/state.py` — **modify**: add `BoardCandidate.local_path`; add `PackageState.merge_user_candidate`.
- `skill/scripts/user_import.py` — **create**: `ImportRow`, `slug_work_id`, `verify_identification`, `build_review`, `parse_review`, `make_pipeline_lookup`, `ingest_import_review`.
- `skill/scripts/gallery.py` — **modify**: include `origin`/`local_path` in the thumbnail-board payload + render an origin badge.
- `skill/SKILL.md` — **modify**: document the import operation.
- Tests: `tests/test_paths.py`, `tests/test_state.py`, `tests/test_user_import.py` (new), `tests/test_gallery.py`, `tests/test_skill_md.py`.

---

### Task 1: `images/user/` directory + import-review paths

**Files:**
- Modify: `skill/scripts/paths.py` (add properties after `session_dir`, line 108; add to `_SCAFFOLD_DIRS`, line 111-119)
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: existing `StudyPaths`, `scaffold`.
- Produces: `StudyPaths.user_images_dir -> Path` (`root/"images"/"user"`), `StudyPaths.import_review_json -> Path` (`root/"import-review.json"`), `StudyPaths.import_review_html -> Path` (`root/"import-review.html"`). `"images/user"` added to scaffold dirs.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_paths.py`:

```python
def test_user_images_dir_and_review_paths(tmp_path):
    from scripts.paths import study_paths
    sp = study_paths(tmp_path, "Paul Klee")
    assert sp.user_images_dir == sp.root / "images" / "user"
    assert sp.import_review_json == sp.root / "import-review.json"
    assert sp.import_review_html == sp.root / "import-review.html"


def test_scaffold_creates_user_images_dir(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "Paul Klee")
    assert sp.user_images_dir.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_paths.py -k "user_images or review_paths" -v`
Expected: FAIL with `AttributeError: 'StudyPaths' object has no attribute 'user_images_dir'`

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/paths.py`, add three properties right after the `session_dir` method (after line 108):

```python
    @property
    def user_images_dir(self) -> Path:
        return self.images_dir / "user"

    @property
    def import_review_json(self) -> Path:
        return self.root / "import-review.json"

    @property
    def import_review_html(self) -> Path:
        return self.root / "import-review.html"
```

Then add `"images/user"` to `_SCAFFOLD_DIRS` (after `"images/selected"`):

```python
_SCAFFOLD_DIRS = (
    "sources",
    "images",
    "images/candidates",
    "images/selected",
    "images/user",
    "drills",
    "prompts",
    "sessions",
)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (all, including existing)

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/paths.py tests/test_paths.py
git commit --no-gpg-sign -m "feat: add images/user dir + import-review paths

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: `BoardCandidate.local_path` field

**Files:**
- Modify: `skill/scripts/state.py` (`BoardCandidate` dataclass lines 46-98)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: existing `BoardCandidate`.
- Produces: `BoardCandidate.local_path: str = ""` carried through `to_dict`/`from_dict`/`from_thumbnail`. `dedup_key` unchanged. Default `""` so legacy candidates load unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
def test_board_candidate_local_path_roundtrips():
    from scripts.state import BoardCandidate
    bc = BoardCandidate(
        work_id="barn", title="Farmhouse", date="1925", museum="",
        thumbnail_url="images/user/barn.jpg", source_url="", rights="unknown",
        origin="user", local_path="images/user/barn.jpg")
    d = bc.to_dict()
    assert d["local_path"] == "images/user/barn.jpg"
    assert BoardCandidate.from_dict(d).local_path == "images/user/barn.jpg"


def test_board_candidate_local_path_defaults_empty_on_legacy_dict():
    from scripts.state import BoardCandidate
    legacy = {"work_id": "exotics", "title": "Exotics", "date": "1939",
              "museum": "aic", "thumbnail_url": "u", "source_url": "s",
              "rights": "in_copyright"}
    assert BoardCandidate.from_dict(legacy).local_path == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k local_path -v`
Expected: FAIL with `TypeError: __init__() got an unexpected keyword argument 'local_path'`

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/state.py`, add the field to `BoardCandidate` (after `first_run`, line 59):

```python
    origin: str = "discovered"
    first_run: str = ""
    local_path: str = ""
```

Add it to `to_dict` (inside the returned dict, after `"first_run"`):

```python
            "origin": self.origin, "first_run": self.first_run,
            "local_path": self.local_path,
```

Add it to `from_dict` (after the `first_run` kwarg):

```python
            origin=d.get("origin", "discovered"), first_run=d.get("first_run", ""),
            local_path=d.get("local_path", ""),
```

`from_thumbnail` needs no change — discovered candidates have no local file, so `local_path` stays its `""` default.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS (all, including existing round-trip tests)

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: add BoardCandidate.local_path for user-supplied pixels

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: `PackageState.merge_user_candidate`

**Files:**
- Modify: `skill/scripts/state.py` (add method to `PackageState`, after `merge_candidates`, line 187)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `BoardCandidate` (Task 2), existing `dedup_key`.
- Produces: `PackageState.merge_user_candidate(bc: BoardCandidate) -> str` returning `"added"` (appended new) or `"enriched"` (existing candidate matched by `dedup_key`; its `local_path` set from `bc.local_path`, `origin`/provenance untouched, no duplicate row).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
def test_merge_user_candidate_appends_new():
    from scripts.state import PackageState, BoardCandidate
    st = PackageState(artist="Paul Klee")
    bc = BoardCandidate(work_id="barn", title="Farmhouse", date="1925", museum="",
                        thumbnail_url="images/user/barn.jpg", source_url="",
                        rights="unknown", origin="user",
                        local_path="images/user/barn.jpg", first_run="run-1")
    assert st.merge_user_candidate(bc) == "added"
    assert len(st.candidates) == 1
    assert st.candidates[0].origin == "user"
    assert st.candidates[0].local_path == "images/user/barn.jpg"


def test_merge_user_candidate_enriches_existing_by_qid():
    from scripts.state import PackageState, BoardCandidate
    existing = BoardCandidate(work_id="senecio", title="Senecio", date="1922",
                              museum="aic", thumbnail_url="http://thumb",
                              source_url="http://aic/senecio", rights="public_domain",
                              qid="Q123", origin="discovered", first_run="run-1")
    st = PackageState(artist="Paul Klee", candidates=[existing])
    user = BoardCandidate(work_id="senecio-user", title="Senecio", date="1922",
                          museum="", thumbnail_url="images/user/senecio.jpg",
                          source_url="", rights="unknown", qid="Q123", origin="user",
                          local_path="images/user/senecio.jpg", first_run="run-2")
    assert st.merge_user_candidate(user) == "enriched"
    assert len(st.candidates) == 1                      # no duplicate
    assert st.candidates[0].origin == "discovered"      # provenance preserved
    assert st.candidates[0].source_url == "http://aic/senecio"
    assert st.candidates[0].local_path == "images/user/senecio.jpg"  # gained the file
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k merge_user_candidate -v`
Expected: FAIL with `AttributeError: 'PackageState' object has no attribute 'merge_user_candidate'`

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/state.py`, add to `PackageState` right after `merge_candidates` (after line 187):

```python
    def merge_user_candidate(self, bc: "BoardCandidate") -> str:
        """Merge a user-supplied candidate: enrich a dedup match with its local file,
        else append. Returns "enriched" or "added"."""
        key = bc.dedup_key()
        for c in self.candidates:
            if c.dedup_key() == key:
                if bc.local_path:
                    c.local_path = bc.local_path
                return "enriched"
        self.candidates.append(bc)
        return "added"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: PackageState.merge_user_candidate (enrich or append)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: `ImportRow` dataclass + `slug_work_id`

**Files:**
- Create: `skill/scripts/user_import.py`
- Test: `tests/test_user_import.py` (create)

**Interfaces:**
- Consumes: `scripts.paths.slugify`.
- Produces:
  - `ImportRow` frozen dataclass: `filename: str, source_path: str, state: str, artist: str = "", title: str = "", date: str = "", qid: str = "", museum: str = "", source_url: str = "", rights: str = "", medium: str = "", inst_ids: tuple[tuple[str,str], ...] = (), work_id: str = ""`. With `to_dict()` and `from_dict(d)`.
  - `slug_work_id(title: str, filename: str, existing: set[str]) -> str` — `slugify(title)` (or `slugify(Path(filename).stem)` if title empty), with `-2`/`-3`… suffix on collision against `existing`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_user_import.py`:

```python
from scripts.user_import import ImportRow, slug_work_id


def test_import_row_roundtrips():
    row = ImportRow(filename="senecio.jpg", source_path="/x/senecio.jpg",
                    state="confirmed", artist="Paul Klee", title="Senecio",
                    date="1922", qid="Q123", museum="aic",
                    source_url="http://aic/senecio", rights="public_domain",
                    inst_ids=(("aic", "555"),), work_id="senecio")
    d = row.to_dict()
    assert d["state"] == "confirmed"
    assert d["inst_ids"] == [["aic", "555"]]
    back = ImportRow.from_dict(d)
    assert back == row


def test_slug_work_id_from_title():
    assert slug_work_id("Senecio", "img001.jpg", set()) == "senecio"


def test_slug_work_id_falls_back_to_filename():
    assert slug_work_id("", "Barn-Study.JPG", set()) == "barn-study"


def test_slug_work_id_suffixes_on_collision():
    assert slug_work_id("Senecio", "x.jpg", {"senecio"}) == "senecio-2"
    assert slug_work_id("Senecio", "x.jpg", {"senecio", "senecio-2"}) == "senecio-3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.user_import'`

- [ ] **Step 3: Write minimal implementation**

Create `skill/scripts/user_import.py`:

```python
"""Thrust 2 — inject the user's own image collection as origin:"user" candidates.

Claude (the agent, in SKILL.md) views each image and emits a guess
{filename, source_path, artist, title, date}. Everything below is pure logic with
injected `lookup`/`copy_file` seams: verify each guess against the discovery
pipeline, build a human-reviewed import-review artifact, and ingest confirmed rows
into the package's candidates[].
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path

from scripts.paths import slugify

IMPORT_STATES: tuple[str, ...] = ("confirmed", "proposed", "off_artist", "unidentified")


@dataclass(frozen=True)
class ImportRow:
    filename: str
    source_path: str
    state: str
    artist: str = ""
    title: str = ""
    date: str = ""
    qid: str = ""
    museum: str = ""
    source_url: str = ""
    rights: str = ""
    medium: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    work_id: str = ""

    def to_dict(self) -> dict:
        return {
            "filename": self.filename, "source_path": self.source_path,
            "state": self.state, "artist": self.artist, "title": self.title,
            "date": self.date, "qid": self.qid, "museum": self.museum,
            "source_url": self.source_url, "rights": self.rights,
            "medium": self.medium, "inst_ids": [list(p) for p in self.inst_ids],
            "work_id": self.work_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImportRow":
        return cls(
            filename=d.get("filename", ""), source_path=d.get("source_path", ""),
            state=d.get("state", "unidentified"), artist=d.get("artist", ""),
            title=d.get("title", ""), date=d.get("date", ""), qid=d.get("qid", ""),
            museum=d.get("museum", ""), source_url=d.get("source_url", ""),
            rights=d.get("rights", ""), medium=d.get("medium", ""),
            inst_ids=tuple((str(a), str(b)) for a, b in d.get("inst_ids", ())),
            work_id=d.get("work_id", ""),
        )


def slug_work_id(title: str, filename: str, existing: set[str]) -> str:
    base = slugify(title) if title.strip() else slugify(Path(filename).stem)
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/user_import.py tests/test_user_import.py
git commit --no-gpg-sign -m "feat: ImportRow + slug_work_id for custom image import

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: `verify_identification`

**Files:**
- Modify: `skill/scripts/user_import.py`
- Test: `tests/test_user_import.py`

**Interfaces:**
- Consumes: `ImportRow` (Task 4).
- Produces: `verify_identification(guess: dict, study_artist: str, *, lookup) -> ImportRow`. `guess` keys: `filename, source_path, artist, title, date` (any may be missing/empty). `lookup` is a callable `lookup(study_artist: str, title: str) -> dict | None` returning a record dict (`title, date, qid, museum, source_url, rights, medium, inst_ids`) or `None`. State rules: no title → `unidentified`; `artist` given and folds different from `study_artist` → `off_artist`; `lookup` hit → `confirmed` (fields filled from record, `rights` from record else `"unknown"`); guess but no hit → `proposed` (`rights="unknown"`). `work_id` is left `""` (assigned at ingest).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_user_import.py`:

```python
from scripts.user_import import verify_identification


def _stub_lookup(record):
    return lambda artist, title: record


def test_verify_unidentified_when_no_title():
    row = verify_identification(
        {"filename": "blur.jpg", "source_path": "/x/blur.jpg"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "unidentified"


def test_verify_off_artist_when_artist_differs():
    row = verify_identification(
        {"filename": "miro.jpg", "artist": "Joan Miro", "title": "Harlequin"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "off_artist"


def test_verify_confirmed_pulls_record_metadata():
    record = {"title": "Senecio", "date": "1922", "qid": "Q123", "museum": "aic",
              "source_url": "http://aic/senecio", "rights": "public_domain",
              "medium": "oil", "inst_ids": (("aic", "555"),)}
    row = verify_identification(
        {"filename": "senecio.jpg", "artist": "Paul Klee", "title": "Senecio"},
        "Paul Klee", lookup=_stub_lookup(record))
    assert row.state == "confirmed"
    assert row.qid == "Q123"
    assert row.source_url == "http://aic/senecio"
    assert row.rights == "public_domain"
    assert row.inst_ids == (("aic", "555"),)


def test_verify_proposed_when_no_record():
    row = verify_identification(
        {"filename": "barn.jpg", "artist": "Paul Klee", "title": "Farmhouse",
         "date": "1925"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "proposed"
    assert row.title == "Farmhouse"
    assert row.rights == "unknown"
    assert row.qid == ""
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_import.py -k verify -v`
Expected: FAIL with `ImportError: cannot import name 'verify_identification'`

- [ ] **Step 3: Write minimal implementation**

Add to `skill/scripts/user_import.py`:

```python
def _fold(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def verify_identification(guess: dict, study_artist: str, *, lookup) -> ImportRow:
    filename = str(guess.get("filename", ""))
    base = ImportRow(
        filename=filename, source_path=str(guess.get("source_path", "")),
        state="unidentified", artist=str(guess.get("artist", "")).strip(),
        title=str(guess.get("title", "")).strip(),
        date=str(guess.get("date", "")).strip())
    if not base.title:
        return base
    if base.artist and _fold(base.artist) != _fold(study_artist):
        return replace(base, state="off_artist")
    record = lookup(study_artist, base.title)
    if record:
        return replace(
            base, state="confirmed",
            title=str(record.get("title") or base.title),
            date=str(record.get("date") or base.date),
            qid=str(record.get("qid", "")), museum=str(record.get("museum", "")),
            source_url=str(record.get("source_url", "")),
            rights=str(record.get("rights") or "unknown"),
            medium=str(record.get("medium", "")),
            inst_ids=tuple((str(a), str(b)) for a, b in record.get("inst_ids", ())))
    return replace(base, state="proposed", rights="unknown")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/user_import.py tests/test_user_import.py
git commit --no-gpg-sign -m "feat: verify_identification state machine for user images

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: `build_review` + `parse_review`

**Files:**
- Modify: `skill/scripts/user_import.py`
- Test: `tests/test_user_import.py`

**Interfaces:**
- Consumes: `ImportRow` (Task 4).
- Produces:
  - `build_review(rows: list[ImportRow], artist: str) -> tuple[dict, str]` — `(json_obj, html_str)`. `json_obj = {"artist": artist, "rows": [row.to_dict(), ...]}`. `html_str` is a self-contained review table; each row shows filename, state badge, and its proposed metadata.
  - `parse_review(json_obj: dict) -> list[ImportRow]` — returns only rows the human confirmed: `state == "confirmed"` **and** a non-empty `title`. (The human edits a `proposed` row's metadata and flips its `state` to `confirmed` in the file to keep it; anything left non-confirmed is dropped.)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_user_import.py`:

```python
from scripts.user_import import build_review, parse_review


def _rows():
    return [
        ImportRow(filename="senecio.jpg", source_path="/x/senecio.jpg",
                  state="confirmed", title="Senecio", date="1922", qid="Q123"),
        ImportRow(filename="barn.jpg", source_path="/x/barn.jpg",
                  state="proposed", title="Farmhouse", rights="unknown"),
        ImportRow(filename="miro.jpg", source_path="/x/miro.jpg",
                  state="off_artist", artist="Joan Miro", title="Harlequin"),
    ]


def test_build_review_json_and_html():
    obj, html = build_review(_rows(), "Paul Klee")
    assert obj["artist"] == "Paul Klee"
    assert [r["filename"] for r in obj["rows"]] == ["senecio.jpg", "barn.jpg", "miro.jpg"]
    assert "Senecio" in html and "off_artist" in html and "proposed" in html


def test_parse_review_keeps_only_confirmed_with_title():
    obj, _ = build_review(_rows(), "Paul Klee")
    kept = parse_review(obj)
    assert [r.filename for r in kept] == ["senecio.jpg"]


def test_parse_review_accepts_human_promoted_proposed_row():
    obj, _ = build_review(_rows(), "Paul Klee")
    obj["rows"][1]["state"] = "confirmed"   # human edited + confirmed the barn row
    kept = parse_review(obj)
    assert {r.filename for r in kept} == {"senecio.jpg", "barn.jpg"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_import.py -k review -v`
Expected: FAIL with `ImportError: cannot import name 'build_review'`

- [ ] **Step 3: Write minimal implementation**

Add to `skill/scripts/user_import.py`:

```python
def build_review(rows: list[ImportRow], artist: str) -> tuple[dict, str]:
    json_obj = {"artist": artist, "rows": [r.to_dict() for r in rows]}
    cells = "\n".join(
        "<tr><td>{fn}</td><td class='st {st}'>{st}</td>"
        "<td>{title}</td><td>{date}</td><td>{museum}</td><td>{rights}</td></tr>".format(
            fn=_esc(r.filename), st=_esc(r.state), title=_esc(r.title),
            date=_esc(r.date), museum=_esc(r.museum), rights=_esc(r.rights))
        for r in rows)
    html = _REVIEW_TEMPLATE.replace("__ARTIST__", _esc(artist)).replace("__ROWS__", cells)
    return json_obj, html


def parse_review(json_obj: dict) -> list[ImportRow]:
    rows = [ImportRow.from_dict(d) for d in json_obj.get("rows", [])]
    return [r for r in rows if r.state == "confirmed" and r.title.strip()]


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


_REVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Import review — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 1rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; font-size: 13px; text-align: left; }
  .st { font-weight: bold; }
  .st.confirmed { color: #137333; }
  .st.proposed { color: #b06000; }
  .st.off_artist, .st.unidentified { color: #a50e0e; }
</style></head><body>
<h2>Import review — __ARTIST__</h2>
<p>Edit proposed rows and set their <code>state</code> to <code>confirmed</code> in
import-review.json to keep them. off_artist / unidentified rows are set aside.</p>
<table>
<tr><th>file</th><th>state</th><th>title</th><th>date</th><th>museum</th><th>rights</th></tr>
__ROWS__
</table></body></html>
"""
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/user_import.py tests/test_user_import.py
git commit --no-gpg-sign -m "feat: build_review/parse_review import-review artifact

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: `make_pipeline_lookup` (default verification seam)

**Files:**
- Modify: `skill/scripts/user_import.py`
- Test: `tests/test_user_import.py`

**Interfaces:**
- Consumes: `scripts.wikidata.search_wikidata` (returns `(board, works, ambiguous)`), `scripts.museum_search.search_aic` (returns `list[ThumbnailCandidate]`). Both injectable.
- Produces: `make_pipeline_lookup(artist: str, *, wikidata_search=search_wikidata, aic_search=search_aic) -> Callable[[str, str], dict | None]`. Fetches the artist's board **once**, indexes by folded title, and returns a `lookup(artist, title)` closure usable as `verify_identification`'s `lookup`. A title hit returns the record dict; a miss returns `None`. Network errors from either search degrade to an empty board (lookup returns `None`), never raise.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_user_import.py`:

```python
from scripts.user_import import make_pipeline_lookup
from scripts.museum_search import ThumbnailCandidate


def test_make_pipeline_lookup_hits_and_misses():
    cand = ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="http://thumb", source_url="http://aic/senecio",
        date="1922", rights="public_domain", medium="oil", qid="Q123",
        inst_ids=(("aic", "555"),))
    lookup = make_pipeline_lookup(
        "Paul Klee",
        wikidata_search=lambda a: ([], [], []),
        aic_search=lambda a: [cand])
    rec = lookup("Paul Klee", "senecio")          # folded title match
    assert rec["qid"] == "Q123"
    assert rec["source_url"] == "http://aic/senecio"
    assert rec["inst_ids"] == (("aic", "555"),)
    assert lookup("Paul Klee", "Nonexistent Work") is None


def test_make_pipeline_lookup_survives_search_errors():
    def boom(a):
        raise RuntimeError("WDQS 504")
    lookup = make_pipeline_lookup(
        "Paul Klee", wikidata_search=boom, aic_search=lambda a: [])
    assert lookup("Paul Klee", "Senecio") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_import.py -k pipeline_lookup -v`
Expected: FAIL with `ImportError: cannot import name 'make_pipeline_lookup'`

- [ ] **Step 3: Write minimal implementation**

Add to `skill/scripts/user_import.py` — extend the imports at the top of the file:

```python
from scripts.museum_search import search_aic
from scripts.wikidata import search_wikidata
```

Then add:

```python
def make_pipeline_lookup(artist: str, *, wikidata_search=search_wikidata,
                         aic_search=search_aic):
    """Build the artist's board once; return a lookup(artist, title) closure that
    corroborates a guessed title against it. Used as verify_identification's `lookup`."""
    board = []
    try:
        cands, _works, _ambiguous = wikidata_search(artist)
        board.extend(cands)
    except Exception:
        pass
    try:
        board.extend(aic_search(artist))
    except Exception:
        pass
    index: dict[str, object] = {}
    for c in board:
        index.setdefault(_fold(c.title), c)

    def lookup(_artist: str, title: str) -> dict | None:
        c = index.get(_fold(title))
        if c is None:
            return None
        return {"title": c.title, "date": c.date, "qid": c.qid, "museum": c.museum,
                "source_url": c.source_url, "rights": c.rights,
                "medium": getattr(c, "medium", ""),
                "inst_ids": tuple(c.inst_ids)}

    return lookup
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/user_import.py tests/test_user_import.py
git commit --no-gpg-sign -m "feat: make_pipeline_lookup — board-backed verification seam

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: `ingest_import_review`

**Files:**
- Modify: `skill/scripts/user_import.py`
- Test: `tests/test_user_import.py`

**Interfaces:**
- Consumes: `ImportRow` (Task 4), `slug_work_id` (Task 4), `PackageState`/`BoardCandidate`/`merge_user_candidate` (Tasks 2-3).
- Produces: `ingest_import_review(rows: list[ImportRow], state, user_dir: Path, run_id: str, *, copy_file=shutil.copy2) -> tuple[int, int]` returning `(added, enriched)`. For each row: assign a unique `work_id` via `slug_work_id` over the package's existing work_ids, `copy_file(source_path, user_dir/<filename>)`, build a `BoardCandidate(origin="user", thumbnail_url=local_rel, local_path=local_rel, first_run=run_id, …)` where `local_rel = f"images/user/{name}"`, and `state.merge_user_candidate(bc)`. Does **not** record the run (the caller does, mirroring discovery). Pure aside from the injected `copy_file`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_user_import.py`:

```python
from pathlib import Path
from scripts.user_import import ingest_import_review
from scripts.state import PackageState, BoardCandidate


def _copy_spy(calls):
    def _copy(src, dst):
        calls.append((str(src), str(dst)))
    return _copy


def test_ingest_appends_new_user_candidate(tmp_path):
    st = PackageState(artist="Paul Klee")
    rows = [ImportRow(filename="barn.jpg", source_path="/x/barn.jpg",
                      state="confirmed", title="Farmhouse", date="1925",
                      rights="unknown")]
    calls = []
    added, enriched = ingest_import_review(
        rows, st, tmp_path / "user", "run-1", copy_file=_copy_spy(calls))
    assert (added, enriched) == (1, 0)
    c = st.candidates[0]
    assert c.origin == "user"
    assert c.work_id == "farmhouse"
    assert c.local_path == "images/user/barn.jpg"
    assert c.thumbnail_url == "images/user/barn.jpg"
    assert c.first_run == "run-1"
    assert calls == [("/x/barn.jpg", str(tmp_path / "user" / "barn.jpg"))]


def test_ingest_enriches_existing_discovered(tmp_path):
    existing = BoardCandidate(work_id="senecio", title="Senecio", date="1922",
                              museum="aic", thumbnail_url="http://thumb",
                              source_url="http://aic/senecio", rights="public_domain",
                              qid="Q123", origin="discovered", first_run="run-1")
    st = PackageState(artist="Paul Klee", candidates=[existing])
    rows = [ImportRow(filename="senecio.jpg", source_path="/x/senecio.jpg",
                      state="confirmed", title="Senecio", qid="Q123")]
    added, enriched = ingest_import_review(
        rows, st, tmp_path / "user", "run-2", copy_file=_copy_spy([]))
    assert (added, enriched) == (0, 1)
    assert len(st.candidates) == 1
    assert st.candidates[0].origin == "discovered"
    assert st.candidates[0].local_path == "images/user/senecio.jpg"


def test_ingest_is_idempotent_on_reimport(tmp_path):
    st = PackageState(artist="Paul Klee")
    rows = [ImportRow(filename="barn.jpg", source_path="/x/barn.jpg",
                      state="confirmed", title="Farmhouse", qid="Q9")]
    ingest_import_review(rows, st, tmp_path / "user", "run-1", copy_file=_copy_spy([]))
    added, enriched = ingest_import_review(
        rows, st, tmp_path / "user", "run-2", copy_file=_copy_spy([]))
    assert (added, enriched) == (0, 1)        # second pass dedups on qid
    assert len(st.candidates) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_user_import.py -k ingest -v`
Expected: FAIL with `ImportError: cannot import name 'ingest_import_review'`

- [ ] **Step 3: Write minimal implementation**

Add to `skill/scripts/user_import.py` — `BoardCandidate` is needed; add to imports:

```python
from scripts.state import BoardCandidate
```

Then add:

```python
def ingest_import_review(rows, state, user_dir: Path, run_id: str,
                         *, copy_file=shutil.copy2) -> tuple[int, int]:
    """Copy confirmed user images into user_dir and merge them into state.candidates[].
    Returns (added, enriched). The caller records the run."""
    user_dir = Path(user_dir)
    user_dir.mkdir(parents=True, exist_ok=True)
    existing_ids = {c.work_id for c in state.candidates}
    added = enriched = 0
    for row in rows:
        wid = slug_work_id(row.title, row.filename, existing_ids)
        existing_ids.add(wid)
        name = Path(row.filename).name
        dest = user_dir / name
        copy_file(row.source_path, dest)
        local_rel = f"images/user/{name}"
        bc = BoardCandidate(
            work_id=wid, title=row.title, date=row.date, museum=row.museum,
            thumbnail_url=local_rel, source_url=row.source_url,
            rights=row.rights or "unknown", medium=row.medium, qid=row.qid,
            inst_ids=tuple(row.inst_ids), origin="user", first_run=run_id,
            local_path=local_rel)
        if state.merge_user_candidate(bc) == "added":
            added += 1
        else:
            enriched += 1
    return added, enriched
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_user_import.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/user_import.py tests/test_user_import.py
git commit --no-gpg-sign -m "feat: ingest_import_review — copy files + merge user candidates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: Gallery origin badge for user candidates

**Files:**
- Modify: `skill/scripts/gallery.py` (`build_thumbnail_gallery` payload, lines 89-104; the thumbnail template's `renderGrid`)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: candidates passed to `build_thumbnail_gallery` may carry `origin`/`local_path` (a `BoardCandidate`). `ThumbnailCandidate` lacks them — read with `getattr(c, "origin", "discovered")` / `getattr(c, "local_path", "")`.
- Produces: the board payload includes `"origin"` per candidate; the rendered HTML shows a `user` badge on user-origin cards. Discovered cards are unchanged.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gallery.py`:

```python
def test_thumbnail_gallery_marks_user_origin():
    from scripts.gallery import build_thumbnail_gallery
    from scripts.state import BoardCandidate
    user = BoardCandidate(
        work_id="barn", title="Farmhouse", date="1925", museum="",
        thumbnail_url="images/user/barn.jpg", source_url="", rights="unknown",
        origin="user", local_path="images/user/barn.jpg")
    html = build_thumbnail_gallery([user], "Paul Klee")
    assert '"origin": "user"' in html
    assert "USER" in html  # badge label rendered in the grid template
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gallery.py -k user_origin -v`
Expected: FAIL (payload has no `origin`; template renders no `USER` badge)

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/gallery.py`, add `"origin"` to the `build_thumbnail_gallery` payload dict (after the `"inst_ids"` line, ~line 101):

```python
            "inst_ids": [list(pair) for pair in c.inst_ids],
            "origin": getattr(c, "origin", "discovered"),
```

Then, in the thumbnail-board template's `renderGrid` function (the `card.innerHTML = ...` for the board grid — the one that renders the `pd`/`©` badge near line 313), add a user badge alongside it. Locate the badge span and extend it:

```javascript
          '<span class="badge ' + (pd ? "pd" : "copy") + '">' + (pd ? "PD" : "\\u00a9") + '</span>' +
          (c.origin === "user" ? '<span class="badge user">USER</span>' : '') + '</div>' +
```

Add a `.badge.user` style next to the existing `.badge` rule (near line 254):

```css
  .badge.user { background: #5b3; color: #042; }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_gallery.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit --no-gpg-sign -m "feat: gallery shows USER badge for origin:user candidates

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: SKILL.md — document the import operation

**Files:**
- Modify: `skill/SKILL.md`
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: the full `user_import` API (Tasks 4-8), `PackageState.record_run` (existing), `StudyPaths.import_review_json/html` + `user_images_dir` (Task 1).
- Produces: a documented **import** operation in SKILL.md wiring the pipeline below. No code interface.

- [ ] **Step 1: Write the failing test**

First inspect how `tests/test_skill_md.py` reads the file and asserts (match its existing pattern — a helper that loads `SKILL.md` text). Then add:

```python
def test_skill_md_documents_user_import():
    text = _skill_md_text()   # reuse the module's existing loader helper
    assert "import" in text.lower()
    assert "user_import" in text
    assert "verify_identification" in text
    assert "ingest_import_review" in text
    assert "import-review" in text
    assert 'source="user-import"' in text or "user-import" in text
```

(If `test_skill_md.py` has no shared loader helper, read `SKILL.md` inline with `pathlib` the same way the other tests in that file do.)

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_md.py -k user_import -v`
Expected: FAIL (SKILL.md does not yet mention these symbols)

- [ ] **Step 3: Write minimal implementation**

Add a section to `skill/SKILL.md` documenting **import** as a re-enterable operation beside discover/select/study. It must contain the literal symbols the test checks (`user_import`, `verify_identification`, `ingest_import_review`, `import-review`, `user-import`). Use this content (place it near the image-discovery / multi-run operations section):

```markdown
### Import your own images (origin:"user")

A re-enterable operation alongside discover · select · study. The user points the
skill at a folder of their own paintings for the **current** artist study.

1. **View each image (Claude vision).** For every image file, look at it and emit a
   guess `{filename, source_path, artist, title, date}` — or a null/empty title if you
   cannot identify the work.
2. **Verify against the pipeline.** Build the verification seam once with
   `make_pipeline_lookup(artist)`, then `verify_identification(guess, artist, lookup=...)`
   per image. Each becomes an `ImportRow` in state `confirmed` (pipeline corroborated),
   `proposed` (a guess, no record — `rights:"unknown"`), `off_artist` (different artist —
   set aside), or `unidentified` (no guess — set aside).
3. **Human trust gate.** `build_review(rows, artist)` → write `import-review.json` and
   `import-review.html` (paths: `StudyPaths.import_review_json` / `import_review_html`).
   **Pause.** The user opens the HTML, edits `proposed` rows, and sets a row's `state` to
   `confirmed` in the JSON to keep it. off_artist / unidentified rows are never ingested.
4. **Ingest.** `parse_review(json)` → confirmed rows →
   `ingest_import_review(rows, state, paths.user_images_dir, run_id, copy_file=shutil.copy2)`.
   It copies files into `images/user/`, appends new works as `origin:"user"`, and
   **enriches** a work already on the board (dedup by QID/inst_ids/work_id) by attaching
   its local file — no duplicate card. Then record the run:
   `state.record_run(source="user-import", added=added, merged=enriched, total=len(state.candidates))`
   and `state.save(paths.state_json)`.

From here, user images flow through curation and analysis identically to discovered
ones — except visual analysis reads their full-resolution local file
(`candidate.local_path`) directly, with no rights-gated re-download. The gallery shows a
`USER` badge on these cards; the studied ✓ badge composes unchanged.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit --no-gpg-sign -m "docs: wire the import (custom images) operation into SKILL.md

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Final Verification

After all tasks, run the full suite:

```bash
uv run pytest -q
```

Expected: all green (the Thrust-1 baseline of 215 + the new `test_user_import.py` cases and added assertions in paths/state/gallery/skill_md).
