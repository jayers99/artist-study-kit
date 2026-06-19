# artist-study-kit Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the skill's foundation — study-package layout, a resumable/idempotent pipeline state model, and the `SKILL.md` orchestration skeleton — so the per-stage tooling (Plans 2–3) has a spine to plug into.

**Architecture:** A single orchestrator skill (`skill/SKILL.md`) drives Claude through eight stages across three runs separated by two human-in-the-loop pauses. Deterministic, importable Python helpers live in `skill/scripts/` (a package): `paths.py` computes the per-artist output tree, `state.py` tracks pipeline progress in `state.json`, `frontmatter.py` parses YAML frontmatter (reused by SKILL.md validation and later output emitters). This plan builds only that spine; network/judgment work is deferred to later plans.

**Tech Stack:** Python ≥3.12, uv, pytest (+ pytest-bdd available for later acceptance specs), PyYAML, Firecrawl (declared, used in Plan 2).

## Global Constraints

- Python `requires-python = ">=3.12"`; managed with **uv** (`uv run` / `uv add`).
- **Venv lives OUTSIDE iCloud** at `~/.venvs/artist-study-kit`; repo `.venv` is a symlink to it. Recreate with `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync` then `ln -s "$HOME/.venvs/artist-study-kit" .venv`.
- Skill packaging: `skill/` = `SKILL.md` + `scripts/` (importable package). Tests in repo-root `tests/`.
- Output contract: per-artist package rooted at `studies/<artist-slug>/` (exact tree in Task 2).
- Pipeline order (stage ids, verbatim): `background`, `source_grading`, `style_definition`, `works_inventory`, `image_discovery`, `preference_synthesis`, `visual_analysis`, `study_retention`.
- Human pauses gate two stages: `preference_synthesis` requires `selection.json`; `visual_analysis` requires a chosen study set.
- Markdown outputs are Obsidian-native (frontmatter + `[[wikilinks]]`); applies to emitters in later plans.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit.
- Use logical `~/iCloud/...` paths in shell; quote paths.

---

### Task 1: Project & test harness setup

**Files:**
- Modify: `pyproject.toml`
- Create: `skill/scripts/__init__.py`
- Create: `tests/__init__.py`
- Test: `tests/test_smoke.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: an importable `scripts` package (via `pythonpath = ["skill"]`) and a working `uv run pytest` command that all later tasks rely on.

- [ ] **Step 1: Ensure the out-of-iCloud venv exists**

```bash
cd "$HOME/iCloud/para/1-projects/artist-study-kit"
UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync
[ -L .venv ] || ln -s "$HOME/.venvs/artist-study-kit" .venv
```
Expected: sync completes; `.venv` is a symlink (no thousands of files inside iCloud).

- [ ] **Step 2: Add dev + runtime dependencies**

```bash
cd "$HOME/iCloud/para/1-projects/artist-study-kit"
uv add pyyaml
uv add --dev pytest pytest-bdd
```
Expected: `pyproject.toml` gains `pyyaml` under dependencies and a `[dependency-groups]`/dev section with `pytest`, `pytest-bdd`.

- [ ] **Step 3: Configure pytest in `pyproject.toml`**

Append this block to `pyproject.toml`:

```toml
[tool.pytest.ini_options]
pythonpath = ["skill"]
testpaths = ["tests"]
```

- [ ] **Step 4: Create the package + test init files**

Create `skill/scripts/__init__.py`:
```python
"""artist-study-kit skill helpers (deterministic tooling)."""
```

Create `tests/__init__.py`:
```python
```

- [ ] **Step 5: Write the failing smoke test**

Create `tests/test_smoke.py`:
```python
def test_scripts_package_importable():
    import scripts  # noqa: F401

    assert scripts.__doc__ is not None
```

- [ ] **Step 6: Run the smoke test**

Run: `cd "$HOME/iCloud/para/1-projects/artist-study-kit" && uv run pytest tests/test_smoke.py -v`
Expected: PASS (1 passed). If it errors on import, recheck `pythonpath = ["skill"]` and that `skill/scripts/__init__.py` exists.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock skill/scripts/__init__.py tests/__init__.py tests/test_smoke.py
git commit -m "chore: skill package + pytest harness"
```

---

