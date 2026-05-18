"""
job_digest_renderer.py
description: Build a self-contained HTML digest of active PM/PO jobs (France) first-seen within a configurable window, grouped by company with contacts.
inputs: --db (SQLite path), --window (days, default 7), --mark-expired (flag), --out (output path), --print (stdout flag); env var JOB_TRACKER_DB_PATH.
outputs: HTML string returned from render_digest_html(); optionally written to --out file or printed to stdout.
"""

import argparse
import os
import re
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv; load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import setup_logging, now_iso, load_jt_config, save_json
from execution.personal_workflows.job_tracker_db import (
    init_db,
    query_active_within_window,
    get_contacts_for_company,
    log_notification,
    mark_expired,
)

logger = setup_logging("job_digest_renderer")

# ---------------------------------------------------------------------------
# Seniority label map
# ---------------------------------------------------------------------------

_SENIORITY_LABELS: dict[str, str] = {
    "cpo": "CPO",
    "vp_product": "VP Product",
    "head_of_product": "Head of Product",
    "senior_pm": "Senior PM",
    "hr": "HR / TA",
}


# ---------------------------------------------------------------------------
# Age formatting
# ---------------------------------------------------------------------------

def _age_label(first_seen_at: str, now_utc: datetime) -> str:
    """Return 'today', 'yesterday', or 'N days ago' from an ISO 8601 UTC string."""
    try:
        seen = datetime.fromisoformat(first_seen_at.replace("Z", "+00:00"))
        if seen.tzinfo is None:
            seen = seen.replace(tzinfo=timezone.utc)
    except (ValueError, AttributeError):
        return "unknown"

    delta_days = (now_utc.date() - seen.astimezone(timezone.utc).date()).days
    if delta_days == 0:
        return "today"
    if delta_days == 1:
        return "yesterday"
    return f"{delta_days} days ago"


# ---------------------------------------------------------------------------
# Inline CSS
# ---------------------------------------------------------------------------

_CSS = """
  body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
    max-width: 880px;
    margin: 0 auto;
    padding: 24px;
    color: #1a1a1a;
    background: #ffffff;
  }
  h1 { font-size: 22px; margin: 0 0 4px 0; }
  .subtitle { color: #444; font-size: 14px; margin: 0 0 16px 0; }
  .summary { font-size: 14px; color: #555; margin-bottom: 16px; }
  .banner {
    background: #fff4e5;
    border-left: 4px solid #f0a500;
    padding: 10px 14px;
    font-size: 13px;
    margin-bottom: 16px;
    border-radius: 2px;
  }
  table.main-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 14px;
  }
  table.main-table th {
    background: #f2f2f2;
    text-align: left;
    padding: 10px 12px;
    font-size: 13px;
    color: #333;
    border-bottom: 2px solid #ddd;
  }
  table.main-table td {
    padding: 12px;
    border-bottom: 1px solid #eee;
    vertical-align: top;
  }
  table.main-table tr:last-child td { border-bottom: none; }
  a { color: #1a73e8; text-decoration: none; }
  a:hover { text-decoration: underline; }
  .meta { font-size: 12px; color: #666; }
  .role-item { margin-bottom: 6px; }
  .role-item:last-child { margin-bottom: 0; }
  .contact-item { margin-bottom: 4px; }
  .contact-item:last-child { margin-bottom: 0; }
  .no-contacts { color: #888; font-style: italic; font-size: 13px; }
  .company-name { font-weight: 600; font-size: 14px; }
  .footer {
    margin-top: 24px;
    font-size: 11px;
    color: #999;
    border-top: 1px solid #eee;
    padding-top: 12px;
    line-height: 1.6;
  }
"""

# ---------------------------------------------------------------------------
# HTML builder helpers
# ---------------------------------------------------------------------------

