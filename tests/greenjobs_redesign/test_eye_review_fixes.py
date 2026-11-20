"""pytest: the 2026-11-20 staging eye review fixes (EYE_REVIEW_2026-11-20.md), Python side. Each guard is shown to fire.

description: one live rule (build_site.is_live == Worker isLive); the staging seed (staging_seed.py): staging-only,
  current Gaia jobs + September jobs re-based and flagged [Test data], real posted dates, closing dates kept,
  sterling kept, idempotent and byte-identical, its safety gates refuse bad rows; build_site refuses a test-data
  dataset in a production build; old-platform URLs (*.asp, strategies hosts) never become a link and the validator
  fails a page that carries one; dashboard tile notes are one text on both sides (build and dashboard.js).
inputs: none (offline; node for the JS parity checks)
outputs: pass/fail
Run: python3 -m pytest -q tests/greenjobs_redesign/test_eye_review_fixes.py
"""

from __future__ import annotations

import json
import sqlite3
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
CODE = REPO / "execution" / "gtm_client_workflows" / "greenjobs_redesign"
SRC = REPO / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
D1 = REPO / "deliverables" / "greenjobs_migration_2026-11-06" / "build" / "d1"
GAIA_FIXTURE = (
    REPO / "tests" / "greenjobs_redesign" / "fixtures" / "gaia_d1" / "feed_small.json"
)
sys.path.insert(0, str(CODE))
import build_site as bs  # noqa: E402
import staging_seed as ss  # noqa: E402
import validate_site as vs  # noqa: E402

SEED = date(2026, 11, 20)


def node(js: str, payload) -> object:
    out = subprocess.run(
        ["node", "--input-type=module", "-e", js],
        input=json.dumps(payload),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=True,
        cwd=REPO,
    )
    return json.loads(out.stdout)


@pytest.fixture(scope="module")
def seeded(tmp_path_factory):
    out = REPO / ".tmp" / "test_staging_seed_py"
    m = ss.prepare("staging", SEED, out, SRC / "data", GAIA_FIXTURE)
    return out, m


# ── 1. one live rule ─────────────────────────────────────────────────────────

CASES = [
    ({"status": "live", "closing": "2026-11-19"}, False),
    ({"status": "live", "closing": "2026-11-20"}, True),
    ({"status": "live", "closing": ""}, True),
    ({"status": "closed", "closing": "2026-12-31"}, False),
    ({"status": "draft", "closing": ""}, False),
    ({"closing": "2026-11-21"}, True),
]


def test_is_live_python_equals_worker_rule():
    today = date(2026, 11, 20)
    py = [bs.is_live(j, today) for j, _ in CASES]
    assert py == [want for _, want in CASES]
    js = node(
        "import {isLive} from './execution/gtm_client_workflows/greenjobs_redesign/platform_worker/src/live.js';"
        "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>console.log(JSON.stringify(JSON.parse(d).map(j=>isLive({status:'live',...j},'2026-11-20')))));",
        [j for j, _ in CASES],
    )
    assert js == py


def test_normalise_drops_closed_and_non_live_rows():
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    jobs = raw["jobs"][:3]
    raw2 = {
        **raw,
        "jobs": [
            {**jobs[0], "closing": "19/11/2026"},
            {**jobs[1], "closing": "20/11/2026"},
            {**jobs[2], "closing": "", "status": "closed"},
        ],
    }
    data = bs.normalise(raw2, "ie", SRC, SRC / "assets" / "logos", SEED)
    assert [j["id"] for j in data["jobs"]] == [jobs[1]["id"]]


# ── 2/3. the staging seed ────────────────────────────────────────────────────


def test_seed_refuses_production_and_paths_outside_build_areas(tmp_path):
    with pytest.raises(ss.SeedError, match="staging-only"):
        ss.prepare("production", SEED, REPO / ".tmp" / "x")
    with pytest.raises(ss.SeedError, match="staging-only"):
        ss.seed_sql("production", {}, "2026-11-20T00:00:00Z")
    with pytest.raises(ss.SeedError, match="must be under"):
        ss.prepare("staging", SEED, tmp_path / "out")


