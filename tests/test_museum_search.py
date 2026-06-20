from scripts.museum_search import (
    ThumbnailCandidate,
    aic_search_params,
    parse_aic_search,
    search_aic,
)

AIC_PAYLOAD = {
    "pagination": {"total": 1254},
    "data": [
        {"id": 10018, "title": "Dancing Girl", "image_id": "c969-aaa", "date_display": "1940", "is_public_domain": False},
        {"id": 61608, "title": "Sunset", "image_id": "92da-bbb", "date_display": "1930", "is_public_domain": True},
        {"id": 999, "title": "No Image Work", "image_id": None, "date_display": "1925", "is_public_domain": True},
    ],
    "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
}


def test_parse_aic_yields_thumbnail_candidates():
    cands = parse_aic_search(AIC_PAYLOAD)
    assert all(isinstance(c, ThumbnailCandidate) for c in cands)
    first = cands[0]
    assert first.title == "Dancing Girl"
    assert first.museum == "aic"
    assert first.thumbnail_url == "https://www.artic.edu/iiif/2/c969-aaa/full/400,/0/default.jpg"
    assert first.source_url == "https://www.artic.edu/artworks/10018"
    assert first.date == "1940"


def test_parse_aic_drops_works_without_image():
    cands = parse_aic_search(AIC_PAYLOAD)
    assert len(cands) == 2  # the image_id=None work is dropped
    assert all(c.thumbnail_url for c in cands)


def test_parse_aic_maps_rights_from_public_domain_flag():
    by_title = {c.title: c for c in parse_aic_search(AIC_PAYLOAD)}
    assert by_title["Dancing Girl"].rights == "in_copyright"
    assert by_title["Sunset"].rights == "public_domain"


def test_parse_aic_respects_thumb_width():
    c = parse_aic_search(AIC_PAYLOAD, thumb_width=843)[0]
    assert "/full/843,/0/default.jpg" in c.thumbnail_url


def test_aic_search_params_match_artist_title():
    p = aic_search_params("Paul Klee", limit=100, page=2)
    assert p["query[match][artist_title]"] == "Paul Klee"
    assert p["limit"] == "100"
    assert p["page"] == "2"
    assert "image_id" in p["fields"]


def test_search_aic_paginates_with_injected_fetch():
    calls = []

    def fake_fetch(params):
        calls.append(params["page"])
        return AIC_PAYLOAD

    cands = search_aic("Paul Klee", limit=100, pages=3, fetch=fake_fetch)
    assert calls == ["1", "2", "3"]
    assert len(cands) == 6  # 2 per page * 3 pages
