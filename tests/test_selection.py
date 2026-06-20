import json
from pathlib import Path

import pytest

from scripts.selection import (
    LIKED_THRESHOLD,
    Rating,
    Selection,
    apply_selection,
    liked,
    load_selection,
    parse_selection,
    validate_selection,
)


def _data(rating=5):
    return {
        "artist": "vincent-van-gogh",
        "ratings": [
            {"work_id": "wheat-field", "iiif_token": "12345",
             "image_rel": "images/candidates/wheat-field/12345.jpg",
             "rating": rating},
        ],
    }


def test_liked_work_needs_no_rationale():
    sel = Selection(artist="X", ratings=[Rating(work_id="w", iiif_token="t", image_rel="r", rating=5)])
    assert validate_selection(sel) == []  # gate removed: a liked work with no rationale is valid


def test_rating_out_of_range_still_flagged():
    sel = Selection(artist="X", ratings=[Rating(work_id="w", iiif_token="t", image_rel="r", rating=7)])
    assert any("out of range" in e for e in validate_selection(sel))


def test_missing_work_id_still_flagged():
    sel = Selection(artist="X", ratings=[Rating(work_id="", iiif_token="t", image_rel="r", rating=2)])
    assert any("missing work_id" in e for e in validate_selection(sel))


def test_parse_reads_title_date_medium_ignores_stale_gate():
    data = {"artist": "X", "ratings": [{
        "work_id": "w", "iiif_token": "t", "image_rel": "r", "rating": 5,
        "title": "Senecio", "date": "1922", "medium": "oil on gauze",
        "thesis": "stale", "anchor_trait": "stale",  # must be ignored, not error
    }]}
    r = parse_selection(data).ratings[0]
    assert (r.title, r.date, r.medium) == ("Senecio", "1922", "oil on gauze")
    assert not hasattr(r, "thesis")


def test_liked_filters_by_threshold():
    data = _data(rating=5)
    data["ratings"].append({"work_id": "irises", "iiif_token": "9", "image_rel": "x.jpg", "rating": 2})
    sel = parse_selection(data)
    assert [r.work_id for r in liked(sel)] == ["wheat-field"]


def test_load_selection_rejects_artist_mismatch(tmp_path):
    p = tmp_path / "selection.json"
    p.write_text(json.dumps(_data()), encoding="utf-8")
    with pytest.raises(ValueError):
        load_selection(p, "claude-monet")


def test_apply_selection_copies_liked_images(tmp_path):
    cdir = tmp_path / "candidates"
    (cdir / "wheat-field").mkdir(parents=True)
    (cdir / "wheat-field" / "12345.jpg").write_bytes(b"\xff\xd8\xffJPEG")
    sdir = tmp_path / "selected"
    sel = parse_selection(_data(rating=5))
    out = apply_selection(sel, cdir, sdir)
    assert out and out[0].is_file()
    assert out[0].read_bytes().startswith(b"\xff\xd8\xff")
    # idempotent: second run does not raise and returns the same path set
    assert apply_selection(sel, cdir, sdir) == out


def test_parse_selection_reads_board_provenance_fields():
    data = {
        "artist": "paul-klee",
        "ratings": [{
            "work_id": "fish-magic", "iiif_token": "phila-0",
            "image_rel": "https://commons.wikimedia.org/wiki/Special:FilePath/Fish.jpg?width=400",
            "rating": 5,
            "qid": "Q3050231", "source_url": "https://www.wikidata.org/wiki/Q3050231",
            "museum": "Philadelphia Museum of Art", "rights": "unknown",
            "inst_ids": [["commons_file", "Fish.jpg"], ["aic", "16569"]],
        }],
    }
    r = parse_selection(data).ratings[0]
    assert r.qid == "Q3050231"
    assert r.museum == "Philadelphia Museum of Art"
    assert r.inst_ids == (("commons_file", "Fish.jpg"), ("aic", "16569"))


def test_parse_selection_defaults_missing_provenance():
    r = parse_selection(_data()).ratings[0]
    assert r.qid == "" and r.inst_ids == ()


def test_ingest_selection_returns_liked_ids_and_defaults_study_set():
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", rating=5),
        Rating(work_id="b", iiif_token="", image_rel="u", rating=2),
        Rating(work_id="c", iiif_token="", image_rel="u", rating=4),
    ])
    selected, study_set = ingest_selection(sel)
    assert selected == ["a", "c"]
    assert study_set == ["a", "c"]


def test_ingest_selection_liked_only_false_keeps_all():
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", rating=5),
        Rating(work_id="b", iiif_token="", image_rel="u", rating=0),
    ])
    selected, study_set = ingest_selection(sel, liked_only=False)
    assert selected == ["a", "b"]
