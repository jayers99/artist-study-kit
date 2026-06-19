---
title: "Image Discovery — high-res candidates, legally"
type: wiki/stage
stage: 5
sources: [03.1-museum-image-apis, 01.1-web-scraping-tooling]
tags: [wiki/stage, technique/image-acquisition]
aliases: []
---

# Image Discovery

> [!info] Pipeline role
> For each inventory work, find and download high-resolution candidate images into a local
> gallery for human review. Emits `images/candidates/` + image metadata.

## What the research says

The acquisition mechanics live in [[concept-iiif]] (from [[03.1-museum-image-apis]]):
IIIF Image/Presentation APIs, the `info.json`-then-`max` fetch pattern, a source priority
order (Met → Rijksmuseum → AIC → Harvard/Europeana → Wikimedia), and automated rights
parsing (`isPublicDomain`, CC0, default-to-restricted).

For non-API sources and discovery on JS-heavy museum portals, [[01.1-web-scraping-tooling]]
applies: **Firecrawl `/map`** for URL discovery, **Scrapy `ImagesPipeline`** for
large-scale binary download (SHA1 dedup, size filtering, S3/GCS storage). Respect robots.txt
and rate limits (the Met allows 80 req/s; throttle others).

## Open questions / tensions

- API coverage is uneven — historical European work is well-covered; contemporary/
  non-Western often isn't. Fall back to graded web sources, but only download what rights
  permit.
- "High-resolution" is not guaranteed (`primaryImage` vs `primaryImageSmall`); validate via
  `info.json` / schema before trusting a candidate.
- Legal line: prioritize CC0/public-domain; treat missing rights as restricted.

## Skill design implications

- Resolution pipeline per work: identity-resolve (search API) → validate metadata+license →
  fetch via IIIF `max`, falling back to direct high-res links.
- Capture per-image metadata: source URL, institution, license, pixel dimensions, IIIF
  identifier, trust grade (from [[stage-source-grading]]), and the parent work id.
- Organize `images/candidates/<work>/` for the human review in [[stage-curation]]; never
  auto-select.
- Standardize on Firecrawl (discovery) + Scrapy (bulk image download) per the repo tooling
  decision; enforce rights checks and polite throttling.
