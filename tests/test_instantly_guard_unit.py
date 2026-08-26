"""Unit tests for execution/infrastructure/instantly_guard.py.

Run: py -3.14 -m pytest tests/test_instantly_guard_unit.py -q

No network. Every external call is faked. The load-bearing tests are the
DEAD_VERDICTS ones -- they pin the invariant that a resolver failure can never
reach the deletion path (~/.claude/rules/probe-failure-is-not-a-verdict.md).
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = ROOT / "execution" / "infrastructure" / "instantly_guard.py"

_spec = importlib.util.spec_from_file_location("instantly_guard", MODULE_PATH)
guard = importlib.util.module_from_spec(_spec)
sys.modules["instantly_guard"] = guard
_spec.loader.exec_module(guard)


# ── the invariant that prevents mass deletion ────────────────────────────────

def test_dead_verdicts_contains_only_authoritative_negatives():
    assert set(guard.DEAD_VERDICTS) == {"NXDOMAIN", "NO_MX", "NULL_MX"}


@pytest.mark.parametrize("verdict", [
    "ERROR_TIMEOUT", "ERROR_SERVFAIL", "ERROR_OTHER", "ERROR_RESOLVER",
    "ERROR_RCODE_2", "ERROR_RCODE_5",
])
def test_no_error_verdict_is_ever_deletable(verdict):
    """A probe that could not complete must never trigger a delete."""
    assert verdict not in guard.DEAD_VERDICTS


def test_ok_is_not_deletable():
    assert "OK" not in guard.DEAD_VERDICTS


# ── domain parsing ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("email,expected", [
    ("a@example.com", "example.com"),
    ("A.User@Example.COM", "example.com"),
    ("  spaced@example.co.uk  ", "example.co.uk"),
    ("x@sub.domain.example.io", "sub.domain.example.io"),
    ("weird+tag@ccm.net.br", "ccm.net.br"),
    ("a@b@example.com", "example.com"),          # rsplit takes the last @
])
def test_domain_of_valid(email, expected):
    assert guard.domain_of(email) == expected


@pytest.mark.parametrize("email", [
    "", None, "no-at-sign", "trailing@", "@leading.com",
    "a@localhost",                                # no dot -> not a public domain
    "a@-bad.com", "a@bad-.com", "a@bad_underscore.com",
])
def test_domain_of_rejects_junk(email):
    assert guard.domain_of(email) is None


# ── chunking ─────────────────────────────────────────────────────────────────

def test_chunked_splits_and_preserves_order():
    assert list(guard.chunked(list(range(7)), 3)) == [[0, 1, 2], [3, 4, 5], [6]]


def test_chunked_empty():
    assert list(guard.chunked([], 10)) == []


def test_bulk_caps_match_documented_api_limits():
    assert guard.BULK_BLOCKLIST_MAX == 1000
    assert guard.BULK_DELETE_MAX == 10000


# ── DoH classification ───────────────────────────────────────────────────────

def _screen_with(monkeypatch, responses):
    """Build an MxScreen whose DoH layer returns canned (status, answers)."""
    screen = guard.MxScreen.__new__(guard.MxScreen)
    screen._cache = {}
    import threading
    screen._lock = threading.Lock()
    screen.timeout = 1.0
    screen.backend = "doh"
    screen._resolver = None

    def fake(domain, rrtype):
        return responses[rrtype]

    monkeypatch.setattr(screen, "_doh_query", fake)
    return screen


def test_doh_nxdomain(monkeypatch):
    s = _screen_with(monkeypatch, {"MX": (3, []), "A": (3, [])})
    assert s.classify("nope.example")[0] == "NXDOMAIN"


def test_doh_no_mx_when_domain_exists(monkeypatch):
    """NOERROR + no MX, but the domain has an A record -> genuinely takes no mail."""
    s = _screen_with(monkeypatch, {"MX": (0, []), "A": (0, ["1.2.3.4"])})
    assert s.classify("web-only.example")[0] == "NO_MX"


def test_doh_empty_mx_but_nonexistent_domain_is_nxdomain(monkeypatch):
    """The A-record follow-up must be able to override NO_MX."""
    s = _screen_with(monkeypatch, {"MX": (0, []), "A": (3, [])})
    assert s.classify("gone.example")[0] == "NXDOMAIN"


def test_doh_null_mx_rfc7505(monkeypatch):
    s = _screen_with(monkeypatch, {"MX": (0, ["0 ."]), "A": (0, [])})
    verdict, records = s.classify("refuses.example")
    assert verdict == "NULL_MX"
    assert records == "."


def test_doh_ok(monkeypatch):
    s = _screen_with(monkeypatch, {"MX": (0, ["10 alt1.aspmx.l.google.com."]), "A": (0, [])})
    verdict, records = s.classify("good.example")
    assert verdict == "OK"
    assert records == "alt1.aspmx.l.google.com"


def test_doh_transport_failure_is_error_not_dead(monkeypatch):
    """The regression that matters: a dead resolver must not condemn the domain."""
    s = guard.MxScreen.__new__(guard.MxScreen)
    s._cache = {}
    import threading
    s._lock = threading.Lock()
    s.timeout = 1.0
    s.backend = "doh"
    s._resolver = None

    def boom(domain, rrtype):
        raise OSError("all DoH endpoints failed")

    monkeypatch.setattr(s, "_doh_query", boom)
    verdict, _ = s.classify("unreachable.example")
    assert verdict == "ERROR_RESOLVER"
    assert verdict not in guard.DEAD_VERDICTS


def test_classify_is_cached(monkeypatch):
    calls = []
    s = _screen_with(monkeypatch, {"MX": (0, ["10 mx.example."]), "A": (0, [])})
    real = s._doh_query

    def counting(domain, rrtype):
        calls.append(domain)
        return real(domain, rrtype)

    monkeypatch.setattr(s, "_doh_query", counting)
    s.classify("x.example")
    s.classify("x.example")
    s.classify("x.example")
    assert len(calls) == 1


def test_screen_returns_a_verdict_per_domain(monkeypatch):
    s = _screen_with(monkeypatch, {"MX": (0, ["10 mx.example."]), "A": (0, [])})
    out = s.screen(["a.example", "b.example", "c.example"], workers=3)
    assert set(out) == {"a.example", "b.example", "c.example"}
    assert all(v[0] == "OK" for v in out.values())


# ── HTTP client behaviour ────────────────────────────────────────────────────

def test_content_type_only_sent_when_body_present(monkeypatch):
    """Fastify rejects Content-Type: application/json with an empty body as
    400 FST_ERR_CTP_EMPTY_JSON_BODY, which silently breaks DELETE /leads/{id}."""
    seen = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        seen["headers"] = dict(req.headers)
        seen["method"] = req.get_method()
        return FakeResponse()

    monkeypatch.setattr(guard.urllib.request, "urlopen", fake_urlopen)
    api = guard.Instantly("fake-key-never-logged")

    api.call("DELETE", "/leads/abc")
    lowered = {k.lower() for k in seen["headers"]}
    assert "content-type" not in lowered, "bodyless DELETE must not declare a JSON body"
    assert seen["method"] == "DELETE"

    api.call("POST", "/leads/list", {"campaign": "x"})
    lowered = {k.lower() for k in seen["headers"]}
    assert "content-type" in lowered, "a request WITH a body must declare its type"


def test_user_agent_is_set(monkeypatch):
    """Instantly sits behind Cloudflare, which 403s urllib's default UA (error 1010)."""
    seen = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b"{}"

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    monkeypatch.setattr(
        guard.urllib.request, "urlopen",
        lambda req, timeout=None: (seen.update(headers=dict(req.headers)), FakeResponse())[1],
    )
    guard.Instantly("k").call("GET", "/campaigns/x")
    ua = next(v for k, v in seen["headers"].items() if k.lower() == "user-agent")
    assert "Mozilla" in ua


