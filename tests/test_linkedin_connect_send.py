"""Offline tests for execution/personal_workflows/linkedin_connect_send.py.

Page logic runs against local HTML fixtures (tests/fixtures/linkedin/) in Playwright's bundled
Chromium; nothing touches LinkedIn, SMTP or Task Scheduler.
"""
from __future__ import annotations

import contextlib
import datetime as dt
import email
import email.header
import importlib.util
import io
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FIX = ROOT / "tests" / "fixtures" / "linkedin"
_spec = importlib.util.spec_from_file_location(
    "linkedin_connect_send", ROOT / "execution" / "personal_workflows" / "linkedin_connect_send.py")
S = importlib.util.module_from_spec(_spec)
sys.modules["linkedin_connect_send"] = S
_spec.loader.exec_module(S)
Q = S.Q

MON, WED, THU, SUN = dt.date(2026, 11, 2), dt.date(2026, 11, 4), dt.date(2026, 11, 5), dt.date(2026, 11, 8)


def _chromium_exe() -> str | None:
    for c in (os.environ.get("LINKEDIN_TEST_CHROMIUM"), "/opt/pw-browsers/chromium"):
        if c and Path(c).exists():
            return c
    return None


@pytest.fixture(autouse=True)
def _fast_and_isolated(monkeypatch, tmp_path):
    monkeypatch.setattr(S, "EML_DIR", tmp_path / "eml")  # never write into the repo's .tmp from tests
    monkeypatch.setattr(Q, "_today", lambda: "2026-11-02")  # the queue's local date, pinned to MON for tests
    monkeypatch.setattr(S, "CONFIRM_TIMEOUT_MS", 3_000)
    monkeypatch.setattr(S, "RENDER_TIMEOUT_MS", 3_000)
    monkeypatch.setattr(S, "NAV_TIMEOUT_MS", 5_000)
    monkeypatch.setattr(S, "UI_RETRY_PAUSE_S", (0, 0))


@pytest.fixture(scope="module")
def browser():
    pw_mod = pytest.importorskip("playwright.sync_api")
    with pw_mod.sync_playwright() as pw:
        exe = _chromium_exe()
        b = pw.chromium.launch(headless=True, **({"executable_path": exe} if exe else {}))
        yield b
        b.close()


@pytest.fixture
def page(browser):
    ctx = browser.new_context()
    p = ctx.new_page()
    yield p
    ctx.close()


def url(name: str) -> str:
    return (FIX / name).as_uri()


def seed(data_dir: Path, people: list[tuple[str, str]], sent_today: int = 0, day: str = "2026-11-02") -> Q.Store:
    """people: (slug, fixture file or raw URL). sent_today: extra already-sent master rows."""
    rows = [{"slug": s, "name": f"{s.title()} Person", "company": "Acme & Co", "position": "CTO",
             "linkedin_url": u if "://" in u else url(u), "source_file": "t.csv"} for s, u in people]
    done = [{"slug": f"done{i}", "name": f"Done {i}", "company": "X", "position": "Y",
             "linkedin_url": url("connect_header.html"), "source_file": "t.csv"} for i in range(sent_today)]
    Q.write_csv(data_dir / "master.csv", rows + done, Q.FIELDS)
    store = Q.Store(data_dir)
    for r in done:
        store.append_ledger({"ts": f"{day}T09:00:00", "date": day, "slug": r["slug"], "name": r["name"],
                             "status": "sent", "note": ""})
    return store


def ledger(store: Q.Store) -> dict[str, tuple[str, str]]:
    return {r["slug"]: (r["status"], r["note"]) for r in store.load_ledger() if not r["slug"].startswith("done")}


# ----------------------------------------------------------------- page states

@pytest.mark.parametrize("fixture,status,note", [
    ("connect_header.html", "sent", ""),
    ("connect_more.html", "sent", ""),
    ("pending.html", "pending", ""),
    ("first_degree.html", "already_connected", ""),
    ("follow_only.html", "retry", "no_connect_button"),
    ("no_more.html", "retry", "no_connect_button:more_missing"),
    ("msg_overlay.html", "sent", ""),
    ("sticky_cover.html", "sent", ""),
    ("header_second_section.html", "sent", ""),
    ("portaled_menu.html", "sent", ""),
    ("rerender.html", "sent", ""),
    ("email_required.html", "skipped", "email_required"),
    ("not_found.html", "skipped", "profile_gone"),
    ("no_confirm.html", "retry", "unconfirmed"),
])
def test_profile_states(page, fixture, status, note):
    out = S.process_profile(page, url(fixture), "jane-doe")
    assert (out.status, out.note, out.stop) == (status, note, None)
    assert not page.evaluate("window.noteClicked || false"), "never add a note"
    assert not page.evaluate("window.otherClicked || false"), "never click a sidebar Connect"


