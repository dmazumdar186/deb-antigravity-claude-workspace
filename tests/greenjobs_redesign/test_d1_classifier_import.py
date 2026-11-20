"""pytest: job_classifier.py, gaia_d1_sync.py and the 2026-11-20 strategies_import.py rules (offline).

description: Proves every guard of the classifier -> D1 path fires: low-confidence / conflicting / unfrozen sectors
  go to the review queue (never guessed), the Gaia feed SQL is idempotent, closes (never deletes) jobs that left
  the feed, links duplicates instead of double-listing, never reopens a closed job or overrides a staff review,
  refuses an empty feed, keeps live writes off without GAIA_FEED_ENABLED and posts dry-run by default; the
  Strategies import emits live jobs only, classified, and keeps personal data off D1 unless a candidate config
  says otherwise (consent, date range, categories, minimised fields); Jobs By Email honours Marketing/Consent.
inputs: tests/greenjobs_redesign/fixtures/{gaia_d1,gaia_eval,strategies}/ (fake data only)
outputs: pytest result; temp files under tmp_path only
Run: python3 -m pytest tests/greenjobs_redesign/test_d1_classifier_import.py -q
"""

from __future__ import annotations

import csv
import io
import json
import sqlite3
import sys
import urllib.error
from datetime import date
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
PKG = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
sys.path.insert(0, str(PKG))

import build_site as bs  # noqa: E402
import gaia_d1_sync as gds  # noqa: E402
import job_classifier as jc  # noqa: E402
import strategies_import as si  # noqa: E402

D1 = REPO / "deliverables" / "greenjobs_migration_2026-11-06" / "build" / "d1"
FX = Path(__file__).resolve().parent / "fixtures"
G = FX / "gaia_d1"
ST = FX / "strategies"
FROZEN = jc.TAXONOMY_PATH  # the one vocabulary (platform_worker/src/taxonomy.json); no test copy
TODAY = date(2026, 11, 20)


def fresh_db() -> sqlite3.Connection:
    con = sqlite3.connect(":memory:")
    con.executescript((D1 / "schema.sql").read_text(encoding="utf-8"))
    for m in sorted((D1 / "migrations").glob("*.sql")):
        con.executescript(m.read_text(encoding="utf-8"))
    return con


def frozen() -> jc.Taxonomy:
    return jc.load_taxonomy(FROZEN)


# ------------------------------------------------------------------ classifier


def test_confident_title_is_published_with_derived_fields():
    c = jc.classify(
        {
            "title": "Senior Ecologist",
            "location": "Cork",
            "description": "Habitat and protected species surveys. Hybrid working, 12 month fixed-term contract.",
        },
        "ie",
        frozen(),
    )
    assert c["needs_review"] is False and c["sectors"] == [
        "Ecology, nature recovery & biodiversity"
    ]
    assert c["sector_confidence"] >= jc.SECTOR_CUT and c["sector_method"] == "keyword"
    assert (
        c["regions"] == ["Cork"]
        and c["loc_class"] == "ie"
        and c["workplace"] == "hybrid"
    )
    assert "fixed-term" in c["contract"] and c["job_type"] == "Contract"
    assert c["taxonomy_frozen"] is True and c["taxonomy_version"] == "frozen-1" and c["taxonomy_number"] == 1


def test_no_sector_keyword_is_queued_not_guessed():
    c = jc.classify(
        {
            "title": "Project Coordinator",
            "location": "Leeds",
            "description": "Run the diary and meetings.",
        },
        "uk",
        frozen(),
    )
    assert c["needs_review"] and c["sectors"] == [] and c["sector_method"] == "fallback"
    assert (
        c["suggested_sectors"] == [jc.FALLBACK_SECTOR]
        and "no sector keyword" in c["review_reason"]
    )


