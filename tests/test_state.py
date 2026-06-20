import pytest

from scripts.state import PAUSE_GATES, STAGES, PipelineState, PackageState, BoardCandidate, DiscoveryRun, StudySession, GROUPINGS, migrate_legacy


def _thumb(**over):
    from scripts.museum_search import ThumbnailCandidate
    base = dict(work_id="exotics", title="Exotics", museum="aic",
                thumbnail_url="https://x/t.jpg", source_url="https://x/134057",
                date="1939", rights="in_copyright", medium="oil",
                qid="Q1", inst_ids=(("aic", "134057"),))
    base.update(over)
    return ThumbnailCandidate(**base)


def test_stage_order_is_the_contract():
    assert STAGES == (
        "background",
        "source_grading",
        "style_definition",
        "works_inventory",
        "image_discovery",
        "curation_interview",
        "preference_synthesis",
        "visual_analysis",
        "study_retention",
    )


def test_next_stage_fresh_is_first():
    st = PipelineState(artist="x", completed=[])
    assert st.next_stage == "background"


def test_next_stage_follows_order_regardless_of_completion_order():
    st = PipelineState(artist="x", completed=["source_grading", "background"])
    assert st.next_stage == "style_definition"


def test_next_stage_none_when_all_done():
    st = PipelineState(artist="x", completed=list(STAGES))
    assert st.next_stage is None


def test_mark_complete_is_idempotent():
    st = PipelineState(artist="x", completed=[])
    st.mark_complete("background")
    st.mark_complete("background")
    assert st.completed.count("background") == 1


def test_mark_complete_rejects_unknown_stage():
    st = PipelineState(artist="x", completed=[])
    with pytest.raises(ValueError):
        st.mark_complete("not_a_stage")


def test_gate_for_returns_requirement_for_paused_stages():
    st = PipelineState(artist="x", completed=[])
    assert st.gate_for("preference_synthesis") == PAUSE_GATES["preference_synthesis"]
    assert st.gate_for("visual_analysis") == PAUSE_GATES["visual_analysis"]
    assert st.gate_for("background") is None


def test_save_and_load_roundtrip(tmp_path):
    st = PipelineState(artist="Vincent van Gogh", completed=["background"])
    p = tmp_path / "state.json"
    st.save(p)
    loaded = PipelineState.load(p, artist="Vincent van Gogh")
    assert loaded.artist == "Vincent van Gogh"
    assert loaded.completed == ["background"]


def test_load_missing_file_returns_fresh_state(tmp_path):
    loaded = PipelineState.load(tmp_path / "absent.json", artist="x")
    assert loaded.completed == []
    assert loaded.next_stage == "background"


def test_is_complete_tracks_marked_stages():
    st = PipelineState(artist="x", completed=[])
    assert st.is_complete("background") is False
    st.mark_complete("background")
    assert st.is_complete("background") is True


def test_from_dict_dedupes_completed_preserving_order():
    st = PipelineState.from_dict(
        {"artist": "x", "completed": ["background", "background", "source_grading"]}
    )
    assert st.completed == ["background", "source_grading"]


def test_load_rejects_artist_mismatch(tmp_path):
    p = tmp_path / "state.json"
    PipelineState(artist="Vincent van Gogh", completed=["background"]).save(p)
    with pytest.raises(ValueError):
        PipelineState.load(p, artist="Claude Monet")


def test_load_allows_matching_artist(tmp_path):
    p = tmp_path / "state.json"
    PipelineState(artist="Vincent van Gogh", completed=[]).save(p)
    loaded = PipelineState.load(p, artist="Vincent van Gogh")
    assert loaded.artist == "Vincent van Gogh"


def test_curation_interview_sits_between_discovery_and_synthesis():
    i = STAGES.index("curation_interview")
    assert STAGES[i - 1] == "image_discovery"
    assert STAGES[i + 1] == "preference_synthesis"


def test_curation_interview_is_gated_on_selection_json():
    assert "selection.json" in PAUSE_GATES["curation_interview"]


def test_preference_synthesis_gate_now_references_study_briefs():
    assert "study-briefs.json" in PAUSE_GATES["preference_synthesis"]


def test_next_stage_reaches_curation_interview_after_discovery():
    s = PipelineState(artist="X", completed=[
        "background", "source_grading", "style_definition",
        "works_inventory", "image_discovery",
    ])
    assert s.next_stage == "curation_interview"


def test_board_candidate_from_thumbnail_carries_origin_and_run():
    bc = BoardCandidate.from_thumbnail(_thumb(), run_id="run-1")
    assert bc.work_id == "exotics"
    assert bc.thumbnail_url == "https://x/t.jpg"
    assert bc.origin == "discovered"
    assert bc.first_run == "run-1"


