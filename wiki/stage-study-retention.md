---
title: "Study & Retention — turning analysis into durable skill"
type: wiki/stage
stage: cross-cutting
sources: [05.1-master-study-pedagogy, 06.1-productive-friction-learning, 07.1-study-aids-scaffolding, 08.1-spaced-repetition-retention]
tags: [wiki/stage, learning/retention, learning/friction]
aliases: []
---

# Study & Retention

> [!info] Pipeline role
> The cross-cutting pedagogy layer: convert the analysis into study notes, drills, aids, and
> a review schedule that actually internalize the artist's grammar. Emits `study-notes.md`,
> drill sets, and a review schedule.

## What the research says

Four reports converge here:

- **Pedagogy & workflow** ([[05.1-master-study-pedagogy]]): the atelier/Bargue/copyist
  tradition — copying to "digest" a master, training the eye, broad accuracy over slavish
  duplication. A 4-stage self-learner workflow: collate/chunk → draw from the flat
  (time-boxed) → **gapped worksheet** (reconstruct a removed passage) → checklist review.
  Critique works against a **fixed external target**; AI as a "simulated tutor" (value maps,
  checklists), never the hand.
- **Friction** ([[concept-desirable-difficulty]]): spacing, interleaving, retrieval, reduced
  feedback; the answer-withholding/Socratic stance and help-abuse guardrails.
- **Aids & fading** ([[concept-worked-example-fading]]): job-vs-learning aids, worked-example
  fading, checklists, the attempt-first protocol, art-study templates.
- **Retention** ([[concept-spaced-repetition]]): FSRS for declarative facts; Woodpecker
  cycles + the 500ms feedback rule for procedural drills; interleaving for discrimination;
  honest SRS limits (can't model brush-on-canvas; active production > recognition).

## Open questions / tensions

- SRS excels for declarative + perceptual discrimination but **can't fully drive
  procedural/motor** retention — the schedule must mix card-review with enacted re-studies.
- Friction must stay inside the ZPD; mis-calibrated difficulty becomes frustration.
- A static study package can't run an adaptive scheduler — does the skill emit a *plan*
  (Leitner-style) or integrate with Anki/FSRS? (Likely emit importable artifacts.)
- **Feature request (live Monet run, 2026-06-20): a medium-aware "digital friction lab."**
  The current `study-notes.md` faded aids tell the learner *what* to imitate; this asks for a
  **progressive ladder of micro-experiments that lets the learner discover the underlying
  technical rules themselves** — never handing over the solution (deepens
  [[concept-desirable-difficulty]] + [[concept-divergent-convergent-thinking]]). Each rung =
  one small task + an empirical "Find out" + a self-check, each isolating **one variable**, so
  the learner reverse-engineers the science: e.g. *which contrast channels draw the eye*
  (value vs chroma vs hue vs edge), and *the optical-mixing thresholds for "shimmer"*
  (value-distance vs hue-distance vs chroma vs mark-size/viewing-distance). Two design moves
  carry the friction: **hints are folded + escalating** (nudge the next experiment, never the
  answer) and the **master work is the "answer key to measure against," not to trace.** Open
  questions for productizing: (a) it's **medium-aware** — it leans on digital instruments
  (eyedropper/HSB readouts, single-variable adjustment layers, blur-as-squint) as *measuring
  tools*; does the skill detect/ask the medium and branch (digital vs wet)? (b) where does it
  sit — a new optional stage, or an enrichment of `study_retention`? (c) the experiment
  ladders are technique-specific (contrast, broken color) — can they be generated per study
  brief, or do they need a library of technique→experiment templates? Reference
  implementation (hand-authored for this run): `studies/claude-monet/learning-path.md`.

## Skill design implications

- Emit `study-notes.md` per work: what to notice first, decisions to imitate, traps,
  exercises — structured as faded aids (cheat sheet → checklist → bare prompt).
- Generate **artifacts**: style-discrimination card sets (A-vs-not-A), spaced study-passage
  /Woodpecker drills, gapped worksheets, and FSRS-importable declarative decks.
- Emit a **review schedule** (spaced + interleaved across works/styles) and bake in
  productive friction (predict-then-reveal, memory-based reconstruction, attempt-first).
- Position any AI critique as a Socratic tutor with answer-withholding + help-abuse
  guardrails; keep production in the human's hand.
