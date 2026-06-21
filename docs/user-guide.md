# artist-study-kit — User Guide & UAT Script

A complete, end-to-end walkthrough of the `artist-study-kit` skill, written so you can
follow it **verbatim** for a UAT pass. Each step has a **Do** (what to type/click), an
**Expect** (what should happen), and a **✓ Verify** checkpoint. Tick the `[ ]` boxes as
you go and record anything off-script in the **Findings log** at the end.

> The skill divides labour deliberately: **Claude** does the art-historical judgment,
> **Python scripts** do the plumbing (state, image discovery, the gallery), and **you**
> make the taste calls at two human pauses. The friction is the point — don't expect it to
> hand you a finished answer.

---

## 0. Before you start (one-time setup)

Run these from the repo root (`~/iCloud/para/1-projects/artist-study-kit`).

- [ ] **Install the Python tooling** (needs [uv](https://docs.astral.sh/uv/) + Python 3.12+):
  ```bash
  UV_PROJECT_ENVIRONMENT="$HOME/.venvs/artist-study-kit" uv sync
  ln -s "$HOME/.venvs/artist-study-kit" .venv   # skip if it already exists
  ```
  **✓ Verify:** `uv run pytest -q` reports **275 passed**.

- [ ] **Install the skill into Claude Code** (it is *not* installed by default):
  ```bash
  ln -s "$PWD/skill" ~/.claude/skills/artist-study-kit
  ```
  **✓ Verify:** `ls -la ~/.claude/skills/artist-study-kit` resolves to this repo's `skill/`.
  Restart / reopen Claude Code so it picks up the new skill.

- [ ] **(Optional) Firecrawl key** — only Stage 2's web fetching escalates to Firecrawl when
  a museum site blocks the built-in fetch. Without a key the run still works (WebFetch only);
  some high-value sources may be skipped.
  ```bash
  cp .env.example .env   # then paste your FIRECRAWL_API_KEY into .env
  ```

- [ ] **Pick your test artist.** For a clean happy-path UAT, use a **fully public-domain**
  artist with strong museum coverage. **Recommended: `Claude Monet`** (validated end-to-end,
  rich Wikidata + Art Institute of Chicago + Wikimedia Commons coverage).
  - To also exercise the **copyright gate** (no PD high-res), run a second pass on a
    still-in-copyright artist such as `Paul Klee` or `Joan Miró` — expect `©` badges and
    reference-link-only resolution instead of downloaded high-res.

> Throughout this guide the worked example is **Claude Monet**, whose study folder is
> `studies/claude-monet/`. The slug is the artist's name lowercased and kebab-cased
> (`Vilhelm Hammershøi` → `vilhelm-hammershoi`). Substitute your artist's slug everywhere.

---

## 1. The run at a glance

A resumable 9-stage pipeline with **two human pauses**. Claude runs stages 1–5
automatically, stops for you to curate, runs the interview + synthesis, stops again to
confirm, then finishes the analysis and study aids.

| # | Stage | Who | You'll see |
|---|-------|-----|------------|
| 1 | Background | Claude | `report.md` |
| 2 | Source grading | Claude | `sources/sources.json` · `source-grades.md` |
| 3 | Style definition | Claude | visual-grammar section in `report.md` |
| 4 | Works inventory | Claude | `works.md` |
| 5 | Image discovery | scripts | `images/candidates/` · `gallery.html` |
| ⏸ | **Human Pause 1 — curation funnel** | **you** | star, select, narrow to ≤4, commit |
| 6 | Curation interview | Claude | Socratic Q&A → `study-briefs.md` |
| 7 | Preference synthesis | Claude | `preference-synthesis.md` |
| ⏸ | **Human Pause 2 — funnel** | **you** | confirm the final study set |
| 8 | Visual analysis | Claude | `analysis.md` |
| 9 | Study & retention | Claude | `study-notes.md` · `drills/` · `review-schedule.md` |

---

## 2. Start the study

- [ ] **Do:** In Claude Code, from the repo root, type a natural request naming the artist:
  > Do a master study of Claude Monet.

  (Other phrasings that should trigger the skill: *"I want to study Monet's water lilies,"*
  *"help me do a master copy study of Claude Monet."*)

- **Expect:** Claude announces it's using the `artist-study-kit` skill and begins Stage 1.
  It scaffolds `studies/claude-monet/` and works through stages 1–5, narrating progress.

- [ ] **✓ Verify:** A folder `studies/claude-monet/` now exists with a `state.json` inside.

> **Possible interruption — artist disambiguation.** During Stage 5, if the artist's
> Wikidata identity is ambiguous, Claude will list candidates (name + birth/death years)
> and ask you to pick the right one. **Do:** reply with the correct person. This is expected
> behaviour, not a bug — note it in the log if it fires.

---

## 3. Stages 1–5 run automatically (background → image discovery)

- **Expect:** Claude completes the five automated stages without further input, then
  **stops at Human Pause 1**, telling you to open `gallery.html` and where to put the files
  you'll export.

- [ ] **✓ Verify — research outputs exist and read sensibly** (skim each):
  - [ ] `studies/claude-monet/report.md` — biography + art-historical placement **and** a
        "visual grammar" / style section. Prose is readable, not truncated.
  - [ ] `studies/claude-monet/sources/source-grades.md` — an A–F trust report; grades have
        reasons (authority, commercial bias, citations). `sources/sources.json` is valid JSON.
  - [ ] `studies/claude-monet/works.md` — a ranked, clustered list of important works
        (importance × studyability), with per-work metadata.
  - [ ] `studies/claude-monet/images/candidates/` — contains downloaded thumbnail images
        (a subfolder per work, each with a `.jpg` + `.json` sidecar).
  - [ ] `studies/claude-monet/gallery.html` — exists and is non-empty.

---

## 4. Human Pause 1 — the curation funnel (you drive)

This is the heart of the UAT. The gallery is a **two-stage zoom funnel**: a wide board where
you rate and select, then a zoomed close-look where you narrow to the final few.

### 4a. Open the board

- [ ] **Do:** Open the generated gallery in a browser (open the file *in place* so the
  thumbnails resolve):
  ```bash
  open "studies/claude-monet/gallery.html"
  ```

- **Expect — Stage 1 (wide board):** A grid titled **"Curation board — Claude Monet"** with
  a count (`N works · 0 selected · N shown`) and controls: a **stars** filter, a
  **public-domain only** checkbox, a **sort** dropdown (year ↑ / stars ↓ / file size), and
  buttons **"Export stars + selection"** and **"Next → zoom."** Each card shows the
  thumbnail, title, museum · date, a **PD** or **©** badge, five clickable **stars**, a
  **select** checkbox, and a **source ↗** link.

- [ ] **✓ Verify:** Thumbnails render (not broken images). Badges are present.

### 4b. Rate and select

- [ ] **Do — rate:** Click stars on a few cards (1–5★). Ratings are **persistent** — they
  survive future runs.
  **✓ Verify:** Stars fill gold and stay set; the **sort → stars ↓** option reorders by them.
- [ ] **Do — filter/sort (smoke test):** Try the **stars** filter (e.g. ≥3), the
  **public-domain only** checkbox, and each **sort** option.
  **✓ Verify:** The grid and the "… shown" count update accordingly.
- [ ] **Do — select a wide cut:** Tick the **select** checkbox on roughly **6–10** works you
  might want to study. Selecting is **independent of rating** — selecting never changes a
  star, rating never selects.
  **✓ Verify:** Selected cards highlight; the header "… selected" count rises. Confirm that
  starring a card does **not** auto-select it (this orthogonality is a key UAT check).

### 4c. Zoom in and narrow

- [ ] **Do:** Click **"Next → zoom."**
- **Expect — Stage 2 (zoom):** The grid re-renders showing **only your selected works** at
  large size for close looking. Header reads `zoom · N in wide cut · M study set (max 4)`.
  Buttons change to **"← Back"** and **"Commit study set"** (disabled until 1–4 are selected).
  > Full-size images are hotlinked from the museum at view resolution and need internet; if
  > one fails to load it falls back to the local thumbnail.
- [ ] **Do — narrow:** Un-check works in the zoom view until **4 or fewer** remain selected —
  these are your **study set**.
  **✓ Verify:** The `M study set` count tracks your selections; **"Commit study set"** enables
  only when 1–4 are selected and stays disabled at 5+.
- [ ] *(Optional)* Click **"← Back"** to confirm it returns to the wide board and clears the
  zoom cut, then redo Next.

### 4d. Commit and hand the files back

- [ ] **Do:** Click **"Commit study set."**
- **Expect:** The status line reads *"saved stars.json + selection.json + study-set.json
  (M to study)."* Three files download to your browser's download folder (usually
  `~/Downloads`).
- [ ] **Do — move the three files into the study folder:**
  ```bash
  mv ~/Downloads/stars.json ~/Downloads/selection.json ~/Downloads/study-set.json \
     "studies/claude-monet/"
  ```
  **✓ Verify:** `studies/claude-monet/` now contains `stars.json`, `selection.json`, and
  `study-set.json`. (`study-set.json` lists your ≤4 works; `selection.json` is the wider cut.)
- [ ] **Do — resume the skill:** Tell Claude you're done:
  > Done — I've committed the curation, files are in the study folder. Continue.

> **Alternative path (partial save):** On the wide board you can click **"Export stars +
> selection"** instead — it saves `stars.json` + `selection.json` only (no study set), for
> when you want to stop and pick later. The main UAT path uses **Next → Commit** so a
> `study-set.json` exists for the stages that follow.

---

## 5. Stage 6 — Socratic curation interview (you answer)

- **Expect:** Claude resumes, validates your files, and starts an **AI-led interview, one
  study-set work at a time.** It will **not** tell you the lesson — it asks what your eye
  does, pushes you to name the underlying *rule* (not just features), redirects you from
  story/iconography back to technique, and ends each work by helping you design a **drill**
  with a success test.

- [ ] **Do:** Answer in your own words for each of your ≤4 works. Describe what you see, then
  what rule produces it, then what you'd practice to steal that rule.
- [ ] **✓ Verify:**
  - [ ] The interview covers **each** work in your study set, one at a time.
  - [ ] It steers *later* works toward lessons that **don't overlap** earlier ones (coverage,
        not repetition).
  - [ ] On finishing, `studies/claude-monet/study-briefs.md` exists and contains, per work, a
        thesis / anchor trait / ordered study plan in language drawn from **your** answers.

