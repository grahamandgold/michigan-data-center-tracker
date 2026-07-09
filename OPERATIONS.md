# Michigan Data Center Tracker — Operations Runbook

How the newsroom actually runs: the public site, the editorial desk, the AI agent
fleet, the data files they share, and the flows that connect them.

Brand: **Graham & Gold**. Public site:
<https://grahamandgold.github.io/mi-data-center-tracker/>

---

## 1. The big picture

Three moving parts:

| Part | What it is | Where it runs |
|------|------------|---------------|
| **Public site** | Static site (homepage, live map, stories, meetings, embeds) | GitHub Pages |
| **Intel Desk (CMS)** | FastAPI app the editor uses to approve/kill stories & review reader tips | Locally, on the News Director's Mac |
| **Agent fleet** | Python scripts that gather, write, judge, and publish | GitHub Actions (scheduled) |

**Git is the database.** There is no server database. Editorial state lives in JSON
files in this repo. Agents and the desk commit changes; the site hot-loads them.

**Two repositories:**
- **`mi-data-center-tracker`** (this repo) — the public site + agent scripts + data files.
- **`michigan-intel-desk`** — the FastAPI CMS ("the desk") the editor uses.

---

## 2. Data files (the database)

| File | Purpose |
|------|---------|
| `live-data.json` | Published stories + meetings shown on the site |
| `live-data-pending.json` | The desk's **approval queue** — agents file here; editor approves → live |
| `community-tips.json` | **Reader tips** from the "Idea?" widget; Emmy fact-checks; editor reviews |
| `map-data.json` | The map — **the source of truth for every stat** |
| `content-data.js` | Homepage stats (`window.MDCT_STATS`), recomputed from `map-data.json` |
| `desk-decisions.json` | Kills — so agents never re-file a killed story |
| `desk-lessons.json` | Trainable corrections the agents re-read before every run |
| `agenda-brief.json`, `training-report.json` | Agenda intel, newsroom scorecard |

**Rule: the map is truth.** Every headline stat (projects, GW, pauses, communities,
projects-by-region) is derived from `map-data.json` by `scripts/compute_stats.py`.
Never hand-edit stats — fix the map, and stats follow.

---

## 3. The agent fleet (`.github/workflows/`)

Each agent is a Python script in `scripts/`, run on a schedule by a workflow. Every
agent commits through **`scripts/safe_commit.sh`** (rebase-retry loop; never fails a
run or loses work even when agents push at the same time).

