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

## Later
- [ ] Stand up the `wiki/` synthesis layer once raw/ has enough reports.
- [ ] Draft the skill design/spec from synthesized research.
- [ ] Build scraping + image-discovery scripts in `scripts/`.
