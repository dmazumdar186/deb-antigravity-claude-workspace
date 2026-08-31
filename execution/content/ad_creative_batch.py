"""Tier-1 compositing ad-creative batch generator (procedural HTML/CSS/SVG).

description: Renders a batch of square ad variants from a brand profile.json
    (locked visual settings) + copy_pool.json (headline/kicker/sub/CTA per
    variant), plus an interactive tuner page and a review/curation page.
    Optionally renders PNGs via Playwright (chromium).
inputs: --brand-dir <dir containing profile.json + copy_pool.json>
    [--no-render] to skip PNG rendering, [--limit N] to cap variants.
outputs: <brand-dir>/variants/variant_NN.html, <brand-dir>/renders/
    variant_NN.png, <brand-dir>/tuner.html, <brand-dir>/review.html
Directive: directives/content/ad_creative_pipeline.md (Tier 1).
Skill: .claude/skills/ad-creative/SKILL.md
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def blob_css(bg: dict) -> str:
    layers = []
    for b in bg["blobs"]:
        layers.append(
            f"radial-gradient(circle at {b['cx']*100:.0f}% {b['cy']*100:.0f}%, "
            f"{b['color']}{int(b['opacity']*255):02x} 0%, transparent {b['r']*100:.0f}%)"
        )
    layers.append(f"linear-gradient({bg['gradient_angle_deg']}deg, {bg['base']}, {bg['base']})")
    return ", ".join(layers)


def variant_html(p: dict, v: dict) -> str:
    c, f = p["canvas"], p["font"]
    g = p["grain"]
    kicker = esc(v["kicker"]).upper() if p["kicker"].get("uppercase") else esc(v["kicker"])
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="{f['google_fonts_url']}">
<style>
  html,body{{margin:0;padding:0}}
  .ad{{position:relative;width:{c['width']}px;height:{c['height']}px;overflow:hidden;
    background:{blob_css(p['background'])};background-color:{p['background']['base']};
    font-family:'{f['family']}',{f['fallback']};box-sizing:border-box;
    padding:{p['content_padding_px']}px;display:flex;flex-direction:column;justify-content:space-between}}
  .grain{{position:absolute;inset:0;opacity:{g['amount']};mix-blend-mode:{g['blend']};pointer-events:none}}
  .wordmark{{font-size:{p['wordmark']['size_px']}px;font-weight:{p['wordmark']['weight']};
    letter-spacing:{p['wordmark']['letter_spacing_em']}em;color:{p['wordmark']['color']}}}
  .mid{{display:flex;flex-direction:column;gap:{p['block_gap_px']}px}}
  .kicker{{font-size:{p['kicker']['size_px']}px;font-weight:{p['kicker']['weight']};
    letter-spacing:{p['kicker']['letter_spacing_em']}em;color:{p['kicker']['color']}}}
  .headline{{font-size:{p['headline']['size_px']}px;font-weight:{p['headline']['weight']};
    letter-spacing:{p['headline']['letter_spacing_em']}em;line-height:{p['headline']['line_height']};
    color:{p['headline']['color']};max-width:{p['headline']['max_width_px']}px;margin:0}}
  .sub{{font-size:{p['sub']['size_px']}px;font-weight:{p['sub']['weight']};line-height:{p['sub']['line_height']};
    color:{p['sub']['color']};max-width:{p['sub']['max_width_px']}px}}
  .bottom{{display:flex;align-items:center;justify-content:space-between}}
  .cta{{display:inline-block;font-size:{p['cta']['size_px']}px;font-weight:{p['cta']['weight']};
    background:{p['cta']['bg']};color:{p['cta']['fg']};padding:{p['cta']['padding']};
    border-radius:{p['cta']['radius_px']}px}}
  .footer{{font-size:{p['footer']['size_px']}px;color:{p['footer']['color']}}}
</style></head><body>
<div class="ad">
  <svg class="grain" width="100%" height="100%"><filter id="n">
    <feTurbulence type="fractalNoise" baseFrequency="{0.9/g['size']:.3f}" numOctaves="2" seed="{g['seed']}" stitchTiles="stitch"/>
    <feColorMatrix type="saturate" values="0"/></filter>
    <rect width="100%" height="100%" filter="url(#n)"/></svg>
  <div class="wordmark">{esc(p['wordmark']['text'])}</div>
  <div class="mid">
    <div class="kicker">{kicker}</div>
    <h1 class="headline">{esc(v['headline'])}</h1>
    <div class="sub">{esc(v['sub'])}</div>
  </div>
  <div class="bottom">
    <span class="cta">{esc(v['cta'])}</span>
    <span class="footer">{esc(p['footer']['text'])}</span>
  </div>
</div></body></html>"""