@pytest.mark.parametrize("fixture,reason", [
    ("weekly_limit.html", "weekly invitation limit"),
    ("security_check.html", "security check"),
    ("logged_out.html", "not logged in"),
])
def test_stop_states(page, fixture, reason):
    out = S.process_profile(page, url(fixture), "jane-doe")
    assert out.stop == reason and out.status is None


def test_more_menu_sends_via_alert_and_pending_flip(page):
    out = S.process_profile(page, url("connect_more.html"), "jane-doe")
    assert out.status == "sent"
    assert page.evaluate("window.connectClicked") == 1 and page.evaluate("window.sendClicked")
    assert page.get_by_role("button", name=S.PENDING_NAME).count() == 1


def test_dry_run_clicks_nothing(page):
    for fx in ("connect_header.html", "connect_more.html"):
        out = S.process_profile(page, url(fx), "jane-doe", dry_run=True)
        assert out.would_send and out.status is None
        assert not page.evaluate("window.connectClicked || 0")


def test_page_load_failure_is_retry(page):
    out = S.process_profile(page, "http://127.0.0.1:9/in/nobody/", "nobody")
    assert (out.status, out.note) == ("retry", "page_load_failed")


def test_canonical_slug():
    assert S.canonical_slug("https://www.linkedin.com/in/karthikachari/", "karthik-achari-54b347198") == "karthikachari"
    assert S.canonical_slug("https://www.linkedin.com/in/jane-doe/", "jane-doe") is None
    assert S.canonical_slug("file:///x/connect_header.html", "jane-doe") is None


# ----------------------------------------------------------------- the day's loop

def test_run_day_marks_each_outcome_and_sleeps_between(page, tmp_path):
    store = seed(tmp_path, [("a", "connect_header.html"), ("b", "pending.html"), ("c", "follow_only.html"),
                            ("d", "email_required.html"), ("e", "first_degree.html")])
    naps: list[float] = []
    res = S.run_day(page, store, "2026-11-02", sleep=naps.append)
    assert res.stop is None and res.sent_run == 1 and res.processed == 5
    assert ledger(store) == {"a": ("sent", ""), "b": ("pending", ""), "c": ("retry", "no_connect_button"),
                             "d": ("skipped", "email_required"), "e": ("already_connected", "")}
    gaps = [n for n in naps if n >= 45]
    assert len(gaps) == 4 and all(45 <= n <= 120 for n in gaps)
    assert naps.count(0) == 1  # the follow-only profile was reloaded once (UI failure), with its own short pause
    assert {r["date"] for r in store.load_ledger()} == {"2026-11-02"}


def test_run_day_respects_cap_and_replans_after_skips(page, tmp_path):
    people = [(f"s{i}", "follow_only.html") for i in range(2)] + [(f"c{i}", "connect_header.html") for i in range(4)]
    store = seed(tmp_path, people, sent_today=18)
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop is None and res.sent_run == 2
    assert len(Q._sent_on(store.load_ledger(), "2026-11-02")) == Q.DAILY_CAP


def test_run_day_stops_on_weekly_limit(page, tmp_path):
    store = seed(tmp_path, [("a", "weekly_limit.html")])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop == "weekly invitation limit" and ledger(store) == {}


def test_run_day_stops_after_three_consecutive_load_failures(page, tmp_path):
    store = seed(tmp_path, [(c, f"http://127.0.0.1:9/in/{c}/") for c in "abcdefg"])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop == "3 profiles in a row did not load or confirm" and res.processed == 3
    assert sorted(ledger(store).values()) == [("retry", "page_load_failed")] * 3


def test_ui_failures_do_not_trip_the_block_streak(page, tmp_path):
    """RCA 2026-11-10: five click/no-Connect retries in a row ended the day. They now neither stop it early
    nor reset into a block stop; a sendable person after them still gets the invitation."""
    people = [(f"f{i}", "follow_only.html") for i in range(6)] + [("ok", "connect_more.html")]
    store = seed(tmp_path, people)
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop is None and res.sent_run == 1 and ledger(store)["ok"] == ("sent", "")


def test_http_999_stops_the_day_and_marks_nothing(page, tmp_path):
    page.route("**/blocked/**", lambda route: route.fulfill(status=999, body="<html><body></body></html>"))
    store = seed(tmp_path, [("a", "https://www.linkedin.com/blocked/a/")])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop == "HTTP 999 (LinkedIn blocked the request)" and ledger(store) == {}


def test_debug_capture_saves_first_three_ui_failures(page, tmp_path):
    store = seed(tmp_path, [(f"f{i}", "no_more.html") for i in range(4)])
    S.run_day(page, store, "2026-11-02", sleep=lambda s: None, debug_dir=tmp_path / "debug")
    files = sorted(f.name for f in (tmp_path / "debug").iterdir())
    assert len(files) == 2 * S.DEBUG_CAPTURES_PER_RUN
    assert files[0].startswith("2026-11-02_") and "no_connect_button-more_missing" in files[0]
    assert all(r == ("retry", "no_connect_button:more_missing") for r in ledger(store).values())


