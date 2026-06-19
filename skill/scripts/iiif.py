"""Stage-5 image discovery: parse IIIF manifests/info.json into validated candidates.

Pure parsing + validation; byte download lives in image_download.py. Rights default
to 'restricted' when absent (spec: treat missing rights as restricted).
"""

from __future__ import annotations

from dataclasses import dataclass

INSTITUTION_PRIORITY: tuple[str, ...] = (
    "met",
    "rijksmuseum",
    "aic",
    "harvard",
    "europeana",
    "wikimedia",
)

_PUBLIC_DOMAIN_MARKERS: tuple[str, ...] = (
    "public domain",
    "publicdomain",
    "cc0",
    "no known copyright",
)


@dataclass(frozen=True)
class ImageCandidate:
    work_id: str
    institution: str
    label: str
    iiif_id: str
    image_url: str
    width: int
    height: int
    license: str | None
    rights_status: str


def institution_rank(institution: str) -> int:
    """Lower = higher priority; unknown institutions sort after all known ones."""
    inst = institution.lower()
    return INSTITUTION_PRIORITY.index(inst) if inst in INSTITUTION_PRIORITY else len(INSTITUTION_PRIORITY)


def classify_rights(value: str | None) -> str:
    """Map a license/rights string to public_domain / restricted / unknown."""
    if not value or not value.strip():
        return "restricted"
    low = value.lower()
    if any(marker in low for marker in _PUBLIC_DOMAIN_MARKERS):
        return "public_domain"
    return "unknown"


def max_image_url(iiif_id: str) -> str:
    """Build the IIIF Image API request for the largest available rendition."""
    return f"{iiif_id.rstrip('/')}/full/max/0/default.jpg"


def parse_info_json(info: dict) -> tuple[str, int, int]:
    """Extract (iiif_id, width, height) from an Image API info.json."""
    iiif_id = info.get("@id") or info.get("id") or ""
    return iiif_id, int(info.get("width", 0)), int(info.get("height", 0))


def _manifest_rights(manifest: dict) -> str | None:
    for entry in manifest.get("metadata", []):
        label = str(entry.get("label", "")).lower()
        if "right" in label or "license" in label:
            return entry.get("value")
    return manifest.get("rights") or manifest.get("license")


def parse_manifest(manifest: dict, *, work_id: str, institution: str) -> list[ImageCandidate]:
    """Flatten a IIIF Presentation v2 manifest into image candidates."""
    rights_value = _manifest_rights(manifest)
    rights_status = classify_rights(rights_value)
    candidates: list[ImageCandidate] = []
    for seq in manifest.get("sequences", []):
        for canvas in seq.get("canvases", []):
            label = str(canvas.get("label", manifest.get("label", "")))
            for image in canvas.get("images", []):
                resource = image.get("resource", {})
                service = resource.get("service", {})
                iiif_id = service.get("@id") or service.get("id")
                if not iiif_id:
                    continue
                candidates.append(
                    ImageCandidate(
                        work_id=work_id,
                        institution=institution.lower(),
                        label=label,
                        iiif_id=iiif_id,
                        image_url=max_image_url(iiif_id),
                        width=int(resource.get("width", 0)),
                        height=int(resource.get("height", 0)),
                        license=rights_value,
                        rights_status=rights_status,
                    )
                )
    return candidates


def meets_resolution(c: ImageCandidate, *, min_long_edge: int = 1500) -> bool:
    """True when the candidate's longer pixel edge meets the study-quality floor."""
    return max(c.width, c.height) >= min_long_edge


def validate_candidate(c: ImageCandidate, *, min_long_edge: int = 1500) -> tuple[bool, list[str]]:
    """Return (passed, reasons). Restricted rights or low resolution fail."""
    reasons: list[str] = []
    if c.rights_status == "restricted":
        reasons.append("rights: restricted or missing")
    if not meets_resolution(c, min_long_edge=min_long_edge):
        reasons.append(f"resolution: long edge {max(c.width, c.height)} < {min_long_edge}")
    return (not reasons, reasons)
