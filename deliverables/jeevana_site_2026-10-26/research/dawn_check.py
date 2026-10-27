#!/usr/bin/env python3
"""Pixel checks for the dawn stage (operator 2026-10-26), called by functional.mjs with a manifest JSON on argv[1].
manifest: {plate, shots:[{kind:'seam', png, film:[l,t,r,b]}, {kind:'stage', png, film}, {kind:'contrast', png, texts:[{rect,color}]}]}
(a) seam ΔE76 < 4: colour 4 px outside vs min(90 px, 8.5 % of the window width — the figure-free margin) inside each vertical window edge at 8 figure-free heights (same height);
    horizontal edges inside the viewport: 4 px outside vs 4 px inside at 8 x positions.
(b) luminance step ≤ 6 % of full scale: |mean(L[x..x+8]) − mean(L[x−8..x])| (relative luminance 0..1) from 120 px outside to the figure-free margin inside each window edge, same rows/columns.
(c) stage (film hidden) at the window midline, window centre x, vs plate median row at 50 %: ΔE76 < 4.
contrast ≥ 4.5: text colour vs median background under each text box (text made transparent for that shot)."""
import json, sys
import numpy as np
from PIL import Image
m = json.load(open(sys.argv[1]))
def lab(c):
    c = np.asarray(c, float) / 255; c = np.where(c > .04045, ((c + .055) / 1.055) ** 2.4, c / 12.92)
    x, y, z = np.dot([[.4124, .3576, .1805], [.2126, .7152, .0722], [.0193, .1192, .9505]], c) / np.array([.95047, 1, 1.08883])
    f = lambda v: v ** (1 / 3) if v > .008856 else 7.787 * v + 16 / 116
    return np.array([116 * f(y) - 16, 500 * (f(x) - f(y)), 200 * (f(y) - f(z))])
def lum(c):
    c = np.asarray(c, float) / 255; c = np.where(c > .04045, ((c + .055) / 1.055) ** 2.4, c / 12.92); return float(np.dot(c, [.2126, .7152, .0722]))
