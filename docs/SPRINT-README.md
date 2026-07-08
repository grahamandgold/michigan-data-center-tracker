# The 72-Hour Sprint — shipped in one session

Everything below drops into `grahamandgold/mi-data-center-tracker` (the public repo),
preserving paths. Nothing touches the desk repo; the desk keeps working unchanged.

## Deploy (10 minutes)

1. Copy this folder's contents into the repo root (same paths). New files add;
   `scripts/agenda_scout.py`, `scripts/wire_agent.py`, `scripts/podcast_agent.py`,
   and the two existing workflows are **replacements**.
2. Add two repo secrets (Settings → Secrets and variables → Actions):
   `ANTHROPIC_API_KEY` and `OPENAI_API_KEY`. (`XAI_API_KEY` is already there.)
   **Everything degrades gracefully — with only the xAI key, all agents still run.**
3. Optional repo *variable* `JUDGE_THRESHOLD` (default 6).
4. Run the **Lessons audit** workflow once by hand (Actions tab) to compile your
   first structured style guide from the 10 corrections already on file.
5. Delete `newsletter_build.py` and `wire_agent.py` at the repo ROOT if they're
   stale duplicates of `scripts/` (they look like leftovers).

## What each piece does

### Workstream 1 — the agenda desk is now reliable (`scripts/doc_extract.py`, `scripts/agenda_scout.py`)
Extraction ladder: plain fetch → **Playwright** render for Granicus/CivicPlus/
BoardDocs/iCompass portals → pypdf → **vision OCR** on scanned PDFs → vision-read
of the rendered page as last resort. Every story carries a **depth score (0–10)**;
below 6 it files honestly as *"thin — needs human background"* instead of pretending.
New: a **background research step** (prior votes, past minutes, local coverage) and
the journalistic meeting-preview prompt (lede → findings → history → what's next,
never "update"/"latest", sober and numbers-first). Grok drafts with live search;
**Claude polishes and checks attribution** before you ever see it.

### Workstream 2 — the Andy-training system (`multi_ai_client.py`, `news_judge.py`, `lessons_util.py`, `lessons_audit.py`, `training_report.py`)
- **`multi_ai_client.py`** — one router, three model families: hunting→Grok,
  judgment→Claude, extraction/vision→GPT-4o, with automatic fallback.
- **`news_judge.py`** — runs hourly after the wire: Claude grades every Grok pick
  1–10 for newsworthiness + duplicate risk. Below threshold or duplicate → spiked
  and logged to `desk-decisions.json` with the reason (`by: "news_judge"`), so the
  wire never re-files it. Passing items carry `judge_score` into your queue.
- **Structured lessons** — your raw corrections stay exactly as they are (the desk
  writer is untouched). Monthly (or on demand), `lessons_audit.py` compiles them
  into a deduped, weighted, contradiction-resolved style guide (`rules` in
  `desk-lessons.json`). **Every agent — wire, agenda, podcast — now loads the
  compiled rules + any corrections newer than the last compile.** A note you file
  at 2 pm is obeyed by the 3 pm run.
- **`training_report.py`** (Mondays) — proves whether they're learning:
  kill/send-back rates per week, judge interceptions, and **"rules being ignored"**
  (kills that match an existing rule — the ones to upweight).
  Baseline measured today: **45% of items needed your red pen.** Watch that number.

### Workstream 3 — distribution (`embeds/`, `scripts/build_story_pages.py`)
- **`embeds/moratorium-wave.html`** — the ownable visual: 32 pauses spreading
  across an animated Michigan map, month by month, with a play button and a
  one-click iframe embed code. Computes live from `map-data.json`.
- **`embeds/pressure-map.html`** — *Communities Under Pressure*: every community
  weighted by projects + pauses + upcoming hearings; hover shows the next meeting.
- **`embeds/index.html`** — press-room gallery with copy-paste embed codes.
- **`build_story_pages.py`** — static HTML snapshot of every published story with
  NewsArticle JSON-LD + `sitemap-stories.xml`, rebuilt automatically on every
  publish. Submit `sitemap-stories.xml` in Google Search Console.

### New workflows
`lessons-audit.yml` (monthly + manual) · `training-report.yml` (Mondays) ·
`story-pages.yml` (on every publish) — plus updated `wire-refresh.yml` (judge step)
and `agenda-scout.yml` (Playwright/vision stack).

## Giving constant feedback (how to Andy-train, day to day)
Your existing desk actions ARE the training interface — nothing new to learn:
- **Kill with a note** and **Send back with a note** — write the note as a rule
  you'd give a cub reporter ("never X", "always Y when Z"). Those exact words
  become the style guide.
- After a heavy correction day, hit **Run workflow** on *Lessons audit* to fold
  everything in immediately instead of waiting for the monthly compile.
- Read Monday's *Training report* run log: if a rule shows under "rules being
  ignored," rewrite it more concretely in a standing note — that's the highest-value
  5 minutes of training you can do.

## Desk on your phone (tonight, 5 minutes, desk repo side)
Install cloudflared (`brew install cloudflared`), then:
`cloudflared tunnel --url http://127.0.0.1:8800`
It prints a public URL for your phone. Before sharing anything, put auth in front:
quickest is FastAPI HTTP basic auth middleware on the desk app — do that first.

## Still on the list (needs the desk repo, which lives on your Mac)
- Show `judge_score` / `depth_score` badges in the Today queue (fields are already
  in the pending items; it's a small template change in `today.html`).
- Render `training-report.json` as a Settings-page scorecard.
- The trusted auto-publish lane with a 4-hour hold (desk-side logic).
