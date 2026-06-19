---
title: "Visual Analysis — deep-reading the selected works"
type: wiki/stage
stage: 7
sources: [04.1-style-analysis-frameworks]
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

To keep analysis from becoming passive viewing, fold in [[concept-desirable-difficulty]]:
**predict-then-reveal** (have the learner guess the light source/structure before the answer)
and start the "unseeing" handed over from [[stage-curation]].

## Open questions / tensions

- Where the work has a per-period grammar, analysis should confirm/deny the artist-level
  traits from [[stage-style-definition]] — close the loop, don't restate.
- LLM visual analysis can hallucinate technique from a low-res image; gate depth on the
  reference quality recorded in [[stage-image-discovery]].

## Skill design implications

- Emit a per-work `analysis.md` from the reusable template, driven by the 5 stage-gate
  prompts; include the technique-imitation checklist as a [[concept-worked-example-fading]]
  job aid for the easel.
- Generate **targeted drills** per work (e.g. the egg/Zorn drill, value thumbnails,
  scumbling study) and pass them to [[stage-study-retention]] as study-passage candidates.
- Cross-check each work against the artist-level grammar; note confirmations and surprises.
- Include a predict-then-reveal variant of the analysis to preserve productive struggle.
