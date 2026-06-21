# artist-study-kit

> Turn a historical artist's name into a structured **studio-prep study package** — background, graded sources, visual grammar, ranked works, high-res reference images, human curation, deep formal analysis, and spaced study drills.

![License: MIT](https://img.shields.io/badge/License-MIT-green.svg)
![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)
![Obsidian vault](https://img.shields.io/badge/Obsidian-vault-7c3aed.svg)
![Built with Claude Code](https://img.shields.io/badge/built%20with-Claude%20Code-d97757.svg)

`artist-study-kit` is a **Claude skill**. Point it at a historical artist and it assembles everything a painter needs to do a serious *master study* — the art-historical homework and the high-resolution reference — organized into a navigable Obsidian vault, with the taste-driven choices left to you.

It runs on a deliberate division of labour:

- **Claude does the art-historical judgment** — biographical research, source grading, visual-grammar definition, works selection, a Socratic curation interview, formal analysis, and study pedagogy.
- **Deterministic Python does the plumbing** — a resumable, multi-run state machine, source-trust scoring, Wikidata/IIIF/Commons image discovery and polite download, a persistent-star curation gallery with a narrowing zoom funnel, ranking, and Obsidian-native emission.
- **You make the taste calls** in one curation pass — star and select candidates, then narrow to the final few (≤4) to study deeply.

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
│   ├── candidates/         # locally-cached thumbnails (board renders offline)
│   ├── user/               # your own imported images (origin:"user"), if any
│   └── selected/           # high-res for the narrow study set only
├── gallery.html            # standalone curation gallery → narrowing zoom funnel (Human Pause 1)
├── stars.json              # persistent 1–5★ ratings (survive every run; ⊥ selection)
├── selection.json          # the wide cut you selected this session
├── study-set.json          # the ≤4 narrow cut you committed to study deeply
├── study-briefs.json/.md   # per-work study briefs from the Socratic curation interview
├── preference-synthesis.md # the pattern across your study set + a ranked funnel
├── analysis.md             # 5-stage formal analysis of your chosen study set
├── study-notes.md          # faded-aid notes (cheat sheet → checklist → bare prompt)
├── drills/                 # perceptual discrimination cards (is-A / is-not-A)
├── review-schedule.md      # spaced + interleaved review plan
├── prompts/                # the prompts used, for reproducibility
└── state.json              # resumable, multi-run pipeline state
```

Markdown is vault-friendly throughout: YAML frontmatter, `[[wikilinks]]`, a tag taxonomy (`#artist/…`, `#movement/…`, `#source-grade/…`), and study callouts (`> [!tip]`, `> [!warning]`).

## How it works

A **resumable, idempotent** 9-stage pipeline with two human-in-the-loop pauses. It is no longer a single linear run but a set of **re-enterable operations** (discover · select · study) over a persisted package — re-invoking picks up from `state.json`, discovery can run many times (new candidates **merge**, never duplicate), and one collected board can feed many study sessions (`skip-discovery`). Each stage overwrites its own outputs without disturbing the others.

| # | Stage | Output | Who |
|---|-------|--------|-----|
| 1 | Background | `report.md` (bio + placement) | Claude |
| 2 | Source grading | `sources.json` · `source-grades.md` | Claude + rubric |
| 3 | Style definition | `report.md` (visual grammar) | Claude |
| 4 | Works inventory | `works.md` | Claude |
| 5 | Image discovery | `images/candidates/` · `gallery.html` | scripts (Wikidata → AIC → Commons) |
| ⏸ | **Human Pause 1 — curation funnel** | `stars.json` · `selection.json` · `study-set.json` | **you** — star, select, narrow to ≤4 |
| 6 | Curation interview | `study-briefs.json` · `study-briefs.md` | Claude — Socratic, one work at a time |
| 7 | Preference synthesis | `preference-synthesis.md` (ranked funnel) | Claude + ranking |
| ⏸ | **Human Pause 2 — funnel** | confirmed study set | **you** — confirm the final few |
| 8 | Visual analysis | `analysis.md` | Claude |
| 9 | Study & retention | `study-notes.md` · `drills/` · `review-schedule.md` | Claude |

At **Human Pause 1** the gallery is a two-stage **narrowing zoom funnel**: rate works 1–5★ (a persistent annotation that survives every run) and select a wide cut, then **Next** re-renders only those works at full size for close looking so you can narrow to **≤4** and **Commit**. **Stars and selection are orthogonal** — rating never selects. Everything expensive (high-res download, deep analysis) runs only on the committed study set. You can also **import your own images** of the artist's work — Claude identifies each by vision, the pipeline corroborates the metadata, and a trust gate lets you confirm before they join the board.

The friction is the point. The curation interview, faded study aids, discrimination drills, and spaced schedule are drawn from learning-science and master-copy pedagogy (desirable difficulty, worked-example fading, spaced repetition) — the research behind each is synthesized in `wiki/`.

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

The skill runs the pipeline and stops at the gallery so you can curate (open `gallery.html`, star and select candidates, then zoom in to narrow to the final ≤4 and commit). It then runs a Socratic interview to build a study brief per work, ranks them, and finishes the deep analysis and study aids. Everything lands in `studies/<artist-slug>/`. You can re-invoke "study <artist>" later to run a fresh study session over the same collected board without re-discovering.

## Repository layout — the LLM-Wiki method

The repo follows Karpathy's **LLM-Wiki** pattern: immutable raw sources → an LLM-maintained synthesis → a schema.

| Path | Role |
|------|------|
| `raw/` | Immutable, numbered corpus (35 docs): NotebookLM deep-research reports, decision docs, session handoffs. Append-only — never edited. |
| `wiki/` | LLM-maintained synthesis (index + log + 9 stage + 7 concept notes), interlinked with `[[wikilinks]]`. Entry point: [`wiki/00-index.md`](wiki/00-index.md). Each stage note's "Skill design implications" is the spec input. |
| `skill/` | The deliverable: [`SKILL.md`](skill/SKILL.md) + `scripts/` (22 Python modules). |
| `tests/` | pytest suite — 275 tests, network boundaries injected. |
| `e2e/` | Live end-to-end harnesses (hit the real network; outside pytest). See [`e2e/README.md`](e2e/README.md). |
| `docs/superpowers/` | The skill specs (7) and build plans (10). |
| `CLAUDE.md` | Project schema and conventions (the "schema" layer). |
| `studies/` | Generated per-artist output (gitignored runtime artifact). |

The whole repo also opens as an **Obsidian vault** — open the folder in Obsidian and the `raw/ → wiki/ → study` links are navigable in the graph.

## Development

Built test-first (the repo convention is outside-in TDD with pytest):

```bash
uv run pytest          # 275 tests
```

Conventions live in [`CLAUDE.md`](CLAUDE.md). In short: research stays in `raw/` (numbered, immutable); synthesis in `wiki/`; code in `skill/scripts/` (managed with uv — httpx/Firecrawl network boundaries are injected so tests never hit the network). Web scraping standardizes on Firecrawl; image discovery leads with **Wikidata** as the identity layer (resolves the artist QID + linked works, with PD/CC0 provenance baked in), supplements with the **Art Institute of Chicago** IIIF, and resolves high-res from **Wikimedia Commons** / AIC IIIF for works with a verified public-domain flag. QID is the cross-source dedup key.

## Status

The skill is built and live-validated (foundation → research tooling → curation/study → stateful multi-run, custom-image injection, and the narrowing-funnel curation — all merged). It has been run end-to-end on Paul Klee and Joan Miró, and the funnel pipeline was validated against live Monet data with zero skill bugs. The "automated" stages are executed by Claude under `SKILL.md`; the scripts are the deterministic tooling around that judgment. The main open item is a deferred duplicate-handling-on-re-query spec (see [`TODO.md`](TODO.md)); other follow-ups include Scrapy-based bulk image download.

## License

MIT © 2026 John Ayers — see [LICENSE](LICENSE).

Generated study packages reference third-party artworks and sources. Respect the rights of each image and institution: the image stage records license / rights status per candidate and defaults missing rights to `restricted`.
