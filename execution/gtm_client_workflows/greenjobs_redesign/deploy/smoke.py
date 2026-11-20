"""GreenJobs post-deploy smoke tests against a deployed environment (staging full, production read-only).

description: Black-box checks of a deployed GreenJobs environment over HTTPS. Read checks (both envs):
    health, job list (Worker API + board page), security headers, KPI dashboard, /api/stats parity
    with the paginated job list and the dashboard figures, 20 sampled legacy redirects -> 301 -> 200,
    build-export auth. Write checks (staging `full` mode only): create an email-mode and a link-mode job
    through the admin API with the staging Access service token, poll until public (<= 15 min), apply
    in both modes (DRY_RUN, synthetic applicant, no CV), close both, expect the closed status (410).
    Production `read_only` mode writes nothing unless --canary: one hidden draft job, closed at once,
    asserted never public.
inputs: --env staging|production; --mode full|read_only (default from environments.json); --sha (seeds
    idempotency keys and the redirect sample); --canary; --out PATH; env GREENJOBS_SMOKE_ACCESS_CLIENT_ID /
    GREENJOBS_SMOKE_ACCESS_CLIENT_SECRET (Cloudflare Access service token; staging write checks, prod
    canary) and GREENJOBS_SMOKE_BUILD_TOKEN (export check). Values are never printed.
outputs: JSON {env, mode, sha, status, checks:[{name,status,detail}]} to --out and a table to stdout.
    Exit 0 all pass (skips allowed only where listed in ENVIRONMENTS.md), 1 any fail, 2 usage.
"""

from __future__ import annotations

import argparse
import http.client
import json
import random
import re
import sys
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlsplit

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[3]
NS = uuid.UUID(
    "6f1c3a52-7d0e-4f53-9a51-0e5b0c1d2a77"
)  # fixed namespace: same sha -> same idempotency keys


@dataclass
class Resp:
    status: int
    headers: dict[str, str]
    body: bytes = b""

    def json(self) -> Any:
        try:
            return json.loads(self.body.decode("utf-8"))
        except ValueError:
            return None

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


Transport = Callable[[str, str, dict[str, str], bytes | None], Resp]


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(
        self, *a: Any, **k: Any
    ) -> None:  # never follow: redirects are asserted, not trusted
        return None


_OPENER = urllib.request.build_opener(_NoRedirect)


def urllib_transport(
    method: str, url: str, headers: dict[str, str], body: bytes | None
) -> Resp:
    if urlsplit(url).scheme != "https":
        raise ValueError(f"smoke only talks https: {url}")
    req = urllib.request.Request(
        url,
        data=body,
        method=method,
        headers={"User-Agent": "greenjobs-smoke/1", **headers},
    )
    try:
        with _OPENER.open(req, timeout=30) as r:
            return Resp(
                r.status,
                {k.lower(): v for k, v in r.headers.items()},
                r.read(2_000_000),
            )
    except urllib.error.HTTPError as e:
        return Resp(
            e.code,
            {k.lower(): v for k, v in (e.headers or {}).items()},
            e.read(2_000_000) if e.fp else b"",
        )


