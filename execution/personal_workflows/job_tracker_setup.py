"""
job_tracker_setup.py
description: One-shot setup helper for the French PM/PO Job Tracker. Validates required
    environment variables, checks pip package availability, optionally installs missing
    packages, and optionally initialises the SQLite database. Run once after first checkout.
inputs: CLI flags (--check-only, --install-deps, --init-db); env vars from .env.
outputs: Printed status report (stdout); optional DB file created at resolved path;
    optional pip install of missing packages.
"""

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import argparse


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_REQUIRED_ENV_VARS = [
    "FIRECRAWL_API_KEY",
    "SERPER_API_KEY",
    "FRANCE_TRAVAIL_CLIENT_ID",
    "FRANCE_TRAVAIL_CLIENT_SECRET",
    "INSEE_SIRENE_API_KEY",
    "GMAIL_SMTP_USER",
    "GMAIL_SMTP_APP_PASSWORD",
    "JOB_TRACKER_RECIPIENT",
]

_REQUIRED_PACKAGES = [
    "firecrawl-py",
    "langdetect",
    "requests",
    "python-dotenv",
    "freezegun",
    "pytest",
]

# Map pip package names to importable module names (where they differ)
_PACKAGE_TO_MODULE = {
    "firecrawl-py": "firecrawl",
    "python-dotenv": "dotenv",
    "freezegun": "freezegun",
    "langdetect": "langdetect",
    "requests": "requests",
    "pytest": "pytest",
}


# ---------------------------------------------------------------------------
# Check helpers
# ---------------------------------------------------------------------------

def _check_env_vars() -> list[str]:
    """Print env var status; return list of missing var names."""
    print("\n=== Environment Variables ===")
    missing: list[str] = []
    for var in _REQUIRED_ENV_VARS:
        value = os.environ.get(var)
        if value:
            print(f"  [OK]       {var}")
        else:
            print(f"  [--MISSING] {var}")
            missing.append(var)
    return missing


def _check_packages() -> list[str]:
    """Print package availability; return list of missing pip package names."""
    print("\n=== Python Packages ===")
    missing: list[str] = []
    for pkg in _REQUIRED_PACKAGES:
        module_name = _PACKAGE_TO_MODULE.get(pkg, pkg)
        spec = importlib.util.find_spec(module_name)
        if spec is not None:
            print(f"  [OK]       {pkg}")
        else:
            print(f"  [--MISSING] {pkg}")
            missing.append(pkg)
    return missing


def _resolve_db_path() -> Path:
    """Resolve DB path from env or config; never reveal secrets."""
    env_val = os.environ.get("JOB_TRACKER_DB_PATH", "")
    if env_val:
        return Path(env_val)
    # Fall back to config
    try:
        from execution.personal_workflows._jt_utils import load_jt_config
        cfg = load_jt_config()
        raw = cfg.get("default_db_path", ".tmp/job_tracker.db")
        return (PROJECT_ROOT / raw).resolve()
    except Exception:
        return PROJECT_ROOT / ".tmp" / "job_tracker.db"


def _check_db(db_path: Path) -> None:
    """Report whether the DB file exists."""
    print("\n=== Database ===")
    if db_path.exists():
        size_kb = db_path.stat().st_size // 1024
        print(f"  [OK]        {db_path}  ({size_kb} KB)")
    else:
        print(f"  [--NOT FOUND] {db_path}")
        print("    Run with --init-db to create it.")


def _print_next_steps(missing_vars: list[str], missing_pkgs: list[str]) -> None:
    """Print actionable next-step instructions."""
    print("\n=== Next Steps ===")
    if missing_vars:
        print("  1. Add the missing env vars to your .env file:")
        for var in missing_vars:
            print(f"       {var}=<your_value>")
    if missing_pkgs:
        print(
            "  2. Install missing packages:\n"
            f"       py execution\\personal_workflows\\job_tracker_setup.py --install-deps"
        )
    print(
        "  3. Initialise the database (first time only):\n"
        "       py execution\\personal_workflows\\job_tracker_setup.py --init-db"
    )
    print(
        "  4. Run a dry-run to verify end-to-end (no email sent):\n"
        "       py execution\\personal_workflows\\job_tracker_pm_france.py --mock --dry-run"
    )
    print(
        "  5. Register the daily Modal cron (replace TOKEN with your token):\n"
        "       modal deploy execution/modal_webhook.py"
    )
    print()


# ---------------------------------------------------------------------------
# Install deps
# ---------------------------------------------------------------------------

def _install_missing_packages(missing: list[str]) -> bool:
    """Pip-install each missing package. Returns True if all succeeded."""
    if not missing:
        print("\n=== Install Dependencies ===")
        print("  All required packages already installed. Nothing to do.")
        return True

    print("\n=== Install Dependencies ===")
    all_ok = True
    for pkg in missing:
        print(f"  Installing {pkg} ...", end=" ", flush=True)
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", pkg],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            print("OK")
        else:
            print(f"FAILED (exit {result.returncode})")
            # Print stderr without leaking secrets — pip output is safe
            for line in result.stderr.strip().splitlines()[-5:]:
                print(f"    {line}")
            all_ok = False
    return all_ok


# ---------------------------------------------------------------------------
# Init DB
# ---------------------------------------------------------------------------

def _init_db(db_path: Path) -> bool:
    """Call init_db() to create the schema. Returns True on success."""
    print("\n=== Initialise Database ===")
    try:
        from execution.personal_workflows.job_tracker_db import init_db
        conn = init_db(db_path)
        # Verify tables were created
        tables = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        ).fetchall()
        table_names = [row[0] for row in tables]
        conn.close()
        print(f"  Database ready at: {db_path}")
        print(f"  Tables: {', '.join(table_names)}")
        return True
    except Exception as exc:
        print(f"  ERROR: Could not initialise database: {exc}")
        return False


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Job Tracker setup helper. Run once after first checkout to validate "
            "your environment, install dependencies, and initialise the SQLite DB."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Examples:\n"
            "  py execution\\personal_workflows\\job_tracker_setup.py          # check only\n"
            "  py execution\\personal_workflows\\job_tracker_setup.py --install-deps\n"
            "  py execution\\personal_workflows\\job_tracker_setup.py --init-db\n"
            "  py execution\\personal_workflows\\job_tracker_setup.py --install-deps --init-db\n"
        ),
    )
    parser.add_argument(
        "--check-only",
        action="store_true",
        default=False,
        help="Print env/package/DB status and exit (default behaviour when no flags given).",
    )
    parser.add_argument(
        "--install-deps",
        action="store_true",
        default=False,
        help="Pip-install any missing packages from the required list.",
    )
    parser.add_argument(
        "--init-db",
        action="store_true",
        default=False,
        help="Create (or migrate) the SQLite database schema.",
    )
    args = parser.parse_args()

    # Default: check-only when no action flags are given
    no_action = not (args.install_deps or args.init_db)
    run_check = args.check_only or no_action

    db_path = _resolve_db_path()
    exit_code = 0

    # Always run check first (info only — never exits 1)
    if run_check or args.install_deps or args.init_db:
        missing_vars = _check_env_vars()
        missing_pkgs = _check_packages()
        _check_db(db_path)

    if args.install_deps:
        ok = _install_missing_packages(missing_pkgs)
        if not ok:
            exit_code = 1

    if args.init_db:
        ok = _init_db(db_path)
        if not ok:
            exit_code = 1

    if run_check:
        _print_next_steps(missing_vars, missing_pkgs)

    return exit_code


if __name__ == "__main__":
    sys.exit(main())
