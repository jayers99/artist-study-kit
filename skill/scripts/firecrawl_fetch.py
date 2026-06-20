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


def _metadata_dict(meta: object) -> dict:
    """Coerce Firecrawl metadata to a plain dict.

    firecrawl-py v4 returns a `DocumentMetadata` pydantic model (not a dict); older
    shapes / fixtures pass a dict. Normalize both to a dict so callers can `.get(...)`.
    """
    if meta is None:
        return {}
    if isinstance(meta, dict):
        return meta
    if hasattr(meta, "model_dump"):
        return meta.model_dump()
    return dict(meta)


def normalize_scrape(url: str, resp: object) -> FetchedPage:
    """Reduce a Firecrawl scrape response to a `FetchedPage` (pure)."""
    doc = getattr(resp, "data", None) or resp
    markdown = getattr(doc, "markdown", "") or ""
    metadata = _metadata_dict(getattr(doc, "metadata", None))
    # v4 metadata is snake_case (url/source_url/status_code); keep camelCase as fallback.
    final_url = (
        metadata.get("url") or metadata.get("source_url") or metadata.get("sourceURL") or url
    )
    status_code = int(metadata.get("status_code") or metadata.get("statusCode") or 0)
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
