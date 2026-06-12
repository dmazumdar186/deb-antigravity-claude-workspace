"""Karpathy-style autoresearch loop. Generic skeleton.

Copy this file when starting a new auto-optimization project. Fill in:
- `mutate_fn(baseline, learnings) -> challenger`
- `deploy_fn(baseline, challenger) -> dict[str, str]` (maps "baseline"/"challenger" to deploy IDs)
- `measure_fn(deploy_id) -> float` (fetches the objective metric for one deployed variant)

Then run with `--mode balanced --max-rounds 20 --cost-cap-usd 50`.

Reference: https://github.com/karpathy/autoresearch
Nick Saraev workspace adaptation: .tmp/video/4Cb_l2LJAW8/breakdown.md
Workflow doc: .claude/workflows/autoresearch.md
Directive template: directives/_TEMPLATE_autoresearch.md

Usage:
    py execution/_TEMPLATE_autoresearch.py --mode balanced [--dry-run]
    py execution/_TEMPLATE_autoresearch.py --max-rounds 20 --cost-cap-usd 50
    py execution/_TEMPLATE_autoresearch.py --dry-run   # mock all 3 callables

Inputs:
    - baseline: the starting variant (defined inline in main() or loaded from file)
    - --learnings-log: path to the append-only markdown file (default: .tmp/learnings.md)

Outputs:
    - winning_variant: printed to stdout + returned from run_loop()
    - learnings_log_path: markdown file with one section per round

Env vars used:
    - ANTHROPIC_API_KEY — needed if mutate_fn calls Claude (fill in your project's vars)

Modes:
    cheap     — Haiku 4.5, fast, lower quality mutations.
    balanced  — Sonnet 4.6, standard depth (default).
    premium   — Opus 4.7, deep reasoning, slowest.
"""
from __future__ import annotations

import argparse
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Model routing — same pattern as execution/_TEMPLATE.py
# ---------------------------------------------------------------------------
MODE_TO_MUTATOR_MODEL: dict[str, str] = {
    "cheap": "claude-haiku-4-5",
    "balanced": "claude-sonnet-4-6",
    "premium": "claude-opus-4-7",
}

# Thread lock for _append_to_log — shared across any threads that might call it.
# (Hardening rule 2: threading.Lock on shared mutable filesystem writes.)
_log_lock = threading.Lock()


# ---------------------------------------------------------------------------
# The 3 callables you MUST fill in for your project
# ---------------------------------------------------------------------------

def mutate_fn(baseline: str, learnings: str, model: str) -> tuple[str, str]:
    """Return (challenger_text, hypothesis_one_line).

    Call your LLM here. Feed it:
    - baseline: the current best variant
    - learnings: full text of learnings.md (or "" on first round)
    - model: the model ID selected by --mode

    Example body (fill in):
        import anthropic
        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=model,
            max_tokens=1024,
            messages=[{"role": "user", "content": f"Improve this:\n\n{baseline}\n\nPast learnings:\n{learnings}"}],
        )
        challenger = resp.content[0].text
        hypothesis = "tested more direct CTA"
        return challenger, hypothesis
    """
    raise NotImplementedError("define mutate_fn in your project — see docstring above")


def deploy_fn(baseline: str, challenger: str) -> dict[str, str]:
    """Push baseline + challenger via your target API.

    Return a dict mapping label -> deploy_id, e.g.:
        {"baseline": "campaign_123_A", "challenger": "campaign_123_B"}

    Example (Instantly API, cold email):
        resp = requests.post("https://api.instantly.ai/api/v1/campaign/create", ...)
        return {"baseline": resp_baseline["id"], "challenger": resp_challenger["id"]}
    """
    raise NotImplementedError("define deploy_fn in your project")


def measure_fn(deploy_id: str) -> float:
    """Fetch the objective metric for one deployed variant.

    Called separately for baseline_id and challenger_id. Returns a float
    (higher = better in all cases — invert if your metric is a cost/rate).

    Example (Instantly reply rate after a wait):
        time.sleep(3600)  # wait 1h for data to accumulate — do this outside the loop
        resp = requests.get(f"https://api.instantly.ai/api/v1/campaign/{deploy_id}/stats", ...)
        return resp.json()["reply_rate"]
    """
    raise NotImplementedError("define measure_fn in your project")


