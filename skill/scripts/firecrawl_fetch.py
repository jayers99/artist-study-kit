"""Thin, testable wrapper over the Firecrawl scrape API (HTML -> markdown).

The network boundary is injected: callers pass a client exposing `.scrape(url)`.
`normalize_scrape` is pure so all parsing is fixture-tested without live calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedPage:
    """A scraped page reduced to what the grader needs."""

    url: str
    final_url: str
    status_code: int
    markdown: str
    metadata: dict


def normalize_scrape(url: str, resp: object) -> FetchedPage:
    """Reduce a Firecrawl scrape response to a `FetchedPage` (pure)."""
    doc = getattr(resp, "data", None) or resp
    markdown = getattr(doc, "markdown", "") or ""
    metadata = getattr(doc, "metadata", None) or {}
    final_url = metadata.get("url") or metadata.get("sourceURL") or url
    status_code = int(metadata.get("statusCode") or 0)
    return FetchedPage(
        url=url,
        final_url=final_url,
        status_code=status_code,
        markdown=markdown,
        metadata=dict(metadata),
    )


def fetch_page(url: str, *, client: object | None = None) -> FetchedPage:
    """Scrape `url` to a `FetchedPage`; build a default client if none given."""
    if client is None:
        from firecrawl import Firecrawl  # lazy: avoids import cost / key need in tests

        client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    return normalize_scrape(url, client.scrape(url))
