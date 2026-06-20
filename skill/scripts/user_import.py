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
from scripts.museum_search import search_aic
from scripts.wikidata import search_wikidata

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


def build_review(rows: list[ImportRow], artist: str) -> tuple[dict, str]:
    json_obj = {"artist": artist, "rows": [r.to_dict() for r in rows]}
    cells = "\n".join(
        "<tr><td>{fn}</td><td class='st {st}'>{st}</td>"
        "<td>{title}</td><td>{date}</td><td>{museum}</td><td>{rights}</td></tr>".format(
            fn=_esc(r.filename), st=_esc(r.state), title=_esc(r.title),
            date=_esc(r.date), museum=_esc(r.museum), rights=_esc(r.rights))
        for r in rows)
    html = _REVIEW_TEMPLATE.replace("__ARTIST__", _esc(artist)).replace("__ROWS__", cells)
    return json_obj, html


def parse_review(json_obj: dict) -> list[ImportRow]:
    rows = [ImportRow.from_dict(d) for d in json_obj.get("rows", [])]
    return [r for r in rows if r.state == "confirmed" and r.title.strip()]


def _esc(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def make_pipeline_lookup(artist: str, *, wikidata_search=search_wikidata,
                         aic_search=search_aic):
    """Build the artist's board once; return a lookup(artist, title) closure that
    corroborates a guessed title against it. Used as verify_identification's `lookup`."""
    board = []
    try:
        cands, _works, _ambiguous = wikidata_search(artist)
        board.extend(cands)
    except Exception:
        pass
    try:
        board.extend(aic_search(artist))
    except Exception:
        pass
    index: dict[str, object] = {}
    for c in board:
        index.setdefault(_fold(c.title), c)

    def lookup(_artist: str, title: str) -> dict | None:
        c = index.get(_fold(title))
        if c is None:
            return None
        return {"title": c.title, "date": c.date, "qid": c.qid, "museum": c.museum,
                "source_url": c.source_url, "rights": c.rights,
                "medium": getattr(c, "medium", ""),
                "inst_ids": tuple(c.inst_ids)}

    return lookup


_REVIEW_TEMPLATE = """<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8">
<title>Import review — __ARTIST__</title>
<style>
  body { font-family: system-ui, sans-serif; margin: 1rem; }
  table { border-collapse: collapse; width: 100%; }
  th, td { border: 1px solid #ccc; padding: 4px 8px; font-size: 13px; text-align: left; }
  .st { font-weight: bold; }
  .st.confirmed { color: #137333; }
  .st.proposed { color: #b06000; }
  .st.off_artist, .st.unidentified { color: #a50e0e; }
</style></head><body>
<h2>Import review — __ARTIST__</h2>
<p>Edit proposed rows and set their <code>state</code> to <code>confirmed</code> in
import-review.json to keep them. off_artist / unidentified rows are set aside.</p>
<table>
<tr><th>file</th><th>state</th><th>title</th><th>date</th><th>museum</th><th>rights</th></tr>
__ROWS__
</table></body></html>
"""
