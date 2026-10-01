"""
description: Render the ProdCraft LinkedIn banner set (20 editorial, brand-matched posters) as PNG, a clickable PDF carousel, animated GIF/MP4 hero cards, captions and a review page.
inputs: --out <dir> (default deliverables/linkedin_banners/prodcraft/<date>); --fonts <dir with fonts_local.css>; --logo <png>; --animate N
outputs: <out>/png/NN_slug.png, <out>/html/, <out>/carousel.pdf, <out>/animated/, <out>/captions.md, <out>/review.html
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import io
import json
import os
import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, H = 1080, 1350  # LinkedIn 4:5 portrait — max feed real estate

LINKS = {
    "call": "https://cal.com/debanjan-mazumdar-ben5rd/30min",
    "site": "https://prodcraft.fyi",
    "github": "https://github.com/dmazumdar186",
    "linkedin": "https://www.linkedin.com/in/dmazumdar/",
}

# Every number below is a published proof point on prodcraft.fyi (fetched 2026-10-01).
VARIANTS = [
    dict(slug="receipts", layout="ledger", kicker="The receipts, not the pitch",
         head="Three numbers I’d rather show you than a slide deck.",
         rows=[("$1M+", "qualified pipeline from one outbound system"),
               ("+45%", "feature adoption on an enterprise GenAI product"),
               ("<30 days", "median ship cycle across 5+ live AI products")],
         note="all three are live — stress-test them on the call"),
    dict(slug="48k-emails", layout="bignum", kicker="Outbound engine · US consultancy",
         num="48,000", unit="cold emails / month", sub="4%+ reply rate. $1M+ pipeline. A 4-SDR team replaced at roughly a tenth of the cost.",
         note="Cloudflare Workers + Instantly + GHL — the whole thing is idempotent"),
    dict(slug="latency", layout="beforeafter", kicker="Enterprise GenAI / RAG · in production",
         head="Same product. Six weeks later.",
         left=("Before", ["slow p95 responses", "features nobody opened", "one LLM, one bill"]),
         right=("After", ["−55% p95 latency", "+45% feature adoption", "multi-LLM routing + eval harness"]),
         note="the latency win was prompt-cache hits, not a bigger model"),
    dict(slug="not-an-agency", layout="margin", kicker="How I work",
         para="No account manager. No junior hand-offs. No “discovery phase” invoice. You talk to the person who writes the code, and the code ships in weeks, not quarters.",
         hl="the person who writes the code", note="15+ yrs · Paris · one operator"),
    dict(slug="walk-away", layout="checklist", kicker="Terms, in plain English",
         head="Walk-away terms from day one.",
         items=["All code in your repo, from the first commit", "All credentials in your vault, never mine", "No retainer lock-in, no exit fee", "Documentation a mid-level engineer can run"],
         note="if you can’t leave, it isn’t your system"),
    dict(slug="cv-optimizer", layout="terminal", kicker="Live SaaS · cv-optimizer.pages.dev",
         lines=["$ paste cv.pdf  --locale fr  --jd job.txt", "✓ langdetect: 42/42 fields in target locale", "✓ recruiter-proxy eval: 95% pass", "✓ golden-screenshot diff: 0 regressions", "→ shipped. ships only when 95% of fields pass."],
         head="Eval-first, or it doesn’t ship.", note="Cloudflare Pages + Worker + Gemini"),
    dict(slug="video-studio", layout="timeline", kicker="ProdCraft AI Video Studio",
         head="Topic prompt to public YouTube video in eight minutes.",
         steps=[("00:00", "topic"), ("01:30", "script + voice clone"), ("05:00", "Remotion render"), ("08:00", "uploaded")],
         note="≈ $0 marginal cost per video · weekly cadence"),
    dict(slug="mobile-14-days", layout="bignum", kicker="Mobile · Expo + EAS",
         num="14", unit="days from idea to TestFlight", sub="iOS and Android from one codebase. No Mac required. AI features (transcription, summaries, agents) wired in from day one.",
         note="2-pass security audit before any store submission"),
    dict(slug="operator-stack", layout="stack", kicker="What’s actually in the box",
         head="The stack I ship on.",
         tags=["Claude Code", "Cloudflare Workers", "Modal", "n8n", "Supabase", "Instantly", "GoHighLevel", "Vapi / Retell", "Remotion", "Expo / EAS", "Gemini", "MCP servers"],
         note="pick what fits — nothing here is a lock-in"),
    dict(slug="sdr-math", layout="ledger", kicker="The SDR math",
         head="What one outbound system replaced.",
         rows=[("$200K/yr", "SDR headcount cost removed"), ("4 SDRs", "worth of volume, automated"), ("~1/10", "of the cost to run it")],
         note="reply detection + CRM sync + kill switch included"),
    dict(slug="voice-agent", layout="margin", kicker="24/7 AI sales assistants",
         para="A voice agent that picks up on the first ring, qualifies, books the slot, and writes the transcript straight into your CRM. Vapi or Retell, your number, your script.",
         hl="writes the transcript straight into your CRM", note="sandbox demo on request — hear it before you buy it"),
    dict(slug="before-you-hire", layout="beforeafter", kicker="Before you post that job",
         head="Senior AI hire vs. ProdCraft.",
         left=("Full-time hire", ["3–6 months to start", "salary + equity + ramp", "one person’s stack"]),
         right=("ProdCraft", ["first commit this week", "walk-away terms", "12+ AI systems shipped"]),
         note="I’m not against hiring — I’m against waiting"),
    dict(slug="shipped-list", layout="checklist", kicker="Systems we’ve shipped",
         head="Real builds. Real metrics. Touchable demos.",
         items=["Always-on outbound engine — $1M+ pipeline", "Enterprise GenAI adoption driver — +45%", "Multi-lingual CV optimizer — live SaaS", "AI video studio — 8 min to upload", "14-day mobile pipeline — iOS + Android"],
         note="two of these you can click on the site right now"),
    dict(slug="kill-switch", layout="terminal", kicker="Engineering that survives Monday",
         lines=["sentinel: idempotent per-lead keys", "dedup: cross-run, cross-campaign", "kill-switch: per campaign, one flag", "reply-detect: dual path (webhook + poll)", "status: 48k/mo, 0 duplicate sends"],
         head="Boring plumbing is the product.", note="this is why the pipeline number is real"),
    dict(slug="paris-founder", layout="quote", kicker="Debanjan Mazumdar · Founder, ProdCraft",
         quote="I spent 15 years shipping products for other people. Now I ship AI systems for founders who are done waiting on roadmaps.",
         note="Paris · EN / FR · built with Claude Code"),
    dict(slug="three-things", layout="stack", kicker="Three things we ship, fast",
         head="Outbound. Voice. Custom AI ops.",
         tags=["Cold-email systems", "Inbox warmup", "AI first lines", "Voice + chat agents", "Inbound qualification", "RAG / document Q&A", "Internal copilots", "Multi-agent orchestration", "Modal + Cloudflare deploys"],
         note="senior operator on every call"),
    dict(slug="hours-saved", layout="bignum", kicker="Claude Code operator stack",
         num="$10K", unit="per week in headcount cost saved", sub="Multi-agent orchestration, MCP servers, internal copilots and audit loops that harden their own code.",
         note="12+ AI systems · 100+ hrs/wk automated"),
    dict(slug="objections", layout="ledger", kicker="The three objections, answered",
         head="“But what if…”",
         rows=[("…you leave?", "you keep everything — repo, keys, docs"), ("…it breaks?", "eval harness + kill switch on every system"), ("…it’s a demo?", "two live products on the site, paste a CV")],
         note="ask the fourth one on the call"),
    dict(slug="how-it-starts", layout="timeline", kicker="How a build starts",
         head="From a 30-minute call to a shipped system.",
         steps=[("Day 0", "free build session"), ("Day 2", "scoped, priced, repo created"), ("Week 2", "first version in your stack"), ("Week 4", "live, documented, yours")],
         note="median <30 days — the receipts above are from this process"),
    dict(slug="book-call", layout="cta", kicker="Free build session · 30 min",
         head="Bring the roadmap. Leave with a build plan.",
         sub="No pitch deck. We look at your stack, pick the one system worth shipping first, and I tell you honestly if it’s not me.",
         note="scan or tap — the link is in the first comment"),
]

CSS = r"""
:root{--bone:#f7f3ec;--bone2:#efe9df;--ink:#16181c;--ink7:#3d4148;--ink8:#25282e;--brass:#c8a35c;--brass5:#aa8638;--slate:#283848;--rule:rgba(22,24,28,.14)}
*{box-sizing:border-box}html,body{margin:0;padding:0;background:#ddd}
.card{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--bone);color:var(--ink);font-family:Geist,system-ui,sans-serif;padding:72px 76px 0;display:flex;flex-direction:column}
.card.dark{background:var(--ink);color:var(--bone);--rule:rgba(247,243,236,.16);--ink7:#b9b4aa;--ink8:#d9d4ca}
.paper{position:absolute;inset:0;pointer-events:none;opacity:.5;mix-blend-mode:multiply}
.dark .paper{opacity:.18;mix-blend-mode:screen}
.serif{font-family:Newsreader,Georgia,serif}.mono{font-family:'JetBrains Mono',monospace}.hand{font-family:Caveat,cursive}
.top{display:flex;align-items:center;justify-content:space-between;z-index:2}
.brand{display:flex;align-items:center;gap:16px}.brand img{width:64px;height:64px}
.brand .wm{font-family:Newsreader;font-weight:600;font-size:40px;letter-spacing:-.01em}
.tag{font-family:'JetBrains Mono';font-size:18px;letter-spacing:.08em;text-transform:uppercase;color:var(--ink7)}
.kicker{margin-top:84px;font-family:'JetBrains Mono';font-size:21px;letter-spacing:.12em;text-transform:uppercase;color:var(--brass5)}
.dark .kicker{color:var(--brass)}
h1{font-family:Newsreader;font-weight:500;font-size:84px;line-height:1.02;letter-spacing:-.025em;margin:22px 0 0;max-width:900px;text-wrap:balance}
h1 em{font-style:italic;font-weight:400}
.body{flex:1;position:relative;z-index:2}
.rail{margin-top:auto;border-top:2px solid var(--ink);padding:26px 0 48px;display:flex;align-items:center;justify-content:space-between;gap:24px;z-index:2}
.dark .rail{border-color:var(--bone)}
.links{display:flex;flex-direction:column;gap:10px}
.lnk{display:flex;align-items:center;gap:14px;font-family:'JetBrains Mono';font-size:20px;color:inherit;text-decoration:none}
.lnk b{font-family:Geist;font-weight:600;font-size:20px;min-width:118px}
.lnk span{opacity:.75}
.qr{display:flex;align-items:center;gap:16px}.qr img{width:124px;height:124px;border:2px solid var(--ink);padding:6px;background:#fff;border-radius:6px}
.dark .qr img{border-color:var(--bone)}
.qr .hand{font-size:28px;color:var(--brass5);max-width:150px;line-height:1;transform:rotate(-4deg)}
.note{position:absolute;right:0;bottom:36px;font-family:Caveat;font-size:40px;color:var(--brass5);max-width:520px;line-height:1.05;transform:rotate(-2.5deg);text-align:right}
.dark .note{color:var(--brass)}
.hl{background:linear-gradient(transparent 55%,rgba(200,163,92,.55) 55%,rgba(200,163,92,.55) 92%,transparent 92%)}
/* ledger */
.ledger{margin-top:56px;border-top:1px solid var(--rule)}
.ledger .row{display:grid;grid-template-columns:330px 1fr;gap:28px;align-items:baseline;padding:26px 0;border-bottom:1px solid var(--rule)}
.ledger .n{font-family:'JetBrains Mono';font-size:62px;font-weight:500;letter-spacing:-.03em}
.ledger .l{font-size:27px;line-height:1.3;color:var(--ink7)}
/* bignum */
.bignum{margin-top:40px}.bignum .n{font-family:'JetBrains Mono';font-weight:500;font-size:250px;line-height:.95;letter-spacing:-.06em}
.bignum .u{font-family:Newsreader;font-size:52px;font-style:italic;margin-top:8px}
.bignum .s{font-size:29px;line-height:1.4;color:var(--ink7);margin-top:44px;max-width:860px}
/* before/after */
.ba{display:grid;grid-template-columns:1fr 1fr;gap:0;margin-top:56px;border:1.5px solid var(--ink);border-radius:8px;overflow:hidden}
.dark .ba{border-color:var(--bone)}
.ba .col{padding:34px 36px}.ba .col+.col{border-left:1.5px solid var(--ink)}
.dark .ba .col+.col{border-left-color:var(--bone)}
.ba .col.hot{background:var(--ink);color:var(--bone)}.dark .ba .col.hot{background:var(--bone);color:var(--ink)}
.ba h3{margin:0 0 20px;font-family:'JetBrains Mono';font-weight:500;font-size:20px;letter-spacing:.1em;text-transform:uppercase}
.ba li{font-family:Newsreader;font-size:33px;line-height:1.25;margin:0 0 18px;list-style:none;padding-left:34px;position:relative}
.ba li:before{content:'—';position:absolute;left:0;opacity:.5}.ba .hot li:before{content:'✓';color:var(--brass)}
.ba ul{padding:0;margin:0}
/* margin */
.para{margin-top:48px;font-family:Newsreader;font-size:58px;line-height:1.22;letter-spacing:-.015em;max-width:900px;text-wrap:pretty}
/* checklist */
.cl{margin-top:48px;padding:0;margin-bottom:0}.cl li{list-style:none;display:flex;gap:26px;align-items:flex-start;padding:20px 0;border-bottom:1px solid var(--rule);font-size:33px;line-height:1.25}
.cl .box{flex:none;width:40px;height:40px;border:2px solid var(--ink);border-radius:5px;position:relative;margin-top:2px}
.dark .cl .box{border-color:var(--bone)}
.cl .box svg{position:absolute;left:-6px;top:-14px;width:58px;height:58px}
/* terminal */
.term{margin-top:48px;background:var(--ink);color:var(--bone);border-radius:12px;padding:34px 38px;font-family:'JetBrains Mono';font-size:25px;line-height:1.75;box-shadow:0 30px 60px rgba(22,24,28,.18)}
.dark .term{background:#0e1013;border:1px solid rgba(247,243,236,.15)}
.term .dots{display:flex;gap:10px;margin-bottom:18px}.term .dots i{width:14px;height:14px;border-radius:50%;background:rgba(247,243,236,.25)}
.term .ok{color:#9ad0a2}.term .arr{color:var(--brass)}
/* timeline */
.tl{margin-top:64px;display:flex;flex-direction:column;position:relative;padding-left:40px;border-left:2px solid var(--ink)}
.dark .tl{border-color:var(--bone)}
.tl .st{position:relative;padding:0 0 42px}.tl .st:before{content:'';position:absolute;left:-49px;top:14px;width:16px;height:16px;border-radius:50%;background:var(--brass)}
.tl .t{font-family:'JetBrains Mono';font-size:21px;letter-spacing:.08em;color:var(--brass5)}.dark .tl .t{color:var(--brass)}
.tl .d{font-family:Newsreader;font-size:44px;line-height:1.1;margin-top:4px}
/* stack */
.tags{margin-top:56px;display:flex;flex-wrap:wrap;gap:16px}
.tags span{font-family:'JetBrains Mono';font-size:26px;padding:16px 26px;border:1.5px solid var(--ink);border-radius:999px}
.dark .tags span{border-color:var(--bone)}.tags span:nth-child(3n){background:var(--ink);color:var(--bone)}.dark .tags span:nth-child(3n){background:var(--bone);color:var(--ink)}
/* quote */
.quote{margin-top:72px;font-family:Newsreader;font-style:italic;font-weight:400;font-size:66px;line-height:1.15;letter-spacing:-.02em;max-width:920px;text-indent:-.4em}
.who{margin-top:44px;display:flex;align-items:center;gap:20px;font-size:26px;color:var(--ink7)}.who i{display:block;width:60px;height:2px;background:var(--brass)}
/* cta */
.cta .sub{font-size:30px;line-height:1.45;color:var(--ink7);margin-top:36px;max-width:860px}
.btn{display:inline-flex;align-items:center;gap:18px;margin-top:56px;background:var(--ink);color:var(--bone);font-family:Geist;font-weight:600;font-size:34px;padding:26px 44px;border-radius:12px;text-decoration:none}
.dark .btn{background:var(--brass);color:var(--ink)}
/* hand marks */
.scribble{position:absolute;pointer-events:none}
/* animation */
.anim .body>*{animation:rise .9s cubic-bezier(.2,.7,.2,1) both}
.anim .body>*:nth-child(2){animation-delay:.25s}.anim .body>*:nth-child(3){animation-delay:.5s}.anim .body>*:nth-child(4){animation-delay:.75s}
.anim .rail{animation:rise .9s 1s both}.anim .note{animation:ink 1.2s 1.3s both}
@keyframes rise{from{opacity:0;transform:translateY(28px)}to{opacity:1;transform:none}}
@keyframes ink{from{opacity:0;clip-path:inset(0 100% 0 0)}to{opacity:1;clip-path:inset(0 0 0 0)}}
"""

PAPER = """<svg class="paper" width="100%" height="100%"><filter id="p"><feTurbulence type="fractalNoise" baseFrequency=".9" numOctaves="3" seed="{seed}" stitchTiles="stitch"/><feColorMatrix type="saturate" values="0"/><feComponentTransfer><feFuncA type="table" tableValues="0 .22"/></feComponentTransfer></filter><rect width="100%" height="100%" filter="url(#p)"/></svg>"""

TICK = '<svg viewBox="0 0 60 60"><path d="M12 32 C20 38 24 46 27 46 C31 44 40 22 54 10" fill="none" stroke="#aa8638" stroke-width="5" stroke-linecap="round"/></svg>'


def rough_underline(x, y, w, color="#c8a35c"):
    return (f'<svg class="scribble" style="left:{x}px;top:{y}px" width="{w}" height="26" viewBox="0 0 {w} 26">'
            f'<path d="M4 14 C {w*.2} 4, {w*.4} 22, {w*.6} 12 S {w*.9} 6, {w-4} 14" fill="none" stroke="{color}" stroke-width="7" stroke-linecap="round" opacity=".9"/>'
            f'<path d="M10 20 C {w*.3} 14, {w*.6} 24, {w-12} 18" fill="none" stroke="{color}" stroke-width="4" stroke-linecap="round" opacity=".55"/></svg>')


def circle_mark(x, y, w, h, color="#c8a35c"):
    return (f'<svg class="scribble" style="left:{x}px;top:{y}px" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
            f'<path d="M{w*.5} 6 C {w*.9} 2, {w-4} {h*.3}, {w-6} {h*.55} C {w-8} {h*.9}, {w*.6} {h-4}, {w*.35} {h-5} C {w*.08} {h-6}, 4 {h*.7}, 6 {h*.45} C 8 {h*.15}, {w*.3} 4, {w*.62} 8"'
            f' fill="none" stroke="{color}" stroke-width="5" stroke-linecap="round" opacity=".9"/></svg>')


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;")


def body_html(v):
    L = v["layout"]
    k = f'<div class="kicker">{esc(v["kicker"])}</div>'
    if L == "ledger":
        rows = "".join(f'<div class="row"><div class="n">{esc(n)}</div><div class="l">{esc(l)}</div></div>' for n, l in v["rows"])
        return k + f'<h1>{esc(v["head"])}</h1><div class="ledger">{rows}</div>'
    if L == "bignum":
        return k + f'<div class="bignum"><div class="n">{esc(v["num"])}</div><div class="u serif">{esc(v["unit"])}</div><div class="s">{esc(v["sub"])}</div></div>' + rough_underline(0, 560, 520)
    if L == "beforeafter":
        def col(t, items, hot):
            return f'<div class="col{" hot" if hot else ""}"><h3>{esc(t)}</h3><ul>' + "".join(f"<li>{esc(i)}</li>" for i in items) + "</ul></div>"
        return k + f'<h1>{esc(v["head"])}</h1><div class="ba">{col(*v["left"], False)}{col(*v["right"], True)}</div>'
    if L == "margin":
        p = esc(v["para"]).replace(esc(v["hl"]), f'<span class="hl">{esc(v["hl"])}</span>')
        return k + f'<p class="para">{p}</p>'
    if L == "checklist":
        items = "".join(f'<li><span class="box">{TICK}</span><span>{esc(i)}</span></li>' for i in v["items"])
        return k + f'<h1>{esc(v["head"])}</h1><ul class="cl">{items}</ul>'
    if L == "terminal":
        def ln(s):
            c = "ok" if s.startswith("✓") else "arr" if s.startswith("→") else ""
            return f'<div class="{c}">{esc(s)}</div>'
        return k + f'<h1>{esc(v["head"])}</h1><div class="term"><div class="dots"><i></i><i></i><i></i></div>' + "".join(ln(s) for s in v["lines"]) + "</div>"
    if L == "timeline":
        st = "".join(f'<div class="st"><div class="t">{esc(t)}</div><div class="d">{esc(d)}</div></div>' for t, d in v["steps"])
        return k + f'<h1>{esc(v["head"])}</h1><div class="tl">{st}</div>'
    if L == "stack":
        return k + f'<h1>{esc(v["head"])}</h1><div class="tags">' + "".join(f"<span>{esc(t)}</span>" for t in v["tags"]) + "</div>"
    if L == "quote":
        return k + f'<p class="quote">“{esc(v["quote"])}”</p><div class="who"><i></i>Debanjan Mazumdar, Founder</div>'
    if L == "cta":
        return k + f'<div class="cta"><h1>{esc(v["head"])}</h1><p class="sub">{esc(v["sub"])}</p><a class="btn" href="{LINKS["call"]}">Book a free build session <span>→</span></a></div>' + circle_mark(-18, 470, 560, 120)
    raise ValueError(L)


def card_html(v, i, logo_uri, qr_uri, fonts_css, dark, anim=False):
    note = f'<div class="note">{esc(v["note"])}</div>' if v.get("note") else ""
    links = (f'<div class="links">'
             f'<a class="lnk" href="{LINKS["call"]}"><b>Book a call</b><span>cal.com/debanjan-mazumdar-ben5rd/30min</span></a>'
             f'<a class="lnk" href="{LINKS["site"]}"><b>Website</b><span>prodcraft.fyi</span></a>'
             f'<a class="lnk" href="{LINKS["github"]}"><b>Code</b><span>github.com/dmazumdar186</span></a></div>')
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css}{CSS}</style></head><body>
<div class="card{' dark' if dark else ''}{' anim' if anim else ''}">{PAPER.format(seed=i + 3)}
<div class="top"><div class="brand"><img src="{logo_uri}" alt="ProdCraft logo"><span class="wm">ProdCraft</span></div><span class="tag">{i:02d} / 20 · Paris</span></div>
<div class="body">{body_html(v)}{note}</div>
<div class="rail">{links}<div class="qr"><span class="hand">scan to book →</span><img src="{qr_uri}" alt="QR: book a call"></div></div>
</div></body></html>"""


def qr_data_uri(url):
    import qrcode
    img = qrcode.make(url, border=0, box_size=8)
    b = io.BytesIO(); img.save(b, format="PNG")
    return "data:image/png;base64," + base64.b64encode(b.getvalue()).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "deliverables/linkedin_banners/prodcraft" / dt.date.today().isoformat()))
    ap.add_argument("--fonts", default=str(ROOT / ".tmp/banners/fonts"))
    ap.add_argument("--logo", default=str(ROOT / ".tmp/banners/logo.png"))
    ap.add_argument("--animate", type=int, default=3)
    a = ap.parse_args()
    out = Path(a.out); (out / "png").mkdir(parents=True, exist_ok=True); (out / "html").mkdir(exist_ok=True); (out / "animated").mkdir(exist_ok=True)
    fonts_dir = Path(a.fonts)
    fonts_css = (fonts_dir / "fonts_local.css").read_text().replace("url(", f"url(file://{fonts_dir}/")
    logo_uri = "data:image/png;base64," + base64.b64encode(Path(a.logo).read_bytes()).decode()
    shutil.copy(a.logo, out / "logo.png")
    qr = qr_data_uri(LINKS["call"])
    dark_idx = {6, 9, 14, 17}  # a few ink-on-dark cards so the feed doesn't read as one template

    from playwright.sync_api import sync_playwright
    pages_html, captions = [], []
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=os.environ.get("PW_CHROME") or next((str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")), None))
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for i, v in enumerate(VARIANTS, 1):
            html = card_html(v, i, logo_uri, qr, fonts_css, i in dark_idx)
            f = out / "html" / f"{i:02d}_{v['slug']}.html"; f.write_text(html)
            pg.goto(f.as_uri()); pg.wait_for_timeout(150)
            pg.screenshot(path=str(out / "png" / f"{i:02d}_{v['slug']}.png"), clip={"x": 0, "y": 0, "width": W, "height": H})
            pages_html.append(html)
            head = v.get("head") or v.get("num", "") + " " + v.get("unit", "") or v.get("quote", "")
            captions.append(f"### {i:02d} · {v['slug']}\n{head}\n\nBook a free build session → {LINKS['call']}\nSee the systems → {LINKS['site']}\nRead the code → {LINKS['github']}\n")
            # animated hero cards
            if i <= a.animate:
                ah = card_html(v, i, logo_uri, qr, fonts_css, i in dark_idx, anim=True)
                af = out / "html" / f"{i:02d}_{v['slug']}_anim.html"; af.write_text(ah)
                pg.goto(af.as_uri()); pg.wait_for_timeout(150)
                frames = []
                for t in range(0, 3000, 100):  # 3 s @ 10 fps
                    pg.evaluate(f"document.getAnimations().forEach(x=>{{x.pause();x.currentTime={t}}})")
                    frames.append(pg.screenshot(clip={"x": 0, "y": 0, "width": W, "height": H}))
                from PIL import Image
                ims = [Image.open(io.BytesIO(b)).convert("RGB").resize((540, 675)).quantize(colors=128) for b in frames]
                ims[0].save(out / "animated" / f"{i:02d}_{v['slug']}.gif", save_all=True, append_images=ims[1:] + [ims[-1]] * 15, duration=100, loop=0, optimize=True)
                fd = out / "animated" / f"_frames_{i:02d}"; fd.mkdir(exist_ok=True)
                for n, b in enumerate(frames + [frames[-1]] * 15):
                    (fd / f"{n:03d}.png").write_bytes(b)
                ff = shutil.which("ffmpeg") or next(iter(Path("/opt/pw-browsers").glob("ffmpeg*/ffmpeg-linux")), None)
                if ff:
                    subprocess.run([str(ff), "-y", "-loglevel", "error", "-framerate", "10", "-i", str(fd / "%03d.png"), "-pix_fmt", "yuv420p", "-vf", "scale=1080:1350", str(out / "animated" / f"{i:02d}_{v['slug']}.mp4")])
                shutil.rmtree(fd)
        # clickable PDF carousel: rendered PNG per page + invisible link overlays (LinkedIn document posts keep <a href>)
        def page(i, v):
            img = (out / "png" / f"{i:02d}_{v['slug']}.png").as_uri()
            ov = "".join(f'<a href="{u}" style="position:absolute;left:{x}px;top:{y}px;width:{w}px;height:{h}px"></a>' for u, x, y, w, h in
                         [(LINKS["call"], 70, 1172, 680, 40), (LINKS["site"], 70, 1212, 680, 40), (LINKS["github"], 70, 1252, 680, 40), (LINKS["call"], 820, 1150, 200, 160)])
            return f'<div style="position:relative;width:{W}px;height:{H}px;page-break-after:always"><img src="{img}" style="width:{W}px;height:{H}px;display:block">{ov}</div>'
        (out / "html" / "_carousel.html").write_text("<!doctype html><html><head><meta charset='utf-8'><style>body{margin:0}</style></head><body>" + "".join(page(i, v) for i, v in enumerate(VARIANTS, 1)) + "</body></html>")
        pg.goto((out / "html" / "_carousel.html").as_uri()); pg.wait_for_timeout(300)
        pg.pdf(path=str(out / "carousel.pdf"), width=f"{W}px", height=f"{H}px", print_background=True, margin={"top": "0", "bottom": "0", "left": "0", "right": "0"})
        br.close()

    (out / "captions.md").write_text("# ProdCraft LinkedIn banners — captions + links\n\nImages on LinkedIn are not clickable. Put the links in the post text or first comment; the QR on every banner opens the booking page; the PDF carousel keeps the links clickable.\n\n" + "\n".join(captions))
    grid = "".join(f'<figure><img src="png/{i:02d}_{v["slug"]}.png"><figcaption>{i:02d} · {v["slug"]}</figcaption></figure>' for i, v in enumerate(VARIANTS, 1))
    (out / "review.html").write_text(f"<!doctype html><meta charset='utf-8'><title>ProdCraft banners</title><style>body{{font-family:Geist,system-ui;background:#f7f3ec;margin:0;padding:32px}}main{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:28px}}img{{width:100%;border-radius:10px;box-shadow:0 12px 40px rgba(0,0,0,.14)}}figure{{margin:0}}figcaption{{font-family:monospace;margin-top:8px;color:#3d4148}}</style><h1>ProdCraft · LinkedIn banners · {dt.date.today()}</h1><p><a href='carousel.pdf'>carousel.pdf (clickable links)</a> · <a href='captions.md'>captions.md</a></p><main>{grid}</main>")
    json.dump({"links": LINKS, "variants": VARIANTS}, open(out / "manifest.json", "w"), indent=1, ensure_ascii=False)
    print("wrote", out)


if __name__ == "__main__":
    main()
