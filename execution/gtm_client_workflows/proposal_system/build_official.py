"""
build_official.py
description: Render the official (Siva-format) proposal page from the mirrored reference template.html, with euro pricing, embedded logos, Stripe pay button, DocuSign button and full event tracking.
inputs: proposals/<slug>.official.json (Siva config schema + logos + docusign_url); deliverables/_samples/proposal-system/template.html.
outputs: out/<slug>/index.html (self-contained; logos inlined as data URIs). Fails if any {{PLACEHOLDER}} remains.
"""
import base64, json, mimetypes, re, sys
from pathlib import Path
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
TPL = ROOT / "deliverables/_samples/proposal-system/template.html"

def data_uri(p):
    p = ROOT / p
    mt = mimetypes.guess_type(str(p))[0] or "image/png"
    return f"data:{mt};base64,{base64.b64encode(p.read_bytes()).decode()}"

def main(slug):
    cfg = json.loads((HERE / "proposals" / f"{slug}.official.json").read_text())
    t = TPL.read_text()
    c, s, pj, sit, sc, inv, ag = (cfg[k] for k in ("client","sender","project","situation","scope","investment","agreement"))
    m = {
     "CLIENT_NAME": c["name"], "CLIENT_TITLE": c["title"], "CLIENT_COMPANY": c["company"], "CLIENT_COMPANY_SLUG": slug,
     "SENDER_NAME": s["name"], "SENDER_NAME_FIRST": s["name"].split()[0], "SENDER_TITLE": s["title"], "SENDER_COMPANY": s["company"],
     "SENDER_EMAIL": s["email"], "LOGO_URL": data_uri(cfg["logos"]["sender"]) if cfg["logos"].get("sender") else "",
     "SENDER_COMPANY_WORDMARK": 'Prod<span class="accent">Craft</span>',
     "PROJECT_TITLE": pj["title"], "COVER_BRAND_LABEL": pj["cover_brand_label"], "COVER_SUBTITLE": pj["cover_subtitle"], "CREATED_DATE": pj["created_date"],
     "SITUATION_HEADLINE": sit["headline"], "SITUATION_LEDE": sit["lede"], "SITUATION_CALLOUT_TITLE": sit["callout_title"],
     "SITUATION_CALLOUT_BODY": sit["callout_body"], "SITUATION_CLOSE": sit["close"],
     "SCOPE_M1_TITLE": sc["m1_title"], "SCOPE_M1_BODY": sc["m1_body"], "SCOPE_M2_TITLE": sc["m2_title"], "SCOPE_M2_BODY": sc["m2_body"],
     "SCOPE_M3_TITLE": sc["m3_title"], "SCOPE_M3_BODY": sc["m3_body"], "SCOPE_THROUGHOUT": sc["throughout"], "OUT_OF_SCOPE": sc["out_of_scope"],
     "M1_DELIVERABLE": inv["m1_deliverable"], "M1_AMOUNT": inv["m1_amount"], "M2_DELIVERABLE": inv["m2_deliverable"], "M2_AMOUNT": inv["m2_amount"],
     "M3_DELIVERABLE": inv["m3_deliverable"], "M3_AMOUNT": inv["m3_amount"], "TOTAL_AMOUNT": inv["total_amount"],
     "ROI_TITLE": inv["roi_title"], "ROI_BODY": inv["roi_body"], "AGREEMENT_BODY": ag["body"], "SENDER_SIGNATURE_TEXT": ag.get("sender_signature_text", s["name"]),
     "STRIPE_PAYMENT_URL": cfg["payment"]["stripe_url"],
    }
    for i, pr in enumerate(cfg["problems"][:4], 1):
        m[f"PROBLEM_0{i}_TITLE"], m[f"PROBLEM_0{i}_BODY"] = pr["title"], pr["body"]
    for i, b in enumerate(cfg["benefits"][:4], 1):
        m[f"BENEFIT_0{i}_TITLE"], m[f"BENEFIT_0{i}_BODY"] = b["title"], b["body"]

    # --- adaptations to the reference template (kept minimal, design untouched) ---
    t = t.replace('<script defer src="/_vercel/insights/script.js"></script>', "")
    t = t.replace("${{M1_AMOUNT}}", "€{{M1_AMOUNT}}").replace("${{M2_AMOUNT}}", "€{{M2_AMOUNT}}").replace("${{M3_AMOUNT}}", "€{{M3_AMOUNT}}").replace("${{TOTAL_AMOUNT}}", "€{{TOTAL_AMOUNT}}")
    t = t.replace("<td>Month 1</td>", "<td>{{M1_LABEL}}</td>").replace("<td>Month 2</td>", "<td>{{M2_LABEL}}</td>").replace("<td>Month 3</td>", "<td>{{M3_LABEL}}</td>")
    m.update(M1_LABEL=inv["m1_label"], M2_LABEL=inv["m2_label"], M3_LABEL=inv["m3_label"])
    t = t.replace("<h3>Three monthly payments. No surprises.</h3>", f"<h3>{inv['heading']}</h3>")
    t = t.replace("<h3>What we're building across three months.</h3>", f"<h3>{sc['heading']}</h3>")
    t = t.replace("<h3>Four problems bleeding revenue today.</h3>", f"<h3>{cfg['problems_heading']}</h3>")
    t = t.replace("<h3>Four systems that earn back their cost in month one.</h3>", f"<h3>{cfg['benefits_heading']}</h3>")
    t = t.replace("Pay First Installment (${{M1_AMOUNT}})", "Pay deposit (€{{M1_AMOUNT}})").replace("Pay First Installment (€{{M1_AMOUNT}})", "Pay deposit (€{{M1_AMOUNT}})")
    # client logos on the cover (right side) + brand row on inner pages
    client_logos = "".join(f'<img src="{data_uri(p)}" alt="" style="height:44px;width:auto;border-radius:8px;background:#fff;padding:6px 10px">' for p in cfg["logos"]["client"])
    t = t.replace('<div class="brand">{{COVER_BRAND_LABEL}}</div>\n  </div>',
                  '<div class="brand">{{COVER_BRAND_LABEL}}</div>\n  </div>\n  <div style="position:absolute;top:56px;right:72px;display:flex;gap:12px;align-items:center">' + client_logos + "</div>")
    # DocuSign button + download tracking + extra events
    t = t.replace('<button class="btn btn-primary" id="accept-btn"',
                  f'<a class="btn btn-secondary" id="docusign-btn" href="{cfg["docusign_url"]}" target="_blank" rel="noopener" onclick="track(\'docusign_clicked\')">✍️ Sign with DocuSign</a>\n      <button class="btn btn-primary" id="accept-btn"')
    t = t.replace("async function downloadSigned() {", "async function downloadSigned() {\n  track('download_clicked');")
    t = t.replace("track('signed', `by ${name}`);", "track('signed', `by ${name}`); track('accept_clicked', `by ${name}`);")
    # scroll-depth and time-on-page events
    t = t.replace("// Signature canvas", """// Engagement: reached the Investment and Agreement pages, and 2-minute dwell
(function(){ const seen={}; const pages=document.querySelectorAll('.page'); const names={5:'investment_viewed',6:'agreement_viewed'};
  const io=new IntersectionObserver(es=>es.forEach(e=>{ if(!e.isIntersecting) return; const i=[...pages].indexOf(e.target); if(names[i]&&!seen[i]){seen[i]=1;track(names[i]);} }),{threshold:0.5});
  pages.forEach(p=>io.observe(p)); setTimeout(()=>track('read_2_minutes'),120000); })();
// Signature canvas""")
    out, missing = re.subn(r"\{\{([A-Z0-9_]+)\}\}", lambda mm: str(m.get(mm.group(1), mm.group(0))), t)
    left = re.findall(r"\{\{[A-Z0-9_]+\}\}", out)
    if left: sys.exit(f"unfilled: {sorted(set(left))}")
    od = HERE / "out" / slug; od.mkdir(parents=True, exist_ok=True)
    (od / "index.html").write_text(out)
    print("wrote", od / "index.html", len(out), "bytes")

if __name__ == "__main__":
    main(sys.argv[1])
