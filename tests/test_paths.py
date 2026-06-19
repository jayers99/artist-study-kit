from pathlib import Path

import pytest

from scripts.paths import StudyPaths, scaffold, slugify, study_paths


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Vincent van Gogh", "vincent-van-gogh"),
        ("Henri de Toulouse-Lautrec", "henri-de-toulouse-lautrec"),
        ("  J.M.W. Turner  ", "jmw-turner"),
        ("Élisabeth Vigée Le Brun", "elisabeth-vigee-le-brun"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_study_paths_root_uses_slug():
    sp = study_paths("studies", "Vincent van Gogh")
    assert sp.root == Path("studies/vincent-van-gogh")


def test_path_properties_match_output_contract():
    sp = study_paths("studies", "x")
    r = sp.root
    assert sp.report_md == r / "report.md"
    assert sp.sources_json == r / "sources" / "sources.json"
    assert sp.source_grades_md == r / "sources" / "source-grades.md"
    assert sp.works_md == r / "works.md"
    assert sp.candidates_dir == r / "images" / "candidates"
    assert sp.selected_dir == r / "images" / "selected"
    assert sp.gallery_html == r / "gallery.html"
    assert sp.selection_json == r / "selection.json"
    assert sp.preference_synthesis_md == r / "preference-synthesis.md"
    assert sp.analysis_md == r / "analysis.md"
    assert sp.study_notes_md == r / "study-notes.md"
    assert sp.drills_dir == r / "drills"
    assert sp.review_schedule_md == r / "review-schedule.md"
    assert sp.prompts_dir == r / "prompts"
    assert sp.state_json == r / "state.json"


def test_scaffold_creates_tree_and_is_idempotent(tmp_path):
    sp = scaffold(tmp_path, "Vincent van Gogh")
    for d in [sp.root, sp.sources_dir, sp.candidates_dir, sp.selected_dir, sp.drills_dir, sp.prompts_dir]:
        assert d.is_dir()
    # Running again must not raise.
    sp2 = scaffold(tmp_path, "Vincent van Gogh")
    assert sp2.root == sp.root


def test_studypaths_is_frozen():
    sp = study_paths("studies", "x")
    with pytest.raises(Exception):
        sp.root = Path("other")  # type: ignore[misc]
