# artist-study-kit Research Tooling Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the deterministic Python tooling for Run A's IO-heavy stages — a Firecrawl fetch wrapper, the two-pass source grader (machine signal-scan → rubric scoring → `sources.json`/`source-grades.md`), and IIIF image discovery (manifest/info.json parsing, license + resolution validation, polite download) — plus the Plan 1 carry-forward hardening fixes.

**Architecture:** Pure, importable helpers in `skill/scripts/` that SKILL.md stages call. Every network boundary is **dependency-injected** (the caller passes a client/fetcher), so all logic is tested against recorded fixtures, never live endpoints. The LLM does rubric *judgment* inside SKILL.md; these scripts do the cheap, repeatable, rights-sensitive IO and the deterministic scoring/serialization around that judgment. This plan plugs into the Plan 1 interfaces (`StudyPaths`, `PipelineState`, `parse_frontmatter`); it adds no stage orchestration (that stays in SKILL.md).

**Tech Stack:** Python ≥3.12, uv, pytest, PyYAML, `firecrawl-py` (HTML→markdown), `httpx` (IIIF JSON + image bytes). Scrapy-based bulk download is explicitly deferred (see end).

## Global Constraints

- Python `requires-python = ">=3.12"`; managed with **uv** (`uv run` / `uv add`).
- **Venv lives OUTSIDE iCloud** at `~/.venvs/artist-study-kit`; repo `.venv` is a symlink to it. Recreate with `UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync` then `ln -s "$HOME/.venvs/artist-study-kit" .venv`.
- Skill packaging: `skill/` = `SKILL.md` + `scripts/` (importable package, exposed to pytest via `pythonpath = ["skill"]`). Tests in repo-root `tests/`; fixtures in `tests/fixtures/`.
- **No live network in tests.** Firecrawl, IIIF, and image-byte fetches are injected; tests use recorded fixtures only.
- Stage id this tooling serves (verbatim): `source_grading` (Stage 2) and `image_discovery` (Stage 5).
- Source-grading rubric weights (verbatim from spec §4 Stage 2): authority 30 / depth 25 / commercial-bias 20 / citations 15 / usability 10. Seed high-trust domains: Smarthistory, Met, CAA. Auction/commerce pages = facts-only.
- Image source priority (verbatim from spec §4 Stage 5): Met → Rijksmuseum → AIC → Harvard/Europeana → Wikimedia. Prioritize CC0/public-domain; **treat missing rights as restricted**. Respect robots.txt + throttle.
- Tier taxonomy is `A`–`F` (matches CLAUDE.md `#source-grade/<a-f>` tag).
- Markdown outputs are Obsidian-native: YAML frontmatter + tags + `[[wikilinks]]`.
- TDD: write the failing test first, watch it fail, implement minimally, watch it pass, commit. Use logical `~/iCloud/...` paths in shell; quote paths.

## File Structure

- `skill/scripts/paths.py` (modify) — `slugify()` empty/symbol-only guard.
- `skill/scripts/state.py` (modify) — `from_dict` dedup + `load()` artist-mismatch policy.
- `skill/scripts/firecrawl_fetch.py` (new) — `FetchedPage` + `fetch_page()` (injected client; response normalization).
- `skill/scripts/source_signals.py` (new) — Stage-2 pass 1: deterministic `scan_source()` → `SignalScan`.
- `skill/scripts/source_grades.py` (new) — Stage-2 pass 2 plumbing: weighted score, tier mapping, `sources.json` + `source-grades.md` emitters.
- `skill/scripts/iiif.py` (new) — Stage-5 discovery: IIIF manifest/info.json parsing, rights + resolution validation.
- `skill/scripts/image_download.py` (new) — Stage-5 IO: robots check, polite download, per-image metadata sidecars, idempotent organize.
- `tests/fixtures/` (new) — recorded Firecrawl responses, a sample IIIF manifest + info.json, robots.txt.

---

### Task 1: Plan 1 carry-forward hardening

Close the deferred Minors from the Plan 1 final review before new code depends on these helpers.

**Files:**
- Modify: `skill/scripts/paths.py`
- Modify: `skill/scripts/state.py`
- Test: `tests/test_paths.py`
- Test: `tests/test_state.py`

**Interfaces:**
- Consumes: `slugify`, `StudyPaths` (Plan 1 Task 2); `PipelineState`, `STAGES` (Plan 1 Task 3).
- Produces (behavior changes, signatures unchanged):
  - `slugify(name)` returns `"untitled"` for empty/symbol-only input (never `""`).
  - `PipelineState.from_dict` de-duplicates `completed` preserving first-seen order.
  - `PipelineState.load(path, artist)` raises `ValueError` when `artist` mismatches the stored artist.

- [ ] **Step 1: Write the failing slugify-guard test**

Add to `tests/test_paths.py`:
```python
@pytest.mark.parametrize("name", ["", "   ", "!!!", "...", "@#$"])
def test_slugify_guards_empty_and_symbol_only(name):
    assert slugify(name) == "untitled"


def test_study_paths_root_never_equals_base_for_blank_name():
    sp = study_paths("studies", "   ")
    assert sp.root == Path("studies/untitled")
```

- [ ] **Step 2: Run to verify failure**

Run: `cd "$HOME/iCloud/para/1-projects/artist-study-kit" && uv run pytest tests/test_paths.py -k "guards or never_equals" -v`
Expected: FAIL — `slugify("")` currently returns `""`, so root collapses to the base dir.

- [ ] **Step 3: Add the guard to `slugify`**

In `skill/scripts/paths.py`, change the final line of `slugify`:
```python
    s = re.sub(r"-+", "-", s)
    return s.strip("-") or "untitled"
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_paths.py -v`
Expected: PASS (all paths tests green).

- [ ] **Step 5: Write the failing state-hardening tests**

Add to `tests/test_state.py`:
```python
def test_is_complete_tracks_marked_stages():
    st = PipelineState(artist="x", completed=[])
    assert st.is_complete("background") is False
    st.mark_complete("background")
    assert st.is_complete("background") is True


def test_from_dict_dedupes_completed_preserving_order():
    st = PipelineState.from_dict(
        {"artist": "x", "completed": ["background", "background", "source_grading"]}
    )
    assert st.completed == ["background", "source_grading"]


def test_load_rejects_artist_mismatch(tmp_path):
    p = tmp_path / "state.json"
    PipelineState(artist="Vincent van Gogh", completed=["background"]).save(p)
    with pytest.raises(ValueError):
        PipelineState.load(p, artist="Claude Monet")


def test_load_allows_matching_artist(tmp_path):
    p = tmp_path / "state.json"
    PipelineState(artist="Vincent van Gogh", completed=[]).save(p)
    loaded = PipelineState.load(p, artist="Vincent van Gogh")
    assert loaded.artist == "Vincent van Gogh"
```

