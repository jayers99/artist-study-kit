"""Stage-5 post-curation: resolve SELECTED works to high-res, rights permitting.

The board (Wikidata-primary) is rights-agnostic; once the human selects works, each is
resolved to the best legally-clear image via a pluggable resolver chain:
  Commons P18 (PD/CC0) -> AIC IIIF 1686px (is_public_domain) -> else keep source_url.
Resolvers return an ImageCandidate ONLY on a verified PD/CC0 flag; downloads reuse
image_download.download_candidate. Network is injected so tests stay offline.
"""

from __future__ import annotations

from scripts import commons
from scripts.iiif import ImageCandidate


def _find(inst_ids, key: str) -> str:
    return next((v for k, v in inst_ids if k == key), "")


def commons_resolver(entry, *, fetch=None):
    """Resolve via the work's Commons file (PD/CC0 only)."""
    fetch = fetch or commons.default_fileinfo
    filename = _find(entry.inst_ids, "commons_file")
    if not filename:
        return None
    cands = commons.parse_commons_search(fetch(filename), work_id=entry.work_id, want=1)
    return cands[0] if cands else None
