# artist-study-kit

## What this project is

A research-and-build project whose **deliverable is a Claude skill**. The skill takes a
historical artist's name and produces a structured studio-prep study package: background,
web-source grading, important-works inventory, high-res image discovery, human curation,
deep visual analysis, and study notes. Full vision: `raw/00-artist-study-kit-seed.md`.

**Stage: Phase 2 (wiki synthesis) complete → skill design.** Both `raw/` (11 research
topics) and the `wiki/` synthesis layer are populated. Next = draft the skill spec from the
wiki, then build. Latest session handoff: `raw/14-phase-2-wiki-session.md`.

## Working method (LLM-Wiki)

This repo follows Karpathy's LLM-Wiki pattern: immutable **raw sources** → an LLM-maintained
**wiki** → a **schema** (this file). The raw layer (Phase 1) and the `wiki/` synthesis layer
(Phase 2) are both populated.

- `raw/`     — immutable, numbered corpus: research reports, decision docs, brainstorms.
- `wiki/`    — LLM-maintained synthesis: interlinked stage + concept notes (see below).
- `scripts/` — Python tooling (uv) for scraping, image discovery, etc. (added as needed).
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
pipeline**. Design rationale: `raw/10-wiki-synthesis-design.md`. Three note types:

- **Index** — `00-index.md` (MOC): pipeline order + concept clusters + source→stage map.
- **Stage notes** — `stage-<slug>.md`, one per skill-pipeline step. Body =
  `## What the research says` · `## Open questions / tensions` · `## Skill design implications`.
  Frontmatter `sources:` lists the backing `raw/` reports (empty = research gap).
- **Concept notes** — `concept-<slug>.md`: atomic, cross-cutting ideas referenced by 2+
  stages (promotion rule: only create one when a 3rd stage needs it). Frontmatter `used-by:`.

Conventions: kebab-case filenames; `type: wiki/stage|wiki/concept|wiki/index`; link back to
raw via `[[NN.1-slug]]` and between wiki notes via `[[stage-*]]`/`[[concept-*]]`. The wiki is
the only layer carrying inter-note `[[wikilinks]]`; `raw/` is never edited to add them.

### Deep research (NotebookLM)
- **All** NotebookLM access goes through the **`notebooklm-jayers` skill** (`/ntlm`) — never wire
  the raw `notebooklm-mcp` into this repo. The skill owns the MCP connection (configured globally
  in `~/.claude/settings.json`) and is the single control point we extend as needs arise.
- Keep each research **prompt under 300 words**.
- **One notebook per topic.** Validated end-to-end pipeline (run from the repo root, `nlm` on PATH at
  `~/.local/bin`). The report is a NotebookLM **studio "report" artifact**; the upgraded skill
  detects it, numbers the file, and writes Obsidian frontmatter:
  1. Save the prompt as `raw/NN-<slug>-prompt.md`.
  2. Discover sources (~5 min): `nlm research start "<concise query>" --mode deep --title "artist-study-kit: NN <topic>"`.
     Note the returned **notebook id** and **task id**. (Keep the query short — overly long queries can yield zero sources.)
  3. Import once complete: `nlm research import <notebook-id> <task-id> --timeout 300`.
     Discovery can run past the 5-min estimate with `source_count` stuck at 0, then land all at once;
     a premature import prints "No sources were found" — re-probe with `nlm research start "probe" -n <nb> --mode fast`
     (answer `n`), which reports "sources available: N" when ready, then import.
  4. Generate the report: `nlm report create <notebook-id> --format "Create Your Own" --confirm --prompt "<the research prompt>"`.
     Returns an **artifact id**.
  5. Wait: poll `nlm studio status <notebook-id>` until the report artifact is `completed`.
  6. Extract to the tree path via the skill:
     `uv run --no-project ~/.claude/skills/notebooklm-jayers/get_deep_research_report.py <notebook-id> --number NN.1 --slug <topic-slug>`
     → writes `raw/NN.1-<topic-slug>.md` with YAML frontmatter. Use `--slug` to match the prompt's
     topic slug (without it, the filename auto-derives from the report title).
- **Topic → notebook map:**
  - `01` web scraping tooling → `72ddf4cf-41dc-4c65-8b93-c43e01936219`
  - `02` source quality grading → `fe59cf3e-bbcb-4e2b-9bcb-6ead3f3d2d1a`
  - `03` museum image apis → `f89f6f2f-84c1-42e8-9e90-e420aa7aeb9a`
  - `04` style analysis frameworks → `2792f9bf-2ebc-44b5-bb0f-2ca993d8cd57`
  - `05` master study pedagogy → `0daad4a4-2862-4528-9d80-fcb3bbed10d0`
  - `06` productive friction learning → `a0c8d5f2-bf87-4d31-8405-529582aacff2`
  - `07` study aids scaffolding → `459f962b-15a8-428e-aa67-fa74484c1ee9`
  - `08` spaced repetition retention → `3c7c8d72-84a1-4ebc-8ec8-3d38d99b5806`
  - `11` artist background research → `d2c20815-2f7f-4165-8314-88a318e0d2e7`
  - `12` works inventory method → `2cf4ccd2-0a0f-406a-91fd-a1c3ec4fe2f1`
  - `13` human curation ux → `c7723fe4-2a83-47de-9a2f-dd29e5c2a038`
  - `16` image source hierarchy → `8260e980-d7cc-42f3-9c4f-4c24e054221f`

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

## Building the skill (Phase 3)

When designing or implementing the skill, **start from the synthesis**: read
`wiki/00-index.md`, then the stage notes. Each stage note's **"Skill design implications"**
section is the spec input; the `raw/` reports are the evidence behind it.

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
- **Packaging.** Deliverable is a Claude skill = `SKILL.md` + `scripts/`. Develop in-repo
  under `skill/` (installable/symlinkable to `~/.claude/skills/` later); confirm the exact
  layout in the skill spec.
- **TDD.** Skill scripts follow the global stack — **outside-in TDD with pytest-bdd**, uv.
  Write the Gherkin / acceptance specs before implementation.

## Current focus
See `TODO.md`. **Phase 2 (wiki synthesis) complete.** Research corpus = 11 topics in `raw/`:
- Domain/tooling: `01` web scraping · `02` source-quality grading · `03` museum/image APIs · `04` style-analysis frameworks.
- Pedagogy/learning-science: `05` master-study pedagogy · `06` productive-friction · `07` study aids/scaffolding · `08` spaced-repetition retention.
- Pipeline-stage gaps (added during wiki design): `11` artist background research · `12` works inventory method · `13` human curation UX.

`wiki/` is stood up (15 notes: 8 stage + 6 concept + index; design `raw/10-wiki-synthesis-design.md`,
entry point `wiki/00-index.md`). Phase 1 handoff: `raw/09-phase-1-research-session.md`.
**Next: draft the skill spec** from the stage notes' "Skill design implications", then build
first `scripts/` (Firecrawl + IIIF image discovery).
