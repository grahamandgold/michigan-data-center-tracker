"""Shared theme toggle markup and bundle injection helpers."""

from __future__ import annotations

import json
import re
from pathlib import Path

SITE_BASE = "/mi-data-center-tracker/"
THEME_CSS_LINK = f'<link rel="stylesheet" href="{SITE_BASE}theme.css">'
CONTENT_DATA_SCRIPT = f'<script src="{SITE_BASE}content-data.js"></script>'
EDITORIAL_SCRIPT = f'<script src="{SITE_BASE}mdct-editorial.js"></script>'
MAP_DATA_SCRIPT = f'<script src="{SITE_BASE}map-points-data.js"></script>'

THEME_TOGGLE = (
    '<button type="button" class="mdct-theme-btn" aria-label="Switch to light mode" '
    'aria-pressed="false" title="Switch to light mode">'
    '<span class="mdct-theme-icon" aria-hidden="true">☀</span>'
    '<span class="mdct-theme-label">Light</span></button>'
)

THEME_HEAD_SCRIPTS = f"""<script>
(function(){{try{{var t=localStorage.getItem('mdct-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}}catch(e){{}}}})();
</script>
<script src="{SITE_BASE}theme.js"></script>"""

# support.js manifest UUIDs from the original Claude bundler output (c61b724).
SUPPORT_UUIDS: dict[str, str] = {
    "index.html": "c4a0d3fe-108e-4d84-90c0-bb88b46407d3",
    "stories.html": "67f7b8cf-c0de-435d-87df-07a0b2a5cd93",
    "meetings.html": "7ec0fba9-ff32-42c0-8272-83cceb923d5d",
    "learn.html": "17728b1c-fb28-4efe-af41-877f3597c487",
    "sponsor.html": "3e552ab2-9b60-4e8c-ab88-e5302952439b",
    "map/index.html": "21b03277-2b8b-4977-8e96-07968db4e894",
}


def split_dc_parts(dc_html: str) -> tuple[str, str | None]:
    m = re.search(r"<x-dc>(.*)</x-dc>", dc_html, re.DOTALL)
    if not m:
        raise ValueError("x-dc block not found in .dc.html")
    inner = m.group(1).strip()
    script_m = re.search(
        r"<script[^>]*data-dc-script[^>]*>.*?</script>",
        dc_html,
        re.DOTALL,
    )
    return inner, script_m.group(0) if script_m else None


def extract_support_uuid(bundle_html: str, bundle_name: str) -> str:
    m = re.search(
        r'<script type="__bundler/template">\s*\n(.+?)\n\s*</script>',
        bundle_html,
        re.DOTALL,
    )
    if m:
        try:
            tpl = json.loads(m.group(1).strip())
            sm = re.search(r'<script src="([0-9a-f-]{36})"></script>', tpl)
            if sm:
                return sm.group(1)
        except json.JSONDecodeError:
            pass
    if bundle_name in SUPPORT_UUIDS:
        return SUPPORT_UUIDS[bundle_name]
    raise ValueError(f"Could not resolve support.js UUID for {bundle_name}")


def wrap_bundle_document(
    inner: str,
    script: str | None,
    support_uuid: str,
    *,
    base_href: str = SITE_BASE,
    extra_head: str = "",
) -> str:
    """Wrap x-dc inner markup in the full HTML document the bundler expects."""
    tpl = (
        "<!DOCTYPE html>\n<html><head>\n"
        '<meta charset="utf-8">\n'
        f'<base href="{base_href}">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"{THEME_HEAD_SCRIPTS}\n"
        f"{CONTENT_DATA_SCRIPT}\n"
        f"{EDITORIAL_SCRIPT}\n"
        f"{extra_head}"
        f'<script src="{support_uuid}"></script>\n'
        "</head>\n<body>\n<x-dc>\n"
        f"{inner}\n"
        "</x-dc>\n"
    )
    if script:
        tpl += script + "\n"
    tpl += "</body></html>"
    return tpl


def inject_theme_template(tpl: str) -> str:
    """Add theme.css and toggle buttons to decoded bundle template inner HTML."""
    if THEME_CSS_LINK not in tpl:
        tpl = tpl.replace(
            '<link rel="apple-touch-icon"',
            THEME_CSS_LINK + "\n" + '<link rel="apple-touch-icon"',
            1,
        )

    if "mdct-theme-btn" not in tpl and 'aria-label="Basemap"' not in tpl:
        tpl = tpl.replace(
            '<button class="hamburger"',
            THEME_TOGGLE + "\n      " + '<button class="hamburger"',
        )

    return tpl


def inject_theme_shell(html: str) -> str:
    """Add early theme scripts to pre-unpack bundle shell (flash prevention)."""
    if "mdct-theme" in html and "theme.js" in html:
        html = harden_error_sink(html)
        return html
    html = html.replace("</head>", "  " + THEME_HEAD_SCRIPTS + "\n</head>", 1)
    return harden_error_sink(html)


def harden_error_sink(html: str) -> str:
    """Suppress noisy resource-load errors in the dev error overlay."""
    old = (
        "    d.textContent = (d.textContent ? d.textContent + String.fromCharCode(10) : '') +\n"
        "      '[bundle] ' + (e.message || e.type) +\n"
        "      (e.filename ? ' (' + e.filename.slice(0, 60) + ':' + e.lineno + ')' : '');"
    )
    new = (
        "    var msg = e.message || '';\n"
        "    if (!msg && e.target && /^(SCRIPT|LINK|IMG|VIDEO)$/.test(e.target.tagName || '')) return;\n"
        "    if (!msg && e.type === 'error') return;\n"
        "    d.textContent = (d.textContent ? d.textContent + String.fromCharCode(10) : '') +\n"
        "      '[bundle] ' + (msg || e.type) +\n"
        "      (e.filename ? ' (' + e.filename.slice(0, 60) + ':' + e.lineno + ')' : '');"
    )
    if old in html:
        html = html.replace(old, new, 1)
    return html


def template_from_dc(dc_html: str) -> str:
    """Return x-dc inner + logic script (unwrapped — prefer wrap_bundle_document)."""
    inner, script = split_dc_parts(dc_html)
    tpl = inner
    if script:
        tpl += "\n" + script
    return tpl