# Research prompt — Web scraping & content-extraction tooling for a Python art-research project

I'm building a Python tool (managed with `uv`) that researches historical artists by gathering material from the open web. I need to standardize on **one primary scraping/extraction stack**. Recommend the best choice and a fallback.

The workload has three distinct jobs:
1. **Clean article-text extraction** from art-history pages, museum essays, and blogs — stripping ads, nav, and SEO boilerplate ("anti-slop" main-content extraction).
2. **Crawling/discovery** across museum and institutional sites, some JavaScript-heavy, to find pages about specific artworks.
3. **High-resolution image discovery and download** from museum/open-access sources, capturing source URL and metadata (IIIF awareness is a plus).

Evaluate and compare these candidates: **Firecrawl, Crawl4AI, Scrapy, Playwright, trafilatura** (and name any strong alternative I've missed, e.g. newspaper3k, MarkItDown, httpx+selectolax).

For each, assess: Python-native fit and ease with `uv`; handling of JavaScript-rendered pages; quality of main-content/markdown extraction; crawling scale and politeness (robots.txt, rate limiting); image extraction support; whether it's a local library vs. a hosted/paid API; licensing and cost; maintenance and community health; and suitability for LLM-agent pipelines.

Cover the legal/ethical baseline: robots.txt, terms-of-service, and ethical use of museum/public-domain image sources.

Conclude with: (a) a single recommended primary tool with rationale, (b) a recommended secondary/fallback tool, (c) when to combine tools, and (d) a minimal example architecture for the three jobs above. Cite institutional or authoritative sources where possible.
