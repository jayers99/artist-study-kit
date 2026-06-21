# tests/test_dedup.py
from scripts.image_similarity import ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.dedup import IncomingImage, resolve, canonical_name


def _inc(tmp_path="/incoming/x.jpg", phash="f" * 16, whash="f" * 16,
         w=400, h=300, b=1000, **kw):
    return IncomingImage(tmp_path=tmp_path, hashes=ImageHashes(phash, whash),
                         width=w, height=h, bytes=b, **kw)


def _entry(work_id, phash="f" * 16, whash="f" * 16, **kw):
    return ManifestEntry(work_id=work_id, phash=phash, whash=whash, **kw)


def test_no_match_is_add(tmp_path):
    inc = _inc(title="The Vase of Tulips", source="aic", source_url="http://x",
               rights="public_domain")
    act = resolve(inc, Manifest(entries=[]), run_id="run1")
    assert act.kind == "add"
    assert act.delete_path is None
    assert act.keep_path == inc.tmp_path
    assert act.canonical_name == "the-vase-of-tulips.jpg"
    assert act.entry.title == "The Vase of Tulips"
    assert act.entry.width == 400 and act.entry.path == "images/library/the-vase-of-tulips.jpg"
    assert act.entry.origins == [{
        "source": "aic", "source_url": "http://x", "run_id": "run1",
        "rights": "public_domain", "width": 400, "height": 300, "bytes": 1000, "won": True}]


def test_incoming_larger_wins_and_preserves_stars(tmp_path):
    existing = _entry("madame-cezanne", title="Madame Cezanne", qid="Q42",
                      filename="madame-cezanne.jpg", path="images/library/madame-cezanne.jpg",
                      width=300, height=200, bytes=500, stars=5)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/big.jpg", w=2000, h=1500, b=900000,
               source="commons", source_url="http://c")
    act = resolve(inc, m, run_id="run2")
    assert act.kind == "merge"
    assert act.keep_path == "/incoming/big.jpg"
    assert act.delete_path == "images/library/madame-cezanne.jpg"
    assert act.entry.width == 2000 and act.entry.bytes == 900000
    assert act.entry.phash == inc.hashes.phash            # winner's hashes
    assert act.entry.qid == "Q42" and act.entry.title == "Madame Cezanne"  # identity kept
    assert act.entry.stars == 5                           # never lost
    assert act.entry.work_id == "madame-cezanne"          # stable
    assert [o["won"] for o in act.entry.origins][-1] is True
    assert act.canonical_name == "madame-cezanne.jpg"     # no churn (already title-derived)


def test_existing_larger_wins_but_metadata_merges(tmp_path):
    existing = _entry("stem-name", title="", qid="",                 # was a fallback name
                      filename="img001.jpg", path="images/library/img001.jpg",
                      width=2000, height=1500, bytes=900000, stars=2)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/small.jpg", w=300, h=200, b=500,
               title="Still Life with Apples", qid="Q7", source="wikidata")
    act = resolve(inc, m, run_id="run3")
    assert act.kind == "merge"
    assert act.keep_path == "images/library/img001.jpg"  # existing file wins
    assert act.delete_path == "/incoming/small.jpg"
    assert act.entry.width == 2000                        # winner dims kept
    assert act.entry.title == "Still Life with Apples"   # gap filled from incoming
    assert act.entry.qid == "Q7"
    assert act.entry.stars == 2
    assert act.canonical_name == "still-life-with-apples.jpg"  # re-derived (existing was fallback)


def test_dim_tie_breaks_on_bytes_then_existing(tmp_path):
    existing = _entry("e", title="E", filename="e.jpg", path="images/library/e.jpg",
                      width=400, height=300, bytes=1000, stars=0)
    m = Manifest(entries=[existing])
    # same dims, smaller bytes -> existing wins
    inc_small = _inc(w=400, h=300, b=900, title="E")
    assert resolve(inc_small, m, "r").keep_path == "images/library/e.jpg"
    # same dims, larger bytes -> incoming wins
    inc_big = _inc(tmp_path="/incoming/e2.jpg", w=400, h=300, b=2000, title="E")
    assert resolve(inc_big, m, "r").keep_path == "/incoming/e2.jpg"


def test_canonical_name_decollides_and_is_safe():
    taken = {"the-vase.jpg"}
    assert canonical_name("The Vase", "", "x", ".jpg", taken) == "the-vase-2.jpg"
    # no title -> qid -> stem fallback chain
    assert canonical_name("", "Q9", "x", ".jpg", set()) == "q9.jpg"
    assert canonical_name("", "", "DSC_001", ".png", set()) == "dsc-001.png"


def test_qid_incoming_overrides_seed_guess_independent_of_pixels():
    # existing: seed guess, NO qid, LARGER pixels, starred
    existing = _entry("dt4962", title="DT4962", qid="", date="",
                      filename="dt4962.jpg", path="images/library/dt4962.jpg",
                      width=2000, height=1500, bytes=900000, stars=4)
    m = Manifest(entries=[existing])
    # incoming: authoritative (qid), SMALLER pixels
    inc = _inc(tmp_path="/incoming/v.jpg", w=400, h=300, b=1000,
               title="The Vase of Tulips", qid="Q1", date="1890")
    act = resolve(inc, m, run_id="r")
    assert act.kind == "merge"
    # existing wins on PIXELS (it is larger) ...
    assert act.keep_path == "images/library/dt4962.jpg"
    assert act.entry.width == 2000 and act.entry.bytes == 900000
    # ... but the authoritative metadata UPGRADES the guess
    assert act.entry.title == "The Vase of Tulips"
    assert act.entry.qid == "Q1"
    assert act.entry.date == "1890"
    # identity is stable across the upgrade
    assert act.entry.work_id == "dt4962"
    assert act.entry.filename == "dt4962.jpg"
    assert act.entry.stars == 4


def test_existing_qid_not_clobbered_by_different_qid():
    existing = _entry("w", title="Real Title", qid="Q1",
                      filename="real-title.jpg", path="images/library/real-title.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/o.jpg", w=2000, h=1500, b=900000,
               title="Other", qid="Q2")
    act = resolve(inc, m, run_id="r")
    # incoming wins pixels, but existing authoritative metadata is kept
    assert act.entry.title == "Real Title"
    assert act.entry.qid == "Q1"


def test_authoritative_incoming_empty_field_does_not_blank_existing():
    existing = _entry("w", title="Old", qid="", date="1890",
                      filename="old.jpg", path="images/library/old.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/x.jpg", w=400, h=300, b=1000,
               title="", qid="Q1", date="")           # authoritative but sparse
    act = resolve(inc, m, run_id="r")
    assert act.entry.qid == "Q1"          # qid applied
    assert act.entry.date == "1890"       # empty incoming date does NOT blank it
    assert act.entry.title == "Old"       # empty incoming title does NOT blank it


def test_neither_has_qid_keeps_existing_wins_unchanged():
    existing = _entry("w", title="A", qid="",
                      filename="a.jpg", path="images/library/a.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/b.jpg", w=2000, h=1500, b=900000,
               title="B", qid="")
    act = resolve(inc, m, run_id="r")
    assert act.entry.title == "A"          # existing-non-empty-wins, unchanged
