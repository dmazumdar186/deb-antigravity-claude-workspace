"""End-to-end pipeline test for mobile_apps scripts.

Codifies the smoke test from the plan:
  bootstrap -> canary -> tester-gate -> mutate health_url -> canary -> remove.
All operations run against a tmp registry + tmp mobile-apps base, no real APIs.
"""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOBILE_APPS_DIR = PROJECT_ROOT / "execution" / "mobile_apps"


def _run(args, env=None):
    return subprocess.run(
        [sys.executable] + [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or os.environ.copy(),
    )


def _wrapper(target_script: str, registry: Path, base: Path | None = None,
             template: Path | None = None) -> str:
    reg_str = str(registry).replace("\\", "/")
    parts = [
        "import sys",
        "from pathlib import Path",
        f"sys.path.insert(0, r'{MOBILE_APPS_DIR}')",
        f"sys.path.insert(0, r'{PROJECT_ROOT}')",
        f"import {target_script} as M",
        f"M.REGISTRY_PATH = Path(r'{reg_str}')",
    ]
    if base is not None:
        parts.append(f"M.MOBILE_APPS_BASE = Path(r'{base}')")
    if template is not None:
        parts.append(f"M.TEMPLATE_DIR = Path(r'{template}')")
    parts += [
        f"sys.argv[0] = r'{target_script}'",
        "sys.exit(M.main())",
    ]
    return "\n".join(parts)


@pytest.fixture
def env(tmp_path):
    base = tmp_path / "mobile-apps"
    base.mkdir()
    template = base / "_template"
    template.mkdir()
    (template / "package.json").write_text(
        '{"name": "{{APP_SLUG}}"}\n', encoding="utf-8"
    )
    (template / "README.md").write_text("# {{APP_SLUG}}\n", encoding="utf-8")

    reg = tmp_path / "registry.json"
    reg.write_text('{"schema_version": 1, "apps": []}\n', encoding="utf-8")

    return {"reg": reg, "base": base, "tmpl": template, "tmp": tmp_path}


def test_full_pipeline(env):
    tmp = env["tmp"]

    # ---- Step 1: bootstrap smoke-e2e-app ----
    bs_wrap = tmp / "bs.py"
    bs_wrap.write_text(
        _wrapper("bootstrap_mobile_app", env["reg"],
                 base=env["base"], template=env["tmpl"]),
        encoding="utf-8",
    )
    rc = _run([bs_wrap, "smoke-e2e-app"])
    assert rc.returncode == 0, f"bootstrap failed: {rc.stderr}\n{rc.stdout}"

    created = env["base"] / "smoke-e2e-app"
    assert created.exists()
    reg = json.loads(env["reg"].read_text(encoding="utf-8"))
    assert any(a["slug"] == "smoke-e2e-app" for a in reg["apps"])

    # ---- Step 2: canary -> missing-health-url ----
    can_wrap = tmp / "can.py"
    can_wrap.write_text(_wrapper("mobile_app_canary", env["reg"]), encoding="utf-8")
    rc = _run([can_wrap, "--dry-run"])
    assert rc.returncode == 0
    idx = rc.stdout.find("{")
    summary = json.loads(rc.stdout[idx:])
    statuses = {r["slug"]: r["status"] for r in summary["results"]}
    assert statuses["smoke-e2e-app"] == "missing-health-url"

    # ---- Step 3: tester-gate -> gate-not-started ----
    gate_wrap = tmp / "gate.py"
    gate_wrap.write_text(
        _wrapper("play_console_tester_gate", env["reg"]), encoding="utf-8"
    )
    rc = _run([gate_wrap, "--app", "smoke-e2e-app"])
    assert rc.returncode == 0
    assert "gate-not-started" in rc.stdout

    # ---- Step 4: mutate registry to add a (fake) health_url ----
    reg = json.loads(env["reg"].read_text(encoding="utf-8"))
    for app in reg["apps"]:
        if app["slug"] == "smoke-e2e-app":
            app["health_url"] = "http://127.0.0.1:1/health"  # unreachable on purpose
    env["reg"].write_text(json.dumps(reg, indent=2), encoding="utf-8")

    # ---- Step 5: canary (real ping path) -> red (connection refused) ----
    # Use a tiny timeout so the test doesn't hang.
    rc = _run([can_wrap, "--timeout", "2", "--max-workers", "2"])
    # Exit code 1 (red) is expected; exit code 0 only if it somehow connected.
    assert rc.returncode in (0, 1)
    idx = rc.stdout.find("{")
    summary = json.loads(rc.stdout[idx:])
    statuses = {r["slug"]: r["status"] for r in summary["results"]}
    assert statuses["smoke-e2e-app"] in ("red", "green"), \
        f"unexpected status: {statuses}"
    # Verify the ping was actually attempted (no "missing-health-url" anymore)
    assert statuses["smoke-e2e-app"] != "missing-health-url"

    # ---- Step 6: remove ----
    rc = _run([bs_wrap, "--remove", "smoke-e2e-app", "--force-remove"])
    assert rc.returncode == 0, f"remove: {rc.stderr}"
    assert not created.exists()
    reg = json.loads(env["reg"].read_text(encoding="utf-8"))
    assert not any(a["slug"] == "smoke-e2e-app" for a in reg["apps"])
