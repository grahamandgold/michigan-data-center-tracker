#!/usr/bin/env python3
"""compute_stats — the map is the single source of truth for every homepage stat.

Reads map-data.json and rewrites window.MDCT_STATS in content-data.js so the
homepage "By the Numbers" and the tile counts always agree with the Live Map.
No stat is ever hand-typed again. Deterministic, stdlib only. Runs whenever
map-data.json changes.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAPD = ROOT / "map-data.json"
CONTENT = ROOT / "content-data.js"

# Canonical county -> region (mirrors mdct-editorial.js COUNTY_REGION).
REGION_LABEL = {"se": "SE Michigan", "west": "West Michigan", "capital": "Capital Region",
                "mid": "Mid-Michigan", "north": "Northern Michigan", "statewide": "Statewide"}
_R = {
    "se": ["Wayne", "Oakland", "Macomb", "Washtenaw", "Monroe", "Livingston", "St. Clair", "St Clair", "Lenawee"],
    "capital": ["Ingham", "Clinton", "Eaton", "Jackson", "Shiawassee", "Gratiot"],
    "west": ["Berrien", "Cass", "St. Joseph", "St Joseph", "Branch", "Hillsdale", "Van Buren", "Kalamazoo",
             "Calhoun", "Allegan", "Barry", "Ottawa", "Kent", "Ionia", "Muskegon", "Montcalm", "Newaygo",
             "Oceana", "Mecosta", "Mason", "Lake", "Osceola"],
    "mid": ["Genesee", "Saginaw", "Midland", "Bay", "Isabella", "Tuscola", "Lapeer", "Sanilac", "Huron",
            "Arenac", "Gladwin", "Clare"],
    "north": ["Oscoda", "Ogemaw", "Iosco", "Roscommon", "Missaukee", "Wexford", "Manistee", "Benzie",
              "Grand Traverse", "Leelanau", "Kalkaska", "Crawford", "Antrim", "Otsego", "Montmorency",
              "Alpena", "Alcona", "Charlevoix", "Emmet", "Cheboygan", "Presque Isle", "Mackinac", "Luce",
              "Chippewa", "Schoolcraft", "Delta", "Alger", "Marquette", "Dickinson", "Menominee", "Iron",
              "Baraga", "Houghton", "Keweenaw", "Ontonagon", "Gogebic"],
}
_C2R = {c.lower(): r for r, cs in _R.items() for c in cs}


def county_region(county: str) -> str:
    if not county:
        return "statewide"
    key = re.sub(r"\s+(county|co\.?)$", "", str(county).lower()).strip()
    return _C2R.get(key, "statewide")


def status_key(status: str, layer: str) -> str:
    if layer == "moratoria":
        return "Moratorium"
    s = (status or "").lower()
    if "construction" in s:
        return "Under construction"
    if any(w in s for w in ("operating", "approved", "conditionally")):
        return "Approved"
    if any(w in s for w in ("proposed", "review", "pending", "filed")):
        return "Proposed / under review"
    if any(w in s for w in ("withdrawn", "rejected", "halted", "dead")):
        return "Withdrawn / rejected"
    return "Proposed / under review"


def main() -> int:
    pts = json.loads(MAPD.read_text(encoding="utf-8")).get("map_points", [])
    proj = [p for p in pts if p.get("layer") == "projects"]
    mor = [p for p in pts if p.get("layer") == "moratoria"]

    projects = len(proj)
    pauses = len(mor)
    communities = len({str(p.get("municipality", "")).strip() for p in pts if p.get("municipality")})

    def mw(p):
        try:
            return float(str(p.get("power_mw", "")).replace(",", ""))
        except Exception:  # noqa: BLE001
            return 0.0
    total_mw = sum(mw(p) for p in proj)
    disclosed_gw = f"{total_mw / 1000:.1f}"

    # status breakdown for projects (the donut)
    order = [("Under construction", "#dd8048"), ("Approved", "#E03131"),
             ("Proposed / under review", "#bda35f"), ("Withdrawn / rejected", "#6f6a64")]
    counts = {}
    for p in proj:
        counts[status_key(p.get("status"), "projects")] = counts.get(status_key(p.get("status"), "projects"), 0) + 1
    status_breakdown = [{"label": lbl, "count": counts.get(lbl, 0), "color": col} for lbl, col in order]

    # by region: projects + pauses, in the five-region order (skip empty regions)
    reg_order = ["se", "west", "capital", "mid", "north"]
    by = {r: {"projects": 0, "pauses": 0} for r in reg_order}
    for p in proj:
        r = county_region(p.get("county"))
        if r in by:  # statewide/unknown-county records don't belong to any region bar
            by[r]["projects"] += 1
    for p in mor:
        r = county_region(p.get("county"))
        if r in by:
            by[r]["pauses"] += 1
    by_region = [{"label": REGION_LABEL[r], "projects": by[r]["projects"], "pauses": by[r]["pauses"]}
                 for r in reg_order if by[r]["projects"] or by[r]["pauses"]]

    active = sum(1 for p in proj if status_key(p.get("status"), "projects") not in ("Withdrawn / rejected",))
    stats = {"projects": projects, "activeProjects": active, "disclosedGW": disclosed_gw,
             "pauses": pauses, "communities": communities,
             "statusBreakdown": status_breakdown, "byRegion": by_region}

    js = "window.MDCT_STATS = " + json.dumps(stats, indent=2) + ";"
    content = CONTENT.read_text(encoding="utf-8")
    new, n = re.subn(r"window\.MDCT_STATS\s*=\s*\{.*?\n\};", lambda m: js, content, count=1, flags=re.S)
    if n == 0:
        print("::error::could not locate the MDCT_STATS block in content-data.js")
        return 1
    summary = (f"Stats from map: projects={projects}, {disclosed_gw} GW, pauses={pauses}, "
               f"communities={communities}, regions={len(by_region)}")
    if new == content:
        print(f"{summary} — already in sync, no change.")
        return 0
    CONTENT.write_text(new, encoding="utf-8")
    print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
