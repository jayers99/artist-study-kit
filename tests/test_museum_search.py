from scripts.museum_search import (
    ThumbnailCandidate,
    aic_artworks_params,
    parse_aic_search,
    pick_agent,
    resolve_aic_agent,
    search_aic,
)

# artworks/search response (agent-id query → all genuinely the artist)
AIC_WORKS = {
    "pagination": {"total": 97},
    "data": [
        {"id": 10018, "title": "Dancing Girl", "image_id": "c969-aaa", "date_display": "1940",
         "is_public_domain": False, "artist_title": "Paul Klee"},
        {"id": 61608, "title": "Sunset", "image_id": "92da-bbb", "date_display": "1930",
         "is_public_domain": False, "artist_title": "Paul Klee"},
        {"id": 999, "title": "No Image", "image_id": None, "date_display": "1925",
         "is_public_domain": False, "artist_title": "Paul Klee"},
    ],
    "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
}

# agents/search puts the foundation ('Zentrum Paul Klee') first; the artist is the exact match.
AIC_AGENTS = {"data": [
    {"id": 114514, "title": "Zentrum Paul Klee"},
    {"id": 35282, "title": "Paul Klee"},
    {"id": 4819, "title": "Paul Citroen"},
]}

# loose match[artist_title] response — leaks other 'Paul' artists
AIC_LOOSE = {
    "pagination": {"total": 300},
    "data": [
        {"id": 1, "title": "Klee work", "image_id": "k1", "date_display": "1922",
         "is_public_domain": False, "artist_title": "Paul Klee"},
        {"id": 2, "title": "Bathers", "image_id": "c1", "date_display": "1905",
         "is_public_domain": True, "artist_title": "Paul Cezanne"},
    ],
    "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
}


def test_pick_agent_takes_exact_title_match_not_first_result():
    assert pick_agent(AIC_AGENTS, "Paul Klee") == 35282  # not 114514 'Zentrum Paul Klee'


def test_pick_agent_is_accent_insensitive():
    payload = {"data": [{"id": 7, "title": "Joan Miró"}]}
    assert pick_agent(payload, "Joan Miro") == 7


def test_pick_agent_returns_none_without_exact_match():
    payload = {"data": [{"id": 1, "title": "Zentrum Paul Klee"}]}
    assert pick_agent(payload, "Paul Klee") is None


def test_aic_artworks_params_use_artist_ids_when_agent_known():
    p = aic_artworks_params(agent_id=35282, limit=100, page=2)
    assert p["query[term][artist_ids]"] == "35282"
    assert "query[match][artist_title]" not in p
    assert p["page"] == "2" and "artist_title" in p["fields"]


def test_aic_artworks_params_fall_back_to_name_match_without_agent():
    p = aic_artworks_params(agent_id=None, artist="Paul Klee")
    assert p["query[match][artist_title]"] == "Paul Klee"


def test_parse_drops_works_without_image_and_maps_rights():
    cands = parse_aic_search(AIC_WORKS)
    assert len(cands) == 2  # 'No Image' dropped
    assert all(isinstance(c, ThumbnailCandidate) for c in cands)
    first = cands[0]
    assert first.thumbnail_url == "https://www.artic.edu/iiif/2/c969-aaa/full/400,/0/default.jpg"
    assert first.source_url == "https://www.artic.edu/artworks/10018"
    assert first.rights == "in_copyright"


def test_parse_artist_guard_drops_other_artists():
    # the fallback loose path can leak other 'Paul' artists; the guard removes them
    cands = parse_aic_search(AIC_LOOSE, artist="Paul Klee")
    assert [c.title for c in cands] == ["Klee work"]  # Cezanne 'Bathers' dropped


def test_search_aic_resolves_agent_then_queries_by_artist_id():
    seen = []

    def fake_fetch(path, params):
        seen.append((path, params.get("page")))
        return AIC_AGENTS if path == "agents/search" else AIC_WORKS

    cands = search_aic("Paul Klee", pages=2, fetch=fake_fetch)
    assert ("agents/search", None) in seen
    # two artwork pages requested after the one agent lookup
    assert [p for (path, p) in seen if path == "artworks/search"] == ["1", "2"]
    assert len(cands) == 4  # 2 per page * 2 pages
    assert all(c.museum == "aic" for c in cands)


def test_resolve_aic_agent_uses_injected_fetch():
    cands = resolve_aic_agent("Paul Klee", fetch=lambda path, params: AIC_AGENTS)
    assert cands == 35282


def test_aic_candidate_carries_aic_inst_id_and_empty_qid():
    cands = parse_aic_search(AIC_WORKS)
    first = cands[0]
    assert first.qid == ""
    assert first.inst_ids == (("aic", "10018"),)


def test_aic_candidate_carries_medium():
    payload = {
        "data": [{"id": 7, "title": "Senecio", "image_id": "abc", "date_display": "1922",
                  "is_public_domain": False, "artist_title": "Paul Klee",
                  "medium_display": "Oil on gauze"}],
        "config": {"iiif_url": "https://www.artic.edu/iiif/2"},
    }
    from scripts.museum_search import parse_aic_search
    assert parse_aic_search(payload)[0].medium == "Oil on gauze"


def test_aic_fields_request_medium():
    from scripts.museum_search import AIC_FIELDS
    assert "medium_display" in AIC_FIELDS
