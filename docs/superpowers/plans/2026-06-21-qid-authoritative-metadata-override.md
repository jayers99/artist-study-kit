# QID-Authoritative Metadata Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In `dedup.resolve`, let a QID-bearing (authoritative) value override a no-QID (guessed) existing value when merging a duplicate, so a seed image's filename-derived title is corrected to the canonical museum/Wikidata title — without clobbering an already-authoritative value.

**Architecture:** A surgical replacement of the 6-line metadata-merge block in `skill/scripts/dedup.py`'s `resolve()` with an authority-aware branch. Nothing else in `resolve` changes — pixel winner, canonical naming, identity, stars, and `origins` are untouched. No manifest schema change; no Spec B change.

**Tech Stack:** Python 3, `pytest` (offline, injected hashes/dims), uv. Tests import `from scripts.dedup import ...` (pytest `pythonpath=["skill"]`).

## Global Constraints

- **Spec:** `docs/superpowers/specs/2026-06-21-qid-authoritative-metadata-override-design.md`.
- **Authority signal:** presence of a `qid`. No new manifest field; no schema change.
- **Override rule:** `if inc.qid and not match.qid:` → incoming's non-empty authoritative fields win; `else` → today's existing-non-empty-wins, byte-for-byte unchanged.
- **Fields covered:** `title`, `date`, `qid`, `inst_ids`, `rights`, `medium`. **Not** `stars`, `source_url`, `work_id`, `filename`, `path`.
- **Metadata ⊥ pixel winner:** the `inc_wins` dims/bytes decision and which file is kept/deleted are unchanged. A smaller authoritative image can upgrade metadata while the larger existing file stays the kept pixels.
- **Identity stable:** `work_id`, canonical `filename`, `stars` never change on a metadata upgrade. The no-churn canonical-name logic is unchanged.
- **Existing QID protected:** an existing entry with a `qid` is never overridden, including by a *different* incoming `qid`.
- **Tests:** offline `pytest`, extend `tests/test_dedup.py`, reuse its existing `_inc`/`_entry` helpers (no images). `uv run pytest`.

---

### Task 1: Authority-aware metadata merge in `dedup.resolve`

**Files:**
- Modify: `skill/scripts/dedup.py` (the metadata-merge block inside `resolve`, currently the 6 lines `title = match.title or inc.title` … `medium = match.medium or inc.medium`)
- Test: `tests/test_dedup.py` (append 4 tests; reuse the existing module-level `_inc` and `_entry` helpers)

**Interfaces:**
- Consumes: existing `dedup.resolve(inc, manifest, run_id, *, threshold) -> DedupAction`, `IncomingImage`, `Manifest`, `ManifestEntry` (all unchanged).
- Produces: no new public surface — same `resolve` signature and `DedupAction` shape; only the merged `entry`'s metadata fields change under the new rule.

- [ ] **Step 1: Write the failing tests** — append to `tests/test_dedup.py` (the `_inc` and `_entry` helpers already exist at the top of this file from the Spec A dedup tests; reuse them):

```python
def test_qid_incoming_overrides_seed_guess_independent_of_pixels():
    # existing: seed guess, NO qid, LARGER pixels, starred
    existing = _entry("dt4962", title="DT4962", qid="", date="",
                      filename="dt4962.jpg", path="images/library/dt4962.jpg",
                      width=2000, height=1500, bytes=900000, stars=4)
    m = Manifest(entries=[existing])
    # incoming: authoritative (qid), SMALLER pixels
    inc = _inc(tmp_path="/incoming/v.jpg", w=400, h=300, b=1000,
               title="The Vase of Tulips", qid="Q1", date="1890")
    act = resolve(inc, m, run_id="r")
    assert act.kind == "merge"
    # existing wins on PIXELS (it is larger) ...
    assert act.keep_path == "images/library/dt4962.jpg"
    assert act.entry.width == 2000 and act.entry.bytes == 900000
    # ... but the authoritative metadata UPGRADES the guess
    assert act.entry.title == "The Vase of Tulips"
    assert act.entry.qid == "Q1"
    assert act.entry.date == "1890"
    # identity is stable across the upgrade
    assert act.entry.work_id == "dt4962"
    assert act.entry.filename == "dt4962.jpg"
    assert act.entry.stars == 4


def test_existing_qid_not_clobbered_by_different_qid():
    existing = _entry("w", title="Real Title", qid="Q1",
                      filename="real-title.jpg", path="images/library/real-title.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/o.jpg", w=2000, h=1500, b=900000,
               title="Other", qid="Q2")
    act = resolve(inc, m, run_id="r")
    # incoming wins pixels, but existing authoritative metadata is kept
    assert act.entry.title == "Real Title"
    assert act.entry.qid == "Q1"


def test_authoritative_incoming_empty_field_does_not_blank_existing():
    existing = _entry("w", title="Old", qid="", date="1890",
                      filename="old.jpg", path="images/library/old.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/x.jpg", w=400, h=300, b=1000,
               title="", qid="Q1", date="")           # authoritative but sparse
    act = resolve(inc, m, run_id="r")
    assert act.entry.qid == "Q1"          # qid applied
    assert act.entry.date == "1890"       # empty incoming date does NOT blank it
    assert act.entry.title == "Old"       # empty incoming title does NOT blank it


def test_neither_has_qid_keeps_existing_wins_unchanged():
    existing = _entry("w", title="A", qid="",
                      filename="a.jpg", path="images/library/a.jpg",
                      width=400, height=300, bytes=1000)
    m = Manifest(entries=[existing])
    inc = _inc(tmp_path="/incoming/b.jpg", w=2000, h=1500, b=900000,
               title="B", qid="")
    act = resolve(inc, m, run_id="r")
    assert act.entry.title == "A"          # existing-non-empty-wins, unchanged
```

