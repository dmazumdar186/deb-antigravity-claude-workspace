"""GreenJobs post-deploy smoke tests against a deployed environment (staging full, production read-only).

description: Black-box checks of a deployed GreenJobs environment over HTTPS. Read checks (both envs):
    health, job list (Worker API + board page), security headers, KPI dashboard, /api/stats parity
    with the paginated job list and every data-stat figure on the home page, dashboard and jobs page (none = fail),
    no rendered page links into the retired platform (.asp / Strategies hosts), and on staging the job-alert
    sign-up answers 2xx on both boards (DRY_RUN: no mail),
    a Worker-rendered job page per site, 20 sampled legacy redirects -> 301 -> 200,
    build-export auth, and REAL-BROWSER checks (browser_smoke.mjs, Playwright Chromium): on staging the on-page
    apply form of one email-apply job per board is filled and submitted and must show the success message from the
    edition's API base; on every env a link-apply button must point at the employer's URL and the boards must not
    overflow at 360-430 px (a browser that cannot start fails the gate). Write checks (staging `full` mode only): create an email-mode and a link-mode job
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
import html as html_lib
import http.client
import json
import random
import re
import subprocess
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
# pages whose data-stat figures are compared with /api/stats (home, KPI dashboard, jobs page: intro + quick match)
STAT_PAGES = ("board_home", "board_dashboard", "board_list")
# pages scanned for links into the retired platform (eye review M3), per board, plus a sample of job pages
LINK_PAGES = ("/{ed}/", "/{ed}/jobs/", "/{ed}/employers/", "/{ed}/dashboard/", "/{ed}/insights/", "/{ed}/sectors/")
LINK_JOB_SAMPLE = 5
URL_RE = re.compile(r"""(?:https?:)?//[A-Za-z0-9.-]+\.[A-Za-z]{2,}[^\s"'<>)\]]*""")
ALERT_SMOKE_EMAIL = "smoke-alerts@example.com"
# real-browser checks (deploy/browser_smoke.mjs, eye review r2 N1): the on-page apply form per edition, a link-apply
# button, phone-width overflow. Fixed applicant per edition: a re-run converges on one application row (DRY_RUN).
BROWSER_SCRIPT = HERE / "browser_smoke.mjs"
BROWSER_APPLY_EMAIL = "smoke-browser-{site}@example.com"
BROWSER_WIDTHS = (360, 375, 390, 414, 430)
BROWSER_LOOKUP_CEILING = 40  # job lookups per edition to find an email-apply and a link-apply page (floor: 1)
BROWSER_TIMEOUT_S = 600


def id_of_slug(site: str, slug: str) -> str:
    """The Worker's idOfSlug: '11502133' -> '<site>:strat:11502133', 'gaia-9360' -> '<site>:gaia:9360'."""
    if ":" in slug:
        return slug
    if slug.isdigit():
        return f"{site}:strat:{slug}"
    src, _, ref = slug.partition("-")
    return f"{site}:{src}:{ref}"


def node_browser_runner(spec: dict[str, Any]) -> dict[str, Any]:
    """Run browser_smoke.mjs with the spec on stdin; its one JSON line back. Raises RuntimeError when it cannot run."""
    try:
        r = subprocess.run(["node", str(BROWSER_SCRIPT)], input=json.dumps(spec), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=BROWSER_TIMEOUT_S)
    except (OSError, subprocess.TimeoutExpired) as e:
        raise RuntimeError(type(e).__name__) from e
    lines = [ln for ln in r.stdout.splitlines() if ln.startswith("{")]
    try:
        out = json.loads(lines[-1]) if lines else {}
    except ValueError:
        out = {}
    if r.returncode != 0 or not isinstance(out.get("checks"), list):
        raise RuntimeError(str(out.get("error") or f"exit {r.returncode}"))
    return out  # one fixed address: a re-run converges on one pending row (DRY_RUN: no mail)
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


