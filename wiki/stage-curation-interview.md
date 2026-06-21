---
title: "Curation Interview — Socratic per-work study briefs"
type: wiki/stage
stage: 6b
sources: [18-uat-feedback, 06.1-productive-friction-learning, 05.1-master-study-pedagogy, 20-dimensions-of-study-cheat-sheet, 21.1-divergent-convergent-strategic-partner-framework, 21.2-llm-creativity-vs-human-cognition-benchmark]
tags: [wiki/stage, learning/friction, learning/socratic]
aliases: ["Socratic Curation Interview", "Study Brief Interview"]
---

# Curation Interview

> [!info] Pipeline role
> After the human exports `selection.json` (visual rating, [[stage-curation]]), an AI-led, friction-bearing interview walks each liked work one at a time and *draws out* its study rationale through questioning. Emits `study-briefs.{json,md}` — the structured rationale handed to [[stage-visual-analysis]].

## What the research says

This stage exists because UAT split rating from rationale ([[18-uat-feedback]] **F6**, superseding F4). The old curatorial gate asked the human to *type* a thesis / anchor-trait / handoff-note into the gallery while rating — opaque ("*I wasn't sure what I was supposed to put in there*"), left blank, and pure data-entry that taught nothing. F6's fix is structural: strip the text fields from the visual phase and replace them with a Socratic interview where the **human does the thinking and the AI only scaffolds** — the gate becomes where learning happens, not a form.

The dry-run (Klee, three works) validated a reliable per-work arc: **observe → hypothesize the rule → (redirect narrative → technique) → commit + design the drill → confirm**. The convergence move is *"if you copy this to steal that one rule, what are you practicing, and what's the test that proves you learned it vs. just a nice copy?"* — it forced a practiceable lesson out of every image and maps directly onto the closing "translation into your own study" layer of [[concept-formal-analysis-taxonomy]] / [[20-dimensions-of-study-cheat-sheet]] (*one thing to copy · one to analyze · one sentence lesson: "this artist teaches me how to ___"*). This operationalizes the master-study pedagogy in [[05.1-master-study-pedagogy]]: a copy is only instructive when it isolates a transferable decision.

The interview embodies [[concept-desirable-difficulty]] (answer-withholding Socratic dialogue) and produces a [[concept-worked-example-fading]] artifact: the handoff is not a flat string but a **faded study protocol with success tests** (e.g. monochrome line → +grays → +color chords; *"trace your eye-path — does it loop?"*). Study→final pairs (a prep drawing and its painting) merge into one target so the protocol exploits the progression.

## Open questions / tensions

- **AI must not pre-frame the picture.** The dry-run's sharpest lesson: the AI mislabeled *Mosaic-Like* as "color-grid" from title+year *without seeing it*; the human's eyes corrected it. Contract for the spec — present neutral facts only (title/year/medium/series/source-image link) and let observation lead. **Never assert what a work looks like from metadata.**
- **The appreciation reflex.** Humans drift into iconography/story ("is this a brothel?"). The redirect that works is to seize the human's *own* formal noticing ("he didn't put eyes on that figure") and bridge it to a practiceable rule — an explicit "redirect narrative → technique" move.
- **Coverage, not redundancy.** Track the running set of confirmed lessons and steer later works toward *non-overlapping* ones (contour-rhythm / facial-economy / opposed-geometries were kept distinct). This is **maximizing semantic distance across the study set** ([[concept-divergent-convergent-thinking]]) — the divergent-association metric applied to lessons, not words: each new brief should sit far from the ones already confirmed. The AI runs the divergent search over candidate readings; the human owns the convergent selection of the lesson.
- **Session cap — RESOLVED (Thrust 3, Spec B, BUILT).** [[19-stateful-runs-custom-images-staged-analysis]] wanted the interview bounded to ~3–4 works per session via a narrowing funnel (small grid → large two-up → commit → interview). The funnel shipped (see [[stage-curation]]): the ≤4 cap is now enforced upstream as `MAX_STUDY` (hard-gated in the funnel JS + `parse_study_set` truncation), and the interview queue is `build_queue(rows)` filtered to the `study_set` — so this stage simply receives an already-capped set. The old "interview prunes, no hard cap" stance is superseded; the cap lives in the funnel, the interview consumes it.
- **Opening-question variety (M1 UAT, live Monet run — further discussion, not yet specced).** The interview is **strong overall** (the observe→rule→drill arc held again on Monet across two works, producing real briefs from the human's words), but the **first question is effectively identical every run** ("look ~10s — where does your eye land first and where does it travel?"). Starting with observation is still the right opening — the concern is *sameness*: the same phrasing every time risks a rut and a rote answer. Directions to explore (undecided): vary the opening move while preserving the **observe-first / never-pre-frame** contract — e.g. seed the prompt from the work's cluster/medium (a still life vs a snow-effect landscape might invite different first looks), rotate among a small bank of observation framings, or let it adapt to *how the human actually performs the look* (the user wants to add detail about their own observation ritual so the AI can mix it up). Classified by the user as a **point of further discussion**, to revisit later.

## Skill design implications

- New pipeline stage `curation_interview` between `image_discovery` and `preference_synthesis`; gate = `selection.json` present; it may not close until every queued target has a complete brief (`validate_briefs` empty). Resumable/idempotent: re-running reads existing briefs and interviews only `pending_targets`.
- `build_queue` orders liked works by cluster/period then studyability and merges study→final pairs (the AI supplies structured `work_meta` hints since `works.md` is prose).
- The brief data model = `thesis` (prose) · `anchor_trait` (short) · ordered `study_plan` of steps, each with an optional `success_test`; serialized to `study-briefs.json` and rendered as Obsidian `> [!example]` callouts in `study-briefs.md` with `[[work_id|Title]]`-style links.
- **Non-negotiable contract:** the AI proposes *questions and sharpened restatements only*, never the lesson. Friction is the feature. Downstream, [[stage-visual-analysis]] and preference-synthesis read the brief as the shortlist rationale [[stage-curation]] always intended.
