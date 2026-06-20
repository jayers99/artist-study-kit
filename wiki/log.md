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

## [2026-06-20] lint | health check + backlink repair
Clean: no dangling links, no orphans, all `sources:` resolve, every `NN.1` report referenced. Fixed bidirectional `used-by` drift between concepts and stages: dropped stale `stage-curation` from [[concept-worked-example-fading]] (its use moved to [[stage-curation-interview]] in the F6 refocus) and added the missing backlinks ([[stage-style-definition]], [[stage-visual-analysis]]); restored intended concept backlinks in [[stage-works-inventory]] ([[concept-source-trust-signals]]) and [[stage-visual-analysis]] ([[concept-spaced-repetition]]); linked [[concept-formal-analysis-taxonomy]] from [[stage-curation-interview]]. Aligned index numbering (6a/6b) and the worked-example-fading annotation. Two pre-existing drifts predated this session's ingest.

## [2026-06-20] ingest | 21.1 + 21.2 divergent/convergent thinking
Ingested two NotebookLM reports from the "Divergent/convergent Thinking" notebook (new raw root **21**, no prompt doc — not from the research pipeline): [[21.1-divergent-convergent-strategic-partner-framework]] (a prompting protocol) and [[21.2-llm-creativity-vs-human-cognition-benchmark]] (human-vs-LLM creativity benchmarking). These are **meta** sources (about LLM/human creativity, not art pedagogy), so they contribute a cognitive *frame* the pipeline already instantiates.
- **New** [[concept-divergent-convergent-thinking]] (variation→selection; semantic distance; creative ceiling; human owns the convergent selection). used-by: curation, curation-interview, visual-analysis (clears the rule-of-three promotion bar).
- [[stage-curation]] — narrowing funnel reframed as a divergent→convergent cycle (human converges).
- [[stage-curation-interview]] — grounded the "coverage, not redundancy" rule as *maximizing semantic distance across the study set* (DAT applied to lessons).
- [[stage-visual-analysis]] — drill ideation as a divergent→convergent pass.
- [[concept-desirable-difficulty]] — cross-linked: AI lacks an autonomous selection phase, so handing over the converged answer is the retrieval-strength anti-pattern.
- Index: concept list + raw corpus (new "Creativity / cognition (meta)" line) + source→stage map (2 rows). Touched 6 wiki pages + index; pipeline unchanged at 9 stages; concepts 6 → 7.