def test_board_candidate_roundtrip_preserves_inst_ids_as_tuples():
    bc = BoardCandidate.from_thumbnail(_thumb(), run_id="run-1")
    back = BoardCandidate.from_dict(bc.to_dict())
    assert back == bc
    assert back.inst_ids == (("aic", "134057"),)


def test_dedup_key_prefers_qid():
    bc = BoardCandidate.from_thumbnail(_thumb(qid="Q42"), run_id="run-1")
    assert bc.dedup_key() == ("qid", "Q42")


def test_dedup_key_falls_back_to_inst_ids_then_work_id():
    no_qid = BoardCandidate.from_thumbnail(_thumb(qid=""), run_id="run-1")
    assert no_qid.dedup_key() == ("inst", (("aic", "134057"),))
    bare = BoardCandidate.from_thumbnail(_thumb(qid="", inst_ids=()), run_id="run-1")
    assert bare.dedup_key() == ("wid", "exotics")


def test_discovery_run_roundtrip():
    r = DiscoveryRun(id="run-1", at="2026-06-20T14:02:00", source="wikidata+aic",
                     added=92, merged=0, total=92, degraded=True)
    assert DiscoveryRun.from_dict(r.to_dict()) == r


def test_study_session_roundtrip():
    s = StudySession(id="sess-1", at="2026-06-21T09:00:00", kind="study",
                     theme="line", grouping="technique",
                     selected=("a", "b"), study_set=("a",),
                     outputs={"analysis": "analysis.md"})
    back = StudySession.from_dict(s.to_dict())
    assert back == s
    assert back.selected == ("a", "b")


def test_package_state_defaults_to_empty_collections():
    st = PackageState(artist="x")
    assert st.runs == [] and st.candidates == [] and st.sessions == []
    assert st.next_stage == "background"


def test_pipeline_state_is_alias_of_package_state():
    from scripts.state import PipelineState
    assert PipelineState is PackageState


def test_legacy_state_dict_loads_with_empty_collections():
    st = PackageState.from_dict({"artist": "x", "completed": ["background"]})
    assert st.completed == ["background"]
    assert st.runs == [] and st.candidates == [] and st.sessions == []


def test_fat_state_roundtrip(tmp_path):
    st = PackageState(artist="Paul Klee", completed=["background"])
    st.runs.append(DiscoveryRun(id="run-1", at="t", source="aic",
                                added=1, merged=0, total=1))
    st.candidates.append(BoardCandidate(
        work_id="exotics", title="Exotics", date="1939", museum="aic",
        thumbnail_url="u", source_url="s", rights="in_copyright",
        inst_ids=(("aic", "134057"),), first_run="run-1"))
    st.sessions.append(StudySession(id="sess-1", at="t", grouping="technique",
                                    selected=("exotics",), study_set=("exotics",),
                                    outputs={"analysis": "analysis.md"}))
    p = tmp_path / "state.json"
    st.save(p)
    back = PackageState.load(p, artist="Paul Klee")
    assert back == st


def test_merge_adds_new_and_reports_counts():
    st = PackageState(artist="x")
    added, merged = st.merge_candidates([_thumb(work_id="a", qid="Q1"),
                                         _thumb(work_id="b", qid="Q2")], "run-1")
    assert (added, merged) == (2, 0)
    assert [c.work_id for c in st.candidates] == ["a", "b"]
    assert all(c.first_run == "run-1" for c in st.candidates)


def test_merge_is_idempotent_by_qid():
    st = PackageState(artist="x")
    st.merge_candidates([_thumb(work_id="a", qid="Q1")], "run-1")
    added, merged = st.merge_candidates([_thumb(work_id="a-again", qid="Q1")], "run-2")
    assert (added, merged) == (0, 1)
    assert len(st.candidates) == 1
    assert st.candidates[0].first_run == "run-1"  # original kept, not clobbered


def test_merge_distinct_qids_with_same_title_year_both_kept():
    st = PackageState(artist="x")
    added, _ = st.merge_candidates(
        [_thumb(work_id="a", qid="Q1"), _thumb(work_id="b", qid="Q2")], "run-1")
    assert added == 2


def test_merge_falls_back_to_inst_ids_when_no_qid():
    st = PackageState(artist="x")
    st.merge_candidates([_thumb(work_id="a", qid="", inst_ids=(("aic", "1"),))], "run-1")
    added, merged = st.merge_candidates(
        [_thumb(work_id="a2", qid="", inst_ids=(("aic", "1"),))], "run-2")
    assert (added, merged) == (0, 1)


def test_merge_dedups_two_same_key_items_in_one_call():
    st = PackageState(artist="x")
    added, merged = st.merge_candidates(
        [_thumb(work_id="a", qid="Q1"), _thumb(work_id="a2", qid="Q1")], "run-1")
    assert (added, merged) == (1, 1)
    assert len(st.candidates) == 1


