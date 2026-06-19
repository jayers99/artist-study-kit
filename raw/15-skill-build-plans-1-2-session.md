---
title: "Skill Build — Plans 1 & 2 (Session Memory) + Plan 3 Handoff"
type: session-summary
created: 2026-06-19
tags: [phase/3, skill-build, handoff, plan/1, plan/2, plan/3]
---

# Skill Build — Plans 1 & 2 (Session Memory) + Plan 3 Handoff

Handoff for the **artist-study-kit** skill-build phase (Phase 3). Continues from
[[14-phase-2-wiki-session]]. The skill is being built from the `wiki/` synthesis via the
superpowers flow (brainstorm → spec → plan → subagent-driven execution) as a **3-plan
sequence**. This session drafted **Plan 2**, then executed Plans 1–2 to merge. **Plan 3 is
the only remaining build work.**

## Where the build stands

- **Spec (approved):** `docs/superpowers/specs/2026-06-19-artist-study-kit-skill-design.md` —
  v1 = "full pipeline, thin": 8 stages, 3 runs, 2 human pauses, resumable via `state.json`.
- **Plan 1 — Foundation — DONE, merged.** `docs/superpowers/plans/2026-06-19-artist-study-kit-foundation.md`.
  Built the spine: `skill/scripts/paths.py` (paths + `slugify` + `scaffold`), `state.py`
  (`PipelineState`, 8-stage `STAGES`, `PAUSE_GATES`), `frontmatter.py` (`parse_frontmatter`),
  `skill/SKILL.md` orchestration skeleton.
- **Plan 2 — Research tooling — DONE, merged** (`main` merge commit `9aeaca8`).
  `docs/superpowers/plans/2026-06-19-artist-study-kit-research-tooling.md`. Added:
  `firecrawl_fetch.py`, `source_signals.py`, `source_grades.py`, `iiif.py`, `image_download.py`,
  plus Plan-1 carry-forward fixes. **74 tests pass, 0 warnings.** Every network/time boundary is
  dependency-injected → tested against fixtures, never live APIs. Added `httpx`.
- **Plan 3 — Curation + study — NOT STARTED.** This is the next session's work.

## Architecture you must respect (unchanged)

A single orchestrator skill (`skill/SKILL.md`) drives Claude through stages **conversationally**;
deterministic, importable Python in `skill/scripts/` (a package) does mechanical/IO work; **Claude
does the art-historical judgment**. Scripts are pure where possible and inject every network/time
boundary so they stay fixture-testable. See spec §3.1 for the LLM↔script split.

### Stage ids (verbatim, ordered) — the resume contract
`background`, `source_grading`, `style_definition`, `works_inventory`, `image_discovery`,
`preference_synthesis`, `visual_analysis`, `study_retention`.
Pause gates (`scripts/state.py` `PAUSE_GATES`): `preference_synthesis` needs `selection.json`;
`visual_analysis` needs a chosen study set.

## Interfaces Plan 3 plugs into (already built — do not rebuild)

- `scripts.paths`: `slugify(name)`, `study_paths(base, artist) -> StudyPaths`,
  `scaffold(base, artist)`. `StudyPaths` exposes every output path: `gallery_html`,
  `selection_json`, `candidates_dir`, `selected_dir`, `preference_synthesis_md`, `analysis_md`,
  `study_notes_md`, `drills_dir`, `review_schedule_md`, `prompts_dir`, `state_json`, etc.
- `scripts.state`: `PipelineState` (`next_stage`, `is_complete`, `mark_complete`, `gate_for`,
  `save`, `load(path, artist)` — raises `ValueError` on artist mismatch), `STAGES`, `PAUSE_GATES`.
- `scripts.frontmatter`: `parse_frontmatter(text) -> dict` (use to round-trip any emitted
  Obsidian frontmatter in tests — see `source_grades.py` for the pattern).
- `scripts.iiif`: `ImageCandidate` (has `work_id`, `image_url`, `width`, `height`,
  `rights_status`, `license`, `iiif_id`, `institution`, `label`).
- `scripts.image_download`: per-image JSON metadata sidecar lives next to each image as
  `<candidates_dir>/<work_id>/<iiif-token>.json` (= `asdict(ImageCandidate)`). **The gallery
  generator (Plan 3) reads these sidecars** to render thumbnails + decision metadata.

## What Plan 3 must build (from spec §4 stages 6–8, §5, §6)

1. **`gallery.html` generator** (Python script, `skill/scripts/`): standalone static HTML+JS
   contact sheet built from the candidate metadata sidecars. Thumb grid (grouped by work, inline
   Elements-of-Art + medium/source/resolution/trust-grade) → detail view with 5★ control +
   auto-advance → **curatorial gate** revealed at ≥4★ (thesis / anchor-trait / handoff-note
   fields) → **Export `selection.json`**. ≥4★ liked set copied/linked into `images/selected/`.
   Spec §5 has the full UI contract. MVP only — defer overlay markup / compare view.
