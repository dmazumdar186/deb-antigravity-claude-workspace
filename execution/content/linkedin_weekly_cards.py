"""
description: Render the ProdCraft 50-week LinkedIn feed cards (1080x1350 PNG, 8 layout families, claim-gated copy) plus captions, proof checklist, contact sheet and manifest. Never publishes.
inputs: --messages execution/content/prodcraft_50_week_messages.json; --claims execution/content/prodcraft_claim_registry.json; --out <dir> (default deliverables/linkedin_weekly_cards/prodcraft/<date>); --fonts <dir with fonts_local.css; WARNs loudly if missing>; --logo <png> (default execution/content/assets/prodcraft_logo.png, embedded as data URI); --weeks 1-10,15 (ranges and lists; default all); --batch <label for index.html/zip, default auto>; env PW_CHROME (optional chromium path)
outputs: <out>/png/NN_week_slug.png, <out>/html/NN_week_slug.html, <out>/messages.json, <out>/captions.md, <out>/proof_checklist.md, <out>/contact_sheet.png, <out>/manifest.json, <out>/index.html (review contact sheet), <out>/prodcraft_weekly_cards_<batch>.zip (PNGs only)
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import html
import json
import os
import re
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
W, H = 1080, 1350
SAFE = 96  # mobile-safe margin; validator checks every text box stays inside it
BOOK_URL = "https://cal.com/debanjan-mazumdar-ben5rd/30min"
DEMO_URL = "https://cv-optimizer.pages.dev"
CTA_ON_IMAGE = {"Book session", "Soft invitation", "Demo link"}
LOGO = ROOT / "execution/content/assets/prodcraft_logo.png"
LOGO_STYLES = {"ink": ROOT / "execution/content/assets/prodcraft_logo_ink_2x.png",  # 96px-tall LANCZOS downsample of _ink.png, alpha cleaned
               "brass": ROOT / "execution/content/assets/prodcraft_logo_brass_2x.png", "color": LOGO}
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"
BRAND_FONTS = ("Newsreader", "Geist", "JetBrains Mono")  # Caveat retired 2026-10-25 (no handwritten mark)
SENTENCE_LINES = {2}  # headlines whose two sentences fit as two lines at 76px (reviewer item, 2026-10-25)
FOOT_LABEL = "ProdCraft · weekly notes"  # series label; prodcraft.fyi never appears on non-offer weeks
WJ = "\u2060"  # word joiner: keeps an em dash with the word before it (break falls after the dash)
NBSP = "\u00a0"
URL_RE = re.compile(r"""url\(\s*["']?(?!data:|file:|https?:)([^"')]+)["']?\s*\)""")
MAX_HEADLINE = 140  # longer headlines WARN; font floor stays 62px
NBH = "\u2011"  # non-breaking hyphen; hoisted so no backslash sits inside an f-string expression (<3.12)
CTA_TEXT = {"Book session": "30-minute session · link in the post",
            "Soft invitation": "More in the post",
            "Demo link": "Live demo · cv-optimizer.pages.dev"}
# Non-numeric receipt rows for case_receipt weeks rendered with a fallback line.
# Verbatim words from the pack copy (fallback line / companion angle); never invented facts.
RECEIPT_FALLBACK = {
    15: [("step 01", "reply routing"), ("step 02", "lead ownership"), ("step 03", "follow-up")],
    25: [("surface", "checkout"), ("risk", "payment edge cases"), ("decision", "onboarding")],
}

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
:root{--paper:#f3f1ec;--ink:#17191d;--ink2:#474b53;--brass:#a8843a;--hair:rgba(23,25,29,.25);--grain:url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='240' height='240'><filter id='g'><feTurbulence type='fractalNoise' baseFrequency='.9' numOctaves='2' stitchTiles='stitch'/><feColorMatrix values='0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 0 .5 0'/></filter><rect width='100%' height='100%' filter='url(%23g)'/></svg>")}
*{box-sizing:border-box}html,body{margin:0;padding:0}
body{font-family:Geist,Inter,system-ui,sans-serif;font-feature-settings:"ss01","cv11"}
.card{position:relative;width:1080px;height:1350px;overflow:hidden;background:var(--paper);color:var(--ink)}
.card:after{content:"";position:absolute;inset:0;background:var(--grain);opacity:.07;pointer-events:none;mix-blend-mode:multiply}
.card.dark{background:var(--ink);color:#f3f1ec;--ink2:#c3bfb6;--hair:rgba(243,241,236,.25);--brass:#c9a35a}
.card.dark:after{opacity:.05;mix-blend-mode:screen}
.serif,.it{font-family:Newsreader,'Bitstream Charter',FreeSerif,Georgia,serif}
.it{font-style:italic;font-weight:400}
.mono{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:15px;letter-spacing:.08em;color:var(--ink2);font-variant-numeric:tabular-nums}
.up{text-transform:uppercase}
/* grid: lockup y96 · kicker y232 · headline bottom-anchored at y712 · content 720-1120 · footer rule y1210 */
.top{position:absolute;left:96px;right:96px;top:96px;height:40px;display:flex;justify-content:space-between;align-items:flex-end}
.brand{display:flex;align-items:flex-end;gap:12px}
.brand img{height:40px;width:auto;display:block;margin-bottom:8px}
.brand span{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-weight:500;font-size:26px;line-height:1;letter-spacing:-.005em;padding-bottom:6px}
.top .mono{line-height:1;padding-bottom:4px}
.kick{display:block;font-size:15px;letter-spacing:.12em;margin-bottom:40px}
.head{position:absolute;left:96px;right:96px;bottom:638px}
h1{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-optical-sizing:auto;font-weight:500;font-size:84px;line-height:1.05;letter-spacing:-.018em;margin:0;max-width:888px}
.content{position:absolute;left:96px;right:96px;top:720px;height:400px;padding-top:32px;display:flex;flex-direction:column;justify-content:flex-start}
.sup{font-size:36px;line-height:44px;color:var(--ink2);margin:0;max-width:640px;text-wrap:pretty;font-weight:400}
.sup+.vis,.vis+.sup{margin-top:36px}
.vis{flex:0 0 auto}
.vis svg{display:block;width:100%;height:auto}
.foot{position:absolute;left:96px;right:96px;top:1210px;border-top:1px solid var(--hair);padding-top:22px;display:flex;justify-content:space-between}
.foot .n{color:var(--brass)}.foot .n.q{color:var(--ink2)}
/* founder note */
.sig{font-size:28px;line-height:1.3;color:var(--brass);margin-top:32px}
/* strip: boxes sized to content + 48px, 1.5px ink, 48px joins, no arrowheads */
.strip{display:flex;align-items:center;justify-content:space-between}
.bx{border:1.5px solid var(--ink);padding:12px 24px;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:17px;letter-spacing:.02em;color:var(--ink);line-height:1.2;white-space:nowrap}
.bx.b{border-color:var(--brass);color:var(--brass)}
.join{height:1.5px;background:var(--ink);flex:1 1 48px}
/* chain: 10px nodes on a 1.5px spine, boxes left-aligned */
.chain{position:relative;padding-left:40px;margin:0;list-style:none}
.chain:before{content:"";position:absolute;left:4.25px;top:32px;bottom:32px;width:1.5px;background:var(--ink)}
.chain li{position:relative;height:64px;display:flex;align-items:center;margin-bottom:20px}
.chain li:last-child{margin-bottom:0}
.chain li:before{content:"";position:absolute;left:-40px;top:27px;width:10px;height:10px;border-radius:50%;border:1.5px solid var(--ink);background:var(--paper)}
.chain li:last-child:before{background:var(--brass);border-color:var(--brass)}
.chain .bx{font-family:Geist,Inter,system-ui,sans-serif;font-size:30px;letter-spacing:0;padding:12px 24px}
/* numbered list: mono numerals, 1px rules */
.ls{list-style:none;padding:0;margin:0;border-top:1px solid var(--hair)}
.ls li{display:flex;gap:28px;align-items:baseline;padding:13px 0;border-bottom:1px solid var(--hair);font-size:34px;line-height:1.25;color:var(--ink)}
.ls .num{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:15px;letter-spacing:.04em;color:var(--ink2);flex:0 0 40px;font-variant-numeric:tabular-nums}
.stem{font-size:36px;line-height:1.3;color:var(--ink2);margin:0 0 20px}
.ls.c li{padding:10px 0;font-size:30px}.ls.c+.stem,.c .stem{margin-bottom:14px}.vis.c{margin-top:32px}
/* two columns */
.two{display:grid;grid-template-columns:1fr 1fr;column-gap:48px}
.two .col{padding-top:32px;border-top:1px solid var(--hair)}
.two .lab{margin-bottom:18px}
.two .v{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-optical-sizing:auto;font-weight:400;font-size:36px;line-height:1.25;margin:0;color:var(--ink)}
.two .v.m{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:22px;letter-spacing:.02em;line-height:1.5}
/* italic statement */
.quote{font-size:44px;line-height:1.25;margin:0;color:var(--ink);max-width:888px}
.quote{font-size:40px}.quote+.quote{margin-top:24px}
/* checklist (generic weeks): 36px squares, 1.5px stroke */
.check{list-style:none;padding:0;margin:0;border-top:1px solid var(--hair)}
.check li{display:flex;gap:28px;align-items:flex-start;padding:22px 0;border-bottom:1px solid var(--hair);font-size:34px;line-height:1.25}
.box{flex:0 0 36px;height:36px;border:1.5px solid var(--ink);margin-top:3px}
/* before/after (generic weeks) */
.ba{display:grid;grid-template-columns:1fr 1fr;column-gap:48px;padding-top:24px;border-top:1px solid var(--hair)}
.col .k{margin-bottom:18px}
.col p{font-family:Newsreader,'Bitstream Charter',FreeSerif,serif;font-optical-sizing:auto;font-weight:400;font-size:36px;line-height:1.2;margin:0;text-wrap:pretty}
.col.a p{color:var(--ink2)}
.col.b{border-left:1px solid var(--hair);padding-left:48px}
/* code */
.code{border:1px solid var(--hair);padding:24px;font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:22px;line-height:1.6;color:#f3f1ec;white-space:pre-wrap;overflow:hidden}
.code .c{color:#9a968e}.code .k{color:var(--brass)}
.illus{margin-top:16px}
/* receipt */
.rcpt{font-family:'JetBrains Mono','DejaVu Sans Mono',monospace;font-size:22px;line-height:1.5;max-width:720px;border-top:1px solid var(--hair)}
.rcpt .row{display:flex;justify-content:space-between;gap:24px;border-bottom:1px solid var(--hair);padding:12px 0}
.rcpt .row span:last-child{text-align:right}
.rcpt .tot{font-weight:600;border:0;padding-top:20px}
"""
FIT_JS = """<script>window.fitHead=function(){var h=document.querySelector('h1');if(!h)return 0;var s=[[84,2],[76,3],[68,4]];
for(var i=0;i<s.length;i++){h.style.fontSize=s[i][0]+'px';var n=Math.round(h.getBoundingClientRect().height/(s[i][0]*1.05));if(n<=s[i][1]&&h.scrollWidth<=h.clientWidth+1)return s[i][0];}return 68;};
window.fitHead();document.fonts.ready.then(window.fitHead);</script>"""