def test_unfrozen_taxonomy_queues_every_sector_unless_relaxed(tmp_path):
    tax = jc.load_taxonomy(tmp_path / "absent.json")
    assert tax.frozen is False and tax.sectors == [t[0] for t in bs.TAXONOMY]
    job = {
        "title": "Senior Ecologist",
        "description": "Habitat surveys across Munster for an ecology consultancy.",
    }
    assert "taxonomy not frozen" in jc.classify(job, "ie", tax)["review_reason"]
    assert jc.classify(job, "ie", tax, require_frozen=False)["needs_review"] is False


def test_source_label_conflict_goes_to_review_and_agreement_raises_confidence():
    job = {
        "title": "Senior Ecologist",
        "description": "Habitat surveys for an ecology consultancy in Cork.",
    }
    bad = jc.classify(
        job,
        "ie",
        frozen(),
        hint={"sectors": ["Water & flood"], "confidence": 1.0, "method": "dict"},
    )
    assert (
        bad["needs_review"]
        and bad["sector_method"] == "conflict"
        and bad["suggested_sectors"][0] == "Water & flood"
    )
    good = jc.classify(
        job,
        "ie",
        frozen(),
        hint={
            "sectors": ["Ecology, nature recovery & biodiversity"],
            "confidence": 1.0,
            "method": "dict",
        },
    )
    assert (
        not good["needs_review"]
        and good["sector_method"] == "source+keyword"
        and good["sector_confidence"] >= 0.9
    )
    queued = jc.classify(
        job, "ie", frozen(), hint={"sectors": [], "confidence": 0.0, "method": "queue"}
    )
    assert (
        queued["needs_review"] and "upstream mapping queued" in queued["review_reason"]
    )


def test_frozen_aliases_map_and_unmappable_primary_is_reviewed(tmp_path):
    p = tmp_path / "t.json"
    p.write_text(
        json.dumps(
            {
                "version": "v9",
                "sectors": [
                    {
                        "name": "Nature & ecology",
                        "aliases": ["Ecology, nature recovery & biodiversity"],
                    },
                    "Water & flood",
                ],
            }
        ),
        encoding="utf-8",
    )
    tax = jc.load_taxonomy(p)
    job = {
        "title": "Senior Ecologist",
        "description": "Habitat surveys for an ecology consultancy in Cork.",
    }
    assert jc.classify(job, "ie", tax)["sectors"] == ["Nature & ecology"]
    solar = jc.classify(
        {
            "title": "Solar PV Designer",
            "description": "Design solar PV farms, photovoltaic layouts.",
        },
        "ie",
        tax,
    )
    assert (
        solar["needs_review"] and "not in the frozen taxonomy" in solar["review_reason"]
    )


@pytest.mark.parametrize(
    "body",
    [
        "{not json",
        json.dumps({"sectors": []}),
        json.dumps({"sectors": ["A", "A"]}),
        json.dumps({"sectors": [{"aliases": ["x"]}]}),
    ],
)
def test_malformed_frozen_taxonomy_fails_loud(tmp_path, body):
    p = tmp_path / "t.json"
    p.write_text(body, encoding="utf-8")
    with pytest.raises(jc.TaxonomyError):
        jc.load_taxonomy(p)


class FailingJev:
    def ask_many(self, items):
        raise TimeoutError("jev down")


class AnsweringJev:
    def __init__(self, choice, conf):
        self.choice, self.conf = choice, conf

    def ask_many(self, items):
        return [
            {"sector": {"choice": self.choice, "confidence": self.conf}} for _ in items
        ]


def test_jev_fails_open_to_the_queue_and_is_used_only_above_the_cut(capsys):
    job = {
        "title": "Project Coordinator",
        "description": "Coordinate the team and the diary.",
    }
    down = jc.classify(job, "ie", frozen(), jev=FailingJev())
    assert down["needs_review"] and "Jev sector call failed" in capsys.readouterr().err
    low = jc.classify(job, "ie", frozen(), jev=AnsweringJev("water_flood", 0.4))
    assert low["needs_review"]
    high = jc.classify(job, "ie", frozen(), jev=AnsweringJev("water_flood", 0.9))
    assert (
        not high["needs_review"]
        and high["sectors"] == ["Water & flood"]
        and high["sector_method"] == "jev"
    )


