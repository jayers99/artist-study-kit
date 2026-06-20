---
title: "Divergent–Convergent Thinking"
type: wiki/concept
sources: [21.1-divergent-convergent-strategic-partner-framework, 21.2-llm-creativity-vs-human-cognition-benchmark]
used-by: [stage-curation, stage-curation-interview, stage-visual-analysis]
tags: [wiki/concept, learning/creativity]
aliases: ["Divergent Thinking", "Convergent Thinking", "Variation–Selection", "Semantic Distance"]
---

# Divergent–Convergent Thinking

Two complementary modes of the creative cycle. **Divergent** = generate many, semantically
*distant* ideas (the "variation"/exploration phase). **Convergent** = identify the single
unifying idea that links the distant nodes and evaluate it against intent (the
"selection"/synthesis phase). Sources: [[21.1-divergent-convergent-strategic-partner-framework]]
(a prompting protocol) and [[21.2-llm-creativity-vs-human-cognition-benchmark]] (a human-vs-LLM
benchmarking review). These are **meta sources** — about LLM/human creativity, not art pedagogy
— so they contribute a cognitive *frame* the pipeline already instantiates, not domain method.

## The frame: variation → selection

The creative cycle runs `nebulous → divergent exploration → convergent selection → plan`
([[21.1-divergent-convergent-strategic-partner-framework]]). Divergent quality is measured by
**semantic distance** (the Divergent Association Task); convergent quality by finding the right
linking concept (the Remote Associates Test).

## Why it matters for a study tool: the human owns selection

The benchmarking ([[21.2-llm-creativity-vs-human-cognition-benchmark]]) is blunt about the
division of labor:

- LLMs match or beat the **average** human on divergent tasks but stay below the **top decile**
  — a persistent "creative ceiling."
- AI creativity is currently a **variation phase without an autonomous selection phase**
  (selection requires evaluation grounded in personal experience and intent).
- Over-aligned models **homogenize** output and collapse toward attractor tokens (GPT-4-turbo
  repeated "ocean" in 90% of sets), narrowing idea diversity.

Implication for artist-study-kit: keep the **human as the convergent decider**; the AI scaffolds
divergent options but must not hand over the converged answer. This is the same contract as
[[concept-desirable-difficulty]] — handing over the selection inflates retrieval strength and
short-circuits learning.

## Where the pipeline instantiates it

- **Narrowing funnel** ([[stage-curation]]) — the wide thumbnail board is the divergent search;
  the staged narrowing (small grid → large two-up → ≤3–4) is convergent selection. The human
  converges, not the AI.
- **Coverage, not redundancy** ([[stage-curation-interview]]) — steering each new study brief
  *away* from lessons already confirmed (contour-rhythm / facial-economy / opposed-geometries
  kept distinct) is literally **maximizing semantic distance across the study set** — the
  divergent metric applied to lessons instead of words.
- **Drill ideation** ([[stage-visual-analysis]]) — generate semantically varied drill options
  (divergent), then converge on the few that isolate the work's anchor trait.

## Implementation tactic (lower altitude)

When the skill *itself* ideates — candidate readings in the interview, drill variants, study
options — divergent diversity can be tuned: high temperature + **min-p** (dynamic-truncation)
sampling, and prompts that "vary etymology" or scan a thesaurus, raise semantic distance;
"meaning opposition" (antonyms) backfires because opposites sit close in latent space
([[21.1-divergent-convergent-strategic-partner-framework]],
[[21.2-llm-creativity-vs-human-cognition-benchmark]]). Treat as a knob, not a principle.
