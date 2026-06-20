# Persistent Board Stars — Design Spec

> Spec A of raw/19 Thrust 3. Spec B (progressive-zoom narrowing funnel +
> skip-discovery) builds on this and is specced separately.

**Date:** 2026-06-20
**Source:** `raw/19-stateful-runs-custom-images-staged-analysis.md` §(c)/(d)
**Builds on:** Thrust 1 (stateful package state, `state.json`) + Thrust 2 (custom
image injection, `origin:"user"` / `local_path`).

---

## 1. Goal

Make the curation board **persistent and self-sufficient**: star ratings live on the
candidate and survive every session and every discovery/import run; the board caches its
thumbnails locally so it never re-pulls; and the human can filter and sort the board.
Star rating and selection-for-advancement become **two fully orthogonal axes** — neither
reads the other.

One sentence: *the board remembers your stars forever, works offline, sorts and filters,
and selection no longer hides behind a star threshold.*

## 2. Why now

Thrust 1 made the package stateful and multi-run; Thrust 2 added the user's own images.
A board that grows across runs needs persistent annotation (so re-querying doesn't
re-surface rejects as fresh) and stable local images (so re-opening doesn't re-hotlink
rotting museum URLs). raw/19 §(d) also reverses the earlier "drop stars for binary
select" decision: stars come back, but as a **persistent annotation**, explicitly
decoupled from selection.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Scope | Spec A only: persistent stars + local thumbnail cache + filter/sort + select-decouple. Funnel/skip-discovery → Spec B. |
| Star persistence | Per-candidate field on `BoardCandidate`; survives all sessions + all runs. New candidates arrive unstarred (`0`). |
| Stars ⊥ selection | Fully orthogonal. Rating never selects; selecting never rates. Nothing in selection reads a star threshold. |
| Local images | **Cache thumbnails on collect** into the package; board renders from local files (fallback to remote on cache miss). |
| Size sort | Real **local thumbnail byte size** (uniform across discovered + user images). Not pixel dimensions. |
| Export shape | **Two files**: `stars.json` (persistent, all candidates) + `selection.json` (this session's explicit picks). |
| Stars key | `work_id` (stable within a package). Cross-run duplicate identity → deferred TODO. |
| Selection lifetime | Per-session; never seeded into the board. Stars are seeded; selections start empty each build. |

## 4. Data model (`state.py`)

Two new fields on `BoardCandidate`:

```python
stars: int = 0            # persistent rating, 0 = unrated, 1..5
thumbnail_path: str = ""  # local cached thumbnail, rel path e.g. "images/candidates/<wid>/thumb.jpg"
```

- `to_dict` / `from_dict` round-trip both; `from_dict` defaults `stars=0`,
  `thumbnail_path=""`, so existing `state.json` files load unchanged (no version bump,
  no migration step).
- `from_thumbnail` leaves `stars=0` (new candidates unstarred) and `thumbnail_path=""`
  (filled by the cache step).
- `merge_candidates` is unchanged: an existing candidate is kept on dedup match, so its
  `stars` survive a re-query automatically. (The messy "is this newly-found image a
  duplicate of a starred one" case is the deferred TODO, not this spec.)

New method on `PackageState`:

```python
def ingest_stars(self, stars_map: dict[str, int]) -> int:
    """Apply {work_id: stars} onto candidates. Returns count updated.
    Ignores unknown work_ids and out-of-range values (keep 0..5)."""
```

## 5. Thumbnail caching on collect (`image_download.py`)

New function, byte-fetch boundary injected exactly like `download_candidate`:

```python
def cache_thumbnail(
    work_id: str, thumbnail_url: str, candidates_dir: Path | str,
    *, fetch=default_fetch,
) -> tuple[str, int]:
    """Download a board thumbnail to <candidates_dir>/<work_id>/thumb.jpg.
    Idempotent (skip if present). Returns (rel_path, byte_size); ("", 0) on failure."""
```

- Writes to `images/candidates/<work_id>/thumb.jpg`; the rel path returned is what goes
  on `candidate.thumbnail_path`.
- Idempotent: if the file exists, return its path + size without re-fetching.
- Failure (network, non-image, non-200) → `("", 0)`, never raises; the board falls back
  to the remote `thumbnail_url` for that card.
- Caching applies to **discovered** candidates. `origin:"user"` candidates already have
  a local file (`local_path`); their `thumbnail_path` is set to that file (no fetch).
- Wiring: after a discovery run merges candidates, iterate the candidates lacking a
  `thumbnail_path` and cache each (throttled between real fetches, mirroring
  `download_candidates`). This is a collect-time step, separate from the rights-gated
  full-res download in Phase 2.

## 6. Gallery (`gallery.py` — `build_thumbnail_gallery` + `_THUMB_TEMPLATE`)

### Payload per card (additions in **bold**)

```
work_id, iiif_token, source_url, title, museum, date, medium, rights, qid, inst_ids, origin,
image_rel  := thumbnail_path or thumbnail_url   (local preferred, remote fallback)
**stars**  := candidate.stars                    (seeded — persistent axis)
**bytes**  := local thumbnail byte size or 0     (size sort)
**year**   := parse_year(date) or null           (year sort; null sorts last)
**selected** := false                            (never seeded; per-session)
```

### Controls

- **Stars** — the existing 1–5 star control, now **seeded** from `stars` and representing
  the *persistent* axis. Editing a star updates only that axis.
- **Select** — a **new, separate** binary per-card toggle (checkbox + a distinct
  non-gold border, e.g. blue `.card.selected`). Visually and behaviorally independent of
  stars. Toggling select changes nothing about stars and vice-versa.
- **Filter** — a star filter (`all` / `unstarred` / `≥1…≥5`), plus the existing
  public-domain filter retained. (`1★ = "seen it, not interested"` is filtered out via
  `unstarred`/`≥2`.)
- **Sort** — a selector: **year ascending (default)** / stars descending / file size.
  Undated (`year == null`) and unknown-size (`bytes == 0`) entries sort last. Sort
  applies to the rendered grid.

### Export — two buttons / two files

- **`stars.json`** — `{artist, stars: [{work_id, stars}]}` for **every** candidate (the
  full persistent picture, not a delta).
- **`selection.json`** — `{artist, ratings: [...]}` where each row carries the existing
  provenance fields plus **`selected: bool`** and **`stars: int`** (stars informational
  only, for audit). The session's selected set = rows with `selected == true`.

The board is regenerated by the skill on each open: it seeds `stars` from state and
leaves `selected` false, so persistent stars show up pre-filled while selection always
starts fresh.

## 7. Skill ingest (`selection.py`)

The decoupling is the heart of orthogonality.

- `Rating` gains two fields: `selected: bool = False` and `stars: int = 0`.
  `parse_selection` reads both.
- **Schema note:** the legacy `rating` field on `selection.json` rows was the star value
  doubling as the selection signal. Going forward, the persistent star lives in
  `stars.json` (and is mirrored into `Rating.stars` for audit only); selection comes from
  the explicit `selected` flag. For back-compat, `parse_selection` still reads the old
  `rating` field into `Rating.rating`, but **nothing in the selection path consumes
  `rating` or `stars`** — only `selected`.
- `ingest_selection(sel)` returns `(selected_ids, study_set_ids)` where
  `selected_ids = [r.work_id for r in sel.ratings if r.selected]` — **no `liked()`
  call**. `study_set` defaults equal to `selected` (Spec B's funnel narrows it).
- `apply_selection` copies images for the **explicitly selected** works, not
  `liked(...)`.
- `liked()` and `LIKED_THRESHOLD` are removed from the selection flow. (`migrate_legacy`
  in `state.py` still references `liked` for one-time legacy import; it keeps a local
  threshold helper so the new selection path carries no star coupling.)

New `ingest_stars` entry on `PackageState` (see §4) is called when the skill ingests
`stars.json`.

## 8. Year parser (`selection.py` or a small `dates.py`)

```python
def parse_year(date: str) -> int | None:
    """Extract a sort year from a free-text date.
    "1889" -> 1889; "c. 1889" -> 1889; "1889–90" / "1889-1890" -> 1889;
    "" / "n.d." / unparseable -> None."""
```

First 4-digit run wins (handles `circa`, ranges, month/day prefixes). `None` sorts last.

## 9. Orthogonality — the invariant to test

> A 1★ work can be selected; a 5★ work can be left unselected. Rating a work does not
> select it; selecting a work does not change its star.

Concretely:
- `ingest_selection` of a payload where every row has `selected=false` but high `stars`
  → empty selected set.
- `ingest_selection` of a payload where rows have `selected=true` but `stars=0` (or 1)
  → those work_ids selected.
- `ingest_stars` changes `candidate.stars` and never touches any session's `selected`.

## 10. Testing (TDD, pytest)

- `BoardCandidate` stars + thumbnail_path round-trip; old state.json loads with defaults.
- `PackageState.ingest_stars`: applies known work_ids, ignores unknown, clamps range.
- `cache_thumbnail`: writes thumb.jpg, idempotent skip, byte size returned, failure → `("",0)`.
- `parse_year`: the cases in §8.
- `parse_selection` reads `selected`; `ingest_selection` uses explicit selected, ignores
  stars (the §9 invariants).
- `apply_selection` copies explicitly-selected works, not by threshold.
- `build_thumbnail_gallery` payload carries stars/bytes/year/selected and prefers
  `thumbnail_path` over `thumbnail_url`.

## 11. Out of scope / deferred

- **Spec B:** progressive-zoom two-up page, ≤4 study-set cap, skip-discovery entry switch.
- **Deferred TODO (already logged):** duplicate handling on re-query/ingest so a newly
  found image that duplicates a starred work isn't re-added unstarred.
- No pixel-dimension metadata plumbing (size sort uses local thumbnail bytes).
