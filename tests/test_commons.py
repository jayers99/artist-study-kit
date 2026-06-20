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


def test_build_search_params_requests_attribution_metadata():
    f = build_search_params("x")["iiextmetadatafilter"]
    assert "Categories" in f and "ObjectName" in f  # needed for the artist guard


def _page(title, *, license="Public domain", width=3000, height=3000,
          mediatype="BITMAP", categories="", object_name=""):
    safe = title.split(":", 1)[-1].replace(" ", "_")
    return {
        "title": title,
        "imageinfo": [{
            "url": f"https://upload.wikimedia.org/wikipedia/commons/0/00/{safe}",
            "width": width, "height": height, "mediatype": mediatype,
            "extmetadata": {
                "LicenseShortName": {"value": license},
                "Categories": {"value": categories},
                "ObjectName": {"value": object_name},
            },
        }],
    }


def _payload(*pages):
    return {"query": {"pages": {str(i): p for i, p in enumerate(pages)}}}


def test_artist_guard_drops_wrong_artist_keyword_matches():
    payload = _payload(
        _page("File:Philip IV as a Hunter - Velazquez", categories="PD-old-100-expired|Paintings by Velázquez"),
        _page("File:Joan Miro - Dona i ocell (1).jpg", categories="Dona i Ocell|FoP-Spain"),
    )
    labels = [c.label for c in parse_commons_search(payload, work_id="w", artist="Joan Miró")]
    assert any("Dona" in l for l in labels)          # the Miró-titled file kept
    assert not any("Velazquez" in l for l in labels)  # the Velázquez file dropped


def test_artist_guard_matches_via_category_when_title_lacks_name():
    payload = _payload(_page("File:Some sculpture at night.jpg", categories="Sculptures by Joan Miró|Barcelona"))
    cands = parse_commons_search(payload, work_id="w", artist="Joan Miró")
    assert len(cands) == 1  # matched on the category, not the title


def test_artist_guard_is_accent_insensitive():
    payload = _payload(_page("File:Senecio.jpg", categories="Paintings by Paul Klee"))
    assert len(parse_commons_search(payload, work_id="w", artist="Paul Klee")) == 1


def test_no_artist_means_no_filtering():
    payload = _payload(_page("File:Philip IV as a Hunter - Velazquez", categories="x"))
    assert len(parse_commons_search(payload, work_id="w")) == 1  # existing behavior preserved


def test_discover_commons_uses_injected_search():
    calls = []

    def fake_search(query, **kwargs):
        calls.append(query)
        return FIXTURE

    cands = discover_commons("Paul Klee Ancient Sound", "ancient-sound-1925", search=fake_search, want=2)
    assert calls == ["Paul Klee Ancient Sound"]
    assert [c.width for c in cands] == [4462, 3500]
