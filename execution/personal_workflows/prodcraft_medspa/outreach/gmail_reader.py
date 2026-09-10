"""
gmail_reader.py
description: Read inbound Gmail replies for scan_replies.py. Live path uses the Gmail API
    (users.threads.get / users.messages.list); --mock reads outreach/fixtures/inbox/*.json.
inputs: Imported by scan_replies.py. Live: env GMAIL_TOKEN_JSON (see gmail_drafts.py for the
    shared auth pattern). Mock: fixtures_root/inbox/*.json.
outputs: list[dict] reply records: {"thread_id", "from", "to", "subject", "body_text",
    "received_at"}; no writes.
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

# Strips common quoted-history markers ("On ... wrote:", "-----Original Message-----", leading
# ">" quote lines) so classify_reply.md only sees the new text, not the whole thread.
_QUOTE_HEADER_RE = re.compile(r"\nOn .{0,120} wrote:\s*$", re.MULTILINE)
_ORIGINAL_MSG_RE = re.compile(r"-{2,}\s*Original Message\s*-{2,}.*", re.DOTALL | re.IGNORECASE)


def strip_quoted_history(body_text: str) -> str:
    """Best-effort trim of quoted reply history from a plain-text email body."""
    text = _ORIGINAL_MSG_RE.split(body_text, maxsplit=1)[0]
    lines = text.splitlines()
    kept: list[str] = []
    for line in lines:
        if line.strip().startswith(">"):
            break  # quoted block begins — everything after is the previous message
        kept.append(line)
    trimmed = "\n".join(kept)
    trimmed = _QUOTE_HEADER_RE.sub("", trimmed)
    return trimmed.strip()


def load_mock_inbox(fixtures_root: Path) -> list[dict]:
    """Load every outreach/fixtures/inbox/*.json fixture reply, sorted by filename."""
    inbox_dir = fixtures_root / "inbox"
    if not inbox_dir.is_dir():
        return []
    records = []
    for path in sorted(inbox_dir.glob("*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        record.setdefault("body_text", strip_quoted_history(record.get("raw_body_text", record.get("body_text", ""))))
        records.append(record)
    return records


def _get_credentials(settings: Any):
    """Reuse gmail_drafts.py's auth so both modules share one token cache and refresh path."""
    from execution.personal_workflows.prodcraft_medspa.outreach.gmail_drafts import _get_credentials as _creds

    return _creds(settings)


def search_replies(*, owner_email: str, since_days: int, settings: Any) -> list[dict]:
    """Live: search `from:{owner_email} newer_than:{since_days}d`, return one record per message."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Gmail reply scanning requires google-api-python-client. "
            "Install with: pip install google-api-python-client"
        ) from exc

    creds = _get_credentials(settings)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    query = f"from:{owner_email} newer_than:{since_days}d"
    resp = service.users().messages().list(userId="me", q=query).execute()
    records: list[dict] = []
    for msg_meta in resp.get("messages", []):
        msg = service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
        records.append(_parse_message(msg))
    return records


def get_thread_messages(*, thread_id: str, settings: Any) -> list[dict]:
    """Live: fetch every message in a Gmail thread."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Gmail reply scanning requires google-api-python-client. "
            "Install with: pip install google-api-python-client"
        ) from exc

    creds = _get_credentials(settings)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
    return [_parse_message(m) for m in thread.get("messages", [])]


def _header(headers: list[dict], name: str) -> str:
    for h in headers:
        if h.get("name", "").lower() == name.lower():
            return h.get("value", "")
    return ""


def _extract_plain_text(payload: dict) -> str:
    import base64

    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")
    for part in payload.get("parts", []) or []:
        text = _extract_plain_text(part)
        if text:
            return text
    return ""


def _parse_message(msg: dict) -> dict:
    payload = msg.get("payload", {})
    headers = payload.get("headers", [])
    raw_body = _extract_plain_text(payload)
    return {
        "thread_id": msg.get("threadId"),
        "message_id": msg.get("id"),
        "from": _header(headers, "From"),
        "to": _header(headers, "To"),
        "subject": _header(headers, "Subject"),
        "body_text": strip_quoted_history(raw_body),
        "received_at": _header(headers, "Date"),
    }
