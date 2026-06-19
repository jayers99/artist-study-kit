import json
import time
from pathlib import Path

from scripts.iiif import ImageCandidate
from scripts.image_download import (
    DownloadResult,
    download_candidate,
    download_candidates,
    robots_allows,
)

ROBOTS = (Path(__file__).parent / "fixtures" / "robots.txt").read_text()


def _candidate(iiif_id="https://images.metmuseum.org/iiif/12345", w=4000, h=3000,
               rights="public_domain", work_id="wheat-field"):
    return ImageCandidate(
        work_id=work_id, institution="met", label="recto", iiif_id=iiif_id,
        image_url=f"{iiif_id}/full/max/0/default.jpg", width=w, height=h,
        license="Public Domain", rights_status=rights,
    )


def _ok_fetch(url):
    return (200, "image/jpeg", b"\xff\xd8\xff\xe0JPEGBYTES")


def test_robots_allows_respects_disallow():
    assert robots_allows(ROBOTS, "/art/collection/1") is True
    assert robots_allows(ROBOTS, "/private/secret") is False
    assert robots_allows(ROBOTS, "/admin/panel") is False


def test_robots_allows_empty_is_permissive():
    assert robots_allows("", "/anything") is True


def test_download_candidate_writes_image_and_metadata(tmp_path):
    res = download_candidate(_candidate(), tmp_path, fetch=_ok_fetch, sleep=lambda s: None)
    assert res.status == "downloaded"
    assert res.image_path.is_file()
    assert res.image_path.parent.name == "wheat-field"
    assert res.image_path.read_bytes().startswith(b"\xff\xd8\xff")
    meta = json.loads(res.meta_path.read_text())
    assert meta["institution"] == "met"
    assert meta["rights_status"] == "public_domain"
    assert meta["iiif_id"].endswith("12345")
    assert meta["width"] == 4000


def test_download_candidate_skips_existing(tmp_path):
    download_candidate(_candidate(), tmp_path, fetch=_ok_fetch, sleep=lambda s: None)

    def _boom(url):
        raise AssertionError("should not refetch an existing image")

    res = download_candidate(_candidate(), tmp_path, fetch=_boom, sleep=lambda s: None)
    assert res.status == "skipped"


def test_download_candidate_rejects_invalid_candidate(tmp_path):
    bad = _candidate(w=400, h=300, rights="restricted")
    res = download_candidate(bad, tmp_path, fetch=_ok_fetch, sleep=lambda s: None)
    assert res.status == "invalid"
    assert res.image_path is None


def test_download_candidate_blocked_by_robots(tmp_path):
    blocked = _candidate(iiif_id="https://images.metmuseum.org/private/9")
    res = download_candidate(blocked, tmp_path, fetch=_ok_fetch, robots_txt=ROBOTS, sleep=lambda s: None)
    assert res.status == "blocked"


def test_download_candidate_handles_non_image_response(tmp_path):
    def _html(url):
        return (200, "text/html", b"<html>not found</html>")

    res = download_candidate(_candidate(), tmp_path, fetch=_html, sleep=lambda s: None)
    assert res.status == "error"
    assert res.image_path is None


def test_download_candidates_throttles_between_requests(tmp_path):
    calls = []
    cands = [_candidate(iiif_id=f"https://images.metmuseum.org/iiif/{i}") for i in range(3)]
    results = download_candidates(
        cands, tmp_path, fetch=_ok_fetch, sleep=lambda s: calls.append(s), min_interval=0.5
    )
    assert all(isinstance(r, DownloadResult) for r in results)
    assert [r.status for r in results] == ["downloaded", "downloaded", "downloaded"]
    # Sleeps between the 3 downloads (not before the first).
    assert calls.count(0.5) == 2
