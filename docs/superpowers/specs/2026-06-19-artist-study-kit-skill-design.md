# artist-study-kit skill — Design Spec

**Date:** 2026-06-19
**Status:** Approved (brainstorming) → ready for implementation plan
**Scope:** v1 = full pipeline, thin (all stages present, each at MVP depth; one artist end-to-end)
**Source of truth for design rationale:** `wiki/00-index.md` + the eight stage notes; output
contract from `raw/00-artist-study-kit-seed.md`.

---

## 1. Purpose

A Claude skill that takes a historical artist's name and produces a structured **studio-prep
study package**: background, graded web sources, the artist's visual grammar, a ranked works
inventory, high-res candidate images, a human curation step, a preference-synthesis step that
finds patterns in what the human liked, a funnel to a small study set, deep visual analysis of
that set, and study/retention artifacts.

The goal is to convert art-historical research into **usable studio preparation**, keeping the
human in control of taste-driven decisions.

Design principles (from the seed): research-grounded, anti-slop, studio-oriented,
human-curated, reproducible, extensible, agentic.

## 2. Pipeline overview

Eight stages across three runs, separated by two human-in-the-loop pauses. The skill is
**resumable and idempotent**, tracking progress in `state.json`.

```
RUN A — automated research
  1. Background research        → report.md (background section)
  2. Source discovery + grading → sources/sources.json, sources/source-grades.md
  3. Style definition           → report.md (visual-grammar section) + style cheat sheet
  4. Works inventory            → works.md (ranked + clustered, dual-axis)
  5. Image discovery            → images/candidates/<work>/ + per-image metadata
                                  + gallery.html
  ──► STOP. Human opens gallery.html.

  [HUMAN PAUSE 1 — curation]
  Star-rate candidates in detail view (auto-advance). For works rated ≥4★, fill the
  curatorial-gate fields (thesis / anchor trait / handoff note). Export selection.json.

RUN B — synthesis + funnel
  6. Preference synthesis       → preference-synthesis.md (patterns/connections across the
                                  liked set: period clustering, recurring formal traits,
                                  subject matter, palette gravitation) + ranked study-set
                                  candidates (pattern-fit + studyability score per work)
  ──► STOP.

  [HUMAN PAUSE 2 — funnel]
  Human picks the final small study set from the ranked list.

RUN C — study
  7. Deep visual analysis       → analysis.md (study set only)
  8. Study & retention          → study-notes.md, drills/, review-schedule.md
```

Re-invoking the skill reads `state.json` and resumes at the next incomplete stage.

## 3. Architecture

A **single orchestrator skill** (`SKILL.md`) drives Claude through the stages
conversationally, calling **deterministic Python scripts** for mechanical/IO work and doing
the **art-historical judgment work itself**.

### 3.1 LLM ↔ script boundary

