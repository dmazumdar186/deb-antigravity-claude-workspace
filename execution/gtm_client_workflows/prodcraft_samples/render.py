"""
render.py
description: Generic HTML page renderer for ProdCraft sample proposals (decks and documents).
  Fixed-size pages, one accent colour per document, sample footer on every page.
inputs: a Doc built by samples.py (list of page HTML strings + page size + accent).
outputs: self-contained HTML string; PDF/PNG conversion is done by render_pdf.js.
"""
from __future__ import annotations

import html
from dataclasses import dataclass, field

FOOTER = "Sample — fictional client, illustrative figures. Prepared by ProdCraft."

SIZES = {
    "deck": ("13.333in", "7.5in"),      # 16:9 landscape
    "letter": ("8.5in", "11in"),        # US portrait
    "a4": ("210mm", "297mm"),           # UK / EU portrait
}


def esc(s: str) -> str:
    return html.escape(str(s), quote=False)


def money(n: int | float, cur: str = "$", signed: bool = False) -> str:
    v = round(n)
    body = f"{cur}{abs(v):,}"
    if v < 0:
        return f"–{body}"
    return f"+{body}" if signed and v > 0 else body


@dataclass
class Doc:
    slug: str
    title: str
    sender: str           # fictional firm issuing the proposal
    size: str             # key of SIZES
    accent: str
    pages: list[str] = field(default_factory=list)

    def add(self, body: str, cls: str = "") -> None:
        self.pages.append((body, cls))


def table(headers, rows, cls="", align=None, widths=None) -> str:
    """rows: list of lists, or (row_list, row_class) tuples. align: per-column 'l'/'r'/'c'."""
    n = len(headers)
    align = align or ["l"] * n
    cols = ""
    if widths:
        cols = "<colgroup>" + "".join(f'<col style="width:{w}">' for w in widths) + "</colgroup>"
    head = "".join(f'<th class="{align[i]}">{h}</th>' for i, h in enumerate(headers))
    body = []
    for r in rows:
        rc = ""
        if isinstance(r, tuple) and len(r) == 2 and isinstance(r[0], list) and isinstance(r[1], str):
            r, rc = r
        r = list(r)
        if len(r) != n:
            raise ValueError(f"ragged row {r!r} (expected {n} cols)")
        body.append(f'<tr class="{rc}">' + "".join(f'<td class="{align[i]}">{c}</td>' for i, c in enumerate(r)) + "</tr>")
    return f'<table class="t {cls}">{cols}<thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table>'


def gantt(periods: list[str], tasks: list[tuple[str, int, int]], milestones: dict[int, str] | None = None,
          sub: list[str] | None = None) -> str:
    """periods: column labels; tasks: (label, start_idx, end_idx_inclusive)."""
    head = "<th class='l'>Activity</th>" + "".join(f"<th class='c'>{p}</th>" for p in periods)
    rows = []
    for label, s, e in tasks:
        cells = "".join(f"<td class='g{' on' if s <= i <= e else ''}'></td>" for i in range(len(periods)))
        rows.append(f"<tr><td class='l'>{label}</td>{cells}</tr>")
    subrow = ""
    if sub:
        subrow = "<tr class='gsub'><td></td>" + "".join(f"<td class='c'>{x}</td>" for x in sub) + "</tr>"
    return f"<table class='t gantt'><thead><tr>{head}</tr>{subrow}</thead><tbody>{''.join(rows)}</tbody></table>"


def built_from(brief: str) -> str:
    return (f'<div class="builtfrom"><div class="bf-label">Built from</div>'
            f'<div class="bf-brief">“{esc(brief)}”</div>'
            f'<div class="bf-arrow">→ this proposal in one working day</div></div>')


