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
    return p if p.is_absolute() else paths.root / p


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
