"""Resumable, idempotent pipeline state for the artist-study-kit skill."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

STAGES: tuple[str, ...] = (
    "background",
    "source_grading",
    "style_definition",
    "works_inventory",
    "image_discovery",
    "preference_synthesis",
    "visual_analysis",
    "study_retention",
)

# Stages that cannot start until the human supplies an artifact.
PAUSE_GATES: dict[str, str] = {
    "preference_synthesis": "curation complete: selection.json present",
    "visual_analysis": "study set chosen from the ranked funnel",
}


@dataclass
class PipelineState:
    artist: str
    completed: list[str] = field(default_factory=list)

    @property
    def next_stage(self) -> str | None:
        for stage in STAGES:
            if stage not in self.completed:
                return stage
        return None

    def is_complete(self, stage: str) -> bool:
        return stage in self.completed

    def mark_complete(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage!r}")
        if stage not in self.completed:
            self.completed.append(stage)

    def gate_for(self, stage: str) -> str | None:
        return PAUSE_GATES.get(stage)

    def to_dict(self) -> dict:
        return {"artist": self.artist, "completed": list(self.completed)}

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineState":
        return cls(artist=d["artist"], completed=list(d.get("completed", [])))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, artist: str) -> "PipelineState":
        if not path.exists():
            return cls(artist=artist, completed=[])
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
