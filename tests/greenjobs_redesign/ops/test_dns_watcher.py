"""DNS watcher: notifies Diana once per domain, alerts on MX/SPF drift (fail loud), never notifies on a lookup failure."""

from __future__ import annotations

import json

import pytest

import common as C
import dns_watcher as W
import notify as N
from conftest import FakeDNS, zones_from_inventory


def outbox(tmp_path):
    return C.read_jsonl(tmp_path / "outbox.jsonl")


def test_ten_domains_and_the_wrong_name_is_not_watched():
    assert (
        len(C.DOMAINS) == 10
        and "renewableenergyjobsuk.com" in C.DOMAINS
        and "renewablejobsuk.com" not in C.DOMAINS
    )


def test_before_the_move_nothing_is_sent(tmp_path):
    out = W.run(tmp_path, FakeDNS(zones_from_inventory()))
    assert not out["loud"] and outbox(tmp_path) == []
    assert all(s["status"] == "pending" for s in out["state"]["domains"].values())


def test_moved_domain_notifies_diana_once_and_never_again(tmp_path):
    dns = FakeDNS(zones_from_inventory(on_cloudflare={"ecologyjobsuk.com"}))
    W.run(tmp_path, dns)
    W.run(tmp_path, dns)
    W.run(tmp_path, dns)
    drafts = [r for r in outbox(tmp_path) if r["key"].startswith("dns-done:")]
    assert [d["key"] for d in drafts] == ["dns-done:ecologyjobsuk.com"]
    assert drafts[0]["to_env"] == "DIANA_EMAIL" and drafts[0]["mode"] == "dry_run"
    assert (
        "ecologyjobsuk.com" in drafts[0]["subject"]
        and "mail is unaffected" in drafts[0]["body"]
    )
    st = C.read_json(tmp_path / "dns_state.json")["domains"]["ecologyjobsuk.com"]
    assert st["status"] == "moved" and st["notified_at"]


def test_state_file_loss_still_does_not_renotify(tmp_path):
    dns = FakeDNS(zones_from_inventory(on_cloudflare={"greenjobs.ie"}))
    W.run(tmp_path, dns)
    (tmp_path / "dns_state.json").unlink()  # the outbox ledger is the second guard
    W.run(tmp_path, dns)
    assert sum(r["key"] == "dns-done:greenjobs.ie" for r in outbox(tmp_path)) == 1


def test_mx_drift_alerts_operator_fails_loud_and_blocks_diana(tmp_path):
    zones = zones_from_inventory(on_cloudflare={"greenjobs.co.uk"})
    zones["greenjobs.co.uk"]["mx"] = [
        "10 route1.mx.cloudflare.net."
    ]  # mail moved by mistake
    out = W.run(tmp_path, FakeDNS(zones))
    assert out["loud"] is True
    rows = outbox(tmp_path)
    assert [r["key"].split(":")[0] for r in rows] == ["mail-drift"]
    assert (
        rows[0]["to_env"] == "OPS_ALERT_EMAIL"
        and "route1.mx.cloudflare.net" in rows[0]["body"]
    )


def test_same_drift_alerts_once_new_drift_alerts_again(tmp_path):
    zones = zones_from_inventory()
    zones["greenjobs.ie"]["txt"] = ['"v=spf1 -all"']
    W.run(tmp_path, FakeDNS(zones))
    W.run(tmp_path, FakeDNS(zones))
    zones["greenjobs.ie"]["txt"] = ['"v=spf1 include:_spf.example -all"']
    W.run(tmp_path, FakeDNS(zones))
    assert (
        sum(r["key"].startswith("mail-drift:greenjobs.ie") for r in outbox(tmp_path))
        == 2
    )


def test_main_exits_2_on_drift(tmp_path, monkeypatch):
    zones = zones_from_inventory()
    zones["solarjobsuk.com"]["mx"] = []
    monkeypatch.setattr(C, "http_get", FakeDNS(zones))
    monkeypatch.setattr(W.C, "http_get", C.http_get)
    assert W.main(["--state-dir", str(tmp_path)]) == 2


