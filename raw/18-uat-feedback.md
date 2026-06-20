---
type: raw/uat-feedback
title: "UAT feedback — refinement iteration backlog"
status: living
opened: 2026-06-20
artist-under-test: "Paul Klee"
tags:
  - "#uat"
  - "#artist/paul-klee"
---

# UAT feedback — next refinement iteration

Living backlog from hands-on runs of the artist-study-kit skill. Each finding: what happened, evidence, and a proposed refinement. Builds on the first e2e run's findings (see memory `e2e-test-paul-klee`). Append freely; triage into specs/plans later.

**Run under test:** second full fresh run on **Paul Klee**, 2026-06-20 (post Wikidata Tier-1 image-discovery merge). Stages 1–5 executed; blocked partway through curation (Human Pause 1 → gate filling).

---

## F1 — WDQS is a hard single-point-of-failure for image discovery · **severity: high**

**What happened.** The new Wikidata-primary board could not be built. The Wikidata Query Service was in an active outage: first `429 — aggressively rate-limiting to 1 req/min (active wdqs outage)`, then a *partial* recovery where a trivial entity-label query returned `200` but the real `qid_lookup_sparql` aggregation query `504`'d after 65s. Net: the headline feature was unusable for the whole session; we fell back to an AIC-only board (the pre-feature behavior).

**Evidence.** `429` on all paced retries (≥65s spacing); later `HTTP_CODE=504 TIME=65.3s` probing the qid-lookup query directly; healthy `200` on `SELECT ?l WHERE { wd:Q44007 rdfs:label ?l }`.

**Proposed refinements.**
- **Lighter QID resolution.** `qid_lookup_sparql` scans `rdfs:label|skos:altLabel` with a `FILTER(LCASE(...))` *and* `COUNT(DISTINCT ?w)` work-aggregation across every human of that name — expensive, and the first thing to 504 on a degraded service. Resolve QID via the entity-search API (`wbsearchentities` / `wikibase:mwapi` EntitySearch) instead; only run the work-count tiebreak when there's genuine ambiguity.
- **First-class degraded path.** Make AIC-only (or cached) a *designed* fallback with a clear board banner ("Wikidata unavailable — partial board"), not a crash/empty result. The skill should detect WDQS failure and proceed, marking the stage `degraded` in state so a later re-run can upgrade.
- **Resilience knobs.** Built-in retry/backoff + a configurable timeout in `default_sparql` (currently fixed 60s); optional on-disk cache of resolved QID + works so a WDQS blip doesn't redo discovery.
- **Docs.** SKILL.md should name the exact `StudyPaths` attributes for stage-5 outputs (`sp.gallery_html`, `sp.root`) — an ad-hoc helper here crashed on a non-existent `sp.study_dir`.

## F2 — selection.json export drops title/date/medium · **severity: high**

**What happened.** Exported `selection.json` entries carry only `work_id` (slug), `stars`, `rights`, `museum`, `source_url`. `title` and `date` are `None`. Gate-filling and every downstream stage are title-blind; titles had to be re-fetched from AIC by object id.

**Evidence.** All 5 ungated entries printed `title: None`, `date: None`; real titles recovered only via `api.artic.edu/artworks/<id>`.

**Proposed refinement.** The gallery export JS (`_THUMB_TEMPLATE` / payload) must serialize `title`, `date`, and ideally `medium` into `selection.json`. `Rating`/`parse_selection` should round-trip them. Downstream stages should never need a second network fetch to learn what a selected work is.

## F3 — attribution guard lets reproductions / posthumous "after" works through · **severity: high**

**What happened.** `der-paukenspieler-the-drummer-boy` (AIC 39193) is a **1972 woven textile produced by Montgomery Ward "after a painting by Paul Klee"** — made 32 years after Klee died, not an original. It reached the board (and got a 4★) because its `artist_display` contains "Paul Klee". The surname guard / agent-id search does not catch "After …" / "Produced by …" / posthumous reproductions.

**Evidence.** AIC 39193 `artist_display: "After a painting by Paul Klee … Produced by Montgomery Ward …"`, `date_display: 1972`, `classification: textile`.

**Proposed refinement.** Filter or flag candidates whose `artist_display` matches `after|produced by|manner of|copy after|workshop of`, or whose `date_display` year exceeds (death year + small margin), or whose classification indicates reproduction. At minimum surface a "⚠ not an original / posthumous" badge on the board so the human isn't asked to study a Montgomery Ward tapestry.

## F4 — curatorial gate is opaque to the user · **severity: medium**

**What happened.** User: *"i wasn't sure what i was supposed to put in there."* The gate fields (thesis / anchor trait / handoff note) have no in-UI explanation, so a non-expert leaves them blank and only discovers the requirement at export-time validation.

