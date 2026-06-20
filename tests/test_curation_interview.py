from scripts.selection import Rating
from scripts.curation_interview import StudyTarget, build_queue, StudyBrief, StudyStep, serialize_briefs, parse_briefs, pending_targets, validate_briefs


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
    assert "> [!example] [[exotics|Exotics]] (1939)" in text
    assert "[[sales-woman]]" in text
    assert "facial economy as the dial" in text
    assert "1. copy the ink study" in text
    assert "*Test:* reads warm / tense / uneasy" in text


def test_study_briefs_paths():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.study_briefs_json.name == "study-briefs.json"
    assert sp.study_briefs_md.name == "study-briefs.md"


def _target(work_id):
    return StudyTarget(work_id=work_id, title=work_id, year="1930", medium="",
                       cluster="c", source_url="u", members=(work_id,))


def _full_brief(work_id):
    return StudyBrief(work_id=work_id, title=work_id, year="1930", members=(work_id,),
                      cluster="c", source_url="u", thesis="t", anchor_trait="a",
                      study_plan=(StudyStep("do it"),))


def test_pending_targets_excludes_briefed_works():
    queue = [_target("a"), _target("b")]
    assert [t.work_id for t in pending_targets(queue, [_full_brief("a")])] == ["b"]


def test_validate_passes_when_every_target_has_a_full_brief():
    queue = [_target("a")]
    assert validate_briefs(queue, [_full_brief("a")]) == []


def test_validate_flags_missing_brief():
    queue = [_target("a")]
    assert any("no study brief" in e for e in validate_briefs(queue, []))


def test_validate_flags_empty_thesis_anchor_or_plan():
    queue = [_target("a")]
    bad = StudyBrief(work_id="a", title="a", year="1930", members=("a",), cluster="c",
                     source_url="u", thesis="  ", anchor_trait="", study_plan=())
    errs = validate_briefs(queue, [bad])
    assert any("thesis" in e for e in errs)
    assert any("anchor_trait" in e for e in errs)
    assert any("study_plan" in e for e in errs)
