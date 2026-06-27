"""
description: Generate a synthetic labeled gold-set for evaluating the
    profile-grounded ranker. Uses Gemini 2.5 Flash + profile.json to construct
    30 jobs across three expected-label buckets:
      - 10 EXPECTED_TIER=A jobs ("perfect fit" — should rank as A)
      - 10 EXPECTED_TIER=B jobs ("promising but not exact" — should rank as B)
      - 10 EXPECTED_TIER=SKIP jobs ("not the operator's target" — should rank
        as SKIP)
    Each job carries a 1-sentence rationale tied to specific profile fields so
    the operator can audit AND edit the JSON if a label is wrong. Editing the
    JSON by hand IS the audit handle — no model judgment is final.

inputs:
    - profile/profile.json (the ground truth used to construct jobs)
    - GEMINI_API_KEY in env
    - CLI: --out PATH (default: tests/fixtures/eval_gold_set.json),
           --per-bucket N (default: 10), --dry-run

outputs:
    - eval_gold_set.json with schema:
        {
          "schema_version": "1.0",
          "generated_at": ISO-8601 UTC,
          "profile_generated_at": ISO from profile.json,
          "items": [
            {
              "expected_tier": "A" | "B" | "SKIP",
              "expected_track": "A" | "B" | null,  # null for SKIP
              "rationale": str,
              "title": str, "company": str, "location": str,
              "contract_type": "cdi"|"freelance"|"cdd"|"unknown",
              "remote_mode": "remote"|"hybrid"|"onsite"|"unknown",
              "description": str (200-500 chars)
            },
          ]
        }

Why synthetic: building a real labeled set requires operator hand-tagging 30
jobs. That's the exact work you said this script should replace. Synthetic
jobs grounded in profile.json + reviewable JSON give the same audit handle
without the upfront ask.

Limitations (honest gaps for the operator):
    - Synthetic jobs are LLM-described; real JDs have noisier text. Real-world
      precision will deviate from this floor. To get a real-world number, run
      `evaluate_ranker.py --against-sheet` which scores the live sheet's
      recent rows (no labels — only old-vs-new tier delta).
    - The generator's labels carry the generator's biases. Always read the
      JSON and flip any label you disagree with before trusting the metrics.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import find_dotenv, load_dotenv

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("profile.generate_eval_set")

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
PROFILE_PATH = Path(__file__).resolve().parent / "profile.json"
DEFAULT_OUT = WORKSPACE_ROOT / "tests" / "fixtures" / "eval_gold_set.json"


ITEM_SCHEMA = {
    "type": "object",
    "properties": {
        "expected_tier": {"type": "string", "enum": ["A", "B", "SKIP"]},
        "expected_track": {"type": "string"},
        "rationale": {"type": "string"},
        "title": {"type": "string"},
        "company": {"type": "string"},
        "location": {"type": "string"},
        "contract_type": {"type": "string"},
        "remote_mode": {"type": "string"},
        "description": {"type": "string"},
    },
    "required": ["expected_tier", "expected_track", "rationale", "title",
                 "company", "location", "contract_type", "remote_mode",
                 "description"],
}

BUCKET_SCHEMA = {
    "type": "object",
    "properties": {
        "items": {"type": "array", "items": ITEM_SCHEMA},
    },
    "required": ["items"],
}


_BUCKET_BRIEFS = {
    "A": (
        "PERFECT-FIT jobs. Each should be UNDENIABLY tier A given the profile. "
        "Mix half Track A (Permanent AI PM CDI in Paris/remote-EU at AI-native or "
        "AI-heavy companies, mentioning RAG/LLM/multi-agent/eval/GDPR/PRD/GTM, "
        "Senior or above) and half Track B (Freelance/Mission AI Automation, "
        "Cloudflare Workers + n8n + Claude Code + cold email + Instantly/GHL + "
        "TJM, Paris area or remote-EU). Title MUST appear (or be a near-literal "
        "variant) in profile.tracks[X].targeted_titles. Location MUST be in "
        "profile.locations.preferred or ok_remote. Contract MUST match the "
        "track's contract_types. Description (200-500 chars) MUST namedrop at "
        "least 5 profile skills (use the exact skill names from profile.skills) "
        "and at least one proof-point-adjacent metric (e.g. '+40% adoption', "
        "'<30 day ship cycle')."
    ),
    "B": (
        "PROMISING-BUT-NOT-PERFECT jobs. Each should be tier B — right role "
        "family, but one or two signals weaken the fit. Mix scenarios: "
        "(1) Senior PM at a NON-AI Paris SaaS (no LLM/RAG mention), CDI; "
        "(2) Generic Python automation freelance mission in Paris (no Claude/"
        "Cloudflare named explicitly); (3) AI Engineer (not AI PM) CDI in "
        "Paris with strong AI focus but lacks the PM framing of Track A; "
        "(4) Remote-EU Senior PM at AI scale-up but country is Spain/Italy "
        "(language risk); (5) Freelance AI consultant at a non-tech firm "
        "(legal/insurance/banking) Paris. Description should mention 2-4 "
        "profile skills but be missing the strongest signal for the track."
    ),
    "SKIP": (
        "OFF-PROFILE jobs. Each should be tier SKIP. Use a mix: "
        "(1) Cybersecurity Analyst Paris CDI; (2) Junior/Intern/Alternance AI "
        "role (any title prefix matching profile.hard_filters.skip_title_substrings); "
        "(3) Senior PM in NEW YORK / SAN FRANCISCO / BANGALORE CDI (blocked "
        "country); (4) Senior PM in Munich/Berlin with a German-only JD ('Wir "
        "suchen einen erfahrenen...'); (5) Comptable / Accountant / SEO "
        "Specialist Paris (off-domain); (6) Marketing PM at a luxury brand "
        "(off-skill); (7) Chef de Projet (anti_title); (8) Senior Backend "
        "Engineer (Java/Spring) with NO AI mention Paris CDI; (9) Mid-level "
        "AI Engineer Paris CDI at <2 yrs xp (seniority fail); (10) Pure data "
        "analyst BI / Power BI / Tableau Paris (off-skill)."
    ),
}


def _build_prompt(profile_json: str, bucket: str, n: int) -> str:
    brief = _BUCKET_BRIEFS[bucket]
    return (
        "You will generate a labeled JSON test set for a job-matching ranker.\n\n"
        f"Bucket: expected_tier='{bucket}', count={n}.\n\n"
        f"Bucket brief: {brief}\n\n"
        "Each item must include:\n"
        "- expected_tier: '" + bucket + "' (exactly)\n"
        "- expected_track: 'A' or 'B' for tier A/B items; 'A' (placeholder, "
        "harmless) for SKIP items\n"
        "- rationale: 1 short sentence citing the SPECIFIC profile field that "
        "drives the expected label (e.g. 'matches profile.tracks[A]."
        "targeted_titles + Paris in profile.locations.preferred + CDI in "
        "contract_types' OR 'cybersecurity is in skip_title_substrings — fail')\n"
        "- title, company, location, contract_type (one of: cdi, freelance, "
        "cdd, unknown), remote_mode (one of: remote, hybrid, onsite, unknown), "
        "description (200-500 chars, realistic JD voice)\n\n"
        "Diversity rule: vary companies, locations within the constraint, and "
        "contract types within the allowed set. Avoid stylistic repetition.\n\n"
        f"=== PROFILE (ground truth) ===\n{profile_json}\n\n"
        "Emit JSON now matching the response schema."
    )


_SYSTEM = (
    "You are constructing labeled test data for a job-matching ranker eval. "
    "Output STRICT JSON matching the response schema. Each generated job MUST "
    "be consistent with its expected_tier label — if a tier-A job's description "
    "doesn't actually match the profile strongly, the entire eval becomes "
    "noise. Treat the profile JSON as authoritative and ground every choice in "
    "specific fields."
)


def _call_gemini(client, profile_json: str, bucket: str, n: int) -> list[dict]:
    from google.genai import types
    cfg = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        response_mime_type="application/json",
        response_schema=BUCKET_SCHEMA,
        temperature=0.4,  # slight variety; not so hot it drifts off-label
        max_output_tokens=15000,
    )
    # Try gemini-2.5-flash first; on 429 (daily-quota) fall through to -lite
    # which has a higher free-tier RPD ceiling. The eval generator is one-shot
    # so we don't need the higher-quality model for synthetic JD prose.
    last_exc: Exception | None = None
    for model_name in ("gemini-2.5-flash", "gemini-2.5-flash-lite"):
        try:
            resp = client.models.generate_content(
                model=model_name, contents=_build_prompt(profile_json, bucket, n),
                config=cfg,
            )
            last_exc = None
            break
        except Exception as exc:  # noqa: BLE001 — Gemini surface
            last_exc = exc
            msg = str(exc)
            if "429" not in msg and "RESOURCE_EXHAUSTED" not in msg:
                raise
            logger.warning("eval-gen: %s 429'd — falling back to next model",
                           model_name)
    if last_exc is not None:
        raise last_exc
    data = json.loads(resp.text or "{}")
    items = data.get("items", [])
    # Hard-set expected_tier on every item (the model occasionally drifts).
    for it in items:
        it["expected_tier"] = bucket
        if bucket == "SKIP":
            it["expected_track"] = "A"  # placeholder; ignored for SKIP scoring
    return items


def generate_eval_set(
    out_path: Path,
    *,
    per_bucket: int = 10,
    dry_run: bool = False,
) -> dict:
    if not PROFILE_PATH.exists():
        raise FileNotFoundError(
            f"profile.json missing at {PROFILE_PATH} — generate it first."
        )

    profile_json = PROFILE_PATH.read_text(encoding="utf-8")
    profile_data = json.loads(profile_json)
    profile_generated_at = profile_data.get("generated_at", "unknown")

    out = {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "profile_generated_at": profile_generated_at,
        "items": [],
    }

    if dry_run:
        for bucket in ("A", "B", "SKIP"):
            for i in range(per_bucket):
                out["items"].append({
                    "expected_tier": bucket,
                    "expected_track": "A" if bucket == "SKIP" else "A",
                    "rationale": f"dry-run stub #{i}",
                    "title": f"Stub {bucket} {i}",
                    "company": "StubCo",
                    "location": "Paris",
                    "contract_type": "cdi",
                    "remote_mode": "hybrid",
                    "description": "Stub description for dry-run." * 6,
                })
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        logger.info("dry-run eval set written: %s (%d items)", out_path,
                    len(out["items"]))
        return out

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError("GEMINI_API_KEY missing — set it in .env")

    from google import genai
    client = genai.Client(api_key=api_key)

    for bucket in ("A", "B", "SKIP"):
        logger.info("generating bucket=%s n=%d", bucket, per_bucket)
        items = _call_gemini(client, profile_json, bucket, per_bucket)
        if len(items) != per_bucket:
            logger.warning("bucket=%s: model returned %d items (expected %d)",
                           bucket, len(items), per_bucket)
        out["items"].extend(items)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                        encoding="utf-8")
    logger.info("eval set written: %s (%d items)", out_path, len(out["items"]))
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--per-bucket", type=int, default=10)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    try:
        generate_eval_set(args.out, per_bucket=args.per_bucket,
                          dry_run=args.dry_run)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("generation failed: %s", exc)
        return 1
    print(f"OK -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
