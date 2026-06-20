"""Stage 6 plumbing: score + rank study-set candidates and emit preference-synthesis.md.

Claude supplies the cross-set pattern insight (prose) and per-candidate pattern-fit /
studyability scores (0-100, the art-historical judgment); this module computes the
combined score, ranks the funnel, and serializes the Obsidian-native note.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts._md import cell as _cell
from scripts._md import frontmatter

PREFERENCE_WEIGHTS: dict[str, int] = {"pattern_fit": 50, "studyability": 50}


@dataclass(frozen=True)
class StudyCandidate:
    work_id: str
    title: str
    pattern_fit: int
    studyability: int
    rationale: str


def combined_score(c: StudyCandidate) -> int:
    """Weighted average of pattern-fit + studyability, rounded to 0-100."""
    total = c.pattern_fit * PREFERENCE_WEIGHTS["pattern_fit"] + c.studyability * PREFERENCE_WEIGHTS["studyability"]
    return round(total / 100)


def rank_candidates(cands: list[StudyCandidate]) -> list[StudyCandidate]:
    """Descending by combined score; stable for ties."""
    return sorted(cands, key=combined_score, reverse=True)


def write_preference_synthesis_md(
    insight: str,
    cands: list[StudyCandidate],
    artist: str,
    path: Path | str,
    *,
    shortlist_cap: int = 8,
) -> None:
    """Emit the 'what you're drawn to' note + the ranked funnel (capped)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    ranked = rank_candidates(cands)
    lines = frontmatter("study/preference-synthesis", artist) + [
        f"# What you're drawn to — {artist}",
        "",
        "> [!tip] Pattern across your liked set",
        f"> {insight}",
        "",
        "## Ranked study-set candidates",
        "",
        "Scored on pattern-fit + studyability. Pick your final small study set from the top.",
        "",
        "| Rank | Work | Score | Pattern-fit | Studyability | Why |",
        "| ---- | ---- | ----- | ----------- | ------------ | --- |",
    ]
    for i, c in enumerate(ranked[:shortlist_cap], start=1):
        lines.append(
            f"| {i} | [[{c.work_id}\\|{_cell(c.title)}]] | {combined_score(c)} | "
            f"{c.pattern_fit} | {c.studyability} | {_cell(c.rationale)} |"
        )
    if len(ranked) > shortlist_cap:
        dropped = len(ranked) - shortlist_cap
        lines += [
            "",
            f"> [!note] {dropped} more candidate(s) fell below the shortlist cap "
            f"({shortlist_cap}) and are omitted from the ranked table.",
        ]
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
