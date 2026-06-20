# 16 — Image source hierarchy (research prompt)

**Context:** artist-study-kit, given a historical artist, must (a) discover images of
that artist's important works across ALL holding institutions to fill a visual "curation
board" (many thumbnails a human rates), then (b) resolve the few selected works to the
best high-resolution reference, respecting copyright. Today it searches only the Art
Institute of Chicago, so works held elsewhere (e.g. Klee's *Fish Magic* at Philadelphia,
*The Goldfish* at the Hamburger Kunsthalle) are invisible.

**Research question:** What are the best PRIMARY sources (institutions that hold and
digitize artworks) and SECONDARY / aggregator sources (cross-institution catalogs) for
programmatically discovering an artist's oeuvre and obtaining images? Propose a ranked
SOURCE HIERARCHY for an automated pipeline.

Rank each source on: (1) coverage of an artist's complete works; (2) attribution
precision — can we query reliably by artist via stable creator IDs and avoid wrong-artist
results?; (3) image availability and resolution (thumbnail vs IIIF high-res); (4)
licensing / rights clarity (public-domain flags, CC, in-copyright handling); (5) API
access — open API, SPARQL, auth/keys, rate limits, and terms of use about hotlinking
thumbnails for private curation; (6) metadata quality and canonical identifiers (Wikidata
QIDs) for cross-source deduplication.

Cover at least: Wikidata (SPARQL, creator P170), Wikimedia Commons (categories, structured
data) and Wikipedia; major museum open-access APIs (Met, Art Institute of Chicago,
Rijksmuseum, Harvard, Cleveland, Smithsonian, National Gallery of Art, Getty, Yale, MoMA,
Tate, Philadelphia, Hamburger Kunsthalle); aggregators (Europeana, Google Arts & Culture,
DPLA, WikiArt, Artsy); and general image search (Google / Bing image search APIs),
including the legality of thumbnail use.

**Deliver:** a tiered recommendation (primary vs secondary; query order), per-source
strengths and limits, and a strategy for combining sources — Wikidata-QID deduplication,
attribution verification, and copyright posture (browse thumbnails broadly; download
high-res only when free). Note any sources to avoid.
