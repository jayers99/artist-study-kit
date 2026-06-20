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
3. If the next stage is gated by a human pause (`curation_interview`, `preference_synthesis`, `visual_analysis`) and its requirement is unmet, print the instructions for that pause and STOP. Otherwise run the next stage, then mark it complete and save state before continuing.
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
`works_inventory`, `image_discovery`, `curation_interview`,
`preference_synthesis`, `visual_analysis`, `study_retention`.

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
5. **image_discovery** — see `wiki/stage-image-discovery.md`. **Two phases.**

   **Phase A — board build (discovery, thumbnails only):** Call `scripts.wikidata.search_wikidata(artist)`, which returns `(board_candidates, works, ambiguous_candidates)`. Wikidata is the **primary** source: it resolves the artist's QID, fetches linked works from Wikimedia Commons, and returns thumbnail candidates with PD/CC0 provenance baked in. If `ambiguous_candidates` is non-empty the QID is unclear — present the candidates to the user (name + birth/death dates), ask them to pick the correct artist, and record that disambiguation prompt under `prompts/` with `scripts.prompts.save_prompt`. Supplement the Wikidata board with AIC results via `scripts.museum_search.search_aic(artist)`, then combine the two boards: `scripts.wikidata.merge_boards(wikidata_board, aic_board, suppress_aic_ids={w.aic_id for w in works if w.aic_id})` (deduplicates works already known from Wikidata). Render the merged board with `scripts.gallery.build_thumbnail_gallery` and write it to `gallery.html`. Thumbnails are hotlinked — no rights issue for browsing. Save the gallery prompt under `prompts/` and mark the stage complete. STOP for Human Pause 1.

   **Phase B — post-curation resolution (high-res, selected works only):** After the human exports `selection.json`, run `scripts.resolve.resolve_selection(load_selection(...), images/selected/)` to fetch high-res for each liked work. The resolver chain is: Wikimedia Commons PD/CC0 full-res → AIC IIIF 1686px (on `is_public_domain`) → else keep `source_url` as a reference link (do not redistribute in-copyright images). The legacy local-candidate path (IIIF discovery) still uses `scripts.selection.apply_selection`; the thumbnail-board path uses `resolve_selection`. Always browse thumbnails freely; **download high-res ONLY for works with a verified PD/CC0 flag**.

> [!info] Human Pause 1 — visual rating
> The user opens `gallery.html` (a board of many thumbnails), star-rates works, ticks the
> filters (liked-only / PD-only), and exports `selection.json`. Rating is purely visual —
> the study rationale is drawn out next, in the `curation_interview` stage. See
> [[stage-curation]].

## Run B — Socratic curation interview (stage 6)

6. **curation_interview** — gated on `selection.json`. Build the interview queue, then
   interview the human **one study target at a time** to produce each work's study brief.

   - Load ratings: `sel = load_selection(sp.selection_json, '<ARTIST>')`; `from scripts.selection import liked`.
   - Assemble `work_meta` from your `works.md` clusters: a dict `work_id -> {"cluster", "studyability", "study_for"}` (`study_for` set when one liked work is a preparatory study for another).
   - `from scripts.curation_interview import build_queue, pending_targets, parse_briefs, write_study_briefs_json, write_study_briefs_md, validate_briefs, StudyBrief, StudyStep`.
   - `queue = build_queue(liked(sel), work_meta)`. If a `study-briefs.json` already exists, `parse_briefs(json.load(...))` it and interview only `pending_targets(queue, briefs)` (resume).
   - **For each pending target, run the interview** (see below), appending a `StudyBrief` as each is confirmed; re-write `study-briefs.json` after each so progress survives interruption.
   - When `pending_targets` is empty, `validate_briefs(queue, briefs)` must return `[]`; if not, print the errors and STOP. Then `write_study_briefs_md(...)`, mark the stage complete, save state.

   **The interview (per target), AI-led, friction-bearing — the AI asks and reflects, never states the lesson:**
   1. Present **neutral facts only** — title, year, medium, cluster, and the `source_url` link. Do **not** describe what the picture looks like (let the human's eyes lead; metadata can mislead).
   2. **Observe** — ask what the eye does; description before interpretation.
   3. **Hypothesize the rule** — push for the mechanism, not a feature catalog.
   4. **Redirect narrative → technique** — if the human drifts into story/iconography, reflect their own formal observation back as the bridge to a practiceable rule.
   5. **Commit + design the drill** — "if you copy this to steal that one rule, what are you practicing, and what's the test that proves you learned it?" — this yields the study plan.
   6. **Confirm + record** — crystallize thesis / anchor_trait / ordered `study_plan` (each step an optional `success_test`) from the human's words; on confirmation, append the `StudyBrief`.
   7. **Coverage** — steer later targets toward lessons that do not overlap those already confirmed.

## Run C — synthesis + funnel (stage 7)

7. **preference_synthesis** — gated on `study-briefs.json`. First validate and apply the human's selection:
   `uv run python -c "from scripts.selection import load_selection, validate_selection, apply_selection; from scripts.paths import study_paths; sp=study_paths('studies','<ARTIST>'); sel=load_selection(sp.selection_json,'<ARTIST>'); print(validate_selection(sel) or 'ok'); apply_selection(sel, sp.candidates_dir, sp.selected_dir)"`
   If validation returns errors, print them and STOP. Then load `parse_briefs(json.load(open(sp.study_briefs_json)))` and use each brief's thesis / anchor_trait / study_plan as the per-work rationale for pattern analysis. Score each study-set candidate on pattern-fit + studyability and emit the note with `scripts.preference_synthesis.write_preference_synthesis_md`.
   Then mark the stage complete, save state, and STOP for Human Pause 2.

> [!info] Human Pause 2 — funnel
> The user picks the final small study set from the ranked list.

## Run D — study (stages 8–9)

8. **visual_analysis** — gated on a chosen study set. See
   `wiki/stage-visual-analysis.md`. Run the 5-stage formal-analysis instruction set
   per study-set work, cross-check against the artist grammar, then serialize with
   `scripts.analysis.write_analysis_md` → `analysis.md`. Save the 5-stage analysis
   instruction to `prompts/` with
   `scripts.prompts.save_prompt(sp.prompts_dir, 'visual-analysis', '<the instruction>', artist='<ARTIST>', stage='visual_analysis')`.
   Mark complete and save state.
9. **study_retention** — see `wiki/stage-study-retention.md`. Emit the faded-aids
   `study-notes.md`, the `drills/discrimination-cards.md`, and `review-schedule.md`
   via `scripts.study_retention` (`write_study_notes_md`, `write_discrimination_cards_md`,
   `write_review_schedule_md`). Mark complete and save state.

## Output contract

`studies/<artist-slug>/`: `report.md`, `sources/`, `works.md`, `images/`,
`gallery.html`, `selection.json`, `study-briefs.json`, `study-briefs.md`,
`preference-synthesis.md`, `analysis.md`,
`study-notes.md`, `drills/`, `review-schedule.md`, `prompts/`, `state.json`.
Markdown is Obsidian-native (frontmatter + `[[wikilinks]]`).

> [!important] Don't hard-wrap body text
> When you author `report.md` / `works.md` (and any prose), put each paragraph, list
> item, and callout body on a **single physical line** — let the editor soft-wrap.
> Obsidian's default ("strict line breaks" off) renders every newline as a `<br>`, so
> wrapping a sentence across source lines shows up as broken/extra blank lines in reading
> view. Keep genuine `> -` callout list items one per line.
