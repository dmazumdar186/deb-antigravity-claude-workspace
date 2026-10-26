#!/usr/bin/env python3
"""Deterministic graphite-drawing renderer for RGBA cut-outs (cover drawing that dissolves into the photo).

description: Per cut-out: lifts dark garments ~1.5 EV, CLAHE-equalises luminance, builds a fine dodge-blend
  pencil layer (blur ~0.5 % of figure height), directional hatching along the local isophotes (+-30 deg jitter,
  midtones only), a 1 px gradient-weighted contour layer (continuous silhouette with a lost edge on the lit side,
  suppressed inside dark garments), an S-curve capping the darkest value at ~28 % grey, procedural paper-tooth
  grain in tonal areas, pure paper in the top highlights, a feathered silhouette and a light hatched contact
  shadow. Same canvas/aspect as the cut-out, scaled to --height. Seeded, so reruns are byte-identical.
inputs: --src DIR of <key>.png RGBA cut-outs (optional cutouts.json is ignored except for ordering),
  --out DIR, --height INT (default 2400), --keys k1,k2 (optional subset).
outputs: <out>/<key>.png RGBA (graphite colour, alpha = tone), <out>/<key>-on-paper.jpg preview on #F3EEE4,
  <out>/pencil.json {key: {w, h, png_bytes, jpg_bytes}}.
"""
import argparse, json
from pathlib import Path
import numpy as np, cv2
from PIL import Image

INK = (38, 36, 40)            # graphite colour; alpha carries the tone
PAPER = (0xF3, 0xEE, 0xE4)
P = dict(lift_ev=1.5, clahe_clip=2.0, clahe_tile=8, dodge_frac=0.005, max_dark=0.72, hatch_op=0.5,
         contour_op=0.45, grain=0.10, paper_pct=15, feather=1.5, alpha_levels=48)


def tooth(h, w, rng):
    n = rng.random((h, w)).astype(np.float32)
    fine = cv2.GaussianBlur(n, (0, 0), 0.8)
    fib = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), sigmaX=3.0, sigmaY=0.6)
    t = 0.65 * fine + 0.35 * fib
    t = (t - t.mean()) / (t.std() + 1e-6)
    return np.clip(t * 0.5 + 0.5, 0, 1)            # ~0..1, mean .5


def hatch_layer(theta, h, w, rng, period=5.0, nb=12):
    """Strokes along angle theta (radians, per pixel). 1 on stroke, 0 between."""
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    out = np.zeros((h, w), np.float32); acc = np.zeros((h, w), np.float32)
    bins = np.linspace(0, np.pi, nb, endpoint=False)
    wob = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 6) * 40
    brk = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), sigmaX=4, sigmaY=4)
    brk = np.clip((brk - brk.mean()) / (brk.std() + 1e-6) * 0.6 + 0.75, 0, 1)
    for b in bins:
        d = np.abs(np.angle(np.exp(1j * 2 * (theta - b)))) / 2      # angular distance mod pi
        wt = np.clip(1 - d / (np.pi / nb), 0, 1)
        if wt.max() == 0: continue
        nrm = -xx * np.sin(b) + yy * np.cos(b) + wob
        ph = np.mod(nrm, period) / period
        line = np.clip(1 - np.abs(ph - 0.5) * period / 0.8, 0, 1)    # ~1.6 px stroke
        out += wt * line; acc += wt
    return out / np.maximum(acc, 1e-6) * brk