def test_merge_empty_is_noop():
    st = PackageState(artist="x")
    assert st.merge_candidates([], "run-1") == (0, 0)


def test_record_run_assigns_monotonic_ids_and_timestamp():
    st = PackageState(artist="x")
    r1 = st.record_run("aic", added=5, merged=0, total=5, now="T1")
    r2 = st.record_run("wikidata", added=2, merged=3, total=7, degraded=True, now="T2")
    assert (r1.id, r1.at) == ("run-1", "T1")
    assert (r2.id, r2.source, r2.degraded) == ("run-2", "wikidata", True)
    assert [r.id for r in st.runs] == ["run-1", "run-2"]


def test_record_session_assigns_ids_and_validates_grouping():
    st = PackageState(artist="x")
    s1 = st.record_session("line", "technique", ["a", "b"], ["a"],
                           {"analysis": "analysis.md"}, now="T1")
    assert (s1.id, s1.grouping, s1.study_set) == ("sess-1", "technique", ("a",))
    with pytest.raises(ValueError):
        st.record_session("x", "vibes", ["a"], ["a"], {})


def test_studied_work_ids_is_union_over_sessions():
    st = PackageState(artist="x")
    st.record_session("t1", "technique", ["a", "b", "c"], ["a", "b"], {})
    st.record_session("t2", "subject", ["b", "d"], ["b", "d"], {})
    assert st.studied_work_ids() == {"a", "b", "d"}


def test_candidate_lookup_by_work_id():
    st = PackageState(artist="x")
    st.merge_candidates([_thumb(work_id="a", qid="Q1")], "run-1")
    assert st.candidate("a").qid == "Q1"
    assert st.candidate("missing") is None


def test_record_run_index_survives_legacy_run_zero():
    st = PackageState(artist="x")
    st.runs.append(DiscoveryRun(id="run-0", at="t", source="legacy-import",
                                added=0, merged=0, total=0))
    assert st.record_run("aic", added=1, merged=0, total=1, now="T").id == "run-1"


def _legacy_selection():
    return {
        "artist": "Paul Klee",
        "ratings": [
            {"work_id": "exotics", "iiif_token": "aic-8", "image_rel": "u1",
             "rating": 4, "title": "Exotics", "date": "1939", "museum": "aic",
             "source_url": "s1", "rights": "in_copyright",
             "inst_ids": [["aic", "134057"]]},
            {"work_id": "schoolhouse", "iiif_token": "aic-9", "image_rel": "u2",
             "rating": 0, "title": "Schoolhouse", "date": "1924", "museum": "aic",
             "source_url": "s2", "rights": "in_copyright", "inst_ids": [["aic", "32590"]]},
        ],
    }


def test_migrate_without_selection_keeps_empty_board():
    st = migrate_legacy({"artist": "Paul Klee", "completed": ["background"]})
    assert st.completed == ["background"]
    assert st.candidates == [] and st.runs == [] and st.sessions == []


def test_migrate_seeds_candidates_run_and_liked_session():
    st = migrate_legacy(
        {"artist": "Paul Klee", "completed": ["image_discovery"]},
        _legacy_selection(), now="T0")
    assert [c.work_id for c in st.candidates] == ["exotics", "schoolhouse"]
    assert st.candidates[0].first_run == "run-0"
    assert st.candidates[0].inst_ids == (("aic", "134057"),)
    assert st.runs[0].id == "run-0" and st.runs[0].source == "legacy-import"
    # only the liked (>=4) row seeds the legacy study session
    assert st.sessions[0].id == "sess-0"
    assert st.sessions[0].study_set == ("exotics",)
    assert st.sessions[0].outputs["study_briefs"] == "study-briefs.json"


def test_migrate_with_no_liked_rows_records_no_session():
    sel = _legacy_selection()
    sel["ratings"][0]["rating"] = 0
    st = migrate_legacy({"artist": "Paul Klee", "completed": []}, sel, now="T0")
    assert st.sessions == []
    assert len(st.candidates) == 2


def test_board_candidate_local_path_roundtrips():
    from scripts.state import BoardCandidate
    bc = BoardCandidate(
        work_id="barn", title="Farmhouse", date="1925", museum="",
        thumbnail_url="images/user/barn.jpg", source_url="", rights="unknown",
        origin="user", local_path="images/user/barn.jpg")
    d = bc.to_dict()
    assert d["local_path"] == "images/user/barn.jpg"
    assert BoardCandidate.from_dict(d).local_path == "images/user/barn.jpg"


def test_board_candidate_local_path_defaults_empty_on_legacy_dict():
    from scripts.state import BoardCandidate
    legacy = {"work_id": "exotics", "title": "Exotics", "date": "1939",
              "museum": "aic", "thumbnail_url": "u", "source_url": "s",
              "rights": "in_copyright"}
    assert BoardCandidate.from_dict(legacy).local_path == ""
