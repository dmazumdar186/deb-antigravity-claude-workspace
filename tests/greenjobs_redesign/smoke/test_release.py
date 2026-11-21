"""Offline tests for the GreenJobs release pipeline (deploy/release.py): config, gates, ledger, rollback.

Run: python3 -m pytest tests/greenjobs_redesign/smoke -q
No network, no Cloudflare: commands go to a fake runner, API calls to a fake.
"""

from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(
    0, str(ROOT / "execution/gtm_client_workflows/greenjobs_redesign/deploy")
)
import release

SHA = "0123456789abcdef0123456789abcdef01234567"
V_NEW = "11111111-2222-4333-8444-555555555555"
V_OLD = "99999999-8888-4777-8666-555555555555"


@pytest.fixture()
def cfg():
    return release.load_config()


class FakeCF:
    """Records every command; answers wrangler / API calls with canned output."""

    def __init__(
        self,
        pending="0001_apply_mode_consent_alerts.sql",
        fail_on=None,
        backup_ok=True,
        workdir=None,
    ):
        self.calls: list[list[str]] = []
        self.api_calls: list[tuple[str, str]] = []
        self.gets: list[str] = []
        self.stats_status = 200
        self.pending, self.fail_on, self.backup_ok, self.workdir = (
            pending,
            fail_on,
            backup_ok,
            workdir,
        )

    def runner(self, argv, env):
        self.calls.append(argv)
        line = " ".join(argv)
        assert (
            "CLOUDFLARE_API_TOKEN" in env and env["CLOUDFLARE_API_TOKEN"] == "tok-test"
        )
        if "gaia_feed_sync.py" in line and not (self.fail_on and self.fail_on in line):
            # stand-in for gaia_feed_sync.py: a one-job feed.json (eye r3: release.fetch_gaia_feed checks it)
            out = Path(argv[argv.index("--out") + 1])
            out = out if out.is_absolute() else Path(release.ROOT) / out
            out.mkdir(parents=True, exist_ok=True)
            (out / "feed.json").write_text(json.dumps({"generated": "2026-11-21T06:00:00Z", "jobs": [{"wp_id": 1}]}), encoding="utf-8")
            return 0, "ok"
        if "staging_seed.py" in line and not (self.fail_on and self.fail_on in line):
            # stand-in for staging_seed.py: the three outputs release.seed() reads, in the real upsert form
            out = Path(argv[argv.index("--out") + 1])
            out = out if out.is_absolute() else Path(release.ROOT) / out
            (out / "data").mkdir(parents=True, exist_ok=True)
            for s in ("ie", "uk"):
                (out / "data" / f"{s}.json").write_text("{}", encoding="utf-8")
            ss = release._staging_seed_module()
            emp = ss._upsert(
                "employers",
                {"id": "ie:seed-emp-acme", "site": "ie", "name": "Acme"},
                "id",
            )
            job = ss._upsert(
                "jobs",
                {
                    "id": "ie:seed:1",
                    "site": "ie",
                    "title": "Ecologist",
                    "apply_mode": "email",
                    "apply_email": None,
                    "apply_url": None,
                    "status": "live",
                    "created_by": "staging-seed",
                },
                "id",
            )
            (out / "seed.sql").write_text(f"-- seed\n{emp}\n{job}\n", encoding="utf-8")
            seed_date = argv[argv.index("--seed-date") + 1]
            (out / "manifest.json").write_text(
                json.dumps(
                    {
                        "env": "staging",
                        "seed_date": seed_date,
                        "counts": {"ie": {"jobs": 1}},
                    }
                ),
                encoding="utf-8",
            )
            return 0, "ok"
        if self.fail_on and self.fail_on in line:
            return 1, "boom"
        if " deploy " in f" {line} " and "wrangler" in line and "pages" not in line:
            return 0, f"Uploaded greenjobs-platform\nCurrent Version ID: {V_NEW}\n"
        if "deployments status" in line:
            return 0, f"Created: 2026-11-19\nVersion(s): (100%) {V_OLD}\n"
        if "time-travel info" in line:
            return 0, json.dumps(
                {
                    "bookmark": "00000085-0000024c-00004c6d-8e61117bf38d7adb71b934ebbf891683"
                }
            )
        if "migrations list" in line:
            return 0, (
                f"Migrations to be applied:\n| {self.pending} |\n"
                if self.pending
                else "No migrations to apply!"
            )
        if "d1 export" in line:
            out = Path(release.ROOT) / argv[argv.index("--output") + 1]
            out.parent.mkdir(parents=True, exist_ok=True)
            out.write_text(
                "CREATE TABLE jobs (id TEXT);\n" if self.backup_ok else "",
                encoding="utf-8",
            )
            return 0, "exported"
        return 0, "ok"

    def http_get(self, url):
        """The deployed Worker's public /api/stats (release.fetch_board_stats); offline."""
        self.gets.append(url)
        site = url.rsplit("site=", 1)[-1]
        body = {"site": site, "live_jobs": 2, "salary": {"n_jobs": 2}, "kpis": {"live": 2}}
        return self.stats_status, json.dumps(body).encode()

    def api(self, method, path, token, account):
        assert token == "tok-test" and account == "acct-test"
        self.api_calls.append((method, path))
        if method == "GET":
            proj = path.split("/")[3]
            return {"success": True, "result": [{"id": f"dep-{proj}-latest"}]}
        return {"success": True, "result": {"id": "rolled"}}


