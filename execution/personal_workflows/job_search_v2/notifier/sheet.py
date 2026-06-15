"""
description: Route v2 NormalizedJobs into the 6 destination tabs (PM, AI PM, AI Automation,
    AI Mobile, AI Process, AI Consultant) by title-synonym matching. Same 14-column schema
    as v1 so the existing Excel/Sheet layout works unchanged.
inputs:
    - list[NormalizedJob] (filtered, ranked)
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH (default credentials/service_account.json)
    - config: tab_routing section of config/job_search_v2.json
outputs:
    - Rows appended to the matching destination tab in the Google Sheet
    - Returns (rows_appended, per_tab_counts, ok)

14-column schema (matches v1 exactly so existing user filters/formats keep working):
    A: _id            B: First Seen    C: Posted       D: Company
    E: Title          F: Country       G: Location     H: Remote?
    I: Contract       J: Source        K: Also Seen On L: Link
    M: Status         N: Notes

Optionally a 15th column (O: Tier) is appended when ranker results are available.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    NormalizedJob,
    RankedJob,
)

load_dotenv()
logger = logging.getLogger("notifier.sheet")

HEADERS = [
    "_id", "First Seen", "Posted", "Company", "Title", "Country",
    "Location", "Remote?", "Contract", "Source", "Also Seen On",
    "Link", "Status", "Notes", "Tier",
]


def route_to_tab(title: str, routing_config: dict) -> str:
    """Map a job title to a destination tab via title synonyms.

    Strategy: longest synonym wins. This way 'ai product manager' (more specific)
    beats 'product manager' (catchall) when both would match the same title.
    """
    title_lower = title.lower().strip()
    titles_cfg = routing_config.get("titles", {})

    # Flatten to (synonym, tab) tuples, then sort by synonym length descending.
    all_synonyms: list[tuple[str, str]] = []
    for key, cfg in titles_cfg.items():
        tab = cfg.get("tab", key)
        for syn in cfg.get("synonyms", []):
            all_synonyms.append((syn.lower(), tab))
    all_synonyms.sort(key=lambda t: -len(t[0]))

    for syn, tab in all_synonyms:
        if syn in title_lower:
            return tab
    return routing_config.get("fallback_tab", "PM")


def _job_to_row(job: NormalizedJob, ranked: RankedJob | None, run_now: str) -> list[str]:
    posted = job.posted_at.isoformat()[:10] if job.posted_at else ""
    also_seen = ", ".join(s.value for s in job.also_seen_on) if job.also_seen_on else ""
    tier = ranked.tier.value if ranked else ""
    return [
        job.content_hash[:16],                          # A: _id (truncated for readability)
        run_now[:10],                                   # B: First Seen
        posted,                                          # C: Posted
        job.company,                                     # D: Company
        job.title,                                       # E: Title
        "",                                              # F: Country (we don't normalize country yet)
        job.location,                                    # G: Location
        job.remote_mode.value,                           # H: Remote?
        job.contract_type.value,                         # I: Contract
        job.source.value,                                # J: Source
        also_seen,                                       # K: Also Seen On
        str(job.url),                                    # L: Link
        "New",                                           # M: Status
        ranked.reasoning if ranked else "",              # N: Notes (use ranker reasoning if present)
        tier,                                            # O: Tier
    ]


def append_jobs(
    jobs: list[NormalizedJob],
    *,
    ranked_by_hash: dict[str, RankedJob] | None = None,
    routing_config: dict | None = None,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
    dry_run: bool = False,
) -> tuple[int, dict[str, int], bool]:
    """Append jobs to their routed tabs. Returns (total_rows, per_tab_counts, ok).

    Failure modes:
      - gspread / google-auth not installed → log + return (0, {}, False).
      - missing creds / spreadsheet_id → log + return (0, {}, False).
      - per-tab append failure → log + skip that tab; other tabs still attempt.
    """
    if not jobs:
        logger.info("notifier.sheet: 0 jobs to append, skipping")
        return 0, {}, True

    routing_config = routing_config or {"fallback_tab": "PM", "titles": {}}
    ranked_by_hash = ranked_by_hash or {}
    spreadsheet_id = spreadsheet_id or os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    sa_path = service_account_path or Path(
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
    )
    now_iso = datetime.now(timezone.utc).isoformat()

    # Group rows by destination tab so each tab gets a single batched append call.
    per_tab: dict[str, list[list[str]]] = {}
    for job in jobs:
        tab = route_to_tab(job.title, routing_config)
        ranked = ranked_by_hash.get(job.content_hash)
        per_tab.setdefault(tab, []).append(_job_to_row(job, ranked, now_iso))

    per_tab_counts = {tab: len(rows) for tab, rows in per_tab.items()}

    if dry_run:
        logger.info("notifier.sheet [dry-run]: would append %s", per_tab_counts)
        return sum(per_tab_counts.values()), per_tab_counts, True

    if not spreadsheet_id:
        logger.warning("notifier.sheet: SHEETS_SPREADSHEET_ID missing — skipping append")
        return 0, {}, False

    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as exc:
        logger.warning("notifier.sheet: gspread / google-auth not installed (%s) — skipping append", exc)
        return 0, {}, False

    if not sa_path.exists():
        logger.warning("notifier.sheet: service account JSON not found at %s — skipping append", sa_path)
        return 0, {}, False

    try:
        creds = Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        sp = client.open_by_key(spreadsheet_id)

        total_written = 0
        ok = True
        for tab, rows in per_tab.items():
            try:
                ws = sp.worksheet(tab)
            except gspread.WorksheetNotFound:
                ws = sp.add_worksheet(title=tab, rows="1000", cols=str(len(HEADERS)))
                ws.append_row(HEADERS)
                logger.info("notifier.sheet: created missing tab %s with headers", tab)

            # Expand to 15 cols if the worksheet was provisioned narrower (v1 used 14).
            if ws.col_count < len(HEADERS):
                try:
                    ws.resize(rows=ws.row_count, cols=len(HEADERS))
                except Exception as exc:  # noqa: BLE001 — resize may fail under quota; log + continue
                    logger.warning("notifier.sheet: resize %s to %d cols failed: %s", tab, len(HEADERS), exc)

            # Ensure header is present (covers fresh / wiped tabs).
            first_row = ws.row_values(1)
            if not first_row:
                ws.append_row(HEADERS)
            elif len(first_row) < len(HEADERS):
                # v1 had 14-col header; we ship 15 (added Tier). Patch the 15th cell.
                ws.update_acell("O1", "Tier")

            try:
                ws.append_rows(rows, value_input_option="USER_ENTERED")
                total_written += len(rows)
                logger.info("notifier.sheet: appended %d rows to %s", len(rows), tab)
            except Exception as exc:  # noqa: BLE001 — gspread surface; log + continue with other tabs
                logger.error("notifier.sheet: append to %s failed: %s", tab, exc)
                ok = False

        return total_written, per_tab_counts, ok
    except Exception as exc:  # noqa: BLE001 — auth or open_by_key failure
        logger.error("notifier.sheet: setup failed: %s", exc)
        return 0, per_tab_counts, False
