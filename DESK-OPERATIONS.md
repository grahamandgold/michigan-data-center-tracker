# DESK OPERATIONS — How the Michigan Intel Desk runs this tracker

**For any AI or developer working on this system. Read before changing anything.**
Last updated: 2026-07-08. Companion doc: `GROK-AGENT-PLAYBOOK.md` (agent details) and the master report on Andy's Desktop.

## The two-repo architecture

| Repo | Role |
|---|---|
| **`grahamandgold/mi-data-center-tracker`** (this repo, public) | The live site (GitHub Pages) + the agent fleet (GitHub Actions) + all shared state files |
| **`grahamandgold/michigan-intel-desk`** (private) | The CMS. FastAPI app on Andy's Mac: `PYTHONPATH=src uvicorn mmt.desk:app --port 8800`. Branch `ui/today-michigan-intel-desk-v2`. Bridge code: `src/mmt/mdct_bridge.py`; UI: `src/mmt/static/today.html` + `inside.html` |

**Publishing model: nothing story-shaped goes live without Andy (the News Director).**
Agents file candidates into `live-data-pending.json`. Andy approves/holds/kills/sends-back from the desk (`/today` on :8800). Approve = the desk commits the story into `live-data.json` via the GitHub Contents API (authenticated with the Mac's `gh` CLI login, committer "intel-desk"). The site hot-loads `live-data.json`, so approvals are live after the ~1–2 min Pages deploy. Meetings auto-publish (deterministic, link-checked). Map changes arrive as PRs only.

## Shared state files (repo root — the entire protocol)

| File | Written by | Read by | Purpose |
|---|---|---|---|
| `live-data.json` | desk (approvals), wire agent (meetings only), podcast reads it | the live site | **Approved** stories + meetings + national |
| `live-data-pending.json` | wire agent, capitol watch, agenda scout, desk (removals) | desk queue | Candidates awaiting the News Director |
| `desk-decisions.json` | desk | wire agent | Killed URLs — agents never re-file them |
| `desk-rework.json` | desk ("send back" notes) | wire agent | Rework orders: re-report with the fix (≤48h old honored, then ignored) |
| `desk-lessons.json` | desk (auto: every rework/kill note) | wire agent | **Training memory** — last 30 corrections injected into every run |
| `agent-notes.json` | desk Settings page | wire, podcast, agenda scout | Standing instructions per agent or "All agents" |
| `pod/script-override.json` | desk Radio page | podcast agent | If dated today: Graham & Emmy read the News Director's edited script verbatim |
| `agenda-brief.json` | agenda scout | newsletter builder | "Inside the agendas" bullets for the 7am send |

## The agent fleet (GitHub Actions, `.github/workflows/`)

| News Team name | Workflow | Schedule (UTC) | Does |
|---|---|---|---|
| Head Writer + Managing Editor + Standards Editor | `wire-refresh.yml` | hourly :15 | Hunts news + X/Reddit → headline/journalism check → files to pending. Reads notes + lessons + rework orders every run |
| Assignment Manager | `agenda-scout.yml` | 20:30 & 09:45 | Opens tonight/tomorrow's agendas, digs into packet PDFs/site plans/renderings + local coverage → original preview stories to pending + `agenda-brief.json` |
| Political Director | `capitol-watch.yml` | 4×/day | LegiScan bill actions → pending (needs `LEGISCAN_API_KEY` secret) |
| Streaming Producer | `daily-podcast.yml` | 09:45 | ~12-minute Graham & Emmy show from the **approved** wire; honors script-override |
| Data Center Editor | `map-scout.yml` | 11:00 | Map record proposals → **pull requests only** |
| Website Manager | pages-build-deployment | on every commit | Deploys the site |
| Newsletter Producer | manual | — | `python scripts/newsletter_build.py` → `newsletter-latest.html` (now includes agenda intel) |

Secrets (Actions): `XAI_API_KEY` ✅, `ELEVENLABS_API_KEY` ✅, `LEGISCAN_API_KEY` ⚠️ still needed. Never commit keys — public repo.

## Desk API (the bridge, all under `/api/mdct/` on :8800)

`queue` · `queue/decision` (approve/hold/unhold/kill/**redo** with note) · `queue/add` (News Director files a story) · `published` · `meetings` · `meetings/add` · `agents` (real last-seen from Actions runs) · `agents/dispatch` (send an agent out now) · `map` (proxies `map-data.json` — desk map mirrors the site) · `podcast` · `podcast/script` (GET/POST; POST with `revoice:true` dispatches the podcast workflow) · `notes` (+ `notes/delete`) · `decisions`

## The training loop (how agents learn from Andy)

1. **Standing notes** (Settings page) → injected into every matching agent's prompt.
2. **Send back with a note** (review drawer) → story pulled, rework order filed, agent re-reports it next run with the fix — and the note becomes a permanent lesson.
3. **Kill with a note** → lesson recorded.
4. Lessons live in `desk-lessons.json` (last 30) and are re-read before **every** run: "the News Director corrected these before — do not repeat the mistakes."

## Operational notes

- Desk must be running on the Mac to approve; the queue accumulates harmlessly otherwise. Restart: `cd ~/mi-data-center-monitor && PYTHONPATH=src nohup .venv312/bin/uvicorn mmt.desk:app --host 127.0.0.1 --port 8800 >> data/desk-8800.log 2>&1 &`
- `raw.githubusercontent.com` caches up to ~5 min — the desk filters approved/killed items locally so the queue reads correctly anyway. Trust `api.github.com/contents` for ground truth.
- All desk timestamps display Eastern Time.
- The old prototype CMS is frozen at `/legacy`. Don't build on it.
- Editorial rules (all prompts): original headlines, always link the source, never invent anything, political balance, identify people by role, honest link labels (via Facebook / VIDEO:), never claim "verified" — we are a transparent aggregator; document-based agenda reporting cites the document.
- Future: move the desk to the DigitalOcean droplet for 24/7 phone approvals — REQUIRES adding authentication in front of the bridge first. Never expose :8800 publicly without auth.
