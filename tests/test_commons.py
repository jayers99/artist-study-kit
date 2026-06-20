import json
from pathlib import Path

from scripts.commons import (
    build_search_params,
    discover_commons,
    parse_commons_search,
)
from scripts.iiif import validate_candidate

FIXTURE = json.loads((Path(__file__).parent / "fixtures" / "commons_search.json").read_text())


def test_parse_returns_public_domain_highres_candidates():
    cands = parse_commons_search(FIXTURE, work_id="ancient-sound-1925")
    # the two PD bitmaps over 1500px, largest first
    assert [c.width for c in cands] == [4462, 3500]
    top = cands[0]
    assert top.work_id == "ancient-sound-1925"
    assert top.institution == "wikimedia"
    assert top.rights_status == "public_domain"
    assert top.image_url.endswith("Ancient_Sound.jpg")
    assert validate_candidate(top)[0] is True


def test_parse_filters_low_resolution():
    cands = parse_commons_search(FIXTURE, work_id="w", min_long_edge=1500)
    assert all(max(c.width, c.height) >= 1500 for c in cands)
    assert not any("thumb" in c.image_url for c in cands)  # the 800px PD image dropped


def test_parse_skips_non_image_mediatypes():
    cands = parse_commons_search(FIXTURE, work_id="w", want=10)
    # the PDF (mediatype OFFICE) must never become a candidate
    assert not any(c.image_url.endswith(".pdf") for c in cands)


def test_parse_excludes_cc_by_default_includes_with_flag():
    pd_only = parse_commons_search(FIXTURE, work_id="w", want=10)
    assert all(c.rights_status == "public_domain" for c in pd_only)

    with_cc = parse_commons_search(FIXTURE, work_id="w", want=10, include_cc=True)
    cc = [c for c in with_cc if "ccbysa" in c.image_url]
    assert len(cc) == 1
    assert cc[0].rights_status == "unknown"  # usable-with-attribution, flagged


def test_parse_caps_to_want_and_assigns_unique_tokens():
    cands = parse_commons_search(FIXTURE, work_id="ancient-sound-1925", want=2)
    assert len(cands) == 2
    tokens = [c.iiif_id.rsplit("/", 1)[-1] for c in cands]
    assert tokens == ["ancient-sound-1925", "ancient-sound-1925-2"]
    assert len(set(tokens)) == 2


def test_build_search_params_targets_files_with_imageinfo():
    params = build_search_params("Paul Klee Ancient Sound")
    assert params["generator"] == "search"
    assert params["gsrnamespace"] == "6"  # File namespace
    assert "size" in params["iiprop"] and "extmetadata" in params["iiprop"]
    assert "mediatype" in params["iiprop"]  # needed to screen out PDFs
    assert params["gsrsearch"] == "Paul Klee Ancient Sound"


def test_discover_commons_uses_injected_search():
    calls = []

    def fake_search(query, **kwargs):
        calls.append(query)
        return FIXTURE

    cands = discover_commons("Paul Klee Ancient Sound", "ancient-sound-1925", search=fake_search, want=2)
    assert calls == ["Paul Klee Ancient Sound"]
    assert [c.width for c in cands] == [4462, 3500]
