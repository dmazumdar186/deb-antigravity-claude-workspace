"""
llm_spend_report.py
description: Summarise LLM spend from the llm_client cost ledger, grouped by script, model or day.
inputs: --days N (default 7), --by script|model|day (default script), --json, --ledger PATH (default .tmp/llm_ledger.jsonl).
outputs: Plain table (calls, prompt/completion tokens, cost_usd, TOTAL line) on stdout, or JSON with --json.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LEDGER = ROOT / ".tmp" / "llm_ledger.jsonl"
KEYS = {"script": "caller", "model": "model", "day": "ts"}


def load_rows(path: Path, days: int) -> list[dict]:
    if not path.exists():
        return []
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            r = json.loads(line)
            ts = datetime.fromisoformat(r["ts"])
        except (ValueError, KeyError, TypeError):
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if ts >= cutoff:
            rows.append(r)
    return rows


def aggregate(rows: list[dict], by: str) -> list[dict]:
    groups: dict[str, dict] = {}
    for r in rows:
        key = str(r.get(KEYS[by]) or "?")
        if by == "day":
            key = key[:10]
        g = groups.setdefault(key, {by: key, "calls": 0, "prompt_tokens": 0,
                                    "completion_tokens": 0, "cost_usd": 0.0})
        g["calls"] += 1
        g["prompt_tokens"] += int(r.get("prompt_tokens") or 0)
        g["completion_tokens"] += int(r.get("completion_tokens") or 0)
        g["cost_usd"] += float(r.get("cost_usd") or 0.0)
    return sorted(groups.values(), key=lambda g: (g[by] if by == "day" else -g["cost_usd"]))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[2])
    ap.add_argument("--days", type=int, default=7)
    ap.add_argument("--by", choices=list(KEYS), default="script")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--ledger", type=Path, default=DEFAULT_LEDGER)
    a = ap.parse_args(argv)

    groups = aggregate(load_rows(a.ledger, a.days), a.by)
    total = {a.by: "TOTAL", "calls": sum(g["calls"] for g in groups),
             "prompt_tokens": sum(g["prompt_tokens"] for g in groups),
             "completion_tokens": sum(g["completion_tokens"] for g in groups),
             "cost_usd": sum(g["cost_usd"] for g in groups)}
    if a.json:
        print(json.dumps({"days": a.days, "by": a.by, "groups": groups, "total": total}, indent=2))
        return 0
    if not groups:
        print("no ledger rows")
        return 0
    width = max(len(a.by), *(len(str(g[a.by])) for g in groups), 5)
    print(f"{a.by:<{width}}  {'calls':>7}  {'prompt_tok':>11}  {'compl_tok':>10}  {'cost_usd':>10}")
    for g in [*groups, total]:
        print(f"{g[a.by]:<{width}}  {g['calls']:>7}  {g['prompt_tokens']:>11}  "
              f"{g['completion_tokens']:>10}  {g['cost_usd']:>10.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
