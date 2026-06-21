"""Spec A — the library manifest: provenance record AND dedup index.

One JSON document (path supplied by caller). find_match() is the perceptual
lookup used by the dedup engine; entries store hex hashes so later runs match
without re-hashing the whole library.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

from scripts.image_similarity import DUP_THRESHOLD, ImageHashes, score


@dataclass
class ManifestEntry:
    work_id: str
    title: str = ""
    date: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    filename: str = ""
    path: str = ""
    width: int = 0
    height: int = 0
    bytes: int = 0
    phash: str = ""
    whash: str = ""
    rights: str = ""
    medium: str = ""
    stars: int = 0
    origins: list = field(default_factory=list)

    def hashes(self) -> "ImageHashes | None":
        if self.phash and self.whash:
            return ImageHashes(self.phash, self.whash)
        return None

    def to_dict(self) -> dict:
        return {
            "work_id": self.work_id, "title": self.title, "date": self.date,
            "qid": self.qid, "inst_ids": [list(p) for p in self.inst_ids],
            "filename": self.filename, "path": self.path,
            "width": self.width, "height": self.height, "bytes": self.bytes,
            "phash": self.phash, "whash": self.whash, "rights": self.rights,
            "medium": self.medium, "stars": self.stars, "origins": self.origins,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "ManifestEntry":
        return cls(
            work_id=d["work_id"], title=d.get("title", ""), date=d.get("date", ""),
            qid=d.get("qid", ""),
            inst_ids=tuple((str(a), str(b)) for a, b in d.get("inst_ids", ())),
            filename=d.get("filename", ""), path=d.get("path", ""),
            width=int(d.get("width", 0)), height=int(d.get("height", 0)),
            bytes=int(d.get("bytes", 0)), phash=d.get("phash", ""),
            whash=d.get("whash", ""), rights=d.get("rights", ""),
            medium=d.get("medium", ""), stars=int(d.get("stars", 0)),
            origins=list(d.get("origins", [])),
        )


@dataclass
class Manifest:
    entries: list = field(default_factory=list)

    @classmethod
    def load(cls, path) -> "Manifest":
        p = Path(path)
        if not p.exists():
            return cls(entries=[])
        data = json.loads(p.read_text())
        return cls(entries=[ManifestEntry.from_dict(d) for d in data.get("entries", [])])

    def save(self, path) -> None:
        Path(path).write_text(json.dumps(
            {"entries": [e.to_dict() for e in self.entries]}, indent=2))

    def find_match(self, h: ImageHashes, threshold: float = DUP_THRESHOLD):
        best = None
        best_s = -1.0
        for e in self.entries:
            eh = e.hashes()
            if eh is None:
                continue
            s = score(h, eh)
            if s >= threshold and s > best_s:
                best_s = s
                best = e
        return best

    def upsert(self, entry: ManifestEntry) -> None:
        for i, e in enumerate(self.entries):
            if e.work_id == entry.work_id:
                self.entries[i] = entry
                return
        self.entries.append(entry)
