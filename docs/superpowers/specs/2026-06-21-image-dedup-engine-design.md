# Perceptual Image Dedup Engine + Manifest — Design Spec

> **Spec A** of the duplicate-handling-on-re-query feature (deferred out of raw/19
> Thrust 3; see `TODO.md`). Spec B (library collection mode + SKILL wiring — eager
> full-res download, seed import, cross-run dedup, e2e on the Cezanne seed) consumes this
> engine and is specced separately.

**Date:** 2026-06-21
**Source / research:** `raw/22.1-image-duplicate-detection.md` (NotebookLM, 64 sources);
wired into `wiki/stage-image-discovery.md`.
**Builds on:** Thrust 1 stateful `state.json` (`BoardCandidate.dedup_key()`), Thrust 2
custom-image injection (`origin:"user"`, `local_path`).

---

## 1. Goal

A reusable, **offline, pixel-content** duplicate-detection core that the collection
pipeline (Spec B) calls to decide whether a newly-found image is the *same artwork* as one
already in the library — and, when it is, which copy to keep and how to merge their
metadata. Three pure modules with injectable file-op seams, no network, no pipeline change.

One sentence: *given two image files, return a 0–1 "same full image" score; given a new
image and a manifest of what we already have, return the keep/delete/merge decision and the
updated manifest entry.*

## 2. Why now