# ── env + state ──────────────────────────────────────────────────────────────

def test_load_env_file_parses_and_strips(tmp_path):
    f = tmp_path / ".env"
    f.write_text(
        '# comment\n'
        'PLAIN=value\n'
        'QUOTED="quoted value"\n'
        "SINGLE='single'\n"
        '\n'
        'WITH_EQUALS=a=b=c\n',
        encoding="utf-8",
    )
    env = guard.load_env_file(f)
    assert env["PLAIN"] == "value"
    assert env["QUOTED"] == "quoted value"
    assert env["SINGLE"] == "single"
    assert env["WITH_EQUALS"] == "a=b=c"
    assert "# comment" not in env


def test_load_env_file_missing_returns_empty(tmp_path):
    assert guard.load_env_file(tmp_path / "nope.env") == {}


def test_resolve_api_key_prefers_environment(monkeypatch, tmp_path):
    f = tmp_path / ".env"
    f.write_text("MY_KEY=from-file\n", encoding="utf-8")
    monkeypatch.setenv("MY_KEY", "from-env")
    assert guard.resolve_api_key("MY_KEY", f) == "from-env"


def test_resolve_api_key_falls_back_to_file(monkeypatch, tmp_path):
    f = tmp_path / ".env"
    f.write_text("MY_KEY=from-file\n", encoding="utf-8")
    monkeypatch.delenv("MY_KEY", raising=False)
    assert guard.resolve_api_key("MY_KEY", f) == "from-file"


