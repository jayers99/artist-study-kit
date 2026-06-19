# artist-study-kit

## What this project is

A research-and-build project whose **deliverable is a Claude skill**. The skill takes a
historical artist's name and produces a structured studio-prep study package: background,
web-source grading, important-works inventory, high-res image discovery, human curation,
deep visual analysis, and study notes. Full vision: `raw/00-artist-study-kit-seed.md`.

**Stage: Phase 1 research complete → synthesis & skill design.** The `raw/` corpus is
populated (8 topics; see `raw/09-phase-1-research-session.md`). Next = stand up `wiki/`
synthesis and/or draft the skill spec.

## Working method (LLM-Wiki, raw layer only)

This repo follows Karpathy's LLM-Wiki pattern: immutable **raw sources** → an LLM-maintained
**wiki** → a **schema** (this file). The raw layer is populated (Phase 1); the `wiki/`
synthesis layer is the next phase and is not stood up yet.

- `raw/`     — immutable, numbered corpus: research reports, decision docs, brainstorms.
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
- **`wiki/`** (deferred) and **skill study-package outputs** — fully Obsidian-native:
  - `[[wikilinks]]` between related notes (artist ↔ works ↔ movements ↔ techniques);
    use `[[NN-slug|Readable Title]]` when the filename is ugly.
  - YAML frontmatter: `tags`, `aliases`, `type`, and domain keys (`artist`, `movement`).
  - Tag taxonomy: `#artist/<name>`, `#movement/<x>`, `#technique/<x>`, `#source-grade/<a-f>`.
  - Callouts for study notes: `> [!tip]`, `> [!warning]` (traps to avoid), `> [!example]`.
- Keep kebab-case filenames (Obsidian-safe); avoid `:` `/` `#` `^` `|` `[` `]` in names.

## Current focus
See `TODO.md`. **Phase 1 research is complete** — 8 topics in `raw/`:
- Domain/tooling: `01` web scraping · `02` source-quality grading · `03` museum/image APIs · `04` style-analysis frameworks.
- Pedagogy/learning-science: `05` master-study pedagogy · `06` productive-friction · `07` study aids/scaffolding · `08` spaced-repetition retention.

Phase 1 handoff: `raw/09-phase-1-research-session.md`. Phase 2 options: stand up `wiki/`
synthesis · draft the skill design/spec · build first `scripts/` (Firecrawl + IIIF image discovery).
