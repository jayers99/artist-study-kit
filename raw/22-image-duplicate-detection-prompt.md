# 22 — Image duplicate detection (perceptual similarity) — research prompt

**Goal:** choose a Python package for near-duplicate image detection to back the deferred
duplicate-handling-on-re-query spec. As the artist-study-kit gallery grows across discovery
runs + custom-image imports, we need to decide whether a newly-found image is the *same
artwork* as one already on the board, so a starred work isn't re-added unstarred.

## Research question

What is the best Python library/approach to compare two images and return a single
similarity score (float 0–1) representing whether they depict the **same artwork**,
robust to differences in **resolution, crop, JPEG quality/compression, color cast, and
watermarks** across museum/web sources? It must support a tunable **threshold** for a
binary duplicate / not-duplicate decision.

## Cover

1. **Approaches compared**: perceptual hashing (`imagehash` — aHash/pHash/dHash/wHash,
   Hamming distance → normalized score), deep-feature embeddings (CLIP / image-encoder
   cosine similarity, e.g. `sentence-transformers`, `open_clip`, `img2vec`), structural
   metrics (SSIM via `scikit-image`), and turnkey libraries (`imagededup`,
   `difPy`, `perception` by Thorn). Strengths/weaknesses of each for the constraints above.
2. **Robustness**: which approach best tolerates size/quality/crop/color/watermark variation
   while still distinguishing genuinely different artworks (low false-positive rate)?
3. **Score → threshold**: how each method yields a 0–1 score and typical threshold values;
   guidance on calibrating a threshold for "same artwork".
4. **Practical**: install/deps (pure-Python vs model download vs GPU), speed, offline use,
   maintenance/maturity, license. Note any that pair a fast hash pre-filter with an
   embedding confirm.
5. **Recommendation**: a primary pick + fallback, with the reasoning, for this exact
   "two images → float 0–1 → threshold" duplicate-detection use case.
