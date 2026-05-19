"""
Sanity smoke checks for humanizer.py.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

WORKSPACE = Path(r"C:/Users/deban/OneDrive/Documents/AntiGravity Project Space")
SCRIPT = str(WORKSPACE / "execution" / "content" / "humanizer.py")
PY = sys.executable

from dotenv import load_dotenv
load_dotenv(str(WORKSPACE / ".env"))

PASS_COUNT = 0
FAIL_COUNT = 0
FAILURES = []


def run(name, fn):
    global PASS_COUNT, FAIL_COUNT
    try:
        fn()
        print(f"PASS  {name}")
        PASS_COUNT += 1
    except Exception as exc:
        print(f"FAIL  {name}")
        print(f"      {exc}")
        FAIL_COUNT += 1
        FAILURES.append((name, str(exc)))


def _cli(*args, stdin_text=None):
    return subprocess.run(
        [PY, SCRIPT, *args],
        input=stdin_text, capture_output=True, text=True,
        encoding="utf-8", errors="replace", cwd=str(WORKSPACE),
    )


def test_help_exit_0_all_flags():
    r = _cli("--help")
    assert r.returncode == 0, f"--help exit {r.returncode}"
    for flag in ["--voice", "--platform", "--tier", "--dry-run", "--show-diff", "--keep-em-dashes"]:
        assert flag in r.stdout, f"--help missing {flag}"


def test_module_importable():
    r = subprocess.run(
        [PY, "-c",
         "import sys; sys.path.insert(0,'execution/content'); sys.path.insert(0,'execution/modules'); import humanizer; print('OK')"],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
        cwd=str(WORKSPACE),
    )
    assert r.returncode == 0 and "OK" in r.stdout, f"Import failed:\n{r.stderr}"


def test_deps_importable():
    deps = ["dotenv", "openai", "anthropic", "google.genai"]
    for dep in deps:
        r = subprocess.run(
            [PY, "-c", f"import {dep}; print('OK')"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(WORKSPACE),
        )
        assert r.returncode == 0, f"Dep '{dep}' not importable:\n{r.stderr}"


def test_debanjan_json_valid():
    vf = WORKSPACE / "execution" / "content" / "voices" / "debanjan.json"
    data = json.loads(vf.read_text(encoding="utf-8"))
    for key in ["name", "lexicon", "examples"]:
        assert key in data, f"debanjan.json missing key: {key}"
    assert len(data["examples"]) >= 1


def test_template_json_valid():
    vf = WORKSPACE / "execution" / "content" / "voices" / "_template.json"
    data = json.loads(vf.read_text(encoding="utf-8"))
    for key in ["name", "lexicon", "examples"]:
        assert key in data, f"_template.json missing key: {key}"


def test_empty_text_no_crash():
    r = _cli("--text", "", "--dry-run")
    assert r.returncode == 0, f"empty text crashed: exit {r.returncode}\n{r.stderr}"


def test_dry_run_stdout_nonempty():
    r = _cli("--text", "Test sentence.", "--dry-run")
    assert r.returncode == 0
    assert len(r.stdout.strip()) > 0, "stdout should not be empty on dry-run"


def test_no_key_leak():
    r = _cli("--text", "Test sentence.", "--dry-run")
    combined = r.stdout + r.stderr
    for pat in ["sk-or-v", "sk-ant-", "AIza"]:
        assert pat not in combined, f"Potential key leak pattern '{pat}' in output"


def test_module_docstring_fields():
    script_text = (WORKSPACE / "execution" / "content" / "humanizer.py").read_text(encoding="utf-8")
    for field in ["description:", "inputs:", "outputs:"]:
        assert field in script_text, f"Module docstring missing: {field}"


if __name__ == "__main__":
    run("sanity 1: --help exit 0 + all required flags", test_help_exit_0_all_flags)
    run("sanity 2: module importable", test_module_importable)
    run("sanity 3: all deps importable", test_deps_importable)
    run("sanity 4: debanjan.json valid + required keys", test_debanjan_json_valid)
    run("sanity 5: _template.json valid + required keys", test_template_json_valid)
    run("sanity 6: empty --text doesn't crash", test_empty_text_no_crash)
    run("sanity 7: --dry-run stdout non-empty", test_dry_run_stdout_nonempty)
    run("sanity 8: no API keys leak to stdout/stderr", test_no_key_leak)
    run("sanity 9: module docstring has description/inputs/outputs", test_module_docstring_fields)

    print(f"\n{'='*50}")
    print(f"Results: {PASS_COUNT} passed, {FAIL_COUNT} failed")
    if FAILURES:
        print("\nFailed tests:")
        for name, err in FAILURES:
            print(f"  FAIL  {name}")
            print(f"        {err}")
    import sys as _sys
    _sys.exit(0 if FAIL_COUNT == 0 else 1)
