from scripts.user_import import ImportRow, slug_work_id, verify_identification


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
