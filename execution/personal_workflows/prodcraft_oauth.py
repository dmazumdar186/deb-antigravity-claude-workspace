"""
description: Shared OAuth flow for the ProdCraft autopilot. Owns the bootstrap + refresh of the YouTube refresh token; provides `get_credentials()` to other scripts (ingest, upload).
inputs:
    Env vars (.env):
        YT_OAUTH_CLIENT_ID         required (from Google Cloud Console)
        YT_OAUTH_CLIENT_SECRET     required
        YT_OAUTH_REFRESH_TOKEN     written by bootstrap; read by get_credentials()
    CLI:
        py prodcraft_oauth.py           runs interactive bootstrap (one-time)
        py prodcraft_oauth.py --check   verifies stored token still refreshes (no browser)
outputs:
    tokens/youtube.json   OAuth token cache (refresh token + scopes + expiry)
    .env update           writes YT_OAUTH_REFRESH_TOKEN= line on first bootstrap
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# force-ssl scope covers: captions read+write (Phase 0 ingest) AND video upload (Phase 3).
# One scope = one consent screen for the operator. Don't expand without re-consent.
SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TOKEN_DIR = WORKSPACE_ROOT / "tokens"
TOKEN_PATH = TOKEN_DIR / "youtube.json"
ENV_PATH = WORKSPACE_ROOT / ".env"


def _client_config_from_env() -> dict:
    """Build the Google OAuth client_config in-memory from .env vars.

    Avoids requiring the operator to download credentials.json from Google Cloud Console.
    """
    cid = os.environ.get("YT_OAUTH_CLIENT_ID")
    csec = os.environ.get("YT_OAUTH_CLIENT_SECRET")
    if not cid or not csec:
        raise SystemExit(
            "YT_OAUTH_CLIENT_ID and YT_OAUTH_CLIENT_SECRET must be in .env.\n"
            "Get them from https://console.cloud.google.com/apis/credentials (Desktop app OAuth client)."
        )
    return {
        "installed": {
            "client_id": cid,
            "client_secret": csec,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def _fingerprint(token: str) -> str:
    """Last-4 fingerprint for log lines. Never print the full token."""
    if not token:
        return "<empty>"
    return f"...{token[-6:]}" if len(token) > 6 else "<short>"


def _atomic_write(path: Path, content: str) -> None:
    """Atomic write via tmp + os.replace (atomic on Windows via MoveFileExW)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    os.replace(tmp, path)


def _update_env_refresh_token(refresh_token: str) -> None:
    """Add or replace YT_OAUTH_REFRESH_TOKEN= line in .env. Atomic write."""
    if not ENV_PATH.exists():
        raise SystemExit(f".env not found at {ENV_PATH}. Aborting (refuse to create one).")
    lines = ENV_PATH.read_text(encoding="utf-8").splitlines()
    target_line = f"YT_OAUTH_REFRESH_TOKEN={refresh_token}"
    found = False
    new_lines: list[str] = []
    for line in lines:
        stripped = line.lstrip()
        if stripped.startswith("YT_OAUTH_REFRESH_TOKEN="):
            new_lines.append(target_line)
            found = True
        else:
            new_lines.append(line)
    if not found:
        if new_lines and new_lines[-1] != "":
            new_lines.append("")
        new_lines.append(target_line)
    new_content = "\n".join(new_lines)
    if not new_content.endswith("\n"):
        new_content += "\n"
    _atomic_write(ENV_PATH, new_content)


def bootstrap(force: bool = False) -> dict:
    """Interactive: open browser, capture refresh token, persist to tokens/ + .env.

    Returns the credentials JSON dict (token, refresh_token, scopes, expiry).
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError as e:
        raise SystemExit("Run: py -m pip install google-auth-oauthlib") from e

    if TOKEN_PATH.exists() and not force:
        print(f"Token already exists at {TOKEN_PATH}. Use --force to re-bootstrap.", file=sys.stderr)
        existing = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
        return existing

    client_config = _client_config_from_env()
    flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
    print("Opening browser for Google consent screen...", file=sys.stderr)
    print("If browser doesn't open, copy the URL printed below into any browser.", file=sys.stderr)
    # access_type=offline + prompt=consent forces Google to return a refresh_token
    # (without it, repeat consents return only access tokens — silently breaks renewal).
    creds = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )

    if not creds.refresh_token:
        raise SystemExit(
            "No refresh_token returned from Google. This usually means consent was previously granted\n"
            "and Google is returning only an access token. Revoke at https://myaccount.google.com/permissions\n"
            "then re-run with --force."
        )

    payload = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes) if creds.scopes else SCOPES,
        "expiry": creds.expiry.isoformat() if creds.expiry else None,
    }
    _atomic_write(TOKEN_PATH, json.dumps(payload, indent=2))
    _update_env_refresh_token(creds.refresh_token)
    print(
        f"✓ refresh token persisted | fingerprint={_fingerprint(creds.refresh_token)} | "
        f"tokens={TOKEN_PATH} | .env updated",
        file=sys.stderr,
    )
    return payload


def get_credentials():
    """Return live `google.oauth2.credentials.Credentials` ready for use with googleapiclient.

    Loads tokens/youtube.json if present, refreshes if expired. Falls back to bootstrap()
    if no token exists yet.
    """
    try:
        from google.auth.transport.requests import Request
        from google.oauth2.credentials import Credentials
    except ImportError as e:
        raise SystemExit("Run: py -m pip install google-auth-oauthlib google-auth-httplib2") from e

    if not TOKEN_PATH.exists():
        raise SystemExit(
            f"No OAuth token at {TOKEN_PATH}. Run:\n"
            f"  py execution/personal_workflows/prodcraft_oauth.py\n"
            f"to bootstrap (opens browser for one-click consent)."
        )

    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    creds = Credentials(
        token=data.get("token"),
        refresh_token=data.get("refresh_token"),
        token_uri=data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=data.get("client_id"),
        client_secret=data.get("client_secret"),
        scopes=data.get("scopes", SCOPES),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:
            raise SystemExit(
                f"OAuth refresh failed: {type(exc).__name__}: {exc}\n"
                f"This usually means the refresh token expired (test-user apps: 7-day TTL).\n"
                f"Re-bootstrap: py execution/personal_workflows/prodcraft_oauth.py --force"
            ) from exc
        # Persist the refreshed access token so next call doesn't re-hit token endpoint.
        data["token"] = creds.token
        data["expiry"] = creds.expiry.isoformat() if creds.expiry else None
        _atomic_write(TOKEN_PATH, json.dumps(data, indent=2))

    return creds


def check() -> int:
    creds = get_credentials()
    print(
        f"✓ credentials valid | refresh_token fp={_fingerprint(creds.refresh_token or '')} "
        f"| expires={creds.expiry} | scopes={creds.scopes}",
        file=sys.stderr,
    )
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft YouTube OAuth bootstrap")
    p.add_argument("--check", action="store_true", help="Verify stored credentials refresh cleanly (no browser)")
    p.add_argument("--force", action="store_true", help="Re-bootstrap even if token already exists")
    args = p.parse_args()

    if args.check:
        return check()
    bootstrap(force=args.force)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
