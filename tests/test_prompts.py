from scripts.prompts import save_prompt


def test_save_prompt_writes_named_file_with_frontmatter(tmp_path):
    p = save_prompt(
        tmp_path, "image-search", "Find public-domain high-res images of Senecio.",
        artist="Paul Klee", stage="image_discovery",
    )
    assert p.name == "image-search.md"
    txt = p.read_text(encoding="utf-8")
    assert "type: study/prompt" in txt
    assert "artist: Paul Klee" in txt
    assert "stage: image_discovery" in txt
    assert "Find public-domain high-res images of Senecio." in txt


def test_save_prompt_creates_dir_and_is_idempotent(tmp_path):
    d = tmp_path / "prompts"
    save_prompt(d, "analysis", "first", artist="X", stage="visual_analysis")
    p = save_prompt(d, "analysis", "second", artist="X", stage="visual_analysis")
    assert p.read_text(encoding="utf-8").count("second") == 1
    assert "first" not in p.read_text(encoding="utf-8")
