#!/usr/bin/env python3
"""Token usage report for Claude Code sessions.

Scans local Claude Code transcript files (~/.claude/projects/**/*.jsonl, or
$CLAUDE_CONFIG_DIR/projects) and reports token consumption by model and day,
with a cache-aware cost estimate and skill/sub-agent invocation counts.

The dollar figure is an API-price *proxy* for subscription (5-hour cap) burn:
the cap's internal weighting is not published, but it tracks model cost, so
the proxy ranks sessions/models correctly even if absolute numbers differ.

Usage:
    python3 execution/infrastructure/token_usage_report.py            # last 7 days
    python3 execution/infrastructure/token_usage_report.py --days 30
    python3 execution/infrastructure/token_usage_report.py --json
"""

import argparse
import json
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Cache-aware pricing: 4 entries per model — input, cache_read (0.1x),
# cache_write (1.25x), output — per $/MTok. Matched by substring on model id.
PRICING = {
    "claude-fable-5":  {"input": 10.0, "cache_read": 1.0,  "cache_write": 12.5,  "output": 50.0},
    "claude-opus-5":   {"input": 5.0,  "cache_read": 0.5,  "cache_write": 6.25,  "output": 25.0},
    "claude-sonnet-5": {"input": 2.0,  "cache_read": 0.2,  "cache_write": 2.5,   "output": 10.0},
    "claude-opus-4":   {"input": 15.0, "cache_read": 1.5,  "cache_write": 18.75, "output": 75.0},
    "claude-haiku-4":  {"input": 1.0,  "cache_read": 0.1,  "cache_write": 1.25,  "output": 5.0},
}
FALLBACK_PRICE = {"input": 5.0, "cache_read": 0.5, "cache_write": 6.25, "output": 25.0}


def price_for(model: str) -> dict:
    for key, table in PRICING.items():
        if key in model:
            return table
    return FALLBACK_PRICE


def transcript_root() -> Path:
    cfg = os.environ.get("CLAUDE_CONFIG_DIR", "")
    root = Path(cfg) if cfg else Path.home() / ".claude"
    return root / "projects"


