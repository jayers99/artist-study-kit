# artist-study-kit — TODO

## Setup (be productive)
- [x] NotebookLM access via the `notebooklm-jayers` skill (`/ntlm`) — no repo-level MCP; skill owns the connection.
- [x] Initialize uv project: `pyproject.toml` + `.venv/` (`uv init`).
- [x] Add `CLAUDE.md` and this `TODO.md`.

## notebooklm-jayers skill — build up as we go
- [x] FR1/FR2/FR3 implemented (studio `report` artifacts, `--number NN.M`/`--next --root`, Obsidian frontmatter). 37 pytest-bdd tests pass. Validated live on doc 03.
- [ ] Add `--slug <slug>` override to `get report`: auto-slug derives from the report *title*, so the file doesn't match the topic slug of its `NN-<slug>-prompt.md`. Currently rename by hand.

## Research backlog (each → numbered raw/ doc via NotebookLM deep research)
- [x] 01 — Web scraping tooling → `raw/01.1-web-scraping-tooling.md`. **Recommendation: Firecrawl (primary), Crawl4AI (fallback), Scrapy for large image jobs.**
- [x] 02 — Source quality grading rubric → `raw/02.1-source-quality-grading.md`. **Weighted rubric + tiers + machine-detectable signals + high-trust shortlist (Smarthistory, Met, CAA).**
- [x] 03 — Museum / image APIs → `raw/03.1-museum-image-apis.md`. **IIIF guide + per-source assessment; priority Met → Rijksmuseum → AIC → Harvard/Europeana → Wikimedia.**
- [ ] 04 — Style-analysis frameworks: art & design principles taxonomy for visual-analysis output.

## Later
- [ ] Stand up the `wiki/` synthesis layer once raw/ has enough reports.
- [ ] Draft the skill design/spec from synthesized research.
- [ ] Build scraping + image-discovery scripts in `scripts/`.