def test_resolve_api_key_missing_exits(monkeypatch, tmp_path):
    monkeypatch.delenv("ABSENT_KEY", raising=False)
    with pytest.raises(SystemExit):
        guard.resolve_api_key("ABSENT_KEY", tmp_path / "nope.env")


def test_state_roundtrip_is_atomic(tmp_path):
    path = tmp_path / "state.json"
    state = {"campaigns": {"cid": {"last_run": "2026-08-26T00:00:00+00:00",
                                   "seen_bounce_ids": ["a", "b"],
                                   "blocklisted_domains": ["x.com"]}}}
    guard.save_state(path, state)
    assert guard.load_state(path) == state
    assert not path.with_suffix(path.suffix + ".tmp").exists()


def test_load_state_survives_corruption(tmp_path):
    path = tmp_path / "state.json"
    path.write_text("{not json", encoding="utf-8")
    assert guard.load_state(path) == {"campaigns": {}}


def test_campaign_status_labels_match_docs():
    assert guard.CAMPAIGN_STATUS[-2] == "Bounce Protect"
    assert guard.CAMPAIGN_STATUS[1] == "Active"
    assert guard.CAMPAIGN_STATUS[-99] == "Account Suspended"


def test_lead_status_bounced_is_minus_one():
    assert guard.LEAD_STATUS[-1] == "Bounced"


# ── CLI contract ─────────────────────────────────────────────────────────────

def test_dry_run_is_the_default():
    args = guard.build_parser().parse_args(["some-campaign-id"])
    assert args.dry_run is True


def test_no_dry_run_flag_disables_it():
    args = guard.build_parser().parse_args(["cid", "--no-dry-run"])
    assert args.dry_run is False


def test_default_key_env_is_the_notifier_key():
    args = guard.build_parser().parse_args(["cid"])
    assert args.api_key_env == "INSTANTLY_NOTIFIER_API_KEY"


def test_resolver_defaults_to_auto():
    assert guard.build_parser().parse_args(["cid"]).resolver == "auto"


def test_module_never_references_the_activate_endpoint():
    """The script must not be able to resume a campaign."""
    src = MODULE_PATH.read_text(encoding="utf-8")
    assert "/activate" not in src


# ── mutation path (added after the 2026-08-26 Cherny-lens FAIL) ──────────────
#
# The --no-dry-run path was originally covered only by an argparse assertion,
# which proves the flag parses and nothing about what the flag DOES. These
# exercise run() end-to-end against a fake API and assert on the calls made.

class FakeInstantly:
    """Records every call so a test can assert what the run actually did."""

    def __init__(self, *_a, **_kw):
        self.calls = 0
        self.recorded: list[tuple] = []
        self.bounced = [
            {"id": "b1", "email": "x@deadco.com", "status": -1},
            {"id": "b2", "email": "y@deadco.com", "status": -1},
            {"id": "b3", "email": "z@othergone.net", "status": -1},
        ]
        # n6 and n7 are the poison pills: the upstream FILTER_VAL_NOT_CONTACTED
        # hands them over, but both show evidence of having been contacted and
        # both sit on DEAD domains. If the guard trusts the filter's name, it
        # deletes real send history. This is the exact shape of the 2026-08-26
        # live incident an audit surfaced.
        self.not_contacted = [
            {"id": "n1", "email": "a@nxdomain.test", "status": 1},
            {"id": "n2", "email": "b@nomx.test", "status": 1},
            {"id": "n3", "email": "c@nullmx.test", "status": 1},
            {"id": "n4", "email": "d@fine.test", "status": 1},
            {"id": "n5", "email": "e@flaky.test", "status": 1},
            {"id": "n6", "email": "f@nxdomain.test", "status": 3},
            {"id": "n7", "email": "g@nomx.test", "status": 1,
             "timestamp_last_contact": "2026-08-20T10:00:00Z"},
        ]

    def expect(self, method, path, body=None):
        self.recorded.append((method, path, body))
        self.calls += 1
        if path.startswith("/campaigns/"):
            return {"name": "Fake Campaign", "status": -2, "allow_risky_contacts": False}
        if path == "/block-lists-entries/bulk-create":
            return {"items": [{"bl_value": v} for v in body["bl_values"]],
                    "valid_count": len(body["bl_values"]), "invalid_count": 0}
        if path == "/leads" and method == "DELETE":
            return {"count": len(body["ids"])}
        raise AssertionError(f"unexpected call {method} {path}")

    def list_leads(self, campaign_id, lead_filter=None):
        self.recorded.append(("LIST", lead_filter, None))
        if lead_filter == "FILTER_VAL_BOUNCED":
            return list(self.bounced)
        if lead_filter == "FILTER_VAL_NOT_CONTACTED":
            return list(self.not_contacted)
        return list(self.bounced) + list(self.not_contacted)

    def already_blocklisted(self, candidates):
        return set()


