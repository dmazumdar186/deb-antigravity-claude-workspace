"""Front-door POST synthetic for cv_optimizer_v2 /api/optimize.

Exercises the full end-to-end path against the live Cloudflare Worker:
  POST https://cv-optimizer-api.debanjan186.workers.dev/api/optimize

Per ~/.claude/rules/front-door-synthetic.md:
  - Enters through the same door a real user would.
  - Validates the returned artifact (CVSpec JSON), not just HTTP 200.
  - Must pass 5 consecutive runs before the project can be called "working".

QUOTA GATE: This test is skipped by default to avoid burning the Gemini
free-tier (250 RPD / 15 RPM). Set CV_OPTIMIZE_LIVE=1 to opt in.

Usage:
    # dry run (skipped):
    py -m pytest tests/test_cv_optimizer_v2_front_door_optimize.py -v

    # live run (burns ~1 Gemini call):
    CV_OPTIMIZE_LIVE=1 py -m pytest tests/test_cv_optimizer_v2_front_door_optimize.py -v -s

Gemini quota handling:
    - HTTP 429 from the Worker → pytest.skip (degraded-state, not regression).
    - HTTP 502 (Gemini call failed) → hard FAIL (unexpected error).
    - HTTP 200 with invalid CVSpec → hard FAIL (contract regression).

Last verified live run: 2026-06-15 — HTTP 200, cv_spec keys present.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

import pytest
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

WORKSPACE = Path(__file__).resolve().parents[1]
load_dotenv(WORKSPACE / ".env")

WORKER_URL = "https://cv-optimizer-api.debanjan186.workers.dev"
OPTIMIZE_ENDPOINT = f"{WORKER_URL}/api/optimize"
FIXTURE_PATH = WORKSPACE / "tests" / "fixtures" / "cv_optimize_request.json"
ARTIFACT_PATH = WORKSPACE / "tests" / ".tmp" / "cv_optimizer_v2_synthetic_latest.json"

# Required top-level keys on a valid CVSpec response.
REQUIRED_CVSPEC_KEYS = {"summary", "experience", "skills"}

_LIVE = os.environ.get("CV_OPTIMIZE_LIVE", "").strip() == "1"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _load_worker_secret() -> str:
    secret = os.environ.get("WORKER_SECRET", "").strip()
    if not secret:
        pytest.skip("WORKER_SECRET not set in .env — cannot authenticate to Worker")
    return secret


def _post_optimize(payload: dict, secret: str, timeout: int = 60) -> tuple[int, dict | None, str]:
    """POST to /api/optimize. Returns (status, parsed_json_or_None, raw_body)."""
    body_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        OPTIMIZE_ENDPOINT,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "X-Worker-Secret": secret,
            "User-Agent": "front-door-synthetic/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read().decode("utf-8", errors="replace")
            try:
                return r.status, json.loads(raw), raw
            except json.JSONDecodeError:
                return r.status, None, raw
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", errors="replace") if e.fp else ""
        return e.code, None, raw
    except (urllib.error.URLError, TimeoutError, OSError) as e:
        return -1, None, f"{type(e).__name__}: {e}"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _LIVE, reason="Set CV_OPTIMIZE_LIVE=1 to run live (burns ~1 Gemini call)")
def test_optimize_returns_valid_cvspec():
    """POST /api/optimize with fixture CV+JD → HTTP 200, valid CVSpec artifact.

    Validations:
    1. HTTP 200 (not 4xx, not 502).
    2. Response body is valid JSON.
    3. CVSpec has required keys: summary (non-empty str), experience (non-empty list),
       skills (non-empty list).
    4. Artifact saved to tests/.tmp/cv_optimizer_v2_synthetic_latest.json.

    On HTTP 429 (Gemini quota exhausted): pytest.skip — degraded-state, not regression.
    """
    secret = _load_worker_secret()

    assert FIXTURE_PATH.exists(), f"Fixture not found: {FIXTURE_PATH}"
    payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    status, data, raw = _post_optimize(payload, secret)

    # --- Quota exhausted: degraded-state, not a regression ---
    if status == 429:
        try:
            err_body = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            err_body = {}
        reason = err_body.get("error", "quota_exhausted")
        pytest.skip(f"Gemini quota exhausted (HTTP 429 — {reason}). Resets ~09:00 Paris time.")

    # --- Network / infra failure ---
    assert status != -1, f"Network error reaching Worker: {raw}"

    # --- Hard failures: unexpected HTTP errors ---
    assert status == 200, (
        f"Expected HTTP 200 from /api/optimize, got {status}.\n"
        f"Body (first 500 chars): {raw[:500]}"
    )

    # --- Response must be JSON ---
    assert data is not None, (
        f"/api/optimize returned HTTP 200 but non-JSON body: {raw[:200]!r}"
    )

    # --- CVSpec contract: required top-level keys ---
    missing = REQUIRED_CVSPEC_KEYS - set(data.keys())
    assert not missing, (
        f"CVSpec missing required keys: {missing}\n"
        f"Returned keys: {sorted(data.keys())}\n"
        f"Body (first 500 chars): {raw[:500]}"
    )

    # --- summary must be a non-empty string ---
    summary = data.get("summary", "")
    assert isinstance(summary, str) and summary.strip(), (
        f"CVSpec.summary is empty or not a string: {summary!r}"
    )

    # --- experience must be a non-empty list ---
    experience = data.get("experience", [])
    assert isinstance(experience, list) and len(experience) > 0, (
        f"CVSpec.experience is empty or not a list: {experience!r}"
    )

    # --- skills must be a non-empty list ---
    skills = data.get("skills", [])
    assert isinstance(skills, list) and len(skills) > 0, (
        f"CVSpec.skills is empty or not a list: {skills!r}"
    )

    # --- Save artifact for inspection ---
    ARTIFACT_PATH.parent.mkdir(parents=True, exist_ok=True)
    ARTIFACT_PATH.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[synthetic] Artifact saved to {ARTIFACT_PATH}")
    print(f"[synthetic] summary[:120]: {summary[:120]!r}")
    print(f"[synthetic] experience entries: {len(experience)}")
    print(f"[synthetic] skills entries: {len(skills)}")


@pytest.mark.skipif(not _LIVE, reason="Set CV_OPTIMIZE_LIVE=1 to run live")
def test_optimize_rejects_missing_cv_text():
    """Confirm the Worker returns 400 when cv_text is absent (contract guard)."""
    secret = _load_worker_secret()
    status, data, raw = _post_optimize({"jd_text": "some jd", "skip_profile": True}, secret)
    assert status == 400, f"Expected 400 for missing cv_text, got {status}: {raw[:200]}"
    err = (data or {}).get("error", "")
    assert "cv_text" in err, f"Expected error key mentioning cv_text, got: {err!r}"


@pytest.mark.skipif(not _LIVE, reason="Set CV_OPTIMIZE_LIVE=1 to run live")
def test_optimize_rejects_missing_jd_text():
    """Confirm the Worker returns 400 when jd_text is absent (contract guard)."""
    secret = _load_worker_secret()
    status, data, raw = _post_optimize({"cv_text": "name: Test", "skip_profile": True}, secret)
    assert status == 400, f"Expected 400 for missing jd_text, got {status}: {raw[:200]}"
    err = (data or {}).get("error", "")
    assert "jd_text" in err, f"Expected error key mentioning jd_text, got: {err!r}"


@pytest.mark.skipif(not _LIVE, reason="Set CV_OPTIMIZE_LIVE=1 to run live")
def test_optimize_rejects_bad_secret():
    """Worker must return 401/403 when X-Worker-Secret is wrong."""
    status, _data, _raw = _post_optimize(
        {"cv_text": "test", "jd_text": "test", "skip_profile": True},
        secret="bad-secret-intentionally-wrong",
    )
    assert status in (401, 403), f"Expected 401 or 403 for bad secret, got {status}"
