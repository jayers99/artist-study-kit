# Image Discovery — Post-Curation Resolution (Plan B) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the human-selected works from the curation board to the best legally-clear high-resolution image — Commons P18 (PD/CC0) → AIC IIIF 1686px (`is_public_domain`) → else keep the `source_url` (in-copyright, thumbnail only) — filling the gap where `apply_selection` only copies non-existent local candidate files.

**Architecture:** New module `scripts/resolve.py` holds a pluggable resolver chain (`RESOLVERS`); each resolver maps a selection entry to an `iiif.ImageCandidate` or `None`, and downloads reuse the existing `image_download.download_candidate` (rights+resolution validation, idempotent, injected byte-fetch). Selection records carry the board's `qid`/`inst_ids`/`source_url`/`museum`/`rights` so resolvers know where to fetch. The thumbnail board export and `selection.Rating` are extended to carry those fields end to end.

**Tech Stack:** Python 3, uv, pytest. Reuses `scripts/commons.py` (Commons MediaWiki API) and `scripts/museum_search.py` (AIC API). Spec: `docs/superpowers/specs/2026-06-20-image-discovery-wikidata-tier1.md`. **Depends on Plan A** (`ThumbnailCandidate.qid`/`inst_ids` must exist).

## Global Constraints

- Venv OUTSIDE iCloud at `~/.venvs/artist-study-kit`; run tests with `uv run pytest` (`.venv` symlink) or `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest`.
- pytest: `pythonpath = ["skill"]`, `testpaths = ["tests"]`; import as `from scripts.<name> import ...`.
- TDD, red-green, one behavior per test. **No live network in tests** — inject every network/IO call via a `fetch=`/`download=` parameter. Real network helpers (`commons.default_fileinfo`) carry the descriptive User-Agent and are NOT tested.
- Resolvers return a downloadable `ImageCandidate` ONLY when a PD/CC0 flag is verified; otherwise `None`. Copyright posture: high-res download only on verified PD/CC0; in-copyright works keep `source_url` and download no bytes.
- Dataclasses `@dataclass(frozen=True)`; collection fields are tuples.
- Commit per task; end commit bodies with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`. Full suite green before each task's final commit.

---

### Task B1: `selection.Rating` carries board provenance fields

**Files:**
- Modify: `skill/scripts/selection.py` (`Rating` ~line 20; `parse_selection` ~line 37)
- Test: `tests/test_selection.py`

**Interfaces:**
- Produces: `Rating(work_id, iiif_token, image_rel, rating, thesis="", anchor_trait="", handoff_note="", qid="", source_url="", museum="", rights="", inst_ids: tuple[tuple[str,str],...] = ())`. `parse_selection` reads the new keys; `inst_ids` arrives from JSON as a list of `[key, value]` pairs and is normalized to a tuple of tuples.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_selection.py`:

```python
def test_parse_selection_reads_board_provenance_fields():
    data = {
        "artist": "paul-klee",
        "ratings": [{
            "work_id": "fish-magic", "iiif_token": "phila-0",
            "image_rel": "https://commons.wikimedia.org/wiki/Special:FilePath/Fish.jpg?width=400",
            "rating": 5, "thesis": "t", "anchor_trait": "a", "handoff_note": "h",
            "qid": "Q3050231", "source_url": "https://www.wikidata.org/wiki/Q3050231",
            "museum": "Philadelphia Museum of Art", "rights": "unknown",
            "inst_ids": [["commons_file", "Fish.jpg"], ["aic", "16569"]],
        }],
    }
    r = parse_selection(data).ratings[0]
    assert r.qid == "Q3050231"
    assert r.museum == "Philadelphia Museum of Art"
    assert r.inst_ids == (("commons_file", "Fish.jpg"), ("aic", "16569"))


def test_parse_selection_defaults_missing_provenance():
    r = parse_selection(_data()).ratings[0]
    assert r.qid == "" and r.inst_ids == ()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_selection.py -k provenance -v`
Expected: FAIL — `TypeError`/`AttributeError` (`Rating` has no `qid`).

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/selection.py`, extend the dataclass:

```python
@dataclass(frozen=True)
class Rating:
    work_id: str
    iiif_token: str
    image_rel: str
    rating: int
    thesis: str = ""
    anchor_trait: str = ""
    handoff_note: str = ""
    qid: str = ""
    source_url: str = ""
    museum: str = ""
    rights: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