---

## 6. Stage 7 + Human Pause 2 — synthesis and confirm

- **Expect:** Claude writes `preference-synthesis.md` — the pattern across your study set plus
  a ranked study funnel — then **stops at Human Pause 2** asking you to confirm the final
  small study set.
- [ ] **✓ Verify:** `studies/claude-monet/preference-synthesis.md` exists and its reasoning
  reflects the works you actually chose.
- [ ] **Do:** Confirm the set (or adjust if asked), e.g.:
  > Confirmed — proceed with these.

---

## 7. Stages 8–9 — analysis and study aids (automatic)

- **Expect:** Claude runs the deep visual analysis and emits the study/retention aids, then
  reports completion.
- [ ] **✓ Verify — final outputs:**
  - [ ] `analysis.md` — a 5-stage formal analysis per study-set work, cross-checked against
        the artist's grammar.
  - [ ] `study-notes.md` — **faded-aid** notes (full cheat sheet → checklist → bare prompt).
  - [ ] `drills/` — perceptual discrimination cards (is-A / is-not-A).
  - [ ] `review-schedule.md` — a spaced + interleaved review plan.
  - [ ] `images/selected/` — high-res files **only for public-domain** study-set works (an
        in-copyright artist will instead carry reference links — confirm no in-copyright image
        was downloaded).
  - [ ] `prompts/` — the prompts used, for reproducibility.

