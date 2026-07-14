"""
sync_suppression_from_kv.py
description: Pull buffered suppression events from the Cloudflare Worker's KV namespace (SUPP_EVENTS), call suppression_writer.add_bulk() to sync them into config/suppression.json, then delete consumed keys from KV. Cron this on the daily pipeline so webhook events land in the local suppression list within hours.
inputs: --wrangler-dir <path to worker>, --binding <SUPP_EVENTS>, --dry-run/--live. Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional).
outputs: Updates config/suppression.json via suppression_writer. Prints a summary stat line. Exit 0 on success.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 sync loop).
Runs `wrangler kv key list/get/delete` as subprocesses because the Cloudflare KV REST API requires an account-scoped API token (extra setup) whereas wrangler is already authed from the operator's local CLI. Every subprocess uses UTF-8 per ~/.claude/rules/python-hardening.md rule 1.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    ROOT,
    get_logger,
    print_stat,
)
from suppression_writer import add_bulk  # noqa: E402

load_dotenv()
log = get_logger("sync_suppression")

# Default wrangler working dir — the Worker project root
_DEFAULT_WRANGLER_DIR = ROOT.parents[2] / "execution" / "infrastructure" / "self_outbound_webhook_worker"
_DEFAULT_BINDING = "SUPP_EVENTS"
_KEY_PREFIX = "event:"


def _run_wrangler(args: list[str], wrangler_dir: Path) -> str:
    """Run a wrangler subcommand and return stdout. Fails loudly on non-zero."""
    cmd = ["wrangler", *args]
    log.info(f"wrangler: {' '.join(cmd)} (cwd={wrangler_dir})")
    proc = subprocess.run(
        cmd,
        cwd=str(wrangler_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"wrangler {' '.join(args)} failed (rc={proc.returncode}):\n"
            f"stdout: {proc.stdout[:500]}\nstderr: {proc.stderr[:500]}"
        )
    return proc.stdout


def _list_kv_keys(binding: str, wrangler_dir: Path, prefix: str = _KEY_PREFIX) -> list[str]:
    """List KV keys under a given prefix via `wrangler kv key list`.
    Returns a list of key names (strings)."""
    out = _run_wrangler(
        ["kv", "key", "list", f"--binding={binding}", f"--prefix={prefix}"],
        wrangler_dir,
    )
    # wrangler outputs JSON array of {name: ..., expiration: ...}
    try:
        items = json.loads(out)
    except json.JSONDecodeError:
        # Some wrangler versions emit non-JSON; try to extract keys line by line
        return [line.strip() for line in out.splitlines() if line.strip().startswith(prefix)]
    if not isinstance(items, list):
        return []
    return [it["name"] for it in items if isinstance(it, dict) and it.get("name", "").startswith(prefix)]


def _get_kv_value(key: str, binding: str, wrangler_dir: Path) -> dict | None:
    """Fetch a single KV value. Returns parsed JSON dict or None on parse failure."""
    out = _run_wrangler(
        ["kv", "key", "get", key, f"--binding={binding}"],
        wrangler_dir,
    )
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        log.warning(f"could not JSON-parse KV value for {key}: {out[:200]}")
        return None


def _delete_kv_key(key: str, binding: str, wrangler_dir: Path) -> None:
    """Delete a KV key after successful sync. Non-fatal on error — TTL of 30d
    is the backstop."""
    try:
        _run_wrangler(
            ["kv", "key", "delete", key, f"--binding={binding}"],
            wrangler_dir,
        )
    except RuntimeError as e:
        # Non-fatal: the KV entry will expire in 30d and future syncs are
        # idempotent (suppression_writer dedups by email). Log so the operator
        # can spot recurring delete failures.
        log.warning(f"kv key delete failed for {key} (non-fatal): {e}")


def sync(binding: str, wrangler_dir: Path, dry_run: bool = False) -> dict:
    """Full sync loop: list -> get each -> add_bulk -> delete consumed keys.
    Returns a summary dict."""
    if not wrangler_dir.exists():
        raise RuntimeError(f"wrangler dir not found: {wrangler_dir}")

    log.info(f"listing KV keys under {_KEY_PREFIX}...")
    keys = _list_kv_keys(binding, wrangler_dir)
    log.info(f"found {len(keys)} pending event keys")

    entries: list[dict] = []
    key_by_email: dict[str, list[str]] = {}
    for k in keys:
        val = _get_kv_value(k, binding, wrangler_dir)
        if not val:
            log.warning(f"skipping empty/unreadable key {k}")
            continue
        entry = {
            "email": val.get("email", ""),
            "reason": val.get("reason", "other"),
            "source": val.get("source") or "webhook",
        }
        if not entry["email"]:
            log.warning(f"skipping key {k} with no email")
            continue
        entries.append(entry)
        key_by_email.setdefault(entry["email"].lower().strip(), []).append(k)

    if not entries:
        log.info("no entries to sync")
        return {"synced": 0, "keys_deleted": 0, "keys_failed_delete": 0, "dry_run": dry_run}

    log.info(f"syncing {len(entries)} entries via suppression_writer.add_bulk (dry_run={dry_run})")
    # Alerts already fired from the Worker; suppress double-alerts on sync.
    results = add_bulk(entries, alert=False, dry_run=dry_run)

    keys_deleted = 0
    keys_failed_delete = 0
    if not dry_run:
        for res in results:
            if "error" in res:
                continue
            email = res.get("normalized_email", "")
            for k in key_by_email.get(email, []):
                try:
                    _delete_kv_key(k, binding, wrangler_dir)
                    keys_deleted += 1
                except RuntimeError:
                    keys_failed_delete += 1

    return {
        "synced": len(results),
        "keys_deleted": keys_deleted,
        "keys_failed_delete": keys_failed_delete,
        "dry_run": dry_run,
        "results": results,
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--wrangler-dir", type=Path, default=_DEFAULT_WRANGLER_DIR,
                   help="Path to the Worker project (must have wrangler.toml).")
    p.add_argument("--binding", type=str, default=_DEFAULT_BINDING,
                   help=f"KV binding name (default: {_DEFAULT_BINDING}).")
    p.add_argument("--dry-run", action="store_true", default=False,
                   help="List + parse but don't write to suppression.json or delete KV keys.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        summary = sync(args.binding, args.wrangler_dir, dry_run=args.dry_run)
    except RuntimeError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2

    print_stat("sync_suppression", {
        "synced": summary["synced"],
        "keys_deleted": summary["keys_deleted"],
        "keys_failed_delete": summary["keys_failed_delete"],
        "dry_run": summary["dry_run"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
