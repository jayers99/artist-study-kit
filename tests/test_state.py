import pytest

from scripts.state import PAUSE_GATES, STAGES, PipelineState


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
