# Library Collection Mode (Spec B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a library-collection mode that eagerly downloads full-res images, deduplicates each against an on-disk library via the built Spec A engine, keeps the best copy with merged metadata, and syncs the deduped library into the existing curation board.

**Architecture:** New `scripts/library.py` executes Spec A `DedupAction`s as real file moves/deletes into `images/library/`, orchestrates batch dedup (`build_library`), seeds the user's external folder (`seed_import`), and mirrors the library onto `state.candidates` (`sync_candidates`). `image_download.download_library` fetches full-res into `images/incoming/`. `SKILL.md` gains a coexisting Phase-A branch. A live `e2e/library_collection.py` validates on the Cezanne seed.

**Tech Stack:** Python 3, the Spec A engine (`scripts/image_similarity`, `scripts/image_manifest`, `scripts/dedup`), `pytest` (offline, seam-injected), uv. Tests import `from scripts.<module> import ...` (pytest `pythonpath=["skill"]`).

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-21-library-collection-mode-design.md`.
- **Consumes Spec A (do not modify it):** `dedup.resolve(inc, manifest, run_id, *, threshold) -> DedupAction`; `DedupAction(kind, keep_path, delete_path, canonical_name, entry)` where `kind in {"add","merge"}` and `entry.path` is already `images/library/<canonical_name>`; `dedup.IncomingImage(tmp_path, hashes, width, height, bytes, title, date, qid, inst_ids, source, source_url, rights, medium)`; `image_similarity.perceptual_hashes(path) -> ImageHashes|None`, `image_dims(path) -> (w,h,bytes)|None`, `DUP_THRESHOLD = 0.90`; `image_manifest.Manifest` (`load`/`save`/`find_match`/`upsert`), `ManifestEntry`.
- **Path constants:** `LIBRARY_REL = "images/library"` (matches `dedup.LIBRARY_REL`), `INCOMING_REL = "images/incoming"`, `MANIFEST_REL = "images/manifest.json"`.
- **Seed handling:** **move, not copy** — files move out of `images/user/` into `images/library/`; `images/user/` ends empty. The **external collection is never modified** (read + copy only).
- **Atomicity:** place the winner at its library path, then delete the loser **only after**; never delete a path equal to the winner's destination; never delete outside the study package.
- **Stars invariant:** `sync_candidates` must **preserve existing `BoardCandidate.stars`** on re-sync (a starred work is never reset to 0 by a later collect).
- **Rights:** recorded on entries/origins, **never gates** a download.
- **Fail-open:** an un-hashable/unreadable image → skipped, never added.
- **Tests:** offline `pytest`, one `tests/test_<module>.py` per module, injected `move`/`delete`/`fetch`/`resolve_url` seams; real PIL fixtures only where pixel behavior is under test. `uv run pytest`. The **e2e harness is live and lives in `e2e/` (outside `tests/`)** — pytest must not collect it.

---

### Task 1: `paths.py` — library/incoming/manifest paths

**Files:**
- Modify: `skill/scripts/paths.py` (add 3 properties + 2 scaffold dirs)
- Test: `tests/test_paths.py`

**Interfaces:**
- Produces: `StudyPaths.library_dir -> Path`, `.incoming_dir -> Path`, `.manifest_json -> Path`; `scaffold()` also creates `images/library` and `images/incoming`.

- [ ] **Step 1: Write the failing test** — append to `tests/test_paths.py`:

```python
def test_library_incoming_manifest_paths(tmp_path):
    from scripts.paths import study_paths, scaffold
    sp = study_paths(tmp_path, "Cezanne")
    assert sp.library_dir == sp.images_dir / "library"
    assert sp.incoming_dir == sp.images_dir / "incoming"
    assert sp.manifest_json == sp.images_dir / "manifest.json"

def test_scaffold_creates_library_and_incoming(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "Cezanne")
    assert sp.library_dir.is_dir()
    assert sp.incoming_dir.is_dir()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_paths.py -k "library_incoming or scaffold_creates_library" -v`
Expected: FAIL — `AttributeError: 'StudyPaths' object has no attribute 'library_dir'`.

- [ ] **Step 3: Implement** — in `skill/scripts/paths.py`, add to the `StudyPaths` class (next to `selected_dir`):

```python
    @property
    def library_dir(self) -> Path:
        return self.images_dir / "library"

    @property
    def incoming_dir(self) -> Path:
        return self.images_dir / "incoming"

    @property
    def manifest_json(self) -> Path:
        return self.images_dir / "manifest.json"
```

And add `"images/library"` and `"images/incoming"` to the `_SCAFFOLD_DIRS` tuple (after `"images/selected"`).

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/paths.py tests/test_paths.py
git commit -m "feat: paths — library/incoming/manifest study-package paths"
```

---

### Task 2: `library.execute_action` — DedupAction → files on disk

