# Socratic Curation Interview — Design Spec

**Date:** 2026-06-20
**Status:** approved (design) → ready for implementation plan
**Source feedback:** `raw/18-uat-feedback.md` finding **F6** (supersedes F4); dry-run worked examples in that doc's "Curation walkthrough decisions" section.
**Related stages:** [[stage-curation]], [[stage-visual-analysis]]; concepts [[concept-desirable-difficulty]], [[concept-worked-example-fading]].

## Motivation

Curation currently asks the human to type three rationale fields — **thesis**, **anchor trait**, **handoff note** — directly into `gallery.html` while rating works. UAT showed two problems:

1. The fields are opaque ("*I wasn't sure what I was supposed to put in there*"), so they get left blank and only fail at export-time `validate_selection`.
2. Typing rationale into a form does no *teaching*. The whole project is built on productive friction; the gate should be where learning happens, not a data-entry chore.

A live dry-run (Paul Klee, three works) proved a better shape: strip the fields out of the visual phase, and after `selection.json` is produced, run an **AI-led Socratic interview, one work at a time**, that *draws the rationale out of the human through questioning*. In the dry-run the human extracted a transferable, practiceable lesson and **designed the study progression themselves** — the AI only asked questions and reflected, never stated the lesson. Three non-overlapping studies emerged (contour-rhythm, facial-economy, opposed-geometries).

This spec splits curation into two cleanly separated steps:

- **Step 1 — visual rating (unchanged tool, trimmed):** look, star-rate, filter → `selection.json`. No rationale here.
- **Step 2 — Socratic interview (new stage):** friction-bearing per-work dialogue → `study-briefs.{json,md}`.

## Goals

- Replace the gallery's three text fields with a conversational, friction-bearing interview that produces each selected work's study rationale **and teaches in the process**.
- Capture the rationale as a **structured study brief** (thesis, anchor trait, ordered study plan with success tests) — richer than three flat strings.
- Make the interview **resumable and idempotent**, and enforce a completeness contract before the stage closes.
- Keep the human in control of taste; the AI never supplies the lesson.

## Non-goals (separate specs)

- **F1** WDQS resilience / lighter QID resolution.
- **F3** reproduction / posthumous-"after" attribution filter (e.g. the 1972 Montgomery Ward *Drummer Boy* that leaked onto the Klee board).
- **F5** zero-PD-candidate board notice.
- No web UI for the interview; no browser automation (a source-image link is sufficient — confirmed in the dry-run).

## Decisions (locked)

| Decision | Choice | Rationale |
| --- | --- | --- |
| Output artifact | **New `study-briefs.json` + `study-briefs.md`** | Keeps `selection.json` purely visual; lets the study plan be a rich structured object. |
| Spec scope | **Both halves** | The split only works if the gallery fields are removed *and* the interview stage exists; shipping them together avoids a dead intermediate state. |
| Coverage / order | **All liked (≥4★), smart order** | Order by cluster/period then studyability; merge study→final pairs; AI steers toward non-overlapping lessons. No hard cap — the interview itself prunes. |
| Interview medium | **In-session conversation (AI is interviewer)** | The dialogue is SKILL.md procedure; only queueing/serialization/validation are scripted. |
| Output structure | **Structured study plan** | The dry-run handoff naturally became a multi-step protocol with success tests, not a one-liner. |

## Architecture

### Pipeline placement

Insert a new stage `curation_interview` into `scripts/state.py::STAGES`, between `image_discovery` and `preference_synthesis`:

```
… image_discovery → curation_interview → preference_synthesis …
```

- Add `PAUSE_GATES["curation_interview"] = "curation complete: selection.json present"`.
- `preference_synthesis`'s existing gate changes from "selection.json present" to "study-briefs.json present" (its real upstream dependency is now the briefs).

The Human Pause that today precedes `preference_synthesis` (export `selection.json`) effectively moves one stage earlier; the interview runs *after* the human exports ratings and *before* synthesis.

### Components

**A. `scripts/gallery.py` (modify).** Remove the three rationale inputs from the board UI and from `_THUMB_TEMPLATE`. Add `title`, `date`, and `medium` to the exported per-work payload (fixes F2 — titles were `None` in UAT). The board stays a pure visual rate/filter tool.

**B. `scripts/selection.py` (modify).** `Rating` keeps visual + provenance fields (`work_id`, `rating`, `qid`, `source_url`, `museum`, `rights`, `inst_ids`, image refs) and gains `title`, `date`, `medium`; it **loses** `thesis`/`anchor_trait`/`handoff_note`. `validate_selection` drops the gate-text checks and validates only: rating in 0–5, `work_id` present. `parse_selection` ignores any stale gate fields.

**C. `scripts/curation_interview.py` (new) — the testable core.**
- `build_queue(liked_ratings, work_meta) -> list[StudyTarget]`: order the liked works for interview. `work_meta` is a `dict[work_id] -> {cluster, studyability, study_for}` supplied by the SKILL.md step, which assembles it from the works inventory the AI authored (`works.md` is prose/markdown, not machine-readable, so the AI passes structured hints rather than the script parsing it). `build_queue` groups by `cluster`, orders by `studyability` descending within a group, and **merges study→final pairs**: when one work's `study_for` names another liked work, they collapse into one `StudyTarget` with `members:[final_id, study_id]` (final first). A target carries its display facts (title/year/medium/cluster/source_url) and the merge reason. Works with no `work_meta` entry sort last in a default group, so the queue is robust to gaps.
- `StudyBrief` dataclass + `serialize_briefs(briefs) -> dict` / `parse_briefs(dict) -> list[StudyBrief]` (round-trip).
- `write_study_briefs_json(briefs, path)` and `write_study_briefs_md(briefs, artist, path)` (Obsidian-native: one `> [!example]` callout per target, `[[wikilinks]]` to works).
- `pending_targets(queue, existing_briefs) -> list[StudyTarget]`: targets without a brief yet (resume support).
- `validate_briefs(queue, briefs) -> list[str]`: every queued target has a brief whose `thesis`, `anchor_trait`, and non-empty `study_plan` are filled; empty list = complete.