| Python `scripts/` (deterministic, TDD'd) | Claude in `SKILL.md` (judgment) |
|---|---|
| Firecrawl `/map` + `/scrape` → markdown | Background synthesis + biography→style bridge |
| Source **signal-scan** (commerce strings, ad/img density, TLD nuance, citation tags) → tier guess | Source **rubric scoring** (close-looking) on borderline / high-value pages |
| IIIF discovery + license check + `max` fetch/download; Scrapy for bulk | Style definition; works ranking (dual-axis); preference synthesis |
| Generate `gallery.html`; ingest/validate `selection.json` | Funnel ranking rationale; visual analysis; study notes/drills |

Rationale: scripts do the cheap, repeatable, rights-sensitive I/O; Claude does the
art-historical reasoning. Matches the two-pass grader (`stage-source-grading`) and the IIIF
pipeline (`stage-image-discovery`).

### 3.2 Packaging

- Develop in-repo under `skill/` = `SKILL.md` + `scripts/` (+ gallery template/assets).
- Symlinkable/installable to `~/.claude/skills/` later; confirm exact layout in the plan.
- Python managed with **uv**; venv outside iCloud at `~/.venvs/artist-study-kit` (per
  CLAUDE.md). Web scraping standardized on **Firecrawl** (`firecrawl-py`), Crawl4AI fallback,
  Scrapy for large image-download jobs.

## 4. Stage detail

Each stage's full rationale and evidence live in the linked wiki note; the "Skill design
implications" section of each is the spec input. MVP depth = the simplest implementation that
honors the implication, deferring deeper rubric/artifact fidelity to later specs.

### Stage 1 — Background research (`wiki/stage-background-research.md`)
Emit a background section: training/lineage, geography & movement, periods, patrons/economics,
art-historical placement, why they matter, curated graded resources. Run an explicit
**biography→style checklist** (workshop continuity, material dating, legal/autograph status,
handedness, functional design) so output *hands signal* to Stage 3. Prefer technical/primary
sources; flag aesthetic-only critique as low-confidence. Degrade gracefully to museum essays +
monographs when conservation data is thin.

### Stage 2 — Source discovery + grading (`wiki/stage-source-grading.md`)
**Two-pass grader:** (1) cheap machine-signal scan on fetched markdown → tier guess; (2) LLM
rubric scoring (authority 30 / depth 25 / commercial-bias 20 / citations 15 / usability 10) on
borderline/high-value pages → 1–100 score + tier + rationale. Emit `source-grades.md`
(per-source score, tier, triggering signals, "use for X / avoid for Y" note — esp. auction =
facts-only). Persist `sources.json` (url, tier, score, signals, fetch metadata) so other stages
filter by trust. Seed domains: Smarthistory, Met, CAA. Fetch via Firecrawl.

### Stage 3 — Style definition (`wiki/stage-style-definition.md`)
Apply the formal-analysis taxonomy at the **artist** level. Emit a **style cheat sheet**:
chunked "structural DNA" across the taxonomy's four levels, in the artist's terms. Express
grammar as **testable traits** ("warm high-chroma lights, muted cool shadows"; "edges lost on
the shadow side") so Stage 7 can confirm/deny per work and Stage 8 can build discrimination
cards. Note period variation when sources support it. Drafted from sources now; refined after
images land.

### Stage 4 — Works inventory (`wiki/stage-works-inventory.md`)
**Per-work metadata schema:** title, date, medium, dimensions, collection, primary technical
lesson, difficulty tier (1–4), reference-quality/availability, early-vs-late development tag,
source page(s). Score each work on **two axes** — art-historical importance AND studyability
(don't collapse them). Output a **clustered, ranked** list that reads as a study progression
(general→specific). Authority hierarchy: catalogues raisonnés → museum catalogues → historical
documentation. Ranking criteria must generalize beyond 19th-c. French academic realism.

### Stage 5 — Image discovery (`wiki/stage-image-discovery.md`)
Per work: identity-resolve (search API) → validate metadata + license → fetch via IIIF `max`,
falling back to direct high-res links. Source priority: Met → Rijksmuseum → AIC →
Harvard/Europeana → Wikimedia. Capture per-image metadata: source URL, institution, license,
pixel dimensions, IIIF identifier, trust grade, parent work id. Rights: prioritize
CC0/public-domain; treat missing rights as restricted. Respect robots.txt + throttle. Organize
`images/candidates/<work>/`; never auto-select.

### Stage 6 — Preference synthesis *(new — extends `wiki/stage-curation.md`)*
After curation, analyze the **liked set as a whole** for connections and generalizations:
period clustering, recurring composition/value/edge traits, subject matter, palette
gravitation — cross-referencing the Stage 3 artist grammar and Stage 4 clusters. Emit
`preference-synthesis.md`: a "what you're drawn to" insight note (itself a study artifact /
metacognition aid) **plus** a ranked list of study-set candidates, each scored on **pattern-fit
+ studyability** with a one-line rationale. This drives the funnel.

### Stage 7 — Deep visual analysis (`wiki/stage-visual-analysis.md`)
On the funnel-selected study set only. Run the formal-analysis **5-stage instruction set**:
(1) structural skeleton (Dow), (2) Notan mapping, (3) palette archaeology, (4) technical
layering hypothesis, (5) traps & misconceptions. Emit per-work `analysis.md` from the reusable
template + a technique-imitation checklist (job aid). Cross-check each work against the
artist-level grammar (confirmations + surprises). Include a **predict-then-reveal** variant to
preserve productive struggle. Gate analysis depth on the reference quality recorded in Stage 5
(don't hallucinate technique from low-res).

### Stage 8 — Study & retention (`wiki/stage-study-retention.md`)
Emit `study-notes.md` per work (notice-first / decisions-to-imitate / traps / exercises),
structured as **faded aids** (cheat sheet → checklist → bare prompt). Generate artifacts:
style-discrimination card sets (A-vs-not-A), spaced study-passage/Woodpecker drills, gapped
worksheets, FSRS-importable declarative decks. Emit a **review schedule** (spaced + interleaved
across works/styles). Position any AI critique as a Socratic tutor (answer-withholding +
help-abuse guardrails); keep production in the human's hand.

## 5. The curation gallery (Human Pause 1)

`gallery.html` — a standalone static HTML+JS contact sheet the human opens in a browser.

- **Thumbnail grid view** — all candidates, grouped by work, with inline decision metadata
  (Elements of Art + medium / source / resolution / trust grade).
- **Detail view** — click a thumbnail to drill in: large image, a **5-star control**; rating a
  work **auto-advances** to the next candidate. A **back button** returns to the grid.
- **Curatorial gate** — when a work is rated **≥4★**, the detail view reveals text fields:
  `thesis` (why study this), `anchor trait` (the trait to study), `handoff note`. This is the
  productive-friction sense-making pause from `wiki/stage-curation.md`.
- **Export** — writes `selection.json` (per-candidate rating + gate text) that Run B ingests.
  Liked set (≥4★) also copied/linked into `images/selected/`.

MVP gallery is generated by a Python script from the candidate metadata; richer survey
affordances (overlay markup, compare view) are deferred.

## 6. Output contract — `studies/<artist>/`

```
report.md                  background + visual-grammar (style cheat sheet)
sources/
  sources.json             structured: url, tier, score, signals, fetch metadata
  source-grades.md         human-readable grades + use/avoid notes
works.md                   ranked + clustered inventory (importance + studyability axes)
images/
  candidates/<work>/       downloaded high-res + per-image metadata
  selected/                liked set (≥4★)
gallery.html               star / detail / curatorial-gate UI
selection.json             ratings + gate text (human output of Pause 1)
preference-synthesis.md    patterns across liked set + ranked study-set candidates
analysis.md                deep visual analysis (study set only)
study-notes.md             notice-first / imitate / traps / exercises (faded aids)
drills/                    discrimination cards, Woodpecker/gapped worksheets, FSRS decks
review-schedule.md         spaced + interleaved schedule
prompts/                   reusable research/critique prompts
state.json                 pipeline progress (resumable, idempotent)
```

Markdown outputs are Obsidian-native: `[[wikilinks]]` (artist ↔ works ↔ movements ↔
techniques), YAML frontmatter, tag taxonomy (`#artist/`, `#movement/`, `#technique/`,
`#source-grade/`), study callouts (`> [!tip]`, `> [!warning]`, `> [!example]`).

## 7. State & resume

`state.json` records which stages are complete and key artifacts produced. Re-invoking the
skill:
1. Reads `state.json`; finds the next incomplete stage.
2. If blocked on a human pause (selection.json missing, or study set not yet picked), prints
   clear instructions and stops.
3. Otherwise resumes the pipeline. Stages are idempotent — re-running overwrites their own
   outputs without corrupting prior stages.

## 8. Testing

Per CLAUDE.md (outside-in TDD, pytest-bdd, uv):

- **Python scripts** get Gherkin acceptance specs + TDD: source signal-scan scoring, IIIF
  license/resolution validation, image fetch/dedup, `gallery.html` generation,
  `selection.json` round-trip (parse + validation), `state.json` transitions.
- **SKILL.md judgment stages** are specified as prompt instructions with example-based
  expectations (golden-ish exemplars), not unit tests.
- Network-dependent scripts (Firecrawl, museum APIs) tested against recorded fixtures, not
  live endpoints.

## 9. Out of scope for v1 (deferred to later specs)

- Deep-fidelity rubrics/artifacts (full FSRS deck generation, gapped-worksheet generators).
- Multi-artist comparison; non-Western/contemporary API coverage gaps.
- Richer gallery (overlay markup, side-by-side compare, in-browser funnel pick).
- Automatic palette extraction, composition thumbnails/diagrams, OCR.
- LLM-as-judge evaluation of source quality / analysis depth.

## 10. Open questions to resolve in planning

- Exact `skill/` directory layout and install/symlink mechanism.
- Target size of the study set (default ~3–5) and shortlist cap (~8–10) — make configurable.
- Whether Run B's ranked funnel pick stays markdown-checklist or grows into a second
  gallery view (kept markdown for v1).
- Firecrawl API key handling / rate-limit config surface.
