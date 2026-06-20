# Image Discovery — Wikidata Tier-1 Discovery (Plan A) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the stage-5 curation board Wikidata-primary — discover an artist's works across all holding institutions via a SPARQL `creator (P170)` query, merge with the existing AIC source, and dedup on the Wikidata QID — so cross-museum works (e.g. Klee's *Fish Magic*, *The Goldfish*) appear on the board.

**Architecture:** New pure module `scripts/wikidata.py` (QID resolution + works SPARQL + Commons FilePath thumbnails + board merge/dedup), with the network boundary injected exactly like `scripts/museum_search.py` (`query=`/`fetch=` callables, real httpx defaults untested). `ThumbnailCandidate` gains `qid` and `inst_ids` so the board can dedup and so Plan B's resolver knows where to fetch high-res. The wiki stage note is rewritten to the tiered model.

**Tech Stack:** Python 3, uv, pytest. SPARQL via `query.wikidata.org/sparql`. Spec: `docs/superpowers/specs/2026-06-20-image-discovery-wikidata-tier1.md`.

## Global Constraints

- Venv lives OUTSIDE iCloud at `~/.venvs/artist-study-kit`; run tests with `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run pytest` (or plain `uv run pytest` via the `.venv` symlink).
- pytest config: `pythonpath = ["skill"]`, `testpaths = ["tests"]` — import modules as `from scripts.<name> import ...`; tests live in `tests/`.
- TDD, red-green, one behavior per test. **No live network in tests** — inject every network call via a `query=`/`fetch=`/`search=` parameter (mirror `museum_search.search_aic`).
- Real network helpers (`default_sparql`) carry the descriptive User-Agent `artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)` and are NOT exercised by tests.
- Dataclasses are `@dataclass(frozen=True)`; collection fields are tuples, never lists (frozen-safe).
- Commit after each task with a `feat:`/`test:`/`docs:` single-line message; end commit bodies with `Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>`.
- Run the full suite (`uv run pytest -q`) green before the final commit of each task.

---

### Task A1: `ThumbnailCandidate` gains `qid` + `inst_ids`

**Files:**
- Modify: `skill/scripts/museum_search.py` (the `ThumbnailCandidate` dataclass ~line 26; `parse_aic_search` ~line 78)
- Test: `tests/test_museum_search.py`

**Interfaces:**
- Produces: `ThumbnailCandidate(work_id, title, museum, thumbnail_url, source_url, date, rights, qid: str = "", inst_ids: tuple[tuple[str, str], ...] = ())`. AIC candidates set `qid=""` and `inst_ids=(("aic", str(id)),)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_museum_search.py`:

```python
def test_aic_candidate_carries_aic_inst_id_and_empty_qid():
    cands = parse_aic_search(AIC_WORKS)
    first = cands[0]
    assert first.qid == ""
    assert first.inst_ids == (("aic", "10018"),)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_museum_search.py::test_aic_candidate_carries_aic_inst_id_and_empty_qid -v`