- [ ] **Step 6: Run to verify failure**

Run: `uv run pytest tests/test_state.py -k "is_complete_tracks or dedupes or mismatch or matching_artist" -v`
Expected: FAIL — `from_dict` keeps duplicates; `load` ignores the `artist` arg on an existing file.

- [ ] **Step 7: Implement dedup + mismatch policy in `state.py`**

Replace `from_dict` and `load` in `skill/scripts/state.py`:
```python
    @classmethod
    def from_dict(cls, d: dict) -> "PipelineState":
        seen: set[str] = set()
        deduped = [s for s in d.get("completed", []) if not (s in seen or seen.add(s))]
        return cls(artist=d["artist"], completed=deduped)

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")

    @classmethod
    def load(cls, path: Path, artist: str) -> "PipelineState":
        if not path.exists():
            return cls(artist=artist, completed=[])
        state = cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
        if state.artist != artist:
            raise ValueError(
                f"state.json artist {state.artist!r} != requested {artist!r}"
            )
        return state
```

- [ ] **Step 8: Run the full suite**

Run: `cd "$HOME/iCloud/para/1-projects/artist-study-kit" && uv run pytest -v`
Expected: PASS (Plan 1 suite + new hardening tests).

- [ ] **Step 9: Commit**

```bash
git add skill/scripts/paths.py skill/scripts/state.py tests/test_paths.py tests/test_state.py
git commit -m "fix: slugify empty-name guard + state dedup/mismatch policy"
```

---

### Task 2: Firecrawl fetch wrapper

**Files:**
- Create: `skill/scripts/firecrawl_fetch.py`
- Create: `tests/fixtures/__init__.py`
- Test: `tests/test_firecrawl_fetch.py`

**Interfaces:**
- Consumes: nothing from earlier tasks; an injected `client` duck-typed to expose `.scrape(url) -> object` (the `firecrawl.Firecrawl` v4 client).
- Produces:
  - `FetchedPage` (frozen dataclass): `url: str`, `final_url: str`, `status_code: int`, `markdown: str`, `metadata: dict`.
  - `normalize_scrape(url: str, resp: object) -> FetchedPage` — pure; reads `.markdown` + `.metadata` (camelCase `sourceURL`/`url`/`statusCode`), tolerates a `.data` wrapper. Consumed by Tasks 3–4 via fixtures.
  - `fetch_page(url: str, *, client: object | None = None) -> FetchedPage` — calls `client.scrape(url)`; when `client is None`, lazily builds `firecrawl.Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_firecrawl_fetch.py`:
```python
from types import SimpleNamespace

import pytest

from scripts.firecrawl_fetch import FetchedPage, fetch_page, normalize_scrape


def _resp(markdown="# Title\n\nBody", **meta):
    md = {"sourceURL": "https://example.com", "url": "https://example.com", "statusCode": 200}
    md.update(meta)
    return SimpleNamespace(markdown=markdown, metadata=md)


def test_normalize_reads_markdown_and_metadata():
    page = normalize_scrape("https://example.com", _resp())
    assert isinstance(page, FetchedPage)
    assert page.markdown.startswith("# Title")
    assert page.status_code == 200
    assert page.final_url == "https://example.com"


def test_normalize_prefers_final_url_after_redirect():
    page = normalize_scrape(
        "https://example.com/old",
        _resp(url="https://example.com/new", sourceURL="https://example.com/old"),
    )
    assert page.url == "https://example.com/old"
    assert page.final_url == "https://example.com/new"


def test_normalize_tolerates_data_wrapper():
    wrapped = SimpleNamespace(data=_resp(markdown="wrapped"))
    page = normalize_scrape("https://example.com", wrapped)
    assert page.markdown == "wrapped"


def test_normalize_defaults_when_metadata_missing():
    page = normalize_scrape("https://example.com", SimpleNamespace(markdown="x"))
    assert page.metadata == {}
    assert page.status_code == 0
    assert page.final_url == "https://example.com"


def test_fetch_page_uses_injected_client():
    class FakeClient:
        def __init__(self):
            self.calls = []

        def scrape(self, url):
            self.calls.append(url)
            return _resp(markdown=f"scraped {url}")

    client = FakeClient()
    page = fetch_page("https://example.com", client=client)
    assert client.calls == ["https://example.com"]
    assert page.markdown == "scraped https://example.com"


def test_fetch_page_without_client_and_without_key_raises():
    import os

    saved = os.environ.pop("FIRECRAWL_API_KEY", None)
    try:
        with pytest.raises(KeyError):
            fetch_page("https://example.com")
    finally:
        if saved is not None:
            os.environ["FIRECRAWL_API_KEY"] = saved
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_firecrawl_fetch.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.firecrawl_fetch'`.

- [ ] **Step 3: Create the fixtures package marker**

Create `tests/fixtures/__init__.py`:
```python
```

- [ ] **Step 4: Implement `firecrawl_fetch.py`**

Create `skill/scripts/firecrawl_fetch.py`:
```python
"""Thin, testable wrapper over the Firecrawl scrape API (HTML -> markdown).

The network boundary is injected: callers pass a client exposing `.scrape(url)`.
`normalize_scrape` is pure so all parsing is fixture-tested without live calls.
"""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class FetchedPage:
    """A scraped page reduced to what the grader needs."""

    url: str
    final_url: str
    status_code: int
    markdown: str
    metadata: dict


def normalize_scrape(url: str, resp: object) -> FetchedPage:
    """Reduce a Firecrawl scrape response to a `FetchedPage` (pure)."""
    doc = getattr(resp, "data", None) or resp
    markdown = getattr(doc, "markdown", "") or ""
    metadata = getattr(doc, "metadata", None) or {}
    final_url = metadata.get("url") or metadata.get("sourceURL") or url
    status_code = int(metadata.get("statusCode") or 0)
    return FetchedPage(
        url=url,
        final_url=final_url,
        status_code=status_code,
        markdown=markdown,
        metadata=dict(metadata),
    )


def fetch_page(url: str, *, client: object | None = None) -> FetchedPage:
    """Scrape `url` to a `FetchedPage`; build a default client if none given."""
    if client is None:
        from firecrawl import Firecrawl  # lazy: avoids import cost / key need in tests

        client = Firecrawl(api_key=os.environ["FIRECRAWL_API_KEY"])
    return normalize_scrape(url, client.scrape(url))
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_firecrawl_fetch.py -v`
Expected: PASS (all cases green).

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/firecrawl_fetch.py tests/fixtures/__init__.py tests/test_firecrawl_fetch.py
git commit -m "feat: firecrawl fetch wrapper (injected client + response normalization)"
```

---

### Task 3: Source signal-scan (grader pass 1)

The cheap, deterministic first pass over fetched markdown: detect commerce/ad signals, citation markers, TLD trust, and the seed shortlist; emit a coarse band + a "needs LLM review" flag so SKILL.md only spends rubric reasoning where it matters.

**Files:**
- Create: `skill/scripts/source_signals.py`
- Test: `tests/test_source_signals.py`

**Interfaces:**
- Consumes: `FetchedPage` (Task 2).
- Produces:
  - Constants: `SHORTLIST_DOMAINS: frozenset[str]`, `TRUSTED_TLDS: frozenset[str]`, `COMMERCE_PATTERNS: tuple[str, ...]`, `CITATION_PATTERNS: tuple[str, ...]`.
  - `SignalScan` (frozen dataclass): `domain: str`, `tld: str`, `tld_trust: str` (`"trusted"|"neutral"|"commercial"`), `commerce_hits: list[str]`, `citation_count: int`, `shortlisted: bool`, `band: str` (`"high"|"borderline"|"low"`), `needs_llm_review: bool`.
  - `scan_source(page: FetchedPage) -> SignalScan` — pure.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_source_signals.py`:
