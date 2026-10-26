#!/usr/bin/env python3
"""Scrub-ready site encodes of the 3:4 film (operator 2026-10-26: 3:4 on all devices, hero-m.mp4 unused).
description: re-encodes research/film/<landscape> into site/assets/film/hero.mp4 (native size, crf 23) and
  hero-phone.mp4 (600 px wide, crf 25), both H.264 yuv420p, GOP 12 (short keyframe interval so seeks land fast),
  no audio, +faststart; raises crf by 1 until each fits its budget (6 MB desktop / 4 MB phone).
usage: python3 research/fit_film.py   (then node research/stamp.mjs)"""
import json, subprocess, pathlib
R = pathlib.Path(__file__).parent; OUT = R.parent / 'site/assets/film'; OUT.mkdir(parents=True, exist_ok=True)
src = R / 'film' / json.loads((R / 'film/hero.json').read_text())['landscape']
log = {}
for name, crf, vf, cap in (('hero.mp4', 23, 'scale=trunc(iw/2)*2:trunc(ih/2)*2', 6 * 2**20), ('hero-phone.mp4', 25, 'scale=600:-2:flags=lanczos', 4 * 2**20)):
    while True:
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-i', str(src), '-an', '-vf', vf, '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf),
                        '-g', '12', '-keyint_min', '12', '-sc_threshold', '0', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', str(OUT / name)], check=True)
        size = (OUT / name).stat().st_size
        if size <= cap or crf >= 34: break
        crf += 1
    log[name] = {'crf': crf, 'bytes': size}
(R / 'film/fit.json').write_text(json.dumps(log, indent=1)); print(log)