CSS = """
@page { size: __W__ __H__; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; background: #d9d6cf; }
body { font-family: Inter, "Helvetica Neue", Arial, sans-serif; color: #16181c; -webkit-print-color-adjust: exact; print-color-adjust: exact; font-feature-settings: "tnum" 1; }
.page { width: __W__; height: __H__; background: #fff; position: relative; overflow: hidden;
  page-break-after: always; break-after: page; display: flex; flex-direction: column; padding: __PAD__; }
.page:last-child { page-break-after: auto; break-after: auto; }
@media screen { .page { margin: 24px auto; box-shadow: 0 4px 18px rgba(0,0,0,.12); } }
.hdr { display: flex; justify-content: space-between; align-items: baseline; font-size: 9.5px; letter-spacing: .14em;
  text-transform: uppercase; color: #6b6f76; border-bottom: 1px solid #e4dfd6; padding-bottom: 8px; margin-bottom: 18px; flex: none; }
.hdr b { color: #16181c; font-weight: 600; }
.content { flex: 1; min-height: 0; overflow: hidden; display: flex; flex-direction: column; }
.ftr { flex: none; display: flex; justify-content: space-between; font-size: 9px; color: #6b6f76;
  border-top: 1px solid #e4dfd6; padding-top: 7px; margin-top: 12px; }
h1 { font-size: 34px; line-height: 1.12; margin: 0 0 10px; font-weight: 650; letter-spacing: -.02em; }
h2 { font-size: 25px; line-height: 1.2; margin: 0 0 6px; font-weight: 650; letter-spacing: -.01em; }
h3 { font-size: 14px; margin: 16px 0 7px; font-weight: 650; }
.kicker { font-size: 10px; letter-spacing: .16em; text-transform: uppercase; color: var(--accent); font-weight: 650; margin-bottom: 6px; }
.lede { font-size: 14px; color: #3d4148; line-height: 1.5; margin: 0 0 14px; max-width: 46em; }
p, li { font-size: 12px; line-height: 1.55; color: #2b2e33; }
p { margin: 0 0 8px; }
ul { margin: 0 0 8px; padding-left: 16px; } li { margin-bottom: 5px; }
.small { font-size: 10.5px; color: #5b6068; }
.t { width: 100%; border-collapse: collapse; font-size: 11.5px; margin: 4px 0 10px; }
.t th { text-align: left; font-weight: 600; font-size: 9.5px; letter-spacing: .06em; text-transform: uppercase; color: #5b6068;
  border-bottom: 1.5px solid #16181c; padding: 5px 6px; }
.t td { padding: 6.5px 7px; border-bottom: 1px solid #ebe7e0; vertical-align: top; }
.t .r { text-align: right; white-space: nowrap; } .t .c { text-align: center; } .t .l { text-align: left; }
.t tr.sub td { font-weight: 600; background: #f7f3ec; }
.t tr.total td { font-weight: 700; font-size: 12.5px; border-top: 1.5px solid #16181c; border-bottom: none; background: #f7f3ec; }
.t tr.muted td { color: #6b6f76; }
.t tr.sec td { font-weight: 650; color: var(--accent); background: #fff; padding-top: 9px; font-size: 9.5px; letter-spacing: .06em; text-transform: uppercase; }
.gantt th.c { font-size: 8.5px; padding: 4px 1px; } .gantt td { padding: 4px 6px; } .gantt td.g { padding: 0; border-left: 1px solid #f0ece6; }
.gantt td.g.on { background: var(--accent); background-clip: content-box; padding: 5px 0; }
.gantt tr.gsub td { font-size: 8px; color: #6b6f76; padding: 2px 0; border-bottom: 1px solid #ebe7e0; }
.grid2 { display: grid; grid-template-columns: 1fr 1fr; gap: 18px; }
.grid3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 14px; }
.grid4 { display: grid; grid-template-columns: repeat(4, 1fr); gap: 12px; }
.card { border: 1px solid #e4dfd6; border-radius: 6px; padding: 12px 14px; background: #fff; }
.card.tint { background: #f7f3ec; border-color: #ece6db; }
.card h3 { margin-top: 0; }
.stat .n { font-size: 26px; white-space: nowrap; font-weight: 700; letter-spacing: -.01em; }
.stat .k { font-size: 9px; letter-spacing: .1em; text-transform: uppercase; color: #6b6f76; }
.builtfrom { border: 1px solid #d8d1c4; border-left: 4px solid var(--accent); background: #f7f3ec; border-radius: 4px; padding: 10px 14px; }
.bf-label { font-size: 9px; letter-spacing: .14em; text-transform: uppercase; color: #6b6f76; font-weight: 650; margin-bottom: 4px; }
.bf-brief { font-size: 11.5px; line-height: 1.45; color: #2b2e33; font-style: italic; }
.bf-arrow { font-size: 12.5px; font-weight: 650; color: var(--accent); margin-top: 6px; }
.cover .content { justify-content: space-between; }
.cover h1 { font-size: 40px; }
.meta { display: flex; gap: 40px; font-size: 10.5px; color: #5b6068; }
.meta > div:last-child { flex: none; }
.meta b { display: block; color: #16181c; font-size: 12.5px; font-weight: 600; margin-top: 2px; }
.band { height: 6px; background: var(--accent); margin: -1px 0 0; }
.sig { display: grid; grid-template-columns: 1fr 1fr; gap: 28px; margin-top: 10px; }
.sig .line { border-bottom: 1px solid #16181c; height: 30px; margin-bottom: 3px; }
.sig .lab { font-size: 9px; color: #6b6f76; margin-bottom: 10px; }
.note { font-size: 9.5px; color: #5b6068; border-left: 2px solid #d8d1c4; padding-left: 8px; margin: 4px 0 8px; }
.pill { display: inline-block; font-size: 9px; font-weight: 600; letter-spacing: .06em; text-transform: uppercase; padding: 2px 7px;
  border-radius: 10px; background: #f7f3ec; color: #3d4148; border: 1px solid #e4dfd6; }
/* deck */
.deck .hdr { margin-bottom: 24px; font-size: 11px; } .deck .ftr { font-size: 11px; }
.deck h1 { font-size: 60px; } .deck h2 { font-size: 38px; margin-bottom: 10px; } .deck .kicker { font-size: 12.5px; margin-bottom: 10px; }
.deck .lede { font-size: 19px; max-width: 52em; margin-bottom: 20px; } .deck p, .deck li { font-size: 16px; } .deck li { margin-bottom: 6px; }
.deck .t { font-size: 14.5px; } .deck .t td { padding: 7px 8px; } .deck .t th { font-size: 11px; padding: 7px 8px; }
.deck .card { padding: 16px 18px; } .deck .card h3 { font-size: 18px; margin-bottom: 8px; } .deck h3 { font-size: 18px; }
.deck .stat .n { font-size: 32px; } .deck .stat .k { font-size: 11px; } .deck .small { font-size: 13px; }
.deck .bf-brief { font-size: 14px; } .deck .bf-label { font-size: 11px; } .deck .bf-arrow { font-size: 15px; }
.deck .meta { font-size: 12.5px; gap: 40px; white-space: nowrap; } .deck .t tr.total td { font-size: 15.5px; } .deck .meta b { font-size: 15px; }
.deck .gantt td { padding: 6px 8px; font-size: 14px; } .deck .gantt th.c { font-size: 11px; }
.deck .gantt td.g.on { padding: 6px 0; }
.deck .stage .el { font-size: 13px; } .deck .stage .lbl { font-size: 12px; }
.oneliner { font-size: 40px; line-height: 1.3; font-weight: 600; letter-spacing: -.01em; max-width: 24em; margin: 8px 0 24px; }
.stage { position: relative; border: 1px solid #d8d1c4; border-radius: 6px; background: #f7f3ec; height: 100%; }
.stage .el { position: absolute; display: flex; align-items: center; justify-content: center; text-align: center;
  font-size: 10.5px; font-weight: 600; color: #fff; border-radius: 3px; }
.stage .lbl { position: absolute; font-size: 9.5px; color: #5b6068; text-align: center; }
.split { display: grid; grid-template-columns: 1.05fr 1fr; gap: 28px; flex: 1; min-height: 0; }
.itin .day { display: grid; grid-template-columns: 56px 1fr; gap: 10px; border-top: 1px solid #e4dfd6; padding: 10px 0 6px; }
.itin .day .d { font-size: 11px; font-weight: 700; color: var(--accent); letter-spacing: .06em; text-transform: uppercase; }
.itin .slot { display: grid; grid-template-columns: 74px 1fr; gap: 8px; margin-bottom: 4px; }
.itin .slot .tm { font-size: 10px; color: #6b6f76; font-weight: 600; padding-top: 1px; }
.itin .slot p { margin: 0; }
"""


def render(doc: Doc) -> str:
    w, h = SIZES[doc.size]
    pad = "0.55in 0.7in 0.38in" if doc.size == "deck" else "0.55in 0.65in 0.4in"
    css = CSS.replace("__W__", w).replace("__H__", h).replace("__PAD__", pad)
    total = len(doc.pages)
    out = []
    for i, (body, cls) in enumerate(doc.pages, 1):
        hdr = (f'<div class="hdr"><span><b>{esc(doc.sender)}</b></span><span>{esc(doc.title)}</span></div>')
        ftr = f'<div class="ftr"><span>{FOOTER}</span><span>{i} / {total}</span></div>'
        out.append(f'<section class="page {cls} {"deck" if doc.size == "deck" else ""}">{hdr}<div class="content">{body}</div>{ftr}</section>')
    return (f'<!DOCTYPE html><html lang="en"><head><meta charset="utf-8"><title>{esc(doc.title)} — sample</title>'
            f'<style>:root{{--accent:{doc.accent};}}{css}</style></head><body>{"".join(out)}</body></html>')
