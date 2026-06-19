# Research prompt — A grading rubric for evaluating art-history web sources for serious study

I'm building a tool that researches historical artists and must **score web sources by quality for learning and master-study preparation**, not for shopping or SEO traffic. Design a practical, reusable grading rubric.

Context: art websites vary wildly. Many are low-value — ad-saturated, SEO-driven, poster/print shops, or shallow aggregation. Auction-house pages can hold useful provenance and market data but are usually weak as general learning sources. I want to reliably separate high-trust scholarly sources from commercial or low-signal ones.

Produce:
1. **A scoring rubric** with weighted criteria, including: institutional authority (museum, university, library); art-historical depth and originality vs. aggregation; accuracy and citation quality; image quality and usefulness; ad density and page usability; commercial bias (poster/print sales, auction/market orientation); and overall suitability for study.
2. **Tier definitions** mapping scores to labels: high-trust, useful-but-limited, image/reference-only, commercially-biased, and low-quality/avoidable.
3. **Detectable signals** — concrete, machine-observable heuristics an LLM or scraper could use to estimate each criterion (e.g. domain type/TLD, presence of citations or bibliography, ad/tracker density, "buy print" or auction-lot markers, word count vs. boilerplate, structured metadata).
4. **A shortlist of consistently high-trust domains/source types** in art history (major museums, IIIF providers, university art-history departments, scholarly catalogues, reputable encyclopedias).

Ground the rubric in established source-evaluation and information-literacy frameworks (e.g. CRAAP, lateral reading, library research guides) and adapt them to the art-history domain. Conclude with a compact one-page scoring template I can apply per source and a worked example grading two contrasting sites.
