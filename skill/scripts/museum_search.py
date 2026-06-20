"""Stage-5 discovery: a broad *thumbnail board* of an artist's works for curation.

The curation gallery needs many images to scan and rate (like an image search), not the
handful of downloadable public-domain files. Museums expose thumbnails for *every* work
regardless of copyright, so we search by artist and collect thumbnail + source URLs here.
Rights only matter later, when the user's *selected* works are resolved to high-res.

AIC (Art Institute of Chicago) is the primary source — large holdings, one search returns
100 works with thumbnails. Pure parsing is fixture-tested; the network boundary is injected.
"""

from __future__ import annotations

from dataclasses import dataclass

from scripts.paths import slugify

AIC_API = "https://api.artic.edu/api/v1/artworks/search"
AIC_FIELDS = "id,title,image_id,date_display,is_public_domain"
AIC_IIIF_DEFAULT = "https://www.artic.edu/iiif/2"


@dataclass(frozen=True)
class ThumbnailCandidate:
    work_id: str
    title: str
    museum: str
    thumbnail_url: str
    source_url: str
    date: str
    rights: str  # public_domain | in_copyright | unknown


def aic_search_params(artist: str, *, limit: int = 100, page: int = 1) -> dict:
    """AIC artworks/search params matching on the artist name (not free text)."""
    return {
        "query[match][artist_title]": artist,
        "fields": AIC_FIELDS,
        "limit": str(limit),
        "page": str(page),
    }


def parse_aic_search(payload: dict, *, thumb_width: int = 400) -> list[ThumbnailCandidate]:
    """Flatten an AIC search response into thumbnail candidates (works with an image)."""
    iiif = (payload.get("config") or {}).get("iiif_url") or AIC_IIIF_DEFAULT
    out: list[ThumbnailCandidate] = []
    for d in payload.get("data", []):
        image_id = d.get("image_id")
        if not image_id:
            continue
        title = d.get("title") or "Untitled"
        out.append(
            ThumbnailCandidate(
                work_id=slugify(title) or f"aic-{d.get('id')}",
                title=title,
                museum="aic",
                thumbnail_url=f"{iiif}/{image_id}/full/{thumb_width},/0/default.jpg",
                source_url=f"https://www.artic.edu/artworks/{d.get('id')}",
                date=str(d.get("date_display") or ""),
                rights="public_domain" if d.get("is_public_domain") else "in_copyright",
            )
        )
    return out


def default_aic_fetch(params: dict) -> dict:
    """Real AIC fetch (httpx). Not exercised in tests."""
    import httpx

    user_agent = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"
    resp = httpx.get(AIC_API, params=params, headers={"User-Agent": user_agent}, timeout=40.0)
    resp.raise_for_status()
    return resp.json()


def search_aic(
    artist: str,
    *,
    limit: int = 100,
    pages: int = 1,
    fetch=default_aic_fetch,
    thumb_width: int = 400,
) -> list[ThumbnailCandidate]:
    """Search AIC for an artist across `pages` of `limit` results -> thumbnail candidates."""
    out: list[ThumbnailCandidate] = []
    for page in range(1, pages + 1):
        payload = fetch(aic_search_params(artist, limit=limit, page=page))
        out.extend(parse_aic_search(payload, thumb_width=thumb_width))
    return out
