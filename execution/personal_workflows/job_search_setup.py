"""
job_search_setup.py
description: Validates Phase 0 provisioning for job-search-sheet pipeline. Checks env vars,
    validates Google service-account auth via a live spreadsheets().get() call, optionally
    bootstraps the workbook tabs.
inputs:  CLI flags --check-only, --bootstrap, --verbose. Env vars (SHEETS_SPREADSHEET_ID,
    GOOGLE_SERVICE_ACCOUNT_PATH, ADZUNA_APP_ID, ADZUNA_APP_KEY, JOOBLE_API_KEY,
    FRANCE_TRAVAIL_CLIENT_ID, FRANCE_TRAVAIL_CLIENT_SECRET, ANTHROPIC_API_KEY, GEMINI_API_KEY).
outputs: Stdout report of [OK] / [--MISSING] per check; exit code 0 if all OK, 1 otherwise.
    With --bootstrap: creates the 6 visible tabs + _meta tab via
    google_sheets_writer.ensure_workbook_initialized.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# sys.path shim — ensures execution/google/google_sheets_writer is importable
# when run as: py execution/personal_workflows/job_search_setup.py
# from the project root.
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_PLACEHOLDER_RE = re.compile(
    r"^(your_|YOUR_|REPLACE|placeholder|<.*>|TODO)",
    re.IGNORECASE,
)

_REQUIRED_VARS: list[tuple[str, str]] = [
    ("SHEETS_SPREADSHEET_ID",          ""),
    ("GOOGLE_SERVICE_ACCOUNT_PATH",    ""),
    ("ADZUNA_APP_ID",                  "sign up at https://developer.adzuna.com/signup"),
    ("ADZUNA_APP_KEY",                 "sign up at https://developer.adzuna.com/signup"),
    ("JOOBLE_API_KEY",                 "register at https://jooble.org/api/about"),
    ("FRANCE_TRAVAIL_CLIENT_ID",       "register at https://francetravail.io"),
    ("FRANCE_TRAVAIL_CLIENT_SECRET",   "register at https://francetravail.io"),
    ("ANTHROPIC_API_KEY",              ""),
    ("GEMINI_API_KEY",                 ""),
]

_CONFIG_PATH = _PROJECT_ROOT / "config" / "job_search.json"


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

def _fmt(status: str, label: str, hint: str = "") -> str:
    """Format a check line. status is [OK] or [--MISSING]."""
    base = f"{status:<12} {label}"
    if hint:
        base += f"  -> {hint}"
    return base


def _check_dotenv(verbose: bool) -> tuple[bool, str]:
    env_path = _PROJECT_ROOT / ".env"
    if env_path.exists():
        if verbose:
            return True, _fmt("[OK]", ".env file found", str(env_path))
        return True, _fmt("[OK]", ".env file found")
    return False, _fmt("[--MISSING]", ".env file", f"create {env_path} with required vars")


def _check_env_var(var: str, hint: str, verbose: bool) -> tuple[bool, str]:
    """Check a single env var: present, non-empty, not a placeholder."""
    value = os.environ.get(var, "")
    if not value:
        msg = hint if hint else f"set {var} in .env"
        return False, _fmt("[--MISSING]", var, msg)
    if _PLACEHOLDER_RE.match(value):
        msg = hint if hint else f"replace placeholder value in .env"
        return False, _fmt("[--MISSING]", f"{var}  (placeholder detected)", msg)
    # Never print the value — just [OK]
    return True, _fmt("[OK]", var)


def _check_service_account_json(verbose: bool) -> tuple[bool, str]:
    """Check that the service-account JSON file exists and parses."""
    raw_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
    if not raw_path:
        return False, _fmt("[--MISSING]", "Service account JSON file", "GOOGLE_SERVICE_ACCOUNT_PATH not set")

    key_path = Path(raw_path)
    if not key_path.is_absolute():
        key_path = _PROJECT_ROOT / key_path

    if not key_path.exists():
        return False, _fmt("[--MISSING]", "Service account JSON file", f"not found at {key_path}")

    try:
        with key_path.open(encoding="utf-8", errors="replace") as fh:
            data = json.load(fh)
        if not isinstance(data, dict) or "type" not in data:
            return False, _fmt("[--MISSING]", "Service account JSON file", "file exists but does not look like a GCP service-account key")
        detail = f"type={data.get('type')}, project={data.get('project_id', 'unknown')}" if verbose else ""
        return True, _fmt("[OK]", "Service account JSON file exists", detail)
    except json.JSONDecodeError as exc:
        return False, _fmt("[--MISSING]", "Service account JSON file", f"JSON parse error: {exc}")
    except Exception as exc:
        return False, _fmt("[--MISSING]", "Service account JSON file", f"read error: {exc}")


def _check_sheets_api(verbose: bool) -> tuple[bool, str, object]:
    """Attempt live Sheets API auth + workbook open. Returns (ok, line, spreadsheet_or_None)."""
    spreadsheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not spreadsheet_id:
        return False, _fmt("[--MISSING]", "Google Sheets API (live check)", "SHEETS_SPREADSHEET_ID not set"), None

    try:
        from execution.google.google_sheets_writer import get_client, open_workbook  # noqa: E402
        get_client()  # raises on auth failure
        sp = open_workbook(spreadsheet_id)
        n_tabs = len(sp.worksheets())
        detail = f"{n_tabs} existing tab(s)" if verbose else f"{n_tabs} existing tab(s)"
        return True, _fmt("[OK]", f"Workbook '{sp.title}' is reachable ({detail})"), sp
    except ImportError as exc:
        return False, _fmt("[--MISSING]", "Google Sheets API (live check)", f"import error: {exc} — run: py -m pip install gspread tenacity"), None
    except Exception as exc:
        hint = str(exc)
        # Detect common failure modes and give actionable guidance
        if "403" in hint or "PERMISSION_DENIED" in hint.upper():
            # Include the service-account email so the user knows exactly who to share with
            sa_email = "unknown"
            try:
                raw_path = os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "").strip()
                if raw_path:
                    key_path = Path(raw_path)
                    if not key_path.is_absolute():
                        key_path = _PROJECT_ROOT / key_path
                    with key_path.open(encoding="utf-8", errors="replace") as _fh:
                        _key_data = json.load(_fh)
                    sa_email = _key_data.get("client_email", "unknown")
            except Exception:  # noqa: BLE001 — fallback to generic message is safe
                pass
            hint = f"403 Forbidden — share the spreadsheet with {sa_email} (Editor)"
        elif "404" in hint or "not found" in hint.lower():
            hint = "404 Not Found — verify SHEETS_SPREADSHEET_ID is the correct spreadsheet ID"
        elif "401" in hint or "UNAUTHENTICATED" in hint.upper():
            hint = "401 Unauthenticated — service account key may be expired or revoked"
        return False, _fmt("[--MISSING]", "Google Sheets API (live check)", hint), None


def _check_config(verbose: bool) -> tuple[bool, str, dict]:
    """Check config/job_search.json exists and parses."""
    if not _CONFIG_PATH.exists():
        return False, _fmt("[--MISSING]", "config/job_search.json", f"not found at {_CONFIG_PATH}"), {}
    try:
        with _CONFIG_PATH.open(encoding="utf-8", errors="replace") as fh:
            cfg = json.load(fh)
        tabs = cfg.get("visible_tabs", [])
        detail = f"{len(tabs)} visible tabs" if verbose else ""
        return True, _fmt("[OK]", "config/job_search.json parses", detail), cfg
    except json.JSONDecodeError as exc:
        return False, _fmt("[--MISSING]", "config/job_search.json", f"JSON parse error: {exc}"), {}
    except Exception as exc:
        return False, _fmt("[--MISSING]", "config/job_search.json", f"read error: {exc}"), {}


def _run_bootstrap(spreadsheet, cfg: dict, verbose: bool) -> tuple[bool, str]:
    """Call ensure_workbook_initialized using config values."""
    if spreadsheet is None:
        return False, _fmt("[--MISSING]", "Bootstrap skipped", "Sheets API check failed; cannot bootstrap")
    if not cfg:
        return False, _fmt("[--MISSING]", "Bootstrap skipped", "config/job_search.json unavailable")
    try:
        from execution.google.google_sheets_writer import ensure_workbook_initialized  # noqa: E402
        visible_tabs = cfg.get("visible_tabs", [])
        column_headers = cfg.get("column_headers", [])
        ensure_workbook_initialized(spreadsheet, visible_tabs, column_headers)
        detail = f"tabs ensured: {', '.join(visible_tabs)}" if verbose else f"{len(visible_tabs)} tabs"
        return True, _fmt("[OK]", f"Bootstrap complete ({detail})")
    except Exception as exc:
        return False, _fmt("[--MISSING]", "Bootstrap", f"error: {exc}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Phase 0 setup check for job-search-sheet pipeline. "
            "Validates env vars, service-account auth, and live Sheets API access."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  py execution/personal_workflows/job_search_setup.py --check-only\n"
            "  py execution/personal_workflows/job_search_setup.py --bootstrap\n"
            "  py execution/personal_workflows/job_search_setup.py --bootstrap --verbose\n"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help="Run checks only; do not touch the sheet (default when no flags given).",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        default=False,
        help="Also call ensure_workbook_initialized to create tabs (idempotent).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        default=False,
        help="Print extra context per check.",
    )
    args = parser.parse_args()

    verbose = args.verbose
    do_bootstrap = args.bootstrap

    print("== Job Search Sheet -- Phase 0 Setup Check ==")
    print()

    results: list[tuple[bool, str]] = []

    # --- .env file ---
    ok, line = _check_dotenv(verbose)
    results.append((ok, line))
    print(line)

    # --- Required env vars ---
    for var, hint in _REQUIRED_VARS:
        ok, line = _check_env_var(var, hint, verbose)
        results.append((ok, line))
        print(line)

    # --- Service account JSON ---
    ok, line = _check_service_account_json(verbose)
    results.append((ok, line))
    print(line)

    # --- Live Sheets API check ---
    ok, line, spreadsheet = _check_sheets_api(verbose)
    results.append((ok, line))
    print(line)

    # --- config/job_search.json ---
    ok, line, cfg = _check_config(verbose)
    results.append((ok, line))
    print(line)

    # --- Optional bootstrap ---
    if do_bootstrap:
        ok, line = _run_bootstrap(spreadsheet, cfg, verbose)
        results.append((ok, line))
        print(line)

    # --- Summary ---
    n_total = len(results)
    n_ok = sum(1 for ok, _ in results if ok)
    n_missing = n_total - n_ok

    print()
    if n_missing == 0:
        print(f"Summary: all {n_total} checks passed. Exit code 0.")
    else:
        print(f"Summary: {n_missing} missing, {n_ok} OK. Exit code 1.")

    return 0 if n_missing == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
