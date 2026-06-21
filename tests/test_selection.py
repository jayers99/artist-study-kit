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


def test_apply_selection_copies_selected_images(tmp_path):
    cdir = tmp_path / "candidates"
    (cdir / "wheat-field").mkdir(parents=True)
    (cdir / "wheat-field" / "12345.jpg").write_bytes(b"img")
    sdir = tmp_path / "selected"
    sel = parse_selection({
        "artist": "x",
        "ratings": [{"work_id": "wheat-field", "iiif_token": "12345",
                     "image_rel": "images/candidates/wheat-field/12345.jpg",
                     "selected": True}],
    })
    out = apply_selection(sel, cdir, sdir)
    assert len(out) == 1 and out[0].is_file()
    assert apply_selection(sel, cdir, sdir) == out   # idempotent


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


def test_parse_selection_reads_selected_and_stars():
    r = parse_selection({"artist": "x", "ratings": [
        {"work_id": "w", "iiif_token": "t", "image_rel": "r", "selected": True, "stars": 3},
    ]}).ratings[0]
    assert r.selected is True
    assert r.stars == 3


def test_ingest_selection_returns_selected_ids_and_defaults_study_set():
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", selected=True),
        Rating(work_id="b", iiif_token="", image_rel="u", selected=False),
        Rating(work_id="c", iiif_token="", image_rel="u", selected=True),
    ])
    selected, study_set = ingest_selection(sel)
    assert selected == ["a", "c"]
    assert study_set == ["a", "c"]


def test_ingest_selection_ignores_stars_entirely():
    # orthogonality: a 5-star work that is NOT selected stays out; a 1-star
    # SELECTED work goes in. Stars never drive selection.
    from scripts.selection import ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="hi", iiif_token="", image_rel="u", stars=5, selected=False),
        Rating(work_id="lo", iiif_token="", image_rel="u", stars=1, selected=True),
    ])
    selected, _ = ingest_selection(sel)
    assert selected == ["lo"]


def test_parse_study_set_returns_ids_truncated_to_max():
    from scripts.selection import parse_study_set
    data = {"artist": "x", "study_set": ["a", "b", "c", "d", "e"]}
    assert parse_study_set(data) == ["a", "b", "c", "d"]            # default max 4
    assert parse_study_set(data, max_study=2) == ["a", "b"]


def test_load_study_set_reads_file_and_checks_artist(tmp_path):
    import json as _json
    from scripts.selection import load_study_set
    p = tmp_path / "study-set.json"
    p.write_text(_json.dumps({"artist": "x", "study_set": ["a", "b"]}), encoding="utf-8")
    assert load_study_set(p, "x") == ["a", "b"]


def test_load_study_set_artist_mismatch_raises(tmp_path):
    import json as _json
    import pytest
    from scripts.selection import load_study_set
    p = tmp_path / "study-set.json"
    p.write_text(_json.dumps({"artist": "other", "study_set": ["a"]}), encoding="utf-8")
    with pytest.raises(ValueError):
        load_study_set(p, "x")


def test_apply_selection_only_filters_to_study_set(tmp_path):
    cdir = tmp_path / "candidates"
    for wid in ("a", "b"):
        (cdir / wid).mkdir(parents=True)
        (cdir / wid / "t.jpg").write_bytes(b"img")
    sdir = tmp_path / "selected"
    sel = parse_selection({"artist": "x", "ratings": [
        {"work_id": "a", "iiif_token": "t", "image_rel": "images/candidates/a/t.jpg", "selected": True},
        {"work_id": "b", "iiif_token": "t", "image_rel": "images/candidates/b/t.jpg", "selected": True},
    ]})
    out = apply_selection(sel, cdir, sdir, only={"a"})
    assert len(out) == 1 and out[0].name.startswith("a-")
