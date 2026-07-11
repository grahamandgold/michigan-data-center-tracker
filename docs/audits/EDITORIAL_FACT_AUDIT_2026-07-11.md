# Editorial Fact Audit — Michigan Data Center Tracker

**Date:** 2026-07-11  
**Repo:** `grahamandgold/mi-data-center-tracker`  
**Branch:** `audit/editorial-facts-2026-07-11`  
**Mode:** Read-only editorial audit; no public facts changed in this commit  
**Status:** HOLD

## Executive finding

The public tracker is **not ready for a factual refresh or relaunch without a controlled correction pass**. The repository contains a mix of current records, stale daily copy, incomplete primary-source support, cross-project configuration leakage, duplicated or possibly misattributed political quotes, and source-quality violations.

This audit reviews the actual repository files rather than proxy trackers.

## Launch blockers

### 1. Cross-project newsletter configuration

**File:** `content-data.js`  
**Current value:** The newsletter form posts to a `fortlauderdalesignal.us2.list-manage.com` Mailchimp endpoint.

**Risk:** Florida Signal configuration is embedded in the Michigan public product. This is a system-boundary violation and could route Michigan subscribers to the wrong audience/account.

**Required action:** Replace only after Andy confirms the correct Michigan list/form endpoint. Until then, disable the signup or show `NOT CONNECTED`.

### 2. Daily homepage copy is stale as of July 11

**File:** `content-data.js`

Examples:

- “Lenox Township board convenes tomorrow” dated July 8 for a July 9 meeting.
- “Saline Township trustees meet tonight” dated July 8.
- The meeting list still includes July 8, July 9, and July 10 meetings.
- `window.MDCT_UPDATED` remains July 8.

**Risk:** Time-relative language is now false on the live site.

**Required action:** Remove or rewrite expired relative language and rebuild the meetings list using absolute dates.

### 3. Political quote duplication / attribution risk

**File:** `your-voice-data.js`

The exact quote beginning “Everybody in the state of Michigan…” appears under both Dylan Wegela and Jim DeSana, using the same WKAR story. The current contexts differ, but the quote text is identical.

**Risk:** One of the candidate records may be misattributed. This is a high-risk political accuracy issue.

**Required action:** Verify against the original audio/transcript or remove the quote from both records until attribution is proven.

### 4. Candidate/race status requires official filing verification

**File:** `your-voice-data.js`

The page labels multiple people as active 2026 candidates and presents race subtitles as settled. Candidate status can change rapidly and must be checked against official Michigan filing records.

**Required action:** Verify every candidate against the Michigan Bureau of Elections qualified-candidate list and add a `verified_date` per candidate.

### 5. Map records use weak or mismatched sources while marked Confirmed

**File:** `map-data.json`

Examples:

- Monroe Power Plant uses Wikipedia / EIA while marked `Confirmed`.
- Belle River, Alpine, Zeeland, Dearborn Industrial, Gratiot Farms, Lake Winds, and Apple Blossom use Wikipedia as the linked source while marked `Confirmed`.
- Presque Isle Power Plant links to a Michigan Public story about the Palisades restart, not Presque Isle.
- Several generic utility homepages are used instead of record-level evidence.

**Risk:** The public confidence label overstates evidence quality and violates the primary-source editorial standard.

**Required action:** Replace with EIA plant records, utility plant pages, MPSC filings, or downgrade confidence to `Reported` / `Needs verification`.

## High-priority project findings

### Saline Township / Stargate

**File:** `map-data.json`

Current record correctly says `Under construction`, but the note says “Full construction targeted early 2026,” which is stale after the June 2026 groundbreaking/construction update.

**Correction needed:** Replace future-target wording with current construction status and add the consent-judgment approval path. Use township/court/EGLE records as primary support.

### Van Buren Township / Project Cannoli

**File:** `map-data.json`

Current status is `Proposed`, while the note says the wetland permit remains pending. The record needs a two-part status that distinguishes local approvals from the unresolved state wetland permit.

**Correction needed:** Use wording such as `Locally approved; state wetland permit pending` only after township and EGLE records are attached.

### Lyon Township / Project Flex

**File:** `map-data.json`

Current status is `Conditionally approved`, but the verification date is September 2025 and the source is a news report.

**Correction needed:** Re-verify against current Lyon Township minutes and explicitly state whether the township moratorium applies to this project.

### Lowell Township

**File:** `map-data.json`

