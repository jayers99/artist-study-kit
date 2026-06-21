# skill/scripts/image_similarity.py
"""Spec A — pure, offline perceptual image similarity (pHash + wHash).

No network. Fail-open: any unreadable/un-hashable image yields None so the
caller never treats it as a duplicate. Hashes are hex strings (manifest-safe).
"""
from __future__ import annotations

import os
from dataclasses import dataclass

import imagehash
from PIL import Image

DUP_THRESHOLD = 0.90
HASH_SIZE = 8
HASH_BITS = HASH_SIZE * HASH_SIZE  # 64
_LOAD_BOX = (1024, 1024)  # bound intermediate decode cost; pHash downsamples anyway


@dataclass(frozen=True)
class ImageHashes:
    phash: str
    whash: str


def perceptual_hashes(path) -> "ImageHashes | None":
    try:
        with Image.open(path) as im:
            im.draft("RGB", _LOAD_BOX)        # cheap pre-scale for JPEG (no-op otherwise)
            rgb = im.convert("RGB")
            rgb.thumbnail(_LOAD_BOX)           # bound non-JPEG (PSD/PNG) memory
            ph = imagehash.phash(rgb, hash_size=HASH_SIZE)
            wh = imagehash.whash(rgb, hash_size=HASH_SIZE)
        return ImageHashes(phash=str(ph), whash=str(wh))
    except Exception:
        return None


def image_dims(path) -> "tuple[int, int, int] | None":
    try:
        size = os.path.getsize(path)
        with Image.open(path) as im:
            w, h = im.size                     # header read, no full decode
        return (int(w), int(h), int(size))
    except Exception:
        return None


def hamming_sim(hex_a: str, hex_b: str) -> float:
    d = imagehash.hex_to_hash(hex_a) - imagehash.hex_to_hash(hex_b)
    return max(0.0, min(1.0, 1.0 - d / HASH_BITS))


def score(a: ImageHashes, b: ImageHashes) -> float:
    return min(hamming_sim(a.phash, b.phash), hamming_sim(a.whash, b.whash))


def is_duplicate(s: float, threshold: float = DUP_THRESHOLD) -> bool:
    return s >= threshold
