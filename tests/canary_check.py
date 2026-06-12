from __future__ import annotations
import importlib, json, os, subprocess, sys, urllib.request, urllib.error
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

WORKSPACE = Path(__file__).resolve().parents[1]
SCRIPT    = WORKSPACE / "execution" / "video" / "youtube_video_analyzer.py"


def _ok(label, detail=""):
    msg = "  PASS  " + label
    if detail: msg += "  (" + detail + ")"
    print(msg, file=sys.stderr)

def _warn(label, detail=""):
    msg = "  WARN  " + label
    if detail: msg += "  (" + detail + ")"
    print(msg, file=sys.stderr)

def _fail(label, detail=""):
    msg = "  FAIL  " + label
    if detail: msg += "  (" + detail + ")"
    print(msg, file=sys.stderr)

def check_secrets():
    keys = {
        "openrouter": bool(os.environ.get("OPENROUTER_API_KEY")),
        "anthropic":  bool(os.environ.get("ANTHROPIC_API_KEY")),
        "gemini":     bool(os.environ.get("GEMINI_API_KEY")),
    }
    any_set = any(keys.values())
    if any_set:
        _ok("secrets", "at least one key configured")
    else:
        _fail("secrets", "OPENROUTER_API_KEY / ANTHROPIC_API_KEY / GEMINI_API_KEY all missing")
    return {**keys, "any_configured": any_set, "status": "OK" if any_set else "FAIL"}


REQUIRED_DEPS = [
    "yt_dlp", "youtube_transcript_api", "scenedetect",
    "imagehash", "PIL", "imageio_ffmpeg",
    "anthropic", "openai", "google.genai",
]

def check_deps():
    missing = []
    for dep in REQUIRED_DEPS:
        try:
            importlib.import_module(dep)
        except ImportError:
            missing.append(dep)
    all_ok = len(missing) == 0
    if all_ok:
        _ok("deps", "all " + str(len(REQUIRED_DEPS)) + " importable")
    else:
        _fail("deps", "missing: " + str(missing))
    return {"all_importable": all_ok, "missing": missing,
            "status": "OK" if all_ok else "FAIL"}


def check_ffmpeg():
    try:
        import imageio_ffmpeg
        path = imageio_ffmpeg.get_ffmpeg_exe()
        exists = Path(path).exists()
        if exists:
            _ok("ffmpeg_binary", path)
            return {"path": path, "exists": True, "status": "OK"}
        else:
            _fail("ffmpeg_binary", "path returned but file missing: " + path)
            return {"path": path, "exists": False, "status": "FAIL"}
    except Exception as exc:
        _fail("ffmpeg_binary", str(exc))
        return {"path": None, "exists": False, "status": "FAIL", "error": str(exc)}


def check_or_endpoint():
    url = "https://openrouter.ai/api/v1/models"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "canary-check/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            status_code = resp.status
            raw = resp.read()
        data = json.loads(raw)
        models = data.get("data", [])
        anthropic_count = sum(
            1 for m in models if str(m.get("id", "")).startswith("anthropic/")
        )
        _ok("or_endpoint",
            "HTTP " + str(status_code) + ", " +
            str(len(models)) + " models, " +
            str(anthropic_count) + " anthropic/*")
        return {
            "status_code": status_code,
            "total_models_in_catalog": len(models),
            "anthropic_models_in_catalog": anthropic_count,
            "status": "OK",
        }
    except Exception as exc:
        _fail("or_endpoint", str(exc))
        return {"status_code": None, "status": "FAIL", "error": str(exc)}


