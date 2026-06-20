# Image-Discovery Stage Redesign — Wikidata Tier-1 + resolver/dedup

- **Date:** 2026-06-20
- **Stage:** 5 (image discovery) of the artist-study-kit skill pipeline
- **Status:** approved design → ready for implementation plans
- **Research basis:** `raw/16.1-image-source-hierarchy.md` (tiered source hierarchy), `raw/03.1-museum-image-apis.md` (IIIF mechanics), session handoff `raw/17-image-discovery-hardening-session.md`

## Problem

Stage-5 discovery currently builds the curation board from the Art Institute of Chicago (AIC) only. Works held elsewhere are invisible — e.g. Klee's *Fish Magic* (Philadelphia Museum of Art) and *The Goldfish* (Hamburger Kunsthalle) never appear. AIC returns ~97 Klee works; a Wikidata `creator (P170)` query returns ~525 with images, spanning every holding institution.

Two distinct gaps:

1. **Discovery is single-source.** The board needs broad cross-institution coverage. The deep-research hierarchy names **Wikidata as the Tier-1 pivot/identity layer** — the right primary discovery source, with QIDs as the universal dedup key.
2. **No post-curation resolver.** The two-phase model (browse a rights-agnostic thumbnail board → resolve rights/high-res only for selected works) was adopted, but the resolver half was never built. `apply_selection` (`selection.py:94`) still copies from local `images/candidates/<work>/` files, which the thumbnail-board path never produces. Selected works therefore never resolve to high-res.

## Goals

- Add **Wikidata as the Tier-1 discovery source** for the curation board; make it primary, AIC a supplement.
- **Dedup** the merged board on the Wikidata QID (and institution-id properties), so the same work held in multiple places appears once.
- Build the **post-curation high-res resolver**: per selected work, fetch the best legally-clear image (Commons P18 PD/CC0 → AIC IIIF on `is_public_domain` → else keep `source_url`, thumbnail only).
- **Spec the redesign in `wiki/stage-image-discovery.md`** so the wiki reflects the tiered model.
- Preserve the copyright posture: browse thumbnails broadly (≤843px, hotlinked, rights-agnostic); download high-res **only** on a verified PD/CC0 flag.

## Non-goals

- Met and Cleveland high-res resolvers — **designed for** (pluggable interface) but **not implemented** in this scope.
- Europeana / DPLA / Google-Arts / WikiArt / general image-search (Tier 3/4 discovery-only) sources.
- Bulk Scrapy download, AIC nightly data dumps, or a persistent local cache of Wikidata results.
- Changes to stages 1–4 or 6–8 beyond the curation→resolution handoff.

## Decisions (from brainstorming)

| # | Decision | Choice |
|---|----------|--------|
| Scope | One spec, both phases | Full stage-5 redesign (discovery + resolution); splits into two implementation plans. |
| QID resolution | Disambiguation strategy | Work-count-ranked SPARQL over `instance of human (Q5)`; auto-pick a clear leader; surface candidates to the user on zero/tie. |
| Board sources | Combine + dedup | Wikidata primary, AIC supplement; dedup by QID → institution-id (P4610 AIC, P3634 Met) → folded title+date. |
| Resolver T2 | Implement now vs design-for | Commons + AIC implemented now; Met (`isPublicDomain`) / Cleveland (`share_license_status=="CC0"`) pluggable via a common interface. |

## Architecture

Two phases of stage 5:

```
DISCOVERY (pre-curation, rights-agnostic board)
  resolve_qid(artist) ──► works_sparql(QID) ──► WikidataWork[]  (PRIMARY)
                                                      │
  search_aic(artist) ──► ThumbnailCandidate[] (SUPPLEMENT) ──► merge_boards() ──► board
                                                      │            (dedup: QID / inst-id / title)
                                              build_thumbnail_gallery() ──► human rates ──► selection.json

RESOLUTION (post-curation, per selected work)
  selection.json ──► resolve_selected(entry)
                       1. Commons P18 PD/CC0  ─► download → images/selected/
                       2. AIC IIIF 1686 (is_public_domain) ─► download → images/selected/
                       3. else in-copyright   ─► sidecar with source_url, no bytes
```

New modules:
- `scripts/wikidata.py` — QID resolution, works SPARQL, Commons FilePath thumbnails, board candidates.
- `scripts/resolve.py` — pluggable post-curation high-res resolver.