def render(src, height, seed):
    im = Image.open(src).convert('RGBA')
    s = height / im.height
    im = im.resize((max(1, round(im.width * s)), height), Image.LANCZOS)
    a = np.asarray(im).astype(np.float32) / 255
    rgb, al = a[..., :3], a[..., 3]
    h, w = al.shape
    rng = np.random.default_rng(seed)
    m = (al > 0.5).astype(np.uint8)
    ys = np.where(m.any(1))[0]; fig_h = (ys[-1] - ys[0] + 1) if len(ys) else h
    L = (0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2])
    L = np.where(al > 0.02, L, 1.0)
    # 1. lift darks ~1.5 EV (shadow-weighted so highlights don't clip)
    g = 2 ** P['lift_ev']
    lifted = L * g / (1 + L * (g - 1))
    # 2. CLAHE
    cl = cv2.createCLAHE(P['clahe_clip'], (P['clahe_tile'], P['clahe_tile']))
    E = cl.apply((lifted * 255).astype(np.uint8)).astype(np.float32) / 255
    E = np.where(al > 0.02, E, 1.0)
    # 3. dodge pencil, small blur
    sig = max(1.5, P['dodge_frac'] * fig_h / 2.5)
    inv = 1 - E; bl = cv2.GaussianBlur(inv, (0, 0), sig)
    dodge = np.clip(E / np.maximum(1 - bl, 1e-3), 0, 1)
    # 4. base tone darkness from smoothed E with S-curve
    Es = cv2.GaussianBlur(E, (0, 0), 1.2)
    t = 1 - Es
    t = np.clip((t - 0.08) / 0.85, 0, 1)
    t = t * t * (3 - 2 * t)                         # S-curve
    # 5. hatching along isophotes
    Lb = cv2.GaussianBlur(lifted, (0, 0), 4)
    gx = cv2.Sobel(Lb, cv2.CV_32F, 1, 0, ksize=3); gy = cv2.Sobel(Lb, cv2.CV_32F, 0, 1, ksize=3)
    J = [cv2.GaussianBlur(v, (0, 0), 12) for v in (gx * gx, gy * gy, gx * gy)]
    theta = 0.5 * np.arctan2(2 * J[2], J[0] - J[1]) + np.pi / 2       # tangent of isophote
    jit = (cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 40) - 0.5)
    jit = jit / (np.abs(jit).max() + 1e-6) * np.deg2rad(30)
    theta = theta + jit
    hat = hatch_layer(theta, h, w, rng)
    hat2 = hatch_layer(theta + np.deg2rad(55), h, w, rng, period=6.0)
    mid = np.exp(-((t - 0.45) / 0.22) ** 2)
    deep = np.clip((t - 0.6) / 0.3, 0, 1)
    hatched = t * (1 - P['hatch_op'] * mid) + P['hatch_op'] * mid * t * 1.9 * hat
    hatched = hatched + deep * 0.35 * t * (hat2 - 0.5)
    # 6. combine with dodge strokes
    D = 1 - dodge
    tone = np.clip(0.62 * hatched + 0.55 * D, 0, 1)
    # 7. contour layer (1 px), gradient weighted
    Lc = cv2.GaussianBlur(E, (0, 0), 1.0)
    mag = np.hypot(cv2.Sobel(Lc, cv2.CV_32F, 1, 0), cv2.Sobel(Lc, cv2.CV_32F, 0, 1))
    can = cv2.Canny((Lc * 255).astype(np.uint8), 40, 95, L2gradient=True).astype(np.float32) / 255
    dark_garm = cv2.GaussianBlur((L < 0.22).astype(np.float32), (0, 0), 6)
    strong = np.clip(mag / (np.percentile(mag[m > 0], 97) + 1e-6), 0, 1) if m.any() else mag
    can *= np.clip(strong * 1.4, 0.25, 1) * (1 - 0.85 * dark_garm * (strong < 0.7))
    # silhouette
    sil = cv2.morphologyEx(m, cv2.MORPH_GRADIENT, np.ones((2, 2), np.uint8)).astype(np.float32)
    inner = cv2.GaussianBlur(np.where(m > 0, L, 0), (0, 0), 8) / np.maximum(cv2.GaussianBlur(m.astype(np.float32), (0, 0), 8), 1e-3)
    lit = np.clip((inner - 0.62) / 0.25, 0, 1)
    breaks = cv2.GaussianBlur(rng.random((h, w)).astype(np.float32), (0, 0), 25)
    breaks = np.clip((breaks - breaks.mean()) * 8 + 0.6, 0, 1)
    silw = sil * (1 - 0.9 * lit * (1 - 0.5 * breaks)) * 0.85
    cont = np.maximum(can, silw)
    cont = cv2.GaussianBlur(cont, (0, 0), 0.5)
    tone = 1 - (1 - tone) * (1 - P['contour_op'] * np.clip(cont * 1.6, 0, 1))
    # 8. highlights pure paper (top ~15 % of figure luminance)
    if m.any():
        thr = np.percentile(Es[m > 0], 100 - P['paper_pct'])
        tone *= np.clip((thr - Es) / 0.04 + 0.0, 0, 1) * 0.0 + np.where(Es >= thr, np.clip(1 - (Es - thr) / 0.03, 0, 1), 1)
    # 9. cap darkness, paper grain in tonal areas
    tone = np.clip(tone, 0, 1) * P['max_dark']
    tt = tooth(h, w, rng)
    tonal = np.clip(tone / 0.12, 0, 1)
    tone = tone * (1 - P['grain'] * 2 * (tt - 0.5) * tonal - 0.04 * tonal)
    # 10. feather silhouette
    fa = cv2.GaussianBlur(cv2.erode(m, np.ones((2, 2), np.uint8)).astype(np.float32), (0, 0), P['feather'])
    fa = np.maximum(fa, silw * 0.9)
    tone = tone * np.clip(fa, 0, 1)
    # 11. contact shadow
    if len(ys):
        bot = ys[-1]; foot = m[max(0, bot - int(0.04 * fig_h)):bot + 1].any(0)
        xs = np.where(foot)[0]
        if len(xs):
            cx = (xs[0] + xs[-1]) / 2; rx = (xs[-1] - xs[0]) / 2 + 0.03 * fig_h; ry = 0.012 * fig_h
            yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
            e = np.clip(1 - ((xx - cx) / rx) ** 2 - ((yy - bot) / ry) ** 2, 0, 1) ** 0.8
            sh = hatch_layer(np.full((h, w), np.deg2rad(8), np.float32), h, w, rng, period=4.5)
            sha = e * (0.10 + 0.22 * sh) * (1 - m)
            tone = np.maximum(tone, sha)
    tone = np.clip(tone, 0, P['max_dark'])
    q = P['alpha_levels']
    tone = np.round(tone / P['max_dark'] * (q - 1)) / (q - 1) * P['max_dark']
    return (tone * 255).astype(np.uint8)


