"""Human Pause 1 output: parse/validate selection.json and materialize the selected set.

selection.json is produced by gallery.html (star ratings) and ingested by Run B.
The schema: {"artist", "ratings": [{work_id, iiif_token, image_rel, rating,
title, date, medium}]}. Explicitly selected works are copied into images/selected/ (rating is orthogonal).
Rationale (thesis/anchor/handoff) is no longer stored here — it is produced by the
curation_interview stage as study-briefs.json.
"""

from __future__ import annotations

import json
import shutil
from dataclasses import dataclass, field
from pathlib import Path

LIKED_THRESHOLD = 4


@dataclass(frozen=True)
class Rating:
    work_id: str
    iiif_token: str
    image_rel: str
    rating: int = 0
    title: str = ""
    date: str = ""
    medium: str = ""
    qid: str = ""
    source_url: str = ""
    museum: str = ""
    rights: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    selected: bool = False
    stars: int = 0


@dataclass(frozen=True)
class Selection:
    artist: str
    ratings: list[Rating] = field(default_factory=list)


def parse_selection(data: dict) -> Selection:
    """Build a Selection from the gallery's JSON payload (missing fields → '')."""
    ratings = [
        Rating(
            work_id=str(r.get("work_id", "")),
            iiif_token=str(r.get("iiif_token", "")),
            image_rel=str(r.get("image_rel", "")),
            rating=int(r.get("rating", 0)),
            title=str(r.get("title", "")),
            date=str(r.get("date", "")),
            medium=str(r.get("medium", "")),
            qid=str(r.get("qid", "")),
            source_url=str(r.get("source_url", "")),
            museum=str(r.get("museum", "")),
            rights=str(r.get("rights", "")),
            inst_ids=tuple((str(p[0]), str(p[1])) for p in r.get("inst_ids", []) if len(p) == 2),
            selected=bool(r.get("selected", False)),
            stars=int(r.get("stars", 0)),
        )
        for r in data.get("ratings", [])
    ]
    return Selection(artist=str(data["artist"]), ratings=ratings)


def validate_selection(sel: Selection) -> list[str]:
    """Return human-readable errors; empty list means the selection is valid.

    Rationale (thesis/anchor/handoff) is no longer gated here — it is produced by the
    curation_interview stage as study-briefs.json. This validates only the visual export.
    """
    errors: list[str] = []
    for r in sel.ratings:
        label = r.work_id or r.iiif_token or "<unknown>"
        if not (0 <= r.rating <= 5):
            errors.append(f"{label}: rating {r.rating} out of range 0-5")
        if not r.work_id:
            errors.append(f"{label}: missing work_id")
    return errors


def load_selection(path: Path, artist: str) -> Selection:
    """Load + validate selection.json; raise ValueError on artist mismatch."""
    sel = parse_selection(json.loads(Path(path).read_text(encoding="utf-8")))
    if sel.artist != artist:
        raise ValueError(f"selection.json artist {sel.artist!r} != requested {artist!r}")
    return sel


def parse_study_set(data: dict, *, max_study: int = 4) -> list[str]:
    """The ordered narrow-cut work_ids from study-set.json, truncated to max_study."""
    ids = [str(w) for w in data.get("study_set", [])]
    return ids[:max_study]


def load_study_set(path: Path, artist: str, *, max_study: int = 4) -> list[str]:
    """Load study-set.json; raise ValueError on artist mismatch."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if str(data.get("artist", "")) != artist:
        raise ValueError(f"study-set.json artist {data.get('artist')!r} != requested {artist!r}")
    return parse_study_set(data, max_study=max_study)


def liked(sel: Selection, threshold: int = LIKED_THRESHOLD) -> list[Rating]:
    return [r for r in sel.ratings if r.rating >= threshold]


def selected_rows(sel: "Selection") -> list[Rating]:
    """The explicitly selected works (the per-session pick).

    Orthogonal to stars: this reads only the `selected` flag, never a rating."""
    return [r for r in sel.ratings if r.selected]


def ingest_selection(sel: "Selection") -> tuple[list[str], list[str]]:
    """Resolve an exported selection into (selected_ids, study_set_ids) for a session.

    selected_ids are the works the human explicitly selected on the board; study_set
    defaults equal to it — the Thrust-3 funnel (Spec B) narrows study_set to <=4 later.
    Stars play no part here (stars persist on the candidate, orthogonally)."""
    rows = selected_rows(sel)
    selected_ids = [r.work_id for r in rows]
    return selected_ids, list(selected_ids)


def apply_selection(
    sel: Selection,
    candidates_dir: Path | str,
    selected_dir: Path | str,
) -> list[Path]:
    """Copy explicitly-selected images from candidates_dir into selected_dir; idempotent."""
    candidates_dir = Path(candidates_dir)
    selected_dir = Path(selected_dir)
    selected_dir.mkdir(parents=True, exist_ok=True)
    out: list[Path] = []
    for r in selected_rows(sel):
        src = candidates_dir / r.work_id / Path(r.image_rel).name
        if not src.is_file():
            continue
        dst = selected_dir / f"{r.work_id}-{Path(r.image_rel).name}"
        if not dst.is_file():
            shutil.copy2(src, dst)
        out.append(dst)
    return out
