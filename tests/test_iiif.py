import json
from pathlib import Path

from scripts.iiif import (
    INSTITUTION_PRIORITY,
    ImageCandidate,
    classify_rights,
    institution_rank,
    max_image_url,
    meets_resolution,
    parse_info_json,
    parse_manifest,
    validate_candidate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _manifest():
    return json.loads((FIXTURES / "met_manifest.json").read_text())


def _info():
    return json.loads((FIXTURES / "met_info.json").read_text())


def test_priority_order_matches_spec():
    assert INSTITUTION_PRIORITY == ("met", "rijksmuseum", "aic", "harvard", "europeana", "wikimedia")


def test_institution_rank_orders_and_sinks_unknown():
    assert institution_rank("met") < institution_rank("wikimedia")
    assert institution_rank("unknown-museum") > institution_rank("wikimedia")


def test_classify_rights_public_domain_variants():
    assert classify_rights("Public Domain") == "public_domain"
    assert classify_rights("CC0 1.0") == "public_domain"
    assert classify_rights("https://creativecommons.org/publicdomain/zero/1.0/") == "public_domain"


def test_classify_rights_missing_is_restricted():
    assert classify_rights(None) == "restricted"
    assert classify_rights("") == "restricted"


def test_classify_rights_unrecognized_is_unknown():
    assert classify_rights("All rights reserved") == "unknown"


def test_max_image_url_builds_iiif_max_request():
    assert max_image_url("https://images.metmuseum.org/iiif/12345") == (
        "https://images.metmuseum.org/iiif/12345/full/max/0/default.jpg"
    )


def test_parse_info_json_extracts_id_and_dims():
    iiif_id, w, h = parse_info_json(_info())
    assert iiif_id == "https://images.metmuseum.org/iiif/12345"
    assert (w, h) == (4000, 3000)


def test_parse_manifest_yields_candidate():
    cands = parse_manifest(_manifest(), work_id="wheat-field-with-cypresses", institution="met")
    assert len(cands) == 1
    c = cands[0]
    assert isinstance(c, ImageCandidate)
    assert c.institution == "met"
    assert c.work_id == "wheat-field-with-cypresses"
    assert c.iiif_id == "https://images.metmuseum.org/iiif/12345"
    assert c.image_url.endswith("/full/max/0/default.jpg")
    assert (c.width, c.height) == (4000, 3000)
    assert c.rights_status == "public_domain"


def test_meets_resolution_uses_long_edge():
    big = ImageCandidate("w", "met", "l", "id", "u", 4000, 3000, "Public Domain", "public_domain")
    small = ImageCandidate("w", "met", "l", "id", "u", 800, 600, "Public Domain", "public_domain")
    assert meets_resolution(big) is True
    assert meets_resolution(small) is False


def test_validate_candidate_flags_restricted_and_lowres():
    ok = ImageCandidate("w", "met", "l", "id", "u", 4000, 3000, "Public Domain", "public_domain")
    passed, reasons = validate_candidate(ok)
    assert passed is True
    assert reasons == []

    bad = ImageCandidate("w", "met", "l", "id", "u", 500, 400, None, "restricted")
    passed, reasons = validate_candidate(bad)
    assert passed is False
    assert any("rights" in r for r in reasons)
    assert any("resolution" in r for r in reasons)
