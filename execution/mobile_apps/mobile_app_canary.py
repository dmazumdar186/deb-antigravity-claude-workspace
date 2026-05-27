"""
mobile_app_canary.py
description: Iterate registry.json, ping each app's /api/health endpoint in parallel (httpx + ThreadPoolExecutor), and report green/red/missing per app. Designed to be invoked manually or from a Modal cron. Shared results dict guarded by threading.Lock (Windows hardening rule #2).
inputs: CLI: --dry-run (skip HTTP, just parse registry), --timeout <seconds> (default 10); reads execution/mobile_apps/registry.json
outputs: Per-app status line + final JSON summary to stdout; exit 0 if all green or --dry-run, exit 1 if any red
usage:
    py execution/mobile_apps/mobile_app_canary.py
    py execution/mobile_apps/mobile_app_canary.py --dry-run
    py execution/mobile_apps/mobile_app_canary.py --timeout 20
"""

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import httpx
except ImportError:
    httpx = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "apps": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def ping_health(slug: str, url: str, timeout: float) -> dict:
    """Single health-check. Returns a result dict, never raises."""
    if httpx is None:
        return {"slug": slug, "status": "missing-dep", "detail": "httpx not installed"}
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        body_excerpt: str | None
        try:
            body_excerpt = resp.text[:500]
        except (UnicodeDecodeError, ValueError) as e:
            # Body decode failed — non-fatal; we still know status code.
            body_excerpt = f"<undecodable body: {e}>"
        ok = 200 <= resp.status_code < 400
        return {
            "slug": slug,
            "url": url,
            "status": "green" if ok else "red",
            "http_status": resp.status_code,
            "body": body_excerpt,
        }
    except httpx.HTTPError as e:
        # Connection/timeout/etc. — record as red rather than crashing the whole canary.
        return {"slug": slug, "url": url, "status": "red", "error": str(e)}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse registry, do not make HTTP calls.")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Per-request timeout in seconds (default 10).")
    parser.add_argument("--max-workers", type=int, default=8,
                        help="Thread pool size (default 8).")
    args = parser.parse_args()

    registry = load_registry()
    apps = registry.get("apps", [])
    print(f"mobile_app_canary: {len(apps)} app(s) in registry "
          f"(dry_run={args.dry_run}, timeout={args.timeout}s)")

    results: dict[str, dict] = {}
    results_lock = threading.Lock()

    if args.dry_run:
        for app in apps:
            slug = app.get("slug")
            url = app.get("health_url")
            entry = {
                "slug": slug,
                "url": url,
                "status": "dry-run" if url else "missing-health-url",
            }
            with results_lock:
                results[slug] = entry
        summary = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "dry_run": True,
            "results": list(results.values()),
        }
        print(json.dumps(summary, indent=2, ensure_ascii=False))
        return 0

    # Filter apps with health_url
    pingable = [a for a in apps if a.get("health_url")]
    missing = [a for a in apps if not a.get("health_url")]
    for app in missing:
        slug = app.get("slug")
        entry = {"slug": slug, "status": "missing-health-url"}
        with results_lock:
            results[slug] = entry
        print(f"  [{slug}] missing-health-url")

    if pingable:
        with ThreadPoolExecutor(max_workers=args.max_workers) as ex:
            futures = {
                ex.submit(ping_health, a["slug"], a["health_url"], args.timeout): a["slug"]
                for a in pingable
            }
            for fut in as_completed(futures):
                slug = futures[fut]
                try:
                    entry = fut.result()
                except (RuntimeError, OSError) as e:
                    # Unexpected ping_health crash — record red rather than abort canary.
                    entry = {"slug": slug, "status": "red", "error": str(e)}
                with results_lock:
                    results[slug] = entry
                print(f"  [{slug}] {entry.get('status')} "
                      f"(http={entry.get('http_status')})")

    n_green = sum(1 for r in results.values() if r.get("status") == "green")
    n_red = sum(1 for r in results.values() if r.get("status") == "red")
    n_missing = sum(1 for r in results.values() if r.get("status") == "missing-health-url")

    summary = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": False,
        "counts": {"green": n_green, "red": n_red, "missing": n_missing,
                   "total": len(apps)},
        "results": list(results.values()),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if n_red else 0


if __name__ == "__main__":
    sys.exit(main())