```python
from scripts.firecrawl_fetch import FetchedPage
from scripts.source_signals import SHORTLIST_DOMAINS, scan_source


def _page(url, markdown):
    return FetchedPage(url=url, final_url=url, status_code=200, markdown=markdown, metadata={})


def test_shortlist_domains_include_seeds():
    assert "smarthistory.org" in SHORTLIST_DOMAINS
    assert "metmuseum.org" in SHORTLIST_DOMAINS


def test_museum_page_scores_high_and_skips_llm():
    md = "Provenance and bibliography. See footnotes [1] [2]. References: catalogue raisonné."
    scan = scan_source(_page("https://www.metmuseum.org/art/collection/123", md))
    assert scan.shortlisted is True
    assert scan.tld_trust == "trusted"
    assert scan.citation_count >= 2
    assert scan.band == "high"
    assert scan.needs_llm_review is False


def test_commerce_page_scores_low_and_skips_llm():
    md = "Add to cart. Buy now. Price: $4,500. Make an offer. Shipping calculated at checkout."
    scan = scan_source(_page("https://auction-house.com/lot/77", md))
    assert scan.commerce_hits  # non-empty
    assert scan.tld_trust == "commercial"
    assert scan.band == "low"
    assert scan.needs_llm_review is False


def test_neutral_page_is_borderline_and_needs_llm():
    md = "An essay about the artist with some discussion and one footnote [1]."
    scan = scan_source(_page("https://some-blog.net/essay", md))
    assert scan.band == "borderline"
    assert scan.needs_llm_review is True


def test_domain_and_tld_parsed_from_url():
    scan = scan_source(_page("https://www.rijksmuseum.nl/en/page", "text"))
    assert scan.domain == "rijksmuseum.nl"
    assert scan.tld == "nl"
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_signals.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.source_signals'`.

- [ ] **Step 3: Implement `source_signals.py`**

Create `skill/scripts/source_signals.py`:
```python
"""Stage-2 pass 1: cheap deterministic signal-scan over fetched markdown.

Flags commerce/citation/TLD signals and a coarse band so SKILL.md only runs the
LLM rubric (pass 2) on borderline or high-value pages.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from scripts.firecrawl_fetch import FetchedPage

SHORTLIST_DOMAINS: frozenset[str] = frozenset(
    {"smarthistory.org", "metmuseum.org", "collegeart.org"}  # Smarthistory, Met, CAA
)

# Generic + national academic/cultural TLDs treated as higher trust.
TRUSTED_TLDS: frozenset[str] = frozenset({"edu", "gov", "museum", "ac.uk"})

COMMERCE_PATTERNS: tuple[str, ...] = (
    r"add to cart",
    r"buy now",
    r"make an offer",
    r"add to basket",
    r"shipping calculated",
    r"\$\s?\d[\d,]*",
    r"estimate:\s*\$",
)

CITATION_PATTERNS: tuple[str, ...] = (
    r"\[\d+\]",
    r"\bfootnotes?\b",
    r"\breferences?\b",
    r"\bbibliography\b",
    r"\bprovenance\b",
    r"catalogue raisonn",
)


@dataclass(frozen=True)
class SignalScan:
    domain: str
    tld: str
    tld_trust: str
    commerce_hits: list[str]
    citation_count: int
    shortlisted: bool
    band: str
    needs_llm_review: bool


def _domain(url: str) -> str:
    host = urlsplit(url).netloc.lower()
    if host.startswith("www."):
        host = host[4:]
    return host


def _tld(domain: str) -> str:
    if domain.endswith(".ac.uk"):
        return "ac.uk"
    return domain.rsplit(".", 1)[-1] if "." in domain else ""


def scan_source(page: FetchedPage) -> SignalScan:
    """Run pass-1 signal detection on a fetched page (pure)."""
    domain = _domain(page.final_url or page.url)
    tld = _tld(domain)
    text = page.markdown.lower()

    commerce_hits = [p for p in COMMERCE_PATTERNS if re.search(p, text)]
    citation_count = sum(len(re.findall(p, text)) for p in CITATION_PATTERNS)
    shortlisted = domain in SHORTLIST_DOMAINS

    if tld in TRUSTED_TLDS or shortlisted:
        tld_trust = "trusted"
    elif len(commerce_hits) >= 2:
        tld_trust = "commercial"
    else:
        tld_trust = "neutral"

    if shortlisted or (tld_trust == "trusted" and citation_count >= 2):
        band = "high"
    elif tld_trust == "commercial" and citation_count < 2:
        band = "low"
    else:
        band = "borderline"

    # Only borderline pages (and high-value-but-unconfirmed) need LLM rubric scoring.
    needs_llm_review = band == "borderline"

    return SignalScan(
        domain=domain,
        tld=tld,
        tld_trust=tld_trust,
        commerce_hits=commerce_hits,
        citation_count=citation_count,
        shortlisted=shortlisted,
        band=band,
        needs_llm_review=needs_llm_review,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_signals.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/source_signals.py tests/test_source_signals.py
git commit -m "feat: source signal-scan (grader pass 1)"
```

---

### Task 4: Source grade model + emitters (grader pass 2 plumbing)

The deterministic plumbing around the LLM rubric: combine the pass-1 scan with LLM-supplied rubric scores into a weighted 1–100 score + A–F tier, and serialize the graded set to `sources.json` (machine) and `source-grades.md` (human, Obsidian-native).

