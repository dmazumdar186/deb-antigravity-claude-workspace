"""Assemble the AlumnForce prep guide from HTML part fragments and print it to PDF.

Usage: python3 projects/alumnforce_case/tools/build_prep_guide.py [parts_dir]
Reads part0.html .. part10.html from parts_dir (default .tmp/af_prep), writes
projects/alumnforce_case/PREP_GUIDE.html and PREP_GUIDE.pdf. Re-runs overwrite both (idempotent).
Fails loudly if a part is missing.
"""

import html
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PARTS = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT.parents[1] / ".tmp" / "af_prep"
OUT_HTML = ROOT / "PREP_GUIDE.html"
OUT_PDF = ROOT / "PREP_GUIDE.pdf"

CSS = """
@page { size: A4; margin: 18mm 16mm 20mm 16mm; }
* { box-sizing: border-box; }
body { font-family: 'Georgia', 'DejaVu Serif', serif; font-size: 10.5pt; line-height: 1.5; color: #1d1d1f; }
h1, h2, h3, h4, .cover, th, .toc { font-family: 'Helvetica Neue', 'DejaVu Sans', Arial, sans-serif; }
h1 { font-size: 22pt; color: #0b3d5c; border-bottom: 3px solid #0b3d5c; padding-bottom: 6px; margin: 0 0 14px; }
h2 { font-size: 14.5pt; color: #0b3d5c; margin: 22px 0 8px; break-after: avoid; }
h3 { font-size: 12pt; color: #234; margin: 16px 0 6px; break-after: avoid; }
h4 { font-size: 11pt; margin: 0 0 6px; color: #123; }
section.part { break-before: page; }
p { margin: 0 0 8px; }
ul, ol { margin: 0 0 8px 0; padding-left: 20px; }
li { margin-bottom: 3px; }
table { border-collapse: collapse; width: 100%; margin: 8px 0 12px; font-size: 9.3pt; break-inside: auto; }
tr { break-inside: avoid; }
th, td { border: 1px solid #c9d3dc; padding: 5px 7px; vertical-align: top; text-align: left; }
th { background: #e8eff5; font-size: 9pt; }
.concept, .decision, .say, .assume, .warn, .recap { border-radius: 6px; padding: 9px 12px; margin: 10px 0 12px; break-inside: avoid; }
.decision { break-inside: auto; }
.concept { background: #f4f8fb; border-left: 4px solid #3a7ca5; }
.concept .plain { background: #fff; border: 1px dashed #b7cfe0; padding: 6px 8px; border-radius: 4px; }
.decision { background: #fbfaf4; border-left: 4px solid #b08900; }
.say { background: #eef8f0; border-left: 4px solid #2e8b57; font-style: italic; }
.assume { background: #f6f1fb; border-left: 4px solid #7b4fa0; }
.warn { background: #fdf0ef; border-left: 4px solid #c0392b; }
.recap { background: #0b3d5c; color: #fff; }
.recap b { color: #ffd166; }
td.best { color: #1e7b3c; font-weight: bold; white-space: nowrap; }
td.good { color: #8a6d00; font-weight: bold; white-space: nowrap; }
td.weak { color: #a33; font-weight: bold; white-space: nowrap; }
a { color: #1f5f8b; text-decoration: none; word-break: break-word; }
.cover { height: 255mm; display: flex; flex-direction: column; justify-content: center; }
.cover .kicker { font-size: 11pt; letter-spacing: 2px; text-transform: uppercase; color: #3a7ca5; }
.cover .title { font-size: 34pt; font-weight: 700; color: #0b3d5c; line-height: 1.1; margin: 10px 0 14px; }
.cover .sub { font-size: 13pt; color: #345; max-width: 150mm; }
.cover .meta { margin-top: 30px; font-size: 10pt; color: #567; }
.toc { break-before: page; }
.toc ol { list-style: none; padding: 0; }
.toc li.p { font-weight: 700; margin-top: 8px; font-size: 10.5pt; }
.toc li.c { padding-left: 16px; font-size: 8.8pt; color: #345; margin-bottom: 1px; }
.toc li { display: flex; justify-content: space-between; gap: 8px; }
.toc li .pg { color: #567; font-variant-numeric: tabular-nums; }
.toc li.p { margin-top: 6px; }
"""