- [ ] **✓ Verify — Obsidian-native:** Open the repo folder as an Obsidian vault. In
  `studies/claude-monet/`, confirm files have YAML frontmatter, `[[wikilinks]]` resolve in the
  graph, tags (`#artist/…`, `#movement/…`, `#source-grade/…`) appear, and study callouts
  (`> [!tip]`, `> [!warning]`) render. No raw `<br>`-style broken line wrapping in reading view.

**🎉 End-to-end happy path complete.** Record the overall result in the Findings log.

---

## 8. Optional branches (run if testing these features)

### A. Resume after interruption
- [ ] **Do:** Stop Claude mid-run (e.g. at Human Pause 1), then in a fresh message say:
  > Continue the Claude Monet study.
- **✓ Verify:** It reads `state.json`, reports the next stage, and picks up where it left off
  rather than restarting. Completed stages are not redone.

### B. New study session over the same board (skip-discovery)
- [ ] **Do:** After a full run, start another session without re-collecting images:
  > Study Claude Monet again — skip discovery, I want a fresh study session.
- **✓ Verify:** It **skips** image discovery (reusing the existing board/candidates), takes
  you straight to the curation funnel, and a previously-studied work shows a **studied ✓
  badge** in the gallery but is still selectable.

### C. Import your own images
- [ ] **Do:** Point the skill at a folder of your own photos of the artist's works:
  > I have my own photos of some Monet paintings in ~/Pictures/monet — import them into the study.
- **Expect:** Claude looks at each image, guesses `{artist, title, date}`, and the pipeline
  corroborates. It writes `import-review.html` / `import-review.json` and **pauses**.
- [ ] **Do:** Open `studies/claude-monet/import-review.html`, review the guesses, edit any
  `proposed` rows in `import-review.json`, and set a row's `state` to `confirmed` to keep it.
  Then tell Claude to ingest.
- **✓ Verify:** Confirmed images are copied into `images/user/`, appear on the board with a
  **USER** badge, and an already-known work is **enriched** (gets your local file) rather than
  duplicated. `off_artist` / `unidentified` rows are **not** ingested.

---

## 9. Reset between UAT passes

To re-test from scratch on the same artist, remove its study folder:
```bash
rm -rf "studies/claude-monet"
```
(Studies are gitignored runtime artifacts; deleting one does not touch the skill or repo.)

---

## 10. Findings log

Record anything that deviated from **Expect** / **✓ Verify**. Severity: **blocker** (can't
proceed), **major** (wrong output), **minor** (cosmetic), **note** (observation / idea).

| # | Step | What I expected | What actually happened | Severity | Notes |
|---|------|-----------------|------------------------|----------|-------|
|   |      |                 |                        |          |       |
|   |      |                 |                        |          |       |
|   |      |                 |                        |          |       |

**Overall result:** ☐ Pass ☐ Pass with minor issues ☐ Fail
**Artist tested:** ____________________  **Date:** ____________________
