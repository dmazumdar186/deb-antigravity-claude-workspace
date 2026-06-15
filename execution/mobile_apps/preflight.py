"""
description: Mobile-app preflight gate. Runs every CLI / account / env-var check required to ship a mobile app and emits a structured JSON report. Exit 0 iff all required items pass.
inputs: env vars (APPLE_ENROLLMENT_STATUS, EXPO_TOKEN, OPENROUTER_API_KEY, FIRECRAWL_API_KEY); host shell with node/eas/wrangler/modal/py on PATH. CLI: --json (machine-readable output), --required-only (skip optional Phase 4-5 keys).
outputs: human table on stdout; machine-readable JSON on stdout when --json is set; exit code 0 if all required items GREEN, 1 if any required item is RED. APPLE_ENROLLMENT_STATUS=pending blocks Phase 4-5 but does NOT make exit non-zero (Phases 1-3 are still green).

Per directives/mobile_apps/preflight.md. Runs read-only — never executes
`eas login`, `wrangler login`, or anything else that could clobber a session.

Usage:
    py execution/mobile_apps/preflight.py
    py execution/mobile_apps/preflight.py --json > preflight.json
    py execution/mobile_apps/preflight.py --required-only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
ENV_PATH = WORKSPACE_ROOT / ".env"

# Required env keys (any missing → RED → exit 1).
_REQUIRED_ENV_KEYS = ("EXPO_TOKEN", "OPENROUTER_API_KEY", "FIRECRAWL_API_KEY")

# Optional env keys (missing → YELLOW; needed for Phase 4-5 iOS submit only).
_OPTIONAL_ENV_KEYS = (
    "APPLE_ID",
    "APPLE_TEAM_ID",
    "APPLE_APP_SPECIFIC_PASSWORD",
    "ASC_KEY_ID",
    "ASC_ISSUER_ID",
    "ASC_PRIVATE_KEY_PATH",
    "GOOGLE_PLAY_SERVICE_ACCOUNT_JSON_PATH",
)

MIN_NODE_MAJOR = 18

# Color codes — only used if stdout is a tty.
_USE_COLOR = sys.stdout.isatty() if hasattr(sys.stdout, "isatty") else False
_C = {
    "GREEN": "\033[92m",
    "YELLOW": "\033[93m",
    "RED": "\033[91m",
    "BLOCK": "\033[95m",
    "RESET": "\033[0m",
}


def _color(label: str) -> str:
    if not _USE_COLOR:
        return f"[{label}]"
    return f"{_C.get(label, '')}[{label}]{_C['RESET']}"


def _run(*cmd: str, timeout: int = 15) -> tuple[int, str, str]:
    """Run a command; return (returncode, stdout, stderr). Never raises."""
    try:
        r = subprocess.run(
            list(cmd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
        )
        return r.returncode, (r.stdout or "").strip(), (r.stderr or "").strip()
    except FileNotFoundError:
        return 127, "", f"{cmd[0]}: not on PATH"
    except subprocess.TimeoutExpired:
        return 124, "", f"{cmd[0]}: timeout after {timeout}s"
    except OSError as e:
        return 1, "", f"{cmd[0]}: OSError: {e}"


# ----------------------------------------------------------------------------
# Individual checks — each returns (status, message, detail)
# status: "GREEN" | "YELLOW" | "RED" | "BLOCK"
# ----------------------------------------------------------------------------

def check_node_version() -> tuple[str, str, str]:
    if shutil.which("node") is None:
        return "RED", "node not on PATH", "install Node ≥ 18: https://nodejs.org/"
    rc, out, err = _run("node", "--version")
    if rc != 0:
        return "RED", f"node --version failed ({rc})", err
    m = re.search(r"v(\d+)\.(\d+)\.", out)
    if not m:
        return "RED", f"node --version output unparseable: {out!r}", out
    major = int(m.group(1))
    if major < MIN_NODE_MAJOR:
        return "RED", f"node {out} < required {MIN_NODE_MAJOR}.x", "upgrade Node — eas-cli silently degrades on Node < 18"
    return "GREEN", out, ""


def check_eas_cli() -> tuple[str, str, str]:
    if shutil.which("eas") is None:
        return "RED", "eas not on PATH", "npm install -g eas-cli"
    rc, out, err = _run("eas", "--version")
    if rc != 0:
        return "RED", f"eas --version failed ({rc})", err
    return "GREEN", out, ""


def check_eas_session() -> tuple[str, str, str]:
    if shutil.which("eas") is None:
        return "RED", "eas not on PATH (cannot check session)", "npm install -g eas-cli"
    rc, out, err = _run("eas", "whoami", timeout=30)
    if rc != 0:
        return "RED", "eas whoami exited non-zero", "run `eas login` in a separate shell — preflight never logs in"
    text = (out or err).strip()
    if not text or "not logged in" in text.lower():
        return "RED", "eas: not logged in", "run `eas login` in a separate shell"
    return "GREEN", text, ""


def check_wrangler_cli() -> tuple[str, str, str]:
    if shutil.which("wrangler") is None:
        return "RED", "wrangler not on PATH", "npm install -g wrangler"
    rc, out, err = _run("wrangler", "--version")
    if rc != 0:
        return "RED", f"wrangler --version failed ({rc})", err
    return "GREEN", out, ""


def check_wrangler_session() -> tuple[str, str, str]:
    if shutil.which("wrangler") is None:
        return "RED", "wrangler not on PATH (cannot check session)", "npm install -g wrangler"
    rc, out, err = _run("wrangler", "whoami", timeout=30)
    if rc != 0:
        return "RED", "wrangler whoami exited non-zero", "log in manually in a separate shell — do NOT run `wrangler login` from preflight (may clobber AM-scoped session)"
    text = (out + "\n" + err).strip()
    return "GREEN", text.splitlines()[0] if text else "logged in", ""


def check_modal_token() -> tuple[str, str, str]:
    if shutil.which("modal") is None:
        return "RED", "modal not on PATH", "pip install modal"
    rc, out, err = _run("modal", "token", "current", timeout=15)
    if rc != 0:
        return "RED", "modal token current failed", "run `modal token new`"
    return "GREEN", out.splitlines()[0] if out else "token present", ""


def _read_env_keys() -> dict[str, str]:
    """Parse .env into {KEY: value}. Never echoes values to stdout; caller decides
    whether to log them."""
    if not ENV_PATH.exists():
        return {}
    out: dict[str, str] = {}
    for raw in ENV_PATH.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.strip().strip('"').strip("'")
        out[k.strip()] = v
    return out


def check_env_key(env_map: dict[str, str], key: str, required: bool) -> tuple[str, str, str]:
    val = env_map.get(key, "")
    present = bool(val and val.strip())
    if present:
        return "GREEN", "present", ""
    if required:
        return "RED", "MISSING", f"add {key}=... to .env"
    return "YELLOW", "absent", f"add {key}=... when this app hits Phase 4 iOS submit"


def check_apple_enrollment() -> tuple[str, str, str]:
    env_map = _read_env_keys()
    # Allow either env or .env override.
    status = (os.environ.get("APPLE_ENROLLMENT_STATUS") or env_map.get("APPLE_ENROLLMENT_STATUS") or "").strip().lower()
    if status == "active":
        return "GREEN", "active", ""
    # Default to blocked (Phases 4-5 gated). Phases 1-3 still proceed.
    return "BLOCK", f"APPLE_ENROLLMENT_STATUS={status or 'unset'}", "Phases 4-5 blocked until Apple Developer enrollment is active"


# ----------------------------------------------------------------------------
# Aggregate
# ----------------------------------------------------------------------------

def collect(required_only: bool = False) -> list[dict[str, Any]]:
    env_map = _read_env_keys()
    items: list[dict[str, Any]] = []

    def add(name: str, result: tuple[str, str, str], required: bool):
        status, message, hint = result
        items.append({
            "name": name,
            "status": status,
            "message": message,
            "hint": hint,
            "required": required,
        })

    add("node --version", check_node_version(), required=True)
    add("eas --version", check_eas_cli(), required=True)
    add("eas whoami", check_eas_session(), required=True)
    add("wrangler --version", check_wrangler_cli(), required=True)
    add("wrangler whoami", check_wrangler_session(), required=True)
    add("modal token current", check_modal_token(), required=True)

    for key in _REQUIRED_ENV_KEYS:
        add(f".env {key}", check_env_key(env_map, key, required=True), required=True)

    if not required_only:
        for key in _OPTIONAL_ENV_KEYS:
            add(f".env {key}", check_env_key(env_map, key, required=False), required=False)

    add("Phase 4-5 gate", check_apple_enrollment(), required=False)
    return items


def aggregate_exit_code(items: list[dict[str, Any]]) -> int:
    """Exit 1 iff any REQUIRED item is RED. Phase 4-5 BLOCK is informational."""
    for it in items:
        if it.get("required") and it.get("status") == "RED":
            return 1
    return 0


def _print_human(items: list[dict[str, Any]]) -> None:
    name_w = max(len(it["name"]) for it in items) if items else 20
    for it in items:
        tag = _color(it["status"])
        print(f"{tag:<10} {it['name']:<{name_w}} {it['message']}")
        if it.get("hint") and it["status"] in ("RED", "BLOCK"):
            print(f"           hint: {it['hint']}")
    print()
    print("Account / cost reminder:")
    print("  Apple Developer Program    $99/yr      iOS TestFlight + App Store")
    print("  Google Play Console        $25 once    Android Play Store")
    print("  Expo EAS                   $0 / $19mo  30 free builds; Production tier $19/mo")
    print("  OpenRouter                 ~$5 start   Phase 5a LLM routing")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Mobile-app preflight gate")
    ap.add_argument("--json", action="store_true", help="Emit JSON to stdout (machine-readable)")
    ap.add_argument("--required-only", action="store_true", help="Skip optional Phase 4-5 env keys")
    args = ap.parse_args(argv)

    items = collect(required_only=args.required_only)
    rc = aggregate_exit_code(items)

    if args.json:
        print(json.dumps({
            "exit_code": rc,
            "all_required_green": rc == 0,
            "phase_4_5_blocked": any(
                it["name"] == "Phase 4-5 gate" and it["status"] == "BLOCK" for it in items
            ),
            "items": items,
        }, indent=2, ensure_ascii=False))
    else:
        _print_human(items)
        if rc != 0:
            print(f"{_color('RED')} Preflight FAILED — fix the RED items above before proceeding.")
        else:
            print(f"{_color('GREEN')} Preflight OK — all required items green.")

    return rc


if __name__ == "__main__":
    sys.exit(main())
