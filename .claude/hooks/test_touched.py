"""PostToolUse hook body: run the pytest files that match an edited .py file.

Input: hook JSON on stdin (tool_input.file_path). Mapping:
  tests/**/test_X*.py edited          -> run that file
  execution/**/X.py edited            -> run tests/**/test_X.py and tests/**/test_X_*.py (max 5 files)
Sandbox (spend 0.00): every env var whose name looks secret (KEY/TOKEN/SECRET/PASSWORD/URL/DSN/...)
is replaced with a dummy, and so is every secret-looking name listed in the project's root .env
(python-dotenv never overrides a set variable, so tests can't load real keys from disk). A real call
that slips through fails auth. GIT_CONFIG_* is dropped as a group. Secret values are redacted from output.
Output: silent on pass / no tests / no pytest. On failure or timeout, emits PostToolUse
additionalContext (tail of the pytest output) so Claude sees it. Never blocks; always exits 0.
"""

import glob
import json
import os
import re
import signal
import subprocess
import sys
from pathlib import Path

TIMEOUT_S = 60
MAX_FILES = 5
DUMMY = "dummy-test-value-not-a-real-credential"
SECRET_RE = re.compile(
    r"KEY|TOKEN|TOEKN|SECRET|PASSWORD|PASSWD|CREDENTIAL|AUTH|COOKIE|SESSION|_PAT$|DSN|WEBHOOK|_URL$|_URI$",
    re.I,
)
ENV_NAME_RE = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=")


def emit(msg: str) -> None:
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PostToolUse", "additionalContext": msg}}))


def dotenv_secret_names(root: Path) -> set:
    """Names only (values never read into memory beyond the line) of secret-looking vars in root .env."""
    try:
        lines = (root / ".env").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return set()  # no .env (cloud) — nothing to shadow
    return {m.group(1) for m in map(ENV_NAME_RE.match, lines) if m and SECRET_RE.search(m.group(1))}


def kill_tree(proc: subprocess.Popen) -> None:
    try:
        if os.name == "nt":
            subprocess.run(["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True,
                           encoding="utf-8", errors="replace", timeout=10)
        else:
            os.killpg(proc.pid, signal.SIGKILL)
    except (OSError, subprocess.SubprocessError) as e:
        print(f"test-touched: tree kill failed ({e}); killing pytest only", file=sys.stderr)
        proc.kill()


def main() -> int:
    payload = json.loads(sys.stdin.buffer.read().decode("utf-8", "replace") or "{}")
    tool_input = payload.get("tool_input") if isinstance(payload, dict) else None
    raw = tool_input.get("file_path") if isinstance(tool_input, dict) else None
    if not isinstance(raw, str) or not raw.lower().endswith(".py"):
        return 0
    root = Path(os.environ.get("CLAUDE_PROJECT_DIR") or payload.get("cwd") or ".").resolve()
    try:
        rel = Path(raw).resolve().relative_to(root)
    except ValueError:
        return 0  # edited file is outside the project (symlinks resolved first)
    parts = rel.parts
    tests_dir = root / "tests"
    if not tests_dir.is_dir() or "_archived_v1" in parts:
        return 0
    if parts[0] == "tests" and rel.name.startswith("test_"):
        targets = [root / rel]
    elif parts[0] == "execution":
        stem = rel.stem
        targets = sorted(
            p for p in tests_dir.rglob(f"test_{glob.escape(stem)}*.py")
            if "_archived_v1" not in p.parts
            and (p.stem == f"test_{stem}" or p.stem.startswith(f"test_{stem}_"))
            and p.resolve().is_relative_to(root)
        )[:MAX_FILES]
    else:
        return 0
    if not targets:
        return 0

    base = dict(os.environ)
    secret_vals = [v for k, v in base.items() if SECRET_RE.search(k) and not v.isdigit() and len(v) >= 6]
    env = {k: (DUMMY if SECRET_RE.search(k) and not v.isdigit() else v) for k, v in base.items()}
    for name in dotenv_secret_names(root):
        env[name] = DUMMY
    # GIT_CONFIG_KEY_n matches the filter; changing it alone breaks GIT_CONFIG_COUNT and every git
    # call exits 128. Drop the whole env-config group together.
    env = {k: v for k, v in env.items() if not k.startswith("GIT_CONFIG_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"

    files = [t.relative_to(root).as_posix() for t in targets]
    cmd = [sys.executable, "-m", "pytest", "-q", "-x", "--no-header", "-p", "no:cacheprovider", *files]
    popen_kw = {"creationflags": subprocess.CREATE_NEW_PROCESS_GROUP} if os.name == "nt" else {"start_new_session": True}
    try:
        proc = subprocess.Popen(cmd, cwd=root, env=env, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace", **popen_kw)
    except OSError as e:
        print(f"test-touched: could not start pytest: {e}", file=sys.stderr)  # fail open, logged
        return 0
    try:
        out, _ = proc.communicate(timeout=TIMEOUT_S)
    except subprocess.TimeoutExpired:
        kill_tree(proc)
        try:
            proc.communicate(timeout=5)
        except subprocess.TimeoutExpired:
            print("test-touched: pytest output pipe still open after kill", file=sys.stderr)
        emit(f"test-touched: pytest timed out after {TIMEOUT_S}s on {' '.join(files)}. Run it manually.")
        return 0
    if proc.returncode in (0, 5):  # 5 = no tests collected
        return 0
    out = (out or "").strip()
    if "No module named pytest" in out:
        return 0  # pytest not installed in this interpreter: helper degrades silently
    for v in secret_vals:
        out = out.replace(v, "[redacted]")
    tail = "\n".join(out.splitlines()[-25:])
    emit(f"test-touched: tests FAILED after editing {rel.as_posix()} (secrets replaced with dummies):\n"
         f"$ pytest {' '.join(files)}\n{tail}")
    return 0


if __name__ == "__main__":
    try:
        main()
    except Exception as e:  # noqa: BLE001 — a hook must never fail the edit; logged to stderr
        print(f"test-touched: internal error, skipped: {type(e).__name__}: {e}", file=sys.stderr)
    sys.exit(0)
