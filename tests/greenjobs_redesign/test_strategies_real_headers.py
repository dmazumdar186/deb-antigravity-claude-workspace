"""pytest: the importer against the REAL Strategies header rows (client, 19 Nov 2026), IE and UK.

description: every real report header row sniffs clean (no unknown header, every required field mapped);
  the duplicated ReferralAmount is never mapped and warns; IE/UK column orders import identically (by name,
  never position); IE sPreferredWorkRegionDesc = UK sPreferredWorkLocationDesc; a quoted header line parses;
  Email/AppLink drive apply_mode; ClientPK<->ClientFK, JobPK<->JobPk, CandidatePK join across reports; Consent
  and Marketing are carried and Consent=0 drops that candidate's alerts; Jobs By Email -> pending alert rows;
  SiteTag/SiteFK are counted and --expect-site-tag filters. Synthetic data only, written under tmp_path.
inputs: deliverables/greenjobs_migration_2026-11-06/build/import/REAL_HEADERS_2026-11-19.json (header names only)
Run: python3 -m pytest -q tests/greenjobs_redesign/test_strategies_real_headers.py
"""

from __future__ import annotations

import csv
import importlib.util
import json
import re
import sqlite3
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = (
    REPO
    / "execution"
    / "gtm_client_workflows"
    / "greenjobs_redesign"
    / "strategies_import.py"
)
SCHEMA = (
    REPO
    / "deliverables"
    / "greenjobs_migration_2026-11-06"
    / "build"
    / "d1"
    / "schema.sql"
)
REAL = json.loads(
    (
        REPO
        / "deliverables"
        / "greenjobs_migration_2026-11-06"
        / "build"
        / "import"
        / "REAL_HEADERS_2026-11-19.json"
    ).read_text(encoding="utf-8")
)
AS_OF = "2026-11-07"

spec = importlib.util.spec_from_file_location("strategies_import_real", SCRIPT)
si = importlib.util.module_from_spec(spec)
sys.modules["strategies_import_real"] = si
spec.loader.exec_module(si)


def report_of(sheet: str) -> str:
    for prefix, rep in (
        ("Recruiters", "recruiters"),
        ("Members registration", "candidates"),
        ("Members profile", "profiles"),
        ("Jobs By Email", "alerts"),
        ("Jobs (All", "jobs"),
        ("Job Applications", "applications"),
    ):
        if sheet.startswith(prefix):
            return rep
    raise AssertionError(sheet)


def header(site: str, report: str) -> list[str]:
    return next(
        h for sheet, h in REAL["sites"][site].items() if report_of(sheet) == report
    )


def write(path: Path, head: list[str], rows: list[dict], delimiter: str = ",") -> Path:
    """Rows are dicts keyed by header NAME; a duplicated header gets the same value list position-wise."""
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh, delimiter=delimiter)
        w.writerow(head)
        for r in rows:
            seen: dict[str, int] = {}
            out = []
            for h in head:
                v = r.get(h, "")
                if isinstance(v, list):
                    v = v[seen.get(h, 0)]
                seen[h] = seen.get(h, 0) + 1
                out.append(v)
            w.writerow(out)
    return path


def run(capsys, *argv) -> tuple[int, dict, str]:
    code = si.main([str(a) for a in argv])
    out = capsys.readouterr().out
    return code, json.loads(out), out


def imp(capsys, site, report, path, *extra):
    return run(
        capsys,
        "--site",
        site,
        "--report",
        report,
        "--as-of",
        AS_OF,
        "--csv",
        path,
        *extra,
    )


DESC = "A synthetic job description that is long enough to pass the validator."
JOB = {
    "JobPK": "7001",
    "ClientFK": "501",
    "SiteFK": "1",
    "JobTitle": "Wind Engineer",
    "LiveDate": "01/11/2026",
    "ExpiryDate": "30/12/2026",
    "SalaryMin": "40000",
    "SalaryMax": "50000",
    "SalaryFrame": "Per Annum",
    "SalaryDesc": "EUR 40-50k",
    "Email": "hr@client.example.com",
    "CompanyName": "Client Ltd",
    "ReferralAmount": ["100", "200"],
    "JobDescription": DESC,
    "AppLink": "",
    "sIndustrySectorDesc": "Wind",
    "sRegionDesc": "Munster",
    "sJobTypeDesc": "Permanent",
    "sVicinityDesc": "Cork",
    "LastChange": "02/11/2026",
    "EditedBy": "staff",
}


