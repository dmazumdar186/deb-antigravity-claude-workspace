#!/usr/bin/env python3
"""
Inbox Cleaner — AI-Powered Unread Email Triage

Fetches all unread emails from your-work-email@example.com, classifies each one
as important or not using Claude, and marks unimportant ones as read.

Usage:
    python inbox_cleaner.py --fetch        # Fetch unread emails
    python inbox_cleaner.py --classify     # Classify with AI
    python inbox_cleaner.py --review       # Review classifications
    python inbox_cleaner.py --mark-read    # Mark unimportant as read

Environment Variables:
    ANTHROPIC_API_KEY: For classifying emails with Claude
"""

import argparse
import base64
import json
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

CONFIG_DIR = Path(__file__).parent.parent.parent.parent / "active" / "config"
DATA_DIR = Path(__file__).parent.parent.parent.parent / "active"
UNREAD_PATH = DATA_DIR / "inbox_unread.json"
CLASSIFIED_PATH = DATA_DIR / "inbox_classified.json"


def set_account_paths(account: str) -> None:
    """Update file paths for the given account."""
    global UNREAD_PATH, CLASSIFIED_PATH
    UNREAD_PATH = DATA_DIR / f"inbox_unread_{account}.json"
    CLASSIFIED_PATH = DATA_DIR / f"inbox_classified_{account}.json"

ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.modify"]

ACCOUNTS = {
    "yourwork": {
        "email": "your-work-email@example.com",
        "token": CONFIG_DIR / "token_yourwork.json",
        "credentials": CONFIG_DIR / "credentials_yourwork.json",
    },
    "youraccount": {
        "email": "your-email@example.com",
        "token": CONFIG_DIR / "token_youraccount.json",
        "credentials": CONFIG_DIR / "credentials.json",
    },
    "personal": {
        "email": "your-personal-email@example.com",
        "token": CONFIG_DIR / "token_personal.json",
        "credentials": CONFIG_DIR / "credentials.json",
    },
}

INBOX_CONFIG = ACCOUNTS["yourwork"]


