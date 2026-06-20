---
title: "Works Inventory — selecting and ranking what to study"
type: wiki/stage
stage: 4
sources: [12.1-works-inventory-method, 03.1-museum-image-apis]
tags: [wiki/stage]
aliases: []
---

# Works Inventory

> [!info] Pipeline role
> Produce a ranked, clustered inventory of the artist's key works — doubling as a study
> sequence — with per-work metadata. Emits `analysis/selected-works.md` (candidate list).

## What the research says

[[12.1-works-inventory-method]] defines **importance** multidimensionally: technical
innovation, representativeness, scholarly/exhibition validation (ground-truth collections —
Louvre, Uffizi, Met), and historical influence. Authority hierarchy: **catalogues
raisonnés** (the absolute inventory; scrutinize "workshop"/"school-of") → museum catalogues
→ historical documentation.

The key distinction is **important vs studyable**: historical fame ≠ pedagogical value. A
studyable work has clarity of form, economy of means, a manageable palette/technique, and —
critically — **high-resolution reference** so the student can see "paint as mark and
material" (image availability comes from [[concept-iiif]] / [[stage-image-discovery]]).

Works cluster into a **pedagogical sequence** (drawing/Bargue → cast/value → master copy
→ full color/composition) and by technical theme (value & edges, color temperature,
anatomy).

## Open questions / tensions

- The source is **opinionated toward 19th-c. French academic realism**; the method's
  ranking criteria must generalize to other periods/artists without importing that bias.
- "Importance" and "studyability" can conflict — the inventory should carry *both* scores,
  not collapse them.
- Reference-quality scoring depends on [[stage-image-discovery]], which runs later → first
  pass estimates availability, refine after fetch.

## Skill design implications

- **Per-work metadata schema:** title, date, medium, dimensions, collection, primary
  technical lesson, difficulty tier (1–4), reference-quality/availability, early-vs-late
  development tag, source page(s).
- Score each work on **two axes** (art-historical importance + studyability) via a weighted
  rubric; let curation ([[stage-curation]]) sort by either.
- Output a **clustered, ranked** list that reads as a study progression (general→specific).
- Pull provenance/market facts from auction (Tier 3) sources, weighting them by the
  [[concept-source-trust-signals]] tiers that [[stage-source-grading]] assigns; pull image
  availability from museum APIs ([[concept-iiif]]).
