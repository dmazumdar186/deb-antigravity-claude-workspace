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
logger = logging.getLogger("ranker.score")

RUBRIC_PATH = Path(__file__).resolve().parent / "rubric.md"
PROFILE_PATH = (
    Path(__file__).resolve().parent.parent / "profile" / "profile.json"
)
DEFAULT_MODEL = "gemini-2.5-flash"
RUBRIC_VERSION = "v3-2026-06-27-profile-grounded"

# Deterministic dimension weights. Sum to 1.0. Changed here = changed
# everywhere (the LLM never sees these — it only scores per-dimension).
DIMENSION_WEIGHTS = {
    "title_fit": 0.30,
    "skill_overlap": 0.30,
    "contract_fit": 0.15,
    "seniority_fit": 0.10,
    "location_fit": 0.15,
}
# Tier thresholds applied to final_score.
TIER_THRESHOLDS = (("A", 0.75), ("B", 0.50), ("C", 0.25))


def _load_profile_for_prompt() -> str:
    """Read profile.json and serialize it for prompt injection. Returns an
    empty string if the file is missing (caller falls back to legacy behavior)."""
    if not PROFILE_PATH.exists():
        logger.warning("ranker: profile.json missing at %s — falling back "
                       "to legacy prose rubric.", PROFILE_PATH)
        return ""
    try:
        return PROFILE_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        logger.warning("ranker: profile.json read failed (%s) — legacy fallback.", exc)
        return ""


def _compute_final_score(dims: dict) -> float:
    """Weighted arithmetic mean of the five dimensions. Penalty: if any of
    title_fit / contract_fit / location_fit is 0, the job is auto-SKIP
    (final = 0). This prevents one weak dim from being masked by strong others
    (e.g. wrong country with great skill match should NOT survive)."""
    hard_zero_dims = ("title_fit", "contract_fit", "location_fit")
    if any(float(dims.get(d, 0.0)) == 0.0 for d in hard_zero_dims):
        return 0.0
    total = 0.0
    for k, w in DIMENSION_WEIGHTS.items():
        total += w * max(0.0, min(1.0, float(dims.get(k, 0.0))))
    return round(total, 4)


def _tier_from_final(score: float) -> JobTier:
    for tier_name, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return JobTier(tier_name)
    return JobTier.SKIP


def _format_reasoning(track: str, dims: dict, matched: list[str],
                      missing: list[str], llm_reason: str) -> str:
    """Render the audit-trail string that goes into RankedJob.reasoning.
    Format: '[track X] title=0.85 skills=0.90 contract=1.0 sen=1.0 loc=1.0 |
    matched: A, B, C | missing: none | <one-sentence why>'.
    Capped at 800 chars (RankedJob.reasoning max_length)."""
    dim_str = " ".join(
        f"{k.split('_')[0]}={float(dims.get(k, 0.0)):.2f}"
        for k in ("title_fit", "skill_overlap", "contract_fit",
                  "seniority_fit", "location_fit")
    )
    matched_str = ", ".join(matched[:8]) if matched else "none"
    missing_str = ", ".join(missing[:4]) if missing else "none"
    out = (f"[track {track}] {dim_str} | matched: {matched_str} | "
           f"missing: {missing_str} | {llm_reason}")
    return out[:800]

# Sheets fallback cell for GEMINI_API_KEY. Lives in Summary!F1 — row 1 is
# excluded from the `A2:F{n}` batch_clear in refresh_summary(), so this cell
# survives every run. This is a stopgap until the workflow YAML
# (which would pass secrets.GEMINI_API_KEY through to the cron env) can land
# at origin — the PAT lacks `workflow` scope, so direct push is rejected.
GEMINI_KEY_SHEET_CELL = "F1"
GEMINI_KEY_SHEET_TAB = "Summary"


def _gsheet_gemini_key_get() -> str | None:
    """Read the GEMINI_API_KEY fallback from Summary!F1. Returns None on any
    failure (creds missing / sheet unreachable / cell empty)."""
    try:
        from execution.personal_workflows.job_search_v2.notifier.sheet import _open_sheet
    except ImportError:
        return None
    try:
        sp, err = _open_sheet(None, None)
        if sp is None:
            return None
        ws = sp.worksheet(GEMINI_KEY_SHEET_TAB)
        val = ws.acell(GEMINI_KEY_SHEET_CELL).value
        return val.strip() if val else None
    except Exception as exc:  # noqa: BLE001 — best-effort read; falls back to heuristic
        logger.warning("ranker: Sheets fallback read failed: %s", exc)
        return None


