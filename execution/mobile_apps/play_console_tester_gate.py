"""
play_console_tester_gate.py
description: Pure date-math reader over registry.json — zero Google API calls. For each app, computes days_remaining toward the Google 20-tester / 14-day gate and reports gate_open status. Supports `--set-started` and `--set-count` to manually update the gate fields from Play Console.
inputs: CLI: --app <slug> (optional, defaults to all), --set-started <slug>, --set-count <slug> <n>; reads execution/mobile_apps/registry.json
outputs: Human-readable gate status to stdout; mutates registry.json on --set-* commands
usage:
    py execution/mobile_apps/play_console_tester_gate.py
    py execution/mobile_apps/play_console_tester_gate.py --app my-app
    py execution/mobile_apps/play_console_tester_gate.py --set-started my-app
    py execution/mobile_apps/play_console_tester_gate.py --set-count my-app 12
"""

import argparse
import json
import os
import sys
import threading
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

# Concurrent-write guard for REGISTRY_PATH; see bootstrap_mobile_app.py for rationale.
_REGISTRY_WRITE_LOCK = threading.Lock()

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"

GATE_DAYS = 14
GATE_TESTERS = 20


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


def find_app_idx(registry: dict, slug: str) -> int:
    for i, app in enumerate(registry.get("apps", [])):
        if app.get("slug") == slug:
            return i
    return -1


def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        # Accept full ISO timestamps or YYYY-MM-DD.
        if "T" in value:
            return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
        return date.fromisoformat(value)
    except ValueError as e:
        print(f"  warn: cannot parse date '{value}': {e}", file=sys.stderr)
        return None


def compute_gate(app: dict, today: date) -> dict:
    started = parse_iso_date(app.get("play_tester_gate_started_at"))
    count_raw = app.get("play_tester_count_manual")
    count = int(count_raw) if isinstance(count_raw, int) else 0

    if started is None:
        days_elapsed = None
        days_remaining = None
    else:
        days_elapsed = (today - started).days
        days_remaining = max(0, GATE_DAYS - days_elapsed)

    testers_needed = max(0, GATE_TESTERS - count)
    gate_open = (
        started is not None
        and days_remaining == 0
        and testers_needed == 0
    )
    return {
        "started_at": started.isoformat() if started else None,
        "days_elapsed": days_elapsed,
        "days_remaining": days_remaining,
        "tester_count": count,
        "testers_needed": testers_needed,
        "gate_open": gate_open,
    }


def report_app(app: dict, today: date) -> None:
    gate = compute_gate(app, today)
    slug = app.get("slug", "<no-slug>")
    print(f"\n[{slug}]")
    if gate["started_at"] is None:
        print("  status: gate-not-started (call --set-started when uploading internal build)")
    print(f"  started_at      : {gate['started_at']}")
    print(f"  days_elapsed    : {gate['days_elapsed']}")
    print(f"  days_remaining  : {gate['days_remaining']}")
    print(f"  tester_count    : {gate['tester_count']} / {GATE_TESTERS}")
    print(f"  testers_needed  : {gate['testers_needed']}")
    print(f"  gate_open       : {gate['gate_open']}")


def cmd_set_started(slug: str) -> int:
    registry = load_registry()
    idx = find_app_idx(registry, slug)
    if idx < 0:
        print(f"ERROR: app '{slug}' not in registry.", file=sys.stderr)
        return 2
    today_iso = datetime.now(timezone.utc).date().isoformat()
    registry["apps"][idx]["play_tester_gate_started_at"] = today_iso
    write_registry_atomic(registry)
    print(f"Set play_tester_gate_started_at={today_iso} for {slug}")
    return 0


def cmd_set_count(slug: str, n: int) -> int:
    if n < 0:
        print("ERROR: count must be >= 0", file=sys.stderr)
        return 2
    registry = load_registry()
    idx = find_app_idx(registry, slug)
    if idx < 0:
        print(f"ERROR: app '{slug}' not in registry.", file=sys.stderr)
        return 2
    registry["apps"][idx]["play_tester_count_manual"] = n
    write_registry_atomic(registry)
    print(f"Set play_tester_count_manual={n} for {slug}")
    return 0


def cmd_report(slug: str | None) -> int:
    registry = load_registry()
    apps = registry.get("apps", [])
    if slug:
        target = [a for a in apps if a.get("slug") == slug]
        if not target:
            print(f"ERROR: app '{slug}' not in registry.", file=sys.stderr)
            return 2
        apps = target
    if not apps:
        print("(no apps in registry)")
        return 0

    today = datetime.now(timezone.utc).date()
    print(f"Play Console tester gate (today={today.isoformat()}, "
          f"target={GATE_TESTERS} testers / {GATE_DAYS} days):")
    for app in apps:
        report_app(app, today)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--app", help="Report only this app slug.")
    parser.add_argument("--set-started", metavar="SLUG",
                        help="Set play_tester_gate_started_at = today (UTC) for this slug.")
    parser.add_argument("--set-count", nargs=2, metavar=("SLUG", "N"),
                        help="Set play_tester_count_manual = N for this slug.")
    args = parser.parse_args()

    if args.set_started:
        return cmd_set_started(args.set_started)

    if args.set_count:
        slug, n_str = args.set_count
        try:
            n = int(n_str)
        except ValueError:
            print(f"ERROR: count '{n_str}' is not an integer.", file=sys.stderr)
            return 2
        return cmd_set_count(slug, n)

    return cmd_report(args.app)


if __name__ == "__main__":
    sys.exit(main())
