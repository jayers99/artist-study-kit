def test_deps_importable():
    import imagehash  # noqa: F401
    from PIL import Image  # noqa: F401
    assert hasattr(imagehash, "phash")


from pathlib import Path
from PIL import Image, ImageDraw
from scripts.image_similarity import (
    DUP_THRESHOLD, ImageHashes, perceptual_hashes, image_dims,
    hamming_sim, score, is_duplicate,
)


def _make_img(path, seed=0, size=(256, 256)):
    """Deterministic 4x4 colored-block pattern; distinct seeds -> distinct images."""
    img = Image.new("RGB", size, "white")
    d = ImageDraw.Draw(img)
    cw, ch = size[0] // 4, size[1] // 4
    for i in range(4):
        for j in range(4):
            v = (seed * 37 + (i * 4 + j) * 53) % 256
            d.rectangle([i * cw, j * ch, (i + 1) * cw, (j + 1) * ch],
                        fill=(v, (v * 2) % 256, (v * 3) % 256))
    img.save(path)
    return path


def test_identical_image_scores_one(tmp_path):
    p = _make_img(tmp_path / "a.png", seed=1)
    h = perceptual_hashes(p)
    assert h is not None
    assert score(h, h) == 1.0
    assert is_duplicate(score(h, h))


def test_reencode_and_resize_are_duplicates(tmp_path):
    # seed=5 at q75 gives ~0.97 margin on pHash+wHash; q30 shreds 4x4 block edges
    base = _make_img(tmp_path / "base.png", seed=5)
    img = Image.open(base).convert("RGB")
    img.save(tmp_path / "q75.jpg", quality=75)        # lossy re-encode
    img.resize((128, 128)).save(tmp_path / "half.png")  # downscale
    h0 = perceptual_hashes(base)
    assert score(h0, perceptual_hashes(tmp_path / "q75.jpg")) >= DUP_THRESHOLD
    assert score(h0, perceptual_hashes(tmp_path / "half.png")) >= DUP_THRESHOLD


def test_color_cast_is_duplicate(tmp_path):
    base = _make_img(tmp_path / "base.png", seed=3)
    img = Image.open(base).convert("RGB")
    shifted = img.point(lambda v: min(255, v + 30))   # uniform brightness shift
    shifted.save(tmp_path / "bright.png")
    assert score(perceptual_hashes(base), perceptual_hashes(tmp_path / "bright.png")) >= DUP_THRESHOLD


def test_crop_and_different_are_not_duplicates(tmp_path):
    base = _make_img(tmp_path / "base.png", seed=4)
    Image.open(base).crop((48, 48, 208, 208)).save(tmp_path / "crop.png")  # center crop
    other = _make_img(tmp_path / "other.png", seed=99)
    h0 = perceptual_hashes(base)
    assert score(h0, perceptual_hashes(tmp_path / "crop.png")) < DUP_THRESHOLD
    assert score(h0, perceptual_hashes(other)) < DUP_THRESHOLD


def test_hamming_sim_clamps_and_is_symmetric(tmp_path):
    a = perceptual_hashes(_make_img(tmp_path / "a.png", seed=5))
    b = perceptual_hashes(_make_img(tmp_path / "b.png", seed=6))
    assert hamming_sim(a.phash, a.phash) == 1.0
    assert hamming_sim(a.phash, b.phash) == hamming_sim(b.phash, a.phash)
    assert 0.0 <= hamming_sim(a.phash, b.phash) <= 1.0


def test_unreadable_returns_none(tmp_path):
    bad = tmp_path / "not-an-image.png"
    bad.write_bytes(b"garbage")
    assert perceptual_hashes(bad) is None
    assert image_dims(bad) is None
    assert perceptual_hashes(tmp_path / "missing.png") is None


def test_image_dims(tmp_path):
    p = _make_img(tmp_path / "a.png", seed=7, size=(200, 120))
    w, h, b = image_dims(p)
    assert (w, h) == (200, 120)
    assert b > 0
