#!/usr/bin/env python3
"""news_ingest — pull FRESH Michigan data-center stories from Google News.

Grok's search was missing obvious local coverage that Google News surfaces
every hour. This grounds the wire in real, dated, sourced articles instead of
hoping the model's search finds them.

Flow:
  1. Fetch Google News RSS for the beat queries (statewide + hot-zone towns),
     restricted to the last day.
  2. Keep only genuinely fresh (< FRESH_HOURS) Michigan data-center items,
     deduped against what's already live / killed / queued.
  3. Hand the batch to the model (Grok primary) to: pick the newsworthy ones,
     rewrite each headline in our voice (no "update"/"latest"), write a dek,
     and tag region + category. The training lessons are injected here too.
  4. File the survivors to live-data-pending.json as normal story candidates.

They then flow through the existing pipeline: headline_check verifies each
against its source (bad URLs self-drop), news_judge scores newsworthiness,
auto_publish promotes the strongest fresh ones. Original wording only; we
always keep the real publisher URL and link back to it.

Requires XAI_API_KEY (or ANTHROPIC/OPENAI as fallback). Stdlib + multi_ai_client.
"""
from __future__ import annotations

import hashlib
import html
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lessons_util  # noqa: E402
import multi_ai_client as ai  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
PENDING = ROOT / "live-data-pending.json"
DECISIONS = ROOT / "desk-decisions.json"

FRESH_HOURS = float(os.environ.get("INGEST_FRESH_HOURS", "40"))
MAX_CANDIDATES = int(os.environ.get("INGEST_MAX", "14"))
UA = {"User-Agent": "Mozilla/5.0 (Michigan Data Center Tracker news desk)"}

# Statewide beat + the current data-center hot zones (townships in the news).
QUERIES = [
    "michigan data center",
    "michigan data center moratorium",
    "michigan data center tax",
    "michigan data center hearing",
    "michigan data center zoning",
    "michigan data center rezoning",
    "michigan data center water",
    "michigan data center opposition",
    "michigan township data center",
    "michigan hyperscale data center",
    "michigan AI data center",
    "consumers energy data center",
    "DTE data center michigan",
    "michigan data center jobs",
    "michigan data center power grid",
]
HOT_ZONES = ["Saline Township", "Lyon Township", "Pittsfield", "Lenox Township",
             "Dowagiac", "Hayes Township", "Wixom", "Mundy Township",
             "Marshall Michigan", "Mason Michigan", "Adrian Michigan", "Garfield Township",
             "Ingham County", "Genesee County", "Washtenaw County", "Monroe County",
             "Eaton County", "Grand Rapids"]


def _rss(query: str) -> list[dict]:
    url = ("https://news.google.com/rss/search?q="
           + urllib.parse.quote(query + " when:4d")
           + "&hl=en-US&gl=US&ceid=US:en")
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
            raw = r.read().decode("utf-8", "ignore")
    except Exception as e:  # noqa: BLE001
        print(f"::warning::RSS fetch failed for '{query}': {e}")
        return []
    out = []
    for block in re.findall(r"<item>(.*?)</item>", raw, re.S):
        def grab(tag):
            m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", block, re.S)
            return html.unescape(re.sub(r"<!\[CDATA\[|\]\]>", "", m.group(1)).strip()) if m else ""
        title, link, pub = grab("title"), grab("link"), grab("pubDate")
        source = grab("source")
        if title and link:
            out.append({"title": title, "link": link, "source": source, "pub": pub})
    return out


def _age_ok(pub: str, now: datetime) -> bool:
    try:
        return (now - parsedate_to_datetime(pub)).total_seconds() / 3600.0 <= FRESH_HOURS
    except Exception:  # noqa: BLE001
        return False


