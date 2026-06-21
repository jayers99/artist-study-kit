# Perceptual Image Dedup Engine + Manifest (Spec A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the pure, offline perceptual image-dedup engine — three `skill/scripts/` modules that score image similarity, index a library manifest, and decide keep/merge/add — with no network, no file orchestration, and no SKILL wiring (Spec B consumes this).

**Architecture:** `image_similarity.py` turns image files into pHash+wHash hex and a 0–1 score. `image_manifest.py` is the `manifest.json` model + a hash-based `find_match`. `dedup.py` is the pure decision function `resolve()` that, given a freshly-seen image and the manifest, returns an action plan (add vs merge, which file wins, the merged manifest entry) without touching the filesystem. Identifier-dedup (`state.dedup_key`) is unchanged and runs first in Spec B; this is the perceptual fallback.

**Tech Stack:** Python 3, `imagehash` (+ Pillow, numpy, scipy, PyWavelets), `pytest` (offline), uv. Tests import via `from scripts.<module> import ...` (pytest `pythonpath=["skill"]`).

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-21-image-dedup-engine-design.md`. Engine only — §11 out-of-scope (download, file moves/deletes, SKILL wiring) is Spec B.
- **Module similarity constant:** `DUP_THRESHOLD = 0.90`. Hash size 8×8 → `HASH_BITS = 64`.
- **Score:** conservative `score = min(hamming_sim(phash), hamming_sim(whash))`, each `1 − Hamming/HASH_BITS`, clamped `[0,1]`.
- **Fail-open:** any unreadable / un-hashable image → `None`; `None`/empty-hash entries are never matched.
- **"Better" copy:** largest pixel area (`width*height`), tie-break larger `bytes`, full tie → **existing wins** (deterministic).
- **Metadata merge:** field-by-field, non-empty wins, **existing entry authoritative for identity**; stars on the existing entry are **always preserved**.
- **Determinism:** no clock / RNG in engine code; `run_id` is passed in by the caller.
- **Library path convention:** canonical files live at `images/library/<canonical_name>` (constant `LIBRARY_REL = "images/library"`). Filenames are kebab-case, Obsidian-safe (reuse `scripts.paths.slugify`).
- **Venv:** out-of-iCloud at `~/.venvs/artist-study-kit` (`.venv` symlink). Run tests with `uv run pytest` (or `uv run --no-project pytest`). Add deps with `uv add`.
- **Test convention:** one `tests/test_<module>.py` per `skill/scripts/` module; fully offline; PIL-generated fixtures under `tmp_path`.

---

### Task 1: Add the `imagehash` dependency

**Files:**
- Modify: `pyproject.toml` (dependencies)
- Test: `tests/test_image_similarity.py` (smoke import only, expanded in Task 2)

**Interfaces:**
- Consumes: nothing.
- Produces: `imagehash` + `PIL` importable in the test venv.

- [ ] **Step 1: Write the failing smoke test**

```python
# tests/test_image_similarity.py
def test_deps_importable():
    import imagehash  # noqa: F401
    from PIL import Image  # noqa: F401
    assert hasattr(imagehash, "phash")
```

- [ ] **Step 2: Run it to verify it fails**

Run: `uv run pytest tests/test_image_similarity.py::test_deps_importable -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'imagehash'` (and PIL).

- [ ] **Step 3: Add the dependency**

Run: `uv add imagehash`
This pulls `imagehash`, `Pillow`, `numpy`, `scipy`, `PyWavelets` into `pyproject.toml` and the venv.

- [ ] **Step 4: Run it to verify it passes**

Run: `uv run pytest tests/test_image_similarity.py::test_deps_importable -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml uv.lock tests/test_image_similarity.py
git commit -m "build: add imagehash (+ Pillow) for perceptual dedup engine"
```

---

### Task 2: `image_similarity.py` — hashes, dims, scoring

**Files:**
- Create: `skill/scripts/image_similarity.py`
- Test: `tests/test_image_similarity.py`

**Interfaces:**
- Consumes: `imagehash`, `PIL.Image`.
- Produces:
  - `DUP_THRESHOLD = 0.90`, `HASH_SIZE = 8`, `HASH_BITS = 64`
  - `ImageHashes` (frozen dataclass: `phash: str`, `whash: str`)
  - `perceptual_hashes(path) -> ImageHashes | None`
  - `image_dims(path) -> tuple[int, int, int] | None`  # (width, height, bytes)
  - `hamming_sim(hex_a: str, hex_b: str) -> float`
  - `score(a: ImageHashes, b: ImageHashes) -> float`
  - `is_duplicate(s: float, threshold: float = DUP_THRESHOLD) -> bool`

- [ ] **Step 1: Add a deterministic fixture helper + identity/score tests**

Append to `tests/test_image_similarity.py`:

```python
from pathlib import Path
from PIL import Image, ImageDraw
from scripts.image_similarity import (
    DUP_THRESHOLD, ImageHashes, perceptual_hashes, image_dims,
    hamming_sim, score, is_duplicate,
)


