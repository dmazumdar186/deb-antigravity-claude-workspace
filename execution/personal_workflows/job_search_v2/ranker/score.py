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
DEFAULT_MODEL = "gemini-2.5-flash"
RUBRIC_VERSION = "v1-2026-06-15"

# Sheets fallback cell for GEMINI_API_KEY. Lives in Summary!F1 — row 1 survives
# the per-run `A2:F` clear in refresh_summary(), and column H is outside any
# range the dashboard writes to. This is a stopgap until the workflow YAML
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
        max_output_tokens=20000,
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
            "description_snippet": j.description_snippet[:400],
        })

    # CHUNKING — 445-job single calls had been timing out ("Server disconnected
    # without sending a response") because the model takes ~30-60s to produce a
    # 64k-token output and the default httpx timeout fires. Split into chunks
    # of ~80 jobs each; sleep 7s between (10 RPM free-tier budget). Each chunk
    # gets its own 3-retry + fallback-model loop, so one chunk's failure only
    # drops ~80 jobs to heuristic, not all 445.
    CHUNK_SIZE = 80
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

    if chunk_failures:
        stats["chunk_failures"] = chunk_failures

    # Any job not in any response → heuristic fallback (don't drop on the floor).
    for j in jobs:
        if j.content_hash[:16] in scored_ids:
            continue
        score = _heuristic_score(j)
        tier = _tier_from_score(score)
        out[j.content_hash] = RankedJob(
            content_hash=j.content_hash,
            score=score,
            tier=tier,
            reasoning="heuristic (LLM unavailable or omitted this job)",
            rubric_version="heuristic-v1",
            ranker_model="heuristic",
        )
        stats["placeholder"] += 1
        stats["by_tier"][tier.value] += 1

    logger.info("ranker: %s", stats)
    return out, stats


# ----- heuristic fallback -----


_HIGH_SIGNAL_TITLE_TERMS = (
    # English
    "ai product manager", "genai product manager", "ml product manager",
    "senior product manager", "lead product manager", "principal product manager",
    "head of product", "staff product manager", "product lead",
    # French
    "chef de produit senior", "responsable produit senior", "directeur produit",
    "directrice produit",
    # German (matches "Senior Produktmanager", "Leiter(in) Produktmanagement",
    # "Head of Produktmanagement" via substring on the lowercased title).
    "senior produktmanager", "leiter produktmanagement", "leiterin produktmanagement",
    "head of produktmanagement", "principal produktmanager",
    # Dutch
    "senior productmanager", "lead productmanager", "hoofd product",
    # Italian
    "responsabile di prodotto senior", "responsabile prodotto senior",
)
_MEDIUM_SIGNAL_TITLE_TERMS = (
    # English
    "product manager", "product owner",
    # French
    "chef de produit", "responsable produit",
    # German
    "produktmanager", "produkt manager", "product owner",
    # Dutch
    "productmanager", "product eigenaar",
    # Italian
    "responsabile di prodotto", "responsabile prodotto",
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

    Weights (sum to 1.0):
      title  0.6  — high-signal phrase 1.0, medium 0.6, else 0.3
      loc    0.3  — high-signal city/region in any of FR/DE/BE/CH = 1.0;
                   country-name only = 0.7; remote/hybrid = 0.7; else 0.4
      type   0.1  — CDI 1.0, Freelance 0.7, CDD 0.5, Unknown = 0.7 when
                   location is in a target country (German jobs report no
                   contract type but are still legitimate full-time roles)
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
    elif any(c in loc for c in _TARGET_COUNTRY_NAMES) or "remote" in loc or "hybrid" in loc:
        loc_s = 0.7
    else:
        loc_s = 0.4

    in_target_country = (
        loc_s >= 0.7  # i.e. we matched a city/country/remote pattern above
    )
    if contract == "cdi":
        type_s = 1.0
    elif contract == "freelance":
        type_s = 0.7
    elif contract == "cdd":
        type_s = 0.5
    elif contract in ("unknown", "") and in_target_country:
        # Non-FR jobs commonly report "Unknown" because the source doesn't
        # expose a French-shaped contract enum. Don't penalize them for that
        # — they are most likely permanent full-time roles.
        type_s = 0.7
    else:
        type_s = 0.3

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