def get_gmail_service():
    """Authenticate and return a Gmail API service."""
    from google.auth.transport.requests import Request
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    token_path = INBOX_CONFIG["token"]
    creds_path = INBOX_CONFIG["credentials"]
    creds = None

    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception:
            creds = None

    if not creds or not creds.valid:
        if not creds_path.exists():
            print(f"ERROR: Credentials file not found: {creds_path}", file=sys.stderr)
            sys.exit(1)
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        with open(token_path, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def get_email_body(payload: dict) -> str:
    """Extract plain text body from Gmail message payload."""
    if payload.get("mimeType") == "text/plain" and payload.get("body", {}).get("data"):
        return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8", errors="replace")

    parts = payload.get("parts", [])
    for part in parts:
        if part.get("mimeType") == "text/plain" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")
        # Check nested parts (multipart/alternative inside multipart/mixed)
        if part.get("parts"):
            for subpart in part["parts"]:
                if subpart.get("mimeType") == "text/plain" and subpart.get("body", {}).get("data"):
                    return base64.urlsafe_b64decode(subpart["body"]["data"]).decode("utf-8", errors="replace")

    # Fallback: try HTML
    for part in parts:
        if part.get("mimeType") == "text/html" and part.get("body", {}).get("data"):
            return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8", errors="replace")

    return "(no body)"


def fetch_unread(max_results: int = 100) -> None:
    """Fetch all unread emails and save metadata + body."""
    service = get_gmail_service()

    print(f"Fetching unread emails from {INBOX_CONFIG['email']}...")

    results = service.users().messages().list(
        userId="me",
        q="is:unread",
        maxResults=max_results,
    ).execute()

    message_ids = results.get("messages", [])
    if not message_ids:
        print("No unread emails found.")
        return

    print(f"Found {len(message_ids)} unread emails. Fetching details...")

    emails = []
    for i, msg_ref in enumerate(message_ids):
        msg = service.users().messages().get(
            userId="me",
            id=msg_ref["id"],
            format="full",
        ).execute()

        headers = {h["name"].lower(): h["value"] for h in msg["payload"].get("headers", [])}
        body = get_email_body(msg["payload"])
        # Truncate body to 2000 chars for classification
        body_truncated = body[:2000] if len(body) > 2000 else body

        emails.append({
            "id": msg["id"],
            "thread_id": msg.get("threadId", ""),
            "from": headers.get("from", ""),
            "to": headers.get("to", ""),
            "subject": headers.get("subject", "(no subject)"),
            "date": headers.get("date", ""),
            "list_unsubscribe": headers.get("list-unsubscribe", ""),
            "body": body_truncated,
            "labels": msg.get("labelIds", []),
        })

        if (i + 1) % 10 == 0:
            print(f"  Fetched {i + 1}/{len(message_ids)}...")

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(UNREAD_PATH, "w") as f:
        json.dump({
            "emails": emails,
            "fetched_at": datetime.now().isoformat(),
            "account": INBOX_CONFIG["email"],
        }, f, indent=2)

    print(f"\nFetched {len(emails)} unread emails -> {UNREAD_PATH}")


def classify_emails() -> None:
    """Classify each unread email as important or not using Claude."""
    import requests

    if not ANTHROPIC_API_KEY:
        print("ERROR: ANTHROPIC_API_KEY not set in .env", file=sys.stderr)
        sys.exit(1)

    if not UNREAD_PATH.exists():
        print("No unread emails found. Run --fetch first.")
        return

    with open(UNREAD_PATH) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    if not emails:
        print("No emails to classify.")
        return

    print(f"Classifying {len(emails)} emails...\n")

    # Batch emails into groups for efficiency (up to 10 per API call)
    batch_size = 10
    classified = []

    for batch_start in range(0, len(emails), batch_size):
        batch = emails[batch_start:batch_start + batch_size]
        batch_descriptions = []

        for i, email in enumerate(batch):
            has_unsubscribe = bool(email.get("list_unsubscribe"))
            batch_descriptions.append(
                f"--- EMAIL {i} ---\n"
                f"From: {email['from']}\n"
                f"Subject: {email['subject']}\n"
                f"Date: {email['date']}\n"
                f"Has unsubscribe header: {has_unsubscribe}\n"
                f"Body:\n{email['body'][:1500]}\n"
            )

        emails_text = "\n".join(batch_descriptions)

        prompt = f"""Classify each email as "important" or "not_important".

An email is IMPORTANT only if it was clearly written by a real human specifically for Debanjan Mazumdar. Signs of importance:
- Personal, conversational tone directed at Nick specifically
- References specific prior conversations, projects, or shared context
- From a known colleague, client, or partner with a substantive message
- A genuine reply in an ongoing thread with real human content

An email is NOT IMPORTANT if any of these apply:
- Automated notification (GitHub, Stripe, Slack, calendar, CI/CD, monitoring, SaaS alerts)
- Marketing email, newsletter, or promotional content
- Cold outreach / sales pitch (templated "I noticed your company..." messages)
- Service receipts, shipping updates, order confirmations
- Social media notifications
- Auto-replies (OOO, delivery confirmations, bounce notices)
- Has an unsubscribe header (strong signal it's mass-sent)
- Feels like it was sent to many recipients

When in doubt, classify as "important" (err on the side of caution).

Respond with a JSON array of objects, one per email, in order:
[
  {{"index": 0, "classification": "important" or "not_important", "reason": "brief reason"}},
  ...
]

Return ONLY the JSON array, no other text.

{emails_text}"""

        headers = {
            "x-api-key": ANTHROPIC_API_KEY,
            "content-type": "application/json",
            "anthropic-version": "2023-06-01",
        }

        payload = {
            "model": "claude-sonnet-5",
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
        }

        print(f"  Classifying batch {batch_start // batch_size + 1} ({len(batch)} emails)...", end=" ")
        try:
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers=headers,
                json=payload,
                timeout=60,
            )
            resp.raise_for_status()
            result_text = resp.json()["content"][0]["text"]

            # Parse JSON from response (handle potential markdown wrapping)
            result_text = result_text.strip()
            if result_text.startswith("```"):
                result_text = result_text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

            batch_results = json.loads(result_text)

            for result in batch_results:
                idx = result["index"]
                if idx < len(batch):
                    email = batch[idx]
                    classified.append({
                        "id": email["id"],
                        "thread_id": email["thread_id"],
                        "from": email["from"],
                        "subject": email["subject"],
                        "date": email["date"],
                        "classification": result["classification"],
                        "reason": result["reason"],
                    })
            print("done")
        except Exception as e:
            print(f"ERROR: {e}")
            # On error, mark all in batch as important (safe default)
            for email in batch:
                classified.append({
                    "id": email["id"],
                    "thread_id": email["thread_id"],
                    "from": email["from"],
                    "subject": email["subject"],
                    "date": email["date"],
                    "classification": "important",
                    "reason": "Classification failed — kept as important",
                })

    with open(CLASSIFIED_PATH, "w") as f:
        json.dump({
            "emails": classified,
            "classified_at": datetime.now().isoformat(),
            "account": INBOX_CONFIG["email"],
        }, f, indent=2)

    important = sum(1 for e in classified if e["classification"] == "important")
    not_important = len(classified) - important

    print(f"\n{'='*60}")
    print(f"Classification complete")
    print(f"  Important (kept unread): {important}")
    print(f"  Not important (will mark read): {not_important}")
    print(f"  Saved to: {CLASSIFIED_PATH}")
    print(f"{'='*60}")


