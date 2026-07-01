"""
description: Send the v2 daily digest. Plain-text email via Gmail SMTP, with a
    breakdown by source + by tier (A/B/C/SKIP) and a link to the v2_jobs tab.
inputs:
    - jobs: list[NormalizedJob] for the day (already filtered by dedup; new-only)
    - stats: dict from filter_new() / orchestrator (counts per source, dedup totals)
    - env: GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD, GMAIL_NOTIFY_TO,
           SHEETS_SPREADSHEET_ID (for the dashboard link)
outputs:
    - Email sent via SMTP (or skipped + logged if creds missing).
    - Returns (sent: bool, subject: str, body: str).

Reuses v1's GMAIL_SMTP_* env vars so the user doesn't re-provision creds at cutover.
"""

from __future__ import annotations

import logging
import os
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob, RankedJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("notifier.email")

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587


def build_digest(
    jobs: list[NormalizedJob],
    stats: dict,
    sheet_id: str | None,
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> tuple[str, str]:
    """Compose (subject, body). Pure function — safe to unit-test.

    Body is a short dashboard summary (~25 lines), not a job dump. The full
    list lives in the sheet — body is the at-a-glance for the morning skim.
    """
    new_count = len(jobs)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ranked_by_hash = ranked_by_hash or {}

    per_source: dict[str, int] = {}
    for j in jobs:
        per_source[j.source.value] = per_source.get(j.source.value, 0) + 1
    src_count = len(per_source)

    subject = f"Job Search — {new_count} new jobs for {today}"

    # Per-source line: at most 6, sorted by count desc.
    src_lines = [f"  {src:<22} {n}" for src, n in sorted(per_source.items(), key=lambda kv: -kv[1])[:6]] or ["  (none)"]
    src_block = "\n".join(src_lines)

    # Tier breakdown.
    by_tier = stats.get("ranker", {}).get("by_tier", {}) if stats.get("ranker") else {}
    tier_block = (
        f"  A (top match):    {by_tier.get('A', 0)}\n"
        f"  B (promising):    {by_tier.get('B', 0)}\n"
        f"  C (skim):         {by_tier.get('C', 0)}"
    )

    # Top 5 picks: tier A > B > C, score desc, then posted_at desc.
    tier_order = {"A": 0, "B": 1, "C": 2, "SKIP": 3}

    def _key(j: NormalizedJob):
        rj = ranked_by_hash.get(j.content_hash)
        tier_rank = tier_order.get(rj.tier.value, 99) if rj else 99
        score = rj.score if rj else 0.0
        posted = j.posted_at or datetime.min.replace(tzinfo=timezone.utc)
        return (tier_rank, -score, -posted.timestamp())

    top = sorted(jobs, key=_key)[:5]
    top_lines = []
    for i, j in enumerate(top, start=1):
        rj = ranked_by_hash.get(j.content_hash) if ranked_by_hash else None
        # 2026-07-01 data-flow auditor: contract type and per-pick tier
        # were absent from the email top-5. Operator couldn't tell CDI
        # from Freelance from Unknown without opening the sheet.
        tier_label = f"[{rj.tier.value}] " if rj else ""
        contract_label = j.contract_type.value if j.contract_type else ""
        contract_part = f" [{contract_label}]" if contract_label and contract_label != "Unknown" else ""
        top_lines.append(
            f"  {i}. {tier_label}{j.title} — {j.company}{contract_part} — {j.location}\n"
            f"     {j.url}"
        )
    top_block = "\n".join(top_lines) or "  (no jobs ranked today)"

    dashboard = (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}/edit"
        if sheet_id else "(SHEETS_SPREADSHEET_ID not set)"
    )

    body = (
        f"Job Search — {today}\n"
        f"{new_count} new jobs from {src_count} sources today\n"
        f"\n"
        f"Per source:\n{src_block}\n"
        f"\n"
        f"Tier breakdown:\n{tier_block}\n"
        f"\n"
        f"Top 5 picks:\n{top_block}\n"
        f"\n"
        f"Full sheet: {dashboard}\n"
    )
    return subject, body


def send_digest(
    jobs: list[NormalizedJob],
    stats: dict,
    *,
    dry_run: bool = False,
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> tuple[bool, str, str]:
    """Compose + send. Returns (sent, subject, body) so callers can log/inspect."""
    sheet_id = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip() or None
    subject, body = build_digest(jobs, stats, sheet_id, ranked_by_hash=ranked_by_hash)

    if dry_run:
        logger.info("notifier.email [dry-run]: subject=%r body_lines=%d", subject, body.count("\n"))
        return False, subject, body

    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    to = os.environ.get("GMAIL_NOTIFY_TO", user).strip()

    if not (user and pw and to):
        logger.warning(
            "notifier.email: SMTP creds missing (GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD / GMAIL_NOTIFY_TO) — skipping send"
        )
        return False, subject, body

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = f"Job Search v2 <{user}>"
    msg["To"] = to

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.send_message(msg)
        logger.info("notifier.email: sent to %s — subject=%r", to, subject)
        return True, subject, body
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("notifier.email: SMTP send failed: %s", exc)
        return False, subject, body