def _gsheet_gemini_key_set(key: str) -> bool:
    """Write a new GEMINI_API_KEY into Summary!F1. Returns True on success."""
    try:
        from execution.personal_workflows.job_search_v2.notifier.sheet import _open_sheet
    except ImportError:
        return False
    try:
        sp, err = _open_sheet(None, None)
        if sp is None:
            logger.error("ranker: Sheets fallback write — could not open sheet: %s", err)
            return False
        ws = sp.worksheet(GEMINI_KEY_SHEET_TAB)
        ws.update(range_name=GEMINI_KEY_SHEET_CELL, values=[[key]], value_input_option="USER_ENTERED")
        return True
    except Exception as exc:  # noqa: BLE001 — log and return False
        logger.error("ranker: Sheets fallback write failed: %s", exc)
        return False


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
        # Sheets fallback — the workflow YAML at origin doesn't plumb
        # GEMINI_API_KEY through (the YAML fix is local-only pending workflow
        # PAT scope). As a stopgap, the key is written to a private cell in
        # the Summary tab from a local environment that DOES have it; the
        # cron-side script reads it from there. Removable as soon as the
        # YAML lands.
        api_key = _gsheet_gemini_key_get() or ""
        if api_key:
            logger.info("ranker: GEMINI_API_KEY missing from env — using Sheets fallback (Summary!F1)")

    if not api_key:
        # Diagnostic: tell the operator exactly where we looked so they can stop
        # debugging "I have it in .env, why is it missing?" — the prior message
        # said "no GEMINI_API_KEY in .env" which was misleading because we actually
        # check os.environ, not the .env file directly. Most common cause in CI:
        # the workflow YAML doesn't pass the secret through to the run step's env.
        dotenv_path = find_dotenv(usecwd=False)
        if dotenv_path:
            where = f"env var not set; .env was located at {dotenv_path} but did not provide it; Sheets fallback also empty"
        else:
            where = "env var not set; no .env file found walking up from this script; Sheets fallback also empty"
        logger.warning("ranker: GEMINI_API_KEY missing — %s. Falling back to heuristic.", where)
        for j in jobs:
            out[j.content_hash] = _placeholder_ranked(j, f"GEMINI_API_KEY missing ({where})")
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
    profile_json = _load_profile_for_prompt()
    client = genai.Client(api_key=api_key)

    # v3 schema (2026-06-27): per-dimension scoring grounded in profile.json.
    # The LLM scores 5 dims + returns matched_skills (audit trail). Python
    # combines them deterministically (see _compute_final_score) so the final
    # tier never depends on the model "feeling" a score.
    batch_schema = {
        "type": "object",
        "properties": {
            "results": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "job_id": {"type": "string"},
                        "track": {"type": "string", "enum": ["A", "B"]},
                        "dimensions": {
                            "type": "object",
                            "properties": {
                                "title_fit": {"type": "number"},
                                "skill_overlap": {"type": "number"},
                                "contract_fit": {"type": "number"},
                                "seniority_fit": {"type": "number"},
                                "location_fit": {"type": "number"},
                            },
                            "required": ["title_fit", "skill_overlap",
                                         "contract_fit", "seniority_fit",
                                         "location_fit"],
                        },
                        "matched_skills": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "missing_critical": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "reasoning": {"type": "string", "maxLength": 200},
                    },
                    "required": ["job_id", "track", "dimensions",
                                 "matched_skills", "missing_critical",
                                 "reasoning"],
                },
            }
        },
        "required": ["results"],
    }

    # System instruction = rubric + profile JSON. Profile is verbatim so the
    # model can grep for skill names and quote them in matched_skills.
    if profile_json:
        system_text = (
            rubric
            + "\n\n<PROFILE>\n" + profile_json + "\n</PROFILE>\n\n"
            + "You will receive a JSON array of jobs. Return one ranking per "
              "job, matching the job_id field exactly. Output must be JSON "
              "{results: [...]}. Cite specific profile skill names verbatim "
              "in matched_skills."
        )
    else:
        # Legacy fallback (profile.json missing). Should never hit in prod.
        system_text = (
            rubric
            + "\n\nYou will receive a JSON array of jobs. Return one ranking "
              "per job, matching the job_id field exactly. Output must be "
              "JSON {results: [...]}."
        )

    cfg = types.GenerateContentConfig(
        system_instruction=system_text,
        response_mime_type="application/json",
        response_schema=batch_schema,
        temperature=0.2,
        # 60k output budget — 2026-07-01 audit: 30k was truncating 40-80 job
        # chunks mid-JSON. Gemini 2.5 Flash supports up to 65k output tokens.
        max_output_tokens=60000,
    )

    fallback_model = "gemini-2.5-flash-lite"

    # Build a job_id → job map so we can stitch the LLM response back to each job.
    id_to_job: dict[str, NormalizedJob] = {}
    all_payload_items = []
    for j in jobs:
        short_id = j.content_hash[:16]
        id_to_job[short_id] = j
        all_payload_items.append({
            "job_id": short_id,
            "title": j.title,
            "company": j.company,
            "location": j.location,
            "source": j.source.value,
            "contract_type": j.contract_type.value,
            "remote_mode": j.remote_mode.value,
            "posted_at": j.posted_at.isoformat() if j.posted_at else "unknown",
            # 220 chars per description — 2026-07-01 audit: 400 chars × 40
            # jobs pushed output tokens over budget. 220 keeps the ranker
            # decisive (contains skill/seniority tells) without runaway
            # tokens in the request.
            "description_snippet": j.description_snippet[:220],
        })

    # CHUNKING — Audit 2026-07-01: 80-job chunks were blowing the 30k-token
    # output budget and Gemini truncated responses mid-JSON. Today's run:
    # 160/166 jobs (96%) fell to heuristic-placeholder because chunk 1 + 2
    # returned `Unterminated string at char 3325` / `Expecting value at char
    # 3496` — both are truncation signatures, not network errors, so the
    # retry loop (which only re-fires on RETRY_MARKERS) never engaged.
    #
    # Fixes: (a) halve CHUNK_SIZE to 40, (b) trim per-job description_snippet
    # from 400 to 220 chars in the payload, (c) raise max_output_tokens from
    # 30k to 60k as a safety margin. Together: worst-case chunk output
    # ~40 * 300 tok/response ≈ 12k tokens, well under 60k budget.
    CHUNK_SIZE = 40
    SLEEP_BETWEEN_CHUNKS = 7.0
    # Retriable error markers (added: "disconnected" / "timeout" / "INTERNAL"
    # to catch the mid-batch socket close + the Gemini-side 500s.).
    RETRY_MARKERS = (
        "503", "429", "500",
        "UNAVAILABLE", "RESOURCE_EXHAUSTED", "INTERNAL", "DEADLINE_EXCEEDED",
        "disconnected", "timeout", "Timeout",
    )

    def _call_chunk(model_name: str, payload_items: list[dict]):
        payload = json.dumps({"jobs": payload_items}, ensure_ascii=False)
        return client.models.generate_content(model=model_name, contents=payload, config=cfg)

    scored_ids: set[str] = set()
    chunk_failures: list[str] = []  # store exception class names for stats
    chunks = [all_payload_items[i:i + CHUNK_SIZE] for i in range(0, len(all_payload_items), CHUNK_SIZE)]

    for chunk_idx, chunk in enumerate(chunks):
        if chunk_idx > 0:
            time.sleep(SLEEP_BETWEEN_CHUNKS)

        resp = None
        used_model = model
        last_exc: Exception | None = None
        for attempt in (1, 2, 3):
            try:
                use = model if attempt < 3 else fallback_model
                resp = _call_chunk(use, chunk)
                used_model = use
                last_exc = None
                break
            except Exception as exc:  # noqa: BLE001 — Gemini surface; backoff + retry
                last_exc = exc
                msg = str(exc)
                if not any(k in msg for k in RETRY_MARKERS):
                    break
                time.sleep(2.0 * attempt)

        if resp is None or last_exc is not None:
            logger.warning(
                "ranker: chunk %d/%d failed (%s: %s) — chunk falls to heuristic",
                chunk_idx + 1, len(chunks), type(last_exc).__name__ if last_exc else "unknown",
                last_exc,
            )
            chunk_failures.append(type(last_exc).__name__ if last_exc else "unknown")
            continue

        try:
            data = json.loads(resp.text or "{}")
            results = data.get("results", [])
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("ranker: chunk %d response parse failed (%s)", chunk_idx + 1, exc)
            chunk_failures.append("ParseError")
            continue

        for r in results:
            jid = str(r.get("job_id", "")).strip()
            if jid not in id_to_job:
                continue
            job = id_to_job[jid]
            try:
                # v3: dimensions drive the score; legacy 'score'/'tier' from
                # the model are IGNORED. This keeps the final number
                # deterministic given a fixed dimension vector.
                dims_raw = r.get("dimensions") or {}
                dims = {
                    k: max(0.0, min(1.0, float(dims_raw.get(k, 0.0))))
                    for k in DIMENSION_WEIGHTS
                }
                final_score = _compute_final_score(dims)
                tier = _tier_from_final(final_score)
                track = str(r.get("track", "A")).upper()
                if track not in ("A", "B"):
                    track = "A"
                matched = [str(s) for s in (r.get("matched_skills") or [])][:12]
                missing = [str(s) for s in (r.get("missing_critical") or [])][:8]
                llm_reason = str(r.get("reasoning", ""))[:300]
                reasoning = _format_reasoning(
                    track, dims, matched, missing, llm_reason
                )
                out[job.content_hash] = RankedJob(
                    content_hash=job.content_hash,
                    score=final_score,
                    tier=tier,
                    reasoning=reasoning,
                    rubric_version=RUBRIC_VERSION,
                    ranker_model=used_model,
                )
                stats["scored"] += 1
                stats["by_tier"][tier.value] += 1
                scored_ids.add(jid)
            except (ValueError, KeyError, TypeError) as exc:
                logger.warning("ranker: result for %s malformed (%s) — heuristic", jid, exc)

    if chunk_failures:
        stats["chunk_failures"] = chunk_failures

    # Any job not in any response → profile-aware heuristic fallback. The
    # legacy substring heuristic (kept below as `_heuristic_score_legacy`)
    # had no profile context and ranked anything matching keywords. The new
    # path runs the SAME 5-dim algorithm the LLM uses, just deterministically
    # in Python — so the fallback path now produces operator-coherent tiers
    # even when Gemini is hard-rate-limited.
    profile_data = _load_profile_data()
    for j in jobs:
        if j.content_hash[:16] in scored_ids:
            continue
        dims, track, matched, missing = _profile_aware_heuristic(j, profile_data)
        final_score = _compute_final_score(dims)
        tier = _tier_from_final(final_score)
        reasoning = _format_reasoning(
            track, dims, matched, missing,
            "profile-aware heuristic (LLM unavailable)"
        )
        out[j.content_hash] = RankedJob(
            content_hash=j.content_hash,
            score=final_score,
            tier=tier,
            reasoning=reasoning,
            rubric_version="heuristic-v2-profile-grounded",
            ranker_model="heuristic-profile",
        )
        stats["placeholder"] += 1
        stats["by_tier"][tier.value] += 1

    logger.info("ranker: %s", stats)
    return out, stats


