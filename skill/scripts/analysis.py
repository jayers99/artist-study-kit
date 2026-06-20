"""Stage 7 emitter: serialize the 5-stage formal analysis of the study set to analysis.md.

Claude does the deep-reading (the WorkAnalysis content); this module enforces the reusable
template + Obsidian formatting (predict-then-reveal as an [!example] callout, the
technique-imitation checklist as a job aid). One file, one section per study-set work.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

# The formal-analysis 5-stage instruction set (spec stage 7).
ANALYSIS_STAGES: tuple[str, ...] = (
    "Structural skeleton",
    "Notan mapping",
    "Palette archaeology",
    "Technical layering hypothesis",
    "Traps & misconceptions",
)


@dataclass(frozen=True)
class WorkAnalysis:
    work_id: str
    title: str
    structural_skeleton: str
    notan: str
    palette: str
    layering: str
    traps: str
    grammar_crosscheck: str
    imitation_checklist: list[str]
    predict_then_reveal: str


def write_analysis_md(works: list[WorkAnalysis], artist: str, path: Path | str) -> None:
    """Emit analysis.md: one section per work, all five formal-analysis stages."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "---",
        "type: study/analysis",
        f"artist: {artist}",
        "tags:",
        "  - 'study/analysis'",
        "---",
        "",
        f"# Visual analysis — {artist}",
        "",
    ]
    for w in works:
        body = {
            "Structural skeleton": w.structural_skeleton,
            "Notan mapping": w.notan,
            "Palette archaeology": w.palette,
            "Technical layering hypothesis": w.layering,
            "Traps & misconceptions": w.traps,
        }
        lines += [f"## {w.title}", f"`work: [[{w.work_id}]]`", ""]
        lines += ["> [!example] Predict, then reveal", f"> {w.predict_then_reveal}", ""]
        for stage in ANALYSIS_STAGES:
            lines += [f"### {stage}", body[stage], ""]
        lines += ["### Grammar cross-check", w.grammar_crosscheck, ""]
        lines += ["### Technique-imitation checklist"]
        lines += [f"- [ ] {item}" for item in w.imitation_checklist]
        lines += [""]
    path.write_text("\n".join(lines), encoding="utf-8")