### Task 2: Study-package paths & scaffolding

**Files:**
- Create: `skill/scripts/paths.py`
- Test: `tests/test_paths.py`

**Interfaces:**
- Consumes: `scripts` package from Task 1.
- Produces:
  - `slugify(name: str) -> str`
  - `StudyPaths` (frozen dataclass) with `.root: Path` and properties: `report_md`, `sources_dir`, `sources_json`, `source_grades_md`, `works_md`, `images_dir`, `candidates_dir`, `selected_dir`, `gallery_html`, `selection_json`, `preference_synthesis_md`, `analysis_md`, `study_notes_md`, `drills_dir`, `review_schedule_md`, `prompts_dir`, `state_json` — all `Path`.
  - `study_paths(base: Path | str, artist: str) -> StudyPaths`
  - `scaffold(base: Path | str, artist: str) -> StudyPaths` (creates the dir tree, idempotent)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_paths.py`:
```python
from pathlib import Path

import pytest

from scripts.paths import StudyPaths, scaffold, slugify, study_paths


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Vincent van Gogh", "vincent-van-gogh"),
        ("Henri de Toulouse-Lautrec", "henri-de-toulouse-lautrec"),
        ("  J.M.W. Turner  ", "jmw-turner"),
        ("Élisabeth Vigée Le Brun", "lisabeth-vige-le-brun"),
    ],
)
def test_slugify(name, expected):
    assert slugify(name) == expected


def test_study_paths_root_uses_slug():
    sp = study_paths("studies", "Vincent van Gogh")
    assert sp.root == Path("studies/vincent-van-gogh")


def test_path_properties_match_output_contract():
    sp = study_paths("studies", "x")
    r = sp.root
    assert sp.report_md == r / "report.md"
    assert sp.sources_json == r / "sources" / "sources.json"
    assert sp.source_grades_md == r / "sources" / "source-grades.md"
    assert sp.works_md == r / "works.md"
    assert sp.candidates_dir == r / "images" / "candidates"
    assert sp.selected_dir == r / "images" / "selected"
    assert sp.gallery_html == r / "gallery.html"
    assert sp.selection_json == r / "selection.json"
    assert sp.preference_synthesis_md == r / "preference-synthesis.md"
    assert sp.analysis_md == r / "analysis.md"
    assert sp.study_notes_md == r / "study-notes.md"
    assert sp.drills_dir == r / "drills"
    assert sp.review_schedule_md == r / "review-schedule.md"
    assert sp.prompts_dir == r / "prompts"
    assert sp.state_json == r / "state.json"


def test_scaffold_creates_tree_and_is_idempotent(tmp_path):
    sp = scaffold(tmp_path, "Vincent van Gogh")
    for d in [sp.root, sp.sources_dir, sp.candidates_dir, sp.selected_dir, sp.drills_dir, sp.prompts_dir]:
        assert d.is_dir()
    # Running again must not raise.
    sp2 = scaffold(tmp_path, "Vincent van Gogh")
    assert sp2.root == sp.root


def test_studypaths_is_frozen():
    sp = study_paths("studies", "x")
    with pytest.raises(Exception):
        sp.root = Path("other")  # type: ignore[misc]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_paths.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.paths'`.

- [ ] **Step 3: Implement `paths.py`**