The built dedup key (`dedup_key()` = QID → `inst_ids` → `work_id`) only catches images that
already share an identifier. It cannot catch the same painting arriving from two sources
with no shared id, or a user's pre-collected image (no metadata, wrong filename) matching a
discovered one. As the library grows across collection runs (e.g. an AIC-only run during a
Wikidata outage, then a later Commons run) the same works recur and must collapse to one
best copy. Perceptual hashing is the missing signal; this spec is the engine, isolated from
the pipeline so it can be fully unit-tested before Spec B wires it in.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Scope | **Spec A only**: similarity scoring + manifest + the keep/merge decision. No download, no SKILL wiring, no file orchestration (that is Spec B). |
| Library / approach | `imagehash` **pHash + wHash**, pure-Python. No CLIP/CNN (over-collapses crops, heavy deps); no SSIM (geometric-sensitive, no hashable index). |
| What counts as duplicate | **Only the same full image** — re-encode / resize / color-cast / watermark of the *same framing*. Crops, detail views, and alternate photographs stay separate (they score low under pHash). |
| Score → decision | Normalize each hash to `1 − Hamming/bits`; combined `score = min(phash_sim, whash_sim)` (conservative — one signal alone can't force a merge). |
| Threshold | `DUP_THRESHOLD = 0.90`, a single tunable module constant. |
| "Better" copy | **Largest pixel area** (`width × height`); tie-break larger byte size; full tie → **existing entry wins** (deterministic, no churn). |
| Metadata merge | Field-by-field, **non-empty + identifier-authoritative wins**; a QID-bearing value supersedes an empty/guessed one. Existing card keeps identity; **never lose stars** (stars carried by the existing entry are preserved). |
| Failure mode | **Fail-open**: any unreadable / un-hashable image yields `None` and is *never* flagged a duplicate (a missed dedup beats a false merge + a wrong delete). |
| Manifest role | `manifest.json` is both the provenance record **and** the dedup index (stored hashes → future runs compare against it, no re-hashing the whole library). |
| Determinism | No `Date.now()`/random in the engine. Canonical filename derives from title/qid/stem; run ids and timestamps are passed in by the caller (Spec B). |

## 4. Module: `scripts/image_similarity.py`

Pure pixel functions over file paths. Depends on `imagehash` (+ Pillow, numpy, scipy,
PyWavelets — new deps, added via uv).

```python
DUP_THRESHOLD = 0.90
HASH_BITS = 64  # 8x8 hash

@dataclass(frozen=True)
class ImageHashes:
    phash: str   # hex
    whash: str   # hex

def perceptual_hashes(path) -> ImageHashes | None:
    """Load, downscale-safe (draft/thumbnail before hashing so 60MB PSD/72MB JPG are cheap),
    return pHash+wHash as hex. Unreadable / unsupported / oversized-error -> None."""

def image_dims(path) -> tuple[int, int, int] | None:
    """(width, height, bytes). Unreadable -> None. Bytes from os.stat (no full decode needed)."""

def hamming_sim(hex_a: str, hex_b: str) -> float:
    """1 - (hamming_distance / HASH_BITS), clamped to [0,1]."""

def score(a: ImageHashes, b: ImageHashes) -> float:
    """Conservative combined similarity: min(hamming_sim(phash), hamming_sim(whash))."""

def is_duplicate(s: float, threshold: float = DUP_THRESHOLD) -> bool:
    return s >= threshold
```

Notes:
- PSD support via Pillow's `PsdImagePlugin` (composite layer); `.webp` natively. Convert to
  `L`/`RGB` before hashing for stable results across modes.
- Large files: call `Image.draft()` / `thumbnail()` to a small box before hashing — pHash
  downsamples to 8×8 anyway, so this only saves load cost, never changes the hash meaning.
- Hashes are stored/compared as **hex strings** (manifest-serializable); a tiny helper
  rebuilds `imagehash.ImageHash` from hex for the Hamming distance.

## 5. Module: `scripts/image_manifest.py`

The library index + dedup acceleration structure. One JSON document at
`images/manifest.json` (path owned by `paths.py` in Spec B; this module takes a path).

```python
@dataclass
class ManifestEntry:
    work_id: str
    title: str = ""
    date: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    filename: str = ""          # canonical name in images/library/
    path: str = ""              # repo-relative, e.g. "images/library/the-vase-of-tulips.jpg"
    width: int = 0
    height: int = 0
    bytes: int = 0
    phash: str = ""
    whash: str = ""
    rights: str = ""
    medium: str = ""
    stars: int = 0              # carried from the matched BoardCandidate; preserved on merge
    origins: list[dict] = field(default_factory=list)
    # each origin: {source, source_url, run_id, rights, width, height, bytes, won: bool}

class Manifest:
    entries: list[ManifestEntry]
    @classmethod
    def load(cls, path) -> "Manifest": ...      # missing file -> empty manifest
    def save(self, path) -> None: ...           # stable key order, 2-space indent
    def find_match(self, h: ImageHashes, threshold=DUP_THRESHOLD) -> ManifestEntry | None:
        """Best entry whose stored (phash,whash) scores >= threshold vs h; None if none.
        Linear scan now (libraries are hundreds, not millions); pHash-prefix bucketing is a
        noted future optimization, out of scope."""
    def upsert(self, entry: ManifestEntry) -> None:  # replace by work_id, else append
```

- `find_match` skips entries with empty/`""` hashes (e.g. a prior fail-open image) — they
  never match, consistent with fail-open.
- Round-trip is loss-less; `from_dict` tolerates older/partial entries (defaults fill).

## 6. Module: `scripts/dedup.py`

The decision engine. **Pure logic, injectable seams** — takes already-computed hashes/dims
and returns *intended actions*; performs **no** file I/O itself (Spec B executes the plan).

```python
@dataclass(frozen=True)
class IncomingImage:
    # everything Spec B knows about a freshly downloaded / seeded image
    tmp_path: str               # where it currently sits (images/incoming/ or images/user/)
    hashes: ImageHashes
    width: int; height: int; bytes: int
    title: str = ""; date: str = ""; qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    source: str = ""            # "user-seed" | "wikidata" | "aic" | "commons" | ...
    source_url: str = ""; rights: str = ""; medium: str = ""

@dataclass(frozen=True)
class DedupAction:
    kind: str                   # "add" (new work) | "merge" (dup found)
    keep_path: str              # winning file's current path
    delete_path: str | None     # losing file to remove (None on "add")
    canonical_name: str         # desired filename in images/library/
    entry: ManifestEntry        # the upserted manifest entry (post-merge)

def canonical_name(title, qid, fallback_stem, ext, taken: set[str]) -> str:
    """slugify(title) or qid or stem, + ext; de-collide with -2, -3 ..."""

def resolve(inc: IncomingImage, manifest: Manifest, run_id: str,
            *, threshold=DUP_THRESHOLD) -> DedupAction:
    """1. match = manifest.find_match(inc.hashes, threshold).
       2. No match -> kind='add': new ManifestEntry from inc, one origin (won=True).
       3. Match -> kind='merge':
          - winner by (width*height, bytes); existing entry's stored dims vs inc's.
          - keep_path / delete_path point to winner / loser.
          - canonical_name: **reuse the existing entry's filename** (no churn) when it is
            already title-derived; only re-derive when the existing name was a fallback
            (stem/qid based) and `inc` supplies a real title. `taken` set =
            `{e.filename for e in manifest.entries}` minus the entry being replaced.
          - merged entry: identity/metadata field-by-field (non-empty + qid-authoritative),
            dims/bytes/hashes from the winner, **stars preserved**, origins += inc origin
            (won flag reflects who won), winner origin won=True.
    """
```

Determinism: `resolve` never touches the clock or RNG; `run_id` is passed in. `find_match`
returns the first best match deterministically (stable scan order).

## 7. How identifier-dedup and perceptual-dedup compose (for Spec B)

Spec B's per-image flow (documented here so the engine's contract is unambiguous):