**Files:**
- Create: `skill/scripts/source_grades.py`
- Test: `tests/test_source_grades.py`

**Interfaces:**
- Consumes: `SignalScan` (Task 3); `StudyPaths.sources_json` / `.source_grades_md` (Plan 1 Task 2).
- Produces:
  - `RUBRIC_WEIGHTS: dict[str, int]` = `{"authority": 30, "depth": 25, "commercial_bias": 20, "citations": 15, "usability": 10}`.
  - `RubricScores` (frozen dataclass): `authority: int`, `depth: int`, `commercial_bias: int`, `citations: int`, `usability: int` (each 0–100, supplied by the LLM).
  - `GradedSource` (frozen dataclass): `url`, `title`, `signals: SignalScan`, `rubric: RubricScores | None`, `score: int`, `tier: str`, `use_for: str`, `avoid_for: str`.
  - `weighted_score(rubric: RubricScores) -> int` — weights sum to 100; returns 1–100.
  - `score_to_tier(score: int) -> str` — A≥85, B 70–84, C 55–69, D 40–54, E 25–39, F≤24.
  - `grade_source(url, title, signals, rubric, *, use_for="", avoid_for="") -> GradedSource`.
  - `write_sources_json(sources: list[GradedSource], path) -> None`.
  - `write_source_grades_md(sources: list[GradedSource], artist: str, path) -> None`.

- [ ] **Step 1: Write the failing tests**

Create `tests/test_source_grades.py`:
```python
import json

from scripts.frontmatter import parse_frontmatter
from scripts.source_grades import (
    RUBRIC_WEIGHTS,
    GradedSource,
    RubricScores,
    grade_source,
    score_to_tier,
    weighted_score,
    write_source_grades_md,
    write_sources_json,
)
from scripts.source_signals import scan_source
from scripts.firecrawl_fetch import FetchedPage


def _scan(url="https://www.metmuseum.org/x", md="references [1] [2] provenance"):
    return scan_source(FetchedPage(url=url, final_url=url, status_code=200, markdown=md, metadata={}))


def test_rubric_weights_sum_to_100():
    assert sum(RUBRIC_WEIGHTS.values()) == 100


def test_weighted_score_perfect_is_100():
    perfect = RubricScores(authority=100, depth=100, commercial_bias=100, citations=100, usability=100)
    assert weighted_score(perfect) == 100


def test_weighted_score_is_weighted_average():
    # authority(30)=80, depth(25)=60, commercial_bias(20)=100, citations(15)=40, usability(10)=20
    r = RubricScores(authority=80, depth=60, commercial_bias=100, citations=40, usability=20)
    # 0.30*80 + 0.25*60 + 0.20*100 + 0.15*40 + 0.10*20 = 24+15+20+6+2 = 67
    assert weighted_score(r) == 67


def test_score_to_tier_cutoffs():
    assert score_to_tier(90) == "A"
    assert score_to_tier(85) == "A"
    assert score_to_tier(84) == "B"
    assert score_to_tier(70) == "B"
    assert score_to_tier(55) == "C"
    assert score_to_tier(40) == "D"
    assert score_to_tier(25) == "E"
    assert score_to_tier(24) == "F"
    assert score_to_tier(1) == "F"


def test_grade_source_assembles_score_and_tier():
    r = RubricScores(authority=90, depth=90, commercial_bias=90, citations=90, usability=90)
    gs = grade_source("https://www.metmuseum.org/x", "Met page", _scan(), r, use_for="facts", avoid_for="opinion")
    assert isinstance(gs, GradedSource)
    assert gs.score == 90
    assert gs.tier == "A"
    assert gs.use_for == "facts"


def test_write_sources_json_roundtrips(tmp_path):
    r = RubricScores(authority=80, depth=70, commercial_bias=60, citations=50, usability=40)
    gs = grade_source("https://x.org/a", "A", _scan(), r)
    p = tmp_path / "sources.json"
    write_sources_json([gs], p)
    data = json.loads(p.read_text())
    assert data[0]["url"] == "https://x.org/a"
    assert data[0]["tier"] == gs.tier
    assert data[0]["signals"]["band"] in {"high", "borderline", "low"}
    assert data[0]["rubric"]["authority"] == 80


def test_write_sources_json_handles_ungraded(tmp_path):
    gs = grade_source("https://x.org/skip", "Skip", _scan(), None)
    p = tmp_path / "sources.json"
    write_sources_json([gs], p)
    data = json.loads(p.read_text())
    assert data[0]["rubric"] is None
    assert data[0]["score"] == 0
    assert data[0]["tier"] == "F"


def test_write_source_grades_md_is_obsidian_native(tmp_path):
    r = RubricScores(authority=90, depth=90, commercial_bias=90, citations=90, usability=90)
    gs = grade_source("https://www.metmuseum.org/x", "Met page", _scan(), r, use_for="facts", avoid_for="aesthetic claims")
    p = tmp_path / "source-grades.md"
    write_source_grades_md([gs], "Vincent van Gogh", p)
    text = p.read_text()
    fm = parse_frontmatter(text)
    assert fm["type"] == "study/source-grades"
    assert "#source-grade/a" in fm.get("tags", [])
    assert "Met page" in text
    assert "facts" in text
    assert "aesthetic claims" in text
```

- [ ] **Step 2: Run to verify failure**

Run: `uv run pytest tests/test_source_grades.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.source_grades'`.

- [ ] **Step 3: Implement `source_grades.py`**