2. **`selection.json` round-trip** (parse + validation, TDD'd): the human output of Pause 1 that
   Run B ingests. Define + test the schema (per-candidate rating + gate text).
3. **Preference-synthesis ranking output** — **NOTE: this is a NEW stage** (spec §4 Stage 6),
   no dedicated wiki note; it **extends `wiki/stage-curation.md`**. Emits `preference-synthesis.md`
   = a "what you're drawn to" insight note **plus** a ranked study-set candidate list scored on
   **pattern-fit + studyability**. The scoring/serialization plumbing is script work; the pattern
   *finding* is Claude's judgment in SKILL.md.
4. **Analysis / study emitters** — `analysis.md` (5-stage formal-analysis template, study set only),
   `study-notes.md` (faded aids: cheat-sheet → checklist → bare prompt), `drills/` (discrimination
   cards / Woodpecker / gapped worksheets / FSRS deck), `review-schedule.md`, `prompts/` population.
   Keep MVP-thin (spec §9 defers full FSRS/gapped-worksheet generators).
5. **SKILL.md wiring** — thread the new scripts into the Stage-6/7/8 narrative and mark stages
   complete via `PipelineState` (Plans 1–2 left SKILL.md as a skeleton; stages aren't wired to
   tooling yet).

Source notes for the judgment work: `wiki/stage-curation.md`, `wiki/stage-visual-analysis.md`,
`wiki/stage-study-retention.md`, and their backing `raw/` reports (`13.1` curation UX, `04.1`
style-analysis, `05.1`/`06.1`/`07.1`/`08.1` pedagogy). Entry point: `wiki/00-index.md`.

## Carry-forward / tech debt to fold into Plan 3 (logged in `.git/sdd/progress.md`)

These are **Minor**, deferred from the Plan-2 final review — none blocked merge, but address when
the live path gets exercised:
- `image_download.default_fetch`: no custom **User-Agent** and no exception handling — a timeout /
  connection error propagates uncaught instead of becoming `status="error"`. Wrap when the real
  download path is first run.
- `image_download.robots_allows`: prefix-match only, **no `Allow:` directive support** and
  exact-string UA matching — can over-block (fails safe). Fine for v1; note the simplification.
- `iiif.validate_candidate`: `"unknown"` rights **pass** (only `"restricted"` fails) by design, so
  unrecognized-license images download for human curation. A test now pins this — don't regress it.
- SKILL.md Stage-2 LLM-routing: `source_signals.needs_llm_review` is `band=="borderline"` only;
  spec §4 Stage 2 also implies high-value confirmation. SKILL.md owns the final routing — decide
  when wiring Stage 2.
- Still deferred beyond Plan 3: **Scrapy bulk image download**; **per-institution identity
  resolution** (search API → IIIF manifest URL per work — Stage 5 currently assumes manifest in hand).

## Process notes (how Plans 1–2 were executed — reuse for Plan 3)

- **superpowers:writing-plans** to draft → **superpowers:subagent-driven-development** to execute:
  fresh implementer subagent per task, task review (spec ✅ + quality) after each, broad opus
  whole-branch review at the end, then **superpowers:finishing-a-development-branch**.
- Durable progress ledger at `$(git rev-parse --git-path sdd)/progress.md` — check it after any
  resume/compaction before re-dispatching anything.
- Branch convention used: `feature/skill-research-tooling` → `--no-ff` merge to `main`, branch deleted.
- **TDD always** (global stack: pytest, uv). Venv is OUTSIDE iCloud at `~/.venvs/artist-study-kit`;
  repo `.venv` is a symlink. Run `uv run pytest` from repo root. `pythonpath = ["skill"]` makes
  `scripts` importable; tests live in repo-root `tests/`, fixtures in `tests/fixtures/`.
- Specs/plans go to `docs/superpowers/`; **research + session handoffs stay in `raw/`** (this doc).

## Output contract (the target Plan 3 completes) — `studies/<artist-slug>/`
`report.md`, `sources/` (`sources.json` + `source-grades.md`), `works.md`,
`images/{candidates,selected}/`, `gallery.html`, `selection.json`, `preference-synthesis.md`,
`analysis.md`, `study-notes.md`, `drills/`, `review-schedule.md`, `prompts/`, `state.json`.
Markdown is Obsidian-native (frontmatter + `[[wikilinks]]` + tag taxonomy + study callouts).
Canonical layout: [[00-artist-study-kit-seed]] §5.
