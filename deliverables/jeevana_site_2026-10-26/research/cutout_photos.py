#!/usr/bin/env python3
"""Cut the subject out of each photo (rembg isnet-general-use, alpha matting) and write RGBA PNGs.

description: Reads the raw photos, EXIF-transposes, downsizes to --height, removes the background, crops to the
  alpha bbox with a margin, and writes <out>/<key>.png plus cutouts.json {key: {file, w, h, bbox, ground}}.
  Deterministic for a given model file; ~13 s per photo on CPU.
inputs: --src DIR, --out DIR, --height INT (default 2400), --map key=file,... (sn-01=_DAV5297.jpg,...)
outputs: PNGs + cutouts.json; prints one line per photo.
"""
import argparse, json, sys, time
from pathlib import Path
from PIL import Image, ImageOps
from rembg import remove, new_session

def main():
    ap = argparse.ArgumentParser(); ap.add_argument('--src', required=True); ap.add_argument('--out', required=True)
    ap.add_argument('--height', type=int, default=2400); ap.add_argument('--map', required=True)
    a = ap.parse_args(); src, out = Path(a.src), Path(a.out); out.mkdir(parents=True, exist_ok=True)
    pairs = [p.split('=', 1) for p in a.map.split(',') if p]
    session = new_session('isnet-general-use'); human = new_session('u2net_human_seg'); done = {}; meta = {}
    import numpy as np
    from scipy import ndimage
    for key, fn in pairs:
        if fn in done:
            import shutil; shutil.copy(out / f'{done[fn]}.png', out / f'{key}.png')
            meta[key] = dict(meta[done[fn]]); meta[key]['file'] = f'{key}.png'; meta[key]['alias_of'] = done[fn]; print(f'{key}\tcopy of {done[fn]}'); continue
        t = time.time(); im = ImageOps.exif_transpose(Image.open(src / fn)).convert('RGB')
        im.thumbnail((a.height * 2, a.height))
        cut = remove(im, session=session, alpha_matting=True, alpha_matting_foreground_threshold=250,
                     alpha_matting_background_threshold=10, alpha_matting_erode_size=12)
        hm = remove(im, session=human, only_mask=True)  # person-only mask: drops mats, poles, monuments, bystanders
        al = np.asarray(cut.getchannel('A'), dtype=np.float32) / 255.0
        h = np.asarray(hm.convert('L') if hasattr(hm, 'convert') else Image.fromarray(hm).convert('L'), dtype=np.float32) / 255.0
        h = ndimage.binary_dilation(h > 0.5, iterations=6).astype(np.float32)  # soft tolerance around the person
        al = al * h
        lab, n = ndimage.label(al > 0.5)
        if n > 1:  # keep the largest connected component only (removes floating remnants)
            sizes = ndimage.sum(al > 0.5, lab, range(1, n + 1)); keep = int(np.argmax(sizes)) + 1
            al = al * (lab == keep)
        cut.putalpha(Image.fromarray((al * 255).astype('uint8')))
        bb = cut.getbbox()
        if not bb: print(f'{key}\tEMPTY', file=sys.stderr); continue
        m = 24; x0, y0, x1, y1 = max(0, bb[0]-m), max(0, bb[1]-m), min(cut.width, bb[2]+m), min(cut.height, bb[3]+m)
        crop = cut.crop((x0, y0, x1, y1)); crop.save(out / f'{key}.png', optimize=True)
        # ground = lowest row with solid alpha (feet / mat contact), relative to the crop height
        alpha = crop.getchannel('A'); w, h = crop.size; ground = h
        for y in range(h - 1, -1, -1):
            if max(alpha.crop((0, y, w, y + 1)).getdata()) > 200: ground = y + 1; break
        meta[key] = {'file': f'{key}.png', 'source': fn, 'w': w, 'h': h, 'ground': round(ground / h, 4)}
        done[fn] = key; print(f'{key}\t{fn}\t{w}x{h}\tground={meta[key]["ground"]}\t{time.time()-t:.1f}s')
    (out / 'cutouts.json').write_text(json.dumps(meta, indent=1))

if __name__ == '__main__': main()