def mk(cfg, env, tmp_path, fake=None, execute=True):
    environ = {"GREENJOBS_RELEASE_TARGET": env}
    ec = cfg["envs"][env]
    environ[ec["api_token_env"]] = "tok-test"
    environ[ec["account_id_env"]] = "acct-test"
    fake = fake or FakeCF()
    rel = release.Release(
        cfg,
        env,
        SHA,
        tmp_path / "ledger",
        execute,
        runner=fake.runner,
        api=fake.api,
        http_get=fake.http_get,
        workdir=tmp_path / "work" / env,
        environ=environ,
    )
    return rel, fake


def resolved(cfg):
    """Config with the REPLACE_ placeholders filled, as it will be once the accounts exist."""
    c = json.loads(json.dumps(cfg))
    for ec in c["envs"].values():
        for g in ("worker_urls", "board_urls"):
            ec[g] = {
                k: v.replace("REPLACE_WORKERS_SUBDOMAIN", "prodcraft")
                for k, v in ec[g].items()
            }
    return c


@pytest.fixture()
def no_toml_placeholders(monkeypatch):
    real = release.tomllib.loads

    def loads(text):
        return real(
            text.replace("REPLACE_WITH_STAGING_D1_ID", "id-s").replace(
                "REPLACE_WITH_PRODUCTION_D1_ID", "id-p"
            )
        )

    monkeypatch.setattr(release.tomllib, "loads", loads)


# ── config ───────────────────────────────────────────────────────────────────


def test_wrangler_toml_envs_match_environments_json(cfg):
    for env in cfg["envs"]:
        assert release.check_wrangler_toml(cfg, env) == [], env


