"""
psi.py
description: PageSpeed Insights v5 wrapper — mobile/desktop performance score + mobile-friendliness.
inputs: Imported by audit_site.py; optional PAGESPEED_API_KEY (keyless works at low volume, per PROJECT_SPEC.md).
outputs: PsiResult dataclass — no filesystem writes (caller persists via Store).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from threading import Lock
from typing import Any

from execution.personal_workflows.prodcraft_medspa.common import http

PSI_ENDPOINT = "https://www.googleapis.com/pagespeedonline/v5/runPagespeed"
MIN_INTERVAL_SECONDS = 1.0  # throttle <= 1 req/s across all callers/threads
MAX_RETRIES = 2

_throttle_lock = Lock()
_last_call_at = 0.0


def _throttle() -> None:
    global _last_call_at
    with _throttle_lock:
        wait = MIN_INTERVAL_SECONDS - (time.monotonic() - _last_call_at)
        if wait > 0:
            time.sleep(wait)
        _last_call_at = time.monotonic()


@dataclass
class PsiResult:
    performance_score: int | None
    is_mobile_friendly: bool | None
    raw: dict[str, Any] = field(default_factory=dict)
    reason: str | None = None


def run_pagespeed(url: str, strategy: str, api_key: str | None = None) -> PsiResult:
    """Call PSI v5 for `url` at `strategy` ('mobile'|'desktop'). Throttled to <=1 req/s.

    On 429/5xx: retry twice with backoff, then return PsiResult(None, None, reason=...).
    Never raises.
    """
    params = {"url": url, "strategy": strategy, "category": "PERFORMANCE"}
    if api_key:
        params["key"] = api_key

    last_reason = "unknown"
    for attempt in range(MAX_RETRIES + 1):
        _throttle()
        try:
            resp = http.get(PSI_ENDPOINT, params=params, timeout=30)
        except Exception as exc:  # noqa: BLE001 — network failure, retry loop handles it
            last_reason = f"request error: {exc}"
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            return PsiResult(None, None, reason=last_reason)

        if resp.status_code in (429, 500, 502, 503, 504):
            last_reason = f"http {resp.status_code}"
            if attempt < MAX_RETRIES:
                time.sleep(2**attempt)
                continue
            return PsiResult(None, None, reason=last_reason)

        if resp.status_code >= 400:
            return PsiResult(None, None, raw={}, reason=f"http {resp.status_code}")

        try:
            data = resp.json()
        except ValueError:
            return PsiResult(None, None, reason="invalid json")

        return _parse_psi_response(data)

    return PsiResult(None, None, reason=last_reason)


def _parse_psi_response(data: dict) -> PsiResult:
    lighthouse = data.get("lighthouseResult") or {}
    categories = lighthouse.get("categories") or {}
    performance = categories.get("performance") or {}
    perf_score = performance.get("score")
    performance_score = round(perf_score * 100) if isinstance(perf_score, (int, float)) else None

    audits = lighthouse.get("audits") or {}
    viewport_audit = audits.get("viewport") or {}
    viewport_score = viewport_audit.get("score")
    is_mobile_friendly = bool(viewport_score == 1) if viewport_score is not None else None

    return PsiResult(performance_score=performance_score, is_mobile_friendly=is_mobile_friendly, raw=data)