| Workflow | Cadence | What it does |
|----------|---------|--------------|
| `wire-refresh.yml` | Hourly | Google News ingest → Grok wire agent → headline accuracy check → second-model newsworthiness judge → auto-publish fresh high-confidence items. Files into `live-data-pending.json`. |
| `agenda-scout.yml` | 4:30pm & 5:45am ET | Investigates meeting agendas, packets, scanned PDFs |
| `capitol-watch.yml` | 4× daily | Watches the Michigan Legislature (needs `LEGISCAN_API_KEY`) |
| `map-scout.yml` | Daily 7am ET | Map records → pull requests (Emmy / Data Center Editor's beat) |
| `compute-stats.yml` | On `map-data.json` change | Recomputes `content-data.js` from the map |
| `map-hygiene.yml` | Daily | Removes past meetings / one-off events from the map |
| `daily-podcast.yml` | 7am & 6pm | **The Gigacast** — Graham & Emmy daily show → `pod/latest.mp3` |
| `tip-research.yml` | On `community-tips.json` change + every 30 min | **Emmy fact-checks new reader tips** |
| `story-pages.yml` | On publish | Builds individual story pages |
| `lessons-audit.yml`, `training-report.yml` | Daily | Maintains the trainable-newsroom lessons + scorecard |

---

## 4. Editorial flow (agents → desk → live)

1. Agents file candidate stories into **`live-data-pending.json`**.
2. The editor opens the desk (`/today`) → **reviews the queue** → **Approve** (commits to
   `live-data.json`; the site hot-loads within seconds) / **Hold** / **Kill**.
3. **A story never leaves the homepage until a fresh one is approved to replace it.**
4. Fresh Google-News items with fully-rewritten headlines can auto-publish (high
   confidence, < 12h old); everything else waits for the editor.
5. Kills are remembered (`desk-decisions.json`) so agents never re-file them. Notes
   left on a kill become **lessons** the agents re-read.

---

## 5. Reader Tips flow ("Idea?" widget → Emmy → editor)

1. A reader clicks the floating **"Idea?"** widget (Emmy, the Data Center Editor) on the
   site and sends a tip (+ optional email, + optional newsletter opt-in).
2. The tip POSTs to **`/api/community-question`** and is written to
   **`community-tips.json`** with `status: "new"`.
   > ⚠️ **The public site cannot reach the desk on `localhost`.** As shipped, if the
   > endpoint is unreachable the widget falls back to **emailing andy@** so no tip is
   > lost. To make public tips flow straight into `community-tips.json`, see §8.
3. **Emmy's research agent** (`scripts/tip_research.py`, via `tip-research.yml`)
   fact-checks every new tip with live web search and writes a structured brief into
   `emmy_research` (verdict, summary, evidence, sources, map-impact, what-to-verify-next),
   then flips status to `researched` — **before the editor ever sees it.**
4. The editor opens the **Reader Tips panel** on the desk → reads Emmy's findings →
   leaves **research notes** → marks **Reviewed** / **Dismissed**.

---

## 6. The newsroom (personas)

AI-run, human-edited. Personas appear with photos; the site is transparent that it is
an AI-run, human-edited newsroom.

| Person | Role |
|--------|------|
| **Andy Gillfillan** | News Director (human) |
| **Graham** | Managing Editor · co-hosts The Gigacast |
| **Emmy** | Data Center Editor · co-hosts The Gigacast · runs the map beat + reader-tip research |
| Head Writer, Standards Editor, Political Director, Assignment Manager, Newsletter Producer, Streaming Producer, Archive Librarian | Background agents |

---

## 7. The homepage bundle — **read before editing the homepage**

The homepage is a **compiled bundle**. `index.html` contains a JSON-encoded template
inside `<script type="__bundler/template">`.

- **`Homepage.dc.html`** is the editable **source**.
- To change the homepage: edit `Homepage.dc.html` **and** apply the same change to the
  bundle template using `scripts/productionize_homepage.py`
  (`extract_template_from_bundle` → edit → `inject_template_into_bundle`). Keep source
  and bundle in sync.
- **Never** hand-edit the JSON-encoded template string, and never do a raw string
  replace on `index.html` that could cross the template boundary — that corrupts the
  bundle (symptoms: sections silently disappear from the compiled page while the source
  still looks fine).
- The bundler **strips empty elements** and does not apply `::before/::after` or
  `nth-child` animations — for animated decorations use inline **SVG + SMIL** (see the
  Gigacast radio-wave rings) or JS-injected elements (see the "Idea?" widget in
  `mdct-editorial.js`).
- Site-wide floating UI (the share FAB and the "Idea?" widget) is injected by
  `mdct-editorial.js` **after** the bundler renders, so it survives the body re-render.

---

## 8. Running the desk (CMS)

```bash
cd michigan-intel-desk
PYTHONPATH=src .venv312/bin/uvicorn mmt.desk:app --host 127.0.0.1 --port 8800
# then open:  http://127.0.0.1:8800/today
```

- There is **no `--reload`** — after changing desk code, **kill and restart** the process.
- The desk reads/writes this repo via the Mac's **`gh` CLI** login (fallback:
  `MDCT_GITHUB_TOKEN`). No secrets are stored in the repo.
- Localhost access bypasses auth. Over a tunnel it requires `DESK_USER` / `DESK_PASS`.

**Key desk endpoints:**
`/today` (CMS UI) · `/api/mdct/queue` (approval queue) · `/api/mdct/tips` (reader tips) ·
`/api/mdct/tips/update` (note/status) · `/api/community-question` (public tip intake).

**Exposing the tip endpoint publicly (optional):** run the desk behind a tunnel
(cloudflared/ngrok), set **`DESK_PUBLIC_FEEDBACK=1`** (opens *only* `/api/community-question`),
and set **`window.MDCT_FEEDBACK_URL`** on the site to the tunnel's
`/api/community-question` URL. The endpoint is hardened (honeypot, length caps, per-IP
rate limit).

---

## 9. Secrets / keys

- **GitHub Actions:** `XAI_API_KEY` (Grok — wire, judging, live search, tip research),
  `ANTHROPIC_API_KEY`, `OPENAI_API_KEY` (fallbacks), `LEGISCAN_API_KEY` (capitol-watch).
- **Desk:** the Mac's `gh auth` token (or `MDCT_GITHUB_TOKEN`).

---

## 10. Deployment & the cache gotcha

- Push to `main` → **GitHub Pages** rebuilds the site (the "pages build and deployment"
  Action; can queue for a few minutes).
- GitHub serves the HTML with a **10-minute browser cache**. After a deploy, a normal
  refresh may still show the old page. To see changes immediately: **hard refresh
  (Cmd+Shift+R)** or open in an **Incognito window**. This is browser cache, not a revert.

---

## 11. Honesty & legal guardrails (standing rules)

- **No lies anywhere on the site.** Every stat traces to `map-data.json`. No fabricated
  subscriber counts, no invented data.
- **No scraping Facebook/X** for content (legal risk). Community input comes through the
  reader-tip widget (human tips) only.
- Headlines are always rewritten in our own words and **linked to the original source**.
