"""
description: Render the ProdCraft 50-week LinkedIn feed cards (1080x1350 PNG, 8 layout families, claim-gated copy) plus captions, proof checklist, contact sheet and manifest. Never publishes.
inputs: --messages execution/content/prodcraft_50_week_messages.json; --claims execution/content/prodcraft_claim_registry.json; --out <dir> (default deliverables/linkedin_weekly_cards/prodcraft/<date>); --fonts <dir with fonts_local.css, optional>; --weeks 1,2,3 (optional subset); env PW_CHROME (optional chromium path)
outputs: <out>/png/NN_week_slug.png, <out>/html/NN_week_slug.html, <out>/messages.json, <out>/captions.md, <out>/proof_checklist.md, <out>/contact_sheet.png, <out>/manifest.json
"""
from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, H = 1080, 1350
SAFE = 96  # mobile-safe margin; validator checks every text box stays inside it
BOOK_URL = "https://cal.com/debanjan-mazumdar-ben5rd/30min"
DEMO_URL = "https://cv-optimizer.pages.dev"
CTA_ON_IMAGE = {"Book session", "Soft invitation", "Demo link"}
MAX_HAND = 8

FAMILY_OF = {
    "minimal_editorial": "minimal_editorial", "three_questions": "minimal_editorial",
    "conversation_snippet": "minimal_editorial",
    "annotated_workflow": "annotated_workflow", "workflow_diagram": "annotated_workflow",
    "large_type_plus_flow": "annotated_workflow", "swimlane": "annotated_workflow",
    "routing_map": "annotated_workflow", "crm_routing_map": "annotated_workflow",
    "sequence_diagram": "annotated_workflow", "call_flow": "annotated_workflow",
    "incident_flow": "annotated_workflow", "funnel_diagram": "annotated_workflow",
    "system_state_diagram": "annotated_workflow", "decision_tree": "annotated_workflow",
    "project_map": "annotated_workflow", "source_trace": "annotated_workflow",
    "failure_case_checklist": "failure_checklist", "checklist_card": "failure_checklist",
    "ownership_checklist": "failure_checklist", "release_checklist": "failure_checklist",
    "document_checklist": "failure_checklist", "handover_checklist": "failure_checklist",
    "call_test_matrix": "failure_checklist", "scope_card": "failure_checklist",
    "annotated_document": "failure_checklist",
    "before_after": "before_after", "two_column_comparison": "before_after",
    "good_bad_example": "before_after", "pilot_vs_production": "before_after",
    "decision_matrix": "before_after",
    "code_to_outcome": "code_to_outcome", "version_diff": "code_to_outcome",
    "test_case_card": "code_to_outcome", "engineering_note": "code_to_outcome",
    "experiment_card": "code_to_outcome", "control_panel": "code_to_outcome",
    "founder_note": "founder_note",
    "evidence_receipt": "case_receipt", "case_receipt": "case_receipt", "cost_breakdown": "case_receipt",
    "simple_offer_card": "offer_card", "brief_template": "offer_card", "annotated_screenshot": "offer_card",
}
# Reassignment order when a family would repeat a third time in a row.
ALTERNATES = ["minimal_editorial", "before_after", "annotated_workflow", "failure_checklist", "code_to_outcome"]
PAIR_LABELS = {"pilot_vs_production": ("Pilot", "Production"), "good_bad_example": ("Weak", "Stronger"),
               "before_after": ("Before", "After")}
DARK_FAMILIES = {"code_to_outcome"}

