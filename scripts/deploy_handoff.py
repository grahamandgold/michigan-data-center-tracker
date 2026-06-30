#!/usr/bin/env python3
"""Deploy Claude handoff dist build into mi-data-center-tracker GitHub Pages repo."""

from __future__ import annotations

import re
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from productionize_homepage import productionize_bundle_file, productionize_dc_source

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = Path("/Users/gillfillan/Downloads/handoff")
DIST = HANDOFF / "dist"
BASE = "/mi-data-center-tracker/"

LINK_REPLACEMENTS = [
    ("Homepage.dc.html", "index.html"),
    ("Live Map.dc.html", "map/"),
    ("Stories.dc.html", "stories.html"),
    ("Meetings.dc.html", "meetings.html"),
    ("Learn.dc.html", "learn.html"),
    ("Sponsor.dc.html", "sponsor.html"),
    # Encoded variants inside bundler JSON
    ("Homepage.dc.html", "index.html"),
]

DEPLOY_MAP = {
    "homepage.html": ROOT / "index.html",
    "live-map.html": ROOT / "map" / "index.html",
    "stories.html": ROOT / "stories.html",
    "meetings.html": ROOT / "meetings.html",
    "learn.html": ROOT / "learn.html",
    "sponsor.html": ROOT / "sponsor.html",
}

# Legacy files replaced by handoff (keep geo/, media, data files)
REMOVE = [
    "app.js",
    "homepage.css",
    "home-map-preview.js",
    "home-map-preview.svg",
    "home-stats.js",
    "content-data.js",
    "map.html",
    "map.js",
    "map-boot.js",
    "map-analytics.js",
    "methodology.html",
]


def patch_html(text: str) -> str:
    for old, new in LINK_REPLACEMENTS:
        text = text.replace(old, new)
    # Bundler escapes slashes in embedded template JSON
    text = text.replace("Live Map.dc.html", "map/")
    if '<base href=' not in text:
        text = re.sub(
            r"(<head[^>]*>)",
            rf'\1\n  <base href="{BASE}">',
            text,
            count=1,
            flags=re.I,
        )
    return text


def main() -> None:
    if not DIST.exists():
        raise SystemExit(f"Handoff dist not found: {DIST}")

    (ROOT / "map").mkdir(exist_ok=True)
    (ROOT / "assets").mkdir(exist_ok=True)
    (ROOT / "handoff").mkdir(exist_ok=True)

    for name, dest in DEPLOY_MAP.items():
        src = DIST / name
        if not src.exists():
            raise SystemExit(f"Missing {src}")
        if name == "homepage.html":
            productionize_bundle_file(src)
        content = patch_html(src.read_text(encoding="utf-8"))
        dest.write_text(content, encoding="utf-8")
        print(f"  wrote {dest.relative_to(ROOT)}")

    mark_src = HANDOFF / "assets" / "mark.svg"
    if mark_src.exists():
        shutil.copy2(mark_src, ROOT / "assets" / "mark.svg")
        print("  wrote assets/mark.svg")

    for item in ("HANDOFF.md", "support.js"):
        p = HANDOFF / item
        if p.exists():
            shutil.copy2(p, ROOT / "handoff" / item)

    for dc in HANDOFF.glob("*.dc.html"):
        dest_dc = ROOT / "handoff" / dc.name
        text = dc.read_text(encoding="utf-8")
        if dc.name == "Homepage.dc.html":
            text = productionize_dc_source(text)
        dest_dc.write_text(text, encoding="utf-8")
        print(f"  wrote handoff/{dc.name}")

    for rel in REMOVE:
        p = ROOT / rel
        if p.exists():
            p.unlink()
            print(f"  removed {rel}")

    def write_redirect(name: str, target: str, title: str) -> None:
        (ROOT / name).write_text(
            f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta http-equiv="refresh" content="0;url={target}">
  <script>location.replace("{target}");</script>
  <link rel="canonical" href="https://midatacentertracker.github.io/mi-data-center-tracker/{target}">
  <title>Redirecting…</title>
</head>
<body><p><a href="{target}">{title}</a></p></body>
</html>
""",
            encoding="utf-8",
        )

    write_redirect("map.html", "map/", "Continue to Live Map")
    write_redirect("sponsorship.html", "sponsor.html", "Continue to Sponsor")
    write_redirect("methodology.html", "learn.html", "Continue to Learn")

    # Site config stub — wire CMS in next phase
    (ROOT / "site-config.js").write_text(
        """// Michigan Data Center Tracker — runtime config
// Set MDCT_CMS when the Public Meeting Tracker desk is wired (next phase).
window.MDCT_CMS = window.MDCT_CMS || '';
""",
        encoding="utf-8",
    )

    print("Deploy complete.")


if __name__ == "__main__":
    main()