"""
description: Jobgether Job-Alert email ingestion source. Reads Jobgether alert emails
    from a Gmail label (default 'JobAlerts/Jobgether') via IMAP and emits one SourceJob
    per advertised job card. Same auth path as the other *_gmail sources — reuses
    GMAIL_SMTP_USER + GMAIL_SMTP_APP_PASSWORD. Jobgether is a remote-first European
    job board; adds remote PM coverage that France Travail / Hellowork / APEC under-index.

    Setup the user needs to do once:
      1. Create Gmail label 'JobAlerts/Jobgether'.
      2. Create a Gmail filter (sender pinned after first real alert; placeholder until then):
           from:(noreply@jobgether.com OR alerts@jobgether.com OR no-reply@jobgether.com)
           Apply label "JobAlerts/Jobgether", Skip the Inbox, (optional) Mark as read.
      3. Subscribe to a Jobgether saved-search alert at https://jobgether.com
         (e.g. "Product Manager" remote-first, Europe), enable daily.
      4. After the first alert arrives, save its raw HTML to
         tests/fixtures/jobgether_email_sample.html and re-run the front-door synthetic
         to lock the parser regex against real layout.

inputs:
    - CLI: --label JobAlerts/Jobgether, --days 2, --max-emails 20, --max-jobs 50
    - CLI: --fixture PATH (offline mode), --out PATH
    - env: GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD (already in .env from v1).

outputs:
    - stdout: JSON-lines of SourceJob
    - .tmp/job_search_v2/jobgether_gmail_<run_id>.jsonl
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv

_THIS = Path(__file__).resolve()
_WORKSPACE_ROOT = _THIS.parents[4]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv()
logger = logging.getLogger("jobgether_gmail")

PROJECT_ROOT = _WORKSPACE_ROOT
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"
DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "jobgether_email_sample.html"

# Jobgether canonical job URL patterns observed:
#   https://jobgether.com/offer/{uuid}-{slug}
#   https://jobgether.com/jobs/{uuid}
#   https://jobgether.com/en/offer/{uuid}-{slug}
# The {uuid} suffix is the stable source_id (24-char hex or UUID-4 shape).
_JOBGETHER_JOB_URL_RE = re.compile(
    r"https?://(?:www\.)?jobgether\.com/(?:[a-z]{2}/)?(?:offer|jobs|job)/([a-f0-9]{8,36}|[A-Za-z0-9_-]{12,})",
    re.IGNORECASE,
)

# Fallback: any jobgether.com link with a trailing id-shaped token.
_JOBGETHER_ID_RE = re.compile(r"jobgether\.com/[^\"'\s>]*?([a-f0-9]{12,}|[A-Za-z0-9_-]{16,})", re.IGNORECASE)

_REL_TIME_RE = re.compile(
    r"(\d+)\s+(minute|hour|day|week)s?\s+ago",
    re.IGNORECASE,
)


class JobgetherGmailAuthError(RuntimeError):
    pass


def _parse_relative_time(text: str, anchor: datetime | None) -> datetime | None:
    if anchor is None:
        return None
    m = _REL_TIME_RE.search(text)
    if not m:
        return None
    n = int(m.group(1))
    unit = m.group(2).lower()
    delta = {
        "minute": timedelta(minutes=n),
        "hour": timedelta(hours=n),
        "day": timedelta(days=n),
        "week": timedelta(weeks=n),
    }.get(unit)
    if delta is None:
        return None
    return anchor - delta


def _parse_jobgether_html(html: str, anchor: datetime | None) -> list[SourceJob]:
    """Parse a Jobgether alert email body. Returns one SourceJob per job card.

    Heuristic until tests/fixtures/jobgether_email_sample.html is in hand: walk every
    <a> with a jobgether.com job URL, treat anchor text as title, walk up to the card
    container, extract company + location from sibling text nodes.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError:
        logger.warning("jobgether_gmail: bs4 not installed — using regex-only fallback")
        return _parse_jobgether_regex_only(html, anchor)

    soup = BeautifulSoup(html, "html.parser")
    jobs: list[SourceJob] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        if "jobgether.com" not in href.lower():
            continue
        m = _JOBGETHER_JOB_URL_RE.search(href) or _JOBGETHER_ID_RE.search(href)
        if not m:
            continue
        job_id = m.group(1)
        if job_id in seen_ids:
            continue

        title = re.sub(r"\s+", " ", a.get_text(" ", strip=True)).strip()
        if not title or len(title) < 4 or title.lower() in {
            "apply", "apply now", "view job", "see all jobs", "new", "unsubscribe",
            "view all", "see more", "open", "open job",
        }:
            continue

        # Walk up to the card container.
        card = a
        for _ in range(6):
            if card.parent is None:
                break
            card = card.parent
            if card.name in ("table", "td", "tr", "div"):
                texts = [t.strip() for t in card.stripped_strings if t.strip()]
                if len(texts) >= 3 and any(title in t or t in title for t in texts):
                    break

        texts = [t.strip() for t in card.stripped_strings if t.strip()]
        skip = {
            "apply", "apply now", "view job", "see all jobs", "new", "sponsored",
            "jobgether.com", "save", "unsave", "you may also like", "open", "open job",
            "view all", "see more", "remote", "hybrid", "onsite",  # tags not company
        }
        candidates = [
            t for t in texts
            if t != title and t.lower() not in skip and len(t) > 1
        ]
        company = candidates[0] if candidates else "Unknown (Jobgether)"
        location_raw = candidates[1] if len(candidates) >= 2 else ""

        posted_at = _parse_relative_time(" ".join(texts), anchor)

        try:
            jobs.append(SourceJob(
                source=JobSource.JOBGETHER_GMAIL,
                source_id=job_id,
                url=href,
                title=title,
                company=company,
                location_raw=location_raw,
                description_snippet="",
                posted_at=posted_at,
                contract_type_raw="",
            ))
            seen_ids.add(job_id)
        except (ValueError, TypeError) as exc:
            logger.warning("jobgether_gmail: skip job_id=%s validation error: %s", job_id, exc)
            continue

    return jobs


