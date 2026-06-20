# artist-study-kit

> Turn a historical artist's name into a structured **studio-prep study package** — background, graded sources, visual grammar, ranked works, high-res reference images, human curation, deep formal analysis, and spaced study drills.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![Obsidian vault](https://img.shields.io/badge/Obsidian-vault-7c3aed.svg)
![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-d97757.svg)

`artist-study-kit` is a **Claude skill**. Point it at a historical artist and it assembles everything a painter needs to do a serious *master study* — the art-historical homework and the high-resolution reference — organized into a navigable Obsidian vault, with the taste-driven choices left to you.

It runs on a deliberate division of labour:

- **Claude does the art-historical judgment** — biographical research, source grading, visual-grammar definition, works selection, formal analysis, and study pedagogy.
- **Deterministic Python does the plumbing** — a resumable state machine, source-trust scoring, IIIF/Commons image discovery and polite download, a star-rating curation gallery, ranking, and Obsidian-native emission.
- **You make the taste calls** at two human pauses — which images are worth studying, and which final few to study deeply.

The goal is to keep *you* doing the seeing. It is research-grounded scaffolding, not a finished answer.

## What you get

Each run produces `studies/<artist-slug>/` — a self-contained, Obsidian-native package (example from a real run on Paul Klee):

```
studies/paul-klee/
├── report.md               # background + art-historical placement + visual grammar
├── sources/
│   ├── sources.json        # machine-readable graded sources
│   └── source-grades.md    # A–F trust report (authority, commercial bias, citations…)
├── works.md                # important works, ranked importance × studyability, clustered
├── images/
│   ├── candidates/         # downloaded high-res candidates (per work)
│   └── selected/           # your liked set, after curation
├── gallery.html            # standalone star-rating curation gallery (Human Pause 1)
├── selection.json          # your ratings + curatorial gate
├── preference-synthesis.md # the pattern across what you liked + a ranked study funnel
├── analysis.md             # 5-stage formal analysis of your chosen study set
├── study-notes.md          # faded-aid notes (cheat sheet → checklist → bare prompt)
├── drills/                 # perceptual discrimination cards (is-A / is-not-A)
├── review-schedule.md      # spaced + interleaved review plan
├── prompts/                # the prompts used, for reproducibility
└── state.json              # resumable pipeline state
```

Markdown is vault-friendly throughout: YAML frontmatter, `[[wikilinks]]`, a tag taxonomy (`#artist/…`, `#movement/…`, `#source-grade/…`), and study callouts (`> [!tip]`, `> [!warning]`).

## How it works

A **resumable, idempotent** 8-stage pipeline with two human-in-the-loop pauses. Re-invoking the skill picks up from `state.json`; each stage overwrites its own outputs without disturbing the others.

| # | Stage | Output | Who |
|---|-------|--------|-----|
| 1 | Background | `report.md` (bio + placement) | Claude |
| 2 | Source grading | `sources.json` · `source-grades.md` | Claude + rubric |
| 3 | Style definition | `report.md` (visual grammar) | Claude |
| 4 | Works inventory | `works.md` | Claude |
| 5 | Image discovery | `images/candidates/` · `gallery.html` | scripts (IIIF → Commons) |
| ⏸ | **Human Pause 1 — curation** | `selection.json` | **you** — star-rate the gallery |
| 6 | Preference synthesis | `preference-synthesis.md` (ranked funnel) | Claude + ranking |
| ⏸ | **Human Pause 2 — funnel** | chosen study set | **you** — pick the final few |
| 7 | Visual analysis | `analysis.md` | Claude |
| 8 | Study & retention | `study-notes.md` · `drills/` · `review-schedule.md` | Claude |

The friction is the point. The curation gallery, faded study aids, discrimination drills, and spaced schedule are drawn from learning-science and master-copy pedagogy (desirable difficulty, worked-example fading, spaced repetition) — the research behind each is synthesized in `wiki/`.

