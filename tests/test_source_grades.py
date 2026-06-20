import json

from scripts.frontmatter import parse_frontmatter
from scripts.source_grades import (
    RUBRIC_WEIGHTS,
    GradedSource,
    RubricScores,
    grade_source,
    score_to_tier,
    weighted_score,
    write_source_grades_md,
    write_sources_json,
)
from scripts.source_signals import scan_source
from scripts.firecrawl_fetch import FetchedPage


def _scan(url="https://www.metmuseum.org/x", md="references [1] [2] provenance"):
    return scan_source(FetchedPage(url=url, final_url=url, status_code=200, markdown=md, metadata={}))


def test_rubric_weights_sum_to_100():
    assert sum(RUBRIC_WEIGHTS.values()) == 100


def test_weighted_score_perfect_is_100():
    perfect = RubricScores(authority=100, depth=100, commercial_bias=100, citations=100, usability=100)
    assert weighted_score(perfect) == 100


def test_weighted_score_is_weighted_average():
    # authority(30)=80, depth(25)=60, commercial_bias(20)=100, citations(15)=40, usability(10)=20
    r = RubricScores(authority=80, depth=60, commercial_bias=100, citations=40, usability=20)
    # 0.30*80 + 0.25*60 + 0.20*100 + 0.15*40 + 0.10*20 = 24+15+20+6+2 = 67
    assert weighted_score(r) == 67


def test_score_to_tier_cutoffs():
    assert score_to_tier(90) == "A"
    assert score_to_tier(85) == "A"
    assert score_to_tier(84) == "B"
    assert score_to_tier(70) == "B"
    assert score_to_tier(55) == "C"
    assert score_to_tier(40) == "D"
    assert score_to_tier(25) == "E"
    assert score_to_tier(24) == "F"
    assert score_to_tier(1) == "F"


def test_grade_source_assembles_score_and_tier():
    r = RubricScores(authority=90, depth=90, commercial_bias=90, citations=90, usability=90)
    gs = grade_source("https://www.metmuseum.org/x", "Met page", _scan(), r, use_for="facts", avoid_for="opinion")
    assert isinstance(gs, GradedSource)
    assert gs.score == 90
    assert gs.tier == "A"
    assert gs.use_for == "facts"


def test_write_sources_json_roundtrips(tmp_path):
    r = RubricScores(authority=80, depth=70, commercial_bias=60, citations=50, usability=40)
    gs = grade_source("https://x.org/a", "A", _scan(), r)
    p = tmp_path / "sources.json"
    write_sources_json([gs], p)
    data = json.loads(p.read_text())
    assert data[0]["url"] == "https://x.org/a"
    assert data[0]["tier"] == gs.tier
    assert data[0]["signals"]["band"] in {"high", "borderline", "low"}
    assert data[0]["rubric"]["authority"] == 80


def test_write_sources_json_handles_ungraded(tmp_path):
    gs = grade_source("https://x.org/skip", "Skip", _scan(), None)
    p = tmp_path / "sources.json"
    write_sources_json([gs], p)
    data = json.loads(p.read_text())
    assert data[0]["rubric"] is None
    assert data[0]["score"] == 0
    assert data[0]["tier"] == "F"


def test_write_source_grades_md_is_obsidian_native(tmp_path):
    r = RubricScores(authority=90, depth=90, commercial_bias=90, citations=90, usability=90)
    gs = grade_source("https://www.metmuseum.org/x", "Met page", _scan(), r, use_for="facts", avoid_for="aesthetic claims")
    p = tmp_path / "source-grades.md"
    write_source_grades_md([gs], "Vincent van Gogh", p)
    text = p.read_text()
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/source-grades"
    assert "#source-grade/a" in fm.get("tags", [])
    assert "#artist/vincent-van-gogh" in fm.get("tags", [])
    assert "Met page" in text
    assert "facts" in text
    assert "aesthetic claims" in text
