"""Offline tests for the GreenJobs smoke client (deploy/smoke.py) against an in-process mock of the platform.

Run: python3 -m pytest tests/greenjobs_redesign/smoke -q
No network: the mock is a transport function; time is a fake clock.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0, str(ROOT / "execution/gtm_client_workflows/greenjobs_redesign/deploy")
)
import smoke

SHA = "0123456789abcdef0123456789abcdef01234567"
SEC_HEADERS = {
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "no-referrer",
}
SECRETS = {
    "access_client_id": "cid",
    "access_client_secret": "csec",
    "build_token": "bt",
}


class Clock:
    def __init__(self):
        self.t = 0.0
        self.sleeps = 0

    def now(self):
        return self.t

    def sleep(self, s):
        self.sleeps += 1
        self.t += s


class MockGreenJobs:
    """Enough of the Worker + boards to exercise every smoke check, with switches to break each one."""

    def __init__(
        self,
        cfg,
        clock,
        live=1500,
        visible_after_s=120,
        closed_status=410,
        stats_off=0,
        drop_header=None,
        bad_redirect=False,
        dashboard_live=None,
        raise_on=None,
        no_cors=False,
        markers=True,
        extra_marker=None,
        no_job_page=False,
    ):
        self.no_cors = no_cors
        self.markers, self.extra_marker, self.no_job_page = markers, extra_marker, no_job_page
        self.cfg, self.clock = cfg, clock
        self.jobs = {
            f"ie:seed-{i}": {"status": "live", "mode": "link", "created": -1e9}
            for i in range(live)
        }
        self.visible_after_s, self.closed_status, self.stats_off = (
            visible_after_s,
            closed_status,
            stats_off,
        )
        self.drop_header, self.bad_redirect, self.raise_on = (
            drop_header,
            bad_redirect,
            raise_on,
        )
        self.dashboard_live = dashboard_live
        self.applications: set[str] = set()
        self.requests: list[tuple[str, str]] = []
        self.idem: dict[str, str] = {}
        # the same rule source the smoke samples from; offline (the mock board serves no data/jobs.json)
        probe = smoke.Smoke(cfg, "staging", "full", "0" * 40, transport=lambda *a: smoke.Resp(404, {}))
        self.redirects = {site: dict(probe.redirect_rules(site)) for site in ("ie", "uk")}

    def r(self, status, body=b"", headers=None, kind="json"):
        h = dict(SEC_HEADERS)
        if self.drop_header:
            h.pop(self.drop_header, None)
        h.update(headers or {})
        if isinstance(body, (dict, list)):
            body = json.dumps(body).encode()
        elif isinstance(body, str):
            body = body.encode()
        return smoke.Resp(status, h, body)

    def live_ids(self):
        return sorted(
            k
            for k, j in self.jobs.items()
            if j["status"] == "live"
            and self.clock.now() - j["created"] >= self.visible_after_s
        )

    def __call__(self, method, url, headers, body):
        self.requests.append((method, url))
        if self.raise_on and self.raise_on in url:
            raise TimeoutError("mock timeout")
        u = urlsplit(url)
        path, q = u.path, parse_qs(u.query)
        if (
            u.hostname.endswith("pages.dev")
            or u.hostname in ("greenjobs.ie", "greenjobs.co.uk")
            and not path.startswith("/api/")
        ):
            site = (
                "uk"
                if ("-uk." in u.hostname or u.hostname.endswith(".co.uk"))
                else "ie"
            )
            return self.board(path, self.redirects[site])
        return self.worker(method, u, path, q, headers, body)

    def board(self, path, redirects):
        if path in redirects and path != redirects[path]:
            target = "/ie/wrong/" if self.bad_redirect else redirects[path]
            return self.r(301, "", {"location": target})
        m = re.fullmatch(r"/(ie|uk)/dashboard/", path)
        if m:
            n = (
                len(self.live_ids())
                if self.dashboard_live is None
                else self.dashboard_live
            )
            if not self.markers:
                return self.r(200, f'<html><p class="n">{n:,}</p></html>')
            extra = f'<b data-stat="{self.extra_marker}">5</b>' if self.extra_marker else ""
            return self.r(200, f'<html><p data-stat="live_jobs">{n:,}</p><b class="kpi__v num" data-stat="kpis.live">{n}</b>{extra}</html>')
        if re.fullmatch(r"/(ie|uk)/", path) and self.markers:
            return self.r(200, f'<html><span data-live="n_jobs" data-stat="salary.n_jobs">{len(self.live_ids())}</span></html>')
        jm = re.fullmatch(r"/(ie|uk)/jobs/([^/]+)/", path)
        if jm and jm.group(2) in self.live_ids():  # production: the Worker route on the board host
            return self.job_page(jm.group(2))
        if path.startswith(("/ie/", "/uk/")):
            return self.r(200, "<html><body>board</body></html>")
        return self.r(404, "<html>404</html>")

    def job_page(self, slug):
        if self.no_job_page or slug not in self.live_ids():
            return self.r(404, "<html>gone</html>")
        return self.r(200, '<html><script type="application/ld+json">{"@type":"JobPosting"}</script></html>')

    def worker(self, method, u, path, q, headers, body):
        if path == "/api/health":
            return self.r(200, {"ok": True})
        if path == "/api/stats":
            n = len(self.live_ids()) + self.stats_off
            return self.r(200, {"live_jobs": n, "salary": {"n_jobs": n}, "kpis": {"live": n}})
        m = re.fullmatch(r"/(ie|uk)/jobs/([^/]+)/", path)
        if m and method == "GET":
            return self.job_page(m.group(2))
        if path == "/api/config":
            acao = {} if self.no_cors else {"access-control-allow-origin": headers.get("Origin", "")}
            return self.r(200, {"site": q["site"][0], "alerts": False, "newsletter": False}, acao)
        if path == "/api/jobs" and q.get("view") == ["board"]:
            ids = self.live_ids()
            limit = int(q.get("limit", ["200"])[0])
            after = q.get("after", [None])[0]
            start = ids.index(after) + 1 if after else 0
            page = ids[start : start + limit]
            nxt = page[-1] if start + limit < len(ids) else None
            return self.r(200, {"site": q["site"][0], "total": len(ids), "jobs": [{"id": i} for i in page], "next": nxt})
        if path == "/api/jobs":
            ids = self.live_ids()
            limit = int(q.get("limit", ["500"])[0])
            after = q.get("after", [None])[0]
            start = ids.index(after) + 1 if after else 0
            page = ids[start : start + limit]
            nxt = page[-1] if start + limit < len(ids) else None
            return self.r(200, {"jobs": [{"id": i} for i in page], "next": nxt})
        if path == "/api/export/jobs":
            return self.r(
                200 if headers.get("Authorization") == "Bearer bt" else 401, {}
            )
        m = re.fullmatch(r"/api/jobs/([^/]+)", path)
        if m and method == "GET":
            j = self.jobs.get(m.group(1))
            if j and j["status"] == "closed":
                return self.r(self.closed_status, {"error": "gone"})
            if j and m.group(1) in self.live_ids():
                return self.r(
                    200,
                    {
                        "id": m.group(1),
                        "apply_mode": j["mode"],
                        "apply_url": j.get("url"),
                    },
                )
            return self.r(404, {"error": "not_found"})
        if path == "/api/apply":
            assert headers["Content-Type"].startswith("multipart/form-data")
            jid = re.search(rb'name="job_id"\r\n\r\n([^\r]+)', body).group(1).decode()
            j = self.jobs[jid]
            if j["mode"] == "link":
                return self.r(409, {"error": "apply_externally"})
            if jid in self.applications:
                return self.r(200, {"ok": True, "status": "already_received"})
            self.applications.add(jid)
            return self.r(
                201, {"ok": True, "status": "received", "delivery": "dry_run"}
            )
        if path.startswith("/api/admin/"):
            if (
                headers.get("CF-Access-Client-Id") != "cid"
                or headers.get("CF-Access-Client-Secret") != "csec"
            ):
                return self.r(401, {"error": "unauthenticated"})
            if headers.get("Origin") != f"{u.scheme}://{u.netloc}" or not headers.get(
                "Idempotency-Key"
            ):
                return self.r(403, {"error": "csrf"})
            data = json.loads(body or b"{}")
            if path == "/api/admin/jobs" and method == "POST":
                key = headers["Idempotency-Key"]
                if key in self.idem:
                    return self.r(200, {"id": self.idem[key], "replayed": True})
                jid = f"ie:smoke-{len(self.jobs)}"
                self.idem[key] = jid
                self.jobs[jid] = {
                    "status": data["status"],
                    "mode": data["apply_mode"],
                    "url": data.get("apply_url"),
                    "created": self.clock.now(),
                }
                return self.r(201, {"id": jid, "version": 1})
            m = re.fullmatch(r"/api/admin/jobs/([^/]+)/close", path)
            if m and method == "POST":
                self.jobs[m.group(1)]["status"] = "closed"
                return self.r(200, {"id": m.group(1), "status": "closed"})
        return self.r(404, {"error": "not_found"})


@pytest.fixture()
def cfg():
    return json.loads(
        (
            ROOT
            / "execution/gtm_client_workflows/greenjobs_redesign/deploy/environments.json"
        ).read_text(encoding="utf-8")
    )


def run(cfg, env="staging", mode="full", secrets=SECRETS, canary=False, **mock_kw):
    clock = Clock()
    mock = MockGreenJobs(cfg, clock, **mock_kw)
    s = smoke.Smoke(
        cfg,
        env,
        mode,
        SHA,
        transport=mock,
        secrets=dict(secrets),
        sleep=clock.sleep,
        clock=clock.now,
        canary=canary,
    )
    res = s.run()
    by = {c["name"]: c for c in res["checks"]}
    return res, by, mock, clock


def failed(res):
    return sorted(c["name"] for c in res["checks"] if c["status"] == "fail")


def test_full_staging_pass(cfg):
    res, by, mock, clock = run(cfg)
    assert res["status"] == "pass", failed(res)
    for name in (
        "health[ie]",
        "jobs_api[ie]",
        "stats_parity[ie]",
        "board_list[uk]",
        "dashboard[ie]",
        "redirects[ie]",
        "redirects[uk]",
        "export_auth",
        "admin_create[email]",
        "job_visible[link]",
        "apply[link]",
        "apply[email]",
        "admin_close[email]",
        "closed_status[link]",
        "security_headers[worker:ie]",
        "security_headers[board:uk]",
    ):
        assert by[name]["status"] == "pass", name
    # staging has a Worker host per site (IE + the staging-uk deployment): no Worker check skips
    for name in ("health[uk]", "jobs_api[uk]", "stats_parity[uk]", "job_page[ie]", "job_page[uk]", "security_headers[worker:uk]"):
        assert by[name]["status"] == "pass", (name, by[name])
    assert [c["name"] for c in res["checks"] if c["status"] == "skip"] == []
    assert "figures compared: 3 (0 differ)" in by["stats_parity[uk]"]["detail"]
    assert any("staging-uk.debanjan186.workers.dev/api/health" in u for _, u in mock.requests)
    assert "1500 jobs over 2 page(s)" in by["jobs_api[ie]"]["detail"]
    assert "figures compared: 3 (0 differ)" in by["stats_parity[ie]"]["detail"]
    assert "20/20 ok" in by["redirects[ie]"]["detail"]
    assert 0 < clock.sleeps <= 900 // 30


def test_rerun_same_sha_converges(cfg):
    """A second smoke run for the same sha passes again and leaves nothing open behind it."""
    clock = Clock()
    mock = MockGreenJobs(cfg, clock)
    for _ in range(2):
        res = smoke.Smoke(cfg, "staging", "full", SHA, transport=mock, secrets=SECRETS, sleep=clock.sleep, clock=clock.now).run()
        assert res["status"] == "pass", failed(res)
    smoke_jobs = [j for k, j in mock.jobs.items() if k.startswith("ie:smoke-")]
    assert len(smoke_jobs) == 4 and all(j["status"] == "closed" for j in smoke_jobs)


def test_retry_within_a_run_reuses_idempotency_key(cfg):
    clock = Clock()
    mock = MockGreenJobs(cfg, clock)
    s = smoke.Smoke(cfg, "staging", "full", SHA, transport=mock, secrets=SECRETS, sleep=clock.sleep, clock=clock.now, run_id="r1")
    a = s.admin("POST", "https://w.example", "/api/admin/jobs", {"status": "draft", "apply_mode": "link"}, "create-x")
    b = s.admin("POST", "https://w.example", "/api/admin/jobs", {"status": "draft", "apply_mode": "link"}, "create-x")
    assert a.json()["id"] == b.json()["id"] and b.json().get("replayed")


def test_closed_job_must_be_410(cfg):
    res, _by, *_ = run(cfg, closed_status=404)
    assert failed(res) == ["closed_status[email]", "closed_status[link]"]


def test_job_never_visible_times_out_bounded(cfg):
    res, by, _mock, clock = run(cfg, visible_after_s=10_000)
    assert "job_visible[email]" in failed(res) and "job_visible[link]" in failed(res)
    assert clock.sleeps <= 2 * (900 // 30 + 1)
    assert (
        by["admin_close[email]"]["status"] == "pass"
    ), "jobs opened by the run are closed even after a failure"


def test_stats_mismatch_fails(cfg):
    res, *_ = run(cfg, stats_off=3)
    assert "stats_parity[ie]" in failed(res)


def test_dashboard_figure_mismatch_fails(cfg):
    res, by, *_ = run(cfg, dashboard_live=7)
    assert (
        "stats_parity[ie]" in failed(res)
        and "dashboard live_jobs=7" in by["stats_parity[ie]"]["detail"]
    )


def test_missing_security_header_fails(cfg):
    res, *_ = run(cfg, drop_header="x-frame-options")
    assert {"security_headers[board:ie]", "security_headers[worker:ie]"} <= set(
        failed(res)
    )


def test_bad_redirect_fails(cfg):
    res, by, *_ = run(cfg, bad_redirect=True)
    assert (
        "redirects[ie]" in failed(res) and "first bad" in by["redirects[ie]"]["detail"]
    )


def test_redirect_sample_is_deterministic_and_20(cfg):
    a = smoke.Smoke(cfg, "staging", "full", SHA).redirect_sample("ie")
    b = smoke.Smoke(cfg, "staging", "full", SHA).redirect_sample("ie")
    c = smoke.Smoke(cfg, "staging", "full", "f" * 40).redirect_sample("ie")
    assert a == b and len(a) == 20 and a != c


def test_network_error_is_a_failed_check_not_a_crash(cfg):
    _res, by, *_ = run(cfg, raise_on="/api/health")
    assert (
        by["health[ie]"]["status"] == "fail" and "HTTP 0" in by["health[ie]"]["detail"]
    )


def test_staging_full_without_access_token_fails(cfg):
    _res, by, mock, _ = run(cfg, secrets={"build_token": "bt"})
    assert by["write_flow"]["status"] == "fail"
    assert not any(m == "POST" for m, _ in mock.requests)


def test_production_read_only_writes_nothing(cfg):
    res, by, mock, _ = run(cfg, env="production", mode="read_only", secrets={})
    assert not any(m != "GET" for m, _ in mock.requests)
    assert by["export_auth"]["status"] == "skip"
    assert by["health[uk]"]["status"] == "pass"
    assert res["status"] == "pass", failed(res)


def test_production_canary_is_hidden_and_closed(cfg):
    res, by, mock, _ = run(cfg, env="production", mode="read_only", canary=True)
    assert res["status"] == "pass", failed(res)
    canary = [j for k, j in mock.jobs.items() if k.startswith("ie:smoke-")]
    assert len(canary) == 1 and canary[0]["status"] == "closed"
    assert by["canary_hidden"]["status"] == "pass"
    assert not any(m == "POST" and "/api/apply" in u for m, u in mock.requests)


def test_full_mode_never_runs_on_production(cfg):
    with pytest.raises(ValueError):
        run(cfg, env="production", mode="full")
    assert smoke.main(["--env", "production", "--mode", "full", "--sha", SHA]) == 2


def test_transport_refuses_plain_http():
    with pytest.raises(ValueError):
        smoke.urllib_transport("GET", "http://example.com/", {}, None)


def test_live_wiring_paginates_the_board_set_and_needs_cors(cfg):
    res, by, mock, _ = run(cfg)
    for site in ("ie", "uk"):
        assert by[f"live_wiring[{site}]"]["status"] == "pass", by[f"live_wiring[{site}]"]
        assert "board set 1500 over 3 page(s)" in by[f"live_wiring[{site}]"]["detail"]
    # staging boards read the workers.dev origin with ?site= (one Worker host serves both editions)
    assert any("/api/jobs?view=board&site=uk" in u and "workers.dev" in u for _, u in mock.requests)
    res, by, _, _ = run(cfg, no_cors=True)
    assert by["live_wiring[ie]"]["status"] == "fail" and "CORS missing" in by["live_wiring[ie]"]["detail"]
    res, by, _, _ = run(cfg, stats_off=1)
    assert by["live_wiring[ie]"]["status"] == "fail"


def test_smoke_apply_sends_render_timestamp():
    """Regression (staging 2026-11-20): apply returned 400 because the smoke omitted the form's
    render timestamp. The multipart body must carry a numeric `ts` at least 3 s in the past."""
    import re as _re
    import time as _time
    from pathlib import Path as _P
    src = (_P(__file__).resolve().parents[3] / "execution/gtm_client_workflows/greenjobs_redesign/deploy/smoke.py").read_text()
    assert '"ts": str(int(time.time() * 1000) - 5000)' in src
    assert _time.time() * 1000 - 5000 < _time.time() * 1000 - 3000
    assert _re.search(r'def apply\(self', src)


def test_stats_parity_with_no_figure_markers_fails(cfg):
    """A parity check that compares nothing must not pass (staging 2026-11-20: 'compared: none' was a PASS)."""
    res, by, *_ = run(cfg, markers=False)
    assert {"stats_parity[ie]", "stats_parity[uk]"} <= set(failed(res))
    assert "figures compared: none" in by["stats_parity[ie]"]["detail"]


def test_stats_parity_marker_with_unknown_key_fails(cfg):
    res, by, *_ = run(cfg, extra_marker="kpis.no_such_figure")
    assert "stats_parity[ie]" in failed(res)
    assert "kpis.no_such_figure=5 vs stats: no such figure" in by["stats_parity[ie]"]["detail"]


def test_stats_parity_compares_every_marker_dotted_and_flat(cfg):
    res, by, *_ = run(cfg, dashboard_live=7)
    d = by["stats_parity[ie]"]["detail"]
    assert "dashboard live_jobs=7" in d and "dashboard kpis.live=7" in d and "figures compared: 3 (2 differ)" in d


def test_job_page_must_render(cfg):
    res, by, *_ = run(cfg, no_job_page=True)
    assert {"job_page[ie]", "job_page[uk]"} <= set(failed(res))
    assert "/uk/jobs/" in by["job_page[uk]"]["detail"] and "HTTP 404" in by["job_page[uk]"]["detail"]


def test_stat_lookup_matches_build_site():
    sys.path.insert(0, str(ROOT / "execution/gtm_client_workflows/greenjobs_redesign"))
    import build_site

    stats = {"live_jobs": 3, "salary": {"n_jobs": 3, "median": "€5k"}, "kpis": {"days_to_close": None}}
    for key in ("live_jobs", "salary.n_jobs", "salary.median", "kpis.days_to_close", "kpis.nope", "salary.n_jobs.x"):
        assert smoke._stat_lookup(stats, key) == build_site.stat_lookup(stats, key), key
