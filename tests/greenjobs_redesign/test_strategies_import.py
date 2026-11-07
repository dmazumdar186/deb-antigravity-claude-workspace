"""pytest suite for execution/gtm_client_workflows/greenjobs_redesign/strategies_import.py.

description: Synthetic-fixture tests for the Strategies CSV -> D1 importer: header aliases, cp1252 +
  semicolon + CRLF batch, cross-batch dedupe, retention, hostile input (formula, prompt injection,
  traversal, ragged, NUL), every gate (yield floor, reject ceiling, retention bounds, missing header),
  path refusals (repo, .tmp, symlink escape), no PII in stdout/report, and emitted SQL applied twice
  to d1/schema.sql in sqlite3 :memory: with identical row counts.
inputs: tests/greenjobs_redesign/fixtures/strategies/*.csv (fake data only)
outputs: pytest result; temp files under pytest's tmp_path only
Run: python3 -m pytest tests/greenjobs_redesign/test_strategies_import.py -q
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sqlite3
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign" / "strategies_import.py"
SCHEMA = REPO / "deliverables" / "greenjobs_migration_2026-11-06" / "build" / "d1" / "schema.sql"
FIX = Path(__file__).resolve().parent / "fixtures" / "strategies"
AS_OF = "2026-11-07"

spec = importlib.util.spec_from_file_location("strategies_import", SCRIPT)
si = importlib.util.module_from_spec(spec)
sys.modules["strategies_import"] = si
spec.loader.exec_module(si)

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def fixture_emails() -> set[str]:
    out = set()
    for p in FIX.glob("*.csv"):
        out |= {e.lower() for e in EMAIL_RE.findall(p.read_bytes().decode("cp1252", errors="replace"))}
    return out


def run(capsys, *argv) -> tuple[int, dict, str]:
    code = si.main([str(a) for a in argv])
    out = capsys.readouterr().out
    return code, json.loads(out), out


def base(report, *csvs):
    args = ["--site", "ie", "--report", report, "--as-of", AS_OF]
    for c in csvs:
        args += ["--csv", c]
    return args


def write_csv(path: Path, header, rows):
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(header)
        w.writerows(rows)
    return path


def fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("PRAGMA foreign_keys = ON")
    return con


def counts(con) -> dict:
    # Fixed literal statements per table (no string-built SQL).
    queries = {
        "employers": "SELECT COUNT(*) FROM employers",
        "jobs": "SELECT COUNT(*) FROM jobs",
        "candidates": "SELECT COUNT(*) FROM candidates",
        "applications": "SELECT COUNT(*) FROM applications",
        "import_batches": "SELECT COUNT(*) FROM import_batches",
    }
    return {t: con.execute(q).fetchone()[0] for t, q in queries.items()}


# --------------------------------------------------------------------------- dry run behaviour

def test_candidates_dry_run_two_batches(capsys):
    code, d, out = run(capsys, *base("candidates", FIX / "candidates_batch1.csv", FIX / "candidates_batch2_cp1252.csv"))
    assert code == 0 and d["status"] == "ok" and d["mode"] == "dry_run" and d["sql_written"] is False
    f1, f2 = d["files"]
    assert (f1["encoding"], f1["delimiter"]) == ("utf-8", ",")
    assert (f2["encoding"], f2["delimiter"]) == ("cp1252", ";")
    assert f1["excluded"] == {"outside_retention": 1, "no_activity_date": 1}
    assert d["reject_reasons"] == {"unsafe_filename": 1, "ragged_row": 1, "invalid_email": 1}
    assert d["totals"]["duplicates_collapsed"] == 1 and d["totals"]["records_out"] == 18
    assert d["flags"]["formula_injection"] == 1 and d["flags"]["prompt_injection"] == 1
    assert d["flags"]["nul_removed"] == 1
    for r in d["rejects"]:
        assert set(r) == {"file", "row", "column", "reason", "evidence"} and len(r["evidence"]) <= 40
    reasons = {w["reason"] for w in d["warnings"]}
    assert "formula_injection_neutralised" in reasons and "prompt_injection_flagged" in reasons


def test_no_pii_in_stdout_or_report(capsys, tmp_path):
    rep = tmp_path / "report.json"
    outs = []
    for argv in (base("candidates", FIX / "candidates_batch1.csv", FIX / "candidates_batch2_cp1252.csv"),
                 base("applications", FIX / "applications.csv") + ["--jobs-csv", FIX / "jobs.csv"],
                 base("recruiters", FIX / "recruiters.csv"),
                 base("profiles", FIX / "profiles.csv") + ["--candidates-csv", FIX / "candidates_batch1.csv"]):
        _, _, out = run(capsys, *argv, "--report-out", rep)
        outs += [out, rep.read_text(encoding="utf-8")]
    blob = "\n".join(outs).lower()
    for email in fixture_emails():
        assert email not in blob, "full email leaked"
    for pii in ("candidate one", "o'candidate", "seán", "555 0101", "555 1011", "test contact one", "hyperlink"):
        assert pii not in blob, pii
    assert "n*** len=12" in blob  # masked invalid email evidence


def test_mask_and_evidence_helpers():
    assert si.mask_email("jane.doe@example.com") == "j***@example.com"
    assert "@" not in si.mask_email("nope")
    assert "example.com" in si.safe_text_evidence("mail jane.doe@example.com now")
    assert "jane.doe" not in si.safe_text_evidence("mail jane.doe@example.com now")
    assert "5550101" not in si.safe_text_evidence("call +353 1 5550101").replace(" ", "")
    assert si.evidence_for("Test Person", {"type": "text", "pii": True}) == "len=11"


def test_formula_rules():
    ctx = si.Ctx(site="ie", report="candidates", as_of=si.date(2026, 11, 7), cutoff_iso="2024-11-07T00:00:00Z",
                 date_formats=["%d/%m/%Y"])
    text = {"type": "text", "max_len": 100}
    assert si.convert("phone", text, "-", ctx) == "-"
    assert si.convert("phone", text, "+353 (1) 555-0100", ctx) == "+353 (1) 555-0100"
    assert si.convert("x", text, "=1+1", ctx) == "'=1+1"
    assert si.convert("x", text, "@SUM(A1)", ctx) == "'@SUM(A1)"
    assert si.convert("x", text, "-2+cmd|' /C calc'!A0", ctx).startswith("'")
    assert si.convert("x", text, "\t=evil", ctx).startswith("'=")
    assert si.convert("x", text, "a\x07b\x00c", ctx) == "abc"
    assert ctx.flags["formula_injection"] == 4
    with pytest.raises(si.RowReject) as e:
        si.convert("email", {"type": "email"}, "=x@example.com", ctx)
    assert e.value.reason == "formula_injection"
    for bad in ("../a.pdf", "/etc/passwd", "C:\\cv.pdf", "https://x.example.com/a.pdf", "%2e%2e%2fa"):
        with pytest.raises(si.RowReject):
            si.convert("cv", {"type": "filename"}, bad, ctx)
    assert si.convert("cv", {"type": "filename"}, "my_cv.pdf", ctx) == "my_cv.pdf"
    with pytest.raises(si.RowReject) as e:
        si.convert("t", {"type": "text", "max_len": 5}, "toolongvalue", ctx)
    assert e.value.reason == "too_long"
    assert si.convert("t", {"type": "text", "max_len": 5, "on_too_long": "truncate"}, "toolongvalue", ctx) == "toolo"


def test_header_aliases_insensitive():
    rep = si.load_mapping(si.DEFAULT_MAPPING)["reports"]["candidates"]
    mapped, _, unmapped, _ = si.map_headers("candidates", rep, ["  candidate_id ", "E-MAIL ADDRESS", "last login", "Shoe Size"])
    assert mapped == {"strategies_id": 0, "email": 1, "last_login": 2}
    assert unmapped == ["Shoe Size"]


def test_jobs_status_and_retention(capsys):
    code, d, _ = run(capsys, *base("jobs", FIX / "jobs.csv"))
    assert code == 0
    f = d["files"][0]
    assert f["excluded"] == {"outside_retention": 1}
    assert d["reject_reasons"] == {"too_short": 1}
    assert d["totals"]["live_jobs"] == 4  # 7002 closed on 01/09/2026


def test_profiles_merge_and_unknown(capsys):
    code, d, _ = run(capsys, *base("profiles", FIX / "profiles.csv"), "--candidates-csv", FIX / "candidates_batch1.csv")
    assert code == 0 and d["reject_reasons"] == {"unknown_candidate": 1}
    assert d["reference_inputs"]["candidates"]["kept"] > 0


def test_profiles_without_email_source_is_usage_error(capsys):
    code, d, _ = run(capsys, *base("profiles", FIX / "profiles.csv"))
    assert code == 2 and "candidates-csv" in d["error"]


def test_applications_orphan_and_dedupe(capsys):
    code, d, _ = run(capsys, *base("applications", FIX / "applications.csv"), "--jobs-csv", FIX / "jobs.csv")
    assert code == 0 and d["reject_reasons"] == {"orphan_job": 1}
    assert d["totals"]["duplicates_collapsed"] == 1


def test_applications_without_jobs_warns_dry_and_refuses_sql(capsys, tmp_path):
    code, d, _ = run(capsys, *base("applications", FIX / "applications.csv"))
    assert code == 0 and any(w["reason"] == "orphan_check_skipped" for w in d["warnings"])
    code, d, _ = run(capsys, *base("applications", FIX / "applications.csv"), "--emit-sql", tmp_path / "a.sql")
    assert code == 2 and not (tmp_path / "a.sql").exists()


def test_known_job_ids_file(capsys, tmp_path):
    ids = tmp_path / "ids.txt"
    ids.write_text("# job ids\n7001\n7002\n", encoding="utf-8")
    code, d, _ = run(capsys, *base("applications", FIX / "applications.csv"), "--known-job-ids", ids,
                     "--max-reject-rate", "0.9")
    assert code == 0 and d["reject_reasons"]["orphan_job"] == 4


# --------------------------------------------------------------------------- gates

def test_missing_required_header_exit_2(capsys):
    code, d, _ = run(capsys, *base("candidates", FIX / "candidates_no_email.csv"))
    assert code == 2 and "email" in d["error"] and "alias" in d["error"]


@pytest.mark.parametrize("months", ["5", "85", "0"])
def test_retention_bounds(capsys, months):
    code, d, _ = run(capsys, *base("candidates", FIX / "candidates_batch1.csv"), "--retention-months", months)
    assert code == 2


@pytest.mark.parametrize("months", ["6", "84"])
def test_retention_bounds_ok(capsys, months):
    code, _, _ = run(capsys, *base("candidates", FIX / "candidates_batch1.csv"), "--retention-months", months)
    assert code == 0


def test_low_yield_gate(capsys, tmp_path):
    p = write_csv(tmp_path / "old.csv", ["Candidate ID", "Email", "Last Login"],
                  [[str(i), f"old{i}@example.com", "01/01/2019"] for i in range(30)])
    code, d, _ = run(capsys, *base("candidates", p), "--emit-sql", tmp_path / "o.sql")
    assert code == 3 and d["status"] == "gate_failed" and not (tmp_path / "o.sql").exists()
    g = d["gates"]["failures"][0]
    assert g["gate"] == "min_yield" and g["excluded"] == {"outside_retention": 30}
    code, d, _ = run(capsys, *base("candidates", p), "--allow-low-yield")
    assert code == 0


def test_reject_ceiling_gate(capsys, tmp_path):
    rows = [[str(i), f"ok{i}@example.com" if i % 2 else "broken-address", "01/10/2026"] for i in range(20)]
    p = write_csv(tmp_path / "bad.csv", ["Candidate ID", "Email", "Last Login"], rows)
    code, d, out = run(capsys, *base("candidates", p))
    assert code == 3
    g = [x for x in d["gates"]["failures"] if x["gate"] == "max_reject_rate"][0]
    assert g["value"] == 0.5 and g["evidence"] and "invalid_email" in g["evidence"][0]
    assert "broken-address" not in out
    code, _, _ = run(capsys, *base("candidates", p), "--max-reject-rate", "0.6")
    assert code == 0


def test_bad_ratio_flag_is_usage_error(capsys):
    with pytest.raises(SystemExit) as e:
        si.main([str(a) for a in base("candidates", FIX / "candidates_batch1.csv")] + ["--min-yield", "1.5"])
    assert e.value.code == 2


def test_zero_rows_is_noop(capsys, tmp_path):
    code, d, _ = run(capsys, *base("candidates", FIX / "candidates_header_only.csv"), "--emit-sql", tmp_path / "z.sql")
    assert code == 0 and d["status"] == "noop" and not (tmp_path / "z.sql").exists()


def test_done_sha256_skips_file(capsys, tmp_path):
    sha = si.read_csv(FIX / "recruiters.csv")["sha256"]
    done = tmp_path / "done.txt"
    done.write_text(sha + "\n", encoding="utf-8")
    code, d, _ = run(capsys, *base("recruiters", FIX / "recruiters.csv"), "--done-sha256", done)
    assert code == 0 and d["status"] == "noop" and d["files"][0]["skipped"] == "already_imported"


# --------------------------------------------------------------------------- path safety

def test_paths(capsys, tmp_path):
    good = FIX / "recruiters.csv"
    tmpdir = REPO / ".tmp"
    tmpdir.mkdir(exist_ok=True)
    in_repo_csv = tmpdir / f"strat_test_{uuid.uuid4().hex}.csv"
    in_repo_csv.write_bytes(good.read_bytes())
    link_in = tmp_path / "link.csv"
    link_out = tmp_path / "link.sql"
    try:
        link_in.symlink_to(in_repo_csv)
        link_out.symlink_to(tmpdir / "escape.sql")
    except OSError:  # Windows without symlink privilege: the resolve() rule is still covered on Linux CI
        in_repo_csv.unlink()
        pytest.skip("symlinks not permitted on this host")
    try:
        assert run(capsys, *base("recruiters", in_repo_csv))[0] == 2          # CSV in repo, not fixtures
        assert run(capsys, *base("recruiters", link_in))[0] == 2              # symlink into repo
        assert run(capsys, *base("recruiters", good), "--emit-sql", tmpdir / "x.sql")[0] == 2   # SQL in .tmp
        assert run(capsys, *base("recruiters", good), "--emit-sql", link_out)[0] == 2           # symlink escape
        assert run(capsys, *base("recruiters", good), "--report-out", REPO / "strat_report.json")[0] == 2
        assert run(capsys, *base("recruiters", good), "--emit-sql", tmp_path / "nodir" / "x.sql")[0] == 2
        rep = tmpdir / f"strat_report_{uuid.uuid4().hex}.json"
        assert run(capsys, *base("recruiters", good), "--report-out", rep)[0] == 0              # report in .tmp ok
        assert rep.exists()
        rep.unlink()
    finally:
        in_repo_csv.unlink()
    assert not (tmpdir / "x.sql").exists() and not (tmpdir / "escape.sql").exists()
    assert not (REPO / "strat_report.json").exists()


# --------------------------------------------------------------------------- SQL emission + idempotency

def emit_all(capsys, tmp_path) -> list[Path]:
    plan = [
        ("recruiters", [FIX / "recruiters.csv"], []),
        ("jobs", [FIX / "jobs.csv"], []),
        ("candidates", [FIX / "candidates_batch1.csv", FIX / "candidates_batch2_cp1252.csv"], []),
        ("profiles", [FIX / "profiles.csv"], ["--candidates-csv", FIX / "candidates_batch1.csv"]),
        ("applications", [FIX / "applications.csv"], ["--jobs-csv", FIX / "jobs.csv"]),
    ]
    files = []
    for report, csvs, extra in plan:
        out = tmp_path / f"{report}.sql"
        code, d, _ = run(capsys, *base(report, *csvs), *extra, "--emit-sql", out)
        assert code == 0 and d["sql_written"], (report, d.get("error"), d.get("gates"))
        files.append(out)
    return files


def test_emitted_sql_idempotent(capsys, tmp_path):
    files = emit_all(capsys, tmp_path)
    con = fresh_db()
    for f in files:
        con.executescript(f.read_text(encoding="utf-8"))
    first = counts(con)
    assert first == {"employers": 4, "jobs": 5, "candidates": 18, "applications": 6, "import_batches": 6}
    for f in files:
        con.executescript(f.read_text(encoding="utf-8"))
    assert counts(con) == first
    # values
    row = con.execute("SELECT first_name, last_name, headline FROM candidates WHERE email_norm = ?",
                      ("test.candidate.two@example.com",)).fetchone()
    assert row == ("Seán", "Ó Tester", "Energy analyst")  # cp1252 batch is newer; profile merged
    assert con.execute("SELECT last_name FROM candidates WHERE source_id='1010'").fetchone()[0] == "O'Candidate Ten"
    assert con.execute("SELECT first_name FROM candidates WHERE source_id='1004'").fetchone()[0].startswith("'=")
    status = dict(con.execute("SELECT source_id, status FROM jobs").fetchall())
    assert status["7001"] == "live" and status["7002"] == "closed"
    emp = dict(con.execute("SELECT source_id, employer_id FROM jobs").fetchall())
    assert emp["7001"] == "ie:strat:501" and emp["7007"] is None   # unknown employer -> NULL, FK safe
    assert con.execute("SELECT logo_key FROM employers WHERE source_id='501'").fetchone()[0] == \
        "strategies/ie/logos/example-energy.png"
    app = con.execute("SELECT source_id, candidate_id, delivery_status, dedupe_key FROM applications "
                      "WHERE job_id='ie:strat:7001' AND applicant_email='test.candidate.one@example.com'").fetchone()
    assert app[0] == "9002" and app[1] == "ie:strat:1001" and app[2] == "imported"
    assert app[3] == si.hashlib.sha256(b"ie|ie:strat:7001|test.candidate.one@example.com").hexdigest()


def test_same_file_twice_is_skipped(capsys, tmp_path):
    out = tmp_path / "r.sql"
    code, d, _ = run(capsys, *base("recruiters", FIX / "recruiters.csv", FIX / "recruiters.csv"), "--emit-sql", out)
    assert code == 0 and d["files"][1]["skipped"] == "duplicate_file_in_this_run"
    sql = out.read_text(encoding="utf-8")
    assert sql.count("INSERT OR IGNORE INTO import_batches") == 1
    con = fresh_db()
    con.executescript(sql)
    con.executescript(sql)
    assert counts(con)["import_batches"] == 1 and counts(con)["employers"] == 4


def test_sql_literal_escaping():
    assert si.sql_lit("O'Brien") == "'O''Brien'"
    assert si.sql_lit(None) == "NULL" and si.sql_lit(3) == "3"
    assert si.sql_lit("a'); DROP TABLE jobs; --") == "'a''); DROP TABLE jobs; --'"
    with pytest.raises(ValueError):
        si.sql_lit("a\x00b")
    con = fresh_db()
    hostile = "x'); DROP TABLE jobs; -- ?1 ?2"
    tpl = si.load_upserts(si.DEFAULT_UPSERTS)
    stmt = si.render(tpl["employers"], ["ie:strat:1", "ie", "strategies", "1", hostile, "x", None, None, None, None,
                                        None, None, "2026-11-07T00:00:00Z"])
    con.executescript(stmt)
    assert con.execute("SELECT name FROM employers").fetchone()[0] == hostile
    assert counts(con)["jobs"] == 0


def test_upsert_shapes_match_contract():
    tpl = si.load_upserts(si.DEFAULT_UPSERTS)
    assert "ON CONFLICT (dedupe_key) DO NOTHING" in tpl["applications"]
    assert "WHERE jobs.source = 'strategies'" in tpl["jobs"]
    assert "ON CONFLICT (site, email_norm)" in tpl["candidates"]


def test_cli_subprocess_and_no_network_imports():
    r = subprocess.run([sys.executable, str(SCRIPT), "--site", "ie", "--report", "recruiters", "--csv",
                        str(FIX / "recruiters.csv"), "--as-of", AS_OF], capture_output=True, text=True,
                       encoding="utf-8", errors="replace", timeout=60)
    assert r.returncode == 0 and json.loads(r.stdout)["status"] == "ok"
    src = SCRIPT.read_text(encoding="utf-8")
    for banned in ("import requests", "urllib.request", "http.client", "socket", "except:", "except Exception"):
        assert banned not in src, banned