Edited modules: `museum_search.py` (`ThumbnailCandidate` gains `qid`, `inst_ids`), `gallery.py` (export `qid`/inst-ids), `selection.py` (`Rating` carries the new fields; resolution handoff), SKILL.md (stage-5 wiring), `wiki/stage-image-discovery.md`.

All network is injected (the `fetch=`/`query=` parameter pattern already used in `museum_search.py`); pure parsers are fixture-tested; **no live network calls in the test suite**.

## Component design

### `scripts/wikidata.py`

**SPARQL access.** `default_sparql(query: str) -> dict` does an httpx GET to `https://query.wikidata.org/sparql` with `format=json` and the existing descriptive User-Agent (WDQS 403s generic agents). Not exercised in tests. WDQS has a 60s timeout; one query per phase per run is well within limits.

**QID resolution (data-driven disambiguation).**
- `qid_lookup_sparql(name: str) -> str` — candidates that are `wdt:P31 wd:Q5` (human) whose `rdfs:label`/`skos:altLabel` match `name`, returning QID, label, a sample occupation (`wdt:P106`) label, and `COUNT` of works (`?w wdt:P170 ?entity`). Ranked by work-count descending.
- `parse_qid_candidates(json) -> list[ArtistEntity]` — `ArtistEntity(qid, label, description, occupation, work_count)`.
- `resolve_qid(name, *, query=default_sparql) -> tuple[str | None, list[ArtistEntity]]` — returns `(qid, candidates)`. Auto-pick rule: a single survivor, or a clear work-count leader (e.g. leader has works and the runner-up has ~none), is chosen silently; otherwise `qid` is `None` and the caller surfaces `candidates` for the user to pick (Decision Q2). The skill prompt for that disambiguation is recorded under `prompts/` via `scripts/prompts.py`.

**Works query.**
- `works_sparql(qid: str) -> str` — `?work wdt:P170 wd:<qid>`; `OPTIONAL` blocks for P18 (image filename), P195 (collection, with label), P571 (inception → year), **P4610 (AIC artwork id)**, **P3634 (Met object id)**; `rdfs:label` for the title. Language fallback `en`.
- `parse_works(json) -> list[WikidataWork]` — `WikidataWork(qid, title, image_file, collection, date, aic_id, met_id)`. Works without an image file are kept for dedup-suppression bookkeeping but excluded from board candidates.

**Thumbnails & candidates.**
- `commons_filepath(filename: str, *, width: int = 400) -> str` — `https://commons.wikimedia.org/wiki/Special:FilePath/<urlencoded filename>?width=<width>`. Spaces→underscores, URL-encode.
- `to_thumbnail_candidates(works) -> list[ThumbnailCandidate]` — one per work with an image: `museum` = collection label or `"wikidata"`, `thumbnail_url` = `commons_filepath(image_file)`, `source_url` = `https://www.wikidata.org/wiki/<qid>`, `date` from inception, `rights="unknown"` (board is rights-agnostic), `qid` set, `inst_ids` populated from `aic_id`/`met_id`.

### Dedup / merge

`merge_boards(primary, supplement, *, suppress_aic_ids: set[str]) -> list[ThumbnailCandidate]` — pure:
1. Drop supplement (AIC) candidates whose AIC id (parsed from `source_url`) is in `suppress_aic_ids` (the set of P4610 values across Wikidata works — canonical inst-id match).
2. Concatenate primary + surviving supplement; fold-dedup keeping first occurrence, keyed by `qid` when present, else `folded(title)+date`.

`ThumbnailCandidate` gains `qid: str = ""` and `inst_ids: tuple[tuple[str, str], ...] = ()` (e.g. `(("aic","12345"),("met","436524"))`). Tuple, not list, to stay frozen-dataclass-safe.

### `scripts/resolve.py`

Resolver protocol: `resolver(entry) -> ImageCandidate | None`, where `entry` is a selection record (work_id, qid, source_url, museum, rights, inst_ids). Registry `RESOLVERS = (commons_resolver, aic_resolver)`, tried in order; Met/Cleveland append later.

- `commons_resolver` — if the work's Wikidata P18 file resolves to a Commons file whose license is PD/CC0 (reuse `iiif.classify_rights` / `commons.py` eligibility), return a full-resolution `ImageCandidate` (Commons original via `Special:FilePath` without width, or the file's direct URL).
- `aic_resolver` — if an AIC id is present and the AIC record's `is_public_domain` is true, return the IIIF 1686px candidate (`{iiif}/{image_id}/full/1686,/0/default.jpg`).
- `resolve_selected(entry, *, resolvers=RESOLVERS) -> Resolved` — first non-None resolver wins → download bytes via `image_download` into `images/selected/`; if all return None (in-copyright / unverifiable), produce `Resolved(rights="in_copyright", image_url=None, source_url=…)` and **download nothing**.
- `Resolved(work_id, image_url, local_path, rights, license, source)`.

