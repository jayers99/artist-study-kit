---
title: "Wiki Synthesis Layer — Design"
type: design
created: 2026-06-19
tags: [phase/2, wiki, design, synthesis]
---

# Wiki Synthesis Layer — Design

Design for standing up the `wiki/` layer of **artist-study-kit**. This is the LLM-Wiki
synthesis step (Karpathy pattern): immutable [[00-artist-study-kit-seed|raw sources]] →
an LLM-maintained **wiki** → a **schema** (`CLAUDE.md`). Phase 1 populated `raw/` with 8
deep-research reports; this layer distills them into interlinked Obsidian notes that feed
the eventual skill design/spec.

## Goal

Turn the 8-report `raw/` corpus into a navigable, cross-linked knowledge base organized
around the **skill's eventual pipeline**, where each note both synthesizes the research and
states **concrete implications for the skill design**. The wiki is the bridge between
"what the research says" and "what the skill should do."

## Non-goals

- Not the skill spec itself. The wiki feeds a later skill design; it does not replace it.
- Not editing `raw/`. Raw stays immutable and append-only; the wiki links *back* to it.
- Not exhaustive concept extraction. Start lean; promote a concept to its own note only
  when a third stage references it (the "collect 3 before abstracting" rule).

## Architecture — three note types

A new `wiki/` directory, fully Obsidian-native. Three kinds of notes:

1. **Index / MOC** — `00-index.md`. A map-of-content hub linking every note, grouped by
   skill pipeline and by concept cluster. The entry point for the vault graph.
2. **Stage notes** — one per skill-pipeline stage. Synthesize the relevant raw reports and
   end with design implications. Frontmatter declares the backing sources so research gaps
   are visible.
3. **Concept notes** — atomic, reusable ideas referenced by 2+ stages. The cross-cutting
   vocabulary (formal-analysis taxonomy, IIIF, desirable difficulty, etc.).

Every wiki note links back to its immutable `raw/` sources via `[[NN.1-slug]]`. The wiki is
the only layer that carries `[[wikilinks]]` between synthesis notes; `raw/` is never edited
to add links.

## Stage note template

```markdown
---
title: "<Stage> — <one-line role in the pipeline>"
type: wiki/stage
stage: <seed-step-number or "cross-cutting">
sources: [04.1-style-analysis-frameworks]   # [] means research gap (seed only)
tags: [wiki/stage, ...]
aliases: []
---

# <Stage>

> [!info] Pipeline role
> One sentence: what this stage does in the skill, and what it emits.

## What the research says
Distilled synthesis with inline links to [[NN.1-slug]] raw reports and [[concept-*]] notes.

## Open questions / tensions
Unresolved trade-offs the skill design must decide (e.g. auction pages: provenance vs bias).

## Skill design implications
- Concrete recommendations: inputs, outputs (which `studies/<artist>/` files it writes),
  heuristics, and human-in-the-loop touchpoints for this stage.
```

A stage note with `sources: []` is an honest **research gap** — it rests on the seed alone,
and its "Skill design implications" section flags what future research (a new `raw/` root)
would strengthen it.

## Concept note template

```markdown
---
title: "<Concept>"
type: wiki/concept
sources: [04.1-style-analysis-frameworks]
used-by: [stage-style-definition, stage-visual-analysis]
tags: [wiki/concept, technique/<x>, ...]
aliases: ["Notan", ...]
---

# <Concept>

Tight definition, the mechanics, and why it matters for artist study. Links back to the
raw report(s) it came from and the stages that consume it.
```

## Note inventory (15 notes)

### Index
- `00-index.md` — MOC.

### Stage notes (8) — mapped to the seed's 7-step workflow + cross-cutting pedagogy

| Note | Skill stage (seed) | `sources:` |
|------|--------------------|-----------|
| `stage-background-research.md` | 1. Artist background | `[]` gap — seed only |
| `stage-source-grading.md` | 2. Source discovery & grading | `02.1`, `01.1` |
| `stage-style-definition.md` | 3. Style definition (grammar up front) | `04.1` |
| `stage-works-inventory.md` | 4. Important works | `03.1` (metadata); seed |
| `stage-image-discovery.md` | 5. Image discovery & collection | `01.1`, `03.1` |
| `stage-curation.md` | 6. Human curation | `06.1`; seed |
| `stage-visual-analysis.md` | 7. Deep visual analysis of selected works | `04.1` |
| `stage-study-retention.md` | cross-cutting: study notes, drills, schedule | `05.1`, `06.1`, `07.1`, `08.1` |

