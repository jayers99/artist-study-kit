from scripts.wikidata import commons_filepath


def test_commons_filepath_encodes_spaces_and_adds_width():
    url = commons_filepath("Paul Klee Fish Magic.jpg")
    assert url == ("https://commons.wikimedia.org/wiki/Special:FilePath/"
                   "Paul_Klee_Fish_Magic.jpg?width=400")


def test_commons_filepath_urlencodes_reserved_chars_and_custom_width():
    url = commons_filepath("Müller & Sohn.jpg", width=1686)
    assert url.startswith("https://commons.wikimedia.org/wiki/Special:FilePath/")
    assert "M%C3%BCller_%26_Sohn.jpg" in url
    assert url.endswith("?width=1686")
