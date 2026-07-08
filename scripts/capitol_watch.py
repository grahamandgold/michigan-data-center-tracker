#!/usr/bin/env python3
"""Capitol watcher — tracks Michigan Legislature activity on data center bills.

Uses the LegiScan API (free key from legiscan.com; repo secret LEGISCAN_API_KEY)
to poll every Michigan bill, keep the ones about data centers, and detect NEW
ACTIONS (referrals, hearings, passage, signings) since the last run. Detected
changes become wire stories — deterministic, factual, template-written in our
own words, linked to the bill page. State lives in capitol-state.json.

No LLM involved: legislative actions are records, not interpretations.
"""
from __future__ import annotations

import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
STATE = ROOT / "capitol-state.json"
KEY = os.environ.get("LEGISCAN_API_KEY", "")

KEYWORDS = re.compile(
    r"data center|data centre|hyperscale|computing facilit|colocation|"
    r"large[- ]load|server farm", re.I)
# Bills we always track regardless of title matching
WATCHED = {"SB1018", "SB1019", "SB1020", "SB1046", "SB1047", "SB1048",
           "SB1049", "SB1050", "SB1051", "HB6135", "HB6136", "HB6137",
           "HB6138", "HB6139", "HB6140", "HB6141", "HB6142"}


def api(op: str, **params) -> dict | None:
    qs = "&".join(f"{k}={urllib.request.quote(str(v))}" for k, v in params.items())
    url = f"https://api.legiscan.com/?key={KEY}&op={op}&{qs}"
    try:
        with urllib.request.urlopen(url, timeout=60) as r:
            data = json.loads(r.read())
        if data.get("status") != "OK":
            print(f"::warning::legiscan {op} status: {data.get('status')} {str(data)[:120]}")
            return None
        return data
    except Exception as e:  # noqa: BLE001
        print(f"::warning::legiscan {op} failed: {e}")
        return None


def main() -> int:
    if not KEY:
        print("::warning::LEGISCAN_API_KEY not set — capitol watch skipped. "
              "Get a free key at legiscan.com/legiscan and add it as a repo secret.")
        return 0

    data = api("getMasterList", state="MI")
    if not data:
        return 0
    bills = [b for b in data.get("masterlist", {}).values() if isinstance(b, dict) and b.get("number")]
    relevant = [b for b in bills
                if b["number"].replace(" ", "").upper() in WATCHED
                or KEYWORDS.search(b.get("title", "") + " " + b.get("description", ""))]
    print(f"masterlist: {len(bills)} bills, {len(relevant)} data-center-relevant")

    prev = {}
    if STATE.exists():
        try:
            prev = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            prev = {}

    first_run = not prev
    stories = []
    state_out = {}
    for b in relevant:
        num = b["number"].replace(" ", "").upper()
        sig = f"{b.get('last_action_date','')}|{b.get('last_action','')}"
        state_out[num] = sig
        if first_run or prev.get(num) == sig or not b.get("last_action"):
            continue  # unchanged (or baseline run: record silently)
        action = str(b.get("last_action", "")).strip()
        title = str(b.get("title", "")).strip().rstrip(".")
        url = b.get("url") or f"https://legiscan.com/MI/bill/{b['number'].replace(' ', '')}"
        stories.append({
            "iso": (b.get("last_action_date") or datetime.now(timezone.utc).strftime("%Y-%m-%d")) + "T12:00:00+00:00",
            "region": "statewide", "cat": "CAPITOL", "tag": "Policy",
            "title": f"Capitol watch: {b['number']} — {action[:110]}",
            "dek": f"{title[:200]}. Recorded action in the Michigan Legislature; see the full bill history at the source link.",
            "source": "Michigan Legislature", "url": url,
            "breaking": False, "lead": False, "accuracy": "official-record",
        })

    STATE.write_text(json.dumps(state_out, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    if first_run:
        print(f"baseline recorded for {len(state_out)} bills — future runs report changes")
        return 0
    if not stories:
        print("no new legislative actions")
        return 0

    # Desk approval model: legislative stories file into the pending queue
    # for Andy's sign-off in the Michigan Intel Desk — nothing auto-publishes.
    import hashlib
    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pending = {"items": []}
    try:
        published = {s.get("url") + "|" + s.get("title", "")
                     for s in json.loads(LIVE.read_text(encoding="utf-8")).get("stories", [])}
    except Exception:  # noqa: BLE001
        published = set()
    have = {str(it.get("url")) + "|" + str(it.get("title", "")) for it in pending.get("items", [])}
    added = 0
    for s in stories:
        key = s["url"] + "|" + s["title"]
        if key in have or key in published:
            continue
        item = dict(s)
        item["id"] = hashlib.sha1(key.encode()).hexdigest()[:12]
        item["kind"] = "capitol"
        item["filed_at"] = now_iso
        item["accuracy"] = "checked"  # deterministic template from LegiScan data
        pending.setdefault("items", []).insert(0, item)
        added += 1
    pending["items"] = pending["items"][:20]
    pending["updated_at"] = now_iso
    PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"filed {added} legislative action stor{'y' if added == 1 else 'ies'} to the desk queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
