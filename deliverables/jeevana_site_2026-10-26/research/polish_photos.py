#!/usr/bin/env python3
"""Polish Jeevana's field photos for v4 (brief_v4 §2 Photos). PIL + numpy, no network.
usage: python3 research/polish_photos.py [--sheet out.jpg]
-> site/assets/photos/<key>@<w>.webp, site/assets/photos/manifest.json (sizes, LQIP data URIs, alt EN/FR), site/assets/og.jpg"""
import base64, io, json, pathlib, sys
import numpy as np
from PIL import Image, ImageFilter, ImageOps

R = pathlib.Path(__file__).resolve().parent.parent
RAW, OUT = R / '_raw_assets', R / 'site/assets/photos'
TARGET = np.array([242, 236, 226], float)
WIDTHS = [800, 1400, 2000]

def load(name):
    return ImageOps.exif_transpose(Image.open(RAW / name)).convert('RGB')

def wb_gain(img):
    a = np.asarray(img.resize((img.width // 8, img.height // 8))).astype(float)
    lum = a.mean(2); sat = a.max(2) - a.min(2)
    m = (lum > np.percentile(lum, 94)) & (sat < 60)
    if m.sum() < 50: m = lum > np.percentile(lum, 97)
    g = TARGET / a[m].mean(0); g = g / g.mean()  # colour only, keep exposure
    return 1 + 0.4 * (g - 1)  # mild

def grade(img, gain):
    a = np.asarray(img).astype(float) / 255 * gain
    a = np.clip(a, 0, 1)
    lum = a @ [0.2126, 0.7152, 0.0722]
    lift = 0.06 * 2.2 * (1 - lum) ** 3 * lum ** 0.5          # shadow lift ~ +6 %
    s = lum + lift
    s = s + 0.08 * (s - 0.5) * (1 - np.abs(2 * s - 1))        # gentle S-curve +8 %
    ratio = np.where(lum > 1e-4, s / np.maximum(lum, 1e-4), 1)[..., None]
    a = np.clip(a * ratio, 0, 1)
    l2 = (a @ [0.2126, 0.7152, 0.0722])[..., None]
    a = np.clip(l2 + 1.04 * (a - l2), 0, 1)                   # saturation +4 %
    return Image.fromarray((a * 255 + .5).astype(np.uint8))

def horizon(img):
    """first row (from the top) where >80 % of pixels are grass and stay grass."""
    a = np.asarray(img.resize((img.width // 16, img.height // 16))).astype(int)
    g = (a[..., 1] > a[..., 0] + 4) & (a[..., 1] > a[..., 2]) & (a.sum(2) < 400)
    frac = g.mean(1); h = len(frac)
    for y in range(h // 4, h):
        if frac[y:y + 6].min() > 0.8: return y / h
    return 0.5

# figure boxes (fraction x0,y0,x1,y1) measured on a gridded contact sheet
STEPS = {1: '_DAV5297.jpg', 2: '_DAV5303.jpg', 3: '_DAV5307.jpg', 4: '_DAV5343.jpg', 5: '_DAV5320.jpg', 6: '_DAV5332.jpg',
         7: '_DAV5337.jpg', 8: '_DAV5320.jpg', 9: '_DAV5310.jpg', 10: '_DAV5307.jpg', 11: '_DAV5303.jpg', 12: '_DAV5300.jpg'}
FIG = {'_DAV5297.jpg': (.33, .20, .62, .80), '_DAV5300.jpg': (.40, .33, .62, .86), '_DAV5303.jpg': (.25, .33, .72, .73),
       '_DAV5307.jpg': (.20, .37, .80, .65), '_DAV5310.jpg': (.22, .24, .82, .58), '_DAV5320.jpg': (.25, .38, .75, .65),
       '_DAV5332.jpg': (.12, .30, .85, .49), '_DAV5337.jpg': (.10, .35, .90, .49), '_DAV5343.jpg': (.15, .14, 1.0, .66)}
ALT = {
 'hero': ("Jeevana seated cross-legged on a park lawn in Paris, eyes closed, a gentle smile, hands resting on her knees.",
          "Jeevana assise en tailleur sur une pelouse à Paris, les yeux fermés, un léger sourire, les mains posées sur les genoux."),
 'practice-01': ("Jeevana in cobra pose on a mat, chest lifted, eyes closed.", "Jeevana en posture du cobra sur un tapis, la poitrine ouverte, les yeux fermés."),
 'practice-02': ("Jeevana in child's pose on a grey mat, seen from above.", "Jeevana en posture de l'enfant sur un tapis gris, vue d'en haut."),
 'practice-03': ("Jeevana seated in meditation on the grass, hands in jñāna mudrā.", "Jeevana assise en méditation sur l'herbe, les mains en jñāna mudrā."),
 'paris': ("Jeevana in a full backbend, Chakrāsana, on a blue mat on the Champ-de-Mars, the Eiffel Tower behind her.",
           "Jeevana en pont complet, Chakrāsana, sur un tapis bleu au Champ-de-Mars, la tour Eiffel derrière elle."),
}
POSE = json.loads((R / 'research/content_fixture.json').read_text())['positions']

def fit_box(W, H, cx, cy, cw, ch):
    x = int(min(max(cx - cw / 2, 0), W - cw)); y = int(min(max(cy - ch / 2, 0), H - ch))
    return (x, y, x + int(cw), y + int(ch))

def export(img, key, widths, manifest, alt, ratio):
    sizes = []
    for w in widths:
        if w > img.width: continue
        im = img.resize((w, round(w * img.height / img.width)), Image.LANCZOS).filter(ImageFilter.UnsharpMask(1.2, 60, 3))
        im.save(OUT / f'{key}@{w}.webp', 'WEBP', quality=82, method=6); sizes.append(w)
    lq = img.resize((24, round(24 * img.height / img.width)), Image.LANCZOS).filter(ImageFilter.GaussianBlur(1))
    b = io.BytesIO(); lq.save(b, 'WEBP', quality=40)
    manifest[key] = {'widths': sizes, 'ratio': ratio, 'w': img.width, 'h': img.height,
                     'lqip': 'data:image/webp;base64,' + base64.b64encode(b.getvalue()).decode(), 'alt_en': alt[0], 'alt_fr': alt[1]}
    return img

def main():
    OUT.mkdir(parents=True, exist_ok=True)
    for f in OUT.glob('*.webp'): f.unlink()
    man, done = {}, {}
    ref = load('_DAV5297.jpg'); gain = wb_gain(ref)   # one grade for the whole field set
    # twelve steps: one crop size (same camera distance), horizon fixed at the 5297 value
    CH = 4114; CW = CH * 3 // 4
    h0 = None
    for n, f in STEPS.items():
        img = load(f); W, H = img.size; s = H / 5760; ch, cw = int(CH * s), int(CW * s)
        if cw > W: cw = W; ch = cw * 4 // 3
        x0, y0, x1, y1 = FIG[f]; hy = horizon(img) * H
        if h0 is None:  # pick output horizon once from _DAV5297 so its figure sits with 8 % margin
            top = y0 * H - 0.08 * ch; h0 = (hy - top) / ch
        top = hy - h0 * ch
        top = min(top, y0 * H - 0.08 * ch); top = max(top, y1 * H + 0.08 * ch - ch)
        box = fit_box(W, H, (x0 + x1) / 2 * W, top + ch / 2, cw, ch)
        key = f'sn-{n:02d}'; p = POSE[n - 1]
        alt = (f"Step {n}: Jeevana in {p['iast']} on a mat on a park lawn in Paris.", f"Étape {n} : Jeevana en {p['iast']} sur un tapis, sur une pelouse à Paris.")
        export(grade(img.crop(box), gain), key, WIDTHS, man, alt, '3/4')
        done[key] = box
    hero = load('_DAV5356.jpg'); W, H = hero.size; ch = 4050
    top = 0.31 * H - 0.38 * ch; top = max(0, min(top, H - ch))
    hc = grade(hero.crop((0, int(top), W, int(top) + ch)), gain)
    export(hc, 'hero', WIDTHS + [2800], man, ALT['hero'], '4/5')
    img = load('_DAV5340.jpg'); W, H = img.size
    export(grade(img.crop(fit_box(W, H, 0.52 * W, 0.545 * H, W, W * 2 / 3)), gain), 'practice-01', WIDTHS, man, ALT['practice-01'], '3/2')
    img = load('_DAV5325.jpg'); W, H = img.size
    export(grade(img.crop(fit_box(W, H, 0.48 * W, 0.56 * H, 2700, 2700)), gain), 'practice-02', WIDTHS, man, ALT['practice-02'], '1/1')
    img = load('_DAV5352.jpg'); W, H = img.size
    export(grade(img.crop(fit_box(W, H, 0.48 * W, 0.50 * H, 2480, 3100)), gain), 'practice-03', WIDTHS, man, ALT['practice-03'], '4/5')
    img = load('IMG-20260810-WA0005.jpg')
    export(grade(img, wb_gain(img)), 'paris', [800, 1200], man, ALT['paris'], '3/4')
    (OUT / 'manifest.json').write_text(json.dumps(man, ensure_ascii=False, indent=1))
    # OG: hero on paper, 1200x630
    og = Image.new('RGB', (1200, 630), (243, 238, 228)); h = hc.resize((448, 560), Image.LANCZOS); og.paste(h, (700, 35))
    og.save(R / 'site/assets/og.jpg', quality=85)
    if '--sheet' in sys.argv:
        keys = list(man); th = 300; sheet = Image.new('RGB', (len(keys) * 230, th), 'white')
        for i, k in enumerate(keys):
            im = Image.open(OUT / f'{k}@800.webp'); im.thumbnail((225, th)); sheet.paste(im, (i * 230, 0))
        sheet.save(sys.argv[sys.argv.index('--sheet') + 1], quality=80)
    print('h0', round(h0, 3), json.dumps(done))

if __name__ == '__main__':
    main()