@dataclass
class Smoke:
    cfg: dict[str, Any]
    env: str
    mode: str
    sha: str
    transport: Transport = urllib_transport
    secrets: dict[str, str] = field(default_factory=dict)
    sleep: Callable[[float], None] = time.sleep
    clock: Callable[[], float] = time.monotonic
    canary: bool = False
    run_id: str = field(default_factory=lambda: uuid.uuid4().hex)  # one run's retries share keys; a new run creates fresh jobs
    checks: list[dict[str, str]] = field(default_factory=list)

    def __post_init__(self) -> None:
        self.ec = self.cfg["envs"][self.env]
        self.sc = self.cfg["smoke"]
        self.paths = self.sc["paths"]

    # -- helpers
    def rec(self, name: str, ok: bool | None, detail: str = "") -> bool:
        status = "skip" if ok is None else ("pass" if ok else "fail")
        self.checks.append({"name": name, "status": status, "detail": detail[:300]})
        return bool(ok)

    def get(self, url: str, headers: dict[str, str] | None = None) -> Resp:
        try:
            return self.transport("GET", url, headers or {}, None)
        # network error is a failed check, reported with its type only
        except (OSError, ValueError, http.client.HTTPException) as e:
            return Resp(0, {}, f"{type(e).__name__}".encode())

    def send(self, method: str, url: str, headers: dict[str, str], body: bytes) -> Resp:
        try:
            return self.transport(method, url, headers, body)
        except (OSError, ValueError, http.client.HTTPException) as e:  # same: surfaced as status 0 in the check detail
            return Resp(0, {}, f"{type(e).__name__}".encode())

    def p(self, key: str, **kw: str) -> str:
        return self.paths[key].format(**kw)

    def sites(self, group: str) -> list[tuple[str, str]]:
        return [(s, u.rstrip("/")) for s, u in sorted(self.ec[group].items())]

    def access_headers(self) -> dict[str, str] | None:
        cid, sec = self.secrets.get("access_client_id"), self.secrets.get(
            "access_client_secret"
        )
        return (
            {"CF-Access-Client-Id": cid, "CF-Access-Client-Secret": sec}
            if cid and sec
            else None
        )

    # -- read checks
    def check_health(self) -> None:
        for site, base in self.sites("worker_urls"):
            if not base:
                self.rec(
                    f"health[{site}]",
                    None,
                    "no Worker host for this site in environments.json",
                )
                continue
            r = self.get(base + self.p("health"))
            body = r.json() or {}
            self.rec(
                f"health[{site}]",
                r.status == 200 and body.get("ok") is not False,
                f"HTTP {r.status}",
            )

    def list_all_jobs(self, base: str, origin: str) -> tuple[int | None, str]:
        n, after, pages = 0, None, 0
        while pages < 50:  # ceiling: 50 x 1000 rows
            q = "?limit=1000" + (f"&after={after}" if after else "")
            r = self.get(base + self.p("jobs_api") + q, {"Origin": origin})
            body = r.json()
            if (
                r.status != 200
                or not isinstance(body, dict)
                or not isinstance(body.get("jobs"), list)
            ):
                return None, f"HTTP {r.status} on page {pages + 1}"
            n += len(body["jobs"])
            pages += 1
            after = body.get("next")
            if not after:
                return n, f"{n} jobs over {pages} page(s)"
        return None, "pagination ceiling hit (50 pages)"

    def check_jobs_and_stats(self) -> None:
        boards = dict(self.sites("board_urls"))
        for site, base in self.sites("worker_urls"):
            if not base:
                self.rec(f"jobs_api[{site}]", None, "no Worker host")
                self.rec(f"stats_parity[{site}]", None, "no Worker host")
                continue
            n, detail = self.list_all_jobs(base, boards[site])
            self.rec(f"jobs_api[{site}]", n is not None, detail)
            r = self.get(base + self.p("stats_api"), {"Origin": boards[site]})
            stats = r.json() if r.status == 200 else None
            live = (
                stats.get(self.sc["stats_live_key"])
                if isinstance(stats, dict)
                else None
            )
            if n is None or not isinstance(live, int):
                self.rec(
                    f"stats_parity[{site}]",
                    False,
                    f"stats HTTP {r.status}, {self.sc['stats_live_key']}={live!r}, list={n}",
                )
                continue
            ok, detail = live == n, f"stats {live} vs list {n}"
            dash = self.get(boards[site] + self.p("board_dashboard", ed=site))
            marks = {
                k: int(v.replace(",", ""))
                for k, v in re.findall(self.sc["dashboard_stat_regex"], dash.text)
            }
            shared = sorted(set(marks) & set(stats))
            for k in shared:
                if isinstance(stats[k], int) and stats[k] != marks[k]:
                    ok, detail = (
                        False,
                        f"{detail}; dashboard {k}={marks[k]} vs stats {stats[k]}",
                    )
            detail += f"; dashboard figures compared: {', '.join(shared) or 'none (no data-stat markers)'}"
            self.rec(f"stats_parity[{site}]", ok, detail)

    def check_boards(self) -> None:
        for site, base in self.sites("board_urls"):
            r = self.get(base + self.p("board_list", ed=site))
            self.rec(
                f"board_list[{site}]",
                r.status == 200 and "<html" in r.text.lower(),
                f"HTTP {r.status}",
            )
            d = self.get(base + self.p("board_dashboard", ed=site))
            self.rec(
                f"dashboard[{site}]",
                d.status == 200 and "<html" in d.text.lower(),
                f"HTTP {d.status}",
            )

    def check_headers(self) -> None:
        targets = [
            ("board", s, b + self.p("board_list", ed=s))
            for s, b in self.sites("board_urls")
        ]
        targets += [
            ("worker", s, b + self.p("jobs_api") + "?limit=1")
            for s, b in self.sites("worker_urls")
            if b
        ]
        for kind, site, url in targets:
            r = self.get(url)
            missing = [
                h for h in self.sc["required_headers"][kind] if h not in r.headers
            ]
            if r.headers.get("x-content-type-options", "nosniff").lower() != "nosniff":
                missing.append("x-content-type-options=nosniff")
            self.rec(
                f"security_headers[{kind}:{site}]",
                r.status == 200 and not missing,
                f"HTTP {r.status}; missing: {', '.join(missing) or 'none'}",
            )

    def redirect_sample(self, site: str) -> list[tuple[str, str]]:
        data = json.loads((ROOT / self.cfg["redirect_map"]).read_text(encoding="utf-8"))
        entries = [
            (e["old"], e["target"])
            for e in data["sites"][site]["entries"]
            if e.get("status") == "mapped"
            and e.get("target")
            and e.get("old") != e.get("target")
        ]
        rng = random.Random(
            f"{self.sha}:{site}"
        )  # deterministic per sha: a re-run checks the same 20
        k = min(self.sc["redirect_sample_size"], len(entries))
        return rng.sample(sorted(entries), k)

    def check_redirects(self) -> None:
        for site, base in self.sites("board_urls"):
            sample = self.redirect_sample(site)
            bad = []
            for old, target in sample:
                r = self.get(base + old)
                loc = r.headers.get("location", "")
                if (
                    r.status != 301
                    or urlsplit(urljoin(base + old, loc)).path != urlsplit(target).path
                ):
                    bad.append(f"{old} -> {r.status} {loc or '-'}")
                    continue
                t = self.get(urljoin(base + old, loc))
                if t.status != 200:
                    bad.append(f"{old} -> {target} -> {t.status}")
            ok = bool(sample) and not bad
            self.rec(
                f"redirects[{site}]",
                ok,
                f"{len(sample) - len(bad)}/{len(sample)} ok"
                + (f"; first bad: {bad[0]}" if bad else ""),
            )

    def check_export(self) -> None:
        _site, base = next(
            ((s, b) for s, b in self.sites("worker_urls") if b), (None, None)
        )
        if not base:
            self.rec("export_auth", None, "no Worker host")
            return
        anon = self.get(base + self.p("export_api"))
        tok = self.secrets.get("build_token")
        if not tok:
            self.rec(
                "export_auth",
                None if self.mode == "read_only" else False,
                f"anon HTTP {anon.status}; GREENJOBS_SMOKE_BUILD_TOKEN not set",
            )
            return
        authed = self.get(
            base + self.p("export_api"), {"Authorization": f"Bearer {tok}"}
        )
        self.rec(
            "export_auth",
            anon.status == 401 and authed.status == 200,
            f"anon {anon.status}, token {authed.status}",
        )

    # -- write checks
    def admin(
        self, method: str, base: str, path: str, body: dict[str, Any], key: str
    ) -> Resp:
        h = {
            **(self.access_headers() or {}),
            "Origin": base,
            "Content-Type": "application/json",
            "Idempotency-Key": str(uuid.uuid5(NS, f"{self.env}:{self.sha}:{self.run_id}:{key}")),
        }
        return self.send(method, base + path, h, json.dumps(body).encode())

    def poll_public(self, base: str, origin: str, job_id: str) -> tuple[Resp, float]:
        start, timeout = self.clock(), self.sc["job_visible_timeout_s"]
        while True:
            r = self.get(base + self.p("job_api", id=job_id), {"Origin": origin})
            waited = self.clock() - start
            if r.status == 200 or waited >= timeout:
                return r, waited
            self.sleep(self.sc["job_visible_poll_s"])

    def multipart(self, fields: dict[str, str]) -> tuple[bytes, str]:
        b = f"----greenjobs-smoke-{uuid.uuid5(NS, self.sha).hex}"
        parts = [
            f'--{b}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'
            for k, v in fields.items()
        ]
        return (
            "".join(parts) + f"--{b}--\r\n"
        ).encode(), f"multipart/form-data; boundary={b}"

    def apply(self, base: str, origin: str, job_id: str) -> Resp:
        body, ct = self.multipart(
            {
                "job_id": job_id,
                "name": "Staging Smoke Test",
                "email": "smoke-test@example.com",
                "cover_note": f"Automated staging smoke test for {self.sha[:12]}.",
                "consent": "yes",
            }
        )
        return self.send(
            "POST",
            base + self.p("apply_api"),
            {"Origin": origin, "Content-Type": ct},
            body,
        )

    def write_flow(self) -> None:
        if self.access_headers() is None:
            self.rec(
                "write_flow",
                False,
                "GREENJOBS_SMOKE_ACCESS_CLIENT_ID/SECRET not set (required for staging full mode)",
            )
            return
        site, base = next(
            ((s, b) for s, b in self.sites("worker_urls") if b), (None, None)
        )
        if not base:
            self.rec("write_flow", False, "no Worker host")
            return
        origin = dict(self.sites("board_urls"))[site]
        tag = self.sha[:12]
        common = {
            "employer": "GreenJobs Staging Smoke",
            "location": "Dublin",
            "summary": "Automated staging smoke job.",
            "description": f"Automated staging smoke test job for release {tag}. Safe to ignore; closed by the same run.",
            "status": "live",
            "sectors": [],
        }
        jobs = {
            "email": {
                **common,
                "title": f"Smoke test email-apply {tag}",
                "apply_mode": "email",
                "apply_email": "staging-smoke@example.com",
            },
            "link": {
                **common,
                "title": f"Smoke test link-apply {tag}",
                "apply_mode": "link",
                "apply_url": "https://example.com/apply",
            },
        }
        ids: dict[str, str] = {}
        for mode, body in jobs.items():
            r = self.admin("POST", base, self.p("admin_jobs"), body, f"create-{mode}")
            jid = (r.json() or {}).get("id") if r.status in (200, 201) else None
            if self.rec(f"admin_create[{mode}]", bool(jid), f"HTTP {r.status}"):
                ids[mode] = jid
        try:
            for mode, jid in ids.items():
                r, waited = self.poll_public(base, origin, jid)
                self.rec(
                    f"job_visible[{mode}]",
                    r.status == 200,
                    f"HTTP {r.status} after {waited:.0f}s (limit {self.sc['job_visible_timeout_s']}s)",
                )
                if mode == "link":
                    pub = r.json() or {}
                    self.rec(
                        "job_link_mode_public",
                        pub.get("apply_mode") == "link"
                        and pub.get("apply_url") == "https://example.com/apply",
                        f"apply_mode={pub.get('apply_mode')!r}",
                    )
                    a = self.apply(base, origin, jid)
                    self.rec(
                        "apply[link]",
                        a.status == 409
                        and (a.json() or {}).get("error") == "apply_externally",
                        f"HTTP {a.status}",
                    )
                else:
                    a = self.apply(base, origin, jid)
                    body = a.json() or {}
                    ok = (a.status == 201 and body.get("delivery") == "dry_run") or (
                        a.status == 200 and body.get("status") == "already_received"
                    )
                    self.rec(
                        "apply[email]",
                        ok,
                        f"HTTP {a.status}, delivery={body.get('delivery')!r}",
                    )
        finally:  # always close what this run opened, even after a failed check
            for mode, jid in ids.items():
                r = self.admin(
                    "POST", base, self.p("admin_close", id=jid), {}, f"close-{mode}"
                )
                self.rec(
                    f"admin_close[{mode}]",
                    r.status == 200 and (r.json() or {}).get("status") == "closed",
                    f"HTTP {r.status}",
                )
                g = self.get(base + self.p("job_api", id=jid), {"Origin": origin})
                self.rec(
                    f"closed_status[{mode}]",
                    g.status == self.sc["closed_job_status"],
                    f"HTTP {g.status}, want {self.sc['closed_job_status']}",
                )

    def canary_flow(self) -> None:
        if self.access_headers() is None:
            self.rec(
                "canary",
                False,
                "--canary needs GREENJOBS_SMOKE_ACCESS_CLIENT_ID/SECRET",
            )
            return
        site, base = next(
            ((s, b) for s, b in self.sites("worker_urls") if b), (None, None)
        )
        origin = dict(self.sites("board_urls"))[site]
        body = {
            "title": f"[canary] release {self.sha[:12]}",
            "employer": "GreenJobs release canary",
            "location": "Dublin",
            "description": "Hidden release canary (draft, never public); closed by the same run.",
            "status": "draft",
            "apply_mode": "link",
            "apply_url": "https://example.com/canary",
            "sectors": [],
        }
        r = self.admin("POST", base, self.p("admin_jobs"), body, "canary-create")
        jid = (r.json() or {}).get("id") if r.status in (200, 201) else None
        if not self.rec("canary_create", bool(jid), f"HTTP {r.status}"):
            return
        try:
            g = self.get(base + self.p("job_api", id=jid), {"Origin": origin})
            self.rec(
                "canary_hidden",
                g.status in (404, self.sc["closed_job_status"]),
                f"public HTTP {g.status}",
            )
        finally:
            c = self.admin(
                "POST", base, self.p("admin_close", id=jid), {}, "canary-close"
            )
            self.rec("canary_close", c.status == 200, f"HTTP {c.status}")

    # -- run
    def run(self) -> dict[str, Any]:
        self.check_health()
        self.check_boards()
        self.check_headers()
        self.check_jobs_and_stats()
        self.check_redirects()
        self.check_export()
        if self.mode == "full":
            if self.env == "production":
                raise ValueError("full (write) mode never runs against production")
            self.write_flow()
        elif self.canary:
            self.canary_flow()
        failed = [c for c in self.checks if c["status"] == "fail"]
        return {
            "env": self.env,
            "mode": self.mode,
            "sha": self.sha,
            "status": "fail" if failed else "pass",
            "canary": self.canary,
            "checks": self.checks,
        }


