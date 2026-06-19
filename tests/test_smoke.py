def test_scripts_package_importable():
    import scripts  # noqa: F401

    assert scripts.__doc__ is not None