```

In `parse_selection`, add the new reads inside the `Rating(...)` call:

```python
            handoff_note=str(r.get("handoff_note", "")),
            qid=str(r.get("qid", "")),
            source_url=str(r.get("source_url", "")),
            museum=str(r.get("museum", "")),
            rights=str(r.get("rights", "")),
            inst_ids=tuple((str(p[0]), str(p[1])) for p in r.get("inst_ids", []) if len(p) == 2),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_selection.py -v`
Expected: PASS (existing + new; defaults keep old tests valid).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/selection.py tests/test_selection.py
git commit -m "feat: selection.Rating carries qid/source_url/museum/rights/inst_ids

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B2: Commons file-info fetch + `commons_resolver`

**Files:**
- Modify: `skill/scripts/commons.py` (add `build_fileinfo_params`, `default_fileinfo`)
- Create: `skill/scripts/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: `commons.parse_commons_search` (existing), `selection.Rating` (B1).
- Produces:
  - `commons.build_fileinfo_params(filename: str) -> dict`
  - `commons.default_fileinfo(filename: str) -> dict` (real httpx; untested)
  - `resolve.commons_resolver(entry, *, fetch=commons.default_fileinfo) -> ImageCandidate | None` — looks up `("commons_file", filename)` in `entry.inst_ids`, fetches Commons imageinfo, returns the first PD/CC0 candidate (via `parse_commons_search`, `want=1`) or `None`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_resolve.py`:

```python
from scripts.iiif import ImageCandidate
from scripts.resolve import commons_resolver
from scripts.selection import Rating


def _entry(**kw):
    base = dict(work_id="fish-magic", iiif_token="t", image_rel="r", rating=5,
                source_url="https://www.wikidata.org/wiki/Q1", inst_ids=())
    base.update(kw)
    return Rating(**base)


def _commons_payload(license_name):
    return {"query": {"pages": {"42": {
        "title": "File:Fish Magic.jpg",
        "imageinfo": [{
            "url": "https://upload.wikimedia.org/fish-magic.jpg",
            "width": 4000, "height": 3000, "mediatype": "BITMAP",
            "extmetadata": {"LicenseShortName": {"value": license_name}},
        }],
    }}}}


def test_commons_resolver_returns_pd_candidate():
    entry = _entry(inst_ids=(("commons_file", "Fish Magic.jpg"),))
    cand = commons_resolver(entry, fetch=lambda fn: _commons_payload("Public domain"))
    assert isinstance(cand, ImageCandidate)
    assert cand.image_url == "https://upload.wikimedia.org/fish-magic.jpg"
    assert cand.rights_status == "public_domain"


def test_commons_resolver_drops_non_pd():
    entry = _entry(inst_ids=(("commons_file", "Fish Magic.jpg"),))
    assert commons_resolver(entry, fetch=lambda fn: _commons_payload("CC BY-SA 4.0")) is None


def test_commons_resolver_none_without_commons_file():
    assert commons_resolver(_entry(inst_ids=(("aic", "5"),))) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -k commons -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.resolve'`.

- [ ] **Step 3: Write minimal implementation**

Append to `skill/scripts/commons.py`:

```python
def build_fileinfo_params(filename: str) -> dict:
    """MediaWiki params to fetch imageinfo for a known File: title."""
    return {
        "action": "query",
        "format": "json",
        "titles": f"File:{filename}",
        "prop": "imageinfo",
        "iiprop": "url|size|mediatype|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|UsageTerms",
    }


def default_fileinfo(filename: str) -> dict:
    """Real MediaWiki file-info fetch (httpx). Not exercised in tests."""
    import httpx

    user_agent = (
        "artist-study-kit/1.0 (studio-prep research; "
        "+https://github.com/jayers99/artist-study-kit)"
    )
    resp = httpx.get(COMMONS_API, params=build_fileinfo_params(filename),
                     headers={"User-Agent": user_agent}, timeout=40.0)
    resp.raise_for_status()
    return resp.json()
```

