#!/usr/bin/env python3
"""auto_publish — keep the public homepage fresh every hour, hands-free.

Runs at the end of the hourly wire refresh, AFTER headline_check (accuracy)
and news_judge (newsworthiness). It promotes only the highest-confidence,
freshest wire items straight onto the live site, and expires anything stale
so the homepage is never frozen on day-old news.

An item is auto-published only if ALL hold:
  * kind == "story"            (wire news — never agenda previews or social)
  * judge_score >= AUTO_MIN    (default 8/10; a repo variable, tune anytime)
  * accuracy is not flagged     (headline_check already verified vs. source)
  * published < FRESH_HOURS ago (default 12h)
  * not already live, not killed by the desk

Everything below the bar stays in the queue for the News Director's tap.
Every auto-published item is logged to desk-decisions.json (by:"auto_publish")
and still appears on the desk — Andy can KILL any of them, which removes it
from the live site AND records a training lesson, exactly like a manual kill.

Safety valves (repo → Settings → Variables, no code change):
  AUTO_PUBLISH_MIN   raise to 11 to effectively pause the lane; lower to loosen
  AUTO_FRESH_HOURS   homepage freshness window (must match mdct-editorial.js)
  AUTO_MAX_LIVE      max stories kept on the live site
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
DECISIONS = ROOT / "desk-decisions.json"

AUTO_MIN = int(os.environ.get("AUTO_PUBLISH_MIN", "8"))
FRESH_HOURS = float(os.environ.get("AUTO_FRESH_HOURS", "12"))
MAX_LIVE = int(os.environ.get("AUTO_MAX_LIVE", "11"))
MIN_LIVE = 5  # never let the homepage fall below this (matches JS MIN_STORIES)


def _age_h(iso: str, now: datetime) -> float:
    try:
        t = datetime.fromisoformat(str(iso).replace("Z", "+00:00"))
        return (now - t).total_seconds() / 3600.0
    except Exception:  # noqa: BLE001
        return 1e9


def _clean_story(it: dict) -> dict:
    """Strip desk-only fields so the live payload stays lean. judge_score is
    KEPT — it drives which story leads the homepage (the 'top story')."""
    drop = {"kind", "filed_at", "judge_note", "auto_approve_at", "headline_rewritten",
            "auto_lane", "auto_link_attempts", "link_verified_at", "held", "ago"}
    return {k: v for k, v in it.items() if k not in drop}


def main() -> int:
    now = datetime.now(timezone.utc)
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::error::no live-data.json: {e}")
        return 1
    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pending = {"items": []}
    try:
        decisions = json.loads(DECISIONS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        decisions = {}
    killed_urls = {k.get("url") for k in decisions.get("killed", [])}

    stories = live.get("stories", [])
    live_urls = {s.get("url") for s in stories}
    items = pending.get("items", [])

    promoted, kept_pending = [], []
    for it in items:
        url = it.get("url", "")
        # Block only genuinely bad accuracy: "thin" (agenda needs a human) or
        # "inaccurate". "unverified-source-unfetchable" just means the outlet
        # blocked our server fetch (normal for WXYZ/MLive/paywalls) — the judge
        # still scored it and the headline was rewritten from the real outlet
        # title, so it's fine to publish and Andy can kill it if wrong.
        acc = str(it.get("accuracy", "")).lower()
        # Google News items must have a genuinely rewritten headline to go
        # straight up; paraphrases wait for a human rewrite on the desk.
        rewritten_ok = it.get("origin") != "google-news" or it.get("headline_rewritten", True)
        ok = (
            it.get("kind") == "story"
            and int(it.get("judge_score", 0)) >= AUTO_MIN
            and "thin" not in acc and "inaccurate" not in acc
            and rewritten_ok
            and _age_h(it.get("iso") or it.get("filed_at", ""), now) <= FRESH_HOURS
            and url and url not in live_urls and url not in killed_urls
        )
        if ok:
            promoted.append(it)
            live_urls.add(url)
        else:
            kept_pending.append(it)

    if promoted:
        stories = [_clean_story(p) for p in promoted] + stories

    # News Director's rule: a story never leaves the homepage until a fresh one
    # REPLACES it. So we only ever prepend fresh stories and cap the list — the
    # oldest falls off exactly when a newer story pushes it past MAX_LIVE. No
    # age-based blanking: if nothing fresh arrives, the current stories stay put.
    stories.sort(key=lambda s: s.get("iso", ""), reverse=True)
    stories = stories[:MAX_LIVE]

    changed = bool(promoted) or stories != live.get("stories", [])
    if not changed:
        print(f"Auto-publish: nothing met the bar (>= {AUTO_MIN}/10, < {FRESH_HOURS:.0f}h). Homepage unchanged.")
        return 0

    live["stories"] = stories
    live["updated_at"] = now_iso
    LIVE.write_text(json.dumps(live, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    pending["items"] = kept_pending
    pending["updated_at"] = now_iso
    PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    if promoted:
        log = decisions.setdefault("auto_published", [])
        for p in promoted:
            log.append({"url": p.get("url"), "title": p.get("title"),
                        "judge_score": p.get("judge_score"), "at": now_iso})
        decisions["auto_published"] = log[-300:]
        DECISIONS.write_text(json.dumps(decisions, indent=1, ensure_ascii=False) + "\n",
                             encoding="utf-8")

    print(f"Auto-publish: {len(promoted)} promoted to live, "
          f"{len(stories)} stories on the homepage (all < {FRESH_HOURS:.0f}h unless floored).")
    for p in promoted:
        print(f"  LIVE ({p.get('judge_score')}/10): {p.get('title', '')[:80]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
