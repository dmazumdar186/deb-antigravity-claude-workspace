"""Round-4 regression tests (2026-09-21): take_down_preview(dnc=...), the negative-reply opt-out
(do_not_contact + sibling cascade), the bounce patch-by-id, the "sends vs cap" weekly number
(send.sends_vs_cap + fit_weights line + `send.py --stats`), the under-send error alert, and the
touch-2 Loom operator path (scripts/set_loom.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from execution.personal_workflows.prodcraft_medspa.common import notify
from execution.personal_workflows.prodcraft_medspa.common.store import LocalStore
from execution.personal_workflows.prodcraft_medspa.outreach import scan_replies, send
from execution.personal_workflows.prodcraft_medspa.preview import takedown
from execution.personal_workflows.prodcraft_medspa.scripts import fit_weights, set_loom

from tests.prodcraft_medspa.test_outreach import (  # noqa: E402
    PKG_ROOT,
    FakeSettings,
    _make_business,
    _make_outreach_row,
    _make_preview,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _notes(row: dict) -> dict:
    n = row.get("notes") or {}
    return json.loads(n) if isinstance(n, str) else dict(n)


# ---------------------------------------------------------------------------
# 1. take_down_preview(dnc=...)
# ---------------------------------------------------------------------------


def test_take_down_preview_dnc_false_leaves_business_and_outreach_alone(local_store, tmp_path):
    business = _make_business(local_store)
    preview = _make_preview(local_store, business_id=business["id"])
    row = _make_outreach_row(local_store, business_id=business["id"], status="sent", preview_id=preview["id"])

    result = takedown.take_down_preview(local_store, preview, mock=True, tmp_root=tmp_path, dnc=False)

    assert result["status"] == "takedown"
    assert result["outreach_closed"] == 0
    assert local_store.get_row("previews", preview["id"])["takedown"] is True
    assert local_store.get_business(business["id"])["do_not_contact"] is False
    assert local_store.get_row("outreach", row["id"])["status"] == "sent"


def test_take_down_preview_default_dnc_true_unchanged(local_store, tmp_path):
    business = _make_business(local_store)
    preview = _make_preview(local_store, business_id=business["id"])
    row = _make_outreach_row(local_store, business_id=business["id"], status="sent", preview_id=preview["id"])

    result = takedown.take_down_preview(local_store, preview, mock=True, tmp_root=tmp_path)

    assert result["outreach_closed"] == 1
    assert local_store.get_business(business["id"])["do_not_contact"] is True
    assert local_store.get_row("outreach", row["id"])["status"] == "dnc"


def test_scan_replies_negative_sets_do_not_contact_and_takes_down(local_store, monkeypatch):
    """Round-4 (Dario lens): a negative reply is an opt-out. The preview comes down AND
    `businesses.do_not_contact` is stamped True, written patch-by-id (never a full-row upsert)."""
    business = _make_business(local_store, email="owner3@example-medspa-3.test")
    preview = _make_preview(local_store, business_id=business["id"])
    local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent",
         "sent_at": "2026-09-01T00:00:00Z", "preview_id": preview["id"]}
    )
    business_writes: list[dict] = []
    orig = local_store.update_row

    def _tracked(table, row_id, patch):
        if table == "businesses":
            business_writes.append(patch)
        return orig(table, row_id, patch)

    monkeypatch.setattr(local_store, "update_row", _tracked)
    monkeypatch.setattr(local_store, "upsert_business", lambda *_a, **_k: pytest.fail("full-row upsert on negative path"))
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    assert local_store.get_row("previews", preview["id"])["status"] == "takedown"
    assert local_store.get_business(business["id"])["do_not_contact"] is True
    assert [p for p in business_writes if "do_not_contact" in p] == [{"do_not_contact": True}]


def test_scan_replies_negative_cascades_queued_sibling_to_dnc(local_store):
    """Round-4 item I: the opt-out cascade must close sibling rows (a queued touch 2) so no orphan
    row is drafted later, dropped at send and counted by _drafted_pending_count."""
    business = _make_business(local_store, email="owner3@example-medspa-3.test")
    preview = _make_preview(local_store, business_id=business["id"])
    t1 = local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent",
         "sent_at": "2026-09-01T00:00:00Z", "preview_id": preview["id"]}
    )
    t2 = _make_outreach_row(local_store, business_id=business["id"], touch=2, status="queued", preview_id=preview["id"])
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    assert local_store.get_row("outreach", t1["id"])["status"] == "closed_lost"
    assert local_store.get_row("outreach", t2["id"])["status"] == "dnc"
    open_rows = [r for r in local_store.list_outreach(business["id"]) if r["status"] not in ("closed_won", "closed_lost", "dnc")]
    assert open_rows == []
    assert local_store.get_business(business["id"])["do_not_contact"] is True


def test_scan_replies_negative_without_preview_still_opts_out(local_store):
    """No preview row at all: the flag and the cascade still happen (the opt-out does not depend
    on there being something to unpublish)."""
    business = _make_business(local_store, email="owner3@example-medspa-3.test")
    local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"}
    )
    t2 = _make_outreach_row(local_store, business_id=business["id"], touch=2, status="drafted")
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    assert local_store.get_business(business["id"])["do_not_contact"] is True
    assert local_store.get_row("outreach", t2["id"])["status"] == "dnc"


def test_scan_replies_bounce_patches_email_status_by_id(local_store, monkeypatch):
    """Round-4 item D: the bounce path patches `email_status` by id; a full-row upsert_business
    would overwrite whatever another process wrote to the business row in between."""
    business = _make_business(local_store, email="owner5@example-medspa-5.test")
    local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"}
    )
    patches: list[tuple] = []
    orig = local_store.update_row

    def _tracked(table, row_id, patch):
        if table == "businesses":
            # simulate a concurrent writer that landed between scan's read and its write
            orig("businesses", row_id, {"owner_first": "Concurrent"})
            patches.append((row_id, patch))
        return orig(table, row_id, patch)

    monkeypatch.setattr(local_store, "update_row", _tracked)
    monkeypatch.setattr(local_store, "upsert_business", lambda *_a, **_k: pytest.fail("full-row upsert on bounce path"))
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["bounce"] == 1
    assert patches == [(business["id"], {"email_status": "undeliverable"})]
    after = local_store.get_business(business["id"])
    assert after["email_status"] == "undeliverable" and after["owner_first"] == "Concurrent"


# ---------------------------------------------------------------------------
# 2. sends vs cap
# ---------------------------------------------------------------------------


def _seed_sends(store: LocalStore, sends_by_date: dict[str, int]) -> None:
    i = 0
    for day, n in sends_by_date.items():
        for _ in range(n):
            i += 1
            b = _make_business(store, name=f"Spa {i}", email=f"o{i}@example-medspa.test")
            store.upsert_outreach(
                {"business_id": b["id"], "touch": 1, "status": "sent", "sent_at": f"{day}T15:00:00Z"}
            )


def test_sends_vs_cap_counts_trailing_7_days_against_ramped_cap(local_store):
    local_store.set_config("phase0", {"cap": 5, "warmup_start_cap": 2, "warmup_days": 14})
    # first live send 2026-09-14 -> ramp day 0..6 across the window; per-day cap from effective_cap
    _seed_sends(local_store, {"2026-09-13": 3, "2026-09-14": 2, "2026-09-16": 1, "2026-09-20": 2})

    summary = send.sends_vs_cap(local_store, date(2026, 9, 20))

    assert summary["window_days"] == 7
    assert [d["date"] for d in summary["days"]] == [f"2026-09-{n}" for n in range(14, 21)]
    assert [d["sent"] for d in summary["days"]] == [2, 0, 1, 0, 0, 0, 2]
    assert summary["sent"] == 5  # the 09-13 sends fall outside the window
    from execution.personal_workflows.prodcraft_medspa.outreach import daily_queue
    expected_caps = [daily_queue.effective_cap(local_store, date(2026, 9, n)) for n in range(14, 21)]
    assert [d["cap"] for d in summary["days"]] == expected_caps
    assert summary["cap"] == sum(expected_caps)
    assert 2 <= min(expected_caps) <= max(expected_caps) <= 5


def test_sends_vs_cap_mock_uses_plain_cap_and_line_has_no_em_dash(local_store):
    local_store.set_config("phase0", {"cap": 5, "warmup_start_cap": 2, "warmup_days": 14})
    _seed_sends(local_store, {"2026-09-20": 4})
    summary = send.sends_vs_cap(local_store, date(2026, 9, 20), mock=True)
    assert all(d["cap"] == 5 for d in summary["days"])
    line = send.format_sends_vs_cap(summary)
    assert line == "sends vs cap (7d): 4/35, per day 0/5 0/5 0/5 0/5 0/5 0/5 4/5"
    assert "—" not in line
    assert fit_weights.sends_vs_cap_line(local_store, mock=True, today=date(2026, 9, 20)) == line


def test_build_telegram_lines_appends_sends_line_as_sixth():
    result = {"n_touch1_sent": 10, "overall_reply_rate": 0.1, "signals": {}}
    lines = fit_weights.build_telegram_lines(result, {}, None, "full", "score", sends_line="sends vs cap (7d): 1/2, per day 1/2")
    assert len(lines) == 6
    assert lines[-1].startswith("sends vs cap")
    assert all("—" not in line for line in lines)


def test_fit_weights_report_telegram_mock_prints_sends_vs_cap(tmp_path):
    store_root = tmp_path / "store"
    LocalStore(store_root)
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "fit_weights.py"),
         "--mock", "--store-root", str(store_root), "--report-telegram", "--min-sent", "50"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    assert "not enough data yet: 0/50 sends" in proc.stdout
    assert "sends vs cap (7d): 0/" in proc.stdout


def test_send_stats_flag_prints_summary_and_sends_nothing(tmp_path):
    store_root = tmp_path / "store"
    st = LocalStore(store_root)
    st.set_config("phase0", {"cap": 5})
    _seed_sends(st, {"2026-09-19": 2})
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "outreach" / "send.py"),
         "--mock", "--store", "local", "--store-root", str(store_root), "--stats", "--date", "2026-09-20"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    out = json.loads(proc.stdout.strip().splitlines()[-1])
    assert out["stats"] == "sends_vs_cap"
    assert out["sent"] == 2 and out["cap"] == 35
    assert out["line"].startswith("sends vs cap (7d): 2/35")
    assert "sent" in out and "dropped" not in out  # no send pass ran


def test_under_send_alert_fires_once_per_day_when_live_and_under_half_cap(local_store, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(notify, "error", lambda service, error, count=1, environment=None: calls.append((service, error, count)) or True)
    monkeypatch.setenv("PRODCRAFT_ENV", "test-env")
    local_store.set_config("phase0", {"cap": 5})
    local_store.set_config("live_send_confirmed", True)
    _seed_sends(local_store, {"2026-09-19": 2})  # 2 of 35

    line = fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 20))

    assert line == "prodcraft_medspa / test-env / under_send_7d / sent=2 cap=35 / 1"
    assert calls == [("prodcraft_medspa", "under_send_7d / sent=2 cap=35", 1)]
    assert "\u2014" not in line
    assert local_store.get_config("notify_dedupe")["under_send_7d"] == "2026-09-20"
    # same day again: still reports the condition, but does not page twice
    assert fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 20)) == line
    assert len(calls) == 1
    # next day: pages again
    fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 21))
    assert len(calls) == 2


def test_under_send_alert_silent_pre_live_or_at_half_cap(local_store, monkeypatch):
    calls: list[tuple] = []
    monkeypatch.setattr(notify, "error", lambda *a, **k: calls.append(a) or True)
    local_store.set_config("phase0", {"cap": 5})
    # pre-live: even 0/35 is by design, no alert
    assert fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 20)) is None
    local_store.set_config("live_send_confirmed", True)
    _seed_sends(local_store, {"2026-09-18": 17, "2026-09-19": 1})  # 18/35 >= 50%
    assert fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 20)) is None
    # cap 0: never divides/alerts
    local_store.set_config("phase0", {"cap": 0})
    assert fit_weights.under_send_alert(local_store, mock=True, today=date(2026, 9, 20)) is None
    assert calls == []
    assert "under_send_7d" not in (local_store.get_config("notify_dedupe", {}) or {})


def test_fit_weights_main_pages_error_channel_on_failure(monkeypatch, tmp_path):
    calls: list[tuple] = []
    monkeypatch.setattr(fit_weights.notify, "error", lambda service, error, count=1, environment=None: calls.append((service, error)) or True)
    monkeypatch.setattr(fit_weights, "touch1_outcomes", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "argv", ["fit_weights.py", "--mock", "--store-root", str(tmp_path / "store")])
    with pytest.raises(RuntimeError):
        fit_weights.main()
    assert calls == [("prodcraft_medspa.fit_weights", "RuntimeError: boom")]


def test_send_stats_pages_error_channel_on_failure(monkeypatch, tmp_path):
    calls: list[tuple] = []
    from execution.personal_workflows.prodcraft_medspa.common import notify as notify_mod
    monkeypatch.setattr(notify_mod, "error", lambda service, error, count=1, environment=None: calls.append((service, error)) or True)
    monkeypatch.setattr(send, "sends_vs_cap", lambda *a, **k: (_ for _ in ()).throw(RuntimeError("boom")))
    monkeypatch.setattr(sys, "argv", ["send.py", "--mock", "--store", "local", "--store-root", str(tmp_path / "store"), "--stats"])
    with pytest.raises(RuntimeError):
        send.main()
    assert calls == [("prodcraft_medspa.send", "--stats: RuntimeError: boom")]


def test_default_day_is_utc_not_local(monkeypatch):
    """Round-4 item C: `send.py --stats` (no --date) and fit_weights' sends line default to the
    UTC calendar day, matching how _sent_today_count buckets sent_at."""
    utc_today = datetime.now(timezone.utc).date()
    assert send._parse_date(None) == utc_today
    assert fit_weights._utc_today() == utc_today
    seen: list = []
    monkeypatch.setattr(send, "sends_vs_cap", lambda st, today, **k: seen.append(today) or {"days": [], "sent": 0, "cap": 0, "window_days": 7})
    fit_weights.sends_vs_cap_line(object(), mock=True)
    assert seen == [utc_today]


# ---------------------------------------------------------------------------
# 3. set_loom.py
# ---------------------------------------------------------------------------

GOOD = "https://www.loom.com/share/abc123def456"


@pytest.mark.parametrize("bad", [
    "http://www.loom.com/share/abc", "https://evil.com/loom.com/share/x", "https://loom.com.evil.test/share/x",
    "https://www.loom.com/", "ftp://loom.com/share/x", "", "https://www.loom.com/share/a b",
])
def test_validate_loom_url_rejects(bad):
    with pytest.raises(set_loom.InvalidLoomUrl):
        set_loom.validate_loom_url(bad)


def test_validate_loom_url_accepts_loom_hosts():
    assert set_loom.validate_loom_url(GOOD) == GOOD
    assert set_loom.validate_loom_url("https://loom.com/share/x1") == "https://loom.com/share/x1"


def test_set_loom_records_url_and_redrafts_drafted_row(local_store):
    business = _make_business(local_store)
    preview = _make_preview(local_store, business_id=business["id"])
    row = _make_outreach_row(
        local_store, business_id=business["id"], touch=2, status="drafted", preview_id=preview["id"],
        draft_subject="Re: x", draft_body="[[LOOM URL]]", gmail_draft_id="d1",
        notes=json.dumps({"needs_operator_input": True}),
    )

    result = set_loom.set_loom(local_store, row["id"], GOOD)

    assert result["status"] == "queued" and result["redrafted"] is True and result["changed"] is True
    after = local_store.get_row("outreach", row["id"])
    assert after["draft_body"] is None and after["gmail_draft_id"] is None
    assert _notes(after)["loom_url"] == GOOD
    assert _notes(after)["needs_operator_input"] is True  # daily_queue._needs_operator_input self-clears it
    events = [e for e in local_store.list_rows("events", entity_id=row["id"])]
    assert any(e["event"] == "manual_patch" for e in events)

    # idempotent: same URL again on the now-queued row changes nothing
    again = set_loom.set_loom(local_store, row["id"], GOOD)
    assert again == {**result, "redrafted": False, "changed": False}


def test_set_loom_same_url_on_drafted_row_does_not_redraft(local_store, monkeypatch):
    """Round-4 item J: notes.loom_url already equal to the given URL -> no patch, no redraft (a
    clean draft rendered with that URL would otherwise be thrown away)."""
    business = _make_business(local_store)
    row = _make_outreach_row(
        local_store, business_id=business["id"], touch=2, status="drafted",
        draft_subject="Re: x", draft_body=f"see {GOOD}", gmail_draft_id="d-clean",
        notes=json.dumps({"loom_url": GOOD}),
    )
    monkeypatch.setattr(set_loom.state_machine, "redraft", lambda *a, **k: pytest.fail("redraft called for an unchanged URL"))

    result = set_loom.set_loom(local_store, row["id"], GOOD)

    assert result["changed"] is False and result["redrafted"] is False and result["status"] == "drafted"
    after = local_store.get_row("outreach", row["id"])
    assert after["draft_body"] == f"see {GOOD}" and after["gmail_draft_id"] == "d-clean"
    assert not any(e["event"] == "manual_patch" for e in local_store.list_rows("events", entity_id=row["id"]))

    # a different URL on the same drafted row does patch + redraft
    monkeypatch.undo()
    other = "https://www.loom.com/share/other999"
    result2 = set_loom.set_loom(local_store, row["id"], other)
    assert result2["changed"] is True and result2["redrafted"] is True and result2["status"] == "queued"


def test_set_loom_resolves_business_id_to_open_touch2_row(local_store):
    business = _make_business(local_store)
    _make_outreach_row(local_store, business_id=business["id"], touch=1, status="sent")
    t2 = _make_outreach_row(local_store, business_id=business["id"], touch=2, status="queued")

    result = set_loom.set_loom(local_store, business["id"], GOOD)
    assert result["outreach_id"] == t2["id"] and result["touch"] == 2
    assert result["status"] == "queued" and result["redrafted"] is False
    with pytest.raises(KeyError):
        set_loom.set_loom(local_store, "nope-not-an-id", GOOD)


def test_set_loom_cli_rejects_bad_url_without_touching_store(tmp_path):
    store_root = tmp_path / "store"
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "set_loom.py"), "--store", "local",
         "--store-root", str(store_root), "--prospect-id", "x", "--url", "http://loom.com/share/x"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 2
    assert "https" in proc.stderr
    assert not (store_root / "outreach.json").exists()


def test_set_loom_cli_prints_one_json_line(tmp_path):
    store_root = tmp_path / "store"
    st = LocalStore(store_root)
    business = _make_business(st)
    row = _make_outreach_row(st, business_id=business["id"], touch=2, status="drafted", draft_body="[[LOOM URL]]")
    proc = subprocess.run(
        [sys.executable, str(PKG_ROOT / "scripts" / "set_loom.py"), "--store", "local",
         "--store-root", str(store_root), "--prospect-id", row["id"], "--url", GOOD],
        capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=str(REPO_ROOT),
    )
    assert proc.returncode == 0, proc.stderr
    lines = [ln for ln in proc.stdout.strip().splitlines() if ln.strip()]
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["script"] == "set_loom" and out["status"] == "queued" and out["redrafted"] is True


# ---------------------------------------------------------------------------
# Gap pass (after round 4): the under-send alert dedupes per day through the
# SupabaseStore code path too, not just LocalStore. tests/prodcraft_medspa has no
# in-memory Supabase double, so this builds a minimal PostgREST emulation behind
# `SupabaseStore._request` (the same seam test_store.py's pagination tests use):
# it serves the only two tables the alert touches, `config` (get/set_config:
# GET ?key=eq.K, POST ?on_conflict=key merge) and `outreach` (list_rows: GET with
# a Range header), and records every request so the assertions can prove the
# dedupe state round-tripped through PostgREST-shaped calls.
# ---------------------------------------------------------------------------


class _FakePostgrest:
    """In-memory stand-in for the PostgREST endpoints SupabaseStore hits during under_send_alert."""

    def __init__(self) -> None:
        self.config: dict[str, object] = {}
        self.outreach: list[dict] = []
        self.calls: list[tuple[str, str]] = []

    def __call__(self, method: str, path: str, **kwargs):
        from tests.prodcraft_medspa.test_store import _FakeResp

        self.calls.append((method, path))
        table = path.split("?", 1)[0]
        if table == "config":
            if method == "GET":
                key = dict(kwargs.get("params") or [])["key"].removeprefix("eq.")
                rows = [{"key": key, "value": self.config[key]}] if key in self.config else []
                return _FakeResp(200, json_data=rows)
            if method == "POST":
                assert "on_conflict=key" in path and "merge-duplicates" in kwargs["headers"]["Prefer"]
                body = kwargs["json"]
                self.config[body["key"]] = body["value"]
                return _FakeResp(201, json_data=[body])
        if table == "outreach" and method == "GET":
            start, end = (int(x) for x in kwargs["headers"]["Range"].split("-"))
            return _FakeResp(200, json_data=self.outreach[start : end + 1])
        raise AssertionError(f"unexpected PostgREST call: {method} {path}")


def test_under_send_alert_dedupes_per_day_through_supabase_store_path(monkeypatch):
    from tests.prodcraft_medspa.test_store import _fake_supabase_store

    calls: list[tuple] = []
    monkeypatch.setattr(notify, "error", lambda service, error, count=1, environment=None: calls.append((service, error, count)) or True)
    monkeypatch.setenv("PRODCRAFT_ENV", "test-env")

    backend = _FakePostgrest()
    backend.config["phase0"] = {"cap": 5}
    backend.config["live_send_confirmed"] = True
    backend.outreach = [
        {"id": f"o{i}", "business_id": f"b{i}", "touch": 1, "status": "sent", "sent_at": "2026-09-19T15:00:00Z"}
        for i in range(2)
    ]  # 2 of 35 over the trailing week
    store = _fake_supabase_store()
    store._request = backend  # noqa: SLF001

    line = fit_weights.under_send_alert(store, mock=True, today=date(2026, 9, 20))

    assert line == "prodcraft_medspa / test-env / under_send_7d / sent=2 cap=35 / 1"
    assert calls == [("prodcraft_medspa", "under_send_7d / sent=2 cap=35", 1)]
    # the dedupe stamp was written through set_config -> POST config?on_conflict=key
    assert backend.config["notify_dedupe"] == {"under_send_7d": "2026-09-20"}
    assert ("POST", "config?on_conflict=key") in backend.calls
    assert store.get_config("notify_dedupe")["under_send_7d"] == "2026-09-20"

    # same UTC day, fresh Store instance (a new cron process): reads the stamp back from
    # PostgREST and does not page twice
    store2 = _fake_supabase_store()
    store2._request = backend  # noqa: SLF001
    assert fit_weights.under_send_alert(store2, mock=True, today=date(2026, 9, 20)) == line
    assert len(calls) == 1
    assert backend.calls.count(("POST", "config?on_conflict=key")) == 1

    # next day: pages again and re-stamps
    fit_weights.under_send_alert(store2, mock=True, today=date(2026, 9, 21))
    assert len(calls) == 2
    assert backend.config["notify_dedupe"] == {"under_send_7d": "2026-09-21"}


def test_scan_replies_live_mode_ignores_mock_inbox_dir(local_store, monkeypatch, tmp_path):
    """Final audit: PRODCRAFT_MOCK_INBOX_DIR is a --mock-only knob. With mock=False the scan must
    go to Gmail and never list or load the mock dir, even when the env var points at a folder
    holding a fixture reply for a sent row."""
    business = _make_business(local_store, email="owner-live@example-medspa.test")
    local_store.upsert_outreach(
        {"business_id": business["id"], "touch": 1, "status": "sent", "sent_at": "2026-09-01T00:00:00Z"}
    )
    inbox_dir = tmp_path / "mock_inbox"
    inbox_dir.mkdir()
    (inbox_dir / "1_remove.json").write_text(
        json.dumps({"owner_email": business["owner_email"], "from": business["owner_email"],
                    "message_id": "m-mock-1", "body_text": "Please remove the preview."}),
        encoding="utf-8",
    )
    monkeypatch.setenv(scan_replies.MOCK_INBOX_DIR_ENV, str(inbox_dir))

    gmail_calls: list[dict] = []
    monkeypatch.setattr(
        scan_replies.gmail_reader, "search_replies",
        lambda **kw: gmail_calls.append(kw) or [],
    )
    monkeypatch.setattr(
        scan_replies.gmail_reader, "load_mock_inbox",
        lambda *a, **k: pytest.fail("live scan consulted the mock inbox dir"),
    )
    orig_glob = Path.glob

    def _guarded_glob(self, pattern, *a, **k):
        if self == inbox_dir:
            pytest.fail("live scan listed PRODCRAFT_MOCK_INBOX_DIR")
        return orig_glob(self, pattern, *a, **k)

    monkeypatch.setattr(Path, "glob", _guarded_glob)
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=False, since_days=14, today=date(2026, 9, 10))

    assert gmail_calls and gmail_calls[0]["owner_email"] == business["owner_email"]
    assert stats["remove"] == 0 and stats["checked"] == 0
    assert local_store.get_business(business["id"]).get("do_not_contact") is not True