pl = np.asarray(Image.open(m['plate']).convert('RGB')).astype(float); ph = pl.shape[0]
plate50 = np.median(pl[int(ph * .5) - 2:int(ph * .5) + 3].reshape(-1, 3), axis=0)
FR = [.02, .05, .08, .11, .25, .5, .75, .89, .92, .95, .98]  # r2 item 17: 25/50/75 % too (the widened film's sides are sky)
out = {'seam': [], 'step': [], 'stage': [], 'contrast': []}
for s in m['shots']:
    im = np.asarray(Image.open(s['png']).convert('RGB')).astype(float); H, W, _ = im.shape
    px = lambda x, y: np.median(im[int(min(H - 3, max(2, y))) - 2:int(min(H - 3, max(2, y))) + 3, int(min(W - 3, max(2, x))) - 2:int(min(W - 3, max(2, x))) + 3].reshape(-1, 3), axis=0)
    L = lambda x, y: lum(im[int(min(H - 1, max(0, y))), int(min(W - 1, max(0, x)))])
    tag = s.get('tag', '')
    if s['kind'] == 'seam':
        l, t, r, b = s['film']; dmax = 0; smax = 0; n = 0; ins = min(90, 0.085 * (r - l)); reach = int(min(120, 0.085 * (r - l)))
        for edge, sign in ((l, 1), (r, -1)):
            if not (4 < edge < W - 4): continue
            for f in FR:
                y = t + (b - t) * f
                if not (2 < y < H - 2): continue
                d = float(np.linalg.norm(lab(px(edge - 4 * sign, y)) - lab(px(edge + ins * sign, y)))); dmax = max(dmax, d); n += 1
                prof = np.array([L(x, y) for x in (range(int(edge - 120), int(edge + reach) + 1) if sign > 0 else range(int(edge - reach), int(edge + 121)))])
                st = max(abs(prof[i:i + 9].mean() - prof[i - 9:i].mean())  for i in range(9, len(prof) - 9))
                smax = max(smax, st)
        for edge, sign in ((t, 1), (b, -1)):
            if not (4 < edge < H - 4): continue
            for f in (.1, .2, .3, .4, .6, .7, .8, .9):
                x = l + (r - l) * f
                d = float(np.linalg.norm(lab(px(x, edge - 4 * sign)) - lab(px(x, edge + 4 * sign)))); dmax = max(dmax, d); n += 1
                rv = int(min(120, 0.12 * (b - t)))  # figure-free margin inside the top/bottom edge
                prof = np.array([L(x, y) for y in (range(int(edge - 120), int(edge + rv) + 1) if sign > 0 else range(int(edge - rv), int(edge + 121)))])
                st = max(abs(prof[i:i + 9].mean() - prof[i - 9:i].mean())  for i in range(9, len(prof) - 9))
                smax = max(smax, st)
        redge = max(float(np.linalg.norm(lab(im[int(H * f), W - 1]) - lab(px(W - 10, H * f)))) for f in (.1, .3, .5, .7, .9))  # r2 item 10: sky reaches the last column
        out.setdefault('rightcol', []).append({'tag': tag, 'dE': round(redge, 2)})
        out['seam'].append({'tag': tag, 'pairs': n, 'dE': round(dmax, 2)}); out['step'].append({'tag': tag, 'step': round(smax, 3)})
    elif s['kind'] == 'panelstep':
        l, t, r, b = s['rect']; smax = 0; fe = 40  # profile: 30 px outside to 40 px inside the panel edge (the outer quarter of the feather)
        for f in (.2, .4, .6, .8):
            for edge, axis, sign in ((l, 'x', 1), (r, 'x', -1), (t, 'y', 1), (b, 'y', -1)):
                if axis == 'x':
                    y = t + (b - t) * f; xs = range(int(edge - 30 * sign), int(edge + fe * sign), sign); prof = np.array([L(x, y) for x in xs if 0 <= x < W])
                else:
                    x = l + (r - l) * f; ys = range(int(edge - 30 * sign), int(edge + fe * sign), sign); prof = np.array([L(x, y) for y in ys if 0 <= y < H])
                if len(prof) > 20 and 0 < edge < (W if axis == 'x' else H) - 1:  # edges at the viewport boundary (full bleed) have no visible edge
                    smax = max(smax, max(abs(prof[i:i + 9].mean() - prof[i - 9:i].mean()) for i in range(9, len(prof) - 9)))
        out.setdefault('panelstep', []).append({'tag': tag, 'step': round(smax, 3)})
    elif s['kind'] == 'panelalpha':
        A, B, C = [np.asarray(Image.open(q).convert('RGB')).astype(float) for q in s['pngs']]; l, t, r, b = s['rect']; res = []
        for f in (.15, .35, .65, .85):
            for x, y in ((l + 1, t + (b - t) * f), (r - 2, t + (b - t) * f), (l + (r - l) * f, t + 1), (l + (r - l) * f, b - 2)):
                x = int(min(W - 1, max(0, x))); y = int(min(H - 1, max(0, y))); d = C[y, x] - B[y, x]; k = int(np.argmax(np.abs(d)))
                if abs(d[k]) >= 40: res.append(float(max(0, (A[y, x][k] - B[y, x][k]) / d[k])))
        out.setdefault('panelalpha', []).append({'tag': tag, 'n': len(res), 'max': round(max(res), 3) if res else None})
    elif s['kind'] == 'figheight':
        a = np.asarray(Image.open(s['png']).convert('RGB')).astype(float); med = np.median(a, axis=1, keepdims=True)
        rows = np.where((np.abs(a - med).max(axis=2) > 45).sum(axis=1) > a.shape[1] * 0.01)[0]
        out['figheight'] = round(float((rows.max() - rows.min()) / a.shape[0]) if len(rows) else 0, 3)
    elif s['kind'] == 'stage':
        l, t, r, b = s['film']; c = px((l + r) / 2, (t + b) / 2)
        out['stage'].append({'tag': tag, 'dE': round(float(np.linalg.norm(lab(c) - lab(plate50))), 2)})
    else:
        worst = 99
        for tx in s['texts']:
            x0, y0, x1, y1 = [int(v) for v in tx['rect']]; x0, y0 = max(0, x0), max(0, y0); x1, y1 = min(W, x1), min(H, y1)
            if x1 - x0 < 2 or y1 - y0 < 2: continue
            bg = np.median(im[y0:y1, x0:x1].reshape(-1, 3), axis=0); r_, g_, b_, a_ = tx['color']; fg = np.array([r_, g_, b_]) * a_ + bg * (1 - a_)
            l1, l2 = lum(fg), lum(bg); cr = (max(l1, l2) + .05) / (min(l1, l2) + .05)
            if cr < worst: worst = cr; wtxt = tx.get('s', '')
        out['contrast'].append({'tag': tag, 'min': round(worst, 2), 'at': wtxt if worst < 99 else ''})
print(json.dumps(out))
