# NotebookLM deep-research runbook

How to add a new numbered research report to `raw/` via NotebookLM. Conventions and rules
(all access via `/ntlm`, prompt < 300 words, one notebook per topic) live in `CLAUDE.md`
§"Deep research (NotebookLM)"; this is the step-by-step + the topic→notebook map.

## Pipeline

All NotebookLM access goes through the **`notebooklm-jayers` skill** (`/ntlm`) — never wire
the raw `notebooklm-mcp` into this repo. Run from the repo root, `nlm` on PATH at
`~/.local/bin`. The report is a NotebookLM **studio "report" artifact**; the skill detects it,
numbers the file, and writes Obsidian frontmatter.

1. Save the prompt as `raw/NN-<slug>-prompt.md`.
2. Discover sources (~5 min): `nlm research start "<concise query>" --mode deep --title "artist-study-kit: NN <topic>"`.
   Note the returned **notebook id** and **task id**. (Keep the query short — overly long queries can yield zero sources.)
3. Import once complete: `nlm research import <notebook-id> <task-id> --timeout 300`.
   Discovery can run past the 5-min estimate with `source_count` stuck at 0, then land all at once;
   a premature import prints "No sources were found" — re-probe with `nlm research start "probe" -n <nb> --mode fast`
   (answer `n`), which reports "sources available: N" when ready, then import.
4. Generate the report: `nlm report create <notebook-id> --format "Create Your Own" --confirm --prompt "<the research prompt>"`.
   Returns an **artifact id**.
5. Wait: poll `nlm studio status <notebook-id>` until the report artifact is `completed`.
6. Extract to the tree path via the skill:
   `uv run --no-project ~/.claude/skills/notebooklm-jayers/get_deep_research_report.py <notebook-id> --number NN.1 --slug <topic-slug>`
   → writes `raw/NN.1-<topic-slug>.md` with YAML frontmatter. Use `--slug` to match the prompt's
   topic slug (without it, the filename auto-derives from the report title).

## Topic → notebook map

- `01` web scraping tooling → `72ddf4cf-41dc-4c65-8b93-c43e01936219`
- `02` source quality grading → `fe59cf3e-bbcb-4e2b-9bcb-6ead3f3d2d1a`
- `03` museum image apis → `f89f6f2f-84c1-42e8-9e90-e420aa7aeb9a`
- `04` style analysis frameworks → `2792f9bf-2ebc-44b5-bb0f-2ca993d8cd57`
- `05` master study pedagogy → `0daad4a4-2862-4528-9d80-fcb3bbed10d0`
- `06` productive friction learning → `a0c8d5f2-bf87-4d31-8405-529582aacff2`
- `07` study aids scaffolding → `459f962b-15a8-428e-aa67-fa74484c1ee9`
- `08` spaced repetition retention → `3c7c8d72-84a1-4ebc-8ec8-3d38d99b5806`
- `11` artist background research → `d2c20815-2f7f-4165-8314-88a318e0d2e7`
- `12` works inventory method → `2cf4ccd2-0a0f-406a-91fd-a1c3ec4fe2f1`
- `13` human curation ux → `c7723fe4-2a83-47de-9a2f-dd29e5c2a038`
- `16` image source hierarchy → `8260e980-d7cc-42f3-9c4f-4c24e054221f`
