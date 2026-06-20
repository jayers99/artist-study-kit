"""Curation-interview stage: turn rated works into ordered study targets and briefs.

The Socratic interview itself is SKILL.md prose (the AI is the interviewer). This module
owns the deterministic, testable parts: order the interview queue (merging study->final
pairs), (de)serialize the resulting study briefs, write the artifacts, and gate that every
queued target has a complete brief before the stage closes.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from scripts._md import frontmatter
from scripts.selection import Rating

_NO_CLUSTER = "~"  # sentinel: works without a cluster sort after named clusters


@dataclass(frozen=True)
class StudyTarget:
    work_id: str          # the primary (final) work
    title: str
    year: str
    medium: str
    cluster: str
    source_url: str
    members: tuple[str, ...]  # (work_id, *merged_study_ids); len > 1 = merged pair


def build_queue(liked_ratings: list[Rating], work_meta: dict[str, dict]) -> list[StudyTarget]:
    """Order liked works for the interview, merging study->final pairs.

    `work_meta[work_id]` may carry `cluster` (str), `studyability` (int), and `study_for`
    (the work_id this one is a preparatory study for). When a work's `study_for` names
    another liked work, the two collapse into one target (final first).
    """
    liked_ids = {r.work_id for r in liked_ratings}
    merged_into: dict[str, list[str]] = {}
    is_merged: set[str] = set()
    for r in liked_ratings:
        final = (work_meta.get(r.work_id) or {}).get("study_for") or ""
        if final and final in liked_ids and final != r.work_id:
            merged_into.setdefault(final, []).append(r.work_id)
            is_merged.add(r.work_id)

    targets: list[StudyTarget] = []
    for r in liked_ratings:
        if r.work_id in is_merged:
            continue
        meta = work_meta.get(r.work_id) or {}
        studies = tuple(sorted(merged_into.get(r.work_id, [])))
        targets.append(StudyTarget(
            work_id=r.work_id,
            title=r.title,
            year=r.date,
            medium=r.medium,
            cluster=meta.get("cluster", "") or "",
            source_url=r.source_url,
            members=(r.work_id, *studies),
        ))

    def sort_key(t: StudyTarget):
        studyability = (work_meta.get(t.work_id) or {}).get("studyability", -1)
        return (t.cluster or _NO_CLUSTER, -studyability, t.work_id)

    return sorted(targets, key=sort_key)


@dataclass(frozen=True)
class StudyStep:
    step: str
    success_test: str = ""


@dataclass(frozen=True)
class StudyBrief:
    work_id: str
    title: str
    year: str
    members: tuple[str, ...]
    cluster: str
    source_url: str
    thesis: str
    anchor_trait: str
    study_plan: tuple[StudyStep, ...]


def serialize_briefs(artist: str, briefs: list[StudyBrief]) -> dict:
    """Build the study-briefs.json payload (empty success_test -> null)."""
    return {
        "artist": artist,
        "briefs": [
            {
                "work_id": b.work_id,
                "title": b.title,
                "year": b.year,
                "members": list(b.members),
                "cluster": b.cluster,
                "source_url": b.source_url,
                "thesis": b.thesis,
                "anchor_trait": b.anchor_trait,
                "study_plan": [
                    {"step": s.step, "success_test": s.success_test or None}
                    for s in b.study_plan
                ],
            }
            for b in briefs
        ],
    }


def parse_briefs(data: dict) -> list[StudyBrief]:
    """Parse a study-briefs.json payload back into StudyBriefs (null test -> '')."""
    out: list[StudyBrief] = []
    for d in data.get("briefs", []):
        steps = tuple(
            StudyStep(step=str(s.get("step", "")), success_test=str(s.get("success_test") or ""))
            for s in d.get("study_plan", [])
        )
        out.append(StudyBrief(
            work_id=str(d.get("work_id", "")),
            title=str(d.get("title", "")),
            year=str(d.get("year", "")),
            members=tuple(str(m) for m in d.get("members", [])),
            cluster=str(d.get("cluster", "")),
            source_url=str(d.get("source_url", "")),
            thesis=str(d.get("thesis", "")),
            anchor_trait=str(d.get("anchor_trait", "")),
            study_plan=steps,
        ))
    return out


def write_study_briefs_json(artist: str, briefs: list[StudyBrief], path: Path | str) -> Path:
    """Persist the machine-readable study briefs."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(serialize_briefs(artist, briefs), indent=2) + "\n", encoding="utf-8")
    return path


def write_study_briefs_md(artist: str, briefs: list[StudyBrief], path: Path | str) -> Path:
    """Write the Obsidian-native study briefs (one callout per study target)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = frontmatter("study/curation-briefs", artist) + [f"# Study briefs — {artist}", ""]
    for b in briefs:
        lines += [
            f"> [!example] {b.title} ({b.year})",
            f"> **Thesis:** {b.thesis}",
            f"> **Anchor trait:** {b.anchor_trait}",
            "> **Study plan:**",
        ]
        for i, s in enumerate(b.study_plan, 1):
            lines.append(f"> {i}. {s.step}")
            if s.success_test:
                lines.append(f">    *Test:* {s.success_test}")
        lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def pending_targets(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[StudyTarget]:
    """Targets that do not yet have a study brief (resume support)."""
    done = {b.work_id for b in briefs}
    return [t for t in queue if t.work_id not in done]


def validate_briefs(queue: list[StudyTarget], briefs: list[StudyBrief]) -> list[str]:
    """Return errors; empty means every queued target has a complete brief."""
    by_id = {b.work_id: b for b in briefs}
    errors: list[str] = []
    for t in queue:
        b = by_id.get(t.work_id)
        if b is None:
            errors.append(f"{t.work_id}: no study brief")
            continue
        if not b.thesis.strip():
            errors.append(f"{t.work_id}: empty thesis")
        if not b.anchor_trait.strip():
            errors.append(f"{t.work_id}: empty anchor_trait")
        if not b.study_plan:
            errors.append(f"{t.work_id}: empty study_plan")
    return errors
