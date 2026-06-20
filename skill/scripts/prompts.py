"""Persist the reusable prompt artifacts a run uses into prompts/ (output contract).

Each stage that runs on an LLM prompt (image-search query, the 5-stage analysis
instruction, etc.) saves it here so the study package is reproducible. Obsidian-native
frontmatter; idempotent (re-saving overwrites the same slug).
"""

from __future__ import annotations

from pathlib import Path


def save_prompt(
    prompts_dir: Path | str,
    slug: str,
    text: str,
    *,
    artist: str = "",
    stage: str = "",
) -> Path:
    """Write prompts/<slug>.md with frontmatter + the prompt body; return its path."""
    prompts_dir = Path(prompts_dir)
    prompts_dir.mkdir(parents=True, exist_ok=True)
    path = prompts_dir / f"{slug}.md"
    lines = [
        "---",
        "type: study/prompt",
        f"artist: {artist}",
        f"stage: {stage}",
        "tags:",
        "  - 'study/prompt'",
        "---",
        "",
        text.strip(),
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path
