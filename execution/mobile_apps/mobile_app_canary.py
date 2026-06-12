"""
mobile_app_canary.py
description: Iterate registry.json, ping each app's /api/health endpoint in parallel (httpx + ThreadPoolExecutor), and report green/red/missing per app. Deduplicates alerts via .tmp/canary_state.json — only fires on status transitions or consecutive-failure threshold breaches. Designed to be invoked manually or from a Modal cron.
inputs: CLI: --dry-run (skip HTTP, just parse registry), --timeout <seconds> (default 10), --alert {none,console,webhook,both} (default console), --webhook-url <url> (or env MOBILE_CANARY_WEBHOOK_URL), --alert-threshold <N> (default 3), --silence-first-run (suppress alerts for checks seen for the very first time); reads execution/mobile_apps/registry.json
outputs: Per-app status line + final JSON summary to stdout; .tmp/canary_state.json updated each run; alert banner/webhook on transition or threshold breach; exit 0 if all green or --dry-run, exit 1 if any red
usage:
    py execution/mobile_apps/mobile_app_canary.py
    py execution/mobile_apps/mobile_app_canary.py --dry-run
    py execution/mobile_apps/mobile_app_canary.py --timeout 20
    py execution/mobile_apps/mobile_app_canary.py --alert webhook --webhook-url https://hooks.example.com/canary
    py execution/mobile_apps/mobile_app_canary.py --alert both --alert-threshold 5
    py execution/mobile_apps/mobile_app_canary.py --silence-first-run
"""

import argparse
import json
import os
import sys
import tempfile
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
TMP_DIR = ROOT / ".tmp"
STATE_PATH = TMP_DIR / "canary_state.json"

# ANSI colours — used for console alerts only; stripped when stdout is not a TTY.
_RED = "\033[1;31m"
_YELLOW = "\033[1;33m"
_GREEN = "\033[1;32m"
_RESET = "\033[0m"


def _colour_supported() -> bool:
    return hasattr(sys.stdout, "isatty") and sys.stdout.isatty()


def _c(code: str, text: str) -> str:
    return f"{code}{text}{_RESET}" if _colour_supported() else text


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "apps": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Health probing
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# State persistence  (.tmp/canary_state.json)
# ---------------------------------------------------------------------------