def _stat_lookup(stats: Any, path: str) -> tuple[bool, Any]:
    """(found, value) for a dotted /api/stats path; the same rule as build_site.stat_lookup."""
    cur = stats
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


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
    browser: Callable[[dict[str, Any]], dict[str, Any]] | None = None  # None = node_browser_runner (tests inject)
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
            compared, bad = self.compare_figures(boards[site], site, stats)
            if bad:
                ok, detail = False, f"{detail}; {'; '.join(bad[:3])}"
            if not compared:
                ok = False
                detail += "; figures compared: none (no data-stat markers on home, dashboard or jobs page): FAIL"
            else:
                detail += f"; figures compared: {compared} ({len(bad)} differ)"
            self.rec(f"stats_parity[{site}]", ok, detail)

    def compare_figures(self, board: str, site: str, stats: dict[str, Any]) -> tuple[int, list[str]]:
        """Every data-stat figure slot on the board's home page, KPI dashboard and jobs page against /api/stats: the key is a
        dotted path into the stats body (salary.n_jobs, kpis.live; a flat key such as live_jobs works too) and the
        printed text must equal the value as the pages print it (thousands separators and a trailing % ignored,
        null = n/a). A key /api/stats does not have is a difference, not a skip. Returns (compared, differences)."""
        compared, bad = 0, []
        for page in STAT_PAGES:
            r = self.get(board + self.p(page, ed=site))
            if r.status != 200:
                bad.append(f"{self.p(page, ed=site)} HTTP {r.status}")
                continue
            found_on_page = re.findall(self.sc["dashboard_stat_regex"], r.text)
            if page == "board_list" and not found_on_page:
                # the jobs-page intro "N green roles" and the quick-match "N live roles are indexed" (eye review B3)
                bad.append("list: no data-stat figure (intro + quick-match counts)")
            for _tag, key, text in found_on_page:
                compared += 1
                found, want = _stat_lookup(stats, key)
                got = text.strip().replace(",", "")
                if not found or isinstance(want, (dict, list)):
                    bad.append(f"{page[6:]} {key}={text.strip()} vs stats: no such figure")
                elif got.rstrip("%") != ("n/a" if want is None else str(want).replace(",", "")):
                    bad.append(f"{page[6:]} {key}={text.strip()} vs stats {want}")
        return compared, bad

    def check_job_pages(self) -> None:
        """Each Worker host renders a job page of its own site from D1: the first job of /api/jobs?view=board
        answers 200 at /{site}/jobs/<slug>/ with its JobPosting structured data."""
        for site, base in self.sites("worker_urls"):
            if not base:
                self.rec(f"job_page[{site}]", None, "no Worker host")
                continue
            r = self.get(f"{base}/api/jobs?view=board&site={site}&limit=1&text=0")
            body = r.json() if r.status == 200 else None
            jobs = body.get("jobs") if isinstance(body, dict) else None
            slug = str(jobs[0].get("id") or "") if isinstance(jobs, list) and jobs and isinstance(jobs[0], dict) else ""
            if not re.fullmatch(r"[A-Za-z0-9_:-]{1,120}", slug):
                self.rec(f"job_page[{site}]", False, f"board list HTTP {r.status}, no job slug")
                continue
            path = self.p("board_job", ed=site, slug=slug)
            g = self.get(base + path)
            self.rec(
                f"job_page[{site}]",
                g.status == 200 and "<html" in g.text.lower() and '"JobPosting"' in g.text,
                f"{path} HTTP {g.status}",
            )

    def check_live_wiring(self) -> None:
        """Each static board reads live data and sign-up flags from its API origin (environments.json api_base;
        "" = the board's own host): /api/config answers the board's Origin with CORS, and the paginated
        /api/jobs?view=board set has exactly /api/stats' live_jobs rows (what the charts and search show).
        An environment without api_base (older config) skips."""
        api = self.ec.get("api_base")
        if not isinstance(api, dict):
            self.rec("live_wiring", None, "no api_base in environments.json")
            return
        for site, board in self.sites("board_urls"):
            base = (api.get(site) or board).rstrip("/")
            h = {"Origin": board}
            c = self.get(f"{base}/api/config?site={site}", h)
            cfg = c.json() if c.status == 200 else None
            cors_ok = base == board or c.headers.get("access-control-allow-origin") == board
            if not (isinstance(cfg, dict) and cfg.get("site") == site and cors_ok):
                self.rec(f"live_wiring[{site}]", False, f"config HTTP {c.status}, CORS {'ok' if cors_ok else 'missing'}")
                continue
            n, after, pages, total = 0, None, 0, None
            while pages < 40:  # ceiling: 40 x 500 rows
                q = f"/api/jobs?view=board&site={site}&limit=500&text=0" + (f"&after={after}" if after else "")
                r = self.get(base + q, h)
                body = r.json() if r.status == 200 else None
                if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
                    total = None
                    break
                if pages == 0:
                    total = body.get("total")
                n, pages, after = n + len(body["jobs"]), pages + 1, body.get("next")
                if not after:
                    break
            s = self.get(f"{base}{self.p('stats_api')}?site={site}", h)
            live = (s.json() or {}).get(self.sc["stats_live_key"]) if s.status == 200 else None
            self.rec(
                f"live_wiring[{site}]",
                total is not None and not after and n == total == live,
                f"alerts={cfg.get('alerts')}, newsletter={cfg.get('newsletter')}; board set {n} over {pages} page(s), total {total}, stats {live}",
            )

    def check_alert_signup(self) -> None:
        """Staging (require_dry_run): the job-alert sign-up of each board answers 2xx through its API origin, as
        the board's form posts it (api.js: POST /api/alerts?site=, JSON, consent). DRY_RUN keeps the confirmation
        mail unsent; the fixed address converges on one pending row. Production writes nothing: not run there."""
        if not self.ec.get("require_dry_run"):
            return
        api = self.ec.get("api_base") or {}
        for site, board in self.sites("board_urls"):
            base = (api.get(site) or board).rstrip("/")
            body = json.dumps({"email": ALERT_SMOKE_EMAIL, "consent": True, "website": ""}).encode()
            r = self.send("POST", f"{base}/api/alerts?site={site}", {"Origin": board, "Content-Type": "application/json"}, body)
            got = r.json() if isinstance(r.json(), dict) else {}
            self.rec(f"alert_signup[{site}]", 200 <= r.status < 300 and got.get("ok") is True,
                     f"HTTP {r.status} {got.get('error') or got.get('next') or ''}".strip())

    def browser_targets(self, site: str, base: str, board: str) -> tuple[dict[str, str] | None, dict[str, str] | None]:
        """(email-apply job, link-apply job) on this board: {url, ...} from the live board set + each job's public
        apply mode, at most BROWSER_LOOKUP_CEILING lookups."""
        r = self.get(f"{base}/api/jobs?view=board&site={site}&limit={BROWSER_LOOKUP_CEILING}&text=0", {"Origin": board})
        jobs = (r.json() or {}).get("jobs") if r.status == 200 and isinstance(r.json(), dict) else None
        email = link = None
        for j in (jobs or [])[:BROWSER_LOOKUP_CEILING]:
            slug = str((j or {}).get("id") or "")
            if not re.fullmatch(r"[A-Za-z0-9_:-]{1,120}", slug):
                continue
            href = str(j.get("href") or "") or self.p("board_job", ed=site, slug=slug)
            if not href.startswith(f"/{site}/jobs/"):
                continue
            g = self.get(base + self.p("job_api", id=id_of_slug(site, slug)), {"Origin": board})
            pub = g.json() if g.status == 200 and isinstance(g.json(), dict) else {}
            if pub.get("apply_mode") == "email" and email is None:
                email = {"url": board + href}
            elif pub.get("apply_mode") == "link" and link is None and str(pub.get("apply_url") or "").startswith("https://"):
                link = {"url": board + href, "expect": pub["apply_url"]}
            if email and link:
                break
        return email, link

    def check_browser(self) -> None:
        """Real Chromium on the deployed boards (eye review r2 N1: the HTTP smoke posted to the API itself and never
        saw a form that posted to the Pages origin). Staging (DRY_RUN pinned): on one email-apply job page per
        edition, fill and submit the ON-PAGE form and require the success message from the edition's API base.
        Every env: a link-apply button points at the employer's URL; no horizontal overflow at 360-430 px. A browser
        that cannot start is a failed check, never a skip."""
        api = self.ec.get("api_base") or {}
        tasks: list[dict[str, Any]] = []
        link_task = None
        for site, board in self.sites("board_urls"):
            base = (api.get(site) or board).rstrip("/")
            email, link = self.browser_targets(site, base, board)
            if self.ec.get("require_dry_run"):
                if email:
                    tasks.append({"kind": "apply", "name": f"browser_apply[{site}]", "url": email["url"],
                                  "expect_post": f"{base}{self.p('apply_api')}", "email": BROWSER_APPLY_EMAIL.format(site=site)})
                else:
                    self.rec(f"browser_apply[{site}]", False, "no email-apply job found on the board")
            if link and link_task is None:
                link_task = {"kind": "link", "name": "browser_link_apply", "url": link["url"], "expect": link["expect"]}
            urls = [board + f"/{site}/"] + [t["url"] for t in (email, link) if t]
            tasks.append({"kind": "layout", "name": f"browser_layout[{site}]", "urls": urls, "widths": list(BROWSER_WIDTHS)})
        if link_task:
            tasks.append(link_task)
        else:
            self.rec("browser_link_apply", False, "no link-apply job found on any board")
        runner = self.browser or node_browser_runner
        try:
            out = runner({"tasks": tasks})
        except RuntimeError as e:
            for t in tasks:
                self.rec(t["name"], False, f"browser did not run: {e}")
            return
        got = {c.get("name"): c for c in out.get("checks") or [] if isinstance(c, dict)}
        for t in tasks:
            c = got.get(t["name"])
            self.rec(t["name"], bool(c and c.get("ok") is True), str((c or {}).get("detail") or "no result"))

    def old_platform_links(self, html_text: str) -> list[str]:
        pkg = str(HERE.parent)
        if pkg not in sys.path:
            sys.path.insert(0, pkg)
        import validate_site  # noqa: PLC0415  (the one old-platform rule, shared with build_site and the Worker)

        out = []
        for raw in URL_RE.findall(html_lib.unescape(html_text)):
            u = ("https:" + raw) if raw.startswith("//") else raw
            if validate_site.is_old_platform_url(u.rstrip(".,;")):
                out.append(u)
        return out

    def check_no_old_platform_links(self) -> None:
        """No rendered page links into the retired platform (greenjobs.ie / greenjobs.co.uk *.asp, /browse-jobs/,
        /jobboard/, or a Strategies host): the board's main pages plus LINK_JOB_SAMPLE job pages per site as the
        Worker renders them (eye review M3)."""
        workers = dict(self.sites("worker_urls"))
        for site, board in self.sites("board_urls"):
            urls = [board + p.format(ed=site) for p in LINK_PAGES]
            base = workers.get(site) or board
            r = self.get(f"{base}/api/jobs?view=board&site={site}&limit={LINK_JOB_SAMPLE}&text=0", {"Origin": board})
            jobs = (r.json() or {}).get("jobs") if r.status == 200 and isinstance(r.json(), dict) else None
            ids = [str(j.get("id")) for j in (jobs or []) if isinstance(j, dict) and re.fullmatch(r"[A-Za-z0-9_:-]{1,120}", str(j.get("id") or ""))]
            urls += [base + self.p("board_job", ed=site, slug=i) for i in ids[:LINK_JOB_SAMPLE]]
            hits, errors = [], []
            for url in urls:
                g = self.get(url)
                if g.status != 200:
                    errors.append(f"{urlsplit(url).path} HTTP {g.status}")
                    continue
                hits += [f"{urlsplit(url).path} -> {h}" for h in self.old_platform_links(g.text)]
            ok = not hits and not errors and len(ids) >= min(LINK_JOB_SAMPLE, 1)
            detail = f"{len(urls) - len(errors)}/{len(urls)} pages scanned ({len(ids)} job pages); old-platform links: {len(hits)}"
            if hits:
                detail += f"; first: {hits[0]}"
            if errors:
                detail += f"; {errors[0]}"
            self.rec(f"no_old_platform_links[{site}]", ok, detail)

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

    def redirect_rules(self, site: str) -> list[tuple[str, str]]:
        """(old, target) pairs the board must answer 301 for. With `redirect_source` (the ops Bulk Redirects
        list) these are exactly the rules build_site.py writes to the board's _redirects (one source);
        otherwise the snapshot redirect_map's mapped entries."""
        if self.cfg.get("redirect_source"):
            pkg = str(HERE.parent)
            if pkg not in sys.path:
                sys.path.insert(0, pkg)
            import build_site  # noqa: PLC0415  (only for the redirect rules)

            bulk = json.loads((ROOT / self.cfg["redirect_source"]).read_text(encoding="utf-8"))
            return build_site.pages_redirect_rules(bulk, site, self.board_job_ids(site))
        data = json.loads((ROOT / self.cfg["redirect_map"]).read_text(encoding="utf-8"))
        return [
            (e["old"], e["target"])
            for e in data["sites"][site]["entries"]
            if e.get("status") == "mapped"
            and e.get("target")
            and e.get("old") != e.get("target")
        ]

    def board_job_ids(self, site: str) -> set[str] | None:
        """The job ids the deployed board serves (its own /{site}/data/jobs.json), so a legacy job URL is expected
        to land where build_site.py sent it. None (unknown) when the board does not answer."""
        base = dict(self.sites("board_urls")).get(site)
        if not base:
            return None
        r = self.get(f"{base}/{site}/data/jobs.json")
        body = r.json() if r.status == 200 else None
        if not isinstance(body, dict) or not isinstance(body.get("jobs"), list):
            return None
        return {str(j.get("id")) for j in body["jobs"] if isinstance(j, dict)}

    def redirect_sample(self, site: str) -> list[tuple[str, str]]:
        entries = self.redirect_rules(site)
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
                # The real form stamps its render time (anti-bot); the Worker rejects
                # submissions under 3 s old or without it (validate.js checkRenderTs).
                "ts": str(int(time.time() * 1000) - 5000),
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
            "sectors": ["Environmental science & consulting"],  # 1..3 taxonomy.json names (console contract)
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
            "sectors": ["Environmental science & consulting"],  # 1..3 taxonomy.json names (console contract)
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
        self.check_job_pages()
        self.check_live_wiring()
        self.check_no_old_platform_links()
        self.check_alert_signup()
        self.check_browser()  # before write_flow: the per-IP apply limit (5 / 10 min) covers 2 browser + 2 API applies
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