# --------------------------------------------------------------------------- 0. every real header row is fully accounted for


@pytest.mark.parametrize("site", ["ie", "uk"])
@pytest.mark.parametrize("report", list(si.REPORTS))
def test_real_header_rows_sniff_clean(capsys, tmp_path, site, report):
    p = write(tmp_path / f"{site}_{report}.csv", header(site, report), [])
    code, d, _ = run(capsys, "--report", report, "--sniff", p)
    assert code == 0 and d["status"] == "ok", d["missing_required"]
    assert d["unknown_headers"] == [], d["unknown_headers"]
    assert d["duplicate_headers"] == (["ReferralAmount"] if report == "jobs" else [])
    assert all(v["verdict"] in ("mapped", "ignored", "duplicate") for v in d["headers"])


def test_mapping_aliases_are_real_header_names():
    """Every alias in the mapping is a real header name (no leftover guesses)."""
    real = {
        si.norm_header(h)
        for site in REAL["sites"].values()
        for hs in site.values()
        for h in hs
    }
    m = si.load_mapping(si.DEFAULT_MAPPING)
    for rep_name, rep in m["reports"].items():
        for fname, f in rep["fields"].items():
            for a in f["aliases"]:
                assert si.norm_header(a) in real, (rep_name, fname, a)
        for h in rep.get("ignored_headers", []):
            assert si.norm_header(h) in real, (rep_name, h)


# --------------------------------------------------------------------------- 1. duplicate ReferralAmount


def test_duplicate_referral_amount_ignored_and_warned(capsys, tmp_path):
    p = write(tmp_path / "jobs.csv", header("ie", "jobs"), [JOB])
    code, d, _ = imp(capsys, "ie", "jobs", p)
    assert code == 0 and d["totals"]["rows_kept"] == 1
    f = d["files"][0]
    assert (
        f["headers"]["duplicate"] == ["ReferralAmount"]
        and "ReferralAmount" not in f["headers"]["mapped"].values()
    )
    assert [w for w in d["warnings"] if w["reason"] == "duplicate_header_ignored"] == [
        {
            "file": "jobs.csv",
            "row": 1,
            "column": None,
            "reason": "duplicate_header_ignored",
            "evidence": "ReferralAmount",
        }
    ]


def test_duplicated_required_header_fails_loud(capsys, tmp_path):
    head = header("ie", "jobs") + ["JobTitle"]
    p = write(tmp_path / "jobs.csv", head, [JOB])
    code, d, _ = imp(capsys, "ie", "jobs", p)
    assert (
        code == 2
        and "title" in d["error"]
        and "Duplicated (never mapped): ['JobTitle', 'ReferralAmount']" in d["error"]
    )


# --------------------------------------------------------------------------- 2. IE and UK column order differ: by name only


def sql_body(path: Path) -> list[str]:
    return [
        ln
        for ln in path.read_text(encoding="utf-8").splitlines()
        if not ln.startswith("--")
    ]