**D. `SKILL.md` (modify).** Document the new stage and the per-work interview procedure (below). The conversation is the AI's job; scripts handle queue, serialization, completeness.

### The interview procedure (SKILL.md prose)

For each `StudyTarget` from `build_queue`, in order:

1. **Present neutral facts only** — title, year, medium, cluster/period, and the source-image link. **Never assert what the picture looks like** (the UAT metadata-misframe: a work was wrongly pre-labeled "color-grid"; the human's eyes corrected it). Let observation lead.
2. **Observe** — ask what the eye actually does; description before interpretation.
3. **Hypothesize the rule** — push the human to state the *mechanism* ("Klee drops a contour when ___ and leaves it open when ___"), not catalog features.
4. **Redirect narrative → technique when needed** — if the human drifts into iconography/story (the "appreciation reflex"), reflect **their own** formal observation back as the bridge to a practiceable rule (in UAT, "he didn't put eyes on that figure" became the *facial-economy* lesson).
5. **Commit + design the drill** — "If you copy this to *steal that one rule*, what are you practicing, and what's the test that proves you learned it, vs. just a nice copy?" This is the reliable convergence move; it yields the study plan.
6. **Confirm + write the brief** — the AI crystallizes thesis / anchor / study-plan from the human's words, the human confirms or tweaks, then it's serialized.
7. **Track coverage** — keep the running set of confirmed lessons; steer later works toward **non-overlapping** lessons rather than redundant ones.

**Contract (non-negotiable):** the AI proposes *questions and sharpened restatements only*. It must not state the lesson for the human. Friction is the feature.

### Data model — `study-briefs.json`

```json
{
  "artist": "Paul Klee",
  "briefs": [
    {
      "work_id": "exotics",
      "title": "Exotics",
      "year": "1939",
      "members": ["exotics", "the-sales-woman-in-the-open-study-for-exotic"],
      "cluster": "late glyph",
      "source_url": "https://www.artic.edu/artworks/134057",
      "thesis": "A study in facial/figural economy as the emotional and narrative dial …",
      "anchor_trait": "economy of facial information — angular face = tension, eyeless figure = watchful blankness",
      "study_plan": [
        { "step": "Copy the ink study (Sales Woman): his linear skeleton + angular faces + omissions as first set.", "success_test": null },
        { "step": "Copy the oil (Exotics): note what changed committing to paint — did faces simplify further?", "success_test": null },
        { "step": "Variation drill: one figure, facial-economy ladder (full features → angular only → eyes omitted).", "success_test": "Make the same figure read warm / tense / uneasy by changing only facial information." }
      ]
    }
  ]
}
```

`members` with length > 1 records a merged study→final pair. `study_plan` steps are ordered (faded complexity); `success_test` is optional per step.

`study-briefs.md` renders each brief as a `> [!example]` callout with thesis, anchor, and the numbered plan, linking `[[work_id|Title]]`.

### Downstream consumption

`preference_synthesis` and `visual_analysis` read `study-briefs.json` instead of the old `Rating` gate fields. The anchor trait and study plan are the rationale handed to visual analysis (the brief *is* the shortlist rationale that [[stage-curation]] always intended).

## Error handling & resume

- **Idempotent:** re-running the stage reads existing `study-briefs.json`; `pending_targets` returns only targets without a brief, so the interview resumes where it stopped.
- **Zero liked works:** stage no-ops with a clear message and does not mark complete.
- **Completeness gate:** the stage may not be marked complete until `validate_briefs` returns empty — the scripted enforcement of the AI's output contract.
- **Stale `selection.json` gate fields:** ignored on parse (no error), easing migration from the old schema.

## Testing

pytest on the pure units (no network, no LLM):

- `build_queue`: cluster grouping, studyability ordering within group, study→final pair merge via `study_for` (the *Exotics* + *Sales Woman* case), and robustness when a `work_meta` entry is missing (work sorts last, no crash). Liked-threshold filtering stays in `selection.liked()` upstream.
- `serialize_briefs` / `parse_briefs`: round-trip including `members` and optional `success_test`.
- `validate_briefs`: flags a target with no brief, a brief with empty thesis/anchor, an empty `study_plan`.
- `validate_selection` (modified): passes a liked work with no rationale (gate removed); still flags out-of-range rating and missing `work_id`.
- gallery export: payload includes `title`/`date`/`medium`.

The interview dialogue itself is SKILL.md prose, not unit-tested; `validate_briefs` enforces its output contract.

## Worked examples (from the dry-run, `raw/18`)

- *Women Harvesting* (1937) → **contour-rhythm**: three-state line grammar (straight/curved/absent) steering the eye; study plan = monochrome line → +grays → +color chords, test by tracing eye-path.
- *Exotics* (1939, merged with its prep drawing *Sales Woman*) → **facial economy**: meaning by omission; study plan exploits the study→final pair.
- *Mosaic-Like* (1932) → **opposed geometries**: angular knot (deep focus) vs. flowing S-curve (travel); study plan = line-only opposition, test by eye-path.

These three are deliberately non-overlapping — the coverage-steering behavior in action.
