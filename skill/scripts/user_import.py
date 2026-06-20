"""Thrust 2 — inject the user's own image collection as origin:"user" candidates.

Claude (the agent, in SKILL.md) views each image and emits a guess
{filename, source_path, artist, title, date}. Everything below is pure logic with
injected `lookup`/`copy_file` seams: verify each guess against the discovery
pipeline, build a human-reviewed import-review artifact, and ingest confirmed rows
into the package's candidates[].
"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field, replace
from pathlib import Path

from scripts.paths import slugify

IMPORT_STATES: tuple[str, ...] = ("confirmed", "proposed", "off_artist", "unidentified")


@dataclass(frozen=True)
class ImportRow:
    filename: str
    source_path: str
    state: str
    artist: str = ""
    title: str = ""
    date: str = ""
    qid: str = ""
    museum: str = ""
    source_url: str = ""
    rights: str = ""
    medium: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    work_id: str = ""

    def to_dict(self) -> dict:
        return {
            "filename": self.filename, "source_path": self.source_path,
            "state": self.state, "artist": self.artist, "title": self.title,
            "date": self.date, "qid": self.qid, "museum": self.museum,
            "source_url": self.source_url, "rights": self.rights,
            "medium": self.medium, "inst_ids": [list(p) for p in self.inst_ids],
            "work_id": self.work_id,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ImportRow":
        return cls(
            filename=d.get("filename", ""), source_path=d.get("source_path", ""),
            state=d.get("state", "unidentified"), artist=d.get("artist", ""),
            title=d.get("title", ""), date=d.get("date", ""), qid=d.get("qid", ""),
            museum=d.get("museum", ""), source_url=d.get("source_url", ""),
            rights=d.get("rights", ""), medium=d.get("medium", ""),
            inst_ids=tuple((str(a), str(b)) for a, b in d.get("inst_ids", ())),
            work_id=d.get("work_id", ""),
        )


def slug_work_id(title: str, filename: str, existing: set[str]) -> str:
    base = slugify(title) if title.strip() else slugify(Path(filename).stem)
    if base not in existing:
        return base
    n = 2
    while f"{base}-{n}" in existing:
        n += 1
    return f"{base}-{n}"


def _fold(text: str) -> str:
    return " ".join(str(text).strip().lower().split())


def verify_identification(guess: dict, study_artist: str, *, lookup) -> ImportRow:
    filename = str(guess.get("filename", ""))
    base = ImportRow(
        filename=filename, source_path=str(guess.get("source_path", "")),
        state="unidentified", artist=str(guess.get("artist", "")).strip(),
        title=str(guess.get("title", "")).strip(),
        date=str(guess.get("date", "")).strip())
    if not base.title:
        return base
    if base.artist and _fold(base.artist) != _fold(study_artist):
        return replace(base, state="off_artist")
    record = lookup(study_artist, base.title)
    if record:
        return replace(
            base, state="confirmed",
            title=str(record.get("title") or base.title),
            date=str(record.get("date") or base.date),
            qid=str(record.get("qid", "")), museum=str(record.get("museum", "")),
            source_url=str(record.get("source_url", "")),
            rights=str(record.get("rights") or "unknown"),
            medium=str(record.get("medium", "")),
            inst_ids=tuple((str(a), str(b)) for a, b in record.get("inst_ids", ())))
    return replace(base, state="proposed", rights="unknown")
