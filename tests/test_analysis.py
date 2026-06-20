from scripts.analysis import ANALYSIS_STAGES, WorkAnalysis, write_analysis_md
from scripts.frontmatter import parse_frontmatter


def _work(work_id="wheat-field", title="Wheat Field"):
    return WorkAnalysis(
        work_id=work_id, title=title,
        structural_skeleton="low horizon, golden-section path",
        notan="3-value: bright field / mid sky / dark cypress",
        palette="cad yellow + ultramarine shadow",
        layering="impasto over thin underpainting",
        traps="don't outline the wheat",
        grammar_crosscheck="confirms warm-light/cool-shadow; surprise: flat sky",
        imitation_checklist=["block 3 values first", "mix the shadow string"],
        predict_then_reveal="Guess the light direction before reading the notan.",
    )


def test_analysis_stages_are_the_five_set():
    assert len(ANALYSIS_STAGES) == 5


def test_emitter_is_obsidian_native_with_all_stages(tmp_path):
    p = tmp_path / "analysis.md"
    write_analysis_md([_work()], "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/analysis"
    assert fm["artist"] == "Vincent van Gogh"
    for stage in ANALYSIS_STAGES:
        assert stage in text
    assert "Wheat Field" in text
    assert "[!example]" in text  # predict-then-reveal callout
    assert "block 3 values first" in text  # checklist item rendered


def test_emitter_renders_each_work_section(tmp_path):
    p = tmp_path / "analysis.md"
    write_analysis_md([_work("a", "Alpha"), _work("b", "Beta")], "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert "## Alpha" in text and "## Beta" in text
