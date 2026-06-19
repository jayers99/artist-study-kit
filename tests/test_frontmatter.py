from scripts.frontmatter import parse_frontmatter


def test_parses_mapping_between_fences():
    text = "---\nname: foo\ndescription: bar baz\n---\n# Body\n"
    fm = parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["description"] == "bar baz"


def test_returns_empty_dict_when_no_frontmatter():
    assert parse_frontmatter("# Just a heading\n") == {}


def test_returns_empty_dict_on_unterminated_fence():
    assert parse_frontmatter("---\nname: foo\n# no closing fence\n") == {}
