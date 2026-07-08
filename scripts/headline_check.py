#!/usr/bin/env python3
"""Headline accuracy checker — the second stage of the hourly wire refresh.

For every story in live-data.json, this fetches the actual source article and
asks Grok (WITHOUT web search — judging only the supplied text) whether our
AI-written headline and dek accurately portray it. Inaccurate stories are
corrected when possible, dropped when not. Runs after wire_agent.py and
before the commit step, so nothing inaccurate ever reaches the site.

Verdicts per story:
  accurate    -> keep
  fixable     -> apply the checker's corrected title/dek (original language)
  inaccurate  -> drop
  unfetchable -> keep but flag (paywalls happen); logged for the human pass

Requires: XAI_API_KEY. Stdlib only.
"""
from __future__ import annotations

import html
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data-pending.json"  # desk model: check the queue before Andy sees it
API_URL = "https://api.x.ai/v1/chat/completions"
MODEL = os.environ.get("XAI_MODEL", "grok-4")
KEY = os.environ.get("XAI_API_KEY", "")


def fetch_text(url: str) -> str:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (MDCT headline-check)"})
        with urllib.request.urlopen(req, timeout=20) as r:
            raw = r.read(600_000).decode("utf-8", "ignore")
    except Exception:  # noqa: BLE001
        return ""
    raw = re.sub(r"<(script|style|nav|header|footer|aside)[^>]*>.*?</\1>", " ", raw, flags=re.S | re.I)
    # prefer paragraph text
    paras = re.findall(r"<p[^>]*>(.*?)</p>", raw, flags=re.S | re.I)
    text = " ".join(paras) if paras else raw
    text = html.unescape(re.sub(r"<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    return text[:5000]


def judge(story: dict, article: str) -> dict | None:
    prompt = (
        "You are a wire editor doing an accuracy check. Judge ONLY from the article text given — "
        "do not use outside knowledge for facts.\n\n"
        "ARTICLE TEXT (extracted, may be partial):\n" + article + "\n\n"
        "OUR HEADLINE: " + story.get("title", "") + "\n"
        "OUR DEK: " + story.get("dek", "") + "\n\n"
        "Questions: Does the headline+dek accurately portray this article? Check numbers, names, "
        "places, what actually happened vs. what is proposed, and tone (no overstatement). Also "
        "confirm the headline is NOT a copy of the article's own headline.\n\n"
        'Respond ONLY with JSON: {"verdict": "accurate|fixable|inaccurate", '
        '"issues": "<short reason or empty>", '
        '"fixed_title": "<corrected original-language headline if fixable, else empty>", '
        '"fixed_dek": "<corrected dek if fixable, else empty>"}'
    )
    import xai_client
    body = {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
            "search_parameters": {"mode": "off"}, "temperature": 0}
    data = xai_client.chat(KEY, body, timeout=180)
    if not data:
        return None
    try:
        text = data["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:  # noqa: BLE001
        print(f"::warning::judge parse failed: {e}")
        return None


def main() -> int:
    if not KEY:
        print("::error::XAI_API_KEY secret is not set")
        return 1
    if not LIVE.exists():
        print("No pending queue — nothing to check.")
        return 0
    data = json.loads(LIVE.read_text(encoding="utf-8"))
    kept, dropped, fixed, unfetchable = [], [], [], []

    for s in data.get("items", []):
        if s.get("accuracy", "").startswith("checked"):
            kept.append(s)  # already verified on a previous hourly pass
            continue
        if any(d in str(s.get("url", "")) for d in ("x.com/", "twitter.com/", "reddit.com/")):
            s["accuracy"] = "social-post"  # social posts are quoted, not judged
            kept.append(s)
            continue
        article = fetch_text(s.get("url", ""))
        if len(article) < 300:
            s["accuracy"] = "unverified-source-unfetchable"
            unfetchable.append(s.get("title", "")[:70])
            kept.append(s)
            continue
        v = judge(s, article) or {}
        verdict = v.get("verdict", "")
        if verdict == "accurate":
            s["accuracy"] = "checked"
            kept.append(s)
        elif verdict == "fixable" and v.get("fixed_title"):
            s["title"] = v["fixed_title"]
            if v.get("fixed_dek"):
                s["dek"] = v["fixed_dek"]
            s["accuracy"] = "checked-corrected"
            fixed.append(s["title"][:70])
            kept.append(s)
        elif verdict == "inaccurate":
            dropped.append((s.get("title", "")[:70], v.get("issues", "")))
        else:
            # judge failed — keep but flag rather than silently trusting
            s["accuracy"] = "unverified-judge-error"
            kept.append(s)

    data["items"] = kept
    data["accuracy_checked_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    LIVE.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")

    print(f"Accuracy check: {len(kept)} kept, {len(fixed)} corrected, {len(dropped)} dropped, {len(unfetchable)} unfetchable")
    for t, why in dropped:
        print(f"::warning::dropped inaccurate story: {t} — {why}")
    for t in fixed:
        print(f"corrected: {t}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
