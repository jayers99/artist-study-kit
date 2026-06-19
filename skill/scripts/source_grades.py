"""Stage-2 pass 2 plumbing: weighted scoring, A-F tiers, and serialization.

The LLM supplies per-dimension rubric scores (0-100) inside SKILL.md; this module
turns them into a weighted score + tier and writes sources.json / source-grades.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.source_signals import SignalScan

RUBRIC_WEIGHTS: dict[str, int] = {
    "authority": 30,
    "depth": 25,
    "commercial_bias": 20,
    "citations": 15,
    "usability": 10,
}

# (lower-inclusive bound, tier), highest first.
_TIER_CUTOFFS: tuple[tuple[int, str], ...] = (
    (85, "A"),
    (70, "B"),
    (55, "C"),
    (40, "D"),
    (25, "E"),
    (0, "F"),
)


@dataclass(frozen=True)
class RubricScores:
    authority: int
    depth: int
    commercial_bias: int
    citations: int
    usability: int


@dataclass(frozen=True)
class GradedSource:
    url: str
    title: str
    signals: SignalScan
    rubric: RubricScores | None
    score: int
    tier: str
    use_for: str
    avoid_for: str


def weighted_score(rubric: RubricScores) -> int:
    """Weighted average of the five rubric dimensions, rounded to 1-100."""
    total = sum(getattr(rubric, dim) * w for dim, w in RUBRIC_WEIGHTS.items())
    return round(total / 100)


def score_to_tier(score: int) -> str:
    for bound, tier in _TIER_CUTOFFS:
        if score >= bound:
            return tier
    return "F"


def grade_source(
    url: str,
    title: str,
    signals: SignalScan,
    rubric: RubricScores | None,
    *,
    use_for: str = "",
    avoid_for: str = "",
) -> GradedSource:
    """Assemble a GradedSource; ungraded (rubric=None) sources score 0 / tier F."""
    score = weighted_score(rubric) if rubric is not None else 0
    return GradedSource(
        url=url,
        title=title,
        signals=signals,
        rubric=rubric,
        score=score,
        tier=score_to_tier(score),
        use_for=use_for,
        avoid_for=avoid_for,
    )


def _source_to_dict(gs: GradedSource) -> dict:
    return {
        "url": gs.url,
        "title": gs.title,
        "score": gs.score,
        "tier": gs.tier,
        "use_for": gs.use_for,
        "avoid_for": gs.avoid_for,
        "signals": asdict(gs.signals),
        "rubric": asdict(gs.rubric) if gs.rubric is not None else None,
    }


def write_sources_json(sources: list[GradedSource], path: Path) -> None:
    """Persist the machine-readable graded source set."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [_source_to_dict(s) for s in sources]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_source_grades_md(sources: list[GradedSource], artist: str, path: Path) -> None:
    """Write the human-readable, Obsidian-native grade report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = sorted({f"#source-grade/{s.tier.lower()}" for s in sources})
    # Use block-style YAML list so '#' characters don't break the YAML parser.
    tag_lines = "\n".join(f"  - '{t}'" for t in tags)
    lines = [
        "---",
        "type: study/source-grades",
        f"artist: {artist}",
        "tags:",
        tag_lines,
        "---",
        "",
        f"# Source grades — {artist}",
        "",
    ]
    for s in sorted(sources, key=lambda x: x.score, reverse=True):
        signals = ", ".join(s.signals.commerce_hits) or "none"
        lines += [
            f"## [{s.title}]({s.url})",
            "",
            f"- **Tier {s.tier}** · score {s.score}/100 · band `{s.signals.band}`",
            f"- Commerce signals: {signals}; citations: {s.signals.citation_count}",
            f"- Use for: {s.use_for or 'TBD by reviewer'}",
            f"- Avoid for: {s.avoid_for or 'TBD by reviewer'}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
