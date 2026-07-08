#!/usr/bin/env python3
"""Agenda investigator v2 — document journalism the tracker owns.

For every meeting on the tracker calendar TODAY or TOMORROW (ET):

  1. DOWNLOAD the agenda page itself, find every linked packet document
     (agenda PDFs, staff reports, site plans), download them, and EXTRACT
     the text (pypdf — installed by the workflow).
  2. Pull the tracker's OWN records for that community from map-data.json
     (projects, megawatts, moratoria) — proprietary context nobody else has.
  3. Give Grok the full dossier and have it write an original story WITH
     PERSPECTIVE: what's actually in the packet, what it means for bills,
     water, and land, who decides, and what happens next.
  4. File the story to the desk approval queue + agenda-brief.json bullets
     for the morning DATA CENTER INTELLIGENCE REPORT.

Fact discipline (hard): every fact comes from the extracted documents, the
tracker's own data, or attributed coverage. Perspective = analysis of those
facts — never speculation about outcomes, never invented figures. If the
documents contain nothing data-center related, skip the meeting.

Requires: XAI_API_KEY. pypdf optional (workflow installs it; degrades to
HTML-only extraction without it).
"""
from __future__ import annotations

import hashlib
import html as htmllib
import io
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin

sys.path.insert(0, str(Path(__file__).resolve().parent))

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
BRIEF = ROOT / "agenda-brief.json"
NOTES = ROOT / "agent-notes.json"
MAPD = ROOT / "map-data.json"
KEY = os.environ.get("XAI_API_KEY", "")
MODEL = os.environ.get("XAI_MODEL", "grok-4")

ET_OFFSET = timedelta(hours=-4)
UA = {"User-Agent": "Mozilla/5.0 (Michigan Data Center Tracker agenda desk)"}


def et_today() -> datetime:
    return datetime.now(timezone.utc) + ET_OFFSET


# ---------------------------------------------------------------- fetching
def fetch(url: str, limit: int = 6_000_000) -> bytes:
    req = urllib.request.Request(url, headers=UA)
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read(limit)


def html_text(raw: bytes) -> str:
    s = raw.decode("utf-8", "ignore")
    s = re.sub(r"<(script|style|nav|header|footer)[^>]*>.*?</\1>", " ", s, flags=re.S | re.I)
    s = htmllib.unescape(re.sub(r"<[^>]+>", " ", s))
    return re.sub(r"\s+", " ", s).strip()


def find_pdf_links(raw: bytes, base_url: str) -> list[tuple[str, str]]:
    """(url, link_text) pairs for likely packet documents on an agenda page."""
    s = raw.decode("utf-8", "ignore")
    out, seen = [], set()
    for m in re.finditer(r'<a[^>]+href="([^"]+)"[^>]*>(.*?)</a>', s, flags=re.S | re.I):
        href, text = m.group(1), re.sub(r"<[^>]+>|\s+", " ", m.group(2)).strip()
        full = urljoin(base_url, htmllib.unescape(href))
        if full in seen:
            continue
        lower = (full + " " + text).lower()
        if full.lower().split("?")[0].endswith(".pdf") or any(
                k in lower for k in ("agenda", "packet", "staff report", "site plan",
                                     "minutes", "downloadfile", "viewfile", "documentcenter")):
            seen.add(full)
            out.append((full, text[:80]))
    return out[:10]


def pdf_text(data: bytes) -> str:
    try:
        from pypdf import PdfReader
        reader = PdfReader(io.BytesIO(data))
        pages = [(p.extract_text() or "") for p in reader.pages[:40]]
        return re.sub(r"\s+", " ", " ".join(pages)).strip()
    except Exception as e:  # noqa: BLE001
        print(f"::warning::pdf extract failed: {e}")
        return ""


def build_dossier(meeting: dict) -> tuple[str, list]:
    """Download the agenda page + its packet PDFs.
    Returns (extracted text, [{label, url}] of documents actually read —
    so the News Director can open the same documents when approving)."""
    url = meeting.get("link", "")
    parts, docs = [], []
    try:
        raw = fetch(url)
    except Exception as e:  # noqa: BLE001
        print(f"::warning::agenda page unreachable {url}: {e}")
        return "", []
    if url.lower().split("?")[0].endswith(".pdf"):
        parts.append(("AGENDA PDF", pdf_text(raw)))
        docs.append({"label": "Agenda (PDF)", "url": url})
    else:
        parts.append(("AGENDA PAGE", html_text(raw)[:6000]))
        docs.append({"label": "Agenda page", "url": url})
        pdfs = find_pdf_links(raw, url)
        print(f"  {meeting.get('body')}: {len(pdfs)} candidate documents")
        grabbed = 0
        for purl, label in pdfs:
            if grabbed >= 3:
                break
            try:
                data = fetch(purl)
                if data[:4] == b"%PDF":
                    text = pdf_text(data)
                    if len(text) > 200:
                        nice = label or purl.rsplit("/", 1)[-1]
                        parts.append((f"DOCUMENT: {nice}", text[:12000]))
                        docs.append({"label": nice[:70], "url": purl})
                        grabbed += 1
                        print(f"    read PDF: {nice[:60]} ({len(text)} chars)")
            except Exception as e:  # noqa: BLE001
                print(f"    skip {purl[-60:]}: {e}")
    dossier = "\n\n".join(f"===== {label} =====\n{text}" for label, text in parts if text)
    return dossier[:30000], docs


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
                        f"{p.get('status')}, {p.get('power_mw') or '?'} MW, developer {p.get('developer') or 'undisclosed'}"
                        f"{' — ' + str(p.get('note'))[:120] if p.get('note') else ''}")
    return "\n".join(hits[:6])


