#!/usr/bin/env python3
"""Chapter images (jury r2 item 1): three different stills from the film, three different crops and scales.
description: frames are extracted from research/film_dawn (else research/film) hero.mp4 at keyframe times and lightly warmed.
  still-01: Aśva Sañcālanāsana (keyframe 3), the whole lunge with its sky extended outward (shown full-bleed, off the left edge).
  still-02: Praṇāmāsana (keyframe 0), a tight crop from above the head to the joined hands at the chest.
  still-03: Praṇāmāsana (keyframe 11), small in a lot of sky: the frame's top row is extended upward (and the sides outward)
            so the figure is <= 35 % of the image height.
usage: python3 research/prep_assets.py   outputs: site/assets/img/still-0N@{800,1200}.webp, research/film/stills.json"""
import json, subprocess, pathlib, tempfile
import numpy as np
from PIL import Image, ImageEnhance, ImageFilter
R = pathlib.Path(__file__).parent; FD = R / ('film_omni' if (R / 'film_omni/hero.json').exists() else 'film_dawn' if (R / 'film_dawn/hero.json').exists() else 'film')
S = R.parent / 'site/assets/img'; S.mkdir(parents=True, exist_ok=True)
hj = json.loads((FD / 'hero.json').read_text()); ks = hj['keyframes_s']; n = len(ks)
boxes = json.loads((R / 'film/figure_boxes.json').read_text())['landscape']
def warm(im):
    im = ImageEnhance.Color(im.convert('RGB')).enhance(0.96); r, g, b = im.split()
    return Image.merge('RGB', (r.point(lambda v: min(255, int(v * 1.01))), g, b.point(lambda v: int(v * 0.985))))
def frame(idx):
    k = round(idx * (n - 1) / 11); t = min(ks[k], hj['seconds'] - 0.05)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(t), '-i', str(FD / hj['landscape']), '-frames:v', '1', d + '/f.png'], check=True)
        return warm(Image.open(d + '/f.png')), k
def save(im, name):
    for w in (800, 1200):
        x = im.copy(); x.thumbnail((w, w * 3)); x.save(S / f'{name}@{w}.webp', quality=82, method=6)
log = {}
def extend(im, top, bottom, side):  # extend the film's own sky outward (edge rows/columns, softened) so feathers fall on sky
    a = np.asarray(im).astype(np.float32); H, W, _ = a.shape; HH, WW = H + top + bottom, W + 2 * side
    c = np.zeros((HH, WW, 3), np.float32); c[top:top + H, side:side + W] = a
    c[:top, side:side + W] = a[:4].mean(axis=0, keepdims=True); c[top + H:, side:side + W] = a[-4:].mean(axis=0, keepdims=True)
    c[:, :side] = c[:, side:side + 2].mean(axis=1, keepdims=True); c[:, side + W:] = c[:, side + W - 2:side + W].mean(axis=1, keepdims=True)
    out = Image.fromarray(c.clip(0, 255).astype(np.uint8)); blur = out.filter(ImageFilter.GaussianBlur(6)); m = Image.new('L', out.size, 0)
    m.paste(255, (side + 24 if side else 0, top + 24 if top else 0, side + W - 24 if side else WW, top + H - 24 if bottom else HH)); return Image.composite(out, blur, m.filter(ImageFilter.GaussianBlur(16)))
im, k = frame(3); W, H = im.size
c1 = extend(im, int(.12 * H), int(.06 * H), int(.22 * W)); save(c1, 'still-01'); log['still-01'] = {'keyframe': k, 'size': c1.size}
im, k = frame(0); W, H = im.size; b = boxes[0]['box']; cx = (b[0] + b[2]) / 2
cw = .50 * W; x0 = int(cx * W - cw / 2); y0 = int(max(0, b[1] - .06) * H); c2 = im.crop((x0, y0, int(x0 + cw), int(.48 * H))); save(c2, 'still-02'); log['still-02'] = {'keyframe': k, 'size': c2.size, 'crop': [x0, y0]}
im, k = frame(11); W, H = im.size; b = boxes[min(k, 11)]['box']
a = np.asarray(im).astype(np.float32); figh = (b[3] - b[1]) * H; HH = int(figh / .33); top = HH - H; WW = int(W * 1.25); pad = (WW - W) // 2
c = np.zeros((HH, WW, 3), np.float32); c[top:, pad:pad + W] = a
c[:top, pad:pad + W] = a[:4].mean(axis=0, keepdims=True); c[:, :pad] = c[:, pad:pad + 2].mean(axis=1, keepdims=True); c[:, pad + W:] = c[:, pad + W - 2:pad + W].mean(axis=1, keepdims=True)
c3 = Image.fromarray(c.clip(0, 255).astype(np.uint8)); blur = c3.filter(ImageFilter.GaussianBlur(6)); m = Image.new('L', c3.size, 0); m.paste(255, (pad + 24, top + 24, pad + W - 24, HH))
c3 = Image.composite(c3, blur, m.filter(ImageFilter.GaussianBlur(16))); save(c3, 'still-03'); log['still-03'] = {'keyframe': k, 'size': c3.size, 'figure_height_frac': round(figh / HH, 3)}
(R / 'film/stills.json').write_text(json.dumps(log, indent=1)); print(log)
