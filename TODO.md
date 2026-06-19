# artist-study-kit — TODO

## Setup (be productive)
- [x] NotebookLM access via the `notebooklm-jayers` skill (`/ntlm`) — no repo-level MCP; skill owns the connection.
- [x] Initialize uv project: `pyproject.toml` + `.venv/` (`uv init`).
- [x] Add `CLAUDE.md` and this `TODO.md`.

## notebooklm-jayers skill — build up as we go
- [ ] Add topic-tree numbering to `ntlm get report` (e.g. `--number NN.1` / `--next` to emit `raw/NN.M-<slug>.md`). Until then, rename manually after extraction.
- [ ] Have `ntlm get report` emit YAML frontmatter (tags, source, date) so raw/ docs are Obsidian graph-navigable.

## Research backlog (each → numbered raw/ doc via NotebookLM deep research)
- [ ] 01 — Web scraping tooling: evaluate Firecrawl / Crawl4AI / Scrapy / Playwright / trafilatura; recommend one.
- [ ] 02 — Source quality grading rubric (anti-slop; institutional authority; ad density; market vs. learning).
- [ ] 03 — Museum / image APIs: IIIF, open-access museum APIs, high-res discovery.
- [ ] 04 — Style-analysis frameworks: art & design principles taxonomy for visual-analysis output.

## Later
- [ ] Stand up the `wiki/` synthesis layer once raw/ has enough reports.
- [ ] Draft the skill design/spec from synthesized research.
- [ ] Build scraping + image-discovery scripts in `scripts/`.
