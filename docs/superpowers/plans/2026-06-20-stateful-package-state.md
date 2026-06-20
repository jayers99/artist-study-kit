# Stateful Package State Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the skill's thin `{artist, completed}` state into a durable per-artist package state that accumulates a mergeable candidate board, a discovery-run ledger, and repeatable study sessions.

**Architecture:** Extend `skill/scripts/state.py` so `state.json` is one fat document `{artist, completed, runs[], candidates[], sessions[]}`. Three leaf dataclasses (`BoardCandidate`, `DiscoveryRun`, `StudySession`) serialize into one aggregate (`PackageState`, the renamed-and-extended `PipelineState`). Discovery merges by a QID→inst_ids→work_id key; "studied" is derived from sessions, never stored as a gate. `selection.py` gains an ingest helper; `paths.py` gains a sessions directory; `SKILL.md` documents the multi-run model.

**Tech Stack:** Python 3, dataclasses, stdlib `json`/`datetime`, pytest. uv-managed (`uv run pytest`). No new dependencies.

## Global Constraints

- **One fat `state.json`** holding `{artist, completed, runs[], candidates[], sessions[]}`; code keeps `BoardCandidate`/`DiscoveryRun`/`StudySession` as separate dataclasses serialized into it.
- **Merge key:** QID primary; `inst_ids` fallback when no QID; `work_id` fallback when neither. A candidate with a QID dedups only against QIDs.
- **"Studied" is a derived badge, never a selection gate** — computed as the union of every session's `study_set`; selection is never constrained.
- **Rating/selection is per-session, not per-candidate.** The candidate persists only identity + metadata + `origin` + `first_run`. Do **not** touch the star-rating schema (`Rating`, `validate_selection`, `liked`) — the in-flight F6 build owns it.
- **`origin` field** is present on every candidate, default `"discovered"`; **no** user-image ingestion is built here (Thrust 2).
- **Per-session output pointers** — state stores `session.outputs` paths only; never assume single-file overwrite.
- **Backward compatible:** a legacy `{artist, completed}` `state.json` loads with empty `runs/candidates/sessions`. Keep `PipelineState` as an alias of `PackageState` so existing SKILL.md one-liners and tests keep working. Preserve `STAGES`, `PAUSE_GATES`, and the stage API (`next_stage`, `is_complete`, `mark_complete`, `gate_for`).
- **`grouping` ∈ `{"subject","media","technique","other"}`**; `record_session` rejects anything else.
- **Timestamps are injectable** (`now` kwarg) so tests are deterministic; default `datetime.now().isoformat(timespec="seconds")`.
- **Tests:** `pytest` config has `pythonpath=["skill"]`, `testpaths=["tests"]`; import as `from scripts.state import …`. Run with `uv run pytest`.
- **Commits:** this environment has no signing key in the agent — commit with `git commit --no-gpg-sign`.

---

### Task 1: Sessions directories in `paths.py`

**Files:**
- Modify: `skill/scripts/paths.py` (add two properties to `StudyPaths`; add `"sessions"` to `_SCAFFOLD_DIRS`)
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `StudyPaths.sessions_dir -> Path` (`root/"sessions"`); `StudyPaths.session_dir(session_id: str) -> Path` (`root/"sessions"/session_id`); `scaffold` now creates `sessions/`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_paths.py`:

```python
def test_sessions_dir_is_under_root():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.sessions_dir == sp.root / "sessions"


def test_session_dir_nests_by_id():
    from scripts.paths import study_paths
    sp = study_paths("studies", "Paul Klee")
    assert sp.session_dir("sess-1") == sp.root / "sessions" / "sess-1"


def test_scaffold_creates_sessions_dir(tmp_path):
    from scripts.paths import scaffold
    sp = scaffold(tmp_path, "Paul Klee")
    assert sp.sessions_dir.is_dir()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_paths.py::test_sessions_dir_is_under_root tests/test_paths.py::test_session_dir_nests_by_id tests/test_paths.py::test_scaffold_creates_sessions_dir -v`
Expected: FAIL with `AttributeError: 'StudyPaths' object has no attribute 'sessions_dir'`.

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/paths.py`, add to the `StudyPaths` dataclass (next to `state_json`):

