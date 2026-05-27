"""
eas_build_helper.py
description: Wrap `eas build --platform <ios|android> --profile <preview|production>`, capture stdout/stderr (utf-8), parse build ID + URL from EAS output, optionally POST a JSON status to MOBILE_BUILD_WEBHOOK_URL, and update last_build_sha in registry.json for the given app.
inputs: CLI: --app <slug>, --platform <ios|android>, --profile <preview|production>; env: MOBILE_BUILD_WEBHOOK_URL (optional)
outputs: Runs `eas build` in the app repo dir; prints captured logs; updates registry.json last_build_sha; optionally POSTs JSON to Modal webhook
usage:
    py execution/mobile_apps/eas_build_helper.py --app my-app --platform ios --profile preview
    py execution/mobile_apps/eas_build_helper.py --app my-app --platform android --profile production
"""

import argparse
import json
import os
import re
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Concurrent-write guard for REGISTRY_PATH; see bootstrap_mobile_app.py for rationale.
_REGISTRY_WRITE_LOCK = threading.Lock()

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"

# EAS Build prints lines like:
#   Build details: https://expo.dev/accounts/xyz/projects/foo/builds/abc-123
# We parse build URL + ID from these.
BUILD_URL_RE = re.compile(r"https://expo\.dev/accounts/[^\s]+/builds/([0-9a-f-]+)", re.IGNORECASE)


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "apps": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_registry_atomic(data: dict) -> None:
    # Per-call unique tmp + lock; see bootstrap_mobile_app.py for rationale.
    with _REGISTRY_WRITE_LOCK:
        tmp = REGISTRY_PATH.with_suffix(f".json.tmp.{os.getpid()}.{uuid.uuid4().hex}")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, REGISTRY_PATH)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    # Safe: stale tmp in same dir, no data loss.
                    pass


def find_app(registry: dict, slug: str) -> dict | None:
    for app in registry.get("apps", []):
        if app.get("slug") == slug:
            return app
    return None


def get_git_sha(repo_path: Path) -> str | None:
    """Return current HEAD SHA of repo_path, or None on failure."""
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        shell=(sys.platform == "win32"),
    )
    if result.returncode != 0:
        # No git repo or no commits yet — non-fatal; we just won't record a SHA.
        print(f"  warn: git rev-parse failed: {result.stderr.strip()}",
              file=sys.stderr)
        return None
    return result.stdout.strip() or None


def parse_build_url(text: str) -> tuple[str | None, str | None]:
    """Return (build_url, build_id) parsed from EAS output."""
    match = BUILD_URL_RE.search(text)
    if not match:
        return None, None
    return match.group(0), match.group(1)


def post_webhook(url: str, payload: dict) -> None:
    if requests is None:
        print("  warn: `requests` not installed — skipping webhook POST", file=sys.stderr)
        return
    try:
        resp = requests.post(url, json=payload, timeout=15)
        print(f"  webhook -> {resp.status_code}")
        if resp.status_code >= 400:
            print(f"  webhook body: {resp.text[:500]}", file=sys.stderr)
    except requests.RequestException as e:
        # Non-fatal: build already succeeded; we just couldn't notify.
        print(f"  warn: webhook POST failed: {e}", file=sys.stderr)


def run_eas_build(repo_path: Path, platform: str, profile: str) -> tuple[int, str, str]:
    """Run eas build, return (returncode, stdout, stderr)."""
    args = ["eas", "build", "--platform", platform, "--profile", profile,
            "--non-interactive"]
    print(f"  running: {' '.join(args)} (cwd={repo_path})")
    result = subprocess.run(
        args,
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        shell=(sys.platform == "win32"),
    )
    return result.returncode, result.stdout, result.stderr


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--app", required=True, help="App slug (must exist in registry).")
    parser.add_argument("--platform", required=True, choices=["ios", "android"])
    parser.add_argument("--profile", required=True, choices=["preview", "production"])
    args = parser.parse_args()

    registry = load_registry()
    app = find_app(registry, args.app)
    if not app:
        print(f"ERROR: app '{args.app}' not in registry. Bootstrap it first.",
              file=sys.stderr)
        return 2

    repo_path = Path(app["repo_path"])
    if not repo_path.exists():
        print(f"ERROR: repo_path {repo_path} does not exist.", file=sys.stderr)
        return 2

    print(f"eas build: app={args.app} platform={args.platform} profile={args.profile}")

    rc, stdout, stderr = run_eas_build(repo_path, args.platform, args.profile)
    print("--- eas stdout ---")
    print(stdout)
    if stderr:
        print("--- eas stderr ---", file=sys.stderr)
        print(stderr, file=sys.stderr)

    combined = (stdout or "") + "\n" + (stderr or "")
    build_url, build_id = parse_build_url(combined)
    print(f"  parsed build_url={build_url} build_id={build_id}")

    head_sha = get_git_sha(repo_path)
    if head_sha:
        app["last_build_sha"] = head_sha
        # Replace and persist
        registry["apps"] = [a if a.get("slug") != args.app else app
                            for a in registry["apps"]]
        write_registry_atomic(registry)
        print(f"  registry: last_build_sha={head_sha[:12]}")

    webhook_url = os.environ.get("MOBILE_BUILD_WEBHOOK_URL")
    if webhook_url:
        payload = {
            "app": args.app,
            "platform": args.platform,
            "profile": args.profile,
            "build_url": build_url,
            "build_id": build_id,
            "exit_code": rc,
            "git_sha": head_sha,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        post_webhook(webhook_url, payload)
    else:
        print("  MOBILE_BUILD_WEBHOOK_URL not set — skipping webhook POST")

    if rc != 0:
        print(f"ERROR: eas build exit code {rc}", file=sys.stderr)
        return rc

    print("Done.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