def test_bad_site_raises():
    with pytest.raises(ValueError):
        jc.classify({"title": "x"}, "fr", frozen())


def test_scores_agree_with_assign_sectors_on_the_real_gaia_snapshot():
    snap = json.loads(
        (FX / "gaia_eval" / "gaia_snapshot_2026-11-20.json").read_text(encoding="utf-8")
    )
    for j in snap["jobs"][:40]:
        bj = jc.to_board_job(
            {"title": j["title"], "description_html": j.get("content") or ""}
        )
        name, score = jc.sector_scores(bj)[0]
        if score >= bs.PRIMARY_MIN:
            assert name == bs.assign_sectors(bj)[0], j["title"]


# ------------------------------------------------------------------ gaia_d1_sync


def gaia_args(tmp_path, *extra, feed=G / "feed_small.json"):
    return [
        "--feed",
        str(feed),
        "--taxonomy",
        str(FROZEN),
        "--as-of",
        "2026-11-20",
        *map(str, extra),
    ]


def emit(
    tmp_path, capsys, feed=G / "feed_small.json", name="g.sql", *extra
) -> tuple[int, dict, str]:
    out = tmp_path / name
    code = gds.main(gaia_args(tmp_path, "--emit-sql", out, *extra, feed=feed))
    summary = json.loads(capsys.readouterr().out)
    return code, summary, out.read_text(encoding="utf-8") if out.exists() else ""


def table(con, sql):
    return con.execute(sql).fetchall()


def test_feed_sql_is_idempotent_and_holds_review_jobs(tmp_path, capsys):
    code, s, sql = emit(tmp_path, capsys)
    assert (
        code == 0
        and s["mode"] == "dry_run"
        and s["sites"]["ie"]["held_for_review"] == 2
    )
    con = fresh_db()
    con.executescript(sql)
    first = table(con, "SELECT id, status, version, sectors_json FROM jobs ORDER BY id")
    con.executescript(sql)
    assert (
        table(con, "SELECT id, status, version, sectors_json FROM jobs ORDER BY id")
        == first
    )  # no version bump
    st = dict((r[0], r[1]) for r in first)
    assert st == {
        "ie:gaia:101": "live",
        "ie:gaia:102": "draft",
        "ie:gaia:104": "live",
        "ie:gaia:105": "draft",
        "uk:gaia:105": "live",
    }
    assert "ie:gaia:103" not in st  # on the board already: linked, not listed twice
    assert table(con, "SELECT site, feed_source_id, board_job_id FROM job_links") == [
        ("ie", "gaia:103", "ie:strat:11500001")
    ]
    rv = dict(table(con, "SELECT job_id, reason FROM job_review"))
    assert (
        set(rv) == {"ie:gaia:102", "ie:gaia:105"}
        and "possible duplicate of ie:strat:11500002" in rv["ie:gaia:105"]
    )
    assert table(
        con, "SELECT apply_mode, apply_email FROM jobs WHERE id='ie:gaia:104'"
    ) == [("email", "jobs@gaiatalent.com")]
    assert table(
        con, "SELECT workplace FROM job_facets WHERE job_id='ie:gaia:101'"
    ) == [("hybrid",)]
    assert table(con, "SELECT COUNT(*) FROM audit_log") == [(2,)]
    assert table(con, "PRAGMA foreign_key_check") == []