1. **Identifier path first (cheap):** existing `state.merge_candidates` / `dedup_key`
   handles QID / inst-id / work-id matches as today.
2. **Perceptual fallback:** for an image with *no* identifier match, Spec B computes
   `perceptual_hashes` + `image_dims`, builds an `IncomingImage`, and calls
   `dedup.resolve` against the `Manifest`.
3. Spec B **executes** the returned `DedupAction` (move winner into `images/library/` under
   `canonical_name`, delete the loser, `manifest.upsert(entry)`, save). The engine only
   *decides*; it never writes.

This spec delivers steps' decision logic only; the file moves and download live in Spec B.

## 8. Dependencies

Add via uv: `imagehash` (pulls `Pillow`, `numpy`, `scipy`, `PyWavelets`). New footprint —
Pillow is **not** currently a dependency and no script decodes pixels today — but pure-Python
wheels, far lighter than the CLIP/TensorFlow alternative. Recorded as a deliberate addition.

## 9. Rights posture (engine-level)

The engine is rights-agnostic: it scores and decides on whatever files it is given. The
**ungated full-res download** decision lives in Spec B (user-authorized deviation for
private study use); this engine only **records** `rights` on entries/origins for
transparency. No enforcement here.

## 10. Testing (offline `pytest`, TDD — write the failing test first)

`tests/test_image_similarity.py` (PIL-generated fixtures, no network):
- identical image → `score == 1.0`, `is_duplicate` True.
- re-encoded (JPEG quality drop), resized (½), and color-cast variants of one fixture →
  `score >= DUP_THRESHOLD`.
- a center **crop** and a **different** image → `score < DUP_THRESHOLD` (the "keep crops
  separate" invariant).
- unreadable / zero-byte / non-image path → `perceptual_hashes` and `image_dims` return
  `None`.
- `hamming_sim` clamps and is symmetric; hex round-trips.

`tests/test_image_manifest.py`:
- `load` of a missing file → empty; `save`→`load` round-trips an entry loss-lessly.
- `find_match` returns the matching entry above threshold, `None` below, and **skips
  empty-hash entries**.
- `upsert` replaces by `work_id`, else appends.

`tests/test_dedup.py` (injected hashes/dims — no real images needed):
- no match → `kind=="add"`, single origin `won=True`, new entry.
- match, incoming larger dims → `kind=="merge"`, `keep_path==incoming`, `delete_path==
  existing file`, dims/hashes from incoming, **stars preserved**, two origins.
- match, existing larger → winner is existing, `delete_path==incoming`, metadata still
  merged (incoming's non-empty title/qid fills gaps).
- tie on dims → larger bytes wins; full tie → existing wins (deterministic).
- `canonical_name` de-collides (`-2`, `-3`) and is Obsidian-safe (kebab-case, no
  `:/#^|[]`).

All tests offline; one `test_<module>.py` per `skill/scripts/` module per project convention.

## 11. Out of scope (→ Spec B)

Eager full-res download, seed-import copy step, `images/library/` + `images/incoming/`
creation, executing the `DedupAction` (file moves/deletes), Phase-A SKILL.md wiring,
cross-run orchestration, and the Cezanne e2e validation. Also out: pHash-bucketing
optimization, watermark detection, and the discovery-board (remote-thumbnail) dedup path.
