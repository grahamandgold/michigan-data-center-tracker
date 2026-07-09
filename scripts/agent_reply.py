#!/usr/bin/env python3
"""Newsroom two-way line — the News Director messages an agent, the agent replies.

Andy sends a message from the desk (to the Managing Editor by default, or a named
agent). This picks up every thread whose last message is from Andy and writes a
reply IN THAT AGENT'S VOICE. If the message is a standing instruction, the agent
also files it as a LESSON (desk-lessons.json) so the newsroom actually adapts on
its next run — messages change behavior, not just chat.

Runs in CI (agent-reply.yml) on every push to newsroom-messages.json + a schedule.
Stdlib only; needs one of XAI/ANTHROPIC/OPENAI keys.
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MSGS = ROOT / "newsroom-messages.json"
LESSONS = ROOT / "desk-lessons.json"
MAPD = ROOT / "map-data.json"
LIVE = ROOT / "live-data.json"
sys.path.insert(0, str(ROOT / "scripts"))

try:
    import multi_ai_client as ai
except Exception as e:  # noqa: BLE001
    ai = None
    _AI_ERR = str(e)

# Which agent each role maps to for the LESSON hook (so a directive reaches the
# right script's lessons_block(agent=...)).
LESSON_AGENT = {
    "Managing Editor": "wire", "Head Writer": "wire", "Standards Editor": "wire",
    "Data Center Editor": "map", "Assignment Manager": "agenda",
    "Political Director": "capitol", "Newsletter Producer": "newsletter",
    "Streaming Producer": "podcast", "Website Manager": "wire", "Archive Librarian": "wire",
}

ROSTER = {
    "Managing Editor": ("Graham, the Managing Editor. You run the newsroom floor for News "
        "Director Andy. You double-check stories and journalism and co-host The Gigacast. "
        "You are the single point of contact: OWN every request, and when it belongs to a "
        "specialist, say who you're assigning it to — Emmy (Data Center Editor) for the "
        "map/data, the Political Director for the Legislature, the Head Writer for "
        "headlines, the Assignment Manager for meeting agendas."),
    "Data Center Editor": ("Emmy, the Data Center Editor. Your beat is the map — every "
        "project, permit, and moratorium — plus fact-checking reader tips."),
    "Head Writer": ("the Head Writer. You write the wire headlines every hour from the "
        "facts, in our own voice — never copying the outlet's wording."),
    "Standards Editor": ("the Standards Editor. You guard accuracy, attribution and "
        "labeling; you catch overstatement and headlines too close to the source."),
    "Political Director": ("the Political Director. You watch the Michigan Legislature four "
        "times a day for anything touching data centers."),
    "Assignment Manager": ("the Assignment Manager. You investigate meeting agendas and "
        "packets and turn them into real stories."),
    "Streaming Producer": ("the Streaming Producer. You produce The Gigacast (Graham & "
        "Emmy) twice a day."),
    "Newsletter Producer": ("the Newsletter Producer. You build the daily Data Center "
        "Intelligence Report email."),
    "Website Manager": ("the Website Manager. You deploy and keep the live site up."),
    "Archive Librarian": ("the Archive Librarian. You keep the archive and the record."),
}


def _now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _snapshot() -> str:
    try:
        pts = json.loads(MAPD.read_text()).get("map_points", [])
        proj = sum(1 for p in pts if p.get("layer") == "projects")
        mor = sum(1 for p in pts if p.get("layer") == "moratoria")
    except Exception:  # noqa: BLE001
        proj = mor = "?"
    try:
        live = len(json.loads(LIVE.read_text()).get("stories", []))
    except Exception:  # noqa: BLE001
        live = "?"
    return f"Newsroom snapshot: {proj} mapped projects, {mor} moratoria, {live} stories live."


def _add_lesson(agent_key: str, text: str) -> None:
    try:
        data = json.loads(LESSONS.read_text()) if LESSONS.exists() else {"lessons": []}
    except Exception:  # noqa: BLE001
        data = {"lessons": []}
    data.setdefault("lessons", []).append(
        {"text": f"[{agent_key}] {text}"[:400], "at": _now(), "source": "news-director-message"})
    data["lessons"] = data["lessons"][-300:]
    LESSONS.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")


def reply_for(thread: dict) -> tuple[str, str]:
    to = thread.get("to", "Managing Editor")
    persona = ROSTER.get(to, ROSTER["Managing Editor"])
    convo = "\n".join(f"{m.get('from')}: {m.get('text','')}" for m in thread.get("messages", []))
    prompt = (
        f"You are {persona}\n\n{_snapshot()}\n\n"
        "News Director Andy is messaging you directly. Reply briefly and directly in your "
        "own voice (2-5 sentences). Acknowledge, answer plainly, and if he's asking for a "
        "fix or an action, say exactly what you'll do — and if you're the Managing Editor "
        "and it belongs to a specialist, name who you're assigning it to. Be concrete and "
        "useful, never corporate.\n\n"
        "IF his message is a standing instruction that should change how the newsroom works "
        "from now on, add a final line EXACTLY like:\nLESSON: <the durable instruction in one sentence>\n"
        "(omit the LESSON line for one-off questions).\n\n"
        f"CONVERSATION SO FAR:\n{convo}\n\nYour reply:")
    if ai is None:
        return (f"(Auto-reply unavailable: {_AI_ERR}. Andy — I got your message and will "
                f"handle it.)", "")
    try:
        raw = ai.chat("judgment", [{"role": "user", "content": prompt}], temperature=0.4)
    except Exception as e:  # noqa: BLE001
        return (f"(Couldn't reach the model just now: {e}. Message received.)", "")
    raw = (raw or "").strip()
    lesson = ""
    for line in raw.splitlines():
        if line.strip().upper().startswith("LESSON:"):
            lesson = line.split(":", 1)[1].strip()
    body = "\n".join(l for l in raw.splitlines() if not l.strip().upper().startswith("LESSON:")).strip()
    return body or "Got it.", lesson


def main() -> int:
    if not MSGS.exists():
        print("[agent_reply] no newsroom-messages.json"); return 0
    data = json.loads(MSGS.read_text(encoding="utf-8"))
    threads = data.get("threads", [])
    changed = 0
    for th in threads:
        msgs = th.get("messages", [])
        if not msgs or msgs[-1].get("from") != "Andy":
            continue  # nothing new from the director to answer
        to = th.get("to", "Managing Editor")
        print(f"[agent_reply] {to} replying to thread {th.get('id')}")
        body, lesson = reply_for(th)
        msgs.append({"from": to, "text": body, "at": _now()})
        th["status"] = "answered"
        if lesson:
            _add_lesson(LESSON_AGENT.get(to, "wire"), lesson)
            th["lesson_filed"] = lesson
        changed += 1
    if changed:
        data["threads"] = threads
        data["updated_at"] = _now()
        MSGS.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        print(f"[agent_reply] answered {changed} message(s)")
    else:
        print("[agent_reply] nothing to answer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