def esc(s: str) -> str:
    return html.escape(s, quote=True)


def slugify(s: str, n: int = 6) -> str:
    words = re.findall(r"[a-z0-9]+", s.lower().replace("’", "").replace("'", ""))
    return "_".join(words[:n]) or "card"


def fragments(text: str) -> list[str]:
    """Split a supporting line into 2-5 short steps, verbatim words only (never invent)."""
    t = text.rstrip(".")
    parts = re.split(r"\s*[:;—]\s*|,\s*(?:and\s+|or\s+)?|\s+and\s+|\s+or\s+|\s+then\s+", t)
    parts = [p.strip(" .") for p in parts if p and len(p.strip(" .")) > 1]
    return parts[:5]


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


def receipt_rows(w: dict, sup: str, numeric_ok: bool) -> list[tuple[str, str]]:
    """Rows printed on a case_receipt card (also stored in messages.json so the validator gates them)."""
    rows = [("case", w["theme"].lower())]
    if not numeric_ok:
        fb = RECEIPT_FALLBACK.get(w["week"])
        if fb:
            return rows + fb
        return rows + [(f"step {i + 1:02d}", s) for i, s in enumerate(fragments(sup)[:3])]
    return rows + [("evidence", "verified")] + [(f"note {i + 1:02d}", s) for i, s in enumerate(fragments(sup)[:3])]


