import json
from pathlib import Path

from scripts.gallery import (
    CandidateView,
    build_gallery_html,
    build_thumbnail_gallery,
    load_candidate_sidecars,
    write_gallery,
)
from scripts.museum_search import ThumbnailCandidate


def test_thumbnail_gallery_renders_remote_thumbnails_and_controls():
    cands = [
        ThumbnailCandidate(
            work_id="senecio", title="Senecio", museum="aic",
            thumbnail_url="https://www.artic.edu/iiif/2/abc/full/400,/0/default.jpg",
            source_url="https://www.artic.edu/artworks/10018", date="1922", rights="in_copyright",
        ),
    ]
    html = build_thumbnail_gallery(cands, "Paul Klee")
    assert "<!DOCTYPE html>" in html and "Paul Klee" in html
    # the remote thumbnail + source link are embedded (a browse board, not local files)
    assert "https://www.artic.edu/iiif/2/abc/full/400,/0/default.jpg" in html
    assert "https://www.artic.edu/artworks/10018" in html
    assert "Senecio" in html
    # same rating + gate + export contract as the download gallery
    assert "data-star" in html
    for gate in ("thesis", "anchor_trait", "handoff_note"):
        assert gate in html
    assert "selection.json" in html


def _sidecar(cdir: Path, work_id="wheat-field", token="12345", width=4000):
    wdir = cdir / work_id
    wdir.mkdir(parents=True, exist_ok=True)
    (wdir / f"{token}.jpg").write_bytes(b"\xff\xd8\xffJPEG")
    meta = {
        "work_id": work_id, "institution": "met", "label": "recto",
        "iiif_id": f"https://images.metmuseum.org/iiif/{token}",
        "image_url": "x", "width": width, "height": 3000,
        "license": "Public Domain", "rights_status": "public_domain",
    }
    (wdir / f"{token}.json").write_text(json.dumps(meta), encoding="utf-8")
    return meta


def test_load_sidecars_pairs_json_with_image(tmp_path):
    _sidecar(tmp_path)
    views = load_candidate_sidecars(tmp_path)
    assert len(views) == 1
    assert views[0].work_id == "wheat-field"
    assert views[0].token == "12345"
    assert views[0].image_rel == "images/candidates/wheat-field/12345.jpg"
    assert views[0].meta["institution"] == "met"


def test_load_sidecars_ignores_json_without_image(tmp_path):
    wdir = tmp_path / "orphan"
    wdir.mkdir()
    (wdir / "9.json").write_text("{}", encoding="utf-8")
    # Orphan json (no jpg) should be filtered out
    assert load_candidate_sidecars(tmp_path) == []

    # Add the jpg sibling; now the json should be included
    (wdir / "9.jpg").write_bytes(b"\xff\xd8\xffJPEG")
    views = load_candidate_sidecars(tmp_path)
    assert len(views) == 1
    assert views[0].token == "9"


def test_build_html_embeds_candidate_data_and_controls():
    view = CandidateView(
        work_id="wheat-field", token="12345",
        image_rel="images/candidates/wheat-field/12345.jpg",
        meta={"institution": "met", "width": 4000, "height": 3000,
              "rights_status": "public_domain", "license": "Public Domain", "label": "recto"},
    )
    html = build_gallery_html([view], "Vincent van Gogh")
    assert "<!DOCTYPE html>" in html
    assert "Vincent van Gogh" in html
    # candidate data is embedded as JSON for the JS
    assert "wheat-field" in html
    assert "images/candidates/wheat-field/12345.jpg" in html
    # decision metadata surfaced inline
    assert "met" in html and "4000" in html
    # star control + curatorial-gate fields + export present
    assert 'data-star' in html
    for gate in ("thesis", "anchor_trait", "handoff_note"):
        assert gate in html
    assert "selection.json" in html


def test_write_gallery_writes_file(tmp_path):
    cdir = tmp_path / "images" / "candidates"
    _sidecar(cdir)
    out = tmp_path / "gallery.html"
    result = write_gallery(cdir, "Vincent van Gogh", out)
    assert result == out
    assert out.is_file()
    assert "wheat-field" in out.read_text(encoding="utf-8")


def test_thumbnail_gallery_embeds_qid_and_inst_ids():
    cands = [ThumbnailCandidate(
        work_id="fish-magic", title="Fish Magic", museum="Philadelphia Museum of Art",
        thumbnail_url="https://commons.wikimedia.org/wiki/Special:FilePath/Fish.jpg?width=400",
        source_url="https://www.wikidata.org/wiki/Q3050231", date="1925", rights="unknown",
        qid="Q3050231", inst_ids=(("commons_file", "Fish.jpg"), ("aic", "16569")))]
    html = build_thumbnail_gallery(cands, "Paul Klee")
    assert "Q3050231" in html
    assert "commons_file" in html and "Fish.jpg" in html
    # the export builder forwards qid + inst_ids into selection.json ratings
    assert "qid: c.qid" in html and "inst_ids: c.inst_ids" in html
