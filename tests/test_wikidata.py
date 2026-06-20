from scripts.museum_search import ThumbnailCandidate
from scripts.wikidata import (
    ArtistEntity,
    WikidataWork,
    commons_filepath,
    parse_qid_candidates,
    parse_works,
    resolve_qid,
    to_thumbnail_candidates,
)


def test_commons_filepath_encodes_spaces_and_adds_width():
    url = commons_filepath("Paul Klee Fish Magic.jpg")
    assert url == ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   "Paul_Klee_Fish_Magic.jpg?width=400")


def test_commons_filepath_urlencodes_reserved_chars_and_custom_width():
    url = commons_filepath("Müller & Sohn.jpg", width=1686)
    assert url.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
    assert "M%C3%BCller_%26_Sohn.jpg" in url
    assert url.endswith("?width=1686")


# WDQS JSON: the painter Q44007 has many works; the foundation Q706082 has none.
QID_KLEE = {"results": {"bindings": [
    {"item": {"value": "http://www.wikidata.org/entity/Q44007"},
     "itemLabel": {"value": "Paul Klee"},
     "itemDescription": {"value": "Swiss-German artist (1879-1940)"},
     "occLabel": {"value": "painter"},
     "works": {"value": "671"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q706082"},
     "itemLabel": {"value": "Zentrum Paul Klee"},
     "itemDescription": {"value": "art museum in Bern"},
     "occLabel": {"value": ""},
     "works": {"value": "0"}},
]}}

QID_TIE = {"results": {"bindings": [
    {"item": {"value": "http://www.wikidata.org/entity/Q1"}, "itemLabel": {"value": "John Smith"},
     "itemDescription": {"value": "painter"}, "occLabel": {"value": "painter"}, "works": {"value": "12"}},
    {"item": {"value": "http://www.wikidata.org/entity/Q2"}, "itemLabel": {"value": "John Smith"},
     "itemDescription": {"value": "illustrator"}, "occLabel": {"value": "illustrator"}, "works": {"value": "8"}},
]}}

QID_NONE = {"results": {"bindings": []}}


def test_parse_qid_candidates_reads_uri_tail_and_workcount():
    cands = parse_qid_candidates(QID_KLEE)
    assert cands[0] == ArtistEntity("Q44007", "Paul Klee",
                                    "Swiss-German artist (1879-1940)", "painter", 671)


def test_resolve_qid_autopicks_sole_creator():
    qid, cands = resolve_qid("Paul Klee", query=lambda q: QID_KLEE)
    assert qid == "Q44007"          # not the foundation Q706082
    assert len(cands) == 2


def test_resolve_qid_surfaces_on_tie():
    qid, cands = resolve_qid("John Smith", query=lambda q: QID_TIE)
    assert qid is None              # two candidates have works → ambiguous
    assert [c.qid for c in cands] == ["Q1", "Q2"]


def test_resolve_qid_returns_none_when_no_candidates():
    qid, cands = resolve_qid("Nobody", query=lambda q: QID_NONE)
    assert qid is None and cands == []


WORKS = {"results": {"bindings": [
    {"work": {"value": "http://www.wikidata.org/entity/Q3050231"},
     "workLabel": {"value": "Fish Magic"},
     "image": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Paul%20Klee%2C%20Fish%20Magic.jpg"},
     "collectionLabel": {"value": "Philadelphia Museum of Art"},
     "inception": {"value": "1925-01-01T00:00:00Z"},
     "aic": {"value": "no"}},
    {"work": {"value": "http://www.wikidata.org/entity/Q123"},
     "workLabel": {"value": "Senecio"},
     "image": {"value": "http://commons.wikimedia.org/wiki/Special:FilePath/Senecio.jpg"},
     "collectionLabel": {"value": "Kunstmuseum Basel"},
     "inception": {"value": "1922-01-01T00:00:00Z"},
     "aic": {"value": "16569"}},
    {"work": {"value": "http://www.wikidata.org/entity/Q999"},
     "workLabel": {"value": "Lost Work"}},  # no image → image_file ""
]}}


def test_parse_works_extracts_filename_year_and_collection():
    works = parse_works(WORKS)
    assert works[0] == WikidataWork(
        qid="Q3050231", title="Fish Magic", image_file="Paul Klee, Fish Magic.jpg",
        collection="Philadelphia Museum of Art", date="1925", aic_id="", met_id="")


def test_parse_works_keeps_aic_id_and_imageless_work():
    works = parse_works(WORKS)
    assert works[1].aic_id == "16569"
    assert works[2].image_file == "" and works[2].title == "Lost Work"


def test_to_thumbnail_candidates_builds_board_entries():
    works = parse_works(WORKS)
    cands = to_thumbnail_candidates(works)
    assert len(cands) == 2  # imageless 'Lost Work' dropped
    fish = cands[0]
    assert isinstance(fish, ThumbnailCandidate)
    assert fish.qid == "Q3050231"
    assert fish.museum == "Philadelphia Museum of Art"
    assert fish.source_url == "https://www.wikidata.org/wiki/Q3050231"
    assert fish.rights == "unknown"
    assert fish.thumbnail_url.endswith("Paul_Klee%2C_Fish_Magic.jpg?width=400")
    assert ("commons_file", "Paul Klee, Fish Magic.jpg") in fish.inst_ids


def test_to_thumbnail_candidates_includes_aic_inst_id():
    senecio = to_thumbnail_candidates(parse_works(WORKS))[1]
    assert ("aic", "16569") in senecio.inst_ids
    assert ("commons_file", "Senecio.jpg") in senecio.inst_ids
