# QID-Authoritative Metadata Override — Design Spec

> Follow-on to the shipped dedup feature (Spec A engine + Spec B library collection
> mode). A surgical change to `dedup.resolve`'s metadata merge — no schema change, no Spec B
> change. Engine spec: `2026-06-21-image-dedup-engine-design.md`.

**Date:** 2026-06-21
**Touches:** `skill/scripts/dedup.py` (the metadata-merge block in `resolve`) + `tests/test_dedup.py`.

---

## 1. Goal

When the dedup engine merges a newly-seen image into an existing library entry, let an
**authoritative** (QID-bearing) value override a **guessed** (no-QID) existing value, so a
seed image imported first with a filename-derived title gets corrected to the canonical
museum/Wikidata title once discovery matches the work — without ever clobbering a value that
is already authoritative.

One sentence: *a QID-bearing field beats a non-QID field; otherwise nothing changes.*

## 2. Why now

`dedup.resolve` currently merges metadata as **existing-non-empty-wins**
(`title = match.title or inc.title`, etc.). Because seed images are imported first with
`title = <filename stem>` (a non-empty guess, no QID), a later QID-rich discovered match only
*fills empties* — so the filename title persists even though the authoritative record is
available. Spec B's final review flagged this as the one remaining dedup follow-on.

## 3. Locked decisions

| Decision | Choice |
|---|---|
| Authority signal | **Presence of a QID.** A value sourced with a `qid` is authoritative; a value with no `qid` is a guess. No new tracking, no manifest schema change. |
| Override rule | **Incoming authoritative + existing not** (`inc.qid` set, `match.qid` empty) → incoming's non-empty authoritative fields win. **Otherwise** (existing has a qid, or neither does) → today's existing-non-empty-wins, unchanged. |
| Existing QID protected | An existing entry that already has a `qid` is **never** overridden by another source — including an incoming with a *different* qid (a likely bad perceptual match). Conservative keep-existing; the conflict remains visible in `origins`. |
| Fields covered | `title`, `date`, `qid`, `inst_ids`, `medium`, `rights`. |
| Not covered | `stars` (human authority, already always preserved), `source_url` (per-copy, lives in `origins`), `work_id` + `filename` + `path` (stable identity — see below). |
| Metadata ⊥ pixel winner | Which physical file is kept is still decided by largest pixel area → bytes (unchanged). A *smaller* authoritative discovered image upgrades the metadata while the *larger* seed file stays as the kept pixels. The two are computed independently in `resolve`. |
| Identity stability | `work_id`, canonical `filename`, and `path` do **not** change on a metadata upgrade (no file churn; stars/selection keyed on `work_id` stay intact). Only descriptive fields update. The no-churn canonical-name logic (`dedup.py:102-108`) is unchanged. |
| Scope | The merge block + tests only. Manifest schema, Spec B (`library.py`, `sync_candidates`), and the on-disk file ops are untouched. The upgraded title flows to the curation board automatically because `sync_candidates` rebuilds the `BoardCandidate` from the manifest entry on every sync. |

## 4. The change (`dedup.resolve`)

Replace the current merge block:

```python
# identity / metadata merge — existing authoritative, incoming fills gaps
title = match.title or inc.title
date = match.date or inc.date
qid = match.qid or inc.qid
inst_ids = match.inst_ids or inc.inst_ids
rights = match.rights or inc.rights
medium = match.medium or inc.medium
```

with an authority-aware merge:

```python
# Metadata merge. A QID-bearing source is authoritative; a no-QID value is a guess.
# When the incoming is authoritative and the existing entry is not, the incoming's
# non-empty fields override the existing guess; otherwise existing-non-empty-wins
# (existing already authoritative, or neither side is). stars/source_url/identity unaffected.
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

Everything else in `resolve` (the `find_match`, the `inc_wins` pixel decision, canonical-name
no-churn logic, the kept/deleted file paths, `origins` append, `stars=match.stars`) is
unchanged.

### Interaction with canonical naming (intentionally unchanged)

The no-churn rule (`if match.title.strip(): cn = match.filename`) keeps a seed entry's
filename-derived name even after the title metadata is upgraded. This is **intended**: the
filename and `work_id` are internal identifiers; renaming the on-disk file on every metadata
correction would churn the library and break nothing but cost effort. The *displayed* title
(the manifest/board metadata) is what the upgrade corrects.

## 5. Edge cases

- **Both have a QID, same value** (the work re-discovered): existing branch → existing wins;
  identical anyway. No-op.
- **Both have a QID, different values** (perceptual false-positive, or a work with two QIDs):
  existing branch → existing metadata kept (no clobber). The incoming copy's `origin` is still
  appended, so the conflicting `qid` is auditable in `origins`. Not specially handled — out of
  scope; keep-existing is the safe default.
- **Incoming authoritative but a field is empty** (a QID record lacking, say, `date`): that
  field keeps the existing value (`inc.date or match.date`) — override only when the
  authoritative value is actually present.
- **Neither has a QID**: identical to today's behavior.

## 6. Testing (offline `pytest`, extend `tests/test_dedup.py`)

- **Upgrade on authority, independent of pixels:** existing entry `qid=""`,
  `title="DT4962"`, large dims; incoming `qid="Q1"`, `title="The Vase of Tulips"`, *smaller*
  dims. Result: `kind=="merge"`, existing **wins on pixels** (`keep_path == existing`,
  entry width = existing width), but `entry.title == "The Vase of Tulips"` and
  `entry.qid == "Q1"`. `work_id` and `stars` unchanged.
- **Existing QID not clobbered:** existing `qid="Q1"`, `title="Real Title"`; incoming
  `qid="Q2"`, `title="Other"`. Result: `entry.title == "Real Title"`, `entry.qid == "Q1"`.
- **Empty incoming field not forced:** incoming `qid="Q1"`, `date=""`; existing `date="1890"`.
  Result: `entry.date == "1890"`.
- **Neither has a QID (regression guard):** existing `qid=""`, `title="A"`; incoming
  `qid=""`, `title="B"`. Result: `entry.title == "A"` (existing-non-empty-wins, unchanged).
- **Identity stable across upgrade:** in the first test, assert `entry.work_id` and
  `entry.filename` equal the existing entry's (no churn).

All offline, injected hashes/dims as in the existing `test_dedup.py` — no images needed.

## 7. Out of scope

Per-field human-edit protection (no human-edited metadata exists in the manifest today);
manifest schema changes; QID-conflict resolution beyond keep-existing; renaming files/work_ids
on a metadata upgrade; any Spec B / `library.py` change.
