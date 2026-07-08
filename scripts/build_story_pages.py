#!/usr/bin/env python3
"""build_story_pages — static HTML snapshots of every published story, for SEO.

The public site renders stories client-side from live-data.json, which search
engines index poorly. This renders every story in live-data.json to a static
page at stories/pages/<slug>.html with proper metadata + NewsArticle JSON-LD,
and writes sitemap-stories.xml. Run after every publish (wire-refresh commit
step) or on its own schedule. Stdlib only, no AI calls, deterministic.
"""
from __future__ import annotations

import html
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LIVE = ROOT / "live-data.json"
OUT = ROOT / "stories" / "pages"
SITEMAP = ROOT / "sitemap-stories.xml"
SITE = "https://grahamandgold.github.io/mi-data-center-tracker"

PAGE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — Michigan Data Center Tracker</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{site}/stories/pages/{slug}.html">
<meta property="og:title" content="{title}">
<meta property="og:description" content="{desc}">
<meta property="og:type" content="article">
<meta property="og:image" content="{site}/social-card.png">
<script type="application/ld+json">{jsonld}</script>
<link href="https://fonts.googleapis.com/css2?family=Saira+Condensed:wght@700;800&family=Archivo:wght@400;600&family=Space+Mono&display=swap" rel="stylesheet">
<style>
 body{{background:#121110;color:#f5f1ea;font-family:Archivo,sans-serif;max-width:720px;margin:0 auto;padding:28px 18px;line-height:1.55}}
 .k{{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.18em;color:#d92b2b;text-transform:uppercase}}
 h1{{font-family:'Saira Condensed',sans-serif;font-weight:800;font-size:clamp(26px,5vw,40px);text-transform:uppercase;line-height:1.08;margin:8px 0}}
 .meta{{color:#8a847c;font-size:13px;margin-bottom:18px}}
 .dek{{font-size:17px}} .sec{{margin-top:18px}} .sec b{{font-family:'Space Mono',monospace;font-size:11px;letter-spacing:.14em;color:#8a847c;text-transform:uppercase;display:block;margin-bottom:4px}}
 a{{color:#f5f1ea}} .src{{margin-top:24px;padding-top:14px;border-top:1px solid #2b2927;font-size:13px;color:#8a847c}}
 .home{{display:inline-block;margin-top:20px;font-family:'Space Mono',monospace;font-size:12px;color:#d92b2b;text-decoration:none}}
</style>
</head>
<body>
<div class="k">{tag} · {region}</div>
<h1>{title}</h1>
<div class="meta">{date} · Michigan Data Center Tracker</div>
<p class="dek">{dek}</p>
{findings}
{perspective}
<div class="src">Original source: <a href="{url}" rel="noopener">{source}</a> — we rewrite every headline in our own words and always link the original.</div>
<a class="home" href="{site}/stories.html">← All stories · Michigan Data Center Tracker</a>
</body>
</html>
"""


def slugify(title: str, iso: str) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:70]
    return f"{iso[:10]}-{s}" if iso else s


def render(story: dict) -> tuple[str, str]:
    title = html.escape(story.get("title", ""))
    dek = html.escape(story.get("dek", ""))
    slug = slugify(story.get("title", ""), story.get("iso", ""))
    findings = ""
    if story.get("findings"):
        items = "".join(f"<li>{html.escape(f.strip())}</li>"
                        for f in str(story["findings"]).split("|") if f.strip())
        findings = f'<div class="sec"><b>From the documents</b><ul>{items}</ul></div>'
    perspective = ""
    if story.get("perspective"):
        perspective = (f'<div class="sec"><b>What happens next</b>'
                       f'<p>{html.escape(str(story["perspective"]))}</p></div>')
    jsonld = json.dumps({
        "@context": "https://schema.org", "@type": "NewsArticle",
        "headline": story.get("title", ""), "description": story.get("dek", "")[:300],
        "datePublished": story.get("iso", ""),
        "publisher": {"@type": "Organization", "name": "Michigan Data Center Tracker"},
        "mainEntityOfPage": f"{SITE}/stories/pages/{slug}.html"}, ensure_ascii=False)
    page = PAGE.format(title=title, desc=dek[:300], slug=slug, site=SITE,
                       tag=html.escape(story.get("tag", "News")),
                       region=html.escape(story.get("region", "Michigan")),
                       date=str(story.get("iso", ""))[:10], dek=dek,
                       findings=findings, perspective=perspective,
                       url=html.escape(story.get("url", "")),
                       source=html.escape(story.get("source", "source")),
                       jsonld=jsonld)
    return slug, page


def main() -> int:
    try:
        live = json.loads(LIVE.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        print(f"::error::no live-data.json: {e}")
        return 1
    national = live.get("national")
    national = national if isinstance(national, list) else ([national] if isinstance(national, dict) else [])
    stories = live.get("stories", []) + national
    OUT.mkdir(parents=True, exist_ok=True)
    urls = []
    for s in stories:
        if not s.get("title"):
            continue
        slug, page = render(s)
        (OUT / f"{slug}.html").write_text(page, encoding="utf-8")
        urls.append((f"{SITE}/stories/pages/{slug}.html", str(s.get("iso", ""))[:10]))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    entries = "\n".join(
        f"  <url><loc>{html.escape(u)}</loc><lastmod>{d or now}</lastmod></url>"
        for u, d in urls)
    SITEMAP.write_text(
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n</urlset>\n", encoding="utf-8")
    print(f"Story pages: {len(urls)} static snapshots + sitemap-stories.xml")
    return 0


if __name__ == "__main__":
    sys.exit(main())
