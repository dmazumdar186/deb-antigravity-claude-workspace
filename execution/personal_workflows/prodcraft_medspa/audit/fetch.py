"""
fetch.py
description: Fetch a business website's HTML, following redirects and recording SSL validity.
inputs: Imported by audit_site.py; no CLI args (importable module).
outputs: FetchResult dataclass — no filesystem writes (caller persists via Store).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import requests

from execution.personal_workflows.prodcraft_medspa.common import http

REQUEST_TIMEOUT = 20


@dataclass
class FetchResult:
    final_url: str | None
    status: int | None
    html: str | None
    has_website: bool
    has_ssl: bool | None
    ssl_error: str | None
    redirect_chain: list[str] = field(default_factory=list)
    elapsed_ms: int = 0
    error: str | None = None


def _redirect_chain(response: requests.Response) -> list[str]:
    return [r.url for r in response.history] + [response.url]


def fetch_site(url: str) -> FetchResult:
    """Fetch `url`, following redirects. Never raises — all failure modes land in FetchResult."""
    if not url:
        return FetchResult(
            final_url=None,
            status=None,
            html=None,
            has_website=False,
            has_ssl=None,
            ssl_error=None,
            error="no url",
        )

    start = time.monotonic()
    try:
        resp = http.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        elapsed_ms = int((time.monotonic() - start) * 1000)

        if resp.status_code >= 400:
            return FetchResult(
                final_url=resp.url,
                status=resp.status_code,
                html=None,
                has_website=False,
                has_ssl=resp.url.startswith("https://") if resp.url else None,
                ssl_error=None,
                redirect_chain=_redirect_chain(resp),
                elapsed_ms=elapsed_ms,
                error=f"http {resp.status_code}",
            )

        has_ssl = resp.url.startswith("https://") if resp.url else False
        return FetchResult(
            final_url=resp.url,
            status=resp.status_code,
            html=resp.text,
            has_website=True,
            has_ssl=has_ssl,
            ssl_error=None,
            redirect_chain=_redirect_chain(resp),
            elapsed_ms=elapsed_ms,
        )

    except requests.exceptions.SSLError as exc:
        # Cert invalid/expired/self-signed: retry once with verify=False so we can still
        # read the HTML for the rest of the audit, but always record has_ssl=False.
        try:
            resp = http.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True, verify=False)
            elapsed_ms = int((time.monotonic() - start) * 1000)
            html = resp.text if resp.status_code < 400 else None
            return FetchResult(
                final_url=resp.url,
                status=resp.status_code,
                html=html,
                has_website=resp.status_code < 400,
                has_ssl=False,
                ssl_error=str(exc),
                redirect_chain=_redirect_chain(resp),
                elapsed_ms=elapsed_ms,
                error=None if resp.status_code < 400 else f"http {resp.status_code}",
            )
        except requests.exceptions.RequestException as exc2:
            elapsed_ms = int((time.monotonic() - start) * 1000)
            return FetchResult(
                final_url=None,
                status=None,
                html=None,
                has_website=False,
                has_ssl=False,
                ssl_error=str(exc),
                elapsed_ms=elapsed_ms,
                error=str(exc2),
            )

    except requests.exceptions.Timeout as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return FetchResult(
            final_url=None,
            status=None,
            html=None,
            has_website=False,
            has_ssl=None,
            ssl_error=None,
            elapsed_ms=elapsed_ms,
            error=f"timeout: {exc}",
        )

    except requests.exceptions.RequestException as exc:
        elapsed_ms = int((time.monotonic() - start) * 1000)
        return FetchResult(
            final_url=None,
            status=None,
            html=None,
            has_website=False,
            has_ssl=None,
            ssl_error=None,
            elapsed_ms=elapsed_ms,
            error=str(exc),
        )