class FakeScreen:
    backend = "fake"
    VERDICTS = {
        "nxdomain.test": ("NXDOMAIN", ""),
        "nomx.test": ("NO_MX", ""),
        "nullmx.test": ("NULL_MX", "."),
        "fine.test": ("OK", "mx.fine.test"),
        "flaky.test": ("ERROR_TIMEOUT", ""),   # must survive the cull
    }

    def __init__(self, *_a, **_kw):
        pass

    def screen(self, domains, workers=10):
        return {d: self.VERDICTS[d] for d in domains}


def _args(tmp_path, dry_run: bool):
    argv = ["fake-campaign-id",
            "--state-file", str(tmp_path / "state.json"),
            "--log-dir", str(tmp_path / "logs"),
            "--env-file", str(tmp_path / ".env")]
    if not dry_run:
        argv.append("--no-dry-run")
    return guard.build_parser().parse_args(argv)


@pytest.fixture
def wired(monkeypatch, tmp_path):
    (tmp_path / ".env").write_text("INSTANTLY_NOTIFIER_API_KEY=fake\n", encoding="utf-8")
    monkeypatch.delenv("INSTANTLY_NOTIFIER_API_KEY", raising=False)
    fake = FakeInstantly()
    monkeypatch.setattr(guard, "Instantly", lambda *a, **k: fake)
    monkeypatch.setattr(guard, "MxScreen", FakeScreen)
    return fake


def test_dry_run_makes_no_mutating_call(wired, tmp_path):
    summary = guard.run(_args(tmp_path, dry_run=True))
    mutations = [r for r in wired.recorded
                 if r[0] == "DELETE" or r[1] == "/block-lists-entries/bulk-create"]
    assert mutations == [], f"dry run performed mutations: {mutations}"
    assert summary["would_blocklist"] == 2      # deadco.com, othergone.net
    assert summary["would_delete"] == 3         # nxdomain + nomx + nullmx
    assert summary["deleted"] == 0
    assert summary["blocklisted"] == []
    assert summary["state_file"] == "(not written -- dry run)"
    assert not (tmp_path / "state.json").exists()


def test_no_dry_run_blocklists_and_deletes(wired, tmp_path):
    summary = guard.run(_args(tmp_path, dry_run=False))

    blocklist_calls = [r for r in wired.recorded if r[1] == "/block-lists-entries/bulk-create"]
    assert len(blocklist_calls) == 1
    assert sorted(blocklist_calls[0][2]["bl_values"]) == ["deadco.com", "othergone.net"]

    delete_calls = [r for r in wired.recorded if r[0] == "DELETE"]
    assert len(delete_calls) == 1
    assert sorted(delete_calls[0][2]["ids"]) == ["n1", "n2", "n3"]
    assert delete_calls[0][2]["campaign_id"] == "fake-campaign-id"

    assert summary["deleted"] == 3
    assert summary["would_delete"] == 0
    assert sorted(summary["blocklisted"]) == ["deadco.com", "othergone.net"]


def test_lead_on_error_verdict_domain_is_never_deleted(wired, tmp_path):
    """flaky.test resolves ERROR_TIMEOUT -- lead n5 must survive."""
    guard.run(_args(tmp_path, dry_run=False))
    deleted_ids = [r for r in wired.recorded if r[0] == "DELETE"][0][2]["ids"]
    assert "n5" not in deleted_ids
    assert "n4" not in deleted_ids          # OK domain, also safe