def save(key, A, out):
    h, w = A.shape
    q = P['alpha_levels']; lv = np.unique(A)
    idx = np.searchsorted(lv, A).astype(np.uint8)
    pal = Image.fromarray(idx, 'P'); pal.putpalette(list(INK) * len(lv))
    pal.info['transparency'] = bytes(lv.tolist())
    pp = out / f'{key}.png'; pal.save(pp, optimize=True, transparency=bytes(lv.tolist()))
    f = A.astype(np.float32)[..., None] / 255
    prev = (np.array(PAPER) * (1 - f) + np.array(INK) * f).astype(np.uint8)
    jp = out / f'{key}-on-paper.jpg'; Image.fromarray(prev).save(jp, quality=88)
    return {'w': w, 'h': h, 'png_bytes': pp.stat().st_size, 'jpg_bytes': jp.stat().st_size}


def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--height', type=int, default=2400); ap.add_argument('--keys', default='')
    a = ap.parse_args(); src, out = Path(a.src), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    keys = [k for k in a.keys.split(',') if k] or sorted(p.stem for p in src.glob('*.png'))
    mf = out / 'pencil.json'; meta = json.loads(mf.read_text()) if mf.exists() else {}
    for i, k in enumerate(keys):
        A = render(src / f'{k}.png', a.height, seed=sum(map(ord, k)))
        meta[k] = save(k, A, out); print(k, meta[k], flush=True)
    meta['_params'] = P
    mf.write_text(json.dumps(meta, indent=1))


if __name__ == '__main__':
    main()
