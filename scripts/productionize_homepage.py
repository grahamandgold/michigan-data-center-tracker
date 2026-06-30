#!/usr/bin/env python3
"""Strip prototype chrome from homepage HTML and make it responsive."""

from __future__ import annotations

import json
import re
from pathlib import Path

RESPONSIVE_CSS = """
  a { color: inherit; }
  .site-header { display:flex; align-items:center; justify-content:space-between; height:96px; padding:0 44px; background:#16140f; border-bottom:1px solid #221f1b; position:sticky; top:0; z-index:50; }
  .lockup { font-size:40px !important; }
  .lockup .mark { height:1.55em !important; width:auto !important; }
  .lockup .sub { font-size:.36em !important; letter-spacing:.24em !important; }
  .desktop-nav { display:flex; align-items:center; gap:28px; font-size:13px; font-weight:600; letter-spacing:.05em; text-transform:uppercase; white-space:nowrap; }
  .hamburger { display:none; flex-direction:column; gap:5px; width:28px; height:44px; justify-content:center; background:none; border:none; cursor:pointer; padding:0; }
  .hamburger span { height:2px; background:#cbc7c3; border-radius:0; }
  .navlink { font-size:14px; }
  .hero-section { display:flex; gap:48px; }
  .hero-copy h2 { font-size:clamp(28px, 5vw, 42px) !important; }
  .wire-grid { display:grid; grid-template-columns:1.05fr 1fr; }
  .tile-grid { display:grid; grid-template-columns:repeat(4, 1fr); gap:16px; }
  .stats-grid { display:grid; grid-template-columns:repeat(3, 1fr); gap:16px; }
  .sponsor-block { display:flex; gap:44px; }
  .signup-row { display:flex; align-items:center; justify-content:space-between; gap:36px; }
  .deck-actions { display:flex; gap:8px; flex-shrink:0; }
  .deck-meta { display:flex; align-items:center; gap:16px; }
  .pod-inner { display:flex; align-items:center; justify-content:center; gap:20px; }
  .pod-wave { flex-shrink:0; display:flex; align-items:flex-end; gap:3px; height:30px; width:200px; overflow:hidden; }
  @media (max-width: 1100px) {
    .tile-grid { grid-template-columns:repeat(2, 1fr); }
    .stats-grid { grid-template-columns:1fr; }
    .sponsor-block { flex-direction:column; }
  }
  @media (max-width: 900px) {
    .wire-grid { grid-template-columns:1fr; }
    .wire-grid .wire-row { border-right:none !important; }
    .signup-row { flex-direction:column; align-items:stretch !important; }
    .signup-row > div:last-child { width:100% !important; }
    .pod-wave { display:none; }
    .deck-row .deck-actions { display:none; }
  }
  @media (max-width: 860px) {
    .desktop-nav { display:none !important; }
    .hamburger { display:flex !important; }
    .site-header { height:68px; padding:0 20px !important; }
    .lockup { font-size:28px !important; }
    .hero-section { flex-direction:column !important; padding:22px 20px 18px !important; gap:24px !important; }
    .hero-map-wrap { min-height:280px !important; }
    .section-pad { padding-left:20px !important; padding-right:20px !important; }
    .section-pad-lg { padding-left:20px !important; padding-right:20px !important; }
    .inset-pad { margin-left:20px !important; margin-right:20px !important; }
    .hero-cta-row { flex-direction:column !important; }
    .hero-cta-row a { text-align:center; }
    .sponsor-strip { flex-wrap:wrap; gap:12px !important; }
    .sponsor-strip .logo-row { display:none; }
    .closing-cta { flex-direction:column !important; align-items:flex-start !important; }
    .footer-cols { flex-direction:column !important; gap:28px !important; }
    .deck-row { flex-wrap:wrap; gap:10px !important; }
    .deck-row .deck-body { white-space:normal !important; }
    .pod-inner { flex-wrap:wrap; justify-content:flex-start !important; padding:11px 20px !important; gap:12px !important; }
    .ticker-hide-label { display:none; }
  }
  @media (max-width: 600px) {
    .tile-grid { grid-template-columns:1fr; }
    .hero-stats { flex-direction:column; }
    .hero-stats > div { border-right:none !important; border-bottom:1px solid #221f1b; }
    .hero-stats > div:last-child { border-bottom:none; }
  }
"""

