#!/usr/bin/env python3
"""Daily Briefing newsletter builder.

Fills the email template below from live-data.json (top 3 headlines), the
map data stats, and upcoming meetings — then writes newsletter-latest.html.
Paste the file's source into a Mailchimp campaign (or automate it later).

Run:  python scripts/newsletter_build.py

Modules (each a self-contained <table>, easy to reorder/delete):
  HEADER · LEAD STORY · HEADLINES · STATS · MAP · ON DECK · PODCAST · FOOTER
Email-safe: 600px tables, inline styles, system fonts, no scripts.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SITE = "https://grahamandgold.github.io/mi-data-center-tracker/"

live = json.loads((ROOT / "live-data.json").read_text(encoding="utf-8"))
stories = live.get("stories", [])
meetings = live.get("meetings", [])[:4]
mapd = json.loads((ROOT / "map-data.json").read_text(encoding="utf-8"))
prj = [p for p in mapd["map_points"] if p.get("layer") == "projects"]
mor = [p for p in mapd["map_points"] if p.get("layer") == "moratoria"]
mw = sum(float(str(p.get("power_mw") or "0").replace(",", "")) for p in prj)
gw = f"{mw/1000:.1f}"
homes = f"{round(mw*800/100000)/10} million" if mw >= 1250 else f"{round(mw*800/1000)},000"

today_iso = datetime.now(timezone.utc).strftime("%Y-%m-%d")
todays = [m for m in meetings if m.get("iso") == today_iso]
ahead = [m for m in meetings if m.get("iso", "") > today_iso][:4]

national = live.get("national")
lead = next((s for s in stories if s.get("lead")), stories[0] if stories else None)
others = [s for s in stories if s is not lead][:3]
today = datetime.now(timezone.utc).strftime("%A, %B %-d, %Y")

def esc(t):
    return str(t or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

def headline_row(s):
    return f"""
  <tr><td style="padding:0 28px 20px;">
    <div style="border-left:3px solid #E03131;padding-left:14px;">
      <div style="font:700 11px/1.4 'Courier New',monospace;letter-spacing:2px;color:#E03131;text-transform:uppercase;padding-bottom:4px;">{esc(s.get('cat','') )}</div>
      <a href="{esc(s.get('url'))}" style="font:800 19px/1.25 Arial,Helvetica,sans-serif;color:#f4f1ee;text-decoration:none;">{esc(s.get('title'))}</a>
      <div style="font:400 13px/1.5 Arial,Helvetica,sans-serif;color:#a39e99;padding-top:6px;">{esc(s.get('dek',''))[:180]}</div>
      <div style="font:700 11px/1.4 'Courier New',monospace;color:#c9a24b;padding-top:6px;">Source: {esc(s.get('source'))} →</div>
    </div>
  </td></tr>"""


def today_row(m):
    return ("<tr><td style=\"padding:14px 28px 0;\">"
        "<a href=\"" + esc(m.get('link', SITE + 'meetings.html')) + "\" style=\"text-decoration:none;display:block;background:#16140f;border:1px solid #4a4226;border-left:3px solid #c9a24b;padding:14px 18px;\">"
        "<span style=\"font:800 15px/1.4 Arial,sans-serif;color:#f4f1ee;\">" + esc(m.get('body')) + "</span>"
        "<span style=\"font:800 13px/1.4 Arial,sans-serif;color:#c9a24b;\">&nbsp;&#183; " + esc(m.get('time', '')) + "</span>"
        "<div style=\"font:400 12px/1.5 Arial,sans-serif;color:#a39e99;padding-top:3px;\">" + esc(m.get('topic', ''))[:120] + " &#183; <span style=\"color:#c9a24b;\">Agenda &#8594;</span></div>"
        "</a></td></tr>")

if todays:
    TODAY_BLOCK = "".join(today_row(m) for m in todays)
else:
    nxt = ""
    if ahead:
        nxt = (" &#8212; next up: <span style=\"color:#f4f1ee;font-weight:700\">" + esc(ahead[0].get('body'))
               + "</span> on " + esc(ahead[0].get('iso', '')[5:].replace('-', '/')))
    TODAY_BLOCK = ("<tr><td style=\"padding:14px 28px 0;\"><div style=\"background:#16140f;border:1px dashed #322e29;"
        "padding:14px 18px;font:400 13px/1.5 Arial,sans-serif;color:#a39e99;\">No data center hearings on today's calendars"
        + nxt + ". We're watching.</div></td></tr>")

NATIONAL_BLOCK = ""
if national:
    NATIONAL_BLOCK = ("<tr><td style=\"padding:0 28px 24px;\">"
        "<div style=\"font:700 10px/1 'Courier New',monospace;letter-spacing:3px;color:#100f0e;background:#7c9cc4;display:inline-block;padding:5px 10px;\">THE NATIONAL PICTURE</div>"
        "<a href=\"" + esc(national.get('url')) + "\" style=\"display:block;font:800 20px/1.25 Arial,sans-serif;color:#f4f1ee;text-decoration:none;padding-top:10px;\">" + esc(national.get('title')) + "</a>"
        "<div style=\"font:400 13px/1.5 Arial,sans-serif;color:#a39e99;padding-top:6px;\">" + esc(national.get('dek', ''))[:200] + "</div>"
        "<div style=\"font:700 11px/1 'Courier New',monospace;color:#c9a24b;padding-top:8px;\">Source: " + esc(national.get('source')) + " &#8594;</div>"
        "</td></tr>")

html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Data Center Intelligence Report</title></head>
<body style="margin:0;padding:0;background:#0c0b0a;">
<center>
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="width:600px;max-width:100%;background:#100f0e;">

  <!-- ============ MODULE: HEADER ============ -->
  <tr><td style="padding:26px 28px 18px;border-bottom:2px solid #E03131;">
    <div style="font:900 26px/1 Arial Black,Arial,sans-serif;color:#f4f1ee;letter-spacing:1px;">MICHIGAN</div>
    <div style="font:700 11px/1.6 Arial,sans-serif;color:#f4f1ee;letter-spacing:4px;">DATA CENTER TRACKER</div>
    <div style="font:400 11px/2 'Courier New',monospace;color:#7d7975;">DATA CENTER INTELLIGENCE REPORT · {today} · Powered by Graham &amp; Gold</div>
  </td></tr>

  <!-- ============ MODULE: HAPPENING TODAY (7am forward focus) ============ -->
  <tr><td style="padding:24px 28px 4px;">
    <div style="font:700 10px/1 'Courier New',monospace;letter-spacing:3px;color:#100f0e;background:#c9a24b;display:inline-block;padding:5px 10px;">HAPPENING TODAY</div>
  </td></tr>
  {TODAY_BLOCK}

  <!-- ============ MODULE: LEAD STORY ============ -->
  <tr><td style="padding:26px 28px 22px;">
    <div style="font:700 10px/1 'Courier New',monospace;letter-spacing:3px;color:#100f0e;background:#E03131;display:inline-block;padding:5px 10px;">THE STORY DRIVING THE DAY</div>
    <a href="{esc(lead.get('url') if lead else SITE)}" style="display:block;font:800 26px/1.2 Arial,Helvetica,sans-serif;color:#f4f1ee;text-decoration:none;padding-top:12px;">{esc(lead.get('title') if lead else 'Visit the tracker for today’s wire')}</a>
    <div style="font:400 14px/1.55 Arial,Helvetica,sans-serif;color:#a39e99;padding-top:10px;">{esc(lead.get('dek','') if lead else '')}</div>
    <div style="font:700 12px/1 'Courier New',monospace;color:#c9a24b;padding-top:10px;">Source: {esc(lead.get('source') if lead else '')} →</div>
  </td></tr>

  <!-- ============ MODULE: HEADLINES ============ -->
  <tr><td style="padding:0 28px 6px;"><div style="font:700 12px/1 'Courier New',monospace;letter-spacing:3px;color:#7d7975;border-bottom:1px solid #262320;padding-bottom:8px;margin-bottom:18px;">ALSO ON THE WIRE</div></td></tr>
  {''.join(headline_row(s) for s in others)}

  <!-- ============ MODULE: NATIONAL ============ -->
  {NATIONAL_BLOCK}

  <!-- ============ MODULE: STATS ============ -->
  <tr><td style="padding:6px 28px 24px;">
    <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
      <td width="33%" style="background:#16140f;border:1px solid #262320;padding:16px 6px;text-align:center;">
        <div style="font:800 26px/1 Arial,sans-serif;color:#f4f1ee;">{len(prj)}</div>
        <div style="font:400 10px/1.6 'Courier New',monospace;color:#7d7975;">TRACKED<br>PROJECTS</div></td>
      <td width="8"></td>
      <td width="33%" style="background:#16140f;border:1px solid #262320;padding:16px 6px;text-align:center;">
        <div style="font:800 26px/1 Arial,sans-serif;color:#E03131;">{gw} GW</div>
        <div style="font:400 10px/1.6 'Courier New',monospace;color:#7d7975;">&#8776; {homes} HOMES'<br>WORTH OF POWER</div></td>
      <td width="8"></td>
      <td width="33%" style="background:#16140f;border:1px solid #262320;padding:16px 6px;text-align:center;">
        <div style="font:800 26px/1 Arial,sans-serif;color:#7c9cc4;">{len(mor)}</div>
        <div style="font:400 10px/1.6 'Courier New',monospace;color:#7d7975;">COMMUNITIES<br>ON PAUSE</div></td>
    </tr></table>
  </td></tr>

  <!-- ============ MODULE: MAP ============ -->
  <tr><td style="padding:0 28px 24px;">
    <a href="{SITE}map/" style="display:block;background:#16140f;border:1px solid #E03131;text-decoration:none;padding:22px 24px;">
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0"><tr>
        <td><div style="font:700 10px/1 'Courier New',monospace;letter-spacing:3px;color:#E03131;">&#9679; LIVE MAP</div>
        <div style="font:800 20px/1.25 Arial,sans-serif;color:#f4f1ee;padding-top:8px;">Every project, permit &amp; pause — mapped &amp; sourced</div>
        <div style="font:400 12px/1.5 Arial,sans-serif;color:#a39e99;padding-top:6px;">{len(prj)+len(mor)} records live right now. Find what's near you.</div></td>
        <td width="64" align="center" style="background:#E03131;"><div style="font:800 30px/64px Arial,sans-serif;color:#100f0e;">&#8594;</div></td>
      </tr></table>
    </a>
  </td></tr>

  <!-- ============ MODULE: ON DECK ============ -->
  <tr><td style="padding:0 28px 8px;"><div style="font:700 12px/1 'Courier New',monospace;letter-spacing:3px;color:#7d7975;border-bottom:1px solid #262320;padding-bottom:8px;">AHEAD THIS WEEK · SHOW UP &amp; SPEAK</div></td></tr>
  {''.join(f'''<tr><td style="padding:14px 28px 0;">
    <a href="{esc(m.get('link', SITE + 'meetings.html'))}" style="text-decoration:none;display:block;">
      <span style="font:800 13px/1 Arial,sans-serif;color:#E03131;">{esc((m.get('iso') or '')[5:].replace('-', '/'))}</span>
      <span style="font:800 14px/1.4 Arial,sans-serif;color:#f4f1ee;">&nbsp; {esc(m.get('body'))}</span>
      <div style="font:400 12px/1.5 Arial,sans-serif;color:#a39e99;padding:2px 0 10px;">{esc(m.get('topic',''))[:110]} · {esc(m.get('time',''))} · <span style="color:#c9a24b;">Agenda →</span></div>
    </a></td></tr>''' for m in ahead)}

  <!-- ============ MODULE: PODCAST ============ -->
  <tr><td style="padding:18px 28px 26px;">
    <a href="{SITE}" style="display:block;background:linear-gradient(90deg,#1d0f0c,#16140f);border:1px solid #262320;text-decoration:none;padding:16px 20px;">
      <span style="font:800 22px/1 Arial,sans-serif;color:#100f0e;background:#E03131;padding:8px 13px;">&#9654;</span>
      <span style="font:800 15px/1 Arial,sans-serif;color:#f4f1ee;">&nbsp; MORNINGS WITH GRAHAM &amp; EMMY</span>
      <span style="font:400 11px/1 'Courier New',monospace;color:#8c8884;">&nbsp; the Michigan Data Wire podcast · new episode every morning · tap to listen</span>
    </a>
  </td></tr>

  <!-- ============ MODULE: FOOTER ============ -->
  <tr><td style="padding:20px 28px 30px;background:#0c0b0a;border-top:1px solid #221f1b;">
    <div style="font:400 11px/1.7 'Courier New',monospace;color:#7d7975;">INDEPENDENT · NONPARTISAN · A transparent aggregator — every headline in our own words, always linked to the source.</div>
    <div style="font:400 11px/2 Arial,sans-serif;color:#5f5b57;">Powered by <a href="https://grahamandgold.com" style="color:#E03131;text-decoration:none;">Graham &amp; Gold</a> · <a href="{SITE}" style="color:#8c8884;">midatacentertracker</a> · <a href="*|UNSUB|*" style="color:#8c8884;">Unsubscribe</a></div>
  </td></tr>

</table>
</center>
</body></html>"""

out = ROOT / "newsletter-latest.html"
out.write_text(html, encoding="utf-8")
print(f"Wrote {out.name}: lead + {len(others)} headlines, {len(meetings)} meetings, stats {len(prj)}/{gw}GW/{len(mor)}")
