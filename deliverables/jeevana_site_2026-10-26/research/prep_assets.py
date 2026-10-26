#!/usr/bin/env python3
"""Chapter images. description: warm-graded film stills for chapters 01/02 (extracted from research/film/hero.mp4 at
keyframe indices 3 and 9 of 12; with fewer keyframes in hero.json the index is scaled) and the Champ-de-Mars photograph
for chapter 03 (keeps its background). usage: python3 research/prep_assets.py  (re-run when the final film lands)
outputs: site/assets/img/still-01@{800,1200}.webp, still-02@…, eiffel@{800,1200}.webp, research/film/stills.json"""
import json, subprocess, pathlib, os, tempfile
from PIL import Image, ImageEnhance
R = pathlib.Path(__file__).parent; FD = R / ('film_dawn' if (R / 'film_dawn/hero.json').exists() else 'film'); S = R.parent / 'site/assets/img'; S.mkdir(parents=True, exist_ok=True)
hj = json.loads((FD / 'hero.json').read_text()); ks = hj['keyframes_s']; n = len(ks)
def warm(im):
    im = ImageEnhance.Color(im.convert("RGB")).enhance(0.96); r, g, b = im.split()
    r = r.point(lambda v: min(255, int(v * 1.01))); b = b.point(lambda v: int(v * 0.985))
    return Image.merge('RGB', (r, g, b))
def save(im, name):
    for w in (800, 1200):
        x = im.copy(); x.thumbnail((w, w * 2)); x.save(S / f'{name}@{w}.webp', quality=80, method=6)
log = {}
for name, idx in (('still-01', 3), ('still-02', 9)):
    k = round(idx * (n - 1) / 11); t = min(ks[k], hj['seconds'] - 0.05)
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-ss', str(t), '-i', str(FD / 'hero.mp4'), '-frames:v', '1', d + '/f.png'], check=True)
        im = warm(Image.open(d + '/f.png')); save(im, name); log[name] = {'keyframe': k, 't': t, 'size': im.size}
im = warm(Image.open(R.parent / '_raw_assets/IMG-20260810-WA0005.jpg')); save(im, 'eiffel'); log['eiffel'] = {'size': im.size}
(R / 'film/stills.json').write_text(json.dumps(log, indent=1)); print(log)
