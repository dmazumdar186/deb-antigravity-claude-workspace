"""
build_samples.py
description: Build the four ProdCraft sample proposals (HTML + PDF) and PNG page previews for visual QA.
inputs: CLI --only <slug> (optional), --out <dir> (default deliverables/prodcraft_samples), --no-png.
outputs: <out>/<slug>.html, <out>/<slug>.pdf; .tmp/prodcraft_samples/png/<slug>-<n>.png; stdout overflow report.
  Exits 2 if any page content overflows its box.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

from render import render  # noqa: E402
import sample_event, sample_fitout_us, sample_fitout_uk, sample_dmc  # noqa: E402

MODULES = [sample_event, sample_fitout_us, sample_fitout_uk, sample_dmc]


def run(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--only")
    ap.add_argument("--out", default=str(ROOT / "deliverables/prodcraft_samples"))
    ap.add_argument("--no-png", action="store_true")
    a = ap.parse_args()
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    png_dir = ROOT / ".tmp/prodcraft_samples/png"; png_dir.mkdir(parents=True, exist_ok=True)
    bad = False
    for m in MODULES:
        doc = m.build()
        if a.only and doc.slug != a.only:
            continue
        html_path, pdf_path = out / f"{doc.slug}.html", out / f"{doc.slug}.pdf"
        html_path.write_text(render(doc), encoding="utf-8")
        r = run(["node", str(HERE / "render_pdf.js"), str(html_path), str(pdf_path)])
        if r.returncode not in (0, 2):
            print(f"[{doc.slug}] render failed: {r.stderr[-800:]}"); bad = True; continue
        rep = json.loads(r.stdout.strip().splitlines()[-1])
        print(f"[{doc.slug}] pages={rep['pages']} overflow={rep['overflow'] or 'none'}")
        bad |= bool(rep["overflow"])
        if not a.no_png:
            for old in png_dir.glob(f"{doc.slug}-*.png"):
                old.unlink()
            p = run(["pdftoppm", "-png", "-r", "75", str(pdf_path), str(png_dir / doc.slug)])
            if p.returncode:
                print(f"[{doc.slug}] pdftoppm failed: {p.stderr[-300:]}"); bad = True
    sys.exit(2 if bad else 0)


if __name__ == "__main__":
    main()
