---
title: "artist-study-kit — Wiki Index"
type: wiki/index
tags: [wiki/index, moc]
aliases: ["Wiki MOC", "Wiki Home"]
---

# artist-study-kit — Wiki

The synthesis layer (LLM-Wiki pattern): immutable [[00-artist-study-kit-seed|raw sources]]
distilled into interlinked notes that feed the skill design. Design rationale:
[[10-wiki-synthesis-design|wiki synthesis design]]. Each **stage note** synthesizes the
research for one step of the skill pipeline and ends with skill-design implications; each
**concept note** is an atomic, cross-cutting idea reused by several stages.

## Skill pipeline (stage notes)

The skill's workflow, in order (seed: [[00-artist-study-kit-seed]]):

1. [[stage-background-research]] — who the artist was; biography→style bridge.
2. [[stage-source-grading]] — discover + grade web sources (anti-slop).
3. [[stage-style-definition]] — the artist's visual grammar, up front.
4. [[stage-works-inventory]] — select + rank works (important vs studyable).
5. [[stage-image-discovery]] — high-res candidate images, legally.
6a. [[stage-curation]] — the human visually rates the board → `selection.json`.
6b. [[stage-curation-interview]] — Socratic per-work interview → `study-briefs`.
7. [[stage-visual-analysis]] — deep-read the selected works.
- ⟳ [[stage-study-retention]] — *cross-cutting*: notes, drills, aids, review schedule.

Chronological wiki history: [[log|wiki log]].

## Concepts (cross-cutting)

- [[concept-formal-analysis-taxonomy]] — Notan, Dow's principles, levels, palette; 18-dim / core-12 study sheet.
  → style-definition, visual-analysis, curation-interview.
- [[concept-source-trust-signals]] — lateral reading, rubric, tiers, machine cues.
  → source-grading, background, works.
- [[concept-iiif]] — IIIF + open-access museum APIs, source priority, rights.
  → image-discovery, works.
- [[concept-desirable-difficulty]] — productive friction, Bjork, ZPD, Socratic AI.
  → curation-interview, curation, visual-analysis, study-retention.
- [[concept-spaced-repetition]] — spacing/lag, FSRS, RB/II, interleaving, 500ms.
  → study-retention, visual-analysis.
- [[concept-worked-example-fading]] — job vs learning aids, fading, crutch problem.
  → study-retention, style-definition, visual-analysis, curation-interview.
- [[concept-divergent-convergent-thinking]] — variation→selection, semantic distance, creative ceiling; human owns selection.
  → curation, curation-interview, visual-analysis.

## Raw corpus (immutable sources)

**Domain / tooling:** [[01.1-web-scraping-tooling]] · [[02.1-source-quality-grading]] ·
[[03.1-museum-image-apis]] · [[04.1-style-analysis-frameworks]]
**Pedagogy / learning-science:** [[05.1-master-study-pedagogy]] ·
[[06.1-productive-friction-learning]] · [[07.1-study-aids-scaffolding]] ·
[[08.1-spaced-repetition-retention]]
**Pipeline-stage method:** [[11.1-artist-background-research]] ·
[[12.1-works-inventory-method]] · [[13.1-human-curation-ux]] · [[16.1-image-source-hierarchy]]
**Build-phase feedback & requests:** [[18-uat-feedback]] ·
[[19-stateful-runs-custom-images-staged-analysis]] · [[20-dimensions-of-study-cheat-sheet]]
**Creativity / cognition (meta):** [[21.1-divergent-convergent-strategic-partner-framework]] ·
[[21.2-llm-creativity-vs-human-cognition-benchmark]]

## Source → stage map

| Raw report | Feeds |
|---|---|
| 01.1 web scraping | source-grading, image-discovery |
| 02.1 source grading | source-grading (+ concept) |
| 03.1 museum/image APIs | image-discovery, works (+ concept) |
| 04.1 style analysis | style-definition, visual-analysis (+ concept) |
| 05.1 master-study pedagogy | study-retention |
| 06.1 productive friction | curation, visual-analysis, study-retention (+ concept) |
| 07.1 study aids | study-retention, curation (+ concept) |
| 08.1 spaced repetition | study-retention (+ concept) |
| 11.1 artist background | background-research |
| 12.1 works inventory | works-inventory |
| 13.1 human curation | curation |
| 16.1 image source hierarchy | image-discovery |
| 18 UAT feedback (F6) | curation-interview, curation, image-discovery (+ desirable-difficulty) |
| 19 stateful runs / custom images / funnel | image-discovery, curation, visual-analysis, curation-interview |
| 20 study-dimensions cheat sheet | visual-analysis, curation-interview (+ formal-analysis-taxonomy) |
| 21.1 divergent-convergent protocol | curation, curation-interview, visual-analysis (+ divergent-convergent-thinking) |
| 21.2 LLM-vs-human creativity benchmark | curation, curation-interview (+ divergent-convergent-thinking, desirable-difficulty) |

Every raw report is referenced by at least one wiki note. The skill is now in build/refine
(Phase 3); the wiki tracks UAT findings and feature requests back into the stage notes'
"Open questions / tensions". Chronological history: [[log|wiki log]].
