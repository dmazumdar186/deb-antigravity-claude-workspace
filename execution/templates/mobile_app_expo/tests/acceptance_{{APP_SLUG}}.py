"""
description: Acceptance gate for {{APP_SLUG}} — hits the paired backend's /api/health and asserts the response contract the mobile app depends on. HARD-FAILS on any deviation. Runs pre-EAS-build in CI (preflight.yml).
inputs: API_BASE_URL env var (defaults to http://localhost:8787). Optional --verbose flag.
outputs: exit 0 on PASS, exit 1 on FAIL with per-check details on stderr.
usage:
    API_BASE_URL=https://{{APP_SLUG}}-api.example.workers.dev py tests/acceptance_{{APP_SLUG}}.py
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request

DEFAULT_BASE = "http://localhost:8787"
TIMEOUT_S = 10
MAX_LATENCY_MS = 2000  # /api/health should be well under this.


def _get_json(url: str, timeout: int = TIMEOUT_S) -> tuple[dict, int, int]:
    """Return (body_json, http_status, latency_ms). Raises on network error."""
    start = time.time()
    req = urllib.request.Request(url, headers={"User-Agent": "acceptance-gate/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8", errors="replace")
        status = resp.status
    latency_ms = int((time.time() - start) * 1000)
    try:
        body = json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"non-JSON response: {raw[:200]!r}") from e
    if not isinstance(body, dict):
        raise ValueError(f"expected JSON object, got {type(body).__name__}")
    return body, status, latency_ms


def check_health(base_url: str, verbose: bool) -> list[str]:
    """Return list of failure strings. Empty = PASS."""
    failures: list[str] = []
    url = base_url.rstrip("/") + "/api/health"

    try:
        body, status, latency_ms = _get_json(url)
    except (urllib.error.URLError, urllib.error.HTTPError, ValueError, TimeoutError) as e:
        return [f"GET {url} failed: {e.__class__.__name__}: {e}"]

    if verbose:
        print(f"  GET {url} -> {status} in {latency_ms}ms")
        print(f"  body: {json.dumps(body, indent=2)}")

    # Contract assertions — these MUST match src/services/api.ts::HealthResponse.
    if status != 200:
        failures.append(f"expected HTTP 200, got {status}")

    if latency_ms > MAX_LATENCY_MS:
        failures.append(f"latency {latency_ms}ms > threshold {MAX_LATENCY_MS}ms")

    if "ok" not in body:
        failures.append("response missing 'ok' key")
    elif body["ok"] is not True:
        failures.append(f"expected ok=True, got ok={body['ok']!r}")

    if "version" not in body:
        failures.append("response missing 'version' key")
    elif not isinstance(body["version"], str) or not body["version"]:
        failures.append(f"expected non-empty string 'version', got {body['version']!r}")

    if "ts" not in body:
        failures.append("response missing 'ts' key")
    elif not isinstance(body["ts"], (int, float)):
        failures.append(f"expected numeric 'ts', got {type(body['ts']).__name__}")

    return failures


def main() -> int:
    parser = argparse.ArgumentParser(description="{{APP_SLUG}} acceptance gate")
    parser.add_argument("--base-url", default=os.getenv("API_BASE_URL", DEFAULT_BASE))
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    print(f"[acceptance] target: {args.base_url}")
    failures = check_health(args.base_url, args.verbose)

    if failures:
        print(f"[acceptance] FAIL ({len(failures)} issue(s)):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1

    print("[acceptance] PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
