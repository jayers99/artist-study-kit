# artist-study-kit — TODO

## Setup (be productive)
- [x] NotebookLM access via the `notebooklm-jayers` skill (`/ntlm`) — no repo-level MCP; skill owns the connection.
- [x] Initialize uv project: `pyproject.toml` + `.venv/` (`uv init`).
- [x] Add `CLAUDE.md` and this `TODO.md`.

## notebooklm-jayers skill — build up as we go
- [x] FR1/FR2/FR3 implemented (studio `report` artifacts, `--number NN.M`/`--next --root`, Obsidian frontmatter). 37 pytest-bdd tests pass. Validated live on doc 03.
- [x] Add `--slug <slug>` override to `get report` (implemented; 39 tests pass; used live on doc 04 — no manual rename).

## Research backlog (each → numbered raw/ doc via NotebookLM deep research)
- [x] 01 — Web scraping tooling → `raw/01.1-web-scraping-tooling.md`. **Recommendation: Firecrawl (primary), Crawl4AI (fallback), Scrapy for large image jobs.**
- [x] 02 — Source quality grading rubric → `raw/02.1-source-quality-grading.md`. **Weighted rubric + tiers + machine-detectable signals + high-trust shortlist (Smarthistory, Met, CAA).**
- [x] 03 — Museum / image APIs → `raw/03.1-museum-image-apis.md`. **IIIF guide + per-source assessment; priority Met → Rijksmuseum → AIC → Harvard/Europeana → Wikimedia.**
- [x] 04 — Style-analysis frameworks → `raw/04.1-style-analysis-frameworks.md`. **Layered taxonomy + 5-stage LLM analysis workflow + study drills + reusable template.**

## Research backlog — pedagogy / learning-science cluster (roots 05–08)
- [x] 05 — Master-study pedagogy → `raw/05.1-master-study-pedagogy.md`. **Atelier/Bargue/copyist traditions, critique practices, staged self-learner workflow.**
- [x] 06 — Productive-friction framework → `raw/06.1-productive-friction-learning.md`. **Desirable difficulties + Socratic AI (Khanmigo) + interaction patterns + anti-patterns.**
- [x] 07 — Study aids & scaffolding → `raw/07.1-study-aids-scaffolding.md`. **Job aid vs learning aid, worked-example fading, crutch problem, art-study templates.**
- [x] 08 — Spaced repetition & retention → `raw/08.1-spaced-repetition-retention.md`. **SRS/interleaving/perceptual+procedural practice, review system, SRS limits.**

## Research backlog — pipeline-stage gaps (roots 11–13, surfaced by wiki design)
- [x] 11 — Artist background research method → `raw/11.1-artist-background-research.md`. **Biographical synthesis + art-historical placement; report template + source priority + biography→style bridge.**
- [x] 12 — Important-works inventory method → `raw/12.1-works-inventory-method.md`. **Canon-selection rubric, important-vs-studyable, ranking/clustering, per-work metadata schema.**
- [x] 13 — Human-curation UX → `raw/13.1-human-curation-ux.md`. **Cull/rate/compare triage, choice architecture, what-to-show-per-candidate, study selection heuristics.**

## Phase 2 — wiki synthesis
- [x] Wiki design spec → `raw/10-wiki-synthesis-design.md` (pipeline-oriented hybrid; 8 stage + 6 concept + index).
- [x] Build the `wiki/` notes per the design — 15 notes (8 stage + 6 concept + `00-index`); link/coverage verified. Entry point: `wiki/00-index.md`.

## Phase 3 — skill build/refine (current)
Skill built and live-validated; build-phase research + feedback ingested back into `wiki/`
(now 9 stage + 7 concept notes). Specs/plans in `docs/superpowers/`.
- [x] 16 — Image source hierarchy research → `raw/16.1-image-source-hierarchy.md`. **Tiered T1 Wikidata identity → T2 Met/AIC/Cleveland high-res+rights → T3 Commons/Europeana → T4 discovery-only; QID as dedup key.**
- [x] Draft the skill design/spec from the wiki → `docs/superpowers/specs/2026-06-19-artist-study-kit-skill-design.md` (+ foundation / research-tooling / curation-study plans).
- [x] Build the skill: `skill/SKILL.md` + ~24 `skill/scripts/` modules (scraping, image discovery, curation, analysis, retention). Tests in `tests/`.
- [x] UAT (`raw/18`) → Socratic curation-interview stage → `docs/superpowers/specs/2026-06-20-socratic-curation-interview-design.md`.
- [x] `raw/19` Thrust 1 — stateful/resumable package state (`state.json`, mergeable discovery, repeatable sessions).
- [x] `raw/19` Thrust 2 — custom-image injection (`origin:"user"`, Claude-vision → pipeline verify, batch trust gate).
- [x] `raw/19` Thrust 3 Spec A — persistent board stars (stars ⊥ selection, thumbnail cache, filter/sort).
- [x] `raw/19` Thrust 3 Spec B — narrowing funnel + skip-discovery (≤4 `study_set`, progressive zoom, `display_url` 843px).
- [x] Ingest study-dimensions (`raw/20`) + divergent/convergent cognition (`raw/21`) into the wiki.
- [x] Live e2e validation — funnel pipeline on Monet (0 skill bugs) + first full run on Klee. Harnesses in `e2e/`.

## Open / next
- [ ] **Duplicate handling on re-query/ingest.** As the gallery grows across discovery runs + custom-image imports, define what happens when a newly-found image is (or may be) a duplicate of one already on the board — so a starred work isn't re-added unstarred. Deferred out of Thrust 3; needs its own spec. (Context: `raw/19` Thrust 3 stateful-stars revision.)
