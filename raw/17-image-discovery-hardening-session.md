---
type: session-handoff
phase: 3
title: "E2E hardening + image-discovery overhaul + source-hierarchy research"
date: 2026-06-20
tags:
  - "session-handoff"
  - "phase/3"
---

# Session 17 — E2E hardening + image-discovery overhaul

> [!abstract] TL;DR
> First full end-to-end run of the built skill (Paul Klee), then a chain of fixes and a
> redesign of the image-discovery stage, plus a NotebookLM deep-research ([[16.1-image-source-hierarchy]])
> to settle the source hierarchy. **11 commits to `main` (`64b3ecf` → `cf13b32`), 133 tests pass.**
> Ends mid-task: the user approved building a **Wikidata Tier-1 discovery source + speccing it in
> the wiki**, which was NOT started. That is the immediate next action.

## Status

- Skill build remains complete; this session was E2E validation → hardening → image-stage redesign → research.
- Two real artists exercised end to end: **Paul Klee** (full 8-stage run) and **Joan Miró** (stages 1–5 + routing/image tests). Both study packages live under `studies/` (gitignored runtime output).
- All four Klee E2E findings fixed; several new bugs found and fixed along the way.
- Image discovery was reframed from "download PD files" to a **two-phase model** (browse a thumbnail board → resolve rights/high-res only for selected works), but the *board source* is still AIC-only — the agreed fix (Wikidata) is pending.

## What happened (in order)

### 1. E2E run on Paul Klee → 4 findings
Ran all 8 stages; emitted the full output contract. Findings (see memory `e2e-test-paul-klee.md`):
1. `source-grades.md` leaked a raw regex (`\$\s?\d[\d,]*`) in the commerce-signals line.
2. `prompts/` was in the output contract but no stage populated it.
3. Tag-taxonomy drift: script emitters wrote bare `study/<type>` instead of the `#artist/…` taxonomy.
4. Klee (d. 1940) is in copyright → priority-museum CC0/IIIF path returns ~no public-domain images.

### 2. Fixes #1 & #2 — `64b3ecf`
Commerce patterns now carry human labels; added `scripts/prompts.py` (`save_prompt`) and wired stages 5 & 7 to populate `prompts/`. TDD.

### 3. Fix #3 (tag taxonomy) — `3b42814`
Extracted shared `scripts/_md.py` (`frontmatter` + `cell`); all emitters now tag `#artist/<slug>` + `#<doc-type>` (source-grades keeps `#source-grade/<tier>`). Cleared the rule-of-three extraction debt.

### 4. Markdown reflow + guidance — `fe6971b`
"Extra newlines" in `report.md` were hard-wraps (Obsidian renders every newline as `<br>` by default). Reflowed Klee `report.md`/`works.md` to one physical line per paragraph/list-item; added a SKILL.md note: **don't hard-wrap body text**.