def _make_img(path, seed=0, size=(256, 256)):
    """Deterministic 4x4 colored-block pattern; distinct seeds -> distinct images."""
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    cw, ch = size[0] // 4, size[1] // 4
    for i in range(4):
        for j in range(4):
            v = (seed * 37 + (i * 4 + j) * 53) % 256
            d.rectangle([i * cw, j * ch, (i + 1) * cw, (j + 1) * ch],
                        fill=(v, (v * 2) % 256, (v * 3) % 256))
    img.save(path)
    return path


def test_identical_image_scores_one(tmp_path):
    p = _make_img(tmp_path / "a.png", seed=1)
    h = perceptual_hashes(p)
    assert h is not None
    assert score(h, h) == 1.0
    assert is_duplicate(score(h, h))


def test_reencode_and_resize_are_duplicates(tmp_path):
    base = _make_img(tmp_path / "base.png", seed=2)
    img = Image.open(base).convert("RGB")
    img.save(tmp_path / "q30.jpg", quality=30)        # lossy re-encode
    img.resize((128, 128)).save(tmp_path / "half.png")  # downscale
    h0 = perceptual_hashes(base)
    assert score(h0, perceptual_hashes(tmp_path / "q30.jpg")) >= DUP_THRESHOLD
    assert score(h0, perceptual_hashes(tmp_path / "half.png")) >= DUP_THRESHOLD


def test_color_cast_is_duplicate(tmp_path):
    base = _make_img(tmp_path / "base.png", seed=3)
    img = Image.open(base).convert("RGB")
    shifted = img.point(lambda v: min(255, v + 30))   # uniform brightness shift
    shifted.save(tmp_path / "bright.png")
    assert score(perceptual_hashes(base), perceptual_hashes(tmp_path / "bright.png")) >= DUP_THRESHOLD


def test_crop_and_different_are_not_duplicates(tmp_path):
    base = _make_img(tmp_path / "base.png", seed=4)
    Image.open(base).crop((48, 48, 208, 208)).save(tmp_path / "crop.png")  # center crop
    other = _make_img(tmp_path / "other.png", seed=99)
    h0 = perceptual_hashes(base)
    assert score(h0, perceptual_hashes(tmp_path / "crop.png")) < DUP_THRESHOLD
    assert score(h0, perceptual_hashes(other)) < DUP_THRESHOLD


def test_hamming_sim_clamps_and_is_symmetric(tmp_path):
    a = perceptual_hashes(_make_img(tmp_path / "a.png", seed=5))
    b = perceptual_hashes(_make_img(tmp_path / "b.png", seed=6))
    assert hamming_sim(a.phash, a.phash) == 1.0
    assert hamming_sim(a.phash, b.phash) == hamming_sim(b.phash, a.phash)
    assert 0.0 <= hamming_sim(a.phash, b.phash) <= 1.0


def test_unreadable_returns_none(tmp_path):
    bad = tmp_path / "not-an-image.png"
    bad.write_bytes(b"garbage")
    assert perceptual_hashes(bad) is None
    assert image_dims(bad) is None
    assert perceptual_hashes(tmp_path / "missing.png") is None


def test_image_dims(tmp_path):
    p = _make_img(tmp_path / "a.png", seed=7, size=(200, 120))
    w, h, b = image_dims(p)
    assert (w, h) == (200, 120)
    assert b > 0
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_image_similarity.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.image_similarity'`.