def test_seed_dataset_flags_test_data_and_rebases_dates(seeded):
    out, m = seeded
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    ds = json.loads((out / "data" / "ie.json").read_text(encoding="utf-8"))
    assert ds["test_data"] is True and ds["fetched"] == SEED.isoformat()
    delta = SEED - date(2026, 9, 22)
    by_id = {j["id"]: j for j in raw["jobs"]}
    test_rows = [j for j in ds["jobs"] if j["seed_source"] == "test"]
    gaia_rows = [j for j in ds["jobs"] if j["seed_source"] == "gaia"]
    assert test_rows and all(j["title"].startswith(ss.TEST_PREFIX) for j in test_rows)
    assert gaia_rows and not any(
        j["title"].startswith(ss.TEST_PREFIX) for j in gaia_rows
    )
    for j in test_rows:
        src = by_id[j["id"]]
        assert (
            j["posted"]
            == (date.fromisoformat(bs.parse_date(src["posted"])) + delta).isoformat()
        )
        if src.get("closing"):
            assert (
                j["closing"]
                == (
                    date.fromisoformat(bs.parse_date(src["closing"])) + delta
                ).isoformat()
            )
    closed_on_snapshot = [
        j["id"]
        for j in raw["jobs"]
        if bs.parse_date(j.get("closing"))
        and bs.parse_date(j["closing"]) < "2026-09-22"
    ]
    assert not set(closed_on_snapshot) & {j["id"] for j in test_rows}
    # Gaia: only 'ready' records on this board, real posted date, the job's own (non-old) apply link
    feed = json.loads(GAIA_FIXTURE.read_text(encoding="utf-8"))
    ready = {
        f"gaia-{r['source_id'].split(':')[1]}"
        for r in feed["jobs"]
        if r["status"] == "ready" and "ie" in r["boards"]
    }
    assert {j["id"] for j in gaia_rows} == ready
    assert all(j["posted"] for j in gaia_rows)


def test_seed_sql_idempotent_byte_identical_and_closes_stale_rows(seeded):
    out, m = seeded
    sql = (out / "seed.sql").read_text(encoding="utf-8")
    m2 = ss.prepare("staging", SEED, out, SRC / "data", GAIA_FIXTURE)
    assert (out / "seed.sql").read_text(encoding="utf-8") == sql and m2["counts"] == m[
        "counts"
    ]
    c = sqlite3.connect(":memory:")
    c.executescript((D1 / "schema.sql").read_text(encoding="utf-8"))
    for mig in sorted((D1 / "migrations").glob("*.sql")):
        c.executescript(mig.read_text(encoding="utf-8"))
    c.execute(
        "INSERT INTO jobs (id, site, source, source_id, title, location, description, status, posted_at, created_by, created_at, updated_at) "
        "VALUES ('ie:strat:1', 'ie', 'feed', 'seed:1', 'Old September Row', 'Cork', 'An old seeded row from the 22 Sep seed.', 'live', "
        "'2026-11-20T00:00:00Z', 'staging-seed', 't', 't')"
    )
    c.execute(
        "INSERT INTO jobs (id, site, source, source_id, title, location, description, status, created_by, created_at, updated_at) "
        "VALUES ('ie:strat:2', 'ie', 'strategies', '2', 'Real Import Row', 'Cork', 'A real import row is never touched.', 'live', 'import', 't', 't')"
    )
    c.executescript(sql)
    snap = c.execute("SELECT * FROM jobs ORDER BY id").fetchall()
    c.executescript(sql)
    assert c.execute("SELECT * FROM jobs ORDER BY id").fetchall() == snap
    st = dict(
        c.execute(
            "SELECT id, status FROM jobs WHERE id IN ('ie:strat:1', 'ie:strat:2')"
        ).fetchall()
    )
    assert st == {"ie:strat:1": "closed", "ie:strat:2": "live"}
    n = c.execute(
        "SELECT COUNT(*) FROM jobs WHERE created_by LIKE 'staging-seed%' AND status = 'live'"
    ).fetchone()[0]
    assert n == sum(v["jobs"] for v in m["counts"].values())
    # closing dates kept, posted from the source, sterling kept on IE, no apply address, no old link
    rows = c.execute(
        "SELECT site, posted_at, closing_at, currency, apply_mode, apply_email, apply_url FROM jobs WHERE created_by LIKE 'staging-seed%' AND status = 'live'"
    ).fetchall()
    assert all(r[2] is None or r[2] >= "2026-11-20" for r in rows) and any(
        r[2] for r in rows
    )
    assert len({r[1] for r in rows}) > 10
    assert any(r[0] == "ie" and r[3] == "GBP" for r in rows)
    assert all(r[5] is None for r in rows)
    assert all(r[4] == "email" or not vs.is_old_platform_url(r[6]) for r in rows)