CSS = r"""
:root{--bone:#f7f3ec;--bone2:#efe9df;--ink:#16181c;--ink7:#5a5e66;--brass:#c8a35c;--brass5:#9c7a32;--rule:rgba(22,24,28,.16)}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font-family:Geist,Inter,system-ui,sans-serif}
.card{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--bone);color:var(--ink);padding:104px 104px 104px;display:flex;flex-direction:column}
.card.dark{background:var(--ink);color:var(--bone);--rule:rgba(247,243,236,.18);--ink7:#b9b4aa}
.serif{font-family:Newsreader,'Bitstream Charter',FreeSerif,Georgia,serif}
.mono{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace}
.hand{font-family:Caveat,'Bitstream Charter',FreeSerif,serif;font-style:italic}
.top{display:flex;justify-content:space-between;align-items:baseline}
.wm{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-weight:700;font-size:28px;letter-spacing:-.01em}
.wm i{color:var(--brass5);font-style:normal}.dark .wm i{color:var(--brass)}
.lbl{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:17px;letter-spacing:.1em;text-transform:uppercase;color:var(--ink7)}
.main{flex:1;display:flex;flex-direction:column;min-height:0}
h1{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-weight:500;line-height:1.06;letter-spacing:-.02em;margin:0;text-wrap:balance}
.sup{font-size:34px;line-height:1.35;color:var(--ink7);margin:0;text-wrap:pretty}
.dark .sup{color:#d9d4ca}
.rule{width:96px;height:4px;background:var(--brass);border:0;margin:40px 0}
.vis{flex:1;min-height:0;display:flex;flex-direction:column;justify-content:center;overflow:hidden}
.cta{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:21px;color:var(--brass5);border-top:1px solid var(--rule);padding-top:22px;margin-top:24px}
.dark .cta{color:var(--brass)}
/* minimal */
.f-minimal_editorial .main{justify-content:center}
.f-minimal_editorial h1{font-size:96px}
/* flow */
.flow{display:flex;flex-direction:column;gap:0;margin-top:8px}
.node{border:2px solid var(--ink);background:#fff;border-radius:10px;padding:16px 24px;font-size:27px;line-height:1.25;max-width:760px}
.node:nth-child(4n+3){margin-left:120px}.node .n{font-family:'JetBrains Mono',monospace;font-size:17px;color:var(--brass5);display:block;margin-bottom:4px}
.arrow{height:34px;width:2px;background:var(--ink);margin-left:48px;position:relative}
.arrow:after{content:"";position:absolute;bottom:-2px;left:-7px;border:8px solid transparent;border-top:10px solid var(--ink)}
/* checklist */
.check{list-style:none;padding:0;margin:0;border-top:1px solid var(--rule)}
.check li{display:flex;gap:22px;align-items:flex-start;padding:20px 0;border-bottom:1px solid var(--rule);font-size:29px;line-height:1.3}
.box{flex:0 0 34px;height:34px;border:2.5px solid var(--ink);border-radius:5px;margin-top:2px;position:relative}
.box.on:after{content:"";position:absolute;left:9px;top:2px;width:9px;height:18px;border:solid var(--brass5);border-width:0 4px 4px 0;transform:rotate(40deg)}
/* before/after */
.ba{display:grid;grid-template-columns:1fr 1fr;gap:28px}
.col{border:2px solid var(--ink);border-radius:12px;padding:26px;background:#fff;min-height:0}
.col.b{background:var(--ink);color:var(--bone)}
.col .k{font-family:'JetBrains Mono',monospace;font-size:18px;letter-spacing:.1em;text-transform:uppercase;color:var(--brass5);margin-bottom:12px}
.col.b .k{color:var(--brass)}
.col p{font-size:28px;line-height:1.3;margin:0}
/* code */
.code{background:#0e1013;border:1px solid rgba(247,243,236,.2);border-radius:12px;padding:30px 34px;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:23px;line-height:1.6;color:#e8e3d9;white-space:pre-wrap;overflow:hidden}
.code .c{color:#8a8f98}.code .k{color:var(--brass)}
.illus{font-family:'JetBrains Mono',monospace;font-size:16px;letter-spacing:.1em;text-transform:uppercase;color:#8a8f98;margin-top:12px}
/* founder */
.f-founder_note{background:var(--bone2)}
.f-founder_note .main{justify-content:center}
.f-founder_note h1{font-style:italic;font-weight:400}
.sig{font-size:44px;color:var(--brass5);margin-top:36px;transform:rotate(-2deg);transform-origin:left}
/* receipt */
.rcpt{background:#fff;border:1px dashed var(--ink);padding:32px 36px;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:22px;line-height:1.5;max-width:780px}
.rcpt .row{display:flex;justify-content:space-between;gap:24px;border-bottom:1px dotted var(--rule);padding:8px 0}
.rcpt .row span:last-child{text-align:right}
.rcpt .tot{font-size:26px;font-weight:700;border:0;padding-top:16px}
/* offer */
.f-offer_card .main{justify-content:center}
.offer{border:2.5px solid var(--ink);border-radius:16px;padding:44px;background:#fff}
.offer .k{font-family:'JetBrains Mono',monospace;font-size:19px;letter-spacing:.12em;text-transform:uppercase;color:var(--brass5);margin-bottom:20px}
"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slugify(s: str, n: int = 6) -> str:
    words = re.findall(r"[a-z0-9]+", s.lower().replace("’", "").replace("'", ""))
    return "_".join(words[:n]) or "card"


def fragments(text: str) -> list[str]:
    """Split a supporting line into 2-5 short steps, verbatim words only (never invent)."""
    t = text.rstrip(".")
    parts = re.split(r"\s*[:;—]\s*|,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+then\s+", t)
    parts = [p.strip(" .") for p in parts if p and len(p.strip(" .")) > 1]
    return parts[:5]


def headline_px(head: str, family: str) -> int:
    n = len(head)
    base = 92 if n <= 40 else 80 if n <= 58 else 70 if n <= 75 else 62
    if family == "minimal_editorial":
        base += 6
    if family in {"annotated_workflow", "failure_checklist", "code_to_outcome", "before_after"}:
        base -= 6
    return base


def claim_ok(week: int, claims: list[dict]) -> tuple[bool, list[dict]]:
    """True when every claim registered for this week that carries match patterns is approved."""
    mine = [c for c in claims if week in c.get("weeks", []) and c.get("match")]
    return all(c["status"] == "approved" for c in mine), mine


def choose_families(weeks: list[dict]) -> tuple[list[str], list[str]]:
    fams, warns = [], []
    for w in weeks:
        f = FAMILY_OF.get(w["visual_direction"], "minimal_editorial")
        if len(fams) >= 2 and fams[-1] == fams[-2] == f:
            nxt = FAMILY_OF.get(weeks[len(fams) + 1]["visual_direction"]) if len(fams) + 1 < len(weeks) else None
            alt = next(a for a in ALTERNATES if a != f and a != nxt)
            warns.append(f"week {w['week']:02d}: {f} would repeat 3x; reassigned to {alt}")
            f = alt
        fams.append(f)
    return fams, warns


def visual(w: dict, fam: str, sup: str, numeric_ok: bool) -> str:
    steps = fragments(sup)
    if fam == "annotated_workflow":
        if len(steps) < 3:
            steps = ["Input", *steps, "Owner + next step"][:5]  # generic labelled flow, no new facts
        out = []
        for i, s in enumerate(steps):
            if i:
                out.append('<div class="arrow"></div>')
            out.append(f'<div class="node t"><span class="n">{i + 1:02d}</span>{esc(s[:1].upper() + s[1:])}</div>')
        return f'<div class="flow">{"".join(out)}</div>'
    if fam == "failure_checklist":
        items = steps if len(steps) >= 2 else [sup]
        lis = "".join(f'<li class="t"><span class="box{" on" if i == 0 else ""}"></span><span>{esc(s[:1].upper() + s[1:])}</span></li>'
                      for i, s in enumerate(items))
        return f'<ul class="check">{lis}</ul>'
    if fam == "before_after":
        heads = [s.strip() for s in re.split(r"(?<=\.)\s+", w["headline"]) if s.strip()]
        left_k, right_k = PAIR_LABELS.get(w["visual_direction"], ("Usually", "Instead"))
        if len(heads) >= 2:
            a, b = heads[0], " ".join(heads[1:])
        else:
            half = max(1, len(steps) // 2)
            a, b = ", ".join(steps[:half]) or sup, ", ".join(steps[half:]) or sup
        return (f'<div class="ba"><div class="col t"><div class="k">{left_k}</div><p>{esc(a)}</p></div>'
                f'<div class="col b t"><div class="k">{right_k}</div><p>{esc(b)}</p></div></div>')
    if fam == "code_to_outcome":
        lines = ['<span class="c"># illustrative sketch, not production code</span>']
        named = [slugify(s, 4) for s in steps] if len(steps) >= 2 else ["read_input", "check_rule", "write_result"]
        if len(steps) < 2:
            lines.append(f'<span class="c"># {esc(sup)}</span>')
        for name in named:
            lines.append(f'<span class="k">step</span>("{esc(name)}")')
        lines.append('<span class="c"># outcome: explained in the post</span>' if w["visual_direction"] != "test_case_card"
                     else '<span class="c"># expected: pass on the edge case, not just the demo</span>')
        return f'<div class="code t">{chr(10).join(lines)}</div><div class="illus">Illustrative pseudo-code</div>'
    if fam == "case_receipt":
        rows = [("case", esc(w["theme"].lower())), ("evidence", "verified" if numeric_ok else "non-numeric")]
        rows += [(f"note {i + 1:02d}", esc(s)) for i, s in enumerate(steps[:3])]
        body = "".join(f'<div class="row"><span>{k}</span><span>{v}</span></div>' for k, v in rows)
        return f'<div class="rcpt t">{body}<div class="row tot"><span>takeaway</span><span>see post</span></div></div>'
    return ""


def cta_line(w: dict) -> str:
    c = w["cta"]
    if c not in CTA_ON_IMAGE:
        return ""
    txt = {"Book session": "30-minute session · link in the post",
           "Soft invitation": "More in the post",
           "Demo link": "Live demo · cv-optimizer.pages.dev"}[c]
    return f'<div class="cta t">{esc(txt)}</div>'


def card_html(w: dict, fam: str, sup: str, numeric_ok: bool, fonts_css: str, hand: bool) -> str:
    hp = headline_px(w["headline"], fam)
    head = f'<h1 class="t" style="font-size:{hp}px">{esc(w["headline"]).replace("-", "\u2011")}</h1>'
    supp = f'<p class="sup t">{esc(sup)}</p>'
    dark = " dark" if fam in DARK_FAMILIES else ""
    vis = visual(w, fam, sup, numeric_ok)
    if fam == "founder_note":
        inner = head + '<div class="rule"></div>' + supp + ('<div class="sig hand t">— Debanjan</div>' if hand else "")
    elif fam == "offer_card":
        k = "Demo" if w["cta"] == "Demo link" else "Brief" if w["visual_direction"] == "brief_template" else "Session"
        inner = f'<div class="offer"><div class="k">{k}</div>{head}<div class="rule"></div>{supp}</div>'
    elif fam == "minimal_editorial":
        inner = head + '<div class="rule"></div>' + supp
    else:
        if fam in {"failure_checklist", "annotated_workflow", "code_to_outcome"} and fragments(sup) and len(fragments(sup)) >= 3:
            supp = ""  # the diagram already carries the supporting line verbatim; avoid saying it twice
        inner = head + (f'<div style="height:28px"></div>{supp}' if supp else "") + f'<div class="vis">{vis}</div>'
    label = f'ProdCraft · wk {w["week"]:02d}'
    return f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css}{CSS}</style></head><body>
<div class="card f-{fam}{dark}"><div class="top"><span class="wm t">Prod<i>Craft</i></span><span class="lbl t">{esc(label)}</span></div>
<div style="height:72px"></div><div class="main">{inner}</div>{cta_line(w)}</div></body></html>"""


