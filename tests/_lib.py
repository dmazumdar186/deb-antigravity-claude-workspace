"""
description: Shared helpers for the test tiers. Pure functions, no test logic.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass


WORKER_URL = os.environ.get("WORKER_URL", "https://dental-receptionist.debanjan186.workers.dev")
RETELL_BASE = "https://api.retellai.com"
VAPI_BASE = "https://api.vapi.ai"
CALCOM_BASE = "https://api.cal.com/v2"


def env(name: str) -> str | None:
    v = os.environ.get(name)
    return v.strip().strip('"') if v else None


def http(method: str, url: str, *, body: dict | None = None,
         headers: dict | None = None, timeout: int = 20) -> tuple[int, str]:
    """Return (status_code, body_text). Does not raise on non-2xx."""
    data = json.dumps(body).encode("utf-8") if body is not None else None
    hdrs = {"User-Agent": "dental-receptionist-tests/1.0"}
    if headers:
        hdrs.update(headers)
    if data is not None and "Content-Type" not in hdrs:
        hdrs["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, r.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        return 0, f"URLError: {exc}"


def http_json(method: str, url: str, **kw) -> tuple[int, dict | None]:
    code, body = http(method, url, **kw)
    try:
        return code, json.loads(body)
    except json.JSONDecodeError:
        return code, None


def vapi_tool_payload(tool_name: str, args: dict) -> dict:
    """Mirrors Vapi's webhook payload shape for /vapi/tools/* endpoints."""
    return {
        "message": {
            "toolCalls": [
                {
                    "id": "tc_test",
                    "function": {"name": tool_name, "arguments": json.dumps(args)},
                }
            ]
        }
    }


def retell_tool_payload(args: dict) -> dict:
    """Retell sends args-only body for tools with Payload:args-only enabled."""
    return args


def all_ascii(s: str) -> bool:
    """True if every byte in the UTF-8 encoding is < 128."""
    return all(b < 128 for b in s.encode("utf-8"))
