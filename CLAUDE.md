# artist-study-kit

## What this project is

A research-and-build project whose **deliverable is a Claude skill**. The skill takes a
historical artist's name and produces a structured studio-prep study package: background,
web-source grading, important-works inventory, high-res image discovery, human curation,
deep visual analysis, and study notes. Full vision: `raw/00-artist-study-kit-seed.md`.

**Stage: Phase 3 (skill build/refine) — skill is built and live-validated.** The research
corpus (`raw/`) and `wiki/` synthesis layer are populated, and the skill itself lives in
`skill/` (`SKILL.md` + `scripts/`; pytest; validated end-to-end on real artists). All of
`raw/19` is shipped (stateful runs, custom-image injection, narrowing funnel); the deferred
duplicate-handling-on-re-query spec is the main open item. **Freshest state = `tail wiki/log.md`
+ `TODO.md`**; deeper narrative in the `raw/` session handoffs (latest `raw/17`).

## Working method (LLM-Wiki)

This repo follows the **LLM-Wiki pattern**: immutable **raw sources** → an LLM-maintained
**wiki** → a **schema** (this file). **`wiki/` is this project's memory** — research synthesis
*and* build status; treat it as the source of truth for "where things stand." Method reference
(the pattern's source doc — read it before an ingest/lint pass):
`/Users/jayers/code/public_shuttle/prompts/llm-wiki.md`. Core operations: **ingest** (a new
`raw/` source → update every wiki page it touches + the index + append to `wiki/log.md`),
**query** (answer from the wiki; file good answers back as notes), and **lint** (health-check
for contradictions, stale claims, orphans, missing links). Build work adds two house ops to
the log: **build** (a shipped thrust → mark the stage note **BUILT**) and **validate** (a live
e2e run → record the result).

- **On session start:** read `wiki/00-index.md`, the stage note(s) you're touching, and
  `tail wiki/log.md` (freshest state) before acting.
- **On finishing work:** append a `log.md` entry and update any stage note whose status
  changed — same discipline as ingest. Keep the wiki current or it rots.

- `raw/`     — immutable, numbered corpus: research reports, decision docs, brainstorms.
- `wiki/`    — LLM-maintained synthesis + project memory: interlinked stage + concept notes (see below).
- `skill/`   — **the deliverable**: `SKILL.md` + `scripts/` (Python, uv). The skill's own code lives here, not at repo root.
- `docs/superpowers/` — skill `specs/` + implementation `plans/` (written by the brainstorming / writing-plans skills).
- `tests/`   — pytest suite (one `test_<module>.py` per `skill/scripts/` module; offline).
- `e2e/`      — live end-to-end harnesses (hit the real network; outside pytest's `tests/`). See `e2e/README.md`.
- `studies/`  — skill output: per-artist study packages (the output contract; see seed §5).
- `CLAUDE.md` — this file: project conventions and workflow schema.

## Conventions

### raw/ numbering (topic-tree convention)
Each **topic** is a root with a two-digit zero-padded prefix (`NN`); its prompt and results
live next to each other and tree off that root with dotted decimals.

- **Root:** two-digit zero-padded (`NN`) — we expect more than ten roots, so always pad.
- **Prompt:** `NN-<slug>-prompt.md` — the trailing `-prompt` marks it as the research input.
- **Children:** single-digit, max nine per parent (`1`–`9`). The deep-research report is typically `NN.1`.
- **Depth:** up to three levels total — `NN`, `NN.M`, `NN.M.K`. Only add a decimal level when a
  document actually has children; don't carry a placeholder `.0` or `.1` on a leaf that doesn't need it.
- Next root number = highest existing root + 1. `00` is the seed (a root with no children).
- `raw/` is append-only sources of truth — don't rewrite history; add a new numbered doc.

Example:
```
raw/
  00-artist-study-kit-seed.md          # seed (root, no children)
  01-web-scraping-tooling-prompt.md    # research prompt
  01.1-web-scraping-tooling.md         # deep-research report (child)
  01.2-web-scraping-decision.md        # follow-on decision doc (child)
  04.1.1-composition-deep-dive.md      # grandchild (level 3) under 04.1
  04.1.2-color-theory-deep-dive.md     # grandchild (level 3) under 04.1
```

### wiki/ structure (synthesis layer)
The `wiki/` is the LLM-maintained synthesis of `raw/`, organized around the **skill
pipeline**. Design rationale: `raw/10-wiki-synthesis-design.md`. Note types:

- **Index** — `00-index.md` (MOC): pipeline order + concept clusters + source→stage map.
- **Log** — `log.md`: append-only, chronological record (newest last), `<op>` ∈
  ingest/query/lint/build/validate. Entry prefix `## [YYYY-MM-DD] <op> | <title>` so
  `grep "^## \[" wiki/log.md | tail` works. Update it on every ingest **and every shipped
  build / live validation**. Deeper narrative still lives in the `raw/` session handoffs.
- **Stage notes** — `stage-<slug>.md`, one per skill-pipeline step. Body =
  `## What the research says` · `## Open questions / tensions` · `## Skill design implications`.
  Frontmatter `sources:` lists the backing `raw/` reports (empty = research gap). UAT findings
  and feature requests are folded into the relevant stage's "Open questions / tensions"; when a
  feature ships, mark its implication **BUILT** (cite the spec/plan path).
- **Concept notes** — `concept-<slug>.md`: atomic, cross-cutting ideas referenced by 2+
  stages (promotion rule: only create one when a 3rd stage needs it). Frontmatter `used-by:`.

Conventions: kebab-case filenames; `type: wiki/stage|wiki/concept|wiki/index|wiki/log`; link back to
raw via `[[NN.1-slug]]` and between wiki notes via `[[stage-*]]`/`[[concept-*]]`. The wiki is
the only layer carrying inter-note `[[wikilinks]]`; `raw/` is never edited to add them.

### Deep research (NotebookLM)
- **All** NotebookLM access goes through the **`notebooklm-jayers` skill** (`/ntlm`) — never wire
  the raw `notebooklm-mcp` into this repo. The skill owns the MCP connection (configured globally
  in `~/.claude/settings.json`) and is the single control point we extend as needs arise.
- Keep each research **prompt under 300 words**; **one notebook per topic**.
- Step-by-step pipeline + topic→notebook-id map: **`docs/notebooklm-deep-research.md`**.

### Python / scripting
- **Python** managed with **uv**. Use `uv run` / `uv add`; dependencies live in `pyproject.toml`.
- **Venv lives OUTSIDE iCloud.** This repo is in iCloud Drive, which would sync a normal
  in-project `.venv/` (thousands of files). The venv is at `~/.venvs/artist-study-kit`:
  - Canonical: `export UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit"` before `uv` commands.
  - Convenience: `.venv` in the repo is a **symlink** → `~/.venvs/artist-study-kit`, so plain
    `uv run`/`uv sync` also stay out of iCloud. (The symlink is tiny; iCloud doesn't traverse it.)
  - To recreate on a fresh machine: `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync`
    then `ln -s "$HOME/.venvs/artist-study-kit" .venv`.

### Web scraping
- **Standardized on Firecrawl** via the **`firecrawl-py`** package (decision: `raw/01.1-web-scraping-tooling.md`).
  Fallback is Crawl4AI; use Scrapy for large image-download jobs. Don't scatter ad-hoc scraping approaches.

### Paths
- Use logical `~/iCloud/...` paths, never physical `~/Library/Mobile Documents/...`. Quote paths.

## Markdown / Obsidian conventions

The repo is intended to open as an **Obsidian vault**. Generated markdown should be
vault-friendly — but scope effort by layer:

- **`raw/`** — immutable NotebookLM reports; do not edit to add links. (Skill may emit
  YAML frontmatter so they're still graph-navigable.)
- **`wiki/`** (synthesis layer) and **skill study-package outputs** — fully Obsidian-native:
  - `[[wikilinks]]` between related notes (artist ↔ works ↔ movements ↔ techniques);
    use `[[NN-slug|Readable Title]]` when the filename is ugly.
  - YAML frontmatter: `tags`, `aliases`, `type`, and domain keys (`artist`, `movement`).
  - Tag taxonomy: `#artist/<name>`, `#movement/<x>`, `#technique/<x>`, `#source-grade/<a-f>`.
  - Callouts for study notes: `> [!tip]`, `> [!warning]` (traps to avoid), `> [!example]`.
- Keep kebab-case filenames (Obsidian-safe); avoid `:` `/` `#` `^` `|` `[` `]` in names.

## Building the skill (Phase 3 — active)

The skill is substantially built (`skill/SKILL.md` + ~24 `scripts/` modules, pytest,
live-validated). When extending or refining it, **start from the synthesis**: read
`wiki/00-index.md`, then the stage note(s) you're touching. Each stage note's **"Skill design
implications"** is the spec input (a **BUILT** marker means it already ships); the `raw/`
reports are the evidence behind it. Build loop: brainstorm → spec → plan → subagent-driven
TDD → merge → record back to the wiki (`log.md` + stage-note status).

- **Research stays in `raw/`** (numbered NotebookLM reports, decision docs, session
  handoffs). **Skill specs & plans go to the superpowers default location**
  (`docs/superpowers/specs/` and its plans dir) — let the brainstorming / writing-plans
  skills write there; don't force specs into `raw/`. (Exception: the pre-existing
  `raw/10-wiki-synthesis-design.md` predates this rule and stays put.)
- **Output contract.** The skill emits a per-artist study package; the canonical structure
  is defined in `raw/00-artist-study-kit-seed.md` (§5 directory layout + "Expected Outputs"):
  `studies/<artist>/` → `report.md`, `sources/` (`sources.json`, `source-grades.md`),
  `works.md`, `images/{candidates,selected}/`, `analysis.md`, `study-notes.md`, `prompts/`.
  Treat that as the contract the skill must produce.
- **Packaging.** Deliverable is a Claude skill = `SKILL.md` + `scripts/`, developed in-repo
  under `skill/` (installable/symlinkable to `~/.claude/skills/` later). Tests live at
  repo-root `tests/` (one `test_<module>.py` per `skill/scripts/` module); `pytest` runs offline.
- **TDD.** Skill scripts follow the global stack — **outside-in TDD, uv**: write the failing
  test before the implementation. Tests are plain `pytest` (`tests/test_<module>.py`), not
  pytest-bdd/Gherkin — the acceptance layer is the per-thrust spec in `docs/superpowers/specs/`.

## Current focus
**Live state = `tail wiki/log.md` + `TODO.md`** (this section is the orientation map, not the
status of record). **Phase 3 (skill build/refine) — skill built and live-validated; all of
`raw/19` shipped.**

Research corpus in `raw/` (deep-research topics): domain/tooling `01` web scraping · `02`
source-quality grading · `03` museum/image APIs · `04` style-analysis frameworks · `16` image
source hierarchy; pedagogy/learning-science `05`–`08`; pipeline-stage method `11`–`13`.
Build-phase feedback/meta: `18` UAT · `19` stateful-runs / custom-images / narrowing-funnel
· `20` study-dimensions · `21` divergent/convergent cognition.

`wiki/` is maintained (**9 stage + 7 concept** + index + log; design
`raw/10-wiki-synthesis-design.md`, entry point `wiki/00-index.md`, history `wiki/log.md`).
Phase 1 handoff: `raw/09-phase-1-research-session.md`. **Next** per `TODO.md` — the main open
item is the deferred duplicate-handling-on-re-query spec.