Create `skill/scripts/paths.py`:
```python
"""Per-artist study-package paths and scaffolding (the output contract)."""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


def slugify(name: str) -> str:
    """Filesystem- and Obsidian-safe kebab-case slug for an artist name."""
    s = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode("ascii")
    s = s.strip().lower()
    s = re.sub(r"[^\w\s-]", "", s)
    s = re.sub(r"[\s_]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


@dataclass(frozen=True)
class StudyPaths:
    """Resolved paths for a single artist's study package."""

    root: Path

    @property
    def report_md(self) -> Path:
        return self.root / "report.md"

    @property
    def sources_dir(self) -> Path:
        return self.root / "sources"

    @property
    def sources_json(self) -> Path:
        return self.sources_dir / "sources.json"

    @property
    def source_grades_md(self) -> Path:
        return self.sources_dir / "source-grades.md"

    @property
    def works_md(self) -> Path:
        return self.root / "works.md"

    @property
    def images_dir(self) -> Path:
        return self.root / "images"

    @property
    def candidates_dir(self) -> Path:
        return self.images_dir / "candidates"

    @property
    def selected_dir(self) -> Path:
        return self.images_dir / "selected"

    @property
    def gallery_html(self) -> Path:
        return self.root / "gallery.html"

    @property
    def selection_json(self) -> Path:
        return self.root / "selection.json"

    @property
    def preference_synthesis_md(self) -> Path:
        return self.root / "preference-synthesis.md"

    @property
    def analysis_md(self) -> Path:
        return self.root / "analysis.md"

    @property
    def study_notes_md(self) -> Path:
        return self.root / "study-notes.md"

    @property
    def drills_dir(self) -> Path:
        return self.root / "drills"

    @property
    def review_schedule_md(self) -> Path:
        return self.root / "review-schedule.md"

    @property
    def prompts_dir(self) -> Path:
        return self.root / "prompts"

    @property
    def state_json(self) -> Path:
        return self.root / "state.json"


_SCAFFOLD_DIRS = (
    "sources",
    "images",
    "images/candidates",
    "images/selected",
    "drills",
    "prompts",
)


def study_paths(base: Path | str, artist: str) -> StudyPaths:
    """Compute (without creating) the study-package paths for an artist."""
    return StudyPaths(root=Path(base) / slugify(artist))


def scaffold(base: Path | str, artist: str) -> StudyPaths:
    """Create the study-package directory tree; idempotent."""
    sp = study_paths(base, artist)
    sp.root.mkdir(parents=True, exist_ok=True)
    for rel in _SCAFFOLD_DIRS:
        (sp.root / rel).mkdir(parents=True, exist_ok=True)
    return sp
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (all parametrized + cases green).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/paths.py tests/test_paths.py
git commit -m "feat: study-package paths + scaffolding"
```

---

### Task 3: Resumable pipeline state model

**Files:**
- Create: `skill/scripts/state.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `StudyPaths.state_json` from Task 2.
- Produces:
  - `STAGES: tuple[str, ...]` — the ordered stage ids (verbatim from Global Constraints).
  - `PAUSE_GATES: dict[str, str]` — stage id → human-input requirement description.
  - `PipelineState` dataclass: fields `artist: str`, `completed: list[str]`; methods/props:
    - `next_stage -> str | None`
    - `is_complete(stage: str) -> bool`
    - `mark_complete(stage: str) -> None` (idempotent; raises `ValueError` on unknown stage)
    - `gate_for(stage: str) -> str | None`
    - `to_dict() -> dict` / `from_dict(d: dict) -> PipelineState` (classmethod)
    - `save(path: Path) -> None` / `load(path: Path, artist: str) -> PipelineState` (classmethod; returns a fresh state if the file is absent)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_state.py`:
```python
import pytest

from scripts.state import PAUSE_GATES, STAGES, PipelineState


def test_stage_order_is_the_contract():
    assert STAGES == (
        "background",
        "source_grading",
        "style_definition",
        "works_inventory",
        "image_discovery",
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_state.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.state'`.

- [ ] **Step 3: Implement `state.py`**

Create `skill/scripts/state.py`:
```python
"""Resumable, idempotent pipeline state for the artist-study-kit skill."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

STAGES: tuple[str, ...] = (
    "background",
    "source_grading",
    "style_definition",
    "works_inventory",
    "image_discovery",
    "preference_synthesis",
    "visual_analysis",
    "study_retention",
)

# Stages that cannot start until the human supplies an artifact.
PAUSE_GATES: dict[str, str] = {
    "preference_synthesis": "curation complete: selection.json present",
    "visual_analysis": "study set chosen from the ranked funnel",
}


@dataclass
class PipelineState:
    artist: str
    completed: list[str] = field(default_factory=list)

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
        return {"artist": self.artist, "completed": list(self.completed)}

    @classmethod
    def from_dict(cls, d: dict) -> "PipelineState":
        return cls(artist=d["artist"], completed=list(d.get("completed", [])))

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, artist: str) -> "PipelineState":
        if not path.exists():
            return cls(artist=artist, completed=[])
        return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_state.py -v`
