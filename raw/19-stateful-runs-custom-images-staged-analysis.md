---
type: raw/feature-request
title: "New feature request — stateful multi-run, custom image injection, staged analysis funnel"
status: living
opened: 2026-06-20
tags:
  - "#feature-request"
  - "#change-in-process"
---

# New feature request — and a change in process

Captured from a working-session brainstorm. This is a **request + intent capture**, not a design — the exact shape of each piece gets settled during the refinement discussion (and likely a `superpowers:brainstorming` pass → spec). Builds directly on the curation/analysis direction in `[[18-uat-feedback]]` (esp. F6's Socratic interview) and the two-phase image model from `[[17-image-discovery-hardening-session]]`.

The through-line: **today the skill is a single linear pass.** The request is to make it a **stateful, resumable, multi-run workflow** where image collection and study sessions can each happen many times against an accumulating, persisted package — plus to fold in the user's own image collection as a first-class source, and to restructure analysis as a narrowing funnel.

---

## Thrust 1 — persistent state + multiple runs

**What's wanted.** The system should **keep state** for an artist study and support **multiple runs over time**, of two distinct kinds:
- **Multiple runs of image discovery** — re-run discovery later (e.g. after a Wikidata outage clears, or to add a newly-found source) and have new candidates merge into the existing board rather than starting from scratch.
- **Multiple study sessions** — come back to the same artist on different days and pick up where you left off, or run a fresh study pass over a different subset of the collected images.

**Why now.** A real study practice is iterative and spread across sessions; a one-shot linear pipeline can't model "I collected images Monday, studied three of them Tuesday, want to study three more next week." `[[18-uat-feedback]]` F1 also wants discovery to mark a stage `degraded` so a later re-run can **upgrade** it — that already presumes persisted, re-enterable state.

**Initial shape (to refine).**
- A durable per-artist state file/manifest under `studies/<artist>/` that records: what discovery runs have happened, the accumulated candidate/board set, which images are user-supplied vs skill-discovered, and the history of study sessions + their outputs.
- Discovery and study become **idempotent, mergeable, resumable** rather than destructive.

**Open questions.**
- What's the state format and where does it live (extend `selection.json`/`resolved.json`, or a new top-level `state.json`)?
- Merge semantics: how do we dedup across discovery runs (QID is the natural key per `[[17-image-discovery-hardening-session]]`)?
- How does a study session reference the exact image set it studied, so sessions are independently replayable/auditable?

## Thrust 2 — inject the user's own image collection

**What's wanted.** Beyond the skill's own discovery, let the user **inject their own paintings** — a large personal collection spanning many artists — into the system as study candidates.

**Initial shape (to refine).**
- User hands the skill a **folder of images**.
- The AI tries to **identify each image** (Google image search / reverse-image lookup) to recover the metadata the skill normally gets from its own discovery: **title, date, source/owner (which institution holds it), where it can be seen**, and ideally medium/dimensions.
- Result: user-supplied images are enriched to the **same metadata shape** as discovered candidates, so they flow through curation/analysis identically.

**Open questions.**
- Reverse-image-search mechanism — Google Images has no clean API; what's the actual tool path (and its reliability/cost)? Worth a small research spike.
- Confidence handling: identification will sometimes be wrong or partial — do we surface a confidence flag and let the human confirm/correct before the metadata is trusted? (Mirrors the F3 attribution-guard lesson: don't silently trust auto-derived provenance.)
- Multi-artist folders: does the user pre-sort by artist, or does the system cluster/route images to the right artist study?
- Provenance/rights: user-supplied images bypass the rights resolver — how do we tag their copyright posture?

## Thrust 3 — multi-study iterations + a narrowing analysis funnel

**What's wanted.** Two related changes to the study side:

**(a) Skip-discovery switch.** A way to enter the skill saying *"don't collect any images — go straight to the selection grid"* and run a study session over images already in the package (from a prior discovery run or from Thrust 2). Decouples "study" from "collect."

**(b) Staged narrowing funnel for analysis — a progressive-zoom flow.** Deep visual analysis + the Socratic interview are **expensive enough that we should cap them at ~3–4 images per session.** So restructure analysis as a multi-level visual funnel where the **core mechanic is: as the cut gets finer, the images get larger and you look at them longer.** Refinement and image-size/dwell-time scale together.

1. **Broad grid — small thumbnails.** The first board stays as it is today: many **small** thumbnails (about the current size), scanned quickly. You rate/select the ones that "from a distance look interesting enough." Example: ~15 selected.
2. **Closer look — large thumbnails, new page.** Hitting *next* opens a **new web page showing only the selected set** at **much larger** size — roughly a **two-up layout** so each image gets real screen real-estate. Here you look more carefully/longer and cut down to a **small number, 4 at most** (e.g. 3–4).
3. **Commit → Socratic.** Hitting *next* from the large-thumb page **writes `selection.json`** and enters the **Socratic interview** (per `[[18-uat-feedback]]` F6) on just those 3–4.
4. **Final output artifacts** — for the chosen few: *these are the studies we'll do*, *what we're trying to learn from each*, *what to think about*, and *what additional research is needed to actually do them*.

**Why.** Keeps each session's expensive analysis bounded and focused, and produces a concrete, actionable study plan instead of a sprawl. The progressive-zoom UX matches how real curation feels — fast wide scan, then slow close looking — and naturally enforces the 3–4 cap. Dovetails with the F6 finding that the interview output is really a **structured study protocol with success tests**, not flat text.

**(c) Sort order — three options, year created by default.** The HTML gallery offers **three sort orders** (just these to start):
1. **Year created (ascending)** — the **default**. Seeing the board chronologically lets the human read an artist's development across the wall and makes period/series grouping legible at a glance (reinforces the F6 "surface series/period" intent). Year comes from the candidate metadata (Wikidata `inception` / museum `date`); works with an unknown/undated year sort last.
2. **By stars** — sort on the persistent per-candidate star rating (see (d)), e.g. to bring the highest-rated to the top or push 1★ "rejects" to the bottom.
3. **By file size** — sort on image size. (Spec note: trivial for `origin:"user"` local files; discovered candidates only have a remote `thumbnail_url`, so file size isn't known without a fetch — decide at spec time whether to fetch lazily, use a proxy like pixel dimensions, or only size what's resolved.)

Sorting applies to the small-thumb grid and should carry through to the large two-up page.

**(d) Keep star ratings — and make them stateful on the gallery.** *(This supersedes the earlier "drop stars for binary select" revision.)* The 1–5★ control stays. The key change: **the star belongs to the gallery/candidate, not the session.** A star is set once and **persists across every study session and every image-collection run** — it never varies by study and never resets when discovery re-queries and ingests more images. New candidates arrive **unstarred**; the human can rate them at any time and the rating remains until they change it.

Use-cases this enables on a board that grows over time:
- **1★ = "seen it, not interested."** Rejects stay on the board (nothing is deleted) but can be filtered out of view, so re-running discovery doesn't re-surface them as fresh.
- **Filter by stars** — e.g. filter to **unstarred** to find what still needs rating, rate them, then filter those out later; or filter to ≥4★ to study the keepers.

**Stars ≠ selection — two completely independent axes.** A star rating and a selection-for-advancement are orthogonal and must **never** depend on each other. The star is a **persistent annotation** (filter/sort only); **selection-for-advancement** is the per-session act of choosing which works move forward through the funnel into a study. Rating a work does **not** select it; selecting a work does **not** change its star. A 1★ work can still be selected into a study; a 5★ work can be left unselected this round. Nothing in selection reads a star threshold, and nothing in rating triggers selection.

Model implication: this **reverses the Thrust-1 locked decision** *"rating/selection is per-session, not per-candidate"* — but only for the **star**, which becomes a persistent `stars` field on `BoardCandidate` (`candidates[]`), surfaced/edited in the gallery, filterable/sortable. **Selection stays per-session** (a session records which works it advanced / studied). Critically, this **breaks the current coupling** in `selection.ingest_selection`, which derives the selected set from `liked()` (rating ≥ 4) — i.e. it uses the star as the selection signal. Thrust 3 must decouple them: selection comes from the funnel's explicit picks, not from a star threshold. `selection.json` / `Rating` and anything that keyed selection off stars must be reworked accordingly.

**Open questions.**
- Stage-count: is it always two visual cuts (small grid → large two-up → Socratic), or can there be a third intermediate size for very large initial selections?
- Sort: is chronological the only order, or a default with optional toggles (by museum, by score)? How do we handle date ranges / circa dates when sorting (sort on the start year)?
- Schema impact: stars become a **persistent per-candidate field** on `BoardCandidate` (`candidates[]`), no longer per-session. Decide how the gallery reads/writes them (the gallery edits state directly, or exports a stars delta the skill ingests), and how filter-by-star / sort-by-star are driven. `selection.json` / `parse_selection` / `Rating` must be reconciled with the candidate-owned star (which works are *studied* in a session is separate from the work's persistent star).
- Future feature (deferred — to-do): **duplicate handling on re-query/ingest.** As the gallery grows across discovery runs and custom-image imports, define what happens when a newly-found image is (or may be) a duplicate of one already on the board — especially so a starred work isn't re-added unstarred. Out of scope for the first Thrust-3 build; straighten out in a later spec.
- What's the triage criterion at the final cut — studyability, non-overlap of lessons (F6 tracks a "running set, steer toward coverage" rule), human gut, or AI-proposed + human-confirmed?
- Are the widths (small/large) and the final cap (≤4) fixed or configurable? Does the funnel's top width depend on board size?
- Layout specifics for the large-thumb page: strictly two-up, or responsive (two-up on wide screens)? Does it carry the same star/gate/filter affordances as the first board, or is it stripped down to "look + pick"?
- How does this funnel interact with multi-session state (Thrust 1) — does each session consume images so the next session naturally studies *different* threes?
- The final "additional research needed" artifact — does it feed back into the deep-research / NotebookLM loop?

---

## Cross-cutting

- **State (Thrust 1) is the backbone** that makes Thrusts 2 and 3 coherent: custom images are just another way state accumulates candidates; the multi-study funnel is a sequence of sessions recorded in state. Design state first.
- **Relationship to in-flight work:** the F6 Socratic interview spec (`docs/superpowers/specs/2026-06-20-socratic-curation-interview-design.md`) is exactly the "deep work on the 3" step of the funnel — these should be specced together, not separately.
- **Process change implied by the title:** the skill stops being a single linear `run` and becomes a set of **re-enterable operations** (discover · import-own · select · narrow · study) over a persisted package. Worth stating that explicitly in the skill's mental model when we spec it.

## Next step
Refinement discussion → `superpowers:brainstorming` on each thrust (state model first), then a spec in `docs/superpowers/specs/`.
