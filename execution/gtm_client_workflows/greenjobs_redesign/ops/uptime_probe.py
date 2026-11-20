"""GreenJobs uptime + mail probe: 20 hostnames end on 200 at the right host; MX/SPF match the inventory.

description: For each of the 10 domains and its www name, GET https://<host>/
  following up to 5 redirects; a check passes when the final answer is 200 on
  the expected host (www.greenjobs.ie for greenjobs.ie; www.greenjobs.co.uk for
  greenjobs.co.uk and every sector domain, which must land on its
  /sectors/<slug>/ page). Then MX and SPF are resolved over DNS-over-HTTPS
  and compared with the zone inventory. One JSONL row per check feeds metrics
  M3 (availability) and M4 (mail intact, DNS half). Read-only; offline unless
  --live is given (without it the plan is printed and nothing is requested).
  Also probes each board's staff console, jobs API and apply endpoint (sev-1
  posting checks) and opens/closes incidents (incidents.py) so the operator is
  alerted at once and response times are measured against the service levels.
inputs: --live [--send] [--log PATH] [--timeout S]
outputs: <state>/probe_log.jsonl rows {at, kind: http|posting|mail, target, scope, ok, detail}, <state>/incidents.json, <state>/outbox.jsonl; stdout summary; exit 1 if any check failed
Schedule: every 5 minutes (SYNTHESIS §4 M3).
"""

from __future__ import annotations

import argparse
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

MAX_REDIRECTS = 5
Get = Callable[[str, float], tuple[int, str | None]]  # (status, Location header)


def targets() -> list[tuple[str, str, str | None]]:
    """(host, expected final host, expected final path or None)."""
    out = []
    for dom in C.DOMAINS:
        path = C.sector_forward_path(dom) if dom in C.SECTOR_DOMAINS else None
        for host in (dom, "www." + dom):
            out.append((host, C.expected_host(dom), path))
    return out


def follow(url: str, get: Get, timeout: float) -> dict[str, Any]:
    hops = 0
    while True:
        try:
            status, loc = get(url, timeout)
        except (
            Exception
        ) as e:  # timeout / TLS / DNS: the check fails with the error type as evidence
            return {
                "status": None,
                "final": url,
                "hops": hops,
                "error": type(e).__name__,
            }
        if status in (301, 302, 303, 307, 308) and loc:
            if hops >= MAX_REDIRECTS:
                return {
                    "status": status,
                    "final": url,
                    "hops": hops,
                    "error": "too many redirects",
                }
            hops += 1
            url = urllib.parse.urljoin(url, loc)
            continue
        return {"status": status, "final": url, "hops": hops, "error": None}


def http_checks(get: Get, timeout: float = 10.0) -> list[dict[str, Any]]:
    rows = []
    at = C.now_iso()
    for host, want_host, want_path in targets():
        r = follow(f"https://{host}/", get, timeout)
        fu = urllib.parse.urlsplit(r["final"])
        ok = (
            r["status"] == 200
            and fu.scheme == "https"
            and fu.hostname == want_host
            and (want_path is None or fu.path == want_path)
        )
        rows.append(
            {
                "at": at,
                "kind": "http",
                "target": host,
                "scope": C.scope_of(host),
                "ok": ok,
                "detail": {
                    "status": r["status"],
                    "final": r["final"],
                    "hops": r["hops"],
                    "error": r["error"],
                    "want": f"https://{want_host}{want_path or '/…'}",
                },
            }
        )
    return rows


def mail_checks(
    fetch: C.Fetch, baseline: dict[str, Any] | None = None
) -> list[dict[str, Any]]:
    base = baseline or C.inventory_baseline()
    at = C.now_iso()
    rows = []
    for dom in C.DOMAINS:
        mx, txt = C.doh(dom, "MX", fetch), C.doh(dom, "TXT", fetch)
        if not (mx["ok"] and txt["ok"]):
            rows.append(
                {
                    "at": at,
                    "kind": "mail",
                    "target": dom,
                    "scope": C.scope_of(dom),
                    "ok": None,
                    "detail": {"error": mx.get("error") or txt.get("error")},
                }
            )
            continue
        got_mx, got_spf = C.norm_mx(mx["data"]), C.spf_of(txt["data"])
        rows.append(
            {
                "at": at,
                "kind": "mail",
                "target": dom,
                    "scope": C.scope_of(dom),
                "ok": got_mx == base[dom]["mx"] and got_spf == base[dom]["spf"],
                "detail": {"mx": got_mx, "spf": got_spf},
            }
        )
    return rows


