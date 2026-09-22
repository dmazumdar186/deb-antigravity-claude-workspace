"""Build the GreenJobs region maps (Ireland counties, UK regions) as SVG.

description: Downloads the public-domain Natural Earth 10m admin-1 GeoJSON
  (or reads a cached copy), merges its districts into the 26 Irish counties
  and the 12 UK regions (9 English regions + Scotland, Wales, Northern
  Ireland) with an edge-cancelling polygon union, simplifies the rings, projects
  them (equirectangular, cos-lat corrected) and writes one SVG per edition with
  a <g data-region="…"> per region so the page script can attach counts,
  tooltips and keyboard buttons.
inputs: --cache <path to ne_10m_admin_1_states_provinces.geojson> (optional;
  downloaded to .tmp/ when absent), --out <src/assets/maps directory>
outputs: <out>/ie.svg and <out>/uk.svg, plus <out>/regions_index.json listing
  the region names each map carries (consumed by build_site.py's mapping table)

CLI:
  python3 execution/gtm_client_workflows/greenjobs_redesign/make_maps.py --out <dir>
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import urllib.request
from collections import defaultdict
from pathlib import Path
from typing import Any

NE_URL = (
    "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/"
    "geojson/ne_10m_admin_1_states_provinces.geojson"
)

# Natural Earth name -> GreenJobs county. Everything else in IRL keeps its name.
IE_MERGE = {
    "Dún Laoghaire–Rathdown": "Dublin",
    "Fingal": "Dublin",
    "South Dublin": "Dublin",
    "North Tipperary": "Tipperary",
    "South Tipperary": "Tipperary",
    "Laoighis": "Laois",
}
UK_NATION = {"SCT": "Scotland", "WLS": "Wales", "NIR": "Northern Ireland"}
UK_ENGLAND = {
    "East": "East of England",
    "East Midlands": "East Midlands",
    "Greater London": "London",
    "North East": "North East",
    "North West": "North West",
    "South East": "South East",
    "South West": "South West",
    "West Midlands": "West Midlands",
    "Yorkshire and the Humber": "Yorkshire and the Humber",
}

Point = tuple[float, float]


def _snap(p: list[float]) -> Point:
    return (round(p[0], 4), round(p[1], 4))


def _rings(geom: dict[str, Any]) -> list[list[Point]]:
    polys = geom["coordinates"] if geom["type"] == "MultiPolygon" else [geom["coordinates"]]
    out: list[list[Point]] = []
    for poly in polys:
        for ring in poly:  # outer + holes: both take part in the union
            pts = [_snap(p) for p in ring]
            if pts and pts[0] == pts[-1]:
                pts.pop()
            if len(pts) >= 3:
                out.append(pts)
    return out


def union_rings(rings: list[list[Point]]) -> list[list[Point]]:
    """Edge-cancelling union: every edge shared by two rings is interior and
    drops out; the survivors are chained back into closed rings."""
    count: dict[tuple[Point, Point], int] = defaultdict(int)
    directed: dict[tuple[Point, Point], int] = defaultdict(int)
    for ring in rings:
        for i, a in enumerate(ring):
            b = ring[(i + 1) % len(ring)]
            if a == b:
                continue
            count[(a, b) if a < b else (b, a)] += 1
            directed[(a, b)] += 1
    edges = [(a, b) for (a, b), n in directed.items() if count[(a, b) if a < b else (b, a)] == 1]
    nxt: dict[Point, list[Point]] = defaultdict(list)
    for a, b in edges:
        nxt[a].append(b)
    out: list[list[Point]] = []
    used: set[tuple[Point, Point]] = set()
    for a, b in edges:
        if (a, b) in used:
            continue
        ring = [a]
        cur, prev = b, a
        used.add((a, b))
        guard = 0
        while cur != a and guard < 200000:
            ring.append(cur)
            cands = [c for c in nxt.get(cur, []) if (cur, c) not in used]
            if not cands:
                break
            step = cands[0]
            used.add((cur, step))
            prev, cur = cur, step
            guard += 1
        if cur == a and len(ring) >= 3:
            out.append(ring)
    return out


def _perp(p: Point, a: Point, b: Point) -> float:
    dx, dy = b[0] - a[0], b[1] - a[1]
    if dx == 0 and dy == 0:
        return math.hypot(p[0] - a[0], p[1] - a[1])
    t = max(0.0, min(1.0, ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / (dx * dx + dy * dy)))
    return math.hypot(p[0] - (a[0] + t * dx), p[1] - (a[1] + t * dy))


def simplify(points: list[Point], tol: float) -> list[Point]:
    """Iterative Douglas-Peucker on a closed ring (first point anchored)."""
    if len(points) < 5:
        return points
    keep = [False] * len(points)
    keep[0] = keep[-1] = True
    stack = [(0, len(points) - 1)]
    while stack:
        s, e = stack.pop()
        best, idx = 0.0, -1
        for i in range(s + 1, e):
            d = _perp(points[i], points[s], points[e])
            if d > best:
                best, idx = d, i
        if best > tol and idx > 0:
            keep[idx] = True
            stack.append((s, idx))
            stack.append((idx, e))
    return [p for p, k in zip(points, keep) if k]


def ring_area(points: list[Point]) -> float:
    a = 0.0
    for i, p in enumerate(points):
        q = points[(i + 1) % len(points)]
        a += p[0] * q[1] - q[0] * p[1]
    return abs(a) / 2


def collect(features: list[dict[str, Any]], edition: str) -> dict[str, list[list[Point]]]:
    groups: dict[str, list[list[Point]]] = defaultdict(list)
    for f in features:
        p = f["properties"]
        if edition == "ie" and p.get("admin") == "Ireland":
            name = IE_MERGE.get(p.get("name") or "", p.get("name") or "")
        elif edition == "uk" and p.get("admin") == "United Kingdom":
            code = p.get("gu_a3")
            name = UK_NATION.get(code) or UK_ENGLAND.get(p.get("region") or "", "")
            if not name:
                continue
        else:
            continue
        groups[name].extend(_rings(f["geometry"]))
    return groups


def project(groups: dict[str, list[list[Point]]], width: float, tol: float, min_area: float) -> tuple[dict[str, list[list[Point]]], float, float]:
    lat0 = sum(p[1] for g in groups.values() for r in g for p in r) / max(
        1, sum(len(r) for g in groups.values() for r in g)
    )
    kx = math.cos(math.radians(lat0))
    merged: dict[str, list[list[Point]]] = {}
    for name, rings in groups.items():
        # Shetland (north of 59.6°N) would add 25% of empty height to the UK
        # map for one archipelago; atlases inset it, the demo omits it.
        rs = [r for r in union_rings(rings) if ring_area(r) >= min_area and min(p[1] for p in r) < 59.6]
        rs = [simplify(r + [r[0]], tol)[:-1] for r in rs]
        merged[name] = [r for r in rs if len(r) >= 3]
    xs = [p[0] * kx for g in merged.values() for r in g for p in r]
    ys = [p[1] for g in merged.values() for r in g for p in r]
    minx, maxx, miny, maxy = min(xs), max(xs), min(ys), max(ys)
    scale = width / (maxx - minx)
    height = (maxy - miny) * scale
    out: dict[str, list[list[Point]]] = {}
    for name, rings in merged.items():
        out[name] = [
            [(round((p[0] * kx - minx) * scale, 1), round((maxy - p[1]) * scale, 1)) for p in r]
            for r in rings
        ]
    return out, width, height


def centroid(rings: list[list[Point]]) -> Point:
    best = max(rings, key=ring_area)
    a = cx = cy = 0.0
    for i, p in enumerate(best):
        q = best[(i + 1) % len(best)]
        cross = p[0] * q[1] - q[0] * p[1]
        a += cross
        cx += (p[0] + q[0]) * cross
        cy += (p[1] + q[1]) * cross
    if abs(a) < 1e-9:
        return best[0]
    return (round(cx / (3 * a), 1), round(cy / (3 * a), 1))


def to_svg(shapes: dict[str, list[list[Point]]], width: float, height: float, title: str) -> str:
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {width:.0f} {height:.0f}" '
        f'class="gmap" role="group" aria-label="{title}">'
    ]
    for name in sorted(shapes):
        rings = shapes[name]
        d = " ".join("M" + " L".join(f"{x},{y}" for x, y in r) + "Z" for r in rings)
        cx, cy = centroid(rings)
        slug = name.lower().replace(" ", "-").replace("&", "and")
        parts.append(
            f'<g class="gmap__r" data-region="{name}" data-slug="{slug}" data-cx="{cx}" data-cy="{cy}">'
            f'<path d="{d}"/></g>'
        )
    parts.append("</svg>")
    return "\n".join(parts) + "\n"


def load_features(cache: Path) -> list[dict[str, Any]]:
    if not cache.exists():
        cache.parent.mkdir(parents=True, exist_ok=True)
        print(f"…  downloading Natural Earth admin-1 to {cache}")
        try:
            with urllib.request.urlopen(NE_URL, timeout=120) as resp:
                cache.write_bytes(resp.read())
        except (OSError, ValueError) as exc:
            raise SystemExit(f"FAIL  could not fetch {NE_URL}: {exc}") from exc
    return json.loads(cache.read_text(encoding="utf-8"))["features"]


def main() -> int:
    repo = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--cache", type=Path, default=repo / ".tmp" / "ne_10m_admin_1.geojson")
    parser.add_argument("--out", type=Path, default=repo / "deliverables" / "greenjobs_redesign_2026-09-22" / "src" / "assets" / "maps")
    args = parser.parse_args()
    features = load_features(args.cache)
    args.out.mkdir(parents=True, exist_ok=True)
    index: dict[str, list[str]] = {}
    for edition, tol, min_area, title in (
        ("ie", 0.012, 0.004, "Map of Ireland by county"),
        ("uk", 0.02, 0.01, "Map of the United Kingdom by region"),
    ):
        groups = collect(features, edition)
        shapes, w, h = project(groups, 600, tol, min_area)
        svg = to_svg(shapes, w, h, title)
        (args.out / f"{edition}.svg").write_text(svg, encoding="utf-8")
        index[edition] = sorted(shapes)
        print(f"PASS  {edition}.svg: {len(shapes)} regions, {len(svg)} bytes, viewBox 600x{h:.0f}")
    (args.out / "regions_index.json").write_text(json.dumps(index, indent=1) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    sys.exit(main())
