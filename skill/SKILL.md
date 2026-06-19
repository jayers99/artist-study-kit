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