def _wrap(text: str, width_px: float, px: int) -> list[str]:
    """Greedy word wrap for SVG text using a conservative Geist average advance (0.56em)."""
    maxc = max(8, int(width_px / (px * 0.56)))
    lines, cur = [], ""
    for word in text.split():
        cand = f"{cur} {word}".strip()
        if len(cand) > maxc and cur:
            lines.append(cur)
            cur = word
        else:
            cur = cand
    if cur:
        lines.append(cur)
    return lines


def _svg_text(x: float, y: float, lines: list[str], px: int, cls: str = "", anchor: str = "start") -> str:
    out = []
    for i, ln in enumerate(lines):
        out.append(f'<text x="{x:.0f}" y="{y + i * px * 1.28:.0f}" font-size="{px}" text-anchor="{anchor}" class="{cls}">{esc(ln)}</text>')
    return "".join(out)


def _cap(s: str) -> str:
    return s[:1].upper() + s[1:]


def flow_svg(steps: list[str], kind: str) -> str:
    """Workflow diagrams (generic weeks): 1.5px ink strokes, 10px nodes, no arrowheads, no fills, no shadows. Shapes: chain, branch, lanes."""
    width, px, pad, gapv = 888, 34, 30, 48
    style = ('<style>text{font-family:Geist,Inter,system-ui,sans-serif;fill:#17191d}'
             '.m{font-family:"JetBrains Mono","DejaVu Sans Mono",monospace;fill:#474b53;letter-spacing:.02em}'
             '.ac{fill:#a8843a}rect,line,path,circle{stroke:#17191d;stroke-width:1.5;fill:none}</style>')
    defs = ""
    body, y = [], 0
    if kind == "branch" and len(steps) >= 3:
        # peers: the support line lists alternatives side by side; joined by "+" so no hierarchy is invented
        n = len(steps)
        gap = 56
        cw = (width - gap * (n - 1)) / n
        wrapped = [_wrap(_cap(k), cw - 2 * pad, px) for k in steps]
        h = max(len(ls) for ls in wrapped) * px * 1.28 + 2 * pad - px * .28
        for i, ls in enumerate(wrapped):
            x = i * (cw + gap)
            body.append(f'<rect x="{x + 1:.0f}" y="1" width="{cw - 2:.0f}" height="{h:.0f}"/>')
            body.append(_svg_text(x + pad, pad + px * .9, ls, px))
            if i < n - 1:
                body.append(f'<text x="{x + cw + gap / 2:.0f}" y="{h / 2 + 10:.0f}" font-size="28" text-anchor="middle" class="m">+</text>')
        return f'<svg viewBox="0 0 {width} {h + 2:.0f}" xmlns="http://www.w3.org/2000/svg">{style}{defs}{"".join(body)}</svg>'
    if kind == "lanes":
        # ledger: one hairline row per case, a mono "when" gutter, a brass dot on the last row
        lane_w = 56
        body.append(f'<line x1="0" y1="1" x2="{width}" y2="1"/>')
        y = 1
        for i, st in enumerate(steps):
            lines = _wrap(_cap(st), width - lane_w - pad, px)
            h = len(lines) * px * 1.28 + 2 * pad - px * .28
            body.append(_svg_text(lane_w, y + pad + px * .9, lines, px))
            last = i == len(steps) - 1
            body.append(f'<circle cx="6" cy="{y + pad + px * .55:.0f}" r="5"{" style=\"fill:#a8843a;stroke:#a8843a\"" if last else ""}/>')
            body.append(f'<line x1="0" y1="{y + h:.0f}" x2="{width}" y2="{y + h:.0f}"{"" if last else " stroke-dasharray=\"2 6\""}/>')
            y += h
        return f'<svg viewBox="0 0 {width} {y + 2:.0f}" xmlns="http://www.w3.org/2000/svg">{style}{defs}{"".join(body)}</svg>'
    # chain: stacked nodes on a left spine, mono step marker, arrows between
    spine = 64
    for i, st in enumerate(steps):
        lines = _wrap(_cap(st), width - spine - 2 * pad, px)
        h = len(lines) * px * 1.28 + 2 * pad - px * .28
        body.append(f'<rect x="{spine + 1}" y="{y + 1:.0f}" width="{width - spine - 2}" height="{h:.0f}"/>')
        body.append(f'<circle cx="{spine / 2:.0f}" cy="{y + h / 2:.0f}" r="5"{" style=\"fill:#a8843a;stroke:#a8843a\"" if i == len(steps) - 1 else ""}/>')
        body.append(_svg_text(spine + pad, y + pad + px * .9, lines, px))
        if i < len(steps) - 1:
            body.append(f'<line x1="{spine / 2:.0f}" y1="{y + h / 2 + 5:.0f}" x2="{spine / 2:.0f}" y2="{y + h + gapv + 0.5 * (len(_wrap(_cap(steps[i + 1]), width - spine - 2 * pad, px)) * px * 1.28 + 2 * pad - px * .28) - 7:.0f}"/>')
        y += h + gapv
    return f'<svg viewBox="0 0 {width} {y - gapv + 3:.0f}" xmlns="http://www.w3.org/2000/svg">{style}{defs}{"".join(body)}</svg>'


