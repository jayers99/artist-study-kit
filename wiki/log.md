---
title: "Wiki Log"
type: wiki/log
tags: [wiki/log]
---

# Wiki Log

Append-only, chronological record of wiki operations (ingest · query · lint), per the LLM-Wiki method (`/Users/jayers/code/public_shuttle/prompts/llm-wiki.md`). Newest at the bottom. Entry prefix is grep-able: `grep "^## \[" wiki/log.md | tail -5`. Deeper session narrative lives in the `raw/` session handoffs (09, 14, 15, 17).

## [2026-06-19] ingest | Phase 2 wiki stand-up (raw 01–13)
Stood up the synthesis layer: index + 8 stage notes + 6 concept notes from the 11-topic research corpus. Design: [[10-wiki-synthesis-design]]; handoff [[14-phase-2-wiki-session]].

## [2026-06-20] ingest | 16.1 image source hierarchy
Wired [[16.1-image-source-hierarchy]] into [[stage-image-discovery]] — tiered source hierarchy (T1 Wikidata identity layer → T2 Met/AIC/Cleveland high-res+rights → T3 Commons/Europeana → T4 discovery-only), QID as cross-source dedup key.

## [2026-06-20] ingest | UAT + feature-requests + study-dimensions (raw 18, 19, 20)
Batch ingest of three sources added since Phase 2.
- [[18-uat-feedback]] (F6) → **new** [[stage-curation-interview]] (Socratic interview → `study-briefs`); refocused [[stage-curation]] to pure visual rating; F1/F3/F5 hardening folded into [[stage-image-discovery]] open questions; wired [[concept-desirable-difficulty]] + [[concept-worked-example-fading]] to the new stage.
- [[19-stateful-runs-custom-images-staged-analysis]] → stateful/resumable multi-run + custom-image injection added to [[stage-image-discovery]]; narrowing-funnel (≤3–4, progressive zoom) added to [[stage-curation]] / [[stage-visual-analysis]] / [[stage-curation-interview]] as open questions (feature request, not yet decided).
- [[20-dimensions-of-study-cheat-sheet]] → enriched [[concept-formal-analysis-taxonomy]] (18-dimension + core-12 taxonomy, translation-to-study layer) and [[stage-visual-analysis]].
Touched 9 wiki pages + index. Pipeline now 9 stage notes; concepts unchanged at 6.