def review_classifications() -> None:
    """Display classification results for review."""
    if not CLASSIFIED_PATH.exists():
        print("No classifications found. Run --classify first.")
        return

    with open(CLASSIFIED_PATH) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    if not emails:
        print("No emails to review.")
        return

    important = [e for e in emails if e["classification"] == "important"]
    not_important = [e for e in emails if e["classification"] == "not_important"]

    print(f"\n{'='*60}")
    print(f"INBOX CLASSIFICATION — {data.get('account', '?')}")
    print(f"Classified at: {data.get('classified_at', '?')}")
    print(f"{'='*60}")

    if important:
        print(f"\n  IMPORTANT — staying unread ({len(important)}):")
        print(f"  {'-'*50}")
        for e in important:
            print(f"    From: {e['from']}")
            print(f"    Subject: {e['subject']}")
            print(f"    Reason: {e['reason']}")
            print()

    if not_important:
        print(f"\n  NOT IMPORTANT — will be marked read ({len(not_important)}):")
        print(f"  {'-'*50}")
        for e in not_important:
            print(f"    From: {e['from']}")
            print(f"    Subject: {e['subject']}")
            print(f"    Reason: {e['reason']}")
            print()

    print(f"{'='*60}")
    print(f"Total: {len(emails)} | Important: {len(important)} | Mark as read: {len(not_important)}")
    print(f"{'='*60}")


def mark_as_read() -> None:
    """Mark all not_important emails as read."""
    if not CLASSIFIED_PATH.exists():
        print("No classifications found. Run --classify first.")
        return

    with open(CLASSIFIED_PATH) as f:
        data = json.load(f)

    emails = data.get("emails", [])
    not_important = [e for e in emails if e["classification"] == "not_important"]

    if not not_important:
        print("No emails to mark as read.")
        return

    service = get_gmail_service()

    print(f"\nMarking {len(not_important)} emails as read...\n")

    # Use batch modify for efficiency
    message_ids = [e["id"] for e in not_important]

    # Gmail batch modify supports up to 1000 IDs at once
    batch_size = 1000
    marked = 0
    for i in range(0, len(message_ids), batch_size):
        batch = message_ids[i:i + batch_size]
        try:
            service.users().messages().batchModify(
                userId="me",
                body={
                    "ids": batch,
                    "removeLabelIds": ["UNREAD"],
                },
            ).execute()
            marked += len(batch)
            print(f"  Marked {marked}/{len(message_ids)} as read")
        except Exception as e:
            print(f"  ERROR marking batch: {e}")

    important_count = len(emails) - len(not_important)
    print(f"\n{'='*60}")
    print(f"Done. Marked {marked} emails as read.")
    print(f"{important_count} important emails remain unread.")
    print(f"{'='*60}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inbox Cleaner — AI Email Triage")
    parser.add_argument("--fetch", action="store_true", help="Fetch unread emails")
    parser.add_argument("--classify", action="store_true", help="Classify emails with AI")
    parser.add_argument("--review", action="store_true", help="Review classifications")
    parser.add_argument("--mark-read", action="store_true", help="Mark unimportant as read")
    parser.add_argument("--max-results", type=int, default=100, help="Max emails to fetch (default 100)")
    parser.add_argument("--account", choices=list(ACCOUNTS.keys()), default="yourwork", help="Which account to use (default: yourwork)")
    args = parser.parse_args()

    INBOX_CONFIG.update(ACCOUNTS[args.account])
    set_account_paths(args.account)

    if args.fetch:
        fetch_unread(args.max_results)
    elif args.classify:
        classify_emails()
    elif args.review:
        review_classifications()
    elif args.mark_read:
        mark_as_read()
    else:
        parser.print_help()
