#!/usr/bin/env python3
"""Emmy's tip desk — auto-researches & fact-checks reader tips BEFORE the editor sees them.

Reads community-tips.json, and for every tip still marked "new" it runs a
web-grounded fact-check (Grok live search via multi_ai_client), writes a
structured brief into tip["emmy_research"], and flips status to "researched".

The editor (Andy) then opens the Reader Tips panel on the desk, reads Emmy's
findings, leaves research notes, and marks the tip reviewed / promoted / dismissed.

Runs in CI (tip-research.yml) on every push to community-tips.json + a safety
schedule. Stdlib only; needs one of XAI/ANTHROPIC/OPENAI keys.
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TIPS = ROOT / "community-tips.json"
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import multi_ai_client as ai  # noqa: E402
except Exception as e:  # noqa: BLE001
    ai = None
    _AI_ERR = str(e)

BUDGET_SEC = 20 * 60  # never run the CI job past ~20 min

PROMPT = """You are Emmy, the Data Center Editor at the Michigan Data Center Tracker \
(a nonpartisan public record of Michigan data centers, permits, moratoria and meetings).

A reader sent the tip below. Research and FACT-CHECK it using live web search. Be skeptical,
cite real sources, and never invent facts. Return STRICT JSON only, no prose:

{
 "verdict": "verified | partly | unverified | false | needs-human",
 "summary": "2-3 sentence plain-English finding a busy editor can read in 10 seconds",
 "evidence": ["short factual bullet with what you actually found", "..."],
 "sources": ["https://real-url-you-verified", "..."],
 "map_impact": "what this would change on the tracker map/data if true, or 'none'",
 "next_steps": "the single most important thing a human should verify before publishing"
}

READER TIP:
{tip}

READER-PROVIDED LINK: {url}

Output only the JSON object."""


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _fallback(msg: str) -> dict:
    return {"verdict": "needs-human", "summary": msg, "evidence": [], "sources": [],
            "map_impact": "unknown", "next_steps": "Research this one manually.",
            "researched_at": _now(), "auto": False}


def research(tip: dict) -> dict:
    if ai is None:
        return _fallback(f"Auto-research unavailable ({_AI_ERR}).")
    prompt = (PROMPT
              .replace("{tip}", (tip.get("message", "") or "")[:1500])
              .replace("{url}", (tip.get("url", "") or "none")))
    try:
        raw = ai.chat("hunting", [{"role": "user", "content": prompt}], temperature=0, search=True)
    except Exception as e:  # noqa: BLE001
        return _fallback(f"Auto-research error: {e}")
    m = re.search(r"\{.*\}", raw or "", re.S)
    if not m:
        return _fallback((raw or "No response.")[:400])
    try:
        d = json.loads(m.group(0))
    except Exception:  # noqa: BLE001
        return _fallback((raw or "")[:400])
    # normalize
    out = {
        "verdict": str(d.get("verdict", "needs-human"))[:20],
        "summary": str(d.get("summary", ""))[:600],
        "evidence": [str(x)[:220] for x in (d.get("evidence") or [])][:6],
        "sources": [str(x)[:300] for x in (d.get("sources") or []) if str(x).startswith("http")][:6],
        "map_impact": str(d.get("map_impact", ""))[:240],
        "next_steps": str(d.get("next_steps", ""))[:300],
        "researched_at": _now(),
        "auto": True,
    }
    return out


def main() -> int:
    if not TIPS.exists():
        print("[tip_research] no community-tips.json — nothing to do")
        return 0
    data = json.loads(TIPS.read_text(encoding="utf-8"))
    tips = data.get("tips", [])
    deadline = time.time() + BUDGET_SEC
    changed = 0
    for t in tips:
        if t.get("status") != "new":
            continue
        if time.time() > deadline:
            print("[tip_research] budget reached — leaving the rest for next run")
            break
        print(f"[tip_research] researching {t.get('id')}: {(t.get('message') or '')[:60]!r}")
        t["emmy_research"] = research(t)
        t["status"] = "researched"
        changed += 1
    if changed:
        data["tips"] = tips
        data["updated_at"] = _now()
        TIPS.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"[tip_research] researched {changed} tip(s)")
    else:
        print("[tip_research] no new tips")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
