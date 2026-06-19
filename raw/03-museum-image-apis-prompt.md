# Research prompt — Museum and image APIs for high-resolution artwork discovery

I'm building a Python tool that, given an artist and their major works, must **find and download high-resolution, legally usable images** from authoritative sources — prioritizing museums, open-access collections, and IIIF.

Research and compare the major options, including: **The Metropolitan Museum, Art Institute of Chicago, Rijksmuseum, Getty, Smithsonian, Cleveland Museum of Art, Harvard Art Museums, Europeana, Wikimedia Commons / Wikidata**, and any other strong open-access or IIIF providers I should know.

For each source, assess:
- **API type and access**: REST/GraphQL/IIIF, base endpoints, whether an API key is required, rate limits.
- **Search capability**: can I query by artist name and/or artwork title and resolve to specific objects?
- **Image access**: max resolution available; whether it exposes the **IIIF Image API** (region/size/rotation/quality parameters) for deep-zoom and large downloads.
- **Licensing**: how to determine public-domain / open-access (e.g. CC0, "Open Access" flags, rights statements) vs. restricted images.
- **Metadata**: what object metadata (date, medium, dimensions, provenance, source URL) comes back.

Also explain **IIIF itself** — Presentation vs. Image API, manifests, and how to fetch full-resolution images via IIIF URLs — since it's the common thread across many institutions.

Cover the **legal/ethical baseline**: respecting rights statements, attribution, and terms of use.

Conclude with: (a) a recommended **priority order** of sources to query, (b) a unified **strategy** for resolving "artist → important works → best available high-res image + metadata," (c) minimal example API/IIIF requests for 2–3 top sources, and (d) gaps (artists/periods poorly covered by open collections). Cite official API docs and institutional sources.
