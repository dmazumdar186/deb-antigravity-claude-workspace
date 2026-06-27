"""
description: Extract a structured operator profile from real artifacts (CV PDF +
    LinkedIn .md + brand strategy + canonical metrics + workspace project signals)
    and emit profile.json. The ranker reads profile.json so every job match is
    anchored to a verifiable skill-and-evidence set rather than a frozen prose
    rubric. Auditable: open the JSON, confirm "yes this is me / no this is wrong"
    in 60 seconds.

inputs:
    - CLI args: --cv PATH (default: workspace root "CV MAZUMDAR Debanjan EN.pdf"),
                --out PATH (default: profile/profile.json), --dry-run
    - Reads (paths resolved from workspace root):
        * CV PDF (pypdf-extracted text)
        * execution/personal_workflows/personal_brand/linkedin_profile.md
        * execution/personal_workflows/personal_brand/brand_strategy.md
        * execution/personal_workflows/personal_brand/metrics_canonical.md
        * directives/personal_workflows/*.md (project signals — shipped systems)
    - env: GEMINI_API_KEY (free tier; failure mode is hard-fail with clear msg)

outputs:
    - profile.json with schema:
        {
          "schema_version": "1.0",
          "generated_at": ISO-8601 UTC,
          "tracks": [
            {
              "id": "A" | "B",
              "title": "Permanent AI PM (CDI)" | "Freelance AI Automation ...",
              "targeted_titles": [str, ...],   # exact + adjacent title forms
              "anti_titles": [str, ...],       # SKIP-on-match
              "contract_types": ["cdi"|"freelance"|"contract"|"mission"],
              "min_seniority": "senior"|"lead"|"principal"|"head",
            },
          ],
          "skills": [
            {
              "name": str, "level": "expert"|"strong"|"familiar",
              "evidence": [str, ...],        # 1-3 short proof points
              "tracks": ["A"]|["B"]|["A","B"],
            },
          ],
          "domains": [str, ...],
          "languages": [{"code": "en"|"fr", "level": "C2"|...}],
          "locations": {
            "preferred": [str, ...],         # Paris, Île-de-France, ...
            "ok_remote": [str, ...],         # remote-EU, remote-FR, ...
            "blocked_countries": [str, ...], # US, India, APAC, ...
          },
          "hard_filters": {
            "skip_title_substrings": [str, ...],
            "skip_description_substrings": [str, ...],
            "skip_seniority": ["junior", "intern", "alternance", ...],
          },
          "proof_points": [                  # for the ranker's "did they ship X?" reasoning
            {"system": str, "metric": str, "track": "A"|"B"},
          ],
          "raw_source_paths": [str, ...],    # audit trail
        }

Notes:
    - Gemini 2.5 Flash is the judge. Strict JSON-schema output. Temperature 0.1.
    - The script does NOT call the ranker. It produces the artifact the ranker
      then reads. Decoupled so you can audit/edit profile.json by hand.
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
logger = logging.getLogger("profile.extract")

WORKSPACE_ROOT = Path(__file__).resolve().parents[4]
DEFAULT_CV = WORKSPACE_ROOT / "CV MAZUMDAR Debanjan EN.pdf"
PERSONAL_BRAND_DIR = WORKSPACE_ROOT / "execution" / "personal_workflows" / "personal_brand"
DIRECTIVES_PW_DIR = WORKSPACE_ROOT / "directives" / "personal_workflows"
DEFAULT_OUT = Path(__file__).resolve().parent / "profile.json"


PROFILE_SCHEMA = {
    "type": "object",
    "properties": {
        "schema_version": {"type": "string"},
        "generated_at": {"type": "string"},
        "tracks": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string", "enum": ["A", "B"]},
                    "title": {"type": "string"},
                    "targeted_titles": {"type": "array", "items": {"type": "string"}},
                    "anti_titles": {"type": "array", "items": {"type": "string"}},
                    "contract_types": {"type": "array", "items": {"type": "string"}},
                    "min_seniority": {"type": "string"},
                },
                "required": ["id", "title", "targeted_titles", "anti_titles",
                             "contract_types", "min_seniority"],
            },
        },
        "skills": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "level": {"type": "string", "enum": ["expert", "strong", "familiar"]},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "tracks": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name", "level", "evidence", "tracks"],
            },
        },
        "domains": {"type": "array", "items": {"type": "string"}},
        "languages": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "code": {"type": "string"},
                    "level": {"type": "string"},
                },
                "required": ["code", "level"],
            },
        },
        "locations": {
            "type": "object",
            "properties": {
                "preferred": {"type": "array", "items": {"type": "string"}},
                "ok_remote": {"type": "array", "items": {"type": "string"}},
                "blocked_countries": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["preferred", "ok_remote", "blocked_countries"],
        },
        "hard_filters": {
            "type": "object",
            "properties": {
                "skip_title_substrings": {"type": "array", "items": {"type": "string"}},
                "skip_description_substrings": {"type": "array", "items": {"type": "string"}},
                "skip_seniority": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["skip_title_substrings", "skip_description_substrings",
                         "skip_seniority"],
        },
        "proof_points": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "system": {"type": "string"},
                    "metric": {"type": "string"},
                    "track": {"type": "string"},
                },
                "required": ["system", "metric", "track"],
            },
        },
        "raw_source_paths": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["schema_version", "generated_at", "tracks", "skills", "domains",
                 "languages", "locations", "hard_filters", "proof_points",
                 "raw_source_paths"],
}


def _read_cv_pdf(path: Path) -> str:
    """Extract CV text via pypdf."""
    import pypdf

    reader = pypdf.PdfReader(str(path))
    parts: list[str] = []
    for page in reader.pages:
        try:
            parts.append(page.extract_text() or "")
        except (ValueError, KeyError) as exc:
            # Per python-hardening rule #5: never bare except. Log specific
            # PDF-extraction failures so a corrupt page surfaces.
            logger.warning("CV PDF page extraction failed: %s", exc)
    return "\n".join(parts).strip()


def _read_text(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _collect_project_signals(limit_files: int = 12) -> list[tuple[str, str]]:
    """Pull short signal blurbs from directives/personal_workflows/*.md. These
    are the project descriptions you've ACTUALLY shipped — the ground truth for
    'what kind of builder are you'.

    Returns: list of (relative_path, first 1200 chars) pairs.
    """
    out: list[tuple[str, str]] = []
    if not DIRECTIVES_PW_DIR.exists():
        return out
    md_files = sorted(DIRECTIVES_PW_DIR.glob("*.md"))[:limit_files]
    for p in md_files:
        try:
            txt = p.read_text(encoding="utf-8", errors="replace")[:1200]
            out.append((str(p.relative_to(WORKSPACE_ROOT)).replace("\\", "/"), txt))
        except OSError as exc:
            logger.warning("project signal read failed for %s: %s", p, exc)
    return out


def _build_prompt(cv_text: str, linkedin_md: str, brand_strategy_md: str,
                  metrics_md: str, project_signals: list[tuple[str, str]]) -> str:
    """Assemble the extractor user message. The system instruction lives in
    _SYSTEM and tells the model what schema to emit."""
    proj_block = "\n\n".join(
        f"### Project signal: {rel}\n{txt}" for rel, txt in project_signals
    )
    return (
        "Extract a structured operator profile by reading the artifacts below.\n\n"
        "Anchoring rules:\n"
        "- ONLY include skills/proof-points that appear (literally or paraphrased) "
        "in at least one source below. No hallucinated capabilities.\n"
        "- Two tracks already defined by the operator: Track A = Permanent AI PM "
        "(CDI), Track B = Freelance AI Automation / Claude Code / React Native. "
        "Map every skill to the track(s) it serves.\n"
        "- 'Level' calibration: expert = repeatedly shipped with measurable "
        "outcome cited; strong = shipped at least once with description; "
        "familiar = mentioned as adjacent / 'comfortable with'.\n"
        "- Languages: only EN + FR are valid for job-matching. Hindi/Bengali "
        "etc are personal but NOT job-relevant — include in `languages` but mark "
        "level honestly.\n"
        "- `proof_points`: extract 6-12 of the most concrete shipped-system + "
        "outcome pairs from the canonical metrics sheet.\n"
        "- `hard_filters`: derive from anti-signals across the artifacts "
        "(e.g. brand strategy says 'NOT chef de projet'; CV implies senior+; "
        "metrics rules out US/APAC).\n\n"
        f"=== CV (PDF, extracted) ===\n{cv_text}\n\n"
        f"=== LinkedIn profile ===\n{linkedin_md}\n\n"
        f"=== Brand strategy ===\n{brand_strategy_md}\n\n"
        f"=== Canonical metrics (single source of truth) ===\n{metrics_md}\n\n"
        f"=== Workspace project signals (shipped systems) ===\n{proj_block}\n\n"
        "Emit the profile JSON now. schema_version must be '1.0'."
    )


_SYSTEM = (
    "You are extracting a structured candidate profile for a job-matching ranker. "
    "Output STRICT JSON matching the response schema. No prose, no markdown, no "
    "explanations outside the schema. Every claim must be grounded in the source "
    "artifacts — if a skill is not in any artifact, do NOT invent it."
)


def extract_profile(
    cv_path: Path,
    out_path: Path,
    *,
    dry_run: bool = False,
) -> dict:
    """Run the extraction. Returns the profile dict; also writes to out_path."""
    if not cv_path.exists():
        raise FileNotFoundError(f"CV not found at {cv_path}")

    api_key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY missing from env. The extractor is one-shot — "
            "set it in .env and re-run (no Sheets-fallback for this script)."
        )

    logger.info("reading CV: %s", cv_path)
    cv_text = _read_cv_pdf(cv_path)
    logger.info("CV chars=%d", len(cv_text))

    linkedin = _read_text(PERSONAL_BRAND_DIR / "linkedin_profile.md")
    brand = _read_text(PERSONAL_BRAND_DIR / "brand_strategy.md")
    metrics = _read_text(PERSONAL_BRAND_DIR / "metrics_canonical.md")
    projects = _collect_project_signals()
    logger.info("loaded brand artifacts: linkedin=%d brand=%d metrics=%d projects=%d",
                len(linkedin), len(brand), len(metrics), len(projects))

    user_msg = _build_prompt(cv_text, linkedin, brand, metrics, projects)

    if dry_run:
        # No LLM call — emit the prompt + a stub profile so the wiring can be
        # tested without burning Gemini quota. Useful for unit tests.
        out = {
            "schema_version": "1.0",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tracks": [], "skills": [], "domains": [], "languages": [],
            "locations": {"preferred": [], "ok_remote": [], "blocked_countries": []},
            "hard_filters": {"skip_title_substrings": [],
                             "skip_description_substrings": [], "skip_seniority": []},
            "proof_points": [],
            "raw_source_paths": [
                str(cv_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
                "execution/personal_workflows/personal_brand/linkedin_profile.md",
                "execution/personal_workflows/personal_brand/brand_strategy.md",
                "execution/personal_workflows/personal_brand/metrics_canonical.md",
            ] + [rel for rel, _ in projects],
            "_dry_run": True,
            "_prompt_chars": len(user_msg),
        }
        out_path.write_text(json.dumps(out, indent=2, ensure_ascii=False),
                            encoding="utf-8")
        logger.info("dry-run profile written: %s (prompt %d chars)",
                    out_path, len(user_msg))
        return out

    from google import genai
    from google.genai import types

    client = genai.Client(api_key=api_key)
    cfg = types.GenerateContentConfig(
        system_instruction=_SYSTEM,
        response_mime_type="application/json",
        response_schema=PROFILE_SCHEMA,
        temperature=0.1,
        max_output_tokens=12000,
    )
    logger.info("calling gemini-2.5-flash (prompt %d chars)", len(user_msg))
    resp = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=user_msg,
        config=cfg,
    )
    raw = resp.text or "{}"
    try:
        profile = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Gemini returned invalid JSON: {exc}\n{raw[:500]}") from exc

    # Stamp post-hoc fields (override whatever the model produced).
    profile["schema_version"] = "1.0"
    profile["generated_at"] = datetime.now(timezone.utc).isoformat()
    profile["raw_source_paths"] = [
        str(cv_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "execution/personal_workflows/personal_brand/linkedin_profile.md",
        "execution/personal_workflows/personal_brand/brand_strategy.md",
        "execution/personal_workflows/personal_brand/metrics_canonical.md",
    ] + [rel for rel, _ in projects]

    out_path.write_text(
        json.dumps(profile, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info("profile written: %s (%d skills, %d proof_points)",
                out_path, len(profile.get("skills", [])),
                len(profile.get("proof_points", [])))
    return profile


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--cv", type=Path, default=DEFAULT_CV,
                        help=f"Path to CV PDF (default: {DEFAULT_CV})")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT,
                        help=f"Output JSON path (default: {DEFAULT_OUT})")
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip the LLM call; write a stub profile.")
    args = parser.parse_args()

    try:
        extract_profile(args.cv, args.out, dry_run=args.dry_run)
    except (FileNotFoundError, RuntimeError) as exc:
        logger.error("extraction failed: %s", exc)
        return 1
    print(f"OK -> {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
