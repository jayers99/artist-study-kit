"""Human Pause 1 output: parse/validate selection.json and materialize the liked set.

selection.json is produced by gallery.html (star ratings + curatorial-gate text) and
ingested by Run B. The schema: {"artist", "ratings": [{work_id, iiif_token, image_rel,
rating, thesis, anchor_trait, handoff_note}]}. Works rated >= LIKED_THRESHOLD must carry
gate text and are copied into images/selected/.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

LIKED_THRESHOLD = 4
_GATE_FIELDS = ("thesis", "anchor_trait", "handoff_note")


@dataclass(frozen=True)
class Rating:
    work_id: str
    iiif_token: str
    image_rel: str
    rating: int
    thesis: str = ""
    anchor_trait: str = ""
    handoff_note: str = ""
    qid: str = ""
    source_url: str = ""
    museum: str = ""
    rights: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Selection:
    artist: str
    ratings: list[Rating] = field(default_factory=list)


def parse_selection(data: dict) -> Selection:
    """Build a Selection from the gallery's JSON payload (missing gate fields → '')."""
    ratings = [
        Rating(
            work_id=str(r.get("work_id", "")),
            iiif_token=str(r.get("iiif_token", "")),
            image_rel=str(r.get("image_rel", "")),
            rating=int(r.get("rating", 0)),
            thesis=str(r.get("thesis", "")),
            anchor_trait=str(r.get("anchor_trait", "")),
            handoff_note=str(r.get("handoff_note", "")),
            qid=str(r.get("qid", "")),
            source_url=str(r.get("source_url", "")),
            museum=str(r.get("museum", "")),
            rights=str(r.get("rights", "")),
            inst_ids=tuple((str(p[0]), str(p[1])) for p in r.get("inst_ids", []) if len(p) == 2),
        )
        for r in data.get("ratings", [])
    ]
    return Selection(artist=str(data["artist"]), ratings=ratings)


def validate_selection(sel: Selection) -> list[str]:
    """Return human-readable errors; empty list means the selection is valid."""
    errors: list[str] = []
    for r in sel.ratings:
        label = r.work_id or r.iiif_token or "<unknown>"
        if not (0 <= r.rating <= 5):
            errors.append(f"{label}: rating {r.rating} out of range 0-5")
        elif r.rating >= LIKED_THRESHOLD:
            for gate in _GATE_FIELDS:
                if not getattr(r, gate).strip():
                    errors.append(f"{label}: liked (>={LIKED_THRESHOLD}*) but {gate} is empty")
        if not r.work_id:
            errors.append(f"{label}: missing work_id")
    return errors


def load_selection(path: Path, artist: str) -> Selection:
    """Load + validate selection.json; raise ValueError on artist mismatch."""
    sel = parse_selection(json.loads(Path(path).read_text(encoding="utf-8")))
    if sel.artist != artist:
        raise ValueError(f"selection.json artist {sel.artist!r} != requested {artist!r}")
    return sel


def liked(sel: Selection, threshold: int = LIKED_THRESHOLD) -> list[Rating]:
    return [r for r in sel.ratings if r.rating >= threshold]


def apply_selection(
    sel: Selection,
    candidates_dir: Path | str,
    selected_dir: Path | str,
    threshold: int = LIKED_THRESHOLD,
) -> list[Path]:
    """Copy liked images from candidates_dir into selected_dir; idempotent."""
    candidates_dir = Path(candidates_dir)
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for r in liked(sel, threshold):
        src = candidates_dir / r.work_id / Path(r.image_rel).name
        if not src.is_file():
            continue
        dst = selected_dir / f"{r.work_id}-{Path(r.image_rel).name}"
        if not dst.is_file():
            shutil.copy2(src, dst)
        out.append(dst)
    return out
