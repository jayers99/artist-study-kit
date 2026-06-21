"""Stage-5 IO: robots-aware, throttled, idempotent image download with metadata.

The byte-fetch boundary is injected (`fetch(url) -> (status, content_type, bytes)`)
so tests run against canned responses, never live museum endpoints. A default
httpx-backed fetcher is provided for real runs.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scripts.iiif import ImageCandidate, validate_candidate


USER_AGENT = "artist-study-kit/1.0 (studio-prep research; +https://github.com/jayers99/artist-study-kit)"


def robots_allows(robots_txt: str, path: str, user_agent: str = "*") -> bool:
    """Minimal robots.txt check for the `*` (or named) user-agent group."""
    if not robots_txt.strip():
        return True
    groups: dict[str, list[str]] = {}
    current: list[str] = []
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            current = groups.setdefault(value, [])
        elif key == "disallow" and value:
            current.append(value)
    rules = groups.get(user_agent, groups.get("*", []))
    return not any(path.startswith(rule) for rule in rules)


@dataclass(frozen=True)
class DownloadResult:
    candidate: ImageCandidate
    image_path: Path | None
    meta_path: Path | None
    status: str
    note: str = ""


def _iiif_token(iiif_id: str) -> str:
    return iiif_id.rstrip("/").rsplit("/", 1)[-1]


def default_fetch(url: str) -> tuple[int, str, bytes]:
    """Real fetcher (httpx). Not exercised in tests. Network errors → (0, "", b"")."""
    import httpx

    try:
        resp = httpx.get(
            url,
            follow_redirects=True,
            timeout=60.0,
            headers={"User-Agent": USER_AGENT},
        )
    except httpx.HTTPError:
        return 0, "", b""
    return resp.status_code, resp.headers.get("content-type", ""), resp.content


def download_candidate(
    candidate: ImageCandidate,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    robots_txt: str = "",
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> DownloadResult:
    """Validate, robots-check, and download one candidate; idempotent."""
    passed, reasons = validate_candidate(candidate)
    if not passed:
        return DownloadResult(candidate, None, None, "invalid", "; ".join(reasons))

    work_dir = Path(candidates_dir) / candidate.work_id
    token = _iiif_token(candidate.iiif_id)
    image_path = work_dir / f"{token}.jpg"
    meta_path = work_dir / f"{token}.json"

    if image_path.is_file():
        return DownloadResult(candidate, image_path, meta_path, "skipped")

    if not robots_allows(robots_txt, urlsplit(candidate.image_url).path):
        return DownloadResult(candidate, None, None, "blocked", candidate.image_url)

    try:
        status_code, content_type, content = fetch(candidate.image_url)
    except Exception as exc:  # network errors must not crash the batch
        return DownloadResult(candidate, None, None, "error", str(exc))
    if status_code != 200 or not content_type.startswith("image/") or not content:
        return DownloadResult(
            candidate, None, None, "error", f"status={status_code} type={content_type}"
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(content)
    meta_path.write_text(json.dumps(asdict(candidate), indent=2) + "\n", encoding="utf-8")
    return DownloadResult(candidate, image_path, meta_path, "downloaded")


def download_candidates(
    candidates: list[ImageCandidate],
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    robots_txt: str = "",
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> list[DownloadResult]:
    """Download a list of candidates, throttling between actual fetches."""
    results: list[DownloadResult] = []
    fetched = False
    for candidate in candidates:
        if fetched:
            sleep(min_interval)
        result = download_candidate(
            candidate,
            candidates_dir,
            fetch=fetch,
            robots_txt=robots_txt,
            sleep=sleep,
            min_interval=min_interval,
        )
        results.append(result)
        if result.status == "downloaded":
            fetched = True
    return results


def cache_thumbnail(
    work_id: str,
    thumbnail_url: str,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
) -> tuple[str, int]:
    """Download a board thumbnail to <candidates_dir>/<work_id>/thumb.jpg.

    Idempotent (skip if present). Returns (rel_path, byte_size); ("", 0) on
    empty URL or any fetch failure. Never raises."""
    work_dir = Path(candidates_dir) / work_id
    dest = work_dir / "thumb.jpg"
    rel = f"images/candidates/{work_id}/thumb.jpg"
    if dest.is_file():
        return rel, dest.stat().st_size
    if not thumbnail_url:
        return "", 0
    try:
        status_code, content_type, content = fetch(thumbnail_url)
    except Exception:
        return "", 0
    if status_code != 200 or not content_type.startswith("image/") or not content:
        return "", 0
    work_dir.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(content)
    return rel, len(content)


def cache_thumbnails(
    candidates,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> int:
    """Cache thumbnails for candidates missing a thumbnail_path; set it in place.

    origin=="user" candidates already have a local file (local_path) — map it,
    don't fetch. Throttles between real fetches. Returns count newly cached."""
    cached = 0
    fetched = False
    for cand in candidates:
        if getattr(cand, "thumbnail_path", ""):
            continue
        if getattr(cand, "origin", "") == "user" and getattr(cand, "local_path", ""):
            cand.thumbnail_path = cand.local_path
            continue
        if fetched:
            sleep(min_interval)
        rel, _size = cache_thumbnail(
            cand.work_id, getattr(cand, "thumbnail_url", ""), candidates_dir, fetch=fetch
        )
        if rel:
            cand.thumbnail_path = rel
            cached += 1
            fetched = True
    return cached
