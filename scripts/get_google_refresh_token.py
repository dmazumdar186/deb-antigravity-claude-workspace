#!/usr/bin/env python
"""
get_google_refresh_token.py — one-off OAuth2 Installed-App flow to obtain
refresh tokens for the yoga-jitendra dashboard V0.1 data pipeline.

Runs LOCALLY on the operator's machine. Not deployed anywhere. Prints the
two refresh tokens (GSC + GBP scopes) to stdout, ready for
`wrangler secret put GOOGLE_REFRESH_TOKEN_GSC` and
`wrangler secret put GOOGLE_REFRESH_TOKEN_GBP`.

Prereqs
=======
  1. Google Cloud Console project with Search Console API + Business
     Profile Performance API enabled.
  2. OAuth 2.0 Client (type: Desktop app OR Web app with the loopback
     redirect URI http://localhost:8765 in the allowed list). Download
     the credentials.json into the same directory as this script.
  3. `pip install google-auth-oauthlib` (already in most workspaces).
  4. If the OAuth consent screen is in "Testing" publishing status
     (which it will be for the personal-scale use), the operator's
     Google account MUST be added as a Test User in the consent screen
     first. Otherwise the consent flow will return access_denied.

Usage
=====
  cd execution/personal_workflows/yoga_jitendra_site/scripts
  py get_google_refresh_token.py

The script opens two browser windows in sequence (one per scope) and
prints the resulting refresh tokens with copy-paste-ready wrangler
commands. Total time: ~2 minutes.

Refresh-token lifetime
======================
Per Google policy, refresh tokens from Testing-status apps expire after
7 days. This is expected steady state; re-run this script every ~6 days
(dashboard shows a "refreshed N days ago" indicator that goes red at 6).

Security
========
- credentials.json contains a client_secret. Keep it .gitignored.
- The printed refresh tokens are secrets. Paste them into
  `wrangler secret put` immediately; do NOT commit them anywhere.
- The loopback flow (localhost:8765) is safe against CSRF because the
  google-auth library uses a PKCE-style state param and validates the
  redirect exactly.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

try:
    from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
except ImportError:
    print(
        "ERROR: google-auth-oauthlib not installed. Install with:\n"
        "  pip install google-auth-oauthlib\n",
        file=sys.stderr,
    )
    sys.exit(2)


# Scopes are minimal — read-only. GSC needs webmasters.readonly; GBP needs
# business.manage (which unfortunately requires read AND write in one scope,
# as Google has not published a business-read-only equivalent for the
# Performance API).
SCOPES_GSC = ["https://www.googleapis.com/auth/webmasters.readonly"]
SCOPES_GBP = ["https://www.googleapis.com/auth/business.manage"]

REDIRECT_PORT = 8765


def _run_flow(client_secrets_path: Path, scopes: list[str], scope_label: str) -> str:
    print(f"\n=== Getting refresh token for: {scope_label} ===")
    print(f"    Scopes: {scopes}")
    print("    Opening browser to Google consent screen...")
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secrets_path), scopes=scopes)
    # access_type=offline + prompt=consent guarantees Google returns a
    # refresh_token (without prompt=consent, subsequent runs return only
    # an access_token because the user has already granted consent).
    creds = flow.run_local_server(
        port=REDIRECT_PORT,
        access_type="offline",
        prompt="consent",
        open_browser=True,
    )
    if not creds.refresh_token:
        raise RuntimeError(
            f"No refresh_token returned for {scope_label}. "
            "This usually means the consent screen skipped the offline-access "
            "prompt because the account has already granted consent. Revoke "
            "access at https://myaccount.google.com/permissions and retry."
        )
    return creds.refresh_token


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Obtain Google OAuth refresh tokens for the yoga-jitendra "
            "dashboard cron. Default runs both scopes (GSC + GBP) "
            "sequentially. Use --only when the two flows share a "
            "browser session and Chrome caches the first flow's state "
            "into the second (produces `mismatching_state CSRF Warning`)."
        )
    )
    parser.add_argument(
        "--only",
        choices=("gsc", "gbp"),
        default=None,
        help=(
            "Run one scope only. Use this if the paired run fails with "
            "`mismatching_state CSRF Warning`: run `--only gsc` first, "
            "close all browser tabs pointing at localhost:8765, then run "
            "`--only gbp` in a fresh terminal."
        ),
    )
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    creds_path = here / "credentials.json"
    if not creds_path.is_file():
        print(
            f"ERROR: {creds_path} not found.\n\n"
            "Download the OAuth 2.0 Client credentials JSON from:\n"
            "  https://console.cloud.google.com/apis/credentials\n"
            "and save it as 'credentials.json' in this directory.\n",
            file=sys.stderr,
        )
        return 1

    # Validate the credentials.json shape early — the InstalledAppFlow gives
    # a cryptic error if the file is a service-account JSON by mistake.
    with creds_path.open("r", encoding="utf-8") as f:
        creds_data = json.load(f)
    if "installed" not in creds_data and "web" not in creds_data:
        print(
            f"ERROR: {creds_path} does not look like an OAuth 2.0 Client JSON. "
            "Expected top-level 'installed' or 'web' key. "
            "Did you download a service account key by mistake?\n",
            file=sys.stderr,
        )
        return 1

    tokens: dict[str, str | None] = {"gsc": None, "gbp": None}
    run_gsc = args.only in (None, "gsc")
    run_gbp = args.only in (None, "gbp")

    if run_gsc:
        try:
            tokens["gsc"] = _run_flow(creds_path, SCOPES_GSC, "Search Console (webmasters.readonly)")
        except Exception as e:
            print(f"\nGSC flow failed: {e}", file=sys.stderr)
            return 3

    if run_gbp:
        try:
            tokens["gbp"] = _run_flow(creds_path, SCOPES_GBP, "Business Profile (business.manage)")
        except Exception as e:
            # GBP failure is non-fatal in a paired run — V0.1 shipped without
            # GBP per plan §7.2b. But if the user explicitly asked for --only gbp,
            # a failure IS fatal; there's no other output they wanted.
            hint = (
                ""
                if args.only != "gbp"
                else (
                    "\nHINT: if this is `mismatching_state CSRF Warning`, close "
                    "every browser tab pointing at localhost:8765, wait a few "
                    "seconds, and re-run this exact command."
                )
            )
            print(
                f"\nGBP flow failed: {e}{hint}",
                file=sys.stderr,
            )
            if args.only == "gbp":
                return 3

    print("\n" + "=" * 72)
    print("SUCCESS. Copy-paste the following into your terminal to update the")
    print("Cloudflare Worker secrets. Run each command separately; wrangler will")
    print("prompt for the value (paste the token, press Enter).")
    print("=" * 72)

    if tokens["gsc"]:
        print("\n# Set GSC refresh token:")
        print(
            "cd execution/infrastructure/yoga_jitendra_cron && "
            "npx wrangler secret put GOOGLE_REFRESH_TOKEN_GSC"
        )
        print(f"# When prompted, paste:  {tokens['gsc']}")

    if tokens["gbp"]:
        print("\n# Set GBP refresh token:")
        print(
            "cd execution/infrastructure/yoga_jitendra_cron && "
            "npx wrangler secret put GOOGLE_REFRESH_TOKEN_GBP"
        )
        print(f"# When prompted, paste:  {tokens['gbp']}")
    elif run_gbp:
        print("\n# GBP token not obtained — V0.1 ships without GBP. Re-run this")
        print("# script with `--only gbp` once the browser session is clean.")

    print("\nAlso set the OAuth client credentials (one-time; same value used")
    print("for both scopes):")
    print(f"  npx wrangler secret put GOOGLE_CLIENT_ID     # {creds_data.get('installed', creds_data.get('web', {})).get('client_id', '<from credentials.json>')}")
    print(f"  npx wrangler secret put GOOGLE_CLIENT_SECRET # <from credentials.json>")

    print(
        "\nNOTE: refresh tokens from Testing-status OAuth apps expire after 7 days."
        "\nRe-run this script every ~6 days. The dashboard shows a reminder pill."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
