import re, html
from pathlib import Path
S = Path(__file__).resolve().parent.parent
md = (S/"captions.md").read_text(encoding="utf-8")
cal = re.search(r"\| Day \|.*?\n(?:\|.*\n)+", md).group(0).strip().split("\n")
rows = [[c.strip() for c in r.strip("|").split("|")] for r in cal[2:]]
posts = []
for m in re.finditer(r"### (IG|LI) (\d\d) · `([^`]+)`\n\*\*Headline on artwork:\*\* (.*?)\n\*\*Caption:\*\*\n(.*?)\n\*\*Post:\*\* (.*?) · \*\*KPI:\*\* (.*?)\n\*\*Accessibility alt text:\*\* (.*?)\n", md, re.S):
    plat, n, slug, head, cap, when, kpi, alt = m.groups()
    posts.append(dict(plat=plat, n=int(n), slug=slug, head=head, cap=cap.strip(), when=when, kpi=kpi, alt=alt))
pngs = sorted((S/"png").glob("*.png"))
def png_for(p):
    pre = f"{p['n'] if p['plat']=='IG' else p['n']+10:02d}_"
    return next(x.name for x in pngs if x.name.startswith(pre))
def card(p):
    cap = html.escape(p["cap"]).replace("\n", "<br>")
    return f"""<article class="card" id="{p['plat'].lower()}-{p['n']:02d}">
<figure><img src="png/{png_for(p)}" alt="{html.escape(p['alt'])}" loading="lazy" width="1080" height="1350"></figure>
<div class="txt"><p class="k">{p['plat'] if p['plat']=='LI' else 'Instagram'}{' · LinkedIn' if False else ''} · {p['n']:02d} / 10 · {html.escape(p['slug'])}</p>
<h3>{html.escape(p['head'])}</h3><p class="cap">{cap}</p>
<p class="meta"><b>Post</b> {html.escape(p['when'])}<br><b>KPI intent</b> {html.escape(p['kpi'])}</p></div></article>"""
ig = "".join(card(p) for p in posts if p["plat"]=="IG"); li = "".join(card(p) for p in posts if p["plat"]=="LI")
caltab = "<table><thead><tr>" + "".join(f"<th>{h}</th>" for h in ["Day","Week","Platform","Post","Slot"]) + "</tr></thead><tbody>" + "".join("<tr>"+"".join(f"<td>{html.escape(c)}</td>" for c in r)+"</tr>" for r in rows) + "</tbody></table>"
page = f"""<!doctype html><html lang="en-GB"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow">
<title>MISB · 20 posts · a social media concept by Debanjan Mazumdar</title>
<style>
@font-face{{font-family:CG;src:url(fonts/cg-500.woff2) format('woff2');font-weight:500}}
@font-face{{font-family:CG;src:url(fonts/cg-400-italic.woff2) format('woff2');font-weight:400;font-style:italic}}
@font-face{{font-family:Inter;src:url(fonts/inter-400.woff2) format('woff2');font-weight:400}}
@font-face{{font-family:Inter;src:url(fonts/inter-500.woff2) format('woff2');font-weight:500}}
*{{box-sizing:border-box;margin:0;padding:0}}
body{{background:#F6F2EA;color:#141414;font:400 16px/1.6 Inter,system-ui,sans-serif;-webkit-font-smoothing:antialiased}}
.wrap{{max-width:1180px;margin:0 auto;padding:48px 24px 96px}}
h1,h2,h3{{font-family:CG,Georgia,serif;font-weight:500;letter-spacing:-.005em}}
h1{{font-size:clamp(40px,6vw,72px);line-height:1;max-width:900px}}
.k{{font:500 12px/1 Inter;letter-spacing:.24em;text-transform:uppercase;display:flex;gap:10px;align-items:center}}
.k:before{{content:'';width:8px;height:8px;border-radius:50%;background:#E64626}}
.intent{{margin-top:22px;max-width:720px;color:#5B5952;font-size:18px}}
nav{{display:flex;gap:28px;margin:40px 0 0;border-top:1px solid #141414;border-bottom:1px solid #141414;padding:18px 0}}
nav a{{color:inherit;text-decoration:none;font:500 13px/1 Inter;letter-spacing:.22em;text-transform:uppercase}}
nav a:hover{{color:#E64626}}
section{{margin-top:72px}} section>h2{{font-size:clamp(32px,4vw,52px);margin:14px 0 36px}}
.grid{{display:grid;gap:56px 40px;grid-template-columns:1fr}}
.card{{display:grid;grid-template-columns:minmax(0,340px) 1fr;gap:28px;align-items:start}}
figure img{{width:100%;height:auto;display:block;border-radius:18px;box-shadow:0 20px 60px rgba(20,20,20,.14);border:1px solid rgba(20,20,20,.08)}}
.card h3{{font-size:30px;line-height:1.15;margin:12px 0 16px}}
.cap{{white-space:normal;max-width:560px}}
.meta{{margin-top:18px;font-size:14px;color:#5B5952}} .meta b{{color:#141414;font-weight:500;letter-spacing:.1em;text-transform:uppercase;font-size:11px;margin-right:8px}}
table{{width:100%;border-collapse:collapse;font-size:15px}} th,td{{text-align:left;padding:12px 10px;border-bottom:1px solid rgba(20,20,20,.18)}} th{{font:500 11px/1 Inter;letter-spacing:.2em;text-transform:uppercase}}
footer{{margin-top:96px;border-top:1px solid #141414;padding-top:24px;color:#5B5952;font-size:14px}}
footer a{{color:inherit}}
@media(max-width:720px){{.card{{grid-template-columns:1fr}} figure{{max-width:360px}} .wrap{{padding:32px 18px 64px}} nav{{gap:18px;flex-wrap:wrap}}}}
</style></head><body><div class="wrap">
<p class="k">MISB · social concept</p>
<h1 style="margin-top:22px">MISB · 20 posts · a social media concept by Debanjan Mazumdar</h1>
<p class="intent">One magazine, two feeds: ten Instagram posts for the international applicant, ten LinkedIn posts for employers, parents and apprenticeship tutors. Every fact, photo and quote is taken from misb.fr as published.</p>
<nav><a href="#instagram">Instagram · 10</a><a href="#linkedin">LinkedIn · 10</a><a href="#calendar">Calendar</a></nav>
<section id="instagram"><p class="k">Instagram · 1080 × 1350</p><h2>For the applicant.</h2><div class="grid">{ig}</div></section>
<section id="linkedin"><p class="k">LinkedIn · 1080 × 1350</p><h2>For the employer, the parent, the tutor.</h2><div class="grid">{li}</div></section>
<section id="calendar"><p class="k">Two-week calendar · Paris time</p><h2>When each post goes out.</h2>{caltab}<p class="meta" style="margin-top:16px">Student-life posts land on Thursdays, the day of MISB's weekly Industry and Cultural Visit Programme. LinkedIn goes out before 09:30 on weekdays.</p></section>
<footer>Concept by Debanjan, Founder, ProdCraft, <a href="mailto:debanjan@prodcraft.fyi">debanjan@prodcraft.fyi</a> · all facts and photos from misb.fr · not affiliated with MISB</footer>
</div></body></html>"""
page = page.replace("<p class=\"k\">LI ·", "<p class=\"k\">LinkedIn ·")
(S/"index.html").write_text(page, encoding="utf-8"); print(len(posts), "posts;", len(page)//1024, "KB")