def _esc(text: str | None) -> str:
    """Minimal HTML escaping for attribute and text values."""
    if not text:
        return ""
    return (
        text
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def _render_roles_cell(jobs: list[dict], now_utc: datetime) -> str:
    parts: list[str] = []
    for j in jobs:
        title_esc = _esc(j.get("title", ""))
        url = _esc(j.get("source_url", "#"))
        board = _esc(j.get("board", ""))
        location = _esc(j.get("location") or "—")
        age = _age_label(j.get("first_seen_at", ""), now_utc)
        meta = f'<span class="meta">— {board} · {location} · seen {age}</span>'
        parts.append(
            f'<div class="role-item"><a href="{url}">{title_esc}</a> {meta}</div>'
        )
    return "\n".join(parts)


def _render_contacts_cell(contacts: list[dict]) -> str:
    if not contacts:
        return '<em class="no-contacts">Contacts pending — will refresh next run.</em>'

    parts: list[str] = []
    for c in contacts[:5]:
        name = _esc(c.get("full_name", ""))
        url = _esc(c.get("linkedin_url") or "")
        raw_title = c.get("title") or ""
        raw_seniority = c.get("seniority") or ""
        label = raw_title or _SENIORITY_LABELS.get(raw_seniority, raw_seniority)
        label_esc = _esc(label)

        if url:
            name_html = f'<a href="{url}">{name}</a>'
        else:
            name_html = name

        meta = f' <span class="meta">— {label_esc}</span>' if label_esc else ""
        parts.append(f'<div class="contact-item">{name_html}{meta}</div>')

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_digest_html(
    db_path: "Path | str",
    *,
    window_days: int = 7,
    generated_at: "str | None" = None,
    degraded_boards: "list[str] | None" = None,
) -> "tuple[str, list[int]]":
    """Build a self-contained HTML digest of active PM/PO jobs.

    Returns:
        (html_string, list_of_job_ids_included)
    """
    conn = init_db(db_path)
    now_utc = datetime.now(timezone.utc)
    paris_tz = ZoneInfo("Europe/Paris")
    now_paris = now_utc.astimezone(paris_tz)

    # Human-friendly header date (e.g. "Wednesday, 14 May 2026")
    header_date = now_paris.strftime("%A, %d %B %Y").replace(" 0", " ")

    # generated_at stamp
    run_stamp = generated_at if generated_at else now_iso()
    # Show Paris + UTC in footer
    footer_paris = now_paris.strftime("%Y-%m-%d %H:%M %Z")
    footer_utc = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    jobs = query_active_within_window(conn, window_days)
    job_ids = [j["id"] for j in jobs]

    # Group by company_id preserving company_name sort (query already ordered by name)
    company_order: list[int] = []
    company_map: dict[int, dict] = {}  # company_id -> {name, jobs}
    for j in jobs:
        cid = j["company_id"]
        if cid not in company_map:
            company_order.append(cid)
            company_map[cid] = {"name": j["company_name"], "jobs": []}
        company_map[cid]["jobs"].append(j)

    n_jobs = len(jobs)
    n_companies = len(company_map)

    # ---- Banner ----
    banner_html = ""
    if degraded_boards:
        board_list = ", ".join(_esc(b) for b in degraded_boards)
        banner_html = (
            f'<div class="banner" style="background:#fff4e5;border-left:4px solid #f0a500;'
            f'padding:10px 14px;font-size:13px;margin-bottom:16px;">'
            f"&#9888; Source(s) degraded today: {board_list}. "
            f"Coverage may be incomplete; recovery attempted next run."
            f"</div>"
        )

    # ---- Table rows ----
    rows_html_parts: list[str] = []
    for cid in company_order:
        entry = company_map[cid]
        company_name_esc = _esc(entry["name"])
        try:
            contacts = get_contacts_for_company(conn, cid)
        except Exception as exc:
            logger.warning("Could not fetch contacts for company_id=%s: %s", cid, exc)
            contacts = []

        roles_cell = _render_roles_cell(entry["jobs"], now_utc)
        contacts_cell = _render_contacts_cell(contacts)

        rows_html_parts.append(
            f"""    <tr>
      <td style="padding:12px;border-bottom:1px solid #eee;vertical-align:top;min-width:140px;">
        <span class="company-name">{company_name_esc}</span>
      </td>
      <td style="padding:12px;border-bottom:1px solid #eee;vertical-align:top;">
        {roles_cell}
      </td>
      <td style="padding:12px;border-bottom:1px solid #eee;vertical-align:top;min-width:180px;">
        {contacts_cell}
      </td>
    </tr>"""
        )

    rows_html = "\n".join(rows_html_parts)

    # ---- Full document ----
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1.0" />
  <title>PM/PO Job Tracker — France</title>
  <style>
{_CSS}
  </style>
</head>
<body>
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width:880px;margin:0 auto;">
  <tr><td style="padding:24px;">

  <h1>Daily PM&#47;PO Job Tracker &mdash; France</h1>
  <p class="subtitle">{_esc(header_date)}</p>
  <p class="summary">{n_jobs} active opening{'s' if n_jobs != 1 else ''} across {n_companies} {'companies' if n_companies != 1 else 'company'} &mdash; showing jobs first seen within the last {window_days} days.</p>

  {banner_html}

  <table class="main-table" role="presentation" width="100%" cellpadding="0" cellspacing="0"
         style="width:100%;border-collapse:collapse;font-size:14px;">
    <thead>
      <tr>
        <th style="background:#f2f2f2;text-align:left;padding:10px 12px;font-size:13px;color:#333;border-bottom:2px solid #ddd;width:22%;">Company</th>
        <th style="background:#f2f2f2;text-align:left;padding:10px 12px;font-size:13px;color:#333;border-bottom:2px solid #ddd;width:46%;">Role(s)</th>
        <th style="background:#f2f2f2;text-align:left;padding:10px 12px;font-size:13px;color:#333;border-bottom:2px solid #ddd;width:32%;">Contacts</th>
      </tr>
    </thead>
    <tbody>
{rows_html}
    </tbody>
  </table>

  <div class="footer">
    Generated: {_esc(footer_paris)} (UTC: {_esc(footer_utc)})<br />
    Each job stays in this digest for {window_days} days from first seen.<br />
    Run: {_esc(run_stamp)}
  </div>

  </td></tr>
</table>
</body>
</html>"""

    conn.close()
    return (html, job_ids)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _resolve_db_path() -> Path:
    env_val = os.environ.get("JOB_TRACKER_DB_PATH")
    if env_val:
        return Path(env_val)
    try:
        cfg = load_jt_config()
        raw = cfg.get("default_db_path", "")
        return (PROJECT_ROOT / raw).resolve() if raw else PROJECT_ROOT / ".tmp" / "job_tracker.db"
    except Exception:
        return PROJECT_ROOT / ".tmp" / "job_tracker.db"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Render an HTML digest of active PM/PO jobs (France).",
    )
    parser.add_argument("--db", metavar="PATH", help="Path to the SQLite database.")
    parser.add_argument("--window", type=int, default=7, metavar="DAYS", help="Look-back window in days (default: 7).")
    parser.add_argument("--mark-expired", action="store_true", help="Mark jobs outside the window as expired before rendering.")
    parser.add_argument("--out", metavar="PATH", help="Write HTML to this file path.")
    parser.add_argument("--print", dest="print_stdout", action="store_true", help="Print HTML to stdout.")
    args = parser.parse_args()

    db_path = Path(args.db) if args.db else _resolve_db_path()

    if args.mark_expired:
        try:
            conn_expire = init_db(db_path)
            expired_count = mark_expired(conn_expire, args.window)
            conn_expire.close()
            logger.info("Marked %d job(s) as expired.", expired_count)
        except Exception as exc:
            logger.error("Failed to mark expired jobs: %s", exc)
            sys.exit(1)

    try:
        html, included_ids = render_digest_html(
            db_path,
            window_days=args.window,
        )
    except Exception as exc:
        logger.error("Digest rendering failed: %s", exc)
        sys.exit(1)

    if args.out:
        out_path = Path(args.out)
        try:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(html, encoding="utf-8")
            logger.info("HTML digest written to: %s (%d jobs)", out_path, len(included_ids))
        except Exception as exc:
            logger.error("Failed to write output file: %s", exc)
            sys.exit(1)

    if args.print_stdout:
        sys.stdout.write(html)

    if not args.out and not args.print_stdout:
        logger.info(
            "Digest generated: %d job(s) across %d company/ies. "
            "Use --out <path> or --print to capture output.",
            len(included_ids),
            len(set(included_ids)),  # rough proxy; actual company count is inside render
        )