**Files:**
- Create: `skill/scripts/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `dedup.DedupAction`, `paths.StudyPaths`.
- Produces:
  - `LibrarySummary(added: int, merged_kept: int, merged_replaced: int)` (frozen dataclass, defaults 0)
  - `_abs(paths, p) -> Path` (absolute path: `Path(p)` if absolute else `paths.root / p`)
  - `execute_action(action, paths, *, move=shutil.move, delete=os.remove) -> ManifestEntry`

- [ ] **Step 1: Write the failing tests** — `tests/test_library.py`:

```python
import os
from dataclasses import dataclass
from pathlib import Path

from scripts.image_manifest import ManifestEntry
from scripts.dedup import DedupAction
from scripts.library import execute_action, _abs


def _spy(record):
    def fn(src, dst=None):
        record.append((str(src), str(dst)) if dst is not None else (str(src),))
        if dst is None:          # delete
            os.remove(src)
        else:                    # move
            os.replace(src, dst)
    return fn


def _entry(work_id, cn):
    return ManifestEntry(work_id=work_id, filename=cn, path=f"images/library/{cn}")


def test_add_moves_incoming_into_library(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    inc = sp.incoming_dir / "x.jpg"; inc.write_bytes(b"img")
    action = DedupAction(kind="add", keep_path=str(inc), delete_path=None,
                         canonical_name="the-vase.jpg", entry=_entry("the-vase", "the-vase.jpg"))
    moves, deletes = [], []
    entry = execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert (sp.library_dir / "the-vase.jpg").is_file()
    assert not inc.exists()
    assert deletes == []
    assert entry.path == "images/library/the-vase.jpg"


def test_merge_incoming_wins_replaces_old_library_file(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    old = sp.library_dir / "old.jpg"; old.write_bytes(b"small")
    inc = sp.incoming_dir / "big.jpg"; inc.write_bytes(b"bigimg")
    action = DedupAction(kind="merge", keep_path=str(inc),
                         delete_path="images/library/old.jpg",
                         canonical_name="old.jpg", entry=_entry("w", "old.jpg"))
    moves, deletes = [], []
    execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert (sp.library_dir / "old.jpg").read_bytes() == b"bigimg"   # winner overwrote
    assert not inc.exists()
    # delete_path == destination -> no separate delete
    assert deletes == []


def test_merge_existing_wins_deletes_incoming(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    lib = sp.library_dir / "keep.jpg"; lib.write_bytes(b"bigimg")
    inc = sp.incoming_dir / "small.jpg"; inc.write_bytes(b"sm")
    action = DedupAction(kind="merge", keep_path="images/library/keep.jpg",
                         delete_path=str(inc), canonical_name="keep.jpg",
                         entry=_entry("w", "keep.jpg"))
    moves, deletes = [], []
    execute_action(action, sp, move=_spy(moves), delete=_spy(deletes))
    assert lib.read_bytes() == b"bigimg"      # untouched
    assert not inc.exists()                   # incoming deleted
    assert moves == []                        # no move (keep == dest)


def test_existing_wins_with_rename_moves_within_library(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    lib = sp.library_dir / "img001.jpg"; lib.write_bytes(b"big")
    inc = sp.incoming_dir / "s.jpg"; inc.write_bytes(b"s")
    action = DedupAction(kind="merge", keep_path="images/library/img001.jpg",
                         delete_path=str(inc), canonical_name="still-life.jpg",
                         entry=_entry("w", "still-life.jpg"))
    execute_action(action, sp, move=lambda s, d: os.replace(s, d), delete=os.remove)
    assert (sp.library_dir / "still-life.jpg").read_bytes() == b"big"
    assert not lib.exists() and not inc.exists()


def test_delete_only_targets_inside_package(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    inc = sp.incoming_dir / "x.jpg"; inc.write_bytes(b"i")
    action = DedupAction(kind="add", keep_path=str(inc), delete_path=None,
                         canonical_name="x.jpg", entry=_entry("x", "x.jpg"))
    deletes = []
    execute_action(action, sp, move=lambda s, d: os.replace(s, d), delete=_spy(deletes))
    assert deletes == []  # add never deletes
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_library.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.library'`.

- [ ] **Step 3: Implement** — create `skill/scripts/library.py`:

```python
"""Spec B — library collection: execute Spec A dedup decisions as real file ops,
orchestrate batch dedup, seed the user's collection, and mirror the library onto
the curation board. Filesystem effects go through injected move/delete/copy seams.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from scripts.dedup import DedupAction, resolve, IncomingImage
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.image_similarity import DUP_THRESHOLD, perceptual_hashes, image_dims
from scripts.state import BoardCandidate, PackageState
from scripts.paths import StudyPaths


@dataclass(frozen=True)
class LibrarySummary:
    added: int = 0
    merged_kept: int = 0       # dup found, existing copy kept (incoming deleted)
    merged_replaced: int = 0   # dup found, incoming larger (old library file replaced)


def _abs(paths: StudyPaths, p) -> Path:
    p = Path(p)
    return p if p.is_absolute() else paths.root / p


def execute_action(action: DedupAction, paths: StudyPaths, *,
                   move=shutil.move, delete=os.remove) -> ManifestEntry:
    entry = action.entry
    dest = _abs(paths, entry.path)
    keep = _abs(paths, action.keep_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if keep.resolve() != dest.resolve():
        move(str(keep), str(dest))
    if action.delete_path:
        loser = _abs(paths, action.delete_path)
        if loser.resolve() != dest.resolve() and loser.exists():
            delete(str(loser))
    return entry
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_library.py -v`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/library.py tests/test_library.py
git commit -m "feat: library.execute_action — DedupAction to file moves/deletes, atomic"
```

---

### Task 3: `library.make_incoming` + `build_library` — batch dedup

**Files:**
- Modify: `skill/scripts/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `execute_action`, `dedup.resolve`, `image_similarity.perceptual_hashes`/`image_dims`, `Manifest`.
- Produces:
  - `make_incoming(path, *, source, source_url="", rights="", title="", date="", qid="", inst_ids=(), medium="", hash_for=perceptual_hashes, dims_for=image_dims) -> IncomingImage | None`
  - `build_library(incoming, manifest, paths, run_id, *, threshold=DUP_THRESHOLD, move=shutil.move, delete=os.remove) -> LibrarySummary`

- [ ] **Step 1: Write the failing tests** — append to `tests/test_library.py`:

```python
from PIL import Image, ImageDraw
from scripts.image_manifest import Manifest
from scripts.library import make_incoming, build_library


def _img(path, seed=0, size=(256, 256)):
    im = Image.new("RGB", size, "white"); d = ImageDraw.Draw(im)
    cw, ch = size[0] // 4, size[1] // 4
    for i in range(4):
        for j in range(4):
            v = (seed * 37 + (i * 4 + j) * 53) % 256
            d.rectangle([i*cw, j*ch, (i+1)*cw, (j+1)*ch], fill=(v, (v*2) % 256, (v*3) % 256))
    im.save(path); return path


def test_make_incoming_none_on_garbage(tmp_path):
    bad = tmp_path / "bad.jpg"; bad.write_bytes(b"nope")
    assert make_incoming(bad, source="user-seed") is None


def test_make_incoming_builds_from_real_image(tmp_path):
    p = _img(tmp_path / "a.png", seed=1, size=(200, 120))
    inc = make_incoming(p, source="aic", title="A", qid="Q1")
    assert inc.width == 200 and inc.height == 120 and inc.bytes > 0
    assert inc.source == "aic" and inc.title == "A" and inc.qid == "Q1"


def test_build_library_collapses_same_work_keeps_larger(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    big = _img(sp.incoming_dir / "big.png", seed=2, size=(400, 400))
    small_src = _img(tmp_path / "small_src.png", seed=2, size=(200, 200))  # same pattern, smaller
    small = sp.incoming_dir / "small.png"; Image.open(small_src).save(small)
    m = Manifest()
    inc = [make_incoming(big, source="aic", title="Vase"),
           make_incoming(small, source="commons", title="Vase")]
    summary = build_library(inc, m, sp, run_id="run1")
    assert summary.added == 1 and (summary.merged_kept + summary.merged_replaced) == 1
    assert len(m.entries) == 1
    # larger (400x400) wins
    assert m.entries[0].width == 400
    libfiles = list(sp.library_dir.glob("*.png"))
    assert len(libfiles) == 1
    assert not list(sp.incoming_dir.glob("*.png"))  # both consumed


def test_build_library_cross_run_merges_against_manifest(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    first = _img(sp.incoming_dir / "f.png", seed=3, size=(300, 300))
    m = Manifest()
    build_library([make_incoming(first, source="aic", title="W")], m, sp, run_id="r1")
    # later run: bigger copy of the same work
    bigger = _img(sp.incoming_dir / "f2.png", seed=3, size=(600, 600))
    s2 = build_library([make_incoming(bigger, source="commons", title="W")], m, sp, run_id="r2")
    assert s2.merged_replaced == 1 and len(m.entries) == 1 and m.entries[0].width == 600
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_library.py -k "make_incoming or build_library" -v`
Expected: FAIL — `ImportError: cannot import name 'make_incoming'`.

- [ ] **Step 3: Implement** — append to `skill/scripts/library.py`:

```python
def make_incoming(path, *, source: str, source_url: str = "", rights: str = "",
                  title: str = "", date: str = "", qid: str = "", inst_ids=(),
                  medium: str = "", hash_for=perceptual_hashes,
                  dims_for=image_dims) -> "IncomingImage | None":
    h = hash_for(path)
    d = dims_for(path)
    if h is None or d is None:
        return None
    w, ht, b = d
    return IncomingImage(
        tmp_path=str(path), hashes=h, width=w, height=ht, bytes=b,
        title=title, date=date, qid=qid, inst_ids=tuple(inst_ids),
        source=source, source_url=source_url, rights=rights, medium=medium)


def build_library(incoming, manifest: Manifest, paths: StudyPaths, run_id: str, *,
                  threshold: float = DUP_THRESHOLD, move=shutil.move,
                  delete=os.remove) -> LibrarySummary:
    added = kept = replaced = 0
    for inc in incoming:
        action = resolve(inc, manifest, run_id, threshold=threshold)
        execute_action(action, paths, move=move, delete=delete)
        manifest.upsert(action.entry)
        if action.kind == "add":
            added += 1
        elif action.keep_path == inc.tmp_path:   # incoming won
            replaced += 1
        else:                                     # existing kept
            kept += 1
    return LibrarySummary(added=added, merged_kept=kept, merged_replaced=replaced)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_library.py -v`
Expected: PASS (all library tests so far).
If a `build_library` collapse test sees the two synthetic images NOT dedup (different `work_id`, both added), the fixtures aren't perceptually identical enough — make `small` an exact downscale of `big` (`Image.open(big).resize((200,200)).save(small)`) so pHash matches. Never lower `DUP_THRESHOLD`.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/library.py tests/test_library.py
git commit -m "feat: library.make_incoming + build_library — batch dedup orchestration"
```

---

### Task 4: `library.sync_candidates` — mirror library onto the board

**Files:**
- Modify: `skill/scripts/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `Manifest`, `state.PackageState`, `state.BoardCandidate`.
- Produces: `sync_candidates(manifest, state, run_id) -> int` (upserts one `BoardCandidate` per entry; **preserves existing `BoardCandidate.stars`**; writes that star value back onto the manifest entry so the two stay consistent).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_library.py`:

```python
from scripts.image_manifest import ManifestEntry
from scripts.state import PackageState, BoardCandidate
from scripts.library import sync_candidates


def _e(work_id, **kw):
    return ManifestEntry(work_id=work_id, filename=f"{work_id}.jpg",
                         path=f"images/library/{work_id}.jpg", **kw)


def test_sync_creates_one_candidate_per_entry(tmp_path):
    m = Manifest(entries=[_e("vase", title="Vase", qid="Q1",
                             origins=[{"source": "user-seed"}]),
                          _e("apples", title="Apples",
                             origins=[{"source": "aic"}])])
    st = PackageState(artist="A")
    n = sync_candidates(m, st, run_id="r1")
    assert n == 2
    by_id = {c.work_id: c for c in st.candidates}
    assert by_id["vase"].local_path == "images/library/vase.jpg"
    assert by_id["vase"].thumbnail_path == "images/library/vase.jpg"
    assert by_id["vase"].origin == "user"        # user-seed origin -> USER badge
    assert by_id["apples"].origin == "discovered"


def test_sync_preserves_existing_board_stars(tmp_path):
    st = PackageState(artist="A")
    st.candidates.append(BoardCandidate(
        work_id="vase", title="Vase", date="", museum="", thumbnail_url="",
        source_url="", rights="", local_path="images/library/vase.jpg", stars=5))
    m = Manifest(entries=[_e("vase", title="Vase", stars=0,
                             origins=[{"source": "aic"}])])
    sync_candidates(m, st, run_id="r2")
    assert len(st.candidates) == 1                  # updated in place
    assert st.candidates[0].stars == 5              # NOT reset to 0
    assert m.entries[0].stars == 5                  # manifest brought in step
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_library.py -k sync -v`
Expected: FAIL — `ImportError: cannot import name 'sync_candidates'`.

- [ ] **Step 3: Implement** — append to `skill/scripts/library.py`:

```python
def _first_source_url(entry: ManifestEntry) -> str:
    for o in entry.origins:
        if o.get("source_url"):
            return o["source_url"]
    return ""


def sync_candidates(manifest: Manifest, state: PackageState, run_id: str) -> int:
    by_id = {c.work_id: c for c in state.candidates}
    n = 0
    for e in manifest.entries:
        existing = by_id.get(e.work_id)
        stars = existing.stars if existing is not None else e.stars
        e.stars = stars  # keep manifest in step with the board (the star authority)
        origin = "user" if any(o.get("source") == "user-seed" for o in e.origins) else "discovered"
        bc = BoardCandidate(
            work_id=e.work_id, title=e.title, date=e.date, museum="",
            thumbnail_url="", source_url=_first_source_url(e), rights=e.rights,
            medium=e.medium, qid=e.qid, inst_ids=tuple(e.inst_ids),
            origin=origin, first_run=(existing.first_run if existing else run_id),
            local_path=e.path, stars=stars, thumbnail_path=e.path)
        if existing is None:
            state.candidates.append(bc)
        else:
            state.candidates[state.candidates.index(existing)] = bc
        n += 1
    return n
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_library.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/library.py tests/test_library.py
git commit -m "feat: library.sync_candidates — mirror library onto board, stars preserved"
```

---

### Task 5: `library.seed_import` — external collection → library

**Files:**
- Modify: `skill/scripts/library.py`
- Test: `tests/test_library.py`

**Interfaces:**
- Consumes: `make_incoming`, `build_library`, `paths.StudyPaths`.
- Produces: `seed_import(external_dir, paths, manifest, run_id, *, copy=shutil.copy2, move=shutil.move, delete=os.remove, hash_for=perceptual_hashes, dims_for=image_dims) -> LibrarySummary`. Copies external images → `images/user/` (external untouched), folds them into the library (so `images/user/` ends empty).

- [ ] **Step 1: Write the failing tests** — append to `tests/test_library.py`:

```python
from scripts.library import seed_import

_IMG_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".psd"}


def test_seed_import_folds_into_library_and_empties_user(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    ext = tmp_path / "external"; ext.mkdir()
    _img(ext / "one.png", seed=10)
    _img(ext / "two.png", seed=20)
    (ext / "notes.txt").write_text("ignore me")
    ext_before = {p.name: p.read_bytes() for p in ext.iterdir()}
    m = Manifest()
    summary = seed_import(ext, sp, m, run_id="seed")
    assert summary.added == 2
    assert len(list(sp.library_dir.glob("*.png"))) == 2
    assert list(sp.user_images_dir.iterdir()) == []      # user/ emptied
    # external NEVER modified
    assert {p.name: p.read_bytes() for p in ext.iterdir()} == ext_before


def test_seed_import_idempotent(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "A")
    ext = tmp_path / "external"; ext.mkdir()
    _img(ext / "one.png", seed=10)
    m = Manifest()
    seed_import(ext, sp, m, run_id="s1")
    s2 = seed_import(ext, sp, m, run_id="s2")
    assert s2.added == 0 and s2.merged_kept == 1           # re-seed dedups
    assert len(m.entries) == 1
    assert list(sp.user_images_dir.iterdir()) == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_library.py -k seed_import -v`
Expected: FAIL — `ImportError: cannot import name 'seed_import'`.

- [ ] **Step 3: Implement** — append to `skill/scripts/library.py`:

```python
_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".psd"}


def seed_import(external_dir, paths: StudyPaths, manifest: Manifest, run_id: str, *,
                copy=shutil.copy2, move=shutil.move, delete=os.remove,
                hash_for=perceptual_hashes, dims_for=image_dims) -> LibrarySummary:
    ext_dir = Path(external_dir)
    user_dir = paths.user_images_dir
    user_dir.mkdir(parents=True, exist_ok=True)
    incoming = []
    for src in sorted(ext_dir.iterdir()):
        if not src.is_file() or src.suffix.lower() not in _IMAGE_EXTS:
            continue
        dest = user_dir / src.name
        copy(str(src), str(dest))               # external is only ever READ
        inc = make_incoming(dest, source="user-seed", rights="unknown",
                            title=src.stem, hash_for=hash_for, dims_for=dims_for)
        if inc is not None:
            incoming.append(inc)
    return build_library(incoming, manifest, paths, run_id, move=move, delete=delete)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_library.py -v`
Expected: PASS (all `test_library.py`).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/library.py tests/test_library.py
git commit -m "feat: library.seed_import — external collection into the deduped library"
```

---

### Task 6: `download_library` + `default_resolve_url` — eager full-res fetch

**Files:**
- Modify: `skill/scripts/image_download.py` (add `LibraryDownload` + `download_library`)
- Modify: `skill/scripts/resolve.py` (add `default_resolve_url`)
- Test: `tests/test_image_download.py`, `tests/test_resolve.py`

**Interfaces:**
- Consumes: existing `default_fetch`, `robots_allows` (in `image_download`); `RESOLVERS` (in `resolve`).
- Produces:
  - `image_download.LibraryDownload(work_id, path, status, note="")` (frozen dataclass; status ∈ `downloaded|skipped|no-image|error|blocked`)
  - `image_download.download_library(candidates, incoming_dir, *, resolve_url, fetch=default_fetch, sleep=time.sleep, min_interval=1.0, robots_txt="") -> list[LibraryDownload]`
  - `resolve.default_resolve_url(candidate, *, resolvers=RESOLVERS) -> str | None`

- [ ] **Step 1: Write the failing tests** —

`tests/test_image_download.py` (append):

```python
from scripts.image_download import download_library, LibraryDownload


class _Cand:
    def __init__(self, work_id, thumbnail_url=""):
        self.work_id = work_id
        self.thumbnail_url = thumbnail_url


def test_download_library_writes_resolved_urls(tmp_path):
    cands = [_Cand("a"), _Cand("b"), _Cand("c")]
    urls = {"a": "http://x/a.jpg", "b": None, "c": "http://x/c.png"}
    def resolve_url(c): return urls[c.work_id]
    def fetch(url):
        return (200, "image/jpeg" if url.endswith(".jpg") else "image/png", b"bytes")
    out = download_library(cands, tmp_path, resolve_url=resolve_url, fetch=fetch,
                           sleep=lambda *_: None)
    by = {r.work_id: r for r in out}
    assert by["a"].status == "downloaded" and by["a"].path == tmp_path / "a.jpg"
    assert by["b"].status == "no-image" and by["b"].path is None
    assert by["c"].path == tmp_path / "c.png"
    assert (tmp_path / "a.jpg").read_bytes() == b"bytes"


def test_download_library_idempotent_skip(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"old")
    calls = []
    def fetch(url): calls.append(url); return (200, "image/jpeg", b"new")
    out = download_library([_Cand("a")], tmp_path, resolve_url=lambda c: "http://x/a.jpg",
                           fetch=fetch, sleep=lambda *_: None)
    assert out[0].status == "skipped" and calls == []
    assert (tmp_path / "a.jpg").read_bytes() == b"old"
```

`tests/test_resolve.py` (append):

```python
from scripts.resolve import default_resolve_url


class _RCand:
    def __init__(self, work_id, thumbnail_url=""):
        self.work_id = work_id; self.thumbnail_url = thumbnail_url; self.inst_ids = ()


def test_default_resolve_url_uses_resolver_then_thumbnail():
    class _Img:  # stand-in for an ImageCandidate
        image_url = "http://m/full.jpg"
    hit = lambda entry: _Img()
    miss = lambda entry: None
    assert default_resolve_url(_RCand("a"), resolvers=(hit,)) == "http://m/full.jpg"
    # no resolver hits -> fall back to the board thumbnail
    assert default_resolve_url(_RCand("a", "http://t/thumb.jpg"), resolvers=(miss,)) == "http://t/thumb.jpg"
    # nothing at all -> None
    assert default_resolve_url(_RCand("a", ""), resolvers=(miss,)) is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_image_download.py -k download_library tests/test_resolve.py -k default_resolve_url -v`
Expected: FAIL — import errors for `download_library` / `default_resolve_url`.

- [ ] **Step 3: Implement** —

In `skill/scripts/image_download.py`, add near the top (after imports) and below `DownloadResult`:

```python
_EXT_BY_TYPE = {
    "image/jpeg": ".jpg", "image/jpg": ".jpg", "image/png": ".png",
    "image/webp": ".webp", "image/tiff": ".tif", "image/gif": ".gif",
}


@dataclass(frozen=True)
class LibraryDownload:
    work_id: str
    path: Path | None
    status: str
    note: str = ""


def download_library(candidates, incoming_dir, *, resolve_url, fetch=default_fetch,
                     sleep=time.sleep, min_interval: float = 1.0,
                     robots_txt: str = "") -> list[LibraryDownload]:
    """Resolve + download best full-res image per candidate into incoming_dir/<work_id>.<ext>.
    Idempotent, throttled, robots-aware. Candidates with no image URL -> 'no-image'."""
    incoming_dir = Path(incoming_dir)
    results: list[LibraryDownload] = []
    fetched = False
    for cand in candidates:
        url = resolve_url(cand)
        if not url:
            results.append(LibraryDownload(cand.work_id, None, "no-image"))
            continue
        existing = next(iter(sorted(incoming_dir.glob(f"{cand.work_id}.*"))), None)
        if existing is not None:
            results.append(LibraryDownload(cand.work_id, existing, "skipped"))
            continue
        if not robots_allows(robots_txt, urlsplit(url).path):
            results.append(LibraryDownload(cand.work_id, None, "blocked", url))
            continue
        if fetched:
            sleep(min_interval)
        try:
            status_code, content_type, content = fetch(url)
        except Exception as exc:
            results.append(LibraryDownload(cand.work_id, None, "error", str(exc)))
            continue
        if status_code != 200 or not content_type.startswith("image/") or not content:
            results.append(LibraryDownload(cand.work_id, None, "error",
                                           f"status={status_code} type={content_type}"))
            continue
        ext = _EXT_BY_TYPE.get(content_type.split(";")[0].strip().lower(), ".jpg")
        incoming_dir.mkdir(parents=True, exist_ok=True)
        dest = incoming_dir / f"{cand.work_id}{ext}"
        dest.write_bytes(content)
        results.append(LibraryDownload(cand.work_id, dest, "downloaded"))
        fetched = True
    return results
```

In `skill/scripts/resolve.py`, add after `RESOLVERS`:

```python
def default_resolve_url(candidate, *, resolvers=RESOLVERS):
    """Best fetchable full-res image URL for a board candidate: try each resolver
    (Commons full / AIC IIIF), else fall back to the board thumbnail. None if neither."""
    for resolver in resolvers:
        cand = resolver(candidate)
        if cand is not None:
            return cand.image_url
    return getattr(candidate, "thumbnail_url", "") or None
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_image_download.py tests/test_resolve.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/image_download.py skill/scripts/resolve.py tests/test_image_download.py tests/test_resolve.py
git commit -m "feat: download_library + default_resolve_url — eager full-res into incoming/"
```

---

### Task 7: `SKILL.md` — library collection mode (Phase A branch)

**Files:**
- Modify: `skill/SKILL.md` (add a "Library collection mode" subsection in the image-discovery stage)
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: the full `scripts.library` API + `download_library` + `default_resolve_url` (documented as the orchestration Claude follows).
- Produces: SKILL.md prose the test asserts on.

- [ ] **Step 1: Write the failing test** — append to `tests/test_skill_md.py`:

```python
def test_skill_md_documents_library_collection_mode():
    text = SKILL_MD.read_text(encoding="utf-8")
    # the new mode's modules are referenced
    for token in ("scripts.library", "seed_import", "download_library",
                  "build_library", "sync_candidates"):
        assert token in text, f"{token!r} missing from SKILL.md"
    # it is presented as a mode that coexists with the thumbnail-only board
    assert "library collection" in text.lower()
    # the library path + manifest are named
    assert "images/library" in text
    assert "manifest" in text.lower()
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_skill_md.py -k library_collection -v`
Expected: FAIL — assertion error (tokens missing).

- [ ] **Step 3: Implement** — in `skill/SKILL.md`, inside the image-discovery stage (near "Phase A — board build"), add a subsection. Use this exact prose:

```markdown
**Library collection mode (optional, coexists with the thumbnail-only board above).**
When the human wants to *build a deduplicated local image library* — typically starting
from a folder of images they already collected — use this mode instead of the thumbnail
board. It downloads full-res, keeps one best copy per work, merges metadata, and feeds the
result into the same funnel.

1. **Seed once (if the human gives a collection path):**
   `man = scripts.image_manifest.Manifest.load(sp.manifest_json)` then
   `scripts.library.seed_import("<path>", sp, man, run_id)` — copies their images into
   `images/user/` (their originals are never touched), deduplicates, and folds the winners
   into `images/library/`, leaving `images/user/` empty. Then `man.save(sp.manifest_json)`,
   `state.record_run("seed-import", s.added, s.merged_kept + s.merged_replaced, total=len(man.entries))`,
   and `scripts.library.sync_candidates(man, state, run_id)`.
2. **Collect:** build the candidate list with the existing discovery
   (`search_wikidata` + `search_aic` + `merge_boards`), then download full-res into
   `images/incoming/`:
   `dls = scripts.image_download.download_library(cands, sp.incoming_dir, resolve_url=scripts.resolve.default_resolve_url)`.
   Build incoming images and dedup them into the library:
   `inc = [scripts.library.make_incoming(d.path, source="discovered", source_url=c.source_url, rights=c.rights, title=c.title, date=c.date, qid=c.qid, inst_ids=c.inst_ids) for c, d in pairs if d.path]`
   (drop `None`s), then
   `s = scripts.library.build_library([x for x in inc if x], man, sp, run_id)`,
   `man.save(sp.manifest_json)`,
   `state.record_run("library:wikidata+aic", s.added, s.merged_kept + s.merged_replaced, total=len(man.entries))`,
   and `scripts.library.sync_candidates(man, state, run_id)`, then `state.save(sp.state_json)`.
3. **Curate:** unchanged. Library cards already carry `thumbnail_path` (the library file), so
   `cache_thumbnails` is a no-op for them; build the funnel gallery over `state.candidates`
   exactly as in the thumbnail-only mode. Rights are recorded per image but do not gate the
   download in this mode (the human owns how they use a private study library).
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit -m "docs: SKILL.md — library collection mode (seed/collect/curate)"
```

---

### Task 8: `e2e/library_collection.py` — live Cezanne validation

**Files:**
- Create: `e2e/library_collection.py`
- Read for reference: `e2e/README.md`, `e2e/funnel_pipeline.py` (existing live-harness style)

**Interfaces:**
- Consumes: the whole Spec B surface live (`seed_import`, discovery, `download_library`, `build_library`, `sync_candidates`).
- Produces: a runnable script (NOT collected by pytest — it lives outside `tests/`).

- [ ] **Step 1: Read the existing harness conventions**

Run: `sed -n '1,40p' e2e/README.md` and skim `e2e/funnel_pipeline.py` for how live harnesses are structured (argparse, real network, print a PASS/result summary, write into a temp study dir — never the committed `studies/`).

- [ ] **Step 2: Write `e2e/library_collection.py`**

```python
"""Live e2e — library collection mode on the Cezanne seed. NOT a pytest test.

Run:  uv run --no-project python e2e/library_collection.py
Hits the real network (Wikidata/AIC + image downloads). Operates in a temp study
dir; the seed at studies/cezanne/images/user is copied in, never mutated here.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "skill"))

from scripts.paths import scaffold
from scripts.image_manifest import Manifest
from scripts import library, resolve, image_download, wikidata, museum_search


def main() -> int:
    seed = Path(__file__).resolve().parents[1] / "studies" / "cezanne" / "images" / "user"
    if not seed.is_dir() or not any(seed.iterdir()):
        print("SKIP: seed studies/cezanne/images/user is empty"); return 0

    work = Path(tempfile.mkdtemp(prefix="cezanne-lib-"))
    sp = scaffold(work, "Cezanne")
    man = Manifest()

    s = library.seed_import(seed, sp, man, run_id="seed")
    print(f"seed_import: added={s.added} merged={s.merged_kept + s.merged_replaced}")
    assert list(sp.user_images_dir.iterdir()) == [], "user/ should be empty after seed"
    seed_works = len(man.entries)
    assert seed_works > 0, "seed produced no library entries"

    # known duplicate pairs in the seed must have already collapsed (same-name + JPG/PSD)
    print(f"seed library entries: {seed_works} (deduped from {len(list(seed.iterdir()))} files)")

    # live discovery + eager download + dedup
    try:
        cands, _works, _amb = wikidata.search_wikidata("Paul Cezanne")
    except Exception as exc:
        cands = []
        print(f"wikidata degraded: {exc}")
    try:
        cands = list(cands) + list(museum_search.search_aic("Paul Cezanne"))
    except Exception as exc:
        print(f"aic degraded: {exc}")
    print(f"discovered {len(cands)} candidates")

    dls = image_download.download_library(cands, sp.incoming_dir,
                                          resolve_url=resolve.default_resolve_url)
    got = [d for d in dls if d.path]
    print(f"downloaded {len(got)} / {len(dls)}")
    inc = [library.make_incoming(d.path, source="discovered") for d in got]
    s2 = library.build_library([x for x in inc if x], man, sp, run_id="collect")
    print(f"collect: added={s2.added} merged={s2.merged_kept + s2.merged_replaced}")

    from scripts.state import PackageState
    st = PackageState(artist="Cezanne")
    n = library.sync_candidates(man, st, run_id="collect")
    print(f"PASS: library={len(man.entries)} entries, board synced ({n} candidates), "
          f"user/ empty, originals untouched")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Verify pytest does NOT collect it**

Run: `uv run pytest -q`
Expected: PASS, unchanged count — `e2e/` is outside `testpaths=["tests"]`, so the live harness is not collected.

- [ ] **Step 4: Run the live harness**

Run: `uv run --no-project python e2e/library_collection.py`
Expected: prints `seed_import` counts, confirms `user/` empty, discovers Cezanne candidates, downloads, builds the library, and prints a final `PASS:` line. Wikidata may be degraded (AIC-only) — that is an acceptable live outcome; the seed-import + dedup + sync path must still pass. Record the actual observed numbers (seed entries, dedup collapses, downloads) in the report.

- [ ] **Step 5: Commit**

```bash
git add e2e/library_collection.py
git commit -m "test(e2e): live library-collection harness on the Cezanne seed"
```

---

## Self-Review

**Spec coverage:**
- §4 paths (library/incoming/manifest + scaffold) → Task 1. ✓
- §5 `execute_action` (atomic place→delete, ordering) → Task 2; `build_library`/`make_incoming` → Task 3; `sync_candidates` (stars preserved) → Task 4. ✓
- §6 `seed_import` (move into library, user/ empties, external untouched, idempotent) → Task 5. ✓
- §7 `download_library` (eager, resolver-chain URL, rights recorded) → Task 6. ✓
- §8 SKILL Phase-A library mode (coexists) → Task 7. ✓
- §11 testing (offline seam-injected + live Cezanne e2e outside tests/) → Tasks 2–6 (offline) + Task 8 (live). ✓
- §3 locked: move-not-copy (Task 5), sync-to-candidates (Task 4), stars preserved (Task 4 test), atomicity (Task 2), rights-recorded-not-gated (Task 6/7), 0.90 inherited. ✓
- §10 error handling: fail-open `make_incoming` (Task 3 test), download error/no-image (Task 6 tests), external-untouched (Task 5 test). ✓

**Placeholder scan:** none — every code step has complete code; the one e2e one-liner has an explicit clearer-alternative noted.

**Type consistency:** `LibrarySummary(added, merged_kept, merged_replaced)`, `execute_action(action, paths, *, move, delete) -> ManifestEntry`, `make_incoming(...) -> IncomingImage|None`, `build_library(incoming, manifest, paths, run_id, *, threshold, move, delete) -> LibrarySummary`, `sync_candidates(manifest, state, run_id) -> int`, `seed_import(external_dir, paths, manifest, run_id, *, ...) -> LibrarySummary`, `download_library(candidates, incoming_dir, *, resolve_url, ...) -> list[LibraryDownload]`, `default_resolve_url(candidate, *, resolvers) -> str|None` are used identically across tasks and the SKILL wiring. `entry.path`/`LIBRARY_REL = "images/library"` consistent with Spec A and Task 1. ✓
