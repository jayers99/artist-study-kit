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