MOBILE_MENU = """
  <sc-if value="{{ menuOpen }}" hint-placeholder-val="{{ false }}">
    <div style="position:fixed;inset:0;z-index:60;background:rgba(12,11,10,.97);padding:24px 20px;display:flex;flex-direction:column;">
      <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:36px;">
        <span class="lockup" style="font-size:26px;"><img class="mark" src="assets/mark.svg" alt="Michigan Data Center Tracker logo" /><span class="divider"></span><span class="words"><span class="mi">MICHIGAN</span><span class="rule"></span><span class="sub">DATA CENTER TRACKER</span></span></span>
        <button onClick="{{ toggleMenu }}" aria-label="Close" style="background:none;border:none;color:#cbc7c3;font-size:30px;cursor:pointer;line-height:1;">×</button>
      </div>
      <nav style="display:flex;flex-direction:column;gap:4px;">
        <a href="index.html" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#f4f1ee;font-family:'Saira Condensed',sans-serif;font-weight:700;font-size:30px;padding:13px 0;border-bottom:1px solid #1a1813;">Home</a>
        <a href="map/" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#cbc7c3;font-family:'Saira Condensed',sans-serif;font-weight:700;font-size:30px;padding:13px 0;border-bottom:1px solid #1a1813;">Live Map</a>
        <a href="stories.html" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#cbc7c3;font-family:'Saira Condensed',sans-serif;font-weight:700;font-size:30px;padding:13px 0;border-bottom:1px solid #1a1813;">Stories</a>
        <a href="meetings.html" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#cbc7c3;font-family:'Saira Condensed',sans-serif;font-weight:700;font-size:30px;padding:13px 0;border-bottom:1px solid #1a1813;">Meetings</a>
        <a href="learn.html" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#cbc7c3;font-family:'Saira Condensed',sans-serif;font-weight:700;font-size:30px;padding:13px 0;border-bottom:1px solid #1a1813;">Learn</a>
        <a href="sponsor.html" onClick="{{ toggleMenu }}" style="text-decoration:none;color:#100f0e;background:#E03131;font-weight:700;text-align:center;font-size:16px;text-transform:uppercase;letter-spacing:.04em;padding:15px;border-radius:0;margin-top:20px;">Sponsor the tracker</a>
        <a href="https://publicmeetingtracker.com" target="_blank" rel="noopener" style="text-decoration:none;color:#9b9794;font-family:'Space Mono',monospace;font-weight:700;font-size:12px;letter-spacing:.1em;text-transform:uppercase;text-align:center;padding:16px 0 0;">Powered by PublicMeetingTracker.com ↗</a>
      </nav>
    </div>
  </sc-if>
"""

RESPONSIVE_HEADER = """
    <header class="site-header">
      <div style="display:flex;flex-direction:column;gap:8px;align-items:flex-start;">
        <a class="lockup" href="index.html" style="font-size:40px;text-decoration:none;"><img class="mark" src="assets/mark.svg" alt="Michigan Data Center Tracker logo" /><span class="divider"></span><span class="words"><span class="mi">MICHIGAN</span><span class="rule"></span><span class="sub">DATA CENTER TRACKER</span></span></a>
        <a href="https://publicmeetingtracker.com" target="_blank" rel="noopener" style="font-family:'Space Mono',monospace;font-size:9px;font-weight:500;letter-spacing:.24em;text-transform:uppercase;color:#56524e;text-decoration:none;" onmouseover="this.style.color='#8c8884'" onmouseout="this.style.color='#56524e'">Powered by PublicMeetingTracker.com</a>
      </div>
      <nav class="desktop-nav">
        <a class="navlink is-active" href="index.html">Home</a>
        <a class="navlink" href="map/">Live Map</a>
        <a class="navlink" href="stories.html">Stories</a>
        <a class="navlink" href="meetings.html">Meetings</a>
        <a class="navlink" href="learn.html">Learn</a>
        <a class="cta" href="sponsor.html" style="text-decoration:none;color:#100f0e;background:#E03131;font-weight:700;padding:11px 19px;border-radius:0;letter-spacing:.04em;">Sponsor</a>
      </nav>
      <button class="hamburger" onClick="{{ toggleMenu }}" aria-label="Menu"><span></span><span></span><span></span></button>
    </header>
"""


