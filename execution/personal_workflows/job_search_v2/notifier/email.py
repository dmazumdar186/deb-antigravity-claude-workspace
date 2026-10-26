"""
description: Send the v2 daily digest over Gmail SMTP. The email is ONE table
    (Company | Job title | Location | Link), one row per new job, and nothing
    else — operator standing order 2026-10-26: "When it says 25 new jobs were
    found, the table should exactly report that only. Anything else is garbage."
inputs:
    - jobs: list[NormalizedJob] appended to the sheet this run (new-only)
    - stats: dict from the orchestrator (only mutated: email_error)
    - ranked_by_hash: dict[content_hash -> RankedJob] for score-desc ordering
    - env: GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD, GMAIL_NOTIFY_TO
outputs:
    - multipart/alternative email: plain part = markdown pipe table,
      HTML part = a single <table>. n == 0 -> no email, returns skipped.
    - Returns (sent: bool, subject: str, body: str) where body is the plain part.

Reuses v1's GMAIL_SMTP_* env vars so the user doesn't re-provision creds at cutover.
"""

from __future__ import annotations

import html
import logging
import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from urllib.parse import urlsplit

from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import NormalizedJob, RankedJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("notifier.email")

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587

HEADERS = ("Company", "Job title", "Location", "Link")
_WS = re.compile(r"\s+")


def _clean(value: object) -> str:
    """Collapse whitespace; never let a newline break a table row."""
    return _WS.sub(" ", str(value or "")).strip()


def _link_text(url: str) -> str:
    """Display text for the link: host + path, no scheme / query / fragment."""
    parts = urlsplit(url)
    return (parts.netloc + parts.path.rstrip("/")) or url


def sort_jobs(
    jobs: list[NormalizedJob],
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> list[NormalizedJob]:
    """Ranker final score descending; title as the tie-break / fallback."""
    ranked_by_hash = ranked_by_hash or {}

    def _key(j: NormalizedJob):
        rj = ranked_by_hash.get(j.content_hash)
        score = rj.score if rj is not None else 0.0
        return (-score, _clean(j.title).lower())

    return sorted(jobs, key=_key)


def _rows(jobs: list[NormalizedJob]) -> list[tuple[str, str, str, str]]:
    return [(_clean(j.company), _clean(j.title), _clean(j.location), _clean(str(j.url))) for j in jobs]


def build_plain_table(jobs: list[NormalizedJob]) -> str:
    """Markdown pipe table. Cell `|` is escaped as `\\|`. Nothing else."""
    def cell(s: str) -> str:
        return s.replace("|", "\\|")

    lines = ["| " + " | ".join(HEADERS) + " |", "|" + "|".join(" --- " for _ in HEADERS) + "|"]
    for company, title, location, url in _rows(jobs):
        lines.append(f"| {cell(company)} | {cell(title)} | {cell(location)} | {cell(url)} |")
    return "\n".join(lines) + "\n"


def build_html_table(jobs: list[NormalizedJob]) -> str:
    """A single <table>: header row + one <tr> per job. No wrapper text."""
    def cell(s: str) -> str:
        return html.escape(s, quote=True)

    out = ["<table border=\"1\" cellpadding=\"4\" cellspacing=\"0\">", "<thead><tr>"]
    out += [f"<th>{cell(h)}</th>" for h in HEADERS]
    out += ["</tr></thead>", "<tbody>"]
    for company, title, location, url in _rows(jobs):
        out.append(
            f"<tr><td>{cell(company)}</td><td>{cell(title)}</td><td>{cell(location)}</td>"
            f"<td><a href=\"{cell(url)}\">{cell(_link_text(url))}</a></td></tr>"
        )
    out += ["</tbody>", "</table>"]
    return "\n".join(out) + "\n"


def build_digest(
    jobs: list[NormalizedJob],
    stats: dict | None = None,
    sheet_id: str | None = None,
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> tuple[str, str]:
    """Compose (subject, plain_body). Pure function — safe to unit-test.

    `stats` and `sheet_id` are accepted for call-site compatibility and
    ignored: the body is the table and only the table.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    ordered = sort_jobs(jobs, ranked_by_hash)
    subject = f"Job Search — {len(ordered)} new jobs for {today}"
    return subject, build_plain_table(ordered)


def build_message(
    jobs: list[NormalizedJob],
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> tuple[str, str, str]:
    """Return (subject, plain_body, html_body) for the sorted job list."""
    subject, plain = build_digest(jobs, ranked_by_hash=ranked_by_hash)
    html_body = build_html_table(sort_jobs(jobs, ranked_by_hash))
    return subject, plain, html_body


def send_digest(
    jobs: list[NormalizedJob],
    stats: dict,
    *,
    dry_run: bool = False,
    ranked_by_hash: dict[str, RankedJob] | None = None,
) -> tuple[bool, str, str]:
    """Compose + send. Returns (sent, subject, plain_body) so callers can log/inspect."""
    subject, body, html_body = build_message(jobs, ranked_by_hash=ranked_by_hash)

    if not jobs:
        logger.info("notifier.email: 0 new jobs — no email sent (skipped)")
        stats["email_error"] = ""
        stats["email_skipped"] = "no new jobs"
        return False, subject, body

    if dry_run:
        logger.info("notifier.email [dry-run]: subject=%r rows=%d", subject, len(jobs))
        return False, subject, body

    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    to = os.environ.get("GMAIL_NOTIFY_TO", user).strip()

    if not (user and pw and to):
        logger.warning(
            "notifier.email: SMTP creds missing (GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD / GMAIL_NOTIFY_TO) — skipping send"
        )
        stats["email_error"] = "creds missing"
        return False, subject, body

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Job Search v2 <{user}>"
    msg["To"] = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    msg.attach(MIMEText(html_body, "html", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, pw)
            smtp.send_message(msg)
        logger.info("notifier.email: sent to %s — subject=%r", to, subject)
        stats["email_error"] = ""
        return True, subject, body
    except (smtplib.SMTPException, OSError) as exc:
        # Persist the error verbatim into stats so run.py can classify the
        # failure — SMTPAuthenticationError ("5.7.8 BadCredentials") means
        # the App Password is dead; a plain SMTPException / OSError means a
        # transient network / DNS / TLS issue. The two need different alarms.
        stats["email_error"] = f"{type(exc).__name__}: {exc}"
        logger.error("notifier.email: SMTP send failed: %s", exc)
        return False, subject, body
