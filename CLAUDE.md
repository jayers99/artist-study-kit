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

### raw/ numbering
- Every `raw/` doc gets a **two-digit zero-padded sequential prefix**: `NN-short-slug.md`.
- Next number = highest existing + 1. `00` is the seed.
- `raw/` is append-only sources of truth — don't rewrite history; add a new numbered doc.

### Deep research (NotebookLM)
- **All** NotebookLM access goes through the **`notebooklm-jayers` skill** (`/ntlm`) — never wire
  the raw `notebooklm-mcp` into this repo. The skill owns the MCP connection (configured globally
  in `~/.claude/settings.json`) and is the single control point we extend as needs arise.
- Keep each research **prompt under 300 words**.
- Workflow per research doc, run from the repo root:
  1. `ntlm research <notebook-id> "<topic>"` — start deep research (or run it in the NotebookLM UI).
  2. `ntlm get report <notebook-id>` — extracts the report, synthesizes a short slug, and saves to
     `./raw/<slug>.md` (creates `raw/` if missing).
  3. Apply the `NN-` two-digit prefix → `raw/NN-<slug>.md`.
- **Known gap / first skill enhancement:** `ntlm get report` does not yet emit the `NN-` prefix.
  For now, rename after extraction. When this bites, extend the skill (e.g. an `--number/--next`
  option) rather than scripting around it here — see `TODO.md`.

### Python / scripting
- **Python** managed with **uv**, in-project `.venv/`. Use `uv run` / `uv add`;
  dependencies live in `pyproject.toml`.

### Web scraping
- Core activity. **Standardize on one tool** (decision pending — `raw/01-web-scraping-tooling.md`).
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
