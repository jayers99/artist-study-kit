from scripts.selection import Rating
from scripts.curation_interview import StudyTarget, build_queue


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