def test_removed_job_is_closed_not_deleted_and_staff_decisions_survive(
    tmp_path, capsys
):
    _, _, sql1 = emit(tmp_path, capsys)
    con = fresh_db()
    con.executescript(sql1)
    # staff approve 102 with another sector (as the review console does), and close 101 by hand
    con.execute(
        "UPDATE jobs SET status='live', sectors_json='[\"Water & flood\"]' WHERE id='ie:gaia:102'"
    )
    con.execute("UPDATE job_review SET status='changed' WHERE job_id='ie:gaia:102'")
    con.execute("UPDATE jobs SET status='closed' WHERE id='ie:gaia:101'")
    feed = json.loads((G / "feed_small.json").read_text(encoding="utf-8"))
    feed["jobs"] = [
        j for j in feed["jobs"] if j["source_id"] not in ("gaia:104", "gaia:103")
    ]
    p = tmp_path / "feed2.json"
    p.write_text(json.dumps(feed), encoding="utf-8")
    _, _, sql2 = emit(tmp_path, capsys, p, "g2.sql")
    con.executescript(sql2)
    st = dict(table(con, "SELECT id, status FROM jobs"))
    assert st["ie:gaia:104"] == "closed" and table(
        con, "SELECT closed_at IS NOT NULL FROM jobs WHERE id='ie:gaia:104'"
    ) == [(1,)]
    assert (
        st["ie:gaia:101"] == "closed"
    )  # a job staff closed is never reopened by the feed
    assert st["ie:gaia:102"] == "live"
    assert table(con, "SELECT sectors_json FROM jobs WHERE id='ie:gaia:102'") == [
        ('["Water & flood"]',)
    ]
    assert table(con, "SELECT status FROM job_review WHERE job_id='ie:gaia:102'") == [
        ("changed",)
    ]
    assert table(con, "SELECT COUNT(*) FROM job_links") == [
        (0,)
    ]  # 103 left the feed: its link is pruned
    assert len(st) == 5  # nothing deleted


def test_feed_never_overwrites_a_strategies_or_console_row(tmp_path, capsys):
    _, _, sql = emit(tmp_path, capsys)
    con = fresh_db()
    con.execute(
        "INSERT INTO jobs (id, site, source, source_id, title, location, description, status, created_by, created_at, updated_at)"
        " VALUES ('ie:gaia:101', 'ie', 'console', NULL, 'Staff Title', 'Cork', 'A description written by staff.', 'live', 'k', 't', 't')"
    )
    con.executescript(sql)
    assert table(con, "SELECT title, source FROM jobs WHERE id='ie:gaia:101'") == [
        ("Staff Title", "console")
    ]


def test_empty_or_all_rejected_feed_is_refused(tmp_path, capsys):
    p = tmp_path / "empty.json"
    p.write_text(json.dumps({"jobs": []}), encoding="utf-8")
    code, s, sql = emit(tmp_path, capsys, p)
    assert code == 3 and s["status"] == "gate_failed" and sql == ""
    feed = json.loads((G / "feed_small.json").read_text(encoding="utf-8"))
    for j in feed["jobs"]:
        j["description_html"] = "<p>short</p>"
        j["on_board"] = []
    p.write_text(json.dumps(feed), encoding="utf-8")
    code, s, sql = emit(tmp_path, capsys, p)
    assert code == 3 and "every feed job was rejected" in s["error"] and sql == ""


def test_record_guards_reject_with_evidence():
    tax = frozen()
    base = json.loads((G / "feed_small.json").read_text(encoding="utf-8"))["jobs"][0]
    for patch, why in (
        ({"title": "AB"}, "title length"),
        ({"expires_at": "01/01/2026"}, "closing date passed"),
        (
            {
                "apply": {"method": "url", "url": "http://x.example"},
                "url": "http://x.example",
            },
            "no usable apply",
        ),
        ({"description_html": "<p>tiny</p>"}, "description"),
    ):
        job, reason = gds.record_to_job(
            {**base, **patch}, "ie", tax, today=TODAY, require_frozen=True, dup_queue=[]
        )
        assert job is None and why in reason
    assert (
        gds.closing_iso("20261231") == "2026-12-31T23:59:59Z"
        and gds.closing_iso("31/02/2026") is None
    )