def productionize_homepage(html: str) -> str:
    """Return homepage markup with prototype chrome removed and responsive layout."""
    html = html.replace("padding:48px 32px 80px", "padding:0")

    # Prototype title block
    html = re.sub(
        r'\s*<div style="max-width:1240px;margin:0 auto 36px;">\s*'
        r'<div[^>]*>Turn 4[^<]*</div>\s*'
        r'<h1[^>]*>Michigan Data Center Tracker — homepage</h1>\s*'
        r'<p[^>]*>Stronger data viz.*?</p>\s*</div>\s*',
        "\n",
        html,
        flags=re.S,
    )

    # Desktop mockup wrapper + fake browser chrome
    html = re.sub(
        r'\s*<!-- =+ DESKTOP =+ -->\s*'
        r'<div id="4a"[^>]*>\s*'
        r'<div style="min-width:1180px;">\s*'
        r'<div style="display:flex;align-items:center;gap:7px;height:36px;[^"]*">.*?</div>\s*',
        "\n",
        html,
        flags=re.S,
    )

    # Mobile mockup section (entire second frame)
    html = re.sub(
        r'\s*<!-- =+ MOBILE =+ -->.*?(?=\n</div>\s*</x-dc>)',
        "\n",
        html,
        flags=re.S,
    )

    # Extra closing divs left from desktop wrapper
    html = re.sub(
        r'</footer>\s*</div>\s*</div>\s*(?=</div>\s*</x-dc>)',
        "</footer>\n",
        html,
        flags=re.S,
    )

    # Responsive CSS in helmet
    if ".site-header" not in html:
        html = html.replace("</style>", RESPONSIVE_CSS + "\n</style>", 1)

    # Replace desktop-only header
    html = re.sub(
        r'<header style="display:flex;align-items:center;justify-content:space-between;min-height:80px;[^"]*"[^>]*>.*?</header>',
        RESPONSIVE_HEADER.strip(),
        html,
        count=1,
        flags=re.S,
    )

    # Mobile nav overlay after header
    if "toggleMenu }}" not in html.split("</header>", 1)[-1][:2000]:
        html = html.replace(
            "</header>",
            "</header>\n" + MOBILE_MENU.strip(),
            1,
        )

    # Section class hooks for responsive CSS
    html = html.replace(
        '<section style="display:flex;gap:48px;padding:26px 44px 18px;',
        '<section class="hero-section section-pad" style="display:flex;gap:48px;padding:26px 44px 18px;',
    )
    html = html.replace(
        '<div style="position:relative;z-index:1;flex:1 1 52%;min-width:0;display:flex;flex-direction:column;justify-content:center;">',
        '<div class="hero-copy" style="position:relative;z-index:1;flex:1 1 52%;min-width:0;display:flex;flex-direction:column;justify-content:center;">',
    )
    html = html.replace(
        '<div style="display:flex;gap:12px;margin-bottom:24px;">',
        '<div class="hero-cta-row" style="display:flex;gap:12px;margin-bottom:24px;">',
        1,
    )
    html = html.replace(
        '<div style="display:flex;align-items:stretch;border:1px solid #221f1b;',
        '<div class="hero-stats" style="display:flex;align-items:stretch;border:1px solid #221f1b;',
        1,
    )
    html = html.replace(
        'id="hero-map-d"',
        'id="hero-map"',
    )
    html = html.replace(
        '<div style="position:relative;z-index:1;flex:1 1 48%;min-width:0;border:1px solid #2b2824;border-radius:0;overflow:hidden;min-height:400px;background:#13110d;">',
        '<div class="hero-map-wrap" style="position:relative;z-index:1;flex:1 1 48%;min-width:0;border:1px solid #2b2824;border-radius:0;overflow:hidden;min-height:400px;background:#13110d;">',
    )
    html = html.replace(
        '<div style="display:flex;align-items:center;justify-content:space-between;gap:36px;margin:0 44px 8px;padding:22px 28px;',
        '<div class="signup-row inset-pad" style="display:flex;align-items:center;justify-content:space-between;gap:36px;margin:0 44px 8px;padding:22px 28px;',
    )
    html = html.replace(
        '<div style="display:flex;align-items:center;gap:24px;margin:0 44px 8px;padding:18px 24px;',
        '<div class="sponsor-strip inset-pad" style="display:flex;align-items:center;gap:24px;margin:0 44px 8px;padding:18px 24px;',
    )
    html = html.replace(
        '<div style="display:flex;align-items:center;gap:14px;flex:1;">',
        '<div class="logo-row" style="display:flex;align-items:center;gap:14px;flex:1;">',
        1,
    )
    html = re.sub(
        r'(<section style="padding:18px 44px)',
        r'<section class="section-pad" style="padding:18px 44px',
        html,
    )
    html = re.sub(
        r'(<section style="padding:16px 44px)',
        r'<section class="section-pad" style="padding:16px 44px',
        html,
    )
    html = html.replace(
        '<div style="display:grid;grid-template-columns:1.05fr 1fr;border:1px solid #262320;">',
        '<div class="wire-grid" style="display:grid;grid-template-columns:1.05fr 1fr;border:1px solid #262320;">',
    )
    html = html.replace(
        '<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;">',
        '<div class="tile-grid" style="display:grid;grid-template-columns:repeat(4,1fr);gap:16px;">',
    )
    html = html.replace(
        '<div style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">',
        '<div class="stats-grid" style="display:grid;grid-template-columns:repeat(3,1fr);gap:16px;">',
    )
    html = html.replace(
        '<section style="margin:30px 44px 4px;border:1px solid #2b2824;border-radius:0;overflow:hidden;background:radial-gradient(130% 150% at 100% 0%, #241f18 0%, #16140f 55%);display:flex;gap:44px;padding:44px 40px;">',
        '<section class="sponsor-block section-pad-lg" style="margin:30px 44px 4px;border:1px solid #2b2824;border-radius:0;overflow:hidden;background:radial-gradient(130% 150% at 100% 0%, #241f18 0%, #16140f 55%);display:flex;gap:44px;padding:44px 40px;">',
    )
    html = html.replace(
        '<section style="margin:20px 44px 0;border:1px solid #E03131;',
        '<section class="closing-cta inset-pad" style="margin:20px 44px 0;border:1px solid #E03131;',
    )
    html = html.replace(
        '<div style="display:flex;gap:56px;">',
        '<div class="footer-cols" style="display:flex;gap:56px;">',
    )
    html = html.replace(
        '<div class="pod {{ podCls }}" style="display:flex;align-items:center;justify-content:center;gap:20px;padding:11px 44px;',
        '<div class="pod {{ podCls }} pod-inner" style="display:flex;align-items:center;justify-content:center;gap:20px;padding:11px 44px;',
    )
    html = html.replace(
        '<div style="flex-shrink:0;display:flex;align-items:flex-end;gap:3px;height:30px;width:200px;overflow:hidden;">',
        '<div class="pod-wave" style="flex-shrink:0;display:flex;align-items:flex-end;gap:3px;height:30px;width:200px;overflow:hidden;">',
        1,
    )
    html = html.replace(
        'class="deck-row" style="display:flex;align-items:center;gap:16px;',
        'class="deck-row" style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;',
    )
    html = html.replace(
        '<span style="flex:1;min-width:0;display:flex;flex-direction:column;gap:1px;">',
        '<span class="deck-body" style="flex:1;min-width:0;display:flex;flex-direction:column;gap:1px;">',
    )
    html = html.replace(
        '<span style="display:flex;gap:8px;flex-shrink:0;"><a class="deck-act"',
        '<span class="deck-actions" style="display:flex;gap:8px;flex-shrink:0;"><a class="deck-act"',
    )

    # Single hero map in script
    html = re.sub(
        r"this\._mapD = build\('hero-map-d'[^;]+;\s*"
        r"this\._mapM = build\('hero-map-m'[^;]+;",
        "build('hero-map', { dragging: false, doubleClickZoom: false, touchZoom: false, keyboard: false }, 6.3);",
        html,
    )
    html = html.replace("hero-map-d", "hero-map")
    html = html.replace("hero-map-m", "hero-map")

    # Don't fetch localhost CMS on the public site (causes CORS noise / errors)
    html = html.replace(
        "cmsBase() { return (typeof window !== 'undefined' && window.MDCT_CMS) || 'http://127.0.0.1:8787'; }",
        "cmsBase() { return (typeof window !== 'undefined' && window.MDCT_CMS) || ''; }",
    )
    html = html.replace(
        "loadCMS() {\n    const base = this.cmsBase();",
        "loadCMS() {\n    const base = this.cmsBase();\n    if (!base) return;",
    )

    return html


