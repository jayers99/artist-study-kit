"""Date-string helpers for sorting the curation board."""

from __future__ import annotations

import re

_YEAR = re.compile(r"\d{4}")


def parse_year(date: str) -> int | None:
    """First 4-digit run in the string as the sort year; None if none present.

    Handles "1889", "c. 1889", ranges ("1889-1890" -> 1889), and month prefixes
    ("May 1889" -> 1889). "" / "n.d." / non-numeric -> None (sorts last)."""
    if not date:
        return None
    match = _YEAR.search(date)
    return int(match.group()) if match else None