Current record lists Franklin Partners and a “top-10 U.S. company” tenant with a December 2025 verification date. The daily content separately says Microsoft is eyeing a five-building campus.

**Risk:** The map and daily editorial language may be describing the same project with different named entities.

**Correction needed:** Resolve developer, applicant, and end-user identities from the current township application packet.

### Southfield / Metrobloks

**File:** `map-data.json`

Current status is `Approved`, based on a December 2025 news story. No current construction-start evidence is attached.

**Correction needed:** Keep `Approved` only if the approval record is linked; do not imply active construction.

## Moratoria findings

### Count and scope mismatch

**Files:** `content-data.js`, `map-data.json`

`window.MDCT_STATS` reports `pauses: 33` and `communities: 74`. The audit supplied by Grok says newer reporting indicates 50+ communities with pauses, but that report did not verify the exact repo list.

**Finding:** The tracker may be counting only mapped records, while the homepage language may be read as a statewide total.

**Required action:** Label the number explicitly as `tracked pauses` unless every Michigan jurisdiction has been verified.

### Expiration risk

Many moratorium records contain a duration but no calculated expiration date or extension status. Examples include Armada, Springfield, Pontiac, Lenox, Lodi, Hayes, East Lansing, and Saginaw.

**Required action:** Add fields for:

- adoption date
- original expiration date
- extension date
- current legal status
- last verified date

Do not label a moratorium simply `Confirmed` after its original term may have expired.

### Detroit classification

The Detroit record is named “moratorium (proposed)” but its `status` field is `Moratorium`.

**Risk:** The map styling can imply an enacted legal pause when the note says council only requested one.

**Required action:** Change status to `Proposed moratorium` unless an enacted ordinance is verified.

## Politics / Your Voice findings

### Disclaimer overpromises

**File:** `your-voice-data.js`

The disclaimer says every quote is copied from a linked public source. That is not enough to establish speaker attribution when one article contains multiple speakers.

**Required action:** Add quote-level verification notes and preserve transcript/audio proof where available.

### District metadata must be checked

The page hard-codes district subtitles, centroids, and county arrays. At least one record is internally incomplete: HD-53 is labeled “Berrien & Cass counties” while the `counties` array contains only `Berrien`.

**Required action:** Validate district geography against official 2026 district maps and correct county arrays/ZIP lookup behavior.

### Missing balance / candidate completeness

Several races contain only one listed officeholder or candidate. The page should not imply a complete ballot unless every qualified candidate is included.

**Required action:** Add `coverage_status: incomplete` until the official candidate list is reconciled.

## Statistics findings

**File:** `content-data.js`

The comment says stats were computed from `map-data.json` and updated June 29, while the map file itself was updated July 11.

**Risk:** The displayed totals may no longer match the current dataset.

**Required action:** Re-run `node scripts/compute-stats.mjs`, compare output to the current map, and commit generated numbers with a timestamp.

## Source-quality violations

The repository standard says public factual claims should be traceable and current. Current map records still rely on:

- Wikipedia
- generic utility homepages
- unrelated articles
- news stories where official records should exist

**Required action:** Replace with record-level sources from:

- township/city agendas and minutes
- EGLE permit records
- MPSC dockets
- Michigan Legislature bill pages
- EIA plant-level records
- official company filings/releases
- court filings/consent judgments

## Definite corrections safe to make after approval

1. Remove stale “today,” “tonight,” and “tomorrow” language from expired July 8–10 items.
2. Update `window.MDCT_UPDATED` only when the content is actually refreshed.
3. Disable or replace the Florida Mailchimp form.
4. Change Detroit from `Moratorium` to `Proposed moratorium` unless enacted status is proven.
5. Remove/downgrade Wikipedia-backed `Confirmed` labels.
6. Correct the Presque Isle source mismatch.
7. Recompute stats from the current map data.
8. Hold duplicated political quotes until speaker attribution is verified.

## Correction workflow

1. Create a claim inventory from `map-data.json`, `content-data.js`, and `your-voice-data.js`.
2. Attach one primary source to every corrected claim.
3. Mark unresolved claims `UNKNOWN` or `NEEDS VERIFICATION` rather than guessing.
4. Make corrections on one branch and one draft PR.
5. Do not merge or publish without Andy’s explicit approval.

## Recommendation

**HOLD.**

The next commit should correct only the definite errors above and add verification metadata. Project-status, moratorium, and candidate changes should wait for record-level primary-source confirmation.
