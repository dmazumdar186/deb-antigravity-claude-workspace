"""Build 20 MISB social posts (HTML -> PNG). Facts: ../research/facts.md only."""
import os, sys, json
from pathlib import Path
HERE = Path(__file__).resolve().parent
FONTS = HERE / "fonts"; IMG = HERE / "img"; HTML = HERE / "html"; PNG = HERE.parent / "png"
W, H = 1080, 1350
PAPER, INK, NAVY, VERM, GOLD, MUTE = "#F6F2EA", "#141414", "#003A70", "#E64626", "#F5DA58", "#5B5952"

CSS = f"""
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-400.woff2) format('woff2');font-weight:400;font-style:normal}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-500.woff2) format('woff2');font-weight:500;font-style:normal}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-600.woff2) format('woff2');font-weight:600;font-style:normal}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-400-italic.woff2) format('woff2');font-weight:400;font-style:italic}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-400.woff2) format('woff2');font-weight:400}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-500.woff2) format('woff2');font-weight:500}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-600.woff2) format('woff2');font-weight:600}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-400-ext.woff2) format('woff2');font-weight:400;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-400-ext.woff2) format('woff2');font-weight:400;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-500-ext.woff2) format('woff2');font-weight:500;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-500-ext.woff2) format('woff2');font-weight:500;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-600-ext.woff2) format('woff2');font-weight:600;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'Inter';src:url(file://{FONTS}/inter-600-ext.woff2) format('woff2');font-weight:600;unicode-range:U+0100-02BA,U+02BD-02C5,U+02C7-02CC,U+02CE-02D7,U+02DD-02FF,U+0304,U+0308,U+0329,U+1E00-1E9F,U+1EF2-1EFF,U+2020,U+20A0-20AB,U+20AD-20C0,U+2113,U+2C60-2C7F,U+A720-A7FF}}
@font-face{{font-family:'CG';src:url(file://{FONTS}/cg-400-italic-ext.woff2) format('woff2');font-weight:400;font-style:italic;unicode-range:U+0100-02BA,U+1E00-1E9F,U+1EF2-1EFF}}
*{{box-sizing:border-box;margin:0;padding:0}}
html,body{{width:{W}px;height:{H}px;overflow:hidden;background:{PAPER};color:{INK};font-family:'Inter',sans-serif;-webkit-font-smoothing:antialiased}}
.post{{position:relative;width:{W}px;height:{H}px;background:{PAPER};color:{INK}}}
.post.dark{{background:{INK};color:{PAPER}}}
.post.navy{{background:{NAVY};color:{PAPER}}}
.kicker{{z-index:5;position:absolute;top:64px;left:72px;font:500 17px/1 'Inter';letter-spacing:.26em;text-transform:uppercase;display:flex;align-items:center;gap:14px}}
.kicker:before{{content:'';width:10px;height:10px;background:{VERM};border-radius:50%}}
.idx{{z-index:5;position:absolute;top:64px;right:72px;font:400 17px/1 'Inter';letter-spacing:.22em;opacity:.7}}
.foot{{z-index:5;position:absolute;left:72px;right:72px;bottom:56px;height:150px;display:flex;align-items:flex-end;justify-content:space-between;border-top:1px solid currentColor;padding:20px 0 0;font:400 16px/1 'Inter';letter-spacing:.2em;text-transform:uppercase}}
.foot img{{width:150px;height:auto;display:block}}
.foot .r{{opacity:.75;padding-bottom:8px}}
h1{{font-family:'CG';font-weight:500;letter-spacing:-.005em;font-feature-settings:'ccmp' 1,'kern' 1,'lnum' 1}}
.num{{font-family:'Inter';font-weight:400;letter-spacing:-.04em}}
.ser{{font-family:'CG';font-feature-settings:'lnum' 1}}
.rule{{height:1px;background:currentColor;opacity:.5}}
.photo{{position:absolute;overflow:hidden;background:#ddd}}
.photo img{{width:100%;height:100%;object-fit:cover;display:block}}
.small{{font:400 19px/1.55 'Inter';letter-spacing:.01em}}
.src{{font:400 14px/1.4 'Inter';letter-spacing:.14em;text-transform:uppercase;opacity:.6}}
.mid{{position:absolute;left:72px;right:72px;top:150px;bottom:210px;display:flex;flex-direction:column;justify-content:center}}
.caps{{font:500 16px/1 'Inter';letter-spacing:.26em;text-transform:uppercase}}
"""

