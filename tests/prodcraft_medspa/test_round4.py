"""Round-4 regression tests (2026-09-21): take_down_preview(dnc=False), the "sends vs cap" weekly
number (send.sends_vs_cap + fit_weights line + `send.py --stats`), and the touch-2 Loom operator
path (scripts/set_loom.py)."""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

import pytest

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


def test_scan_replies_negative_never_writes_do_not_contact(local_store, monkeypatch):
    """The revert is gone: a negative reply must not touch `businesses.do_not_contact` at all
    (no flip-then-revert window), while the preview still comes down."""
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
    settings = FakeSettings(PKG_ROOT / "outreach" / "fixtures")
    stats = scan_replies.scan(local_store, settings, mock=True, since_days=14, today=date(2026, 9, 10))

    assert stats["negative"] == 1
    assert local_store.get_row("previews", preview["id"])["status"] == "takedown"
    assert local_store.get_business(business["id"])["do_not_contact"] is False
    assert not any("do_not_contact" in p for p in business_writes), business_writes


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
    lines = [l for l in proc.stdout.strip().splitlines() if l.strip()]
    assert len(lines) == 1
    out = json.loads(lines[0])
    assert out["script"] == "set_loom" and out["status"] == "queued" and out["redrafted"] is True
