#!/usr/bin/env python3
"""training_report — is the Andy-training actually working? Measure it.

Reads the newsroom's own paper trail (all in git already):
  desk-decisions.json  what was killed, by whom (Andy vs news_judge)
  desk-rework.json     what was sent back for a re-do
  desk-lessons.json    every correction + the compiled rules
  live-data.json       what made it to publication

and computes the numbers that tell you whether the agents are learning:
  * kill rate and send-back rate per ISO week (falling = learning)
  * how often the judge spikes things before Andy ever sees them
  * corrections filed per week (falling while quality holds = learning)
  * repeat offenses: killed items whose reason matches an existing rule
    (these are the rules agents are IGNORING — the audit should upweight them)

Writes training-report.json (the desk's Today page or Settings page can
render it) and prints a human summary to the Actions log. Stdlib only.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "training-report.json"


def load(name: str) -> dict:
    try:
        return json.loads((ROOT / name).read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def week(ts: str) -> str:
    try:
        d = datetime.fromisoformat(str(ts).replace("Z", "+00:00"))
        return f"{d.isocalendar().year}-W{d.isocalendar().week:02d}"
    except Exception:  # noqa: BLE001
        return "unknown"


def main() -> int:
    decisions = load("desk-decisions.json")
    rework = load("desk-rework.json")
    lessons = load("desk-lessons.json")
    live = load("live-data.json")

    weeks: dict[str, dict] = defaultdict(lambda: {"published": 0, "killed_human": 0,
                                                  "killed_judge": 0, "sent_back": 0,
                                                  "corrections": 0})
    national = live.get("national")
    national = national if isinstance(national, list) else ([national] if isinstance(national, dict) else [])
    for s in live.get("stories", []) + national:
        weeks[week(s.get("iso", ""))]["published"] += 1
    for k in decisions.get("killed", []):
        key = "killed_judge" if k.get("by") == "news_judge" else "killed_human"
        weeks[week(k.get("at", ""))][key] += 1
    for r in rework.get("requests", []):
        weeks[week(r.get("at", ""))]["sent_back"] += 1
    for l in lessons.get("lessons", []):
        weeks[week(l.get("at", ""))]["corrections"] += 1
    weeks.pop("unknown", None)

    # repeat offenses: human kills whose note echoes a compiled rule's key words
    rules = [r for r in lessons.get("rules", []) if not r.get("retired")]
    repeat = []
    for k in decisions.get("killed", []):
        if k.get("by") == "news_judge":
            continue
        note = str(k.get("note", "") or "").lower()
        if not note:
            continue
        for r in rules:
            words = [w for w in re.findall(r"[a-z]{5,}", str(r.get("rule", "")).lower())][:6]
            if words and sum(1 for w in words if w in note) >= 2:
                repeat.append({"rule_id": r.get("id"), "rule": r.get("rule", "")[:120],
                               "killed_title": k.get("title", "")[:90], "at": k.get("at", "")})
                break

    ordered = dict(sorted(weeks.items()))
    report = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "totals": {
            "published": sum(w["published"] for w in weeks.values()),
            "killed_by_andy": sum(w["killed_human"] for w in weeks.values()),
            "killed_by_judge": sum(w["killed_judge"] for w in weeks.values()),
            "sent_back": sum(w["sent_back"] for w in weeks.values()),
            "raw_corrections": len(lessons.get("lessons", [])),
            "compiled_rules": len(rules),
        },
        "by_week": ordered,
        "rules_being_ignored": repeat[-20:],
    }
    OUT.write_text(json.dumps(report, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    t = report["totals"]
    print(f"Training report — {t['published']} published, "
          f"{t['killed_by_andy']} killed by Andy, {t['killed_by_judge']} spiked by the judge, "
          f"{t['sent_back']} sent back, {t['raw_corrections']} corrections "
          f"-> {t['compiled_rules']} compiled rules")
    for wk, v in list(ordered.items())[-6:]:
        total = v["published"] + v["killed_human"] + v["sent_back"]
        rate = (v["killed_human"] + v["sent_back"]) / total * 100 if total else 0
        print(f"  {wk}: {v['published']} live, {v['killed_human']} killed, "
              f"{v['sent_back']} sent back — {rate:.0f}% needed Andy's red pen")
    if repeat:
        print(f"  ⚠ {len(repeat)} kills matched an EXISTING rule — agents are ignoring these:")
        for r in repeat[-5:]:
            print(f"    [{r['rule_id']}] {r['rule'][:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