def test_live_needs_the_feature_flag_and_post_needs_a_token(
    tmp_path, capsys, monkeypatch
):
    monkeypatch.delenv("GAIA_FEED_ENABLED", raising=False)
    monkeypatch.setenv("BUILD_TOKEN", "t")
    assert (
        gds.main(
            gaia_args(
                tmp_path, "--post", "https://greenjobs.ie/api/admin/import", "--live"
            )
        )
        == 2
    )
    assert "GAIA_FEED_ENABLED" in json.loads(capsys.readouterr().out)["error"]
    monkeypatch.delenv("BUILD_TOKEN")
    assert (
        gds.main(gaia_args(tmp_path, "--post", "https://greenjobs.ie/api/admin/import"))
        == 2
    )
    assert "BUILD_TOKEN" in json.loads(capsys.readouterr().out)["error"]
    assert gds.main(gaia_args(tmp_path, "--live")) == 2  # --live without --post
    capsys.readouterr()


class FakeResp(io.BytesIO):
    status = 200

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def test_post_is_dry_run_by_default_and_errors_fail_loud(tmp_path, capsys, monkeypatch):
    monkeypatch.setenv("BUILD_TOKEN", "secret-token")
    sent = []

    def opener(req, timeout):
        sent.append(
            (req.full_url, req.headers.get("Authorization"), json.loads(req.data))
        )
        return FakeResp(json.dumps({"dry_run": True, "plan": {}}).encode())

    assert (
        gds.main(
            gaia_args(tmp_path, "--post", "https://greenjobs.ie/api/admin/import"),
            opener=opener,
        )
        == 0
    )
    out = capsys.readouterr().out
    assert "secret-token" not in out
    assert {b["site"] for _, _, b in sent} == {"ie", "uk"} and all(
        b["dry_run"] is True for _, _, b in sent
    )
    assert all(a == "Bearer secret-token" for _, a, _ in sent) and all(
        "rejects" not in b for _, _, b in sent
    )

    def failing(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 409, "mass close", {}, None)

    assert (
        gds.main(
            gaia_args(tmp_path, "--post", "https://greenjobs.ie/api/admin/import"),
            opener=failing,
        )
        == 3
    )
    assert "409" in json.loads(capsys.readouterr().out)["error"]
    monkeypatch.setenv("GAIA_FEED_ENABLED", "1")
    sent.clear()
    assert (
        gds.main(
            gaia_args(
                tmp_path, "--post", "https://greenjobs.ie/api/admin/import", "--live"
            ),
            opener=opener,
        )
        == 0
    )
    assert all(b["dry_run"] is False for _, _, b in sent)
    capsys.readouterr()


def test_output_inside_repo_is_refused(tmp_path, capsys):
    assert gds.main(gaia_args(tmp_path, "--emit-sql", REPO / "gaia.sql")) == 2
    capsys.readouterr()
    assert not (REPO / "gaia.sql").exists()


def test_once_offline_real_snapshot_end_to_end(tmp_path, capsys):
    ev = FX / "gaia_eval"
    out = tmp_path / "real.sql"
    argv = [
        "--once",
        "--offline",
        str(ev / "gaia_snapshot_2026-11-20.json"),
        "--board-jobs",
        str(ev / "board_snapshot_2026-11-20.json"),
        "--work-dir",
        str(tmp_path / "w"),
        "--no-jev",
        "--as-of",
        "2026-11-20",
        "--emit-sql",
        str(out),
        "--taxonomy",
        str(tmp_path / "none.json"),
    ]
    assert gds.main(argv) == 0
    s = json.loads(capsys.readouterr().out)
    ie = s["sites"]["ie"]
    assert (
        s["upstream"]["jobs_in_feed"] == 83 and ie["links"] >= 70
    )  # most Gaia jobs are already on greenjobs.ie
    assert (
        ie["live"] == 0 and ie["held_for_review"] == ie["jobs"]
    )  # unfrozen taxonomy: every sector reviewed
    con = fresh_db()
    con.executescript(out.read_text(encoding="utf-8"))
    before = table(con, "SELECT COUNT(*), SUM(version) FROM jobs")
    con.executescript(out.read_text(encoding="utf-8"))
    assert table(con, "SELECT COUNT(*), SUM(version) FROM jobs") == before