def _resolve(link: str) -> str:
    """Follow the Google News redirect to the real publisher URL when we can."""
    try:
        req = urllib.request.Request(link, headers=UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            final = r.geturl()
        if "news.google.com" not in final:
            return final
    except Exception:  # noqa: BLE001
        pass
    return link


def _headline_original(ours: str, source: str) -> bool:
    """True when our headline is genuinely different from the outlet's — not a
    reword. Compares significant-word overlap (Jaccard); high overlap = a
    paraphrase, which must go to the desk for a real rewrite, not auto-publish."""
    stop = {"the", "a", "an", "to", "of", "in", "on", "for", "and", "as", "at",
            "its", "it", "with", "over", "data", "center", "centers", "michigan"}
    def toks(s):
        return {w for w in re.findall(r"[a-z0-9$]+", s.lower()) if w not in stop and len(w) > 2}
    a, b = toks(ours), toks(source)
    if not a or not b:
        return True
    overlap = len(a & b) / len(a | b)
    return overlap < 0.38


def _known_urls() -> set:
    urls = set()
    for path, key in ((LIVE, "stories"), (PENDING, "items")):
        try:
            for s in json.loads(path.read_text(encoding="utf-8")).get(key, []):
                urls.add(s.get("url"))
        except Exception:  # noqa: BLE001
            pass
    try:
        for k in json.loads(DECISIONS.read_text(encoding="utf-8")).get("killed", []):
            urls.add(k.get("url"))
    except Exception:  # noqa: BLE001
        pass
    return urls


def main() -> int:
    now = datetime.now(timezone.utc)
    seen_titles, raw_items = set(), []
    for q in QUERIES + [f"{z} data center" for z in HOT_ZONES]:
        for it in _rss(q):
            key = re.sub(r"\W+", "", it["title"].lower())[:60]
            if key in seen_titles or not _age_ok(it["pub"], now):
                continue
            seen_titles.add(key)
            raw_items.append(it)
    print(f"Google News: {len(raw_items)} fresh (< {FRESH_HOURS:.0f}h) unique items")
    if not raw_items:
        print("Nothing fresh from Google News this run.")
        return 0

    def _pubdt(it):
        try:
            return parsedate_to_datetime(it.get("pub", ""))
        except Exception:  # noqa: BLE001
            return datetime(1970, 1, 1, tzinfo=timezone.utc)
    raw_items.sort(key=_pubdt, reverse=True)  # freshest first, so the cap keeps the best
    raw_items = raw_items[:45]
    known = _known_urls()
    catalog = "\n".join(
        f"[{i}] {it['title']} — {it['source']} ({it['pub']})"
        for i, it in enumerate(raw_items))

    prompt = f"""You are the wire editor of the Michigan Data Center Tracker. Below are FRESH
headlines pulled from Google News in the last day. Select ONLY the items that are (a)
about Michigan's data-center buildout (projects, moratoria, hearings, power/water, tax,
politics) and (b) genuinely newsworthy to a Michigan reader. Skip national trend pieces
with no Michigan hook, pure PR, and duplicates. But select EVERY genuine Michigan
data-center story here — a township vote, a county action, a specific project, a hearing,
a lawsuit, a tax deal, a utility filing — not only the biggest one. A single local zoning
decision matters to that community; do not leave real local stories on the table.

WRITE A GENUINELY ORIGINAL HEADLINE FOR EACH — this is the golden rule and the News
Director rejects anything that fails it:
- Do NOT paraphrase or lightly reword the outlet's headline. Start from the FACTS and
  write a fresh headline from scratch, in our own voice.
- Lead with the STAKE a resident feels — the dollars, megawatts, water, who-wins/loses —
  NOT procedural jargon. Never write "weighs", "considers", "Board to Review", "IFEC",
  acronyms, or agenda language. Never use "update" or "latest".
- Make a civilian 30 minutes away care. Be specific: the figure, the town, the consequence.
  BAD (rejected, copies source): "Saline Township weighs 12-year tax break for Oracle"
  GOOD: "Oracle wants Saline to skip 12 years of taxes on its $43B campus"
  BAD (rejected, copies source): "Adrian enacts year-long pause on data center proposals"
  GOOD: "Adrian slams the brakes: no new data centers for a year"
Then write a 3-4 sentence dek and tag it.

FRESH HEADLINES (the outlet's wording — do NOT echo it, write your own from the facts):
{catalog}

Respond ONLY with a JSON array:
[{{"i": <index>, "title": "<original rewrite <=100 chars>",
   "dek": "<3-4 sentences, factual, why a Michigan reader cares>",
   "county": "<the Michigan county this story is about — e.g. Washtenaw, Lenawee, Ingham; empty only if truly statewide>",
   "region": "metro|west|mid|north|statewide",
   "tag": "Power & Grid|Local Government|Policy|Water|Money|Explainers"}}]
Keep at most {MAX_CANDIDATES}. If none qualify, return [].
{lessons_util.lessons_block(agent="wire")}"""

    reply = ai.chat("hunting", [{"role": "user", "content": prompt}], temperature=0.2, timeout=300)
    picks = ai.extract_json(reply)
    if not isinstance(picks, list) or not picks:
        print("Model selected nothing usable from the fresh batch.")
        return 0

    try:
        pending = json.loads(PENDING.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        pending = {"items": []}
    now_iso = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    added = 0
    for p in picks:
        try:
            src = raw_items[int(p["i"])]
        except (KeyError, ValueError, IndexError):
            continue
        url = _resolve(src["link"])
        if not url or url in known:
            continue
        title = str(p.get("title", "")).strip()
        if len(title) < 12:
            continue
        region = p.get("region") if p.get("region") in {"metro", "west", "mid", "north", "statewide"} else "statewide"
        tag = p.get("tag") if p.get("tag") in {"Power & Grid", "Local Government", "Policy", "Water", "Money", "Explainers"} else "Policy"
        # Originality gate: Google News stories only auto-publish when the headline
        # is genuinely rewritten, not a paraphrase of the outlet's. If our title
        # still overlaps the source too much, keep it as a desk candidate (needs
        # a human rewrite) instead of letting it go straight to the homepage.
        rewritten = _headline_original(title, src.get("title", ""))
        # The timestamp must be the TRUTH: the source's real publish time, not
        # when we ingested it. Otherwise every story from one run shows the same
        # "Nh ago". Fall back to now only if the feed gave no usable date.
        try:
            pub_iso = parsedate_to_datetime(src.get("pub", "")).astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        except Exception:  # noqa: BLE001
            pub_iso = now_iso
        item = {
            "title": title[:130], "dek": str(p.get("dek", ""))[:600], "url": url,
            "source": src.get("source") or "News", "region": region, "cat": "STATEWIDE",
            "county": str(p.get("county", "")).strip(),
            "tag": tag, "iso": pub_iso, "kind": "story",
            "id": hashlib.sha1(url.encode()).hexdigest()[:12], "filed_at": now_iso,
            "origin": "google-news", "headline_rewritten": rewritten,
            # Keep the outlet's own headline so the desk can show ours vs theirs
            # side-by-side — the editor's proof we're writing new, not copying.
            "source_title": str(src.get("title", "")).strip()[:200],
            "source_url": url,
        }
        pending.setdefault("items", []).insert(0, item)
        known.add(url)
        added += 1
        print(f"  QUEUED: {title[:80]}  [{src.get('source')}]")

    if added:
        pending["items"] = pending["items"][:40]
        pending["updated_at"] = now_iso
        PENDING.write_text(json.dumps(pending, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"news_ingest: {added} fresh candidates filed to the desk queue")
    return 0


if __name__ == "__main__":
    sys.exit(main())