def test_ie_and_uk_job_orders_import_identically(capsys, tmp_path):
    ie_h, uk_h = header("ie", "jobs"), header("uk", "jobs")
    assert ie_h != uk_h and sorted(ie_h) == sorted(uk_h)
    rows = [
        JOB,
        {
            **JOB,
            "JobPK": "7002",
            "AppLink": "https://ats.example.com/7002",
            "sVicinityDesc": "",
            "nRegionVal": "9",
            "nJobTypeVal": "3",
            "sEducationLevelDesc": "Degree",
            "sJobCategoryDesc": "Engineering",
        },
    ]
    outs = []
    for site_order, head in (("ie", ie_h), ("uk", uk_h)):
        p = write(tmp_path / f"{site_order}.csv", head, rows)
        o = tmp_path / f"{site_order}.sql"
        code, d, _ = imp(capsys, "ie", "jobs", p, "--emit-sql", o)
        assert code == 0 and d["sql_written"]
        outs.append(o)
    a, b = sql_body(outs[0]), sql_body(outs[1])
    a = [
        re.sub(r"'[0-9a-f]{64}'", "'SHA'", x) for x in a
    ]  # import_batches row: the files differ by design
    b = [re.sub(r"'[0-9a-f]{64}'", "'SHA'", x) for x in b]
    assert a == b
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.executescript(outs[1].read_text(encoding="utf-8"))
    got = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT source_id, location, region, job_type, apply_mode FROM jobs"
        )
    }
    assert got == {
        "7001": ("Cork", "Munster", "Permanent", "email"),
        "7002": ("Munster", "Munster", "Permanent", "link"),
    }


# --------------------------------------------------------------------------- 3. profile region alias


@pytest.mark.parametrize(
    "site,col",
    [("ie", "sPreferredWorkRegionDesc"), ("uk", "sPreferredWorkLocationDesc")],
)
def test_profile_preferred_region_alias(capsys, tmp_path, site, col):
    assert col in header(site, "profiles")
    p = write(
        tmp_path / "prof.csv",
        header(site, "profiles"),
        [
            {
                "CandidatePK": "1001",
                "sEmail": "a.candidate@example.com",
                col: "Munster",
                "dLastLoggedIn": "01/11/2026",
                "sTown": "Hometown",
                "sCurrentJobTitleDesc": "Engineer",
            }
        ],
    )
    o = tmp_path / "p.sql"
    code, d, _ = imp(capsys, site, "profiles", p, "--emit-sql", o)
    assert code == 0 and d["files"][0]["headers"]["mapped"]["location"] == col
    sql = o.read_text(encoding="utf-8")
    assert (
        "'Munster'" in sql and "Hometown" not in sql
    )  # preferred area kept, home town never imported


# --------------------------------------------------------------------------- 4. quoted header line (UK jobs)


def test_quoted_header_line_parses(capsys, tmp_path):
    head = header("uk", "jobs")
    line = head[0] + "," + ",".join(f'"{h}"' for h in head[1:])
    p = tmp_path / "uk_jobs.csv"
    with p.open("w", encoding="utf-8", newline="") as fh:
        fh.write(line + "\r\n")
        csv.writer(fh).writerow(
            [JOB.get(h, "") if not isinstance(JOB.get(h), list) else "1" for h in head]
        )
    code, d, _ = run(capsys, "--report", "jobs", "--sniff", p)
    assert (
        code == 0
        and d["mapped"]["strategies_id"] == "JobPK"
        and d["mapped"]["employer_id"] == "ClientFK"
    )
    assert d["first_row"]["width_matches"] is True
    code, d, _ = imp(capsys, "uk", "jobs", p)
    assert code == 0 and d["totals"]["rows_kept"] == 1


# --------------------------------------------------------------------------- 5-8. one end-to-end import over the real shapes


