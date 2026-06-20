from scripts.user_import import ImportRow, slug_work_id, verify_identification, build_review, parse_review, make_pipeline_lookup
from scripts.museum_search import ThumbnailCandidate


def _stub_lookup(record):
    return lambda artist, title: record


def test_verify_unidentified_when_no_title():
    row = verify_identification(
        {"filename": "blur.jpg", "source_path": "/x/blur.jpg"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "unidentified"


def test_verify_off_artist_when_artist_differs():
    row = verify_identification(
        {"filename": "miro.jpg", "artist": "Joan Miro", "title": "Harlequin"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "off_artist"


def test_verify_confirmed_pulls_record_metadata():
    record = {"title": "Senecio", "date": "1922", "qid": "Q123", "museum": "aic",
              "source_url": "http://aic/senecio", "rights": "public_domain",
              "medium": "oil", "inst_ids": (("aic", "555"),)}
    row = verify_identification(
        {"filename": "senecio.jpg", "artist": "Paul Klee", "title": "Senecio"},
        "Paul Klee", lookup=_stub_lookup(record))
    assert row.state == "confirmed"
    assert row.qid == "Q123"
    assert row.source_url == "http://aic/senecio"
    assert row.rights == "public_domain"
    assert row.inst_ids == (("aic", "555"),)


def test_verify_proposed_when_no_record():
    row = verify_identification(
        {"filename": "barn.jpg", "artist": "Paul Klee", "title": "Farmhouse",
         "date": "1925"},
        "Paul Klee", lookup=_stub_lookup(None))
    assert row.state == "proposed"
    assert row.title == "Farmhouse"
    assert row.rights == "unknown"
    assert row.qid == ""


def test_import_row_roundtrips():
    row = ImportRow(filename="senecio.jpg", source_path="/x/senecio.jpg",
                    state="confirmed", artist="Paul Klee", title="Senecio",
                    date="1922", qid="Q123", museum="aic",
                    source_url="http://aic/senecio", rights="public_domain",
                    inst_ids=(("aic", "555"),), work_id="senecio")
    d = row.to_dict()
    assert d["state"] == "confirmed"
    assert d["inst_ids"] == [["aic", "555"]]
    back = ImportRow.from_dict(d)
    assert back == row


def test_slug_work_id_from_title():
    assert slug_work_id("Senecio", "img001.jpg", set()) == "senecio"


def test_slug_work_id_falls_back_to_filename():
    assert slug_work_id("", "Barn-Study.JPG", set()) == "barn-study"


def test_slug_work_id_suffixes_on_collision():
    assert slug_work_id("Senecio", "x.jpg", {"senecio"}) == "senecio-2"
    assert slug_work_id("Senecio", "x.jpg", {"senecio", "senecio-2"}) == "senecio-3"


def _rows():
    return [
        ImportRow(filename="senecio.jpg", source_path="/x/senecio.jpg",
                  state="confirmed", title="Senecio", date="1922", qid="Q123"),
        ImportRow(filename="barn.jpg", source_path="/x/barn.jpg",
                  state="proposed", title="Farmhouse", rights="unknown"),
        ImportRow(filename="miro.jpg", source_path="/x/miro.jpg",
                  state="off_artist", artist="Joan Miro", title="Harlequin"),
    ]


def test_build_review_json_and_html():
    obj, html = build_review(_rows(), "Paul Klee")
    assert obj["artist"] == "Paul Klee"
    assert [r["filename"] for r in obj["rows"]] == ["senecio.jpg", "barn.jpg", "miro.jpg"]
    assert "Senecio" in html and "off_artist" in html and "proposed" in html


def test_parse_review_keeps_only_confirmed_with_title():
    obj, _ = build_review(_rows(), "Paul Klee")
    kept = parse_review(obj)
    assert [r.filename for r in kept] == ["senecio.jpg"]


def test_parse_review_accepts_human_promoted_proposed_row():
    obj, _ = build_review(_rows(), "Paul Klee")
    obj["rows"][1]["state"] = "confirmed"   # human edited + confirmed the barn row
    kept = parse_review(obj)
    assert {r.filename for r in kept} == {"senecio.jpg", "barn.jpg"}


def test_make_pipeline_lookup_hits_and_misses():
    cand = ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="http://thumb", source_url="http://aic/senecio",
        date="1922", rights="public_domain", medium="oil", qid="Q123",
        inst_ids=(("aic", "555"),))
    lookup = make_pipeline_lookup(
        "Paul Klee",
        wikidata_search=lambda a: ([], [], []),
        aic_search=lambda a: [cand])
    rec = lookup("Paul Klee", "senecio")          # folded title match
    assert rec["qid"] == "Q123"
    assert rec["source_url"] == "http://aic/senecio"
    assert rec["inst_ids"] == (("aic", "555"),)
    assert lookup("Paul Klee", "Nonexistent Work") is None


def test_make_pipeline_lookup_survives_search_errors():
    def boom(a):
        raise RuntimeError("WDQS 504")
    lookup = make_pipeline_lookup(
        "Paul Klee", wikidata_search=boom, aic_search=lambda a: [])
    assert lookup("Paul Klee", "Senecio") is None
