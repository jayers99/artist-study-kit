"""Stage-2 pass 1: cheap deterministic signal-scan over fetched markdown.

Flags commerce/citation/TLD signals and a coarse band so SKILL.md only runs the
LLM rubric (pass 2) on borderline or high-value pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from scripts.firecrawl_fetch import FetchedPage

SHORTLIST_DOMAINS: frozenset[str] = frozenset(
    {"smarthistory.org", "metmuseum.org", "collegeart.org"}  # Smarthistory, Met, CAA
)

# Generic + national academic/cultural TLDs treated as higher trust.
TRUSTED_TLDS: frozenset[str] = frozenset({"edu", "gov", "museum", "ac.uk"})

COMMERCE_PATTERNS: tuple[str, ...] = (
    r"add to cart",
    r"buy now",
    r"make an offer",
    r"add to basket",
    r"shipping calculated",
    r"\$\s?\d[\d,]*",
    r"estimate:\s*\$",
)

CITATION_PATTERNS: tuple[str, ...] = (
    r"\[\d+\]",
    r"\bfootnotes?\b",
    r"\breferences?\b",
    r"\bbibliography\b",
    r"\bprovenance\b",
    r"catalogue raisonn",
)


@dataclass(frozen=True)
class SignalScan:
    domain: str
    tld: str
    tld_trust: str
    commerce_hits: list[str]
    citation_count: int
    shortlisted: bool
    band: str
    needs_llm_review: bool


def _domain(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _tld(domain: str) -> str:
    if domain.endswith(".ac.uk"):
        return "ac.uk"
    return domain.rsplit(".", 1)[-1] if "." in domain else ""


def scan_source(page: FetchedPage) -> SignalScan:
    """Run pass-1 signal detection on a fetched page (pure)."""
    domain = _domain(page.final_url or page.url)
    tld = _tld(domain)
    text = page.markdown.lower()

    commerce_hits = [p for p in COMMERCE_PATTERNS if re.search(p, text)]
    citation_count = sum(len(re.findall(p, text)) for p in CITATION_PATTERNS)
    shortlisted = domain in SHORTLIST_DOMAINS

    if tld in TRUSTED_TLDS or shortlisted:
        tld_trust = "trusted"
    elif len(commerce_hits) >= 2:
        tld_trust = "commercial"
    else:
        tld_trust = "neutral"

    if shortlisted or (tld_trust == "trusted" and citation_count >= 2):
        band = "high"
    elif tld_trust == "commercial" and citation_count < 2:
        band = "low"
    else:
        band = "borderline"

    # Only borderline pages need LLM rubric scoring; high/low bands are graded by signal alone.
    needs_llm_review = band == "borderline"

    return SignalScan(
        domain=domain,
        tld=tld,
        tld_trust=tld_trust,
        commerce_hits=commerce_hits,
        citation_count=citation_count,
        shortlisted=shortlisted,
        band=band,
        needs_llm_review=needs_llm_review,
    )
