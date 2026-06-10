"""
description: LLM relevance gate + fit-scorer for the job-search-sheet pipeline. Scores each candidate job (relevance, contract_type, fit_score 0-100, match_identity) in BATCHES (one call per ~10 jobs) to stay within free quota. FREE by default: primary gemini-2.5-flash, secondary gemini-2.5-flash-lite; PAID Anthropic tier only if anthropic_optin=True. Hard cap: 200 jobs per run.
inputs:  Candidate jobs (list[dict] in RawJob+ schema). Env vars GEMINI_API_KEY (required), ANTHROPIC_API_KEY (only if anthropic_optin).
outputs: For each input job: {"relevance": ..., "contract_type": str|None, "fit_score": int, "match_identity": str|None, "reason": str}.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
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
_VALID_MATCH_IDENTITIES = {"salaried", "freelance"}

_SYSTEM_PROMPT_TEMPLATE = """\
You are a job-relevance classifier and fit-scorer for a single candidate.
{profile_section}
Given a job's title, company, location, and description snippet, output ONLY a JSON object with these fields IN THIS ORDER:
{{"relevance": "relevant" | "borderline" | "irrelevant", "contract_type": "<one of CDI/CDD/Freelance/Contract/Permanent/Unknown>", "fit_score": <integer 0-100>, "match_identity": "salaried" | "freelance", "reason": "<12 words max>"}}

Classification rules:
- "relevant" = clearly matches the candidate's profile.
- "borderline" = related but ambiguous (e.g. AI Consultant role that could be sales).
- "irrelevant" = obvious mismatch (junior, wrong domain, customer-facing only).
- contract_type: try to infer from the description. If unsure, "Unknown".

Scoring rules (fit_score 0-100) — SCORE LIKE A STRICT HIRING MANAGER. DISCRIMINATE; DO NOT CLUSTER.
- Score against the BETTER-matching identity (salaried AI/Senior PM vs freelance AI-automation builder);
  set match_identity to whichever scores higher.
- 5 axes: (1) seniority, (2) domain, (3) location, (4) language, (5) contract-fit.
  A weakness on ANY axis must pull the score down — do not average it away.
- Calibration bands (use the FULL range, vary the number job-to-job):
  * 90-100: near-perfect — exact seniority + core domain + location + contract all aligned. Would almost
    certainly get an interview. RARE — reserve for the genuinely exceptional; most days have none.
  * 80-89: strong match, very likely an interview with a tailored application. Still selective.
  * 65-79: relevant but with a REAL gap (seniority off, domain adjacent, or contract mismatch). NOT a top match.
  * 40-64: borderline / tangential.
  * 0-39: irrelevant / wrong field / junior.
- Most genuinely relevant roles land 70-88; only the very best exceed 90. Avoid defaulting to one number
  (e.g. do not give everything 82) — differentiate by how many axes are truly strong.
- reason: <= 12 words naming the deciding factor (e.g. "exact AI PM + Paris + CDI" or "senior but no GenAI").

