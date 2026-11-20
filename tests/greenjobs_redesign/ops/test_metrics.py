"""Metrics runner, status page, measures object, weekly + monthly renderers: unmeasured never shows PASS or a number."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import jsonschema
import pytest

import common as C
import keith_weekly as K
import metrics as M
import monthly_report as MR

NOW = datetime(2026, 12, 10, 12, 0, tzinfo=timezone.utc)
SCHEMA = json.loads((C.HERE / "measures.schema.json").read_text())


def iso(dt):
    return dt.isoformat().replace("+00:00", "Z")


def write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".jsonl":
        path.write_text("".join(json.dumps(r) + "\n" for r in data))
    else:
        path.write_text(json.dumps(data))


@pytest.fixture
def world(tmp_path):
    inp, st, out = tmp_path / "in", tmp_path / "state", tmp_path / "out"
    jobs = [
        {"id": "j1", "site": "uk", "source": "console", "employer_id": "e1", "title": "Ecologist", "status": "live", "closing_at": "2026-12-31", "created_at": iso(NOW - timedelta(days=3)), "posted_at": iso(NOW - timedelta(days=3))},
        {"id": "j2", "site": "uk", "source": "feed", "employer_id": "g", "title": "Wind Analyst", "status": "live", "closing_at": "2026-12-01", "created_at": iso(NOW - timedelta(days=5))},
        {"id": "j3", "site": "uk", "source": "feed", "employer_id": "g", "title": "Wind  analyst", "status": "live", "closing_at": None, "created_at": iso(NOW - timedelta(days=5))},
        {"id": "j4", "site": "ie", "source": "strategies", "employer_id": "e1", "title": "Planner", "status": "live", "closing_at": None, "created_at": "2026-11-01T00:00:00Z"},
    ]
    employers = [{"id": "e1", "name": "Acme", "name_norm": "acme"}, {"id": "g", "name": "Gaia Talent", "name_norm": "gaia talent"}]
    apps = [{"id": f"a{n}", "site": "uk", "source": "apply", "job_id": "j1", "delivery_status": "sent", "submitted_at": iso(NOW - timedelta(days=n))} for n in range(1, 4)]
    apps.append({"id": "a9", "site": "ie", "source": "apply", "job_id": "j4", "delivery_status": "failed", "submitted_at": iso(NOW - timedelta(days=2))})
    write(inp / "d1_export.json", {"tables": {"jobs": jobs, "employers": employers, "applications": apps}})
    write(inp / "reconciliation.json", {"exported": {"jobs": 200, "employers": 50}, "imported": {"jobs": 200, "employers": 50}, "sample_field_diffs": 0, "fields_exported": 40, "fields_migrated": 22})
    write(inp / "alert_sends.jsonl", [{"site": "uk", "sent_at": iso(NOW - timedelta(days=1)), "consent_marketing": True, "opened_at": iso(NOW)},
                                       {"site": "uk", "sent_at": iso(NOW - timedelta(days=1)), "consent_marketing": None}])
    write(inp / "staff_checkin.json", {"month": "2026-12", "minutes": 300})
    probes = []
    for h in range(0, 48, 1):
        at = iso(NOW - timedelta(hours=h))
        for host in ("greenjobs.ie", "www.greenjobs.ie", "greenjobs.co.uk", "www.greenjobs.co.uk"):
            probes.append({"at": at, "kind": "http", "target": host, "scope": "core", "ok": True})
        probes.append({"at": at, "kind": "http", "target": "windjobsuk.com", "scope": "optional", "ok": False})
        probes.append({"at": at, "kind": "mail", "target": "greenjobs.ie", "scope": "core", "ok": True})
    write(st / "probe_log.jsonl", probes)
    write(st / "redirect_crawl.json", {"checked": 1000, "ok_le_2_hops": 960, "at": iso(NOW)})
    write(st / "backup_log.jsonl", [{"at": iso(NOW - timedelta(hours=30)), "mode": "live", "ok": True, "key": "d1/x.sql"}])
    write(st / "restore_drill_log.jsonl", [{"at": iso(NOW - timedelta(days=5)), "mode": "live", "ok": True, "key": "d1/x.sql", "detail": "counts ok"}])
    write(st / "incidents.json", {"incidents": {}})
    return inp, st, out


def by_id(status):
    return {m["id"]: m for m in status["metrics"]}


def test_metric_guard_null_value_is_never_pass():
    for g in (M.PASS, M.WARN, M.FAIL, M.INFO):
        m = M.metric("X", "x", None, g, "d")
        assert m["grade"] == M.UNMEASURED and m["display"] == "not measured"


def test_no_inputs_everything_unmeasured_nothing_passes(tmp_path):
    st = M.run(tmp_path / "in", tmp_path / "s", tmp_path / "o", NOW)
    assert all(m["grade"] != M.PASS for m in st["metrics"])
    assert all(m["value"] is None and m["grade"] == M.UNMEASURED for m in st["metrics"])
    assert st["overall"] == M.UNMEASURED
    for site in ("ie", "uk"):
        ms = C.read_json(tmp_path / "o" / f"measures_{site}.json")
        jsonschema.validate(ms, SCHEMA)
        assert all(v is None for v in ms["measures"].values())
    html = (tmp_path / "o" / "status.html").read_text()
    assert '<span class="g PASS">' not in html and "UNMEASURED" in html and 'name="viewport"' in html


def test_full_inputs_grade_per_synthesis_thresholds(world):
    inp, st_dir, out = world
    st = M.run(inp, st_dir, out, NOW)
    m = by_id(st)
    assert m["M1"]["grade"] == M.PASS
    assert m["M2"]["grade"] == M.WARN and m["M2"]["value"] == 0.96
    assert m["M3"]["grade"] == M.PASS and m["M3"]["value"] == 1.0  # optional network domains are not in the gate
    assert m["M4"]["grade"] == M.UNMEASURED  # DNS matches but no test mail: not PASS
    assert m["M6"]["value"] == 1.0 and m["M6"]["grade"] == M.PASS
    assert m["M7"]["value"] == 5.0 and m["M7"]["grade"] == M.WARN
    assert m["M8"]["grade"] == M.FAIL  # 3 sent, 1 failed
    assert m["M9"]["value"] == 1 and m["M9"]["grade"] == M.FAIL  # unknown consent counts as a breach
    assert m["B1"]["grade"] == M.WARN and m["B2"]["grade"] == M.PASS
    assert m["SLA1"]["grade"] == M.PASS and m["SLA2"]["display"] == "no incidents"
    assert m["NET1"]["grade"] == M.INFO and m["NET1"]["value"] == 0.0
    assert m["CPO3"]["value"] == 1 and m["CPO4"]["value"] == 1
    assert st["overall"] == M.FAIL


def test_fail_drafts_one_operator_alert_per_metric_per_day(world):
    inp, st_dir, out = world
    M.run(inp, st_dir, out, NOW)
    M.run(inp, st_dir, out, NOW + timedelta(hours=2))
    keys = [r["key"] for r in C.read_jsonl(st_dir / "outbox.jsonl")]
    assert sorted(keys) == sorted({k for k in keys}) and "metric-fail:M9:2026-12-10" in keys


def test_partial_probe_window_is_not_graded(tmp_path):
    rows = [{"at": iso(NOW - timedelta(hours=h)), "kind": "http", "target": "www.greenjobs.ie", "scope": "core", "ok": True} for h in range(3)]
    write(tmp_path / "s" / "probe_log.jsonl", rows)
    st = M.run(tmp_path / "in", tmp_path / "s", tmp_path / "o", NOW)
    m = by_id(st)
    assert m["M3"]["grade"] == M.UNMEASURED and "partial" in m["M3"]["display"]
    assert m["SLA1"]["grade"] == M.UNMEASURED


def test_mx_drift_on_a_board_fails_m4(world):
    inp, st_dir, out = world
    write(st_dir / "dns_state.json", {"domains": {"greenjobs.co.uk": {"last_drift": "abc"}, "windjobsuk.com": {"last_drift": "x"}}})
    m = by_id(M.run(inp, st_dir, out, NOW))
    assert m["M4"]["grade"] == M.FAIL and "greenjobs.co.uk" in m["M4"]["detail"] and "windjobsuk" not in m["M4"]["detail"]


def test_sla_breach_fails_and_shows(world):
    inp, st_dir, out = world
    write(st_dir / "incidents.json", {"incidents": {"i1": {"check": "posting:ie:console", "sev": 1, "opened_at": iso(NOW - timedelta(hours=6)), "acked_at": None, "closed_at": None}}})
    st = M.run(inp, st_dir, out, NOW)
    assert by_id(st)["SLA2"]["grade"] == M.FAIL
    assert "SLA2" in (out / "status.html").read_text()


def test_backup_age_thresholds(world):
    inp, st_dir, out = world
    write(st_dir / "backup_log.jsonl", [{"at": iso(NOW - timedelta(hours=50)), "mode": "live", "ok": True}, {"at": iso(NOW), "mode": "dry_run", "ok": None}])
    assert by_id(M.run(inp, st_dir, out, NOW))["B1"]["grade"] == M.FAIL  # a dry run is not a backup


def test_measures_match_schema_and_are_per_site(world):
    inp, st_dir, out = world
    M.run(inp, st_dir, out, NOW)
    uk, ie = (C.read_json(out / f"measures_{s}.json") for s in ("uk", "ie"))
    for ms in (uk, ie):
        jsonschema.validate(ms, SCHEMA)
    assert uk["measures"]["live_jobs"] == 3 and uk["measures"]["applications_7d"] == 3 and uk["measures"]["applications_per_job_30d"] == 1.0
    assert uk["measures"]["alerts_sent_7d"] == 2 and uk["measures"]["alerts_opened_7d"] == 1
    assert ie["measures"]["jobs_posted_30d"] == 0 and ie["measures"]["staff_minutes_month"] == 300
    assert tuple(SCHEMA["properties"]["measures"]["required"]) == M.MEASURE_KEYS


def test_weekly_renders_five_lines_without_fake_numbers(world, tmp_path):
    st = M.run(tmp_path / "none", tmp_path / "s", tmp_path / "o", NOW)
    ms = {s: C.read_json(tmp_path / "o" / f"measures_{s}.json") for s in ("ie", "uk")}
    text = K.render(st, ms, "Diana moves the .ie nameservers")
    lines = text.splitlines()
    assert len(lines) == 5 and lines[0] == "Red items: none" and "not measured yet" in lines[1] and "not measured yet" in lines[3]
    inp, st_dir, out = world
    st = M.run(inp, st_dir, out, NOW)
    ms = {s: C.read_json(out / f"measures_{s}.json") for s in ("ie", "uk")}
    lines = K.render(st, ms, "x").splitlines()
    assert "consent" in lines[0] and lines[1] == "Applications this week: 4" and lines[3] == "Staff hours this month: 5.0"
    assert (
        lines[2] == "Alerts sent this week: 2"
    )  # the send log exists, so ie's 0 is measured
    with pytest.raises(ValueError):
        K.render(st, ms, " ")


def test_monthly_report_uses_real_figures_or_says_not_measured(world, tmp_path):
    inp, st_dir, out = world
    f = MR.figures("2026-12", inp, st_dir)
    text = MR.render(f, None, ["Switched both boards on 3 Dec"])
    assert "Uptime: 100.0% of checks answered on both boards (measured on 3 of 31 days)" in text
    assert "Traffic: not measured yet" in text and "Applications: 4 (greenjobs.ie 1, greenjobs.co.uk 3)" in text
    assert "- 1 posted in the console" in text and "- 2 arrived by the Gaia feed" in text
    empty = MR.render(MR.figures("2026-12", tmp_path / "x", tmp_path / "y"), None, ["n"])
    assert empty.count("not measured yet") >= 4 and not any(ch.isdigit() for ch in empty.split("Uptime:")[1].split("\n")[0])
    with pytest.raises(ValueError):
        MR.render(f, None, [""])
    assert MR.last_month(NOW) == "2026-11" and MR.last_month(datetime(2027, 1, 5, tzinfo=timezone.utc)) == "2026-12"
