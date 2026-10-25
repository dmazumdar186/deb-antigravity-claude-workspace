"""
description: Render the ProdCraft weekly LinkedIn cards, batch 1 v2 (panel spec 2026-10-25): three recurring layouts on one grid (hook in the top 20%, Newsreader headline >= 96px/line, artefact zone 520-1150, footer rule y1210). face = headshot cut-out on paper + one Caveat margin note; artefact = code/config payload as an editor fragment with the brass line; carousel = 5-7 document slides (1080x1350 PNG + one PDF). Extends linkedin_weekly_cards.py (fonts, chromium, logo, slug, contact sheet are imported from it). Never publishes.
inputs: --messages execution/content/prodcraft_batch1_v2_messages.json; --out <dir> (default deliverables/linkedin_weekly_cards/prodcraft/<date>-v2); --fonts <dir with fonts_local.css>; --cutout <rgba png> (default .tmp/banners/headshot_cutout.png, built by headshot_cutout.py when missing); --weeks 1-10; --batch <label>; env PW_CHROME
outputs: <out>/png/NN_week_slug.png (single cards), <out>/carousels/NN/slide_k.png + <out>/carousels/NN_week_slug.pdf, <out>/html/*.html (cards and slides, for the validator), <out>/thumbs/*.png (400px review thumbnails), <out>/captions.md, <out>/messages_v2.json, <out>/contact_sheet.png, <out>/manifest.json, <out>/index.html, <out>/prodcraft_weekly_cards_<batch>.zip; exit 1 if any headline needs more than two lines or a figure/brass budget is missed
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import re
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from execution.content.linkedin_weekly_cards import (  # noqa: E402
    NBH, NBSP, WJ, BRAND_FONTS, FOOT_LABEL, H, LOGO_STYLES, W, chromium_path, contact_sheet, esc, load_fonts, logo_data_uri, parse_weeks, slugify, verify_fonts,
)

CUTOUT = ROOT / ".tmp/banners/headshot_cutout.png"
PAPER, INK, BRASS = (243, 241, 236), (23, 25, 29), (168, 132, 58)
FIGURE_BUDGET = (0.35, 0.45)  # share of the card covered by the figure's visible bounding box
BRASS_BUDGET = 0.05
HEAD_STEPS = [[92, 1.05, -.022], [90, 1.067, -.025], [88, 1.09, -.03]]  # every step keeps the line box >= 96px (>= 35px at a 400px thumbnail)

CSS = r"""
:root{--paper:#f3f1ec;--pane:#ebe8e1;--ink:#17191d;--ink2:#474b53;--brass:#a8843a;--slate:#3b5b7a;--hair:rgba(23,25,29,.22);
--grain:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='g'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .5 0'/></filter><rect width='100%' height='100%' filter='url(%23g)'/></svg>")}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font-family:Geist,Inter,system-ui,sans-serif;font-feature-settings:"ss01","cv11"}
.card{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--paper);color:var(--ink)}
.card:after{content:"";position:absolute;inset:0;background:var(--grain);opacity:.06;pointer-events:none;mix-blend-mode:multiply}
.serif{font-family:Newsreader,'Bitstream Charter',FreeSerif,Georgia,serif;font-optical-sizing:auto}
.mono{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:15px;letter-spacing:.08em;color:var(--ink2);font-variant-numeric:tabular-nums}
.up{text-transform:uppercase}
/* grid v2: lockup y96 (40px) · headline top y160, <=2 lines of >=96px · zone 520-1150 · footer rule y1210 */
.top{position:absolute;left:96px;right:96px;top:96px;height:40px;display:flex;justify-content:space-between;align-items:flex-end}
.brand{display:flex;align-items:flex-end;gap:12px}
.brand img{height:40px;width:auto;display:block}
.brand span{font-family:Newsreader,serif;font-weight:500;font-size:26px;line-height:1;padding-bottom:5px}
.top .mono{line-height:1;padding-bottom:4px}
h1{position:absolute;left:96px;top:160px;width:888px;font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-optical-sizing:auto;font-weight:500;font-size:92px;line-height:1.05;letter-spacing:-.022em;margin:0;text-wrap:balance}
.fact{position:absolute;left:96px;top:392px;width:888px;margin:0;font-family:Newsreader,serif;font-weight:400;font-size:34px;line-height:1.25;color:var(--ink);text-wrap:pretty}
.fact b{font-weight:500}
.foot{position:absolute;left:96px;right:96px;top:1210px;border-top:1px solid var(--hair);padding-top:22px;display:flex;justify-content:space-between}
.foot .n{color:var(--brass)}
/* face */
.face .fact{top:520px;width:430px;font-size:36px;line-height:1.28}
.face .fig{position:absolute;bottom:140px;left:380px;height:760px;width:auto;display:block}
.note{position:absolute;left:100px;top:844px;width:420px;padding-bottom:8px;font-family:Caveat,cursive;font-weight:500;font-size:40px;line-height:1.15;color:var(--ink2);transform:rotate(-2.2deg);transform-origin:left top}
.note:before{content:"";position:absolute;left:-4px;top:-18px;width:120px;height:2px;background:var(--brass);transform:rotate(-1deg)}
/* artefact: editor fragment */
.pane{position:absolute;left:72px;top:496px;width:936px;height:654px;background:var(--pane);border:1px solid var(--hair);overflow:hidden;box-shadow:0 1px 0 rgba(23,25,29,.06)}
.tabs{height:56px;border-bottom:1px solid var(--hair);display:flex;align-items:stretch;padding-left:24px}
.tab{display:flex;align-items:center;gap:12px;padding:0 20px;font-family:'JetBrains Mono',monospace;font-size:20px;color:var(--ink);background:var(--paper);border-left:1px solid var(--hair);border-right:1px solid var(--hair);margin-bottom:-1px;border-bottom:1px solid var(--paper)}
.tab .dir{color:var(--ink2)}.tab .dot{width:10px;height:10px;border-radius:50%;background:var(--brass);opacity:.9}
pre{margin:0;padding:22px 0 22px 0;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:24px;line-height:1.5;color:var(--ink);white-space:pre-wrap;overflow-wrap:anywhere;tab-size:4}
pre .ln{display:block;padding:0 36px 0 60px;text-indent:-28px;min-height:36px}
pre .ln.hot{background:rgba(168,132,58,.16);box-shadow:inset 6px 0 0 var(--brass)}
pre .c{color:var(--ink2)}pre .s{color:var(--slate)}pre .k{font-weight:600}pre .h{font-weight:600}
.md pre .h{font-weight:600}
.src{position:absolute;left:96px;top:1164px;font-size:15px}
/* carousel slides */
.hd{position:absolute;left:96px;top:160px;width:888px}
.kick{display:block;font-size:17px;letter-spacing:.14em;margin-bottom:20px}
.slide h2{margin:0;font-family:Newsreader,serif;font-weight:500;font-size:68px;line-height:1.08;letter-spacing:-.018em;text-wrap:balance}
.slide .body{margin:36px 0 0;font-size:33px;line-height:1.35;color:var(--ink2);text-wrap:pretty}
.slide.nocode .body{font-size:40px;line-height:1.3;color:var(--ink);margin-top:56px}
.slide .pane{left:96px;width:888px;top:560px;height:590px}
.slide.q .hd{top:420px}.slide.q h2{font-size:76px;line-height:1.1}
.slide.hook .body{position:absolute;left:96px;top:400px;width:888px;margin:0;font-family:Newsreader,serif;font-size:42px;line-height:1.3;color:var(--ink)}
.slide .cta{position:absolute;left:96px;top:1120px;font-size:17px;letter-spacing:.1em}
"""
FIT_JS = """<script>window.fitHead=function(){var h=document.querySelector('h1,.slide h2.fit');if(!h)return null;var steps=%s;
for(var i=0;i<steps.length;i++){h.style.fontSize=steps[i][0]+'px';h.style.lineHeight=steps[i][1];h.style.letterSpacing=steps[i][2]+'em';var lh=steps[i][0]*steps[i][1];
var n=Math.round(h.getBoundingClientRect().height/lh);if(n<=2){h.dataset.lines=n;h.dataset.px=steps[i][0];return [steps[i][0],n];}}
var lh=steps[steps.length-1][0]*steps[steps.length-1][1];var n=Math.round(h.getBoundingClientRect().height/lh);h.dataset.lines=n;return [steps[steps.length-1][0],n];};
window.fitHead();document.fonts.ready.then(window.fitHead);</script>""" % json.dumps(HEAD_STEPS)

TOKEN_RE = {
    "python": re.compile(r"(?P<c>(?<!&)#.*$)|(?P<s>&quot;.*?&quot;|&#x27;.*?&#x27;)|(?P<k>\b(?:def|return|if|elif|else|except|raise|import|from|not|or|and|assert|async|await|class)\b)", re.M),
    "markdown": re.compile(r"(?P<h>^## .*$)", re.M),
    "prompt": re.compile(r"(?P<k>\*\*[^*]+\*\*)|(?P<s>&quot;.*?&quot;|`[^`]+`)"),
}


def tint(line: str, lang: str) -> str:
    """Three tints only: ink (code), ink2 (comments), slate (strings); keywords bold ink.
    One pass over the escaped text so inserted markup is never re-matched."""
    e = esc(line)
    rx = TOKEN_RE.get(lang)
    if not rx:
        return e

    def sub(m: re.Match) -> str:
        kind = m.lastgroup
        txt = m.group(kind)
        if kind == "k" and lang == "prompt":
            txt = txt.strip("*")
        return f'<span class="{kind}">{txt}</span>'
    return rx.sub(sub, e)


def pane(code: str, tab: str, lang: str, brass: str, max_lines: int) -> str:
    lines = code.replace("\\\"", '"').split("\n")
    if len(lines) > max_lines:
        lines = lines[:max_lines - 1] + ["…"]
    hot_seen = False
    out = []
    for ln in lines:
        hot = (brass and brass.replace("\\\"", '"') in ln.replace("\\\"", '"')) and not hot_seen
        hot_seen = hot_seen or hot
        out.append(f'<span class="ln{" hot" if hot else ""}">{tint(ln, lang) or " "}</span>')
    d, _, f = tab.rpartition(" / ")
    tabs = f'<div class="tabs"><div class="tab t"><span class="dot"></span><span class="dir">{esc(d)}{" / " if d else ""}</span>{esc(f)}</div></div>'
    return f'<div class="pane{" md" if lang == "markdown" else ""}">{tabs}<pre>{"".join(out)}</pre></div>', hot_seen


def head_text(text: str) -> str:
    """Escape; hyphens never break; a short quoted phrase ('add AI') stays on one line; em dash sticks to the word before it."""
    t = esc(text).replace("-", NBH).replace("\u2014", WJ + "\u2014")
    return re.sub(r"(&#x27;[^&]{1,12}?)\s([^&]{1,12}?&#x27;)", lambda m: m.group(1) + NBSP + m.group(2), t)


def frame(inner: str, fonts_css: str, cls: str, fit: bool = True) -> str:
    return (f'<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css}{CSS}</style></head><body>'
            f'<div class="card {cls}">{inner}</div>{FIT_JS if fit else ""}</body></html>')


def top(logo_uri: str, week: int, right: str = "") -> str:
    brand = (f'<span class="brand"><img src="{logo_uri}" alt=""><span class="t">ProdCraft</span></span>' if logo_uri
             else '<span class="brand"><span class="t">ProdCraft</span></span>')
    return f'<div class="top">{brand}<span class="mono t">{esc(right or f"wk {week:02d}")}</span></div>'


def foot(week: int, label: str = FOOT_LABEL, numeral: str | None = None) -> str:
    return f'<div class="foot"><span class="mono t">{esc(label)}</span><span class="mono n t">{esc(numeral if numeral is not None else f"{week:02d}")}</span></div>'


def face_html(r: dict, logo_uri: str, cutout_uri: str) -> str:
    cta = r.get("cta_line")
    return (f'{top(logo_uri, r["week"])}<h1 class="t">{head_text(r["headline"])}</h1>'
            f'<img class="fig" src="{cutout_uri}" alt="">'
            f'<p class="fact t">{esc(r["card_fact"])}</p>'
            f'<div class="note t">{esc(r["annotation"])}</div>'
            f'{foot(r["week"], cta or FOOT_LABEL)}')


def artefact_html(r: dict, logo_uri: str) -> tuple[str, bool]:
    a = r["artefact"]
    p, hot = pane(a["code"], a["tab"], a["lang"], a.get("brass", ""), 16)
    return (f'{top(logo_uri, r["week"])}<h1 class="t">{head_text(r["headline"])}</h1>'
            f'<p class="fact t">{esc(r["card_fact"])}</p>{p}'
            f'<div class="src mono t">verbatim · {esc(a["tab"])}</div>{foot(r["week"])}'), hot


def slide_html(r: dict, s: dict, i: int, n: int, logo_uri: str) -> tuple[str, bool]:
    wk = r["week"]
    pos = f"{i + 1} / {n}"
    if s["kind"] == "hook":
        inner = f'{top(logo_uri, wk)}<h1 class="t">{head_text(s["title"])}</h1><p class="body t">{esc(s["body"])}</p>{foot(wk, FOOT_LABEL, pos)}'
        return frame_slide(inner, "hook"), True
    if s["kind"] == "question":
        cta = f'<div class="cta mono up t">{esc(r["cta_line"])}</div>' if r.get("cta_line") else ""
        inner = f'{top(logo_uri, wk)}<div class="hd"><h2 class="t">{esc(s["title"])}</h2></div>{cta}{foot(wk, FOOT_LABEL, pos)}'
        return frame_slide(inner, "q"), True
    hd = f'<div class="hd"><span class="kick mono up t">{esc(s["kicker"])}</span><h2 class="t">{esc(s["title"])}</h2><p class="body t">{esc(s["body"])}</p></div>'
    code = s.get("code")
    if code:
        tab = s["tab"]
        lang = "python" if tab.endswith(".py") else "prompt" if tab.endswith(".md") else "python"
        p, hot = pane(code, tab, lang, s.get("brass", ""), 12)
        return frame_slide(f'{top(logo_uri, wk)}{hd}{p}{foot(wk, FOOT_LABEL, pos)}', "point"), hot
    return frame_slide(f'{top(logo_uri, wk)}{hd}{foot(wk, FOOT_LABEL, pos)}', "point nocode"), True


def frame_slide(inner: str, cls: str) -> str:
    return f'<div class="slide {cls}">{inner}</div>'


def build_cutout(path: Path) -> None:
    if path.exists():
        return
    print(f"note: {path} missing; building it with headshot_cutout.py", file=sys.stderr)
    subprocess.run([sys.executable, str(ROOT / "execution/content/headshot_cutout.py"), "--out", str(path)], check=True, encoding="utf-8", errors="replace")


def data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def brass_share(png: Path) -> float:
    from PIL import Image
    with Image.open(png) as im:
        px = im.convert("RGB").resize((W // 4, H // 4)).getdata()
    hot = sum(1 for r, g, b in px if abs(r - BRASS[0]) < 40 and abs(g - BRASS[1]) < 40 and abs(b - BRASS[2]) < 40 and r > b + 40)
    return hot / len(px)


def contrast(a: tuple, b: tuple) -> float:
    def lum(c):
        ch = [v / 255 for v in c]
        ch = [v / 12.92 if v <= .03928 else ((v + .055) / 1.055) ** 2.4 for v in ch]
        return .2126 * ch[0] + .7152 * ch[1] + .0722 * ch[2]
    la, lb = sorted([lum(a), lum(b)], reverse=True)
    return (la + .05) / (lb + .05)


def thumb(png: Path, dest: Path) -> None:
    from PIL import Image
    with Image.open(png) as im:
        im.convert("RGB").resize((400, 500), Image.LANCZOS).save(dest)


def pdf_from_pngs(pngs: list[Path], dest: Path) -> None:
    from PIL import Image
    ims = [Image.open(p).convert("RGB") for p in pngs]
    ims[0].save(dest, save_all=True, append_images=ims[1:], resolution=144.0)
    for im in ims:
        im.close()


def captions_md(rows: list[dict]) -> str:
    out = ["# Captions — batch 1 v2\n", "Posting notes apply to every week: personal profile, not the company page. No link anywhere in the post or the first comment. "
           "No hashtags. Reply to every saver and commenter by DM within the day. Log per post: impressions, saves, profile views at 48 h, inbound DMs. "
           "After 6 posts: kill a format under 1 save per 500 impressions or under 1% profile-view rate; scale above 2% profile views or 1 inbound DM per 2 posts.\n"]
    for r in rows:
        fmt = {"face": "single image (4:5 PNG)", "artefact": "single image (4:5 PNG)", "carousel": f"document post (upload the PDF, {len(r.get('slides', []))} pages)"}[r["format"]]
        out.append(f"## Week {r['week']:02d} — {r['theme']} — {r['format']}\n")
        out.append(f"**Headline (on image):** {r['headline']}  \n**Original headline:** {r['headline_original']}  \n**Card fact (image only, not in caption):** {r['card_fact']}\n")
        out.append("**Caption** (" + str(len(r["caption"])) + " chars):\n\n" + r["caption"] + "\n")
        out.append(f"**Alt text:** {r['alt_text']}\n")
        notes = [f"Format: {fmt}.", "Link: none.", f"CTA: {r['cta']}." + (f" On image: '{r['cta_line']}'." if r.get("cta_line") else "")]
        if r.get("publish_guardrail", "none") != "none":
            notes.append(f"Guardrail: {r['publish_guardrail']}")
        notes.append("Measure: impressions · saves · profile views at 48 h · inbound DMs.")
        out.append("**Posting notes:** " + " ".join(notes) + "\n")
    return "\n".join(out)


def review_page(out: Path, rows: list[dict], batch: str, zip_name: str, scores: dict | None) -> None:
    blocks = []
    for r in rows:
        sc = (scores or {}).get(str(r["week"]))
        sc_html = (f'<p class="cap"><b>Jev after</b> stop {sc["stop"]} · self-relevance {sc["self_relevance"]} · generic {sc["generic"]} · curiosity {sc["curiosity"]}</p>' if sc else "")
        if r["format"] == "carousel":
            strip = "".join(f'<img src="{esc(p)}" width="216" height="270" alt="slide" loading="lazy">' for p in r["slides_png"])
            media = f'<div class="strip">{strip}</div>'
            dl = f'<a href="{esc(r["pdf"])}" download>Download PDF</a> · ' + " · ".join(f'<a href="{esc(p)}" download>slide {i + 1}</a>' for i, p in enumerate(r["slides_png"]))
        else:
            media = f'<img src="{esc(r["file"])}" width="540" height="675" alt="week {r["week"]:02d}" loading="lazy">'
            dl = f'<a href="{esc(r["file"])}" download>Download PNG</a>'
        blocks.append(f'<section><h2>wk {r["week"]:02d} · {esc(r["theme"])} <span class="m">{esc(r["format"])}</span></h2>{media}'
                      f'<p class="cap"><b>Headline</b> {esc(r["headline"])} <span class="m">was: {esc(r["headline_original"])}</span></p>'
                      f'<p class="cap"><b>Card fact</b> {esc(r["card_fact"])}</p>{sc_html}'
                      f'<pre class="caption">{esc(r["caption"])}</pre><p class="cap"><b>Alt</b> {esc(r["alt_text"])}</p><p class="cap">{dl}</p></section>')
    title = f"ProdCraft · weekly cards · {batch} (weeks 1–10, v2)"
    doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)}</title><style>
body{{margin:0;padding:48px;background:#f3f1ec;color:#17191d;font:16px/1.5 Geist,Inter,system-ui,sans-serif;max-width:1240px}}
h1{{font-family:Newsreader,Georgia,serif;font-weight:500;font-size:32px;margin:0 0 8px}}h2{{font-family:Newsreader,Georgia,serif;font-weight:500;font-size:24px;margin:48px 0 12px}}
p{{margin:0 0 12px;color:#474b53}}a{{color:#17191d}}.m{{font-family:"JetBrains Mono",monospace;font-size:13px;color:#474b53}}
img{{display:block;border:1px solid rgba(23,25,29,.18)}}.strip{{display:flex;gap:8px;flex-wrap:wrap}}.strip img{{width:216px;height:270px}}
.cap{{font-size:14px;margin:8px 0}}.cap b{{color:#17191d;font-weight:500}}pre.caption{{white-space:pre-wrap;font:15px/1.5 Geist,Inter,system-ui,sans-serif;background:#fff;padding:16px;border:1px solid rgba(23,25,29,.12);max-width:720px}}
</style></head><body><h1>{esc(title)}</h1>
<p>Single cards are 1080×1350 PNG; carousels are document posts (one PDF each, pages 1080×1350). <a href="{esc(zip_name)}" download>Download everything (zip)</a> · <a href="contact_sheet.png">contact sheet</a> · <a href="captions.md">captions.md</a> · <a href="headline_scores.json">headline_scores.json</a></p>
{"".join(blocks)}</body></html>
"""
    (out / "index.html").write_text(doc, encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--messages", default=str(ROOT / "execution/content/prodcraft_batch1_v2_messages.json"))
    ap.add_argument("--out", default=str(ROOT / "deliverables/linkedin_weekly_cards/prodcraft" / (dt.date.today().isoformat() + "-v2")))
    ap.add_argument("--fonts", default=str(ROOT / ".tmp/banners/fonts"))
    ap.add_argument("--cutout", default=str(CUTOUT))
    ap.add_argument("--logo-style", choices=sorted(LOGO_STYLES), default="ink")
    ap.add_argument("--weeks", default="", type=parse_weeks)
    ap.add_argument("--batch", default="batch1_v2")
    ap.add_argument("--scores", default="", help="headline_scores.json to show on the review page (copied into out)")
    a = ap.parse_args()

    weeks = json.loads(Path(a.messages).read_text(encoding="utf-8"))["weeks"]
    if a.weeks:
        weeks = [w for w in weeks if w["week"] in a.weeks]
    out = Path(a.out).resolve()
    for d in ("png", "html", "carousels", "thumbs"):
        (out / d).mkdir(parents=True, exist_ok=True)
    fonts_css = load_fonts(Path(a.fonts))
    logo_uri = logo_data_uri(LOGO_STYLES[a.logo_style])
    build_cutout(Path(a.cutout))
    cutout_uri = data_uri(Path(a.cutout))
    fonts_seen: set[str] = set()
    problems: list[str] = []
    rows, pngs = [], []

    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium_path())
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)

        def shoot(doc: str, name: str, dest: Path) -> dict:
            f = out / "html" / f"{name}.html"
            f.write_text(doc, encoding="utf-8")
            pg.goto(f.as_uri())
            fonts_seen.update(verify_fonts(pg))
            fit = pg.evaluate("window.fitHead && window.fitHead()")
            pg.wait_for_timeout(120)
            pg.screenshot(path=str(dest), clip={"x": 0, "y": 0, "width": W, "height": H})
            fig = pg.evaluate("() => { const f = document.querySelector('.fig'); if (!f) return null; const r = f.getBoundingClientRect();"
                              " const vis = (Math.min(r.right, 1080) - Math.max(r.left, 0)) * (Math.min(r.bottom, 1350) - Math.max(r.top, 0)); return vis / (1080 * 1350); }")
            return {"html": f"html/{name}.html", "head_px": fit[0] if fit else None, "head_lines": fit[1] if fit else None, "figure_share": fig}

        for r in weeks:
            wk = r["week"]
            name = f"{wk:02d}_week_{slugify(r['headline'])}"
            row = {**r, "layout": r["format"], "rendered_supporting_line": r["card_fact"], "visual_words": [], "receipt_rows": [], "cta_text": r.get("cta_line", "")}
            if r["format"] == "carousel":
                cdir = out / "carousels" / f"{wk:02d}"
                cdir.mkdir(exist_ok=True)
                slide_pngs, slide_meta = [], []
                n = len(r["slides"])
                for i, s in enumerate(r["slides"]):
                    doc, hot = slide_html(r, s, i, n, logo_uri)
                    doc = frame(doc, fonts_css, "", fit=(s["kind"] == "hook"))
                    dest = cdir / f"slide_{i + 1}.png"
                    meta = shoot(doc, f"{wk:02d}_slide_{i + 1}", dest)
                    if s.get("code") and not hot:
                        problems.append(f"week {wk:02d} slide {i + 1}: brass line '{s.get('brass')}' not found in code")
                    if s["kind"] == "hook" and (meta["head_lines"] or 9) > 2:
                        problems.append(f"week {wk:02d} slide 1: headline needs {meta['head_lines']} lines")
                    slide_pngs.append(dest)
                    slide_meta.append({**meta, "png": f"carousels/{wk:02d}/slide_{i + 1}.png", "kind": s["kind"]})
                    thumb(dest, out / "thumbs" / f"{wk:02d}_slide_{i + 1}.png")
                pdf = out / "carousels" / f"{name}.pdf"
                pdf_from_pngs(slide_pngs, pdf)
                row.update({"file": f"carousels/{wk:02d}/slide_1.png", "html": f"html/{wk:02d}_slide_1.html", "slides_png": [m["png"] for m in slide_meta],
                            "slides_html": [m["html"] for m in slide_meta], "pdf": f"carousels/{pdf.name}", "head_px": slide_meta[0]["head_px"], "head_lines": slide_meta[0]["head_lines"],
                            "brass_share": max(brass_share(x) for x in slide_pngs)})
                pngs.append(slide_pngs[0])
            else:
                if r["format"] == "face":
                    doc = frame(face_html(r, logo_uri, cutout_uri), fonts_css, "face")
                else:
                    inner, hot = artefact_html(r, logo_uri)
                    if not hot:
                        problems.append(f"week {wk:02d}: brass line '{r['artefact'].get('brass')}' not found in code")
                    doc = frame(inner, fonts_css, "artefact")
                dest = out / "png" / f"{name}.png"
                meta = shoot(doc, name, dest)
                thumb(dest, out / "thumbs" / f"{name}.png")
                pngs.append(dest)
                row.update({"file": f"png/{name}.png", **meta, "brass_share": brass_share(dest)})
                if (meta["head_lines"] or 9) > 2:
                    problems.append(f"week {wk:02d}: headline needs {meta['head_lines']} lines at {meta['head_px']}px")
                if r["format"] == "face" and not (FIGURE_BUDGET[0] <= (meta["figure_share"] or 0) <= FIGURE_BUDGET[1]):
                    problems.append(f"week {wk:02d}: figure covers {meta['figure_share']:.1%} (budget {FIGURE_BUDGET})")
            if row["brass_share"] > BRASS_BUDGET:
                problems.append(f"week {wk:02d}: brass {row['brass_share']:.1%} > {BRASS_BUDGET:.0%}")
            rows.append(row)
        br.close()

    # this run is the batch: stale png/html/pdf/thumbs from earlier headlines are removed so zip, sheet and index agree
    keep = {str(p.resolve()) for p in pngs}
    for r in rows:
        keep |= {str((out / x).resolve()) for x in [r.get("html"), r.get("file"), r.get("pdf"), *r.get("slides_png", []), *r.get("slides_html", [])] if x}
    keep |= {str(p.resolve()) for p in (out / "thumbs").glob("*.png") if any(p.stem == Path(k).stem or p.stem.startswith(Path(k).parent.name + "_slide") for k in keep)}
    for sub in ("png", "html", "carousels", "thumbs"):
        for stale in (out / sub).rglob("*"):
            if stale.is_file() and str(stale.resolve()) not in keep and not (sub == "thumbs" and (out / "png" / stale.name).exists()):
                stale.unlink()
                print(f"note: removed stale {stale.relative_to(out)}", file=sys.stderr)
    missing_fonts = [x for x in BRAND_FONTS if x not in fonts_seen]
    if missing_fonts:
        problems.append(f"fonts not loaded in Chromium: {missing_fonts}")
    scores = None
    if a.scores and Path(a.scores).exists():
        sj = json.loads(Path(a.scores).read_text(encoding="utf-8"))
        scores = {str(w["week"]): w["scores"] for w in sj.get("weeks", []) if w.get("scores")}
        (out / "headline_scores.json").write_text(json.dumps(sj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (out / "messages_v2.json").write_text(json.dumps({"weeks": rows, "grid": {"lockup_y": 96, "headline_top": 160, "headline_steps": HEAD_STEPS, "zone": [520, 1150], "footer_rule_y": 1210},
                                                        "contrast_ink_on_paper": round(contrast(INK, PAPER), 1)}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "captions.md").write_text(captions_md(rows), encoding="utf-8")
    contact_sheet(sorted(pngs), out / "contact_sheet.png")
    zip_name = f"prodcraft_weekly_cards_{a.batch}.zip"
    review_page(out, rows, a.batch, zip_name, scores)
    with zipfile.ZipFile(out / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for sub in ("png", "carousels"):
            for pth in sorted((out / sub).rglob("*")):
                if pth.is_file():
                    zf.write(pth, str(pth.relative_to(out)))
        for extra in ("captions.md", "messages_v2.json", "contact_sheet.png", "index.html", "headline_scores.json"):
            if (out / extra).exists():
                zf.write(out / extra, extra)
    manifest = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "size": [W, H], "weeks": [r["week"] for r in rows],
                "formats": {f: [r["week"] for r in rows if r["format"] == f] for f in ("face", "artefact", "carousel")},
                "headline_px": {r["week"]: r.get("head_px") for r in rows}, "figure_share": {r["week"]: r.get("figure_share") for r in rows if r["format"] == "face"},
                "brass_share_max": max(r["brass_share"] for r in rows), "contrast_ink_on_paper": round(contrast(INK, PAPER), 1),
                "fonts_loaded": sorted(fonts_seen), "problems": problems, "zip": zip_name, "index": "index.html", "published": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    for pr in problems:
        print("PROBLEM", pr, file=sys.stderr)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
