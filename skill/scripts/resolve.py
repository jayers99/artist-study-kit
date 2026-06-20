"""Stage-5 post-curation: resolve SELECTED works to high-res, rights permitting.

The board (Wikidata-primary) is rights-agnostic; once the human selects works, each is
resolved to the best legally-clear image via a pluggable resolver chain:
  Commons P18 (PD/CC0) -> AIC IIIF 1686px (is_public_domain) -> else keep source_url.
Resolvers return an ImageCandidate ONLY on a verified PD/CC0 flag; downloads reuse
image_download.download_candidate. Network is injected so tests stay offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from scripts import commons
from scripts.iiif import ImageCandidate
from scripts.image_download import download_candidate
from scripts.museum_search import AIC_IIIF_DEFAULT, default_aic_fetch


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


def aic_resolver(entry, *, fetch=None):
    """Resolve via the work's AIC record (IIIF 1686px, public-domain only)."""
    fetch = fetch or default_aic_fetch
    aic_id = _find(entry.inst_ids, "aic")
    if not aic_id:
        return None
    payload = fetch(f"artworks/{aic_id}", {"fields": "id,image_id,is_public_domain"})
    data = payload.get("data") or {}
    if not data.get("is_public_domain") or not data.get("image_id"):
        return None
    iiif = (payload.get("config") or {}).get("iiif_url") or AIC_IIIF_DEFAULT
    return ImageCandidate(
        work_id=entry.work_id,
        institution="aic",
        label=entry.work_id,
        iiif_id=f"aic/{aic_id}",
        image_url=f"{iiif}/{data['image_id']}/full/1686,/0/default.jpg",
        width=1686,
        height=1686,
        license="Public Domain",
        rights_status="public_domain",
    )


@dataclass(frozen=True)
class Resolved:
    work_id: str
    rights: str  # public_domain | in_copyright
    image_path: Path | None
    image_url: str | None
    source_url: str
    license: str = ""
    institution: str = ""


RESOLVERS = (commons_resolver, aic_resolver)


def resolve_selected(entry, selected_dir, *, resolvers=RESOLVERS, download=download_candidate) -> Resolved:
    """Resolve one selected work to high-res, falling back to source_url when in copyright."""
    for resolver in resolvers:
        cand = resolver(entry)
        if cand is None:
            continue
        result = download(cand, selected_dir)
        if result.status in ("downloaded", "skipped") and result.image_path is not None:
            return Resolved(entry.work_id, "public_domain", result.image_path, cand.image_url,
                            entry.source_url, license=cand.license or "", institution=cand.institution)
    return Resolved(entry.work_id, "in_copyright", None, None, entry.source_url)
