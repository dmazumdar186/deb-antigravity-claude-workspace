"""
test_vps_cloud_init.py
description: Offline checks for the Hetzner VPS cloud-init and its two helper scripts.
inputs: none (no network, no root, no secrets).
outputs: pytest results.
"""

import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parent.parent
INFRA = ROOT / "execution" / "infrastructure"
CLOUD_INIT = INFRA / "vps_cloud_init.yaml"
INSTALL = INFRA / "vps_install_tools.sh"
FINISH = INFRA / "vps_finish_setup.sh"

SECRET_PATTERNS = [
    r"(?i)(api[_-]?key|secret|token|passw(or)?d|passwd)\s*[:=]\s*['\"]?[A-Za-z0-9/+_\-]{8,}",
    r"sk-[A-Za-z0-9_\-]{20,}",
    r"gh[pousr]_[A-Za-z0-9]{20,}",
    r"tskey-[A-Za-z0-9\-]{10,}",
    r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
    r"(?i)\$6\$[./A-Za-z0-9]{8,}",  # hashed password
]


@pytest.fixture(scope="module")
def text():
    return CLOUD_INIT.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def doc(text):
    return yaml.safe_load(text)


def bootstrap_script(doc):
    for f in doc["write_files"]:
        if f["path"] == "/usr/local/sbin/deb-vps-bootstrap.sh":
            return f["content"]
    raise AssertionError("bootstrap script missing from write_files")


def test_header_and_size(text):
    assert text.splitlines()[0] == "#cloud-config"
    assert len(text.encode("utf-8")) < 32768


def test_yaml_parses(doc):
    assert isinstance(doc, dict)
    deb = [u for u in doc["users"] if isinstance(u, dict) and u.get("name") == "deb"][0]
    assert "docker" in deb["groups"] and "NOPASSWD" in deb["sudo"]
    assert doc["ssh_pwauth"] is False and doc["disable_root"] is True


@pytest.mark.parametrize("pattern", SECRET_PATTERNS)
def test_no_secrets(text, pattern):
    for path in (CLOUD_INIT, INSTALL, FINISH):
        assert not re.search(pattern, path.read_text(encoding="utf-8")), f"{path.name} matches {pattern}"


def test_repo_paths_exist(text):
    refs = set(re.findall(r"(?:/home/deb/workspace|\$WS)/([A-Za-z0-9_./\-]+)", text))
    assert refs, "expected workspace path references"
    for rel in refs:
        assert (ROOT / rel).exists(), rel


def test_scripts_executable():
    for p in (INSTALL, FINISH):
        assert p.stat().st_mode & stat.S_IXUSR, p


def test_ufw_no_public_ssh(doc):
    script = bootstrap_script(doc)
    ufw_lines = [ln for ln in script.splitlines() if "ufw " in ln]
    assert any("allow in on tailscale0" in ln for ln in ufw_lines)
    assert any("default deny incoming" in ln for ln in ufw_lines)
    for ln in ufw_lines:
        for m in re.finditer(r"ufw allow ([^&;]*)", ln):
            rule = m.group(1)
            assert "tailscale0" in rule, f"public allow rule: {rule}"
    assert not re.search(r"ufw allow\s+(22|ssh|OpenSSH)\b", script)


def test_remote_control_not_enabled_at_boot(doc):
    script = bootstrap_script(doc)
    assert "enable claude-remote-control" not in script
    assert "enable --now claude-remote-control" not in script
    unit = [f for f in doc["write_files"] if f["path"].endswith("claude-remote-control.service")][0]["content"]
    assert "ConditionPathExists=/home/deb/.claude/.credentials.json" in unit


def test_bash_syntax(doc, tmp_path):
    boot = tmp_path / "bootstrap.sh"
    boot.write_text(bootstrap_script(doc))
    for p in (INSTALL, FINISH, boot):
        r = subprocess.run(["bash", "-n", str(p)], capture_output=True, text=True, encoding="utf-8", errors="replace")
        assert r.returncode == 0, r.stderr


