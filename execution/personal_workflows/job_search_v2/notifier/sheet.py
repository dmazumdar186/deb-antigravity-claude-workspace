"""
description: Append v2 NormalizedJobs to a single rolling Google Sheet tab.
inputs:
    - list[NormalizedJob] (the new-today jobs after dedup)
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH (defaults: credentials/service_account.json)
    - tab name (default "v2_jobs") — kept separate from v1 tabs so the rollback is one config change
outputs:
    - Rows appended to the spreadsheet, idempotent because dedup upstream guarantees no repeats.
    - Returns (rows_appended, ok) tuple.

v2 schema (12 cols, intentionally simpler than v1's 14):
    A: dedup_hash   B: first_seen   C: posted       D: company
    E: title        F: location     G: source       H: contract
    I: remote       J: url          K: status       L: notes

The header row is written exactly once (on first run with --ensure-header).
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob  # noqa: E402

load_dotenv()
logger = logging.getLogger("notifier.sheet")

V2_TAB = "v2_jobs"
HEADERS = [
    "dedup_hash", "first_seen", "posted", "company", "title", "location",
    "source", "contract", "remote", "url", "status", "notes",
]


def _job_to_row(job: NormalizedJob, run_now: str) -> list[str]:
    posted = job.posted_at.isoformat()[:10] if job.posted_at else ""
    return [
        job.content_hash,
        run_now[:10],
        posted,
        job.company,
        job.title,
        job.location,
        job.source.value,
        job.contract_type.value,
        job.remote_mode.value,
        str(job.url),
        "New",
        "",
    ]


def append_jobs(
    jobs: list[NormalizedJob],
    *,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
    tab: str = V2_TAB,
    dry_run: bool = False,
) -> tuple[int, bool]:
    """Append v2 NormalizedJobs to the Google Sheet. Returns (rows_appended, ok).

    Failure modes:
      - gspread not installed → log, return (0, False).
      - missing creds → log, return (0, False).
      - sheet API error → log, return (n_attempted, False).
    """
    if not jobs:
        logger.info("notifier.sheet: 0 jobs to append, skipping")
        return 0, True

    spreadsheet_id = spreadsheet_id or os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    sa_path = service_account_path or Path(
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    rows = [_job_to_row(j, now_iso) for j in jobs]

    if dry_run:
        logger.info("notifier.sheet [dry-run]: would append %d rows to tab %s", len(rows), tab)
        return len(rows), True

    if not spreadsheet_id:
        logger.warning("notifier.sheet: SHEETS_SPREADSHEET_ID missing — skipping append")
        return 0, False

    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as exc:
        logger.warning("notifier.sheet: gspread / google-auth not installed (%s) — skipping append", exc)
        return 0, False

    if not sa_path.exists():
        logger.warning("notifier.sheet: service account JSON not found at %s — skipping append", sa_path)
        return 0, False

    try:
        creds = Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        sp = client.open_by_key(spreadsheet_id)
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            ws = sp.add_worksheet(title=tab, rows="1000", cols=str(len(HEADERS)))
            ws.append_row(HEADERS)
            logger.info("notifier.sheet: created tab %s with headers", tab)

        # Ensure headers if the tab existed but was blank
        if not ws.row_values(1):
            ws.append_row(HEADERS)

        ws.append_rows(rows, value_input_option="USER_ENTERED")
        logger.info("notifier.sheet: appended %d rows to %s/%s", len(rows), spreadsheet_id, tab)
        return len(rows), True
    except Exception as exc:  # noqa: BLE001 — gspread surface is broad; log + return False
        logger.error("notifier.sheet: append failed: %s", exc)
        return len(rows), False
