"""Daily D1 backup (dry-run default, idempotent), restore drill (counts verified), 10-day acceptance checks."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

import acceptance_check as A
import common as C
import d1_backup as BK
import d1_restore_drill as RD


def make_dump(path: Path, extra_job: bool = False) -> dict[str, int]:
    """A D1-style SQL dump from the real schema with a few rows (the shape `wrangler d1 export` writes)."""
    con = sqlite3.connect(":memory:")
    con.executescript(BK.SCHEMA.read_text(encoding="utf-8"))
    now = "2026-12-01T00:00:00Z"
    con.execute(
        "INSERT INTO employers (id, site, source, name, name_norm, created_at, updated_at) VALUES ('e1','uk','console','Acme','acme',?,?)",
        (now, now),
    )
    for n in range(2 + extra_job):
        con.execute(
            "INSERT INTO jobs (id, site, source, employer_id, title, location, description, apply_mode, apply_email, status, created_by, created_at, updated_at) "
            "VALUES (?, 'uk', 'console', 'e1', 'Ecologist', 'Leeds', 'A role with enough words in it.', 'email', 'jobs@acme.example', 'live', 'staff@x', ?, ?)",
            (f"j{n}", now, now),
        )
    con.commit()
    path.write_text("\n".join(con.iterdump()), encoding="utf-8")
    return {
        t: con.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in BK.tables()
    }


def test_tables_come_from_the_schema():
    assert {"jobs", "employers", "applications", "audit_log"} <= set(BK.tables())


def test_backup_dry_run_is_default_and_spends_nothing(tmp_path):
    calls = []
    r = BK.backup(
        tmp_path,
        "2026-12-04",
        "greenjobs",
        "greenjobs-backups",
        live=False,
        runner=lambda c: calls.append(c) or (0, ""),
    )
    assert r["status"] == "dry_run" and calls == [] and r["spend_usd"] == 0.0
    assert any(
        "r2 object put greenjobs-backups/d1/2026-12-04.sql" in c for c in r["commands"]
    )
    assert BK.main(["--state-dir", str(tmp_path), "--date", "2026-12-04"]) == 0


def test_backup_live_without_credentials_fails_loud(tmp_path):
    r = BK.backup(
        tmp_path, "2026-12-04", "greenjobs", "b", live=True, runner=lambda c: (0, "")
    )
    assert r["status"] == "failed" and "CLOUDFLARE_API_TOKEN" in r["error"]


def fake_wrangler(src_dump: Path, counts: dict[str, int], uploads: list):
    def run(cmd):
        if cmd[4:6] == ["d1", "export"]:
            Path(cmd[cmd.index("--output") + 1]).write_text(src_dump.read_text())
            return 0, ""
        if cmd[4:6] == ["d1", "execute"]:
            return 0, "wrangler noise\n" + json.dumps(
                [
                    {
                        "results": [{"t": t, "n": n} for t, n in counts.items()],
                        "success": True,
                    }
                ]
            )
        if cmd[4:7] == ["r2", "object", "put"]:
            uploads.append(cmd[7])
            return 0, ""
        return 1, "unexpected"

    return run


def test_backup_live_records_counts_once_per_day(tmp_path, monkeypatch):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    dump = tmp_path / "src.sql"
    counts = make_dump(dump)
    uploads = []
    r1 = BK.backup(
        tmp_path,
        "2026-12-04",
        "greenjobs",
        "b",
        True,
        fake_wrangler(dump, counts, uploads),
    )
    r2 = BK.backup(
        tmp_path,
        "2026-12-04",
        "greenjobs",
        "b",
        True,
        fake_wrangler(dump, counts, uploads),
    )
    assert (
        r1["status"] == "ok" and r1["counts"]["jobs"] == 2 and len(r1["sha256"]) == 64
    )
    assert r2["status"] == "skipped" and uploads == ["b/d1/2026-12-04.sql"]
    assert len(C.read_jsonl(tmp_path / "cost_ledger.jsonl")) == 1


def test_restore_drill_passes_on_a_good_dump_and_fails_on_a_short_one(tmp_path):
    dump = tmp_path / "d.sql"
    counts = make_dump(dump)
    ok = RD.drill(tmp_path, "b", False, sqlite_dump=dump, recorded=counts)
    assert ok["ok"] is True
    bad = RD.drill(
        tmp_path,
        "b",
        False,
        sqlite_dump=dump,
        recorded={**counts, "jobs": counts["jobs"] + 5},
    )
    assert bad["ok"] is False and "jobs" in bad["detail"]
    assert RD.drill(tmp_path, "b", False, sqlite_dump=dump, recorded={})["ok"] is False


def test_restore_drill_live_restores_into_scratch_and_deletes_only_scratch(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("CLOUDFLARE_API_TOKEN", "t")
    monkeypatch.setenv("CLOUDFLARE_ACCOUNT_ID", "a")
    dump = tmp_path / "src.sql"
    counts = make_dump(dump)
    BK.backup(
        tmp_path, "2026-12-04", "greenjobs", "b", True, fake_wrangler(dump, counts, [])
    )
    seen = []

    def run(cmd):
        seen.append(cmd)
        if cmd[4:7] == ["r2", "object", "get"]:
            Path(cmd[cmd.index("--file") + 1]).write_text(dump.read_text())
            return 0, ""
        if "--command" in cmd:
            return 0, json.dumps(
                [{"results": [{"t": t, "n": n} for t, n in counts.items()]}]
            )
        return 0, ""

    row = RD.drill(tmp_path, "b", True, runner=run)
    assert row["ok"] is True and row["mode"] == "live"
    deletes = [c for c in seen if c[4:6] == ["d1", "delete"]]
    assert len(deletes) == 1 and deletes[0][6].startswith("greenjobs-drill-")
    assert not any(c[4:6] == ["d1", "delete"] and c[6] == "greenjobs" for c in seen)


def test_acceptance_window_is_ten_working_days_from_3_dec():
    w = A.window("2026-12-03", 10)
    assert (
        w[0] == "2026-12-03"
        and w[-1] == "2026-12-16"
        and "2026-12-05" not in w
        and len(w) == 10
    )


def test_acceptance_outside_window_is_a_no_op(tmp_path):
    assert A.run("2026-11-30", A.LIST, tmp_path, tmp_path, tmp_path / "e.json") is None
    assert not (tmp_path / "acceptance_history.json").exists()


def test_acceptance_grades_from_evidence_only_and_keeps_dated_history(tmp_path):
    status_dir = tmp_path / "status"
    status_dir.mkdir()
    day = "2026-12-04"
    (status_dir / "status.json").write_text(
        json.dumps(
            {
                "generated_at": day + "T06:00:00Z",
                "metrics": [
                    {"id": "M2", "grade": "PASS", "display": "99.5%"},
                    {"id": "M10", "grade": "FAIL", "display": "90%"},
                    {"id": "M4", "grade": "UNMEASURED", "display": "not measured"},
                    {"id": "B1", "grade": "PASS", "display": "5 h"},
                ],
            }
        )
    )
    for s, n in (("ie", 4), ("uk", 0)):
        (status_dir / f"measures_{s}.json").write_text(
            json.dumps({"as_of": day + "T06:00:00Z", "measures": {"live_jobs": n}})
        )
    ev = tmp_path / "ev.json"
    ev.write_text(
        json.dumps(
            {
                "A3": {day: {"ok": True, "note": "job 1 posted, edited, closed"}},
                "A5": {day: {"ok": True, "note": ""}},
                "A6": {"2026-12-03": {"ok": True, "note": "alert received"}},
            }
        )
    )
    e = A.run(day, A.LIST, tmp_path, status_dir, ev)
    g = {k: v["grade"] for k, v in e["items"].items()}
    assert (
        g["A3"] == "PASS" and g["A5"] == "UNMEASURED" and g["A6"] == "UNMEASURED"
    )  # no note / wrong day: not PASS
    assert (
        g["A8"] == "PASS"
        and g["A9"] == "FAIL"
        and g["A10"] == "UNMEASURED"
        and g["A11"] == "PASS"
    )
    assert g["A2-ie"] == "PASS" and g["A2-uk"] == "FAIL" and g["A1"] == "UNMEASURED"
    assert e["verdict"] == "FAIL" and e["day"] == 2
    A.run(
        day, A.LIST, tmp_path, status_dir, ev
    )  # same day again: replaced, not duplicated
    A.run("2026-12-07", A.LIST, tmp_path, status_dir, ev)
    hist = C.read_json(tmp_path / "acceptance_history.json")
    assert list(hist) == ["2026-12-04", "2026-12-07"]
    assert all(
        v["grade"] == "UNMEASURED"
        for k, v in hist["2026-12-07"]["items"].items()
        if k not in ()
    )  # stale status: nothing graded