Create `skill/scripts/source_grades.py`:
```python
"""Stage-2 pass 2 plumbing: weighted scoring, A-F tiers, and serialization.

The LLM supplies per-dimension rubric scores (0-100) inside SKILL.md; this module
turns them into a weighted score + tier and writes sources.json / source-grades.md.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from scripts.source_signals import SignalScan

RUBRIC_WEIGHTS: dict[str, int] = {
    "authority": 30,
    "depth": 25,
    "commercial_bias": 20,
    "citations": 15,
    "usability": 10,
}

# (lower-inclusive bound, tier), highest first.
_TIER_CUTOFFS: tuple[tuple[int, str], ...] = (
    (85, "A"),
    (70, "B"),
    (55, "C"),
    (40, "D"),
    (25, "E"),
    (0, "F"),
)


@dataclass(frozen=True)
class RubricScores:
    authority: int
    depth: int
    commercial_bias: int
    citations: int
    usability: int


@dataclass(frozen=True)
class GradedSource:
    url: str
    title: str
    signals: SignalScan
    rubric: RubricScores | None
    score: int
    tier: str
    use_for: str
    avoid_for: str


def weighted_score(rubric: RubricScores) -> int:
    """Weighted average of the five rubric dimensions, rounded to 1-100."""
    total = sum(getattr(rubric, dim) * w for dim, w in RUBRIC_WEIGHTS.items())
    return round(total / 100)


def score_to_tier(score: int) -> str:
    for bound, tier in _TIER_CUTOFFS:
        if score >= bound:
            return tier
    return "F"


def grade_source(
    url: str,
    title: str,
    signals: SignalScan,
    rubric: RubricScores | None,
    *,
    use_for: str = "",
    avoid_for: str = "",
) -> GradedSource:
    """Assemble a GradedSource; ungraded (rubric=None) sources score 0 / tier F."""
    score = weighted_score(rubric) if rubric is not None else 0
    return GradedSource(
        url=url,
        title=title,
        signals=signals,
        rubric=rubric,
        score=score,
        tier=score_to_tier(score),
        use_for=use_for,
        avoid_for=avoid_for,
    )


def _source_to_dict(gs: GradedSource) -> dict:
    return {
        "url": gs.url,
        "title": gs.title,
        "score": gs.score,
        "tier": gs.tier,
        "use_for": gs.use_for,
        "avoid_for": gs.avoid_for,
        "signals": asdict(gs.signals),
        "rubric": asdict(gs.rubric) if gs.rubric is not None else None,
    }


def write_sources_json(sources: list[GradedSource], path: Path) -> None:
    """Persist the machine-readable graded source set."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [_source_to_dict(s) for s in sources]
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def write_source_grades_md(sources: list[GradedSource], artist: str, path: Path) -> None:
    """Write the human-readable, Obsidian-native grade report."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tags = sorted({f"#source-grade/{s.tier.lower()}" for s in sources})
    lines = [
        "---",
        "type: study/source-grades",
        f"artist: {artist}",
        f"tags: [{', '.join(tags)}]",
        "---",
        "",
        f"# Source grades — {artist}",
        "",
    ]
    for s in sorted(sources, key=lambda x: x.score, reverse=True):
        signals = ", ".join(s.signals.commerce_hits) or "none"
        lines += [
            f"## [{s.title}]({s.url})",
            "",
            f"- **Tier {s.tier}** · score {s.score}/100 · band `{s.signals.band}`",
            f"- Commerce signals: {signals}; citations: {s.signals.citation_count}",
            f"- Use for: {s.use_for or 'TBD by reviewer'}",
            f"- Avoid for: {s.avoid_for or 'TBD by reviewer'}",
            "",
        ]
    path.write_text("\n".join(lines), encoding="utf-8")
```

- [ ] **Step 4: Run to verify pass**

Run: `uv run pytest tests/test_source_grades.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add skill/scripts/source_grades.py tests/test_source_grades.py
git commit -m "feat: source grade model + sources.json/source-grades.md emitters"
```

---

### Task 5: IIIF discovery + license/resolution validation

Parse IIIF Presentation manifests and Image `info.json` into validated, prioritized image candidates — without downloading bytes. Rights default to restricted when absent; resolution gate uses the IIIF-reported pixel size.

**Files:**
- Modify: `pyproject.toml` (add `httpx`)
- Create: `skill/scripts/iiif.py`
- Create: `tests/fixtures/met_manifest.json`
- Create: `tests/fixtures/met_info.json`
- Test: `tests/test_iiif.py`

**Interfaces:**
- Consumes: nothing from earlier tasks (pure parsing).
- Produces:
  - `INSTITUTION_PRIORITY: tuple[str, ...]` = `("met", "rijksmuseum", "aic", "harvard", "europeana", "wikimedia")`.
  - `ImageCandidate` (frozen dataclass): `work_id`, `institution`, `label`, `iiif_id` (Image API service id), `image_url` (`{id}/full/max/0/default.jpg`), `width`, `height`, `license`, `rights_status` (`"public_domain"|"restricted"|"unknown"`).
  - `classify_rights(value: str | None) -> str`.
  - `max_image_url(iiif_id: str) -> str`.
  - `parse_info_json(info: dict) -> tuple[str, int, int]` → `(iiif_id, width, height)`.
  - `parse_manifest(manifest: dict, *, work_id: str, institution: str) -> list[ImageCandidate]`.
  - `meets_resolution(c: ImageCandidate, *, min_long_edge: int = 1500) -> bool`.
  - `validate_candidate(c: ImageCandidate, *, min_long_edge: int = 1500) -> tuple[bool, list[str]]`.
  - `institution_rank(institution: str) -> int` (lower = higher priority; unknown sorts last).

- [ ] **Step 1: Add httpx**

```bash
cd "$HOME/iCloud/para/1-projects/artist-study-kit"
uv add httpx
```
Expected: `pyproject.toml` `dependencies` gains `httpx`.

- [ ] **Step 2: Create the IIIF fixtures**

Create `tests/fixtures/met_manifest.json`:
```json
{
  "@context": "http://iiif.io/api/presentation/2/context.json",
  "@type": "sc:Manifest",
  "label": "Wheat Field with Cypresses",
  "metadata": [
    {"label": "Rights", "value": "Public Domain"}
  ],
  "sequences": [
    {
      "canvases": [
        {
          "label": "recto",
          "images": [
            {
              "resource": {
                "service": {
                  "@id": "https://images.metmuseum.org/iiif/12345",
                  "@context": "http://iiif.io/api/image/2/context.json"
                },
                "width": 4000,
                "height": 3000
              }
            }
          ]
        }
      ]
    }
  ]
}
```

Create `tests/fixtures/met_info.json`:
```json
{
  "@context": "http://iiif.io/api/image/2/context.json",
  "@id": "https://images.metmuseum.org/iiif/12345",
  "width": 4000,
  "height": 3000
}
```

- [ ] **Step 3: Write the failing tests**

