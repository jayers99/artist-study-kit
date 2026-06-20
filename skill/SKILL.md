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
4. **Mark a stage complete** after its outputs are written, before moving on:
   `uv run python -c "from scripts.state import PipelineState; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); s=PipelineState.load(sp.state_json,'<ARTIST>'); s.mark_complete('<STAGE_ID>'); s.save(sp.state_json)"`
   Stages are idempotent — re-running overwrites their own outputs without corrupting
   prior stages.

> [!note] Stage-2 source routing
> `scripts.source_signals.needs_llm_review` flags `borderline`-band pages for rubric
> scoring. Also route any **high-value** page (seed domains: Smarthistory, Met, CAA;
> or a page a later stage will cite) through the rubric even if its band is `high`, so
> trust scores on load-bearing sources are confirmed, not assumed.

> [!note] Stage-2 fetching — WebFetch first, Firecrawl on block
> Fetch each source with **WebFetch** (free, built-in) by default. **Escalate to
> `scripts.firecrawl_fetch.fetch_page(url)` (1 Firecrawl credit) when WebFetch is blocked
> or empty** — HTTP 403/429 or no body. Empirically this is the norm for the highest-value
> art sources: museum and scholarly sites (Smarthistory, the Met, MoMA) bot-block WebFetch
> but Firecrawl gets through. WebFetch returns a model read of the page (good enough to
> judge commerce/citation signals directly); Firecrawl returns full markdown for the
> deterministic `scan_source`. Either way, feed what you obtained to the rubric.

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
5. **image_discovery** — see `wiki/stage-image-discovery.md`. Discover candidates per
   work, then download to `images/candidates/<work>/` with `scripts.image_download`.
   Source order: **priority-museum IIIF** (`scripts.iiif`) first; if a work returns no
   public-domain, high-res candidate there — expected for any artist still in copyright
   (e.g. died < ~85 years ago: museums flag the work non-PD) — **fall back to Wikimedia
   Commons** with `scripts.commons.discover_commons(query, work_id)`, which yields
   validated PD `ImageCandidate`s for the same download path:
   `uv run python -c "from scripts.commons import discover_commons; from scripts.image_download import download_candidates; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); cs=discover_commons('<work search query>', '<work-id>', artist='<ARTIST>'); download_candidates(cs, sp.candidates_dir)"`
   Always pass `artist='<ARTIST>'`: Commons search is keyword-based, so without it you get
   wrong-artist PD hits (e.g. Velázquez's *Philip IV as a Hunter* for Miró's *The Hunter*).
   The guard is conservative — it can drop a correct file that never names the artist in its
   title/categories; for in-copyright artists expect few or zero PD candidates either way.
   (Pass `include_cc=True` to also accept CC-BY/CC-BY-SA images — usable with attribution,
   flagged `rights_status: unknown`.) Then generate the contact sheet:
   `uv run python -c "from scripts.gallery import write_gallery; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); write_gallery(sp.candidates_dir, '<ARTIST>', sp.gallery_html)"`
   Save the image-search query you used to `prompts/` for reproducibility with
   `scripts.prompts.save_prompt(sp.prompts_dir, 'image-search', '<the query>', artist='<ARTIST>', stage='image_discovery')`.
   Mark the stage complete, save state, and STOP for Human Pause 1.

> [!info] Human Pause 1 — curation
> The user opens `gallery.html`, star-rates candidates (detail view auto-advances),
> fills the curatorial-gate fields (thesis / anchor trait / handoff note) for
> works rated ≥4★, and exports `selection.json`. See `wiki/stage-curation.md`.

## Run B — synthesis + funnel (stage 6)

6. **preference_synthesis** — gated on `selection.json`. First validate the human's
   curation:
   `uv run python -c "from scripts.selection import load_selection, validate_selection, apply_selection; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); sel=load_selection(sp.selection_json,'<ARTIST>'); print(validate_selection(sel) or 'ok'); apply_selection(sel, sp.candidates_dir, sp.selected_dir)"`
   If validation returns errors, print them and STOP. Otherwise analyze the liked set
   for patterns (your judgment), score each study-set candidate on pattern-fit +
   studyability, and emit the note with `scripts.preference_synthesis.write_preference_synthesis_md`.
   Then mark the stage complete, save state, and STOP for Human Pause 2.

> [!info] Human Pause 2 — funnel
> The user picks the final small study set from the ranked list.

## Run C — study (stages 7–8)

7. **visual_analysis** — gated on a chosen study set. See
   `wiki/stage-visual-analysis.md`. Run the 5-stage formal-analysis instruction set
   per study-set work, cross-check against the artist grammar, then serialize with
   `scripts.analysis.write_analysis_md` → `analysis.md`. Save the 5-stage analysis
   instruction to `prompts/` with
   `scripts.prompts.save_prompt(sp.prompts_dir, 'visual-analysis', '<the instruction>', artist='<ARTIST>', stage='visual_analysis')`.
   Mark complete and save state.
8. **study_retention** — see `wiki/stage-study-retention.md`. Emit the faded-aids
   `study-notes.md`, the `drills/discrimination-cards.md`, and `review-schedule.md`
   via `scripts.study_retention` (`write_study_notes_md`, `write_discrimination_cards_md`,
   `write_review_schedule_md`). Mark complete and save state.

## Output contract

`studies/<artist-slug>/`: `report.md`, `sources/`, `works.md`, `images/`,
`gallery.html`, `selection.json`, `preference-synthesis.md`, `analysis.md`,
`study-notes.md`, `drills/`, `review-schedule.md`, `prompts/`, `state.json`.
Markdown is Obsidian-native (frontmatter + `[[wikilinks]]`).

> [!important] Don't hard-wrap body text
> When you author `report.md` / `works.md` (and any prose), put each paragraph, list
> item, and callout body on a **single physical line** — let the editor soft-wrap.
> Obsidian's default ("strict line breaks" off) renders every newline as a `<br>`, so
> wrapping a sentence across source lines shows up as broken/extra blank lines in reading
> view. Keep genuine `> -` callout list items one per line.
