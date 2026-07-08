#!/usr/bin/env python3
"""Daily Grok map scout — proposes updates to map-data.json.

Unlike the hourly wire (which commits directly), map records carry
coordinates and statuses that define the site's credibility, so this agent
NEVER writes to main. It applies validated changes to map-data.json on a
branch; the workflow opens a pull request for human review.

Change types the model may propose:
  add            — a new project / moratorium / meeting point (with source)
  update_status  — status/note/verified_date change to an existing point
  remove_meeting — a meetings-layer point whose date has passed

Guardrails: statuses from a fixed vocabulary; coordinates must fall inside
Michigan's bounding box and SHOULD be municipality centroids unless a public
source identifies the site; every change needs an https source URL.
Requires: XAI_API_KEY. Stdlib only.
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
DATA = ROOT / "map-data.json"
API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = os.environ.get("XAI_MODEL", "grok-4")
KEY = os.environ.get("XAI_API_KEY", "")

LAYERS = {"projects", "moratoria", "meetings", "policy"}
STATUSES = {
    "projects": {"Proposed", "Under review", "Approved", "Conditionally approved",
                 "Under construction", "Operating", "Withdrawn", "Rejected by planning commission"},
    "moratoria": {"Moratorium", "Utility pause"},
    "meetings": {"Public meeting"},
    "policy": {"Public signal"},
}
MI_LAT = (41.5, 48.4)
MI_LNG = (-90.5, -82.0)

PROMPT = """You are the map editor for the Michigan Data Center Tracker. Current UTC: {now}.
Below is the current tracked-record index (name | layer | status | county | verified_date):

{index}

TASK: Search the last 7 days of Michigan news and official sources for
(a) NEW data center projects, moratoria/pauses, or upcoming public meetings not in the index,
(b) STATUS CHANGES to indexed records (approved, withdrawn, construction started, moratorium
    expired/extended, etc.),
(c) indexed meetings whose date has passed.

HARD RULES:
- Only report what a real, working https source confirms. Never invent anything.
- Coordinates: use the municipality's center point unless a public source identifies the
  exact site. Note "approximate" in the note when using a centroid.
- Notes under 40 words, neutral language.

Respond with ONLY JSON (no fences):
{{"changes": [
  {{"op": "add", "point": {{"name": "...", "municipality": "...", "county": "...",
    "status": "<from the allowed vocabulary>", "layer": "projects|moratoria|meetings|policy",
    "developer": "...", "power_mw": "", "latitude": 0.0, "longitude": 0.0,
    "source_url": "https://...", "source_name": "...",
    "verified_date": "YYYY-MM-DD", "confidence": "Confirmed|Reported", "note": "..."}}}},
  {{"op": "update_status", "name": "<exact indexed name>", "status": "...",
    "note": "...", "verified_date": "YYYY-MM-DD", "source_url": "https://...", "source_name": "..."}},
  {{"op": "remove_meeting", "name": "<exact indexed name>"}}
]}}
Allowed statuses — projects: Proposed, Under review, Approved, Conditionally approved,
Under construction, Operating, Withdrawn, Rejected by planning commission;
moratoria: Moratorium, Utility pause; meetings: Public meeting; policy: Public signal.
If nothing verified changed, return {{"changes": []}}."""


def call_grok(index: str) -> dict | None:
    body = {
        "model": MODEL,
        "messages": [{"role": "user", "content": PROMPT.format(now=datetime.now(timezone.utc).isoformat(), index=index)}],
        "search_parameters": {"mode": "on", "return_citations": True},
        "temperature": 0.1,
    }
    req = urllib.request.Request(API_URL, data=json.dumps(body).encode(),
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=420) as r:
            text = json.loads(r.read())["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:  # noqa: BLE001
        print(f"::warning::map scout API failure: {e}")
        return None


def https_ok(u) -> bool:
    return isinstance(u, str) and u.startswith("https://")


def valid_add(p: dict, names: set) -> bool:
    try:
        return (p["name"] not in names
                and p.get("layer") in LAYERS
                and p.get("status") in STATUSES[p["layer"]]
                and MI_LAT[0] <= float(p["latitude"]) <= MI_LAT[1]
                and MI_LNG[0] <= float(p["longitude"]) <= MI_LNG[1]
                and https_ok(p.get("source_url"))
                and p.get("source_name") and p.get("municipality") and p.get("county")
                and datetime.strptime(p["verified_date"], "%Y-%m-%d") is not None
                and p.get("confidence") in {"Confirmed", "Reported"})
    except Exception:  # noqa: BLE001
        return False


def main() -> int:
    if not KEY:
        print("::error::XAI_API_KEY secret is not set")
        return 1
    data = json.loads(DATA.read_text(encoding="utf-8"))
    pts = data["map_points"]
    names = {p["name"] for p in pts}
    index = "\n".join(f"{p['name']} | {p.get('layer')} | {p.get('status')} | {p.get('county')} | {p.get('verified_date','')}"
                      for p in pts if p.get("layer") in LAYERS)

    out = call_grok(index)
    if not out or not isinstance(out.get("changes"), list):
        print("No usable scout output — nothing to propose.")
        return 0

    applied = []
    for ch in out["changes"][:20]:
        op = ch.get("op")
        if op == "add" and isinstance(ch.get("point"), dict) and valid_add(ch["point"], names):
            pts.append(ch["point"]); names.add(ch["point"]["name"])
            applied.append(f"ADD {ch['point']['name']} ({ch['point']['status']}) — {ch['point']['source_name']}")
        elif op == "update_status" and ch.get("name") in names and https_ok(ch.get("source_url")):
            for p in pts:
                if p["name"] == ch["name"] and p.get("layer") in LAYERS:
                    new_status = ch.get("status")
                    if new_status and new_status not in STATUSES.get(p.get("layer", ""), set()):
                        break
                    if new_status:
                        p["status"] = new_status
                    if ch.get("note"):
                        p["note"] = str(ch["note"])[:300]
                    if ch.get("verified_date"):
                        p["verified_date"] = ch["verified_date"]
                    p["source_url"] = ch["source_url"]
                    if ch.get("source_name"):
                        p["source_name"] = ch["source_name"]
                    applied.append(f"UPDATE {p['name']} -> {p['status']}")
                    break
        elif op == "remove_meeting" and ch.get("name") in names:
            before = len(pts)
            pts[:] = [p for p in pts if not (p["name"] == ch["name"] and p.get("layer") == "meetings")]
            if len(pts) < before:
                applied.append(f"REMOVE past meeting {ch['name']}")

    if not applied:
        print("No valid changes proposed.")
        return 0

    data["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    DATA.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    summary = "\n".join("- " + a for a in applied)
    Path(ROOT / "map-scout-summary.md").write_text(
        "## Map scout proposals\n\nEvery change below cites a source. Verify before merging.\n\n" + summary + "\n",
        encoding="utf-8")
    print(f"Proposed {len(applied)} change(s):\n{summary}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
