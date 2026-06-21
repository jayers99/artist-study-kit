---
title: "Curation — the human rates the board"
type: wiki/stage
stage: 6a
sources: [13.1-human-curation-ux, 06.1-productive-friction-learning, 18-uat-feedback, 21.1-divergent-convergent-strategic-partner-framework, 21.2-llm-creativity-vs-human-cognition-benchmark]
tags: [wiki/stage, learning/friction]
aliases: []
---

# Curation

> [!info] Pipeline role
> The human-in-the-loop step: the artist reviews the candidate gallery and **visually
> rates/filters** it to a shortlist. Emits `selection.json` (purely visual — no typed
> rationale). The rationale is drawn out next, in [[stage-curation-interview]].

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

This stage originally embodied [[concept-desirable-difficulty]] with a **curatorial gate** —
typing a thesis + anchor trait + handoff note before a work joined the shortlist. UAT
([[18-uat-feedback]] **F6**, superseding F4) found that typing rationale into a form is
opaque and teaches nothing. The friction was **relocated, not removed**: rating stays fast
and purely visual here, and the sense-making happens in the Socratic
[[stage-curation-interview]] that follows. This note now covers only the visual phase.

## Open questions / tensions

- How much to automate the cull (e.g. pre-flag low-res/duplicates) without
  short-circuiting observation? Tooling research is photography-DAM-centric (Lightroom,
  PureRef) — adapt, don't adopt wholesale.
- **Export fidelity (F2).** `selection.json` must round-trip `title`/`date`/`medium`, not
  just `work_id`/`stars`/`rights` — downstream stages and the interview should never re-fetch
  to learn what a selected work *is*.
- **Reproduction badge (F3).** The board should flag posthumous "after / produced by /
  manner of" reproductions (the 1972 Montgomery Ward *Drummer Boy* leaked onto the Klee
  board) so the human isn't asked to rate a non-original; the attribution guard lives in
  [[stage-image-discovery]].
- **Narrowing funnel (request).** [[19-stateful-runs-custom-images-staged-analysis]]
  (Thrust 3) proposes a progressive-zoom flow — small-thumbnail grid → large two-up page →
  commit → interview — where the cut narrows to ≤3–4 as images get larger and dwell time
  grows. Not yet built; would make rating multi-pass and naturally cap the interview. The
  flow is a **divergent→convergent** cycle ([[concept-divergent-convergent-thinking]]): the
  wide board is the divergent search, the staged narrowing is convergent selection — and the
  *human* does the converging, never the AI. It now sits on built multi-session state (below)
  — the funnel records its wide cut as a session's `selected` and its narrow cut as
  `study_set`.
- **Stateful gallery stars — BUILT (Thrust 3, Spec A).**
  [[19-stateful-runs-custom-images-staged-analysis]] §(d), specced/planned as
  `docs/superpowers/{specs,plans}/2026-06-20-persistent-board-stars*` and merged
  2026-06-20 (8-task subagent-driven TDD, 261 tests). The 1–5★ control is **kept**
  (reversing the earlier "drop stars for binary select") and the star is now **persistent on
  the candidate, not the session**: a `stars` field on `BoardCandidate` (`candidates[]`),
  set once, surviving every session and every discovery/import run (`ingest_stars` persists a
  gallery `stars.json`). 1★ = "seen it, not interested" (kept but filterable-out); the board
  now **filters by stars** (all / unstarred / ≥N) and **sorts** by year (default, undated
  last) / stars / file size — the latter enabled by a new collect-time **local thumbnail
  cache** (`cache_thumbnails` → `thumbnail_path`), so the board renders offline and never
  re-pulls. **Stars and selection-for-advancement are orthogonal axes that never read each
  other** — a 1★ work can be selected, a 5★ work left unselected; rating never selects,
  selecting never rates. This **broke and removed the old coupling** in
  `selection.ingest_selection` (which derived `selected` from `liked()`, rating ≥ 4):
  selection now comes from an explicit per-card `selected` flag, carried end-to-end through
  `apply_selection` / `resolve.resolve_selection` / the [[stage-curation-interview]] queue
  (`build_queue(selected_rows(sel), …)`). `liked()` survives only for legacy migration.
  **Still open:** the progressive-zoom funnel + skip-discovery (Thrust 3 **Spec B**, not yet
  built) and the deferred duplicate-handling-on-re-query spec (see `TODO.md`).
- **Multi-session curation — backbone BUILT (Thrust 1).** Curation is no longer one-shot:
  package state (`docs/superpowers/specs/2026-06-20-stateful-package-state-design.md`, merged
  2026-06-20) records each pass as a `session` (`selected`, `study_set`, a `grouping`
  dimension — subject/media/technique/other — and per-session output pointers). A work
  studied in a prior session shows a **studied ✓ badge** (derived from
  `PackageState.studied_work_ids()`) but is **never** filtered out — freedom of choice is
  deliberate: the same work can be re-studied along a different dimension. *Open:* the
  funnel UX and the binary-select gallery (Thrust 3) that consume this state.

## Skill design implications

- Present a **contact-sheet gallery** per work with the decision metadata inline; support a
  fast pick/reject/star pass to a shortlist. Rating is purely visual — **no typed gate**.
- Keep selection human; the skill informs (pre-sorts by importance/studyability/resolution)
  but never auto-picks.
- Emit `selection.json` carrying visual + provenance + `title`/`date`/`medium`; that file is
  the sole input to [[stage-curation-interview]], which produces the study rationale.
- Provide non-destructive markup affordances (overlay arrows/frames) to start the
  "unseeing" that the interview and [[stage-visual-analysis]] continue.
