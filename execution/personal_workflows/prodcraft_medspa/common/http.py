"""
http.py
description: Shared requests.Session with retry/backoff and a fixed timeout, plus a stable User-Agent.
inputs: Imported by discovery/, audit/, enrich/, preview/ scripts; no CLI args (importable module).
outputs: A configured requests.Session and get()/post() wrappers.
"""

from __future__ import annotations

from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "ProdCraftAuditBot/1.0 (+https://prodcraft.fyi/bot)"
DEFAULT_TIMEOUT = 20


def session() -> requests.Session:
    """A requests.Session with retries (3x, 1s backoff, 429/500/502/503/504) and the bot UA."""
    s = requests.Session()
    retry = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=None,  # retry on all methods, including POST (idempotent calls only)
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    s.headers.update({"User-Agent": USER_AGENT})
    return s


_SHARED = session()


def get(url: str, **kw: Any) -> requests.Response:
    """GET with the shared retry session and a 20s default timeout."""
    kw.setdefault("timeout", DEFAULT_TIMEOUT)
    return _SHARED.get(url, **kw)


def post(url: str, **kw: Any) -> requests.Response:
    """POST with the shared retry session and a 20s default timeout."""
    kw.setdefault("timeout", DEFAULT_TIMEOUT)
    return _SHARED.post(url, **kw)
