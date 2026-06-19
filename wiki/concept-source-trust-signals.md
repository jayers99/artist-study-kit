---
title: "Source Trust Signals"
type: wiki/concept
sources: [02.1-source-quality-grading]
used-by: [stage-source-grading, stage-background-research, stage-works-inventory]
tags: [wiki/concept, source-grade/a, source-grade/f]
aliases: ["Lateral Reading", "SIFT", "Anti-slop signals"]
---

# Source Trust Signals

Machine-observable and human heuristics for grading art-history web sources. Source:
[[02.1-source-quality-grading]]. Used by [[stage-source-grading]] (the grading engine),
and as a filter in [[stage-background-research]] and [[stage-works-inventory]].

## Method shift: lateral reading

Move from vertical reading (judging a site from inside it) and the CRAAP test toward
**SIFT** (Stop, Investigate the source, Find better coverage, Trace claims) and
**art-historical lateral reading** — leave the site to verify author standing, funding,
and claims. Watch for "closed loops" (a site citing only its own posts).

## Weighted rubric

| Criterion | Weight |
|---|---|
| Institutional authority (terminal degrees, accredited museum/university) | 30% |
| Depth & scholarly originality ("close looking", >1,000-word essays) | 25% |
| Commercial bias & purpose (non-profit mission vs affiliate/print sales) | 20% |
| Accuracy & citation quality (external bibliography vs internal loops) | 15% |
| Usability & ad density (many high-res images vs ad-saturated thumbnails) | 10% |

## Tiers

1. Scholarly/institutional (gold) — e.g. Smarthistory · 2. Useful-but-limited (silver) —
e.g. *caa.reviews* · 3. Reference/data-only (bronze) — auction houses (facts only) ·
4. Commercially biased (poster/affiliate) · 5. Low-quality SEO farms (avoid).

## Machine-detectable cues

- **Commerce strings:** `Add to Cart`, `Buy Print`, `Shopping Cart 0`, `12% Commission`.
- **TLD nuance:** `.edu`/`.gov` high-trust; `.org` no longer definitive.
- **Citation tags:** `<footer>`, `<section id="references">`, "Recommended Citation".
- **Visual complexity:** high `<img>`-per-article ratio (Smarthistory ~50+/object).
- **Language cues:** low-trust ("monetization", "buyer's guide", "trending"); high-trust
  ("visual analysis", "historiography", "provenance", "peer-reviewed").

High-trust shortlist: **Smarthistory**, **The Met (Heilbrunn Timeline)**, **CAA**,
university digital commons.
