"""
doctor.py
description: For every pipeline stage, lists each required env var present/missing (never prints
    values); with --live, makes one cheap authenticated call per service and prints
    `service | env present | live ok | detail`. Also checks Node >= 20, a Chromium install,
    template/node_modules, and preview/worker/node_modules. Exits non-zero if any stage selected
    via --stages is missing a required var. Must never crash with no env configured.
inputs: CLI: [--live] [--stages discovery,audit,enrich,preview,outreach,store,notify]. Env: every
    var in CONTRACTS.md's "Secrets only via env" list (all optional for the default, non-live run).
outputs: stdout: env-presence table, and with --live, the live-check table + Node/Chromium/
    node_modules checks; final JSON stat line.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common.config import (  # noqa: E402
    REQUIRED_BY_STAGE,
    bootstrap,
)

PKG_ROOT = REPO_ROOT / "execution" / "personal_workflows" / "prodcraft_medspa"

# service -> env var name(s) it needs, for the presence table.
SERVICE_ENV_VARS: dict[str, list[str]] = {
    "google_places": ["GOOGLE_PLACES_API_KEY"],
    "pagespeed": ["PAGESPEED_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "apollo": ["APOLLO_API_KEY"],
    "findymail": ["FINDYMAIL_API_KEY"],
    "hunter": ["HUNTER_API_KEY"],
    "million_verifier": ["MILLION_VERIFIER_API_KEY"],
    "supabase": ["SUPABASE_URL", "SUPABASE_SERVICE_KEY"],
    "cloudflare": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID"],
    "r2": ["CLOUDFLARE_API_TOKEN", "CLOUDFLARE_ACCOUNT_ID", "R2_BUCKET"],
    "gmail": ["GMAIL_CREDENTIALS_JSON", "GMAIL_TOKEN_JSON"],
    "telegram": ["TELEGRAM_BOT_TOKEN", "TELEGRAM_CHAT_ID"],
}


def env_presence(settings) -> dict[str, bool]:
    """service -> True only if every env var it needs is set."""
    out = {}
    for service, names in SERVICE_ENV_VARS.items():
        out[service] = all(bool(getattr(settings, n, None)) for n in names)
    return out


# ---------------------------------------------------------------------------
# Live checks — each returns (ok: bool | None, detail: str). None = skipped (no creds).
# ---------------------------------------------------------------------------


def _live_google_places(settings) -> tuple[bool | None, str]:
    key = settings.GOOGLE_PLACES_API_KEY
    if not key:
        return None, "skipped (no key)"
    try:
        import requests

        resp = requests.post(
            "https://places.googleapis.com/v1/places:searchText",
            headers={
                "Content-Type": "application/json",
                "X-Goog-Api-Key": key,
                "X-Goog-FieldMask": "places.id",
            },
            json={"textQuery": "med spa", "maxResultCount": 1},
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001 — doctor must report, never crash, on any live-check failure
        return False, f"error: {exc}"


def _live_pagespeed(settings) -> tuple[bool | None, str]:
    try:
        import requests

        params = {"url": "https://example.com", "strategy": "mobile"}
        if settings.PAGESPEED_API_KEY:
            params["key"] = settings.PAGESPEED_API_KEY
        resp = requests.get(
            "https://www.googleapis.com/pagespeedonline/v5/runPagespeed", params=params, timeout=30
        )
        return resp.status_code == 200, f"HTTP {resp.status_code} (keyless run: {'no' if not settings.PAGESPEED_API_KEY else 'yes'} key)"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_anthropic(settings) -> tuple[bool | None, str]:
    if not settings.ANTHROPIC_API_KEY:
        return None, "skipped (no key)"
    try:
        import anthropic

        client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        client.messages.create(
            model="claude-sonnet-5", max_tokens=1, messages=[{"role": "user", "content": "hi"}]
        )
        return True, "1-token message ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_apollo(settings) -> tuple[bool | None, str]:
    if not settings.APOLLO_API_KEY:
        return None, "skipped (no key)"
    try:
        import requests

        resp = requests.get(
            "https://api.apollo.io/v1/auth/health",
            headers={"X-Api-Key": settings.APOLLO_API_KEY},
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_findymail(settings) -> tuple[bool | None, str]:
    if not settings.FINDYMAIL_API_KEY:
        return None, "skipped (no key)"
    try:
        import requests

        resp = requests.get(
            "https://app.findymail.com/api/account",
            headers={"Authorization": f"Bearer {settings.FINDYMAIL_API_KEY}"},
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_hunter(settings) -> tuple[bool | None, str]:
    if not settings.HUNTER_API_KEY:
        return None, "skipped (no key)"
    try:
        import requests

        resp = requests.get(
            "https://api.hunter.io/v2/account", params={"api_key": settings.HUNTER_API_KEY}, timeout=15
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_million_verifier(settings) -> tuple[bool | None, str]:
    if not settings.MILLION_VERIFIER_API_KEY:
        return None, "skipped (no key)"
    try:
        import requests

        resp = requests.get(
            "https://api.millionverifier.com/api/v3/credits",
            params={"api": settings.MILLION_VERIFIER_API_KEY},
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_supabase(settings) -> tuple[bool | None, str]:
    if not (settings.SUPABASE_URL and settings.SUPABASE_SERVICE_KEY):
        return None, "skipped (no url/key)"
    try:
        import requests

        resp = requests.get(
            f"{settings.SUPABASE_URL.rstrip('/')}/rest/v1/config",
            params={"select": "key"},
            headers={
                "apikey": settings.SUPABASE_SERVICE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_KEY}",
            },
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_cloudflare(settings) -> tuple[bool | None, str]:
    if not settings.CLOUDFLARE_API_TOKEN:
        return None, "skipped (no token)"
    try:
        import requests

        resp = requests.get(
            "https://api.cloudflare.com/client/v4/user/tokens/verify",
            headers={"Authorization": f"Bearer {settings.CLOUDFLARE_API_TOKEN}"},
            timeout=15,
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_r2(settings) -> tuple[bool | None, str]:
    if not (settings.CLOUDFLARE_API_TOKEN and settings.CLOUDFLARE_ACCOUNT_ID and settings.R2_BUCKET):
        return None, "skipped (no token/account/bucket)"
    try:
        sys.path.insert(0, str(PKG_ROOT))
        from preview import r2  # type: ignore  # noqa: PLC0415 — optional, another agent's package
    except ImportError:
        return None, "skipped (preview/r2.py not implemented yet)"
    try:
        r2.list_keys(bucket=settings.R2_BUCKET, prefix="", max_keys=1)  # type: ignore[attr-defined]
        return True, "listed 1 key ok"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_gmail(settings) -> tuple[bool | None, str]:
    if not (settings.GMAIL_CREDENTIALS_JSON and settings.GMAIL_TOKEN_JSON):
        return None, "skipped (no credentials/token)"
    try:
        import json as _json

        from google.oauth2.credentials import Credentials  # type: ignore[import-untyped]
        from googleapiclient.discovery import build  # type: ignore[import-untyped]

        token_info = _json.loads(settings.GMAIL_TOKEN_JSON)
        creds = Credentials.from_authorized_user_info(token_info)
        service = build("gmail", "v1", credentials=creds)
        profile = service.users().getProfile(userId="me").execute()
        return True, f"profile ok ({profile.get('emailAddress', '?')})"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


def _live_telegram(settings) -> tuple[bool | None, str]:
    if not settings.TELEGRAM_BOT_TOKEN:
        return None, "skipped (no token)"
    try:
        import requests

        resp = requests.get(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getMe", timeout=15
        )
        return resp.status_code == 200, f"HTTP {resp.status_code}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error: {exc}"


LIVE_CHECKS: dict[str, Callable[[Any], tuple[bool | None, str]]] = {
    "google_places": _live_google_places,
    "pagespeed": _live_pagespeed,
    "anthropic": _live_anthropic,
    "apollo": _live_apollo,
    "findymail": _live_findymail,
    "hunter": _live_hunter,
    "million_verifier": _live_million_verifier,
    "supabase": _live_supabase,
    "cloudflare": _live_cloudflare,
    "r2": _live_r2,
    "gmail": _live_gmail,
    "telegram": _live_telegram,
}


# ---------------------------------------------------------------------------
# Environment checks (Node, Chromium, node_modules)
# ---------------------------------------------------------------------------


def check_node_version() -> tuple[bool | None, str]:
    node = shutil.which("node")
    if not node:
        return False, "node not found on PATH"
    try:
        proc = subprocess.run(
            [node, "--version"], capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=10
        )
        version_str = proc.stdout.strip().lstrip("v")
        major = int(version_str.split(".")[0])
        return major >= 20, f"node {proc.stdout.strip()}"
    except Exception as exc:  # noqa: BLE001
        return False, f"error checking node version: {exc}"


def check_chromium() -> tuple[bool | None, str]:
    candidate = Path("/opt/pw-browsers/chromium")
    if candidate.exists():
        return True, str(candidate)
    pw_cache = Path.home() / ".cache" / "ms-playwright"
    if pw_cache.exists() and any(pw_cache.glob("chromium-*")):
        found = next(pw_cache.glob("chromium-*"))
        return True, str(found)
    return False, "no chromium at /opt/pw-browsers/chromium or Playwright's default cache"


def check_node_modules(path: Path) -> tuple[bool | None, str]:
    exists = (path / "node_modules").is_dir()
    return exists, str(path / "node_modules")


def print_table(rows: list[tuple[str, ...]], headers: tuple[str, ...]) -> None:
    widths = [len(h) for h in headers]
    for row in rows:
        for i, cell in enumerate(row):
            widths[i] = max(widths[i], len(str(cell)))
    fmt = "  ".join("{:<" + str(w) + "}" for w in widths)
    print(fmt.format(*headers))
    print(fmt.format(*["-" * w for w in widths]))
    for row in rows:
        print(fmt.format(*[str(c) for c in row]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--stages",
        default="discovery,audit,enrich,preview,outreach",
        help=(
            "comma-separated stages to gate the exit code on (default: the pipeline stages a "
            "normal run touches; 'store' and 'notify' are opt-in since local store + no Telegram "
            "are valid defaults, not missing configuration)"
        ),
    )
    args = parser.parse_args()

    settings = bootstrap()
    selected_stages = [s.strip() for s in args.stages.split(",") if s.strip()]

    print("=== Env presence by stage ===")
    stage_rows = []
    stage_missing: dict[str, list[str]] = {}
    for stage, required in REQUIRED_BY_STAGE.items():
        missing = settings.missing_for_stage(stage)
        stage_missing[stage] = missing
        status = "OK" if not missing else f"MISSING: {', '.join(missing)}"
        stage_rows.append((stage, ", ".join(required), status))
    print_table(stage_rows, ("stage", "required (never printing values)", "status"))

    presence = env_presence(settings)

    live_rows: list[tuple[str, str, str, str]] = []
    if args.live:
        print("\n=== Live checks ===")
        for service, present in presence.items():
            checker = LIVE_CHECKS.get(service)
            ok: bool | None = None
            detail = "no checker"
            if checker is not None:
                ok, detail = checker(settings)
            live_rows.append((service, "yes" if present else "no", "n/a" if ok is None else ("yes" if ok else "no"), detail))
        print_table(live_rows, ("service", "env present", "live ok", "detail"))

        print("\n=== Environment ===")
        node_ok, node_detail = check_node_version()
        chromium_ok, chromium_detail = check_chromium()
        template_nm_ok, template_nm_detail = check_node_modules(PKG_ROOT / "template")
        worker_nm_ok, worker_nm_detail = check_node_modules(PKG_ROOT / "preview" / "worker")
        env_rows = [
            ("node >= 20", "yes" if node_ok else "no", node_detail),
            ("chromium", "yes" if chromium_ok else "no", chromium_detail),
            ("template/node_modules", "yes" if template_nm_ok else "no", template_nm_detail),
            ("preview/worker/node_modules", "yes" if worker_nm_ok else "no", worker_nm_detail),
        ]
        print_table(env_rows, ("check", "ok", "detail"))
    else:
        print("\n(pass --live to make one cheap authenticated call per service and check Node/Chromium/node_modules)")

    failing_stages = [s for s in selected_stages if stage_missing.get(s)]
    print(
        json.dumps(
            {
                "script": "doctor",
                "live": args.live,
                "selected_stages": selected_stages,
                "failing_stages": failing_stages,
            }
        )
    )
    if failing_stages:
        sys.exit(1)


if __name__ == "__main__":
    main()
