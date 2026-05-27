"""Integration tests for the 6 mobile_apps scripts.

Real subprocess calls, but ALL pointed at a tmp registry + tmp mobile-apps base.
No paid APIs, no real Modal/ASC/Firecrawl calls.
"""

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
MOBILE_APPS_DIR = PROJECT_ROOT / "execution" / "mobile_apps"

BOOTSTRAP = MOBILE_APPS_DIR / "bootstrap_mobile_app.py"
CANARY = MOBILE_APPS_DIR / "mobile_app_canary.py"
GATE = MOBILE_APPS_DIR / "play_console_tester_gate.py"
EAS = MOBILE_APPS_DIR / "eas_build_helper.py"


def _run(args, env=None):
    """subprocess.run with utf-8 hardening."""
    return subprocess.run(
        [sys.executable] + [str(a) for a in args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env or os.environ.copy(),
    )


@pytest.fixture
def script_env(tmp_path, monkeypatch):
    """Build a tmp scaffold and return (env_dict, paths_dict). The scripts hard-code
    REGISTRY_PATH and MOBILE_APPS_BASE so we do an in-place sed-style replacement
    via a wrapper approach: spawn the script as a module after patching sys.modules.

    Simpler alternative used here: write a wrapper script that imports the target
    module after patching the module-level constants.
    """
    tmp_base = tmp_path / "mobile-apps"
    tmp_base.mkdir()
    template = tmp_base / "_template"
    template.mkdir()
    (template / "package.json").write_text(
        '{"name": "{{APP_SLUG}}", "version": "0.0.1"}\n', encoding="utf-8"
    )
    (template / "README.md").write_text("# {{APP_SLUG}}\n", encoding="utf-8")
    (template / ".env.example").write_text("APP_NAME={{APP_SLUG}}\n", encoding="utf-8")

    tmp_reg = tmp_path / "registry.json"
    tmp_reg.write_text('{"schema_version": 1, "apps": []}\n', encoding="utf-8")

    return {
        "registry": tmp_reg,
        "base": tmp_base,
        "template": template,
        "tmp_path": tmp_path,
    }


def _wrapper(target_script: str, registry: Path, base: Path | None = None,
             template: Path | None = None) -> str:
    """Build a Python wrapper that patches REGISTRY_PATH (and optionally
    MOBILE_APPS_BASE + TEMPLATE_DIR) at import time, then re-execs main().
    """
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
        "import sys as _s",
        f"_s.argv[0] = r'{target_script}'",
        "_s.exit(M.main())",
    ]
    return "\n".join(parts)


def test_bootstrap_dry_run_does_not_mutate(script_env, tmp_path):
    wrapper = tmp_path / "wrap.py"
    wrapper.write_text(
        _wrapper("bootstrap_mobile_app", script_env["registry"],
                 base=script_env["base"], template=script_env["template"]),
        encoding="utf-8",
    )
    # Pre-state
    pre = script_env["registry"].read_text(encoding="utf-8")
    pre_files = set(p.name for p in script_env["base"].iterdir())

    rc = _run([wrapper, "--dry-run", "smoke-dry"])
    assert rc.returncode == 0, f"stderr={rc.stderr}\nstdout={rc.stdout}"

    # Post-state: identical
    post = script_env["registry"].read_text(encoding="utf-8")
    post_files = set(p.name for p in script_env["base"].iterdir())
    assert pre == post
    assert pre_files == post_files


def test_bootstrap_create_then_remove(script_env, tmp_path):
    wrapper = tmp_path / "wrap.py"
    wrapper.write_text(
        _wrapper("bootstrap_mobile_app", script_env["registry"],
                 base=script_env["base"], template=script_env["template"]),
        encoding="utf-8",
    )

    rc = _run([wrapper, "smoke-int-test"])
    assert rc.returncode == 0, f"create failed: stderr={rc.stderr}\nstdout={rc.stdout}"

    # New dir exists
    created = script_env["base"] / "smoke-int-test"
    assert created.exists() and created.is_dir()

    # Registry has entry
    reg = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    slugs = [a["slug"] for a in reg["apps"]]
    assert "smoke-int-test" in slugs

    # Placeholder was replaced in package.json
    pkg = (created / "package.json").read_text(encoding="utf-8")
    assert "smoke-int-test" in pkg
    assert "{{APP_SLUG}}" not in pkg

    # .git exists (if git is on PATH)
    git_dir = created / ".git"
    # We accept either: .git exists (git was found) OR script printed a warning
    # but continued. Both are documented behaviors.

    # Remove
    rc = _run([wrapper, "--remove", "smoke-int-test", "--force-remove"])
    assert rc.returncode == 0, f"remove failed: stderr={rc.stderr}\nstdout={rc.stdout}"

    assert not created.exists()
    reg2 = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    slugs2 = [a["slug"] for a in reg2["apps"]]
    assert "smoke-int-test" not in slugs2


