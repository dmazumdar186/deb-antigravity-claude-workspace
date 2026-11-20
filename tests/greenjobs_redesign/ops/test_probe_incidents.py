"""Uptime/email probe + incidents: right host and path, MX vs inventory, sev-1 posting outage alerts at once, SLA clock."""

from __future__ import annotations

from datetime import datetime, timezone

import common as C
import incidents as I
import uptime_probe as P
from conftest import FakeDNS, zones_from_inventory
from notify import Notifier


def healthy_get(url, timeout):
    """New stack: apex -> www (301), sector domains -> greenjobs.co.uk/sectors/<slug>/ (301), www answers 200."""
    from urllib.parse import urlsplit

    u = urlsplit(url)
    host = u.hostname
    if host in C.SECTOR_DOMAINS or host.removeprefix("www.") in C.SECTOR_DOMAINS:
        return 301, C.CANONICAL["uk"] + C.sector_forward_path(host.removeprefix("www."))
    if not host.startswith("www."):
        return 301, f"https://www.{host}{u.path}"
    return 200, None


def healthy_status(method, url, headers, timeout):
    return {"/admin/": 302, "/api/jobs": 200, "/api/apply": 204}[
        url.split(".ie", 1)[-1].split(".co.uk", 1)[-1]
    ]


def test_targets_cover_20_hostnames_with_expected_hosts():
    t = P.targets()
    assert len(t) == 20
    assert ("greenjobs.ie", "www.greenjobs.ie", None) in t
    assert (
        "www.wastejobsuk.com",
        "www.greenjobs.co.uk",
        "/sectors/waste-circular-economy/",
    ) in t


def test_healthy_stack_passes_every_check(tmp_path):
    rows = P.run(
        tmp_path / "probe_log.jsonl",
        healthy_get,
        FakeDNS(zones_from_inventory()),
        healthy_status,
    )
    assert rows and all(r["ok"] is True for r in rows), [r for r in rows if not r["ok"]]
    assert {r["kind"] for r in rows} == {"http", "posting", "mail"}
    assert len(C.read_jsonl(tmp_path / "probe_log.jsonl")) == len(rows)
    assert (C.read_json(tmp_path / "incidents.json") or {}).get("incidents") == {}


def test_wrong_host_wrong_sector_path_and_errors_fail():
    def bad_get(url, timeout):
        if "solarjobsuk" in url:
            return 301, "https://www.greenjobs.co.uk/jobs/"  # not the sector page
        if "greenjobs.ie" in url:
            raise TimeoutError
        if url.startswith("https://greenjobs.co.uk"):
            return 301, "https://strategies.example/"  # old host
        return healthy_get(url, timeout)

    rows = {
        r["target"]: r
        for r in P.http_checks(
            lambda u, t: bad_get(u, t) if "strategies.example" not in u else (200, None)
        )
    }
    assert (
        rows["solarjobsuk.com"]["ok"] is False
        and rows["www.greenjobs.ie"]["ok"] is False
    )
    assert (
        rows["greenjobs.co.uk"]["ok"] is False and rows["windjobsuk.com"]["ok"] is True
    )
    assert rows["www.greenjobs.ie"]["detail"]["error"] == "TimeoutError"


def test_mx_mismatch_is_reported_and_lookup_error_is_not_a_pass():
    zones = zones_from_inventory()
    zones["greenjobs.co.uk"]["mx"] = ["5 other.example."]
    rows = {
        r["target"]: r for r in P.mail_checks(FakeDNS(zones, fail={"waterjobsuk.com"}))
    }
    assert rows["greenjobs.co.uk"]["ok"] is False
    assert rows["waterjobsuk.com"]["ok"] is None
    assert rows["greenjobs.ie"]["ok"] is True


def test_posting_outage_opens_one_sev1_incident_and_alerts_immediately(tmp_path):
    def console_down(method, url, headers, timeout):
        if url.endswith("/admin/") and ".ie" in url:
            return 503
        return healthy_status(method, url, headers, timeout)

    log = tmp_path / "probe_log.jsonl"
    for _ in range(3):
        P.run(log, healthy_get, FakeDNS(zones_from_inventory()), console_down)
    incs = C.read_json(tmp_path / "incidents.json")["incidents"]
    assert len(incs) == 1
    inc = next(iter(incs.values()))
    assert (
        inc["sev"] == 1
        and inc["check"] == "posting:ie:console"
        and inc["closed_at"] is None
    )
    alerts = [
        r
        for r in C.read_jsonl(tmp_path / "outbox.jsonl")
        if r["key"].startswith("incident:")
    ]
    assert (
        len(alerts) == 1
        and "SEV-1" in alerts[0]["subject"]
        and alerts[0]["to_env"] == "OPS_ALERT_EMAIL"
    )
    P.run(log, healthy_get, FakeDNS(zones_from_inventory()), healthy_status)
    assert next(iter(C.read_json(tmp_path / "incidents.json")["incidents"].values()))[
        "closed_at"
    ]


def test_optional_network_domains_never_open_incidents(tmp_path):
    def sector_down(url, timeout):
        if "windjobsuk" in url:
            return 502, None
        return healthy_get(url, timeout)

    P.run(
        tmp_path / "probe_log.jsonl",
        sector_down,
        FakeDNS(zones_from_inventory()),
        healthy_status,
    )
    assert C.read_json(tmp_path / "incidents.json")["incidents"] == {}


def _incident(state, sev, opened, acked=None):
    nt = Notifier(state)
    I.update(state, {f"x:{opened}": (sev, "e")}, {f"x:{opened}"}, opened, nt)
    if acked:
        iid = next(
            k
            for k, v in C.read_json(state / "incidents.json")["incidents"].items()
            if v["opened_at"] == opened
        )
        assert I.ack(state, iid, acked)


def test_sla_clock_sev1_4h_and_sev2_one_business_day(tmp_path):
    _incident(tmp_path, 1, "2026-12-07T10:00:00Z", "2026-12-07T13:59:00Z")  # met
    _incident(tmp_path, 1, "2026-12-08T10:00:00Z", "2026-12-08T14:30:00Z")  # breached
    _incident(
        tmp_path, 2, "2026-12-11T16:00:00Z", "2026-12-14T15:00:00Z"
    )  # Fri -> Mon: met (1 business day)
    _incident(
        tmp_path, 2, "2026-12-15T09:00:00Z"
    )  # unacked, deadline passed by the 17th
    s = I.sla(tmp_path, datetime(2026, 12, 17, tzinfo=timezone.utc))
    assert (
        s["incidents"] == 4
        and s["met"] == 2
        and len(s["breached"]) == 2
        and s["sev1"] == 2
    )


def test_ack_is_idempotent(tmp_path):
    _incident(tmp_path, 1, "2026-12-07T10:00:00Z", "2026-12-07T11:00:00Z")
    iid = next(iter(C.read_json(tmp_path / "incidents.json")["incidents"]))
    I.ack(tmp_path, iid, "2026-12-07T23:00:00Z")
    assert (
        C.read_json(tmp_path / "incidents.json")["incidents"][iid]["acked_at"]
        == "2026-12-07T11:00:00Z"
    )
    assert not I.ack(tmp_path, "nope")


def test_probe_without_live_makes_no_request(capsys):
    assert P.main([]) == 0
    assert "Pass --live" in capsys.readouterr().out
