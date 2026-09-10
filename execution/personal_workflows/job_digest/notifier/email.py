"""
description: Build and send the job_digest daily email (friend-facing, per-profile).
inputs:
    - pairs: list[tuple[NormalizedJob, RankedJob]] — the jobs that survived
      filtering + ranking for this run, each paired with its ranker verdict.
    - profile: Profile (candidate identity, roles, countries, recipient address).
    - stats: dict of run counters (fetched/new/kept per filter, per source, etc.)
      from the orchestrator. Shape is not fixed here — build_digest renders
      whatever is present rather than assuming specific keys, since run.py
      (owned separately) is free to add counters over time.
    - sheet_url: str | None — link to the friend's Google Sheet, or None if
      sheet writing is disabled/failed this run.
outputs:
    - build_digest() -> (subject, plain_text, html): pure function, safe to
      unit-test without network or SMTP.
    - send_digest() -> bool: True on a real send OR a dry-run write; False on
      a non-auth SMTP failure. Raises SmtpAuthError on bad credentials so the
      caller can map it to a distinct exit code (per the friend's workflow's
      failure-issue playbook).

Job-derived strings (title, company, location, contract, source, reasoning) are
UNTRUSTED — they come from public job boards. Every one of them is HTML-escaped
before landing in the HTML body; the plain-text body needs no escaping.
"""

from __future__ import annotations

import logging
import os
import smtplib
from datetime import datetime, timezone
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from html import escape as _esc
from pathlib import Path

from ..contracts import JobTier, NormalizedJob, RankedJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.notifier.email")

_SMTP_HOST = "smtp.gmail.com"
_SMTP_PORT = 587

_TIER_ORDER = (JobTier.A, JobTier.B, JobTier.C)
_TIER_LABEL = {
    JobTier.A: "Tier A — top match",
    JobTier.B: "Tier B — promising",
    JobTier.C: "Tier C — weak fit",
}
_TIER_COLOR = {
    JobTier.A: "#0f7b3a",
    JobTier.B: "#8a6d00",
    JobTier.C: "#666666",
}


class SmtpAuthError(RuntimeError):
    """Raised when Gmail SMTP rejects the App Password — distinct from a
    transient network/DNS/TLS failure so callers can alarm differently."""


def _role_label(profile: Profile) -> str:
    return "/".join(r.title for r in profile.roles)


def _country_label(profile: Profile) -> str:
    return ", ".join(profile.locations.countries)