```python
    @property
    def sessions_dir(self) -> Path:
        return self.root / "sessions"

    def session_dir(self, session_id: str) -> Path:
        return self.sessions_dir / session_id
```

And add `"sessions"` to the `_SCAFFOLD_DIRS` tuple:

```python
_SCAFFOLD_DIRS = (
    "sources",
    "images",
    "images/candidates",
    "images/selected",
    "drills",
    "prompts",
    "sessions",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (all paths tests green).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/paths.py tests/test_paths.py
git commit --no-gpg-sign -m "feat: per-session directories in StudyPaths"
```

---

### Task 2: Leaf dataclasses (`BoardCandidate`, `DiscoveryRun`, `StudySession`)

**Files:**
- Modify: `skill/scripts/state.py` (add three dataclasses + a `GROUPINGS` constant near the top; leave `PipelineState` untouched in this task)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: nothing new.
- Produces:
  - `BoardCandidate(work_id, title, date, museum, thumbnail_url, source_url, rights, medium="", qid="", inst_ids=(), origin="discovered", first_run="")` with `to_dict() -> dict`, `from_dict(d) -> BoardCandidate`, `from_thumbnail(cand, *, run_id) -> BoardCandidate` (duck-typed on `cand`'s attributes), and `dedup_key() -> tuple`.
  - `DiscoveryRun(id, at, source, added, merged, total, degraded=False)` with `to_dict`/`from_dict`.
  - `StudySession(id, at, kind="study", theme="", grouping="other", selected=(), study_set=(), outputs=<dict>)` with `to_dict`/`from_dict`.
  - `GROUPINGS = ("subject", "media", "technique", "other")`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
from scripts.state import BoardCandidate, DiscoveryRun, StudySession, GROUPINGS


def _thumb(**over):
    from scripts.museum_search import ThumbnailCandidate
    base = dict(work_id="exotics", title="Exotics", museum="aic",
                thumbnail_url="https://x/t.jpg", source_url="https://x/134057",
                date="1939", rights="in_copyright", medium="oil",
                qid="Q1", inst_ids=(("aic", "134057"),))
    base.update(over)
    return ThumbnailCandidate(**base)


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k "board_candidate or dedup or discovery_run or study_session" -v`
Expected: FAIL with `ImportError: cannot import name 'BoardCandidate' from 'scripts.state'`.

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/state.py`, after the imports add `from datetime import datetime`, and below `PAUSE_GATES` add:

```python
GROUPINGS: tuple[str, ...] = ("subject", "media", "technique", "other")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")


def _tuple_inst_ids(raw) -> tuple[tuple[str, str], ...]:
    return tuple((str(a), str(b)) for a, b in raw)


@dataclass
class BoardCandidate:
    work_id: str
    title: str
    date: str
    museum: str
    thumbnail_url: str
    source_url: str
    rights: str
    medium: str = ""
    qid: str = ""
    inst_ids: tuple[tuple[str, str], ...] = ()
    origin: str = "discovered"
    first_run: str = ""

    def dedup_key(self) -> tuple:
        if self.qid:
            return ("qid", self.qid)
        if self.inst_ids:
            return ("inst", tuple(sorted(self.inst_ids)))
        return ("wid", self.work_id)

    def to_dict(self) -> dict:
        return {
            "work_id": self.work_id, "title": self.title, "date": self.date,
            "museum": self.museum, "thumbnail_url": self.thumbnail_url,
            "source_url": self.source_url, "rights": self.rights,
            "medium": self.medium, "qid": self.qid,
            "inst_ids": [list(p) for p in self.inst_ids],
            "origin": self.origin, "first_run": self.first_run,
        }

    @classmethod
    def from_dict(cls, d: dict) -> "BoardCandidate":
        return cls(
            work_id=d["work_id"], title=d.get("title", ""), date=d.get("date", ""),
            museum=d.get("museum", ""), thumbnail_url=d.get("thumbnail_url", ""),
            source_url=d.get("source_url", ""), rights=d.get("rights", ""),
            medium=d.get("medium", ""), qid=d.get("qid", ""),
            inst_ids=_tuple_inst_ids(d.get("inst_ids", ())),
            origin=d.get("origin", "discovered"), first_run=d.get("first_run", ""),
        )

    @classmethod
    def from_thumbnail(cls, cand, *, run_id: str) -> "BoardCandidate":
        return cls(
            work_id=cand.work_id, title=cand.title, date=cand.date,
            museum=cand.museum, thumbnail_url=cand.thumbnail_url,
            source_url=cand.source_url, rights=cand.rights,
            medium=getattr(cand, "medium", ""), qid=getattr(cand, "qid", ""),
            inst_ids=_tuple_inst_ids(getattr(cand, "inst_ids", ())),
            origin="discovered", first_run=run_id,
        )


@dataclass
class DiscoveryRun:
    id: str
    at: str
    source: str
    added: int
    merged: int
    total: int
    degraded: bool = False

    def to_dict(self) -> dict:
        return {"id": self.id, "at": self.at, "source": self.source,
                "added": self.added, "merged": self.merged, "total": self.total,
                "degraded": self.degraded}

    @classmethod
    def from_dict(cls, d: dict) -> "DiscoveryRun":
        return cls(id=d["id"], at=d["at"], source=d.get("source", ""),
                   added=int(d.get("added", 0)), merged=int(d.get("merged", 0)),
                   total=int(d.get("total", 0)), degraded=bool(d.get("degraded", False)))


@dataclass
class StudySession:
    id: str
    at: str
    kind: str = "study"
    theme: str = ""
    grouping: str = "other"
    selected: tuple[str, ...] = ()
    study_set: tuple[str, ...] = ()
    outputs: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"id": self.id, "at": self.at, "kind": self.kind, "theme": self.theme,
                "grouping": self.grouping, "selected": list(self.selected),
                "study_set": list(self.study_set), "outputs": dict(self.outputs)}

    @classmethod
    def from_dict(cls, d: dict) -> "StudySession":
        return cls(id=d["id"], at=d["at"], kind=d.get("kind", "study"),
                   theme=d.get("theme", ""), grouping=d.get("grouping", "other"),
                   selected=tuple(d.get("selected", ())),
                   study_set=tuple(d.get("study_set", ())),
                   outputs=dict(d.get("outputs", {})))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -k "board_candidate or dedup or discovery_run or study_session" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: BoardCandidate/DiscoveryRun/StudySession dataclasses"
```

---

### Task 3: `PackageState` aggregate (rename + extend `PipelineState`, back-compat)

**Files:**
- Modify: `skill/scripts/state.py` (rename `PipelineState` → `PackageState`, add the three list fields, extend `to_dict`/`from_dict`, keep a `PipelineState` alias)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `BoardCandidate`, `DiscoveryRun`, `StudySession` (Task 2).
- Produces: `PackageState(artist, completed=[], runs=[], candidates=[], sessions=[])` preserving `next_stage`, `is_complete`, `mark_complete(stage)`, `gate_for(stage)`, `save(path)`, `load(path, artist)`; extended `to_dict`/`from_dict` carrying the three lists; module-level `PipelineState = PackageState`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
from scripts.state import PackageState


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k "package_state or alias or legacy_state or fat_state" -v`
Expected: FAIL with `ImportError: cannot import name 'PackageState'`.

- [ ] **Step 3: Write minimal implementation**

In `skill/scripts/state.py`, replace the `@dataclass class PipelineState … ` block with the renamed, extended class. Keep every existing method; add the three fields and extend serialization:

```python
@dataclass
class PackageState:
    artist: str
    completed: list[str] = field(default_factory=list)
    runs: list[DiscoveryRun] = field(default_factory=list)
    candidates: list[BoardCandidate] = field(default_factory=list)
    sessions: list[StudySession] = field(default_factory=list)

    @property
    def next_stage(self) -> str | None:
        for stage in STAGES:
            if stage not in self.completed:
                return stage
        return None

    def is_complete(self, stage: str) -> bool:
        return stage in self.completed

    def mark_complete(self, stage: str) -> None:
        if stage not in STAGES:
            raise ValueError(f"unknown stage: {stage!r}")
        if stage not in self.completed:
            self.completed.append(stage)

    def gate_for(self, stage: str) -> str | None:
        return PAUSE_GATES.get(stage)

    def to_dict(self) -> dict:
        return {
            "artist": self.artist,
            "completed": list(self.completed),
            "runs": [r.to_dict() for r in self.runs],
            "candidates": [c.to_dict() for c in self.candidates],
            "sessions": [s.to_dict() for s in self.sessions],
        }

    @classmethod
    def from_dict(cls, d: dict) -> "PackageState":
        seen: set[str] = set()
        deduped = [s for s in d.get("completed", []) if not (s in seen or seen.add(s))]
        return cls(
            artist=d["artist"],
            completed=deduped,
            runs=[DiscoveryRun.from_dict(x) for x in d.get("runs", [])],
            candidates=[BoardCandidate.from_dict(x) for x in d.get("candidates", [])],
            sessions=[StudySession.from_dict(x) for x in d.get("sessions", [])],
        )

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, artist: str) -> "PackageState":
        if not path.exists():
            return cls(artist=artist)
        state = cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if state.artist != artist:
            raise ValueError(
                f"state.json artist {state.artist!r} != requested {artist!r}"
            )
        return state