def dataset(tmp_path: Path, site: str) -> dict[str, Path]:
    w = lambda name, rep, rows: write(
        tmp_path / f"{site}_{name}.csv", header(site, rep), rows
    )  # noqa: E731
    return {
        "recruiters": w(
            "rec",
            "recruiters",
            [
                {
                    "ClientPK": "501",
                    "SiteTag": "GJ",
                    "CompanyName": "Client Ltd",
                    "email": "boss@client.example.com",
                    "contactName": "Pat Boss",
                    "CreateDate": "01/01/2026",
                    "LastJobLiveDate": "01/11/2026",
                }
            ],
        ),
        "jobs": w(
            "jobs",
            "jobs",
            [
                JOB,
                {
                    **JOB,
                    "JobPK": "7002",
                    "Email": "hr@client.example.com",
                    "AppLink": "https://ats.example.com/7002",
                },
                {
                    **JOB,
                    "JobPK": "7003",
                    "Email": "not-an-email",
                    "AppLink": "http://insecure.example.com",
                },
            ],
        ),
        "candidates": w(
            "cand",
            "candidates",
            [
                {
                    "SiteTag": "GJ",
                    "CandidatePK": "1001",
                    "email": "One@Example.com",
                    "FirstName": "One",
                    "LastName": "Cand",
                    "registerDate": "01/02/2026",
                    "LastLoggedIn": "01/11/2026",
                    "Marketing": "1",
                    "Consent": "1",
                    "HasJobsByEmail": "1",
                    "HomePhone": "01 234 5678",
                    "Mobile": "087 123 4567",
                },
                {
                    "SiteTag": "GJ",
                    "CandidatePK": "1002",
                    "email": "two@example.com",
                    "FirstName": "Two",
                    "LastName": "Cand",
                    "registerDate": "01/02/2026",
                    "LastLoggedIn": "01/11/2026",
                    "Marketing": "0",
                    "Consent": "0",
                    "HasJobsByEmail": "1",
                },
                {
                    "SiteTag": "GJ",
                    "CandidatePK": "1003",
                    "email": "three@example.com",
                    "FirstName": "Three",
                    "LastName": "Cand",
                    "registerDate": "01/02/2026",
                    "LastLoggedIn": "01/11/2026",
                    "Marketing": "",
                    "Consent": "",
                    "HasJobsByEmail": "0",
                },
            ],
        ),
        "profiles": w(
            "prof",
            "profiles",
            [
                {
                    "CandidatePK": "1001",
                    "sCurrentJobTitleDesc": "Engineer",
                    "dLastLoggedIn": "02/11/2026",
                }
            ],
        ),
        "applications": w(
            "apps",
            "applications",
            [
                {
                    "JobPk": "7001",
                    "ApplicationDate": "03/11/2026",
                    "Name": "One Cand",
                    "CandEmail": "one@example.com",
                    "JobTitle": "Wind Engineer",
                }
            ],
        ),
        "alerts": w(
            "alerts",
            "alerts",
            [
                {
                    "CandidatePK": "1001",
                    "Email": "one@example.com",
                    "Name": "One Cand",
                    "SearchName": "Wind in Cork",
                    "Keywords": "wind",
                    "SalaryMin": "40000",
                    "SalaryFrame": "Per Annum",
                    "sRegionDesc": "Munster",
                    "sIndustrySectorDesc": "Wind;Solar",
                },
                {
                    "CandidatePK": "1002",
                    "Email": "two@example.com",
                    "Name": "Two Cand",
                    "Keywords": "solar",
                },
                {
                    "CandidatePK": "9999",
                    "Email": "gone@example.com",
                    "Name": "Gone",
                    "Keywords": "x",
                },
            ],
        ),
    }


def emit_all(capsys, tmp_path, site="ie") -> sqlite3.Connection:
    ds = dataset(tmp_path, site)
    con = sqlite3.connect(":memory:")
    con.executescript(SCHEMA.read_text(encoding="utf-8"))
    con.execute("PRAGMA foreign_keys = ON")
    plan = [
        ("recruiters", []),
        ("jobs", []),
        ("candidates", []),
        ("profiles", ["--candidates-csv", ds["candidates"]]),
        ("applications", ["--jobs-csv", ds["jobs"]]),
        ("alerts", ["--candidates-csv", ds["candidates"]]),
    ]
    sql = []
    for rep, extra in plan:
        o = tmp_path / f"{site}_{rep}.sql"
        code, d, _ = imp(
            capsys, site, rep, ds[rep], *extra, "--emit-sql", o, "--allow-low-yield"
        )
        assert code == 0 and d["sql_written"], (rep, d.get("error"), d.get("gates"))
        sql.append(o.read_text(encoding="utf-8"))
    for _ in range(2):  # idempotent
        for s in sql:
            con.executescript(s)
    return con