def test_seed_safety_gates_fire():
    good = {
        "id": "ie:strat:1",
        "status": "live",
        "apply_email": None,
        "apply_mode": "email",
        "apply_url": None,
        "created_by": "staging-seed-test",
    }
    ss.assert_jobs_safe([good])
    for bad in (
        {"apply_email": "a@b.ie"},
        {"status": "draft"},
        {"apply_mode": "link", "apply_url": "https://www.greenjobs.ie/jobs/1/x.asp"},
        {"apply_mode": "link", "apply_url": "http://ats.example.com/"},
        {"created_by": "import"},
    ):
        with pytest.raises(ss.SeedError):
            ss.assert_jobs_safe([{**good, **bad}])
    for stmt in (
        "DELETE FROM jobs;",
        "UPDATE jobs SET status = 'closed' WHERE 1;",
        "INSERT INTO candidates (id) VALUES (1) ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO employers (id, contact_email) VALUES ('x', 'a@b') ON CONFLICT (id) DO NOTHING;",
        "INSERT INTO jobs (id) VALUES ('x');",
    ):
        with pytest.raises(ss.SeedError):
            ss.assert_seed_safe(stmt + "\n")
    with pytest.raises(ss.SeedError, match="Worker slug"):
        ss.d1_id("ie", "seed-abc")


def test_production_build_refuses_test_data(seeded, tmp_path):
    out, _ = seeded
    rc = bs.build(
        SRC,
        REPO / ".tmp" / "test_prod_refuse",
        editions=["ie", "uk"],
        data_dir=out / "data",
        today=SEED,
        robots_index=True,
    )
    assert rc == 2
    rc = bs.build(
        SRC,
        REPO / ".tmp" / "test_prod_refuse",
        editions=["ie", "uk"],
        data_dir=out / "data",
        today=SEED,
        analytics="production",
    )
    assert rc == 2


# ── 4. old-platform links ────────────────────────────────────────────────────


def test_old_platform_urls_from_september_data():
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    uk = json.loads((SRC / "data" / "uk.json").read_text(encoding="utf-8"))
    real = (
        [j["url"] for j in raw["jobs"][:5] + uk["jobs"][:5]]
        + [e["url"] for e in raw["employers"][:3]]
        + [raw["jobs"][0]["logo_url"]]
    )
    assert real and all(bs.is_old_platform_url(u) for u in real)
    assert all(
        bs.apply_of(j)["apply_mode"] == "email" for j in raw["jobs"]
    )  # every September row: email mode, never the .asp link
    for ok in (
        "https://greenjobs.ie/ie/jobs/11488772/",
        "https://gaiatalent.com/jobs/x",
        "https://ats.example.com/7.asp",
    ):
        assert not bs.is_old_platform_url(ok)
    ctx = bs.apply_ctx(
        {"id": "x", "url": raw["jobs"][0]["url"], "apply_mode": "legacy"},
        "greenjobs.ie",
    )
    assert ctx["apply_url"] == "#apply-form" and ".asp" not in json.dumps(
        ctx
    )  # render-time guard on a stale row
    ctx = bs.apply_ctx(
        {
            "id": "x",
            "url": "https://gaiatalent.com/j",
            "apply_mode": "link",
            "apply_url": raw["jobs"][0]["url"],
        },
        "greenjobs.ie",
    )
    assert ctx["apply_url"] == "#apply-form"
    wall = bs.client_wall(
        {
            "site": "greenjobs.ie",
            "ed": "ie",
            "fetched": "2026-09-22",
            "clients": [
                {"name": "A", "file": "a.png", "lw": 1, "lh": 1, "live": False}
            ],
        },
        "../",
    )
    assert (
        "for-employers.asp" not in wall["html"]
        and 'href="../ie/employers/index.html"' in wall["html"]
    )


def test_validator_fails_a_page_linking_into_the_old_platform(tmp_path):
    site = REPO / ".tmp" / "test_old_link_site"
    (site / "ie").mkdir(parents=True, exist_ok=True)
    (site / "ie" / "index.html").write_text(
        '<!doctype html><html lang="en"><head><title>t</title><meta name="robots" content="noindex,nofollow"></head>'
        '<body><h1>x</h1><a href="https://www.greenjobs.ie/for-employers.asp">old</a></body></html>',
        encoding="utf-8",
    )
    fails = vs.validate(site, {})
    assert any("retired Strategies platform" in f for f in fails), fails


# ── 5. dashboard: a refreshed value carries its own note ─────────────────────