- [ ] **Step 2: Run to verify they fail**

Run: `uv run pytest tests/test_dedup.py -k "qid_incoming_overrides or existing_qid_not_clobbered or authoritative_incoming_empty or neither_has_qid" -v`
Expected: `test_qid_incoming_overrides_seed_guess_independent_of_pixels`, `test_existing_qid_not_clobbered_by_different_qid`, and `test_authoritative_incoming_empty_field_does_not_blank_existing` FAIL (current code is existing-non-empty-wins, so the seed title/qid are NOT upgraded); `test_neither_has_qid_keeps_existing_wins_unchanged` already PASSES (regression guard).

- [ ] **Step 3: Implement the authority-aware merge** — in `skill/scripts/dedup.py`, inside `resolve`, replace exactly this block:

```python
    # identity / metadata merge — existing authoritative, incoming fills gaps
    title = match.title or inc.title
    date = match.date or inc.date
    qid = match.qid or inc.qid
    inst_ids = match.inst_ids or inc.inst_ids
    rights = match.rights or inc.rights
    medium = match.medium or inc.medium
```

with:

```python
    # Metadata merge. A QID-bearing source is authoritative; a no-QID value is a guess.
    # When the incoming is authoritative and the existing entry is not, the incoming's
    # non-empty fields override the existing guess; otherwise existing-non-empty-wins
    # (existing already authoritative, or neither side is). stars/source_url/identity
    # (work_id/filename) are unaffected, and this is independent of the pixel winner.
    if inc.qid and not match.qid:
        title = inc.title or match.title
        date = inc.date or match.date
        qid = inc.qid
        inst_ids = inc.inst_ids or match.inst_ids
        rights = inc.rights or match.rights
        medium = inc.medium or match.medium
    else:
        title = match.title or inc.title
        date = match.date or inc.date
        qid = match.qid or inc.qid
        inst_ids = match.inst_ids or inc.inst_ids
        rights = match.rights or inc.rights
        medium = match.medium or inc.medium
```

Leave everything else in `resolve` (the `inc_wins` pixel decision, the canonical-name no-churn block, the `keep_path`/`delete_path` assignment, the `ManifestEntry(...)` construction with `stars=match.stars` and the `origins` append) exactly as it is.

- [ ] **Step 4: Run to verify they pass**

Run: `uv run pytest tests/test_dedup.py -v`
Expected: PASS — the 4 new tests plus all pre-existing `test_dedup.py` tests (the existing-wins / add / merge cases are preserved by the `else` branch).

- [ ] **Step 5: Run the full suite (no regressions)**

Run: `uv run pytest -q`
Expected: PASS — the whole offline suite (the dedup engine is consumed by `library.py`/Spec B; confirm those tests still pass since merged-entry shape is unchanged).

- [ ] **Step 6: Commit**

```bash
git add skill/scripts/dedup.py tests/test_dedup.py
git commit -m "feat: dedup — QID-authoritative metadata override (upgrade seed guesses)"
```

---

## Self-Review

**Spec coverage:**
- §3 authority signal (qid presence), override rule (`inc.qid and not match.qid`), existing-qid-protected, fields covered, metadata⊥pixel, identity stability → Task 1 implementation + tests. ✓
- §4 exact code change → Task 1 Step 3 (verbatim block replacement). ✓
- §5 edge cases (different-qid → keep existing; empty authoritative field → keep existing; neither-qid → unchanged) → tests 2, 3, 4. ✓
- §6 test list (upgrade-independent-of-pixels incl. identity-stable assertions; existing-qid-not-clobbered; empty-field; neither-qid regression) → the 4 tests. ✓
- §7 out of scope (no schema/Spec B change) → Task 1 touches only `dedup.py` + `test_dedup.py`. ✓

**Placeholder scan:** none — the change and all 4 tests are complete code; exact block-to-replace is quoted verbatim.

**Type consistency:** reuses the existing `resolve`/`IncomingImage`/`Manifest`/`ManifestEntry`/`DedupAction` surface unchanged; `_inc`/`_entry` are the helpers already defined at the top of `tests/test_dedup.py`. No new names introduced.
