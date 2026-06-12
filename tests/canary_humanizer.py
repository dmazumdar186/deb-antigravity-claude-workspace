from __future__ import annotations
import importlib, json, os, subprocess, sys, re
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WORKSPACE  = Path(__file__).resolve().parents[1]
HUMANIZER  = WORKSPACE / "execution" / "content" / "humanizer.py"
VOICES_DIR = WORKSPACE / "execution" / "content" / "voices"
PY         = sys.executable


def _e(lv, lb, d=""):
    msg = "  " + lv.ljust(4) + "  " + lb
    if d:
        msg += "  (" + d + ")"
    print(msg, file=sys.stderr)

def _pass(l, d=""): _e("PASS", l, d)
def _warn(l, d=""): _e("WARN", l, d)
def _fail(l, d=""): _e("FAIL", l, d)


def check_secrets():
    keys = {
        "OPENROUTER_API_KEY": bool(os.environ.get("OPENROUTER_API_KEY")),
        "GEMINI_API_KEY":     bool(os.environ.get("GEMINI_API_KEY")),
        "ANTHROPIC_API_KEY":  bool(os.environ.get("ANTHROPIC_API_KEY")),
    }
    any_set = any(keys.values())
    status  = "PASS" if any_set else "FAIL"
    detail  = str(sum(keys.values())) + "/3 keys present"
    (_pass if any_set else _fail)("secrets", detail)
    return {"status": status, "keys_present": keys, "any_configured": any_set}


def check_deps():
    required = ["dotenv", "openai", "anthropic", "google.genai"]
    results  = {}
    all_ok   = True
    for dep in required:
        try:
            importlib.import_module(dep)
            results[dep] = True
        except ImportError as e:
            results[dep] = str(e)
            all_ok = False
    status = "PASS" if all_ok else "FAIL"
    missing_list = [k for k, v in results.items() if v is not True]
    detail = "all importable" if all_ok else "missing: " + str(missing_list)
    (_pass if all_ok else _fail)("deps", detail)
    return {"status": status, "results": results}

def check_voices():
    REQUIRED_KEYS = {"name", "lexicon", "examples"}
    voice_files = {
        "debanjan.json":  VOICES_DIR / "debanjan.json",
        "_template.json": VOICES_DIR / "_template.json",
    }
    results = {}
    all_ok = True
    for fname, path in voice_files.items():
        if not path.exists():
            results[fname] = "MISSING at " + str(path)
            all_ok = False
            continue
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            missing = REQUIRED_KEYS - set(data.keys())
            if missing:
                results[fname] = "missing keys: " + str(missing)
                all_ok = False
            else:
                results[fname] = "OK"
        except json.JSONDecodeError as exc:
            results[fname] = "invalid JSON: " + str(exc)
            all_ok = False
    status = "PASS" if all_ok else "FAIL"
    (_pass if all_ok else _fail)("voices", str(results) if not all_ok else "both valid")
    return {"status": status, "results": results}