def director_notes() -> str:
    try:
        notes = json.loads(NOTES.read_text(encoding="utf-8")).get("notes", [])
        mine = [n for n in notes if n.get("agent") in ("All agents", "Assignment Manager")]
        if mine:
            return ("\nSTANDING NOTES FROM THE NEWS DIRECTOR (obey these):\n"
                    + "\n".join(f"- {n['text']}" for n in mine))
    except Exception:  # noqa: BLE001
        pass
    return ""


# ---------------------------------------------------------------- writing
def write_story(meeting: dict, when_label: str, dossier: str, our_context: str) -> dict | None:
    prompt = f"""You are the agenda desk of the Michigan Data Center Tracker, writing an
ORIGINAL document-based story about a public meeting {when_label.lower()}. We extracted the
actual agenda and packet documents for you — this is primary-source material readers
can't get anywhere else. Write the story WITH PERSPECTIVE: not just what's on the
agenda, but what it means and what happens next.

THE MEETING ({when_label}):
- Body: {meeting.get('body')} — {meeting.get('iso')} at {meeting.get('time', 'TBD')} ET
- Agenda link: {meeting.get('link', '')}

EXTRACTED DOCUMENTS (primary source — quote figures and items from here):
{dossier if dossier else '(documents could not be extracted — you may search for the agenda and local coverage instead)'}

THE TRACKER'S OWN RECORDS FOR THIS COMMUNITY (our proprietary context — use it):
{our_context or '(none on file)'}

You may also SEARCH for background: prior votes by this body, local coverage,
how similar decisions went in other Michigan townships.

WRITE WITH PERSPECTIVE — the analysis layers that make this ours:
- WHAT'S ACTUALLY IN THE PACKET: the concrete items — parcels, acreage, megawatts,
  dollar figures, abatement terms, moratorium language — each attributed ("per the
  staff report", "the packet shows", "the draft resolution would…").
- WHY IT MATTERS: connect to electric bills, water, farmland, tax base — grounded
  in the documents and our tracker records, plainly explained.
- THE STAKES & PLAYERS: who decides, what the options on the table are, where this
  body has stood before (attributed), residents' concerns if documented.
- WHAT HAPPENS NEXT: the procedural path (vote tonight? public comment? next reading?).

HARD RULES: facts only from the documents, our records, or attributed coverage.
No invented figures, items, quotes, or predictions of the outcome. Balanced —
present both the case for and concerns about the project as documented. Identify
every named person by role. Original wording throughout. If the documents contain
NOTHING data-center/power/water/land-use related, return {{"skip": true, "why": "<one line>"}}.

Respond ONLY with JSON:
{{"skip": false,
 "title": "<original headline with a specific hook from the documents, ≤100 chars>",
 "dek": "<3-4 sentences: the most newsworthy specifics + why it matters, attributed>",
 "findings": "<4-6 key specifics from the documents, attributed, separated by ' | '>",
 "perspective": "<2-3 sentences of analysis: stakes and what happens next>",
 "brief": "<one newsletter bullet ≤160 chars with the single hardest fact>",
 "region": "<Southeast Michigan|West Michigan|Mid-Michigan|Northern Michigan|statewide>"}}
{director_notes()}"""
    import xai_client
    out = xai_client.chat(KEY, {"model": MODEL, "messages": [{"role": "user", "content": prompt}],
                                "search_parameters": {"mode": "on"}, "temperature": 0.25}, timeout=420)
    if not out:
        return None
    try:
        text = out["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", text, re.S)
        return json.loads(m.group(0)) if m else None
    except Exception as e:  # noqa: BLE001
        print(f"::warning::parse failed for {meeting.get('body')}: {e}")
        return None


def main() -> int:
    if not KEY:
        print("::error::XAI_API_KEY secret is not set")
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
        dossier, docs_read = build_dossier(m)
        context = tracker_context(m)
        r = write_story(m, label, dossier, context)
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
        # replace any thinner pending story for this same agenda with the richer one
        pending["items"] = [it for it in pending.get("items", [])
                            if not (it.get("url") == url and it.get("kind") == "agenda")]
        if url in published_urls:
            print(f"  already published: {m.get('body')}")
            continue
        item = {
            "title": r["title"][:130], "dek": r["dek"][:600], "url": url,
            "source": f"{m.get('body', 'Meeting')} agenda", "region": r.get("region", "statewide"),
            "cat": "Meetings", "tag": "Agenda watch", "iso": now_iso,
            "kind": "agenda", "id": hashlib.sha1((url + m.get("iso", "") + "v2").encode()).hexdigest()[:12],
            "filed_at": now_iso, "accuracy": "document-based",
            "findings": r.get("findings", "")[:800],
            "perspective": r.get("perspective", "")[:400],
            "documents": docs_read[:4],
        }
        pending["items"].insert(0, item)
        filed += 1
        print(f"  FILED: {item['title'][:90]}")

    pending["items"] = pending["items"][:20]
    pending["updated_at"] = now_iso
    PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    BRIEF.write_text(json.dumps({"generated_at": now_iso, "for_dates": [today, tomorrow],
                                 "items": briefs}, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"Agenda desk: {filed} document-based stories filed, {len(briefs)} newsletter bullets")
    return 0


if __name__ == "__main__":
    sys.exit(main())
