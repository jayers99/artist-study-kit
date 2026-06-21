"""Stage-5 discovery: a broad *thumbnail board* of an artist's works for curation.

The curation gallery needs many images to scan and rate (like an image search), not the
handful of downloadable public-domain files. Museums expose thumbnails for *every* work
regardless of copyright, so we search by artist and collect thumbnail + source URLs here.
Rights only matter later, when the user's *selected* works are resolved to high-res.

AIC (Art Institute of Chicago) is the primary source. Its `artist_title` match is fuzzy
(it pulls in every other 'Paul'), so we resolve the artist to an AIC **agent id** by exact
title match and query by `artist_ids`, with a surname guard as backstop. Pure parsing is
fixture-tested; the network boundary (`fetch(path, params)`) is injected.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

from scripts.paths import slugify

AIC_BASE = "https://api.artic.edu/api/v1"
AIC_FIELDS = "id,title,image_id,date_display,is_public_domain,artist_title,medium_display"
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
    medium: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()


def _fold(text: str) -> str:
    """Accent-fold to lowercase ASCII so 'Miró' and 'Miro' compare equal."""
    return unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").lower()


# IIIF Image API URL: {id}/{region}/{size}/{rotation}/{quality}.{fmt}; swap the size.
_IIIF_SIZE = re.compile(r"(/full/)[^/]+(/\d+/default\.\w+)$")
_DISPLAY_SIZE = "843,"


def display_url(candidate) -> str:
    """Best-effort largest *display* image for close looking (hotlinked, display-only).

    IIIF sources -> swap the thumbnail size segment for ~843px; user images -> their
    local file; everything else -> the thumbnail URL unchanged. No network."""
    if getattr(candidate, "origin", "discovered") == "user":
        local = getattr(candidate, "local_path", "")
        if local:
            return local
    url = getattr(candidate, "thumbnail_url", "") or ""
    if _IIIF_SIZE.search(url):
        return _IIIF_SIZE.sub(rf"\g<1>{_DISPLAY_SIZE}\g<2>", url)
    return url


def aic_agent_params(artist: str) -> dict:
    """Params to look an artist up in the AIC agents (people) index."""
    return {"q": artist, "fields": "id,title", "limit": "10"}


def pick_agent(payload: dict, artist: str) -> int | None:
    """Pick the agent whose title *exactly* matches the artist (accent-folded).

    The top search hit is often the wrong agent (e.g. 'Zentrum Paul Klee' for 'Paul Klee'),
    so match on title equality rather than rank.
    """
    target = _fold(artist)
    for agent in payload.get("data", []):
        if _fold(agent.get("title", "")) == target:
            return agent.get("id")
    return None


def aic_artworks_params(*, agent_id: int | None = None, artist: str | None = None,
                        limit: int = 100, page: int = 1) -> dict:
    """Artwork-search params: by agent id when known (precise), else fuzzy name match."""
    params = {"fields": AIC_FIELDS, "limit": str(limit), "page": str(page)}
    if agent_id is not None:
        params["query[term][artist_ids]"] = str(agent_id)
    elif artist:
        params["query[match][artist_title]"] = artist
    return params


def _artist_ok(artist: str | None, artist_title: str | None) -> bool:
    """Backstop guard: the artist's surname must appear in the work's artist_title."""
    if not artist:
        return True
    return _fold(artist).split()[-1] in _fold(artist_title or "")


def parse_aic_search(payload: dict, *, artist: str | None = None,
                     thumb_width: int = 400) -> list[ThumbnailCandidate]:
    """Flatten an AIC artwork response into thumbnail candidates (works with an image).

    When `artist` is given, drop works whose artist_title doesn't carry the surname — guards
    the fuzzy-match fallback against other artists bleeding in.
    """
    iiif = (payload.get("config") or {}).get("iiif_url") or AIC_IIIF_DEFAULT
    out: list[ThumbnailCandidate] = []
    for d in payload.get("data", []):
        image_id = d.get("image_id")
        if not image_id:
            continue
        if not _artist_ok(artist, d.get("artist_title")):
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
                medium=str(d.get("medium_display") or ""),
                inst_ids=(("aic", str(d.get("id"))),),
            )
        )
    return out


def default_aic_fetch(path: str, params: dict) -> dict:
    """Real AIC fetch (httpx) against an API path. Not exercised in tests."""
    import httpx

    user_agent = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"
    resp = httpx.get(f"{AIC_BASE}/{path}", params=params, headers={"User-Agent": user_agent}, timeout=40.0)
    resp.raise_for_status()
    return resp.json()


def resolve_aic_agent(artist: str, *, fetch=default_aic_fetch) -> int | None:
    """Resolve an artist name to its AIC agent id (None if no exact match)."""
    return pick_agent(fetch("agents/search", aic_agent_params(artist)), artist)


def search_aic(
    artist: str,
    *,
    pages: int = 1,
    fetch=default_aic_fetch,
    thumb_width: int = 400,
) -> list[ThumbnailCandidate]:
    """Search AIC for an artist's works → thumbnail candidates.

    Resolves the AIC agent id first (precise); falls back to a name match (guarded by
    surname) when the artist isn't an indexed agent.
    """
    agent_id = resolve_aic_agent(artist, fetch=fetch)
    out: list[ThumbnailCandidate] = []
    for page in range(1, pages + 1):
        payload = fetch("artworks/search", aic_artworks_params(
            agent_id=agent_id, artist=artist, limit=100, page=page))
        out.extend(parse_aic_search(payload, artist=artist, thumb_width=thumb_width))
    return out
