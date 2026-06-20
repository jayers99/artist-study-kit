from scripts.frontmatter import parse_frontmatter
from scripts.study_retention import (
    DiscriminationCard,
    ReviewItem,
    StudyNote,
    write_discrimination_cards_md,
    write_review_schedule_md,
    write_study_notes_md,
)


def test_study_notes_is_obsidian_native_with_faded_aids(tmp_path):
    p = tmp_path / "study-notes.md"
    note = StudyNote(
        work_id="wheat-field", title="Wheat Field",
        notice_first="the value of the sky vs field",
        decisions_to_imitate=["limit to 3 values", "warm the lights"],
        traps=["don't outline"],
        exercises=["10-min value thumbnail"],
    )
    write_study_notes_md([note], "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/notes"
    assert "#artist/vincent-van-gogh" in fm.get("tags", [])
    assert "#study/notes" in fm.get("tags", [])
    assert "Wheat Field" in text
    # faded aids: cheat sheet -> checklist -> bare prompt
    assert "Cheat sheet" in text and "Checklist" in text and "Bare prompt" in text
    assert "[!warning]" in text  # traps callout
    assert "limit to 3 values" in text


def test_discrimination_cards_render_a_vs_not_a(tmp_path):
    p = tmp_path / "discrimination-cards.md"
    cards = [DiscriminationCard(trait="lost edges", is_a="edge dissolves into shadow",
                                not_a="edge stays crisp in shadow")]
    write_discrimination_cards_md(cards, "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert parse_frontmatter(text)["type"] == "study/drills"
    assert "lost edges" in text
    assert "edge dissolves into shadow" in text
    assert "edge stays crisp in shadow" in text


def test_discrimination_cards_escape_pipe_in_cell(tmp_path):
    p = tmp_path / "discrimination-cards.md"
    cards = [DiscriminationCard(trait="blending", is_a="dissolves | softly", not_a="stays crisp")]
    write_discrimination_cards_md(cards, "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert "dissolves \\| softly" in text


def test_review_schedule_is_spaced_table(tmp_path):
    p = tmp_path / "review-schedule.md"
    items = [ReviewItem(day=1, focus="Wheat Field value map", mode="reconstruct"),
             ReviewItem(day=3, focus="interleave: edges across works", mode="discriminate")]
    write_review_schedule_md(items, "Artist", p)
    text = p.read_text(encoding="utf-8")
    assert parse_frontmatter(text)["type"] == "study/review-schedule"
    assert "Day 1" in text and "Day 3" in text
    assert "reconstruct" in text
