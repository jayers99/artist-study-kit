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
