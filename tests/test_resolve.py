import json
from types import SimpleNamespace

from scripts.iiif import ImageCandidate
from scripts.resolve import commons_resolver, aic_resolver, Resolved, resolve_selected, resolve_selection
from scripts.selection import Rating, Selection


def _entry(**kw):
    base = dict(work_id="fish-magic", iiif_token="t", image_rel="r", selected=True,
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


def _cand(work_id="fish-magic"):
    return ImageCandidate(work_id=work_id, institution="wikimedia", label="x",
                          iiif_id=f"wikimedia/{work_id}", image_url="u",
                          width=4000, height=3000, license="Public Domain",
                          rights_status="public_domain")


def test_resolve_selected_uses_first_successful_resolver(tmp_path):
    captured = {}

    def fake_download(cand, sel_dir):
        captured["dir"] = sel_dir
        return SimpleNamespace(status="downloaded", image_path=tmp_path / "fish.jpg")

    res = resolve_selected(
        _entry(), tmp_path,
        resolvers=[lambda e: None, lambda e: _cand()],   # commons misses, aic hits
        download=fake_download)
    assert isinstance(res, Resolved)
    assert res.rights == "public_domain"
    assert res.image_path == tmp_path / "fish.jpg"
    assert captured["dir"] == tmp_path


def test_resolve_selected_keeps_source_url_when_in_copyright(tmp_path):
    called = []
    res = resolve_selected(
        _entry(source_url="https://www.wikidata.org/wiki/Q1"), tmp_path,
        resolvers=[lambda e: None, lambda e: None],
        download=lambda c, d: called.append(c) or SimpleNamespace(status="downloaded", image_path=None))
    assert res.rights == "in_copyright"
    assert res.image_path is None
    assert res.source_url == "https://www.wikidata.org/wiki/Q1"
    assert called == []   # nothing downloaded for in-copyright works


def test_resolve_selected_pd_download_failure_stays_public_domain(tmp_path):
    # resolver verified PD/CC0 but the byte fetch fails -> still public_domain, no local file
    res = resolve_selected(
        _entry(), tmp_path,
        resolvers=[lambda e: _cand()],
        download=lambda c, d: SimpleNamespace(status="error", image_path=None))
    assert res.rights == "public_domain"
    assert res.image_path is None
    assert res.image_url == "u"   # _cand() sets image_url="u"; preserved for retry


def test_resolve_selection_resolves_selected_and_writes_manifest(tmp_path):
    sel = Selection(artist="paul-klee", ratings=[
        _entry(work_id="fish-magic", selected=True, inst_ids=(("commons_file", "Fish.jpg"),)),
        _entry(work_id="meh", selected=False),  # not selected → skipped
    ])

    def fake_download(cand, sel_dir):
        return SimpleNamespace(status="downloaded", image_path=sel_dir / f"{cand.work_id}.jpg")

    out = resolve_selection(sel, tmp_path,
                            resolvers=[lambda e: _cand(e.work_id)], download=fake_download)
    assert [r.work_id for r in out] == ["fish-magic"]   # only selected
    manifest = json.loads((tmp_path / "resolved.json").read_text(encoding="utf-8"))
    assert manifest[0]["work_id"] == "fish-magic"
    assert manifest[0]["image"] == "fish-magic.jpg"
    assert manifest[0]["rights"] == "public_domain"
