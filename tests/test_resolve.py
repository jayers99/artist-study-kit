from scripts.iiif import ImageCandidate
from scripts.resolve import commons_resolver, aic_resolver
from scripts.selection import Rating


def _entry(**kw):
    base = dict(work_id="fish-magic", iiif_token="t", image_rel="r", rating=5,
                source_url="https://www.wikidata.org/wiki/Q1", inst_ids=())
    base.update(kw)
    return Rating(**base)


def _commons_payload(license_name):
    return {"query": {"pages": {"42": {
        "title": "File:Fish Magic.jpg",
        "imageinfo": [{
            "url": "https://upload.wikimedia.org/fish-magic.jpg",
            "width": 4000, "height": 3000, "mediatype": "BITMAP",
            "extmetadata": {"LicenseShortName": {"value": license_name}},
        }],
    }}}}


def test_commons_resolver_returns_pd_candidate():
    entry = _entry(inst_ids=(("commons_file", "Fish Magic.jpg"),))
    cand = commons_resolver(entry, fetch=lambda fn: _commons_payload("Public domain"))
    assert isinstance(cand, ImageCandidate)
    assert cand.image_url == "https://upload.wikimedia.org/fish-magic.jpg"
    assert cand.rights_status == "public_domain"


def test_commons_resolver_drops_non_pd():
    entry = _entry(inst_ids=(("commons_file", "Fish Magic.jpg"),))
    assert commons_resolver(entry, fetch=lambda fn: _commons_payload("CC BY-SA 4.0")) is None


def test_commons_resolver_none_without_commons_file():
    assert commons_resolver(_entry(inst_ids=(("aic", "5"),))) is None


def _aic_payload(is_pd):
    return {"data": {"id": 16569, "image_id": "abc-123", "is_public_domain": is_pd},
            "config": {"iiif_url": "https://www.artic.edu/iiif/2"}}


def test_aic_resolver_builds_1686_candidate_when_public_domain():
    entry = _entry(inst_ids=(("aic", "16569"),))
    cand = aic_resolver(entry, fetch=lambda path, params: _aic_payload(True))
    assert cand.image_url == "https://www.artic.edu/iiif/2/abc-123/full/1686,/0/default.jpg"
    assert cand.rights_status == "public_domain"
    assert max(cand.width, cand.height) >= 1500


def test_aic_resolver_none_when_in_copyright():
    entry = _entry(inst_ids=(("aic", "16569"),))
    assert aic_resolver(entry, fetch=lambda path, params: _aic_payload(False)) is None


def test_aic_resolver_none_without_aic_id():
    assert aic_resolver(_entry(inst_ids=(("commons_file", "x.jpg"),))) is None