def test_debug_capture_prunes_old_files(tmp_path):
    d = tmp_path / "debug"
    d.mkdir()
    old = d / "old.png"
    old.write_text("x")
    os.utime(old, (0, 0))
    S._debug_capturer(d, "2026-11-02")
    assert not old.exists()


def test_more_missing_is_not_final_on_day_three(tmp_path):
    """Only the Follow-only note counts toward no_connect_button_3x; an unreadable header can only reach retry_4x."""
    store = seed(tmp_path, [("m", "no_more.html")])
    for day in ("2026-10-30", "2026-10-31"):
        store.append_ledger({"ts": f"{day}T10:00:00", "date": day, "slug": "m", "name": "M",
                             "status": "retry", "note": "no_connect_button:more_missing"})
    S._quiet(Q.cmd_mark, store, "m", "retry", "no_connect_button:more_missing", None)
    assert "m" not in Q._blocked(store.load_ledger(), "2026-11-03")


def test_click_failure_kinds():
    assert S.click_failure_kind("<div class=x> intercepts pointer events") == "overlay_covered"
    assert S.click_failure_kind("element is not attached to the DOM") == "detached"
    assert S.click_failure_kind("element is not stable") == "unstable"
    assert S.click_failure_kind("Timeout 5000ms exceeded.") == "timeout"
    assert S.is_ui_failure("click_failed:overlay_covered") and S.is_ui_failure("no_connect_button")
    assert not S.is_ui_failure("page_load_failed") and not S.is_ui_failure("unconfirmed")


def test_no_connect_button_on_third_day_becomes_final(tmp_path):
    store = seed(tmp_path, [("f", "follow_only.html"), ("g", "follow_only.html")])
    for day in ("2026-10-30", "2026-10-31"):
        store.append_ledger({"ts": f"{day}T10:00:00", "date": day, "slug": "f", "name": "F",
                             "status": "retry", "note": "no_connect_button"})
    store.append_ledger({"ts": "2026-10-31T10:00:00", "date": "2026-10-31", "slug": "g", "name": "G",
                         "status": "retry", "note": "no_connect_button"})
    S._quiet(Q.cmd_mark, store, "f", "retry", "no_connect_button", None)  # 3rd distinct day -> final
    S._quiet(Q.cmd_mark, store, "g", "retry", "no_connect_button", None)  # 2nd day -> still retry
    today = [r for r in store.load_ledger() if r["date"] == "2026-11-02"]
    assert [(r["slug"], r["status"], r["note"]) for r in today] == [
        ("f", "skipped", "no_connect_button_3x"), ("g", "retry", "no_connect_button")]
    assert "f" in Q._blocked(store.load_ledger(), "2026-11-03")
    assert "g" not in Q._blocked(store.load_ledger(), "2026-11-03")


def test_run_day_dry_run_writes_no_ledger(page, tmp_path):
    store = seed(tmp_path, [("a", "connect_header.html"), ("b", "connect_more.html"), ("c", "pending.html")])
    res = S.run_day(page, store, "2026-11-02", dry_run=True, sleep=lambda s: None)
    assert sorted(r["slug"] for r in res.would_send) == ["a", "b"] and not store.ledger.exists()


# ----------------------------------------------------------------- calendar, cap, email

def test_send_days_and_cap_constants():
    assert [d for d in range(7) if S.is_send_day(MON + dt.timedelta(days=d))] == [0, 1, 3, 4, 5]
    assert not S.is_send_day(WED) and not S.is_send_day(SUN) and S.is_send_day(THU)
    assert Q.DAILY_CAP == 20 and Q.DAILY_CAP * len(S.SEND_DAYS) == 100


def test_room_left():
    assert S.room_left(0) == 20 and S.room_left(7) == 13 and S.room_left(20) == 0 and S.room_left(25) == 0


def test_subject():
    assert S.build_subject("2026-11-02", 20, None) == "LinkedIn connects 2026-11-02 (20 sent)"
    assert S.build_subject("2026-11-02", 3, "weekly invitation limit") == \
        "LinkedIn connects 2026-11-02 (3 sent) — STOPPED: weekly invitation limit"


def test_table_html_escapes_and_has_only_the_table():
    rows = [{"slug": "jo-o", "name": "Jo <b>O'Neil</b>", "company": "A & B", "position": 'Head "of" <x>'}]
    body = S.build_table_html(rows)
    assert body.strip().startswith("<table") and body.strip().endswith("</table>")
    assert "<b>" not in body and "&lt;b&gt;" in body and "A &amp; B" in body and "&quot;of&quot;" in body
    assert '<a href="https://www.linkedin.com/in/jo-o/">jo-o</a>' in body
    for h in ("#", "First name", "Name", "Company", "Position", "LinkedIn ID"):
        assert f">{h}</th>" in body
    assert ">Jo</td>" in body
    assert S.build_table_html([]).count("<tr>") == 1