- [ ] **Step 3: Implement `image_similarity.py`**

```python
# skill/scripts/image_similarity.py
"""Spec A — pure, offline perceptual image similarity (pHash + wHash).

No network. Fail-open: any unreadable/un-hashable image yields None so the
caller never treats it as a duplicate. Hashes are hex strings (manifest-safe).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import imagehash
from PIL import Image

DUP_THRESHOLD = 0.90
HASH_SIZE = 8
HASH_BITS = HASH_SIZE * HASH_SIZE  # 64
_LOAD_BOX = (1024, 1024)  # bound intermediate decode cost; pHash downsamples anyway


@dataclass(frozen=True)
class ImageHashes:
    phash: str
    whash: str


def perceptual_hashes(path) -> "ImageHashes | None":
    try:
        with Image.open(path) as im:
            im.draft("RGB", _LOAD_BOX)        # cheap pre-scale for JPEG (no-op otherwise)
            rgb = im.convert("RGB")
            rgb.thumbnail(_LOAD_BOX)           # bound non-JPEG (PSD/PNG) memory
            ph = imagehash.phash(rgb, hash_size=HASH_SIZE)
            wh = imagehash.whash(rgb, hash_size=HASH_SIZE)
        return ImageHashes(phash=str(ph), whash=str(wh))
    except Exception:
        return None


def image_dims(path) -> "tuple[int, int, int] | None":
    try:
        size = os.path.getsize(path)
        with Image.open(path) as im:
            w, h = im.size                     # header read, no full decode
        return (int(w), int(h), int(size))
    except Exception:
        return None


def hamming_sim(hex_a: str, hex_b: str) -> float:
    d = imagehash.hex_to_hash(hex_a) - imagehash.hex_to_hash(hex_b)
    return max(0.0, min(1.0, 1.0 - d / HASH_BITS))


def score(a: ImageHashes, b: ImageHashes) -> float:
    return min(hamming_sim(a.phash, b.phash), hamming_sim(a.whash, b.whash))


def is_duplicate(s: float, threshold: float = DUP_THRESHOLD) -> bool:
    return s >= threshold
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_image_similarity.py -v`
Expected: PASS (all 8 tests).
If `test_crop_and_different_are_not_duplicates` or a `>=` test lands borderline, **adjust the fixture** (e.g. larger crop, more distinct seed) — never weaken `DUP_THRESHOLD`. The threshold is the contract.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/image_similarity.py tests/test_image_similarity.py
git commit -m "feat: image_similarity — pHash+wHash 0-1 scoring, fail-open"
```

---

### Task 3: `image_manifest.py` — library index + hash match

**Files:**
- Create: `skill/scripts/image_manifest.py`
- Test: `tests/test_image_manifest.py`

**Interfaces:**
- Consumes: `scripts.image_similarity.ImageHashes`, `score`, `DUP_THRESHOLD`.
- Produces:
  - `ManifestEntry` dataclass with fields: `work_id, title, date, qid, inst_ids, filename, path, width, height, bytes, phash, whash, rights, medium, stars, origins`; methods `hashes() -> ImageHashes | None`, `to_dict()`, `from_dict(d)`.
  - `Manifest` with `entries: list[ManifestEntry]`; classmethod `load(path) -> Manifest` (missing → empty); `save(path)`; `find_match(h: ImageHashes, threshold=DUP_THRESHOLD) -> ManifestEntry | None`; `upsert(entry)`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_image_manifest.py
from scripts.image_similarity import ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry


def _entry(work_id, phash, whash, **kw):
    return ManifestEntry(work_id=work_id, phash=phash, whash=whash, **kw)


def test_load_missing_is_empty(tmp_path):
    m = Manifest.load(tmp_path / "nope.json")
    assert m.entries == []


def test_save_load_roundtrip(tmp_path):
    e = _entry("the-vase", "f" * 16, "0" * 16, title="The Vase", qid="Q1",
               inst_ids=(("aic", "123"),), width=800, height=600, bytes=4242,
               filename="the-vase.jpg", path="images/library/the-vase.jpg",
               stars=3, origins=[{"source": "aic", "won": True}])
    p = tmp_path / "manifest.json"
    Manifest(entries=[e]).save(p)
    back = Manifest.load(p).entries[0]
    assert back.work_id == "the-vase"
    assert back.inst_ids == (("aic", "123"),)
    assert back.stars == 3
    assert back.origins == [{"source": "aic", "won": True}]
    assert back.hashes() == ImageHashes("f" * 16, "0" * 16)


def test_find_match_above_below_threshold(tmp_path):
    h = ImageHashes("f" * 16, "f" * 16)
    same = _entry("same", "f" * 16, "f" * 16)          # score 1.0
    far = _entry("far", "0" * 16, "0" * 16)            # score 0.0
    m = Manifest(entries=[far, same])
    assert m.find_match(h).work_id == "same"
    assert Manifest(entries=[far]).find_match(h) is None


def test_find_match_skips_empty_hash_entries():
    h = ImageHashes("f" * 16, "f" * 16)
    blank = _entry("blank", "", "")                    # fail-open image: never matches
    m = Manifest(entries=[blank])
    assert m.find_match(h) is None


def test_upsert_replaces_by_work_id_else_appends():
    m = Manifest(entries=[_entry("a", "f" * 16, "f" * 16, title="old")])
    m.upsert(_entry("a", "f" * 16, "f" * 16, title="new"))
    assert len(m.entries) == 1 and m.entries[0].title == "new"
    m.upsert(_entry("b", "0" * 16, "0" * 16))
    assert {e.work_id for e in m.entries} == {"a", "b"}
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_image_manifest.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.image_manifest'`.

