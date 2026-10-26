#!/usr/bin/env python3
"""Compose the 12 Sūrya Namaskāra keyframes: cut-out figure on a dawn-sky plate, graded and grounded.
description: builds research/keyframes/dawn/frame-NN.jpg (1080x1440) from _raw_assets/cutouts_v3 + cutouts.json.
  Parameters at the top (rim, haze, shadow, grade) are the knobs; the plate is procedural (gradient + glow + grain).
inputs: --out DIR (default research/keyframes/dawn). outputs: frame-01..12.jpg, plate.jpg."""
# (starting point written by the brain 2026-10-26; the compositor worker iterates the knobs to an art-director GO)
import argparse, json
from pathlib import Path
import numpy as np, cv2
from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
CUT = ROOT / "_raw_assets" / "cutouts_v3"
W, H = 1080, 1440
FIG_H, GROUND_Y, MAX_W = 0.72, 0.86, 0.88
SUN = (0.14, 0.80)                       # low-left, fraction of canvas
# knobs
RIM_OPACITY, RIM_PX, RIM_RGB = 0.28, 1.5, (236, 178, 104)       # ochre, sun side only
HAZE_PLATE, HAZE_SUBJ_MAX = 0.55, 0.35
CONTACT_OP, CAST_OP, CAST_LEN, CAST_SQUASH = 0.45, 0.22, 0.9, 0.14
CONTRAST, WRAP_OP, WRAP_RGB = 0.86, 0.14, (255, 176, 112)
CREAM, HI_START, HI_COMP = np.array([240, 222, 196.]), 170, 0.6
FRINGE_PX, GRAIN = 3, 5.0
STOPS = [(0.0, (46, 44, 92)), (0.35, (122, 88, 128)), (0.62, (206, 140, 136)),
         (0.82, (232, 176, 128)), (1.0, (214, 170, 128))]          # indigo -> dusty rose -> ochre haze


def plate(seed=0):
    y = np.linspace(0, 1, H)[:, None]
    img = np.zeros((H, W, 3))
    for c in range(3):
        img[..., c] = np.interp(y, [s[0] for s in STOPS], [s[1][c] for s in STOPS]) * np.ones((1, W))
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    d = np.hypot((xx - SUN[0]) * W / H, yy - SUN[1])
    glow = np.exp(-(d / 0.30) ** 2)
    img += glow[..., None] * np.array([70, 42, 10.]) * 0.9
    band = np.exp(-((yy - GROUND_Y) / 0.06) ** 2)          # horizon haze
    img = img * (1 - HAZE_PLATE * band[..., None] * 0.5) + np.array([240, 205, 170.]) * HAZE_PLATE * band[..., None] * 0.5
    return img


def grain(img, seed):
    rng = np.random.default_rng(seed)
    n = cv2.GaussianBlur(rng.normal(0, 1, (H, W)).astype(np.float32), (0, 0), 0.7)
    return img + n[..., None] * GRAIN


def load(name):
    meta = json.loads((CUT / "cutouts.json").read_text())[name]
    a = np.array(Image.open(CUT / meta["file"]).convert("RGBA")).astype(np.float32)
    return a, meta["ground"]


def fix_cutout(rgba):
    rgb, al = rgba[..., :3], rgba[..., 3] / 255
    # edge decontamination: replace edge band with blurred interior colour, kill blue cast
    core = cv2.erode((al > 0.98).astype(np.float32), np.ones((2 * FRINGE_PX + 1,) * 2))
    k = 9
    num = cv2.GaussianBlur(rgb * core[..., None], (0, 0), k)
    den = cv2.GaussianBlur(core, (0, 0), k)[..., None] + 1e-4
    inner = num / den
    band = np.clip((al > 0.02) - core, 0, 1)
    band = cv2.GaussianBlur(band, (0, 0), 1.0)[..., None]
    has = (den > 0.02).astype(np.float32)
    rgb = rgb * (1 - band * has) + inner * band * has
    lum = rgb.mean(2, keepdims=True)
    blue = np.clip((rgb[..., 2:3] - rgb[..., :1]) / 40, 0, 1) * np.clip(band * 2, 0, 1)
    rgb = rgb * (1 - blue) + lum * blue
    # fleece: cool bright low-sat -> cream, compressed
    mx, mn = rgb.max(2), rgb.min(2)
    L = rgb.mean(2)
    w = np.clip((L - 85) / 35, 0, 1) * np.clip(1 - (mx - mn) / 110, 0, 1)
    w = cv2.GaussianBlur(w, (0, 0), 1.5)[..., None]
    Lc = HI_START + (L - HI_START).clip(0) * HI_COMP
    Lc = np.where(L > HI_START, Lc, L)[..., None]
    cream = CREAM / CREAM.mean() * Lc
    rgb = rgb * (1 - w) + cream * w
    # soften hard daylight contrast toward a warmer mid
    m = (rgb * al[..., None]).sum((0, 1)) / (al.sum() + 1)
    rgb = m + (rgb - m) * CONTRAST
    rgb = rgb * np.array([1.03, 0.99, 0.94])
    return np.dstack([rgb.clip(0, 255), al * 255])