def test_no_dry_run_persists_state_for_next_run(wired, tmp_path):
    guard.run(_args(tmp_path, dry_run=False))
    state = json.loads((tmp_path / "state.json").read_text(encoding="utf-8"))
    entry = state["campaigns"]["fake-campaign-id"]
    assert sorted(entry["seen_bounce_ids"]) == ["b1", "b2", "b3"]
    assert sorted(entry["blocklisted_domains"]) == ["deadco.com", "othergone.net"]
    assert entry["last_run"]


def test_second_run_reports_no_new_bounces(wired, tmp_path):
    guard.run(_args(tmp_path, dry_run=False))
    wired.recorded.clear()
    second = guard.run(_args(tmp_path, dry_run=False))
    assert second["bounced_total"] == 3
    assert second["bounced_new"] == 0, "already-seen bounces must not re-trigger"
    assert [r for r in wired.recorded if r[1] == "/block-lists-entries/bulk-create"] == []


def test_run_writes_a_dated_log_line(wired, tmp_path):
    guard.run(_args(tmp_path, dry_run=False))
    logs = list((tmp_path / "logs").glob("instantly_guard_fake-cam_*.log"))
    assert len(logs) == 1
    line = json.loads(logs[0].read_text(encoding="utf-8").strip().splitlines()[-1])
    assert line["deleted"] == 3
    assert line["dry_run"] is False


def test_run_never_calls_activate(wired, tmp_path):
    guard.run(_args(tmp_path, dry_run=False))
    assert not any("activate" in str(r[1]) for r in wired.recorded)


def test_contacted_lead_on_dead_domain_is_never_deleted(wired, tmp_path):
    """Defence in depth: the upstream filter is trusted for scope, never for safety.

    n6 (status 3 = Completed) and n7 (populated timestamp_last_contact) both sit
    on dead domains and are both returned by FILTER_VAL_NOT_CONTACTED in this
    fake. Deleting them would destroy send history for zero deliverability gain,
    because a lead that has already been contacted cannot bounce again.
    """
    summary = guard.run(_args(tmp_path, dry_run=False))
    deleted_ids = [r for r in wired.recorded if r[0] == "DELETE"][0][2]["ids"]
    assert "n6" not in deleted_ids, "deleted a Completed lead"
    assert "n7" not in deleted_ids, "deleted a lead with a last-contact timestamp"
    assert sorted(deleted_ids) == ["n1", "n2", "n3"]
    assert summary["pending_excluded_as_contacted"] == 2


def test_excluded_contacted_leads_are_reported_not_hidden(wired, tmp_path):
    """The exclusion must be visible in the summary and the dated log, so an
    operator can see the guard declined to touch something."""
    summary = guard.run(_args(tmp_path, dry_run=True))
    assert summary["pending_excluded_as_contacted"] == 2
    assert summary["not_contacted"] == 5, "post-filter pending count"


# ── owed tests named by the 2026-08-26 adversarial audit ─────────────────────

def test_classify_system_downgrades_raw_oserror(monkeypatch):
    """dnspython does not wrap every socket failure. An unwrapped OSError used to
    propagate through ThreadPoolExecutor.map and kill the entire run."""
    if not guard.HAVE_DNSPYTHON:
        pytest.skip("dnspython not importable in this interpreter")

    screen = guard.MxScreen.__new__(guard.MxScreen)
    screen._cache = {}
    import threading
    screen._lock = threading.Lock()
    screen.timeout = 1.0
    screen.backend = "system"

    class BoomResolver:
        def resolve(self, *_a, **_kw):
            raise OSError("[Errno 101] Network is unreachable")

    screen._resolver = BoomResolver()
    verdict, detail = screen.classify("whatever.test")
    assert verdict == "ERROR_OTHER"
    assert verdict not in guard.DEAD_VERDICTS
    assert "OSError" in detail


def test_classify_system_survives_one_bad_domain_in_a_batch(monkeypatch):
    """One exploding domain must not take out the whole screen."""
    if not guard.HAVE_DNSPYTHON:
        pytest.skip("dnspython not importable in this interpreter")

    screen = guard.MxScreen.__new__(guard.MxScreen)
    screen._cache = {}
    import threading
    screen._lock = threading.Lock()
    screen.timeout = 1.0
    screen.backend = "system"

    class MixedResolver:
        def resolve(self, name, _rr):
            if name == "boom.test":
                raise OSError("socket died")
            class R:
                exchange = "mx.ok.test."
            return [R()]

    screen._resolver = MixedResolver()
    out = screen.screen(["boom.test", "fine.test"], workers=2)
    assert out["boom.test"][0] == "ERROR_OTHER"
    assert out["fine.test"][0] == "OK"


