#!/usr/bin/env python3
"""Ingest real photos for the Jeevana site.

inputs:  --src FOLDER (jpg/jpeg/png/webp), --out site/assets/img,
         --sequence name=file,... (rename map; sn-NN = Surya Namaskar frame NN),
         --focus name=X%_Y%,... (optional object-position per output name; default 50%_42%).
outputs: <out>/<name>.webp (<= 1600 px long edge, q82), <out>/<name>-m.webp (<= 1000 px),
         <out>/manifest.json {frames:{"sn-01":{file,mfile,w,h,focus}}, photos:[{name,file,mfile,w,h,focus}]}.
         Files not named in --sequence are ingested as photos under their stem.
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--src", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sequence", default="")
    ap.add_argument("--focus", default="")
    a = ap.parse_args()
    src, out = pathlib.Path(a.src), pathlib.Path(a.out)
    if not src.is_dir():
        print(f"no such folder: {src}", file=sys.stderr)
        return 2
    out.mkdir(parents=True, exist_ok=True)
    seq = parse_map(a.sequence)
    focus = {k: v.replace("_", " ") for k, v in parse_map(a.focus).items()}
    by_file = {v: k for k, v in seq.items()}
    files = sorted(p for p in src.iterdir() if p.suffix.lower() in EXT)
    missing = [v for v in seq.values() if not (src / v).exists()]
    if missing:
        print("missing in --src: " + ", ".join(missing), file=sys.stderr)
        return 2
    man: dict = {"frames": {}, "photos": []}
    for f in files:
        name = by_file.get(f.name, re.sub(r"[^a-z0-9-]+", "-", f.stem.lower()))
        with Image.open(f) as raw:
            img = ImageOps.exif_transpose(raw).convert("RGB")
        w, h = save(img, out / f"{name}.webp", 1600)
        save(img, out / f"{name}-m.webp", 1000)
        rec = {"file": f"{name}.webp", "mfile": f"{name}-m.webp", "w": w, "h": h, "focus": focus.get(name, "50% 42%")}
        if re.fullmatch(r"sn-\d{2}", name):
            man["frames"][name] = rec
        else:
            man["photos"].append({"name": name, **rec})
        print(f"{f.name} -> {name}.webp {w}x{h}")
    man["frames"] = dict(sorted(man["frames"].items()))
    (out / "manifest.json").write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    print(f"manifest: {len(man['frames'])} frames, {len(man['photos'])} photos")
    return 0


if __name__ == "__main__":
    sys.exit(main())
