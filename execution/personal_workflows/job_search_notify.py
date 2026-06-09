"""
job_search_notify.py
description: Send a plain-text Gmail summary after each job-search-sheet run.
    Self-contained — used both locally and from the GitHub Actions cron.
    Silently skips with a warning if SMTP credentials are missing (graceful degradation).
inputs:
    - Env vars (all required for actual send): GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD,
      GMAIL_NOTIFY_TO (defaults to GMAIL_SMTP_USER).
    - send_run_summary(summary_dict) — called from job_search_sheet.py Stage 6.
    - CLI for local testing: --dry-run / --recipient / --summary-json
outputs:
    - Sent email (or log line if dry-run / skipped).
    - Exit code 0 (sent or skipped) / 1 (SMTP failure).
"""

import argparse
import json
import os
import smtplib
import sys
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from execution.personal_workflows._jt_utils import setup_logging  # noqa: E402

logger = setup_logging("job_search_notify")

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587

_PROD_SHEET_URL_TEMPLATE = "https://docs.google.com/spreadsheets/d/{sid}/edit"


def _build_body(summary: dict, sheet_id: str | None) -> tuple[str, str]:
    """Return (subject, body) for a run summary email."""
    write_counts = summary.get("written_per_tab", {}) or {}
    total_added = sum(int(v) for v in write_counts.values())
    discovered = summary.get("discovered", "?")
    llm_dropped = summary.get("llm_dropped", "?")
    after_dedup = summary.get("after_dedup", "?")
    run_at = summary.get("run_at", "")

    subject = f"Job Search — {total_added} new job{'s' if total_added != 1 else ''} added today"

    breakdown = "\n".join(f"  {tab:<18} {n}" for tab, n in write_counts.items())
    dashboard_line = ""
    if sheet_id:
        url = _PROD_SHEET_URL_TEMPLATE.format(sid=sheet_id)
        dashboard_line = f"\nOpen dashboard: {url}\n"

    body = (
        f"Daily job-search run finished at {run_at}.\n\n"
        f"New jobs added today: {total_added}\n\n"
        f"Per tab:\n{breakdown}\n\n"
        f"Pipeline counters:\n"
        f"  Raw discovered:        {discovered}\n"
        f"  After dedup:           {after_dedup}\n"
        f"  LLM-dropped:           {llm_dropped}\n"
        f"{dashboard_line}\n"
        f"— job-search-sheet pipeline\n"
    )
    return subject, body


def send_run_summary(summary: dict) -> bool:
    """Send a single daily-summary email. Returns True if sent, False if skipped or failed.
    Reads SMTP creds from env. Non-fatal: logs and returns False on missing creds or SMTP error."""
    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    to = os.environ.get("GMAIL_NOTIFY_TO", user).strip()
    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip() or None

    if not (user and pw and to):
        logger.warning(
            "job_search_notify: skipping email — missing GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD / GMAIL_NOTIFY_TO."
            " To enable: create a Gmail App Password (myaccount.google.com → Security → App passwords) and set"
            " GMAIL_SMTP_USER (your gmail) + GMAIL_SMTP_APP_PASSWORD (16-char app password) in .env."
        )
        return False

    subject, body = _build_body(summary, sheet_id)
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = user
    msg["To"] = to

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.sendmail(user, [to], msg.as_string())
        logger.info("job_search_notify: sent summary email to %s (subject=%r)", to, subject)
        return True
    except Exception as exc:  # noqa: BLE001 — non-fatal; cron should not fail because of email
        logger.error("job_search_notify: SMTP send failed: %s", exc)
        return False


# ---------------------------------------------------------------------------
# CLI for local testing
# ---------------------------------------------------------------------------

def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--summary-json", help="Path to a runs-log JSON line (most recent line of .tmp/job_search/job_search_runs.jsonl by default)")
    p.add_argument("--dry-run", action="store_true", help="Print the email body without sending")
    p.add_argument("--recipient", help="Override recipient (defaults to env GMAIL_NOTIFY_TO or GMAIL_SMTP_USER)")
    args = p.parse_args()

    # Load a summary: either from --summary-json or from the latest runs-log line
    if args.summary_json:
        summary = json.loads(Path(args.summary_json).read_text(encoding="utf-8"))
    else:
        runs_log = ROOT / ".tmp" / "job_search" / "job_search_runs.jsonl"
        if not runs_log.exists():
            print(f"[FAIL] no runs log at {runs_log}")
            return 1
        last_line = ""
        for ln in runs_log.read_text(encoding="utf-8", errors="replace").splitlines():
            if ln.strip():
                last_line = ln
        summary = json.loads(last_line)

    if args.recipient:
        os.environ["GMAIL_NOTIFY_TO"] = args.recipient

    subject, body = _build_body(summary, os.environ.get("SHEETS_SPREADSHEET_ID", "").strip() or None)
    if args.dry_run:
        print(f"Subject: {subject}\n\n{body}")
        return 0
    return 0 if send_run_summary(summary) else 1


if __name__ == "__main__":
    sys.exit(main())