def main(argv: list[str] | None = None) -> int:
    import os

    ap = argparse.ArgumentParser(description="GreenJobs post-deploy smoke tests")
    ap.add_argument("--env", required=True, choices=["staging", "production"])
    ap.add_argument("--mode", choices=["full", "read_only"], default=None)
    ap.add_argument("--sha", required=True)
    ap.add_argument(
        "--canary",
        action="store_true",
        help="production only: hidden draft job, closed at once",
    )
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument("--config", type=Path, default=HERE / "environments.json")
    args = ap.parse_args(argv)
    cfg = json.loads(args.config.read_text(encoding="utf-8"))
    mode = args.mode or cfg["envs"][args.env]["smoke_mode"]
    if args.env == "production" and mode == "full":
        print(
            "refusing: production smoke is read_only (use --canary for the hidden canary)",
            file=sys.stderr,
        )
        return 2
    secrets = {
        "access_client_id": os.environ.get("GREENJOBS_SMOKE_ACCESS_CLIENT_ID", ""),
        "access_client_secret": os.environ.get(
            "GREENJOBS_SMOKE_ACCESS_CLIENT_SECRET", ""
        ),
        "build_token": os.environ.get("GREENJOBS_SMOKE_BUILD_TOKEN", ""),
    }
    result = Smoke(
        cfg, args.env, mode, args.sha, secrets=secrets, canary=args.canary
    ).run()
    for c in result["checks"]:
        print(f"{c['status'].upper():4}  {c['name']:34} {c['detail']}")
    print(f"\nsmoke {args.env} ({mode}): {result['status'].upper()}")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return 0 if result["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