Create `tests/test_iiif.py`:
```python
import json
from pathlib import Path

from scripts.iiif import (
    INSTITUTION_PRIORITY,
    ImageCandidate,
    classify_rights,
    institution_rank,
    max_image_url,
    meets_resolution,
    parse_info_json,
    parse_manifest,
    validate_candidate,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _manifest():
    return json.loads((FIXTURES / "met_manifest.json").read_text())


def _info():
    return json.loads((FIXTURES / "met_info.json").read_text())


def test_priority_order_matches_spec():
    assert INSTITUTION_PRIORITY == ("met", "rijksmuseum", "aic", "harvard", "europeana", "wikimedia")


def test_institution_rank_orders_and_sinks_unknown():
    assert institution_rank("met") < institution_rank("wikimedia")
    assert institution_rank("unknown-museum") > institution_rank("wikimedia")


def test_classify_rights_public_domain_variants():
    assert classify_rights("Public Domain") == "public_domain"
    assert classify_rights("CC0 1.0") == "public_domain"
    assert classify_rights("https://creativecommons.org/publicdomain/zero/1.0/") == "public_domain"


def test_classify_rights_missing_is_restricted():
    assert classify_rights(None) == "restricted"
    assert classify_rights("") == "restricted"


def test_classify_rights_unrecognized_is_unknown():
    assert classify_rights("All rights reserved") == "unknown"


def test_max_image_url_builds_iiif_max_request():
    assert max_image_url("https://images.metmuseum.org/iiif/12345") == (
        "https://images.metmuseum.org/iiif/12345/full/max/0/default.jpg"
    )


def test_parse_info_json_extracts_id_and_dims():
    iiif_id, w, h = parse_info_json(_info())
    assert iiif_id == "https://images.metmuseum.org/iiif/12345"
    assert (w, h) == (4000, 3000)


def test_parse_manifest_yields_candidate():
    cands = parse_manifest(_manifest(), work_id="wheat-field-with-cypresses", institution="met")
    assert len(cands) == 1
    c = cands[0]
    assert isinstance(c, ImageCandidate)
    assert c.institution == "met"
    assert c.work_id == "wheat-field-with-cypresses"
    assert c.iiif_id == "https://images.metmuseum.org/iiif/12345"
    assert c.image_url.endswith("/full/max/0/default.jpg")
    assert (c.width, c.height) == (4000, 3000)
    assert c.rights_status == "public_domain"


def test_meets_resolution_uses_long_edge():
    big = ImageCandidate("w", "met", "l", "id", "u", 4000, 3000, "Public Domain", "public_domain")
    small = ImageCandidate("w", "met", "l", "id", "u", 800, 600, "Public Domain", "public_domain")
    assert meets_resolution(big) is True
    assert meets_resolution(small) is False


def test_validate_candidate_flags_restricted_and_lowres():
    ok = ImageCandidate("w", "met", "l", "id", "u", 4000, 3000, "Public Domain", "public_domain")
    passed, reasons = validate_candidate(ok)
    assert passed is True
    assert reasons == []

    bad = ImageCandidate("w", "met", "l", "id", "u", 500, 400, None, "restricted")
    passed, reasons = validate_candidate(bad)
    assert passed is False
    assert any("rights" in r for r in reasons)
    assert any("resolution" in r for r in reasons)
```

- [ ] **Step 4: Run to verify failure**

Run: `uv run pytest tests/test_iiif.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.iiif'`.

- [ ] **Step 5: Implement `iiif.py`**

Create `skill/scripts/iiif.py`:
```python
"""Stage-5 image discovery: parse IIIF manifests/info.json into validated candidates.

Pure parsing + validation; byte download lives in image_download.py. Rights default
to 'restricted' when absent (spec: treat missing rights as restricted).
"""

from __future__ import annotations

from dataclasses import dataclass

INSTITUTION_PRIORITY: tuple[str, ...] = (
    "met",
    "rijksmuseum",
    "aic",
    "harvard",
    "europeana",
    "wikimedia",
)

_PUBLIC_DOMAIN_MARKERS: tuple[str, ...] = (
    "public domain",
    "publicdomain",
    "cc0",
    "no known copyright",
)


@dataclass(frozen=True)
class ImageCandidate:
    work_id: str
    institution: str
    label: str
    iiif_id: str
    image_url: str
    width: int
    height: int
    license: str | None
    rights_status: str


def institution_rank(institution: str) -> int:
    """Lower = higher priority; unknown institutions sort after all known ones."""
    inst = institution.lower()
    return INSTITUTION_PRIORITY.index(inst) if inst in INSTITUTION_PRIORITY else len(INSTITUTION_PRIORITY)


def classify_rights(value: str | None) -> str:
    """Map a license/rights string to public_domain / restricted / unknown."""
    if not value or not value.strip():
        return "restricted"
    low = value.lower()
    if any(marker in low for marker in _PUBLIC_DOMAIN_MARKERS):
        return "public_domain"
    return "unknown"


def max_image_url(iiif_id: str) -> str:
    """Build the IIIF Image API request for the largest available rendition."""
    return f"{iiif_id.rstrip('/')}/full/max/0/default.jpg"


def parse_info_json(info: dict) -> tuple[str, int, int]:
    """Extract (iiif_id, width, height) from an Image API info.json."""
    iiif_id = info.get("@id") or info.get("id") or ""
    return iiif_id, int(info.get("width", 0)), int(info.get("height", 0))


def _manifest_rights(manifest: dict) -> str | None:
    for entry in manifest.get("metadata", []):
        label = str(entry.get("label", "")).lower()
        if "right" in label or "license" in label:
            return entry.get("value")
    return manifest.get("rights") or manifest.get("license")


def parse_manifest(manifest: dict, *, work_id: str, institution: str) -> list[ImageCandidate]:
    """Flatten a IIIF Presentation v2 manifest into image candidates."""
    rights_value = _manifest_rights(manifest)
    rights_status = classify_rights(rights_value)
    candidates: list[ImageCandidate] = []
    for seq in manifest.get("sequences", []):
        for canvas in seq.get("canvases", []):
            label = str(canvas.get("label", manifest.get("label", "")))
            for image in canvas.get("images", []):
                resource = image.get("resource", {})
                service = resource.get("service", {})
                iiif_id = service.get("@id") or service.get("id")
                if not iiif_id:
                    continue
                candidates.append(
                    ImageCandidate(
                        work_id=work_id,
                        institution=institution.lower(),
                        label=label,
                        iiif_id=iiif_id,
                        image_url=max_image_url(iiif_id),
                        width=int(resource.get("width", 0)),
                        height=int(resource.get("height", 0)),
                        license=rights_value,
                        rights_status=rights_status,
                    )
                )
    return candidates


def meets_resolution(c: ImageCandidate, *, min_long_edge: int = 1500) -> bool:
    """True when the candidate's longer pixel edge meets the study-quality floor."""
    return max(c.width, c.height) >= min_long_edge


def validate_candidate(c: ImageCandidate, *, min_long_edge: int = 1500) -> tuple[bool, list[str]]:
    """Return (passed, reasons). Restricted rights or low resolution fail."""
    reasons: list[str] = []
    if c.rights_status == "restricted":
        reasons.append("rights: restricted or missing")
    if not meets_resolution(c, min_long_edge=min_long_edge):
        reasons.append(f"resolution: long edge {max(c.width, c.height)} < {min_long_edge}")
    return (not reasons, reasons)
```