# ----- profile-aware heuristic (v2 fallback) -----


_profile_cache: dict | None = None


def _load_profile_data() -> dict:
    """Memoized profile.json read. Returns {} on missing/unreadable so the
    heuristic still runs (degraded to legacy keyword scoring)."""
    global _profile_cache
    if _profile_cache is not None:
        return _profile_cache
    if not PROFILE_PATH.exists():
        _profile_cache = {}
        return _profile_cache
    try:
        _profile_cache = json.loads(PROFILE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("heuristic: profile.json unreadable (%s); empty fallback", exc)
        _profile_cache = {}
    return _profile_cache


_SKILL_LEVEL_WEIGHT = {"expert": 3.0, "strong": 2.0, "familiar": 1.0}
_SKILL_OVERLAP_NORM = 8.0  # matches rubric: score = min(1, weight / 8)
_SENIORITY_TOKENS = (
    "senior", "lead", "principal", "head ", "head of", "director",
    "staff", "vp ", "vp of", "chief", "fractional",
)
_JUNIOR_TOKENS = (
    "junior", "intern", "stagiaire", "alternance", "trainee",
    "graduate", "apprenti",
)
_FOREIGN_LANG_TELLS = (
    "wir suchen", "een ervaren", "cerchiamo", "buscamos",
    "muttersprache", "moedertaal", "madrelingua",
)


def _profile_aware_heuristic(
    job: NormalizedJob, profile: dict,
) -> tuple[dict, str, list[str], list[str]]:
    """Deterministic 5-dim scoring grounded in profile.json. Returns
    (dimensions, track, matched_skills, missing_critical) for downstream
    _compute_final_score + _format_reasoning.

    No LLM involved. Same algorithm the LLM uses, applied in Python."""
    title = (job.title or "").lower()
    desc = (job.description_snippet or "").lower()
    haystack = title + " " + desc
    loc = (job.location or "").lower()
    contract = (job.contract_type.value or "").lower()

    tracks = profile.get("tracks", []) or []
    skills = profile.get("skills", []) or []
    locations_cfg = profile.get("locations", {}) or {}
    hard = profile.get("hard_filters", {}) or {}

    # Hard-zero short-circuit: skip-list substring or blocked country or
    # foreign-language tell. Returning all-zero dims here makes
    # _compute_final_score emit 0 → SKIP.
    skip_subs = [s.lower() for s in hard.get("skip_title_substrings", [])]
    skip_descs = [s.lower() for s in hard.get("skip_description_substrings", [])]
    blocked = [b.lower() for b in locations_cfg.get("blocked_countries", [])]

    def _zero(reason_tag: str) -> tuple[dict, str, list[str], list[str]]:
        dims = {k: 0.0 for k in DIMENSION_WEIGHTS}
        return dims, "A", [], [reason_tag]

    if any(s in title for s in skip_subs):
        return _zero("title-skip-filter")
    if any(s in desc for s in skip_descs):
        return _zero("desc-skip-filter")
    if any(b in loc for b in blocked) or any(
        c in loc for c in ("new york", "san francisco", "bangalore",
                           "mumbai", "delhi", "singapore", "sydney",
                           " usa", " us ", "united states")
    ):
        return _zero("blocked-country")
    if any(t in haystack for t in _FOREIGN_LANG_TELLS):
        return _zero("foreign-language-jd")

    # Decide track. Try Track A title patterns first; if Track B titles fit
    # better, switch. Used to pick which targeted_titles + contract_types
    # apply.
    def _title_score(target_titles: list[str], anti_titles: list[str]) -> float:
        for t in (anti_titles or []):
            if t.lower() in title:
                return 0.0
        for t in (target_titles or []):
            tl = t.lower()
            if tl in title:
                return 1.0
            # token overlap as near-literal
            ttokens = [w for w in tl.split() if len(w) > 2]
            if ttokens and all(w in title for w in ttokens):
                return 0.9
        # adjacent role family — at least 2 of the title's words appear
        # somewhere in the target list (e.g. "AI" + "Engineer" in any
        # target — drift)
        title_words = {w for w in title.split() if len(w) > 2}
        for t in (target_titles or []):
            tw = {w for w in t.lower().split() if len(w) > 2}
            overlap = len(title_words & tw)
            if overlap >= 2:
                return 0.7
            if overlap == 1:
                return 0.4
        return 0.0

    track_a = next((t for t in tracks if t.get("id") == "A"), {})
    track_b = next((t for t in tracks if t.get("id") == "B"), {})
    title_a = _title_score(track_a.get("targeted_titles", []),
                           track_a.get("anti_titles", []))
    title_b = _title_score(track_b.get("targeted_titles", []),
                           track_b.get("anti_titles", []))

    # Description tells: "freelance" / "mission" / "tjm" boost Track B
    track_b_desc_tells = ("freelance", "mission", "tjm", "/jour", "daily rate",
                          "indépendant", "independant", "contract")
    if any(t in haystack for t in track_b_desc_tells):
        title_b = min(1.0, title_b + 0.2)

    if title_b > title_a:
        chosen_track = "B"
        track_cfg = track_b
        title_fit = title_b
    else:
        chosen_track = "A"
        track_cfg = track_a
        title_fit = title_a

    # Skill overlap: scan profile.skills for names in haystack, weighted.
    matched: list[str] = []
    weight_sum = 0.0
    for s in skills:
        name = (s.get("name") or "").lower()
        if not name:
            continue
        # match by name; also by simpler base form (strip parens / dots)
        bases = {name, name.split("(")[0].strip(), name.replace(".", "")}
        if any(b and b in haystack for b in bases):
            matched.append(s["name"])
            weight_sum += _SKILL_LEVEL_WEIGHT.get(s.get("level", "familiar"), 1.0)
    skill_overlap = min(1.0, weight_sum / _SKILL_OVERLAP_NORM)

    # Contract fit.
    track_contracts = [c.lower() for c in track_cfg.get("contract_types", [])]
    if contract and contract in track_contracts:
        contract_fit = 1.0
    elif not contract or contract == "unknown":
        contract_fit = 0.6
    else:
        contract_fit = 0.0  # wrong contract for chosen track

    # Seniority fit.
    if any(t in haystack for t in _JUNIOR_TOKENS):
        seniority_fit = 0.0
    elif any(t in haystack for t in _SENIORITY_TOKENS):
        seniority_fit = 1.0
    else:
        seniority_fit = 0.6

    # Location fit.
    preferred = [p.lower() for p in locations_cfg.get("preferred", [])]
    ok_remote = [r.lower() for r in locations_cfg.get("ok_remote", [])]
    if any(p in loc for p in preferred) or "paris" in loc or "île-de-france" in loc or "ile-de-france" in loc:
        location_fit = 1.0
    elif any(r in loc for r in ok_remote) or "remote" in loc:
        location_fit = 1.0 if "eu" in loc or "europe" in loc else 0.7
    elif any(c in loc for c in ("france", "germany", "belgium", "switzerland",
                                 "schengen", "deutschland")):
        location_fit = 0.7
    elif any(c in loc for c in ("spain", "italy", "netherlands", "portugal")):
        location_fit = 0.3
    else:
        location_fit = 0.3

    dims = {
        "title_fit": title_fit,
        "skill_overlap": skill_overlap,
        "contract_fit": contract_fit,
        "seniority_fit": seniority_fit,
        "location_fit": location_fit,
    }
    return dims, chosen_track, matched[:12], []


# ----- legacy heuristic (kept for reference; no longer the fallback path) -----


# Track A (Permanent AI PM) signals.
_TRACK_A_HIGH = (
    "ai product manager", "genai product manager", "ml product manager",
    "llm product manager", "ai/ml product manager",
    "head of product", "vp product", "vp of product", "chief product officer",
    "senior ai product manager", "lead ai product manager",
    "chef de produit ia", "responsable produit ia",
    "directeur produit", "directrice produit",
)
_TRACK_A_MEDIUM = (
    "senior product manager", "lead product manager", "principal product manager",
    "staff product manager", "product lead",
    "chef de produit senior", "responsable produit senior",
    "product manager", "product owner",
    "chef de produit", "responsable produit",
)

# Track B (Freelance AI Automation / Claude Code / React Native) signals.
_TRACK_B_HIGH = (
    "ai automation engineer", "ai automation specialist", "ai automation consultant",
    "ai engineer", "claude code",
    "ai consultant", "ai strategy consultant", "ai transformation consultant",
    "ai solutions consultant", "ai advisor",
    "react native developer", "react native engineer",
    "consultant ia", "automatisation ia",
)
_TRACK_B_MEDIUM = (
    "ai mobile", "mobile ai", "automation engineer",
    "process automation", "ai process",
    "freelance ai", "ai contractor",
    "head of ai", "ai lead",
)

# Signals in the description that boost Track B (the listing IS a freelance/
# mission framing). Track B is about role TYPE as much as title.
_FREELANCE_DESC_TELLS = (
    "freelance", "contract", "contractor", "consultant",
    "mission", "tjm", "/jour", "/day", "daily rate",
    "indépendant", "independant",
)
# Major-city / region targets across all 4 in-scope countries. Anything in this
# tuple gets the full location weight; "france/germany/belgium/switzerland"
# country-name match gets a slightly lower weight; everything else is the floor.
_HIGH_SIGNAL_LOCATIONS = (
    # France
    "paris", "île-de-france", "ile-de-france",
    "lyon", "toulouse", "marseille", "bordeaux", "nantes", "lille",
    # Germany
    "berlin", "munich", "münchen", "muenchen", "hamburg",
    "frankfurt", "köln", "koeln", "cologne", "düsseldorf", "duesseldorf", "stuttgart",
    # Belgium
    "brussels", "bruxelles", "brussel", "antwerp", "anvers", "antwerpen",
    "ghent", "gent", "gand", "leuven", "louvain", "liège", "liege",
    # Switzerland
    "geneva", "genève", "geneve", "genf",
    "zurich", "zürich", "lausanne", "bern", "berne", "basel", "bâle", "lugano",
    # Remote-EU friendlies
    "remote (france)", "remote (germany)", "remote (belgium)", "remote (switzerland)",
    "remote (europe)", "remote (eu)",
)
_TARGET_COUNTRY_NAMES = (
    "france", "germany", "deutschland",
    "belgium", "belgique", "belgië", "belgie",
    "switzerland", "suisse", "schweiz", "svizzera",
)


def _heuristic_score(job: NormalizedJob) -> float:
    """Deterministic 0..1 score for when the LLM is unavailable.

    Tracks-aware (2026-06-24 reset against operator's CV + Malt + GitHub):
      Track A — Permanent AI PM. Title-driven.
      Track B — Freelance AI Automation / Claude Code / React Native.
                Title + freelance-tells in description.
    Final score = max(track_a_score, track_b_score) so a job that's a
    great fit for EITHER track gets credit.

    Per-track weights (sum to 1.0 inside each track):
      title  0.6  — track-specific high (1.0), medium (0.6), else (0.2)
      loc    0.25 — high-signal city = 1.0; target country = 0.7;
                    remote/hybrid = 0.7; else 0.3
      type   0.15 — Track A wants CDI; Track B wants Freelance/Contract.
                    Unknown contract in target country = neutral 0.6.
    """
    title = (job.title or "").lower()
    desc = (job.description_snippet or "").lower()
    loc = (job.location or "").lower()
    contract = (job.contract_type.value or "").lower()

    # Track-specific title scores.
    if any(t in title for t in _TRACK_A_HIGH):
        track_a_title = 1.0
    elif any(t in title for t in _TRACK_A_MEDIUM):
        track_a_title = 0.6
    else:
        track_a_title = 0.2

    if any(t in title for t in _TRACK_B_HIGH):
        track_b_title = 1.0
    elif any(t in title for t in _TRACK_B_MEDIUM):
        track_b_title = 0.6
    else:
        track_b_title = 0.2

    # Location score — shared across tracks. Paris+50km is operator's stated
    # on-site zone; rest of France is fine; DE/BE/CH-English is fine (the
    # language filter ensures the listing is in EN/FR).
    if any(t in loc for t in _HIGH_SIGNAL_LOCATIONS):
        loc_s = 1.0
    elif any(c in loc for c in _TARGET_COUNTRY_NAMES) or "remote" in loc or "hybrid" in loc:
        loc_s = 0.7
    else:
        loc_s = 0.3

    in_target_country = loc_s >= 0.7

    # Contract scores DIFFER per track.
    if contract == "cdi":
        track_a_type = 1.0
        track_b_type = 0.2  # CDI not what Track B is looking for
    elif contract == "freelance":
        track_a_type = 0.3
        track_b_type = 1.0
    elif contract == "cdd":
        track_a_type = 0.5
        track_b_type = 0.4
    elif contract in ("unknown", "") and in_target_country:
        # Source didn't expose contract — neutral.
        track_a_type = 0.6
        track_b_type = 0.6
    else:
        track_a_type = 0.2
        track_b_type = 0.2

    # Freelance-tell boost for Track B — if the description explicitly mentions
    # freelance/mission/TJM/daily-rate, this is more clearly a Track B fit.
    if any(t in desc for t in _FREELANCE_DESC_TELLS):
        track_b_type = max(track_b_type, 0.8)
        # Also boost Track B title a notch (signals are reinforcing).
        track_b_title = min(1.0, track_b_title + 0.2)

    track_a_score = 0.6 * track_a_title + 0.25 * loc_s + 0.15 * track_a_type
    track_b_score = 0.6 * track_b_title + 0.25 * loc_s + 0.15 * track_b_type

    return round(max(track_a_score, track_b_score), 4)


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
