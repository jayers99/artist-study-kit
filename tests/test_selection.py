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


def _data(rating=5, **gate):
    fields = {"thesis": "studies broken color", "anchor_trait": "warm/cool value split",
              "handoff_note": "look at the sky"}
    fields.update(gate)
    return {
        "artist": "vincent-van-gogh",
        "ratings": [
            {"work_id": "wheat-field", "iiif_token": "12345",
             "image_rel": "images/candidates/wheat-field/12345.jpg",
             "rating": rating, **(fields if rating >= LIKED_THRESHOLD else {})},
        ],
    }


def test_parse_selection_reads_ratings():
    sel = parse_selection(_data())
    assert isinstance(sel, Selection)
    assert sel.artist == "vincent-van-gogh"
    assert sel.ratings[0].rating == 5
    assert sel.ratings[0].thesis == "studies broken color"


def test_parse_selection_defaults_missing_gate_fields():
    sel = parse_selection(_data(rating=2))
    assert sel.ratings[0].anchor_trait == ""


def test_validate_passes_clean_selection():
    assert validate_selection(parse_selection(_data())) == []


def test_validate_rejects_out_of_range_rating():
    sel = parse_selection(_data(rating=9))
    errs = validate_selection(sel)
    assert any("rating" in e for e in errs)


def test_validate_requires_gate_fields_when_liked():
    sel = parse_selection(_data(rating=4, thesis="", anchor_trait="", handoff_note=""))
    errs = validate_selection(sel)
    assert any("thesis" in e for e in errs)


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
