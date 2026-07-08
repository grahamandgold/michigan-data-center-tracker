# Michigan Data Center Tracker

Independent public-source tracking of Michigan data center projects, public meetings, moratoria, power, water, and policy.

**Live site:** https://grahamandgold.github.io/mi-data-center-tracker/

**AI assistants:** read [`AI_HANDOFF.md`](AI_HANDOFF.md) and [`docs/REPO_BOUNDARIES.md`](docs/REPO_BOUNDARIES.md).

---

## What this site is

Public-facing static product site. It displays **approved/exported** outputs from [Michigan Live Desk](https://github.com/grahamandgold/michigan-intel-desk) — not raw pipeline data.

| Does not use | Why |
|--------------|-----|
| Raw `mmt.db` | Private Desk datastore |
| Live `source_checks/` | Private pipeline input |
| Google Drive | Not a live CMS |
| `florida-signal-prod` Supabase | Florida Signal only |

Coverage language should say **tracked**, **monitored**, or **updated as records are detected** — not real-time statewide completeness unless verified.

---

## Pages

- `index.html` — responsive homepage (Live Wire, On Deck, hero map teaser, stats)
- `map/` — interactive live map
- `stories.html` — The Wire / published stories
- `meetings.html` — hearings and public meetings
- `learn.html` — methodology and sources
- `sponsor.html` — partnership / support
- `handoff/` — design source + CMS wiring notes

## Data layers

- `content-data.js` — **daily editorial updates** (wire, stories, meetings, watch list, stats)
- `mdct-editorial.js` — shared render helpers (recency badges, date formatting)
- `map-data.json` — sourced map export (projects, moratoria, meetings)
- `geo/` — Michigan county and infrastructure GeoJSON
- `map-points-data.js` — sync fallback for map pins
- `map-layers-data.js` — transmission and grid overlays
- `map-data.json` — consolidated map records

## CMS wiring (not live yet)

`site-config.js` sets `window.MDCT_CMS = window.MDCT_CMS || ''` — blank until explicitly wired to approved Desk export endpoints.

Public Meeting Tracker (`publicmeetingtracker.com`) is a separate future consumer of approved Desk outputs.