# ----------------------------------------------------------------- cmd_run end to end

def _patch_browser(monkeypatch, browser):
    """cmd_run's browser = a fresh context on the shared test Chromium (one sync_playwright per process)."""
    @contextlib.contextmanager
    def fake_open(data_dir):
        ctx = browser.new_context()
        try:
            yield ctx.new_page()
        finally:
            ctx.close()
    monkeypatch.setattr(S, "open_browser", fake_open)
    monkeypatch.setattr(S.time, "sleep", lambda s: None)


def test_rest_day_is_silent_noop(tmp_path):
    seed(tmp_path, [("a", "connect_header.html")])
    before = sorted(p.name for p in tmp_path.iterdir())
    assert S.cmd_run(tmp_path, dry_run=False, today=WED) == 0
    assert S.cmd_run(tmp_path, dry_run=False, today=SUN) == 0
    assert sorted(p.name for p in tmp_path.iterdir()) == before


def test_marker_makes_run_idempotent(tmp_path, monkeypatch):
    seed(tmp_path, [("a", "connect_header.html")])
    S.marker_path(tmp_path, "2026-11-02").write_text("x", encoding="utf-8")
    monkeypatch.setattr(S, "launch_context", lambda *a, **k: pytest.fail("must not launch"))
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 0


def test_config_errors(tmp_path, monkeypatch):
    assert S.cmd_run(tmp_path / "empty", dry_run=True, today=MON) == 3
    seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.delenv("GMAIL_SMTP_USER", raising=False)
    monkeypatch.delenv("GMAIL_SMTP_APP_PASSWORD", raising=False)
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 3


