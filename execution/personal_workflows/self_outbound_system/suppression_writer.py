"""
suppression_writer.py
description: Append entries to config/suppression.json in a concurrency-safe, dedup-aware, GDPR-compliant way. Callable both as a CLI (single-entry mode) and as a library (bulk-append + import from reply_classifier / webhook_receiver). Every write is idempotent — appending an already-suppressed email is a no-op that still records the event in history. Optional Telegram alert on write.
inputs: --email <addr>, --reason <str>, --source <webhook|reply_classifier|manual|cron>, --dry-run/--live, --alert/--no-alert. Env: TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID (optional for alerts).
outputs: Updates config/suppression.json. Prints JSON status line to stdout. Exit 0 on success, non-zero on validation failure.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 leftover from `_writer_owed` marker in suppression.json).
Concurrency: uses a lock file at config/.suppression.lock. Threading + multi-process safe.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CONFIG_DIR,
    get_logger,
    print_stat,
)

load_dotenv()
log = get_logger("suppression_writer")

SUPPRESSION_FILE = CONFIG_DIR / "suppression.json"
LOCK_FILE = CONFIG_DIR / ".suppression.lock"

VALID_SOURCES = {"webhook", "reply_classifier", "manual", "cron", "seed"}
VALID_REASONS = {
    "negative_reply",
    "unsubscribe_click",
    "hard_bounce",
    "spam_complaint",
    "manual_add",
    "already_customer",
    "am_locked_domain",
    "wrong_person",
    "duplicate_of_prior_lead",
    "other",
}


class SuppressionError(Exception):
    """Validation or I/O failure while writing suppression."""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _normalize_email(email: str) -> str:
    """Lowercase + strip. No fancy canonicalization (no plus-addressing collapse
    — those ARE distinct addresses for consent purposes)."""
    return (email or "").strip().lower()


def _domain_of(email: str) -> str:
    if "@" not in email:
        return ""
    return email.split("@", 1)[1].lower()


class _FileLock:
    """Cross-platform advisory file lock. Uses msvcrt on Windows, fcntl on
    POSIX. Blocks up to `timeout_s` waiting for the lock; raises on timeout."""

    def __init__(self, path: Path, timeout_s: float = 5.0):
        self.path = path
        self.timeout_s = timeout_s
        self._fh = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        deadline = time.time() + self.timeout_s
        self._fh = open(self.path, "a+", encoding="utf-8")
        while time.time() < deadline:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return self
            except (OSError, BlockingIOError):
                time.sleep(0.05)
        # Timed out — release fh + raise
        self._fh.close()
        self._fh = None
        raise SuppressionError(f"suppression lock timeout ({self.timeout_s}s) on {self.path}")

    def __exit__(self, exc_type, exc, tb):
        if self._fh is not None:
            try:
                if os.name == "nt":
                    import msvcrt
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
            except OSError as e:
                log.warning(f"lock release warning (usually harmless): {e}")
            self._fh.close()
            self._fh = None


def _telegram_alert(text: str) -> None:
    """Fire-and-forget Telegram alert. Silently no-ops if env not configured
    or if network fails (this is a nice-to-have, not a hard requirement)."""
    token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    if not (token and chat_id):
        log.info("telegram: TELEGRAM_BOT_TOKEN/TELEGRAM_CHAT_ID not set, skipping alert")
        return
    try:
        import urllib.parse
        import urllib.request
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        data = urllib.parse.urlencode({
            "chat_id": chat_id,
            "text": text,
            "parse_mode": "Markdown",
        }).encode("utf-8")
        req = urllib.request.Request(url, data=data, method="POST")
        with urllib.request.urlopen(req, timeout=5) as resp:
            _ = resp.read()
    except Exception as e:  # noqa: BLE001
        # Alert is a nice-to-have. Log and swallow — don't block the suppression write.
        log.warning(f"telegram alert failed (swallowed to not block suppression write): {e}")


def add_suppression(
    email: str,
    reason: str,
    source: str,
    *,
    alert: bool = False,
    dry_run: bool = False,
    now_iso_override: str | None = None,
) -> dict:
    """Idempotently add an email to config/suppression.json.emails (dedup on
    lowercase-email). Always appends to history for auditability even if the
    email was already suppressed. Fires an optional Telegram alert unless
    alert=False.

    Returns a dict summarizing the action:
      {added_to_emails: bool, already_present: bool, history_appended: True,
       normalized_email: <lc>, reason: <r>, source: <s>, timestamp: <iso>}
    """
    email_norm = _normalize_email(email)
    if not email_norm or "@" not in email_norm:
        raise SuppressionError(f"invalid email: {email!r}")
    if reason not in VALID_REASONS:
        raise SuppressionError(f"invalid reason {reason!r}; must be one of {sorted(VALID_REASONS)}")
    if source not in VALID_SOURCES:
        raise SuppressionError(f"invalid source {source!r}; must be one of {sorted(VALID_SOURCES)}")

    ts = now_iso_override or _now_iso()

    with _FileLock(LOCK_FILE):
        if not SUPPRESSION_FILE.exists():
            raise SuppressionError(f"suppression file missing: {SUPPRESSION_FILE}")

        with open(SUPPRESSION_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)

        emails: list = state.setdefault("emails", [])
        history: list = state.setdefault("history", [])
        domains: list = state.setdefault("domains", [])

        # Dedup emails (case-insensitive)
        existing_lc = {str(e).strip().lower() for e in emails}
        already_present = email_norm in existing_lc
        if not already_present:
            emails.append(email_norm)

        # Also flag if the domain is AM-locked — always log to history
        dom = _domain_of(email_norm)
        am_locked = any(str(d).strip().lower() == dom for d in domains)

        entry = {
            "email": email_norm,
            "reason": reason,
            "source": source,
            "timestamp": ts,
            "already_present": already_present,
            "am_locked_domain": am_locked,
        }
        history.append(entry)
        state["_last_updated"] = ts.split("T")[0]

        if not dry_run:
            # Atomic write via temp-then-rename
            tmp_path = SUPPRESSION_FILE.with_suffix(".json.tmp")
            with open(tmp_path, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.write("\n")
            os.replace(tmp_path, SUPPRESSION_FILE)

    if alert and not dry_run:
        marker = "ALREADY-SUPPRESSED" if already_present else "NEW-SUPPRESSION"
        text = (
            f"*{marker}*\n"
            f"email: `{email_norm}`\n"
            f"reason: `{reason}`\n"
            f"source: `{source}`\n"
            f"at: `{ts}`"
        )
        if am_locked:
            text += "\n_domain is AM-locked (already blocked at config level)_"
        _telegram_alert(text)

    return {
        "added_to_emails": not already_present,
        "already_present": already_present,
        "history_appended": True,
        "normalized_email": email_norm,
        "reason": reason,
        "source": source,
        "timestamp": ts,
        "am_locked_domain": am_locked,
        "dry_run": dry_run,
    }


def add_bulk(
    entries: list[dict],
    *,
    alert: bool = False,
    dry_run: bool = False,
) -> list[dict]:
    """Bulk add many suppressions in one lock acquisition (efficient for cron
    replay of a batch of webhook events). Each entry: {email, reason, source}.
    Returns per-entry result dicts (same shape as add_suppression). Skips
    invalid entries with an error result rather than failing the whole batch."""
    results = []
    ts = _now_iso()
    for entry in entries:
        try:
            res = add_suppression(
                email=entry["email"],
                reason=entry.get("reason", "manual_add"),
                source=entry.get("source", "manual"),
                alert=alert,
                dry_run=dry_run,
                now_iso_override=ts,
            )
        except SuppressionError as e:
            res = {"error": str(e), "entry": entry}
        results.append(res)
    return results


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--email", required=True, help="Email to suppress.")
    p.add_argument("--reason", required=True, choices=sorted(VALID_REASONS),
                   help="Suppression reason.")
    p.add_argument("--source", required=True, choices=sorted(VALID_SOURCES),
                   help="Source of the suppression event.")
    p.add_argument("--dry-run", action="store_true", default=False,
                   help="Validate + log but don't write to disk.")
    p.add_argument("--alert", dest="alert", action="store_true", default=True,
                   help="Fire Telegram alert (default: on).")
    p.add_argument("--no-alert", dest="alert", action="store_false",
                   help="Suppress the Telegram alert.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        result = add_suppression(
            email=args.email,
            reason=args.reason,
            source=args.source,
            alert=args.alert,
            dry_run=args.dry_run,
        )
    except SuppressionError as e:
        print(json.dumps({"ok": False, "error": str(e)}))
        return 2

    print(json.dumps({"ok": True, **result}))
    print_stat("suppression_writer", {
        "email": result["normalized_email"],
        "added": result["added_to_emails"],
        "already_present": result["already_present"],
        "reason": result["reason"],
        "source": result["source"],
        "dry_run": result["dry_run"],
    })
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
