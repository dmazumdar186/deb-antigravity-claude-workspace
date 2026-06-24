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
    """Compose (subject, body). Pure function — safe to unit-test."""
    new_count = len(jobs)
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ranked_by_hash = ranked_by_hash or {}

    # Subject reflects ranker tier breakdown when present.
    by_tier = stats.get("ranker", {}).get("by_tier", {}) if stats.get("ranker") else {}
    if by_tier:
        tier_summary = f" (A:{by_tier.get('A', 0)} B:{by_tier.get('B', 0)} C:{by_tier.get('C', 0)})"
    else:
        tier_summary = ""
    subject = f"Job Search v2 — {new_count} new for {today}{tier_summary}"

    # Per-source breakdown
    per_source: dict[str, int] = {}
    for j in jobs:
        per_source[j.source.value] = per_source.get(j.source.value, 0) + 1
    src_lines = "\n".join(f"  {src:<18} {n}" for src, n in sorted(per_source.items())) or "  (none)"

    # Sort top jobs: tier A > B > C > placeholder, then by posted_at desc.
    tier_order = {"A": 0, "B": 1, "C": 2, "SKIP": 3}
    def _key(j: NormalizedJob):
        rj = ranked_by_hash.get(j.content_hash)
        tier_rank = tier_order.get(rj.tier.value, 99) if rj else 99
        posted = j.posted_at or datetime.min.replace(tzinfo=timezone.utc)
        # Negative posted for desc within tier
        return (tier_rank, -posted.timestamp())
    top = sorted(jobs, key=_key)[:15]

    job_lines = []
    for j in top:
        posted = j.posted_at.strftime("%Y-%m-%d") if j.posted_at else "?"
        also = f" (also on: {', '.join(s.value for s in j.also_seen_on)})" if j.also_seen_on else ""
        rj = ranked_by_hash.get(j.content_hash)
        tier_tag = f"[{rj.tier.value}] " if rj and rj.tier.value != "B" else ""
        reasoning = f"\n      -> {rj.reasoning}" if rj and rj.reasoning else ""
        job_lines.append(
            f"  {tier_tag}[{j.source.value}] {posted}  {j.title}\n"
            f"      {j.company} — {j.location} — {j.contract_type.value} — {j.remote_mode.value}{also}{reasoning}\n"
            f"      {j.url}"
        )
    top_block = "\n\n".join(job_lines) or "  (no top jobs)"

    dashboard = ""
    if sheet_id:
        dashboard = f"\nDashboard: https://docs.google.com/spreadsheets/d/{sheet_id}/edit\n"

    loc_reasons = stats.get("location_by_reason", {})
    loc_breakdown = ""
    if loc_reasons:
        loc_breakdown = "\n  location filter reasons:\n" + "\n".join(
            f"    {k:<24} {v}" for k, v in sorted(loc_reasons.items())
        ) + "\n"
    pipeline_totals = (
        f"\nPipeline counters:\n"
        f"  total_fetched:        {stats.get('total_fetched', '?')}\n"
        f"  after_normalize:     {stats.get('after_normalize', '?')}\n"
        f"  after_dedup_new:     {stats.get('after_dedup_new', '?')}\n"
        f"  already_seen:        {stats.get('already_seen', '?')}\n"
        f"  after_location_filter: {stats.get('after_location_filter', '?')}\n"
        f"  location_rejected:   {stats.get('location_rejected', '?')}\n"
        f"{loc_breakdown}"
    )

    body = (
        f"Job Search v2 — {today}\n"
        f"========================\n\n"
        f"{new_count} new job(s) added.\n\n"
        f"Per source:\n{src_lines}\n\n"
        f"Top 10 (most recent):\n\n{top_block}\n"
        f"{pipeline_totals}"
        f"{dashboard}\n"
        f"— job_search_v2"
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
