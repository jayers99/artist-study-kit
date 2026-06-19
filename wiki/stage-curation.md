---
title: "Curation — the human picks the shortlist"
type: wiki/stage
stage: 6
sources: [13.1-human-curation-ux, 06.1-productive-friction-learning]
tags: [wiki/stage, learning/friction]
aliases: []
---

# Curation

> [!info] Pipeline role
> The human-in-the-loop step: the artist reviews the candidate gallery and selects a
> shortlist for deep study. Emits `images/selected/` + a shortlist rationale.

## What the research says

[[13.1-human-curation-ux]] frames curation as two phases: **jurying** (subtractive, fast
"cull" — Pick/Reject/Unflag with auto-advance, ergonomic shortcuts) then **curating**
(additive, thesis-driven — start from 1–2 anchor pieces and build a set). A selection set
beyond **8–10 works induces choice paralysis**, so a "focus mode" mutes non-shortlisted
assets.

Metadata at decision time should surface the **Elements of Art** (line, shape, form, color,
value, texture, space, pattern) plus tech data (medium, source, resolution) so the choice
is about *educational value*, not just prettiness. Selection heuristics favor
**learnability** over taste (the "learnability ladder"; "truth to materials" filter).

Crucially, this stage embodies [[concept-desirable-difficulty]]: a **curatorial gate**
forces a sense-making pause (assign an Element-of-Art tag + a one-line observation) before a
work joins the shortlist — preventing a passive "visual heap" and keeping the human a real
agent. This is productive friction by design, not automation.

## Open questions / tensions

- How much to automate the cull (e.g. pre-flag low-res/duplicates) without
  short-circuiting observation? Tooling research is photography-DAM-centric (Lightroom,
  PureRef) — adapt, don't adopt wholesale.
- Where does the UI live? A CLI/skill can't render a Lightroom-grade survey view; likely an
  Obsidian/HTML contact sheet + a structured selection worksheet.

## Skill design implications

- Present a **contact-sheet gallery** per work with the decision metadata inline; support a
  fast pick/reject pass, then a thesis-driven shortlist (cap ~8–10).
- Implement a **curatorial gate**: to select a work, the human must record a curatorial
  thesis, a visual anchor (the trait to study), and a handoff note — this *is* the
  shortlist rationale handed to [[stage-visual-analysis]].
- Keep selection human; the skill informs (pre-sorts by importance/studyability/resolution)
  but never auto-picks.
- Provide non-destructive markup affordances (overlay arrows/frames) to start the
  "unseeing" that visual analysis continues.
