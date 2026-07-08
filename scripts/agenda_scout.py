#!/usr/bin/env python3
"""Agenda investigator v3 — document journalism the tracker owns.

What changed from v2:
  * Extraction ladder (doc_extract.py): plain fetch -> Playwright render for
    JS portals (Granicus/CivicPlus/BoardDocs/iCompass) -> pypdf -> vision OCR
    on scanned PDFs -> vision-read of the rendered page as last resort.
  * Document depth score (0-10) on every story. Below 6 the story is filed
    honestly as "thin — needs human background," never dressed up.
  * Background step: the agent searches prior minutes, this body's past votes
    on similar items, and local coverage — history is part of the story.
  * Council flow via multi_ai_client: Grok (hunting) drafts with live search;
    Claude (judgment) checks attribution + polishes before Andy sees it.
  * The training memory (compiled rules + fresh corrections) is injected into
    every run via lessons_util.

The desk item shape is unchanged — everything lands in the same approval
queue, with extra fields: depth_score, depth_label, extraction_method.
"""
from __future__ import annotations

import hashlib
import json
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import doc_extract  # noqa: E402
import lessons_util  # noqa: E402
import multi_ai_client as ai  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
BRIEF = ROOT / "agenda-brief.json"
NOTES = ROOT / "agent-notes.json"
MAPD = ROOT / "map-data.json"

ET_OFFSET = timedelta(hours=-4)


def et_today() -> datetime:
    return datetime.now(timezone.utc) + ET_OFFSET


def tracker_context(meeting: dict) -> str:
    """Our own map records for this community — the context we own."""
    try:
        pts = json.loads(MAPD.read_text(encoding="utf-8")).get("map_points", [])
    except Exception:  # noqa: BLE001
        return ""
    hay = (str(meeting.get("body", "")) + " " + str(meeting.get("county", ""))).lower()
    hits = []
    for p in pts:
        muni = str(p.get("municipality", "")).lower()
        county = str(p.get("county", "")).lower()
        if (muni and any(w in hay for w in muni.split() if len(w) > 4)) or (county and county in hay):
            hits.append(f"- {p.get('name')} ({p.get('municipality')}, {p.get('county')} Co.): "
                        f"{p.get('status')}, {p.get('power_mw') or '?'} MW, developer "
                        f"{p.get('developer') or 'undisclosed'}"
                        f"{' — ' + str(p.get('note'))[:120] if p.get('note') else ''}")
    return "\n".join(hits[:6])


def director_notes() -> str:
    out = ""
    try:
        notes = json.loads(NOTES.read_text(encoding="utf-8")).get("notes", [])
        mine = [n for n in notes if n.get("agent") in ("All agents", "Assignment Manager")]
        if mine:
            out += ("\nSTANDING NOTES FROM THE NEWS DIRECTOR (obey these):\n"
                    + "\n".join(f"- {n['text']}" for n in mine))
    except Exception:  # noqa: BLE001
        pass
    out += lessons_util.lessons_block(agent="agenda")
    return out


# ---------------------------------------------------------------- background
def background_research(meeting: dict) -> str:
    """Search for history: prior votes, past minutes, local coverage."""
    prompt = f"""Research the recent history relevant to this Michigan public meeting.
Body: {meeting.get('body')} ({meeting.get('county')} County) — meets {meeting.get('iso')}.
Topic on the agenda: {meeting.get('topic', 'data center related item')}

Find and report, with source names:
1. How this body has voted on data-center / large-development items before
   (search "{meeting.get('body')}" minutes, past agendas, local news).
2. Any prior local coverage of this specific project or applicant.
3. How comparable Michigan townships handled similar requests (one line).

Rules: only report what you actually found, each fact with its source name.
If you find nothing on a point, say "nothing found" for that point.
Keep it under 250 words. Plain text."""
    out = ai.chat("hunting", [{"role": "user", "content": prompt}],
                  temperature=0.1, search=True, timeout=300)
    return (out or "").strip()[:2500]


