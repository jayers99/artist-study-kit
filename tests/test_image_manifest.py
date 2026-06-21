from scripts.image_similarity import ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry


def _entry(work_id, phash, whash, **kw):
    return ManifestEntry(work_id=work_id, phash=phash, whash=whash, **kw)


def test_load_missing_is_empty(tmp_path):
    m = Manifest.load(tmp_path / "nope.json")
    assert m.entries == []


def test_save_load_roundtrip(tmp_path):
    e = _entry("the-vase", "f" * 16, "0" * 16, title="The Vase", qid="Q1",
               inst_ids=(("aic", "123"),), width=800, height=600, bytes=4242,
               filename="the-vase.jpg", path="images/library/the-vase.jpg",
               stars=3, origins=[{"source": "aic", "won": True}])
    p = tmp_path / "manifest.json"
    Manifest(entries=[e]).save(p)
    back = Manifest.load(p).entries[0]
    assert back.work_id == "the-vase"
    assert back.inst_ids == (("aic", "123"),)
    assert back.stars == 3
    assert back.origins == [{"source": "aic", "won": True}]
    assert back.hashes() == ImageHashes("f" * 16, "0" * 16)


def test_find_match_above_below_threshold(tmp_path):
    h = ImageHashes("f" * 16, "f" * 16)
    same = _entry("same", "f" * 16, "f" * 16)          # score 1.0
    far = _entry("far", "0" * 16, "0" * 16)            # score 0.0
    m = Manifest(entries=[far, same])
    assert m.find_match(h).work_id == "same"
    assert Manifest(entries=[far]).find_match(h) is None


def test_find_match_skips_empty_hash_entries():
    h = ImageHashes("f" * 16, "f" * 16)
    blank = _entry("blank", "", "")                    # fail-open image: never matches
    m = Manifest(entries=[blank])
    assert m.find_match(h) is None


def test_upsert_replaces_by_work_id_else_appends():
    m = Manifest(entries=[_entry("a", "f" * 16, "f" * 16, title="old")])
    m.upsert(_entry("a", "f" * 16, "f" * 16, title="new"))
    assert len(m.entries) == 1 and m.entries[0].title == "new"
    m.upsert(_entry("b", "0" * 16, "0" * 16))
    assert {e.work_id for e in m.entries} == {"a", "b"}