def visual(w: dict, fam: str, sup: str, numeric_ok: bool) -> str:
    steps = fragments(sup)
    if fam == "annotated_workflow":
        if len(steps) < 3:
            return ""  # no invented nodes: the card renders headline + supporting line only
        kind = "branch" if w["visual_direction"] in {"decision_tree", "routing_map", "crm_routing_map"} else \
            "lanes" if w["visual_direction"] in {"swimlane", "sequence_diagram"} else "chain"
        return flow_svg(steps, kind)
    if fam == "failure_checklist":
        items = steps if len(steps) >= 2 else [sup]
        lis = "".join(f'<li class="t"><span class="num">{i + 1:02d}</span><span>{esc(_cap(s))}</span></li>' for i, s in enumerate(items))
        return f'<ul class="ls">{lis}</ul>'
    if fam == "before_after":
        heads = [s.strip() for s in re.split(r"(?<=\.)\s+", w["headline"]) if s.strip()]
        left_k, right_k = PAIR_LABELS.get(w["visual_direction"], ("Usually", "Instead"))
        neg = re.match(r"^(.*?)\s+(?:is not|isn[’']t|is just|isn[’']t yet)\s+(.*?)\.?$", w["headline"])
        if len(heads) >= 2:
            a, b = heads[0], " ".join(heads[1:])
        elif neg:
            a, b = neg.group(1), _cap(neg.group(2))  # verbatim halves of the headline's own contrast
        else:
            half = max(1, len(steps) // 2)
            a, b = ", ".join(steps[:half]) or sup, ", ".join(steps[half:]) or sup
        return (f'<div class="ba"><div class="col a t"><div class="k mono up">{left_k}</div><p>{esc(a)}</p></div>'
                f'<div class="col b t"><div class="k mono up">{right_k}</div><p>{esc(b)}</p></div></div>')
    if fam == "code_to_outcome":
        lines = ['<span class="c"># illustrative sketch, not production code</span>']
        named = [slugify(s, 4) for s in steps] if len(steps) >= 2 else ["read_input", "check_rule", "write_result"]
        if len(steps) < 2:
            lines.append(f'<span class="c"># {esc(sup)}</span>')
        for name in named:
            lines.append(f'<span class="k">step</span>("{esc(name)}")')
        lines.append('<span class="c"># outcome: explained in the post</span>' if w["visual_direction"] != "test_case_card"
                     else '<span class="c"># expected: pass on the edge case, not just the demo</span>')
        return f'<div class="code t">{chr(10).join(lines)}</div><div class="illus mono">illustrative pseudo-code</div>'
    if fam == "case_receipt":
        body = "".join(f'<div class="row"><span>{esc(k)}</span><span>{esc(v)}</span></div>' for k, v in receipt_rows(w, sup, numeric_ok))
        return f'<div class="rcpt t">{body}<div class="row tot"><span>takeaway</span><span>see post</span></div></div>'
    return ""


def cta_line(w: dict) -> str:  # kept for callers; the CTA now lives in the footer label
    txt = cta_text(w)
    return esc(txt) if txt else ""


def cta_text(w: dict) -> str:
    return CTA_TEXT.get(w["cta"], "") if w["cta"] in CTA_ON_IMAGE else ""


def typeset(text: str, sentences: bool = False) -> str:
    """Escape, non-breaking hyphens, em dash stays with the word before it, no single-word widow.
    sentences=True glues each sentence into one unbreakable line (used when two sentences fit as two lines)."""
    t = esc(text).replace("-", NBH).replace("—", WJ + "—")
    if sentences:
        return " ".join(part.replace(" ", NBSP) for part in re.split(r"(?<=\.)\s+", t))
    if t.count(" ") >= 2:
        head, tail = t.rsplit(" ", 1)
        t = head + NBSP + tail
    return t


def _list(stem: str, items: list[str], compact: bool = False) -> str:
    lis = "".join(f'<li class="t"><span class="num">{i + 1:02d}</span><span>{esc(x)}</span></li>' for i, x in enumerate(items))
    c = " c" if compact else ""
    return f'<div class="{c.strip()}"><p class="stem t">{esc(stem)}</p><ul class="ls{c}">{lis}</ul></div>'


def _two(lk: str, lv: str, rk: str, rv: str, mono: bool = False) -> str:
    m = " m" if mono else ""
    return (f'<div class="two"><div class="col"><div class="lab mono up t">{esc(lk)}</div><p class="v{m} t">{esc(lv)}</p></div>'
            f'<div class="col"><div class="lab mono up t">{esc(rk)}</div><p class="v{m} t">{esc(rv)}</p></div></div>')


def custom_visual(w: dict, sup: str) -> dict | None:
    """Reviewed visuals for weeks 01-10. Words come only from supporting_line + companion_post (never invented).
    Returns {"vis": html, "sup": "above"|"below"|"none", "words": [gated strings], "brass": bool(visual carries the brass)}."""
    k = w["week"]
    if k == 1:
        steps = [("happy path", ""), ("handoff", " b"), ("exception", "")]
        strip = '<span class="join"></span>'.join(f'<span class="bx t{c}">{t}</span>' for t, c in steps)
        return {"vis": f'<div class="strip">{strip}</div>', "sup": "above", "words": [t for t, _ in steps], "brass": True}
    if k == 2:
        return {"vis": _two("activity", "sent", "progress", "classified · routed · followed up").replace("routed · followed", "routed<br>followed"), "sup": "below",
                "words": ["activity", "sent", "progress", "classified · routed · followed up"], "brass": False}
    if k == 3:
        stem, items = "A product has to handle:", ["Missing fields", "Strange inputs", "Wrong answers"]
        return {"vis": _list(stem, items), "sup": "none", "words": [stem] + items, "brass": False}
    if k == 4:
        steps = fragments(sup)[:4]
        lis = "".join(f'<li><span class="bx t">{esc(_cap(x))}</span></li>' for x in steps)
        return {"vis": f'<ul class="chain">{lis}</ul>', "sup": "none", "words": [], "brass": True}
    if k == 5:
        sig = "— Debanjan, ProdCraft"
        return {"vis": f'<div class="sig it t">{esc(sig)}</div>', "sup": "above", "words": [sig], "brass": True}
    if k == 6:
        q, cap = "a rule + an API call + one human check", "…are enough."
        return {"vis": f'<p class="quote it t">{esc(q)}</p><p class="quote it t">{esc(cap)}</p>', "sup": "none",
                "words": [q, cap], "brass": False}
    if k == 7:
        stem, items = "A handoff should preserve:", ["caller context", "reason", "transcript"]
        return {"vis": _list(stem, items, compact=True), "sup": "above", "words": [stem] + items, "brass": False}
    if k == 8:
        return {"vis": "", "sup": "above", "words": [], "brass": False}
    if k == 9:
        words = ["roadmap item", "feature ships", "outcome", "what changes for the user"]
        return {"vis": _two(*words), "sup": "above", "words": words, "brass": False}
    if k == 10:
        stem, items = "Who acts when:", ["the model is uncertain", "the API fails", "the customer needs a person"]
        return {"vis": _list(stem, items), "sup": "none", "words": [stem] + items, "brass": False}
    return None


def card_html(w: dict, fam: str, sup: str, numeric_ok: bool, fonts_css: str, hand: bool, logo_uri: str) -> tuple[str, list[str]]:
    """Return (html, visual_words). Grid: lockup y96, kicker y232, headline bottom y712, content 720-1120, footer y1210."""
    kick = "WORKING SESSION · more in the post" if w["week"] == 8 else w["theme"].upper()
    head = f'<div class="head"><div class="kick mono t">{esc(kick)}</div><h1 class="t">{typeset(w["headline"], sentences=w["week"] in SENTENCE_LINES)}</h1></div>'
    supp = f'<p class="sup t">{typeset(sup)}</p>'
    dark = " dark" if fam in DARK_FAMILIES else ""
    cv = custom_visual(w, sup)
    if cv:
        vis, mode, words, brass_vis = cv["vis"], cv["sup"], cv["words"], cv["brass"]
    else:
        vis, words, brass_vis = visual(w, fam, sup, numeric_ok), [], fam in {"annotated_workflow", "case_receipt"}
        mode = "none" if fam in {"failure_checklist", "annotated_workflow", "code_to_outcome"} and len(fragments(sup)) >= 3 and vis else "above"
        if fam == "founder_note":
            sig = "— Debanjan, ProdCraft"
            vis, words, brass_vis = f'<div class="sig it t">{esc(sig)}</div>', [sig], True
    visb = f'<div class="vis">{vis}</div>' if vis else ""
    content = {"above": supp + visb, "below": visb + supp, "none": visb or supp}[mode]
    brand = (f'<span class="brand"><img src="{logo_uri}" alt=""><span class="t">ProdCraft</span></span>' if logo_uri
             else '<span class="brand"><span class="t">ProdCraft</span></span>')
    label = FOOT_LABEL
    return (f"""<!doctype html><html><head><meta charset="utf-8"><style>{fonts_css}{CSS}</style></head><body>
<div class="card f-{fam}{dark}"><div class="top">{brand}<span class="mono t">wk {w["week"]:02d}</span></div>
{head}
<div class="content">{content}</div>
<div class="foot"><span class="mono t">{esc(label)}</span><span class="mono n{" q" if brass_vis else ""} t">{w["week"]:02d}</span></div></div>{FIT_JS}</body></html>""", words)


def chromium_path() -> str | None:
    if os.environ.get("PW_CHROME"):
        return os.environ["PW_CHROME"]
    return next((str(x) for x in Path("/opt/pw-browsers").glob("chromium-*/chrome-linux*/chrome")), None)


def load_fonts(fonts_dir: Path) -> str:
    css = fonts_dir / "fonts_local.css"
    if css.exists():
        base = fonts_dir.resolve().as_uri()
        return URL_RE.sub(lambda m: f'url("{base}/{m.group(1)}")', css.read_text(encoding="utf-8"))
    print(f"WARN WARN WARN fonts: {css} missing; cards will render in system fallbacks and will NOT look like the brand. "
          "Restore .tmp/banners/fonts/ (see directives/content/linkedin_banners.md) before shipping.", file=sys.stderr)
    return ""


def verify_fonts(pg) -> list[str]:
    """Return brand families that Chromium actually loaded for the current page (document.fonts)."""
    loaded = pg.evaluate("async () => { await document.fonts.ready; return [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, '')); }")
    return sorted({f for f in loaded if f in BRAND_FONTS})


def parse_weeks(spec: str) -> set[int]:
    """'1-10,15' -> {1..10, 15}; '' -> empty set (= all). Raises argparse.ArgumentTypeError on anything outside 1..50 or lo > hi."""
    out: set[int] = set()
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.fullmatch(r"(\d+)(?:-(\d+))?", part)
        if not m:
            raise argparse.ArgumentTypeError(f"--weeks: '{part}' is not N or N-M")
        lo, hi = int(m.group(1)), int(m.group(2) or m.group(1))
        if not 1 <= lo <= hi <= 50:
            raise argparse.ArgumentTypeError(f"--weeks: '{part}' must satisfy 1 <= lo <= hi <= 50")
        out.update(range(lo, hi + 1))
    return out


def logo_data_uri(path: Path) -> str:
    if not path.is_file() or not path.read_bytes().startswith(PNG_MAGIC):
        print(f"WARN logo {path} missing or not a PNG; wordmark only", file=sys.stderr)
        return ""
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode()


def review_page(out: Path, rows: list[dict], pngs: list[Path], batch: str, zip_name: str) -> None:
    """Contact-sheet index for the review link: every card at 540px with caption (angle, CTA, guardrail) + PNG download; no trackers."""
    by_file = {r.get("file"): r for r in rows}
    weeks = [by_file[f"png/{p.name}"]["week"] for p in pngs if f"png/{p.name}" in by_file]
    rng = f"weeks {min(weeks)}–{max(weeks)}" if weeks else "no weeks"
    cards = []
    for p in pngs:
        r = by_file.get(f"png/{p.name}")
        if not r:
            continue
        link = BOOK_URL if r["cta"] == "Book session" else DEMO_URL if r["cta"] == "Demo link" else ""
        cards.append(
            f'<figure><img src="png/{esc(p.name)}" width="540" height="675" alt="week {r["week"]:02d}" loading="lazy">'
            f'<figcaption><b>wk {r["week"]:02d}</b> · {esc(r["theme"])} <span class="m">{esc(r["layout"])}</span>'
            f'<p class="cap"><b>Angle</b> {esc(r["companion_post"])}</p>'
            f'<p class="cap"><b>CTA</b> {esc(r["cta"])}{(" · " + esc(link)) if link else ""}</p>'
            f'<p class="cap"><b>Guardrail</b> {esc(r["publish_guardrail"])}</p>'
            f'<a href="png/{esc(p.name)}" download>Download PNG</a></figcaption></figure>')
    title = f"ProdCraft · weekly cards · {batch} ({rng})"
    html_doc = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><style>
body{{margin:0;padding:48px;background:#f3f1ec;color:#17191d;font:16px/1.5 Geist,Inter,system-ui,sans-serif}}
h1{{font-family:Newsreader,Georgia,serif;font-weight:500;font-size:32px;margin:0 0 8px}}
p{{margin:0 0 32px;color:#474b53}}p a{{color:#17191d}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,540px);gap:48px 32px}}
figure{{margin:0}}img{{display:block;width:540px;height:675px;border:1px solid rgba(23,25,29,.18)}}
figcaption{{padding-top:12px}}.m{{font-family:"JetBrains Mono",monospace;font-size:13px;color:#474b53}}
figcaption a{{color:#17191d}}figcaption .cap{{margin:8px 0;font-size:14px;color:#474b53}}figcaption .cap b{{color:#17191d;font-weight:500}}
</style></head><body>
<h1>{esc(title)}</h1>
<p>PNGs are 1080×1350 (4:5), LinkedIn image-post ready, under 5 MB each. <a href="{esc(zip_name)}" download>Download all (zip)</a> · <a href="contact_sheet.png">contact sheet</a> · {len(cards)} cards</p>
<div class="grid">{"".join(cards)}</div></body></html>
"""
    (out / "index.html").write_text(html_doc, encoding="utf-8")


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
    tw, th = 216, 270
    cols = 5 if len(pngs) <= 10 else 10
    rows = max(1, (len(pngs) + cols - 1) // cols)
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
    ap.add_argument("--logo", default="", help="PNG mark override (default: the --logo-style asset), embedded as data URI, 40px tall")
    ap.add_argument("--logo-style", choices=sorted(LOGO_STYLES), default="ink", help="ink (flat one-colour, default), brass, or the original colour raster")
    ap.add_argument("--weeks", default="", type=parse_weeks, help="weeks to render, ranges and lists: 1-10,15 (default all)")
    ap.add_argument("--batch", default="", help="label for index.html/zip, e.g. 'batch 1' (default: batch N from the first week)")
    a = ap.parse_args()

    weeks = json.loads(Path(a.messages).read_text(encoding="utf-8"))["weeks"]
    claims = json.loads(Path(a.claims).read_text(encoding="utf-8"))["claims"]
    only: set[int] = a.weeks
    missing_weeks = sorted(only - {w["week"] for w in weeks})
    if missing_weeks:
        print(f"ERROR --weeks {missing_weeks} not found in {a.messages}", file=sys.stderr)
        return 2
    fams, warns = choose_families(weeks)
    for wn in warns:
        print("WARN", wn, file=sys.stderr)
    out = Path(a.out).resolve()
    (out / "png").mkdir(parents=True, exist_ok=True)
    (out / "html").mkdir(exist_ok=True)
    fonts_css = load_fonts(Path(a.fonts))
    logo_uri = logo_data_uri(Path(a.logo) if a.logo else LOGO_STYLES[a.logo_style])
    fonts_seen: set[str] = set()

    from playwright.sync_api import sync_playwright
    rows, pngs, hand_used = [], [], 0
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=chromium_path())
        pg = br.new_page(viewport={"width": W, "height": H}, device_scale_factor=1)
        for w, fam in zip(weeks, fams):
            ok, mine = claim_ok(w["week"], claims)
            sup = w["supporting_line"] if ok else w.get("fallback_supporting_line", "")
            head_ok = ok or not any(any(m in w["headline"] for m in c["match"]) for c in mine)
            if len(w["headline"]) > MAX_HEADLINE:
                print(f"WARN week {w['week']:02d}: headline {len(w['headline'])} chars > {MAX_HEADLINE}", file=sys.stderr)
            if not head_ok or not sup:
                why = "headline carries an unapproved number" if not head_ok else "unapproved claim and no fallback_supporting_line"
                print(f"WARN week {w['week']:02d}: {why}; card not rendered", file=sys.stderr)
                rows.append({**w, "layout": fam, "verdict": "blocked", "blocked_reason": why, "file": None, "html": None})
                continue
            name = f"{w['week']:02d}_week_{slugify(w['headline'])}"
            doc, words = card_html(w, fam, sup, ok, fonts_css, False, logo_uri)
            row = {**w, "layout": fam, "rendered_supporting_line": sup, "used_fallback": sup != w["supporting_line"],
                   "handwritten": False, "cta_text": cta_text(w), "visual_words": words,
                   "receipt_rows": [list(x) for x in receipt_rows(w, sup, ok)] if fam == "case_receipt" else [],
                   "evidence": ("verified" if ok else "non-numeric") if fam == "case_receipt" else None, "file": f"png/{name}.png", "html": f"html/{name}.html"}
            rows.append(row)
            if only and w["week"] not in only:
                continue
            f = out / "html" / f"{name}.html"
            f.write_text(doc, encoding="utf-8")
            pg.goto(f.as_uri())
            fonts_seen.update(verify_fonts(pg))  # awaits document.fonts.ready
            pg.evaluate("window.fitHead && window.fitHead()")  # headline size by line count, measured in the brand face
            pg.wait_for_timeout(120)
            png = out / "png" / f"{name}.png"
            pg.screenshot(path=str(png), clip={"x": 0, "y": 0, "width": W, "height": H})
            pngs.append(png)
        br.close()
    missing_fonts = [x for x in BRAND_FONTS[:3] if x not in fonts_seen]
    if pngs and missing_fonts:
        print(f"WARN WARN WARN fonts not loaded in Chromium: {missing_fonts} (loaded: {sorted(fonts_seen)}); cards are in fallback faces", file=sys.stderr)
    else:
        print(f"fonts loaded: {sorted(fonts_seen)}", file=sys.stderr)

    # this run's PNGs are the batch: stale png/html from other weeks are removed so zip, sheet and manifest agree
    keep = {p.name for p in pngs} | {p.with_suffix(".html").name for p in pngs}
    for stale in [*(out / "png").glob("*.png"), *(out / "html").glob("*.html")]:
        if stale.name not in keep:
            stale.unlink()
            print(f"note: removed stale {stale.relative_to(out)}", file=sys.stderr)
    (out / "messages.json").write_text(json.dumps({"weeks": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (out / "captions.md").write_text(captions(rows), encoding="utf-8")
    (out / "proof_checklist.md").write_text(proof_checklist(weeks, claims), encoding="utf-8")
    run_pngs = sorted(pngs)
    contact_sheet(run_pngs, out / "contact_sheet.png")
    rendered_weeks = sorted(only) if only else [r["week"] for r in rows]
    batch = a.batch or f"batch {(min(rendered_weeks) - 1) // 10 + 1}"
    zip_name = f"prodcraft_weekly_cards_{batch.replace(' ', '')}.zip"
    with zipfile.ZipFile(out / zip_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for pth in run_pngs:
            zf.write(pth, f"png/{pth.name}")
    review_page(out, rows, run_pngs, batch, zip_name)
    dist: dict[str, int] = {}
    for r in rows:
        dist[r["layout"]] = dist.get(r["layout"], 0) + 1
    manifest = {"generated": dt.datetime.now().isoformat(timespec="seconds"), "size": [W, H], "count": len(run_pngs),
                "weeks": [int(p.name[:2]) for p in run_pngs], "layouts": dist, "repeat_warnings": warns, "handwritten": hand_used,
                "fallback_weeks": [r["week"] for r in rows if r.get("used_fallback")],
                "blocked_weeks": [r["week"] for r in rows if r.get("verdict") == "blocked"],
                "non_numeric_receipts": [r["week"] for r in rows if r.get("evidence") == "non-numeric"],
                "fonts_loaded": sorted(fonts_seen), "logo": bool(logo_uri), "logo_style": a.logo_style if not a.logo else "custom",
                "index": "index.html", "zip": zip_name, "published": False}
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(manifest, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
