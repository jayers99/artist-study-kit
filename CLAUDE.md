# artist-study-kit

## What this project is

A research-and-build project whose **deliverable is a Claude skill**. The skill takes a
historical artist's name and produces a structured studio-prep study package: background,
web-source grading, important-works inventory, high-res image discovery, human curation,
deep visual analysis, and study notes. Full vision: `raw/00-artist-study-kit-seed.md`.

**Stage: planning / research.** Current work = curate research into `raw/`, make decisions,
then design the skill.

## Working method (LLM-Wiki, raw layer only)

This repo follows Karpathy's LLM-Wiki pattern: immutable **raw sources** → an LLM-maintained
**wiki** → a **schema** (this file). Only the raw layer is active now; `wiki/` is deferred
until `raw/` is populated.

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
  `~/.local/bin`); the report is a NotebookLM **studio "report" artifact**, fetched with
  `nlm download report` — *not* the source-scanning `ntlm get report`, which only finds
  `generated_text` sources and misses these:
  1. Save the prompt as `raw/NN-<slug>-prompt.md`.
  2. Discover sources (~5 min): `nlm research start "<concise query>" --mode deep --title "artist-study-kit: NN <topic>"`.
     Note the returned **notebook id** and **task id**. (Keep the query short — overly long queries can yield zero sources.)
  3. Import once complete: `nlm research import <notebook-id> <task-id> --timeout 300`
     (poll `nlm get notebook <id>` for `source_count`; a re-run of `research start` reports
     "sources available: N — not yet imported" if import raced ahead).
  4. Generate the report: `nlm report create <notebook-id> --format "Create Your Own" --confirm --prompt "<the research prompt>"`.
     Returns an **artifact id**.
  5. Wait: poll `nlm studio status <notebook-id>` until the report artifact is `completed`.
  6. Download to the tree path:
     `nlm download report <notebook-id> --id <artifact-id> -o "raw/NN.1-<slug>.md"`.
- **Skill gap / enhancement (see `TODO.md`):** teach `notebooklm-jayers` to (a) fetch studio
  `report` artifacts, not just `generated_text` sources, and (b) emit the `NN.M-` tree prefix —
  so this whole flow collapses back to a couple of `ntlm` verbs.
- **Topic → notebook map:**
  - `01` web scraping tooling → `72ddf4cf-41dc-4c65-8b93-c43e01936219`

### Python / scripting
- **Python** managed with **uv**, in-project `.venv/`. Use `uv run` / `uv add`;
  dependencies live in `pyproject.toml`.

### Web scraping
- Core activity. **Standardize on one tool** (decision pending — `raw/01.1-web-scraping-tooling.md`).
  Until decided, don't scatter ad-hoc scraping approaches.

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
See `TODO.md`. Research backlog → numbered `raw/` docs:
01 web scraping tooling · 02 source-quality grading · 03 museum/image APIs · 04 style-analysis frameworks.