@pytest.mark.parametrize("site", ["ie", "uk"])
def test_end_to_end_keys_apply_mode_consent_alerts(capsys, tmp_path, site):
    con = emit_all(capsys, tmp_path, site)
    # 6. keys: ClientPK <-> ClientFK, JobPK <-> JobPk, CandidatePK across registration / profile / alerts
    assert (
        con.execute(
            f"SELECT employer_id FROM jobs WHERE id = '{site}:strat:7001'"
        ).fetchone()[0]
        == f"{site}:strat:501"
    )
    assert con.execute("SELECT job_id, candidate_id FROM applications").fetchall() == [
        (f"{site}:strat:7001", f"{site}:strat:1001")
    ]
    assert (
        con.execute(
            "SELECT headline FROM candidates WHERE source_id = '1001'"
        ).fetchone()[0]
        == "Engineer"
    )
    # 5. apply mode: AppLink https -> link; else valid Email -> email; else site default (NULL)
    modes = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT source_id, apply_mode, apply_email, apply_url FROM jobs"
        )
    }
    assert modes == {
        "7001": ("email", "hr@client.example.com", None),
        "7002": ("link", None, "https://ats.example.com/7002"),
        "7003": ("email", None, None),
    }
    # 7. Consent and Marketing carried through; mobile preferred over home phone
    c = {
        r[0]: r[1:]
        for r in con.execute(
            "SELECT source_id, consent_marketing, strategies_consent, phone FROM candidates"
        )
    }
    assert c == {
        "1001": (1, 1, "087 123 4567"),
        "1002": (0, 0, None),
        "1003": (0, None, None),
    }
    # 8. Jobs By Email -> pending alert subscriptions; Consent=0 and unknown candidates excluded; Name not stored
    alerts = con.execute(
        "SELECT email_norm, status, frequency, query_json FROM alert_subscriptions"
    ).fetchall()
    assert len(alerts) == 1
    email, status, freq, q = alerts[0]
    assert (email, status, freq) == ("one@example.com", "pending", "weekly")
    assert json.loads(q) == {
        "label": "Wind in Cork",
        "keywords": "wind",
        "sal_min": 40000,
        "period": "year",
        "region": "Munster",
        "sectors": ["Wind", "Solar"],
    }
    assert "One Cand" not in q
    assert con.execute("PRAGMA foreign_key_check").fetchall() == []


def test_alerts_report_summary_and_guards(capsys, tmp_path):
    ds = dataset(tmp_path, "ie")
    code, d, _ = imp(capsys, "ie", "alerts", ds["alerts"])
    assert code == 2 and "--candidates-csv" in d["error"]
    code, d, out = imp(
        capsys,
        "ie",
        "alerts",
        ds["alerts"],
        "--candidates-csv",
        ds["candidates"],
        "--allow-low-yield",
    )
    assert code == 0 and d["target_table"] == "alert_subscriptions"
    assert d["files"][0]["excluded"] == {
        "candidate_consent_0": 1,
        "candidate_not_retained": 1,
    }
    assert "One Cand" not in out and "one@example.com" not in out


def test_site_tag_counted_and_filtered(capsys, tmp_path):
    p = write(
        tmp_path / "cand.csv",
        header("ie", "candidates"),
        [
            {
                "SiteTag": "GJIE",
                "CandidatePK": "1",
                "email": "a@example.com",
                "LastLoggedIn": "01/11/2026",
            },
            {
                "SiteTag": "GJUK",
                "CandidatePK": "2",
                "email": "b@example.com",
                "LastLoggedIn": "01/11/2026",
            },
        ],
    )
    code, d, _ = imp(capsys, "ie", "candidates", p)
    assert (
        code == 0
        and d["files"][0]["site_tags"] == {"GJIE": 1, "GJUK": 1}
        and d["totals"]["rows_kept"] == 2
    )
    code, d, _ = imp(capsys, "ie", "candidates", p, "--expect-site-tag", "GJIE")
    assert (
        code == 0
        and d["totals"]["rows_kept"] == 1
        and d["files"][0]["excluded"] == {"other_site_tag": 1}
    )