def test_lookup_failure_is_unknown_not_moved_and_alerts_after_a_streak(tmp_path):
    dns = FakeDNS(
        zones_from_inventory(on_cloudflare={"windjobsuk.com"}), fail={"windjobsuk.com"}
    )
    for _ in range(W.LOOKUP_FAIL_ALERT_AFTER - 1):
        out = W.run(tmp_path, dns)
        assert not out["loud"]
    out = W.run(tmp_path, dns)
    out = W.run(tmp_path, dns)
    keys = [r["key"] for r in outbox(tmp_path)]
    assert (
        sum(k.startswith("lookup-fail:windjobsuk.com") for k in keys) == 1
        and out["loud"]
    )
    assert not any(k.startswith("dns-done") for k in keys)


def test_live_send_needs_keys_and_redteam_approval(tmp_path, monkeypatch):
    posts = []
    nt = N.Notifier(tmp_path, send=True, post=lambda p, k: posts.append(p) or (200, ""))
    dns = FakeDNS(zones_from_inventory(on_cloudflare={"greenjobs.ie"}))
    out = W.run(tmp_path, dns, notifier=nt)
    assert posts == [] and "blocked" in " ".join(out["events"])
    monkeypatch.setenv("RESEND_API_KEY", "re_test")
    monkeypatch.setenv("OPS_MAIL_FROM", "ops@example.test")
    monkeypatch.setenv("DIANA_EMAIL", "diana@example.test")
    W.run(
        tmp_path,
        dns,
        notifier=N.Notifier(
            tmp_path, send=True, post=lambda p, k: posts.append(p) or (200, "")
        ),
    )
    assert posts == []  # template not yet approved by /redteam
    appr = tmp_path / "approved.json"
    appr.write_text(json.dumps({"diana_dns_done": [N.template_sha(W.DIANA_BODY)]}))
    monkeypatch.setattr(N, "APPROVED", appr)
    for _ in range(3):
        W.run(
            tmp_path,
            dns,
            notifier=N.Notifier(
                tmp_path, send=True, post=lambda p, k: posts.append(p) or (200, "")
            ),
        )
    assert len(posts) == 1 and posts[0]["to"] == ["diana@example.test"]
    ledger = C.read_jsonl(tmp_path / "cost_ledger.jsonl")
    assert len(ledger) == 1 and ledger[0]["cost_usd"] == 0.0


def test_dry_run_draft_does_not_consume_the_live_send(tmp_path, monkeypatch):
    dns = FakeDNS(zones_from_inventory(on_cloudflare={"greenjobs.ie"}))
    W.run(tmp_path, dns)  # dry run drafts
    for v, x in (
        ("RESEND_API_KEY", "re_test"),
        ("OPS_MAIL_FROM", "a@example.test"),
        ("DIANA_EMAIL", "d@example.test"),
    ):
        monkeypatch.setenv(v, x)
    appr = tmp_path / "approved.json"
    appr.write_text(json.dumps({"diana_dns_done": [N.template_sha(W.DIANA_BODY)]}))
    monkeypatch.setattr(N, "APPROVED", appr)
    posts = []
    W.run(
        tmp_path,
        dns,
        notifier=N.Notifier(
            tmp_path, send=True, post=lambda p, k: posts.append(p) or (200, "")
        ),
    )
    W.run(
        tmp_path,
        dns,
        notifier=N.Notifier(
            tmp_path, send=True, post=lambda p, k: posts.append(p) or (200, "")
        ),
    )
    assert len(posts) == 1


def test_failed_live_send_is_retried_not_marked_done(tmp_path, monkeypatch):
    for v, x in (
        ("RESEND_API_KEY", "re_test"),
        ("OPS_MAIL_FROM", "a@example.test"),
        ("OPS_ALERT_EMAIL", "o@example.test"),
    ):
        monkeypatch.setenv(v, x)
    zones = zones_from_inventory()
    zones["greenjobs.ie"]["mx"] = []
    codes = iter([500, 200])
    posts = []
    for _ in range(3):
        W.run(
            tmp_path,
            FakeDNS(zones),
            notifier=N.Notifier(
                tmp_path,
                send=True,
                post=lambda p, k: posts.append(p) or (next(codes, 200), ""),
            ),
        )
    assert len(posts) == 2  # one failure, one success, then deduped
