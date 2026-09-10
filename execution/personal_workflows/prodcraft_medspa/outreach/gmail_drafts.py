"""
gmail_drafts.py
description: Create a Gmail draft (never sends) via the Gmail API users.drafts.create, following
    this workspace's OAuth-user-token pattern (execution/personal_workflows/prodcraft_oauth.py).
inputs: create_draft(to_email, subject, body, sender_name, settings, mock, business_id=None);
    env GMAIL_CREDENTIALS_JSON (OAuth client id/secret JSON path), GMAIL_TOKEN_JSON (token cache
    path, refreshed in place like prodcraft_oauth.py's tokens/youtube.json).
outputs: live -> one Gmail draft via users.drafts.create; --mock -> a .eml file under
    .tmp/prodcraft_medspa/drafts/. Returns {"gmail_draft_id": str, "eml_path": str|None}.
"""

from __future__ import annotations

import argparse
import base64
import json
import uuid
from email.mime.text import MIMEText
from pathlib import Path
from typing import Any

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.compose"]


def _get_credentials(settings: Any):
    """Load + refresh Gmail OAuth-user credentials from GMAIL_TOKEN_JSON, mirroring
    prodcraft_oauth.get_credentials()'s pattern (token cache, refresh-in-place, clear errors)."""
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as exc:
        raise ImportError(
            "Gmail draft creation requires google-auth-oauthlib and google-auth-httplib2. "
            "Install with: pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client"
        ) from exc

    token_path_raw = getattr(settings, "GMAIL_TOKEN_JSON", None)
    if not token_path_raw:
        raise RuntimeError(
            "GMAIL_TOKEN_JSON is not set. Point it at a Gmail OAuth token cache file "
            "(see execution/personal_workflows/prodcraft_oauth.py for the bootstrap pattern)."
        )
    token_path = Path(token_path_raw)
    if not token_path.exists():
        raise RuntimeError(f"No Gmail OAuth token at {token_path}. Bootstrap it first (one-time consent flow).")

    data = json.loads(token_path.read_text(encoding="utf-8"))
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", GMAIL_SCOPES),
    )
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        data["token"] = creds.token
        data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        token_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    return creds


def create_draft(
    *,
    to_email: str,
    subject: str,
    body: str,
    sender_name: str,
    settings: Any,
    mock: bool,
    business_id: str | None = None,
) -> dict:
    """Create one Gmail draft. In --mock mode, writes a .eml file instead of calling the API."""
    if mock:
        out_dir = settings.TMP / "drafts"
        out_dir.mkdir(parents=True, exist_ok=True)
        eml_path = out_dir / f"{business_id or 'draft'}_{uuid.uuid4().hex[:8]}.eml"
        eml_content = (
            f"To: {to_email}\nSubject: {subject}\nFrom: {sender_name}\n\n{body}\n"
        )
        eml_path.write_text(eml_content, encoding="utf-8")
        return {"gmail_draft_id": f"mock-{eml_path.stem}", "eml_path": str(eml_path)}

    try:
        from googleapiclient.discovery import build
    except ImportError as exc:
        raise ImportError(
            "Gmail draft creation requires google-api-python-client. "
            "Install with: pip install google-api-python-client"
        ) from exc

    creds = _get_credentials(settings)
    service = build("gmail", "v1", credentials=creds, cache_discovery=False)

    message = MIMEText(body)
    message["To"] = to_email
    message["Subject"] = subject
    message["From"] = sender_name
    raw = base64.urlsafe_b64encode(message.as_bytes()).decode("ascii")

    draft = service.users().drafts().create(userId="me", body={"message": {"raw": raw}}).execute()
    return {"gmail_draft_id": draft["id"], "eml_path": None}


def main() -> None:
    parser = argparse.ArgumentParser(description="Create one Gmail draft (never sends)")
    parser.add_argument("--to", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--body", required=True)
    parser.add_argument("--sender-name", default="")
    parser.add_argument("--mock", action="store_true")
    args = parser.parse_args()

    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[4]))
    from execution.personal_workflows.prodcraft_medspa.common import config  # noqa: E402

    settings = config.bootstrap()
    result = create_draft(
        to_email=args.to,
        subject=args.subject,
        body=args.body,
        sender_name=args.sender_name,
        settings=settings,
        mock=args.mock,
    )
    print(json.dumps({"script": "gmail_drafts", **result}))


if __name__ == "__main__":
    main()
