---
title: "Image Discovery — cross-museum board, legally"
type: wiki/stage
stage: 5
sources: [16.1-image-source-hierarchy, 03.1-museum-image-apis, 01.1-web-scraping-tooling, 18-uat-feedback, 19-stateful-runs-custom-images-staged-analysis]
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
- **WDQS is a single point of failure (F1).** A live Klee run hit a WDQS outage: the heavy `qid_lookup_sparql` (label-filter + work-count aggregation) `504`'d while a trivial label query still `200`'d — the headline Wikidata board was unusable for the whole session ([[18-uat-feedback]]). Resolve QID via the lighter entity-search API (`wbsearchentities`) and run the work-count tiebreak only on genuine ambiguity; make AIC-only a *designed* degraded fallback (clear board banner, stage marked `degraded` in state) rather than a crash.
- **Posthumous / reproduction attribution (F3).** The surname/agent-id match let a 1972 Montgomery Ward textile "after a painting by Paul Klee" onto the board. Guard against `after | produced by | manner of | copy after | workshop of` in `artist_display`, a `date_display` year past death + margin, or a reproduction classification — flag at minimum.
- **Zero-PD artists (F5).** For artists like Klee (d. 1940) the board can be 100% in-copyright with nothing for the high-res phase to resolve; surface a board notice so the human expects analysis to lean on graded sources + reference links, not redistributed images.
- **Stateful, re-enterable discovery (request).** [[19-stateful-runs-custom-images-staged-analysis]] (Thrust 1) wants discovery to be idempotent and *mergeable across runs* (re-run after an outage clears or a new source appears; new candidates fold into the existing board, QID as the merge key) and a `degraded` stage to later **upgrade** — which presumes persisted per-artist state as the backbone. Open: state format/location and session/audit model.
- **User-supplied images as a first-class source (request).** Thrust 2 wants the user's own image folder injected as candidates, reverse-image-searched up to the same metadata shape (title/date/holding institution/medium) with a confidence flag for human confirmation (mirrors the F3 "don't trust auto-derived provenance" lesson). Open: reverse-image-search tool path, multi-artist routing, rights tagging.

## Skill design implications

Two phases:
1. **Discovery → board (rights-agnostic).** Wikidata is the primary source (`search_wikidata`): resolve the artist QID, query works, build thumbnail candidates (Commons `Special:FilePath`). AIC supplements works Wikidata lacks; `merge_boards` dedups by QID → AIC/Met inst-id → folded title+date. The board shows many thumbnails for the human to rate.
2. **Resolution → selected (rights-gated).** For each selected work, a pluggable resolver chain fetches the best legally-clear high-res: Commons P18 (PD/CC0) → AIC IIIF 1686px (`is_public_domain`) → else keep `source_url` (in-copyright, thumbnail only). Met/Cleveland resolvers drop into the same interface later.

Copyright posture: browse thumbnails ≤843px (hotlinked, for private curation); download high-res ONLY on a verified PD/CC0 flag. Capture per-image metadata: source URL, institution, license, pixel dimensions, QID, and parent work id. Never auto-select — curation is human ([[stage-curation]]).