Copyright gate is enforced in the resolvers, not the caller: a resolver returns a downloadable candidate **only** when it has verified a PD/CC0 flag.

### `selection.json` + curation→resolution handoff

The thumbnail-board export (`gallery._THUMB_TEMPLATE`) already emits `work_id/source_url/museum/rights/rating`; **add `qid` and `inst_ids`**. `selection.Rating` and `parse_selection` carry the new fields (back-compatible defaults). New `resolve_selection(sel, selected_dir, *, resolvers=RESOLVERS, download=…) -> list[Resolved]` drives the board path; the legacy `apply_selection` (local-candidate copy) is retained for the IIIF discovery path. SKILL.md stage-5 documents: discovery builds the board (Wikidata primary), curation exports `selection.json`, resolution runs `resolve_selection`.

### Wiki — `wiki/stage-image-discovery.md`

Rewrite to the tiered model:
- Frontmatter `sources:` add `16.1-image-source-hierarchy`.
- **What the research says** — T1 Wikidata pivot (QID dedup, `creator P170`) → T2 Met/AIC/Cleveland (high-res + machine-readable rights) → T3 Commons (SDC)/Europeana → T4 discovery-only; link `[[16.1-image-source-hierarchy]]`, `[[concept-iiif]]`.
- **Open questions / tensions** — coverage gaps, namesake/foundation QID collisions, recall vs precision on attribution.
- **Skill design implications** — the two-phase spec (discover→board→curate→resolve), Wikidata-primary board with QID/inst-id dedup, copyright posture (≤843 browse, high-res only on verified PD/CC0), pluggable resolver interface.

## Testing (TDD, outside-in, pytest)

- `tests/test_wikidata.py` — fixture SPARQL JSON: QID disambiguation (Klee Q44007 vs "Zentrum Paul Klee" by work-count; zero/tie → no auto-pick), `parse_works`, `commons_filepath` encoding, `to_thumbnail_candidates`, `merge_boards` (AIC-id suppression, QID dedup, title+date fallback).
- `tests/test_resolve.py` — resolver decision tree with fixtures: Commons-PD download, AIC-PD 1686 download, in-copyright keeps `source_url` with no bytes; registry order; resolver returns None unless a PD/CC0 flag is verified.
- Update `tests/test_museum_search.py`, `tests/test_gallery.py`, `tests/test_selection.py` for the `qid`/`inst_ids` fields and export.
- All network injected; suite stays offline. Target: existing 133 tests plus new ones all green.

## Implementation plans

- **Plan A — Discovery:** `scripts/wikidata.py` (QID resolution + works SPARQL + Commons FilePath + candidates), `merge_boards`, `ThumbnailCandidate.qid`/`inst_ids`, `wiki/stage-image-discovery.md` rewrite, tests. Outcome: board is Wikidata-primary and deduped; *Fish Magic* and *The Goldfish* appear.
- **Plan B — Resolution:** `scripts/resolve.py` (Commons + AIC resolvers, registry, `resolve_selected`/`resolve_selection`), `selection.json`/`Rating` field additions, `gallery` export, SKILL.md stage-5 wiring, tests. Outcome: selected works resolve to high-res PD/CC0 downloads or graceful in-copyright source_url.

## Risks / open items

- **WDQS reliability/UA:** generic User-Agents get 403; the descriptive UA is mandatory. A WDQS timeout on a very prolific artist is possible — acceptable for now (single query, 60s budget); caching is a non-goal.
- **Commons license signal:** P18 presence does not guarantee PD/CC0; the resolver must read the file's license (extmetadata) before treating it as downloadable — reuse `commons.py` eligibility logic.
- **Attribution recall:** the precision-first Commons keyword guard (`a68a587`) can drop correct files; Wikidata-creator discovery now supersedes it for the board, improving recall for the discovery half. The keyword Commons path remains only inside the resolver.
- **Met/Cleveland deferral:** documented as pluggable; selected works held only by Met/Cleveland will keep `source_url` (no high-res) until those resolvers land.
