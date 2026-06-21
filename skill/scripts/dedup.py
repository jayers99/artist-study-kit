# skill/scripts/dedup.py
"""Spec A — pure keep/merge/add decision. NO filesystem I/O.

resolve() takes a freshly-seen image (hashes + dims + metadata already computed
by the caller) and the current Manifest, and returns a DedupAction the caller
(Spec B) executes: move winner into images/library/, delete the loser, upsert
the entry. Deterministic: run_id is injected; no clock/RNG here.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from scripts.image_similarity import DUP_THRESHOLD, ImageHashes
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.paths import slugify

LIBRARY_REL = "images/library"


@dataclass(frozen=True)
class IncomingImage:
    tmp_path: str
    hashes: ImageHashes
    width: int
    height: int
    bytes: int
    title: str = ""
    date: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    source: str = ""
    source_url: str = ""
    rights: str = ""
    medium: str = ""


@dataclass(frozen=True)
class DedupAction:
    kind: str                 # "add" | "merge"
    keep_path: str
    delete_path: "str | None"
    canonical_name: str
    entry: ManifestEntry


def _slug_base(title: str, qid: str, fallback_stem: str) -> str:
    if title.strip():
        return slugify(title)
    if qid.strip():
        return slugify(qid)
    # fallback: use the stem as-is (lowercased) — it's already a filesystem-safe name
    return fallback_stem.lower()


def canonical_name(title: str, qid: str, fallback_stem: str, ext: str,
                   taken) -> str:
    base = _slug_base(title, qid, fallback_stem)
    name = f"{base}{ext}"
    if name not in taken:
        return name
    n = 2
    while f"{base}-{n}{ext}" in taken:
        n += 1
    return f"{base}-{n}{ext}"


def _origin(inc: IncomingImage, run_id: str, won: bool) -> dict:
    return {"source": inc.source, "source_url": inc.source_url, "run_id": run_id,
            "rights": inc.rights, "width": inc.width, "height": inc.height,
            "bytes": inc.bytes, "won": won}


def resolve(inc: IncomingImage, manifest: Manifest, run_id: str,
            *, threshold: float = DUP_THRESHOLD) -> DedupAction:
    ext = Path(inc.tmp_path).suffix
    match = manifest.find_match(inc.hashes, threshold)

    if match is None:
        taken = {e.filename for e in manifest.entries}
        cn = canonical_name(inc.title, inc.qid, Path(inc.tmp_path).stem, ext, taken)
        entry = ManifestEntry(
            work_id=_slug_base(inc.title, inc.qid, Path(inc.tmp_path).stem),
            title=inc.title, date=inc.date, qid=inc.qid, inst_ids=inc.inst_ids,
            filename=cn, path=f"{LIBRARY_REL}/{cn}", width=inc.width,
            height=inc.height, bytes=inc.bytes, phash=inc.hashes.phash,
            whash=inc.hashes.whash, rights=inc.rights, medium=inc.medium,
            stars=0, origins=[_origin(inc, run_id, won=True)])
        return DedupAction(kind="add", keep_path=inc.tmp_path, delete_path=None,
                           canonical_name=cn, entry=entry)

    inc_wins = (inc.width * inc.height, inc.bytes) > (match.width * match.height, match.bytes)

    # identity / metadata merge — existing authoritative, incoming fills gaps
    title = match.title or inc.title
    date = match.date or inc.date
    qid = match.qid or inc.qid
    inst_ids = match.inst_ids or inc.inst_ids
    rights = match.rights or inc.rights
    medium = match.medium or inc.medium

    # canonical name: reuse existing (no churn) when it was already title-derived;
    # re-derive when the existing name was a fallback and we now have a real title.
    taken = {e.filename for e in manifest.entries if e.work_id != match.work_id}
    if match.title.strip():
        cn = match.filename
    else:
        cn = canonical_name(title, qid, Path(match.filename or inc.tmp_path).stem, ext, taken)

    if inc_wins:
        keep_path, delete_path = inc.tmp_path, match.path
        w, h, b = inc.width, inc.height, inc.bytes
        ph, wh = inc.hashes.phash, inc.hashes.whash
    else:
        keep_path, delete_path = match.path, inc.tmp_path
        w, h, b = match.width, match.height, match.bytes
        ph, wh = match.phash, match.whash

    entry = ManifestEntry(
        work_id=match.work_id, title=title, date=date, qid=qid, inst_ids=inst_ids,
        filename=cn, path=f"{LIBRARY_REL}/{cn}", width=w, height=h, bytes=b,
        phash=ph, whash=wh, rights=rights, medium=medium, stars=match.stars,
        origins=list(match.origins) + [_origin(inc, run_id, won=inc_wins)])
    return DedupAction(kind="merge", keep_path=keep_path, delete_path=delete_path,
                       canonical_name=cn, entry=entry)