- [ ] **Step 6: Run to verify pass**

Run: `uv run pytest tests/test_iiif.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add pyproject.toml uv.lock skill/scripts/iiif.py tests/fixtures/met_manifest.json tests/fixtures/met_info.json tests/test_iiif.py
git commit -m "feat: IIIF discovery + license/resolution validation"
```

---

### Task 6: Polite image download + per-image metadata

Download validated candidates to `images/candidates/<work-slug>/`, with a robots check, an injected fetcher (no live network in tests), throttling between requests, a JSON metadata sidecar per image, and idempotent skips.

**Files:**
- Create: `skill/scripts/image_download.py`
- Create: `tests/fixtures/robots.txt`
- Test: `tests/test_image_download.py`

**Interfaces:**
- Consumes: `ImageCandidate`, `validate_candidate` (Task 5); `slugify`, `StudyPaths.candidates_dir` (Plan 1 Task 2).
- Produces:
  - `robots_allows(robots_txt: str, path: str, user_agent: str = "*") -> bool`.
  - `DownloadResult` (frozen dataclass): `candidate: ImageCandidate`, `image_path: Path | None`, `meta_path: Path | None`, `status: str` (`"downloaded"|"skipped"|"invalid"|"blocked"|"error"`), `note: str`.
  - `download_candidate(candidate, candidates_dir, *, fetch, robots_txt="", sleep=time.sleep, min_interval=1.0) -> DownloadResult` — `fetch(url) -> (status_code: int, content_type: str, content: bytes)`.
  - `download_candidates(candidates, candidates_dir, *, fetch, robots_txt="", sleep=time.sleep, min_interval=1.0) -> list[DownloadResult]`.

- [ ] **Step 1: Create the robots fixture**

Create `tests/fixtures/robots.txt`:
```text
User-agent: *
Disallow: /private/
Disallow: /admin

User-agent: BadBot
Disallow: /
```

- [ ] **Step 2: Write the failing tests**

Create `tests/test_image_download.py`:
```python
import json
import time
from pathlib import Path

from scripts.iiif import ImageCandidate
from scripts.image_download import (
    DownloadResult,
    download_candidate,
    download_candidates,
    robots_allows,
)

ROBOTS = (Path(__file__).parent / "fixtures" / "robots.txt").read_text()


def _candidate(iiif_id="https://images.metmuseum.org/iiif/12345", w=4000, h=3000,
               rights="public_domain", work_id="wheat-field"):
    return ImageCandidate(
        work_id=work_id, institution="met", label="recto", iiif_id=iiif_id,
        image_url=f"{iiif_id}/full/max/0/default.jpg", width=w, height=h,
        license="Public Domain", rights_status=rights,
    )


def _ok_fetch(url):
    return (200, "image/jpeg", b"\xff\xd8\xff\xe0JPEGBYTES")


def test_robots_allows_respects_disallow():
    assert robots_allows(ROBOTS, "/art/collection/1") is True
    assert robots_allows(ROBOTS, "/private/secret") is False
    assert robots_allows(ROBOTS, "/admin/panel") is False


def test_robots_allows_empty_is_permissive():
    assert robots_allows("", "/anything") is True


def test_download_candidate_writes_image_and_metadata(tmp_path):
    res = download_candidate(_candidate(), tmp_path, fetch=_ok_fetch, sleep=lambda s: None)
    assert res.status == "downloaded"
    assert res.image_path.is_file()
    assert res.image_path.parent.name == "wheat-field"
    assert res.image_path.read_bytes().startswith(b"\xff\xd8\xff")
    meta = json.loads(res.meta_path.read_text())
    assert meta["institution"] == "met"
    assert meta["rights_status"] == "public_domain"
    assert meta["iiif_id"].endswith("12345")
    assert meta["width"] == 4000


def test_download_candidate_skips_existing(tmp_path):
    download_candidate(_candidate(), tmp_path, fetch=_ok_fetch, sleep=lambda s: None)

    def _boom(url):
        raise AssertionError("should not refetch an existing image")

    res = download_candidate(_candidate(), tmp_path, fetch=_boom, sleep=lambda s: None)
    assert res.status == "skipped"


def test_download_candidate_rejects_invalid_candidate(tmp_path):
    bad = _candidate(w=400, h=300, rights="restricted")
    res = download_candidate(bad, tmp_path, fetch=_ok_fetch, sleep=lambda s: None)
    assert res.status == "invalid"
    assert res.image_path is None


def test_download_candidate_blocked_by_robots(tmp_path):
    blocked = _candidate(iiif_id="https://images.metmuseum.org/private/9")
    res = download_candidate(blocked, tmp_path, fetch=_ok_fetch, robots_txt=ROBOTS, sleep=lambda s: None)
    assert res.status == "blocked"


def test_download_candidate_handles_non_image_response(tmp_path):
    def _html(url):
        return (200, "text/html", b"<html>not found</html>")

    res = download_candidate(_candidate(), tmp_path, fetch=_html, sleep=lambda s: None)
    assert res.status == "error"
    assert res.image_path is None


def test_download_candidates_throttles_between_requests(tmp_path):
    calls = []
    cands = [_candidate(iiif_id=f"https://images.metmuseum.org/iiif/{i}") for i in range(3)]
    results = download_candidates(
        cands, tmp_path, fetch=_ok_fetch, sleep=lambda s: calls.append(s), min_interval=0.5
    )
    assert all(isinstance(r, DownloadResult) for r in results)
    assert [r.status for r in results] == ["downloaded", "downloaded", "downloaded"]
    # Sleeps between the 3 downloads (not before the first).
    assert calls.count(0.5) == 2
```

- [ ] **Step 3: Run to verify failure**

Run: `uv run pytest tests/test_image_download.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.image_download'`.

- [ ] **Step 4: Implement `image_download.py`**

