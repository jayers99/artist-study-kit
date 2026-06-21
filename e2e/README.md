# e2e — live end-to-end harnesses

Standalone scripts that exercise the **funnel pipeline against the live network**
(AIC discovery, real thumbnail/high-res downloads, Wikimedia Commons). These are NOT
pytest unit tests — they hit real services and are intentionally outside `tests/` so
pytest does not collect them. The unit suite stays offline (injected fetch boundaries);
these are for manual confidence checks after a pipeline change.

The one un-automatable step is the browser funnel itself (clicking **Next → Commit** in
`gallery.html`). The harness synthesizes the exact three JSON files the gallery JS would
download (`stars.json`, `selection.json`, `study-set.json`) and then runs the real
ingest → resolve → record path, asserting the Spec-B invariants on disk.

## Run

From the repo root (the venv lives outside iCloud):

```bash
UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run python e2e/funnel_pipeline.py "Claude Monet"
UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run python e2e/commons_resolve.py "Claude Monet"
UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv run python e2e/library_collection.py
```

- `funnel_pipeline.py <artist>` — full funnel: live AIC discovery → local thumbnail cache
  → build funnel `gallery.html` → `display_url` (validated) → simulate the funnel commit →
  real `ingest_stars`/`ingest_selection`/`load_study_set`/`resolve_selection(only=…)`/
  `record_session`. Resolve is stubbed here (deterministic) — the funnel logic is the
  subject. Artifacts land in `/tmp/funnel-e2e-studies/<artist-slug>/`.
- `commons_resolve.py <artist>` — re-runs just the resolve step with the **live Commons
  resolver** + real `download_candidate`, downloading real high-res PD files for the
  study set into `images/selected/`. Run `funnel_pipeline.py` first (it produces the
  `selection.json` / `study-set.json` this reads).
- `library_collection.py` — Spec B end-to-end: seeds the Cezanne collection
  (`studies/cezanne/images/user/`), runs live AIC/Wikidata discovery, downloads up to 20
  candidates, builds and deduplicates the library, syncs to the curation board. Wikidata
  timeout degrades to AIC-only gracefully. Artifacts land in a temp dir (never `studies/`).

Pick a **public-domain** artist (Monet, Hokusai, van Gogh). A still-in-copyright artist
(e.g. Klee, d. 1940) legitimately has no PD high-res to resolve — that's expected, not a
failure.

Exit code is non-zero if any invariant fails.
