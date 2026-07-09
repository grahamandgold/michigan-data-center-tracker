#!/usr/bin/env python3
"""news_judge — the two-model newsworthiness gate.

Runs after wire_agent + headline_check, before the commit step. Grok drafted
the stories; a DIFFERENT model family (Claude, via the judgment route) now
grades every item in the pending queue:

  newsworthiness 1-10  — is this a genuinely new development a Michigan
                          reader should care about, or noise?
  duplicate risk       — near-duplicate of anything already live or already
                          killed by the News Director?

Anything scoring < JUDGE_THRESHOLD (default 6) or flagged duplicate is
removed from the queue and logged to desk-decisions.json under "killed"
with by:"news_judge" — so the wire agent never re-files it, and Andy can
see in the Archive exactly what the machine spiked and why.

Items that PASS carry {"judge_score": N, "judge_note": "..."} into the desk
queue so the Today page can show the grade next to each candidate.

Agenda stories (kind:"agenda") are exempt from the duplicate check against
their own meeting and get a lower bar when document-based — original
reporting is the product.
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_ai_client as ai  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
PENDING = ROOT / "live-data-pending.json"
LIVE = ROOT / "live-data.json"
DECISIONS = ROOT / "desk-decisions.json"
THRESHOLD = int(os.environ.get("JUDGE_THRESHOLD", "6"))

PROMPT = """You are the second editor at the Michigan Data Center Tracker — a
different model family than the one that drafted these stories. Grade each
candidate for the approval queue. Be tough: the human News Director's time is
the scarcest resource in the building.

Newsworthiness 1-10 for a MICHIGAN reader tracking the data-center buildout:
  9-10 a decision was made / project confirmed / money moved / vote happened
  7-8  concrete new development: filing, hearing scheduled, official statement
  5-6  incremental but real; document-based agenda previews land here or higher
  3-4  national trend piece, thin rehash, speculation
  1-2  noise, PR, engagement bait

Duplicate: true if it covers the same development as any ALREADY-LIVE or
ALREADY-KILLED title below (same event reworded = duplicate; a genuinely new
development in the same saga = not).

ALREADY LIVE (do not re-approve these developments):
{live}

KILLED BY THE NEWS DIRECTOR (never resurrect):
{killed}

CANDIDATES:
{candidates}

Respond ONLY with a JSON array, one object per candidate, same order:
[{{"i": 0, "score": 7, "duplicate": false, "note": "<one sentence reason>"}}]"""


def main() -> int:
    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"No pending queue to judge: {e}")
        return 0
    items = pending.get("items", [])
    # bare meeting listings belong to the desk's trusted auto-lane — never judge/spike them
    unjudged = [it for it in items
                if "judge_score" not in it and it.get("kind") != "meeting"]
    if not unjudged:
        print("Queue empty or already judged.")
        return 0

    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
        live_titles = [s.get("title", "") for s in live.get("stories", [])][:25]
    except Exception:  # noqa: BLE001
        live_titles = []
    try:
        decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        decisions = {"killed": []}
    killed_titles = [k.get("title", "") for k in decisions.get("killed", [])][-25:]

    cands = "\n".join(
        f"[{i}] ({it.get('kind', 'wire')}) {it.get('title', '')} — {str(it.get('dek', ''))[:200]}"
        for i, it in enumerate(unjudged))
    reply = ai.chat("judgment",
                    [{"role": "user", "content": PROMPT.format(
                        live="\n".join(f"- {t}" for t in live_titles) or "(none)",
                        killed="\n".join(f"- {t}" for t in killed_titles) or "(none)",
                        candidates=cands)}],
                    temperature=0)
    verdicts = ai.extract_json(reply)
    if not isinstance(verdicts, list):
        print("::warning::judge unavailable or unparseable — queue passes unjudged")
        return 0

    by_i = {v.get("i"): v for v in verdicts if isinstance(v, dict)}
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    kept, dropped = [], 0
    for i, it in enumerate(unjudged):
        v = by_i.get(i)
        if not v:
            kept.append(it)  # never drop on a missing verdict
            continue
        try:
            score = int(v.get("score", 5))
        except (TypeError, ValueError):  # model returned null / non-numeric
            score = 5
        note = str(v.get("note") or "")[:160]
        dup = bool(v.get("duplicate"))
        # document-based agenda previews are our product — only drop clear junk
        floor = 4 if it.get("kind") == "agenda" and it.get("accuracy") == "document-based" else THRESHOLD
        if dup or score < floor:
            dropped += 1
            decisions.setdefault("killed", []).append({
                "url": it.get("url", ""), "title": it.get("title", ""),
                "at": now, "by": "news_judge",
                "note": f"score {score}/10{', duplicate' if dup else ''}: {note}"})
            print(f"  SPIKED ({score}/10{' dup' if dup else ''}): {it.get('title', '')[:80]}")
        else:
            it["judge_score"] = score
            it["judge_note"] = note
            kept.append(it)

    if dropped:
        judged_ids = {id(x) for x in unjudged}
        pending["items"] = [it for it in items if id(it) not in judged_ids] + kept
        pending["items"].sort(key=lambda x: x.get("filed_at", ""), reverse=True)
        pending["updated_at"] = now
        PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
        decisions["killed"] = decisions["killed"][-200:]
        DECISIONS.write_text(json.dumps(decisions, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")
    else:
        PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n",
                           encoding="utf-8")
    print(f"Judge: {len(unjudged)} reviewed, {dropped} spiked, {len(kept)} passed to the desk")
    return 0


if __name__ == "__main__":
    sys.exit(main())