Create `skill/scripts/image_download.py`:
```python
"""Stage-5 IO: robots-aware, throttled, idempotent image download with metadata.

The byte-fetch boundary is injected (`fetch(url) -> (status, content_type, bytes)`)
so tests run against canned responses, never live museum endpoints. A default
httpx-backed fetcher is provided for real runs.
"""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scripts.iiif import ImageCandidate, validate_candidate


def robots_allows(robots_txt: str, path: str, user_agent: str = "*") -> bool:
    """Minimal robots.txt check for the `*` (or named) user-agent group."""
    if not robots_txt.strip():
        return True
    groups: dict[str, list[str]] = {}
    current: list[str] = []
    for raw in robots_txt.splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key, value = key.strip().lower(), value.strip()
        if key == "user-agent":
            current = groups.setdefault(value, [])
        elif key == "disallow" and value:
            current.append(value)
    rules = groups.get(user_agent, groups.get("*", []))
    return not any(path.startswith(rule) for rule in rules)


@dataclass(frozen=True)
class DownloadResult:
    candidate: ImageCandidate
    image_path: Path | None
    meta_path: Path | None
    status: str
    note: str = ""


def _iiif_token(iiif_id: str) -> str:
    return iiif_id.rstrip("/").rsplit("/", 1)[-1]


def default_fetch(url: str) -> tuple[int, str, bytes]:
    """Real fetcher (httpx). Not exercised in tests."""
    import httpx

    resp = httpx.get(url, follow_redirects=True, timeout=60.0)
    return resp.status_code, resp.headers.get("content-type", ""), resp.content


def download_candidate(
    candidate: ImageCandidate,
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    robots_txt: str = "",
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> DownloadResult:
    """Validate, robots-check, and download one candidate; idempotent."""
    passed, reasons = validate_candidate(candidate)
    if not passed:
        return DownloadResult(candidate, None, None, "invalid", "; ".join(reasons))

    work_dir = Path(candidates_dir) / candidate.work_id
    token = _iiif_token(candidate.iiif_id)
    image_path = work_dir / f"{token}.jpg"
    meta_path = work_dir / f"{token}.json"

    if image_path.is_file():
        return DownloadResult(candidate, image_path, meta_path, "skipped")

    if not robots_allows(robots_txt, urlsplit(candidate.image_url).path):
        return DownloadResult(candidate, None, None, "blocked", candidate.image_url)

    status_code, content_type, content = fetch(candidate.image_url)
    if status_code != 200 or not content_type.startswith("image/") or not content:
        return DownloadResult(
            candidate, None, None, "error", f"status={status_code} type={content_type}"
        )

    work_dir.mkdir(parents=True, exist_ok=True)
    image_path.write_bytes(content)
    meta_path.write_text(json.dumps(asdict(candidate), indent=2) + "\n", encoding="utf-8")
    return DownloadResult(candidate, image_path, meta_path, "downloaded")


def download_candidates(
    candidates: list[ImageCandidate],
    candidates_dir: Path | str,
    *,
    fetch=default_fetch,
    robots_txt: str = "",
    sleep=time.sleep,
    min_interval: float = 1.0,
) -> list[DownloadResult]:
    """Download a list of candidates, throttling between actual fetches."""
    results: list[DownloadResult] = []
    fetched = False
    for candidate in candidates:
        if fetched:
            sleep(min_interval)
        result = download_candidate(
            candidate,
            candidates_dir,
            fetch=fetch,
            robots_txt=robots_txt,
            sleep=sleep,
            min_interval=min_interval,
        )
        results.append(result)
        if result.status == "downloaded":
            fetched = True
    return results
```

- [ ] **Step 5: Run to verify pass**

Run: `uv run pytest tests/test_image_download.py -v`
Expected: PASS.

> [!note] The throttle test asserts a sleep is issued before each download after the first. In `download_candidates` the `fetched` flag flips only after a real download, so leading skips/invalids don't trigger spurious sleeps. The per-call `sleep`/`min_interval` params on `download_candidate` are accepted for signature symmetry but unused there (throttling is orchestrated by `download_candidates`).

- [ ] **Step 6: Run the full suite**

Run: `cd "$HOME/iCloud/para/1-projects/artist-study-kit" && uv run pytest -v`
Expected: PASS (Plan 1 + all Plan 2 tasks green).

- [ ] **Step 7: Commit**

```bash
git add skill/scripts/image_download.py tests/fixtures/robots.txt tests/test_image_download.py
git commit -m "feat: polite idempotent image download + per-image metadata"
```

---

## What this plan deliberately defers

- **Scrapy bulk download.** v1 uses the per-candidate `httpx` downloader; Scrapy for large image jobs (CLAUDE.md) is a later optimization once candidate counts justify it.
- **Live identity resolution** (search-API lookup of work → IIIF manifest URL per institution). Stage 5 currently assumes the manifest/info.json is in hand; the per-institution search adapters are a follow-on (the parsing/validation contract they feed is fixed here).
- **Plan 3 (curation + study):** `gallery.html` generator + `selection.json` round-trip; preference-synthesis ranking; analysis/study-notes/drills/schedule emitters; `prompts/` population.
- **SKILL.md stage wiring.** This plan ships importable helpers; threading them into the Stage-2/Stage-5 narrative in `SKILL.md` (and marking stages complete via `PipelineState`) happens when the stages are exercised end-to-end.

## Self-Review

- **Spec coverage (Run-A tooling slice):**
  - spec §3.1 Firecrawl `/scrape` → markdown → Task 2 ✔
  - spec §4 Stage 2 two-pass grader: machine signal-scan (pass 1) → Task 3 ✔; rubric weights + 1–100 score + tier + `sources.json`/`source-grades.md` (pass-2 plumbing) → Task 4 ✔; auction=facts-only via `use_for`/`avoid_for` fields ✔
  - spec §4 Stage 5 IIIF discovery, license check, `max` fetch, source priority, missing-rights=restricted, robots+throttle, `images/candidates/<work>/` + per-image metadata → Tasks 5–6 ✔
  - spec §8 fixtures-not-live-endpoints (all network injected) → Tasks 2/6 ✔; CLAUDE.md venv-outside-iCloud + uv + TDD → Global Constraints + every task ✔
  - Plan 1 carry-forward Minors → Task 1 ✔
  - Deferred-and-mapped: Scrapy bulk, identity resolution, gallery/selection (Plan 3), SKILL.md wiring.
- **Placeholder scan:** no TBD/TODO in code; every code step shows complete code; every run step shows command + expected result. (The string `"TBD by reviewer"` in `write_source_grades_md` is intentional *runtime output*, not a plan placeholder.)
- **Type consistency:** `FetchedPage` (Task 2) → consumed by `scan_source` (Task 3) and `_scan` test helper (Task 4) ✔. `SignalScan` (Task 3) → field on `GradedSource` and serialized via `asdict` (Task 4) ✔. `RubricScores`/`weighted_score`/`score_to_tier`/`grade_source` names consistent across Task 4 definition + tests ✔. `ImageCandidate` (Task 5) → consumed by `validate_candidate` (Task 5) and `download_candidate` (Task 6) ✔; `iiif_id`/`image_url`/`work_id`/`rights_status`/`width`/`height` field names match across `parse_manifest`, validation, download, and metadata sidecar ✔. `validate_candidate` returns `(bool, list[str])` in both definition (Task 5) and consumer (Task 6) ✔.