def review_html(pool: dict, rendered: bool) -> str:
    cards = []
    for v in pool["variants"]:
        nn = f"{v['id']:02d}"
        media = (
            f'<img src="renders/variant_{nn}.png" loading="lazy">'
            if rendered
            else f'<iframe src="variants/variant_{nn}.html" scrolling="no"></iframe>'
        )
        cards.append(
            f'<label class="card"><input type="checkbox" data-nn="{nn}">{media}'
            f'<div class="meta">#{nn} · {esc(v["angle"])} · {esc(v["headline"][:60])}</div></label>'
        )
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>ProdCraft ad batch review</title>
<style>
  body{{font-family:'Segoe UI',Arial,sans-serif;background:#14161d;color:#eee;margin:0;padding:24px}}
  h1{{font-size:20px}} .grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));gap:16px}}
  .card{{display:block;background:#1d2029;border-radius:10px;padding:10px;cursor:pointer;border:2px solid transparent}}
  .card:has(input:checked){{border-color:#7c9dff}}
  .card img,.card iframe{{width:100%;aspect-ratio:1;border:0;border-radius:6px;pointer-events:none;transform-origin:top left}}
  .meta{{font-size:12px;color:#aab;margin-top:8px}} input{{position:absolute;opacity:0}}
  button{{position:fixed;bottom:20px;right:20px;padding:14px 22px;border-radius:999px;border:0;
    background:#7c9dff;color:#101218;font-weight:700;font-size:15px;cursor:pointer}}
</style></head><body>
<h1>Review — check the winners, then Download selected. Human curates; nothing auto-picked.</h1>
<div class="grid">{''.join(cards)}</div>
<button onclick="dl()">Download selected</button>
<script>
function dl(){{document.querySelectorAll('input:checked').forEach(cb=>{{
  const a=document.createElement('a');a.href='renders/variant_'+cb.dataset.nn+'.png';
  a.download='prodcraft_ad_'+cb.dataset.nn+'.png';document.body.appendChild(a);a.click();a.remove();}});}}
</script></body></html>"""


def tuner_html(p: dict) -> str:
    profile_js = json.dumps(p)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8"><title>Ad tuner</title>
<style>body{{margin:0;display:flex;font-family:'Segoe UI',Arial,sans-serif;background:#14161d;color:#eee}}
#panel{{width:340px;padding:16px;overflow-y:auto;height:100vh;box-sizing:border-box}}
#panel label{{display:block;font-size:12px;margin:10px 0 2px;color:#aab}}
#panel input,#panel select{{width:100%}}#stage{{flex:1;display:flex;align-items:center;justify-content:center;height:100vh}}
iframe{{width:540px;height:540px;border:0;border-radius:8px;background:#000}}
button{{margin-top:14px;width:100%;padding:10px;border-radius:8px;border:0;background:#7c9dff;font-weight:700;cursor:pointer}}
textarea{{width:100%;height:120px;margin-top:8px;background:#0c0e13;color:#9fd;border:1px solid #333}}</style>
</head><body>
<div id="panel">
  <h3>Ad tuner</h3>
  <label>Gradient angle (<span id="av"></span>deg)</label><input type="range" id="angle" min="0" max="360" step="1">
  <label>Grain amount</label><input type="range" id="gamt" min="0" max="0.3" step="0.01">
  <label>Grain size</label><input type="range" id="gsize" min="0.5" max="5" step="0.1">
  <label>Grain seed</label><input type="range" id="gseed" min="1" max="40" step="1">
  <label>Grain blend</label><select id="gblend"><option>overlay</option><option>multiply</option><option>soft-light</option><option>screen</option></select>
  <label>Font</label><select id="font"><option>Manrope</option><option>Inter</option><option>Sora</option><option>Bricolage Grotesque</option><option>Red Hat Display</option></select>
  <label>Headline size</label><input type="range" id="hsize" min="48" max="130" step="2">
  <label>Letter spacing (em)</label><input type="range" id="hspace" min="-0.06" max="0.05" step="0.005">
  <label>Line height</label><input type="range" id="hline" min="0.9" max="1.5" step="0.02">
  <label>Content padding</label><input type="range" id="pad" min="40" max="160" step="4">
  <label>Block gap</label><input type="range" id="gap" min="10" max="80" step="2">
  <label>CTA style</label><select id="ctastyle"><option>pill</option><option>plain</option></select>
  <label>CTA copy</label><input type="text" id="ctacopy">
  <button onclick="exportSettings()">Export Settings (JSON)</button>
  <textarea id="out" placeholder="Exported JSON appears here — save as profile.json and re-run the batch."></textarea>
</div>
<div id="stage"><iframe id="prev"></iframe></div>
<script>
const P = {profile_js};
const $ = id => document.getElementById(id);
function init(){{
  $('angle').value=P.background.gradient_angle_deg; $('gamt').value=P.grain.amount;
  $('gsize').value=P.grain.size; $('gseed').value=P.grain.seed; $('gblend').value=P.grain.blend;
  $('font').value=P.font.family; $('hsize').value=P.headline.size_px;
  $('hspace').value=P.headline.letter_spacing_em; $('hline').value=P.headline.line_height;
  $('pad').value=P.content_padding_px; $('gap').value=P.block_gap_px;
  $('ctastyle').value=P.cta.style; $('ctacopy').value='Book an intro call';
}}
function sync(){{
  P.background.gradient_angle_deg=+$('angle').value; $('av').textContent=$('angle').value;
  P.grain.amount=+$('gamt').value; P.grain.size=+$('gsize').value; P.grain.seed=+$('gseed').value;
  P.grain.blend=$('gblend').value; P.font.family=$('font').value;
  P.font.google_fonts_url='https://fonts.googleapis.com/css2?family='+P.font.family.replaceAll(' ','+')+':wght@400;600;800&display=swap';
  P.headline.size_px=+$('hsize').value; P.headline.letter_spacing_em=+$('hspace').value;
  P.headline.line_height=+$('hline').value; P.content_padding_px=+$('pad').value;
  P.block_gap_px=+$('gap').value; P.cta.style=$('ctastyle').value;
  if(P.cta.style==='plain'){{P.cta.bg='transparent';P.cta.fg='#f4f4f6';}}else{{P.cta.bg='#f4f4f6';P.cta.fg='#0b0d14';}}
  render();
}}
function blobCss(bg){{
  const L=bg.blobs.map(b=>`radial-gradient(circle at ${{b.cx*100}}% ${{b.cy*100}}%, ${{b.color}}${{Math.round(b.opacity*255).toString(16).padStart(2,'0')}} 0%, transparent ${{b.r*100}}%)`);
  L.push(`linear-gradient(${{bg.gradient_angle_deg}}deg, ${{bg.base}}, ${{bg.base}})`);
  return L.join(', ');
}}
function render(){{
  const v={{kicker:'FRACTIONAL AI ENGINEERING',headline:'The senior AI engineer your roadmap is missing.',
    sub:'Production AI systems shipped in weeks - no full-time hire, no agency overhead.',cta:$('ctacopy').value}};
  const html=`<!DOCTYPE html><html><head><link rel="stylesheet" href="${{P.font.google_fonts_url}}"><style>
  html,body{{margin:0}} .ad{{position:relative;width:1080px;height:1080px;overflow:hidden;transform:scale(0.5);transform-origin:top left;
  background:${{blobCss(P.background)}};background-color:${{P.background.base}};font-family:'${{P.font.family}}',sans-serif;
  box-sizing:border-box;padding:${{P.content_padding_px}}px;display:flex;flex-direction:column;justify-content:space-between}}
  .grain{{position:absolute;inset:0;opacity:${{P.grain.amount}};mix-blend-mode:${{P.grain.blend}}}}
  .wm{{font-size:${{P.wordmark.size_px}}px;font-weight:800;color:${{P.wordmark.color}}}}
  .mid{{display:flex;flex-direction:column;gap:${{P.block_gap_px}}px}}
  .k{{font-size:${{P.kicker.size_px}}px;font-weight:600;letter-spacing:.14em;color:${{P.kicker.color}}}}
  .h{{font-size:${{P.headline.size_px}}px;font-weight:800;letter-spacing:${{P.headline.letter_spacing_em}}em;line-height:${{P.headline.line_height}};color:#fff;max-width:880px;margin:0}}
  .s{{font-size:${{P.sub.size_px}}px;color:${{P.sub.color}};max-width:760px;line-height:1.35}}
  .b{{display:flex;justify-content:space-between;align-items:center}}
  .c{{font-size:${{P.cta.size_px}}px;font-weight:700;background:${{P.cta.bg}};color:${{P.cta.fg}};padding:${{P.cta.padding}};border-radius:${{P.cta.radius_px}}px}}
  .f{{font-size:${{P.footer.size_px}}px;color:${{P.footer.color}}}}</style></head><body><div class="ad">
  <svg class="grain" width="100%" height="100%"><filter id="n"><feTurbulence type="fractalNoise" baseFrequency="${{(0.9/P.grain.size).toFixed(3)}}" numOctaves="2" seed="${{P.grain.seed}}" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/></filter><rect width="100%" height="100%" filter="url(#n)"/></svg>
  <div class="wm">${{P.wordmark.text}}</div><div class="mid"><div class="k">${{v.kicker}}</div><h1 class="h">${{v.headline}}</h1><div class="s">${{v.sub}}</div></div>
  <div class="b"><span class="c">${{v.cta}}</span><span class="f">${{P.footer.text}}</span></div></div></body></html>`;
  $('prev').srcdoc=html;
}}
function exportSettings(){{ $('out').value=JSON.stringify(P,null,2); }}
document.querySelectorAll('#panel input,#panel select').forEach(el=>el.addEventListener('input',sync));
init(); sync();
</script></body></html>"""


def main() -> int:
    ap = argparse.ArgumentParser(description="Tier-1 compositing ad batch generator")
    ap.add_argument("--brand-dir", required=True)
    ap.add_argument("--no-render", action="store_true", help="skip Playwright PNG rendering")
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()

    brand = Path(args.brand_dir).resolve()
    profile = json.loads((brand / "profile.json").read_text(encoding="utf-8-sig"))
    pool = json.loads((brand / "copy_pool.json").read_text(encoding="utf-8-sig"))
    variants = pool["variants"][: args.limit] if args.limit else pool["variants"]

    vdir = brand / "variants"
    vdir.mkdir(exist_ok=True)
    for v in variants:
        (vdir / f"variant_{v['id']:02d}.html").write_text(variant_html(profile, v), encoding="utf-8")
    (brand / "tuner.html").write_text(tuner_html(profile), encoding="utf-8")

    rendered = False
    if not args.no_render:
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            print("WARN: playwright not installed - skipping PNG render (review page will use iframes)")
        else:
            rdir = brand / "renders"
            rdir.mkdir(exist_ok=True)
            with sync_playwright() as pw:
                browser = pw.chromium.launch()
                page = browser.new_page(viewport={"width": profile["canvas"]["width"], "height": profile["canvas"]["height"]})
                for v in variants:
                    nn = f"{v['id']:02d}"
                    page.goto((vdir / f"variant_{nn}.html").as_uri())
                    page.wait_for_load_state("networkidle")
                    page.evaluate("document.fonts.ready")
                    page.screenshot(path=str(rdir / f"variant_{nn}.png"))
                    print(f"rendered variant_{nn}.png")
                browser.close()
            rendered = True

    (brand / "review.html").write_text(review_html({"variants": variants}, rendered), encoding="utf-8")
    print(f"DONE: {len(variants)} variants -> {vdir}; rendered={rendered}; review: {brand / 'review.html'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
