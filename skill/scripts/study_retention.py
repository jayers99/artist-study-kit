"""Stage 8 emitters: study-notes.md (faded aids), discrimination cards, review schedule.

MVP (spec section 9 defers full FSRS deck + gapped-worksheet generators). Claude supplies
the pedagogy content; this module serializes the Obsidian-native artifacts with the
faded-aids structure (cheat sheet -> checklist -> bare prompt) and study callouts.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


def _cell(text: str) -> str:
    """Escape a pipe so it doesn't break the markdown table cell."""
    return str(text).replace("|", "\\|")


@dataclass(frozen=True)
class StudyNote:
    work_id: str
    title: str
    notice_first: str
    decisions_to_imitate: list[str]
    traps: list[str]
    exercises: list[str]


@dataclass(frozen=True)
class DiscriminationCard:
    trait: str
    is_a: str
    not_a: str


@dataclass(frozen=True)
class ReviewItem:
    day: int
    focus: str
    mode: str


def _frontmatter(doc_type: str, artist: str) -> list[str]:
    return ["---", f"type: {doc_type}", f"artist: {artist}", "tags:",
            f"  - '{doc_type}'", "---", ""]


def write_study_notes_md(notes: list[StudyNote], artist: str, path: Path | str) -> None:
    """Per-work notes as faded aids: cheat sheet -> checklist -> bare prompt."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/notes", artist) + [f"# Study notes — {artist}", ""]
    for n in notes:
        lines += [f"## {n.title}", f"**Work:** [[{n.work_id}]]", ""]
        # Aid 1 — cheat sheet (most support)
        lines += ["### Cheat sheet", f"> [!tip] Notice first", f"> {n.notice_first}", ""]
        lines += ["Decisions to imitate:"]
        lines += [f"- {d}" for d in n.decisions_to_imitate]
        lines += ["", "> [!warning] Traps"]
        lines += [f"> - {t}" for t in n.traps]
        lines += [""]
        # Aid 2 — checklist (less support)
        lines += ["### Checklist", "Before you call the study done:"]
        lines += [f"- [ ] {d}" for d in n.decisions_to_imitate]
        lines += [""]
        # Aid 3 — bare prompt (no support)
        lines += ["### Bare prompt",
                  f"> [!example] From memory", f"> {n.exercises[0] if n.exercises else 'Reproduce the value structure from memory.'}",
                  ""]
        if len(n.exercises) > 1:
            lines += ["Further exercises:"] + [f"- {e}" for e in n.exercises[1:]] + [""]
    path.write_text("\n".join(lines), encoding="utf-8")


def write_discrimination_cards_md(cards: list[DiscriminationCard], artist: str, path: Path | str) -> None:
    """A-vs-not-A perceptual discrimination set (interleaving drill)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/drills", artist) + [
        f"# Discrimination cards — {artist}", "",
        "| Trait | Is (A) | Is not (not-A) |",
        "| ----- | ------ | -------------- |",
    ]
    for c in cards:
        lines.append(f"| {_cell(c.trait)} | {_cell(c.is_a)} | {_cell(c.not_a)} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")


def write_review_schedule_md(items: list[ReviewItem], artist: str, path: Path | str) -> None:
    """Spaced + interleaved review plan."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _frontmatter("study/review-schedule", artist) + [
        f"# Review schedule — {artist}", "",
        "Spaced + interleaved across works and styles.", "",
        "| When | Focus | Mode |",
        "| ---- | ----- | ---- |",
    ]
    for it in sorted(items, key=lambda x: x.day):
        lines.append(f"| Day {it.day} | {_cell(it.focus)} | {_cell(it.mode)} |")
    lines.append("")
    path.write_text("\n".join(lines), encoding="utf-8")
