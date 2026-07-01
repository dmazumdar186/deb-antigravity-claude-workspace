"""
description: Second-pass shortlist re-ranker using Claude Sonnet 4.6 via the
    Anthropic API. Takes the top N jobs after the Gemini/heuristic pass and
    re-scores them in a single batched tool-use call for sharper reasoning on
    the entries that end up in the Top Matches dashboard / email digest.
inputs:
    - list[NormalizedJob] (after Gemini/heuristic ranker, after dedup+location filter)
    - dict[str, RankedJob] (output of ranker.score.rank_jobs)
    - env: ANTHROPIC_API_KEY (no key -> silent no-op, returns input unchanged)
outputs:
    - dict[str, RankedJob] (same shape; entries for the top-N are replaced with
      Sonnet-refined scores; entries outside the top-N pass through unchanged)
    - stats dict: {requested, refined, failed, by_tier_after, cost_eur_estimate}

Cost: one tool-use call per pipeline run. At ~25 jobs x ~600 input tokens each
= ~15K input + ~5K output. Sonnet 4.6 pricing $3/M input + $15/M output =
~$0.12 per run. 2 runs/day x 30 days = ~$7/month. Skipped silently if the
ANTHROPIC_API_KEY env var is empty (so the pipeline is safe to ship before the
$20 console top-up clears).
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    JobTier,
    NormalizedJob,
    RankedJob,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("ranker.sonnet_rerank")

DEFAULT_MODEL = "claude-sonnet-4-6"
RUBRIC_VERSION = "sonnet-rerank-v1-2026-06-23"

# Sonnet 4.6 pricing — Anthropic publishes in USD per million tokens. We store
# the USD rate card as the source-of-truth and convert to EUR for operator
# display per ~/.claude/rules/currency-eur.md (Paris-based operator). Cache
# pricing not used here — re-rank is one-shot per run, no cache hit.
PRICE_INPUT_PER_M_USD = 3.0
PRICE_OUTPUT_PER_M_USD = 15.0
# 2026-06-27 reference rate. Refresh when EUR/USD moves >5%.
USD_TO_EUR = 0.92


def _tier_from_score(score: float) -> JobTier:
    if score >= 0.8:
        return JobTier.A
    if score >= 0.5:
        return JobTier.B
    if score >= 0.2:
        return JobTier.C
    return JobTier.SKIP


RUBRIC = """You are a senior product-management recruiter helping a candidate
prioritize which jobs to apply to today. The candidate is a 15-year experienced
AI Product Manager based in Paris, bilingual French + English, comfortable with
Germany / Belgium / Switzerland / EU-remote roles. Strong preference for:

- AI / ML / GenAI product roles
- Senior, Lead, Principal, Head-of titles (not junior/IC)
- CDI (permanent) or Freelance contracts; not internships
- Roles posted in the last 48h
- Companies that ship product (not pure-consulting body-shops)

Score each job 0.0-1.0 and assign a tier:
- A (>=0.8): apply today; strong title + location + employer fit
- B (>=0.5): worth reviewing; partial fit
- C (>=0.2): weak fit; skim only
- SKIP (<0.2): not appropriate (wrong seniority, wrong geography, internship, etc.)

Reasoning must be ONE concrete sentence naming the strongest signal — "Senior AI
PM at a profitable scale-up in Paris" — not generic praise. Don't repeat the job
title back; add new information.

