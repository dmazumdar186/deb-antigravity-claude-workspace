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


FIG_KEYS = ["sn-01", "sn-02", "sn-03", "sn-04", "sn-05", "sn-06", "photo-05", "alt-09", "sn-12", "portrait", "photo-03"]
FIG_KEEP_CONTACT = {"photo-05", "sn-06", "sn-05", "photo-03"}  # prone / seated: keep the hand/knee contact row
FIG_HEIGHTS = [2400, 1600, 1000]
PENCIL_KEYS = {"portrait"}  # art direction 2026-10-26: graphite renders only for the About portrait (A grade)
WASH_HEIGHTS = [1600, 1000]  # the wash is shown at ~18 % opacity: no need for the 2400 variant


def hires_cutout(key: str, meta: dict, cut: Image.Image, raw_dir: pathlib.Path, height: int = 2400) -> Image.Image:
    """Re-apply the cut-out's alpha to the full-resolution original (never upscales the photograph: only the
    smooth alpha mask is resampled). The crop offset inside the 2400-px working image is found by masked
    template matching (coarse at 1/8, refined at full scale)."""
    import cv2
    import numpy as np
    src = raw_dir / meta["source"]
    if not src.exists():
        return cut
    with Image.open(src) as r:
        orig = ImageOps.exif_transpose(r).convert("RGB")
    work = orig.copy()
    work.thumbnail((height * 2, height))
    s = orig.height / work.height
    if s <= 1.01:
        HI_SCALE[key] = 1.0
        return cut
    W = np.asarray(work, dtype=np.float32)
    T = np.asarray(cut.convert("RGB"), dtype=np.float32)
    M = (np.asarray(cut.getchannel("A")) > 200).astype(np.float32)
    k = 8
    Wc = cv2.resize(W, (W.shape[1] // k, W.shape[0] // k), interpolation=cv2.INTER_AREA)
    Tc = cv2.resize(T, (T.shape[1] // k, T.shape[0] // k), interpolation=cv2.INTER_AREA)
    Mc = (cv2.resize(M, (Tc.shape[1], Tc.shape[0]), interpolation=cv2.INTER_AREA) > 0.99).astype(np.float32)
    r = cv2.matchTemplate(Wc, Tc, cv2.TM_SQDIFF, mask=np.dstack([Mc] * 3))
    _, _, (cx, cy), _ = cv2.minMaxLoc(r)
    x0 = max(0, cx * k - k * 2); y0 = max(0, cy * k - k * 2)
    x1 = min(W.shape[1] - T.shape[1], cx * k + k * 2); y1 = min(W.shape[0] - T.shape[0], cy * k + k * 2)
    sub = W[y0:y1 + T.shape[0], x0:x1 + T.shape[1]]
    r = cv2.matchTemplate(sub, T, cv2.TM_SQDIFF, mask=np.dstack([M] * 3))
    _, _, (fx, fy), _ = cv2.minMaxLoc(r)
    ox, oy = x0 + fx, y0 + fy
    box = (round(ox * s), round(oy * s), round((ox + cut.width) * s), round((oy + cut.height) * s))
    rgb = orig.crop(box)
    a = cut.getchannel("A").resize(rgb.size, Image.LANCZOS)
    rgb.putalpha(a)
    HI_SCALE[key] = rgb.width / cut.width
    print(f"  {key}: offset {ox},{oy} in working image, x{s:.2f} -> {rgb.size[0]}x{rgb.size[1]} native")
    return rgb


def touch_up(key: str, im: Image.Image, ground: float) -> Image.Image:
    """Deterministic touch-up (brief_v2): ground clip, speck removal, 1 px erode + 1 px feather, portrait hand."""
    import numpy as np
    from scipy import ndimage
    a = np.asarray(im.getchannel("A"), dtype=np.float32)
    h, w = a.shape
    if key not in FIG_KEEP_CONTACT:
        g = int(round((ground + 0.01) * h))
        a[g:, :] = 0
    solid = a > 24
    lab, n = ndimage.label(solid)
    ys, xs = np.nonzero(solid)
    if n > 1 and len(ys):
        area = (ys.max() - ys.min() + 1) * (xs.max() - xs.min() + 1)
        sizes = ndimage.sum(solid, lab, range(1, n + 1))
        drop = np.isin(lab, [i + 1 for i, sz in enumerate(sizes) if sz < 0.002 * area])
        a[drop] = 0
        a[(a <= 24) & ~ndimage.binary_dilation(a > 24, iterations=2)] = 0
    if key == "portrait":
        filled = ndimage.binary_fill_holes(ndimage.binary_closing(a > 24, iterations=12))
        half = (a > 8) & (a < 120) & filled
        a[half] = 255 * 0.9
    er = ndimage.grey_erosion(a, size=(3, 3))
    a = ndimage.gaussian_filter(er, 1.0)
    im = im.copy()
    im.putalpha(Image.fromarray(np.clip(a, 0, 255).astype("uint8")))
    return im


def contour_path(im: Image.Image, target_h: int = 420) -> tuple[str, list[int]]:
    """Single simplified outer contour of the alpha (potrace), in a viewBox of the figure's own size."""
    import numpy as np
    import potrace
    from scipy import ndimage
    a = im.getchannel("A")
    sc = target_h / im.height
    small = np.asarray(a.resize((max(1, round(im.width * sc)), target_h), Image.LANCZOS)) > 110
    lab, n = ndimage.label(small)
    if n > 1:
        sizes = ndimage.sum(small, lab, range(1, n + 1))
        small = lab == (int(np.argmax(sizes)) + 1)
    small = ndimage.binary_fill_holes(small)
    pad = 4  # potracer fills dark (False) pixels: trace the inverted, padded mask so the figure is the filled shape
    small = np.pad(small, pad)
    plist = potrace.Bitmap(~small).trace(turdsize=40, alphamax=1.0, opttolerance=0.5)
    curve = max(plist, key=lambda c: len(c.segments)) if len(plist) else None
    if curve is None:
        return "", [im.width, im.height]
    f = 1 / sc

    def pt(p):
        return f"{(p.x - pad) * f:.0f} {(p.y - pad) * f:.0f}"
    d = [f"M{pt(curve.start_point)}"]
    for seg in curve.segments:
        if seg.is_corner:
            d.append(f"L{pt(seg.c)}L{pt(seg.end_point)}")
        else:
            d.append(f"C{pt(seg.c1)} {pt(seg.c2)} {pt(seg.end_point)}")
    return "".join(d) + "Z", [im.width, im.height]


def ingest_figs(cut_dir: pathlib.Path, pencil_dir: pathlib.Path | None, out: pathlib.Path, raw_dir: pathlib.Path,
                manifest: pathlib.Path) -> int:
    """--cutouts mode: hi-res cut-outs + touch-up + pencil -> site/assets/fig/<key>[-pencil]@<h>.webp + manifest.fig."""
    import numpy as np
    meta = json.loads((cut_dir / "cutouts.json").read_text(encoding="utf-8"))
    pmeta = {}
    if pencil_dir and (pencil_dir / "pencil.json").exists():
        pmeta = json.loads((pencil_dir / "pencil.json").read_text(encoding="utf-8"))
    out.mkdir(parents=True, exist_ok=True)
    man = json.loads(manifest.read_text(encoding="utf-8")) if manifest.exists() else {}
    man["fig"] = {}
    contours = {}
    for key in FIG_KEYS:
        m = meta[key]
        with Image.open(cut_dir / m["file"]) as c:
            cut = c.convert("RGBA")
        hi = hires_cutout(key, m, cut, raw_dir)
        hi = touch_up(key, hi, m["ground"])
        bb = hi.getchannel("A").point(lambda v: 255 if v > 24 else 0).getbbox()
        hi = hi.crop(bb)
        A = np.asarray(hi.getchannel("A"))
        rows = np.nonzero(A.max(axis=1) > 200)[0]
        ground = round((rows.max() + 1) / hi.height, 4) if len(rows) else 1.0
        srcset, pset = [], []
        full_h = hi.height
        heights = [hh for hh in FIG_HEIGHTS if hh <= full_h] or [full_h]
        if full_h < FIG_HEIGHTS[0] and full_h not in heights:
            heights = [full_h] + heights
        for hh in heights:
            v = hi if hh == full_h else hi.resize((round(hi.width * hh / full_h), hh), Image.LANCZOS)
            name = f"{key}@{hh}.webp"
            v.save(out / name, "WEBP", quality=92, method=6, exact=False)
            srcset.append([name, v.width, v.height])
        # flat graphite wash: the cut-out's own luminance, desaturated, alpha kept (drawn states S0-S8)
        wset = []
        L = hi.convert("L")
        wash = Image.merge("RGBA", (L, L, L, hi.getchannel("A")))
        for hh in [x for x in WASH_HEIGHTS if x <= full_h] or [full_h]:
            v = wash if hh == full_h else wash.resize((round(wash.width * hh / full_h), hh), Image.LANCZOS)
            name = f"{key}-wash@{hh}.webp"
            v.save(out / name, "WEBP", quality=88, method=6)
            wset.append([name, v.width, v.height])
        if key in PENCIL_KEYS and pencil_dir and (pencil_dir / f"{key}.png").exists():
            with Image.open(pencil_dir / f"{key}.png") as pr:
                pen = pr.convert("RGBA")
            # map the cut-out crop (in hi-res px) back to the pencil canvas by the shared aspect
            sc = pen.height / cut.height
            # bb is in hi-res px of the cut-out canvas; hi-res canvas = cut canvas * s
            s_hi = HI_SCALE.get(key, 1.0)
            pbox = tuple(round(v / s_hi * sc) for v in bb)
            pen = pen.crop(pbox)
            for hh in [x for x in heights if x <= pen.height * 1.0001] or [pen.height]:
                v = pen if hh >= pen.height else pen.resize((round(pen.width * hh / pen.height), hh), Image.LANCZOS)
                name = f"{key}-pencil@{hh}.webp"
                v.save(out / name, "WEBP", quality=92, method=6)
                pset.append([name, v.width, v.height])
        d, vb = contour_path(hi)
        contours[key] = {"vb": vb, "d": d}
        man["fig"][key] = {"w": hi.width, "h": hi.height, "ground": ground,
                           "srcset": srcset, "wash": wset, "pencil": pset}
        print(f"{key}: {hi.width}x{hi.height} ground {ground} variants {[x[2] for x in srcset]} wash {len(wset)} pencil {len(pset)} contour {len(d)} B")
    (out / "contours.json").write_text(json.dumps(contours, separators=(",", ":")), encoding="utf-8")
    manifest.write_text(json.dumps(man, indent=1) + "\n", encoding="utf-8")
    return 0


HI_SCALE: dict[str, float] = {}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--cutouts", default="", help="cutouts_v2 dir: hi-res cut-out figures -> --out (assets/fig)")
    ap.add_argument("--pencil", default="", help="pencil dir (graphite RGBA per key + pencil.json); optional")
    ap.add_argument("--raw", default="", help="raw photo dir for the full-resolution re-apply (default: cutouts/..)")
    ap.add_argument("--manifest", default="", help="manifest.json to extend with fig:{} (default: --out/manifest.json)")
    ap.add_argument("--src", required=False)
    ap.add_argument("--out", required=True)
    ap.add_argument("--sequence", default="")
    ap.add_argument("--focus", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--zoom", default="", help="name=minZoom,... extra crop for a frame (e.g. to crop a bystander out)")
    a = ap.parse_args()
    if a.cutouts:
        cd = pathlib.Path(a.cutouts); out = pathlib.Path(a.out)
        pd = pathlib.Path(a.pencil) if a.pencil and pathlib.Path(a.pencil).is_dir() else None
        if a.pencil and not pd:
            print(f"pencil dir absent ({a.pencil}): figures only; the site falls back to the interim drawing")
        return ingest_figs(cd, pd, out, pathlib.Path(a.raw) if a.raw else cd.parent,
                           pathlib.Path(a.manifest) if a.manifest else out / "manifest.json")
    if not a.src:
        ap.error("--src is required without --cutouts")
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