@pytest.mark.skipif(not shutil.which("cloud-init"), reason="cloud-init not installed (pip install not allowed)")
def test_cloud_init_schema():
    r = subprocess.run(["cloud-init", "schema", "-c", str(CLOUD_INIT)], capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert r.returncode == 0, r.stdout + r.stderr


def _stub_bin(tmp_path, names):
    """PATH dir whose commands only record that they were called."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    calls = tmp_path / "calls.log"
    for n in names:
        p = bindir / n
        p.write_text(f'#!/bin/sh\necho "{n} $*" >> "{calls}"\nexit 0\n')
        p.chmod(0o755)
    return bindir, calls


def _snapshot(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def test_finish_dry_run_calls_nothing(tmp_path):
    bindir, calls = _stub_bin(tmp_path, ["tailscale", "systemctl", "sudo", "runuser", "cloud-init", "docker", "claude"])
    home = tmp_path / "home"
    home.mkdir()
    env = {**os.environ, "PATH": f"{bindir}:{os.environ['PATH']}", "HOME": str(home),
           "DEB_HOME": str(home), "TMPDIR": str(tmp_path)}
    before = _snapshot(home)
    r = subprocess.run(["bash", str(FINISH), "--dry-run"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 0, r.stderr
    assert "tailscale serve --bg --https=8443 https+insecure://127.0.0.1:8443" in r.stdout
    assert "funnel" not in r.stdout.replace("never funnel", "")
    assert not calls.exists(), calls.read_text()
    assert _snapshot(home) == before


def _install_env(tmp_path, **extra):
    home = tmp_path / "home"
    home.mkdir(exist_ok=True)
    return {**os.environ, "HOME": str(home), "TMPDIR": str(tmp_path),
            "DEB_TOOLS_LOG_DIR": str(tmp_path / "logs"),
            "DEB_TOOLS_MARKER": str(tmp_path / "state" / "installed"),
            "DEB_TOOLS_DOCKER_WAIT": "0", **extra}


@pytest.mark.skipif(not shutil.which("git"), reason="git needed by setup scripts")
def test_install_dry_run_real_scripts(tmp_path):
    env = _install_env(tmp_path)
    r = subprocess.run(["bash", str(INSTALL), "--dry-run"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:] + r.stderr[-2000:]
    for t in ("freellmapi", "open_seo", "opencode", "voicestudio", "openbot", "pentagi"):
        assert re.search(rf"^{t}\s+OK", r.stdout, re.M), t
    assert not (tmp_path / "state").exists()       # no marker on dry-run
    assert not (tmp_path / "logs").exists()        # real log dir untouched on dry-run
    # nothing cloned (an already-installed opencode may create its own ~/.cache etc. on --version)
    assert not (tmp_path / "home" / "dev").exists()


def test_install_one_failure_does_not_stop_others(tmp_path):
    sdir = tmp_path / "scripts"
    sdir.mkdir()
    (sdir / "setup_a.sh").write_text('echo "a $*" >> "$OUT"\n')
    (sdir / "setup_b.sh").write_text('echo "b $*" >> "$OUT"; exit 3\n')
    (sdir / "setup_c.sh").write_text('echo "c $*" >> "$OUT"\n')
    out = tmp_path / "out.txt"
    env = _install_env(tmp_path, VPS_TOOLS_SCRIPT_DIR=str(sdir), VPS_TOOLS_LIST="a b c", OUT=str(out))
    r = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 1
    assert out.read_text().split("\n")[:3] == ["a ", "b ", "c "]
    assert "FAIL(3)" in (tmp_path / "logs" / "summary.txt").read_text()
    assert not (tmp_path / "state" / "installed").exists()

    (sdir / "setup_b.sh").write_text('echo "b $*" >> "$OUT"\n')
    r = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 0 and (tmp_path / "state" / "installed").exists()
    r = subprocess.run(["bash", str(INSTALL)], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env, timeout=60)
    assert r.returncode == 0 and "already installed" in r.stdout  # idempotent no-op

    r = subprocess.run(["bash", str(INSTALL), "--dry-run", "--force"], capture_output=True, text=True, encoding="utf-8", errors="replace", env=env)
    assert r.returncode == 0 and out.read_text().strip().endswith("c --dry-run")
