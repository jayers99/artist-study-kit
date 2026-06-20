---
title: "Visual Analysis — deep-reading the selected works"
type: wiki/stage
stage: 7
sources: [04.1-style-analysis-frameworks, 20-dimensions-of-study-cheat-sheet, 19-stateful-runs-custom-images-staged-analysis]
tags: [wiki/stage, technique/composition, technique/value]
aliases: []
---

# Visual Analysis

> [!info] Pipeline role
> For each curated work, produce a deep formal analysis and the notes a learner needs to
> prepare a study. Emits `analysis.md` per work.

## What the research says

This stage runs the [[concept-formal-analysis-taxonomy]] (from
[[04.1-style-analysis-frameworks]]) as a **5-stage instruction set**, now on a specific
image: (1) structural skeleton (Dow), (2) Notan mapping, (3) palette archeology,
(4) technical layering hypothesis, (5) traps & misconceptions. The report's **reusable
template** captures work id, compositional hierarchy, Notan, palette, layering strategy,
mark-making, and a technique-imitation checklist.

It answers the seed's questions: what is the image doing visually, what to notice first,
the dominant decisions, what to imitate, what traps to avoid, and which exercises to try.

[[20-dimensions-of-study-cheat-sheet]] supplies a broader, exhaustive checklist that the
Dow/Notan/Zorn model nests inside (see [[concept-formal-analysis-taxonomy]]): 18 dimensions
ordered material → organization → subject → feeling → historical, a working **core-12** for
repeated practice, and a closing **"translation into your own study"** layer (*one thing to
copy exactly · one to analyze separately · one to exaggerate · one sentence lesson*). That
last layer is the same artifact the [[stage-curation-interview]] produces per work — analysis
should consume the interview's `study-briefs` as its thesis/anchor input, then deepen them,
not restate.

To keep analysis from becoming passive viewing, fold in [[concept-desirable-difficulty]]:
**predict-then-reveal** (have the learner guess the light source/structure before the answer)
and start the "unseeing" handed over from [[stage-curation]].

## Open questions / tensions

- Where the work has a per-period grammar, analysis should confirm/deny the artist-level
  traits from [[stage-style-definition]] — close the loop, don't restate.
- LLM visual analysis can hallucinate technique from a low-res image; gate depth on the
  reference quality recorded in [[stage-image-discovery]]. (Same metadata-misframe risk the
  [[stage-curation-interview]] flags: don't assert content the image doesn't show.)
- **Bounded depth (request).** [[19-stateful-runs-custom-images-staged-analysis]] (Thrust 3)
  argues deep analysis is expensive and should be capped at ~3–4 works per session via the
  narrowing funnel, with a per-session "what to learn / what to think about / what further
  research is needed" output. Pairs with multi-session state so each session studies a
  different few.

## Skill design implications

- Emit a per-work `analysis.md` from the reusable template, driven by the 5 stage-gate
  prompts; include the technique-imitation checklist as a [[concept-worked-example-fading]]
  job aid for the easel.
- Generate **targeted drills** per work (e.g. the egg/Zorn drill, value thumbnails,
  scumbling study) and pass them to [[stage-study-retention]] as study-passage candidates
  for [[concept-spaced-repetition]] scheduling.
- Cross-check each work against the artist-level grammar; note confirmations and surprises.
- Include a predict-then-reveal variant of the analysis to preserve productive struggle.