You will be given a NUMBERED list of jobs. Return ONLY a JSON ARRAY with exactly one verdict object per
job, in the SAME ORDER as the input (element i = job [i+1]). No preamble, no markdown fences, no extra keys.\
"""

_PROFILE_SECTION_TEMPLATE = """\
--- CANDIDATE PROFILE ---
{profile_text}
--- END PROFILE ---\
"""

_FALLBACK_PROFILE_HINT = (
    "senior product manager / AI product specialist with 15 years experience, "
    "based in Paris, open to EU roles; also freelance AI-automation builder"
)

_FALLBACK_VERDICT_PARSE_ERROR: dict = {
    "relevance": "borderline",
    "contract_type": None,
    "fit_score": 0,
    "match_identity": None,
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
    fit_score: int = 0  # 0-100 fit score against the better-matching identity
    match_identity: str | None = None  # "salaried" | "freelance" | None


def classify_batch(
    jobs: list[dict],
    *,
    max_jobs: int = 200,
    primary_model: str = "gemini-2.5-flash",
    secondary_model: str = "gemini-2.5-flash-lite",
    anthropic_optin: bool = False,
    anthropic_model: str = "claude-sonnet-4-6",
    batch_size: int = 10,
    throttle_s: float = 7.0,
    target_profile_hint: str = "senior product manager / AI product specialist with 15 years experience",
    profile_text: str | None = None,
) -> list[GateVerdict | None]:
    """Classify jobs for relevance, contract_type, fit_score, and match_identity.

    FREE-FIRST design: jobs are scored in BATCHES of `batch_size` (ONE LLM call per
    batch, not per job) so a daily run uses ~N/batch_size calls — a handful, well within
    Gemini's free-tier daily quota. No paid call is ever made unless `anthropic_optin=True`.

    Returns same length as input. None means "exceeded max_jobs cap, not classified".
    Order is preserved.

    Sticky tier escalation (logged once; applies to the remainder of the run):
      tier 0 = primary  Gemini (e.g. gemini-2.5-flash)      — FREE
      tier 1 = secondary Gemini (e.g. gemini-2.5-flash-lite) — FREE, separate quota pool
      tier 2 = Anthropic (anthropic_model)                   — PAID. Only used if anthropic_optin=True;
               otherwise a failed batch yields parse_error fallbacks (the gate NEVER auto-charges).
    `throttle_s` spaces out Gemini calls to respect free-tier RPM (set 0 in tests).
    """
    if not jobs:
        return []

    if profile_text:
        profile_section = _PROFILE_SECTION_TEMPLATE.format(profile_text=profile_text)
    else:
        profile_section = f"The candidate is a {target_profile_hint}."
    system_prompt = _SYSTEM_PROMPT_TEMPLATE.format(profile_section=profile_section)

    # Hard cap: first max_jobs are classified; the rest get None
    jobs_to_classify = jobs[:max_jobs]
    tail_count = max(0, len(jobs) - max_jobs)
    if tail_count:
        logger.warning(
            "classify_batch: %d jobs exceed cap %d; last %d will not be classified.",
            len(jobs), max_jobs, tail_count,
        )

    batch_size = max(1, int(batch_size))
    chunks = [
        jobs_to_classify[i:i + batch_size]
        for i in range(0, len(jobs_to_classify), batch_size)
    ]
    logger.info(
        "classify_batch: scoring %d jobs in %d batch(es) of <=%d (primary=%s).",
        len(jobs_to_classify), len(chunks), batch_size, primary_model,
    )

    results: list[GateVerdict | None] = []
    tier = 0  # 0=Gemini primary, 1=Gemini secondary, 2=Anthropic (opt-in)
    tier_logged = {1: False, 2: False}
    _gemini_primary = None
    _gemini_secondary = None
    _claude_client = None
    _use_cache = profile_text is not None

    for ci, chunk in enumerate(chunks):
        n = len(chunk)
        user_msg = _build_batch_user_msg(chunk)
        dicts: list[dict] | None = None

        # Space out Gemini calls to respect free-tier RPM (skip before the first call).
        if ci > 0 and tier < 2 and throttle_s > 0:
            time.sleep(throttle_s)

        # --- Tier 0: Gemini primary ---
        if tier == 0:
            try:
                if _gemini_primary is None:
                    _gemini_primary = _build_gemini_model(primary_model)
                dicts = _score_batch_gemini(_gemini_primary, system_prompt, user_msg, n)
            except Exception as exc:  # noqa: BLE001 — escalate to secondary Gemini
                logger.warning(
                    "classify_batch: primary %s failed (%s); escalating to secondary %s.",
                    primary_model, exc, secondary_model,
                )
                tier = 1

        # --- Tier 1: Gemini secondary (sticky) ---
        if tier == 1 and dicts is None:
            if not tier_logged[1]:
                logger.info("classify_batch: secondary model %s active for remainder of run.", secondary_model)
                tier_logged[1] = True
            try:
                if _gemini_secondary is None:
                    _gemini_secondary = _build_gemini_model(secondary_model)
                dicts = _score_batch_gemini(_gemini_secondary, system_prompt, user_msg, n)
            except Exception as exc:  # noqa: BLE001 — escalate to paid tier (if opted in)
                logger.warning(
                    "classify_batch: secondary %s failed (%s); %s.",
                    secondary_model, exc,
                    "escalating to Anthropic opt-in tier" if anthropic_optin
                    else "using parse_error fallback (paid tier OFF)",
                )
                tier = 2

        # --- Tier 2: Anthropic (PAID) — only if opted in; otherwise parse_error fallback ---
        if tier == 2 and dicts is None:
            if not anthropic_optin:
                if not tier_logged[2]:
                    logger.error(
                        "classify_batch: both free Gemini tiers failed and anthropic_optin=False; "
                        "remaining batches get parse_error fallback (NO paid calls)."
                    )
                    tier_logged[2] = True
                dicts = None
            else:
                if not tier_logged[2]:
                    logger.warning(
                        "classify_batch: PAID Anthropic tier (%s) active for remainder of run.", anthropic_model
                    )
                    tier_logged[2] = True
                try:
                    if _claude_client is None:
                        _claude_client = _build_claude_client()
                    dicts = _score_batch_claude(
                        _claude_client, anthropic_model, system_prompt, user_msg, n, use_cache=_use_cache
                    )
                except Exception as exc:  # noqa: BLE001 — all providers failed
                    logger.error("classify_batch: Anthropic also failed (%s); parse_error fallback.", exc)
                    dicts = None

        if dicts is None:
            dicts = [dict(_FALLBACK_VERDICT_PARSE_ERROR) for _ in range(n)]

        results.extend(_make_verdict(d) for d in dicts)

    results.extend([None] * tail_count)
    return results


# ---------------------------------------------------------------------------
# Batch helpers
# ---------------------------------------------------------------------------


def _build_batch_user_msg(chunk: list[dict]) -> str:
    """Render a numbered list of jobs for one batched scoring call."""
    n = len(chunk)
    lines = [f"Score these {n} jobs. Return a JSON array of exactly {n} objects, in order:\n"]
    for i, job in enumerate(chunk, start=1):
        lines.append(
            f"[{i}] Title: {job.get('title', '')} | Company: {job.get('company_name', '')} | "
            f"Location: {job.get('location', '')} | "
            f"Snippet: {(job.get('description_snippet') or '')[:300]}"
        )
    return "\n".join(lines)


def _score_batch_gemini(model, system_prompt: str, user_msg: str, n: int) -> list[dict]:
    """One batched Gemini call → list of n verdict dicts (free tier).

    NOTE: Gemini 2.5 models think before answering, and thinking tokens count against
    max_output_tokens. A low cap truncates the JSON (finish_reason=MAX_TOKENS) and the
    parse fails. So we (a) force JSON via response_mime_type and (b) set a generous cap
    that covers thinking + the array. Empirically n=10 uses ~7k tokens total; 8192 is safe.
    """
    full_prompt = system_prompt + "\n\n" + user_msg
    response = model.generate_content(
        full_prompt,
        generation_config={
            "temperature": 0,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        },
    )
    text = (getattr(response, "text", "") or "").strip()
    if not text:
        # Empty (often a safety block or truncated-before-any-output) → let the caller escalate.
        raise RuntimeError("Gemini returned empty text")
    dicts = _parse_verdict_array(text, n)
    # If the WHOLE batch failed to parse (e.g. JSON truncated by thinking-token MAX_TOKENS),
    # raise so classify_batch escalates to the secondary model instead of silently dropping
    # every job in the batch to parse_error.
    if dicts and all(d.get("reason") == "parse_error" for d in dicts):
        raise RuntimeError("Gemini batch unparseable (likely truncated)")
    return dicts


def _score_batch_claude(
    client, model: str, system_prompt: str, user_msg: str, n: int, *, use_cache: bool = False
) -> list[dict]:
    """One batched Anthropic call → list of n verdict dicts (PAID, opt-in tier only)."""
    from tenacity import (  # imported lazily
        retry,
        retry_if_exception,
        stop_after_attempt,
        wait_exponential,
    )

    def _is_retriable_anthropic(exc: BaseException) -> bool:
        try:
            import anthropic
            return isinstance(exc, (anthropic.RateLimitError, anthropic.InternalServerError))
        except ImportError:
            return False

    if use_cache:
        system_param: list | str = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]
    else:
        system_param = system_prompt

    @retry(
        retry=retry_if_exception(_is_retriable_anthropic),
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _invoke() -> list[dict]:
        response = client.messages.create(
            model=model,
            max_tokens=min(8192, 150 + n * 90),
            temperature=0,
            system=system_param,
            messages=[{"role": "user", "content": user_msg}],
        )
        return _parse_verdict_array(response.content[0].text.strip(), n)

    return _invoke()


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


def _call_claude(
    client, model: str, system_prompt: str, user_msg: str, *, use_cache: bool = False
) -> dict:
    """Call Claude synchronously with tenacity retry (2 retries on 429/5xx).

    When use_cache=True the system param becomes a list-of-blocks with cache_control
    so Anthropic can cache the (large) profile system prompt across the batch.

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

    # Build the system param: list-of-blocks with cache_control when profile is present;
    # plain string otherwise (backward-compatible).
    if use_cache:
        system_param: list | str = [
            {"type": "text", "text": system_prompt, "cache_control": {"type": "ephemeral"}}
        ]
    else:
        system_param = system_prompt

    @retry(
        retry=retry_if_exception(_is_retriable_anthropic),
        stop=stop_after_attempt(3),  # initial + 2 retries
        wait=wait_exponential(multiplier=1, min=2, max=20),
        reraise=True,
    )
    def _invoke() -> dict:
        response = client.messages.create(
            model=model,
            max_tokens=220,
            temperature=0,
            system=system_param,
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
    # Pass generation_config as a plain dict — the SDK accepts dict or GenerationConfig object.
    # temperature=0 stabilises the classifier output (mirrors the Claude path).
    response = model.generate_content(
        full_prompt,
        generation_config={"temperature": 0},
    )
    raw_text = response.text.strip()
    return _parse_verdict_json(raw_text)


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


def _strip_fences(raw: str) -> str:
    """Remove ```...``` markdown fences if the model wrapped its JSON."""
    text = raw.strip()
    if text.startswith("```"):
        lines = [l for l in text.splitlines() if not l.startswith("```")]
        text = "\n".join(lines).strip()
    return text


def _normalize_verdict_dict(parsed: dict) -> dict:
    """Normalise one raw verdict dict: relevance enum, contract_type map, fit_score clamp,
    match_identity enum-guard, reason truncation. Pure; no I/O."""
    relevance = (parsed.get("relevance") or "borderline")
    relevance = relevance.lower() if isinstance(relevance, str) else "borderline"
    if relevance not in _VALID_RELEVANCES:
        relevance = "borderline"

    raw_ct = parsed.get("contract_type")
    contract_type: str | None = None
    if raw_ct and isinstance(raw_ct, str):
        ct_lookup = {v.lower(): v for v in _VALID_CONTRACT_TYPES}
        contract_type = ct_lookup.get(raw_ct.strip().lower())
        if contract_type == "Unknown":
            contract_type = None  # Normalise "Unknown" → None

    # fit_score: clamp to 0-100; non-int (or bool) or missing → 0
    raw_score = parsed.get("fit_score")
    if isinstance(raw_score, (int, float)) and not isinstance(raw_score, bool):
        fit_score = max(0, min(100, int(raw_score)))
    else:
        fit_score = 0

    # match_identity: enum-guard to {"salaried", "freelance"}; anything else → None
    raw_identity = parsed.get("match_identity")
    if isinstance(raw_identity, str) and raw_identity.lower() in _VALID_MATCH_IDENTITIES:
        match_identity: str | None = raw_identity.lower()
    else:
        match_identity = None

    reason = str(parsed.get("reason") or "ok")[:120]

    return {
        "relevance": relevance,
        "contract_type": contract_type,
        "fit_score": fit_score,
        "match_identity": match_identity,
        "reason": reason,
    }


def _parse_verdict_json(raw: str) -> dict:
    """Parse a single JSON verdict object. Falls back to parse_error dict on failure."""
    text = _strip_fences(raw)
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        logger.warning("_parse_verdict_json: failed to parse: %r", raw[:200])
        return dict(_FALLBACK_VERDICT_PARSE_ERROR)
    if not isinstance(parsed, dict):
        logger.warning("_parse_verdict_json: expected object, got %s", type(parsed).__name__)
        return dict(_FALLBACK_VERDICT_PARSE_ERROR)
    return _normalize_verdict_dict(parsed)


def _parse_verdict_array(raw: str, n: int) -> list[dict]:
    """Parse a JSON ARRAY of n verdict objects. Always returns exactly n dicts:
    short arrays are padded and long ones truncated with parse_error fallbacks."""
    text = _strip_fences(raw)
    parsed = None
    try:
        parsed = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        # Salvage the outermost [...] if the model added stray prose.
        start, end = text.find("["), text.rfind("]")
        if start != -1 and end > start:
            try:
                parsed = json.loads(text[start:end + 1])
            except (json.JSONDecodeError, ValueError):
                parsed = None

    if isinstance(parsed, dict) and n == 1:
        return [_normalize_verdict_dict(parsed)]
    if not isinstance(parsed, list):
        logger.warning("_parse_verdict_array: no JSON array (got %s); %d parse_error fallback(s).",
                       type(parsed).__name__, n)
        return [dict(_FALLBACK_VERDICT_PARSE_ERROR) for _ in range(n)]

    out = [
        _normalize_verdict_dict(x) if isinstance(x, dict) else dict(_FALLBACK_VERDICT_PARSE_ERROR)
        for x in parsed
    ]
    if len(out) != n:
        logger.warning("_parse_verdict_array: expected %d objects, got %d; padding/truncating.", n, len(out))
    if len(out) < n:
        out.extend(dict(_FALLBACK_VERDICT_PARSE_ERROR) for _ in range(n - len(out)))
    return out[:n]


def _make_verdict(d: dict) -> GateVerdict:
    return GateVerdict(
        relevance=d.get("relevance", "borderline"),
        contract_type=d.get("contract_type"),
        reason=d.get("reason", ""),
        fit_score=d.get("fit_score", 0),
        match_identity=d.get("match_identity"),
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
        default="gemini-2.5-flash",
        help="Primary FREE Gemini model (default: gemini-2.5-flash).",
    )
    parser.add_argument(
        "--secondary-model",
        default="gemini-2.5-flash-lite",
        help="Secondary FREE Gemini model on primary failure (default: gemini-2.5-flash-lite).",
    )
    parser.add_argument(
        "--batch-size",
        type=int, default=10,
        help="Jobs scored per LLM call (default: 10).",
    )
    parser.add_argument(
        "--anthropic-optin",
        action="store_true",
        help="Allow PAID Anthropic fallback if both Gemini tiers fail (default: off — never charges).",
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
        secondary_model=args.secondary_model,
        batch_size=args.batch_size,
        anthropic_optin=args.anthropic_optin,
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
