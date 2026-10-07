"""CLI for the Jev page assembler.

description: Renders persona pages with one Jev call each and prints a persona x slot
             choice table with cost and latency.
inputs: render --persona X [--out .tmp/page_X.html]; render-all [--out-dir .tmp/jev_pages];
        --brand-json {name, product, audience}; --no-cache; --debug.
        env OPENROUTER_API_KEY (or alias).
outputs: HTML files, table on stdout, summary JSON at <out-dir>/summary.json (render-all).
"""
from __future__ import annotations

import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[3]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.content.jev_page_assembler import assembler  # noqa: E402


def print_table(rows: list[tuple[str, dict[str, Any]]]) -> None:
    cols = ["persona"] + assembler.SLOTS + ["buyer", "ms", "cost", "note"]
    data = [[name] + [r["choices"][s] for s in assembler.SLOTS]
            + [f"{r['buyer_stage']:.2f}", str(r["latency_ms"]), f"${r['cost']:.5f}",
               "cached" if r["cached"] else ("FALLBACK" if r["error"] else "")]
            for name, r in rows]
    w = [max(len(c), *(len(d[i]) for d in data)) for i, c in enumerate(cols)]
    print(" | ".join(c.ljust(w[i]) for i, c in enumerate(cols)))
    print("-+-".join("-" * x for x in w))
    for d in data:
        print(" | ".join(v.ljust(w[i]) for i, v in enumerate(d)))
    print(f"total cost ${sum(r['cost'] for _, r in rows):.5f}")


def _safe_out(path: Path) -> Path:
    p = path.resolve()
    if not p.is_relative_to(_ROOT.resolve()):
        raise ValueError(f"output path outside workspace: {p}")
    return p


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--brand-json")
    ap.add_argument("--no-cache", action="store_true")
    ap.add_argument("--debug", action="store_true", help="include debug ribbon in HTML")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("render")
    r.add_argument("--persona", required=True)
    r.add_argument("--out")
    ra = sub.add_parser("render-all")
    ra.add_argument("--out-dir", default=".tmp/jev_pages")
    a = ap.parse_args(argv)

    brand = (json.loads(Path(a.brand_json).read_text(encoding="utf-8"))
             if a.brand_json else assembler.DEFAULT_BRAND)
    personas = assembler.load_personas()
    library = assembler.load_library()
    cache = None if a.no_cache else assembler.DEFAULT_CACHE_FILE

    if a.cmd == "render":
        if a.persona not in personas:
            print("unknown persona; one of: " + ", ".join(personas), file=sys.stderr)
            return 2
        out = _safe_out(Path(a.out or f".tmp/page_{a.persona}.html"))
        res = assembler.assemble(personas[a.persona], brand, library, debug=a.debug, cache_file=cache)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(res["html"], encoding="utf-8")
        print_table([(a.persona, res)])
        print(f"wrote {out}")
        return 0

    out_dir = _safe_out(Path(a.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)
    names = list(personas)
    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(lambda n: assembler.assemble(
            personas[n], brand, library, debug=a.debug, cache_file=cache), names))
    summary = {}
    for n, res in zip(names, results):
        (out_dir / f"page_{n}.html").write_text(res["html"], encoding="utf-8")
        summary[n] = {k: v for k, v in res.items() if k != "html"}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print_table(list(zip(names, results)))
    print(f"wrote {len(names)} pages to {out_dir}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