Create `skill/scripts/resolve.py`:

```python
"""Stage-5 post-curation: resolve SELECTED works to high-res, rights permitting.

The board (Wikidata-primary) is rights-agnostic; once the human selects works, each is
resolved to the best legally-clear image via a pluggable resolver chain:
  Commons P18 (PD/CC0) -> AIC IIIF 1686px (is_public_domain) -> else keep source_url.
Resolvers return an ImageCandidate ONLY on a verified PD/CC0 flag; downloads reuse
image_download.download_candidate. Network is injected so tests stay offline.
"""

from __future__ import annotations

from scripts import commons
from scripts.iiif import ImageCandidate


def _find(inst_ids, key: str) -> str:
    return next((v for k, v in inst_ids if k == key), "")


def commons_resolver(entry, *, fetch=None):
    """Resolve via the work's Commons file (PD/CC0 only)."""
    fetch = fetch or commons.default_fileinfo
    filename = _find(entry.inst_ids, "commons_file")
    if not filename:
        return None
    cands = commons.parse_commons_search(fetch(filename), work_id=entry.work_id, want=1)
    return cands[0] if cands else None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolve.py -k commons -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/commons.py skill/scripts/resolve.py tests/test_resolve.py
git commit -m "feat: commons file-info fetch + commons_resolver (PD/CC0 high-res)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B3: `aic_resolver`

**Files:**
- Modify: `skill/scripts/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: `museum_search.default_aic_fetch`, `museum_search.AIC_IIIF_DEFAULT`, `iiif.ImageCandidate`.
- Produces: `resolve.aic_resolver(entry, *, fetch=museum_search.default_aic_fetch) -> ImageCandidate | None` — looks up `("aic", id)`; fetches `artworks/{id}`; returns a 1686px IIIF candidate only when `is_public_domain` is true and an `image_id` exists.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_resolve.py`:

```python
from scripts.resolve import aic_resolver


def _aic_payload(is_pd):
    return {"data": {"id": 16569, "image_id": "abc-123", "is_public_domain": is_pd},
            "config": {"iiif_url": "https://www.artic.edu/iiif/2"}}


def test_aic_resolver_builds_1686_candidate_when_public_domain():
    entry = _entry(inst_ids=(("aic", "16569"),))
    cand = aic_resolver(entry, fetch=lambda path, params: _aic_payload(True))
    assert cand.image_url == "https://www.artic.edu/iiif/2/abc-123/full/1686,/0/default.jpg"
    assert cand.rights_status == "public_domain"
    assert max(cand.width, cand.height) >= 1500


def test_aic_resolver_none_when_in_copyright():
    entry = _entry(inst_ids=(("aic", "16569"),))
    assert aic_resolver(entry, fetch=lambda path, params: _aic_payload(False)) is None


