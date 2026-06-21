"""Spec B — library collection: execute Spec A dedup decisions as real file ops,
orchestrate batch dedup, seed the user's collection, and mirror the library onto
the curation board. Filesystem effects go through injected move/delete/copy seams.
"""
from __future__ import annotations

import os
import shutil
from dataclasses import dataclass
from pathlib import Path

from scripts.dedup import DedupAction, resolve, IncomingImage
from scripts.image_manifest import Manifest, ManifestEntry
from scripts.image_similarity import DUP_THRESHOLD, perceptual_hashes, image_dims
from scripts.state import BoardCandidate, PackageState
from scripts.paths import StudyPaths


@dataclass(frozen=True)
class LibrarySummary:
    added: int = 0
    merged_kept: int = 0       # dup found, existing copy kept (incoming deleted)
    merged_replaced: int = 0   # dup found, incoming larger (old library file replaced)


def _abs(paths: StudyPaths, p) -> Path:
    p = Path(p)
    if p.is_absolute():
        return p
    root = Path(paths.root)
    # Idempotent: when paths.root is relative, captured tmp_paths/keep_paths are
    # already root-prefixed (e.g. "studies/a/images/incoming/x"). Re-joining them
    # against root would double the prefix; only prefix genuinely root-relative
    # paths (canonical entry paths like "images/library/y").
    if p == root or root in p.parents:
        return p
    return root / p


def make_incoming(path, *, source: str, source_url: str = "", rights: str = "",
                  title: str = "", date: str = "", qid: str = "", inst_ids=(),
                  medium: str = "", hash_for=perceptual_hashes,
                  dims_for=image_dims) -> "IncomingImage | None":
    h = hash_for(path)
    d = dims_for(path)
    if h is None or d is None:
        return None
    w, ht, b = d
    return IncomingImage(
        tmp_path=str(path), hashes=h, width=w, height=ht, bytes=b,
        title=title, date=date, qid=qid, inst_ids=tuple(inst_ids),
        source=source, source_url=source_url, rights=rights, medium=medium)


def build_library(incoming, manifest: Manifest, paths: StudyPaths, run_id: str, *,
                  threshold: float = DUP_THRESHOLD, move=shutil.move,
                  delete=os.remove) -> LibrarySummary:
    added = kept = replaced = 0
    for inc in incoming:
        action = resolve(inc, manifest, run_id, threshold=threshold)
        execute_action(action, paths, move=move, delete=delete)
        manifest.upsert(action.entry)
        if action.kind == "add":
            added += 1
        elif action.keep_path == inc.tmp_path:   # incoming won
            replaced += 1
        else:                                     # existing kept
            kept += 1
    return LibrarySummary(added=added, merged_kept=kept, merged_replaced=replaced)


def execute_action(action: DedupAction, paths: StudyPaths, *,
                   move=shutil.move, delete=os.remove) -> ManifestEntry:
    entry = action.entry
    dest = _abs(paths, entry.path)
    keep = _abs(paths, action.keep_path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    if keep.resolve() != dest.resolve():
        move(str(keep), str(dest))
    if action.delete_path:
        loser = _abs(paths, action.delete_path)
        if loser.resolve() != dest.resolve() and loser.exists():
            delete(str(loser))
    return entry


def _first_source_url(entry: ManifestEntry) -> str:
    for o in entry.origins:
        if o.get("source_url"):
            return o["source_url"]
    return ""


_IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".tif", ".tiff", ".bmp", ".gif", ".psd"}


def seed_import(external_dir, paths: StudyPaths, manifest: Manifest, run_id: str, *,
                copy=shutil.copy2, move=shutil.move, delete=os.remove,
                hash_for=perceptual_hashes, dims_for=image_dims) -> LibrarySummary:
    ext_dir = Path(external_dir)
    user_dir = paths.user_images_dir
    user_dir.mkdir(parents=True, exist_ok=True)
    incoming = []
    for src in sorted(ext_dir.iterdir()):
        if not src.is_file() or src.suffix.lower() not in _IMAGE_EXTS:
            continue
        dest = user_dir / src.name
        copy(str(src), str(dest))               # external is only ever READ
        inc = make_incoming(dest, source="user-seed", rights="unknown",
                            title=src.stem, hash_for=hash_for, dims_for=dims_for)
        if inc is not None:
            incoming.append(inc)
    return build_library(incoming, manifest, paths, run_id, move=move, delete=delete)


def sync_candidates(manifest: Manifest, state: PackageState, run_id: str) -> int:
    by_id = {c.work_id: c for c in state.candidates}
    n = 0
    for e in manifest.entries:
        existing = by_id.get(e.work_id)
        stars = existing.stars if existing is not None else e.stars
        e.stars = stars  # keep manifest in step with the board (the star authority)
        origin = "user" if any(o.get("source") == "user-seed" for o in e.origins) else "discovered"
        bc = BoardCandidate(
            work_id=e.work_id, title=e.title, date=e.date, museum="",
            thumbnail_url="", source_url=_first_source_url(e), rights=e.rights,
            medium=e.medium, qid=e.qid, inst_ids=tuple(e.inst_ids),
            origin=origin, first_run=(existing.first_run if existing else run_id),
            local_path=e.path, stars=stars, thumbnail_path=e.path)
        if existing is None:
            state.candidates.append(bc)
        else:
            state.candidates[state.candidates.index(existing)] = bc
        n += 1
    return n
