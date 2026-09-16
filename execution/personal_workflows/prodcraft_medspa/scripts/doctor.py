"""
doctor.py
description: For every pipeline stage, lists each required env var present/missing (never prints
    values); with --live, makes one cheap authenticated call per service and prints
    `service | env present | live ok | detail`. Also checks Node >= 20, a Chromium install,
    template/node_modules, preview/worker/node_modules, the Gmail token's gmail.send scope (parsed
    from GMAIL_TOKEN_JSON, no network call), GOOGLE_SHEETS_MIRROR_ID + service-account presence,
    config.queue_pick, and PRODCRAFT_RECIPIENT_OVERRIDE (shown domain-only, with a warning that
    every send goes there while set). Exits non-zero if any stage selected via --stages is missing
    a required var — 'outreach' also fails if the Gmail token is confirmed missing gmail.send;
    'sheets' is opt-in like 'store'/'notify'. Must never crash with no env configured.
inputs: CLI: [--live] [--stages discovery,audit,enrich,preview,outreach,store,notify,sheets]. Env:
    every var in CONTRACTS.md's "Secrets only via env" list plus GOOGLE_SERVICE_ACCOUNT_PATH/
    GOOGLE_SERVICE_ACCOUNT_JSON and PRODCRAFT_RECIPIENT_OVERRIDE (all optional for the default,
    non-live run).
outputs: stdout: env-presence table, gmail-scope/sheets/store-config tables, and with --live, the
    live-check table + Node/Chromium/node_modules checks; final JSON stat line.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from execution.personal_workflows.prodcraft_medspa.common.store import get_store  # noqa: E402
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


def check_gmail_send_scope(settings) -> tuple[bool | None, str]:
    """Parses GMAIL_TOKEN_JSON's `scopes` field (never a network call — that's `_live_gmail`'s
    job) and reports whether `gmail.send` is present, since the daily loop's automated send needs
    it. None = skipped (no token configured, or an older token JSON with no `scopes` field —
    those are reported but never fail a stage; only a token confirmed to be missing the scope does).
    """
    token_raw = settings.GMAIL_TOKEN_JSON
    if not token_raw:
        return None, "skipped (GMAIL_TOKEN_JSON not set)"
    try:
        token_info = json.loads(token_raw)
    except (ValueError, TypeError) as exc:
        return False, f"GMAIL_TOKEN_JSON is not valid JSON: {type(exc).__name__}: {exc}"
    scopes = token_info.get("scopes")
    if not scopes:
        return None, "token JSON has no 'scopes' field — cannot verify (older token format)"
    has_send = any("gmail.send" in s for s in scopes)
    detail = f"scopes: {', '.join(scopes)}"
    return has_send, detail if has_send else f"missing gmail.send — {detail}"


def check_sheets_config() -> tuple[bool, str]:
    """GOOGLE_SHEETS_MIRROR_ID + a service-account key path/JSON must both be present before
    sync_sheets.py's live path (vs. its CSV fallback) can run."""
    mirror_id = os.environ.get("GOOGLE_SHEETS_MIRROR_ID", "").strip()
    sa_present = bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()) or bool(
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "").strip()
    )
    missing = []
    if not mirror_id:
        missing.append("GOOGLE_SHEETS_MIRROR_ID")
    if not sa_present:
        missing.append("GOOGLE_SERVICE_ACCOUNT_PATH (or GOOGLE_SERVICE_ACCOUNT_JSON)")
    if missing:
        return False, f"missing: {', '.join(missing)}"
    return True, "GOOGLE_SHEETS_MIRROR_ID + service account present"


def masked_recipient_override() -> tuple[str, str]:
    """Never print the full override address — only its domain — since doctor's output can land
    in CI logs. Returns (display_value, warning_or_empty)."""
    val = os.environ.get("PRODCRAFT_RECIPIENT_OVERRIDE", "").strip()
    if not val:
        return "(not set)", ""
    domain = val.split("@", 1)[1] if "@" in val else "?"
    return f"***@{domain}", "WARNING: every send goes to this address while PRODCRAFT_RECIPIENT_OVERRIDE is set"


def check_sender_config(store) -> tuple[bool, str]:
    """config.sender.name and .physical_address must be set before any outreach draft can pass
    lint_draft (CAN-SPAM rules 1 and 3). Seeded empty on purpose; the operator fills it once via
    the dashboard Config tab or store.set_config("sender", {...})."""
    try:
        sender = store.get_config("sender", {}) or {}
    except Exception as exc:  # noqa: BLE001 — report, never crash doctor
        return False, f"could not read config.sender: {type(exc).__name__}: {exc}"
    missing = [k for k in ("name", "physical_address") if not (sender.get(k) or "").strip()]
    if missing:
        return False, f"config.sender missing: {', '.join(missing)} (drafts fail CAN-SPAM lint until set)"
    return True, "config.sender name + physical_address set"


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

    print("\n=== Gmail token scope ===")
    scope_ok, scope_detail = check_gmail_send_scope(settings)
    print_table(
        [("gmail.send scope", "n/a" if scope_ok is None else ("yes" if scope_ok else "no"), scope_detail)],
        ("check", "ok", "detail"),
    )
    if scope_ok is False and "outreach" in selected_stages:
        # only a token confirmed missing the scope fails the stage; "n/a" (no token / no scopes
        # field) is already covered by the GMAIL_TOKEN_JSON presence check above.
        stage_missing.setdefault("outreach", []).append("GMAIL_TOKEN_JSON missing gmail.send scope")

    print("\n=== Google Sheets mirror ===")
    sheets_ok, sheets_detail = check_sheets_config()
    print_table([("sheets", "yes" if sheets_ok else "no", sheets_detail)], ("check", "ok", "detail"))
    if not sheets_ok and "sheets" in selected_stages:
        stage_missing.setdefault("sheets", []).append("GOOGLE_SHEETS_MIRROR_ID/service-account")

    print("\n=== Store config ===")
    try:
        # never crash without env: an unconfigured Supabase store is a report row, not a traceback
        store = get_store()
        sender_ok, sender_detail = check_sender_config(store)
        try:
            queue_pick = store.get_config("queue_pick", None)
        except Exception as exc:  # noqa: BLE001 — doctor reports, it does not fail
            queue_pick = f"error: {type(exc).__name__}: {exc}"
    except Exception as exc:  # noqa: BLE001 — doctor reports, it does not fail
        sender_ok, sender_detail = False, f"store unavailable: {type(exc).__name__}: {exc}"
        queue_pick = "store unavailable"
    override_display, override_warning = masked_recipient_override()
    config_rows = [
        ("config.sender", "yes" if sender_ok else "no", sender_detail),
        ("config.queue_pick", "n/a", str(queue_pick)),
        ("PRODCRAFT_RECIPIENT_OVERRIDE", "n/a", override_display),
    ]
    print_table(config_rows, ("check", "ok", "detail"))
    if override_warning:
        print(override_warning)
    if not sender_ok and "outreach" in selected_stages:
        stage_missing.setdefault("outreach", []).append("config.sender")

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
