"""Shared theme toggle markup and bundle injection helpers."""

from __future__ import annotations

import re

THEME_CSS_LINK = '<link rel="stylesheet" href="theme.css">'

THEME_TOGGLE = (
    '<button type="button" class="mdct-theme-btn" aria-label="Switch to daylight mode" '
    'aria-pressed="false" title="Switch to daylight mode">'
    '<span class="mdct-theme-icon" aria-hidden="true">☀</span>'
    '<span class="mdct-theme-label">Day</span></button>'
)

THEME_SHELL_INLINE = """<script>
(function(){try{var t=localStorage.getItem('mdct-theme');if(t==='light'||t==='dark')document.documentElement.dataset.theme=t;}catch(e){}})();
</script>
<script src="theme.js"></script>"""


def inject_theme_template(tpl: str) -> str:
    """Add theme.css and toggle buttons to a decoded bundle template."""
    if THEME_CSS_LINK not in tpl:
        tpl = tpl.replace(
            '<link rel="apple-touch-icon"',
            THEME_CSS_LINK + "\n" + '<link rel="apple-touch-icon"',
            1,
        )

    if "mdct-theme-btn" not in tpl:
        tpl = tpl.replace(
            '<button class="hamburger"',
            THEME_TOGGLE + "\n      " + '<button class="hamburger"',
        )
        tpl = tpl.replace(
            '<div class="seg" role="group" aria-label="Basemap">',
            THEME_TOGGLE + "\n      " + '<div class="seg" role="group" aria-label="Basemap">',
            1,
        )

    return tpl


def inject_theme_shell(html: str) -> str:
    """Add early theme scripts to bundle shell <head>."""
    if "theme.js" in html:
        return html
    return html.replace("</head>", "  " + THEME_SHELL_INLINE + "\n</head>", 1)


def template_from_dc(dc_html: str) -> str:
    m = re.search(r"<x-dc>(.*)</x-dc>", dc_html, re.DOTALL)
    if not m:
        raise ValueError("x-dc block not found in .dc.html")
    return m.group(1).strip()