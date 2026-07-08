#!/usr/bin/env python3
"""Visual polish pass: richer Wire lead, legible county chips, scannable
story cards, minute timestamps, live-data hot-reload hooks."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

def must(src, old, new, n=1, label=""):
    assert old in src, "MISSING (" + label + "): " + old[:90]
    return src.replace(old, new, n)

# ================= HOMEPAGE =================
p = ROOT / "handoff" / "Homepage.dc.html"
s = p.read_text(encoding="utf-8")

# lead card: stop vertical-centering into a void; add texture
s = must(s,
  ".wire-lead { display:flex; flex-direction:column; justify-content:center; border-right:1px solid #262320; border-left:3px solid #E03131; background:#16140f; padding:28px 26px; min-height:100%; }",
  ".wire-lead { display:flex; flex-direction:column; justify-content:center; border-right:1px solid #262320; border-left:3px solid #E03131; background:radial-gradient(140% 130% at 0% 0%, #201a15 0%, #16140f 58%); padding:26px 26px 24px; min-height:100%; position:relative; overflow:hidden; }\n"
  "  .wire-lead::after { content:\"\"; position:absolute; right:-70px; bottom:-70px; width:230px; height:230px; border-radius:50%; border:26px solid rgba(224,49,49,.05); pointer-events:none; }\n"
  "  .wire-lead-dek { margin:0 0 16px; color:#a39e99; font-size:14.5px; line-height:1.6; max-width:520px; }\n"
  "  .wire-lead-hl-link { text-decoration:none; display:block; }\n"
  "  .wire-lead-hl-link:hover .wire-lead-hl { color:#fff; }\n"
  "  .wire-lead-foot { display:flex; align-items:center; justify-content:space-between; gap:14px; flex-wrap:wrap; margin-top:2px; }\n"
  "  .wire-lead-cta { display:inline-block; font-family:'Space Mono',monospace; font-size:11px; font-weight:700; letter-spacing:.08em; text-transform:uppercase; color:#f4f1ee; background:#E03131; padding:9px 15px; text-decoration:none; transition:background .15s ease, transform .15s ease; }\n"
  "  .wire-lead-cta:hover { background:#f24343; transform:translateY(-1px); }",
  label="wire-lead css")

# county tag in the wire list: readable chip instead of 9px dim caps
s = must(s,
  ".wire-src-cat { color:#5f5b57; font-size:9px; letter-spacing:.06em; text-transform:uppercase; }",
  ".wire-src-cat { color:#c3beb9; font-size:10px; letter-spacing:.07em; text-transform:uppercase; background:#221f1b; border:1px solid #35312b; padding:2px 7px; white-space:nowrap; }",
  label="wire-src-cat chip")

# lead template: linked headline + dek + footer with CTA
s = must(s,
  '<h4 class="wire-hl wire-lead-hl">{{ lead.title }}</h4>\n          <div class="wire-src-line">\n            <span class="wire-src-label">Source:</span>\n            <a class="wire-src-link {{ lead.sourceKind }}" href="{{ lead.url }}" target="_blank" rel="noopener noreferrer">{{ lead.source }}</a><span class="wire-src-arrow"> →</span>\n          </div>',
  '<a class="wire-lead-hl-link" href="{{ lead.url }}" target="_blank" rel="noopener noreferrer"><h4 class="wire-hl wire-lead-hl">{{ lead.title }}</h4></a>\n          <p class="wire-lead-dek">{{ lead.dek }}</p>\n          <div class="wire-lead-foot">\n            <div class="wire-src-line">\n              <span class="wire-src-label">Source:</span>\n              <a class="wire-src-link {{ lead.sourceKind }}" href="{{ lead.url }}" target="_blank" rel="noopener noreferrer">{{ lead.source }}</a><span class="wire-src-arrow"> →</span>\n            </div>\n            <a class="wire-lead-cta" href="{{ lead.url }}" target="_blank" rel="noopener noreferrer">Read the story →</a>\n          </div>',
  label="lead markup")

# county tag color on the lead pill: brighter default
s = must(s, "catColor: CAT[w.cat] || '#9b9794',", "catColor: CAT[w.cat] || '#cbc7c3',", label="catColor")

# hot-reload the live feed
s = must(s, "  componentDidMount() {",
  "  componentDidMount() {\n    try { if (window.MDCT && window.MDCT.loadLive) window.MDCT.loadLive(() => { if (!this._dead) this.setState({ liveTick: Date.now() }); }); } catch (e) {}",
  label="home loadLive")
p.write_text(s, encoding="utf-8")
print("Homepage polished")

# ================= STORIES =================
p = ROOT / "handoff" / "Stories.dc.html"
s = p.read_text(encoding="utf-8")

# CSS: clamp deks, county chips, colored category rules, tighter lead
s = must(s,
  "  .hot-dek { margin:0; color:#8c8884; font-size:14px; line-height:1.55; flex:1; }",
  "  .hot-dek { margin:0; color:#98938e; font-size:13.5px; line-height:1.55; flex:1; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }",
  label="hot-dek clamp")
s = must(s,
  "  .text-card-dek { margin:0 0 16px; color:#8c8884; font-size:14px; line-height:1.55; flex:1; }",
  "  .text-card-dek { margin:0 0 14px; color:#98938e; font-size:13.5px; line-height:1.55; flex:1; display:-webkit-box; -webkit-line-clamp:2; -webkit-box-orient:vertical; overflow:hidden; }\n"
  "  .county-chip { font-family:'Space Mono',monospace; font-size:10px; letter-spacing:.07em; text-transform:uppercase; color:#c3beb9; background:#221f1b; border:1px solid #35312b; padding:2px 7px; white-space:nowrap; }",
  label="text-card-dek clamp + county chip")
s = must(s,
  "  .text-card { padding:22px 22px 24px; }",
  "  .text-card { padding:20px 22px 20px; border-top:2px solid {{}}; }",  # placeholder replaced below
  label="text-card pad")
# (top accent applied inline per-card instead of class-level)
s = s.replace("  .text-card { padding:20px 22px 20px; border-top:2px solid {{}}; }",
              "  .text-card { padding:20px 22px 20px; }")
s = must(s,
  "  .text-card-tag { font-family:'Space Mono',monospace; font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; color:#E03131; }",
  "  .text-card-tag { font-family:'Space Mono',monospace; font-size:10.5px; letter-spacing:.1em; text-transform:uppercase; font-weight:700; }",
  label="tag color unlock")

# text-card markup: colored top rule, colored tag, county chip
s = must(s,
  '<a class="scard text-card" href="{{ s.url }}" target="_blank" rel="noopener">\n          <div class="text-card-meta">\n            <span class="text-card-tag">{{ s.tag }}</span>\n            <span class="text-card-date">{{ s.date }}</span>\n          </div>',
  '<a class="scard text-card" href="{{ s.url }}" target="_blank" rel="noopener" style="border-top:2px solid {{ s.tagColor }};">\n          <div class="text-card-meta">\n            <span class="text-card-tag" style="color:{{ s.tagColor }};">{{ s.tag }}</span>\n            <span class="county-chip">{{ s.cat }}</span>\n            <span class="text-card-date">{{ s.date }}</span>\n          </div>',
  label="text-card markup")

# story grid headline: slightly smaller for density relief
s = must(s,
  '<h3 class="sc-head" style="font-family:\'Saira Condensed\',sans-serif;font-weight:700;font-size:23px;line-height:1.06;margin:0 0 10px;color:#f4f1ee;">{{ s.title }}</h3>',
  '<h3 class="sc-head" style="font-family:\'Saira Condensed\',sans-serif;font-weight:700;font-size:21px;line-height:1.1;margin:0 0 9px;color:#f4f1ee;">{{ s.title }}</h3>',
  label="grid headline size")

# hot card foot: add county chip
s = must(s,
  '<div class="hot-foot">\n              <span class="hot-date">{{ h.date }}</span>',
  '<div class="hot-foot">\n              <span style="display:flex;align-items:center;gap:8px;"><span class="county-chip">{{ h.cat }}</span><span class="hot-date">{{ h.timeAgo }}</span></span>',
  label="hot foot")

# lead card: county chip + relative time + read CTA
s = must(s,
  '<div class="lead-meta">\n          <span style="font-family:\'Space Mono\',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;color:#E03131;">{{ leadStory.tag }}</span>\n          <span style="font-family:\'Space Mono\',monospace;font-size:11px;color:#6f6b67;">{{ leadStory.date }}</span>\n        </div>',
  '<div class="lead-meta">\n          <span style="font-family:\'Space Mono\',monospace;font-size:11px;letter-spacing:.1em;text-transform:uppercase;font-weight:700;color:{{ leadStory.tagColor }};">{{ leadStory.tag }}</span>\n          <span class="county-chip">{{ leadStory.cat }}</span>\n          <span style="font-family:\'Space Mono\',monospace;font-size:11px;color:#8c8884;">{{ leadStory.timeAgo }}</span>\n        </div>',
  label="lead meta")
s = must(s,
  '<span class="source-link {{ leadStory.sourceKind }}">Source ↗ {{ leadStory.source }}</span>\n      </div>\n    </a>',
  '<div style="display:flex;align-items:center;justify-content:space-between;gap:14px;flex-wrap:wrap;">\n          <span class="source-link {{ leadStory.sourceKind }}">Source ↗ {{ leadStory.source }}</span>\n          <span style="font-family:\'Space Mono\',monospace;font-size:11px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:#f4f1ee;background:#E03131;padding:9px 15px;">Read the story →</span>\n        </div>\n      </div>\n    </a>',
  label="lead cta")

# mapStory: expose cat / tagColor / timeAgo
s = must(s,
  "      return {\n        title: h.title,\n        dek: h.dek,\n        tag: h.tag,\n        date: MD.dateLabel ? MD.dateLabel(h.iso) : h.iso,",
  "      return {\n        title: h.title,\n        dek: h.dek,\n        tag: h.tag,\n        cat: h.cat || '',\n        tagColor: (MD.tagColor ? MD.tagColor(h.tag) : '#9b9794'),\n        timeAgo: MD.ago ? MD.ago(h.iso) : '',\n        date: MD.dateLabel ? MD.dateLabel(h.iso) : h.iso,",
  label="mapStory fields")

# hot rail: strictly the last HOT_HOURS window
s = must(s,
  "    const hotStories = headlines\n      .filter((h) => {\n        const rec = MD.recency ? MD.recency(h.iso) : { hot: false };\n        return rec.hot || h.breaking;\n      })\n      .slice(0, 4)",
  "    const hotStories = headlines\n      .filter((h) => {\n        const rec = MD.recency ? MD.recency(h.iso) : { hot: false };\n        return rec.hot;\n      })\n      .slice(0, 4)",
  label="hot window strict")

# hot-reload live feed
s = must(s,
  "  componentDidMount() {\n    const social =",
  "  componentDidMount() {\n    try { if (window.MDCT && window.MDCT.loadLive) window.MDCT.loadLive(() => { if (!this._dead) this.setState({ liveTick: Date.now() }); }); } catch (e) {}\n    const social =",
  label="stories loadLive")
p.write_text(s, encoding="utf-8")
print("Stories polished")

# ================= MEETINGS =================
p = ROOT / "handoff" / "Meetings.dc.html"
s = p.read_text(encoding="utf-8")
# hot-reload live feed
if "componentDidMount() {" in s:
    s = must(s, "  renderVals() {",
      "  componentDidMount() {\n    try { if (window.MDCT && window.MDCT.loadLive) window.MDCT.loadLive(() => { if (!this._dead) this.setState({ liveTick: Date.now() }); }); } catch (e) {}\n  }\n  componentWillUnmount() { this._dead = true; }\n\n  renderVals() {",
      label="meetings loadLive") if "componentDidMount() {" not in s.split("renderVals")[0] else s
else:
    s = must(s, "  renderVals() {",
      "  componentDidMount() {\n    try { if (window.MDCT && window.MDCT.loadLive) window.MDCT.loadLive(() => { if (!this._dead) this.setState({ liveTick: Date.now() }); }); } catch (e) {}\n  }\n  componentWillUnmount() { this._dead = true; }\n\n  renderVals() {",
      label="meetings loadLive")
# county line legibility
s = s.replace("font-size:11px;color:#7d7975;", "font-size:11.5px;color:#a39e99;")
p.write_text(s, encoding="utf-8")
print("Meetings polished")
