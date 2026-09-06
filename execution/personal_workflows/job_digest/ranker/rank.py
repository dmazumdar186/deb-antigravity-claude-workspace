"""
description: Ranking dispatcher for job_digest — runs the three optional rungs in
    order and merges their results.
inputs: list[NormalizedJob] (post-filter), profile_schema.Profile, optional
    gemini_key/anthropic_key, top_n for the Anthropic shortlist.
outputs: tuple[list[RankedJob], dict[str, str]] — the ranked jobs (1:1 with the
    input jobs' order) plus a `rungs` dict recording what each rung actually did:
    {"heuristic": "ran", "gemini": "ran"|"skipped:<reason>"|"failed:<reason>",
    "anthropic": same shape}. Callers (run.py) surface `rungs` in stats so a
    silently-skipped/failed LLM rung is visible instead of looking identical to
    a successful heuristic-only run.

Rungs:
    1. heuristic (ranker/heuristic.py) — always runs, deterministic, no API key.
    2. Gemini (ranker/gemini.py) — optional; when it returns a full result
       (never None), it OVERRIDES every job's RankedJob from rung 1.
    3. Anthropic (ranker/anthropic.py) — optional; reranks only the current
       top-N (by rung 1/2 score) and overrides just those entries.
Each rung either fully succeeds (a complete list/aligned result) or returns
None, in which case its output is discarded entirely and the prior rung's
scores stand — never a partial mix within one rung.
"""

from __future__ import annotations

import logging

from ..contracts import NormalizedJob, RankedJob
from ..profile_schema import Profile
from .anthropic import rerank_anthropic
from .gemini import score_gemini
from .heuristic import score_heuristic

logger = logging.getLogger("job_digest.ranker.rank")

_TIER_PRIORITY = {"A": 0, "B": 1, "C": 2, "SKIP": 3}


def rank(
    jobs: list[NormalizedJob],
    profile: Profile,
    *,
    gemini_key: str | None = None,
    anthropic_key: str | None = None,
    top_n: int = 25,
) -> tuple[list[RankedJob], dict[str, str]]:
    """Run the ranking pipeline and return (list[RankedJob] aligned to `jobs`, rungs)."""
    rungs: dict[str, str] = {}
    if not jobs:
        logger.info("rank: no jobs to rank")
        rungs = {
            "heuristic": "skipped:no_jobs",
            "gemini": "skipped:no_jobs",
            "anthropic": "skipped:no_jobs",
        }
        return [], rungs

    ranked = score_heuristic(jobs, profile)
    ranked_by_hash: dict[str, RankedJob] = {rj.content_hash: rj for rj in ranked}
    rungs["heuristic"] = "ran"

    if gemini_key:
        try:
            gemini_result = score_gemini(jobs, profile, gemini_key)
        except Exception as exc:  # noqa: BLE001 — rung failure must not crash ranking
            logger.warning("rank: gemini rung raised (%s: %s) — keeping heuristic scores", type(exc).__name__, exc)
            gemini_result = None
            rungs["gemini"] = f"failed:{type(exc).__name__}"
        else:
            if gemini_result is not None and len(gemini_result) == len(jobs):
                ranked_by_hash = {rj.content_hash: rj for rj in gemini_result}
                rungs["gemini"] = "ran"
            else:
                logger.info("rank: gemini rung skipped or failed — keeping heuristic scores")
                rungs["gemini"] = "failed:no_result"
    else:
        rungs["gemini"] = "skipped:no_key"

    if anthropic_key:
        pool = [(job, ranked_by_hash[job.content_hash]) for job in jobs if job.content_hash in ranked_by_hash]
        pool.sort(key=lambda pair: (_TIER_PRIORITY.get(pair[1].tier.value, 9), -pair[1].score))
        shortlist = pool[:top_n]
        try:
            anthropic_result = rerank_anthropic(shortlist, profile, anthropic_key)
        except Exception as exc:  # noqa: BLE001 — rung failure must not crash ranking
            logger.warning("rank: anthropic rung raised (%s: %s) — keeping prior scores", type(exc).__name__, exc)
            anthropic_result = None
            rungs["anthropic"] = f"failed:{type(exc).__name__}"
        else:
            if anthropic_result is not None and len(anthropic_result) == len(shortlist):
                for rj in anthropic_result:
                    ranked_by_hash[rj.content_hash] = rj
                rungs["anthropic"] = "ran"
            else:
                logger.info("rank: anthropic rung skipped or failed — keeping prior scores")
                rungs["anthropic"] = "failed:no_result"
    else:
        rungs["anthropic"] = "skipped:no_key"

    logger.info("rank: rungs = %s", rungs)
    ranked_out = [ranked_by_hash[job.content_hash] for job in jobs if job.content_hash in ranked_by_hash]
    return ranked_out, rungs
