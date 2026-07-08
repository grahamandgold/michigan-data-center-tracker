#!/usr/bin/env python3
"""Hourly Grok wire agent — refreshes live-data.json with verified
Michigan data center stories from the last 15 hours.

Fail-safe by design:
  * Any API failure, invalid JSON, or weak result -> keep the existing file.
  * Strict validation mirrors the client-side checks in mdct-editorial.js.
  * Story URLs are HEAD-checked; dead links are dropped.
Requires: XAI_API_KEY (repo secret). Optional: XAI_MODEL (repo variable).
Uses only the Python standard library.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
DECISIONS = ROOT / "desk-decisions.json"
API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = os.environ.get("XAI_MODEL", "grok-4")
KEY = os.environ.get("XAI_API_KEY", "")

REGIONS = {"metro", "west", "mid", "north", "statewide"}
TAGS = {"Power & Grid", "Local Government", "Policy", "Water", "Money", "Explainers"}
MEET_REGIONS = {"SE Michigan", "West Michigan", "Mid-Michigan", "Northern Michigan", "Statewide"}

PROMPT = """You are the wire editor for the Michigan Data Center Tracker \
(https://grahamandgold.github.io/mi-data-center-tracker/). Current UTC time: {now}.

MISSION: fill the homepage wire with what is happening RIGHT NOW — real
reporting first. The News Director's standing rule: NO MORE THAN ONE X or
Reddit item per run, and only when it documents something genuinely
newsworthy (an official's statement, a hot community fight). NEVER pad a
thin news cycle with social posts. When outlet news is thin, the right
fill is TONIGHT'S AND TOMORROW'S MEETING PREVIEWS — what's on the agendas
(rezonings, tax abatements, moratorium votes), written from the agenda
pages themselves as preview stories ("Tonight in Saline: …").

1. SEARCH (use web_search first, x_search second) for Michigan data center
news from the LAST 15 HOURS ONLY. Priorities, in order:
   a. Fresh reporting: MLive, Michigan Advance, Bridge Michigan, Crain's, Detroit News, \
Free Press, Lansing State Journal, City Pulse, WOOD TV, WWMT, WXYZ, WKAR, WILX, WNEM, \
IPR, Traverse Ticker, UP outlets.
   b. Official postings and TONIGHT'S/TOMORROW'S agendas: township/city agenda pages, \
legislature.mi.gov (SB 1018-1020, SB 1046-1051, HB 6135-6142), MPSC filings — file \
preview stories about what those bodies decide tonight/tomorrow.
   c. AT MOST ONE X or Reddit item (r/Michigan, r/Detroit, r/grandrapids, r/lansing), \
and only if it's genuinely newsworthy on its own.
For EVERY meeting you report: "link" must be the official agenda page — or the
page where that body posts agendas (AgendaCenter, clerk page). Also check whether
the body streams meetings (YouTube channel, Granicus/Zoom, public-access cable
page) and put that page in "stream". VERIFY every agenda link actually loads before including it — prefer the
body's agenda-LISTING page (AgendaCenter, clerk page, meetings page) over deep
links to individual PDFs, which break. Meetings without a working agenda-location
link are not publishable.

2. HARD RULES:
- NEWS items: target the last 15 hours; stretch to 24 hours to fill. \
- X/REDDIT: maximum ONE item per run, ≤24 hours old, genuinely newsworthy. \
- To reach 8-12 items, use outlet reporting and meeting-preview stories — never more social posts. \
- Never backfill anything older; find TODAY's development instead.
- Write every headline and dek in ORIGINAL, neutral, journalistic language. NEVER \
copy or lightly rearrange a publisher's headline or a post.
- Every item MUST have a real, working https source URL you actually found. For X \
coverage link the specific post (https://x.com/...) from a newsroom, reporter, \
official, or candidate account, and set "source": "X". For Reddit link the specific thread and set "source": "Reddit" — posts document the public conversation; inclusion is not endorsement.
- Never invent a story, meeting, quote, URL, or statistic. Unverified means omitted.
- Deks under 55 words, factual. Note when something is a live/developing event.
- IDENTIFY PEOPLE: give every named person their role on first mention — \
"U.S. Rep. John James, a Republican candidate for Senate", "Sen. Jim Runestad \
(R-White Lake)". Never assume readers know who someone is.
- POLITICAL BALANCE: when covering candidates or a debate, cover ALL major \
candidates' data center positions — not just one. If you ran an item on one \
candidate, search for and include the rivals' statements from the same event. \
If a rival said nothing on the topic, reflect the range of positions in one \
combined debate story instead of a single-candidate item.
- Prefer the outlet's OWN website link over its Facebook/YouTube post when both \
exist. If only a social/video link exists, keep "source" as the outlet name — the \
site labels the destination automatically.

3. Respond with ONLY a JSON object (no markdown fences, no commentary):
{{"updated_at": "<current ISO-8601 UTC>", "generator": "grok-wire-agent",
 "stories": [8-12 items, newest first: {{"iso": "<publication time ISO-8601, best estimate to the hour>",
   "region": "metro|west|mid|north|statewide", "cat": "<County> Co." or "STATEWIDE",
   "tag": "Power & Grid|Local Government|Policy|Water|Money|Explainers",
   "title": "<original headline>", "dek": "<original 1-2 sentence summary>",
   "source": "<outlet or X>", "url": "<https link>", "breaking": <bool>, "lead": <true on exactly one>}}],
 "national": {{one item — the biggest U.S. (non-Michigan) data center story of the \
last 24 hours, pushing ahead to what happens next; same fields and rules as stories}},
 "meetings": [future-dated only: {{"iso": "YYYY-MM-DD", "body": "<government body>",
   "topic": "<what is decided>", "region": "SE Michigan|West Michigan|Mid-Michigan|Northern Michigan",
   "regionKey": "metro|west|mid|north", "county": "<county>", "time": "<h:mm AM/PM>",
   "status": "Public hearing|Board meeting|State hearing|Planning commission",
   "urgent": <bool>, "link": "<official https agenda url>", "linkLabel": "Agenda",
   "stream": "<https live-stream url if one exists, else omit>"}}]}}

Regions: metro = SE Michigan incl. Ann Arbor (Wayne, Oakland, Macomb, Washtenaw, Monroe, \
Livingston); west = Grand Rapids, Holland, Kalamazoo, lakeshore; mid = Tri-Cities, Lansing, \
Jackson, Flint; north = Mt Pleasant northward + the UP.
Give each story your best-estimate publication time (to the hour) as ISO-8601 — \
never omit "iso". Only if you can verify fewer than 3 items in the last 24 hours, \
return {{"stories": []}}. Never pad with old news."""


def director_notes() -> str:
    """Everything the News Director has taught the newsroom, injected into
    every run: standing notes + accumulated lessons + open rework orders."""
    out = ""
    try:
        notes = json.loads((ROOT / "agent-notes.json").read_text(encoding="utf-8")).get("notes", [])
        mine = [n for n in notes if n.get("agent") in ("All agents", "Head Writer", "Managing Editor", "Standards Editor")]
        if mine:
            out += ("\n\nSTANDING NOTES FROM THE NEWS DIRECTOR (these override defaults):\n"
                    + "\n".join(f"- {n['text']}" for n in mine))
    except Exception:  # noqa: BLE001
        pass
    try:
        import lessons_util
        out += lessons_util.lessons_block(agent="wire")
    except Exception:  # noqa: BLE001
        try:
            lessons = json.loads((ROOT / "desk-lessons.json").read_text(encoding="utf-8")).get("lessons", [])
            if lessons:
                out += ("\n\nLESSONS FROM PAST FEEDBACK (the News Director corrected these before — "
                        "do not repeat the mistakes):\n" + "\n".join(f"- {l['text']}" for l in lessons[-15:]))
        except Exception:  # noqa: BLE001
            pass
    try:
        reqs = json.loads((ROOT / "desk-rework.json").read_text(encoding="utf-8")).get("requests", [])
        fresh = [r for r in reqs if fresh_enough(r.get("at", ""), hours=48.0)]
        if fresh:
            out += ("\n\nREWORK ORDERS — the News Director sent these stories back. Re-report each one, "
                    "fixing exactly what the note says, and include the corrected story in this run's output:\n"
                    + "\n".join(f"- '{r.get('title','')}' ({r.get('url','')}) — FIX: {r.get('note','')}" for r in fresh))
    except Exception:  # noqa: BLE001
        pass
    return out


def call_grok() -> dict | None:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(now=datetime.now(timezone.utc).isoformat()) + director_notes()}],
        "search_parameters": {"mode": "on", "return_citations": True,
                              "from_date": (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")},
        "temperature": 0.2,
    }
    import xai_client
    data = xai_client.chat(KEY, body)
    if not data:
        return None
    try:
        text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        print("::warning::unexpected API response shape")
        return None
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        print("::warning::no JSON object in model output")
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        print(f"::warning::model JSON did not parse: {e}")
        return None


def head_ok(url: str) -> bool:
    for method in ("HEAD", "GET"):
        try:
            req = urllib.request.Request(url, method=method, headers={"User-Agent": "MDCT-linkcheck/1.0"})
            with urllib.request.urlopen(req, timeout=12) as r:
                if r.status < 400:
                    return True
        except Exception:  # noqa: BLE001
            continue
    return False


def fresh_enough(iso: str, hours: float = 20.0) -> bool:
    try:
        d = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).total_seconds() <= hours * 3600
    except Exception:  # noqa: BLE001
        return False


def _is_rework_url(url: str) -> bool:
    try:
        reqs = json.loads((ROOT / "desk-rework.json").read_text(encoding="utf-8")).get("requests", [])
        return any(r.get("url") == url for r in reqs)
    except Exception:  # noqa: BLE001
        return False


def valid_story(s: dict) -> bool:
    """Normalize what we can; reject only what we must. Logs every rejection."""
    try:
        if not (isinstance(s.get("title"), str) and len(s["title"]) > 10):
            print(f"::warning::rejected (title): {str(s.get('title'))[:60]}")
            return False
        if not (isinstance(s.get("url"), str) and s["url"].startswith("https://")):
            print(f"::warning::rejected (url): {s.get('title','')[:60]}")
            return False
        social = any(d in str(s.get("url", "")) for d in ("x.com/", "twitter.com/", "reddit.com/"))
        # Desk model: these are CANDIDATES for the News Director, not auto-publishes.
        # A real development the tracker has never carried is filable up to ~2.5 days
        # back (the homepage's own 15-hour guard governs what displays). Rework
        # orders bypass staleness entirely — the News Director asked for them.
        if _is_rework_url(s.get("url", "")):
            pass
        elif not fresh_enough(s.get("iso", ""), hours=38.0 if social else 60.0):
            print(f"::warning::rejected (stale/no iso {s.get('iso')}): {s.get('title','')[:60]}")
            return False
        if s.get("region") not in REGIONS:
            s["region"] = "statewide"
        if s.get("tag") not in TAGS:
            s["tag"] = "Policy"
        if not s.get("cat"):
            s["cat"] = "STATEWIDE"
        if not isinstance(s.get("dek"), str):
            s["dek"] = ""
        if not s.get("source"):
            s["source"] = "Source"
        return True
    except Exception as e:  # noqa: BLE001
        print(f"::warning::rejected (error {e}): {str(s)[:80]}")
        return False


def valid_meeting(m: dict) -> bool:
    try:
        d = datetime.strptime(m["iso"], "%Y-%m-%d").date()
        return (d >= datetime.now(timezone.utc).date()
                and m.get("body") and m.get("topic")
                and m.get("region") in MEET_REGIONS
                and str(m.get("link", "")).startswith("https://"))
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    if not KEY:
        print("::error::XAI_API_KEY secret is not set")
        return 1
    out = call_grok()
    stories = [x for x in (out.get("stories", []) if out else []) if valid_story(x)]
    if len(stories) < 3:
        print("first pass thin — retrying with explicit 24-hour window")
        global PROMPT
        PROMPT = PROMPT.replace("LAST 15 HOURS", "LAST 24 HOURS")
        out = call_grok()
        stories = [x for x in (out.get("stories", []) if out else []) if valid_story(x)]
    if not out:
        print("Keeping existing live-data.json")
        return 0
    checked = []
    for s in stories[:14]:
        if any(d in s["url"] for d in ("x.com/", "twitter.com/", "reddit.com/")):
            checked.append(s)  # X/Reddit block bots; URL came from the search tools
            continue
        if head_ok(s["url"]):
            checked.append(s)
        else:
            print(f"::warning::dropped dead link: {s['url'][:90]}")
    meetings = []
    for m in out.get("meetings", []):
        if not valid_meeting(m):
            continue
        if not head_ok(m["link"]):
            print(f"::warning::meeting dropped, dead agenda link: {m.get('body','')} {m.get('link','')[:80]}")
            continue
        if m.get("stream") and not head_ok(m["stream"]):
            print(f"::warning::stream link dead, removed: {m.get('stream','')[:80]}")
            m.pop("stream", None)
        meetings.append(m)

    # Desk model: file every validated candidate — even one. The News
    # Director decides what publishes; an empty run still prunes the queue.
    if checked:
        leads = [s for s in checked if s.get("lead")]
        for s in checked:
            s["lead"] = False
        (leads[0] if leads else checked[0])["lead"] = True
    else:
        print("::warning::no valid new stories this run — pruning queue only")

    # ------------------------------------------------------------------
    # DESK APPROVAL MODEL: new stories file into live-data-pending.json
    # for sign-off in the Michigan Intel Desk. live-data.json (the live
    # site) keeps only stories the desk has approved. Meetings remain
    # auto-published: they are deterministic and every link is checked.
    # ------------------------------------------------------------------
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    prev_payload = {}
    try:
        prev_payload = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::no previous live-data.json: {e}")
    published_urls = {s.get("url") for s in prev_payload.get("stories", [])}

    killed_urls = set()
    try:
        killed_urls = {k.get("url") for k in json.loads(DECISIONS.read_text(encoding="utf-8")).get("killed", [])}
    except Exception:  # noqa: BLE001
        pass

    pend_items = []
    try:
        pend_items = json.loads(PENDING.read_text(encoding="utf-8")).get("items", [])
    except Exception:  # noqa: BLE001
        pass
    # prune queue: already published, killed by the desk, or stale (>36h)
    pend_items = [it for it in pend_items
                  if it.get("url") not in published_urls and it.get("url") not in killed_urls
                  and fresh_enough(it.get("iso", ""), hours=36.0)]
    pend_urls = {it.get("url") for it in pend_items}

    added = 0
    for s in checked:
        if s["url"] in published_urls or s["url"] in pend_urls or s["url"] in killed_urls:
            continue
        item = dict(s)
        item["id"] = hashlib.sha1(s["url"].encode()).hexdigest()[:12]
        item["kind"] = "story"
        item["filed_at"] = now_iso
        pend_items.append(item)
        pend_urls.add(s["url"])
        added += 1

    national = out.get("national")
    if isinstance(national, dict) and valid_story(dict(national, region="statewide")):
        prev_nat_url = (prev_payload.get("national") or {}).get("url")
        if national.get("url") not in (prev_nat_url,) and national.get("url") not in pend_urls \
                and national.get("url") not in killed_urls:
            item = dict(national)
            item["id"] = hashlib.sha1(str(national.get("url", "")).encode()).hexdigest()[:12]
            item["kind"] = "national"
            item["filed_at"] = now_iso
            pend_items.append(item)
            added += 1

    pend_items.sort(key=lambda x: str(x.get("filed_at", "")), reverse=True)
    PENDING.write_text(json.dumps(
        {"updated_at": now_iso, "generator": "grok-wire-agent", "items": pend_items[:20]},
        indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Filed {added} new items to the desk queue ({len(pend_items[:20])} waiting)")

    # Meetings accumulate + auto-publish; approved stories pass through untouched
    try:
        prev_m = prev_payload.get("meetings", [])
        have_m = {(m.get("iso"), str(m.get("body", "")).lower()) for m in meetings}
        for om in prev_m:
            k = (om.get("iso"), str(om.get("body", "")).lower())
            if k not in have_m and valid_meeting(om):
                meetings.append(om)
        meetings.sort(key=lambda m: str(m.get("iso", "")))
    except Exception as e:  # noqa: BLE001
        print(f"::warning::meeting accumulate skipped: {e}")

    payload = dict(prev_payload)
    payload["updated_at"] = now_iso
    payload["generator"] = "grok-wire-agent"
    payload.setdefault("stories", [])
    payload["meetings"] = meetings
    LIVE.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote live-data.json: {len(payload['stories'])} approved stories kept, {len(meetings)} meetings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
