---
title: "Phase 1 — Research (Session Memory)"
type: session-summary
created: 2026-06-19
tags: [phase/1, research, handoff]
---

# Phase 1 — Research (Session Memory)

A handoff summary of the first working session on **artist-study-kit**. Phase 1 set up
the project's working method and produced the initial research corpus that later phases
(synthesis → skill design → build) will draw on.

## Project goal (recap)

artist-study-kit's deliverable is a **Claude skill**: given a historical artist's name,
produce a structured studio-prep study package (background, source grading, important
works, image discovery, human curation, deep visual analysis, study notes). Full vision:
[[00-artist-study-kit-seed]].

## What Phase 1 accomplished

1. **Established the working method** (LLM-Wiki, raw layer only) and conventions in `CLAUDE.md`.
2. **Built the NotebookLM research pipeline** and validated it end-to-end.
3. **Upgraded the `notebooklm-jayers` skill** to fit our conventions.
4. **Set up the Python toolchain** (uv + firecrawl-py, venv outside iCloud).
5. **Produced 8 research reports** across two clusters (domain + pedagogy).

## Conventions locked in

- **raw/ topic tree:** root `NN` (two-digit, zero-padded); prompt `NN-<slug>-prompt.md`;
  report `NN.1-<slug>.md`; up to three levels (`NN.M.K`), single-digit children.
- **Research loop:** prompts < 300 words; one NotebookLM notebook per topic; pipeline =
  `research start --mode deep` → `research import` → `report create` (studio artifact) →
  poll `studio status` → extract via the skill with `--number`/`--slug`.
  - Gotcha: deep research can sit at 0 sources past the 5-min estimate, then land all at
    once; a premature import prints "No sources were found" — re-probe before importing.
- **Reports are studio `report` artifacts**, not `generated_text` sources.
- **Python:** uv; venv at `~/.venvs/artist-study-kit` (iCloud must not sync it; `.venv` is a symlink).
- **Web scraping:** standardized on **Firecrawl** (`firecrawl-py`); fallback Crawl4AI; Scrapy for image jobs.
- **Output style:** Obsidian-friendly (frontmatter, `[[wikilinks]]`, tag taxonomy) for the
  wiki layer and skill outputs; raw NotebookLM reports left as-is apart from frontmatter.

## Research corpus

**Domain / tooling cluster**
- [[01.1-web-scraping-tooling]] — Firecrawl (primary), Crawl4AI (fallback), Scrapy for images. ([[01-web-scraping-tooling-prompt|prompt]])
- [[02.1-source-quality-grading]] — weighted rubric + machine-detectable signals + high-trust shortlist (Smarthistory, Met, CAA). ([[02-source-quality-grading-prompt|prompt]])
- [[03.1-museum-image-apis]] — IIIF guide + per-source assessment; priority Met → Rijksmuseum → AIC → Harvard/Europeana → Wikimedia. ([[03-museum-image-apis-prompt|prompt]])
- [[04.1-style-analysis-frameworks]] — layered formal-analysis taxonomy + 5-stage LLM workflow + study drills + reusable template. ([[04-style-analysis-frameworks-prompt|prompt]])

**Pedagogy / learning-science cluster**
- [[05.1-master-study-pedagogy]] — atelier/Bargue/copyist traditions, critique practices, staged self-learner workflow. ([[05-master-study-pedagogy-prompt|prompt]])
- [[06.1-productive-friction-learning]] — desirable difficulties + Socratic AI (Khanmigo), interaction patterns, anti-patterns. ([[06-productive-friction-learning-prompt|prompt]])
- [[07.1-study-aids-scaffolding]] — job aid vs learning aid, worked-example fading, the crutch problem, art-study templates. ([[07-study-aids-scaffolding-prompt|prompt]])
- [[08.1-spaced-repetition-retention]] — SRS/interleaving, perceptual + procedural practice, a review system, honest SRS limits. ([[08-spaced-repetition-retention-prompt|prompt]])

## Tooling / skill work

- **`notebooklm-jayers` skill** extended (separate repo): FR1 studio-artifact detection,
  FR2 `--number NN.M` / `--next --root` tree numbering, FR3 Obsidian YAML frontmatter, and a
  `--slug` override. Backed by 39 passing pytest-bdd tests. The feature request that drove it:
  `~/.claude/skills/notebooklm-jayers/feature-requests/01-report-artifacts-tree-numbering-frontmatter.md`.
- **Topic → notebook map** is maintained in `CLAUDE.md`.

## Key decisions

- NotebookLM access goes **only** through the `notebooklm-jayers` skill — no repo-level MCP.
- `wiki/` synthesis layer **deferred** until raw/ was populated (now is — see Next).
- Pedagogy treated as **separate roots 05–08**, not a single grouped subtopic.

## State & next steps

Phase 1 (research) is complete: 8 topics, 16 prompt+report files in `raw/`, all committed.

Recommended Phase 2 options (see `TODO.md` "Later"):
1. **Stand up `wiki/`** — synthesize the domain + pedagogy threads into a cross-linked study
   methodology (the LLM-Wiki step).
2. **Draft the skill design/spec** from the synthesized research (brainstorming → writing-plans).
3. **First `scripts/` work** — Firecrawl-based scraping + museum/IIIF image discovery.