def build_digest(
    pairs: list[tuple[NormalizedJob, RankedJob]],
    profile: Profile,
    stats: dict,
    sheet_url: str | None,
) -> tuple[str, str, str]:
    """Compose (subject, plain_text, html). Pure — no I/O, no network."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    new_count = len(pairs)

    subject = f"Job digest · {new_count} new · {_role_label(profile)} · {_country_label(profile)} · {today}"

    # Only tier A/B/C are digest-worthy; a SKIP verdict should never have
    # reached build_digest, but guard anyway rather than trust the caller.
    grouped: dict[JobTier, list[tuple[NormalizedJob, RankedJob]]] = {t: [] for t in _TIER_ORDER}
    for job, ranked in pairs:
        if ranked.tier in grouped:
            grouped[ranked.tier].append((job, ranked))
    for tier in grouped:
        grouped[tier].sort(key=lambda jr: -jr[1].score)

    plain_text = _build_plain_text(grouped, profile, stats, sheet_url, today)
    html = _build_html(grouped, profile, stats, sheet_url, today, subject)
    return subject, plain_text, html


def _build_plain_text(
    grouped: dict[JobTier, list[tuple[NormalizedJob, RankedJob]]],
    profile: Profile,
    stats: dict,
    sheet_url: str | None,
    today: str,
) -> str:
    lines = [f"Job digest — {today}", f"Roles: {_role_label(profile)}  |  Countries: {_country_label(profile)}", ""]
    any_rows = False
    for tier in _TIER_ORDER:
        rows = grouped[tier]
        if not rows:
            continue
        any_rows = True
        lines.append(f"{_TIER_LABEL[tier]} ({len(rows)})")
        for job, ranked in rows:
            contract = job.contract_type.value if job.contract_type else "Unknown"
            lines.append(f"  - {job.title} — {job.company} — {job.location} — {contract} — {job.source.value}")
            lines.append(f"    score {ranked.score:.2f} — {ranked.reasoning}")
            lines.append(f"    {job.url}")
        lines.append("")
    if not any_rows:
        lines.append("No jobs matched your profile in this run.\n")

    lines.append("--- Run stats ---")
    lines.extend(_render_stats_plain(stats))
    lines.append("")
    lines.append(f"Sheet: {sheet_url}" if sheet_url else "Sheet: (not configured for this run)")
    return "\n".join(lines) + "\n"


def _render_stats_plain(stats: dict) -> list[str]:
    out: list[str] = []
    for key, value in stats.items():
        if isinstance(value, dict):
            out.append(f"{key}:")
            for sub_key, sub_value in value.items():
                out.append(f"  {sub_key}: {sub_value}")
        else:
            out.append(f"{key}: {value}")
    return out or ["(no stats provided)"]


def _render_stats_html(stats: dict) -> str:
    parts = []
    for key, value in stats.items():
        if isinstance(value, dict):
            sub_items = "".join(
                f"<li>{_esc(str(sub_key))}: {_esc(str(sub_value))}</li>"
                for sub_key, sub_value in value.items()
            )
            parts.append(f"<li>{_esc(str(key))}<ul>{sub_items}</ul></li>")
        else:
            parts.append(f"<li>{_esc(str(key))}: {_esc(str(value))}</li>")
    if not parts:
        return "<p>(no stats provided)</p>"
    return f"<ul>{''.join(parts)}</ul>"


def _job_row_html(job: NormalizedJob, ranked: RankedJob) -> str:
    url = _esc(str(job.url))
    title = _esc(job.title)
    company = _esc(job.company)
    location = _esc(job.location)
    contract = _esc(job.contract_type.value if job.contract_type else "Unknown")
    source = _esc(job.source.value)
    reasoning = _esc(ranked.reasoning)
    return f"""
    <tr>
      <td style="padding:10px 12px;border-bottom:1px solid #e5e5e5;">
        <a href="{url}" style="color:#0b57d0;text-decoration:none;font-weight:600;">{title}</a><br/>
        <span style="color:#333;font-size:13px;">{company} &middot; {location} &middot; {contract} &middot; {source}</span><br/>
        <span style="color:#666;font-size:12px;">{reasoning}</span>
      </td>
    </tr>"""


def _tier_section_html(tier: JobTier, rows: list[tuple[NormalizedJob, RankedJob]]) -> str:
    if not rows:
        return ""
    color = _TIER_COLOR[tier]
    label = _esc(_TIER_LABEL[tier])
    body = "".join(_job_row_html(job, ranked) for job, ranked in rows)
    return f"""
    <tr><td style="padding:18px 0 6px 0;">
      <span style="display:inline-block;background:{color};color:#ffffff;font-size:12px;
                   font-weight:700;padding:3px 10px;border-radius:12px;">{label} &middot; {len(rows)}</span>
    </td></tr>
    <tr><td>
      <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
        {body}
      </table>
    </td></tr>"""


def _build_html(
    grouped: dict[JobTier, list[tuple[NormalizedJob, RankedJob]]],
    profile: Profile,
    stats: dict,
    sheet_url: str | None,
    today: str,
    subject: str,
) -> str:
    any_rows = any(grouped[t] for t in _TIER_ORDER)
    sections = "".join(_tier_section_html(t, grouped[t]) for t in _TIER_ORDER)
    if not any_rows:
        sections = '<tr><td style="padding:24px 0;color:#666;">No jobs matched your profile in this run.</td></tr>'

    sheet_line = (
        f'<a href="{_esc(sheet_url)}" style="color:#0b57d0;">Open the tracking sheet</a>'
        if sheet_url else "Sheet not configured for this run."
    )
    stats_html = _render_stats_html(stats)

    return f"""<!doctype html>