**Proposed refinement.** Add inline help / placeholder examples in the gallery gate UI for each field (one-line definition + a worked example). Consider a "needs gate" badge on liked works and a pre-export checklist so the human fixes it in-place rather than bouncing off `validate_selection` after export. Definitions to reuse: thesis = *why this work earns a slot*; anchor trait = *the one visual thing you'll study* (from the grammar); handoff note = *a reminder to future-you at the easel*.

## F5 — Klee board is 100% in-copyright; Phase B has nothing to resolve · **severity: medium (artist-specific, known)**

**What happened.** All 97 AIC candidates flagged `in_copyright`; 0 QIDs (Wikidata down); 0 downloadable high-res for Phase B. Expected for Klee (d. 1940) but means this artist exercises the resolver chain only on its "keep source_url as reference" branch.

**Proposed refinement.** Mostly a coverage note: the Wikidata/Commons path is the only realistic source of the handful of PD pre-1923 Klee graphics, which reinforces F1 (WDQS resilience matters most exactly for in-copyright-heavy artists). Consider a board notice when a run yields zero PD/CC0 candidates, setting expectations that analysis will lean on graded sources + reference links, not redistributed images.

## F6 — split rating from rationale: replace gate text fields with a Socratic AI interview · **severity: high (design direction)**

**Supersedes F4.** F4 treated the opaque gate as a UI copy problem; the real fix is structural — the three rationale fields don't belong in the visual selection phase at all.