def slug(i: int) -> str:
    return f"s{i}"


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9]", "", t.lower())


def find_pages(toc: list) -> dict:
    """Map heading anchor -> PDF page number by scanning extracted text in document order."""
    from pypdf import PdfReader

    texts = [norm(pg.extract_text() or "") for pg in PdfReader(str(OUT_PDF)).pages]
    # Skip the cover and contents: start after the last page that holds the contents list.
    start = next(i for i, t in enumerate(texts) if t.startswith("part0the60secondversion"))
    out, cur = {}, start
    for _, sid, t in toc:
        key = norm(t)[:40]
        for i in range(cur, len(texts)):
            if key and key in texts[i]:
                out[sid], cur = i + 1, i
                break
    return out


def render() -> None:
    js = f"""
const {{ chromium }} = require('playwright');
(async () => {{
  const b = await chromium.launch();
  const p = await b.newPage();
  await p.goto('file://{OUT_HTML}', {{ waitUntil: 'load' }});
  await p.pdf({{ path: '{OUT_PDF}', format: 'A4', printBackground: true, displayHeaderFooter: true,
    headerTemplate: '<div></div>',
    footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#789;">AlumnForce, inside out · <span class="pageNumber"></span> / <span class="totalPages"></span></div>',
    margin: {{ top: '18mm', bottom: '20mm', left: '16mm', right: '16mm' }} }});
  await b.close();
}})();
"""
    subprocess.run(["node", "-e", js], check=True)


def main() -> None:
    frags = []
    for n in range(11):
        f = PARTS / f"part{n}.html"
        if not f.exists():
            sys.exit(f"missing {f}")
        frags.append(f.read_text(encoding="utf-8"))
    body = "\n".join(frags)

    # Number every h1/h2 with an anchor and build the table of contents.
    toc, counter = [], [0]

    def tag(m: re.Match) -> str:
        counter[0] += 1
        level, attrs, inner = m.group(1), m.group(2), m.group(3)
        sid = slug(counter[0])
        text = html.unescape(re.sub(r"<[^>]+>", "", inner)).strip()
        toc.append((level, sid, text))
        return f'<h{level} id="{sid}"{attrs}>{inner}</h{level}>'

    body = re.sub(r"<h([12])([^>]*)>(.*?)</h\1>", tag, body, flags=re.S)
    def compose(pages: dict) -> str:
        toc_html = "".join(
            f'<li class="{"p" if lvl == "1" else "c"}"><a href="#{sid}">{html.escape(t)}</a>'
            f'<span class="pg">{pages.get(sid, "")}</span></li>'
            for lvl, sid, t in toc
        )
        return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AlumnForce: the complete prep guide</title><style>{CSS}</style></head><body>
<div class="cover"><div class="kicker">Private preparation document · not for sending</div>
<div class="title">AlumnForce, inside out</div>
<div class="sub">The company, the technology from zero, the case study, how we read the problem, every option we weighed, the solution we built, our assumptions, what we left out, and the CPO conversation drill.</div>
<div class="meta">Prepared for Debanjan Mazumdar · 17 November 2026 · for the session of 18 November 2026</div></div>
<nav class="toc"><h1>Contents</h1><ol>{toc_html}</ol></nav>
{body}
</body></html>"""

    # Pass 1 renders with placeholder numbers (same width), pass 2 fills real page numbers.
    OUT_HTML.write_text(compose({sid: "00" for _, sid, _ in toc}), encoding="utf-8")
    render()
    pages = find_pages(toc)
    OUT_HTML.write_text(compose(pages), encoding="utf-8")
    render()
    missing = [t for _, sid, t in toc if sid not in pages]
    if missing:
        print(f"WARNING: no page found for {len(missing)} headings: {missing[:5]}")
    print(f"wrote {OUT_HTML} and {OUT_PDF} ({OUT_PDF.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
