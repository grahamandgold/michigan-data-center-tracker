#!/usr/bin/env python3
"""lessons_audit — compile raw corrections into a structured style guide.

Runs monthly (or on demand). Takes every raw lesson in desk-lessons.json,
plus the existing compiled rules, and asks the judgment model (Claude) to:
  * merge duplicates and near-duplicates,
  * resolve contradictions in favor of the NEWER correction,
  * generalize one-off notes into reusable rules,
  * weight rules by how often the same correction recurred,
  * retire anything time-bound that has expired.

Raw lessons are NEVER deleted — they are the permanent record. This only
maintains the compiled "rules" layer that lessons_util.py serves to agents.

Requires ANTHROPIC_API_KEY (falls back to other providers via the router).
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import multi_ai_client as ai  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "desk-lessons.json"

PROMPT = """You are the standards editor of a small AI-run local newsroom
(the Michigan Data Center Tracker). Below is (1) the current compiled style
guide and (2) every raw correction the human News Director has filed.

Compile a clean, structured style guide. Rules:
- Merge duplicates/near-duplicates into one rule; increase its weight by 0.5
  for each merged duplicate (cap 3.0).
- If two corrections contradict, the NEWER one wins; note nothing.
- Generalize one-off corrections into reusable rules, but keep a concrete
  example from the original correction.
- "trigger" is the moment the rule applies: headline | story-selection |
  social-posts | sourcing | tone | agenda | podcast | general.
- "applies_to" is which agent: all | wire | agenda | podcast | newsletter.
- Set "retired": true (keep the rule, flagged) only for rules that were
  clearly time-bound and expired.
- Keep every rule under 200 characters. Keep the guide under 40 rules —
  merge aggressively.

CURRENT COMPILED RULES:
{rules}

ALL RAW CORRECTIONS (oldest first, each with its timestamp):
{raw}

Respond ONLY with a JSON array of rule objects:
[{{"id": "L001", "trigger": "...", "rule": "...", "applies_to": "...",
   "weight": 1.0, "examples": ["..."], "retired": false}}]"""


def main() -> int:
    try:
        data = json.loads(LESSONS.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::error::cannot read desk-lessons.json: {e}")
        return 1

    raw = data.get("lessons", [])
    if not raw and not data.get("rules"):
        print("No lessons to compile.")
        return 0

    raw_text = "\n".join(f"[{l.get('at', '?')}] {l.get('text', '')}" for l in raw)
    rules_text = json.dumps(data.get("rules", []), indent=1, ensure_ascii=False) or "[]"

    reply = ai.chat("judgment",
                    [{"role": "user",
                      "content": PROMPT.format(rules=rules_text, raw=raw_text)}],
                    temperature=0)
    rules = ai.extract_json(reply)
    if not isinstance(rules, list) or not rules:
        print("::error::audit produced no valid rules — leaving file untouched")
        return 1

    # sanity: every rule needs id + rule text
    clean = []
    for i, r in enumerate(rules):
        if not isinstance(r, dict) or not r.get("rule"):
            continue
        r.setdefault("id", f"L{i + 1:03d}")
        r.setdefault("trigger", "general")
        r.setdefault("applies_to", "all")
        r.setdefault("weight", 1.0)
        r.setdefault("retired", False)
        clean.append(r)
    if not clean:
        print("::error::no usable rules after cleaning — aborting")
        return 1

    data["rules"] = clean
    data["rules_compiled_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    LESSONS.write_text(json.dumps(data, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    active = sum(1 for r in clean if not r.get("retired"))
    print(f"Lessons audit: {len(raw)} raw corrections -> {len(clean)} rules ({active} active)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
