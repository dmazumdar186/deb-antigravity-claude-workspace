#!/usr/bin/env python3
"""Ingest real photos for the Jeevana site.

inputs:  --src FOLDER (jpg/jpeg/png/webp), --out site/assets/img,
         --sequence name=file,... (rename map; sn-NN = Surya Namaskar frame NN),
         --focus name=X%_Y%,... (optional object-position per output name; default 50%_42%).
outputs: <out>/<name>.webp (<= 1600 px long edge, q82), <out>/<name>-m.webp (<= 1000 px),
         <out>/manifest.json {frames:{"sn-01":{file,mfile,w,h,focus}}, photos:[{name,file,mfile,w,h,focus}]}.
         With --sequence, only mapped files are ingested (one file may serve several names: the sequence
         repeats); --all also ingests unmapped files as photos under their stem. Without --focus the
         horizontal focus is estimated from the image (column deviation from the row-median background).
usage:   python3 research/ingest_photos.py --src _raw_assets --out site/assets/img \
           --sequence sn-01=pranamasana-side.jpg,sn-02=hasta-uttanasana-side.jpg,portrait=pranamasana-front.jpg,photo-01=chakrasana-eiffel.jpg
Adding a new sn-NN entry and re-running is all that is needed for a new cover frame (no HTML edits).
"""
from __future__ import annotations

import argparse
import json
import pathlib
import re
import sys

from PIL import Image, ImageOps

EXT = {".jpg", ".jpeg", ".png", ".webp"}


def parse_map(text: str | None) -> dict[str, str]:
    out: dict[str, str] = {}
    for part in (text or "").split(","):
        if "=" in part:
            k, v = part.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def save(img: Image.Image, path: pathlib.Path, edge: int) -> tuple[int, int]:
    im = img.copy()
    im.thumbnail((edge, edge), Image.LANCZOS)
    im.save(path, "WEBP", quality=82, method=6)
    return im.size


def estimate_focus(img: Image.Image) -> tuple[str, list[float]]:
    """Rough subject locator: pixels far from their row's median colour are 'figure'.
    Returns ('X% Y%' centroid, [x0, y0, x1, y1] box as fractions, 6th-94th percentile of figure mass)."""
    sm = img.resize((90, 160))
    px = sm.load()
    W, H = sm.size
    colw = [0.0] * W
    roww = [0.0] * H
    for y in range(H):
        row = [px[x, y] for x in range(W)]
        med = [sorted(c[i] for c in row)[W // 2] for i in range(3)]
        for x, c in enumerate(row):
            d = sum(abs(c[i] - med[i]) for i in range(3))
            if d > 60:
                colw[x] += d
                roww[y] += d

    def span(v: list[float]) -> tuple[float, float, float]:
        tot = sum(v) or 1.0
        acc, lo, hi = 0.0, 0, len(v) - 1
        for i, x in enumerate(v):
            if acc < tot * 0.06 <= acc + x:
                lo = i
            if acc < tot * 0.94 <= acc + x:
                hi = i
            acc += x
        c = sum(i * x for i, x in enumerate(v)) / tot
        n = len(v) - 1
        return lo / n, hi / n, c / n

    x0, x1, cx = span(colw)
    y0, y1, cy = span(roww)
    cx = min(max(cx, 0.2), 0.8)
    cy = min(max(cy, 0.3), 0.7)
    return f"{round(cx * 100)}% {round(cy * 100)}%", [round(x0, 3), round(y0, 3), round(x1, 3), round(y1, 3)]


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sequence", default="")
    ap.add_argument("--focus", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--zoom", default="", help="name=minZoom,... extra crop for a frame (e.g. to crop a bystander out)")
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if not src.is_dir():
        print(f"no such folder: {src}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    seq = parse_map(a.sequence)
    focus = {k: v.replace("_", " ") for k, v in parse_map(a.focus).items()}
    zoom = parse_map(a.zoom)
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXT)
    missing = [v for v in seq.values() if not (src / v).exists()]
    if missing:
        print("missing in --src: " + ", ".join(missing), file=sys.stderr)
        return 2
    jobs = list(seq.items())
    if a.all or not seq:
        mapped = set(seq.values())
        jobs += [(re.sub(r"[^a-z0-9-]+", "-", f.stem.lower()), f.name) for f in files if f.name not in mapped]
    man: dict = {"frames": {}, "photos": []}
    cache: dict[str, tuple] = {}
    for name, fname in jobs:
        if fname not in cache:
            with Image.open(src / fname) as raw:
                img = ImageOps.exif_transpose(raw).convert("RGB")
            cache.clear()
            cache[fname] = (img, *estimate_focus(img))
        img, est, box = cache[fname]
        w, h = save(img, out / f"{name}.webp", 1600)
        save(img, out / f"{name}-m.webp", 1000)
        rec = {"file": f"{name}.webp", "mfile": f"{name}-m.webp", "w": w, "h": h, "focus": focus.get(name, est), "box": box, "src": fname}
        if name in zoom:
            rec["zoom"] = float(zoom[name])
        if re.fullmatch(r"sn-\d{2}", name):
            man["frames"][name] = rec
        else:
            man["photos"].append({"name": name, **rec})
        print(f"{fname} -> {name}.webp {w}x{h} focus {rec['focus']} box {box}")
    man["frames"] = dict(sorted(man["frames"].items()))
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print(f"manifest: {len(man['frames'])} frames, {len(man['photos'])} photos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
