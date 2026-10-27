#!/usr/bin/env python3
"""Cut one figure with birefnet-general at capped resolution, decontaminate edges, trim the base sliver; update cutouts.json.
description: one process per photo to bound memory. inputs: key, source file, out dir. outputs: <out>/<key>.png + json entry."""
import sys, json, numpy as np
from pathlib import Path
from PIL import Image, ImageOps
from rembg import remove, new_session
from scipy import ndimage
key, fn, out = sys.argv[1], sys.argv[2], Path(sys.argv[3])
im = ImageOps.exif_transpose(Image.open(Path('_raw_assets') / fn)).convert('RGB'); im.thumbnail((7200, 3600))
cut = remove(im, session=new_session('birefnet-general'), alpha_matting=False)
A = np.asarray(cut.getchannel('A')); al = A > 128; lab, n = ndimage.label(al)
if n > 1:
    sizes = ndimage.sum(al, lab, range(1, n + 1)); al = lab == (int(np.argmax(sizes)) + 1)
hard = ndimage.binary_erosion(al, iterations=3)
rows = np.where(hard.any(axis=1))[0]; y1 = rows.max(); hard[y1 - int(0.004 * (y1 - rows.min())):y1 + 1, :] = False
a = ndimage.gaussian_filter(hard.astype(np.float32), 1.5) * 255
rgb = np.asarray(cut.convert('RGB')).astype(np.float32)
inner = ndimage.binary_erosion(hard, iterations=5).astype(np.float32)
num = np.stack([ndimage.gaussian_filter(rgb[..., c] * inner, 6) for c in range(3)], -1); den = ndimage.gaussian_filter(inner, 6)[..., None] + 1e-3
edge = ((a > 0) & (~inner.astype(bool)))[..., None]; rgb = np.where(edge, num / den, rgb)
o = Image.fromarray(np.clip(rgb, 0, 255).astype('uint8')).convert('RGBA'); o.putalpha(Image.fromarray(a.astype('uint8')))
crop = o.crop(o.getbbox())
if crop.height > 2600: crop = crop.resize((int(crop.width * 2600 / crop.height), 2600), Image.LANCZOS)
out.mkdir(exist_ok=True); crop.save(out / f'{key}.png')
A2 = np.asarray(crop.getchannel('A')); r2 = np.where(A2.max(axis=1) > 200)[0]; ground = (r2.max() + 1) / crop.height
jp = out / 'cutouts.json'; meta = json.loads(jp.read_text()) if jp.exists() else {}
meta[key] = {'file': f'{key}.png', 'source': fn, 'w': crop.width, 'h': crop.height, 'ground': round(float(ground), 4)}
jp.write_text(json.dumps(meta, indent=1)); print(key, crop.size, meta[key]['ground'])