Expected: PASS (all cases green).

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/state.py tests/test_state.py
git commit -m "feat: resumable pipeline state model"
```

---

### Task 4: Frontmatter parser + SKILL.md skeleton

**Files:**
- Create: `skill/scripts/frontmatter.py`
- Create: `skill/SKILL.md`
- Test: `tests/test_frontmatter.py`
- Test: `tests/test_skill_md.py`

**Interfaces:**
- Consumes: nothing new (pure helper) + `STAGES` from Task 3 for the validation test.
- Produces:
  - `parse_frontmatter(text: str) -> dict` — returns the YAML mapping between leading `---` fences; `{}` when absent. (Reused by later plans to validate emitted Obsidian outputs.)
  - `skill/SKILL.md` with valid skill frontmatter (`name`, `description`) and an orchestration body covering the three runs, two human pauses, and resume logic.

- [ ] **Step 1: Write the failing frontmatter tests**

Create `tests/test_frontmatter.py`:
```python
from scripts.frontmatter import parse_frontmatter


def test_parses_mapping_between_fences():
    text = "---\nname: foo\ndescription: bar baz\n---\n# Body\n"
    fm = parse_frontmatter(text)
    assert fm["name"] == "foo"
    assert fm["description"] == "bar baz"


def test_returns_empty_dict_when_no_frontmatter():
    assert parse_frontmatter("# Just a heading\n") == {}


def test_returns_empty_dict_on_unterminated_fence():
    assert parse_frontmatter("---\nname: foo\n# no closing fence\n") == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.frontmatter'`.

- [ ] **Step 3: Implement `frontmatter.py`**

Create `skill/scripts/frontmatter.py`:
```python
"""Parse YAML frontmatter from markdown (skill + Obsidian outputs)."""

from __future__ import annotations

import yaml


def parse_frontmatter(text: str) -> dict:
    """Return the YAML mapping between leading `---` fences, or `{}`."""
    if not text.startswith("---\n"):
        return {}
    rest = text[4:]
    end = rest.find("\n---")
    if end == -1:
        return {}
    block = rest[:end]
    data = yaml.safe_load(block)
    return data if isinstance(data, dict) else {}
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_frontmatter.py -v`
Expected: PASS.

- [ ] **Step 5: Write the failing SKILL.md validation test**

Create `tests/test_skill_md.py`:
```python
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
```

- [ ] **Step 6: Run test to verify it fails**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: FAIL (`test_skill_md_exists` fails — file absent).

- [ ] **Step 7: Write `skill/SKILL.md`**

