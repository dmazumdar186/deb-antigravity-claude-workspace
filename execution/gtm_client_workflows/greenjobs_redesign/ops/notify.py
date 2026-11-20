"""Outbox-first notifier for the GreenJobs ops scripts (dry-run by default).

description: Every message is first written to an outbox JSONL keyed by a
  stable dedupe key (a key already in the outbox is never queued or sent
  again). Live delivery through Resend happens only when the caller passes
  send=True AND RESEND_API_KEY, OPS_MAIL_FROM and the recipient's env var are
  set AND the template's sha256 is listed in approved_templates.json (written
  only after the template passed /redteam) AND the per-run cap is not reached.
  Each live send appends a cost-ledger row (Resend free tier: 0.00).
inputs: env RESEND_API_KEY, OPS_MAIL_FROM, recipient env vars (OPS_ALERT_EMAIL, DIANA_EMAIL)
outputs: <state>/outbox.jsonl, <state>/cost_ledger.jsonl; HTTPS POST api.resend.com only when live
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path
from typing import Any, Callable

sys.path.insert(0, str(Path(__file__).resolve().parent))

import common as C  # noqa: E402

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # cloud sessions have env vars only; dotenv is optional
    pass

APPROVED = Path(__file__).resolve().parent / "approved_templates.json"
CLIENT_FACING = {"diana_dns_done"}  # outward text: live only once its hash is in approved_templates.json (/redteam)
MAX_LIVE_SENDS_PER_RUN = 12  # budget guard: 10 domains + 2 alerts


def template_sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def approved(template_id: str, template_text: str) -> bool:
    data = C.read_json(APPROVED, {}) or {}
    return template_sha(template_text) in (data.get(template_id) or [])


def _resend_post(payload: dict[str, Any], key: str) -> tuple[int, str]:
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "GreenJobsOps/1.0",
        },
    )
    try:
        with urllib.request.urlopen(
            req, timeout=15
        ) as r:  # noqa: S310 (fixed https host)
            return r.status, ""
    except urllib.error.HTTPError as e:
        return e.code, f"HTTP {e.code}"
    except (
        Exception
    ) as e:  # network failure: recorded as a failed send, the outbox row stays for the next run
        return 0, type(e).__name__


class Notifier:
    def __init__(
        self,
        state_dir: Path,
        send: bool = False,
        post: Callable[[dict[str, Any], str], tuple[int, str]] = _resend_post,
    ):
        self.state = Path(state_dir)
        self.outbox = self.state / "outbox.jsonl"
        self.ledger = self.state / "cost_ledger.jsonl"
        self.send = send
        self.post = post
        self.live_sent = 0

    def keys(self) -> set[str]:
        """Keys already handled in this mode: a live run skips only keys SENT live (a dry-run draft does
        not consume the live send); a dry run skips any key already drafted or sent."""
        rows = C.read_jsonl(self.outbox)
        if self.send:
            return {r["key"] for r in rows if r.get("mode") == "sent"}
        return {r["key"] for r in rows}

    def queue(
        self,
        key: str,
        to_env: str,
        subject: str,
        body: str,
        template_id: str,
        template_text: str,
    ) -> str:
        """'duplicate' | 'drafted' | 'sent' | 'send_failed' | 'blocked:<reason>'. Never sends a key twice."""
        if key in self.keys():
            return "duplicate"
        row = {
            "key": key,
            "at": C.now_iso(),
            "to_env": to_env,
            "subject": subject,
            "body": body,
            "template": template_id,
            "mode": "dry_run",
        }
        status = "drafted"
        if self.send:
            reason = self._blocked(to_env, template_id, template_text)
            if reason:
                return f"blocked:{reason}"  # not recorded: the next live run tries again once the gap is fixed
            else:
                code, err = self.post(
                    {
                        "from": os.environ["OPS_MAIL_FROM"],
                        "to": [os.environ[to_env]],
                        "subject": subject,
                        "text": body,
                    },
                    os.environ["RESEND_API_KEY"],
                )
                self.live_sent += 1
                status = "sent" if 200 <= code < 300 else "send_failed"
                C.append_jsonl(
                    self.ledger,
                    {
                        "at": C.now_iso(),
                        "service": "resend",
                        "units": 1,
                        "cost_usd": 0.00,
                        "key": key,
                        "status": status,
                        "error": err,
                    },
                )
                if status == "send_failed":
                    return status  # not recorded in the outbox: the next run retries this key
            row["mode"] = status
        C.append_jsonl(self.outbox, row)
        return status

    def _blocked(self, to_env: str, template_id: str, template_text: str) -> str:
        for var in ("RESEND_API_KEY", "OPS_MAIL_FROM", to_env):
            if not os.environ.get(var):
                return f"{var} not set"
        if template_id in CLIENT_FACING and not approved(template_id, template_text):
            return "template not red-team approved"
        if self.live_sent >= MAX_LIVE_SENDS_PER_RUN:
            return "per-run send cap reached"
        return ""