### 5. `.env.example` — `fcafa4b`
Template for `FIRECRAWL_API_KEY`. Negated `!.env.example` in repo `.gitignore` (the user's global gitignore has `.env.*`); real `.env` stays ignored.

### 6. Fix #4 — Commons fallback — `e2810c1`
`scripts/commons.py` (`discover_commons` + pure `parse_commons_search`): MediaWiki API fallback yielding validated PD `ImageCandidate`s for the existing download path; screens non-image mediatypes (the PDFs that errored in the Klee run). Wired as the IIIF fallback in SKILL.md stage 5.

### 7. README — `c7d8132`
Full README: what the skill is, the 8-stage human-in-the-loop pipeline, install/use, the LLM-Wiki layout, development. MIT.

### 8. Live Firecrawl Stage 2 + WebFetch-first routing — `5dcd94d`
The Firecrawl path was fixture-tested but **never run live** — it crashed on the real API (`'DocumentMetadata' object has no attribute 'get'`: firecrawl-py v4 returns a pydantic metadata model, not a dict). Fixed `normalize_scrape` (coerce via `model_dump`, read snake_case `url`/`status_code`).
Live eval on 5 Klee sources: **WebFetch is blocked (403/429) on the highest-value sites** (Smarthistory, Met, MoMA); **Firecrawl got 5/5 at 1 credit each**. SKILL.md stage 2 now fetches **WebFetch-first, Firecrawl on block/empty**.

### 9. Miró routing + image-stage tests (no commits — `studies/` gitignored)
- Stage 2 routing validated on a second artist: WebFetch served 2/6 (Tate, 1stDibs), Firecrawl escalated the 4 blocked (Met/MoMA/NGA/Artsy) — 4 credits vs 6. Pattern holds across artists.
- Image stage on Miró (d. 1983, ~all in copyright): Commons fallback degraded gracefully (5/10 works → 0); only PD result was the public sculpture *Woman and Bird* (FoP). Surfaced a precision bug → next item.

### 10. Commons artist-attribution guard — `a68a587`
Commons free-text search returned wrong-artist PD hits (Velázquez's *Philip IV as a Hunter* for Miró's *The Hunter*). `discover_commons`/`parse_commons_search` now take `artist=` and keep a candidate only if the accent-folded surname/full-name is in title / Categories / ObjectName. Conservative (can drop correct files that don't name the artist).

### 11. Thumbnail curation board — `522886b`
"Gallery count too small" → root cause was conflating *browse* with *download*. Reframed stage 5 to **two phases**: (1) browse a board of MANY hotlinked museum thumbnails (copyright-agnostic, like image search); (2) resolve rights/high-res only for SELECTED works. Added `scripts/museum_search.py` (`search_aic` → `ThumbnailCandidate`) and `gallery.build_thumbnail_gallery` (remote-thumbnail board: rating + gate + PD/© badge + liked/PD filters).

### 12. AIC precision fix — `f0afdf9`
"A lot of those images are other artists" → AIC `query[match][artist_title]` is a fuzzy token match (pulled in every other "Paul" — Cézanne/Gauguin/Rubens — which also faked a high PD count). Fix: resolve the artist to an AIC **agent id** by exact title match (trap: `agents/search` ranks "Zentrum Paul Klee" first), query by `artist_ids`; surname guard backstops the fallback. Clean live counts: **Klee 97 / Miró 70, both 0 PD**.

### 13. "Fish Magic & The Goldfish missing" → diagnosis (no commit)
Confirmed both are **not in AIC** (*Fish Magic* → Philadelphia Museum of Art; *The Goldfish* → Hamburger Kunsthalle); the board is AIC-only. Verified a **Wikidata** query (`creator P170 = Q44007`) returns **671 Klee works, 525 with images, across every museum** — and catches both. This motivated the research below.

### 14. NotebookLM deep research — root 16 — `cf13b32`
Topic: source hierarchy for cross-museum image discovery. `raw/16-image-source-hierarchy-prompt.md` + `raw/16.1-image-source-hierarchy.md` (73 sources). Notebook added to the CLAUDE.md topic map (`16` → `8260e980-d7cc-42f3-9c4f-4c24e054221f`).

## Key decisions

- **Two-phase image discovery.** Browse on many thumbnails (rights-agnostic, hotlinked); apply rights/high-res download only to the human-selected works. Copyright posture: thumbnails ≤843px for private curation; high-res only on a verified PD/CC0 flag.
- **Fetch routing.** WebFetch first (free); escalate to Firecrawl only on 403/429/empty. Museums/scholarly sites bot-block WebFetch, so escalation is the norm for the best sources — but credit spend stays proportional.
- **Source hierarchy** (from [[16.1-image-source-hierarchy]]): **T1 Wikidata** (identity/pivot, `creator P170`, QID dedup) · **T2 Met / AIC / Cleveland** (high-res + machine-readable rights) · **T3 Wikimedia Commons (SDC) / Europeana** (discovery) · **T4 DPLA / Google Arts / WikiArt / Google-Bing image search** (discovery-only, no rights). Combine: discover broad → resolve to QID → back-reference to a T2 record → dedup (institutional supersedes) → high-res only when CC0 verified.

## New modules / APIs this session

- `scripts/prompts.py` — `save_prompt`.
- `scripts/_md.py` — shared `frontmatter` + `cell`.
- `scripts/commons.py` — `discover_commons` / `parse_commons_search` (PD/CC0; `artist=` guard; mediatype screen).
- `scripts/museum_search.py` — `search_aic`, `resolve_aic_agent`, `pick_agent`, `parse_aic_search` → `ThumbnailCandidate`.
- `scripts/gallery.py` — added `build_thumbnail_gallery`.
- `scripts/firecrawl_fetch.py` — `normalize_scrape` coerces firecrawl-py v4 metadata.
- Memory updated: `e2e-test-paul-klee.md` (all four findings + later fixes), `MEMORY.md` index.

## Open questions / next steps

> [!important] Immediate next action (approved, not started)
> **Build the Wikidata Tier-1 discovery source and spec it in `wiki/stage-image-discovery.md`.**
> - Query `?work wdt:P170 wd:<artistQID>`; pull `P18` (image) + `P195` (collection) + label; thumbnail via Commons `Special:FilePath/<file>?width=400`; carry the QID as the dedup key.
> - Resolve the artist name → QID first (Wikidata search/`wbsearchentities`, pick the human/painter entity — beware foundation/namesake collisions, same trap as the AIC agent lookup).
> - Make Wikidata the **board's primary** source; AIC/Met/Cleveland become **T2 high-res resolvers** for selected works. This directly fixes the missing-paintings problem and ~5×'s coverage (Klee 97 → ~525).
> - TDD: pure SPARQL-response parser fixture-tested; injected network boundary. Update the stage note's "Skill design implications".

Other deferred (lower priority):
- **Post-curation high-res resolver:** selected works → download PD/CC0 (Commons/IIIF) into `images/selected/`, else keep `source_url`. `apply_selection` still assumes local candidate files, so the board → selected-download handoff needs this resolver before curation flows into stages 6–8.
- **More T2 museums** in the resolver (Met, Cleveland) + cross-source dedup by Wikidata QID.
- Recover Commons-guard recall via Wikidata `creator` / category-tree (the guard is precision-first today).
- Pre-existing deferred sweep (from `skill-build-status` memory): tuple-ize frozen-dataclass `list` fields; quote `artist:` YAML scalar; `selection.validate_selection` empty-`image_rel` flag; Scrapy bulk download.

## Pointers
- Research: [[16.1-image-source-hierarchy]] · prompt `raw/16-image-source-hierarchy-prompt.md`.
- Prior handoffs: `raw/09-phase-1-research-session.md`, `raw/14-phase-2-wiki-session.md`.
- Skill spec: `docs/superpowers/specs/2026-06-19-artist-study-kit-skill-design.md`.