You will receive the top-N candidates from a faster first-pass ranker. Re-evaluate
each independently; you can disagree with the first pass."""


def _build_payload(jobs_and_first_pass: list[tuple[NormalizedJob, RankedJob]]) -> str:
    items = []
    for job, first in jobs_and_first_pass:
        items.append({
            "job_id": job.content_hash[:16],
            "title": job.title,
            "company": job.company,
            "location": job.location,
            "source": job.source.value,
            "contract_type": job.contract_type.value,
            "remote_mode": job.remote_mode.value,
            "posted_at": job.posted_at.isoformat() if job.posted_at else "unknown",
            "description_snippet": job.description_snippet[:600],
            "first_pass_tier": first.tier.value,
            "first_pass_score": first.score,
            "first_pass_reasoning": first.reasoning[:200],
        })
    return json.dumps({"candidates": items}, ensure_ascii=False)


def rerank_shortlist(
    jobs: list[NormalizedJob],
    ranked_by_hash: dict[str, RankedJob],
    *,
    top_n: int = 25,
    model: str = DEFAULT_MODEL,
    enabled: bool = True,
) -> tuple[dict[str, RankedJob], dict]:
    """Refine the top-N jobs from the first-pass ranker using Sonnet.

    Behavior:
      - If ANTHROPIC_API_KEY is unset OR enabled=False OR no jobs -> silent no-op,
        return (ranked_by_hash, stats with reason).
      - Pick the top-N from the input by first-pass score (tier A>B>C ties broken by score).
      - One batched tool-use call to Sonnet returning {job_id, tier, score, reasoning}
        for each entry.
      - Merge: replace RankedJob entries for the top-N with Sonnet's output.
        Entries outside the top-N pass through unchanged.
      - Failure modes (SDK missing / API error / bad output) -> log + return input.

    Returns (updated_ranked_by_hash, stats).
    """
    stats: dict = {
        "requested": 0,
        "refined": 0,
        "failed": 0,
        "by_tier_after": {"A": 0, "B": 0, "C": 0, "SKIP": 0},
        "cost_eur_estimate": 0.0,
        "skipped_reason": "",
        "model": model,
    }

    if not enabled:
        stats["skipped_reason"] = "sonnet rerank disabled (flag or config)"
        return ranked_by_hash, stats
    if not jobs:
        stats["skipped_reason"] = "no jobs to rerank"
        return ranked_by_hash, stats

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        # The whole point of the gating: ship the code now, top up the Anthropic
        # console later, and the rerank kicks in automatically the moment the key
        # appears in .env / secrets. Until then this is a silent no-op.
        stats["skipped_reason"] = "ANTHROPIC_API_KEY not in environment — rerank skipped (top up at console.anthropic.com)"
        logger.info("sonnet_rerank: %s", stats["skipped_reason"])
        return ranked_by_hash, stats

    try:
        from anthropic import Anthropic  # type: ignore
    except ImportError:
        stats["skipped_reason"] = "anthropic SDK not installed (pip install anthropic) — rerank skipped"
        logger.warning("sonnet_rerank: %s", stats["skipped_reason"])
        return ranked_by_hash, stats

    # Select the top-N from the first pass.
    tier_priority = {"A": 0, "B": 1, "C": 2, "SKIP": 3}
    pool = []
    for job in jobs:
        rj = ranked_by_hash.get(job.content_hash)
        if rj is None:
            continue
        pool.append((job, rj))
    pool.sort(key=lambda jr: (tier_priority.get(jr[1].tier.value, 9), -jr[1].score))
    shortlist = pool[:top_n]
    if not shortlist:
        stats["skipped_reason"] = "first-pass ranker produced no ranked jobs"
        return ranked_by_hash, stats

    stats["requested"] = len(shortlist)
    payload = _build_payload(shortlist)

    submit_tool = {
        "name": "submit_rankings",
        "description": "Submit the re-ranked tier, score, and reasoning for each job in the shortlist.",
        "input_schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "job_id": {"type": "string", "description": "Echo the input job_id exactly."},
                            "tier": {"type": "string", "enum": ["A", "B", "C", "SKIP"]},
                            "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                            "reasoning": {"type": "string", "maxLength": 280},
                        },
                        "required": ["job_id", "tier", "score", "reasoning"],
                    },
                }
            },
            "required": ["results"],
        },
    }

    client = Anthropic(api_key=api_key)
    try:
        resp = client.messages.create(
            model=model,
            max_tokens=8000,
            system=RUBRIC,
            tools=[submit_tool],
            tool_choice={"type": "tool", "name": "submit_rankings"},
            messages=[{"role": "user", "content": payload}],
        )
    except Exception as exc:  # noqa: BLE001 — Anthropic surface; treat as soft failure.
        stats["skipped_reason"] = f"anthropic API call failed: {type(exc).__name__}: {exc}"
        stats["failed"] = stats["requested"]
        logger.warning("sonnet_rerank: %s", stats["skipped_reason"])
        return ranked_by_hash, stats

    # Extract tool_use block.
    tool_input = None
    for block in resp.content or []:
        if getattr(block, "type", None) == "tool_use" and getattr(block, "name", "") == "submit_rankings":
            tool_input = block.input
            break

    if not tool_input:
        stats["skipped_reason"] = "no tool_use block in Sonnet response"
        stats["failed"] = stats["requested"]
        logger.warning("sonnet_rerank: %s", stats["skipped_reason"])
        return ranked_by_hash, stats

    results = tool_input.get("results", []) if isinstance(tool_input, dict) else []
    id_to_pair = {job.content_hash[:16]: (job, rj) for job, rj in shortlist}

    out = dict(ranked_by_hash)  # shallow copy so caller's ref is untouched

    for r in results:
        jid = str(r.get("job_id", "")).strip()
        if jid not in id_to_pair:
            continue
        job, _first = id_to_pair[jid]
        try:
            score = max(0.0, min(1.0, float(r.get("score", 0.5))))
            tier_str = str(r.get("tier", "B")).upper()
            tier = JobTier(tier_str) if tier_str in {"A", "B", "C", "SKIP"} else _tier_from_score(score)
            reasoning = str(r.get("reasoning", ""))[:600]
            out[job.content_hash] = RankedJob(
                content_hash=job.content_hash,
                score=score,
                tier=tier,
                reasoning=reasoning,
                rubric_version=RUBRIC_VERSION,
                ranker_model=model,
            )
            stats["refined"] += 1
            stats["by_tier_after"][tier.value] += 1
        except (ValueError, KeyError) as exc:
            stats["failed"] += 1
            logger.warning("sonnet_rerank: result for %s malformed (%s)", jid, exc)

    # Cost estimate (read directly from the response's usage block). Stored as
    # cost_eur_estimate per ~/.claude/rules/currency-eur.md — operator reads
    # numbers in EUR; Anthropic bills in USD so we convert at emit time.
    try:
        usage = resp.usage
        in_tok = getattr(usage, "input_tokens", 0) or 0
        out_tok = getattr(usage, "output_tokens", 0) or 0
        cost_usd = (in_tok * PRICE_INPUT_PER_M_USD
                    + out_tok * PRICE_OUTPUT_PER_M_USD) / 1_000_000.0
        stats["cost_eur_estimate"] = round(cost_usd * USD_TO_EUR, 4)
        stats["input_tokens"] = in_tok
        stats["output_tokens"] = out_tok
    except Exception as exc:  # noqa: BLE001 — usage block shape may vary; cost is informational.
        logger.info("sonnet_rerank: could not read usage block: %s", exc)

    logger.info("sonnet_rerank: %s", stats)
    return out, stats