def _live_get(url: str, timeout: float) -> tuple[int, str | None]:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    req = urllib.request.Request(
        url, headers={"User-Agent": "GreenJobsUptimeProbe/1.0"}
    )
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as r:
            return r.status, r.headers.get("Location")
    except urllib.error.HTTPError as e:
        return e.code, e.headers.get("Location")


Status = Callable[[str, str, dict[str, str], float], int]  # (method, url, headers, timeout) -> status
# Sev-1 "posting outage" checks per board (P20): staff console, public jobs API, apply endpoint.
POSTING_CHECKS = (
    ("console", "GET", "/admin/", lambda s: s is not None and s < 500 and s != 404),  # Access login redirect / 401 / 403 = up
    ("jobs_api", "GET", "/api/jobs", lambda s: s == 200),
    ("apply", "OPTIONS", "/api/apply", lambda s: s in (200, 204)),  # CORS preflight: no side effect, proves the route
)


def posting_checks(status: Status, timeout: float = 10.0) -> list[dict[str, Any]]:
    rows, at = [], C.now_iso()
    for ed, base in C.CANONICAL.items():
        for name, method, path, good in POSTING_CHECKS:
            try:
                code = status(method, base + path, {"Origin": base}, timeout)
                err = None
            except Exception as e:  # timeout / TLS / DNS: the check is down, with the error type as evidence
                code, err = None, type(e).__name__
            rows.append({"at": at, "kind": "posting", "target": f"{ed}:{name}", "scope": "core", "ok": bool(good(code)),
                         "detail": {"method": method, "url": base + path, "status": code, "error": err}})
    return rows


def incident_input(rows: list[dict[str, Any]]) -> tuple[dict[str, tuple[int, str]], set[str]]:
    """Core-scope rows only (the network domains are out of the sold scope). Sev-1: posting checks; sev-2: host or mail."""
    failing, checked = {}, set()
    for r in rows:
        if r.get("scope") != "core" or r["ok"] is None:
            continue
        cid = f"{r['kind']}:{r['target']}"
        checked.add(cid)
        if r["ok"] is not True:
            failing[cid] = (1 if r["kind"] == "posting" else 2, str(r["detail"])[:300])
    return failing, checked


def run(log: Path, get: Get, fetch: C.Fetch, status: Status | None = None, timeout: float = 10.0,
        notifier: Any = None) -> list[dict[str, Any]]:
    import incidents
    from notify import Notifier

    rows = http_checks(get, timeout) + (posting_checks(status, timeout) if status else []) + mail_checks(fetch)
    for r in rows:
        C.append_jsonl(log, r)
    failing, checked = incident_input(rows)
    incidents.update(Path(log).parent, failing, checked, C.now_iso(), notifier or Notifier(Path(log).parent))
    return rows


def _live_status(method: str, url: str, headers: dict[str, str], timeout: float) -> int:
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, *a, **k):
            return None

    req = urllib.request.Request(url, method=method, headers={"User-Agent": "GreenJobsUptimeProbe/1.0", **headers})
    try:
        with urllib.request.build_opener(NoRedirect).open(req, timeout=timeout) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument(
        "--live", action="store_true", help="make the read-only HTTPS and DoH requests"
    )
    ap.add_argument("--log", type=Path, default=C.STATE_DIR / "probe_log.jsonl")
    ap.add_argument("--timeout", type=float, default=10.0)
    ap.add_argument("--send", action="store_true", help="live operator alerts for new incidents (Resend)")
    a = ap.parse_args(argv)
    if not a.live:
        for host, want, path in targets():
            print(f"plan: GET https://{host}/ -> 200 at https://{want}{path or '/'}")
        print(
            f"plan: MX + SPF for {len(C.DOMAINS)} domains vs inventory. Pass --live to run."
        )
        return 0
    from notify import Notifier

    rows = run(a.log, _live_get, C.http_get, _live_status, a.timeout, Notifier(a.log.parent, send=a.send))
    bad = [r for r in rows if r["ok"] is not True]
    print(f"probe: {len(rows) - len(bad)}/{len(rows)} checks ok -> {a.log}")
    for r in bad:
        print(f"  FAIL {r['kind']} {r['target']} ({r['scope']}): {r['detail']}")
    return (
        1 if any(r["scope"] == "core" for r in bad) else 0
    )  # optional network domains never fail the run


if __name__ == "__main__":
    sys.exit(main())