def iter_lines(root: Path):
    for path in root.rglob("*.jsonl"):
        try:
            with open(path, encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    yield line
        except OSError as exc:
            print(f"warn: cannot read {path}: {exc}", file=sys.stderr)


def main() -> int:
    ap = argparse.ArgumentParser(description="Claude Code token usage report")
    ap.add_argument("--days", type=int, default=7, help="lookback window (default 7)")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a table")
    ap.add_argument("--summary", action="store_true",
                    help="compact digest (a few lines) for hook injection")
    args = ap.parse_args()

    root = transcript_root()
    if not root.is_dir():
        print(f"No transcripts found at {root} — run on the machine where Claude Code runs.")
        return 1

    cutoff = datetime.now(timezone.utc) - timedelta(days=args.days)
    by_model = defaultdict(lambda: defaultdict(int))
    by_day_cost = defaultdict(float)
    skills = defaultdict(int)
    agents = defaultdict(int)

    for line in iter_lines(root):
        try:
            rec = json.loads(line)
        except json.JSONDecodeError:
            continue
        try:
            ts_raw = rec.get("timestamp", "")
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00")) if ts_raw else None
            if ts is None or ts < cutoff:
                continue
            msg = rec.get("message") or {}
            usage = msg.get("usage") or {}
            model = msg.get("model", "")
            if usage and model and model != "<synthetic>":
                m = by_model[model]
                m["input"] += usage.get("input_tokens", 0) or 0
                m["output"] += usage.get("output_tokens", 0) or 0
                m["cache_read"] += usage.get("cache_read_input_tokens", 0) or 0
                m["cache_write"] += usage.get("cache_creation_input_tokens", 0) or 0
                m["calls"] += 1
                p = price_for(model)
                cost = (
                    (usage.get("input_tokens", 0) or 0) * p["input"]
                    + (usage.get("cache_read_input_tokens", 0) or 0) * p["cache_read"]
                    + (usage.get("cache_creation_input_tokens", 0) or 0) * p["cache_write"]
                    + (usage.get("output_tokens", 0) or 0) * p["output"]
                ) / 1_000_000
                by_day_cost[ts.date().isoformat()] += cost
            for block in msg.get("content") or []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name", "")
                binput = block.get("input") or {}
                if name == "Skill" and binput.get("skill"):
                    skills[binput["skill"]] += 1
                elif name in ("Task", "Agent") and binput.get("subagent_type"):
                    agents[binput["subagent_type"]] += 1
        except (KeyError, TypeError, ValueError, AttributeError):
            continue

    totals = {}
    grand = 0.0
    for model, m in by_model.items():
        p = price_for(model)
        cost = (
            m["input"] * p["input"] + m["cache_read"] * p["cache_read"]
            + m["cache_write"] * p["cache_write"] + m["output"] * p["output"]
        ) / 1_000_000
        grand += cost
        totals[model] = {**m, "est_cost_usd": round(cost, 2)}

    if args.summary:
        if not totals:
            print(f"No usage recorded in the last {args.days} days.")
            return 0
        parts = []
        for model, m in sorted(totals.items(), key=lambda kv: -kv[1]["est_cost_usd"]):
            short = model.replace("claude-", "")
            parts.append(f"{short} ${m['est_cost_usd']:.0f} ({m['calls']} calls)")
        print(f"Last {args.days}d burn (API-price proxy): " + " | ".join(parts)
              + f" | total ${grand:.0f}")
        top_sk = sorted(skills.items(), key=lambda kv: -kv[1])[:5]
        top_ag = sorted(agents.items(), key=lambda kv: -kv[1])[:5]
        if top_sk:
            print("Top skills: " + ", ".join(f"{k} x{v}" for k, v in top_sk))
        if top_ag:
            print("Sub-agent spawns: " + ", ".join(f"{k} x{v}" for k, v in top_ag))
        else:
            print("Sub-agent spawns: NONE — if multi-file work happened, delegation is failing.")
        return 0

    if args.json:
        print(json.dumps({
            "window_days": args.days,
            "by_model": totals,
            "by_day_cost_usd": {k: round(v, 2) for k, v in sorted(by_day_cost.items())},
            "skill_invocations": dict(sorted(skills.items(), key=lambda kv: -kv[1])),
            "subagent_spawns": dict(sorted(agents.items(), key=lambda kv: -kv[1])),
            "est_total_cost_usd": round(grand, 2),
        }, indent=2))
        return 0

    print(f"# Token usage — last {args.days} days (API-price proxy for cap burn)\n")
    if not totals:
        print("No usage recorded in window.")
        return 0
    hdr = f"{'model':<28} {'calls':>7} {'input':>12} {'cache_read':>12} {'cache_write':>12} {'output':>10} {'est $':>8}"
    print(hdr)
    print("-" * len(hdr))
    for model, m in sorted(totals.items(), key=lambda kv: -kv[1]["est_cost_usd"]):
        print(f"{model:<28} {m['calls']:>7} {m['input']:>12,} {m['cache_read']:>12,} "
              f"{m['cache_write']:>12,} {m['output']:>10,} {m['est_cost_usd']:>8.2f}")
    print(f"\nEstimated total: ${grand:.2f}")
    if by_day_cost:
        print("\nPer day:")
        for day, cost in sorted(by_day_cost.items()):
            print(f"  {day}  ${cost:.2f}")
    if skills:
        print("\nSkill invocations (informs pruning — zero-use skills are archive candidates):")
        for name, n in sorted(skills.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>4}  {name}")
    if agents:
        print("\nSub-agent spawns (delegation health — should dominate over main-thread grinding):")
        for name, n in sorted(agents.items(), key=lambda kv: -kv[1]):
            print(f"  {n:>4}  {name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