def check_help():
    try:
        r = subprocess.run(
            [PY, str(HUMANIZER), "--help"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15,
        )
        expected = ["--text", "--file", "--voice", "--platform", "--tier", "--dry-run"]
        missing = [f for f in expected if f not in r.stdout]
        if r.returncode == 0 and not missing:
            _pass("help", "exit 0, all expected flags present")
            return {"status": "PASS", "exit_code": 0, "missing_flags": []}
        else:
            detail = "exit=" + str(r.returncode) + ", missing=" + str(missing)
            _fail("help", detail)
            return {"status": "FAIL", "exit_code": r.returncode, "missing_flags": missing}
    except Exception as exc:
        _fail("help", str(exc))
        return {"status": "FAIL", "error": str(exc)}


def check_prepass():
    test_input = "Certainly! Let me delve into this for you."
    try:
        r = subprocess.run(
            [PY, str(HUMANIZER), "--text", test_input, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, cwd=str(WORKSPACE),
        )
        combined = r.stdout + r.stderr
        certainly_stripped = "Certainly" not in r.stdout
        delve_flagged = "delve" in combined.lower() and "banned" in combined.lower()
        if r.returncode == 0 and certainly_stripped and delve_flagged:
            _pass("prepass", "Certainly! stripped; delve flagged")
            return {"status": "PASS", "exit_code": 0,
                    "certainly_stripped": True, "delve_flagged": True}
        else:
            detail = ("exit=" + str(r.returncode)
                      + ", certainly_stripped=" + str(certainly_stripped)
                      + ", delve_flagged=" + str(delve_flagged))
            _warn("prepass", detail)
            return {"status": "WARN", "exit_code": r.returncode,
                    "certainly_stripped": certainly_stripped, "delve_flagged": delve_flagged,
                    "stdout_excerpt": r.stdout[:200], "stderr_excerpt": r.stderr[:400]}
    except Exception as exc:
        _fail("prepass", str(exc))
        return {"status": "FAIL", "error": str(exc)}

def check_model_registry():
    try:
        sys.path.insert(0, str(WORKSPACE))
        from execution.modules.model_registry import resolve_model
        model_id = resolve_model("openrouter", "default", allow_network=False)
        if isinstance(model_id, str) and model_id:
            _pass("model_registry", "resolved -> " + model_id)
            return {"status": "PASS", "resolved": model_id}
        else:
            _fail("model_registry", "non-string: " + repr(model_id))
            return {"status": "FAIL", "resolved": repr(model_id)}
    except Exception as exc:
        _fail("model_registry", str(exc))
        return {"status": "FAIL", "error": str(exc)}


def check_llm_smoke():
    if not os.environ.get("GEMINI_API_KEY"):
        _warn("llm_smoke", "GEMINI_API_KEY not set -- skipped")
        return {"status": "WARN", "skipped": True, "reason": "GEMINI_API_KEY not set"}
    try:
        r = subprocess.run(
            [PY, str(HUMANIZER), "--text", "Hello world", "--tier", "gemini"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=60, cwd=str(WORKSPACE),
        )
        output = r.stdout.strip()
        if r.returncode == 0 and output:
            _pass("llm_smoke", "exit 0, output=" + repr(output[:60]))
            return {"status": "PASS", "exit_code": 0, "output_length": len(output)}
        else:
            _fail("llm_smoke", "exit=" + str(r.returncode))
            return {"status": "FAIL", "exit_code": r.returncode,
                    "stdout": output[:200], "stderr": r.stderr[:300]}
    except Exception as exc:
        _fail("llm_smoke", str(exc))
        return {"status": "FAIL", "error": str(exc)}


def check_build_sha():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=5, cwd=str(WORKSPACE),
        )
        sha = r.stdout.strip() if r.returncode == 0 else "unavailable"
    except Exception:
        sha = "unavailable"
    _pass("build_sha", sha)
    return sha


def check_cost_estimation():
    try:
        r = subprocess.run(
            [PY, str(HUMANIZER), "--text", "X" * 100, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, cwd=str(WORKSPACE),
        )
        m = re.search(r"Cost[\s:~$]*([\d.]+)", r.stderr, re.IGNORECASE)
        if m:
            cost = float(m.group(1))
            if 0 < cost < 0.01:
                _pass("cost_estimation", "dollar" + f"{cost:.5f}" + " lt 0.01")
                return {"status": "PASS", "estimated_cost": cost}
            else:
                _warn("cost_estimation", "cost " + str(cost) + " outside 0..0.01")
                return {"status": "WARN", "estimated_cost": cost}
        else:
            _warn("cost_estimation", "cost line not found in dry-run stderr")
            return {"status": "WARN", "stderr_excerpt": r.stderr[:300]}
    except Exception as exc:
        _fail("cost_estimation", str(exc))
        return {"status": "FAIL", "error": str(exc)}

def check_secret_leakage():
    LEAK_PATTERNS = ["sk-or-v", "sk-ant-", "AIza"]
    try:
        r = subprocess.run(
            [PY, str(HUMANIZER), "--text", "Hello world", "--dry-run"],
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=20, cwd=str(WORKSPACE),
        )
        combined = r.stdout + r.stderr
        found = [p for p in LEAK_PATTERNS if p in combined]
        if not found:
            _pass("secret_leakage_check", "no secret prefixes in stdout/stderr")
            return {"status": "PASS", "patterns_checked": LEAK_PATTERNS, "leaked": []}
        else:
            _fail("secret_leakage_check", "found: " + str(found))
            return {"status": "FAIL", "leaked": found}
    except Exception as exc:
        _fail("secret_leakage_check", str(exc))
        return {"status": "FAIL", "error": str(exc)}


CRITICAL_CHECKS = {"secrets", "deps", "voices", "help", "prepass"}


def compute_verdict(checks):
    statuses = {k: (v.get("status") if isinstance(v, dict) else "PASS")
               for k, v in checks.items()}
    critical_fail = any(statuses.get(k) == "FAIL" for k in CRITICAL_CHECKS)
    any_fail = any(s == "FAIL" for s in statuses.values())
    any_warn = any(s == "WARN" for s in statuses.values())
    if critical_fail or any_fail:
        return "DOWN"
    if any_warn:
        return "DEGRADED"
    return "READY"


def main():
    print("=== humanizer canary ===", file=sys.stderr)
    sha = check_build_sha()
    checks = {
        "secrets":              check_secrets(),
        "deps":                 check_deps(),
        "voices":               check_voices(),
        "help":                 check_help(),
        "prepass":              check_prepass(),
        "model_registry":       check_model_registry(),
        "llm_smoke":            check_llm_smoke(),
        "cost_estimation":      check_cost_estimation(),
        "secret_leakage_check": check_secret_leakage(),
    }
    verdict = compute_verdict(checks)
    print("  verdict: " + verdict, file=sys.stderr)
    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "build_sha":  sha,
        "checks":     checks,
        "verdict":    verdict,
    }
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