def test_aic_resolver_none_without_aic_id():
    assert aic_resolver(_entry(inst_ids=(("commons_file", "x.jpg"),))) is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -k aic -v`
Expected: FAIL — `ImportError: cannot import name 'aic_resolver'`.

- [ ] **Step 3: Write minimal implementation**

Add the import at the top of `skill/scripts/resolve.py`:

```python
from scripts.museum_search import AIC_IIIF_DEFAULT, default_aic_fetch
```

Append:

```python
def aic_resolver(entry, *, fetch=None):
    """Resolve via the work's AIC record (IIIF 1686px, public-domain only)."""
    fetch = fetch or default_aic_fetch
    aic_id = _find(entry.inst_ids, "aic")
    if not aic_id:
        return None
    payload = fetch(f"artworks/{aic_id}", {"fields": "id,image_id,is_public_domain"})
    data = payload.get("data") or {}
    if not data.get("is_public_domain") or not data.get("image_id"):
        return None
    iiif = (payload.get("config") or {}).get("iiif_url") or AIC_IIIF_DEFAULT
    return ImageCandidate(
        work_id=entry.work_id,
        institution="aic",
        label=entry.work_id,
        iiif_id=f"aic/{aic_id}",
        image_url=f"{iiif}/{data['image_id']}/full/1686,/0/default.jpg",
        width=1686,
        height=1686,
        license="Public Domain",
        rights_status="public_domain",
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolve.py -k aic -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/resolve.py tests/test_resolve.py
git commit -m "feat: aic_resolver (IIIF 1686px on is_public_domain)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B4: `resolve_selected` — chain + download + in-copyright fallback

**Files:**
- Modify: `skill/scripts/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: `commons_resolver`, `aic_resolver` (B2/B3), `image_download.download_candidate`.
- Produces:
  - `@dataclass(frozen=True) Resolved(work_id: str, rights: str, image_path, image_url, source_url: str, license: str = "", institution: str = "")`
  - `RESOLVERS = (commons_resolver, aic_resolver)`
  - `resolve_selected(entry, selected_dir, *, resolvers=RESOLVERS, download=download_candidate) -> Resolved` — first resolver yielding a candidate whose download succeeds wins (`rights="public_domain"`); if none, returns `Resolved(rights="in_copyright", image_path=None, image_url=None, source_url=entry.source_url)` and downloads nothing.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_resolve.py`:

```python
from types import SimpleNamespace

from scripts.iiif import ImageCandidate
from scripts.resolve import Resolved, resolve_selected


def _cand(work_id="fish-magic"):
    return ImageCandidate(work_id=work_id, institution="wikimedia", label="x",
                          iiif_id=f"wikimedia/{work_id}", image_url="u",
                          width=4000, height=3000, license="Public Domain",
                          rights_status="public_domain")


def test_resolve_selected_uses_first_successful_resolver(tmp_path):
    captured = {}

    def fake_download(cand, sel_dir):
        captured["dir"] = sel_dir
        return SimpleNamespace(status="downloaded", image_path=tmp_path / "fish.jpg")

    res = resolve_selected(
        _entry(), tmp_path,
        resolvers=[lambda e: None, lambda e: _cand()],   # commons misses, aic hits
        download=fake_download)
    assert isinstance(res, Resolved)
    assert res.rights == "public_domain"
    assert res.image_path == tmp_path / "fish.jpg"
    assert captured["dir"] == tmp_path


def test_resolve_selected_keeps_source_url_when_in_copyright(tmp_path):
    called = []
    res = resolve_selected(
        _entry(source_url="https://www.wikidata.org/wiki/Q1"), tmp_path,
        resolvers=[lambda e: None, lambda e: None],
        download=lambda c, d: called.append(c) or SimpleNamespace(status="downloaded", image_path=None))
    assert res.rights == "in_copyright"
    assert res.image_path is None
    assert res.source_url == "https://www.wikidata.org/wiki/Q1"
    assert called == []   # nothing downloaded for in-copyright works
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -k resolve_selected -v`
Expected: FAIL — `ImportError: cannot import name 'Resolved'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top imports of `skill/scripts/resolve.py`:

```python
from dataclasses import dataclass
from pathlib import Path

from scripts.image_download import download_candidate
```

Append:

```python
@dataclass(frozen=True)
class Resolved:
    work_id: str
    rights: str  # public_domain | in_copyright
    image_path: Path | None
    image_url: str | None
    source_url: str
    license: str = ""
    institution: str = ""


RESOLVERS = (commons_resolver, aic_resolver)


def resolve_selected(entry, selected_dir, *, resolvers=RESOLVERS, download=download_candidate) -> Resolved:
    """Resolve one selected work to high-res, falling back to source_url when in copyright."""
    for resolver in resolvers:
        cand = resolver(entry)
        if cand is None:
            continue
        result = download(cand, selected_dir)
        if result.status in ("downloaded", "skipped") and result.image_path is not None:
            return Resolved(entry.work_id, "public_domain", result.image_path, cand.image_url,
                            entry.source_url, license=cand.license or "", institution=cand.institution)
    return Resolved(entry.work_id, "in_copyright", None, None, entry.source_url)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: PASS (all resolve tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/resolve.py tests/test_resolve.py
git commit -m "feat: resolve_selected — resolver chain + download + in-copyright fallback

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B5: `resolve_selection` — drive the liked set + write a manifest

**Files:**
- Modify: `skill/scripts/resolve.py`
- Test: `tests/test_resolve.py`

**Interfaces:**
- Consumes: `resolve_selected` (B4), `selection.Selection`/`selection.liked`.
- Produces: `resolve_selection(sel, selected_dir, *, resolvers=RESOLVERS, download=download_candidate) -> list[Resolved]` — resolves every liked rating, writes `selected_dir/resolved.json` (a list of `{work_id, rights, image, source_url, license, institution}`; `image` is the file name or `null`), returns the `Resolved` list.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_resolve.py`:

```python
import json

from scripts.resolve import resolve_selection
from scripts.selection import Selection


def test_resolve_selection_resolves_liked_and_writes_manifest(tmp_path):
    sel = Selection(artist="paul-klee", ratings=[
        _entry(work_id="fish-magic", rating=5, inst_ids=(("commons_file", "Fish.jpg"),)),
        _entry(work_id="meh", rating=2),  # below threshold → skipped
    ])

    def fake_download(cand, sel_dir):
        return SimpleNamespace(status="downloaded", image_path=sel_dir / f"{cand.work_id}.jpg")

    out = resolve_selection(sel, tmp_path,
                            resolvers=[lambda e: _cand(e.work_id)], download=fake_download)
    assert [r.work_id for r in out] == ["fish-magic"]   # only liked
    manifest = json.loads((tmp_path / "resolved.json").read_text(encoding="utf-8"))
    assert manifest[0]["work_id"] == "fish-magic"
    assert manifest[0]["image"] == "fish-magic.jpg"
    assert manifest[0]["rights"] == "public_domain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_resolve.py -k resolve_selection -v`
Expected: FAIL — `ImportError: cannot import name 'resolve_selection'`.

- [ ] **Step 3: Write minimal implementation**

Add to the top imports of `skill/scripts/resolve.py`:

```python
import json

from scripts.selection import liked
```

Append:

```python
def resolve_selection(sel, selected_dir, *, resolvers=RESOLVERS, download=download_candidate) -> list[Resolved]:
    """Resolve every liked work; write selected_dir/resolved.json; return the results."""
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Resolved] = []
    for rating in liked(sel):
        out.append(resolve_selected(rating, selected_dir, resolvers=resolvers, download=download))
    manifest = [
        {
            "work_id": r.work_id,
            "rights": r.rights,
            "image": r.image_path.name if r.image_path else None,
            "source_url": r.source_url,
            "license": r.license,
            "institution": r.institution,
        }
        for r in out
    ]
    (selected_dir / "resolved.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_resolve.py -v`
Expected: PASS (all resolve tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/resolve.py tests/test_resolve.py
git commit -m "feat: resolve_selection — resolve liked set + write resolved.json manifest

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B6: Thumbnail board export carries `qid` + `inst_ids`

**Files:**
- Modify: `skill/scripts/gallery.py` (`build_thumbnail_gallery` payload ~line 85; export JS in `_THUMB_TEMPLATE` ~line 376)
- Test: `tests/test_gallery.py`

**Interfaces:**
- Consumes: `ThumbnailCandidate.qid`/`inst_ids` (Plan A, Task A1).
- Produces: the board's embedded `candidates` payload and the exported `selection.json` ratings each include `qid` and `inst_ids`, so the resolver (B2–B5) receives them.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_gallery.py`:

```python
def test_thumbnail_gallery_embeds_qid_and_inst_ids():
    cands = [ThumbnailCandidate(
        work_id="fish-magic", title="Fish Magic", museum="Philadelphia Museum of Art",
        thumbnail_url="https://commons.wikimedia.org/wiki/Special:FilePath/Fish.jpg?width=400",
        source_url="https://www.wikidata.org/wiki/Q3050231", date="1925", rights="unknown",
        qid="Q3050231", inst_ids=(("commons_file", "Fish.jpg"), ("aic", "16569")))]
    html = build_thumbnail_gallery(cands, "Paul Klee")
    assert "Q3050231" in html
    assert "commons_file" in html and "Fish.jpg" in html
    # the export builder forwards qid + inst_ids into selection.json ratings
    assert "qid: c.qid" in html and "inst_ids: c.inst_ids" in html
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_gallery.py -k qid_and_inst_ids -v`
Expected: FAIL — `Q3050231`/`qid: c.qid` not present in the HTML.

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/gallery.py`, add to the `build_thumbnail_gallery` payload dict (after `"rights": c.rights,`):

```python
            "rights": c.rights,
            "qid": c.qid,
            "inst_ids": [list(pair) for pair in c.inst_ids],
```

In `_THUMB_TEMPLATE`, extend the export object (the `return { ... }` inside the `export` click handler) to forward the fields:

```javascript
      work_id: c.work_id, iiif_token: c.iiif_token, image_rel: c.image_rel,
      source_url: c.source_url, museum: c.museum, rights: c.rights,
      qid: c.qid, inst_ids: c.inst_ids,
      rating: s.rating || 0, thesis: s.thesis || "",
      anchor_trait: s.anchor_trait || "", handoff_note: s.handoff_note || "",
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_gallery.py -v`
Expected: PASS (existing + new).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/gallery.py tests/test_gallery.py
git commit -m "feat: thumbnail board exports qid + inst_ids into selection.json

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task B7: Wire the resolver into SKILL.md stage 5

**Files:**
- Modify: `skill/SKILL.md` (stage-5 / image-discovery section and the post-curation handoff)

**Interfaces:** none (documentation). Note `tests/test_skill_md.py` may assert on SKILL.md structure — keep it green.

- [ ] **Step 1: Inspect the current stage-5 wording**

Run: `grep -n "image_discovery\|selection.json\|apply_selection\|discover_commons\|search_aic\|thumbnail" skill/SKILL.md`
Read the surrounding lines so the edit matches the existing voice and the stage's two runs (board build, then post-curation resolution).

- [ ] **Step 2: Edit SKILL.md**

Update the stage-5 description to document the two-phase flow:
- **Discovery:** build the board with `scripts/wikidata.py` `search_wikidata(artist)` as the **primary** source (resolve the QID — if it returns ambiguous candidates, present them and ask the user to pick; record that prompt under `prompts/`); supplement with `museum_search.search_aic(artist)`; combine via `wikidata.merge_boards(wikidata_board, aic_board, suppress_aic_ids=<AIC ids on the Wikidata works>)`; render with `gallery.build_thumbnail_gallery`.
- **Post-curation resolution:** after the human exports `selection.json`, run `resolve.resolve_selection(load_selection(...), images/selected/)` to fetch high-res for liked works (Commons PD/CC0 → AIC 1686px → keep `source_url`). Note that `selection.apply_selection` remains for the legacy local-candidate (IIIF discovery) path; the thumbnail-board path uses `resolve_selection`.
- Keep the copyright posture note: browse thumbnails freely; download high-res only on a verified PD/CC0 flag. Do not hard-wrap body text.

- [ ] **Step 3: Run the suite**

Run: `uv run pytest -q`
Expected: PASS (all tests, including `tests/test_skill_md.py`).

- [ ] **Step 4: Commit**

```bash
git add skill/SKILL.md
git commit -m "docs: wire Wikidata board + post-curation resolver into SKILL.md stage 5

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (Plan B)

- **Spec coverage:** post-curation resolver with pluggable chain (B2–B5), Commons + AIC implemented now / Met+Cleveland pluggable via the `resolvers` interface (B4), in-copyright keeps `source_url` and downloads nothing (B4), `selection.json` carries provenance (B1, B6), SKILL.md wiring (B7). Met/Cleveland resolvers are explicitly out of scope per the spec's non-goals. ✓
- **Placeholder scan:** every code/test step has complete code; B7 is a doc task with concrete instructions and a grep to locate the section. ✓
- **Type consistency:** `Rating(... qid, source_url, museum, rights, inst_ids)` (B1) is the `entry` consumed by `_find`/`commons_resolver`/`aic_resolver`/`resolve_selected` (B2–B4); `ImageCandidate` returned by resolvers (B2/B3) consumed by `resolve_selected` (B4); `download_candidate(cand, dir) -> result.status/.image_path` matches `image_download.DownloadResult`; `Resolved` shape consistent B4→B5. ✓
- **Dependency on Plan A:** requires `ThumbnailCandidate.qid`/`inst_ids` and the `("commons_file", …)`/`("aic", …)` convention from Plan A Tasks A1/A5. Land Plan A first. ✓