- [ ] **Step 3: Implement `image_manifest.py`**

```python
# skill/scripts/image_manifest.py
"""Spec A — the library manifest: provenance record AND dedup index.

One JSON document (path supplied by caller). find_match() is the perceptual
lookup used by the dedup engine; entries store hex hashes so later runs match
without re-hashing the whole library.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from scripts.image_similarity import DUP_THRESHOLD, ImageHashes, score


@dataclass
class ManifestEntry:
    work_id: str
    title: str = ""
    date: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    filename: str = ""
    path: str = ""
    width: int = 0
    height: int = 0
    bytes: int = 0
    phash: str = ""
    whash: str = ""
    rights: str = ""
    medium: str = ""
    stars: int = 0
    origins: list = field(default_factory=list)

    def hashes(self) -> "ImageHashes | None":
        if self.phash and self.whash:
            return ImageHashes(self.phash, self.whash)
        return None

    def to_dict(self) -> dict:
        return {
            "work_id": self.work_id, "title": self.title, "date": self.date,
            "qid": self.qid, "inst_ids": [list(p) for p in self.inst_ids],
            "filename": self.filename, "path": self.path,
            "width": self.width, "height": self.height, "bytes": self.bytes,
            "phash": self.phash, "whash": self.whash, "rights": self.rights,
            "medium": self.medium, "stars": self.stars, "origins": self.origins,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ManifestEntry":
        return cls(
            work_id=d["work_id"], title=d.get("title", ""), date=d.get("date", ""),
            qid=d.get("qid", ""),
            inst_ids=tuple((str(a), str(b)) for a, b in d.get("inst_ids", ())),
            filename=d.get("filename", ""), path=d.get("path", ""),
            width=int(d.get("width", 0)), height=int(d.get("height", 0)),
            bytes=int(d.get("bytes", 0)), phash=d.get("phash", ""),
            whash=d.get("whash", ""), rights=d.get("rights", ""),
            medium=d.get("medium", ""), stars=int(d.get("stars", 0)),
            origins=list(d.get("origins", [])),
        )


@dataclass
class Manifest:
    entries: list = field(default_factory=list)

    @classmethod
    def load(cls, path) -> "Manifest":
        p = Path(path)
        if not p.exists():
            return cls(entries=[])
        data = json.loads(p.read_text())
        return cls(entries=[ManifestEntry.from_dict(d) for d in data.get("entries", [])])

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(
            {"entries": [e.to_dict() for e in self.entries]}, indent=2))

    def find_match(self, h: ImageHashes, threshold: float = DUP_THRESHOLD):
        best = None
        best_s = -1.0
        for e in self.entries:
            eh = e.hashes()
            if eh is None:
                continue
            s = score(h, eh)
            if s >= threshold and s > best_s:
                best_s = s
                best = e
        return best

    def upsert(self, entry: ManifestEntry) -> None:
        for i, e in enumerate(self.entries):
            if e.work_id == entry.work_id:
                self.entries[i] = entry
                return
        self.entries.append(entry)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_image_manifest.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/image_manifest.py tests/test_image_manifest.py
git commit -m "feat: image_manifest — library index + hash-based find_match"
```