def test_staging_toml_must_pin_dry_run(cfg, tmp_path):
    src = (ROOT / cfg["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    start = src.index("[env.staging.vars]")
    bad = src[:start] + src[start:].replace('DRY_RUN = "1"', 'DRY_RUN = "0"', 1)
    p = tmp_path / "wrangler.toml"
    p.write_text(bad, encoding="utf-8")
    assert any("DRY_RUN" in x for x in release.check_wrangler_toml(cfg, "staging", p))


def test_env_missing_a_top_level_var_is_reported(cfg, tmp_path):
    src = (ROOT / cfg["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    start = src.index("[env.production.vars]")
    bad = src[:start] + src[start:].replace('MAIL_DAILY_CAP = "200"\n', "", 1)
    p = tmp_path / "wrangler.toml"
    p.write_text(bad, encoding="utf-8")
    assert any(
        "MAIL_DAILY_CAP" in x for x in release.check_wrangler_toml(cfg, "production", p)
    )


def test_top_level_keys_unchanged(cfg):
    data = release.tomllib.loads(
        (ROOT / cfg["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    )
    assert data["name"] == "greenjobs-platform" and data["vars"]["DRY_RUN"] == "1"
    assert data["d1_databases"][0]["database_name"] == "greenjobs"


def test_execute_refuses_placeholders_and_missing_target(cfg, tmp_path):
    import copy

    unfilled = copy.deepcopy(cfg)  # staging's placeholders are filled (2026-11-20); production's are not
    unfilled["envs"]["staging"]["worker_urls"]["ie"] = "https://greenjobs-platform-staging.REPLACE_WORKERS_SUBDOMAIN.workers.dev"
    rel, _ = mk(unfilled, "staging", tmp_path)
    with pytest.raises(release.GateError, match="placeholders"):
        rel.stage()
    rel, _ = mk(resolved(cfg), "staging", tmp_path)
    rel.environ.pop("GREENJOBS_RELEASE_TARGET")
    with pytest.raises(release.GateError, match="GREENJOBS_RELEASE_TARGET"):
        rel.stage()


# ── SQL ──────────────────────────────────────────────────────────────────────


def test_destructive_detection():
    assert (
        release.destructive_statements(
            "CREATE TABLE IF NOT EXISTS a (x);\n-- DROP TABLE a;\n"
        )
        == []
    )
    assert release.destructive_statements("DROP TABLE jobs;")
    assert release.destructive_statements("ALTER TABLE jobs_new RENAME TO jobs;")
    assert release.destructive_statements("delete from jobs where 1;")
    real = (
        ROOT
        / "deliverables/greenjobs_migration_2026-11-06/build/d1/migrations/0001_apply_mode_consent_alerts.sql"
    ).read_text(encoding="utf-8")
    assert release.destructive_statements(real), "0001 rebuilds tables: must be flagged"


def test_pending_from_list_output():
    files = ["0001_a.sql", "0002_b.sql"]
    assert release.pending_from_list_output("No migrations to apply!", files) == []
    assert release.pending_from_list_output("| 0002_b.sql |", files) == ["0002_b.sql"]


def test_parsers():
    assert release.parse_worker_version(f"Current Version ID: {V_NEW}") == V_NEW
    assert release.parse_worker_version("nothing") is None
    assert release.parse_deployment_status(f"Version(s): (100%) {V_OLD}\n") == V_OLD
    assert release.parse_deployment_status(f"(60%) {V_OLD}\n(40%) {V_NEW}") is None
    assert (
        release.parse_time_travel_bookmark('{"bookmark": "abc-0000000000000000000000"}')
        == "abc-0000000000000000000000"
    )


def _closed_before(raw, fetched: str) -> bool:
    import re as _re

    m = _re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})", str(raw or ""))
    iso = f"{m.group(3)}-{int(m.group(2)):02d}-{int(m.group(1)):02d}" if m else str(raw or "")[:10]
    return bool(iso) and iso < fetched


def test_seed_is_public_only_idempotent_and_valid(cfg):
    srcs = {k: ROOT / v for k, v in cfg["seed_sources"].items()}
    sql, n = release.build_seed_sql("staging", srcs, "2026-11-20T00:00:00Z")
    sql2, _ = release.build_seed_sql("staging", srcs, "2026-11-20T00:00:00Z")
    assert sql == sql2 and n > 50
    assert "apply_email, apply_url" in sql and "contact_email" not in sql
    c = sqlite3.connect(":memory:")
    c.executescript((ROOT / cfg["schema"]).read_text(encoding="utf-8"))
    for m in sorted((ROOT / cfg["migrations_dir"]).glob("*.sql")):  # deploy order: schema, migrations, seed
        c.executescript(m.read_text(encoding="utf-8"))
    c.execute("PRAGMA foreign_keys = ON")
    c.executescript(sql)
    c.executescript(sql)
    assert c.execute("SELECT count(*) FROM jobs").fetchone()[0] == n
    # every seeded job has its job_facets row (classifier + taxonomy.json) and the Strategies-shaped id the
    # Worker serves at /{site}/jobs/<id>/
    assert c.execute("SELECT count(*) FROM job_facets").fetchone()[0] == n
    assert c.execute("SELECT count(*) FROM jobs WHERE id NOT GLOB '[iu][ek]:strat:[0-9]*'").fetchone()[0] == 0
    assert c.execute("SELECT count(*) FROM job_facets WHERE taxonomy_version = 1 AND set_by = 'import' AND json_array_length(sectors_json) BETWEEN 1 AND 3").fetchone()[0] == n
    assert c.execute("PRAGMA foreign_key_check").fetchall() == []
    # the static board's snapshot: adverts closed at the dataset's fetched date (dd/mm/yyyy in the data) are not seeded
    for site, src in srcs.items():
        data = json.loads(src.read_text(encoding="utf-8"))
        fetched = str(data["fetched"])[:10]
        open_ids = {f"{site}:strat:{j['id']}" for j in data["jobs"] if not _closed_before(j.get("closing"), fetched)}
        seeded = {r[0] for r in c.execute("SELECT id FROM jobs WHERE site = ?", (site,))}
        assert seeded <= open_ids and len(seeded) >= len(open_ids) - 5, site
    assert (
        c.execute("SELECT count(*) FROM jobs WHERE apply_email IS NOT NULL").fetchone()[
            0
        ]
        == 0
    )
    assert c.execute("SELECT count(*) FROM candidates").fetchone()[0] == 0


def test_seed_refuses_production_and_unsafe_sql(cfg):
    with pytest.raises(release.GateError):
        release.build_seed_sql("production", {}, "2026-11-20T00:00:00Z")
    with pytest.raises(release.GateError):
        release.assert_seed_safe("INSERT OR IGNORE INTO candidates (id) VALUES ('x');")
    with pytest.raises(release.GateError):
        release.assert_seed_safe("DELETE FROM jobs;")
    with pytest.raises(release.GateError):
        release.assert_seed_safe(
            "INSERT OR IGNORE INTO employers (id, contact_email) VALUES ('a', 'b');"
        )


# ── stage ────────────────────────────────────────────────────────────────────


def test_stage_dry_run_prints_commands_and_calls_nothing(cfg, tmp_path, capsys):
    rel, fake = mk(cfg, "staging", tmp_path, execute=False)
    rec = rel.stage()
    out = capsys.readouterr().out
    assert fake.calls == [] and fake.api_calls == []
    assert rec["status"] == "planned" and not rec["executed"]
    assert (
        "--env staging" in out
        and "d1 migrations apply greenjobs-staging --remote" in out
    )
    assert "deploy_cloudflare.sh" in out and "greenjobs-stg-uk" in out
    assert "tok-test" not in out


def test_stage_execute_records_versions(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rec = rel.stage()
    assert rec["status"] == "deployed" and rec["worker_version_id"] == V_NEW
    assert rec["pages_deployments"] == {
        "ie": "dep-greenjobs-stg-ie-latest",
        "uk": "dep-greenjobs-stg-uk-latest",
    }
    latest = sorted(p.name for p in (ROOT / "deliverables/greenjobs_migration_2026-11-06/build/d1/migrations").glob("*.sql"))[-1]
    assert rec["d1_migration_level"] == latest == "0004_job_alerts_newsletter.sql"
    order = [" ".join(c) for c in fake.calls]
    assert order.index(next(c for c in order if "schema.sql" in c)) < order.index(
        next(c for c in order if "migrations apply" in c)
    )
    assert any("staging_seed/seed.sql" in c and "d1 execute" in c for c in order)
    rows = release.read_ledger(tmp_path / "ledger")
    assert rows[-1]["event"] == "deploy" and rows[-1]["sha"] == SHA
    assert (tmp_path / "ledger" / "summary.md").read_text(encoding="utf-8").count(
        V_NEW
    ) == 1


def test_stage_refuses_production(cfg, tmp_path):
    rel, _ = mk(cfg, "production", tmp_path, execute=False)
    with pytest.raises(release.GateError):
        rel.stage()


def test_stage_failure_is_recorded_and_stops(cfg, tmp_path, no_toml_placeholders):
    fake = FakeCF(fail_on="migrations apply")
    rel, fake = mk(resolved(cfg), "staging", tmp_path, fake)
    with pytest.raises(release.StepError):
        rel.stage()
    assert fake.calls[-1][4:7] == [
        "d1",
        "migrations",
        "apply",
    ], "nothing runs after the failed step"
    assert not any(
        c[4:5] == ["deploy"] or "deploy_cloudflare.sh" in " ".join(c)
        for c in fake.calls
    )
    assert release.read_ledger(tmp_path / "ledger")[-1]["status"] == "failed"


# ── promote ─────────────────────────────────────────────────────────────────


def staging_pass(sha=SHA, status="pass", mode="full", executed=True):
    return {
        "env": "staging",
        "sha": sha,
        "executed": executed,
        "smoke": {"status": status, "mode": mode},
    }


@pytest.mark.parametrize(
    "bad",
    [
        staging_pass(sha="f" * 40),
        staging_pass(status="fail"),
        staging_pass(mode="read_only"),
        staging_pass(executed=False),
        {**staging_pass(), "env": "production"},
    ],
)
def test_verify_promotable_rejects(bad):
    with pytest.raises(release.GateError):
        release.verify_promotable(bad, SHA)


def test_promote_requires_staging_record_on_execute(
    cfg, tmp_path, no_toml_placeholders
):
    rel, fake = mk(resolved(cfg), "production", tmp_path)
    with pytest.raises(release.GateError, match="staging-record"):
        rel.promote(None, allow_destructive=True)
    assert fake.calls == []


def test_promote_backup_precedes_migrations_and_records_previous(
    cfg, tmp_path, no_toml_placeholders
):
    rel, fake = mk(resolved(cfg), "production", tmp_path)
    rec = rel.promote(staging_pass(), allow_destructive=True)
    lines = [" ".join(c) for c in fake.calls]
    i_export = next(i for i, c in enumerate(lines) if "d1 export greenjobs" in c)
    i_r2 = next(
        i for i, c in enumerate(lines) if "r2 object put greenjobs-backups/d1/" in c
    )
    i_mig = next(i for i, c in enumerate(lines) if "migrations apply" in c)
    i_deploy = next(
        i
        for i, c in enumerate(lines)
        if c.endswith("--env production") and " deploy " in c
    )
    assert i_export < i_r2 < i_mig < i_deploy
    assert rec["previous"]["worker_version_id"] == V_OLD
    assert rec["previous"]["pages_deployments"] == {
        "ie": "dep-greenjobs-ie-latest",
        "uk": "dep-greenjobs-uk-latest",
    }
    assert rec["previous"]["d1_bookmark"].startswith("00000085")
    assert rec["backup"]["verified"] and rec["destructive_migrations"] == [
        "0001_apply_mode_consent_alerts.sql"
    ]
    assert not any(
        (tmp_path / "work" / "production").glob("d1_*.sql")
    ), "local backup (PII) must be deleted"
    assert all(
        "--env" in c and "production" in c for c in fake.calls if "wrangler" in c
    )


def test_promote_refuses_destructive_without_flag(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "production", tmp_path)
    with pytest.raises(release.GateError, match="destructive"):
        rel.promote(staging_pass(), allow_destructive=False)
    assert not any("migrations apply" in " ".join(c) for c in fake.calls)
    assert any(
        "r2 object put" in " ".join(c) for c in fake.calls
    ), "backup still taken first"


def test_promote_no_pending_needs_no_flag(cfg, tmp_path, no_toml_placeholders):
    rel, _ = mk(resolved(cfg), "production", tmp_path, FakeCF(pending=""))
    assert rel.promote(staging_pass(), allow_destructive=False)["status"] == "deployed"


def test_promote_empty_backup_blocks_migration(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "production", tmp_path, FakeCF(backup_ok=False))
    with pytest.raises(release.GateError, match="backup"):
        rel.promote(staging_pass(), allow_destructive=True)
    assert not any(
        "migrations apply" in " ".join(c) or "r2 object put" in " ".join(c)
        for c in fake.calls
    )


def test_promote_failed_backup_upload_blocks_migration(
    cfg, tmp_path, no_toml_placeholders
):
    rel, fake = mk(
        resolved(cfg), "production", tmp_path, FakeCF(fail_on="r2 object put")
    )
    with pytest.raises(release.StepError):
        rel.promote(staging_pass(), allow_destructive=True)
    assert not any("migrations apply" in " ".join(c) for c in fake.calls)


# ── rollback ────────────────────────────────────────────────────────────────


def deployed_record():
    return {
        **release.new_record("production", SHA, True),
        "worker_version_id": V_NEW,
        "previous": {
            "worker_version_id": V_OLD,
            "pages_deployments": {"ie": "dep-ie-old", "uk": "dep-uk-old"},
            "d1_bookmark": "bm-1",
        },
    }


def test_rollback_restores_previous_worker_and_pages(
    cfg, tmp_path, no_toml_placeholders, capsys
):
    rel, fake = mk(resolved(cfg), "production", tmp_path)
    rec = rel.rollback(deployed_record())
    assert any(c[4:6] == ["rollback", V_OLD] for c in fake.calls)
    assert (
        "POST",
        "/pages/projects/greenjobs-ie/deployments/dep-ie-old/rollback",
    ) in fake.api_calls
    assert (
        "POST",
        "/pages/projects/greenjobs-uk/deployments/dep-uk-old/rollback",
    ) in fake.api_calls
    assert rec["rollback"]["status"] == "done" and rec["status"] == "rolled_back"
    assert (
        "time-travel restore greenjobs --bookmark bm-1"
        in rec["rollback"]["d1_manual_restore"]
    )
    assert not any(
        "time-travel restore" in " ".join(c) for c in fake.calls
    ), "D1 restore is manual only"
    assert release.read_ledger(tmp_path / "ledger")[-1]["event"] == "rollback"


def test_rollback_without_previous_is_loud(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "production", tmp_path)
    rec = deployed_record()
    rec["previous"]["worker_version_id"] = None
    with pytest.raises(release.GateError, match="rollback target missing"):
        rel.rollback(rec)
    assert fake.calls == []
    assert (
        release.read_ledger(tmp_path / "ledger")[-1]["status"] == "rollback_impossible"
    )


def test_rollback_dry_run_prints_api_call_without_token(cfg, tmp_path, capsys):
    rel, fake = mk(cfg, "production", tmp_path, execute=False)
    rel.rollback(deployed_record())
    out = capsys.readouterr().out
    assert (
        fake.calls == []
        and "$GREENJOBS_PROD_CLOUDFLARE_API_TOKEN" in out
        and "tok-test" not in out
    )
    assert f"rollback {V_OLD}" in out


def test_last_good_skips_failed_and_rolled_back(tmp_path):
    d = tmp_path / "l"
    a = {
        **release.new_record("production", "a" * 40, True),
        "smoke": {"status": "pass"},
    }
    b = {
        **release.new_record("production", "b" * 40, True),
        "smoke": {"status": "fail"},
    }
    c = {
        **release.new_record("production", "c" * 40, True),
        "smoke": {"status": "pass"},
        "rollback": {"status": "done"},
    }
    for r in (a, b, c):
        release.append_ledger(d, "deploy", r)
    assert release.last_good(release.read_ledger(d), "production")["sha"] == "a" * 40
    assert release.last_good(release.read_ledger(d), "staging") is None


def test_record_smoke_cli(tmp_path):
    d = tmp_path / "l"
    release.append_ledger(d, "deploy", release.new_record("staging", SHA, True))
    (tmp_path / "s.json").write_text(
        json.dumps(
            {
                "status": "pass",
                "mode": "full",
                "checks": [{"name": "x", "status": "pass"}],
            }
        ),
        encoding="utf-8",
    )
    assert (
        release.main(
            [
                "record-smoke",
                "--ledger-dir",
                str(d),
                "--smoke",
                str(tmp_path / "s.json"),
            ]
        )
        == 0
    )
    rec = json.loads((d / "deploy_record.json").read_text(encoding="utf-8"))
    assert rec["smoke"]["status"] == "pass"
    assert (
        release.main(
            [
                "verify-promotable",
                "--record",
                str(d / "deploy_record.json"),
                "--sha",
                SHA,
            ]
        )
        == 0
    )
    assert (
        release.main(
            [
                "verify-promotable",
                "--record",
                str(d / "deploy_record.json"),
                "--sha",
                "e" * 40,
            ]
        )
        == 3
    )


def test_scan_secrets(tmp_path):
    ok = tmp_path / "ok.py"
    ok.write_text('TOKEN = os.environ["CLOUDFLARE_API_TOKEN"]\n', encoding="utf-8")
    bad = tmp_path / "bad.sh"
    bad.write_text(
        "CLOUDFLARE_API_TOKEN=" + "k3Q9" * 8 + "\n", encoding="utf-8"
    )
    assert release.scan_secrets([ok]) == []
    assert release.scan_secrets([bad]) == [f"{bad}:1"]
    dummy = tmp_path / "dummy.mjs"
    dummy.write_text("BUILD_TOKEN: 'build-token-for-tests-only',\n", encoding="utf-8")
    assert release.scan_secrets([dummy]) == []


# ── staging UK Worker + board figures from /api/stats (2026-11-20) ───────────


def test_stage_deploys_the_uk_worker_after_the_primary(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rec = rel.stage()
    deploys = [" ".join(c) for c in fake.calls if c[4:5] == ["deploy"]]
    assert len(deploys) == 2
    assert deploys[0].endswith("--env staging") and deploys[1].endswith("--env staging-uk")
    assert all(f"RELEASE_SHA:{SHA}" in d for d in deploys)
    assert rec["extra_worker_versions"] == {"greenjobs-platform-staging-uk": V_NEW}
    # D1 schema / migrations / seed run once, against the primary env (one shared D1)
    assert sum("migrations apply" in " ".join(c) for c in fake.calls) == 1


def test_stage_builds_boards_with_live_stats_for_both_editions(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rel.stage()
    assert fake.gets == [
        "https://greenjobs-platform-staging.debanjan186.workers.dev/api/stats?site=ie",
        "https://greenjobs-platform-staging-uk.debanjan186.workers.dev/api/stats?site=uk",
    ]
    builds = [c for c in fake.calls if "build_site.py" in " ".join(c)]
    assert len(builds) == 2
    for b in builds:
        pairs = [b[i + 1] for i, a in enumerate(b) if a == "--stats-json"]
        assert [x.split("=")[0] for x in pairs] == ["ie", "uk"]
    uk_build = next(b for b in builds if b[b.index("--board-site") + 1] == "uk")
    assert uk_build[uk_build.index("--api-base") + 1] == "https://greenjobs-platform-staging-uk.debanjan186.workers.dev"
    assert json.loads((tmp_path / "work" / "staging" / "stats-uk.json").read_text(encoding="utf-8"))["site"] == "uk"


def test_stage_stops_when_stats_are_unusable(cfg, tmp_path, no_toml_placeholders):
    fake = FakeCF()
    fake.stats_status = 503
    rel, fake = mk(resolved(cfg), "staging", tmp_path, fake)
    with pytest.raises(release.StepError):
        rel.stage()
    assert not any("deploy_cloudflare.sh" in " ".join(c) for c in fake.calls)


def test_production_does_not_fetch_stats_or_deploy_extra_workers(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "production", tmp_path, execute=False)
    rel.deploy_worker()
    rel.deploy_boards()
    assert fake.gets == [] and not any("--stats-json" in l or "staging-uk" in l for l in rel.log)


@pytest.mark.parametrize(
    "mutate,needle",
    [
        (lambda t: t.replace('[env.staging-uk.triggers]\ncrons = []', '[env.staging-uk.triggers]\ncrons = ["*/10 * * * *"]'), "triggers.crons"),
        (lambda t: t.replace('HOST_SITE_MAP = \'{"greenjobs-platform-staging-uk.debanjan186.workers.dev":"uk"}\'',
                             'HOST_SITE_MAP = \'{"greenjobs-platform-staging-uk.debanjan186.workers.dev":"ie"}\''), "HOST_SITE_MAP"),
        (lambda t: t.replace('name = "greenjobs-platform-staging-uk"', 'name = "greenjobs-platform"'), "name"),
        (lambda t: t.replace("[[env.staging-uk.d1_databases]]\nbinding = \"DB\"\ndatabase_name = \"greenjobs-staging\"",
                             "[[env.staging-uk.d1_databases]]\nbinding = \"DB\"\ndatabase_name = \"greenjobs\""), "d1_databases"),
    ],
)
def test_check_config_pins_the_uk_worker(cfg, tmp_path, mutate, needle):
    src = (ROOT / cfg["worker_dir"] / "wrangler.toml").read_text(encoding="utf-8")
    bad = mutate(src)
    assert bad != src, needle
    t = tmp_path / "wrangler.toml"
    t.write_text(bad, encoding="utf-8")
    problems = release.check_wrangler_toml(cfg, "staging", t)
    assert any(needle in p and "staging-uk" in p for p in problems), problems
    assert release.check_wrangler_toml(cfg, "staging") == []
# ── staging seed via staging_seed.py (eye review 2026-11-20; STAGING_FLAGS_NOTE.md section 2) ────────────


def test_stage_seeds_from_gaia_and_staging_seed_then_builds_with_the_same_data(
    cfg, tmp_path, no_toml_placeholders
):
    fake = FakeCF()
    rel, fake = mk(resolved(cfg), "staging", tmp_path, fake)
    rel.environ["GREENJOBS_SEED_DATE"] = "2026-11-20"
    rec = rel.stage()
    order = [" ".join(c) for c in fake.calls]
    i_feed = next(i for i, c in enumerate(order) if "gaia_feed_sync.py --no-jev" in c)
    i_seed = next(
        i
        for i, c in enumerate(order)
        if "staging_seed.py --env staging --seed-date 2026-11-20" in c
    )
    i_d1 = next(
        i
        for i, c in enumerate(order)
        if "d1 execute" in c and "staging_seed/seed.sql" in c
    )
    i_build = next(i for i, c in enumerate(order) if "build_site.py" in c)
    assert i_feed < i_seed < i_d1 < i_build
    builds = [c for c in fake.calls if "build_site.py" in " ".join(c)]
    for b in builds:
        assert b[b.index("--today") + 1] == "2026-11-20"
        assert b[b.index("--data-dir") + 1].endswith("staging_seed/data")
    assert rec["seed"]["seed_date"] == "2026-11-20"
    assert not any(
        "seed_staging.sql" in c for c in order
    )  # the old INSERT OR IGNORE snapshot seed is gone


def test_stage_refuses_an_unsafe_seed_file(cfg, tmp_path, no_toml_placeholders):
    class Bad(FakeCF):
        def runner(self, argv, env):
            code, out = super().runner(argv, env)
            if "staging_seed.py" in " ".join(argv):
                f = Path(argv[argv.index("--out") + 1]) / "seed.sql"
                f.write_text("DELETE FROM jobs;\n", encoding="utf-8")
            return code, out

    rel, fake = mk(resolved(cfg), "staging", tmp_path, Bad())
    with pytest.raises(release.GateError):
        rel.stage()
    assert not any(
        "d1 execute" in " ".join(c) and "seed.sql" in " ".join(c) for c in fake.calls
    )


def test_assert_seed_safe_accepts_the_upsert_file_and_refuses_bad_rows():
    ss = release._staging_seed_module()
    ok_job = ss._upsert(
        "jobs",
        {
            "id": "ie:seed:1",
            "site": "ie",
            "apply_mode": "email",
            "apply_email": None,
            "apply_url": None,
            "status": "live",
            "created_by": "staging-seed",
        },
        "id",
    )
    close = (
        "UPDATE jobs SET status = 'closed', closed_at = 'x', updated_at = 'x' WHERE created_by IN "
        "('staging-seed', 'staging-seed-test') AND status <> 'closed' AND id NOT IN (SELECT value FROM json_each('[]'));"
    )
    release.assert_seed_safe(f"-- c\n{ok_job}\n{close}\n")
    with pytest.raises(release.GateError):  # a stored apply address
        release.assert_seed_safe(
            ok_job.replace("'email', NULL", "'email', 'a@b.ie'") + "\n"
        )
    with pytest.raises(release.GateError):  # a link into the retired platform
        release.assert_seed_safe(
            ss._upsert(
                "jobs",
                {
                    "id": "ie:seed:2",
                    "apply_mode": "link",
                    "apply_email": None,
                    "apply_url": "https://www.greenjobs.ie/jobs/1/x.asp",
                },
                "id",
            )
            + "\n"
        )
    with pytest.raises(release.GateError):  # an unscoped close
        release.assert_seed_safe("UPDATE jobs SET status = 'closed' WHERE 1;\n")
    with pytest.raises(release.GateError):  # personal data
        release.assert_seed_safe(
            ss._upsert("employers", {"id": "e", "contact_email": "x"}, "id") + "\n"
        )


def test_production_never_gets_seed_data(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "production", tmp_path, execute=False)
    rel.seed()  # seed_public_jobs is false: a no-op
    assert not any("staging_seed" in l or "gaia_feed_sync" in l for l in rel.log)
    rel.seed_data_dir, rel.seed_date = tmp_path / "data", "2026-11-20"
    with pytest.raises(release.GateError):
        rel.deploy_boards()
    assert cfg["envs"]["production"]["seed_public_jobs"] is False


# ── eye review r3: Gaia feed fallback (HTTP 522 etc.) and the edition switch origins ─────────────


def test_r3_gaia_fetch_failure_falls_back_to_the_last_good_snapshot_and_says_so(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rel.stage()  # a good fetch leaves the last good snapshot in the ledger dir
    snap = tmp_path / "ledger" / release.GAIA_LAST_GOOD
    assert json.loads(snap.read_text(encoding="utf-8"))["jobs"]
    assert rel.record["gaia_feed"]["source"] == "live"
    bad = FakeCF(fail_on="gaia_feed_sync.py")
    rel2, fake2 = mk(resolved(cfg), "staging", tmp_path, bad)
    rec = rel2.stage()
    assert rec["status"] == "deployed"
    assert rec["gaia_feed"]["source"] == "last_good_snapshot"
    assert rec["gaia_feed"]["generated"] == "2026-11-21T06:00:00Z"
    assert "exit 1" in rec["gaia_feed"]["reason"]
    assert any("staging_seed.py" in " ".join(c) for c in fake2.calls), "the seed still ran"
    assert release.read_ledger(tmp_path / "ledger")[-1]["gaia_feed"]["source"] == "last_good_snapshot"
    assert "| Gaia feed | last_good_snapshot" in (tmp_path / "ledger" / "summary.md").read_text(encoding="utf-8")


def test_r3_gaia_fetch_failure_without_a_snapshot_fails_loud(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path, FakeCF(fail_on="gaia_feed_sync.py"))
    with pytest.raises(release.StepError, match="no last good Gaia feed snapshot"):
        rel.stage()
    assert not any("staging_seed.py" in " ".join(c) for c in fake.calls)


def test_r3_board_builds_pass_each_editions_own_board_origin(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rel.stage()
    builds = [c for c in fake.calls if "build_site.py" in " ".join(c)]
    assert len(builds) == 2
    for b in builds:
        pairs = [b[i + 1] for i, a in enumerate(b) if a == "--edition-origin"]
        assert pairs == ["ie=https://greenjobs-stg-ie.pages.dev", "uk=https://greenjobs-stg-uk.pages.dev"]
