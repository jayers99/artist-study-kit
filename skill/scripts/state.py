"""Resumable, idempotent pipeline state for the artist-study-kit skill."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

STAGES: tuple[str, ...] = (
    "background",
    "source_grading",
    "style_definition",
    "works_inventory",
    "image_discovery",
    "curation_interview",
    "preference_synthesis",
    "visual_analysis",
    "study_retention",
)

# Stages that cannot start until the human supplies an artifact.
PAUSE_GATES: dict[str, str] = {
    "curation_interview": "curation complete: selection.json present",
    "preference_synthesis": "study briefs ready: study-briefs.json present",
    "visual_analysis": "study set chosen from the ranked funnel",
}

GROUPINGS: tuple[str, ...] = ("subject", "media", "technique", "other")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _next_index(items: list) -> int:
    nums = [int(x.id.rsplit("-", 1)[1]) for x in items
            if x.id.rsplit("-", 1)[-1].isdigit()]
    return (max(nums) + 1) if nums else 1


def _tuple_inst_ids(raw) -> tuple[tuple[str, str], ...]:
    return tuple((str(a), str(b)) for a, b in raw)


@dataclass
class BoardCandidate:
    work_id: str
    title: str
    date: str
    museum: str
    thumbnail_url: str
    source_url: str
    rights: str
    medium: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    origin: str = "discovered"
    first_run: str = ""

    def dedup_key(self) -> tuple:
        if self.qid:
            return ("qid", self.qid)
        if self.inst_ids:
            return ("inst", tuple(sorted(self.inst_ids)))
        return ("wid", self.work_id)

    def to_dict(self) -> dict:
        return {
            "work_id": self.work_id, "title": self.title, "date": self.date,
            "museum": self.museum, "thumbnail_url": self.thumbnail_url,
            "source_url": self.source_url, "rights": self.rights,
            "medium": self.medium, "qid": self.qid,
            "inst_ids": [list(p) for p in self.inst_ids],
            "origin": self.origin, "first_run": self.first_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoardCandidate":
        return cls(
            work_id=d["work_id"], title=d.get("title", ""), date=d.get("date", ""),
            museum=d.get("museum", ""), thumbnail_url=d.get("thumbnail_url", ""),
            source_url=d.get("source_url", ""), rights=d.get("rights", ""),
            medium=d.get("medium", ""), qid=d.get("qid", ""),
            inst_ids=_tuple_inst_ids(d.get("inst_ids", ())),
            origin=d.get("origin", "discovered"), first_run=d.get("first_run", ""),
        )

    @classmethod
    def from_thumbnail(cls, cand, *, run_id: str) -> "BoardCandidate":
        return cls(
            work_id=cand.work_id, title=cand.title, date=cand.date,
            museum=cand.museum, thumbnail_url=cand.thumbnail_url,
            source_url=cand.source_url, rights=cand.rights,
            medium=getattr(cand, "medium", ""), qid=getattr(cand, "qid", ""),
            inst_ids=_tuple_inst_ids(getattr(cand, "inst_ids", ())),
            origin="discovered", first_run=run_id,
        )


@dataclass
class DiscoveryRun:
    id: str
    at: str
    source: str
    added: int
    merged: int
    total: int
    degraded: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "at": self.at, "source": self.source,
                "added": self.added, "merged": self.merged, "total": self.total,
                "degraded": self.degraded}

    @classmethod
    def from_dict(cls, d: dict) -> "DiscoveryRun":
        return cls(id=d["id"], at=d["at"], source=d.get("source", ""),
                   added=int(d.get("added", 0)), merged=int(d.get("merged", 0)),
                   total=int(d.get("total", 0)), degraded=bool(d.get("degraded", False)))


@dataclass
class StudySession:
    id: str
    at: str
    kind: str = "study"
    theme: str = ""
    grouping: str = "other"
    selected: tuple[str, ...] = ()
    study_set: tuple[str, ...] = ()
    outputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "at": self.at, "kind": self.kind, "theme": self.theme,
                "grouping": self.grouping, "selected": list(self.selected),
                "study_set": list(self.study_set), "outputs": dict(self.outputs)}

    @classmethod
    def from_dict(cls, d: dict) -> "StudySession":
        return cls(id=d["id"], at=d["at"], kind=d.get("kind", "study"),
                   theme=d.get("theme", ""), grouping=d.get("grouping", "other"),
                   selected=tuple(d.get("selected", ())),
                   study_set=tuple(d.get("study_set", ())),
                   outputs=dict(d.get("outputs", {})))


@dataclass
class PackageState:
    artist: str
    completed: list[str] = field(default_factory=list)
    runs: list[DiscoveryRun] = field(default_factory=list)
    candidates: list[BoardCandidate] = field(default_factory=list)
    sessions: list[StudySession] = field(default_factory=list)

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

    def merge_candidates(self, new: list, run_id: str) -> tuple[int, int]:
        seen = {c.dedup_key() for c in self.candidates}
        added = merged = 0
        for cand in new:
            bc = BoardCandidate.from_thumbnail(cand, run_id=run_id)
            key = bc.dedup_key()
            if key in seen:
                merged += 1
                continue
            seen.add(key)
            self.candidates.append(bc)
            added += 1
        return added, merged

    def record_run(self, source: str, added: int, merged: int, total: int,
                   *, degraded: bool = False, now: str | None = None) -> DiscoveryRun:
        run = DiscoveryRun(id=f"run-{_next_index(self.runs)}", at=now or _now(),
                           source=source, added=added, merged=merged,
                           total=total, degraded=degraded)
        self.runs.append(run)
        return run

    def record_session(self, theme: str, grouping: str, selected, study_set,
                       outputs: dict, *, kind: str = "study",
                       now: str | None = None) -> StudySession:
        if grouping not in GROUPINGS:
            raise ValueError(f"grouping {grouping!r} not in {GROUPINGS}")
        sess = StudySession(id=f"sess-{_next_index(self.sessions)}", at=now or _now(),
                            kind=kind, theme=theme, grouping=grouping,
                            selected=tuple(selected), study_set=tuple(study_set),
                            outputs=dict(outputs))
        self.sessions.append(sess)
        return sess

    def studied_work_ids(self) -> set[str]:
        return {wid for s in self.sessions for wid in s.study_set}

    def candidate(self, work_id: str) -> "BoardCandidate | None":
        for c in self.candidates:
            if c.work_id == work_id:
                return c
        return None

    def to_dict(self) -> dict:
        return {
            "artist": self.artist,
            "completed": list(self.completed),
            "runs": [r.to_dict() for r in self.runs],
            "candidates": [c.to_dict() for c in self.candidates],
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PackageState":
        seen: set[str] = set()
        deduped = [s for s in d.get("completed", []) if not (s in seen or seen.add(s))]
        return cls(
            artist=d["artist"],
            completed=deduped,
            runs=[DiscoveryRun.from_dict(x) for x in d.get("runs", [])],
            candidates=[BoardCandidate.from_dict(x) for x in d.get("candidates", [])],
            sessions=[StudySession.from_dict(x) for x in d.get("sessions", [])],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, artist: str) -> "PackageState":
        if not path.exists():
            return cls(artist=artist)
        state = cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if state.artist != artist:
            raise ValueError(
                f"state.json artist {state.artist!r} != requested {artist!r}"
            )
        return state


PipelineState = PackageState


def migrate_legacy(state_dict: dict, selection_dict: dict | None = None,
                   *, now: str | None = None) -> PackageState:
    from scripts.selection import liked, parse_selection

    st = PackageState.from_dict(state_dict)
    if not selection_dict:
        return st

    sel = parse_selection(selection_dict)
    stamp = now or _now()
    st.runs.append(DiscoveryRun(id="run-0", at=stamp, source="legacy-import",
                                added=len(sel.ratings), merged=0, total=len(sel.ratings)))
    for r in sel.ratings:
        st.candidates.append(BoardCandidate(
            work_id=r.work_id, title=r.title, date=r.date, museum=r.museum,
            thumbnail_url=r.image_rel, source_url=r.source_url, rights=r.rights,
            medium=r.medium, qid=r.qid, inst_ids=_tuple_inst_ids(r.inst_ids),
            origin="discovered", first_run="run-0"))
    liked_ids = [r.work_id for r in liked(sel)]
    if liked_ids:
        st.sessions.append(StudySession(
            id="sess-0", at=stamp, kind="study", theme="legacy import",
            grouping="other", selected=tuple(liked_ids), study_set=tuple(liked_ids),
            outputs={"study_briefs": "study-briefs.json", "analysis": "analysis.md"}))
    return st