<html>
<body style="margin:0;padding:0;background:#f4f4f4;font-family:Arial,Helvetica,sans-serif;color:#111;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background:#f4f4f4;padding:24px 0;">
    <tr><td align="center">
      <table role="presentation" width="600" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:8px;overflow:hidden;max-width:600px;width:100%;">
        <tr><td style="background:#111827;color:#ffffff;padding:20px 24px;">
          <div style="font-size:18px;font-weight:700;">{_esc(subject)}</div>
          <div style="font-size:13px;color:#c7c9d1;margin-top:4px;">
            Roles: {_esc(_role_label(profile))} &middot; Countries: {_esc(_country_label(profile))}
          </div>
        </td></tr>
        <tr><td style="padding:8px 24px 24px 24px;">
          <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="border-collapse:collapse;">
            {sections}
          </table>
        </td></tr>
        <tr><td style="padding:16px 24px;background:#fafafa;border-top:1px solid #e5e5e5;font-size:12px;color:#555;">
          <div style="margin-bottom:8px;">{sheet_line}</div>
          <div style="font-weight:700;margin-bottom:4px;">Run stats — {_esc(today)}</div>
          {stats_html}
        </td></tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""


def _write_dry_run(subject: str, plain_text: str, html: str, out_dir: Path | None = None) -> Path:
    if out_dir is None:
        # Fallback only — callers (run.py) should always pass the run's own
        # out_dir explicitly (M6); the env var exists for standalone/manual use.
        out_dir = Path(os.environ.get("JOB_DIGEST_OUT_DIR", ".tmp/job_digest"))
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "digest.txt").write_text(plain_text, encoding="utf-8")
    (out_dir / "digest.html").write_text(html, encoding="utf-8")
    (out_dir / "subject.txt").write_text(subject, encoding="utf-8")
    logger.info("notifier.email [dry-run]: wrote digest.txt/digest.html to %s (subject=%r)", out_dir, subject)
    return out_dir


def send_digest(
    subject: str,
    plain_text: str,
    html: str,
    profile: Profile,
    *,
    dry: bool = False,
    out_dir: Path | None = None,
) -> bool:
    """Send the digest via Gmail SMTP, or write it to disk when dry=True.

    `out_dir` (M6) is the run's own out_dir — the dry-run digest.txt/html/subject
    files land there instead of the JOB_DIGEST_OUT_DIR env var's fixed location,
    so dry/preview runs are self-contained per invocation. The env var remains
    the fallback when out_dir is not given (e.g. a standalone manual call).

    Raises SmtpAuthError on SMTPAuthenticationError (dead App Password) so the
    caller can distinguish it from a transient send failure. Any other SMTP or
    network error is logged and returns False rather than raising, matching
    the rest of the pipeline's soft-fail-and-report convention.
    """
    if dry:
        _write_dry_run(subject, plain_text, html, out_dir)
        return True

    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    password = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    to_addr = profile.candidate.email

    if not user or not password:
        logger.error("notifier.email: GMAIL_SMTP_USER / GMAIL_SMTP_APP_PASSWORD not set — cannot send")
        return False

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = f"Job Digest <{user}>"
    msg["To"] = to_addr
    msg.attach(MIMEText(plain_text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    try:
        with smtplib.SMTP(_SMTP_HOST, _SMTP_PORT, timeout=30) as smtp:
            smtp.starttls()
            smtp.login(user, password)
            smtp.send_message(msg)
        logger.info("notifier.email: sent to %s — subject=%r", to_addr, subject)
        return True
    except smtplib.SMTPAuthenticationError as exc:
        logger.error("notifier.email: SMTP auth failed: %s", exc)
        raise SmtpAuthError(str(exc)) from exc
    except (smtplib.SMTPException, OSError) as exc:
        logger.error("notifier.email: SMTP send failed: %s", exc)
        return False
