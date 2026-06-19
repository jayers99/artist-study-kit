"""Parse YAML frontmatter from markdown (skill + Obsidian outputs)."""

from __future__ import annotations

import yaml


def parse_frontmatter(text: str) -> dict:
    """Return the YAML mapping between leading `---` fences, or `{}`."""
    if not text.startswith("---\n"):
        return {}
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        return {}
    block = rest[:end]
    data = yaml.safe_load(block)
    return data if isinstance(data, dict) else {}
