from scripts.frontmatter import parse_frontmatter
from scripts.preference_synthesis import (
    PREFERENCE_WEIGHTS,
    StudyCandidate,
    combined_score,
    rank_candidates,
    write_preference_synthesis_md,
)


def _c(work_id, title, pf, st, rationale="fits the palette pattern"):
    return StudyCandidate(work_id=work_id, title=title, pattern_fit=pf, studyability=st, rationale=rationale)


def test_weights_sum_to_100():
    assert sum(PREFERENCE_WEIGHTS.values()) == 100


def test_combined_score_is_weighted_average():
    assert combined_score(_c("a", "A", 80, 60)) == 70


def test_rank_orders_descending():
    ranked = rank_candidates([_c("a", "A", 40, 40), _c("b", "B", 90, 90), _c("c", "C", 70, 50)])
    assert [c.work_id for c in ranked] == ["b", "c", "a"]


def test_emitter_is_obsidian_native(tmp_path):
    p = tmp_path / "preference-synthesis.md"
    cands = [_c("wheat-field", "Wheat Field", 90, 85), _c("irises", "Irises", 60, 70)]
    write_preference_synthesis_md("You gravitate to high-chroma rural scenes.", cands, "Vincent van Gogh", p)
    text = p.read_text(encoding="utf-8")
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/preference-synthesis"
    assert fm["artist"] == "Vincent van Gogh"
    assert "You gravitate to high-chroma rural scenes." in text
    assert "Wheat Field" in text
    # ranked list is ordered: Wheat Field (87) before Irises (65)
    assert text.index("Wheat Field") < text.index("Irises")


def test_emitter_respects_shortlist_cap(tmp_path):
    p = tmp_path / "preference-synthesis.md"
    cands = [_c(f"w{i}", f"Work {i}", 90 - i, 80) for i in range(12)]
    write_preference_synthesis_md("insight", cands, "Artist", p, shortlist_cap=8)
    text = p.read_text(encoding="utf-8")
    assert "Work 0" in text and "Work 7" in text
    # capped: the 9th-ranked work is noted as below the cap, not in the ranked table rows
    assert "shortlist cap" in text.lower()
