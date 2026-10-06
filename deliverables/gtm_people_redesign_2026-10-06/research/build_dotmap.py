#!/usr/bin/env python3
"""Rasterise Natural Earth 110m land (TopoJSON) into a dot-matrix bitmask for the v4 opening map.

description: Decodes .tmp/geo/land-110m.json (TopoJSON: quantised, delta-encoded arcs + transform),
  scanline-fills every land polygon onto an equirectangular grid (step 2.2 deg lon x 2.2 deg lat,
  lat clamped to +-60) and prints a compact base-64 bitmask (cols x rows, row-major, MSB first)
  that js/main.js inlines as DOTMAP. Also self-checks known points (London, Tokyo, Cape Town land;
  mid-Atlantic sea).
inputs: --topo PATH (default .tmp/geo/land-110m.json), --step 2.2, --lat 60, --write (patch main.js DOTMAP).
outputs: stdout: cols rows base64; with --write replaces the DOTMAP line in site/js/main.js.
"""
import argparse, base64, json, math, re, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]

def decode(topo):
    sx, sy = topo["transform"]["scale"]; tx, ty = topo["transform"]["translate"]
    arcs = []
    for arc in topo["arcs"]:
        x = y = 0; pts = []
        for dx, dy in arc:
            x += dx; y += dy; pts.append((x * sx + tx, y * sy + ty))
        arcs.append(pts)
    def ring(idx):
        out = []
        for i in idx:
            a = arcs[~i][::-1] if i < 0 else arcs[i]
            out.extend(a if not out else a[1:])
        return out
    polys = []
    for g in topo["objects"]["land"]["geometries"]:
        if g["type"] == "Polygon": polys.append([ring(r) for r in g["arcs"]])
        elif g["type"] == "MultiPolygon": polys.extend([[ring(r) for r in p] for p in g["arcs"]])
    return polys

def rasterise(polys, step, latmax):
    cols = int(round(360 / step)); rows = int(round(2 * latmax / step))
    grid = [[0] * cols for _ in range(rows)]
    edges = [(a, b) for poly in polys for rg in poly for a, b in zip(rg, rg[1:] + rg[:1]) if a[1] != b[1]]
    for r in range(rows):
        lat = latmax - (r + .5) * step
        xs = []
        for (x1, y1), (x2, y2) in edges:
            if (y1 <= lat < y2) or (y2 <= lat < y1):
                xs.append(x1 + (lat - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for i in range(0, len(xs) - 1, 2):
            c0 = int(math.floor((xs[i] + 180) / step)); c1 = int(math.floor((xs[i + 1] + 180) / step))
            for c in range(max(0, c0), min(cols - 1, c1) + 1):
                if xs[i] <= -180 + (c + .5) * step <= xs[i + 1]: grid[r][c] = 1
    return cols, rows, grid

def pack(cols, rows, grid):
    bits = [grid[r][c] for r in range(rows) for c in range(cols)]
    bits += [0] * (-len(bits) % 8)
    return base64.b64encode(bytes(int("".join(map(str, bits[i:i + 8])), 2) for i in range(0, len(bits), 8))).decode()

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--topo", type=Path, default=ROOT / ".tmp/geo/land-110m.json")
    ap.add_argument("--step", type=float, default=2.2); ap.add_argument("--lat", type=float, default=60)
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args()
    polys = decode(json.loads(a.topo.read_text(encoding="utf-8")))
    cols, rows, grid = rasterise(polys, a.step, a.lat)
    def land(lon, lat):
        c = int((lon + 180) / a.step); r = int((a.lat - lat) / a.step)  # land if the cell or a neighbour is land (110m coastlines)
        return max(grid[rr][cc] for rr in (r - 1, r, r + 1) for cc in (c - 1, c, c + 1) if 0 <= rr < rows and 0 <= cc < cols)
    checks = {"London": (-0.13, 51.5, 1), "Tokyo": (139.7, 35.7, 1), "Cape Town": (18.4, -33.9, 1), "mid-Atlantic": (-35, 30, 0), "Sydney": (151.2, -33.9, 1), "Denver": (-105, 39.7, 1)}
    bad = [k for k, (lo, la, want) in checks.items() if land(lo, la) != want]
    b64 = pack(cols, rows, grid)
    print(f"{cols}x{rows} cells, {sum(map(sum, grid))} land, b64 {len(b64)} chars; geo checks: {'PASS' if not bad else 'FAIL ' + ','.join(bad)}")
    if bad: return 1
    if a.write:
        js = ROOT / "deliverables/gtm_people_redesign_2026-10-06/site/js/main.js"
        src = js.read_text(encoding="utf-8")
        new = f"  var DOTMAP = {{ cols: {cols}, rows: {rows}, step: {a.step}, lat: {a.lat}, b64: '{b64}' }};"
        out, n = re.subn(r"  var DOTMAP = \{.*?\};", new, src, count=1, flags=re.S)
        if not n: print("DOTMAP line not found in main.js"); return 1
        js.write_text(out, encoding="utf-8"); print("main.js DOTMAP updated")
    else: print(cols, rows, b64)
    return 0

if __name__ == "__main__":
    sys.exit(main())