---

### Task 4: `dedup.py` — the keep/merge/add decision

**Files:**
- Create: `skill/scripts/dedup.py`
- Test: `tests/test_dedup.py`

**Interfaces:**
- Consumes: `scripts.image_similarity.{ImageHashes, DUP_THRESHOLD}`, `scripts.image_manifest.{Manifest, ManifestEntry}`, `scripts.paths.slugify`.
- Produces:
  - `LIBRARY_REL = "images/library"`
  - `IncomingImage` (frozen dataclass — see code).
  - `DedupAction` (frozen dataclass: `kind, keep_path, delete_path, canonical_name, entry`).
  - `canonical_name(title, qid, fallback_stem, ext, taken) -> str`
  - `resolve(inc: IncomingImage, manifest: Manifest, run_id: str, *, threshold=DUP_THRESHOLD) -> DedupAction`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_dedup.py
from scripts.image_similarity import ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.dedup import IncomingImage, resolve, canonical_name


def _inc(tmp_path="/incoming/x.jpg", phash="f" * 16, whash="f" * 16,
         w=400, h=300, b=1000, **kw):
    return IncomingImage(tmp_path=tmp_path, hashes=ImageHashes(phash, whash),
                         width=w, height=h, bytes=b, **kw)


def _entry(work_id, phash="f" * 16, whash="f" * 16, **kw):
    return ManifestEntry(work_id=work_id, phash=phash, whash=whash, **kw)


def test_no_match_is_add(tmp_path):
    inc = _inc(title="The Vase of Tulips", source="aic", source_url="http://x",
               rights="public_domain")
    act = resolve(inc, Manifest(entries=[]), run_id="run1")
    assert act.kind == "add"
    assert act.delete_path is None
    assert act.keep_path == inc.tmp_path
    assert act.canonical_name == "the-vase-of-tulips.jpg"
    assert act.entry.title == "The Vase of Tulips"
    assert act.entry.width == 400 and act.entry.path == "images/library/the-vase-of-tulips.jpg"
    assert act.entry.origins == [{
        "source": "aic", "source_url": "http://x", "run_id": "run1",
        "rights": "public_domain", "width": 400, "height": 300, "bytes": 1000, "won": True}]


def test_incoming_larger_wins_and_preserves_stars(tmp_path):
    existing = _entry("madame-cezanne", title="Madame Cezanne", qid="Q42",
                      filename="madame-cezanne.jpg", path="images/library/madame-cezanne.jpg",
                      width=300, height=200, bytes=500, stars=5)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/big.jpg", w=2000, h=1500, b=900000,
               source="commons", source_url="http://c")
    act = resolve(inc, m, run_id="run2")
    assert act.kind == "merge"
    assert act.keep_path == "/incoming/big.jpg"
    assert act.delete_path == "images/library/madame-cezanne.jpg"
    assert act.entry.width == 2000 and act.entry.bytes == 900000
    assert act.entry.phash == inc.hashes.phash            # winner's hashes
    assert act.entry.qid == "Q42" and act.entry.title == "Madame Cezanne"  # identity kept
    assert act.entry.stars == 5                           # never lost
    assert act.entry.work_id == "madame-cezanne"          # stable
    assert [o["won"] for o in act.entry.origins][-1] is True
    assert act.canonical_name == "madame-cezanne.jpg"     # no churn (already title-derived)