# ---------------------------------------------------------------------------
# Core loop
# ---------------------------------------------------------------------------

def run_loop(
    baseline: str,
    mutate_fn,
    deploy_fn,
    measure_fn,
    *,
    max_rounds: int = 10,
    cost_cap_usd: float = 5.0,
    metric_min_improve: float = 0.05,
    learnings_log: Path,
    model: str,
    dry_run: bool = False,
) -> dict:
    """Run the 4-step propose-deploy-measure-mutate loop.

    Returns:
        {
            "winner": str,           # final best variant text
            "rounds_run": int,
            "total_cost_usd": float, # fill in cost tracking in your mutate_fn
            "plateaued": bool,       # True if stopped due to 3 consecutive non-wins
        }
    """
    total_cost_usd = 0.0
    plateau_streak = 0
    round_n = 0

    learnings_text = learnings_log.read_text(encoding="utf-8") if learnings_log.exists() else ""

    for round_n in range(1, max_rounds + 1):
        if total_cost_usd >= cost_cap_usd:
            print(f"[autoresearch] cost cap ${cost_cap_usd:.2f} reached — stopping at round {round_n}.")
            round_n -= 1  # didn't complete this round
            break

        print(f"\n[autoresearch] === Round {round_n}/{max_rounds} ===")

        # Step 1: Mutate
        if dry_run:
            challenger = f"[DRY-RUN challenger round {round_n}]"
            hypothesis = "dry-run hypothesis"
        else:
            challenger, hypothesis = mutate_fn(baseline, learnings_text, model)

        # Step 2: Deploy
        if dry_run:
            deploy_ids = {"baseline": f"dry_baseline_{round_n}", "challenger": f"dry_challenger_{round_n}"}
        else:
            try:
                deploy_ids = deploy_fn(baseline, challenger)
            except Exception as exc:
                # Hardening rule 5: never swallow silently — log + skip round.
                msg = f"DEPLOY_FAILURE round={round_n} error={exc}"
                print(f"[autoresearch] {msg}")
                _append_to_log(
                    learnings_log, round_n,
                    baseline_summary="<see above>", challenger_summary="<deploy failed>",
                    baseline_metric=float("nan"), challenger_metric=float("nan"),
                    winner_label="baseline (deploy failed)", hypothesis=hypothesis, notes=msg,
                )
                learnings_text = learnings_log.read_text(encoding="utf-8")
                continue

        # Step 3: Measure
        if dry_run:
            baseline_metric, challenger_metric = 0.50, 0.55  # mock: challenger wins
        else:
            baseline_metric = measure_fn(deploy_ids["baseline"])
            challenger_metric = measure_fn(deploy_ids["challenger"])

        print(f"[autoresearch] baseline={baseline_metric:.4f}  challenger={challenger_metric:.4f}")

        # Step 4: Pick winner (stability bias: ties go to baseline)
        relative_gain = (
            (challenger_metric - baseline_metric) / max(abs(baseline_metric), 1e-9)
        )
        challenger_wins = relative_gain >= metric_min_improve
        winner_label = "challenger" if challenger_wins else "baseline"
        notes = f"relative_gain={relative_gain:+.2%}"

        if challenger_wins:
            baseline = challenger
            plateau_streak = 0
        else:
            plateau_streak += 1

        _append_to_log(
            learnings_log, round_n,
            baseline_summary=baseline[:120].replace("\n", " "),
            challenger_summary=challenger[:120].replace("\n", " "),
            baseline_metric=baseline_metric,
            challenger_metric=challenger_metric,
            winner_label=winner_label,
            hypothesis=hypothesis,
            notes=notes,
        )
        learnings_text = learnings_log.read_text(encoding="utf-8")

        if plateau_streak >= 3:
            print(f"[autoresearch] plateau — 3 consecutive non-wins. Stopping.")
            break

    return {
        "winner": baseline,
        "rounds_run": round_n,
        "total_cost_usd": total_cost_usd,
        "plateaued": plateau_streak >= 3,
    }


