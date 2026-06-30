#!/usr/bin/env python3
"""Patch live map bundle template in map/index.html (preserves bundler shell)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from patch_bundle_template import decompress_manifest, encode_like_bundler

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = ROOT / "handoff"
MAP_HTML = ROOT / "map" / "index.html"

LINK_REPLACEMENTS = [
    ("Homepage.dc.html", "index.html"),
    ("Live Map.dc.html", "map/"),
    ("Stories.dc.html", "stories.html"),
    ("Meetings.dc.html", "meetings.html"),
    ("Learn.dc.html", "learn.html"),
    ("Sponsor.dc.html", "sponsor.html"),
]

MAP_PATCHES: list[tuple[str, str]] = [
    (
        "    this.REGIONS = [\n"
        "      { key: 'all', label: 'All' }, { key: 'metro', label: 'SE Michigan' },\n"
        "      { key: 'west', label: 'West MI' }, { key: 'mid', label: 'Mid-Michigan' }, { key: 'north', label: 'Northern MI' },\n"
        "    ];\n"
        "    this.state = {\n"
        "      basemap: 'dark', tab: 'list', region: 'all', query: '', selectedId: 1,",
        "    this.REGIONS = [\n"
        "      { key: 'all', label: 'All' }, { key: 'metro', label: 'SE Michigan' },\n"
        "      { key: 'west', label: 'West MI' }, { key: 'mid', label: 'Mid-Michigan' }, { key: 'north', label: 'Northern MI' },\n"
        "    ];\n"
        "    this.LOWER_PEN_BOUNDS = [[41.68, -87.5], [45.35, -82.3]];\n"
        "    this.state = {\n"
        "      basemap: 'dark', tab: 'list', region: 'all', query: '', selectedId: null,",
    ),
    (
        "  componentWillUnmount() { clearInterval(this._wait); if (this._map) this._map.remove(); }\n\n"
        "  initMap() {\n"
        "    const el = document.getElementById('mdct-map');\n"
        "    if (!el || this._map) return;\n"
        "    const map = L.map(el, { zoomControl: false, attributionControl: true, minZoom: 5, maxZoom: 14, zoomSnap: 0.5 })\n"
        "      .setView([43.7, -84.6], 6.8);\n"
        "    this._map = map;\n"
        "    L.control.zoom({ position: 'topright' }).addTo(map);\n"
        "    this.tiles = {\n"
        "      dark: L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png', { subdomains: 'abcd', maxZoom: 19, attribution: '© OpenStreetMap · © CARTO' }),\n"
        "      day:  L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', { subdomains: 'abcd', maxZoom: 19, attribution: '© OpenStreetMap · © CARTO' }),\n"
        "      sat:  L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: '© Esri' }),\n"
        "    };",
        "  componentWillUnmount() { clearInterval(this._wait); if (this._map) this._map.remove(); }\n\n"
        "  viewLowerPeninsula() {\n"
        "    if (!this._map) return;\n"
        "    this._map.fitBounds(this.LOWER_PEN_BOUNDS, { padding: [28, 28], maxZoom: 7.5 });\n"
        "  }\n\n"
        "  initMap() {\n"
        "    const el = document.getElementById('mdct-map');\n"
        "    if (!el || this._map) return;\n"
        "    const map = L.map(el, { zoomControl: false, attributionControl: true, minZoom: 5, maxZoom: 14, zoomSnap: 0.5 });\n"
        "    this._map = map;\n"
        "    L.control.zoom({ position: 'topright' }).addTo(map);\n"
        "    const carto = { subdomains: 'abcd', maxZoom: 19, attribution: '© OpenStreetMap · © CARTO' };\n"
        "    this.tiles = {\n"
        "      dark: L.layerGroup([\n"
        "        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_nolabels/{z}/{x}/{y}.png', carto),\n"
        "        L.tileLayer('https://{s}.basemaps.cartocdn.com/dark_only_labels/{z}/{x}/{y}.png', { subdomains: 'abcd', maxZoom: 19 }),\n"
        "      ]),\n"
        "      day: L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager/{z}/{x}/{y}.png', carto),\n"
        "      sat: L.layerGroup([\n"
        "        L.tileLayer('https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}', { maxZoom: 18, attribution: '© Esri' }),\n"
        "        L.tileLayer('https://{s}.basemaps.cartocdn.com/rastertiles/voyager_only_labels/{z}/{x}/{y}.png', { subdomains: 'abcd', maxZoom: 19 }),\n"
        "      ]),\n"
        "    };",
    ),
    (
        "setTimeout(() => { map.invalidateSize(false); this.focusSelected(false); }, 240);",
        "setTimeout(() => { map.invalidateSize(false); this.viewLowerPeninsula(); }, 240);",
    ),
    (
        "    this.setState({ region: 'all', query: '', status: { Operating: true, Construction: true, Permitting: true, Proposed: true, Moratorium: true } });\n"
        "    if (this._map) this._map.setView([43.7, -84.6], 6.8);",
        "    this.setState({ region: 'all', query: '', selectedId: null, status: { Operating: true, Construction: true, Permitting: true, Proposed: true, Moratorium: true } });\n"
        "    if (this._map) this.viewLowerPeninsula();",
    ),
    (
        "if (this._map) this._map.setView([43.7, -84.6], 6.8); }",
        "if (this._map) this.viewLowerPeninsula(); }",
    ),
]


def patch_map_template(tpl: str) -> str:
    for old, new in MAP_PATCHES:
        if old in tpl:
            tpl = tpl.replace(old, new, 1)
    for old, new in LINK_REPLACEMENTS:
        tpl = tpl.replace(old, new)
    if '<base href="/mi-data-center-tracker/">' not in tpl:
        tpl = tpl.replace(
            '<meta charset="utf-8">\n<meta name="viewport"',
            '<meta charset="utf-8">\n<base href="/mi-data-center-tracker/">\n<meta name="viewport"',
            1,
        )
    tpl = tpl.replace('href="#map"', 'href="map/"')
    tpl = tpl.replace('href="Homepage.dc.html"', 'href="index.html"')
    tpl = tpl.replace('href="Stories.dc.html"', 'href="stories.html"')
    tpl = tpl.replace('href="Meetings.dc.html"', 'href="meetings.html"')
    tpl = tpl.replace('href="Learn.dc.html"', 'href="learn.html"')
    tpl = tpl.replace('href="Sponsor.dc.html"', 'href="sponsor.html"')
    tpl = tpl.replace('href="Live Map.dc.html"', 'href="map/"')
    return tpl


def load_map_template(support_uuid: str) -> str:
    from theme_assets import inject_theme_template, split_dc_parts, wrap_bundle_document

    dc = (HANDOFF / "Live Map.dc.html").read_text(encoding="utf-8")
    inner, script = split_dc_parts(dc)
    inner = patch_map_template(inner)
    if script:
        script = patch_map_template(script)
    inner = inject_theme_template(inner)
    return wrap_bundle_document(inner, script, support_uuid)


def patch_map_html(html: str) -> str:
    from theme_assets import extract_support_uuid, inject_theme_shell

    m = re.search(
        r'(<script type="__bundler/template">\s*\n)(.+?)(\n\s*</script>)',
        html,
        re.DOTALL,
    )
    if not m:
        raise ValueError("template block not found in map bundle")
    support_uuid = extract_support_uuid(html, "map/index.html")
    template = load_map_template(support_uuid)
    encoded = encode_like_bundler(template)
    html = html[: m.start()] + m.group(1) + encoded + m.group(3) + html[m.end() :]
    html = decompress_manifest(html)
    return inject_theme_shell(html)


def main() -> None:
    html = MAP_HTML.read_text(encoding="utf-8")
    MAP_HTML.write_text(patch_map_html(html), encoding="utf-8")
    print(f"Patched {MAP_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()