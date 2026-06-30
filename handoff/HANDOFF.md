# Michigan Data Center Tracker — Design Handoff

This package is a **design reference build** of the homepage + 5 inner pages, in the
sharp dark-editorial style. Your live repo (`midatacentertracker/mi-data-center-tracker`)
already has its own architecture (`index.html`, `app.js`, `map/`, `geo/`, `assets/`,
GitHub Pages). **Goal: port the new design + behavior into that existing structure** —
do not blindly overwrite `app.js`/`index.html`.

---

## What's in this package

| File / folder | What it is | Use it for |
|---|---|---|
| `dist/homepage.html` | Standalone, fully-inlined homepage (works offline) | Visual reference + copy/markup source of truth |
| `dist/live-map.html` | Standalone Live Map | Reference for map UI/UX |
| `dist/stories.html` `dist/meetings.html` `dist/learn.html` `dist/sponsor.html` | Standalone inner pages | Reference for each page |
| `*.dc.html` (Homepage, Live Map, Stories, Meetings, Learn, Sponsor) | Editable source (template + logic) | Read the structure/logic to port from |
| `assets/mark.svg` | Dotted-Michigan logo mark (also the favicon) | Brand mark |
| `support.js` | Runtime the `.dc.html` files need to render locally | Only needed if you open `.dc.html` directly |

> Fastest way to view: open any `dist/*.html` in a browser. Self-contained.

---

## PROMPT FOR GROK BUILD (paste this)

> You're integrating a finished design into our existing repo
> `mi-data-center-tracker` (static site: `index.html` + `app.js`, deployed via
> GitHub Pages, with `map/`, `geo/`, `assets/`). I've added a `handoff/` folder with
> the reference build (`dist/*.html` are standalone; `*.dc.html` are the source).
>
> Port the new homepage design into our `index.html` / `app.js` — keep our file
> architecture and deploy. Match the reference exactly: sharp hard edges (no rounded
> corners/pills), dark editorial palette (`#100f0e` bg, `#16140f` panels, `#E03131`
> red accent), Saira Condensed + Archivo + Space Mono type.
>
> Bring over these homepage modules in order, top to bottom:
> 1. **Live Wire ticker** — slim red-tagged scrolling headline bar (pulsing "LIVE WIRE" tag, ~64s loop, pauses on hover).
> 2. **Podcast bar** — "Michigan Data Wire", centered on desktop, thinner on mobile, shimmering red play button, plays real audio on tap.
> 3. **Hero** — "Updated daily" eyebrow, headline, you/impact subhead, two CTAs, above-the-fold email capture, and a clickable Michigan map teaser with a big red arrow → links to the map page.
> 4. **The Wire** — lead story (BREAKING badge + county/STATEWIDE tag + red timestamp) beside a tight list; new items (<36h) get a red left accent.
> 5. **On Deck** — skinny one-line hearing rows: date · status (red if "Vote expected") · org + topic · region tag · countdown · time. Agenda + Watch links.
> 6. **Explore tiles**, **By the Numbers** (donut + bars), **Sponsor/Partnership block**, **closing support CTA**, **footer**.
> 7. **10-second fly-in modal** — email + ZIP capture, dismissible, once-per-visitor via `localStorage('mdct_flyin_seen')`.
>
> **Wire The Wire + On Deck to our CMS** (see CMS section below). Keep our `map/`
> and `geo/` as the Live Map. Convert the homepage to a single responsive page (the
> reference shows desktop + mobile as a side-by-side mockup — ship it as one fluid
> responsive page with a sticky header). Then commit to `main` and let GitHub Pages deploy.

---

## Branding requirements baked in (carry these through)

- **"Powered by PublicMeetingTracker.com"** appears (1) under the logo in every header,
  (2) in the mobile menu / desktop nav, and (3) in every footer. It links to
  `https://publicmeetingtracker.com` (separate site, opens in new tab). Keep all three placements.
- **AI-transparency line:** "AI-drafted, journalist-reviewed" shows in every footer and as a
  visible badge in The Wire header (homepage) and the Live Map panel. Keep this language (or your
  approved equivalent) visible — it's an intentional trust signal.

## CMS integration (already designed in, just point it at the desk)

The homepage logic does a **fetch-with-fallback**: it tries the CMS and falls back to
built-in placeholder content if unreachable.

Activate by setting, before the page script:
```html
<script>window.MDCT_CMS = 'http://127.0.0.1:8787';</script>
```

Endpoints it calls:
- `GET /api/stories`  → The Wire
- `GET /api/on-deck`  (falls back to `GET /api/meetings`) → On Deck

Field mapping it accepts (tolerant — first match wins):

**Stories:** `iso` | `published_at` | `date` | `created_at` · `title` | `headline` | `name` ·
`source` | `byline` | `publication` · `cat` | `county` | `region` | `tag` ·
`breaking` | `is_breaking` · `lead` | `is_lead` (first item auto-leads)

**Meetings / On Deck:** `iso` | `date` | `starts_at` (date only) · `body` | `org` | `title` | `name` ·
`topic` | `summary` | `description` · `region` | `area` · `time` | `start_time` ·
`status` | `type` (status containing "vote" → flagged urgent/red) · `urgent`

> If the desk's JSON field names differ, either rename in the desk response or adjust
> the mapper in `renderVals()` / `loadCMS()`. CORS: the desk must allow the page's
> origin, or serve the page from the same origin as the desk.

---

## Still TODO (needs your accounts/server — can't be done in the design tool)

- **Mailchimp (or ESP):** wire the email/ZIP forms (hero, fly-in, hearings alerts, media kit) to a real list. Forms currently show success UI only.
- **Real data:** the Live Map `SITES` array, story feed, and meeting feed are realistic placeholders until the CMS is connected.
- **Hosting/deploy:** commit to `main`; GitHub Pages already deploys this repo.
- **Single-responsive homepage:** convert the desktop+mobile mockup into one fluid page with a sticky header (inner pages are already responsive with sticky headers).
