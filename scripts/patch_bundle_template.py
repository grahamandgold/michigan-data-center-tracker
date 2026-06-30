#!/usr/bin/env python3
"""Patch the homepage bundle template JSON in-place (preserves bundler encoding)."""

from __future__ import annotations

import base64
import gzip
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "handoff"
BASE = "/mi-data-center-tracker/"

LINK_REPLACEMENTS = [
    ("Homepage.dc.html", "index.html"),
    ("Live Map.dc.html", "map/"),
    ("Stories.dc.html", "stories.html"),
    ("Meetings.dc.html", "meetings.html"),
    ("Learn.dc.html", "learn.html"),
    ("Sponsor.dc.html", "sponsor.html"),
]


def extract_raw_template(html: str) -> tuple[str, str, str]:
    m = re.search(
        r'(<script type="__bundler/template">\s*\n)(.+?)(\n\s*</script>)',
        html,
        re.DOTALL,
    )
    if not m:
        raise ValueError("template block not found")
    return m.group(1), m.group(2).strip(), m.group(3)


def _escape_json_closing_tags(encoded: str) -> str:
    return re.sub(
        r"</([^>]+)>",
        lambda m: "<\\u002F" + m.group(1) + ">",
        encoded,
    )


def encode_like_bundler(template: str) -> str:
    """Match Claude bundler JSON: escape every closing HTML tag in the string."""
    return _escape_json_closing_tags(json.dumps(template, ensure_ascii=True))


def load_homepage_template(support_uuid: str) -> str:
    from productionize_homepage import productionize_homepage
    from theme_assets import inject_theme_template, split_dc_parts, wrap_bundle_document

    dc = (HANDOFF / "Homepage.dc.html").read_text(encoding="utf-8")
    inner, script = split_dc_parts(dc)
    inner = productionize_homepage("<x-dc>" + inner + "</x-dc>")
    inner = inner[len("<x-dc>") : -len("</x-dc>")]
    if script:
        script = productionize_homepage(script)
    for old, new in LINK_REPLACEMENTS:
        inner = inner.replace(old, new)
    inner = inject_theme_template(inner)
    return wrap_bundle_document(inner, script, support_uuid)


def patch_decoded_template(support_uuid: str) -> str:
    return load_homepage_template(support_uuid)


def decompress_manifest(html: str) -> str:
    """Store manifest assets uncompressed so unpack works without DecompressionStream."""
    m = re.search(
        r'(<script type="__bundler/manifest">\s*\n)(.+?)(\n\s*</script>)',
        html,
        re.DOTALL,
    )
    if not m:
        return html
    manifest = json.loads(m.group(2))
    for entry in manifest.values():
        if not entry.get("compressed"):
            continue
        entry["data"] = base64.b64encode(
            gzip.decompress(base64.b64decode(entry["data"]))
        ).decode("ascii")
        entry["compressed"] = False
    encoded = json.dumps(manifest, separators=(",", ":"))
    return html[: m.start()] + m.group(1) + encoded + m.group(3) + html[m.end() :]


def harden_bundle_shell(html: str) -> str:
    """Reduce stale-cache blank screens and surface load failures to users."""
    if '<meta http-equiv="Cache-Control"' not in html:
        html = html.replace(
            "<meta charset=\"utf-8\">",
            '<meta charset="utf-8">\n  <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">',
            1,
        )

    html = html.replace(
        "body { background: #faf9f5; display: flex; align-items: center; justify-content: center; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, sans-serif; }",
        "body { background: #16140f; min-height: 100vh; font-family: -apple-system, BlinkMacSystemFont, sans-serif; color: #f4f1ee; }",
    )

    if "window.Babel.transformScriptTags" in html and "__bundler_render_check" not in html:
        html = html.replace(
            "    if (window.Babel && typeof window.Babel.transformScriptTags === 'function') {\n"
            "      window.Babel.transformScriptTags();\n"
            "    }",
            "    if (window.Babel && typeof window.Babel.transformScriptTags === 'function') {\n"
            "      window.Babel.transformScriptTags();\n"
            "    }\n"
            "    setTimeout(function() {\n"
            "      var host = document.querySelector('.sc-host');\n"
            "      var len = host ? host.innerHTML.length : 0;\n"
            "      if (len < 100) {\n"
            "        var fb = document.getElementById('__bundler_fatal');\n"
            "        if (!fb) {\n"
            "          fb = document.body.appendChild(document.createElement('div'));\n"
            "          fb.id = '__bundler_fatal';\n"
            "        }\n"
            "        fb.style.cssText = 'position:fixed;inset:0;display:flex;align-items:center;justify-content:center;background:#16140f;color:#f4f1ee;font:16px/1.5 system-ui,sans-serif;z-index:999999;padding:24px;text-align:center;';\n"
            "        fb.innerHTML = '<div><p style=\"font-size:20px;margin-bottom:12px;\">Homepage failed to load</p>' +\n"
            "          '<p style=\"color:#9b9794;max-width:440px;\">Your browser may be using a cached broken copy. Hard refresh: <b>Cmd+Shift+R</b> (Mac) or <b>Ctrl+Shift+R</b> (Windows), or open in a private window.</p>' +\n"
            "          '<p style=\"margin-top:16px;\"><a href=\"' + location.href.split('#')[0] + '\" style=\"color:#E03131\">Reload</a></p></div>';\n"
            "      }\n"
            "    }, 8000);",
        )

    return html


def patch_index_html(html: str) -> str:
    m = re.search(
        r'(<script type="__bundler/template">\s*\n)(.+?)(\n\s*</script>)',
        html,
        re.DOTALL,
    )
    if not m:
        raise ValueError("template block not found")
    from theme_assets import extract_support_uuid

    support_uuid = extract_support_uuid(html, "index.html")
    template = patch_decoded_template(support_uuid)
    encoded = encode_like_bundler(template)
    html = html[: m.start()] + m.group(1) + encoded + m.group(3) + html[m.end() :]
    html = decompress_manifest(html)
    html = harden_bundle_shell(html)
    from theme_assets import inject_theme_shell

    return inject_theme_shell(html)


def main() -> None:
    shell = subprocess.check_output(
        ["git", "-C", str(ROOT), "show", "c61b724:index.html"],
        text=True,
    )
    (ROOT / "index.html").write_text(patch_index_html(shell), encoding="utf-8")
    print("Patched index.html from c61b724 shell")


if __name__ == "__main__":
    main()