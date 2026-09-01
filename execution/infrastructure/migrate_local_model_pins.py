"""
description: One-shot local follow-up of the 2026-09-01 Fable 5.1 migration. On the
             Windows machine only, rewrites the "model" pin claude-fable-5 ->
             claude-fable-5-1 in ~/.claude/settings.json and the workspace's
             .claude/settings.local.json (the two files that override the repo pin),
             and appends the tier-doctrine note to ~/.claude/rules/model-tier.md.
             Invoked by .claude/hooks/session-start.sh; safe to run by hand.
inputs: No CLI args. Env: OS / USERPROFILE (Windows detection), HOME. Reads the two
        settings files and model-tier.md if present.
outputs: Rewrites the files above (only while the pin still says claude-fable-5);
         one-shot stamp .tmp/model_pin_migrated_fable51 so the documented revert in
         .claude/SETTINGS_NOTES.md is never flipped back; append-only change log
         .tmp/model_pin_migration.log; a one-line summary on stdout (empty if no-op).
"""

from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

OLD_PIN = "claude-fable-5"
NEW_PIN = "claude-fable-5-1"

_WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
_STAMP = _WORKSPACE_ROOT / ".tmp" / "model_pin_migrated_fable51"
_LOG = _WORKSPACE_ROOT / ".tmp" / "model_pin_migration.log"

_TIER_NOTE = """

## 2026-09-01 — judgement tier is claude-fable-5-1
Auto-appended by the workspace's one-shot pin migration (session-start hook).
The judgement/premium tier and Claude Code session default moved claude-fable-5 ->
claude-fable-5-1 (same $10/$50 per MTok; cache reads now $0.25/MTok). Doctrine
unchanged: "Fable thinks, Sonnet works" — grunt work stays on claude-sonnet-5
sub-agents. Details and the one-line revert: the workspace's
.claude/SETTINGS_NOTES.md (2026-09-01 migration entry).
"""


def _is_windows_machine() -> bool:
    """The migration targets the operator's Windows files only — cloud/Linux
    containers manage their own settings and must never be touched here."""
    return os.name == "nt" or os.environ.get("OS") == "Windows_NT" or bool(
        os.environ.get("USERPROFILE")
    )


def _migrate_pin(path: Path) -> str | None:
    """Rewrite the model pin in one settings file; None if nothing to do.

    Text-level replace of the exact quoted ID (preserves formatting/comments-free
    JSON layout), guarded twice: only runs while data["model"] is the old pin, and
    the result must re-parse as JSON or nothing is written.
    """
    try:
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except Exception:
        return None  # unreadable/unparsable: leave the file alone
    if data.get("model") != OLD_PIN:
        return None  # already migrated, deliberately reverted, or pinned elsewhere
    new_text = text.replace(f'"{OLD_PIN}"', f'"{NEW_PIN}"')
    try:
        json.loads(new_text)
    except Exception:
        return None  # refuse to write anything that no longer parses
    path.write_text(new_text, encoding="utf-8", newline="")
    return f"{path.name}: model pin -> {NEW_PIN}."


def main() -> int:
    if not _is_windows_machine() or _STAMP.exists():
        return 0

    home = Path(os.environ.get("HOME") or os.environ.get("USERPROFILE") or "~").expanduser()
    user_claude = home / ".claude"
    actions: list[str] = []

    for pin_file in (user_claude / "settings.json",
                     _WORKSPACE_ROOT / ".claude" / "settings.local.json"):
        if pin_file.is_file():
            note = _migrate_pin(pin_file)
            if note:
                actions.append(note)

    tier_md = user_claude / "rules" / "model-tier.md"
    try:
        if tier_md.is_file() and NEW_PIN not in tier_md.read_text(encoding="utf-8"):
            with tier_md.open("a", encoding="utf-8", newline="") as f:
                f.write(_TIER_NOTE)
            actions.append("model-tier.md: doctrine note appended.")
    except Exception as exc:
        # Non-fatal: the pins are the load-bearing part; the note is advisory.
        print(f"model-tier.md append skipped: {exc}", file=sys.stderr)

    if actions:
        summary = " ".join(actions)
        stamp_line = f"{datetime.now(timezone.utc).isoformat()} {summary}\n"
        _LOG.parent.mkdir(parents=True, exist_ok=True)
        with _LOG.open("a", encoding="utf-8") as f:
            f.write(stamp_line)
        _STAMP.write_text(stamp_line, encoding="utf-8")
        print(summary)
    return 0


if __name__ == "__main__":
    sys.exit(main())
