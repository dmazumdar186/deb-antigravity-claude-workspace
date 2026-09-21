"""
verify_counts.py
description: Print a per-suburb business count table from the store, optionally compared against a manual
  Google Maps spot-check, flagging any suburb where the pipeline found < 60% of the manual count.
inputs: --metro (required), --store {local,supabase}, --store-root PATH, --manual-counts PATH
  (default: fixtures/manual_counts_{metro}.json if present).
outputs: A printed table to stdout; one JSON stat line: {"script","metro","suburbs","flagged"}.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

# execution/personal_workflows/prodcraft_medspa/discovery/verify_counts.py -> repo root is 4 parents up.
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.common import config  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402

FLAG_THRESHOLD = 0.60


def pipeline_counts_by_suburb(store, metro: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for b in store.find_businesses(metro=metro):
        suburb = b.get("suburb") or "(unknown)"
        counts[suburb] = counts.get(suburb, 0) + 1
    return counts


def load_manual_counts(path: Path) -> dict[str, int]:
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("suburbs", data) if isinstance(data, dict) else {}


def build_table(pipeline: dict[str, int], manual: dict[str, int]) -> tuple[list[tuple[str, int, int | None, bool]], int]:
    """Rows: (suburb, pipeline_count, manual_count_or_None, flagged). Returns (rows, flagged_count)."""
    all_suburbs = sorted(set(pipeline) | set(manual))
    rows = []
    flagged = 0
    for suburb in all_suburbs:
        p_count = pipeline.get(suburb, 0)
        m_count = manual.get(suburb)
        is_flagged = m_count is not None and m_count > 0 and p_count < FLAG_THRESHOLD * m_count
        if is_flagged:
            flagged += 1
        rows.append((suburb, p_count, m_count, is_flagged))
    return rows, flagged


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Per-suburb discovery count check against a manual sample.")
    parser.add_argument("--metro", required=True)
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--manual-counts", default=None, help="Path to a manual_counts_{metro}.json file")
    return parser


def main(argv: list[str] | None = None) -> None:
    settings = config.bootstrap()
    args = build_arg_parser().parse_args(argv)

    store = get_store(kind=args.store or settings.store_kind, root=args.store_root)

    manual_path = (
        Path(args.manual_counts)
        if args.manual_counts
        else Path(__file__).resolve().parent / "fixtures" / f"manual_counts_{args.metro}.json"
    )
    manual = load_manual_counts(manual_path)
    pipeline = pipeline_counts_by_suburb(store, args.metro)

    rows, flagged = build_table(pipeline, manual)

    print(f"Suburb counts for metro={args.metro} (manual source: {manual_path if manual else 'none provided'})")
    print(f"{'suburb':<22} {'pipeline':>10} {'manual':>10} {'flag':>6}")
    for suburb, p_count, m_count, is_flagged in rows:
        manual_str = str(m_count) if m_count is not None else "-"
        flag_str = "LOW" if is_flagged else ""
        print(f"{suburb:<22} {p_count:>10} {manual_str:>10} {flag_str:>6}")

    if flagged:
        print(f"\n{flagged} suburb(s) found < {int(FLAG_THRESHOLD * 100)}% of the manual count.")

    print(json.dumps({"script": "verify_counts", "metro": args.metro, "suburbs": len(rows), "flagged": flagged}))


if __name__ == "__main__":
    main()