def place(rgba, ground):
    h, w = rgba.shape[:2]
    ys, xs = np.nonzero(rgba[..., 3] > 20)
    top, gy = ys.min(), ground * h
    s = min(FIG_H * H / (gy - top), MAX_W * W / (xs.max() - xs.min()))
    big = cv2.resize(rgba, (round(w * s), round(h * s)), interpolation=cv2.INTER_AREA)
    cx = (xs.min() + xs.max()) / 2 * s
    ox, oy = round(W / 2 - cx), round(GROUND_Y * H - gy * s)
    M = np.float32([[1, 0, ox], [0, 1, oy]])
    out = cv2.warpAffine(big, M, (W, H), flags=cv2.INTER_LINEAR, borderValue=(0, 0, 0, 0))
    return out


def compose(name, bg, seed):
    rgba, g = load(name)
    fig = place(fix_cutout(rgba), g)
    rgb, al = fig[..., :3], fig[..., 3] / 255
    gy = int(GROUND_Y * H)
    img = bg.copy()
    # contact shadow: pixels of figure within ~3% above ground, squashed and blurred
    near = al * (np.arange(H)[:, None] > gy - 0.035 * H)
    cols = near.max(0)
    cs = np.zeros((H, W), np.float32)
    cs[gy - 4:gy + 6] = cols
    cs = cv2.GaussianBlur(cs, (0, 0), 9)
    # cast shadow: silhouette flattened onto ground and skewed away from sun (to the right)
    ys = np.arange(H)[:, None]
    hgt = (gy - ys).clip(0)
    src = cv2.GaussianBlur(al, (0, 0), 2)
    M = np.float32([[1, -CAST_LEN / CAST_SQUASH * CAST_SQUASH * 1.0 / 1, 0], [0, 1, 0]])
    # map: shadow point (x', y') = (x + CAST_LEN*h, gy + CAST_SQUASH*h)
    M = np.float32([[1, CAST_LEN / CAST_SQUASH, 0], [0, 1, 0]])
    flat = cv2.warpAffine(src, np.float32([[1, 0, 0], [0, -CAST_SQUASH, gy * (1 + CAST_SQUASH)]]), (W, H))
    flat = cv2.warpAffine(flat, np.float32([[1, CAST_LEN / CAST_SQUASH, -CAST_LEN / CAST_SQUASH * gy], [0, 1, 0]]), (W, H))
    fade = np.exp(-((ys - gy) / (0.05 * H)).clip(0))
    cast = cv2.GaussianBlur(flat * fade, (0, 0), 6) * (ys >= gy - 2)
    sh = np.clip(CONTACT_OP * cs + CAST_OP * cast, 0, 0.6)[..., None]
    img = img * (1 - sh * np.array([0.55, 0.62, 0.70]))
    # wrap light: warm from lower-left on figure
    yy, xx = np.mgrid[0:H, 0:W] / np.array([H, W])[:, None, None]
    wl = np.clip(1 - np.hypot(xx - SUN[0], yy - SUN[1]) / 0.9, 0, 1) ** 1.5
    lit = rgb + (255 - rgb) * (np.array(WRAP_RGB) / 255) * (WRAP_OP * wl)[..., None]
    # rim on sun side: alpha edge whose left neighbour is empty
    shift = int(round(RIM_PX))
    left = np.zeros_like(al); left[:, shift:] = al[:, :-shift]
    down = np.zeros_like(al); down[:-1] = al[1:]
    edge = np.clip(al - np.minimum(left, 1) * 0.0 - left, 0, 1) + 0.4 * np.clip(al - down, 0, 1)
    edge = cv2.GaussianBlur(np.clip(edge, 0, 1), (0, 0), 0.6) * al * (0.4 + 0.6 * wl)
    lit = lit * (1 - RIM_OPACITY * edge[..., None]) + np.array(RIM_RGB) * RIM_OPACITY * edge[..., None]
    img = img * (1 - al[..., None]) + lit * al[..., None]
    # horizon haze over subject, capped
    band = np.exp(-((ys - gy) / (0.05 * H)) ** 2) * HAZE_SUBJ_MAX
    img = img * (1 - band[..., None] * al[..., None]) + bg * band[..., None] * al[..., None]
    return np.clip(grain(img, seed), 0, 255).astype(np.uint8)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "research/keyframes/dawn"))
    ap.add_argument("--frames", default="1-12")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    lo, hi = map(int, a.frames.split("-")) if "-" in a.frames else (int(a.frames),) * 2
    bg = plate()
    Image.fromarray(np.clip(grain(bg, 0), 0, 255).astype(np.uint8)).save(out / "plate.jpg", quality=92)
    for i in range(lo, hi + 1):
        Image.fromarray(compose(f"sn-{i:02d}", bg, i)).save(out / f"frame-{i:02d}.jpg", quality=92)


if __name__ == "__main__":
    main()
