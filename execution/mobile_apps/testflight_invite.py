"""
testflight_invite.py
description: Add emails to TestFlight (internal or external group) via the App Store Connect API using JWT auth (ES256 with the App-Store-Connect private key). Reads ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY_PATH from .env. App is resolved from registry.json by slug (uses its `ios_bundle_id`).
inputs: CLI: --app <slug>, --emails <email1,email2,...>, --group <internal|external>; env: ASC_KEY_ID, ASC_ISSUER_ID, ASC_PRIVATE_KEY_PATH
outputs: HTTPS POSTs to https://api.appstoreconnect.apple.com; prints per-email success/failure
usage:
    py execution/mobile_apps/testflight_invite.py --app my-app --emails alice@x.com,bob@y.com --group internal
    py execution/mobile_apps/testflight_invite.py --app my-app --emails tester@x.com --group external
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

try:
    import jwt  # PyJWT
except ImportError:
    jwt = None

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"
ASC_BASE = "https://api.appstoreconnect.apple.com"
ASC_AUDIENCE = "appstoreconnect-v1"
TOKEN_TTL_SECONDS = 1200  # ASC max is 20 minutes


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "apps": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def find_app(registry: dict, slug: str) -> dict | None:
    for app in registry.get("apps", []):
        if app.get("slug") == slug:
            return app
    return None


def require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise SystemExit(
            f"ERROR: {key} not set. Add it to .env. "
            "See https://developer.apple.com/documentation/appstoreconnectapi"
        )
    return val


def generate_jwt(key_id: str, issuer_id: str, private_key_path: Path) -> str:
    if jwt is None:
        raise SystemExit("ERROR: PyJWT not installed. Run: pip install pyjwt[crypto]")
    if not private_key_path.exists():
        raise SystemExit(f"ERROR: private key not found at {private_key_path}")
    private_key = private_key_path.read_text(encoding="utf-8")
    now = int(time.time())
    payload = {
        "iss": issuer_id,
        "iat": now,
        "exp": now + TOKEN_TTL_SECONDS,
        "aud": ASC_AUDIENCE,
    }
    headers = {"alg": "ES256", "kid": key_id, "typ": "JWT"}
    return jwt.encode(payload, private_key, algorithm="ES256", headers=headers)


def asc_get(token: str, path: str, params: dict | None = None) -> dict:
    if requests is None:
        raise SystemExit("ERROR: `requests` not installed. Run: pip install requests")
    resp = requests.get(
        f"{ASC_BASE}{path}",
        headers={"Authorization": f"Bearer {token}"},
        params=params or {},
        timeout=30,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"ASC GET {path} -> {resp.status_code}: {resp.text[:500]}")
    return resp.json()


def asc_post(token: str, path: str, body: dict) -> dict:
    if requests is None:
        raise SystemExit("ERROR: `requests` not installed. Run: pip install requests")
    resp = requests.post(
        f"{ASC_BASE}{path}",
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        json=body,
        timeout=30,
    )
    return {"status": resp.status_code, "body": resp.text}


def find_app_id_by_bundle(token: str, bundle_id: str) -> str | None:
    """Resolve ASC numeric app id from bundleId."""
    data = asc_get(token, "/v1/apps", params={"filter[bundleId]": bundle_id, "limit": 5})
    for item in data.get("data", []):
        if item.get("attributes", {}).get("bundleId") == bundle_id:
            return item.get("id")
    return None


def invite_internal(token: str, app_id: str, email: str) -> dict:
    """Internal testers must be App Store Connect users — create a betaTester record."""
    body = {
        "data": {
            "type": "betaTesters",
            "attributes": {"email": email, "firstName": "Tester", "lastName": "Internal"},
            "relationships": {
                "apps": {"data": [{"type": "apps", "id": app_id}]},
            },
        }
    }
    return asc_post(token, "/v1/betaTesters", body)


def invite_external(token: str, app_id: str, email: str) -> dict:
    """External: create betaTester linked to the app (group assignment via beta group is recommended)."""
    body = {
        "data": {
            "type": "betaTesters",
            "attributes": {"email": email, "firstName": "Tester", "lastName": "External"},
            "relationships": {
                "apps": {"data": [{"type": "apps", "id": app_id}]},
            },
        }
    }
    return asc_post(token, "/v1/betaTesters", body)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("--app", required=True, help="App slug (must exist in registry).")
    parser.add_argument("--emails", required=True,
                        help="Comma-separated emails to invite.")
    parser.add_argument("--group", required=True, choices=["internal", "external"])
    args = parser.parse_args()

    registry = load_registry()
    app = find_app(registry, args.app)
    if not app:
        print(f"ERROR: app '{args.app}' not in registry.", file=sys.stderr)
        return 2
    bundle_id = app.get("ios_bundle_id")
    if not bundle_id:
        print(f"ERROR: app '{args.app}' has no ios_bundle_id in registry.", file=sys.stderr)
        return 2

    key_id = require_env("ASC_KEY_ID")
    issuer_id = require_env("ASC_ISSUER_ID")
    key_path = Path(require_env("ASC_PRIVATE_KEY_PATH"))

    emails = [e.strip() for e in args.emails.split(",") if e.strip()]
    if not emails:
        print("ERROR: --emails empty", file=sys.stderr)
        return 2

    print(f"TestFlight invite: app={args.app} bundle={bundle_id} "
          f"group={args.group} count={len(emails)}")

    token = generate_jwt(key_id, issuer_id, key_path)
    asc_app_id = find_app_id_by_bundle(token, bundle_id)
    if not asc_app_id:
        print(f"ERROR: ASC has no app with bundleId={bundle_id}. "
              "Upload at least one build via EAS first.", file=sys.stderr)
        return 2
    print(f"  asc_app_id={asc_app_id}")

    invite_fn = invite_internal if args.group == "internal" else invite_external
    failures = 0
    for email in emails:
        try:
            result = invite_fn(token, asc_app_id, email)
            status = result.get("status")
            if isinstance(status, int) and status < 400:
                print(f"  OK  {email} -> {status}")
            else:
                failures += 1
                print(f"  ERR {email} -> {status}: {result.get('body','')[:300]}",
                      file=sys.stderr)
        except (RuntimeError, OSError) as e:
            # Network/HTTP/file errors per invite — log and continue with remaining emails.
            failures += 1
            print(f"  ERR {email} -> {e}", file=sys.stderr)

    print(f"\nDone. failures={failures}/{len(emails)}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
