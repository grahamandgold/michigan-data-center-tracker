#!/usr/bin/env python3
"""lessons_util — one loader for the newsroom's training memory.

desk-lessons.json now has two layers:
  "lessons"  raw corrections, appended by the desk exactly as before
             (the desk's writer is untouched — full backward compatibility)
  "rules"    the compiled style guide: deduped, weighted, structured rules
             produced by lessons_audit.py

Agents call lessons_block() and get the compiled rules plus any raw lessons
newer than the last compile — so a correction Andy makes at 2pm is obeyed by
the 3pm run even though the audit hasn't run yet.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LESSONS = ROOT / "desk-lessons.json"


def _load() -> dict:
    try:
        return json.loads(LESSONS.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}


def lessons_block(agent: str = "", max_raw: int = 15) -> str:
    """The training-memory text to inject into an agent prompt."""
    data = _load()
    rules = [r for r in data.get("rules", []) if not r.get("retired")]
    compiled_at = data.get("rules_compiled_at", "")
    out = ""

    if rules:
        rules.sort(key=lambda r: -float(r.get("weight", 1.0)))
        lines = []
        for r in rules:
            scope = r.get("applies_to", "all")
            if agent and scope not in ("all", agent):
                continue
            ex = f" (e.g. {r['examples'][0]})" if r.get("examples") else ""
            lines.append(f"- [{r.get('trigger', 'general')}] {r.get('rule', '')}{ex}")
        if lines:
            out += ("\n\nNEWSROOM STYLE GUIDE — compiled from every correction the News "
                    "Director has ever made. These are standing rules, not suggestions:\n"
                    + "\n".join(lines))

    raw = data.get("lessons", [])
    fresh = [l for l in raw if str(l.get("at", "")) > compiled_at] if compiled_at else raw
    fresh = fresh[-max_raw:]
    if fresh:
        out += ("\n\nRECENT CORRECTIONS (newest feedback, not yet folded into the style "
                "guide — obey these too):\n" + "\n".join(f"- {l.get('text', '')}" for l in fresh))
    return out