# ------------------------------------------------------------------ strategies_import (2026-11-20 rules)


def imp(capsys, *argv):
    code = si.main([str(a) for a in argv])
    return code, json.loads(capsys.readouterr().out)


def base(report, *csvs, site="ie"):
    a = ["--site", site, "--report", report, "--as-of", "2026-11-07"]
    for c in csvs:
        a += ["--csv", c]
    return a


@pytest.mark.parametrize(
    "report,extra",
    [
        ("candidates", []),
        ("profiles", ["--candidates-csv", ST / "candidates_batch1.csv"]),
        ("applications", ["--jobs-csv", ST / "jobs.csv"]),
    ],
)
def test_personal_data_is_off_by_default(capsys, tmp_path, report, extra):
    out = tmp_path / "p.sql"
    code, d = imp(
        capsys,
        *base(
            report,
            (
                ST / f"{report}.csv"
                if report != "candidates"
                else ST / "candidates_batch1.csv"
            ),
        ),
        *extra,
        "--emit-sql",
        out,
    )
    assert code == 2 and "off by default" in d["error"] and not out.exists()
    code, d = imp(
        capsys, *base("candidates", ST / "candidates_batch1.csv")
    )  # dry-run validation still works
    assert code == 0 and d["candidate_import"] == "off: raw archive only"


def write_cfg(tmp_path, **kw) -> Path:
    p = tmp_path / "cfg.json"
    p.write_text(
        json.dumps(
            {
                "enabled": True,
                "reports": ["candidates", "profiles", "applications"],
                **kw,
            }
        ),
        encoding="utf-8",
    )
    return p


@pytest.mark.parametrize(
    "cfg",
    [
        {"enabled": False, "reports": ["candidates"]},
        {"enabled": True, "reports": ["jobs"]},
        {"enabled": True, "reports": ["candidates"], "fields": ["password"]},
        {"enabled": True, "reports": ["candidates"], "surprise": 1},
        {"enabled": True, "reports": ["candidates"], "active_since": "last year"},
    ],
)
def test_bad_candidate_config_is_refused(capsys, tmp_path, cfg):
    p = tmp_path / "c.json"
    p.write_text(json.dumps(cfg), encoding="utf-8")
    code, d = imp(
        capsys,
        *base("candidates", ST / "candidates_batch1.csv"),
        "--candidate-config",
        p,
    )
    assert code == 2


def test_config_minimises_fields_and_imports_consented_only(capsys, tmp_path):
    out = tmp_path / "c.sql"
    code, d = imp(
        capsys,
        *base("candidates", ST / "candidates_batch1.csv"),
        "--candidate-config",
        write_cfg(tmp_path),
        "--emit-sql",
        out,
        "--allow-low-yield",
    )
    assert code == 0 and d["candidate_import"]["fields"] == sorted(
        si.DEFAULT_CANDIDATE_FIELDS
    )
    con = fresh_db()
    con.executescript(out.read_text(encoding="utf-8"))
    rows = table(
        con,
        "SELECT source_id, first_name, phone, location FROM candidates ORDER BY source_id",
    )
    assert [r[0] for r in rows] == ["1001", "1010"]  # Marketing yes only
    assert all(
        r[2] is None and r[3] is None for r in rows
    )  # no phone, no home town unless the config asks
    assert d["files"][0]["excluded"].get("candidate_marketing_0", 0) >= 10


