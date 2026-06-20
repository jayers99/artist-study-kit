"""Stage-5 Tier-1 discovery: Wikidata as the curation board's primary source.

Wikidata is the "pivot/identity layer" (raw/16.1-image-source-hierarchy): a `creator
(P170)` SPARQL query returns an artist's works across every holding institution, with the
QID as the universal dedup key. Pure parsing/builders are fixture-tested; the network
boundary (`default_sparql`) is injected so tests never hit live WDQS.
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import quote, unquote

COMMONS_FILEPATH = "https://commons.wikimedia.org/wiki/Special:FilePath"
WDQS = "https://query.wikidata.org/sparql"
USER_AGENT = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"


def commons_filepath(filename: str, *, width: int = 400) -> str:
    """Thumbnail/full URL for a Commons file via Special:FilePath."""
    name = quote(filename.strip().replace(" ", "_"), safe="")
    return f"{COMMONS_FILEPATH}/{name}?width={width}"


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
