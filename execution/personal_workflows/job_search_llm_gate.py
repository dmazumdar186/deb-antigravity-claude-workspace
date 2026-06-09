"""
description: LLM relevance gate for the job-search-sheet pipeline. Classifies each candidate job as relevant/borderline/irrelevant and extracts contract_type when the scraper did not provide it. Primary: Claude Haiku 4.5 via Anthropic API. Failover: Gemini 2.0 Flash. Hard cap: 200 jobs per run.
inputs:  Candidate jobs (list[dict] in RawJob+ schema). Env vars ANTHROPIC_API_KEY, GEMINI_API_KEY.
outputs: For each input job: {"relevance": "relevant"|"borderline"|"irrelevant", "contract_type": str|None, "reason": str}.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import setup_logging  # noqa: E402

logger = setup_logging("job_search_llm_gate")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_VALID_RELEVANCES = {"relevant", "borderline", "irrelevant"}
_VALID_CONTRACT_TYPES = {"CDI", "CDD", "Freelance", "Contract", "Permanent", "Unknown"}

_SYSTEM_PROMPT_TEMPLATE = """\
You are a job-relevance classifier for a single user (a {profile}).
Given a job's title, company, location, and description snippet, output JSON:
{{"relevance": "relevant" | "borderline" | "irrelevant", "contract_type": "<one of CDI/CDD/Freelance/Contract/Permanent/Unknown>", "reason": "<10 words max>"}}