def frame(body, kicker, idx, dark=False, extra=""):
    logo = "footerWhite.svg" if dark else "misblogo.png"
    cls = "post dark" if dark == True else ("post navy" if dark == "navy" else "post")
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{CSS}{extra}</style></head><body>
<div class="{cls}"><div class="kicker">{kicker}</div><div class="idx">{idx}</div>{body}
<div class="foot"><img src="../img/{logo}" alt="MISB"><span class="r">misb.fr &nbsp;·&nbsp; @misb.fr</span></div></div></body></html>"""

def photo(src, x, y, w, h, pos="center", frame_=True):
    b = f"outline:1px solid {PAPER};outline-offset:-24px;" if frame_ else ""
    return f'<div class="photo" style="left:{x}px;top:{y}px;width:{w}px;height:{h}px"><img src="../img/{src}" style="object-position:{pos}"></div><div style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px;{b}pointer-events:none"></div>'

# ---------- layouts ----------
def hero(p):  # full-bleed photo top, ivory band with headline
    return photo(p["img"], 0, 0, W, 820, p.get("pos","center")) + f"""
<div style="position:absolute;left:72px;top:862px;width:936px">
<h1 style="font-size:{p.get('size',80)}px;line-height:1.02">{p['h']}</h1>
<p class="small" style="margin-top:18px;max-width:760px;color:{MUTE}">{p.get('sub','')}</p></div>""", {"kick_dark":True}

def plate(p):  # ivory page, photo plate with margins, headline below
    return f"""<div style="position:absolute;left:72px;top:136px;width:936px;height:1px;background:{INK};opacity:.3"></div>""" + photo(p["img"], 72, 160, 936, 700, p.get("pos","center"), frame_=False) + f"""
<div style="position:absolute;left:72px;top:900px;width:936px">
<h1 style="font-size:{p.get('size',72)}px;line-height:1.04">{p['h']}</h1>
<p class="small" style="margin-top:20px;max-width:720px;color:{MUTE}">{p.get('sub','')}</p></div>"""

def typo(p):  # typographic statement
    lines = "".join(f'<p class="small" style="margin-top:10px">{l}</p>' for l in p.get("lines",[]))
    return f"""<div class="mid"><div>
<h1 style="font-size:{p.get('size',112)}px;line-height:.98;max-width:{p.get('maxw',900)}px">{p['h']}</h1>
<div style="margin-top:56px;max-width:700px">{lines}</div>
<p class="src" style="margin-top:48px">{p.get('src','')}</p></div>"""

def fact(p):  # one number
    rows = "".join(f'<div style="display:flex;justify-content:space-between;align-items:baseline;padding:22px 0;border-top:1px solid currentColor"><span class="ser" style="font-size:40px;font-weight:500">{a}</span><span class="small" style="opacity:.8;text-align:right;max-width:520px">{b}</span></div>' for a,b in p.get("rows",[]))
    return f"""<div class="mid"><div>
<div class="{'num' if p.get('numfont')=='inter' else 'ser'}" style="font-size:{p.get('size',250)}px;font-weight:400;line-height:.9;letter-spacing:-.02em">{p['num']}</div>
<h1 style="font-size:58px;line-height:1.06;margin-top:36px;max-width:860px">{p['h']}</h1>
{('<p class="ser" style="font-size:34px;margin-top:18px;opacity:.8">'+p['h2']+'</p>') if p.get('h2') else ''}
<div style="margin-top:48px">{rows}</div>
<p class="src" style="margin-top:40px">{p.get('src','As published on misb.fr')}</p></div>"""

def quote(p):  # testimonial: full-width plate, quote below, small-caps attribution
    return photo(p["img"], 72, 150, 936, 560, p.get("pos","center"), frame_=False) + f"""
<div style="position:absolute;left:72px;top:760px;width:936px">
<h1 style="font-size:{p.get('size',58)}px;line-height:1.16;font-style:italic;font-weight:400;color:{NAVY}">&ldquo;{p['h']}&rdquo;</h1>
<p class="caps" style="margin-top:36px">{p['who']}</p>
<p class="src" style="margin-top:14px;text-transform:none;letter-spacing:.04em;font-size:16px">{p['attr']}</p></div>"""

def diptych(p):
    return photo(p["img"], 72, 160, 456, 640, p.get("pos","center"), frame_=False) + photo(p["img2"], 552, 160, 456, 640, p.get("pos2","center"), frame_=False) + f"""
<div style="position:absolute;left:72px;top:170px;width:456px" class="caps"><span style="background:{PAPER};padding:10px 14px;display:inline-block;margin:14px">{p.get('l1','')}</span></div>
<div style="position:absolute;left:552px;top:170px;width:456px" class="caps"><span style="background:{PAPER};padding:10px 14px;display:inline-block;margin:14px">{p.get('l2','')}</span></div>
<div style="position:absolute;left:72px;top:860px;width:936px">
<h1 style="font-size:{p.get('size',76)}px;line-height:1.04">{p['h']}</h1>
<p class="small" style="margin-top:20px;max-width:760px;color:{MUTE}">{p.get('sub','')}</p></div>"""

def cta(p):  # open-day / apply card
    items = "".join(f'<div style="padding:26px 0;border-top:1px solid currentColor;display:flex;gap:40px;align-items:baseline"><span class="caps" style="opacity:.6;width:200px;flex:none">{a}</span><span class="ser" style="font-size:38px;font-weight:500">{b}</span></div>' for a,b in p.get("rows",[]))
    return f"""<div class="mid"><div>