`04.1` feeds two stages: **style-definition** (recognizing the artist's visual grammar
before studying) and **visual-analysis** (deep-reading the curated shortlist). Distinct
jobs, same source.

### Concept notes (6) — each referenced by 2+ stages

| Note | From | Used by |
|------|------|---------|
| `concept-formal-analysis-taxonomy.md` — Notan, Dow's principles, layered Levels | `04.1` | style-definition, visual-analysis |
| `concept-source-trust-signals.md` — machine-detectable quality/slop signals + tiers | `02.1` | source-grading, background, works |
| `concept-iiif.md` — IIIF + open-access museum APIs, priority order | `03.1` | image-discovery, works |
| `concept-desirable-difficulty.md` — productive friction, Socratic scaffolding | `06.1` | curation, visual-analysis, study-retention |
| `concept-spaced-repetition.md` — SRS/interleaving/perceptual+procedural practice | `08.1` | study-retention |
| `concept-worked-example-fading.md` — job-aid vs learning-aid, fading, crutch problem | `07.1` | study-retention, curation |

## Conventions

Follow the repo's existing Obsidian conventions (CLAUDE.md "Markdown / Obsidian"):

- **Filenames:** kebab-case, no `: / # ^ | [ ]`. Stage notes `stage-<slug>.md`; concept
  notes `concept-<slug>.md`; index `00-index.md`.
- **Frontmatter:** `title`, `type` (`wiki/stage` | `wiki/concept` | `wiki/index`),
  `sources`, `tags`, `aliases`; stage notes add `stage`, concept notes add `used-by`.
- **Wikilinks:** `[[NN.1-slug]]` to raw; `[[stage-*]]` / `[[concept-*]]` between wiki notes;
  `[[NN-slug|Readable Title]]` when a filename is ugly.
- **Tag taxonomy:** `#wiki/stage`, `#wiki/concept`, plus domain tags `#technique/<x>`,
  `#source-grade/<a-f>` where relevant.
- **Callouts:** `> [!info]` for pipeline role, `> [!tip]` / `> [!warning]` (traps) /
  `> [!example]` in synthesis where they aid a future studio reader.

## Build order

1. `wiki/00-index.md` skeleton (section headings + placeholder links).
2. Research-backed stage notes first: `stage-source-grading`, `stage-style-definition`,
   `stage-image-discovery`, `stage-visual-analysis`, `stage-study-retention`.
3. Gap/thin stage notes: `stage-background-research`, `stage-works-inventory`,
   `stage-curation`.
4. The 6 concept notes.
5. Wire all cross-links; fill in the index.
6. Update `CLAUDE.md` schema: replace "wiki deferred" language with a `wiki/` conventions
   section describing the three note types and their templates.
7. Update `TODO.md`: check off "stand up wiki/"; note the surfaced research gaps as
   candidate Phase-2 research roots (11+).

## Verification

This is knowledge work, not code — verification is link/coverage integrity:

- **Link integrity:** no dangling `[[wikilinks]]` except intentional gap stubs.
- **Source coverage:** every `raw/NN.1` report is referenced by ≥1 wiki note.
- **Graph reachability:** every note is reachable from `00-index.md`.
- **Obsidian-opens-clean:** frontmatter parses; filenames are vault-safe.

A lightweight check: `grep` for `[[...]]` targets and confirm each resolves to a file in
`wiki/` or `raw/` (or is a known gap stub). No test framework needed.

## Surfaced research gaps (output of this layer)

The three `sources: []` / thin stages name where the skill currently rests on the seed
alone — candidates for future `raw/` research roots:

- Artist background research method (biographical synthesis, art-historical placement).
- Important-works inventory method (canon selection, catalogue raisonné use).
- Human-curation UX (how to present a candidate gallery; selection heuristics).