# ---------------------------------------------------------------------------
# Log helper (thread-safe per hardening rule 2)
# ---------------------------------------------------------------------------

def _append_to_log(
    path: Path,
    round_n: int,
    baseline_summary: str,
    challenger_summary: str,
    baseline_metric: float,
    challenger_metric: float,
    winner_label: str,
    hypothesis: str,
    notes: str,
) -> None:
    """Append one round's results to the learnings markdown file.

    Thread-safe: acquires _log_lock before any read/write.
    """
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n## [{ts}] Round {round_n}\n"
        f"Baseline: {baseline_summary}\n"
        f"Challenger: {challenger_summary}\n"
        f"Baseline metric: {baseline_metric}\n"
        f"Challenger metric: {challenger_metric}\n"
        f"Winner: {winner_label}\n"
        f"Hypothesis tested: {hypothesis}\n"
        f"Outcome notes: {notes}\n"
    )
    with _log_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--mode",
        choices=list(MODE_TO_MUTATOR_MODEL.keys()),
        default="balanced",
        help="Mutator tier: cheap (Haiku) / balanced (Sonnet, default) / premium (Opus).",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=10,
        metavar="N",
        help="Maximum propose-deploy-measure cycles (default: 10).",
    )
    parser.add_argument(
        "--cost-cap-usd",
        type=float,
        default=5.0,
        metavar="F",
        help="Hard cost ceiling in USD (default: 5.0). Loop aborts if exceeded.",
    )
    parser.add_argument(
        "--metric-min-improve",
        type=float,
        default=0.05,
        metavar="F",
        help="Minimum relative improvement (0.05 = 5%%) to count as a win (default: 0.05).",
    )
    parser.add_argument(
        "--learnings-log",
        type=Path,
        default=Path(".tmp/learnings.md"),
        metavar="PATH",
        help="Append-only markdown log path (default: .tmp/learnings.md).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Mock all 3 callables. Returns would_* counts, no real API calls.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    model = MODE_TO_MUTATOR_MODEL[args.mode]

    # --- dry-run demo path ---
    if args.dry_run:
        print(f"[autoresearch] DRY-RUN mode={args.mode} model={model}")
        print(f"  max_rounds={args.max_rounds}  cost_cap=${args.cost_cap_usd}  "
              f"min_improve={args.metric_min_improve:.0%}")

        # In dry-run, run_loop mocks all 3 callables internally.
        # Fill in a real baseline string for your project.
        demo_baseline = "Subject: Quick question\n\nHi {{first_name}}, ..."

        result = run_loop(
            demo_baseline,
            mutate_fn=mutate_fn,
            deploy_fn=deploy_fn,
            measure_fn=measure_fn,
            max_rounds=args.max_rounds,
            cost_cap_usd=args.cost_cap_usd,
            metric_min_improve=args.metric_min_improve,
            learnings_log=args.learnings_log,
            model=model,
            dry_run=True,
        )
        print(f"\n[autoresearch] DRY-RUN result:")
        print(f"  would_rounds_run={result['rounds_run']}")
        print(f"  would_total_cost_usd={result['total_cost_usd']:.4f}")
        print(f"  would_plateaued={result['plateaued']}")
        print(f"  learnings_log={args.learnings_log}")
        return 0

    # --- real path: fill in your baseline + callables, then uncomment ---
    # result = run_loop(
    #     baseline=YOUR_BASELINE_HERE,
    #     mutate_fn=mutate_fn,
    #     deploy_fn=deploy_fn,
    #     measure_fn=measure_fn,
    #     max_rounds=args.max_rounds,
    #     cost_cap_usd=args.cost_cap_usd,
    #     metric_min_improve=args.metric_min_improve,
    #     learnings_log=args.learnings_log,
    #     model=model,
    # )
    # print(f"[autoresearch] winner: {result['winner'][:200]}")
    # print(f"  rounds={result['rounds_run']}  cost=${result['total_cost_usd']:.4f}  plateaued={result['plateaued']}")

    print("[autoresearch] skeleton only — fill in mutate_fn / deploy_fn / measure_fn, then uncomment the real path.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
