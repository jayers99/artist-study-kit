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
from scripts.state import BoardCandidate


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
    # rating + export contract; gate fields are intentionally absent (moved to interview stage)
    assert "data-star" in html
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
    # star control + export present; gate fields intentionally absent (moved to interview stage)
    assert 'data-star' in html
    assert "selection.json" in html


def test_write_gallery_writes_file(tmp_path):
    cdir = tmp_path / "images" / "candidates"
    _sidecar(cdir)
    out = tmp_path / "gallery.html"
    result = write_gallery(cdir, "Vincent van Gogh", out)
    assert result == out
    assert out.is_file()
    assert "wheat-field" in out.read_text(encoding="utf-8")


def _cand():
    return ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="http://x/t.jpg", source_url="http://x/9",
        date="1922", rights="in_copyright", medium="Oil on gauze",
        qid="Q1", inst_ids=(("aic", "9"),),
    )


def test_board_payload_includes_medium():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    assert '"medium": "Oil on gauze"' in html


def test_board_has_no_rationale_gate():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    assert "data-gate" not in html
    assert "thesis" not in html
    assert "anchor_trait" not in html
    assert "handoff_note" not in html


def test_board_export_carries_title_date_medium():
    html = build_thumbnail_gallery([_cand()], "Paul Klee")
    # export object source in the embedded template
    assert "title: c.title" in html
    assert "date: c.date" in html
    assert "medium: c.medium" in html


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


def test_thumbnail_gallery_marks_user_origin():
    user = BoardCandidate(
        work_id="barn", title="Farmhouse", date="1925", museum="",
        thumbnail_url="images/user/barn.jpg", source_url="", rights="unknown",
        origin="user", local_path="images/user/barn.jpg")
    html = build_thumbnail_gallery([user], "Paul Klee")
    assert '"origin": "user"' in html
    assert "USER" in html  # badge label rendered in the grid template


def test_thumbnail_gallery_payload_carries_stars_year_selected_and_local_src(tmp_path):
    import json as _json
    pkg = tmp_path
    thumb = pkg / "images" / "candidates" / "senecio" / "thumb.jpg"
    thumb.parent.mkdir(parents=True)
    thumb.write_bytes(b"012345678")  # 9 bytes
    cand = BoardCandidate(
        work_id="senecio", title="Senecio", date="c. 1922", museum="aic",
        thumbnail_url="https://x/remote.jpg", source_url="https://x/1", rights="in_copyright",
        stars=4, thumbnail_path="images/candidates/senecio/thumb.jpg",
    )
    html = build_thumbnail_gallery([cand], "Paul Klee", package_root=pkg)
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    row = data["candidates"][0]
    assert row["stars"] == 4
    assert row["year"] == 1922
    assert row["selected"] is False                       # never seeded
    assert row["image_rel"] == "images/candidates/senecio/thumb.jpg"   # local preferred
    assert row["bytes"] == 9


def test_thumbnail_gallery_falls_back_to_remote_url_without_cache():
    import json as _json
    cand = BoardCandidate(
        work_id="w", title="T", date="", museum="met",
        thumbnail_url="https://x/remote.jpg", source_url="https://x/1", rights="public_domain",
    )
    html = build_thumbnail_gallery([cand], "X")
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    row = data["candidates"][0]
    assert row["image_rel"] == "https://x/remote.jpg"     # remote fallback
    assert row["year"] is None
    assert row["bytes"] == 0


def test_thumbnail_template_has_seed_select_filter_sort_and_two_exports():
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    # stars seeded from payload (persistent axis), not hardcoded zero
    assert "seedStars" in html
    # selection is a separate control from stars
    assert "data-select" in html
    # filter + sort controls
    assert 'id="star-filter"' in html
    assert 'id="sort"' in html
    # two distinct export files
    assert "stars.json" in html
    assert "selection.json" in html


def test_thumbnail_template_export_keys_selected_and_stars():
    cand = BoardCandidate(work_id="w", title="T", date="1920", museum="met",
                          thumbnail_url="https://x/t.jpg", source_url="https://x/1",
                          rights="public_domain", stars=3)
    html = build_thumbnail_gallery([cand], "X")
    # the selection.json builder emits an explicit `selected` field per row
    assert "selected:" in html


def test_thumbnail_gallery_payload_carries_full_url():
    import json as _json
    from scripts.museum_search import ThumbnailCandidate
    cand = ThumbnailCandidate(
        work_id="senecio", title="Senecio", museum="aic",
        thumbnail_url="https://www.artic.edu/iiif/2/c969/full/400,/0/default.jpg",
        source_url="https://x/1", date="1922", rights="in_copyright")
    html = build_thumbnail_gallery([cand], "X")
    data = _json.loads(html.split('type="application/json">', 1)[1].split("</script>", 1)[0])
    assert data["candidates"][0]["full_url"] == \
        "https://www.artic.edu/iiif/2/c969/full/843,/0/default.jpg"
