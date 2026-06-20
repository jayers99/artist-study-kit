from scripts.wikidata import (
    ArtistEntity,
    commons_filepath,
    parse_qid_candidates,
    resolve_qid,
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