## Quick start

### 1. Install the tooling

Requires [uv](https://docs.astral.sh/uv/) and Python 3.12+.

```bash
git clone https://github.com/jayers99/artist-study-kit
cd artist-study-kit
uv sync
```

> [!NOTE]
> This repo is designed to live in iCloud Drive, which would sync a normal in-project `.venv/` (thousands of files). The venv is therefore kept **outside** iCloud and symlinked in. To recreate it:
> ```bash
> UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync
> ln -s "$HOME/.venvs/artist-study-kit" .venv
> ```
> Outside iCloud, plain `uv sync` is fine.

### 2. (Optional) add a Firecrawl key

Only Stage 2's web fetching uses [Firecrawl](https://www.firecrawl.dev/); image discovery does not.

```bash
cp .env.example .env   # then paste your FIRECRAWL_API_KEY
```

### 3. Install the skill into Claude Code

```bash
ln -s "$PWD/skill" ~/.claude/skills/artist-study-kit
```

### 4. Use it

In [Claude Code](https://claude.com/claude-code), just name an artist:

> "Do a master study of Paul Klee."
> "I want to study Vilhelm Hammershøi's interiors."

The skill runs the pipeline and stops at the gallery so you can star-rate candidates (open `gallery.html`, rate, fill the curatorial gate for keepers, export `selection.json`). It then stops again for you to pick the final study set from the ranked funnel, and finishes the deep analysis and study aids. Everything lands in `studies/<artist-slug>/`.

## Repository layout — the LLM-Wiki method

The repo follows Karpathy's **LLM-Wiki** pattern: immutable raw sources → an LLM-maintained synthesis → a schema.

| Path | Role |
|------|------|
| `raw/` | Immutable, numbered corpus (27 docs): NotebookLM deep-research reports, decision docs, session handoffs. Append-only — never edited. |
| `wiki/` | LLM-maintained synthesis (15 notes: index + 8 stage + 6 concept), interlinked with `[[wikilinks]]`. Entry point: [`wiki/00-index.md`](wiki/00-index.md). Each stage note's "Skill design implications" is the spec input. |
| `skill/` | The deliverable: [`SKILL.md`](skill/SKILL.md) + `scripts/` (16 Python modules). |
| `tests/` | pytest suite — 117 tests, network boundaries injected. |
| `docs/superpowers/` | The skill spec and the three build plans. |
| `CLAUDE.md` | Project schema and conventions (the "schema" layer). |
| `studies/` | Generated per-artist output (gitignored runtime artifact). |

The whole repo also opens as an **Obsidian vault** — open the folder in Obsidian and the `raw/ → wiki/ → study` links are navigable in the graph.

## Development

Built test-first (the repo convention is outside-in TDD with pytest):

```bash
uv run pytest          # 117 tests
```

Conventions live in [`CLAUDE.md`](CLAUDE.md). In short: research stays in `raw/` (numbered, immutable); synthesis in `wiki/`; code in `skill/scripts/` (managed with uv — httpx/Firecrawl network boundaries are injected so tests never hit the network). Web scraping standardizes on Firecrawl; image discovery prefers museum **IIIF** (Met → Rijksmuseum → Art Institute of Chicago → Harvard → Europeana → Wikimedia) and falls back to **Wikimedia Commons** for artists still in copyright, where museums hold no public-domain image.

## Status

The skill is built (foundation → research tooling → curation/study, all merged) and has been run end-to-end on Paul Klee. The "automated" stages are executed by Claude under `SKILL.md`; the scripts are the deterministic tooling around that judgment. Known follow-ups (deferred, non-blocking) include Scrapy-based bulk image download and per-institution identity resolution.

## License

MIT © 2026 John Ayers — see [LICENSE](LICENSE).

Generated study packages reference third-party artworks and sources. Respect the rights of each image and institution: the image stage records license / rights status per candidate and defaults missing rights to `restricted`.
