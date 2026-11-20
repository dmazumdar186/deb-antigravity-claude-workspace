"""Shared fixtures for the GreenJobs ops tests: offline, no network, no .env."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

OPS = (
    Path(__file__).resolve().parents[3]
    / "execution"
    / "gtm_client_workflows"
    / "greenjobs_redesign"
    / "ops"
)
sys.path.insert(0, str(OPS))

import common as C  # noqa: E402

TYPES = {"NS": 2, "MX": 15, "TXT": 16}


class FakeDNS:
    """DoH transport: answers from a {domain: {"ns": [...], "mx": [...], "txt": [...]}} table; never touches the network."""

    def __init__(
        self, zones: dict[str, dict[str, list[str]]], fail: set[str] | None = None
    ):
        self.zones, self.fail, self.calls = zones, fail or set(), 0

    def __call__(
        self, url: str, headers: dict[str, str], timeout: float
    ) -> tuple[int, bytes]:
        self.calls += 1
        from urllib.parse import parse_qs, urlsplit

        q = parse_qs(urlsplit(url).query)
        name, rtype = q["name"][0], q["type"][0]
        if name in self.fail:
            raise TimeoutError("fake timeout")
        z = self.zones.get(name, {})
        ans = [{"type": TYPES[rtype], "data": d} for d in z.get(rtype.lower(), [])]
        return 200, json.dumps({"Status": 0, "Answer": ans}).encode()


def zones_from_inventory(
    on_cloudflare: set[str] = frozenset(),
) -> dict[str, dict[str, list[str]]]:
    base = C.inventory_baseline()
    out = {}
    for dom, b in base.items():
        ns = (
            ["ada.ns.cloudflare.com.", "bob.ns.cloudflare.com."]
            if dom in on_cloudflare
            else [n + "." for n in b["ns"]]
        )
        out[dom] = {
            "ns": ns,
            "mx": [m + "." for m in b["mx"]],
            "txt": [f'"{s}"' for s in b["spf"]] + ['"D6911740"'],
        }
    return out


@pytest.fixture(autouse=True)
def no_live_env(monkeypatch):
    for v in (
        "RESEND_API_KEY",
        "OPS_MAIL_FROM",
        "DIANA_EMAIL",
        "OPS_ALERT_EMAIL",
        "CLOUDFLARE_API_TOKEN",
        "CLOUDFLARE_ACCOUNT_ID",
    ):
        monkeypatch.delenv(v, raising=False)
