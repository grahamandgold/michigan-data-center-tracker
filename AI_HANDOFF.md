# AI Handoff — Michigan Data Center Tracker

**Last updated:** 2026-07-03

Public static site repo. **Not** the Michigan Live Desk pipeline.

---

## Read first

1. [`README.md`](README.md)
2. [`docs/REPO_BOUNDARIES.md`](docs/REPO_BOUNDARIES.md)
3. Michigan Live Desk: `grahamandgold/michigan-intel-desk` → `README_STAGING_STATE.md`

---

## Rules

- Consumes **approved/exported** Desk outputs only
- `window.MDCT_CMS` is blank — not wired to live Desk yet
- Do not connect to raw `mmt.db`, live `source_checks/`, or Google Drive as live feed
- Do not connect to `florida-signal-prod` Supabase
- Do not imply complete statewide live coverage unless verified
- Florida Signal, WKAR, Pink Boat, and client sites are separate projects

---

## Source of truth

| Layer | Role |
|-------|------|
| This repo `main` | Public site code and static data |
| Michigan Live Desk | Private editorial engine — exports approved content |
| Google Drive | Docs mirror only — not live CMS |