def load_state() -> dict:
    """Load prior run state; return empty skeleton on any read error."""
    if not STATE_PATH.exists():
        return {"last_run_at": None, "checks": {}}
    try:
        with STATE_PATH.open("r", encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        # Corrupted or missing state — start fresh. Intentional swallow: this
        # is a best-effort dedup file; the canary must keep running regardless.
        print(f"  [state] could not read {STATE_PATH}: {e} — starting fresh",
              file=sys.stderr)
        return {"last_run_at": None, "checks": {}}


def save_state(state: dict) -> None:
    """Atomically write state to .tmp/canary_state.json via temp-file rename."""
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    # Write to a sibling temp file then rename — atomic on POSIX; best-effort on Windows.
    fd, tmp_path = tempfile.mkstemp(dir=TMP_DIR, prefix="canary_state_", suffix=".json.tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(state, f, indent=2, ensure_ascii=False)
        Path(tmp_path).replace(STATE_PATH)
    except OSError as e:
        # Non-fatal: state dedup is best-effort. Log and continue.
        print(f"  [state] failed to save {STATE_PATH}: {e}", file=sys.stderr)
        try:
            Path(tmp_path).unlink(missing_ok=True)
        except OSError:
            pass  # Can't clean up the temp file — ignore; it's under .tmp/ (gitignored).


# ---------------------------------------------------------------------------
# Alert logic
# ---------------------------------------------------------------------------

def _canonical_status(raw_status: str) -> str:
    """Map result statuses to pass/fail for state tracking."""
    return "pass" if raw_status == "green" else "fail"


def compute_alerts(
    results: dict[str, dict],
    prior_state: dict,
    alert_threshold: int,
    now_iso: str,
    silence_first_run: bool = False,
) -> tuple[dict, list[dict]]:
    """
    Compare current results against prior state.

    Args:
        results:           Per-slug result dicts from the current run.
        prior_state:       The loaded .tmp/canary_state.json (or empty skeleton).
        alert_threshold:   Fire repeated alert every N consecutive failures.
        now_iso:           ISO-8601 timestamp string for this run.
        silence_first_run: When True, a check whose slug has *never* appeared in the
                           state file (prior_status is None) will not fire an alert
                           on its first observed failure — the failure is recorded in
                           state so subsequent runs apply normal threshold rules.
                           Default False (backwards-compatible behaviour: first
                           observation at threshold=1 does fire an alert).

    Returns:
        (updated_checks, alerts) — updated checks dict and list of alert payloads.
    """
    checks = prior_state.get("checks", {})
    alerts = []

    for slug, result in results.items():
        current_status = _canonical_status(result.get("status", "fail"))
        prior = checks.get(slug, {})
        prior_status = prior.get("status")
        consecutive = prior.get("consecutive_failures", 0)
        last_change = prior.get("last_status_change_at", now_iso)

        is_first_observation = prior_status is None
        transitioned = not is_first_observation and current_status != prior_status
        if current_status == "fail":
            consecutive += 1
        else:
            consecutive = 0

        threshold_breach = (
            current_status == "fail"
            and consecutive >= alert_threshold
            and consecutive % alert_threshold == 0
        )

        # When --silence-first-run is set, suppress both transition AND threshold
        # alerts for a check that has never been seen before. The state file is
        # still written so the next run observes consecutive=1 already recorded.
        if silence_first_run and is_first_observation:
            threshold_breach = False
            # transitioned is already False for first observations

        if transitioned or threshold_breach:
            if transitioned:
                last_change = now_iso
            alerts.append({
                "check_name": slug,
                "status": current_status,
                "message": result.get("error") or result.get("detail") or
                           f"http_status={result.get('http_status')}",
                "consecutive_failures": consecutive,
                "last_status_change_at": last_change,
                "trigger": "transition" if transitioned else "threshold",
            })

        checks[slug] = {
            "status": current_status,
            "last_status_change_at": last_change,
            "consecutive_failures": consecutive,
        }

    return checks, alerts


def fire_console_alert(alert: dict) -> None:
    """Print a clearly-formatted ANSI banner for the alert."""
    status = alert["status"]
    colour = _RED if status == "fail" else _GREEN
    trigger = alert.get("trigger", "unknown")
    slug = alert["check_name"]
    consecutive = alert["consecutive_failures"]
    msg = alert["message"]
    last_change = alert["last_status_change_at"]

    banner = (
        "\n" +
        _c(colour, "=" * 60) + "\n" +
        _c(colour, f"  CANARY ALERT [{trigger.upper()}]") + "\n" +
        _c(colour, f"  App:    {slug}") + "\n" +
        _c(colour, f"  Status: {status.upper()}") + "\n" +
        _c(colour, f"  Consecutive failures: {consecutive}") + "\n" +
        _c(colour, f"  Last change: {last_change}") + "\n" +
        _c(colour, f"  Detail: {msg}") + "\n" +
        _c(colour, "=" * 60) + "\n"
    )
    print(banner)


def fire_webhook_alert(alert: dict, webhook_url: str) -> None:
    """POST alert payload to webhook URL. Logs warning on delivery failure — never raises."""
    if httpx is None:
        print("  [alert] webhook skipped — httpx not installed", file=sys.stderr)
        return
    try:
        resp = httpx.post(
            webhook_url,
            json=alert,
            timeout=10.0,
            headers={"Content-Type": "application/json"},
        )
        if resp.status_code >= 400:
            print(
                f"  [alert] webhook delivery returned HTTP {resp.status_code} "
                f"for slug={alert['check_name']}",
                file=sys.stderr,
            )
    except httpx.HTTPError as e:
        # Delivery failure is non-fatal — log and move on; don't crash the canary.
        print(f"  [alert] webhook delivery failed for slug={alert['check_name']}: {e}",
              file=sys.stderr)


def dispatch_alerts(
    alerts: list[dict],
    alert_mode: str,
    webhook_url: str | None,
) -> None:
    """Route each alert to the appropriate channel(s)."""
    if alert_mode == "none" or not alerts:
        return

    for alert in alerts:
        if alert_mode in ("console", "both"):
            fire_console_alert(alert)
        if alert_mode in ("webhook", "both"):
            if webhook_url:
                fire_webhook_alert(alert, webhook_url)
            else:
                print(
                    "  [alert] webhook mode requested but no URL provided "
                    "(--webhook-url or MOBILE_CANARY_WEBHOOK_URL)",
                    file=sys.stderr,
                )


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--dry-run", action="store_true",
                        help="Parse registry, do not make HTTP calls.")
    parser.add_argument("--timeout", type=float, default=10.0,
                        help="Per-request timeout in seconds (default 10).")
    parser.add_argument("--max-workers", type=int, default=8,
                        help="Thread pool size (default 8).")
    parser.add_argument(
        "--alert",
        choices=["none", "console", "webhook", "both"],
        default="console",
        help="Alert delivery mode (default: console).",
    )
    parser.add_argument(
        "--webhook-url",
        default=os.environ.get("MOBILE_CANARY_WEBHOOK_URL"),
        help="Webhook URL for alert POSTs (or env MOBILE_CANARY_WEBHOOK_URL).",
    )
    parser.add_argument(
        "--alert-threshold",
        type=int,
        default=3,
        metavar="N",
        help="Fire alert every N consecutive failures even without a transition (default 3).",
    )
    parser.add_argument(
        "--silence-first-run",
        action="store_true",
        default=False,
        help=(
            "When set, a check whose slug has never appeared in the state file will not "
            "fire an alert on its very first observed failure. The failure is recorded in "
            "state, so subsequent runs apply normal threshold rules. Recommended when "
            "adding new apps to registry.json to avoid noisy first-run alerts. "
            "Default off for backwards compatibility."
        ),
    )
    args = parser.parse_args()

    registry = load_registry()
    apps = registry.get("apps", [])
    print(f"mobile_app_canary: {len(apps)} app(s) in registry "
          f"(dry_run={args.dry_run}, timeout={args.timeout}s, "
          f"alert={args.alert}, threshold={args.alert_threshold})")

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

    # State dedup + alert dispatch
    now_iso = datetime.now(timezone.utc).isoformat()
    prior_state = load_state()

    # Only include pingable results (exclude missing-health-url) in state tracking
    pingable_results = {
        slug: r for slug, r in results.items()
        if r.get("status") not in ("missing-health-url",)
    }
    updated_checks, alerts = compute_alerts(
        pingable_results, prior_state, args.alert_threshold, now_iso,
        silence_first_run=args.silence_first_run,
    )

    new_state = {
        "last_run_at": now_iso,
        "checks": updated_checks,
    }
    save_state(new_state)

    dispatch_alerts(alerts, args.alert, args.webhook_url)

    summary = {
        "timestamp": now_iso,
        "dry_run": False,
        "counts": {"green": n_green, "red": n_red, "missing": n_missing,
                   "total": len(apps)},
        "alerts_fired": len(alerts),
        "results": list(results.values()),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 1 if n_red else 0


if __name__ == "__main__":
    sys.exit(main())