Expected: FAIL — `TypeError` (unexpected keyword) or `AttributeError: 'ThumbnailCandidate' object has no attribute 'qid'`.

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/museum_search.py`, extend the dataclass:

```python
@dataclass(frozen=True)
class ThumbnailCandidate:
    work_id: str
    title: str
    museum: str
    thumbnail_url: str
    source_url: str
    date: str
    rights: str  # public_domain | in_copyright | unknown
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
```

In `parse_aic_search`, set the inst id when appending the candidate:

```python
        out.append(
            ThumbnailCandidate(
                work_id=slugify(title) or f"aic-{d.get('id')}",
                title=title,
                museum="aic",
                thumbnail_url=f"{iiif}/{image_id}/full/{thumb_width},/0/default.jpg",
                source_url=f"https://www.artic.edu/artworks/{d.get('id')}",
                date=str(d.get("date_display") or ""),
                rights="public_domain" if d.get("is_public_domain") else "in_copyright",
                inst_ids=(("aic", str(d.get("id"))),),
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_museum_search.py -v`
Expected: PASS (all existing tests + the new one; defaults keep old assertions valid).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/museum_search.py tests/test_museum_search.py
git commit -m "feat: ThumbnailCandidate carries qid + inst_ids for cross-source dedup

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A2: `commons_filepath` thumbnail URL builder

**Files:**
- Create: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Produces: `commons_filepath(filename: str, *, width: int = 400) -> str` — builds `https://commons.wikimedia.org/wiki/Special:FilePath/<urlencoded, spaces→underscores>?width=<width>`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_wikidata.py`:

```python
from scripts.wikidata import commons_filepath


def test_commons_filepath_encodes_spaces_and_adds_width():
    url = commons_filepath("Paul Klee Fish Magic.jpg")
    assert url == ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   "Paul_Klee_Fish_Magic.jpg?width=400")


def test_commons_filepath_urlencodes_reserved_chars_and_custom_width():
    url = commons_filepath("Müller & Sohn.jpg", width=1686)
    assert url.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
    assert "M%C3%BCller_%26_Sohn.jpg" in url
    assert url.endswith("?width=1686")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'scripts.wikidata'`.

- [ ] **Step 3: Write minimal implementation**

Create `skill/scripts/wikidata.py`:

```python
"""Stage-5 Tier-1 discovery: Wikidata as the curation board's primary source.

Wikidata is the "pivot/identity layer" (raw/16.1-image-source-hierarchy): a `creator
(P170)` SPARQL query returns an artist's works across every holding institution, with the
QID as the universal dedup key. Pure parsing/builders are fixture-tested; the network
boundary (`default_sparql`) is injected so tests never hit live WDQS.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote

COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath"
WDQS = "https://query.wikidata.org/sparql"
USER_AGENT = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"


def commons_filepath(filename: str, *, width: int = 400) -> str:
    """Thumbnail/full URL for a Commons file via Special:FilePath."""
    name = quote(filename.strip().replace(" ", "_"), safe="")
    return f"{COMMONS_FILEPATH}/{name}?width={width}"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: PASS (both tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: wikidata.commons_filepath thumbnail URL builder

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A3: QID resolution with work-count disambiguation

**Files:**
- Modify: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `@dataclass(frozen=True) ArtistEntity(qid: str, label: str, description: str, occupation: str, work_count: int)`
  - `qid_lookup_sparql(name: str) -> str`
  - `parse_qid_candidates(payload: dict) -> list[ArtistEntity]`
  - `resolve_qid(name: str, *, query=default_sparql) -> tuple[str | None, list[ArtistEntity]]` — auto-pick when exactly one candidate has any works; `(None, candidates)` when zero candidates, the leader has no works, or two+ candidates have works (caller surfaces for the user).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wikidata.py`:

```python
from scripts.wikidata import (
    ArtistEntity,
    parse_qid_candidates,
    resolve_qid,
)

# WDQS JSON: the painter Q44007 has many works; the foundation Q706082 has none.
QID_KLEE = {"results": {"bindings": [
    {"item": {"value": "http://www.wikidata.org/entity/Q44007"},
     "itemLabel": {"value": "Paul Klee"},
     "itemDescription": {"value": "Swiss-German artist (1879-1940)"},
     "occLabel": {"value": "painter"},
     "works": {"value": "671"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q706082"},
     "itemLabel": {"value": "Zentrum Paul Klee"},
     "itemDescription": {"value": "art museum in Bern"},
     "occLabel": {"value": ""},
     "works": {"value": "0"}},
]}}

QID_TIE = {"results": {"bindings": [
    {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "John Smith"},
     "itemDescription": {"value": "painter"}, "occLabel": {"value": "painter"}, "works": {"value": "12"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "itemLabel": {"value": "John Smith"},
     "itemDescription": {"value": "illustrator"}, "occLabel": {"value": "illustrator"}, "works": {"value": "8"}},
]}}

QID_NONE = {"results": {"bindings": []}}


def test_parse_qid_candidates_reads_uri_tail_and_workcount():
    cands = parse_qid_candidates(QID_KLEE)
    assert cands[0] == ArtistEntity("Q44007", "Paul Klee",
                                    "Swiss-German artist (1879-1940)", "painter", 671)


def test_resolve_qid_autopicks_sole_creator():
    qid, cands = resolve_qid("Paul Klee", query=lambda q: QID_KLEE)
    assert qid == "Q44007"          # not the foundation Q706082
    assert len(cands) == 2


def test_resolve_qid_surfaces_on_tie():
    qid, cands = resolve_qid("John Smith", query=lambda q: QID_TIE)
    assert qid is None              # two candidates have works → ambiguous
    assert [c.qid for c in cands] == ["Q1", "Q2"]


def test_resolve_qid_returns_none_when_no_candidates():
    qid, cands = resolve_qid("Nobody", query=lambda q: QID_NONE)
    assert qid is None and cands == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -k qid -v`
Expected: FAIL — `ImportError: cannot import name 'ArtistEntity'`.

- [ ] **Step 3: Write minimal implementation**

Append to `skill/scripts/wikidata.py`:

```python
@dataclass(frozen=True)
class ArtistEntity:
    qid: str
    label: str
    description: str
    occupation: str
    work_count: int


def _qid_tail(uri: str) -> str:
    return uri.rstrip("/").rsplit("/", 1)[-1]


def _binding(row: dict, key: str) -> str:
    return (row.get(key) or {}).get("value", "")


def qid_lookup_sparql(name: str) -> str:
    """Humans whose label/alias matches `name`, ranked by number of works created."""
    safe = name.replace('"', '\\"')
    return f'''
SELECT ?item ?itemLabel ?itemDescription ?occLabel (COUNT(DISTINCT ?w) AS ?works) WHERE {{
  ?item rdfs:label|skos:altLabel ?name .
  FILTER(LCASE(STR(?name)) = LCASE("{safe}"))
  ?item wdt:P31 wd:Q5 .
  OPTIONAL {{ ?item wdt:P106 ?occ . }}
  OPTIONAL {{ ?w wdt:P170 ?item . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
GROUP BY ?item ?itemLabel ?itemDescription ?occLabel
ORDER BY DESC(?works)
'''.strip()


def parse_qid_candidates(payload: dict) -> list[ArtistEntity]:
    out: list[ArtistEntity] = []
    for row in (payload.get("results") or {}).get("bindings", []):
        out.append(ArtistEntity(
            qid=_qid_tail(_binding(row, "item")),
            label=_binding(row, "itemLabel"),
            description=_binding(row, "itemDescription"),
            occupation=_binding(row, "occLabel"),
            work_count=int(_binding(row, "works") or 0),
        ))
    return out


def resolve_qid(name: str, *, query=None) -> tuple[str | None, list[ArtistEntity]]:
    """Resolve an artist name to a QID. Auto-pick the sole work-having entity.

    Returns (qid, candidates). qid is None when nothing matches, the leader has no
    works, or 2+ entities have works (ambiguous → caller surfaces candidates).
    """
    query = query or default_sparql
    ranked = sorted(parse_qid_candidates(query(qid_lookup_sparql(name))),
                    key=lambda c: c.work_count, reverse=True)
    if not ranked or ranked[0].work_count == 0:
        return None, ranked
    if any(c.work_count > 0 for c in ranked[1:]):
        return None, ranked  # tie / ambiguous
    return ranked[0].qid, ranked


def default_sparql(query: str) -> dict:
    """Real WDQS fetch (httpx). Not exercised in tests."""
    import httpx

    resp = httpx.get(WDQS, params={"query": query, "format": "json"},
                     headers={"User-Agent": USER_AGENT, "Accept": "application/sparql-results+json"},
                     timeout=60.0)
    resp.raise_for_status()
    return resp.json()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -k qid -v`
Expected: PASS (4 tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: wikidata QID resolution with work-count disambiguation

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A4: Works SPARQL + `parse_works`

**Files:**
- Modify: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: `_binding`, `_qid_tail` (Task A3).
- Produces:
  - `@dataclass(frozen=True) WikidataWork(qid: str, title: str, image_file: str, collection: str, date: str, aic_id: str, met_id: str)`
  - `works_sparql(qid: str) -> str`
  - `parse_works(payload: dict) -> list[WikidataWork]` — `image_file` is the Commons filename parsed from a P18 `Special:FilePath/<file>` value (URL-decoded); `date` is the 4-digit year from inception; works without an image keep `image_file=""`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wikidata.py`:

```python
from scripts.wikidata import WikidataWork, parse_works

WORKS = {"results": {"bindings": [
    {"work": {"value": "http://www.wikidata.org/entity/Q3050231"},
     "workLabel": {"value": "Fish Magic"},
     "image": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Paul%20Klee%2C%20Fish%20Magic.jpg"},
     "collectionLabel": {"value": "Philadelphia Museum of Art"},
     "inception": {"value": "1925-01-01T00:00:00Z"},
     "aic": {"value": "no"}},
    {"work": {"value": "http://www.wikidata.org/entity/Q123"},
     "workLabel": {"value": "Senecio"},
     "image": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Senecio.jpg"},
     "collectionLabel": {"value": "Kunstmuseum Basel"},
     "inception": {"value": "1922-01-01T00:00:00Z"},
     "aic": {"value": "16569"}},
    {"work": {"value": "http://www.wikidata.org/entity/Q999"},
     "workLabel": {"value": "Lost Work"}},  # no image → image_file ""
]}}


def test_parse_works_extracts_filename_year_and_collection():
    works = parse_works(WORKS)
    assert works[0] == WikidataWork(
        qid="Q3050231", title="Fish Magic", image_file="Paul Klee, Fish Magic.jpg",
        collection="Philadelphia Museum of Art", date="1925", aic_id="", met_id="")


def test_parse_works_keeps_aic_id_and_imageless_work():
    works = parse_works(WORKS)
    assert works[1].aic_id == "16569"
    assert works[2].image_file == "" and works[2].title == "Lost Work"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -k works -v`
Expected: FAIL — `ImportError: cannot import name 'WikidataWork'`.

- [ ] **Step 3: Write minimal implementation**

Append to `skill/scripts/wikidata.py` (add `from urllib.parse import quote, unquote` — update the existing import line):

```python
@dataclass(frozen=True)
class WikidataWork:
    qid: str
    title: str
    image_file: str
    collection: str
    date: str
    aic_id: str
    met_id: str


def _filepath_filename(image_url: str) -> str:
    """`.../Special:FilePath/Paul%20Klee.jpg` -> `Paul Klee.jpg` (URL-decoded)."""
    if not image_url:
        return ""
    tail = image_url.rstrip("/").rsplit("/", 1)[-1]
    return unquote(tail).replace("_", " ")


def works_sparql(qid: str) -> str:
    return f'''
SELECT ?work ?workLabel ?image ?collectionLabel ?inception ?aic ?met WHERE {{
  ?work wdt:P170 wd:{qid} .
  OPTIONAL {{ ?work wdt:P18 ?image . }}
  OPTIONAL {{ ?work wdt:P195 ?collection . }}
  OPTIONAL {{ ?work wdt:P571 ?inception . }}
  OPTIONAL {{ ?work wdt:P4610 ?aic . }}
  OPTIONAL {{ ?work wdt:P3634 ?met . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en". }}
}}
'''.strip()


def parse_works(payload: dict) -> list[WikidataWork]:
    out: list[WikidataWork] = []
    for row in (payload.get("results") or {}).get("bindings", []):
        aic = _binding(row, "aic")
        out.append(WikidataWork(
            qid=_qid_tail(_binding(row, "work")),
            title=_binding(row, "workLabel"),
            image_file=_filepath_filename(_binding(row, "image")),
            collection=_binding(row, "collectionLabel"),
            date=_binding(row, "inception")[:4],
            aic_id=aic if aic.isdigit() else "",
            met_id=_binding(row, "met") if _binding(row, "met").isdigit() else "",
        ))
    return out
```

Note: change the top-of-file import to `from urllib.parse import quote, unquote`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: PASS (all wikidata tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: wikidata works SPARQL + parse_works (image/collection/inst-ids)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A5: `to_thumbnail_candidates`

**Files:**
- Modify: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: `WikidataWork` (A4), `commons_filepath` (A2), `ThumbnailCandidate` (A1), `scripts.paths.slugify`.
- Produces: `to_thumbnail_candidates(works: list[WikidataWork], *, thumb_width: int = 400) -> list[ThumbnailCandidate]` — one per work WITH an image; `museum` = collection or `"wikidata"`; `source_url` = entity URL; `rights="unknown"`; `qid` set; `inst_ids` carries `("commons_file", filename)` plus `("aic", id)` / `("met", id)` when present.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wikidata.py`:

```python
from scripts.museum_search import ThumbnailCandidate
from scripts.wikidata import to_thumbnail_candidates


def test_to_thumbnail_candidates_builds_board_entries():
    works = parse_works(WORKS)
    cands = to_thumbnail_candidates(works)
    assert len(cands) == 2  # imageless 'Lost Work' dropped
    fish = cands[0]
    assert isinstance(fish, ThumbnailCandidate)
    assert fish.qid == "Q3050231"
    assert fish.museum == "Philadelphia Museum of Art"
    assert fish.source_url == "https://www.wikidata.org/wiki/Q3050231"
    assert fish.rights == "unknown"
    assert fish.thumbnail_url.endswith("Paul_Klee,_Fish_Magic.jpg?width=400")
    assert ("commons_file", "Paul Klee, Fish Magic.jpg") in fish.inst_ids


def test_to_thumbnail_candidates_includes_aic_inst_id():
    senecio = to_thumbnail_candidates(parse_works(WORKS))[1]
    assert ("aic", "16569") in senecio.inst_ids
    assert ("commons_file", "Senecio.jpg") in senecio.inst_ids
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -k thumbnail_candidates -v`
Expected: FAIL — `ImportError: cannot import name 'to_thumbnail_candidates'`.

- [ ] **Step 3: Write minimal implementation**

Add the import near the top of `skill/scripts/wikidata.py`:

```python
from scripts.museum_search import ThumbnailCandidate
from scripts.paths import slugify
```

Append:

```python
def to_thumbnail_candidates(works: list[WikidataWork], *, thumb_width: int = 400) -> list[ThumbnailCandidate]:
    """Board entries for works that have a Commons image (rights resolved later)."""
    out: list[ThumbnailCandidate] = []
    for w in works:
        if not w.image_file:
            continue
        inst: list[tuple[str, str]] = [("commons_file", w.image_file)]
        if w.aic_id:
            inst.append(("aic", w.aic_id))
        if w.met_id:
            inst.append(("met", w.met_id))
        out.append(ThumbnailCandidate(
            work_id=slugify(w.title) or w.qid.lower(),
            title=w.title or "Untitled",
            museum=w.collection or "wikidata",
            thumbnail_url=commons_filepath(w.image_file, width=thumb_width),
            source_url=f"https://www.wikidata.org/wiki/{w.qid}",
            date=w.date,
            rights="unknown",
            qid=w.qid,
            inst_ids=tuple(inst),
        ))
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: wikidata to_thumbnail_candidates (board entries with qid + inst_ids)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A6: `merge_boards` — QID/inst-id/title dedup

**Files:**
- Modify: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: `ThumbnailCandidate` (A1), `WikidataWork` (A4).
- Produces: `merge_boards(primary: list[ThumbnailCandidate], supplement: list[ThumbnailCandidate], *, suppress_aic_ids: set[str]) -> list[ThumbnailCandidate]` — drops supplement AIC entries whose AIC id is in `suppress_aic_ids`, then dedups the concatenation (primary first) keyed by `qid` else folded `title|date`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wikidata.py`:

```python
from scripts.wikidata import merge_boards


def _tc(title, *, museum="aic", qid="", aic_id="", date="1922"):
    inst = (("aic", aic_id),) if aic_id else ()
    return ThumbnailCandidate(
        work_id=title.lower().replace(" ", "-"), title=title, museum=museum,
        thumbnail_url="t", source_url="s", date=date, rights="unknown",
        qid=qid, inst_ids=inst)


def test_merge_suppresses_aic_dupe_by_inst_id():
    primary = [_tc("Senecio", museum="Kunstmuseum Basel", qid="Q123")]
    supplement = [_tc("Senecio", aic_id="16569"), _tc("AIC Only", aic_id="999")]
    out = merge_boards(primary, supplement, suppress_aic_ids={"16569"})
    titles = [c.title for c in out]
    assert titles == ["Senecio", "AIC Only"]   # AIC Senecio suppressed, AIC-only kept
    assert out[0].qid == "Q123"                 # the Wikidata record wins


def test_merge_dedups_remaining_by_title_and_date():
    primary = [_tc("Twittering Machine", qid="Q44", date="1922")]
    supplement = [_tc("Twittering Machine", aic_id="5", date="1922")]
    out = merge_boards(primary, supplement, suppress_aic_ids=set())
    assert len(out) == 1 and out[0].qid == "Q44"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -k merge -v`
Expected: FAIL — `ImportError: cannot import name 'merge_boards'`.

- [ ] **Step 3: Write minimal implementation**

Append to `skill/scripts/wikidata.py` (add `import unicodedata` at the top):

```python
def _fold(text: str) -> str:
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower().strip()


def _aic_id(cand: ThumbnailCandidate) -> str:
    return next((v for k, v in cand.inst_ids if k == "aic"), "")


def merge_boards(primary, supplement, *, suppress_aic_ids: set[str]):
    """Wikidata-primary board: drop AIC dupes by inst-id, then dedup by qid/title+date."""
    merged: list[ThumbnailCandidate] = list(primary)
    merged += [c for c in supplement if _aic_id(c) not in suppress_aic_ids]
    seen: set[str] = set()
    out: list[ThumbnailCandidate] = []
    for c in merged:
        key = c.qid or f"{_fold(c.title)}|{c.date}"
        if key in seen:
            continue
        seen.add(key)
        out.append(c)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: merge_boards — Wikidata-primary board dedup (inst-id, qid, title)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A7: `search_wikidata` orchestrator

**Files:**
- Modify: `skill/scripts/wikidata.py`
- Test: `tests/test_wikidata.py`

**Interfaces:**
- Consumes: `resolve_qid`, `works_sparql`, `parse_works`, `to_thumbnail_candidates` (A3–A5).
- Produces: `search_wikidata(artist: str, *, query=default_sparql, thumb_width: int = 400) -> tuple[list[ThumbnailCandidate], list[WikidataWork], list[ArtistEntity]]` — returns `(board_candidates, works, ambiguous_candidates)`; `board_candidates`/`works` are empty when the QID is unresolved (and `ambiguous_candidates` is non-empty so the caller can prompt the user). Note `works` is returned so Task A8's caller can build the `suppress_aic_ids` set (the AIC ids on Wikidata works) for `merge_boards`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_wikidata.py`:

```python
from scripts.wikidata import search_wikidata


def test_search_wikidata_resolves_then_fetches_works():
    calls = []

    def fake_query(q):
        calls.append(q)
        return QID_KLEE if "P31 wd:Q5" in q else WORKS

    board, works, ambiguous = search_wikidata("Paul Klee", query=fake_query)
    assert ambiguous == []                       # auto-resolved
    assert [w.title for w in works] == ["Fish Magic", "Senecio", "Lost Work"]
    assert {c.title for c in board} == {"Fish Magic", "Senecio"}
    assert any("wd:Q44007" in q for q in calls)  # works query used the resolved QID


def test_search_wikidata_returns_candidates_when_ambiguous():
    board, works, ambiguous = search_wikidata("John Smith", query=lambda q: QID_TIE)
    assert board == [] and works == []
    assert [c.qid for c in ambiguous] == ["Q1", "Q2"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wikidata.py -k search_wikidata -v`
Expected: FAIL — `ImportError: cannot import name 'search_wikidata'`.

- [ ] **Step 3: Write minimal implementation**

Append to `skill/scripts/wikidata.py`:

```python
def search_wikidata(artist: str, *, query=None, thumb_width: int = 400):
    """Resolve the artist's QID, fetch their works, build board candidates.

    Returns (board_candidates, works, ambiguous_candidates). When the QID can't be
    auto-resolved, board/works are empty and ambiguous_candidates is non-empty.
    """
    query = query or default_sparql
    qid, candidates = resolve_qid(artist, query=query)
    if qid is None:
        return [], [], candidates
    works = parse_works(query(works_sparql(qid)))
    return to_thumbnail_candidates(works, thumb_width=thumb_width), works, []
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wikidata.py -v`
Expected: PASS (all wikidata tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/wikidata.py tests/test_wikidata.py
git commit -m "feat: search_wikidata orchestrator (resolve QID -> works -> board)

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

### Task A8: Rewrite `wiki/stage-image-discovery.md` to the tiered model

**Files:**
- Modify: `wiki/stage-image-discovery.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Rewrite the stage note**

Replace the body of `wiki/stage-image-discovery.md` with the tiered, two-phase spec. Keep the existing frontmatter shape; add the new research source. Do NOT hard-wrap body text (Obsidian renders single newlines as `<br>`). Content:

```markdown
---
title: "Image Discovery — cross-museum board, legally"
type: wiki/stage
stage: 5
sources: [16.1-image-source-hierarchy, 03.1-museum-image-apis, 01.1-web-scraping-tooling]
tags: [wiki/stage, technique/image-acquisition]
aliases: []
---

# Image Discovery

> [!info] Pipeline role
> Build a broad cross-institution **thumbnail board** of an artist's works for human curation, then resolve only the SELECTED works to the best legally-clear high-resolution image. Emits the curation board, then `images/selected/` + per-image metadata.

## What the research says

[[16.1-image-source-hierarchy]] establishes a tiered source hierarchy. **T1 — Wikidata** is the pivot/identity layer: a `creator (P170)` SPARQL query returns an artist's works across every holding institution, with the QID as the universal key for cross-source dedup (institution-id properties P4610 AIC, P3634 Met bridge to museum records). **T2 — Met / AIC / Cleveland** provide the highest-resolution assets and machine-readable rights (`isPublicDomain`, `is_public_domain`, `share_license_status=="CC0"`). **T3 — Wikimedia Commons (SDC) / Europeana** are broad discovery aggregators. **T4 — DPLA / Google Arts / WikiArt / general image search** are discovery-only (no reliable rights) and must be verified through T1/T2 before any high-res download.

The IIIF acquisition mechanics live in [[concept-iiif]] (from [[03.1-museum-image-apis]]): the `info.json`-then-`max` fetch pattern and automated rights parsing. Commons thumbnails are reached via `Special:FilePath/<file>?width=N`.

## Open questions / tensions

- **Namesake/foundation QID collisions** — name search returns both the artist and lookalike entities (e.g. "Zentrum Paul Klee"). Disambiguate by work-count (the real creator has the works); surface to the user on a genuine tie.
- **Coverage vs rights** — the board is intentionally rights-agnostic (browse everything); rights only gate the post-curation high-res download. Missing rights ⇒ treat as restricted, keep the thumbnail/source link only.
- **Recall vs precision on attribution** — Wikidata `creator` discovery is high-recall and authoritative; the legacy Commons keyword guard was precision-first (could drop correct files). Wikidata supersedes it for discovery; the keyword path survives only inside the resolver.

## Skill design implications

Two phases:
1. **Discovery → board (rights-agnostic).** Wikidata is the primary source (`search_wikidata`): resolve the artist QID, query works, build thumbnail candidates (Commons `Special:FilePath`). AIC supplements works Wikidata lacks; `merge_boards` dedups by QID → AIC/Met inst-id → folded title+date. The board shows many thumbnails for the human to rate.
2. **Resolution → selected (rights-gated).** For each selected work, a pluggable resolver chain fetches the best legally-clear high-res: Commons P18 (PD/CC0) → AIC IIIF 1686px (`is_public_domain`) → else keep `source_url` (in-copyright, thumbnail only). Met/Cleveland resolvers drop into the same interface later.

Copyright posture: browse thumbnails ≤843px (hotlinked, for private curation); download high-res ONLY on a verified PD/CC0 flag. Capture per-image metadata: source URL, institution, license, pixel dimensions, QID, and parent work id. Never auto-select — curation is human ([[stage-curation]]).
```

- [ ] **Step 2: Verify the suite is unaffected**

Run: `uv run pytest -q`
Expected: PASS (docs change; `tests/test_skill_md.py` and others stay green).

- [ ] **Step 3: Commit**

```bash
git add wiki/stage-image-discovery.md
git commit -m "docs: rewrite stage-image-discovery wiki note to tiered two-phase model

Co-Authored-By: Claude Opus 4.8 (1M context) <noreply@anthropic.com>"
```

---

## Self-Review (Plan A)

- **Spec coverage:** Wikidata Tier-1 source (A2–A5, A7), QID work-count disambiguation (A3), board merge/dedup by QID/inst-id/title (A6), `ThumbnailCandidate.qid`/`inst_ids` (A1), wiki spec rewrite (A8). The post-curation resolver + `selection.json` changes are Plan B (by design). ✓
- **Placeholder scan:** every code/test step carries complete code; no TBD/TODO. ✓
- **Type consistency:** `ThumbnailCandidate(... qid, inst_ids)` (A1) consumed by A5/A6; `_binding`/`_qid_tail` defined A3, reused A4; `WikidataWork`/`parse_works` A4 consumed A5/A7; `resolve_qid` return tuple shape consistent A3→A7. ✓
- **Discovery handoff to Plan B:** board candidates carry `qid` + `inst_ids` (incl. `("commons_file", …)`, `("aic", …)`, `("met", …)`) — exactly what Plan B's resolvers consume. ✓