Rules:
- "relevant" = clearly matches the user's profile.
- "borderline" = related but ambiguous (e.g. AI Consultant role that could be sales).
- "irrelevant" = obvious mismatch (junior, wrong domain, customer-facing only).
- contract_type: try to infer from the description. If unsure, "Unknown".
Output ONLY the JSON object, no preamble.\
"""

_FALLBACK_VERDICT_PARSE_ERROR: dict = {
    "relevance": "borderline",
    "contract_type": None,
    "reason": "parse_error",
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


@dataclass
class GateVerdict:
    """Classification result for one job."""

    relevance: str  # "relevant" | "borderline" | "irrelevant"
    contract_type: str | None  # "CDI" / "CDD" / "Freelance" / "Contract" / "Permanent" / None
    reason: str  # short explanation, for logging


def classify_batch(
    jobs: list[dict],
    *,
    max_jobs: int = 200,
    primary_model: str = "claude-haiku-4-5",
    failover_model: str = "gemini-2.0-flash",
    target_profile_hint: str = "senior product manager / AI product specialist with 15 years experience",
) -> list[GateVerdict | None]:
    """Classify a batch of jobs for relevance and contract_type.

    Returns same length as input. None means "exceeded max_jobs cap, not classified".
    Order is preserved.

    Failover policy: try Claude per job.  On 429/5xx after 2 retries (via tenacity),
    switch to Gemini for the remainder of the batch (sticky failover — no toggle back).
    Logs the failover event exactly once.
    """
    if not jobs:
        return []

    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(profile=target_profile_hint)

    # Hard cap: first max_jobs are classified; the rest get None
    jobs_to_classify = jobs[:max_jobs]
    tail_count = max(0, len(jobs) - max_jobs)
    if tail_count:
        logger.warning(
            "classify_batch: %d jobs exceed cap %d; last %d will not be classified.",
            len(jobs),
            max_jobs,
            tail_count,
        )

    results: list[GateVerdict | None] = []
    using_failover = False
    failover_logged = False

    # Build API clients lazily
    _claude_client = None
    _gemini_model = None

    for job in jobs_to_classify:
        user_msg = (
            f"Title: {job.get('title', '')}\n"
            f"Company: {job.get('company_name', '')}\n"
            f"Location: {job.get('location', '')}\n"
            f"Snippet: {(job.get('description_snippet') or '')[:400]}"
        )

        verdict_dict: dict | None = None

        # --- Primary: Claude ---
        if not using_failover:
            try:
                if _claude_client is None:
                    _claude_client = _build_claude_client()
                verdict_dict = _call_claude(
                    _claude_client, primary_model, system_prompt, user_msg
                )
            except Exception as exc:  # noqa: BLE001 — broad catch; log + failover
                err_str = str(exc)
                logger.warning(
                    "classify_batch: Claude call failed (%s); switching to Gemini failover.", err_str
                )
                using_failover = True

        # --- Failover: Gemini (sticky) ---
        if using_failover:
            if not failover_logged:
                logger.info(
                    "classify_batch: Gemini failover activated for remainder of batch."
                )
                failover_logged = True
            try:
                if _gemini_model is None:
                    _gemini_model = _build_gemini_model(failover_model)
                verdict_dict = _call_gemini(
                    _gemini_model, system_prompt, user_msg
                )
            except Exception as exc:  # noqa: BLE001 — both providers failed; use fallback
                logger.error(
                    "classify_batch: Gemini also failed (%s); using parse_error fallback.", exc
                )
                verdict_dict = None

        if verdict_dict is None:
            results.append(_make_verdict(_FALLBACK_VERDICT_PARSE_ERROR))
        else:
            results.append(_make_verdict(verdict_dict))

    # Append None for jobs beyond the cap
    results.extend([None] * tail_count)
    return results


# ---------------------------------------------------------------------------
# Claude helpers
# ---------------------------------------------------------------------------


def _build_claude_client():
    """Build and return an Anthropic client.  Raises ValueError if key is absent."""
    import anthropic  # imported lazily so module loads without the SDK installed

    api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY not set in environment.")
    return anthropic.Anthropic(api_key=api_key)


def _call_claude(client, model: str, system_prompt: str, user_msg: str) -> dict:
    """Call Claude synchronously with tenacity retry (2 retries on 429/5xx).

    Returns parsed dict.  Raises on parse failure or exhausted retries.
    """
    from tenacity import (  # imported lazily
        retry,
        retry_if_exception,
        stop_after_attempt,
        wait_exponential,
    )

    def _is_retriable_anthropic(exc: BaseException) -> bool:
        """True for Anthropic RateLimitError and InternalServerError."""
        try:
            import anthropic
            return isinstance(exc, (anthropic.RateLimitError, anthropic.InternalServerError))
        except ImportError:
            return False

    @retry(
        retry=retry_if_exception(_is_retriable_anthropic),
        stop=stop_after_attempt(3),  # initial + 2 retries
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _invoke() -> dict:
        response = client.messages.create(
            model=model,
            max_tokens=128,
            system=system_prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw_text = response.content[0].text.strip()
        return _parse_verdict_json(raw_text)

    return _invoke()


# ---------------------------------------------------------------------------
# Gemini helpers
# ---------------------------------------------------------------------------


def _build_gemini_model(model_name: str):
    """Build and return a Gemini GenerativeModel.  Raises ValueError if key absent."""
    import google.generativeai as genai  # imported lazily

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("GEMINI_API_KEY not set in environment.")
    genai.configure(api_key=api_key)
    return genai.GenerativeModel(model_name)


def _call_gemini(model, system_prompt: str, user_msg: str) -> dict:
    """Call Gemini and return parsed verdict dict."""
    full_prompt = system_prompt + "\n\n" + user_msg
    response = model.generate_content(full_prompt)
    raw_text = response.text.strip()
    return _parse_verdict_json(raw_text)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _parse_verdict_json(raw: str) -> dict:
    """Parse a JSON verdict string.  Falls back to parse_error dict on failure."""
    # Strip markdown code fences if present
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # Remove opening and closing fence lines
        lines = [l for l in lines if not l.startswith("```")]
        text = "\n".join(lines).strip()

    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_parse_verdict_json: failed to parse: %r", raw[:200])
        return dict(_FALLBACK_VERDICT_PARSE_ERROR)

    relevance = (parsed.get("relevance") or "borderline").lower()
    if relevance not in _VALID_RELEVANCES:
        logger.warning("_parse_verdict_json: unknown relevance %r; using 'borderline'", relevance)
        relevance = "borderline"

    raw_ct = parsed.get("contract_type")
    contract_type: str | None = None
    if raw_ct and isinstance(raw_ct, str):
        ct_stripped = raw_ct.strip()
        # Map case-insensitively
        ct_lookup = {v.lower(): v for v in _VALID_CONTRACT_TYPES}
        contract_type = ct_lookup.get(ct_stripped.lower())
        if contract_type == "Unknown":
            contract_type = None  # Normalise "Unknown" → None in the dataclass

    reason = str(parsed.get("reason") or "ok")[:120]

    return {"relevance": relevance, "contract_type": contract_type, "reason": reason}


def _make_verdict(d: dict) -> GateVerdict:
    return GateVerdict(
        relevance=d.get("relevance", "borderline"),
        contract_type=d.get("contract_type"),
        reason=d.get("reason", ""),
    )


# ---------------------------------------------------------------------------
# CLI (standalone test)
# ---------------------------------------------------------------------------


def _main() -> None:
    parser = argparse.ArgumentParser(
        description="LLM relevance gate — standalone test via fixture file."
    )
    parser.add_argument(
        "--input-fixture",
        metavar="PATH",
        required=True,
        help="Path to a JSON file containing a list of RawJob dicts.",
    )
    parser.add_argument(
        "--max-jobs",
        type=int,
        default=200,
        help="Hard cap on jobs classified per run (default: 200).",
    )
    parser.add_argument(
        "--primary-model",
        default="claude-haiku-4-5",
        help="Primary LLM model ID (default: claude-haiku-4-5).",
    )
    parser.add_argument(
        "--failover-model",
        default="gemini-2.0-flash",
        help="Failover LLM model ID (default: gemini-2.0-flash).",
    )
    args = parser.parse_args()

    fixture_path = Path(args.input_fixture)
    if not fixture_path.exists():
        print(f"[ERROR] Fixture file not found: {fixture_path}", file=sys.stderr)
        sys.exit(1)

    with fixture_path.open("r", encoding="utf-8") as fh:
        jobs = json.load(fh)

    if not isinstance(jobs, list):
        print("[ERROR] Fixture must be a JSON array of job dicts.", file=sys.stderr)
        sys.exit(1)

    print(f"Classifying {len(jobs)} jobs (cap: {args.max_jobs}) …")
    verdicts = classify_batch(
        jobs,
        max_jobs=args.max_jobs,
        primary_model=args.primary_model,
        failover_model=args.failover_model,
    )

    for i, (job, verdict) in enumerate(zip(jobs, verdicts)):
        title = job.get("title", "(no title)")
        if verdict is None:
            print(f"  [{i:3d}] {title!r:60s} → SKIPPED (cap)")
        else:
            print(
                f"  [{i:3d}] {title!r:60s} → {verdict.relevance:12s} "
                f"contract={verdict.contract_type}  reason={verdict.reason!r}"
            )


if __name__ == "__main__":
    _main()