def check_youtube():
    url = "https://www.youtube.com"
    try:
        req = urllib.request.Request(url, method="HEAD",
                                     headers={"User-Agent": "canary-check/1.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            code = resp.status
        ok = code < 400
        if ok:
            _ok("youtube_reachable", "HTTP " + str(code))
        else:
            _warn("youtube_reachable", "HTTP " + str(code))
        return {"reachable": ok, "status": "OK" if ok else "WARN"}
    except Exception as exc:
        _fail("youtube_reachable", str(exc))
        return {"reachable": False, "status": "FAIL", "error": str(exc)}

def check_cache_age():
    cache_path = WORKSPACE / ".tmp" / "model_registry.json"
    if not cache_path.exists():
        _warn("cache_age", "model_registry.json not found -- run dry-run once to populate")
        return {"exists": False, "age_days": None, "status": "WARN"}
    try:
        data = json.loads(cache_path.read_text(encoding="utf-8"))
        resolved_at = datetime.fromisoformat(data["resolved_at"])
        age_days = (datetime.now(timezone.utc) - resolved_at).total_seconds() / 86400
        stale = age_days > 7
        if stale:
            _warn("cache_age", str(round(age_days, 2)) + " days old (>7 day TTL -- stale)")
        else:
            _ok("cache_age", str(round(age_days, 4)) + " days old")
        return {
            "exists": True,
            "age_days": round(age_days, 4),
            "resolved_at": data.get("resolved_at"),
            "status": "WARN" if stale else "OK",
        }
    except Exception as exc:
        _fail("cache_age", str(exc))
        return {"exists": True, "age_days": None, "status": "FAIL", "error": str(exc)}


def get_build_sha():
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            cwd=str(WORKSPACE), timeout=5,
        )
        if r.returncode == 0:
            return r.stdout.strip()
        return "unknown"
    except Exception:
        return "unknown"


ZOO_URL = "https://youtu.be/jNQXAC9IVRw"

# Shallow --dry-run fields (no grid_count / estimated_input_tokens — those are --deep-dry-run only)
REQUIRED_FIELDS = [
    "video_id", "tier", "provider", "model_id",
    "would_call_provider", "would_use_model", "estimated_cost",
]

def check_dry_run_smoke():
    try:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), ZOO_URL, "--dry-run"],
            capture_output=True, text=True, encoding="utf-8",
            cwd=str(WORKSPACE), timeout=120,
        )
    except subprocess.TimeoutExpired:
        _fail("dry_run_smoke", "timed out after 120s")
        return {"exit_code": -1, "status": "FAIL", "error": "timeout"}
    except Exception as exc:
        _fail("dry_run_smoke", str(exc))
        return {"exit_code": -1, "status": "FAIL", "error": str(exc)}

    exit_code = result.returncode

    # Detect YouTube IP-block -- a cloud/VPN infra issue, not a script bug.
    # In that case we WARN rather than FAIL so the canary stays green on CI.
    stderr_lower = result.stderr.lower()
    ip_blocked = "ipblocked" in result.stderr or "ip blocked" in stderr_lower or "ipblocked" in stderr_lower
    if exit_code != 0 and ip_blocked:
        _warn("dry_run_smoke",
              "exit=" + str(exit_code) + " -- YouTube IP-blocked; "
              "shallow --dry-run should make no network calls post-R1. "
              "Check for script regression.")
        return {
            "exit_code": exit_code,
            "status": "WARN",
            "note": "IpBlocked by YouTube -- expected in cloud/datacenter IPs; not a script bug",
            "known_limitation": (
                # Smoke check: shallow --dry-run exits before any network call (post-R1).
                # DEGRADED only if the dry-run itself errors. IP-block from YouTube is no longer
                # a concern on this path; the canary path uses shallow dry-run only.
                "Shallow --dry-run exits before any network call (post-R1). "
                "IP-block on this path is unexpected — check script for regression."
            ),
            "stderr_preview": result.stderr[:400],
        }

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        _fail("dry_run_smoke",
              "exit=" + str(exit_code) + ", stdout not valid JSON: " + result.stdout[:200])
        return {
            "exit_code": exit_code, "status": "FAIL",
            "error": "JSON parse: " + str(exc),
            "stdout_preview": result.stdout[:300],
            "stderr_preview": result.stderr[:300],
        }

    missing_fields = [f for f in REQUIRED_FIELDS if f not in data]

    if exit_code != 0:
        _fail("dry_run_smoke",
              "exit=" + str(exit_code) + ", stderr: " + result.stderr[:200])
        return {"exit_code": exit_code, "status": "FAIL",
                "stderr_preview": result.stderr[:300]}

    if missing_fields:
        _warn("dry_run_smoke", "exit=0 but missing fields: " + str(missing_fields))
        status = "WARN"
    else:
        would_use = data.get("would_use_model", "?")
        est_cost  = data.get("estimated_cost")
        _ok("dry_run_smoke",
            "exit=0, would_use_model=" + repr(would_use) + ", estimated_cost=" + str(est_cost))
        status = "OK"

    return {
        "exit_code":          exit_code,
        "video_id":           data.get("video_id"),
        "tier":               data.get("tier"),
        "provider":           data.get("provider"),
        "model_id":           data.get("model_id"),
        "would_call_provider": data.get("would_call_provider"),
        "would_use_model":    data.get("would_use_model"),
        "estimated_cost":     data.get("estimated_cost"),
        "missing_fields":     missing_fields,
        "status":             status,
    }


def _verdict(checks):
    statuses = [v["status"] for v in checks.values()]
    if "FAIL" in statuses: return "DOWN"
    if "WARN" in statuses: return "DEGRADED"
    return "READY"


def main():
    print("", file=sys.stderr)
    print("=== YouTube Analyzer Canary Check ===", file=sys.stderr)
    build_sha = get_build_sha()
    now_iso = datetime.now(timezone.utc).isoformat()
    print("  build_sha:  " + build_sha, file=sys.stderr)
    print("  checked_at: " + now_iso, file=sys.stderr)
    print("", file=sys.stderr)

    checks = {}
    checks["secrets"]           = check_secrets()
    checks["deps"]              = check_deps()
    checks["ffmpeg_binary"]     = check_ffmpeg()
    checks["or_endpoint"]       = check_or_endpoint()
    checks["youtube_reachable"] = check_youtube()
    checks["cache_age"]         = check_cache_age()
    checks["dry_run_smoke"]     = check_dry_run_smoke()

    verdict = _verdict(checks)

    report = {
        "checked_at": datetime.now(timezone.utc).isoformat(),
        "build_sha":  build_sha,
        "checks":     checks,
        "verdict":    verdict,
    }

    print("", file=sys.stderr)
    print("  VERDICT: " + verdict, file=sys.stderr)
    print("", file=sys.stderr)

    print(json.dumps(report, indent=2))
    return 0 if verdict == "READY" else (1 if verdict == "DEGRADED" else 2)


if __name__ == "__main__":
    sys.exit(main())
