---
title: "IIIF & Open-Access Museum APIs"
type: wiki/concept
sources: [03.1-museum-image-apis]
used-by: [stage-image-discovery, stage-works-inventory]
tags: [wiki/concept, technique/image-acquisition]
aliases: ["IIIF", "Image API", "Presentation API", "Museum APIs"]
---

# IIIF & Open-Access Museum APIs

The architectural standard and source priority for fetching high-resolution artwork legally.
Source: [[03.1-museum-image-apis]]. Used by [[stage-image-discovery]] (the fetch engine)
and [[stage-works-inventory]] (image-availability metadata).

## IIIF in brief

The International Image Interoperability Framework decouples metadata from pixel delivery:

- **Presentation API (Manifest):** a JSON object — title, artist, rights, structure.
- **Image API:** binary pixels; request regions/sizes/rotations without the full file.
- **`info.json`:** query *first* to confirm max dimensions/profiles before a `max` fetch.
- **URL syntax:** `{scheme}://{server}/{prefix}/{identifier}/{region}/{size}/{rotation}/{quality}.{format}`
  — e.g. `.../full/max/0/default.png` or `.../full/max/0/gray.jpg`.

## Source priority order

1. **The Met** — RESTful, no key, 470k+ CC0 records, direct high-res JPEG (`primaryImage`).
2. **Rijksmuseum** — IIIF 3.0 (Micrio), no key, on-the-fly transforms.
3. **Art Institute of Chicago** — unified API, clear CC0, IIIF manifests.
4. **Harvard Art Museums / Europeana** — large but require API keys (friction).
5. **Wikimedia Commons** — broad fallback; weaker/looser metadata.

## Rights parsing

Parse `isPublicDomain` (Met) or "CC0 Public Domain Designation" (AIC) as download triggers;
default missing `edm:rights` (Europeana) to **restricted**. CC0 needs no attribution, but
AIC requests "Artist, Title, Date, The Art Institute of Chicago."

## Limits

Resolution varies (`primaryImage` vs `primaryImageSmall`); historical European work is
over-represented; APIs can break across versions — build version-check + error handling.
