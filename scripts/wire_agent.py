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
API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = os.environ.get("XAI_MODEL", "grok-4")
KEY = os.environ.get("XAI_API_KEY", "")

REGIONS = {"metro", "west", "mid", "north", "statewide"}
TAGS = {"Power & Grid", "Local Government", "Policy", "Water", "Money", "Explainers"}
MEET_REGIONS = {"SE Michigan", "West Michigan", "Mid-Michigan", "Northern Michigan", "Statewide"}

PROMPT = """You are the wire editor for the Michigan Data Center Tracker \
(https://grahamandgold.github.io/mi-data-center-tracker/). Current UTC time: {now}.

MISSION: fill the homepage wire with what is happening RIGHT NOW.
START by running x_search for "Michigan data center", "Michigan Senate debate",
and "Grand Rapids debate" over the last 15 hours — live political events (a Senate
debate where data centers came up, for example) are exactly the lead we want.

1. SEARCH (use web_search AND x_search) for Michigan data center news from the \
LAST 15 HOURS ONLY. Priorities, in order:
   a. HOT community conversations on X AND Reddit right now (r/Michigan, r/Detroit, r/grandrapids, r/lansing, r/kzoo): debates, hearings, votes, outages, resident fights — debates, hearings, \
votes, candidate statements (e.g., a U.S. Senate debate touching data centers).
   b. Fresh reporting: MLive, Michigan Advance, Bridge Michigan, Crain's, Detroit News, \
Free Press, Lansing State Journal, City Pulse, WOOD TV, WWMT, WXYZ, WKAR, WILX, WNEM, \
IPR, Traverse Ticker, UP outlets.
   c. Official postings: township/city agendas, legislature.mi.gov (SB 1018-1020, \
SB 1046-1051, HB 6135-6142), MPSC filings.

2. HARD RULES:
- Target the LAST 15 HOURS. If you cannot fill 6 items, you may stretch to 24 \
hours — never older. Do NOT backfill old items; find TODAY's development instead.
- Write every headline and dek in ORIGINAL, neutral, journalistic language. NEVER \
copy or lightly rearrange a publisher's headline or a post.
- Every item MUST have a real, working https source URL you actually found. For X \
coverage link the specific post (https://x.com/...) from a newsroom, reporter, \
official, or candidate account, and set "source": "X". For Reddit link the specific thread and set "source": "Reddit" — posts document the public conversation; inclusion is not endorsement.
- Never invent a story, meeting, quote, URL, or statistic. Unverified means omitted.
- Deks under 55 words, factual. Note when something is a live/developing event.

3. Respond with ONLY a JSON object (no markdown fences, no commentary):
{{"updated_at": "<current ISO-8601 UTC>", "generator": "grok-wire-agent",
 "stories": [6-10 items, newest first, ALL <15h old: {{"iso": "<publication time ISO-8601, best estimate to the hour>",
   "region": "metro|west|mid|north|statewide", "cat": "<County> Co." or "STATEWIDE",
   "tag": "Power & Grid|Local Government|Policy|Water|Money|Explainers",
   "title": "<original headline>", "dek": "<original 1-2 sentence summary>",
   "source": "<outlet or X>", "url": "<https link>", "breaking": <bool>, "lead": <true on exactly one>}}],
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


def call_grok() -> dict | None:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(now=datetime.now(timezone.utc).isoformat())}],
        "search_parameters": {"mode": "on", "return_citations": True,
                              "from_date": (datetime.now(timezone.utc) - timedelta(days=8)).strftime("%Y-%m-%d")},
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


def valid_story(s: dict) -> bool:
    """Normalize what we can; reject only what we must. Logs every rejection."""
    try:
        if not (isinstance(s.get("title"), str) and len(s["title"]) > 10):
            print(f"::warning::rejected (title): {str(s.get('title'))[:60]}")
            return False
        if not (isinstance(s.get("url"), str) and s["url"].startswith("https://")):
            print(f"::warning::rejected (url): {s.get('title','')[:60]}")
            return False
        if not fresh_enough(s.get("iso", ""), hours=26.0):
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
    meetings = [m for m in out.get("meetings", []) if valid_meeting(m)]

    if len(checked) < 3:
        print(f"::warning::only {len(checked)} valid stories — keeping existing file")
        return 0

    leads = [s for s in checked if s.get("lead")]
    for s in checked:
        s["lead"] = False
    (leads[0] if leads else checked[0])["lead"] = True

    payload = {
        "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "generator": "grok-wire-agent",
        "stories": checked,
        "meetings": meetings,
    }
    LIVE.write_text(json.dumps(payload, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Wrote live-data.json: {len(checked)} stories, {len(meetings)} meetings")
    return 0


if __name__ == "__main__":
    sys.exit(main())
