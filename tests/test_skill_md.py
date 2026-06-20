from pathlib import Path

from scripts.frontmatter import parse_frontmatter

SKILL_MD = Path(__file__).resolve().parents[1] / "skill" / "SKILL.md"


def test_skill_md_exists():
    assert SKILL_MD.is_file()


def test_skill_md_has_required_frontmatter():
    fm = parse_frontmatter(SKILL_MD.read_text(encoding="utf-8"))
    assert fm.get("name")
    assert fm.get("description")
    # description must encode trigger guidance (skills load by description match).
    assert len(str(fm["description"])) >= 40


def test_skill_md_lists_every_pipeline_stage():
    from scripts.state import STAGES

    text = SKILL_MD.read_text(encoding="utf-8")
    for stage in STAGES:
        assert stage in text, f"stage id {stage!r} missing from SKILL.md"


def test_skill_md_references_plan3_scripts():
    text = SKILL_MD.read_text(encoding="utf-8")
    for module in ("scripts.gallery", "scripts.selection", "scripts.preference_synthesis",
                   "scripts.analysis", "scripts.study_retention"):
        assert module in text, f"SKILL.md does not wire {module}"


def test_skill_md_documents_stage_completion():
    text = SKILL_MD.read_text(encoding="utf-8")
    assert "mark_complete" in text


def test_skill_md_documents_multi_run_state():
    text = SKILL_MD.read_text(encoding="utf-8")
    for token in ("merge_candidates", "record_run", "record_session",
                  "studied_work_ids", "ingest_selection"):
        assert token in text, f"SKILL.md does not wire {token}"


def test_skill_md_explains_studied_badge_is_not_a_gate():
    text = SKILL_MD.read_text(encoding="utf-8").lower()
    assert "studied" in text
    assert "badge" in text