def chromium_path() -> str | None:
    if os.environ.get("PW_CHROME"):
        return os.environ["PW_CHROME"]
    return next((str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")), None)


def load_fonts(fonts_dir: Path) -> str:
    css = fonts_dir / "fonts_local.css"
    if css.exists():
        return css.read_text(encoding="utf-8").replace("url(", f"url(file://{fonts_dir}/")
    print(f"fonts: {css} missing, using system fallbacks (Charter/FreeSerif, Inter, JetBrains Mono)", file=sys.stderr)
    return ""


def proof_checklist(weeks: list[dict], claims: list[dict]) -> str:
    req = ["source", "date_range", "denominator", "definition", "attribution", "disclosure_permission", "approved_wording"]
    out = ["# Proof checklist\n", "Rule (pack section 4): a numeric card ships only when every field below is filled and status is approved; otherwise the non-numeric fallback renders.\n"]
    for c in claims:
        missing = [f for f in req if not c.get(f) or "MISSING" in str(c.get(f))]
        wk = ", ".join(f"W{x:02d}" for x in c["weeks"]) or "all"
        flag = "BLOCKS numeric line" if c["status"] in {"pending_verification", "pending_permission", "blocked"} and c.get("match") else \
            "never publish" if c["status"] == "retired" else "check before publish" if c["status"] != "approved" else "ok"
        out.append(f"- **{c['id']}** ({wk}) — status `{c['status']}` — {flag}. Missing: {', '.join(missing) or 'none'}. {c.get('notes', '')}")
    out.append("\n## Week guardrails\n")
    out += [f"- W{w['week']:02d}: {w['publish_guardrail']}" for w in weeks if w["publish_guardrail"] != "none"]
    return "\n".join(out) + "\n"


def captions(rows: list[dict]) -> str:
    out = ["# Captions (angles, not finished posts — write the real example yourself)\n"]
    for r in rows:
        link = BOOK_URL if r["cta"] == "Book session" else DEMO_URL if r["cta"] == "Demo link" else ""
        out.append(f"## Week {r['week']:02d} — {r['theme']}\n\n**Angle:** {r['companion_post']}\n\n**CTA:** {r['cta']}"
                   + (f"\n\n**Link (post text):** {link}" if link else "") + f"\n\n**Guardrail:** {r['publish_guardrail']}\n")
    return "\n".join(out)


def contact_sheet(pngs: list[Path], dest: Path) -> None:
    from PIL import Image
    tw, th, cols = 216, 270, 10
    rows = (len(pngs) + cols - 1) // cols
    sheet = Image.new("RGB", (cols * tw, rows * th), "#ddd")
    for i, p in enumerate(pngs):
        with Image.open(p) as im:
            sheet.paste(im.convert("RGB").resize((tw, th)), ((i % cols) * tw, (i // cols) * th))
    sheet.save(dest)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--messages", default=str(ROOT / "execution/content/prodcraft_50_week_messages.json"))
    ap.add_argument("--claims", default=str(ROOT / "execution/content/prodcraft_claim_registry.json"))
    ap.add_argument("--out", default=str(ROOT / "deliverables/linkedin_weekly_cards/prodcraft" / dt.date.today().isoformat()))
    ap.add_argument("--fonts", default=str(ROOT / ".tmp/banners/fonts"))
    ap.add_argument("--weeks", default="", help="comma list of week numbers to render (default all)")
    a = ap.parse_args()

    weeks = json.loads(Path(a.messages).read_text(encoding="utf-8"))["weeks"]
    claims = json.loads(Path(a.claims).read_text(encoding="utf-8"))["claims"]
    fams, warns = choose_families(weeks)
    for wn in warns:
        print("WARN", wn, file=sys.stderr)
    only = {int(x) for x in a.weeks.split(",") if x.strip()}
    out = Path(a.out).resolve()
    (out / "png").mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(exist_ok=True)
    fonts_css = load_fonts(Path(a.fonts))

    from playwright.sync_api import sync_playwright
    rows, pngs, hand_used = [], [], 0
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium_path())
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for w, fam in zip(weeks, fams):
            ok, mine = claim_ok(w["week"], claims)
            sup = w["supporting_line"] if ok or "fallback_supporting_line" not in w else w["fallback_supporting_line"]
            head_ok = ok or not any(any(m in w["headline"] for m in c["match"]) for c in mine)
            if not head_ok:
                print(f"WARN week {w['week']:02d}: headline carries an unapproved number; card not rendered", file=sys.stderr)
                continue
            hand = fam == "founder_note" and hand_used < MAX_HAND
            hand_used += hand
            name = f"{w['week']:02d}_week_{slugify(w['headline'])}"
            row = {**w, "layout": fam, "rendered_supporting_line": sup, "used_fallback": sup != w["supporting_line"],
                   "handwritten": hand, "file": f"png/{name}.png", "html": f"html/{name}.html"}
            rows.append(row)
            if only and w["week"] not in only:
                continue
            f = out / "html" / f"{name}.html"
            f.write_text(card_html(w, fam, sup, ok, fonts_css, hand), encoding="utf-8")
            pg.goto(f.as_uri())
            pg.wait_for_timeout(120)
            png = out / "png" / f"{name}.png"
            pg.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": W, "height": H})
            pngs.append(png)
        br.close()

    (out / "messages.json").write_text(json.dumps({"weeks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "captions.md").write_text(captions(rows), encoding="utf-8")
    (out / "proof_checklist.md").write_text(proof_checklist(weeks, claims), encoding="utf-8")
    all_pngs = sorted((out / "png").glob("*.png"))
    contact_sheet(all_pngs, out / "contact_sheet.png")
    dist: dict[str, int] = {}
    for r in rows:
        dist[r["layout"]] = dist.get(r["layout"], 0) + 1
    manifest = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "size": [W, H], "count": len(all_pngs),
                "layouts": dist, "repeat_warnings": warns, "handwritten": hand_used,
                "fallback_weeks": [r["week"] for r in rows if r["used_fallback"]], "published": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
