"""Per-artist study-package paths and scaffolding (the output contract)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def slugify(name: str) -> str:
    """Filesystem- and Obsidian-safe kebab-case slug for an artist name."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "untitled"


@dataclass(frozen=True)
class StudyPaths:
    """Resolved paths for a single artist's study package."""

    root: Path

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    @property
    def sources_json(self) -> Path:
        return self.sources_dir / "sources.json"

    @property
    def source_grades_md(self) -> Path:
        return self.sources_dir / "source-grades.md"

    @property
    def works_md(self) -> Path:
        return self.root / "works.md"

    @property
    def images_dir(self) -> Path:
        return self.root / "images"

    @property
    def candidates_dir(self) -> Path:
        return self.images_dir / "candidates"

    @property
    def selected_dir(self) -> Path:
        return self.images_dir / "selected"

    @property
    def gallery_html(self) -> Path:
        return self.root / "gallery.html"

    @property
    def selection_json(self) -> Path:
        return self.root / "selection.json"

    @property
    def study_briefs_json(self) -> Path:
        return self.root / "study-briefs.json"

    @property
    def study_briefs_md(self) -> Path:
        return self.root / "study-briefs.md"

    @property
    def preference_synthesis_md(self) -> Path:
        return self.root / "preference-synthesis.md"

    @property
    def analysis_md(self) -> Path:
        return self.root / "analysis.md"

    @property
    def study_notes_md(self) -> Path:
        return self.root / "study-notes.md"

    @property
    def drills_dir(self) -> Path:
        return self.root / "drills"

    @property
    def review_schedule_md(self) -> Path:
        return self.root / "review-schedule.md"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def state_json(self) -> Path:
        return self.root / "state.json"

    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id


_SCAFFOLD_DIRS = (
    "sources",
    "images",
    "images/candidates",
    "images/selected",
    "drills",
    "prompts",
    "sessions",
)


def study_paths(base: Path | str, artist: str) -> StudyPaths:
    """Compute (without creating) the study-package paths for an artist."""
    return StudyPaths(root=Path(base) / slugify(artist))


def scaffold(base: Path | str, artist: str) -> StudyPaths:
    """Create the study-package directory tree; idempotent."""
    sp = study_paths(base, artist)
    sp.root.mkdir(parents=True, exist_ok=True)
    for rel in _SCAFFOLD_DIRS:
        (sp.root / rel).mkdir(parents=True, exist_ok=True)
    return sp
