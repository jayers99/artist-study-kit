from scripts._md import cell, frontmatter, study_tags


def test_study_tags_lead_with_artist_and_doctype():
    tags = study_tags("Paul Klee", "study/analysis")
    assert tags[0] == "#artist/paul-klee"
    assert "#study/analysis" in tags


def test_frontmatter_block_is_obsidian_native():
    text = "\n".join(frontmatter("study/analysis", "Paul Klee"))
    assert "type: study/analysis" in text
    assert "artist: Paul Klee" in text
    assert "  - '#artist/paul-klee'" in text
    assert "  - '#study/analysis'" in text


def test_frontmatter_appends_extra_tags():
    text = "\n".join(frontmatter("study/source-grades", "X", extra_tags=["#source-grade/a"]))
    assert "  - '#source-grade/a'" in text


def test_cell_escapes_pipe():
    assert cell("a|b") == "a\\|b"
