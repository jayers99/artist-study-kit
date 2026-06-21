import json
import time
from pathlib import Path

from scripts.iiif import ImageCandidate
from scripts.image_download import (
    DownloadResult,
    download_candidate,
    download_candidates,
    robots_allows,
    USER_AGENT,
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


def test_download_candidates_skip_does_not_trip_throttle(tmp_path):
    """A leading skipped candidate must not cause an extra sleep before the next real download."""
    calls = []
    first = _candidate(iiif_id="https://images.metmuseum.org/iiif/10")
    second = _candidate(iiif_id="https://images.metmuseum.org/iiif/11")
    third = _candidate(iiif_id="https://images.metmuseum.org/iiif/12")

    # Pre-download the first candidate so it will be skipped.
    download_candidate(first, tmp_path, fetch=_ok_fetch, sleep=lambda s: None)

    results = download_candidates(
        [first, second, third], tmp_path,
        fetch=_ok_fetch, sleep=lambda s: calls.append(s), min_interval=0.5,
    )

    statuses = [r.status for r in results]
    assert statuses[0] == "skipped"
    assert statuses[1] == "downloaded"
    assert statuses[2] == "downloaded"
    # Exactly one sleep between the two real downloads; the skip adds none.
    assert calls.count(0.5) == 1


def test_user_agent_is_descriptive():
    assert "artist-study-kit" in USER_AGENT


def test_download_candidate_handles_fetch_exception(tmp_path):
    def _boom(url):
        raise ConnectionError("connection reset")

    res = download_candidate(_candidate(), tmp_path, fetch=_boom, sleep=lambda s: None)
    assert res.status == "error"
    assert res.image_path is None
    assert "connection reset" in res.note


def test_cache_thumbnail_writes_and_returns_size(tmp_path):
    from scripts.image_download import cache_thumbnail
    body = b"\xff\xd8\xff\xe0thumbnailbytes"
    rel, size = cache_thumbnail("senecio", "https://x/t.jpg", tmp_path,
                                fetch=lambda u: (200, "image/jpeg", body))
    assert rel == "images/candidates/senecio/thumb.jpg"
    assert size == len(body)
    assert (tmp_path / "senecio" / "thumb.jpg").read_bytes() == body


def test_cache_thumbnail_is_idempotent(tmp_path):
    from scripts.image_download import cache_thumbnail
    body = b"\xff\xd8\xff\xe0bytes"
    cache_thumbnail("w", "https://x/t.jpg", tmp_path, fetch=lambda u: (200, "image/jpeg", body))

    def _boom(url):
        raise AssertionError("must not re-fetch when cached")

    rel, size = cache_thumbnail("w", "https://x/t.jpg", tmp_path, fetch=_boom)
    assert rel == "images/candidates/w/thumb.jpg"
    assert size == len(body)


def test_cache_thumbnail_failure_returns_empty(tmp_path):
    from scripts.image_download import cache_thumbnail
    assert cache_thumbnail("w", "https://x/t.jpg", tmp_path,
                           fetch=lambda u: (404, "text/html", b"")) == ("", 0)
    assert cache_thumbnail("w", "", tmp_path,
                           fetch=lambda u: (200, "image/jpeg", b"x")) == ("", 0)


def test_cache_thumbnails_batch_sets_paths_and_skips_user_local(tmp_path):
    from scripts.image_download import cache_thumbnails
    from scripts.state import BoardCandidate
    disc = BoardCandidate(work_id="senecio", title="", date="", museum="",
                          thumbnail_url="https://x/t.jpg", source_url="", rights="")
    user = BoardCandidate(work_id="mine", title="", date="", museum="",
                          thumbnail_url="", source_url="", rights="", origin="user",
                          local_path="images/user/mine.jpg")
    already = BoardCandidate(work_id="done", title="", date="", museum="",
                             thumbnail_url="https://x/d.jpg", source_url="", rights="",
                             thumbnail_path="images/candidates/done/thumb.jpg")
    cached = cache_thumbnails([disc, user, already], tmp_path,
                              fetch=lambda u: (200, "image/jpeg", b"jpegbytes"),
                              sleep=lambda s: None)
    assert cached == 1                                            # only disc fetched
    assert disc.thumbnail_path == "images/candidates/senecio/thumb.jpg"
    assert user.thumbnail_path == "images/user/mine.jpg"          # mapped, not fetched
    assert already.thumbnail_path == "images/candidates/done/thumb.jpg"  # untouched


# ---------------------------------------------------------------------------
# Task 6: download_library + LibraryDownload
# ---------------------------------------------------------------------------

from scripts.image_download import download_library, LibraryDownload


class _Cand:
    def __init__(self, work_id, thumbnail_url=""):
        self.work_id = work_id
        self.thumbnail_url = thumbnail_url


def test_download_library_writes_resolved_urls(tmp_path):
    cands = [_Cand("a"), _Cand("b"), _Cand("c")]
    urls = {"a": "http://x/a.jpg", "b": None, "c": "http://x/c.png"}
    def resolve_url(c): return urls[c.work_id]
    def fetch(url):
        return (200, "image/jpeg" if url.endswith(".jpg") else "image/png", b"bytes")
    out = download_library(cands, tmp_path, resolve_url=resolve_url, fetch=fetch,
                           sleep=lambda *_: None)
    by = {r.work_id: r for r in out}
    assert by["a"].status == "downloaded" and by["a"].path == tmp_path / "a.jpg"
    assert by["b"].status == "no-image" and by["b"].path is None
    assert by["c"].path == tmp_path / "c.png"
    assert (tmp_path / "a.jpg").read_bytes() == b"bytes"


def test_download_library_idempotent_skip(tmp_path):
    (tmp_path / "a.jpg").write_bytes(b"old")
    calls = []
    def fetch(url): calls.append(url); return (200, "image/jpeg", b"new")
    out = download_library([_Cand("a")], tmp_path, resolve_url=lambda c: "http://x/a.jpg",
                           fetch=fetch, sleep=lambda *_: None)
    assert out[0].status == "skipped" and calls == []
    assert (tmp_path / "a.jpg").read_bytes() == b"old"
