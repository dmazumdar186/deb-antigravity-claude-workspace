"""Offline tests: compat_check, audit_summary, patch_state and the monthly report's patches section."""

import importlib.util
import json
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
G = ROOT / "execution/gtm_client_workflows/greenjobs_redesign"
sys.path.insert(0, str(G / "deploy"))
sys.path.insert(0, str(G / "ops"))
import audit_summary as A  # noqa: E402
import compat_check as CC  # noqa: E402
import patch_state as PS  # noqa: E402

spec = importlib.util.spec_from_file_location(
    "monthly_report_p", G / "ops/monthly_report.py"
)
MR = importlib.util.module_from_spec(spec)
spec.loader.exec_module(MR)

TOML = 'compatibility_date = "2026-09-01"\ncompatibility_flags = ["nodejs_compat"]\n[env.staging]\ncompatibility_flags = ["x_flag"]\n'


def test_compat_fresh_and_stale():
    r = CC.check(TOML, date(2026, 11, 20))
    assert (
        r["age_days"] == 80
        and not r["stale"]
        and r["flags_to_review"] == ["nodejs_compat", "x_flag"]
    )
    assert CC.check(TOML, date(2026, 12, 1))["stale"]


def test_compat_cli_exit_codes_and_json(tmp_path):
    t = tmp_path / "w.toml"
    t.write_text(TOML)
    out = tmp_path / "p.json"
    assert (
        CC.main(["--toml", str(t), "--today", "2026-11-20", "--write-json", str(out)])
        == 0
    )
    assert (
        CC.main(["--toml", str(t), "--today", "2027-01-01", "--write-json", str(out)])
        == 1
    )
    assert json.loads(out.read_text())["compat"]["stale"] is True
    t.write_text("nothing = 1")
    assert CC.main(["--toml", str(t)]) == 2
    assert CC.main(["--toml", str(tmp_path / "missing.toml")]) == 2


def test_real_wrangler_toml_parses():
    assert CC.check(
        (G / "platform_worker/wrangler.toml").read_text(), date(2026, 11, 20)
    )["compatibility_date"]


def _w(tmp, name, obj):
    p = tmp / name
    p.write_text(json.dumps(obj) if not isinstance(obj, str) else obj)
    return p


def test_audit_clean_and_findings(tmp_path):
    npm = _w(tmp_path, "n.json", {"vulnerabilities": {"a": {"severity": "low"}}})
    pip = _w(
        tmp_path,
        "p.json",
        {"dependencies": [{"name": "x", "version": "1", "vulns": []}]},
    )
    assert A.main(["--npm", str(npm), "--pip", str(pip)]) == 0
    npm = _w(
        tmp_path,
        "n2.json",
        {"vulnerabilities": {"a": {"severity": "high"}, "b": {"severity": "critical"}}},
    )
    pip = _w(
        tmp_path,
        "p2.json",
        {"dependencies": [{"name": "x", "version": "1", "vulns": [{"id": "PYSEC-1"}]}]},
    )
    out = tmp_path / "o.json"
    assert A.main(["--npm", str(npm), "--pip", str(pip), "--write-json", str(out)]) == 1
    a = json.loads(out.read_text())["audit"]
    assert a["npm_high_critical"] == 2 and a["pip_advisories"] == 1


def test_audit_missing_or_garbage_is_not_measured_and_fails(tmp_path):
    out = tmp_path / "o.json"
    bad = _w(tmp_path, "bad.json", "not json")
    assert (
        A.main(
            [
                "--npm",
                str(bad),
                "--pip",
                str(tmp_path / "none"),
                "--write-json",
                str(out),
            ]
        )
        == 1
    )
    a = json.loads(out.read_text())["audit"]
    assert a["npm_high_critical"] is None and a["pip_advisories"] is None


def test_patch_state_merges_idempotently(tmp_path):
    p = tmp_path / "i" / "patches.json"
    PS.merge_write(p, "audit", {"a": 1})
    PS.merge_write(p, "compat", {"b": 2})
    PS.merge_write(p, "audit", {"a": 1})
    assert json.loads(p.read_text()) == {"audit": {"a": 1}, "compat": {"b": 2}}
    p.write_text("{broken")
    assert PS.merge_write(p, "audit", {"a": 3}) == {"audit": {"a": 3}}


def test_report_lines_never_invent_numbers():
    assert all("not measured yet" in x for x in MR.patch_lines(None))
    assert all(
        "not measured yet" in x
        for x in MR.patch_lines(
            {
                "audit": {"at": "d", "npm_high_critical": None, "pip_advisories": 0},
                "compat": {"age_days": None},
            }
        )
    )
    ok = MR.patch_lines(
        {
            "audit": {"at": "2026-11-16", "npm_high_critical": 0, "pip_advisories": 0},
            "compat": {"at": "2026-11-16", "age_days": 10, "stale": False},
        }
    )
    assert "no known serious issues" in ok[0] and "up to date" in ok[1]
    bad = MR.patch_lines(
        {
            "audit": {"at": "d", "npm_high_critical": 1, "pip_advisories": 2},
            "compat": {"at": "d", "age_days": 99, "stale": True},
        }
    )
    assert "3 known" in bad[0] and "due for a routine update" in bad[1]
