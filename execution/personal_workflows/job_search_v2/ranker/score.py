"""
description: Gemini 2.5 Flash LLM-judge ranker for NormalizedJobs.
    Reads ranker/rubric.md as the system prompt; for each job returns a RankedJob
    with tier (A/B/C/SKIP), score (0..1) and a 1-sentence reasoning.

    Free tier shape (Gemini 2.5 Flash, 2026): 250 RPD, 10 RPM. The pipeline scores
    ~30 jobs/day, well within budget. Sequential calls with a 1.2s throttle stay
    under the 10 RPM cap with margin.

inputs:
    - list[NormalizedJob] (post-dedup, post-location-filter — already reduced set)
    - env: GEMINI_API_KEY (free tier; sign up at https://aistudio.google.com/apikey)
    - rubric: execution/.../ranker/rubric.md

outputs:
    - list[RankedJob] in 1:1 order with input
    - Returns ([], stats) with a graceful "skipped" reason if SDK missing / no key
      so the orchestrator never crashes on the LLM layer.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    JobTier,
    NormalizedJob,
    RankedJob,
)

load_dotenv()
logger = logging.getLogger("ranker.score")

RUBRIC_PATH = Path(__file__).resolve().parent / "rubric.md"
DEFAULT_MODEL = "gemini-2.5-flash"
RUBRIC_VERSION = "v1-2026-06-15"


def _load_rubric() -> str:
    if not RUBRIC_PATH.exists():
        return "Score each job A/B/C/SKIP based on senior PM fit; output JSON."
    return RUBRIC_PATH.read_text(encoding="utf-8")


def _job_to_prompt_payload(job: NormalizedJob) -> str:
    """Compact, machine-readable representation passed to the LLM."""
    posted = job.posted_at.isoformat() if job.posted_at else "unknown"
    return json.dumps({
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "source": job.source.value,
        "contract_type": job.contract_type.value,
        "remote_mode": job.remote_mode.value,
        "posted_at": posted,
        "description_snippet": job.description_snippet[:600],
        "url": str(job.url),
    }, ensure_ascii=False)


def _tier_from_score(score: float) -> JobTier:
    if score >= 0.8:
        return JobTier.A
    if score >= 0.5:
        return JobTier.B
    if score >= 0.2:
        return JobTier.C
    return JobTier.SKIP


def _placeholder_ranked(job: NormalizedJob, reason: str) -> RankedJob:
    """When ranking is disabled or fails, return a tier-B placeholder so notify still works."""
    return RankedJob(
        content_hash=job.content_hash,
        score=0.5,
        tier=JobTier.B,
        reasoning=reason,
        rubric_version="placeholder",
        ranker_model="none",
    )


def rank_jobs(
    jobs: list[NormalizedJob],
    *,
    model: str = DEFAULT_MODEL,
    throttle_s: float = 1.2,
    enabled: bool = True,
) -> tuple[dict[str, RankedJob], dict]:
    """Score each job. Returns ({content_hash: RankedJob}, stats).

    Stats: {requested, scored, placeholder, skipped, by_tier}.
    Failure modes:
      - GEMINI_API_KEY missing → placeholders for all, stats['skipped'] = len(jobs).
      - google-genai SDK missing → same.
      - Per-job LLM error → that one gets a placeholder, others continue.
    """
    stats = {
        "requested": len(jobs),
        "scored": 0,
        "placeholder": 0,
        "skipped": 0,
        "by_tier": {"A": 0, "B": 0, "C": 0, "SKIP": 0},
    }
    out: dict[str, RankedJob] = {}

    if not jobs:
        return out, stats

    if not enabled:
        for j in jobs:
            out[j.content_hash] = _placeholder_ranked(j, "ranker disabled in config")
            stats["placeholder"] += 1
            stats["by_tier"]["B"] += 1
        return out, stats

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        logger.warning("ranker: GEMINI_API_KEY missing — emitting placeholders. "
                       "Sign up free at https://aistudio.google.com/apikey")
        for j in jobs:
            out[j.content_hash] = _placeholder_ranked(j, "no GEMINI_API_KEY in .env")
            stats["skipped"] += 1
            stats["by_tier"]["B"] += 1
        return out, stats

    try:
        from google import genai  # type: ignore
        from google.genai import types  # type: ignore
    except ImportError:
        logger.warning("ranker: google-genai SDK missing — emitting placeholders. "
                       "Install with: pip install google-genai")
        for j in jobs:
            out[j.content_hash] = _placeholder_ranked(j, "google-genai SDK not installed")
            stats["skipped"] += 1
            stats["by_tier"]["B"] += 1
        return out, stats

    rubric = _load_rubric()
    client = genai.Client(api_key=api_key)

    # BATCH MODE — the Gemini free tier dropped from 250 RPD to 20 RPD on
    # gemini-2.5-flash (observed 2026-06-23). One-call-per-job blew through the
    # quota after ~20 jobs and the rest fell to placeholders. The fix is a single
    # batched call: one prompt scoring every job, one response with a list of
    # rankings. Gemini 2.5 Flash's 1M-context comfortably holds 200+ jobs at ~600
    # tokens each.
    batch_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "tier": {"type": "string", "enum": ["A", "B", "C", "SKIP"]},
                        "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                        "reasoning": {"type": "string", "maxLength": 200},
                    },
                    "required": ["job_id", "tier", "score", "reasoning"],
                },
            }
        },
        "required": ["results"],
    }

    cfg = types.GenerateContentConfig(
        system_instruction=rubric + "\n\nYou will receive a JSON array of jobs. Return one ranking per job, "
                                    "matching the job_id field exactly. Output must be JSON {results: [...]}.",
        response_mime_type="application/json",
        response_schema=batch_schema,
        temperature=0.2,
        max_output_tokens=64000,
    )

    fallback_model = "gemini-2.5-flash-lite"

    # Build a job_id → job map so we can stitch the LLM response back to each job.
    id_to_job: dict[str, NormalizedJob] = {}
    payload_items = []
    for j in jobs:
        short_id = j.content_hash[:16]
        id_to_job[short_id] = j
        payload_items.append({
            "job_id": short_id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "source": j.source.value,
            "contract_type": j.contract_type.value,
            "remote_mode": j.remote_mode.value,
            "posted_at": j.posted_at.isoformat() if j.posted_at else "unknown",
            "description_snippet": j.description_snippet[:400],
        })
    batch_payload = json.dumps({"jobs": payload_items}, ensure_ascii=False)

    def _call_once(model_name: str):
        return client.models.generate_content(model=model_name, contents=batch_payload, config=cfg)

    resp = None
    used_model = model
    last_exc: Exception | None = None
    for attempt in (1, 2, 3):
        try:
            use = model if attempt < 3 else fallback_model
            resp = _call_once(use)
            used_model = use
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001 — Gemini surface; backoff + retry
            last_exc = exc
            msg = str(exc)
            if not any(k in msg for k in ("503", "429", "UNAVAILABLE", "RESOURCE_EXHAUSTED")):
                break
            time.sleep(2.0 * attempt)

    if resp is None or last_exc is not None:
        # Quota exhausted or transient failure — heuristic fallback so the dashboard
        # is never blank. Score by simple title-keyword match against high-signal phrases.
        logger.warning("ranker: batch call failed (%s) — using heuristic fallback", last_exc)
        for j in jobs:
            score = _heuristic_score(j)
            tier = _tier_from_score(score)
            reasoning = f"heuristic (LLM unavailable: {type(last_exc).__name__ if last_exc else 'unknown'})"
            out[j.content_hash] = RankedJob(
                content_hash=j.content_hash,
                score=score,
                tier=tier,
                reasoning=reasoning,
                rubric_version="heuristic-v1",
                ranker_model="heuristic",
            )
            stats["placeholder"] += 1
            stats["by_tier"][tier.value] += 1
        logger.info("ranker: %s", stats)
        return out, stats

    try:
        data = json.loads(resp.text or "{}")
        results = data.get("results", [])
    except (ValueError, json.JSONDecodeError) as exc:
        logger.warning("ranker: batch response parse failed (%s) — heuristic fallback", exc)
        results = []

    scored_ids: set[str] = set()
    for r in results:
        jid = str(r.get("job_id", "")).strip()
        if jid not in id_to_job:
            continue
        job = id_to_job[jid]
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
                ranker_model=used_model,
            )
            stats["scored"] += 1
            stats["by_tier"][tier.value] += 1
            scored_ids.add(jid)
        except (ValueError, KeyError) as exc:
            logger.warning("ranker: result for %s malformed (%s) — heuristic", jid, exc)

    # Any job not in the response → heuristic fallback (don't drop on the floor).
    for j in jobs:
        if j.content_hash[:16] in scored_ids:
            continue
        score = _heuristic_score(j)
        tier = _tier_from_score(score)
        out[j.content_hash] = RankedJob(
            content_hash=j.content_hash,
            score=score,
            tier=tier,
            reasoning="heuristic (LLM omitted this job from response)",
            rubric_version="heuristic-v1",
            ranker_model="heuristic",
        )
        stats["placeholder"] += 1
        stats["by_tier"][tier.value] += 1

    logger.info("ranker: %s", stats)
    return out, stats


# ----- heuristic fallback -----


_HIGH_SIGNAL_TITLE_TERMS = (
    "ai product manager", "genai product manager", "ml product manager",
    "senior product manager", "lead product manager", "principal product manager",
    "head of product", "staff product manager",
    "chef de produit senior", "product lead",
)
_MEDIUM_SIGNAL_TITLE_TERMS = (
    "product manager", "chef de produit", "product owner",
)
_HIGH_SIGNAL_LOCATIONS = ("paris", "île-de-france", "ile-de-france", "remote (france)", "remote (eu)")


def _heuristic_score(job: NormalizedJob) -> float:
    """Deterministic 0..1 score for when the LLM is unavailable.

    Weights (sum to 1.0):
      title  0.6  — high-signal phrase 1.0, medium 0.6, else 0.3
      loc    0.3  — Paris/Île-de-France/EU-remote 1.0, France 0.7, other 0.4
      type   0.1  — CDI 1.0, Freelance 0.7, CDD 0.5, else 0.3
    """
    title = (job.title or "").lower()
    loc = (job.location or "").lower()
    contract = (job.contract_type.value or "").lower()

    if any(t in title for t in _HIGH_SIGNAL_TITLE_TERMS):
        title_s = 1.0
    elif any(t in title for t in _MEDIUM_SIGNAL_TITLE_TERMS):
        title_s = 0.6
    else:
        title_s = 0.3

    if any(t in loc for t in _HIGH_SIGNAL_LOCATIONS):
        loc_s = 1.0
    elif "france" in loc:
        loc_s = 0.7
    else:
        loc_s = 0.4

    type_s = {"cdi": 1.0, "freelance": 0.7, "cdd": 0.5}.get(contract, 0.3)

    return round(0.6 * title_s + 0.3 * loc_s + 0.1 * type_s, 4)


def main() -> int:
    """CLI: read NormalizedJob JSONL from stdin, write RankedJob JSONL to stdout."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Score NormalizedJobs via Gemini 2.5 Flash.")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--throttle-s", type=float, default=1.2)
    parser.add_argument("--disable", action="store_true", help="Bypass ranker (emit placeholders).")
    args = parser.parse_args()

    jobs: list[NormalizedJob] = []
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            jobs.append(NormalizedJob.model_validate_json(line))
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("ranker [cli]: skip line (parse error): %s", exc)

    ranked_map, stats = rank_jobs(jobs, model=args.model, throttle_s=args.throttle_s, enabled=not args.disable)
    for j in jobs:
        rj = ranked_map.get(j.content_hash)
        if rj is None:
            continue
        sys.stdout.write(rj.model_dump_json() + "\n")
    sys.stderr.write(f"ranker: {stats}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