Create `skill/SKILL.md`:
```markdown
---
name: artist-study-kit
description: Use when a user names a historical artist they want to study, copy, or do a master study of — produces a structured studio-prep package (background, graded sources, visual grammar, ranked works, high-res images, human curation, deep analysis, study drills).
---

# artist-study-kit

Turn a historical artist's name into a studio-prep study package under
`studies/<artist-slug>/`. Convert art-historical research into usable studio
preparation; keep the human in control of taste-driven choices.

Design rationale and per-stage evidence live in the repo `wiki/` (entry point
`wiki/00-index.md`); each stage below cites its stage note.

## How to run

The pipeline is **resumable**. On every invocation:

1. Resolve the artist slug and ensure the package exists:
   `uv run python -c "from scripts.paths import scaffold; scaffold('studies', '<ARTIST>')"`
2. Load state and find the next stage:
   `uv run python -c "from scripts.state import PipelineState; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); print(PipelineState.load(sp.state_json,'<ARTIST>').next_stage)"`
3. If the next stage is gated by a human pause (`preference_synthesis`,
   `visual_analysis`) and its requirement is unmet, print the instructions for
   that pause and STOP. Otherwise run the next stage, then mark it complete and
   save state before continuing.

Stage ids, in order: `background`, `source_grading`, `style_definition`,
`works_inventory`, `image_discovery`, `preference_synthesis`,
`visual_analysis`, `study_retention`.

## Run A — automated research (stages 1–5)

1. **background** — see `wiki/stage-background-research.md`. Emit the background
   section of `report.md`; run the biography→style checklist so signal reaches
   style definition. (Tooling: Plan 2.)
2. **source_grading** — see `wiki/stage-source-grading.md`. Two-pass grader →
   `sources/sources.json` + `sources/source-grades.md`. (Tooling: Plan 2.)
3. **style_definition** — see `wiki/stage-style-definition.md`. Emit the visual
   grammar section + style cheat sheet into `report.md`.
4. **works_inventory** — see `wiki/stage-works-inventory.md`. Dual-axis ranked,
   clustered `works.md`.
5. **image_discovery** — see `wiki/stage-image-discovery.md`. Download high-res
   candidates to `images/candidates/<work>/` and generate `gallery.html`.
   (Tooling: Plans 2–3.) Then STOP for Human Pause 1.

> [!info] Human Pause 1 — curation
> The user opens `gallery.html`, star-rates candidates (detail view auto-advances),
> fills the curatorial-gate fields (thesis / anchor trait / handoff note) for
> works rated ≥4★, and exports `selection.json`. See `wiki/stage-curation.md`.

## Run B — synthesis + funnel (stage 6)

6. **preference_synthesis** — gated on `selection.json`. Analyze the liked set
   for patterns/connections; emit `preference-synthesis.md` with a "what you're
   drawn to" note plus a ranked study-set list (pattern-fit + studyability).
   Then STOP for Human Pause 2.

> [!info] Human Pause 2 — funnel
> The user picks the final small study set from the ranked list.

## Run C — study (stages 7–8)

7. **visual_analysis** — gated on a chosen study set. See
   `wiki/stage-visual-analysis.md`. Emit per-work `analysis.md` via the 5-stage
   formal-analysis instruction set; cross-check against the artist grammar.
8. **study_retention** — see `wiki/stage-study-retention.md`. Emit
   `study-notes.md` (faded aids), `drills/`, and `review-schedule.md`.

## Output contract

`studies/<artist-slug>/`: `report.md`, `sources/`, `works.md`, `images/`,
`gallery.html`, `selection.json`, `preference-synthesis.md`, `analysis.md`,
`study-notes.md`, `drills/`, `review-schedule.md`, `prompts/`, `state.json`.
Markdown is Obsidian-native (frontmatter + `[[wikilinks]]`).
```

- [ ] **Step 8: Run the SKILL.md tests to verify they pass**

Run: `uv run pytest tests/test_skill_md.py -v`
Expected: PASS.

- [ ] **Step 9: Run the full suite**

Run: `cd "$HOME/iCloud/para/1-projects/artist-study-kit" && uv run pytest -v`
Expected: PASS (all tests across Tasks 1–4 green).

- [ ] **Step 10: Commit**

```bash
git add skill/scripts/frontmatter.py skill/SKILL.md tests/test_frontmatter.py tests/test_skill_md.py
git commit -m "feat: frontmatter parser + SKILL.md orchestration skeleton"
```

---

## What this plan deliberately defers

- **Plan 2 (research tooling):** Firecrawl fetch wrapper; source signal-scan + rubric scoring (`sources.json`/`source-grades.md` emitters); IIIF discovery, license/resolution validation, image download (Scrapy for bulk). Tested against recorded fixtures, not live endpoints.
- **Plan 3 (curation + study):** `gallery.html` generator + `selection.json` parse/validate round-trip; preference-synthesis ranking output; analysis/study-notes/drills/schedule emitters; `prompts/` population.

Each later plan plugs into the Task 2–3 interfaces (`StudyPaths`, `PipelineState`) and follows the same TDD cadence.

## Self-Review

- **Spec coverage (foundation slice):** output contract → Task 2 ✔; resume/state model (spec §7) → Task 3 ✔; single-orchestrator architecture + SKILL.md (spec §3) → Task 4 ✔; uv/venv-outside-iCloud + TDD harness (spec §8, CLAUDE.md) → Task 1 ✔. Stage-specific tooling (spec §4) is intentionally deferred to Plans 2–3 and mapped above.
- **Placeholder scan:** no TBD/TODO; every code step shows complete code; every run step shows the command + expected result.
- **Type consistency:** `StudyPaths`/`study_paths`/`scaffold`/`slugify` names match between Task 2 definition and Task 4 SKILL.md usage; `PipelineState`/`STAGES`/`PAUSE_GATES`/`next_stage`/`mark_complete`/`load`/`save` match between Task 3 definition and the state-test + SKILL.md references; `parse_frontmatter` matches between Task 4 definition and both frontmatter + skill-md tests.