def test_dashboard_notes_are_one_text_build_and_js():
    raw = json.loads((SRC / "data" / "ie.json").read_text(encoding="utf-8"))
    data = bs.normalise(raw, "ie", SRC, SRC / "assets" / "logos")
    k = bs.dashboard_kpis(data)
    py = bs.kpi_notes(k, "€")
    js = node(
        "import {createRequire} from 'node:module';const r=createRequire(import.meta.url);"
        "const D=r('./deliverables/greenjobs_redesign_2026-09-22/src/js/dashboard.js');"
        "let d='';process.stdin.on('data',c=>d+=c).on('end',()=>console.log(JSON.stringify(D.tileNotes(JSON.parse(d),'€'))));",
        k,
    )
    assert js == py
    assert f'({k["sal_n"]} of {k["live"]})' in py[3]
    js_src = (SRC / "js" / "dashboard.js").read_text(encoding="utf-8")
    assert (
        ".kpi__d" in js_src and "tileNotes(k, sym)" in js_src
    )  # draw() rewrites every note with the live value
    for t in (
        "home.html",
        "insights.html",
        "guides.html",
        "guide_salary.html",
        "landing.html",
        "_shell.html",
    ):
        assert "{{snapshot" not in (SRC / "templates" / t).read_text(
            encoding="utf-8"
        ) and "{{updated}}" not in (SRC / "templates" / t).read_text(
            encoding="utf-8"
        ), t


def test_static_list_uses_the_job_page_clock():
    js = (SRC / "js" / "jobs.js").read_text(encoding="utf-8")
    assert (
        "function liveToday(" in js
        and "jobs.filter(function (j) { return !isClosed(j); })" in js
    )
    main = (SRC / "js" / "main.js").read_text(encoding="utf-8")
    assert (
        "closeMs + 864e5 <= Date.now()" in main
    )  # the page's rule = the list's (UTC day after the closing date)


# ── 3/4. Strategies import: LiveDate is the posted date; an old .asp apply link becomes email mode ─


def test_strategies_import_posted_date_and_old_platform_apply(capsys, tmp_path):
    import csv

    import strategies_import as si

    fix = REPO / "tests" / "greenjobs_redesign" / "fixtures" / "strategies"
    rows = list(csv.reader((fix / "jobs.csv").open(encoding="utf-8")))
    hdr, r1 = rows[0], rows[1]
    col = {h: i for i, h in enumerate(hdr)}

    def row(pk, email, link, live, expiry="30/12/2026"):
        r = list(r1)
        r[col["JobPK"]], r[col["Email"]], r[col["AppLink"]] = pk, email, link
        r[col["LiveDate"]], r[col["ExpiryDate"]] = live, expiry
        return r

    old = row(
        "7101",
        "hr@client.ie",
        "https://www.greenjobs.ie/jobs/11501648/labs-designer-and-facilitator-uk-ireland.asp",
        "10/09/2026",
    )
    strat = row(
        "7102",
        "",
        "https://www-greenjobs-co-uk.cname.strategiesuk.net/apply.asp?id=7102",
        "03/10/2026",
    )
    ats = row("7103", "", "https://ats.example.com/7103", "01/10/2026")
    p = tmp_path / "jobs.csv"
    with p.open("w", newline="", encoding="utf-8") as fh:
        csv.writer(fh).writerows([hdr, old, strat, ats])
    sql_r, sql_j = tmp_path / "r.sql", tmp_path / "j.sql"
    common = ["--site", "ie", "--as-of", "2026-11-07", "--emit-sql"]
    assert (
        si.main(
            common
            + [
                str(sql_r),
                "--report",
                "recruiters",
                "--csv",
                str(fix / "recruiters.csv"),
            ]
        )
        == 0
    )
    assert si.main(common + [str(sql_j), "--report", "jobs", "--csv", str(p)]) == 0
    capsys.readouterr()
    c = sqlite3.connect(":memory:")
    c.executescript((D1 / "schema.sql").read_text(encoding="utf-8"))
    for mig in sorted((D1 / "migrations").glob("*.sql")):
        c.executescript(mig.read_text(encoding="utf-8"))
    c.executescript(sql_r.read_text(encoding="utf-8"))
    c.executescript(sql_j.read_text(encoding="utf-8"))
    got = {
        r[0]: r[1:]
        for r in c.execute(
            "SELECT source_id, apply_mode, apply_email, apply_url, substr(posted_at, 1, 10) FROM jobs"
        )
    }
    assert got["7101"] == (
        "email",
        "hr@client.ie",
        None,
        "2026-09-10",
    )  # own Email; LiveDate, never the import day
    assert got["7102"] == (
        "email",
        None,
        None,
        "2026-10-03",
    )  # no Email: the site default inbox
    assert got["7103"][:3] == ("link", None, "https://ats.example.com/7103")
    assert all(v[3] != "2026-11-07" for v in got.values())