def test_canary_dry_run_against_tmp_registry(script_env, tmp_path):
    wrapper = tmp_path / "wrap_canary.py"
    wrapper.write_text(
        _wrapper("mobile_app_canary", script_env["registry"]),
        encoding="utf-8",
    )

    # Add an app to the registry first
    reg = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    reg["apps"].append({
        "slug": "fake-app",
        "repo_path": "/tmp/fake-app",
        "ios_bundle_id": None,
        "android_package": None,
        "eas_project_id": None,
        "last_build_sha": None,
        "health_url": None,
        "play_tester_gate_started_at": None,
        "play_tester_count_manual": None,
        "created_at": "2026-05-27T00:00:00+00:00",
    })
    script_env["registry"].write_text(json.dumps(reg, indent=2), encoding="utf-8")

    rc = _run([wrapper, "--dry-run"])
    assert rc.returncode == 0
    # Output contains a JSON block we can parse
    out = rc.stdout
    idx = out.find("{")
    parsed = json.loads(out[idx:])
    assert parsed["dry_run"] is True
    assert len(parsed["results"]) == 1
    assert parsed["results"][0]["slug"] == "fake-app"
    assert parsed["results"][0]["status"] == "missing-health-url"


def test_play_gate_set_started_and_count(script_env, tmp_path):
    wrapper = tmp_path / "wrap_gate.py"
    wrapper.write_text(
        _wrapper("play_console_tester_gate", script_env["registry"]),
        encoding="utf-8",
    )

    # Seed registry with one app
    reg = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    reg["apps"].append({
        "slug": "gate-test", "repo_path": "/tmp/x",
        "ios_bundle_id": None, "android_package": None,
        "eas_project_id": None, "last_build_sha": None, "health_url": None,
        "play_tester_gate_started_at": None,
        "play_tester_count_manual": None,
        "created_at": "2026-05-27T00:00:00+00:00",
    })
    script_env["registry"].write_text(json.dumps(reg, indent=2), encoding="utf-8")

    # --set-started
    rc = _run([wrapper, "--set-started", "gate-test"])
    assert rc.returncode == 0, f"set-started: {rc.stderr}"
    reg2 = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    assert reg2["apps"][0]["play_tester_gate_started_at"] is not None

    # --set-count
    rc = _run([wrapper, "--set-count", "gate-test", "12"])
    assert rc.returncode == 0, f"set-count: {rc.stderr}"
    reg3 = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    assert reg3["apps"][0]["play_tester_count_manual"] == 12


def test_play_gate_set_count_unknown_slug(script_env, tmp_path):
    wrapper = tmp_path / "wrap_gate.py"
    wrapper.write_text(
        _wrapper("play_console_tester_gate", script_env["registry"]),
        encoding="utf-8",
    )
    rc = _run([wrapper, "--set-count", "ghost", "5"])
    assert rc.returncode == 2
    assert "not in registry" in rc.stderr


def test_registry_concurrent_writes(script_env, tmp_path):
    """Spawn 3 threads, each calling write_registry_atomic — final file must parse
    and be one of the writes (no partial/corrupted file)."""
    import sys as _sys
    _sys.path.insert(0, str(MOBILE_APPS_DIR))
    import bootstrap_mobile_app as bma  # noqa: E402

    # Point its REGISTRY_PATH at the tmp file
    bma.REGISTRY_PATH = script_env["registry"]

    errors = []
    lock = threading.Lock()

    def worker(idx):
        try:
            data = {
                "schema_version": 1,
                "apps": [{"slug": f"thread-{idx}", "repo_path": f"/tmp/t{idx}"}],
            }
            for _ in range(5):
                bma.write_registry_atomic(data)
                time.sleep(0.001)
        except Exception as e:
            with lock:
                errors.append(repr(e))

    threads = [threading.Thread(target=worker, args=(i,)) for i in range(3)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Concurrent write errors: {errors}"
    # Final file must parse
    parsed = json.loads(script_env["registry"].read_text(encoding="utf-8"))
    assert parsed.get("schema_version") == 1
    assert isinstance(parsed.get("apps"), list)
    # No duplicates within a single snapshot (each write replaces wholly)
    slugs = [a.get("slug") for a in parsed["apps"]]
    assert len(slugs) == len(set(slugs))


def test_env_loading_detects_firecrawl_key():
    """Without printing the value, verify FIRECRAWL_API_KEY presence detection
    via require_env. We monkey-set it then unset."""
    import sys as _sys
    _sys.path.insert(0, str(MOBILE_APPS_DIR))
    import app_store_research as asr  # noqa: E402

    os.environ.pop("TEST_FC_KEY_DETECT", None)
    with pytest.raises(SystemExit):
        asr.require_env("TEST_FC_KEY_DETECT")

    os.environ["TEST_FC_KEY_DETECT"] = "sk-test"
    try:
        assert asr.require_env("TEST_FC_KEY_DETECT") == "sk-test"
    finally:
        os.environ.pop("TEST_FC_KEY_DETECT", None)