def test_existing_larger_wins_but_metadata_merges(tmp_path):
    existing = _entry("stem-name", title="", qid="",                 # was a fallback name
                      filename="img001.jpg", path="images/library/img001.jpg",
                      width=2000, height=1500, bytes=900000, stars=2)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/small.jpg", w=300, h=200, b=500,
               title="Still Life with Apples", qid="Q7", source="wikidata")
    act = resolve(inc, m, run_id="run3")
    assert act.kind == "merge"
    assert act.keep_path == "images/library/img001.jpg"  # existing file wins
    assert act.delete_path == "/incoming/small.jpg"
    assert act.entry.width == 2000                        # winner dims kept
    assert act.entry.title == "Still Life with Apples"   # gap filled from incoming
    assert act.entry.qid == "Q7"
    assert act.entry.stars == 2
    assert act.canonical_name == "still-life-with-apples.jpg"  # re-derived (existing was fallback)


def test_dim_tie_breaks_on_bytes_then_existing(tmp_path):
    existing = _entry("e", title="E", filename="e.jpg", path="images/library/e.jpg",
                      width=400, height=300, bytes=1000, stars=0)
    m = Manifest(entries=[existing])
    # same dims, smaller bytes -> existing wins
    inc_small = _inc(w=400, h=300, b=900, title="E")
    assert resolve(inc_small, m, "r").keep_path == "images/library/e.jpg"
    # same dims, larger bytes -> incoming wins
    inc_big = _inc(tmp_path="/incoming/e2.jpg", w=400, h=300, b=2000, title="E")
    assert resolve(inc_big, m, "r").keep_path == "/incoming/e2.jpg"


def test_canonical_name_decollides_and_is_safe():
    taken = {"the-vase.jpg"}
    assert canonical_name("The Vase", "", "x", ".jpg", taken) == "the-vase-2.jpg"
    # no title -> qid -> stem fallback chain
    assert canonical_name("", "Q9", "x", ".jpg", set()) == "q9.jpg"
    assert canonical_name("", "", "DSC_001", ".png", set()) == "dsc_001.png"
```

- [ ] **Step 2: Run to verify it fails**

Run: `uv run pytest tests/test_dedup.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.dedup'`.

- [ ] **Step 3: Implement `dedup.py`**

