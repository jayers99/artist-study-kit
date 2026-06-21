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