PipelineState = PackageState
```

- [ ] **Step 4: Run the whole state + skill suite to verify nothing regressed**

Run: `uv run pytest tests/test_state.py tests/test_skill_md.py -v`
Expected: PASS — the new tests plus every pre-existing `PipelineState` test (still green via the alias).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: PackageState aggregate over fat state.json (PipelineState alias)"
```

---

### Task 4: `merge_candidates` — idempotent discovery merge

**Files:**
- Modify: `skill/scripts/state.py` (add `merge_candidates` to `PackageState`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `BoardCandidate.from_thumbnail`/`dedup_key` (Task 2); `PackageState.candidates` (Task 3).
- Produces: `PackageState.merge_candidates(new: list, run_id: str) -> tuple[int, int]` returning `(added, merged)`. New entries are appended with `first_run=run_id`; existing keys are left untouched.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
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


def test_merge_empty_is_noop():
    st = PackageState(artist="x")
    assert st.merge_candidates([], "run-1") == (0, 0)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k merge -v`
Expected: FAIL with `AttributeError: 'PackageState' object has no attribute 'merge_candidates'`.

- [ ] **Step 3: Write minimal implementation**

Add to `PackageState` (in `skill/scripts/state.py`):

```python
    def merge_candidates(self, new: list, run_id: str) -> tuple[int, int]:
        seen = {c.dedup_key() for c in self.candidates}
        added = merged = 0
        for cand in new:
            bc = BoardCandidate.from_thumbnail(cand, run_id=run_id)
            key = bc.dedup_key()
            if key in seen:
                merged += 1
                continue
            seen.add(key)
            self.candidates.append(bc)
            added += 1
        return added, merged
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -k merge -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: idempotent merge_candidates by QID/inst_ids/work_id"
```

---

### Task 5: `record_run`, `record_session`, `studied_work_ids`, `candidate`

**Files:**
- Modify: `skill/scripts/state.py` (add a `_next_index` helper + four methods on `PackageState`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `DiscoveryRun`, `StudySession`, `GROUPINGS`, `_now` (Task 2); `PackageState` (Task 3).
- Produces:
  - `PackageState.record_run(source, added, merged, total, *, degraded=False, now=None) -> DiscoveryRun`
  - `PackageState.record_session(theme, grouping, selected, study_set, outputs, *, kind="study", now=None) -> StudySession` (raises `ValueError` on bad `grouping`)
  - `PackageState.studied_work_ids() -> set[str]`
  - `PackageState.candidate(work_id) -> BoardCandidate | None`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k "record_run or record_session or studied or candidate_lookup" -v`
Expected: FAIL with `AttributeError: 'PackageState' object has no attribute 'record_run'`.

- [ ] **Step 3: Write minimal implementation**

Add a module-level helper near `_now` in `skill/scripts/state.py`:

```python
def _next_index(items: list) -> int:
    nums = [int(x.id.rsplit("-", 1)[1]) for x in items
            if x.id.rsplit("-", 1)[-1].isdigit()]
    return (max(nums) + 1) if nums else 1
```

Add to `PackageState`:

```python
    def record_run(self, source: str, added: int, merged: int, total: int,
                   *, degraded: bool = False, now: str | None = None) -> DiscoveryRun:
        run = DiscoveryRun(id=f"run-{_next_index(self.runs)}", at=now or _now(),
                           source=source, added=added, merged=merged,
                           total=total, degraded=degraded)
        self.runs.append(run)
        return run

    def record_session(self, theme: str, grouping: str, selected, study_set,
                       outputs: dict, *, kind: str = "study",
                       now: str | None = None) -> StudySession:
        if grouping not in GROUPINGS:
            raise ValueError(f"grouping {grouping!r} not in {GROUPINGS}")
        sess = StudySession(id=f"sess-{_next_index(self.sessions)}", at=now or _now(),
                            kind=kind, theme=theme, grouping=grouping,
                            selected=tuple(selected), study_set=tuple(study_set),
                            outputs=dict(outputs))
        self.sessions.append(sess)
        return sess

    def studied_work_ids(self) -> set[str]:
        return {wid for s in self.sessions for wid in s.study_set}

    def candidate(self, work_id: str):
        for c in self.candidates:
            if c.work_id == work_id:
                return c
        return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -k "record_run or record_session or studied or candidate_lookup" -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: record_run/record_session/studied_work_ids/candidate"
```

---

### Task 6: `migrate_legacy` — seed state from an old `selection.json`

**Files:**
- Modify: `skill/scripts/state.py` (add module-level `migrate_legacy`)
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `PackageState`, `BoardCandidate`, `DiscoveryRun`, `StudySession` (Tasks 2–3); `scripts.selection.parse_selection` + `liked`.
- Produces: `migrate_legacy(state_dict: dict, selection_dict: dict | None = None, *, now: str | None = None) -> PackageState`. Seeds `run-0` (`source="legacy-import"`) and one `BoardCandidate` per `Rating` (`origin="discovered"`, `first_run="run-0"`); liked rows seed `sess-0` (`grouping="other"`, outputs pointing at the existing root files). No `selection_dict` → just the loaded state, empty board.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_state.py`:

```python
from scripts.state import migrate_legacy


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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_state.py -k migrate -v`
Expected: FAIL with `ImportError: cannot import name 'migrate_legacy'`.

- [ ] **Step 3: Write minimal implementation**

Add at the bottom of `skill/scripts/state.py`:

```python
def migrate_legacy(state_dict: dict, selection_dict: dict | None = None,
                   *, now: str | None = None) -> PackageState:
    from scripts.selection import liked, parse_selection

    st = PackageState.from_dict(state_dict)
    if not selection_dict:
        return st

    sel = parse_selection(selection_dict)
    stamp = now or _now()
    st.runs.append(DiscoveryRun(id="run-0", at=stamp, source="legacy-import",
                                added=len(sel.ratings), merged=0, total=len(sel.ratings)))
    for r in sel.ratings:
        st.candidates.append(BoardCandidate(
            work_id=r.work_id, title=r.title, date=r.date, museum=r.museum,
            thumbnail_url=r.image_rel, source_url=r.source_url, rights=r.rights,
            medium=r.medium, qid=r.qid, inst_ids=_tuple_inst_ids(r.inst_ids),
            origin="discovered", first_run="run-0"))
    liked_ids = [r.work_id for r in liked(sel)]
    if liked_ids:
        st.sessions.append(StudySession(
            id="sess-0", at=stamp, kind="study", theme="legacy import",
            grouping="other", selected=tuple(liked_ids), study_set=tuple(liked_ids),
            outputs={"study_briefs": "study-briefs.json", "analysis": "analysis.md"}))
    return st
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_state.py -k migrate -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit --no-gpg-sign -m "feat: migrate_legacy seeds package state from old selection.json"
```

---

### Task 7: `ingest_selection` in `selection.py`

**Files:**
- Modify: `skill/scripts/selection.py` (add `ingest_selection`; do **not** touch `Rating`/`validate_selection`/`liked`)
- Test: `tests/test_selection.py`

**Interfaces:**
- Consumes: `Selection`, `Rating`, `liked`, `LIKED_THRESHOLD` (existing).
- Produces: `ingest_selection(sel: Selection, *, liked_only: bool = True) -> tuple[list[str], list[str]]` returning `(selected_ids, study_set_ids)`. `selected_ids` = liked work_ids (or all work_ids when `liked_only=False`); `study_set_ids` defaults equal to `selected_ids` (Thrust 3 supplies a narrower set later).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_selection.py`:

```python
def test_ingest_selection_returns_liked_ids_and_defaults_study_set():
    from scripts.selection import Rating, Selection, ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", rating=5),
        Rating(work_id="b", iiif_token="", image_rel="u", rating=2),
        Rating(work_id="c", iiif_token="", image_rel="u", rating=4),
    ])
    selected, study_set = ingest_selection(sel)
    assert selected == ["a", "c"]
    assert study_set == ["a", "c"]


def test_ingest_selection_liked_only_false_keeps_all():
    from scripts.selection import Rating, Selection, ingest_selection
    sel = Selection(artist="x", ratings=[
        Rating(work_id="a", iiif_token="", image_rel="u", rating=5),
        Rating(work_id="b", iiif_token="", image_rel="u", rating=0),
    ])
    selected, study_set = ingest_selection(sel, liked_only=False)
    assert selected == ["a", "b"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_selection.py -k ingest -v`
Expected: FAIL with `ImportError: cannot import name 'ingest_selection'`.

- [ ] **Step 3: Write minimal implementation**

Add to `skill/scripts/selection.py` (after `liked`):

```python
def ingest_selection(sel: "Selection", *, liked_only: bool = True) -> tuple[list[str], list[str]]:
    """Resolve an exported selection into (selected_ids, study_set_ids) for a session.

    selected_ids are the wide cut (liked works by default); study_set defaults equal
    to it — the Thrust-3 funnel narrows study_set to <=4 later.
    """
    rows = liked(sel) if liked_only else sel.ratings
    selected_ids = [r.work_id for r in rows]
    return selected_ids, list(selected_ids)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_selection.py -v`
Expected: PASS (new tests plus all existing selection tests).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/selection.py tests/test_selection.py
git commit --no-gpg-sign -m "feat: ingest_selection resolves selection.json into session ids"
```

---

### Task 8: Wire the multi-run model into `SKILL.md`

**Files:**
- Modify: `skill/SKILL.md` (extend the "How to run" + image-discovery + Human-Pause sections)
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: `PackageState.merge_candidates`/`record_run`/`record_session`/`studied_work_ids` (Tasks 4–5); `ingest_selection` (Task 7).
- Produces: documentation only. Existing `test_skill_md.py` assertions must stay green (every `STAGES` id present; `scripts.gallery`/`scripts.selection`/`scripts.preference_synthesis`/`scripts.analysis`/`scripts.study_retention` referenced; `mark_complete` present).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_skill_md.py`:

```python
def test_skill_md_documents_multi_run_state():
    text = SKILL_MD.read_text(encoding="utf-8")
    for token in ("merge_candidates", "record_run", "record_session",
                  "studied_work_ids", "ingest_selection"):
        assert token in text, f"SKILL.md does not wire {token}"


def test_skill_md_explains_studied_badge_is_not_a_gate():
    text = SKILL_MD.read_text(encoding="utf-8").lower()
    assert "studied" in text
    assert "badge" in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: FAIL on `test_skill_md_documents_multi_run_state` (tokens absent).

- [ ] **Step 3: Write minimal implementation**

In `skill/SKILL.md`, replace the intro of the **How to run** section (the line "The pipeline is **resumable**. On every invocation:") with a multi-run framing, then add the wiring. Insert this block immediately after that sentence:

```markdown
The skill is no longer a single linear `run` — it is a set of **re-enterable
operations** (discover · select · study) over a persisted package
(`state.json`). `state.json` is one document: `{artist, completed, runs[],
candidates[], sessions[]}`. Discovery can run many times (new candidates
**merge** into `candidates[]` by QID/inst_ids — never duplicated); study can
run many times (each a `session` recording its `selected` wide cut, `study_set`,
and per-session `outputs`). A work already studied shows a **studied ✓ badge**
in the gallery (`PackageState.studied_work_ids()`) but is **never** filtered out
— a work may be studied again along a different dimension.
```

Then, in **Phase A — board build**, replace "Render the merged board … and mark the stage complete." with:

```markdown
Render the merged board with `scripts.gallery.build_thumbnail_gallery` and write it to `gallery.html`. Persist the board into state: `added, merged = state.merge_candidates(board, run_id)` then `state.record_run("wikidata+aic", added, merged, total=len(state.candidates), degraded=<True if Wikidata was unavailable>)` and `state.save(sp.state_json)` (re-running discovery later merges into the existing board; mark `degraded=True` on a Wikidata outage so a later run can upgrade). Save the gallery prompt under `prompts/` and mark the stage complete. STOP for Human Pause 1.
```

Update **Human Pause 1** to record the session on ingest — replace its body with:

```markdown
> The user opens `gallery.html` (a board of many thumbnails; works studied in a
> prior session carry a **studied ✓ badge** but stay selectable), rates/selects
> works, and exports `selection.json`. On return, the skill resolves it with
> `selected, study_set = ingest_selection(load_selection(sp.selection_json, '<ARTIST>'))`,
> asks the human for the session's grouping dimension (`subject` / `media` /
> `technique` / `other`) and a short theme label, then
> `state.record_session(theme, grouping, selected, study_set, outputs={...})` and
> saves state. Rating is purely visual — rationale is drawn out next in the
> `curation_interview` stage. See [[stage-curation]].
```

(Leave every stage id and the existing `scripts.*` references in place so the other `test_skill_md` assertions stay green.)

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: PASS (new tokens present; all prior assertions still hold).

- [ ] **Step 5: Run the full suite**

Run: `uv run pytest`
Expected: PASS — every test green.

- [ ] **Step 6: Commit**

```bash
git add skill/SKILL.md tests/test_skill_md.py
git commit --no-gpg-sign -m "docs: wire multi-run package state into SKILL.md"
```

---

## Notes for the executor

- **Do not** modify the star-rating schema (`Rating`, `validate_selection`, `liked`) — Thrust 3 (a separate spec) drops stars for binary select; pre-breaking it here would collide with the in-flight F6 build.
- **Do not** build user-image ingestion — only the `origin` field exists as a seam for Thrust 2.
- Existing `studies/paul-klee` / `studies/joan-miro` packages keep working via back-compat load; running `migrate_legacy` on them is optional and out of scope for this plan (no task migrates on-disk packages — the function is provided and unit-tested for when Thrust 3 needs it).
- After Task 3, the full suite should stay green at every task boundary; if a pre-existing `PipelineState` test breaks, the alias is missing.
