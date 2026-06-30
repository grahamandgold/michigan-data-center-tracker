# Michigan Data Center Tracker

Independent public-source tracking of Michigan data center projects, public meetings, moratoria, power, water and policy.

**Live site:** https://midatacentertracker.github.io/mi-data-center-tracker/

## Pages (design handoff build)

- `index.html` — homepage (Live Wire, On Deck, hero map teaser, stats)
- `map/` — interactive live map
- `stories.html` — The Wire / published stories
- `meetings.html` — hearings and public meetings
- `learn.html` — methodology and sources
- `sponsor.html` — partnership / support
- `handoff/` — Claude design source + `HANDOFF.md` for future CMS wiring

## Data layers (preserved from prior build)

- `geo/` — Michigan county and infrastructure GeoJSON
- `map-points-data.js` — sourced project and moratorium pins
- `map-layers-data.js` — transmission and grid overlays
- `map-data.json` — consolidated map records

## Next: Meeting Tracker CMS

Set `window.MDCT_CMS` (see `site-config.js`) to the Public Meeting Tracker desk URL to wire The Wire and On Deck to live meeting data.