<h1 style="font-size:{p.get('size',120)}px;line-height:.96;max-width:900px">{p['h']}</h1>
<p class="small" style="margin-top:40px;max-width:680px;opacity:.85">{p.get('sub','')}</p>
<div style="margin-top:64px">{items}<div class="rule"></div></div>
<div style="margin-top:56px;display:inline-block;border:1px solid currentColor;padding:26px 44px" class="caps">{p.get('btn','')}</div></div>"""

def listcard(p):  # numbered list of programmes / tracks
    items = "".join(f'<div style="display:flex;gap:36px;align-items:baseline;padding:{p.get("pad",20)}px 0;border-top:1px solid currentColor"><span class="caps" style="opacity:.55;width:52px;flex:none">{i:02d}</span><span class="ser" style="font-size:{p.get("isize",46)}px;font-weight:500;line-height:1.1">{t}</span></div>' for i,t in enumerate(p["items"],1))
    return f"""<div class="mid"><div>
<h1 style="font-size:{p.get('size',88)}px;line-height:1">{p['h']}</h1>
<p class="small" style="margin-top:22px;max-width:740px;opacity:.8">{p.get('sub','')}</p>
<div style="margin-top:48px">{items}<div class="rule"></div></div>
<p class="src" style="margin-top:36px">{p.get('src','')}</p></div>"""

def addr(p):  # map / address card, type only
    cols = ""
    for c in p["cols"]:
        cols += f"""<div style="flex:1;padding-right:40px"><p class="caps" style="color:{NAVY}">{c['k']}</p>
<h1 style="font-size:{p.get('hsize',62)}px;line-height:1.02;margin-top:26px">{c['h']}</h1>
<p class="ser" style="font-size:34px;line-height:1.3;margin-top:30px;font-weight:400">{c['a']}</p>
<p class="small" style="margin-top:22px;opacity:.75">{c['t']}</p></div>"""
    return f"""<div class="mid"><div>
<h1 style="font-size:{p.get('size',96)}px;line-height:1">{p['h']}</h1>
<div class="rule" style="margin:56px 0 48px"></div>
<div style="display:flex">{cols}</div>
<p class="src" style="margin-top:56px">{p.get('src','')}</p></div>"""

LAY = dict(hero=hero, plate=plate, typo=typo, fact=fact, quote=quote, diptych=diptych, cta=cta, list=listcard, addr=addr)

import unicodedata
def _nfc(o):
    if isinstance(o,str): return unicodedata.normalize('NFC',o)
    if isinstance(o,dict): return {k:_nfc(v) for k,v in o.items()}
    if isinstance(o,(list,tuple)): return type(o)(_nfc(v) for v in o)
    return o

def build(posts):
    posts=[_nfc(p) for p in posts]
    HTML.mkdir(exist_ok=True); PNG.mkdir(exist_ok=True)
    out = []
    for n, p in enumerate(posts, 1):
        body = LAY[p["lay"]](p)
        kd = False
        if isinstance(body, tuple): body, meta = body; kd = meta.get("kick_dark")
        if '<div class="mid">' in body: body += "</div>"
        extra = f".kicker,.idx{{background:{PAPER};color:{INK};padding:12px 16px;top:52px;opacity:1}} .kicker{{left:60px}} .idx{{right:60px}}" if kd and not p.get("dark") else ""
        html = frame(body, p["kicker"], p["idx"], p.get("dark", False), extra)
        f = HTML / f'{n:02d}_{p["platform"]}_{p["slug"]}.html'; f.write_text(html, encoding="utf-8"); out.append(f)
    return out

def render(files):
    from playwright.sync_api import sync_playwright
    exe = next(str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome"))
    with sync_playwright() as pw:
        br = pw.chromium.launch(executable_path=exe)
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for f in files:
            pg.goto(f.as_uri()); pg.wait_for_timeout(250)
            pg.evaluate("document.fonts.ready")
            pg.screenshot(path=str(PNG / (f.stem + ".png")), clip={"x": 0, "y": 0, "width": W, "height": H})
        br.close()
    from PIL import Image
    for f in files:
        pf = PNG / (f.stem + ".png")
        if pf.stat().st_size > 600_000:
            im = Image.open(pf).convert("RGB").quantize(colors=256, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.FLOYDSTEINBERG)
            im.save(pf, optimize=True)
        print(pf.name, pf.stat().st_size // 1024, "KB")

if __name__ == "__main__":
    from posts import POSTS
    sel = sys.argv[1:]  # optional slugs filter
    files = build(POSTS)
    if sel: files = [f for f in files if any(s in f.stem for s in sel)]
    render(files)