def test_config_date_range_and_categories(capsys, tmp_path):
    out = tmp_path / "c.sql"
    cfg = write_cfg(tmp_path, active_since="2026-11-01")
    code, d = imp(
        capsys,
        *base("candidates", ST / "candidates_batch1.csv"),
        "--candidate-config",
        cfg,
        "--emit-sql",
        out,
        "--allow-low-yield",
    )
    assert (
        code == 0 and "config_inactive_before_active_since" in d["files"][0]["excluded"]
    )
    cfg = write_cfg(tmp_path, categories=["Solar"])
    code, d = imp(
        capsys,
        *base("candidates", ST / "candidates_batch1.csv"),
        "--candidate-config",
        cfg,
        "--emit-sql",
        out,
    )
    assert code == 2 and "--profiles-csv" in d["error"]
    code, d = imp(
        capsys,
        *base("candidates", ST / "candidates_batch1.csv"),
        "--candidate-config",
        cfg,
        "--emit-sql",
        out,
        "--profiles-csv",
        ST / "profiles.csv",
        "--allow-low-yield",
    )
    assert code == 0
    con = fresh_db()
    con.executescript(out.read_text(encoding="utf-8"))
    assert table(con, "SELECT source_id FROM candidates") == [
        ("1001",)
    ]  # 1010 has no Solar profile
    code, d = imp(
        capsys, *base("profiles", ST / "profiles.csv"), "--candidate-config", cfg
    )
    assert code == 2 and "--candidates-csv" in d["error"]


def test_jobs_live_only_and_classified(capsys, tmp_path):
    out = tmp_path / "j.sql"
    code, d = imp(capsys, *base("jobs", ST / "jobs.csv"), "--emit-sql", out)
    assert code == 0 and d["closed_jobs_not_emitted"] >= 1
    sql = out.read_text(encoding="utf-8")
    assert "'7002'" not in sql  # closed on 01/09/2026: archive only
    con = fresh_db()
    con.executescript(sql)
    con.executescript(sql)
    jobs = dict(table(con, "SELECT source_id, sectors_json FROM jobs"))
    assert set(jobs) == {"7001", "7004", "7005", "7007"}  # 7002, 7003 closed; 7006 rejected (short)
    assert (
        json.loads(jobs["7001"])[0] == "Solar energy"
    )  # classified into the board vocabulary
    assert table(con, "SELECT COUNT(*) FROM job_facets") == [(len(jobs),)]
    held = table(con, "SELECT hold FROM job_review")
    assert all(
        h == (0,) for h in held
    )  # a live Strategies job stays live while its sector is reviewed
    assert set(r[0] for r in table(con, "SELECT status FROM jobs")) == {"live"}
    code, d = imp(
        capsys, *base("candidates", ST / "candidates_batch1.csv"), "--include-closed"
    )
    assert code == 2


def test_alerts_honour_marketing_and_consent():
    assert si.consent_verdict(1, None) is None and si.consent_verdict(None, 1) is None
    assert si.consent_verdict(0, 1) == "candidate_consent_0"
    assert si.consent_verdict(1, 0) == "candidate_marketing_0"
    assert si.consent_verdict(None, None) == "candidate_no_affirmative_consent"


def test_alert_with_marketing_0_is_excluded(capsys, tmp_path):
    reg = tmp_path / "reg.csv"
    with reg.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["CandidatePK", "email", "LastLoggedIn", "Marketing", "Consent"])
        w.writerow(["1", "a@example.com", "01/11/2026", "0", ""])
        w.writerow(["2", "b@example.com", "01/11/2026", "", ""])
        w.writerow(["3", "c@example.com", "01/11/2026", "1", ""])
    al = tmp_path / "alerts.csv"
    with al.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["CandidatePK", "Email", "Keywords"])
        for i, e in (
            ("1", "a@example.com"),
            ("2", "b@example.com"),
            ("3", "c@example.com"),
        ):
            w.writerow([i, e, "wind"])
    code, d = imp(
        capsys, *base("alerts", al), "--candidates-csv", reg, "--allow-low-yield"
    )
    assert code == 0 and d["files"][0]["excluded"] == {
        "candidate_marketing_0": 1,
        "candidate_no_affirmative_consent": 1,
    }
    assert d["totals"]["rows_kept"] == 1
