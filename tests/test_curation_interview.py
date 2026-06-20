from scripts.selection import Rating
from scripts.curation_interview import StudyTarget, build_queue, StudyBrief, StudyStep, serialize_briefs, parse_briefs


def _r(work_id, date="1930", title=None):
    return Rating(work_id=work_id, iiif_token="t", image_rel="r", rating=5,
                  title=title or work_id, date=date, source_url=f"http://x/{work_id}")


def test_queue_orders_by_cluster_then_studyability_desc():
    liked = [_r("a"), _r("b"), _r("c")]
    meta = {
        "a": {"cluster": "grid", "studyability": 3},
        "b": {"cluster": "grid", "studyability": 5},
        "c": {"cluster": "line", "studyability": 4},
    }
    ids = [t.work_id for t in build_queue(liked, meta)]
    assert ids == ["b", "a", "c"]  # grid (5 then 3), then line


def test_study_for_pair_is_merged_into_one_target():
    liked = [_r("exotics"), _r("sales-woman")]
    meta = {
        "exotics": {"cluster": "late", "studyability": 4},
        "sales-woman": {"cluster": "late", "studyability": 4, "study_for": "exotics"},
    }
    queue = build_queue(liked, meta)
    assert [t.work_id for t in queue] == ["exotics"]
    assert queue[0].members == ("exotics", "sales-woman")


def test_work_without_meta_sorts_last_without_crashing():
    liked = [_r("known"), _r("orphan")]
    meta = {"known": {"cluster": "grid", "studyability": 2}}
    queue = build_queue(liked, meta)
    assert [t.work_id for t in queue] == ["known", "orphan"]
    assert queue[-1].cluster == ""


def test_target_carries_display_facts():
    liked = [_r("senecio", date="1922", title="Senecio")]
    queue = build_queue(liked, {"senecio": {"cluster": "grid", "studyability": 5}})
    t = queue[0]
    assert (t.title, t.year, t.cluster, t.source_url) == ("Senecio", "1922", "grid", "http://x/senecio")


def _brief():
    return StudyBrief(
        work_id="exotics", title="Exotics", year="1939",
        members=("exotics", "sales-woman"), cluster="late",
        source_url="http://x/exotics", thesis="facial economy as the dial",
        anchor_trait="economy of facial information",
        study_plan=(
            StudyStep("copy the ink study"),
            StudyStep("variation drill", success_test="reads warm / tense / uneasy"),
        ),
    )


def test_brief_round_trips_through_json_shape():
    briefs = [_brief()]
    assert parse_briefs(serialize_briefs("Paul Klee", briefs)) == briefs


def test_empty_success_test_serializes_to_null():
    data = serialize_briefs("X", [_brief()])
    assert data["briefs"][0]["study_plan"][0]["success_test"] is None
    assert data["artist"] == "X"


def test_write_json_then_parse_recovers_briefs(tmp_path):
    from scripts.curation_interview import write_study_briefs_json
    p = tmp_path / "study-briefs.json"
    write_study_briefs_json("Paul Klee", [_brief()], p)
    import json
    assert parse_briefs(json.loads(p.read_text())) == [_brief()]


def test_write_md_renders_thesis_anchor_and_steps(tmp_path):
    from scripts.curation_interview import write_study_briefs_md
    p = tmp_path / "study-briefs.md"
    write_study_briefs_md("Paul Klee", [_brief()], p)
    text = p.read_text()
    assert "> [!example] Exotics (1939)" in text
    assert "facial economy as the dial" in text
    assert "1. copy the ink study" in text
    assert "*Test:* reads warm / tense / uneasy" in text


def test_study_briefs_paths():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.study_briefs_json.name == "study-briefs.json"
    assert sp.study_briefs_md.name == "study-briefs.md"