def extract_template_from_bundle(bundle_html: str) -> str:
    m = re.search(
        r'<script type="__bundler/template">\s*\n"((?:\\.|[^"\\])*)"\s*\n',
        bundle_html,
        re.DOTALL,
    )
    if not m:
        raise ValueError("Could not find __bundler/template in bundle")
    return json.loads('"' + m.group(1) + '"')


def encode_bundle_template(template: str) -> str:
    """JSON-encode template for embedding in HTML <script> tag.

    The bundler escapes every ``</tag>`` as ``<\\u002Ftag>`` inside the JSON
    string. Re-encoding with only ``</script>`` / ``</style>`` breaks DC render.
    """
    encoded = json.dumps(template, ensure_ascii=True)
    encoded = re.sub(
        r"</([^>]+)>",
        lambda m: "<\\u002F" + m.group(1) + ">",
        encoded,
    )
    return encoded


def inject_template_into_bundle(bundle_html: str, template: str) -> str:
    encoded = encode_bundle_template(template)
    m = re.search(
        r'<script type="__bundler/template">\s*\n"(?:\\.|[^"\\])*"\s*\n',
        bundle_html,
        re.DOTALL,
    )
    if not m:
        raise ValueError("Could not find template block to replace")
    start, end = m.span()
    return bundle_html[:start] + f'<script type="__bundler/template">\n{encoded}\n' + bundle_html[end:]


