"""Stage-5 fallback: discover public-domain images on Wikimedia Commons.

The priority-museum IIIF path returns nothing for artists still in copyright (e.g. Klee,
d. 1940 — museums flag every work non-public-domain). Commons (itself a priority
institution) hosts faithful PD-Art reproductions of the pre-copyright works, so this
module queries the MediaWiki API and yields validated `ImageCandidate`s for the same
download path as `iiif`/`image_download`.

Pure parsing (`parse_commons_search`) is fixture-tested; the network boundary
(`default_search`) is injected so tests never hit live Commons. Non-image mediatypes
(PDF catalogues, etc.) are screened out at discovery — not left for the download guard.
"""

from __future__ import annotations

from scripts.iiif import ImageCandidate, classify_rights

COMMONS_API = "https://commons.wikimedia.org/w/api.php"

# Commons mediatypes worth downloading as study images (drawings + raster scans).
ALLOWED_MEDIATYPES: frozenset[str] = frozenset({"BITMAP", "DRAWING"})


def build_search_params(query: str, *, limit: int = 8) -> dict:
    """MediaWiki API params: search the File namespace, return imageinfo per hit."""
    return {
        "action": "query",
        "format": "json",
        "generator": "search",
        "gsrsearch": query,
        "gsrnamespace": "6",  # File:
        "gsrlimit": str(limit),
        "prop": "imageinfo",
        "iiprop": "url|size|mediatype|extmetadata",
        "iiextmetadatafilter": "LicenseShortName|UsageTerms",
    }


def _label(title: str) -> str:
    """`File:Foo bar.jpg` -> `Foo bar`."""
    return title.split(":", 1)[-1].rsplit(".", 1)[0]


def _eligible(imageinfo: dict, *, min_long_edge: int, include_cc: bool) -> tuple[bool, str, str]:
    """Return (ok, license_str, rights_status) for one imageinfo record."""
    url = imageinfo.get("url")
    if not url:
        return False, "", "restricted"
    mediatype = imageinfo.get("mediatype")
    if mediatype and mediatype not in ALLOWED_MEDIATYPES:
        return False, "", "restricted"  # PDFs / video / audio — not study images
    long_edge = max(int(imageinfo.get("width", 0)), int(imageinfo.get("height", 0)))
    if long_edge < min_long_edge:
        return False, "", "restricted"
    license_str = ((imageinfo.get("extmetadata") or {}).get("LicenseShortName") or {}).get("value", "")
    rights = classify_rights(license_str)
    if rights == "restricted":
        return False, license_str, rights
    if rights != "public_domain" and not include_cc:
        return False, license_str, rights  # CC-licensed; only kept when include_cc
    return True, license_str, rights


def parse_commons_search(
    payload: dict,
    *,
    work_id: str,
    want: int = 3,
    min_long_edge: int = 1500,
    include_cc: bool = False,
) -> list[ImageCandidate]:
    """Flatten a MediaWiki imageinfo response into ranked, validated candidates.

    Public-domain (PD/CC0) only by default; `include_cc=True` also keeps CC-licensed
    images (rights_status `unknown`, usable with attribution). Largest first, capped to
    `want`, with unique per-candidate iiif tokens so downloads don't collide.
    """
    pages = (payload.get("query") or {}).get("pages") or {}
    scored: list[tuple[int, str, int, int, str, str]] = []
    for page in pages.values():
        info = (page.get("imageinfo") or [{}])[0]
        ok, license_str, rights = _eligible(info, min_long_edge=min_long_edge, include_cc=include_cc)
        if not ok:
            continue
        w, h = int(info["width"]), int(info["height"])
        scored.append((max(w, h), info["url"], w, h, license_str, _label(page.get("title", ""))))

    scored.sort(key=lambda r: r[0], reverse=True)

    candidates: list[ImageCandidate] = []
    for n, (_, url, w, h, license_str, label) in enumerate(scored[:want], start=1):
        suffix = "" if n == 1 else f"-{n}"
        candidates.append(
            ImageCandidate(
                work_id=work_id,
                institution="wikimedia",
                label=label,
                iiif_id=f"wikimedia/{work_id}{suffix}",
                image_url=url,
                width=w,
                height=h,
                license=license_str,
                rights_status=classify_rights(license_str),
            )
        )
    return candidates


def default_search(query: str, *, limit: int = 8) -> dict:
    """Real MediaWiki search (httpx). Not exercised in tests."""
    import httpx

    user_agent = (
        "artist-study-kit/1.0 (studio-prep research; "
        "+https://github.com/jayers99/artist-study-kit)"
    )
    resp = httpx.get(
        COMMONS_API,
        params=build_search_params(query, limit=limit),
        headers={"User-Agent": user_agent},
        timeout=40.0,
    )
    resp.raise_for_status()
    return resp.json()


def discover_commons(
    query: str,
    work_id: str,
    *,
    search=default_search,
    want: int = 3,
    min_long_edge: int = 1500,
    include_cc: bool = False,
) -> list[ImageCandidate]:
    """Search Commons for `query` and return candidates for `work_id`."""
    payload = search(query)
    return parse_commons_search(
        payload,
        work_id=work_id,
        want=want,
        min_long_edge=min_long_edge,
        include_cc=include_cc,
    )
