#!/usr/bin/env python3
"""Scrub-ready, widened site encodes of the 3:4 film (operator 2026-10-26: 3:4 on all devices; jury r2 items 8/17/18).
description: the film's own sky is extended sideways so every window feather falls on sky, never on her: the empty plate
  (research/keyframes/dawn/plate.jpg, scaled to the film) sits in the centre and its edge columns are extended to a
  1330 x 1108 canvas (aspect 1.2, pad 251 px a side); the film is laid over it with a 64 px horizontal alpha blend at its
  own edges. Outputs site/assets/film/hero.mp4 (crf 23..), hero-phone.mp4 (720 px wide, crf 25..), poster.jpg (widened),
  all H.264 yuv420p, crf from 20 with -tune grain + aq-mode 3 (round 3: no sky banding), tagged BT.709 (Chromium decodes untagged HD as 709; a 601 encode shifted the sky ~5 levels), GOP 12, +faststart; crf rises until each fits its budget (6 MB / 4 MB).
usage: python3 research/fit_film.py   (then node research/stamp.mjs)"""
import json, subprocess, pathlib, tempfile
import numpy as np
from PIL import Image, ImageFilter
R = pathlib.Path(__file__).parent; FD = R / ('film_omni' if (R / 'film_omni/hero.json').exists() else 'film_dawn' if (R / 'film_dawn/hero.json').exists() else 'film')
OUT = R.parent / 'site/assets/film'; OUT.mkdir(parents=True, exist_ok=True)
meta = json.loads((FD / 'hero.json').read_text()); src = FD / meta['landscape']
import subprocess as _sp
_dims = _sp.run(['ffprobe', '-v', 'error', '-select_streams', 'v', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', str(src)], capture_output=True, text=True).stdout.strip().split(',')
H0, WW, BL = 1108, 1330, 64; W0 = int(round(int(_dims[0]) * H0 / int(_dims[1]) / 2) * 2); PAD = (WW - W0) // 2  # 3:4 → 828, 9:16 → 624; the window stays 1330 x 1108
tmp = pathlib.Path(tempfile.mkdtemp())
plate_p = R / 'keyframes/dawn/plate.jpg'
def cover(im, w, h):
    s_ = max(w / im.width, h / im.height); im = im.resize((round(im.width * s_), round(im.height * s_)), Image.LANCZOS); x = (im.width - w) // 2; y = (im.height - h) // 2; return im.crop((x, y, x + w, y + h))
plate = cover(Image.open(plate_p).convert('RGB'), W0, H0) if plate_p.exists() else None
def widen(frame):
    a = np.asarray(frame).astype(np.float32); base = np.asarray(plate).astype(np.float32) if plate is not None else a
    bg = np.zeros((H0, WW, 3), np.float32); bg[:, PAD:PAD + W0] = base
    bg[:, :PAD] = base[:, :2].mean(axis=1, keepdims=True); bg[:, PAD + W0:] = base[:, -2:].mean(axis=1, keepdims=True)
    bgi = Image.fromarray(bg.clip(0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(2)); bg = np.asarray(bgi).astype(np.float32)
    al = np.ones(W0, np.float32); ramp = np.linspace(0, 1, BL); al[:BL] = ramp; al[-BL:] = ramp[::-1]
    out = bg.copy(); out[:, PAD:PAD + W0] = a * al[None, :, None] + bg[:, PAD:PAD + W0] * (1 - al[None, :, None])
    return Image.fromarray(out.clip(0, 255).astype(np.uint8))
# background still + alpha mask for ffmpeg
widen(plate if plate is not None else Image.new('RGB', (W0, H0))).save(tmp / 'bg.png')
mask = np.tile(np.concatenate([np.linspace(0, 255, BL), np.full(W0 - 2 * BL, 255), np.linspace(255, 0, BL)])[None, :], (H0, 1)).astype(np.uint8)
Image.fromarray(mask, 'L').save(tmp / 'mask.png')
# widened poster from the film's poster
widen(cover(Image.open(FD / meta['poster']).convert('RGB'), W0, H0)).save(OUT / 'poster.jpg', quality=86)
FC = f"[1:v]scale={W0}:{H0}:flags=lanczos,format=rgb24[f];[2:v]format=gray,loop=-1:1:0[m];[f][m]alphamerge[fa];[0:v][fa]overlay={PAD}:0:shortest=1"
log = {}
for name, crf, scale, cap in (('hero.mp4', 20, None, 6 * 2**20), ('hero-phone.mp4', 20, 720, 4 * 2**20)):
    while True:
        vf = FC + (f",scale={scale}:-2:flags=lanczos" if scale else '') + ',scale=out_color_matrix=bt709:out_range=tv,format=yuv420p'
        subprocess.run(['ffmpeg', '-y', '-loglevel', 'error', '-loop', '1', '-i', str(tmp / 'bg.png'), '-i', str(src), '-loop', '1', '-i', str(tmp / 'mask.png'),
                        '-filter_complex', vf, '-an', '-c:v', 'libx264', '-preset', 'slow', '-crf', str(crf), '-tune', 'grain', '-x264-params', 'aq-mode=3', '-g', '12', '-keyint_min', '12', '-sc_threshold', '0',
                        '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709', '-color_range', 'tv', '-movflags', '+faststart', '-t', str(meta['seconds']), str(OUT / name)], check=True)
        size = (OUT / name).stat().st_size
        if size <= cap or crf >= 34: break
        crf += 1
    log[name] = {'crf': crf, 'bytes': size}
log['wide'] = {'width': WW, 'height': H0, 'pad': PAD, 'orig_width': W0, 'blend': BL}
(R / 'film/fit.json').write_text(json.dumps(log, indent=1)); print(log)