def _parse_jobgether_regex_only(html: str, anchor: datetime | None) -> list[SourceJob]:
    """Stdlib-only fallback. Used when bs4 is unavailable."""
    jobs: list[SourceJob] = []
    seen_ids: set[str] = set()
    anchor_re = re.compile(
        r'<a\b[^>]*href=["\']([^"\']*jobgether\.com[^"\']*?([a-f0-9]{12,}|[A-Za-z0-9_-]{16,})[^"\']*)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for href, job_id, inner in anchor_re.findall(html):
        if job_id in seen_ids:
            continue
        title = re.sub(r"<[^>]+>", " ", inner)
        title = re.sub(r"\s+", " ", title).strip()
        if not title or len(title) < 4 or title.lower() in {"apply", "view job", "new", "open"}:
            continue
        try:
            jobs.append(SourceJob(
                source=JobSource.JOBGETHER_GMAIL,
                source_id=job_id,
                url=href,
                title=title,
                company="Unknown (Jobgether)",
                location_raw="",
                description_snippet="",
                posted_at=_parse_relative_time(html, anchor),
                contract_type_raw="",
            ))
            seen_ids.add(job_id)
        except (ValueError, TypeError):
            continue
    return jobs


def fetch_via_imap(
    label: str = "JobAlerts/Jobgether",
    days: int = 2,
    max_emails: int = 20,
    max_jobs: int = 50,
) -> list[SourceJob]:
    """Read Jobgether alert emails from a Gmail label via IMAP."""
    import imaplib
    import email as email_lib
    from email.policy import default as P

    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    if not (user and pw):
        raise JobgetherGmailAuthError(
            "GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD must be set in .env."
        )

    jobs: list[SourceJob] = []
    seen_global: set[str] = set()

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        imap.login(user, pw)
    except (imaplib.IMAP4.error, OSError) as exc:
        raise JobgetherGmailAuthError(f"IMAP login failed: {exc}") from exc

    try:
        status, _ = imap.select(f'"{label}"', readonly=True)
        if status != "OK":
            logger.warning("jobgether_gmail [imap]: label %r not found — skipping source. "
                           "Set up the Gmail filter: see module docstring.", label)
            return jobs

        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = imap.search(None, f'SINCE {since}')
        if status != "OK":
            logger.warning("jobgether_gmail [imap]: SEARCH failed: %s", status)
            return jobs

        ids = (data[0] or b"").split()
        ids = ids[-max_emails:]
        logger.info("jobgether_gmail [imap]: %d emails since %s in %r", len(ids), since, label)

        for msg_id in reversed(ids):
            if len(jobs) >= max_jobs:
                break
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                continue
            try:
                msg = email_lib.message_from_bytes(msg_data[0][1], policy=P)
            except Exception as exc:  # noqa: BLE001 — email surface is broad
                logger.warning("jobgether_gmail: parse failure: %s", exc)
                continue

            date_str = msg.get("Date", "")
            try:
                anchor = parsedate_to_datetime(date_str) if date_str else None
                if anchor is not None and anchor.tzinfo is None:
                    anchor = anchor.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                anchor = None

            html = ""
            for part in msg.walk():
                if part.get_content_type() == "text/html":
                    try:
                        html = part.get_content()
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("jobgether_gmail: get_content failed: %s", exc)
            if not html:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            html = part.get_content()
                            break
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("jobgether_gmail: get_content failed: %s", exc)
            if not html:
                continue

            parsed = _parse_jobgether_html(html, anchor)
            if not parsed:
                logger.warning("jobgether_gmail: parsed 0 jobs from email id=%s — Jobgether may have shifted template", msg_id)
            for job in parsed:
                if job.source_id in seen_global:
                    continue
                seen_global.add(job.source_id)
                jobs.append(job)
                if len(jobs) >= max_jobs:
                    break
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass

    logger.info("jobgether_gmail [imap]: emitted %d jobs", len(jobs))
    return jobs


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: parse a recorded HTML file. Used by the front-door synthetic."""
    html = fixture_path.read_text(encoding="utf-8")
    return _parse_jobgether_html(html, datetime.now(timezone.utc))


def fetch(
    label: str = "JobAlerts/Jobgether",
    days: int = 2,
    max_emails: int = 20,
    max_jobs: int = 50,
) -> list[SourceJob]:
    """Public fetch entry point — currently always IMAP."""
    return fetch_via_imap(label=label, days=days, max_emails=max_emails, max_jobs=max_jobs)


def _write_jsonl(jobs: list[SourceJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Jobgether Job-Alert email ingestion (Gmail IMAP).")
    parser.add_argument("--label", default="JobAlerts/Jobgether")
    parser.add_argument("--days", type=int, default=2)
    parser.add_argument("--max-emails", type=int, default=20)
    parser.add_argument("--max-jobs", type=int, default=50)
    parser.add_argument("--fixture", type=Path, help="Parse an HTML fixture instead of hitting Gmail.")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        if not args.fixture.exists():
            logger.error("jobgether_gmail: fixture not found: %s", args.fixture)
            return 2
        jobs = fetch_from_fixture(args.fixture)
        logger.info("jobgether_gmail: %d jobs from fixture %s", len(jobs), args.fixture)
    else:
        try:
            jobs = fetch(label=args.label, days=args.days, max_emails=args.max_emails, max_jobs=args.max_jobs)
        except JobgetherGmailAuthError as exc:
            logger.error("jobgether_gmail: auth — %s", exc)
            return 2

    run_id = uuid.uuid4().hex[:8]
    out_path = args.out or (TMP_DIR / f"jobgether_gmail_{run_id}.jsonl")
    _write_jsonl(jobs, out_path)
    logger.info("jobgether_gmail: wrote %d jobs to %s", len(jobs), out_path)
    for job in jobs:
        sys.stdout.write(job.model_dump_json() + "\n")
    return 0 if jobs else 1


if __name__ == "__main__":
    sys.exit(main())
