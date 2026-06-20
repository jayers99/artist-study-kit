from scripts.user_import import ImportRow, slug_work_id


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