**Direction.**
- **Strip the three text fields (thesis / anchor trait / handoff note) out of the gallery web UI.** The selection phase should be purely visual and fast: look at images, star-rate, filter. Generating `selection.json` ends that phase. (The three attributes are still the right things to capture — just not here, and not by typing into a form.)
- **Add a new interactive stage after `selection.json`: a Socratic, AI-led interview, one image at a time.** The AI walks the human through each liked work and *draws out* the thesis, anchor trait, and handoff note through questioning — rather than handing them over or asking for blank-field input. The guidance style we used live in this run (propose a candidate reading, invite push-back, refine together) is the right tone — but it must keep **productive friction**: the human does the thinking, the AI scaffolds. (Ties to [[concept-desirable-difficulty]] and the productive-friction research `[[06.1-...]]`.)
- **Context per image — keep it lightweight (revised after dry-run).** The AI presents, inline in the chat: a **link to the source image** plus title, year, and whatever metadata is available (medium, collection, dimensions). The human opens the link themselves. **No browser automation / Playwright needed** — a plain source link worked well in the dry-run and avoids the cost and fragility of driving a headless browser. Pull metadata from Wikidata primarily (museum source as fallback).
- **Surface series / period / grouping.** Tell the human whether the work sits in a recognizable **series, period, or logical grouping** for that artist (e.g. Klee's Tunisia watercolours, the magic-square works, the late glyph period). This context makes the thesis-building richer and helps the human see a work as part of a study route, not in isolation. Source from Wikidata (series/movement/inception) + the works-inventory clusters.
- **Intelligent ordering of the interview.** Don't walk the images in arbitrary/export order. Sequence them with some intelligence — e.g. by period/series, by studyability, or general→specific — so the interview builds a coherent narrative and earlier images inform later theses.
- **Bake in the master-study research.** The interview's questions should operationalize the deep-research findings on *what makes a good master study* and *how to leverage the learning* (`[[05.1-...]]` master-study pedagogy, study-aids/scaffolding). Each image's questions should push toward: what specific, transferable lesson does copying this teach, and how will it be practiced.

**Net effect.** Curation becomes two cleanly-separated steps: (1) fast visual rating in the browser → `selection.json`; (2) a friction-bearing Socratic interview that produces the per-work rationale (thesis/anchor/handoff) *and* does real learning in the process. This also resolves F2 (titles/dates must be present) and F4 (no more opaque blank form), and leans on F1's Wikidata metadata being available.

**Output is richer than three flat strings (learned from the Women Harvesting dry-run).** The interview's `handoff` naturally came out as a *multi-stage study protocol with a success test* (monochrome line → add grays → add color chords; "trace your eye-path to verify"), not a one-line note. The data model for the interview output should support: `thesis` (prose), `anchor_trait` (short), and `handoff` as a **structured study plan** — an ordered list of study steps, each with an optional success/verification test — rather than a single string. This dovetails with the worked-example-fading and master-study research (progressive complexity is exactly the recommended structure).

**Dry-run validated the core mechanic.** In the live test the human extracted the transferable rule and designed the study progression entirely through questioning — the AI only reflected and pressure-tested, never stated the lesson. Keep that contract explicit in the spec: the AI proposes *questions and sharpened restatements*, never the answer.

---

## Curation walkthrough decisions (this run)

Logging the gate answers as we settle them, so they double as worked examples for F4.

- `der-paukenspieler-the-drummer-boy` — **dropped (user confirmed)**: 1972 Montgomery Ward textile reproduction "after a painting by Paul Klee," not a Klee original (F3). Demonstrates the need for the attribution/reproduction filter.
- `women-harvesting` (1937) — **gated (Socratic dry-run, confirmed).**
  - **Thesis:** a study in *contour-as-rhythm* — Klee's three-state line grammar (straight / curved / **absent**) steering the eye around a 2-D field, over figures hinted so economically that "finding them" is what holds the viewer; the lesson (how line presence, weight, and shape control the gaze) isolates cleanly from color.
  - **Anchor trait:** the three-state contour — straight lines wall the edges, curves circulate the center, absence dissolves the figure — deployed for rhythmic, looping eye-movement.
  - **Handoff note (a study protocol, not a one-liner):** run as a 3-stage faded series — (1) monochrome, line only: straight/curved/absent contours, generate the rhythm, *test by tracing your own eye-path — does it loop and resist leaving the frame?*; (2) add ~4 grays; (3) add the color chords last (close-valued greens + warm gold/tan negative space). Success = the eye circulates and figures stay findable-but-withheld, not a pretty copy.
  - **Process note:** the human extracted the lesson and *designed the study* through questioning alone — the AI never stated the lesson. Validates the F6 Socratic approach.
- `exotics` (1939) — **gated (Socratic dry-run, confirmed).**
  - **Thesis:** a study in *facial/figural economy as the emotional and narrative dial* — Klee controls both feeling and how much story the viewer projects purely by what he includes and omits in a face (angular vs. soft line, eyes vs. no eyes, hand detail vs. none). The viewer reads a whole narrative out of *which features were withheld*.
  - **Anchor trait:** economy of facial information — angular face as tension, eyeless figure as watchful blankness; meaning set by omission.
  - **Handoff note (study protocol, exploits the study→final pair):** (1) copy the ink study *Sales Woman* — his linear skeleton + angular faces + omissions as first set; (2) copy the oil *Exotics* — note what changed committing to paint, did faces simplify further?; (3) variation drill: one figure, run a facial-economy ladder (full features → angular only → eyes omitted). *Success test: make the same figure read warm / tense / uneasy by changing only facial information.*
  - **Process note (F6 design):** the human drifted hard into iconography/narrative ("is this a brothel?") — the *appreciation reflex*. The redirect that worked was to seize the human's **own formal observation** ("he didn't put eyes on that figure") and use it as the bridge back to a practiceable rule. The interview needs an explicit **"redirect from narrative to technique"** move, and reflecting the human's own technical noticings back is the gentlest version of it.
- `the-sales-woman-in-the-open-study-for-exotic` (1938) — **folded into `exotics`** as the prep-drawing step of its study protocol (it is literally Klee's study *for* Exotic). Not gated separately. **Process note (F6 design):** the grouping intelligence should detect "study for X" / study→final relationships and offer to merge them into one study target rather than treating them as independent picks.
- `mosaic-like` (1932) — **gated (Socratic dry-run, confirmed).**
  - **Thesis:** a study in *micro/macro eye oscillation via opposed geometries* — an angular *knot* of intersections pulls the eye into deep focus while a rounded, flowing fountain/whirlpool S-curve pulls it back out to travel; the opposition between the two is the engine that makes the gaze cycle between close-reading and overview.
  - **Anchor trait:** opposed geometries — angular/knotted (deep focus) set against rounded/flowing (macro travel), with the single line that turns back under itself to support the belly of the S-curve as the one structural exception.
  - **Handoff note (study protocol):** (1) line-only: compose one flowing rounded form opposed to one angular knot of intersections; tune until the knot grabs deep focus and the curve carries travel; (2) *test: trace your eye-path (or a second viewer's) — does it both lock into the knot AND circulate the curve? If only one, the opposition isn't tuned*; (3) add the divisionist/mosaic ground to see how the substrate supports the two figures.
  - **Process note (F6 design — important):** the AI mis-framed this work as "color-grid / magic-square" from title + year **without seeing it**; the human's observation revealed flowing line forms instead. Risk: metadata-based pre-framing can steer the human wrong. Rule for the spec: *the AI must not assert what a picture looks like from metadata alone — present neutral facts (title/year/medium/series) and let the human's observation lead the visual reading.*

**Process learnings across the dry-run (for the F6 spec):**
- The "turn analysis into a study + success test" question is the reliable convergence move — it forced a practiceable lesson out of every image.
- Each confirmed lesson should be checked for **non-overlap** with the set so far (contour-rhythm / facial-economy / opposed-geometries were deliberately kept distinct) — the interview should track the running set and steer toward coverage, not redundancy.
- A light **observation → hypothesize-the-rule → commit + design-the-drill → confirm** arc worked as the per-image script.
