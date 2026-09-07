"""
description: Persistent dedup + email-lock state for job_digest, JSON-file backed
    (no SQLite — this state directory is meant to be git-committed back by the
    friend's own GitHub Actions workflow, so it must stay diffable text).
inputs: list[NormalizedJob] (filter_new/mark_seen); a state directory path.
outputs:
    - state/seen.json: {content_hash: first_seen_iso}, TTL 60 days, swept on save().
    - state/email_lock.txt: ISO timestamp of the last email actually sent.

Both files are written atomically (write to a sibling temp file, then os.replace)
so a crash or a killed CI job can never leave a half-written state file that
corrupts the next run.
"""

from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..contracts import NormalizedJob

logger = logging.getLogger("job_digest.normalizer.state")

DEFAULT_TTL_DAYS = 60

_SEEN_FILENAME = "seen.json"
_EMAIL_LOCK_FILENAME = "email_lock.txt"


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(text)
        os.replace(tmp_name, path)
    except OSError:
        # Best-effort cleanup of the temp file if the replace itself failed.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass  # tmp file already gone or replace partially succeeded — nothing more to clean up
        raise


class State:
    """Dedup (seen.json) + email send-lock (email_lock.txt) for one profile's state dir."""

    def __init__(self, state_dir: Path) -> None:
        self.state_dir = Path(state_dir)
        self.seen_path = self.state_dir / _SEEN_FILENAME
        self.email_lock_path = self.state_dir / _EMAIL_LOCK_FILENAME
        self._seen: dict[str, str] = self._load_seen()

    def _load_seen(self) -> dict[str, str]:
        if not self.seen_path.exists():
            return {}
        try:
            raw = json.loads(self.seen_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("state: seen.json unreadable (%s) — starting empty", exc)
            return {}
        if not isinstance(raw, dict):
            logger.warning("state: seen.json is not a JSON object — starting empty")
            return {}
        return {str(k): str(v) for k, v in raw.items()}

    def filter_new(self, jobs: list[NormalizedJob]) -> list[NormalizedJob]:
        """Return only the jobs whose content_hash is not already recorded as seen.
        Does not mutate state — call mark_seen() separately once the digest is final.
        """
        return [j for j in jobs if j.content_hash not in self._seen]

    def mark_seen(self, jobs: list[NormalizedJob]) -> None:
        """Record each job's content_hash as seen (in-memory). Call save() to persist.
        A job already recorded keeps its original first_seen_at.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        for job in jobs:
            if job.content_hash not in self._seen:
                self._seen[job.content_hash] = now_iso

    def _sweep_expired(self, ttl_days: int) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=ttl_days)
        expired: list[str] = []
        for content_hash, first_seen_iso in self._seen.items():
            try:
                first_seen = datetime.fromisoformat(first_seen_iso)
            except ValueError:
                expired.append(content_hash)  # unparsable timestamp — drop it
                continue
            if first_seen.tzinfo is None:
                first_seen = first_seen.replace(tzinfo=timezone.utc)
            if first_seen < cutoff:
                expired.append(content_hash)
        for content_hash in expired:
            del self._seen[content_hash]
        return len(expired)

    def save(self, ttl_days: int = DEFAULT_TTL_DAYS) -> None:
        """Sweep entries older than ttl_days, then atomically write seen.json."""
        swept = self._sweep_expired(ttl_days)
        if swept:
            logger.info("state: swept %d expired seen-entries (TTL %d days)", swept, ttl_days)
        _atomic_write_text(self.seen_path, json.dumps(self._seen, indent=2, sort_keys=True))

    def email_lock_ok(self, min_hours: float) -> bool:
        """True if enough time has elapsed since the last recorded email send
        (or none was ever recorded) that a new send is allowed.
        """
        if not self.email_lock_path.exists():
            return True
        try:
            raw = self.email_lock_path.read_text(encoding="utf-8").strip()
        except OSError as exc:
            logger.warning("state: email_lock.txt unreadable (%s) — treating as unlocked", exc)
            return True
        if not raw:
            return True
        try:
            last_sent = datetime.fromisoformat(raw)
        except ValueError:
            logger.warning("state: email_lock.txt has an unparsable timestamp (%r) — treating as unlocked", raw)
            return True
        if last_sent.tzinfo is None:
            last_sent = last_sent.replace(tzinfo=timezone.utc)
        elapsed = datetime.now(timezone.utc) - last_sent
        return elapsed >= timedelta(hours=min_hours)

    def set_email_lock(self) -> None:
        """Record 'now' as the last email-sent timestamp. Written immediately
        (atomically) — unlike seen.json, there is no reason to batch this.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        _atomic_write_text(self.email_lock_path, now_iso)
