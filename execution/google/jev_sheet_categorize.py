"""
jev_sheet_categorize.py
description: Fill a category column in a CSV or Google Sheet tab using Jev (TypeSafe typed
             decisions via OpenRouter). One `choice` question per row; Jev can only pick from
             the operator's option list, so it never invents a category. Low-confidence rows
             get "?" for human review. "Use case 1 - Jev in Google Sheets".
inputs:  --csv PATH (local CSV, no Google creds needed) OR --sheet-id ID --tab NAME (gspread,
         GOOGLE_SERVICE_ACCOUNT_PATH); --column NAME; --options "A,B,C" or "A=desc,B=desc";
         optional --question, --source-cols, --min-confidence, --limit, --dry-run, --workers,
         --overwrite, --output. Env: OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / _TOEKN).
outputs: CSV mode writes <input>.jev.csv (or --output) with the column filled; sheet mode
         writes the column in place. Prints a summary (rows, filled, needs-review, cost USD,
         wall time, per-option counts) and appends one row to .tmp/jev_ledger.jsonl.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv; load_dotenv()  # noqa: E702

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.modules import jev_client  # noqa: E402

REVIEW_MARK = "?"
QUESTION_NAME = "category"


# ---------------------------------------------------------------------------
# Option parsing
# ---------------------------------------------------------------------------

def parse_options(raw: str) -> dict[str, str]:
    """'A,B,C' or 'A=desc,B=desc' -> {key: description}. Keys keep their original case."""
    options: dict[str, str] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part:
            continue
        if "=" in part:
            key, desc = part.split("=", 1)
            key, desc = key.strip(), desc.strip()
        else:
            key, desc = part, ""
        if not key:
            continue
        options[key] = desc or f"the row belongs to '{key}'"
    if len(options) < 2:
        raise ValueError("--options needs at least two comma-separated options")
    return options


def default_question(column: str, options: dict[str, str]) -> str:
    return (
        f"Pick the single best '{column}' for this row from the listed options. "
        f"Options: {', '.join(options)}. Use the description when unsure."
    )


# ---------------------------------------------------------------------------
# Core: rows -> decisions
# ---------------------------------------------------------------------------

def build_state(row: dict[str, Any], source_cols: list[str]) -> dict[str, Any]:
    return {c: ("" if row.get(c) is None else str(row.get(c))) for c in source_cols}


def categorize_rows(
    rows: list[dict[str, Any]],
    *,
    column: str,
    options: dict[str, str],
    question: str,
    source_cols: list[str],
    min_confidence: float,
    overwrite: bool,
    limit: int | None,
    workers: int,
) -> dict[str, Any]:
    """Decide the category for every eligible row IN PLACE. Returns stats.

    Eligible = blank target cell (or every row when overwrite). Never writes a value that is
    not a key of `options`; anything else (error, unknown choice, low confidence) -> "?".
    """
    questions = {QUESTION_NAME: jev_client.choice(question, options)}
    lookup = {k.lower(): k for k in options}  # Jev may echo a different case

    todo: list[int] = []
    for i, row in enumerate(rows):
        if limit is not None and len(todo) >= limit:
            break
        if overwrite or not str(row.get(column) or "").strip():
            todo.append(i)

    states = [build_state(rows[i], source_cols) for i in todo]
    t0 = time.perf_counter()
    results = jev_client.decide_many(states, questions, workers=workers) if states else []
    wall_s = time.perf_counter() - t0

    lock = threading.Lock()  # stats mutated only here (single thread) but keep the contract
    stats: dict[str, Any] = {
        "rows": len(rows), "eligible": len(todo), "filled": 0, "needs_review": 0,
        "errors": 0, "cost_usd": 0.0, "input_tokens": 0, "wall_s": round(wall_s, 3),
        "per_option": Counter(), "decisions": [],
    }
    for i, res in zip(todo, results):
        raw_choice = res.choice(QUESTION_NAME)
        conf = res.confidence(QUESTION_NAME)
        key = lookup.get(raw_choice.strip().lower())
        with lock:
            stats["cost_usd"] += res.cost_usd
            stats["input_tokens"] += res.input_tokens
            if res.error:
                stats["errors"] += 1
            if key is not None and conf >= min_confidence and not res.error:
                rows[i][column] = key
                stats["filled"] += 1
                stats["per_option"][key] += 1
            else:
                rows[i][column] = REVIEW_MARK
                stats["needs_review"] += 1
            stats["decisions"].append({
                "index": i, "choice": raw_choice, "confidence": round(conf, 3),
                "written": rows[i][column], "error": res.error,
            })
    return stats


# ---------------------------------------------------------------------------
# CSV mode
# ---------------------------------------------------------------------------

def read_csv(path: Path) -> tuple[list[str], list[dict[str, Any]]]:
    with path.open("r", encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        headers = list(reader.fieldnames or [])
        rows = [dict(r) for r in reader]
    return headers, rows


def write_csv(path: Path, headers: list[str], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers, extrasaction="ignore")
        writer.writeheader()
        for r in rows:
            writer.writerow({h: r.get(h, "") for h in headers})


# ---------------------------------------------------------------------------
# Google Sheets mode (gspread imported lazily so CSV mode needs no creds)
# ---------------------------------------------------------------------------

def read_sheet(sheet_id: str, tab: str) -> tuple[Any, list[str], list[dict[str, Any]]]:
    from execution.google.google_sheets_writer import open_workbook

    ws = open_workbook(sheet_id).worksheet(tab)
    values = ws.get_all_values()
    if not values:
        return ws, [], []
    headers = [h.strip() for h in values[0]]
    rows = [{h: (r[j] if j < len(r) else "") for j, h in enumerate(headers)} for r in values[1:]]
    return ws, headers, rows


def write_sheet_column(ws: Any, headers: list[str], column: str, rows: list[dict[str, Any]]) -> None:
    import gspread.utils as gu

    if column not in headers:
        headers.append(column)
        ws.update_cell(1, len(headers), column)
    col_idx = headers.index(column) + 1
    col_letter = gu.rowcol_to_a1(1, col_idx).rstrip("1")
    cells = [[str(r.get(column, "") or "")] for r in rows]
    if cells:
        ws.update(f"{col_letter}2:{col_letter}{len(rows) + 1}", cells, value_input_option="RAW")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _print_summary(stats: dict[str, Any], column: str, dry_run: bool) -> None:
    print(f"rows={stats['rows']} eligible={stats['eligible']} filled={stats['filled']} "
          f"needs_review={stats['needs_review']} errors={stats['errors']}")
    print(f"cost_usd={stats['cost_usd']:.6f} input_tokens={stats['input_tokens']} "
          f"wall_s={stats['wall_s']}")
    per = ", ".join(f"{k}={v}" for k, v in sorted(stats["per_option"].items())) or "-"
    print(f"per_option[{column}]: {per}")
    if dry_run:
        print("dry-run: nothing written")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Fill a category column with Jev (typed choice).")
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--csv", help="local CSV path")
    src.add_argument("--sheet-id", help="Google Sheet ID (needs --tab)")
    ap.add_argument("--tab", help="worksheet name for --sheet-id")
    ap.add_argument("--column", default="category", help="target column (created if missing)")
    ap.add_argument("--options", required=True, help='"A,B,C" or "A=desc,B=desc"')
    ap.add_argument("--question", default=None, help="instructions for Jev")
    ap.add_argument("--source-cols", default=None, help="comma list of columns fed to Jev (default all)")
    ap.add_argument("--min-confidence", type=float, default=0.55)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--overwrite", action="store_true", help="re-decide non-blank cells too")
    ap.add_argument("--output", default=None, help="CSV mode output (default <input>.jev.csv)")
    ap.add_argument("--json", action="store_true", help="also print per-row decisions as JSON")
    args = ap.parse_args(argv)

    if args.sheet_id and not args.tab:
        ap.error("--sheet-id requires --tab")
    if not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    try:
        options = parse_options(args.options)
    except ValueError as exc:
        ap.error(str(exc))

    ws = None
    if args.csv:
        in_path = Path(args.csv)
        headers, rows = read_csv(in_path)
    else:
        ws, headers, rows = read_sheet(args.sheet_id, args.tab)
    if args.column not in headers:
        headers.append(args.column)

    if args.source_cols:
        source_cols = [c.strip() for c in args.source_cols.split(",") if c.strip()]
        missing = [c for c in source_cols if c not in headers]
        if missing:
            ap.error(f"--source-cols not in header: {missing}")
    else:
        source_cols = [h for h in headers if h != args.column]

    question = args.question or default_question(args.column, options)
    stats = categorize_rows(
        rows, column=args.column, options=options, question=question,
        source_cols=source_cols, min_confidence=args.min_confidence,
        overwrite=args.overwrite, limit=args.limit, workers=args.workers,
    )

    if not args.dry_run:
        if args.csv:
            out = Path(args.output) if args.output else Path(args.csv).with_suffix(".jev.csv")
            write_csv(out, headers, rows)
            print(f"wrote {out}")
        else:
            write_sheet_column(ws, headers, args.column, rows)
            print(f"wrote column '{args.column}' to sheet {args.sheet_id} / {args.tab}")

    _print_summary(stats, args.column, args.dry_run)
    if args.json or args.dry_run:
        for d in stats["decisions"]:
            print(json.dumps(d, ensure_ascii=True))

    jev_client.append_ledger({
        "caller": "jev_sheet_categorize", "rows": stats["eligible"], "filled": stats["filled"],
        "needs_review": stats["needs_review"], "errors": stats["errors"],
        "cost_usd": round(stats["cost_usd"], 8), "input_tokens": stats["input_tokens"],
        "wall_s": stats["wall_s"], "dry_run": args.dry_run,
    })
    return 0


if __name__ == "__main__":
    sys.exit(main())
