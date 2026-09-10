"""
verify.py
description: Waterfall step 7 — verify the chosen email via MillionVerifier. Wraps
  execution/enrichment/million_verifier.py's verify_email() for live calls (imported, not
  subprocessed, per CONTRACTS.md); --mock reads this package's own fixtures so the enrich test suite
  has no dependency on execution/enrichment/'s unrelated mock dataset.
inputs: email str; mock: bool; fixtures_root: Path; api_key: str | None.
outputs: (email_status, cost_usd) tuple — email_status in {deliverable, risky, undeliverable, unknown}.
  Only an "ok"-class MillionVerifier result maps to "deliverable"; "catch_all" maps to "risky" and is
  never promoted to deliverable.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

COST_PER_CHECK_USD = 0.004

_REPO_ROOT = Path(__file__).resolve().parents[4]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_DELIVERABLE_RESULTS = {"ok", "deliverable", "valid"}
_UNDELIVERABLE_RESULTS = {"invalid", "disposable", "error", "unverifiable"}


def _classify(result: str | None) -> str:
    result = (result or "").lower()
    if result in _DELIVERABLE_RESULTS:
        return "deliverable"
    if result == "catch_all":
        return "risky"
    if result in _UNDELIVERABLE_RESULTS:
        return "undeliverable"
    return "unknown"


def _mock_result(email: str, fixtures_root: Path) -> dict:
    fixture_path = fixtures_root / "millionverifier" / "results.json"
    if not fixture_path.exists():
        return {"result": "unknown"}
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    return data.get(email, {"result": "unknown"})


def verify(email: str | None, *, mock: bool, fixtures_root: Path, api_key: str | None) -> tuple[str, float]:
    """Returns (email_status, cost_usd). Never raises — an API failure classifies as "unknown"."""
    if not email:
        return "unknown", 0.0

    if mock:
        result = _mock_result(email, fixtures_root)
        return _classify(result.get("result")), COST_PER_CHECK_USD

    if not api_key:
        return "unknown", 0.0

    from execution.enrichment.million_verifier import verify_email  # reuse the existing API function

    try:
        result = verify_email(email, api_key)
        return _classify(result.get("result")), COST_PER_CHECK_USD
    except Exception:  # noqa: BLE001 — a verifier outage must not crash the waterfall; classify unknown
        return "unknown", COST_PER_CHECK_USD
