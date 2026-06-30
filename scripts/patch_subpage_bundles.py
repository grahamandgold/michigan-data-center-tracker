#!/usr/bin/env python3
"""Rebuild stories/meetings/learn/sponsor bundles from handoff .dc.html sources."""

from __future__ import annotations

import json
import re
from pathlib import Path

from patch_bundle_template import decompress_manifest, encode_like_bundler
from theme_assets import inject_theme_shell, inject_theme_template, template_from_dc

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "handoff"

LINK_REPLACEMENTS = [
    ("Homepage.dc.html", "index.html"),
    ("Live Map.dc.html", "map/"),
    ("Stories.dc.html", "stories.html"),
    ("Meetings.dc.html", "meetings.html"),
    ("Learn.dc.html", "learn.html"),
    ("Sponsor.dc.html", "sponsor.html"),
]

SUBPAGES = {
    "Stories.dc.html": ROOT / "stories.html",
    "Meetings.dc.html": ROOT / "meetings.html",
    "Learn.dc.html": ROOT / "learn.html",
    "Sponsor.dc.html": ROOT / "sponsor.html",
}


def patch_subpage_template(tpl: str) -> str:
    for old, new in LINK_REPLACEMENTS:
        tpl = tpl.replace(old, new)
    return inject_theme_template(tpl)


def patch_subpage_html(html: str, dc_name: str) -> str:
    dc = (HANDOFF / dc_name).read_text(encoding="utf-8")
    template = patch_subpage_template(template_from_dc(dc))
    m = re.search(
        r"(<script type=\"__bundler/template\">\s*\n)(.+?)(\n\s*</script>)",
        html,
        re.DOTALL,
    )
    if not m:
        raise ValueError(f"template block not found in {dc_name}")
    encoded = encode_like_bundler(template)
    html = html[: m.start()] + m.group(1) + encoded + m.group(3) + html[m.end() :]
    html = decompress_manifest(html)
    html = inject_theme_shell(html)
    return html


def main() -> None:
    for dc_name, dest in SUBPAGES.items():
        html = dest.read_text(encoding="utf-8")
        dest.write_text(patch_subpage_html(html, dc_name), encoding="utf-8")
        print(f"Patched {dest.relative_to(ROOT)} from handoff/{dc_name}")


if __name__ == "__main__":
    main()