# ---------------------------------------------------------------- writing
def write_story(meeting: dict, when_label: str, dossier: str, our_context: str,
                background: str, meta: dict) -> dict | None:
    thin = meta.get("thin", True)
    depth_label = ("THIN — packet not extractable; be explicit about what is not yet public"
                   if thin else "solid primary-source material")
    depth_note = f"Document depth: {meta.get('depth_score', 0)}/10 ({depth_label})"
    prompt = f"""Write a true journalistic meeting preview (150-250 words of body across dek,
findings and perspective) in the style of a sharp local reporter — the agenda desk of the
Michigan Data Center Tracker, writing about a public meeting {when_label.lower()}.

STRUCTURE — every layer required:
1. LEDE: a headline + dek that make a civilian 30 minutes away care. Specific hook from
   the documents, never generic.
2. FINDINGS: concrete stakes from the actual packet + our map records + prior votes —
   parcels, acreage, megawatts, dollar figures, abatement terms — each attributed
   ("per the staff report", "the packet shows", "the draft resolution would…").
3. HISTORY/CONTEXT: one or two sentences on how this body has handled similar items
   before, from the background research below (attributed).
4. WHAT HAPPENS NEXT + WHY IT MATTERS: the procedural path (vote tonight? public
   comment? next reading?) and the connection to bills, water, farmland, tax base.

{depth_note}

THE MEETING ({when_label}):
- Body: {meeting.get('body')} — {meeting.get('iso')} at {meeting.get('time', 'TBD')} ET
- Agenda link: {meeting.get('link', '')}

EXTRACTED DOCUMENTS (primary source — quote figures and items from here):
{dossier if dossier else '(no documents were extractable — write honestly about what the public cannot yet see, using the background research and our records only)'}

BACKGROUND RESEARCH (attributed history — use for the context layer):
{background or '(none found)'}

THE TRACKER'S OWN RECORDS FOR THIS COMMUNITY (our proprietary context — use it):
{our_context or '(none on file)'}

HARD RULES: facts only from the documents, the background research, our records, or
attributed coverage. No invented figures, items, quotes, or outcome predictions.
Never use the words "update", "latest", or hype. Tone: sober, transparent,
numbers-first. Balanced — the case for and the documented concerns about the project.
Identify every named person by role. Original wording throughout. If the documents and
research contain NOTHING data-center/power/water/land-use related, return
{{"skip": true, "why": "<one line>"}}.

Respond ONLY with JSON:
{{"skip": false,
 "title": "<original headline with a specific hook, <=100 chars>",
 "dek": "<3-4 sentences: the most newsworthy specifics + why a reader 30 min away cares>",
 "findings": "<4-6 key specifics, attributed, separated by ' | '>",
 "perspective": "<2-3 sentences: history/context + what happens next>",
 "brief": "<one newsletter bullet <=160 chars with the single hardest fact>",
 "region": "<Southeast Michigan|West Michigan|Mid-Michigan|Northern Michigan|statewide>"}}
{director_notes()}"""
    draft_text = ai.chat("hunting", [{"role": "user", "content": prompt}],
                         temperature=0.25, search=True, timeout=420)
    draft = ai.extract_json(draft_text)
    if not isinstance(draft, dict) or draft.get("skip"):
        return draft if isinstance(draft, dict) else None
    return polish(draft, dossier, meta)