```python
# skill/scripts/dedup.py
"""Spec A — pure keep/merge/add decision. NO filesystem I/O.

resolve() takes a freshly-seen image (hashes + dims + metadata already computed
by the caller) and the current Manifest, and returns a DedupAction the caller
(Spec B) executes: move winner into images/library/, delete the loser, upsert
the entry. Deterministic: run_id is injected; no clock/RNG here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.image_similarity import DUP_THRESHOLD, ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.paths import slugify

LIBRARY_REL = "images/library"


@dataclass(frozen=True)
class IncomingImage:
    tmp_path: str
    hashes: ImageHashes
    width: int
    height: int
    bytes: int
    title: str = ""
    date: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    source: str = ""
    source_url: str = ""
    rights: str = ""
    medium: str = ""


@dataclass(frozen=True)
class DedupAction:
    kind: str                 # "add" | "merge"
    keep_path: str
    delete_path: "str | None"
    canonical_name: str
    entry: ManifestEntry


def _slug_base(title: str, qid: str, fallback_stem: str) -> str:
    if title.strip():
        return slugify(title)
    if qid.strip():
        return slugify(qid)
    return slugify(fallback_stem)


def canonical_name(title: str, qid: str, fallback_stem: str, ext: str,
                   taken) -> str:
    base = _slug_base(title, qid, fallback_stem)
    name = f"{base}{ext}"
    if name not in taken:
        return name
    n = 2
    while f"{base}-{n}{ext}" in taken:
        n += 1
    return f"{base}-{n}{ext}"


def _origin(inc: IncomingImage, run_id: str, won: bool) -> dict:
    return {"source": inc.source, "source_url": inc.source_url, "run_id": run_id,
            "rights": inc.rights, "width": inc.width, "height": inc.height,
            "bytes": inc.bytes, "won": won}


def resolve(inc: IncomingImage, manifest: Manifest, run_id: str,
            *, threshold: float = DUP_THRESHOLD) -> DedupAction:
    ext = Path(inc.tmp_path).suffix
    match = manifest.find_match(inc.hashes, threshold)

    if match is None:
        taken = {e.filename for e in manifest.entries}
        cn = canonical_name(inc.title, inc.qid, Path(inc.tmp_path).stem, ext, taken)
        entry = ManifestEntry(
            work_id=_slug_base(inc.title, inc.qid, Path(inc.tmp_path).stem),
            title=inc.title, date=inc.date, qid=inc.qid, inst_ids=inc.inst_ids,
            filename=cn, path=f"{LIBRARY_REL}/{cn}", width=inc.width,
            height=inc.height, bytes=inc.bytes, phash=inc.hashes.phash,
            whash=inc.hashes.whash, rights=inc.rights, medium=inc.medium,
            stars=0, origins=[_origin(inc, run_id, won=True)])
        return DedupAction(kind="add", keep_path=inc.tmp_path, delete_path=None,
                           canonical_name=cn, entry=entry)

    inc_wins = (inc.width * inc.height, inc.bytes) > (match.width * match.height, match.bytes)

    # identity / metadata merge — existing authoritative, incoming fills gaps
    title = match.title or inc.title
    date = match.date or inc.date
    qid = match.qid or inc.qid
    inst_ids = match.inst_ids or inc.inst_ids
    rights = match.rights or inc.rights
    medium = match.medium or inc.medium

    # canonical name: reuse existing (no churn) when it was already title-derived;
    # re-derive when the existing name was a fallback and we now have a real title.
    taken = {e.filename for e in manifest.entries if e.work_id != match.work_id}
    if match.title.strip():
        cn = match.filename
    else:
        cn = canonical_name(title, qid, Path(match.filename or inc.tmp_path).stem, ext, taken)

    if inc_wins:
        keep_path, delete_path = inc.tmp_path, match.path
        w, h, b = inc.width, inc.height, inc.bytes
        ph, wh = inc.hashes.phash, inc.hashes.whash
    else:
        keep_path, delete_path = match.path, inc.tmp_path
        w, h, b = match.width, match.height, match.bytes
        ph, wh = match.phash, match.whash

    entry = ManifestEntry(
        work_id=match.work_id, title=title, date=date, qid=qid, inst_ids=inst_ids,
        filename=cn, path=f"{LIBRARY_REL}/{cn}", width=w, height=h, bytes=b,
        phash=ph, whash=wh, rights=rights, medium=medium, stars=match.stars,
        origins=list(match.origins) + [_origin(inc, run_id, won=inc_wins)])
    return DedupAction(kind="merge", keep_path=keep_path, delete_path=delete_path,
                       canonical_name=cn, entry=entry)
```

- [ ] **Step 4: Run to verify it passes**

Run: `uv run pytest tests/test_dedup.py -v`
Expected: PASS (all 5 tests).

- [ ] **Step 5: Run the whole suite (no regressions)**

Run: `uv run pytest -q`
Expected: PASS — the prior suite plus the new `image_similarity`/`image_manifest`/`dedup` tests.

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/dedup.py tests/test_dedup.py
git commit -m "feat: dedup — pure keep/merge/add decision (largest-dims, stars-safe)"
```

---

## Self-Review

**Spec coverage:**
- §4 image_similarity (hashes, dims, hamming, score, is_duplicate, fail-open, downscale) → Task 2. ✓
- §5 image_manifest (ManifestEntry incl. `stars`/`origins`, load/save, find_match skips empty, upsert) → Task 3. ✓
- §6 dedup (IncomingImage, DedupAction, canonical_name, resolve: add/merge, largest-dims+bytes tie→existing, metadata merge, stars preserved, no-churn rename) → Task 4. ✓
- §3 locked decisions (0.90, min-of-both, fail-open, library path) → Global Constraints + enforced in tests. ✓
- §8 dependency (imagehash) → Task 1. ✓
- §9 rights recorded not enforced → `rights` carried on entry/origin, never gated. ✓
- §11 out-of-scope (download, file moves, SKILL wiring) → not in any task. ✓

**Placeholder scan:** none — every step has runnable code/commands.

**Type consistency:** `ImageHashes(phash, whash)`, `score(a,b)`, `find_match(h, threshold)`, `ManifestEntry` field set, `IncomingImage`/`DedupAction` shapes, and `resolve(inc, manifest, run_id, *, threshold)` are used identically across Tasks 2→3→4 and the tests. `LIBRARY_REL = "images/library"` matches the `entry.path` assertions. ✓