def productionize_dc_source(dc_html: str) -> str:
    """Apply productionize to a .dc.html source file."""
    open_m = re.search(r"<x-dc>", dc_html)
    close_m = re.search(r"</x-dc>", dc_html)
    if not open_m or not close_m:
        raise ValueError("Not a valid .dc.html file")
    inner = dc_html[open_m.end() : close_m.start()]
    # inner is helmet + div; productionize expects full template body inside x-dc
    inner = productionize_homepage("<x-dc>" + inner + "</x-dc>")
    inner = inner[len("<x-dc>") : -len("</x-dc>")]
    script_m = re.search(r"<script[^>]*data-dc-script[^>]*>.*?</script>", dc_html, re.S)
    script = script_m.group(0) if script_m else ""
    if script:
        script = productionize_homepage(script)
    head = dc_html[: open_m.start()]
    tail = dc_html[close_m.end() :]
    if script_m:
        tail = tail.replace(script_m.group(0), script)
    return head + "<x-dc>" + inner + "</x-dc>" + tail


def productionize_bundle_file(path: Path) -> None:
    raw = path.read_text(encoding="utf-8")
    template = extract_template_from_bundle(raw)
    template = productionize_homepage(template)
    path.write_text(inject_template_into_bundle(raw, template), encoding="utf-8")


if __name__ == "__main__":
    import sys

    target = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    if target and target.suffix == ".html":
        if "__bundler/template" in target.read_text(encoding="utf-8"):
            productionize_bundle_file(target)
            print(f"Productionized bundle: {target}")
        else:
            text = target.read_text(encoding="utf-8")
            target.write_text(productionize_dc_source(text), encoding="utf-8")
            print(f"Productionized source: {target}")
    else:
        print("Usage: productionize_homepage.py <homepage.html|Homepage.dc.html>")