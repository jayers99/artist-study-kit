"""Shared Obsidian-native markdown helpers for the study-package emitters.

Centralizes frontmatter + table-cell escaping so every emitter tags consistently with
the project taxonomy (CLAUDE.md §Markdown): every study doc carries `#artist/<slug>` and
a `#<doc-type>` tag, plus any doc-specific domain tags (e.g. `#source-grade/<tier>`).
"""

from __future__ import annotations

from collections.abc import Iterable

from scripts.paths import slugify


def study_tags(artist: str, doc_type: str, extra_tags: Iterable[str] = ()) -> list[str]:
    """Taxonomy tags for a study doc: artist + doc-type, then any extras."""
    return [f"#artist/{slugify(artist)}", f"#{doc_type}", *extra_tags]


def frontmatter(doc_type: str, artist: str, *, extra_tags: Iterable[str] = ()) -> list[str]:
    """YAML frontmatter lines (through the closing fence + blank line)."""
    lines = ["---", f"type: {doc_type}", f"artist: {artist}", "tags:"]
    lines += [f"  - '{tag}'" for tag in study_tags(artist, doc_type, extra_tags)]
    lines += ["---", ""]
    return lines


def cell(text: str) -> str:
    """Escape a pipe so it doesn't break a markdown table cell."""
    return str(text).replace("|", "\\|")
