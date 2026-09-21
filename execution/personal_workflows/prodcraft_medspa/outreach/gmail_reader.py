"""
gmail_reader.py
description: Read inbound Gmail replies for scan_replies.py. Live path uses the Gmail API
    (users.threads.get / users.messages.list); --mock reads outreach/fixtures/inbox/*.json.
inputs: Imported by scan_replies.py. Live: env GMAIL_TOKEN_JSON (see gmail_drafts.py for the
    shared auth pattern). search_replies() also takes an optional gmail_thread_id so replies
    from a different address in the same thread are matched, not just the tracked owner_email.
    Mock: fixtures_root/inbox/*.json.
outputs: list[dict] reply records: {"thread_id", "from", "to", "subject", "body_text",
    "received_at"}; no writes.
"""

from __future__ import annotations

import email.utils
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# Cache of the authenticated Gmail profile's own address, keyed by GMAIL_TOKEN_JSON path (one
# entry per credential set — a session normally only ever uses one, but this keeps two distinct
# settings objects in the same test process from clobbering each other's cached value).
_profile_email_cache: dict[str, str] = {}

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


def _get_profile_email(service: Any, settings: Any) -> str:
    """Fetch (and module-cache) the authenticated Gmail account's own address via
    users().getProfile(), so search_replies can exclude our own outbound messages (C3)."""
    cache_key = str(getattr(settings, "GMAIL_TOKEN_JSON", None) or "default")
    cached = _profile_email_cache.get(cache_key)
    if cached is not None:
        return cached
    profile = service.users().getProfile(userId="me").execute()
    email_address = (profile.get("emailAddress") or "").strip().lower()
    _profile_email_cache[cache_key] = email_address
    return email_address


def _is_own_outbound_message(msg: dict, *, profile_email: str, sender_email: str | None) -> bool:
    """True when `msg` (a raw users().messages().get(format="full") response) is a message WE
    sent — either Gmail labelled it SENT, or its From header matches the authenticated profile
    address or the configured sender address. scan_replies must never classify our own send as
    an inbound reply (code-review C3)."""
    label_ids = msg.get("labelIds") or []
    if "SENT" in label_ids:
        return True
    from_header = _header(msg.get("payload", {}).get("headers", []), "From").lower()
    if profile_email and profile_email in from_header:
        return True
    if sender_email and sender_email.strip().lower() in from_header:
        return True
    return False


def search_replies(
    *,
    owner_email: str = "",
    since_days: int,
    settings: Any,
    thread_id: str | None = None,
    sender_email: str | None = None,
) -> list[dict]:
    """Live: search `from:{owner_email} newer_than:{since_days}d`, plus every message already in
    `thread_id` (when the outreach row has one, from the send step) so a reply sent from a
    different address in that same Gmail thread is still caught. Excludes any message that is
    OUR OWN outbound send (Gmail SENT label, or From matching the authenticated profile address
    or `sender_email` if given) so a self-sent message is never misread as an inbound reply
    (code-review C3). Returns EVERY remaining message as one record each (the caller,
    scan_replies.py, is responsible for idempotency via notes.seen_reply_ids — this function no
    longer truncates to "the last one"), deduped by message_id (thread messages first, then any
    additional from-address matches)."""
    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Gmail reply scanning requires google-api-python-client. "
            "Install with: pip install google-api-python-client"
        ) from exc

    creds = _get_credentials(settings)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)
    profile_email = _get_profile_email(service, settings)

    records: list[dict] = []
    seen_ids: set[str] = set()

    if thread_id:
        thread = service.users().threads().get(userId="me", id=thread_id, format="full").execute()
        for msg in thread.get("messages", []):
            if _is_own_outbound_message(msg, profile_email=profile_email, sender_email=sender_email):
                continue
            record = _parse_message(msg)
            message_id = record.get("message_id")
            if message_id and message_id not in seen_ids:
                seen_ids.add(message_id)
                records.append(record)

    if owner_email:
        query = f"from:{owner_email} newer_than:{since_days}d"
        resp = service.users().messages().list(userId="me", q=query).execute()
        for msg_meta in resp.get("messages", []):
            if msg_meta["id"] in seen_ids:
                continue
            msg = service.users().messages().get(userId="me", id=msg_meta["id"], format="full").execute()
            if _is_own_outbound_message(msg, profile_email=profile_email, sender_email=sender_email):
                continue
            record = _parse_message(msg)
            seen_ids.add(record.get("message_id") or msg_meta["id"])
            records.append(record)

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


def _received_at(headers: list[dict], internal_date: Any) -> str:
    """M4: parse the RFC 2822 `Date` header into a UTC ISO-8601 string; fall back to Gmail's
    own `internalDate` (epoch milliseconds, always present and server-assigned) when the Date
    header is missing or unparseable, rather than passing through a raw, non-ISO header value."""
    date_header = _header(headers, "Date")
    if date_header:
        try:
            parsed = email.utils.parsedate_to_datetime(date_header)
        except (TypeError, ValueError, IndexError):
            parsed = None
        if parsed is not None:
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

    if internal_date not in (None, ""):
        try:
            epoch_ms = int(internal_date)
            return (
                datetime.fromtimestamp(epoch_ms / 1000, tz=timezone.utc)
                .isoformat()
                .replace("+00:00", "Z")
            )
        except (TypeError, ValueError, OverflowError, OSError):
            pass

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
        "received_at": _received_at(headers, msg.get("internalDate")),
    }