def test_already_blocklisted_ignores_wildcard_entries(monkeypatch):
    """A wildcard-stored value must not be mistaken for an exact match.

    Documents the trade-off: '*.domain.com' does NOT count as domain.com being
    blocked, so the domain gets re-submitted. Redundant, never wrong -- the
    failure mode we refuse is treating a near-match as 'already handled' and
    silently skipping a real blocklist write.
    """
    class FakeResponse:
        status = 200

        def __init__(self, payload):
            self._payload = payload

        def read(self):
            return json.dumps(self._payload).encode()

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_urlopen(req, timeout=None):
        return FakeResponse({"items": [{"bl_value": "*.domain.com"},
                                       {"bl_value": "other.com"}]})

    monkeypatch.setattr(guard.urllib.request, "urlopen", fake_urlopen)
    api = guard.Instantly("k")
    assert api.already_blocklisted(["domain.com"]) == set()
    assert api.already_blocklisted(["other.com"]) == {"other.com"}


def test_second_run_does_not_redelete_already_removed_leads(wired, tmp_path):
    """Fake fidelity: a real second list_leads() omits deleted leads. Mirror that,
    so the test proves run-to-run dead-lead idempotency rather than assuming it."""
    guard.run(_args(tmp_path, dry_run=False))
    deleted = set([r for r in wired.recorded if r[0] == "DELETE"][0][2]["ids"])
    wired.not_contacted = [l for l in wired.not_contacted if l["id"] not in deleted]
    wired.recorded.clear()

    second = guard.run(_args(tmp_path, dry_run=False))
    assert second["dead_leads"] == 0
    assert [r for r in wired.recorded if r[0] == "DELETE"] == []


# ── concurrency + abort logging (added after the honest-gaps audit) ──────────

def test_state_lock_refuses_a_concurrent_run(tmp_path):
    state = tmp_path / "state.json"
    with guard.StateLock(state):
        with pytest.raises(SystemExit) as excinfo:
            with guard.StateLock(state):
                pass
    assert "Refusing to run concurrently" in str(excinfo.value)


def test_state_lock_releases_on_exit(tmp_path):
    state = tmp_path / "state.json"
    lock = state.with_suffix(state.suffix + ".lock")
    with guard.StateLock(state):
        assert lock.exists()
    assert not lock.exists()


def test_state_lock_steals_a_stale_lock(tmp_path):
    """One crash must not wedge the cron forever."""
    state = tmp_path / "state.json"
    lock = state.with_suffix(state.suffix + ".lock")
    lock.write_text("99999", encoding="utf-8")
    import os as _os
    _os.utime(lock, (0, 0))          # epoch mtime == very stale
    with guard.StateLock(state, stale_after=60.0):
        assert lock.exists()
    assert not lock.exists()


def test_abort_mid_mutation_still_writes_a_log_line(wired, tmp_path):
    """The destructive action must never be invisible. If a delete batch dies,
    the partial summary is still logged before the exception propagates."""
    original = wired.expect

    def explode(method, path, body=None):
        if method == "DELETE":
            raise SystemExit("FATAL: DELETE /leads -> HTTP 500")
        return original(method, path, body)

    wired.expect = explode

    with pytest.raises(SystemExit):
        guard.run(_args(tmp_path, dry_run=False))

    logs = list((tmp_path / "logs").glob("instantly_guard_*.log"))
    assert len(logs) == 1, "abort produced no log file"
    entry = json.loads(logs[0].read_text(encoding="utf-8").strip().splitlines()[-1])
    assert "aborted" in entry
    assert "HTTP 500" in entry["aborted"]
    # the blocklist write that DID land must be visible in the partial record
    assert sorted(entry["blocklisted"]) == ["deadco.com", "othergone.net"]


def test_abort_releases_the_lock(wired, tmp_path):
    def explode(method, path, body=None):
        raise SystemExit("boom")

    wired.expect = explode
    state = tmp_path / "state.json"
    with pytest.raises(SystemExit):
        guard.run(_args(tmp_path, dry_run=False))
    assert not state.with_suffix(state.suffix + ".lock").exists()
