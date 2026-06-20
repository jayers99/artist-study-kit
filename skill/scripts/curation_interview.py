"""Curation-interview stage: turn rated works into ordered study targets and briefs.

The Socratic interview itself is SKILL.md prose (the AI is the interviewer). This module
owns the deterministic, testable parts: order the interview queue (merging study->final
pairs), (de)serialize the resulting study briefs, write the artifacts, and gate that every
queued target has a complete brief before the stage closes.
"""

from __future__ import annotations

from dataclasses import dataclass

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
