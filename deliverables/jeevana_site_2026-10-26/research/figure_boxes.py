#!/usr/bin/env python3
"""Figure boxes for the no-text-over-figure assertion.
description: for each stitched keyframe research/keyframes/frame-NN.jpg (cream paper ground), the bbox of non-paper pixels
  (|pixel - paper| ΔRGB > 28 after a 5 px median, components < 0.05 % dropped), normalised 0..1 to the 3:4 film frame,
  plus the same box mapped into the 9:16 centre crop used for hero-m.mp4.
usage: python3 research/figure_boxes.py  -> research/film/figure_boxes.json"""
import json, glob, pathlib
import numpy as np
from PIL import Image, ImageFilter
from scipy import ndimage
R = pathlib.Path(__file__).parent
out = {"source": "research/keyframes/frame-NN.jpg", "units": "fraction of frame", "landscape": [], "portrait": []}
crop_w = (9 / 16) / (3 / 4)  # hero-m: crop=ih*9/16:ih of the 3:4 film
for f in sorted(glob.glob(str(R / 'keyframes/frame-*.jpg'))):
    im = Image.open(f).convert('RGB').filter(ImageFilter.MedianFilter(5)); a = np.asarray(im).astype(int); h, w, _ = a.shape
    border = np.concatenate([a[:8].reshape(-1, 3), a[-8:].reshape(-1, 3), a[:, :8].reshape(-1, 3), a[:, -8:].reshape(-1, 3)])
    paper = np.median(border, axis=0)
    m = np.abs(a - paper).max(axis=2) > 28
    lab, n = ndimage.label(m); sizes = ndimage.sum(m, lab, range(1, n + 1))
    keep = np.isin(lab, [i + 1 for i, s in enumerate(sizes) if s > 0.0005 * h * w])
    ys, xs = np.nonzero(keep)
    b = [round(xs.min() / w, 4), round(ys.min() / h, 4), round((xs.max() + 1) / w, 4), round((ys.max() + 1) / h, 4)]
    out["landscape"].append({"frame": pathlib.Path(f).name, "paper": [int(v) for v in paper], "box": b})
    x0 = max(0, (b[0] - (1 - crop_w) / 2) / crop_w); x1 = min(1, (b[2] - (1 - crop_w) / 2) / crop_w)
    out["portrait"].append({"frame": pathlib.Path(f).name, "box": [round(x0, 4), b[1], round(x1, 4), b[3]]})
(R / 'film/figure_boxes.json').write_text(json.dumps(out, indent=1))
for e in out["landscape"]: print(e["frame"], e["paper"], e["box"])
