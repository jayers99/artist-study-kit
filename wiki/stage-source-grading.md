---
title: "Source Grading — separating scholarship from slop"
type: wiki/stage
stage: 2
sources: [02.1-source-quality-grading, 01.1-web-scraping-tooling]
tags: [wiki/stage, source-grade/a]
aliases: []
---

# Source Grading

> [!info] Pipeline role
> Discover web sources for the artist, fetch them, and grade each for study-worthiness.
> Emits `sources/sources.json` + `sources/source-grades.md`.

## What the research says

The grading rubric, tiers, and machine-detectable signals are captured in
[[concept-source-trust-signals]] (from [[02.1-source-quality-grading]]): lateral
reading/SIFT over CRAAP, a weighted rubric (authority 30 / depth 25 / commercial-bias 20 /
citations 15 / usability 10), a five-tier scale, and scrapeable cues (commerce strings, TLD
nuance, citation tags, image density, language).

**Fetching** is the mechanism behind grading. [[01.1-web-scraping-tooling]] standardizes on
**Firecrawl** (managed, markdown-first, `/map` for discovery, `/scrape` with
`only_main_content`); **Crawl4AI** fallback; **Scrapy** for large image jobs. Markdown
output is what makes a page gradable by an LLM and detectable for signals.

## Open questions / tensions

- **Auction houses** (Tier 3): genuinely useful for provenance/market data yet poor for
  learning — grade them low overall but *retain* the factual fields for
  [[stage-works-inventory]].
- Signals are heuristics — a scholarly site can carry ads; weight signals, don't hard-gate.
- Where does grading run: cheap signal scan first, LLM "close-looking" judgment only on
  the survivors? (Cost vs accuracy.)

## Skill design implications

- Two-pass grader: (1) cheap machine-signal scan on fetched markdown → tier guess;
  (2) LLM rubric scoring on borderline/high-value pages → 1–100 score + tier + rationale.
- Emit `source-grades.md` with per-source score, tier, the triggering signals, and a
  one-line "use it for X / avoid for Y" note (esp. auction = facts-only).
- Persist a structured `sources.json` (url, tier, score, signals, fetch metadata) so other
  stages can filter by trust.
- Use Firecrawl for discovery+scrape; keep the high-trust shortlist (Smarthistory, Met,
  CAA) as seed domains.
