def test_deps_importable():
    import imagehash  # noqa: F401
    from PIL import Image  # noqa: F401
    assert hasattr(imagehash, "phash")