def test_dry_run_writes_eml(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    seed(tmp_path / "d", [("a", "connect_header.html"), ("b", "follow_only.html")])
    monkeypatch.setattr(S, "EML_DIR", tmp_path / "eml")
    rc = S.cmd_run(tmp_path / "d", dry_run=True, today=MON)
    assert rc == 0
    msg = email.message_from_bytes((tmp_path / "eml" / "linkedin_connect_2026-11-02.eml").read_bytes())
    assert str(email.header.make_header(email.header.decode_header(msg["Subject"]))) == \
        "LinkedIn connects 2026-11-02 (1 sent)"
    assert msg.get_content_type() == "text/html" and not msg.is_multipart()
    assert "<table" in msg.get_payload(decode=True).decode()
    assert not S.marker_path(tmp_path / "d", "2026-11-02").exists() and not Q.Store(tmp_path / "d").ledger.exists()


class _FakeSMTP:
    sent: list = []

    def __init__(self, *a, **k): pass
    def __enter__(self): return self
    def __exit__(self, *a): return False
    def starttls(self): pass
    def login(self, u, p): pass
    def send_message(self, m): _FakeSMTP.sent.append(m)


def test_real_run_sends_one_email_and_writes_marker(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    monkeypatch.setattr(S.smtplib, "SMTP", _FakeSMTP)
    _FakeSMTP.sent = []
    store = seed(tmp_path, [("a", "connect_header.html"), ("b", "weekly_limit.html")])
    rc = S.cmd_run(tmp_path, dry_run=False, today=MON)
    sent_rows = Q._sent_on(store.load_ledger(), "2026-11-02")
    n = len(sent_rows)
    assert len(_FakeSMTP.sent) == 1
    subj = _FakeSMTP.sent[0]["Subject"]
    if n == 1:  # shuffled order: a first -> 1 sent then the limit; b first -> 0 sent
        assert rc == 2 and "(1 sent) — STOPPED: weekly invitation limit" in subj
    else:
        assert rc == 2 and "(0 sent) — STOPPED: weekly invitation limit" in subj
    assert S.marker_path(tmp_path, "2026-11-02").exists()
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 0 and len(_FakeSMTP.sent) == 1


def test_zero_sent_while_people_remain_is_stopped(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    monkeypatch.setattr(S, "EML_DIR", tmp_path / "eml")
    seed(tmp_path / "d", [("a", "follow_only.html"), ("b", "pending.html")])
    assert S.cmd_run(tmp_path / "d", dry_run=True, today=MON) == 2
    msg = email.message_from_bytes((tmp_path / "eml" / "linkedin_connect_2026-11-02.eml").read_bytes())
    assert _subject(msg).endswith("(0 sent) — STOPPED: 0 sent while people remained")


def _subject(msg) -> str:
    return str(email.header.make_header(email.header.decode_header(msg["Subject"])))


def _smtp_env(monkeypatch, fake):
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    monkeypatch.setattr(S.smtplib, "SMTP", fake)
    monkeypatch.setattr(S, "SMTP_RETRY_S", 0)


def test_missing_connect_everywhere_stops_after_ten(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    _smtp_env(monkeypatch, _FakeSMTP)
    _FakeSMTP.sent = []
    store = seed(tmp_path, [(f"f{i}", "follow_only.html") for i in range(12)])
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 2
    rows = ledger(store)
    assert len(rows) == S.MAX_UI_STREAK and all(v == ("retry", "no_connect_button") for v in rows.values())
    assert not any(st == "skipped" for st, _ in rows.values())
    assert _FakeSMTP.sent[0]["Subject"] == \
        "LinkedIn connects 2026-11-02 (0 sent) — STOPPED: 10 profiles in a row without a clickable Connect"


def test_visit_limit_and_time_budget(page, tmp_path, monkeypatch):
    monkeypatch.setattr(Q, "DAILY_CAP", 2)
    monkeypatch.setattr(S, "VISIT_FACTOR", 1)
    store = seed(tmp_path / "a", [("p1", "pending.html"), ("p2", "pending.html"), ("c", "connect_header.html")])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.processed == 2 and res.stop == "2 profiles visited, cap not reached"
    monkeypatch.setattr(S, "RUN_BUDGET_S", -1)
    store = seed(tmp_path / "b", [("c", "connect_header.html")])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.processed == 0 and res.stop == "time budget reached"


def test_worst_case_run_fits_task_limit():
    one_visit = (S.NAV_TIMEOUT_MS + S.RENDER_TIMEOUT_MS + S.SETTLE_MAX_MS + S.CONFIRM_TIMEOUT_MS
                 + 3 * (S.STABLE_MAX_MS + S.CLICK_TIMEOUT_MS)) / 1000  # More, Connect, Send
    per_profile = S.GAP_SECONDS[1] + S.UI_RETRY_PAUSE_S[1] + 2 * one_visit  # a UI failure is visited twice
    assert S.RUN_BUDGET_S + per_profile + 90 + S.SMTP_ATTEMPTS * (4 * 30 + S.SMTP_RETRY_S) < 3 * 3600  # 90 s Chrome start; 4 socket ops x 30 s per SMTP try


class _FlakySMTP(_FakeSMTP):
    calls = 0
    fail_first = 2

    def send_message(self, m):
        _FlakySMTP.calls += 1
        if _FlakySMTP.calls <= _FlakySMTP.fail_first:
            raise S.smtplib.SMTPServerDisconnected("boom")
        _FakeSMTP.sent.append(m)


def test_smtp_retries_then_succeeds(monkeypatch):
    _smtp_env(monkeypatch, _FlakySMTP)
    naps: list[float] = []
    monkeypatch.setattr(S.time, "sleep", naps.append)
    monkeypatch.setattr(S, "SMTP_RETRY_S", 7)
    _FakeSMTP.sent, _FlakySMTP.calls, _FlakySMTP.fail_first = [], 0, 2
    assert S.deliver("s", "<table></table>", "2026-11-02", dry_run=False)
    assert _FlakySMTP.calls == 3 and naps == [7, 7] and len(_FakeSMTP.sent) == 1


def test_smtp_gives_up_after_three_and_writes_no_marker(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    _smtp_env(monkeypatch, _FlakySMTP)
    _FakeSMTP.sent, _FlakySMTP.calls, _FlakySMTP.fail_first = [], 0, 99
    seed(tmp_path, [("a", "pending.html")])
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 3
    assert _FlakySMTP.calls == 3 and not S.marker_path(tmp_path, "2026-11-02").exists()


def test_chrome_missing_is_loud(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def no_chrome(data_dir):
        raise S.ChromeUnavailable("Google Chrome could not start (not found)")
        yield  # pragma: no cover
    monkeypatch.setattr(S, "open_browser", no_chrome)
    _smtp_env(monkeypatch, _FakeSMTP)
    _FakeSMTP.sent = []
    seed(tmp_path, [("a", "connect_header.html")])
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 3
    assert _FakeSMTP.sent[0]["Subject"].endswith("— STOPPED: Chrome not available")


def test_detect_stop_ignores_profile_body_text(page):
    page.set_content("<main><section><h1>A</h1><p>I run security check audits; weekly invitation limit expert.</p>"
                     "<button aria-label='Invite A to connect'>Connect</button></section></main>")
    assert S.detect_stop(page) is None


# ----------------------------------------------------------------- 2026-11-05: loud setup errors, lock, setup task

def test_missing_playwright_emails_stopped_without_marker(tmp_path, monkeypatch):
    """A job that cannot start the browser must still email (the 11-03..11-05 silent gap)."""
    seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    _FakeSMTP.sent = []
    monkeypatch.setattr(S.smtplib, "SMTP", _FakeSMTP)
    import builtins
    real_import = builtins.__import__

    def no_playwright(name, *a, **k):
        if name.startswith("playwright"):
            raise ImportError(name)
        return real_import(name, *a, **k)
    monkeypatch.setattr(builtins, "__import__", no_playwright)
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 3
    assert [m["Subject"] for m in _FakeSMTP.sent] == \
        ["LinkedIn connects 2026-11-02 (0 sent) — STOPPED: playwright not installed"]
    assert not S.marker_path(tmp_path, "2026-11-02").exists()  # a rerun after the fix still sends today


def test_live_lock_makes_second_run_a_silent_noop(tmp_path, monkeypatch):
    store = seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    with contextlib.redirect_stdout(io.StringIO()):
        assert Q.cmd_lock(store, "acquire") == 0
    monkeypatch.setattr(S, "launch_context", lambda *a, **k: pytest.fail("must not launch"))
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 0
    assert not S.marker_path(tmp_path, "2026-11-02").exists()


def test_run_releases_lock(tmp_path, monkeypatch, browser):
    _patch_browser(monkeypatch, browser)
    store = seed(tmp_path / "d", [("a", "connect_header.html")])
    monkeypatch.setattr(S, "EML_DIR", tmp_path / "eml")
    S.cmd_run(tmp_path / "d", dry_run=True, today=MON)
    assert not (tmp_path / "d" / "send.lock").exists() and Q._lock_age_min(store) is None


def test_send_lock_is_exclusive_and_stale_is_taken_over(tmp_path):
    assert S.acquire_lock(tmp_path) and not S.acquire_lock(tmp_path)  # second caller loses, no TOCTOU
    S.release_lock(tmp_path)
    assert S.acquire_lock(tmp_path)
    old = S.time.time() - (S.SEND_LOCK_TTL_MIN + 5) * 60
    os.utime(tmp_path / "send.lock", (old, old))
    assert S.acquire_lock(tmp_path)  # crashed run's lock taken over
    S.release_lock(tmp_path)
    S.release_lock(tmp_path)  # idempotent


def test_held_send_lock_makes_run_a_silent_noop(tmp_path, monkeypatch):
    seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    assert S.acquire_lock(tmp_path)
    monkeypatch.setattr(S, "launch_context", lambda *a, **k: pytest.fail("must not launch"))
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 0
    assert (tmp_path / "send.lock").exists()  # the other run's lock is left alone


def test_chrome_missing_writes_no_marker(tmp_path, monkeypatch):
    @contextlib.contextmanager
    def no_chrome(data_dir):
        raise S.ChromeUnavailable("Google Chrome could not start (not found)")
        yield  # pragma: no cover
    monkeypatch.setattr(S, "open_browser", no_chrome)
    _smtp_env(monkeypatch, _FakeSMTP)
    seed(tmp_path, [("a", "connect_header.html")])
    assert S.cmd_run(tmp_path, dry_run=False, today=MON) == 3
    assert not S.marker_path(tmp_path, "2026-11-02").exists()


def test_stale_cookie_is_not_a_session(page):
    page.set_content("<main><a href='#'>Sign in</a><button>Join now</button></main>")
    page.goto = lambda *a, **k: None  # stay on the fixture: LinkedIn bounced us to a signed-out page
    page.wait_for_timeout = lambda *a, **k: None
    assert S._session_works(page) is False


def test_setup_refuses_store_python(tmp_path, monkeypatch):
    monkeypatch.setattr(S.os, "name", "nt")
    monkeypatch.setenv("GMAIL_SMTP_USER", "me@example.com")
    monkeypatch.setenv("GMAIL_SMTP_APP_PASSWORD", "x")
    seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.setattr(S.sys, "executable", r"C:\Users\d\AppData\Local\Microsoft\WindowsApps\python.exe")
    monkeypatch.setattr(S.Path, "resolve", lambda self: self)
    monkeypatch.setattr(S, "ensure_login", lambda *a, **k: pytest.fail("must refuse before login"))
    assert S.cmd_setup(tmp_path, start=True) == 3


def test_task_script_quotes_paths_and_is_idempotent():
    ps = S.task_script(r"C:\Py 3\python.exe", Path(r"C:\it's\send.py"), Path(r"C:\it's"), start=True)
    assert "-Execute 'C:\\Py 3\\python.exe'" in ps
    assert "'\"C:\\it''s\\send.py\" run'" in ps and "-WorkingDirectory 'C:\\it''s'" in ps
    assert "-Force" in ps and ps.endswith("Write-Output 'started'")
    assert "Monday,Tuesday,Thursday,Friday,Saturday -At 10:00" in ps and "IgnoreNew" in ps
    assert "Start-ScheduledTask" not in S.task_script("p", Path("s"), Path("r"), start=False)


def test_setup_refuses_off_windows(tmp_path, monkeypatch):
    monkeypatch.setattr(S.os, "name", "posix")
    assert S.cmd_setup(tmp_path, start=True) == 3


def test_release_lock_only_deletes_own_lock_and_never_raises(tmp_path, monkeypatch):
    (tmp_path / "send.lock").write_text("2026-11-05T10:00:00|999999999\n", encoding="utf-8")
    S.release_lock(tmp_path)
    assert (tmp_path / "send.lock").exists()  # another run's lock survives
    (tmp_path / "send.lock").unlink()
    assert S.acquire_lock(tmp_path)

    def locked(self, *a, **k):
        raise PermissionError(32, "in use")
    monkeypatch.setattr(S.Path, "unlink", locked)
    S.release_lock(tmp_path)  # OneDrive/AV lock: no exception


def test_unsendable_people_never_stop_the_day_and_20_still_go_out(page, tmp_path):
    """Operator order 2026-11-05: email-verification / Follow-only / gone / pending profiles are recorded and
    skipped; the run moves on until 20 are sent. Interleaved so no 5-in-a-row streak forms."""
    blockers = ["email_required.html", "follow_only.html", "not_found.html", "pending.html"]
    people = []
    for i in range(20):
        people.append((f"x{i}", blockers[i % 4]))
        people.append((f"ok{i}", "connect_header.html"))
    store = seed(tmp_path, people)
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    rows = ledger(store)
    assert res.stop is None and res.sent_run == 20
    assert sum(1 for st, _ in rows.values() if st == "sent") == 20
    assert all(rows[f"x{i}"][0] in ("skipped", "retry", "pending") for i in range(20) if f"x{i}" in rows)
    email_skips = [s for s, v in rows.items() if v == ("skipped", "email_required")]
    assert email_skips
    assert all(s in Q._blocked(store.load_ledger(), "2026-11-09") for s in email_skips)  # never queued again


def test_visit_ceiling_and_budget_constants():
    assert S.VISIT_FACTOR * Q.DAILY_CAP == 100 and (S.MAX_BLOCK_STREAK, S.MAX_UI_STREAK) == (3, 10)
    assert S.SEND_LOCK_TTL_MIN * 60 > S.RUN_BUDGET_S + 300 + S.SMTP_ATTEMPTS * (4 * 30 + S.SMTP_RETRY_S)


def test_covered_connect_button_is_this_persons_retry_not_a_crash(page, monkeypatch):
    monkeypatch.setattr(S, "CLICK_TIMEOUT_MS", 800)
    page.set_content("<main><section><h1>A</h1><button aria-label='Invite A to connect'>Connect</button>"
                     "<div style='position:fixed;inset:0;background:#fff'></div></section></main>")
    page.goto = lambda *a, **k: None
    out = S.process_profile(page, "https://www.linkedin.com/in/a/", "a")
    assert (out.status, out.note, out.stop) == ("retry", "click_failed:overlay_covered", None)  # unknown cover: never clicked through


def test_email_input_dialog_is_skipped_whatever_its_wording(page):
    page.set_content("<main><section><h1>A</h1></section></main><div role='dialog'><p>To verify this member "
                     "knows you, type their address</p><input type='email'><button disabled>Send</button></div>")
    out = S._finish_invite(page, S.top_card(page), "a", None)
    assert (out.status, out.note) == ("skipped", "email_required")


def test_only_the_last_cover_decides_a_dispatched_click():
    msg = ("Locator.click: Timeout 5000ms exceeded.\n  - <aside class=\"msg-overlay-container\"></aside> intercepts "
           "pointer events\n  - <div class=\"artdeco-modal__content\">Verify</div> intercepts pointer events\n")
    assert not S.BENIGN_COVER_RE.search(S.cover_lines(msg))  # a modal opened over the panel: never click through
    assert S.BENIGN_COVER_RE.search(S.cover_lines(msg.split("\n  - <div")[0]))


def test_wrapper_section_is_not_the_card(page):
    page.set_content("<main><section class='wrap'><section class='top'><h1>A</h1><button>Follow</button></section>"
                     "<section><h2>People also viewed</h2><button aria-label='Invite Other to connect'>Connect</button>"
                     "</section></section></main>")
    assert S._connect_in(S.top_card(page)) is None


def test_interleaved_failures_stop_at_the_overall_ceiling(page, tmp_path, monkeypatch):
    seq = iter([S.Outcome("retry", "page_load_failed"), S.Outcome("retry", "click_failed:timeout")] * 10)
    monkeypatch.setattr(S, "process_profile", lambda *a, **k: next(seq))
    monkeypatch.setattr(S, "is_ui_failure", lambda note: False)  # no reload-retry, one outcome per person
    store = seed(tmp_path, [(f"p{i}", "connect_header.html") for i in range(20)])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.stop == f"{S.MAX_RETRY_STREAK} profiles in a row without a send" and res.processed == S.MAX_RETRY_STREAK


def test_debug_folder_error_never_stops_the_day(page, tmp_path):
    blocker = tmp_path / "debug"
    blocker.write_text("a file where the folder should be")
    store = seed(tmp_path, [("a", "connect_header.html")])
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None, debug_dir=blocker)
    assert res.stop is None and res.sent_run == 1


def test_any_retry_on_fourth_day_becomes_final(tmp_path):
    store = seed(tmp_path, [("r", "no_confirm.html")])
    for day, note in (("2026-10-28", "click_failed:timeout"), ("2026-10-30", "unconfirmed"),
                      ("2026-10-31", "page_load_failed")):
        store.append_ledger({"ts": f"{day}T10:00:00", "date": day, "slug": "r", "name": "R",
                             "status": "retry", "note": note})
    S._quiet(Q.cmd_mark, store, "r", "retry", "unconfirmed", None)
    last = store.load_ledger()[-1]
    assert (last["status"], last["note"]) == ("skipped", "retry_4x:unconfirmed")
    assert "r" in Q._blocked(store.load_ledger(), "2026-11-03")


def test_menu_in_people_also_viewed_rail_is_never_used(page):
    page.set_content("<main><section><h1>A</h1><button aria-label='More actions'>More</button></section></main>"
                     "<aside><div role=menu><div role=button aria-label='Invite Other to connect'>Connect</div>"
                     "</div></aside>")
    out = S._act(page, None, "a", dry_run=True)
    assert (out.status, out.note) == ("retry", "no_connect_button:menu_no_connect")


def test_menu_named_by_aria_controls_is_used(page):
    page.set_content("<main><section><h1>A</h1><button aria-label='More actions' aria-controls='dd'>More</button>"
                     "</section></main><div id='dd' class='artdeco-dropdown__content'>"
                     "<div role=button aria-label='Invite A to connect'>Connect</div></div>")
    assert S._act(page, None, "a", dry_run=True).would_send


def test_task_wakes_the_pc_and_doctor_reads_state(tmp_path):
    assert "-WakeToRun" in S.task_script("py.exe", Path("s.py"), Path("r"), False)
    (tmp_path / "send.log").write_text("2026-11-02 10:00:07 INFO run 2026-11-02: 0 already sent today, cap 20\n",
                                       encoding="utf-8")
    S.marker_path(tmp_path, "2026-11-02").write_text("LinkedIn connects 2026-11-02 (20 sent)\n", encoding="utf-8")
    rep = S.doctor_report(tmp_path, MON, None)
    assert "send day" in rep and "(20 sent)" in rep and "last run started: 2026-11-02 10:00:07" in rep
    assert "send.lock: none" in rep and "Windows only" in rep
    assert "never run" in S.doctor_report(tmp_path / "empty", WED, "x")


def test_menu_in_a_main_rail_section_is_never_used(page):
    page.set_content("<main><section><h1>A</h1><button aria-label='More actions'>More</button></section>"
                     "<section><h2>People also viewed</h2><div role=menu><div role=button "
                     "aria-label='Invite Other to connect'>Connect</div></div></section></main>")
    out = S._act(page, None, "a", dry_run=True)
    assert (out.status, out.note) == ("retry", "no_connect_button:menu_no_connect")


def test_no_dispatched_click_while_a_dialog_is_open(page, monkeypatch):
    monkeypatch.setattr(S, "CLICK_TIMEOUT_MS", 800)
    page.set_content("<button id=b onclick='window.clicked = true'>More</button><div role=dialog>Verify it's you</div>"
                     "<div class='artdeco-toast-item' style='position:fixed;inset:0'></div>")
    assert not page.evaluate("window.clicked || false")
    with pytest.raises(S.ClickFailed) as e:
        S.safe_click(page, page.locator("#b"), "More")
    assert e.value.kind == "dialog_open" and not page.evaluate("window.clicked || false")


def test_doctor_survives_unreadable_files(tmp_path, monkeypatch):
    (tmp_path / "send.log").write_text("x", encoding="utf-8")
    S.marker_path(tmp_path, "2026-11-02").write_text("x", encoding="utf-8")
    def boom(self, *a, **k):
        raise PermissionError("locked")
    monkeypatch.setattr(Path, "read_text", boom)
    rep = S.doctor_report(tmp_path, MON, None)
    assert "marker unreadable" in rep and "send.log unreadable" in rep


def test_run_crossing_midnight_reads_the_queue_it_planned(page, tmp_path, monkeypatch):
    store = seed(tmp_path, [("a", "connect_header.html")])
    monkeypatch.setattr(Q, "_today", lambda: "2026-11-03")  # the clock passed midnight after the run started
    res = S.run_day(page, store, "2026-11-02", sleep=lambda s: None)
    assert res.processed == 1
