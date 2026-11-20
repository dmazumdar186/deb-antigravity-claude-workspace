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
    rel, _ = mk(cfg, "staging", tmp_path)
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


def test_seed_is_public_only_idempotent_and_valid(cfg):
    srcs = {k: ROOT / v for k, v in cfg["seed_sources"].items()}
    sql, n = release.build_seed_sql("staging", srcs, "2026-11-20T00:00:00Z")
    sql2, _ = release.build_seed_sql("staging", srcs, "2026-11-20T00:00:00Z")
    assert sql == sql2 and n > 50
    assert "apply_email, apply_url" in sql and "contact_email" not in sql
    c = sqlite3.connect(":memory:")
    c.executescript((ROOT / cfg["schema"]).read_text(encoding="utf-8"))
    c.executescript(sql)
    c.executescript(sql)
    assert c.execute("SELECT count(*) FROM jobs").fetchone()[0] == n
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
    assert "deploy_cloudflare.sh" in out and "greenjobs-staging-uk" in out
    assert "tok-test" not in out


def test_stage_execute_records_versions(cfg, tmp_path, no_toml_placeholders):
    rel, fake = mk(resolved(cfg), "staging", tmp_path)
    rec = rel.stage()
    assert rec["status"] == "deployed" and rec["worker_version_id"] == V_NEW
    assert rec["pages_deployments"] == {
        "ie": "dep-greenjobs-staging-ie-latest",
        "uk": "dep-greenjobs-staging-uk-latest",
    }
    latest = sorted(p.name for p in (ROOT / "deliverables/greenjobs_migration_2026-11-06/build/d1/migrations").glob("*.sql"))[-1]
    assert rec["d1_migration_level"] == latest == "0004_job_alerts_newsletter.sql"
    order = [" ".join(c) for c in fake.calls]
    assert order.index(next(c for c in order if "schema.sql" in c)) < order.index(
        next(c for c in order if "migrations apply" in c)
    )
    assert any("seed_staging.sql" in c for c in order)
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
    assert fake.calls[-1][3:6] == [
        "d1",
        "migrations",
        "apply",
    ], "nothing runs after the failed step"
    assert not any(
        c[3:4] == ["deploy"] or "deploy_cloudflare.sh" in " ".join(c)
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
        "--env" in c and "production" in c for c in fake.calls if "wrangler@4" in c
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
    assert any(c[3:5] == ["rollback", V_OLD] for c in fake.calls)
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