def polish(draft: dict, dossier: str, meta: dict) -> dict:
    """Second model family checks attribution and sharpens the draft."""
    prompt = f"""You are the standards editor (a different model family than the writer).
Review this meeting-preview story against the extracted documents. Fix, do not rewrite
from scratch:
- Any figure/claim NOT supported by the documents or clearly attributed -> remove or
  soften to what IS supported.
- Headline must carry a specific hook and never the words "update" or "latest".
- Dek must answer "why should someone 30 minutes away care" in the first sentence.
- Keep the exact same JSON shape and keys. Original wording. Sober, numbers-first.

DOCUMENTS (ground truth):
{dossier[:15000] if dossier else '(none — the story must be explicit that the packet is not yet public)'}

STORY:
{json.dumps(draft, ensure_ascii=False)}

Respond ONLY with the corrected JSON object."""
    fixed_text = ai.chat("judgment", [{"role": "user", "content": prompt}],
                         temperature=0, timeout=300)
    fixed = ai.extract_json(fixed_text)
    if isinstance(fixed, dict) and fixed.get("title") and fixed.get("dek"):
        return fixed
    return draft  # polish is best-effort, never fatal


# ---------------------------------------------------------------- main
def main() -> int:
    if not any(os.environ.get(k) for k in ("XAI_API_KEY", "ANTHROPIC_API_KEY", "OPENAI_API_KEY")):
        print("::error::no AI API key set")
        return 1
    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::error::no live-data.json: {e}")
        return 1

    today = et_today().strftime("%Y-%m-%d")
    tomorrow = (et_today() + timedelta(days=1)).strftime("%Y-%m-%d")
    targets = [m for m in live.get("meetings", []) if m.get("iso") in (today, tomorrow) and m.get("link")]
    if not targets:
        print("No meetings today or tomorrow — nothing to investigate.")
        return 0

    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pending = {"items": []}
    published_urls = {s.get("url") for s in live.get("stories", [])}

    now_iso = datetime.now(timezone.utc).isoformat(timespec="seconds")
    briefs, filed = [], 0
    for m in targets[:6]:
        label = "Tonight" if m.get("iso") == today else "Tomorrow"
        print(f"Investigating: {m.get('body')} ({label})")
        dossier, docs_read, meta = doc_extract.build_dossier(m.get("link", ""), m.get("body", ""))
        print(f"  depth {meta['depth_score']}/10 via {meta['method']} "
              f"({meta['pdfs_read']} PDFs){' — THIN' if meta['thin'] else ''}")
        context = tracker_context(m)
        background = background_research(m)
        r = write_story(m, label, dossier, context, background, meta)
        if not r:
            continue
        if r.get("skip"):
            print(f"  skip: {r.get('why', '')[:90]}")
            continue
        if not (r.get("title") and r.get("dek")):
            continue
        url = m.get("link", "")
        briefs.append({"iso": m.get("iso"), "time": m.get("time", "TBD"), "meeting": m.get("body"),
                       "bullet": (r.get("brief") or r["title"])[:180], "link": url})
        pending["items"] = [it for it in pending.get("items", [])
                            if not (it.get("url") == url and it.get("kind") == "agenda")]
        if url in published_urls:
            print(f"  already published: {m.get('body')}")
            continue
        item = {
            "title": r["title"][:130], "dek": r["dek"][:600], "url": url,
            "source": f"{m.get('body', 'Meeting')} agenda", "region": r.get("region", "statewide"),
            "cat": "Meetings", "tag": "Agenda watch", "iso": now_iso,
            "kind": "agenda", "id": hashlib.sha1((url + m.get("iso", "") + "v3").encode()).hexdigest()[:12],
            "filed_at": now_iso,
            "accuracy": "document-based" if not meta["thin"] else "thin — needs human background",
            "findings": r.get("findings", "")[:800],
            "perspective": r.get("perspective", "")[:400],
            "documents": docs_read[:4],
            "depth_score": meta["depth_score"],
            "extraction_method": meta["method"],
        }
        pending["items"].insert(0, item)
        filed += 1
        print(f"  FILED ({item['accuracy']}): {item['title'][:90]}")

    pending["items"] = pending["items"][:20]
    pending["updated_at"] = now_iso
    PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    BRIEF.write_text(json.dumps({"generated_at": now_iso, "for_dates": [today, tomorrow],
                                 "items": briefs}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Agenda desk: {filed} document-based stories filed, {len(briefs)} newsletter bullets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
