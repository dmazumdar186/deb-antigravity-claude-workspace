"""
description: LinkedIn Job-Alert email ingestion source. Reads LinkedIn "Job Alert" emails
    out of the user's Gmail inbox via the Gmail REST API (google-api-python-client) and
    parses each email's HTML body into one SourceJob per advertised job card.
    NB: we deliberately do NOT scrape linkedin.com — that violates LinkedIn's ToS and
    triggers their anti-bot stack. The whole point is to let LinkedIn email us the jobs
    via their built-in "Job Alerts" feature, then read those emails.

inputs:
    - env: GMAIL_TOKEN_PATH (default: tokens/gmail.json) — path to a Google OAuth-user
           token JSON (the standard Google Python quickstart pattern: a one-time `flow.run_local_server()`
           bootstrap on the operator's machine writes this file; thereafter the script
           refreshes silently). Reason for OAuth-user vs service-account: the daily cron
           runs against the operator's own personal Gmail (debanjan186@gmail.com), which
           is NOT a Google Workspace account, so domain-wide delegation is unavailable.
           OAuth-user with refresh token is the supported quickstart pattern.
    - env: GMAIL_CREDENTIALS_PATH (default: credentials/gmail_oauth_client.json) — the
           OAuth 2.0 Client ID JSON from Google Cloud Console (Desktop application).
           Only needed for the first-run bootstrap (when tokens/gmail.json does not yet
           exist). On subsequent runs the refresh token in tokens/gmail.json is enough.
    - CLI: --query (default: "label:JobAlerts/LinkedIn newer_than:2d")
    - CLI: --days (default: 2) — convenience: overrides newer_than:Nd in the default query
    - CLI: --max-emails (default: 20)
    - CLI: --max-jobs (default: 50)
    - CLI: --fixture PATH (offline mode — parse a recorded HTML file instead of hitting Gmail)
    - CLI: --out PATH (output JSONL; defaults to .tmp/job_search_v2/linkedin_gmail_<run_id>.jsonl)

outputs:
    - stdout: JSON-lines of SourceJob records (one per line)
    - .tmp/job_search_v2/linkedin_gmail_<run_id>.jsonl
    - Gmail API calls: users.messages.list + users.messages.get (metadata + full payload)

Gmail access path chosen: **direct Gmail REST API** (google-api-python-client + OAuth-user
token with refresh) — NOT the Gmail MCP. Reason: the daily cron runs from GitHub Actions
(see .github/workflows/job_search_daily.yml) where the Claude Code MCP layer is not
reachable. The MCP path (`mcp__claude_ai_Gmail__search_threads`) only works inside an
interactive Claude Code session. Documenting this so a future contributor doesn't quietly
"simplify" us back to the MCP and break the cron.

LinkedIn alert HTML layout (observed June 2026 — review every ~6 months because LinkedIn
re-skins their templated emails roughly every release cycle):
    - Each job card contains an <a> with href matching r'linkedin\\.com/comm/jobs/view/(\\d+)'.
    - The card's job title is the text content of a <strong> tag inside that <a> (or, if
      LinkedIn changes templates, the <a>'s own text — we fall back).
    - Company name is a sibling <p>/<span> immediately after the title link; we walk the
      DOM upward to the card root and pick the next text node that isn't the title.
    - Location is the next text node after the company (e.g. "Paris, Île-de-France, France").
    - "X hours ago" / "X days ago" if present sits near the bottom of the card.

If the parser yields 0 jobs from a non-empty email, we log a WARNING (LinkedIn likely
changed their email template) and return what we have — we never crash the pipeline.
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import sys
import uuid
from base64 import urlsafe_b64decode
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path

from dotenv import load_dotenv

# Local import bootstrap — works under `py execution/personal_workflows/job_search_v2/sources/linkedin_gmail.py`
# AND `python -m execution.personal_workflows.job_search_v2.sources.linkedin_gmail`.
_THIS = Path(__file__).resolve()
# sources/ -> job_search_v2/ -> personal_workflows/ -> execution/ -> workspace_root
_WORKSPACE_ROOT = _THIS.parents[4]
if str(_WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE_ROOT))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv()
logger = logging.getLogger("linkedin_gmail")

PROJECT_ROOT = _WORKSPACE_ROOT
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"
DEFAULT_FIXTURE = PROJECT_ROOT / "tests" / "fixtures" / "linkedin_email_sample.html"

# Read-only scope — narrowest scope that lets us list and fetch message bodies.
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]

# LinkedIn alert URL pattern — the canonical "view a job" URL in alert emails.
# Example: https://www.linkedin.com/comm/jobs/view/3941258371?refId=...&trk=eml-...
_LINKEDIN_JOB_URL_RE = re.compile(
    r"https?://(?:www\.)?linkedin\.com/comm/jobs/view/(\d+)[^\"'\s>]*",
    re.IGNORECASE,
)

# Relative-time phrases LinkedIn likes ("2 hours ago", "1 day ago", "3 days ago").
_REL_TIME_RE = re.compile(
    r"(\d+)\s+(minute|hour|day|week)s?\s+ago",
    re.IGNORECASE,
)


class LinkedInGmailAuthError(RuntimeError):
    """Raised when the OAuth token is missing, expired beyond refresh, or refused."""


# ---------------------------------------------------------------------------
# Gmail client
# ---------------------------------------------------------------------------


def _build_gmail_service():
    """Construct an authenticated Gmail API client.

    Returns the googleapiclient resource. Raises LinkedInGmailAuthError on any
    credential/setup problem so the caller can decide policy (skip vs. fail-hard).

    Implementation note: google-api-python-client + google-auth are wrapped in a
    try/except ImportError so a misconfigured environment degrades gracefully to
    "0 jobs from linkedin_gmail" rather than crashing the whole orchestrator.
    """
    try:
        from google.auth.transport.requests import Request  # type: ignore
        from google.oauth2.credentials import Credentials  # type: ignore
        from google_auth_oauthlib.flow import InstalledAppFlow  # type: ignore
        from googleapiclient.discovery import build  # type: ignore
    except ImportError as exc:
        raise LinkedInGmailAuthError(
            "google-api-python-client / google-auth-oauthlib not installed. "
            "Install with: pip install google-api-python-client google-auth google-auth-oauthlib. "
            f"Underlying ImportError: {exc}"
        ) from exc

    token_path = Path(os.environ.get("GMAIL_TOKEN_PATH", "tokens/gmail.json"))
    creds_path = Path(os.environ.get("GMAIL_CREDENTIALS_PATH", "credentials/gmail_oauth_client.json"))

    creds = None
    if token_path.exists():
        try:
            creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)
        except (ValueError, OSError) as exc:
            logger.warning("linkedin_gmail: failed to load token at %s: %s", token_path, exc)
            creds = None

    if creds and creds.valid:
        pass
    elif creds and creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
        except Exception as exc:  # google-auth raises broad RefreshError; we log+rethrow as auth error.
            raise LinkedInGmailAuthError(
                f"OAuth token refresh failed for {token_path} — re-run the bootstrap flow. Detail: {exc}"
            ) from exc
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError as exc:
            logger.warning("linkedin_gmail: refreshed creds, but could not rewrite %s: %s", token_path, exc)
    else:
        # No usable token — try the bootstrap flow. This is interactive (opens a browser)
        # and only works on the operator's machine, NOT in cron. Cron must already have
        # the token file in place.
        if not creds_path.exists():
            raise LinkedInGmailAuthError(
                f"No Gmail OAuth token at {token_path} and no client_secret at {creds_path}. "
                "Bootstrap: download OAuth 2.0 Client ID (Desktop) JSON from Google Cloud Console "
                f"to {creds_path}, then run this script once interactively to mint {token_path}."
            )
        logger.info("linkedin_gmail: starting interactive OAuth flow (one-time bootstrap)")
        flow = InstalledAppFlow.from_client_secrets_file(str(creds_path), GMAIL_SCOPES)
        creds = flow.run_local_server(port=0)
        try:
            token_path.parent.mkdir(parents=True, exist_ok=True)
            token_path.write_text(creds.to_json(), encoding="utf-8")
        except OSError as exc:
            # Token still works for this run, but the next run will re-bootstrap. That's a real problem.
            logger.error("linkedin_gmail: minted creds, but could not write %s: %s", token_path, exc)

    try:
        return build("gmail", "v1", credentials=creds, cache_discovery=False)
    except Exception as exc:
        raise LinkedInGmailAuthError(f"Could not construct Gmail service: {exc}") from exc


# ---------------------------------------------------------------------------
# Body extraction
# ---------------------------------------------------------------------------


def _walk_payload_for_html(payload: dict) -> str:
    """Recurse through a Gmail message payload tree and return the first text/html part.

    Falls back to text/plain if no HTML part exists. Returns '' if neither.
    Gmail returns body data as URL-safe base64; we decode and utf-8-with-replace it
    (Windows-safe — see python-hardening rule 1).
    """
    if not payload:
        return ""

    mime = payload.get("mimeType", "")
    body = payload.get("body", {}) or {}
    data = body.get("data")

    if mime == "text/html" and data:
        try:
            return urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning("linkedin_gmail: failed to decode text/html part: %s", exc)
            return ""

    # Recurse into parts.
    for part in payload.get("parts", []) or []:
        html = _walk_payload_for_html(part)
        if html:
            return html

    # Last-resort fallback: plain text (rarely useful for LinkedIn alerts, but better than '').
    if mime == "text/plain" and data:
        try:
            return urlsafe_b64decode(data.encode("ascii")).decode("utf-8", errors="replace")
        except (ValueError, UnicodeDecodeError) as exc:
            logger.warning("linkedin_gmail: failed to decode text/plain part: %s", exc)
            return ""

    return ""


def _get_message_date(headers: list[dict]) -> datetime | None:
    """Pull the message Date header and parse to a tz-aware datetime."""
    for h in headers or []:
        if h.get("name", "").lower() == "date":
            raw = h.get("value", "")
            try:
                dt = parsedate_to_datetime(raw)
                if dt is not None and dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except (TypeError, ValueError) as exc:
                logger.warning("linkedin_gmail: bad Date header %r: %s", raw, exc)
                return None
    return None


# ---------------------------------------------------------------------------
# HTML parser
# ---------------------------------------------------------------------------


def _parse_relative_time(text: str, anchor: datetime | None) -> datetime | None:
    """Resolve 'X hours ago' / 'X days ago' against the email's Date header.

    Returns None if no relative-time phrase is found or anchor is missing.
    """
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


def _parse_linkedin_html(html: str, anchor: datetime | None) -> list[SourceJob]:
    """Parse a LinkedIn job-alert email body and return one SourceJob per job card.

    Strategy: locate each anchor matching the LinkedIn job-view URL pattern. For each
    match we walk up to the nearest ancestor that contains both the anchor and at
    least two adjacent text nodes (these carry company and location). This is more
    robust to LinkedIn's recurring template tweaks than nailing specific class names.

    Failure mode: if BeautifulSoup is not installed OR LinkedIn's template moves so
    far that we cannot locate company/location, we emit best-effort records with
    placeholder company "Unknown (LinkedIn)" rather than crashing — but we log
    WARNING so the operator can re-tune selectors.

    Dedup within one email: LinkedIn often surfaces the same job under multiple
    "highlights" sections. We dedup by job_id within a single email.
    """
    try:
        from bs4 import BeautifulSoup  # type: ignore
    except ImportError as exc:
        logger.warning(
            "linkedin_gmail: beautifulsoup4 not installed — falling back to regex-only parser. "
            "Install with: pip install beautifulsoup4. Detail: %s",
            exc,
        )
        return _parse_linkedin_html_regex_only(html, anchor)

    soup = BeautifulSoup(html, "html.parser")
    jobs: list[SourceJob] = []
    seen_ids: set[str] = set()

    for a in soup.find_all("a", href=True):
        href = a["href"]
        m = _LINKEDIN_JOB_URL_RE.search(href)
        if not m:
            continue
        job_id = m.group(1)
        if job_id in seen_ids:
            continue

        # ----- Title extraction -----
        # Observed real structure (June 2026): anchor wraps a nested table where the
        # title sits in a div with class containing "font-bold" (LinkedIn's design-token
        # naming). Older / alternate templates may use <strong>. Try in order.
        title = ""
        title_div = a.find("div", class_=re.compile(r"font-bold", re.IGNORECASE))
        if title_div:
            title = title_div.get_text(" ", strip=True)
        else:
            strong = a.find("strong")
            if strong:
                title = strong.get_text(" ", strip=True)
            else:
                # Last resort: anchor text with newline separators so we can split later.
                title_lines = [t.strip() for t in a.get_text("\n", strip=True).split("\n") if t.strip()]
                title = title_lines[0] if title_lines else ""
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            logger.debug("linkedin_gmail: skipping job_id=%s — empty title", job_id)
            continue

        # ----- Company + location extraction -----
        # Real structure: a <p> sibling of the title div contains "Company · Location"
        # (LinkedIn uses U+00B7 MIDDLE DOT '·' as the separator). The company logo
        # <img> also carries `alt="<Company>"` as a stable backup signal.
        company = ""
        location_raw = ""

        p_meta = a.find("p")
        if p_meta:
            meta_text = re.sub(r"\s+", " ", p_meta.get_text(" ", strip=True)).strip()
            # Split on middle-dot, bullet, or " · " whitespace variants
            parts = re.split(r"\s*[·•⋅]\s*", meta_text)
            if len(parts) >= 2:
                company = parts[0].strip()
                location_raw = " · ".join(parts[1:]).strip()
            else:
                # No separator: treat the whole thing as company.
                company = meta_text

        if not company:
            # Fallback to img alt (always present for posted jobs with company logos).
            img = a.find("img", alt=True)
            if img and img.get("alt"):
                alt = img["alt"].strip()
                if alt and alt.lower() not in {"linkedin", "logo"}:
                    company = alt

        if not company:
            company = "Unknown (LinkedIn)"

        # ----- Posted-at -----
        # Scan the WHOLE card text (not just anchor) for "X hours ago" / "X days ago".
        card = a
        for _ in range(4):
            if card.parent is None:
                break
            card = card.parent
            if card.name in ("td", "tr", "table"):
                break
        card_text = card.get_text(" ", strip=True) if card is not None else ""
        posted_at = _parse_relative_time(card_text, anchor)

        # The href in the email already carries the tracking query string we want to
        # preserve — normalize.py / canonicalize_url() will strip utm_/trk later.
        url = href

        try:
            jobs.append(SourceJob(
                source=JobSource.LINKEDIN_GMAIL,
                source_id=job_id,
                url=url,
                title=title,
                company=company,
                location_raw=location_raw,
                description_snippet="",
                posted_at=posted_at,
                contract_type_raw="",
            ))
            seen_ids.add(job_id)
        except (ValueError, TypeError) as exc:
            # Pydantic validation error (empty title/company/etc.) — skip this card.
            logger.warning("linkedin_gmail: skip job_id=%s (validation error): %s", job_id, exc)
            continue

    return jobs


def _parse_linkedin_html_regex_only(html: str, anchor: datetime | None) -> list[SourceJob]:
    """Fallback parser used when BeautifulSoup is unavailable.

    Strictly best-effort: pulls (job_id, url) tuples via regex and uses the anchor
    text inside `>...</a>` as the title. Cannot recover company / location reliably,
    so emits placeholder company. The orchestrator can still dedup by URL/title.
    """
    jobs: list[SourceJob] = []
    seen_ids: set[str] = set()
    # Crude anchor-with-href capture: <a ... href="LINK">TEXT</a>
    anchor_re = re.compile(
        r'<a\b[^>]*href=["\']([^"\']*linkedin\.com/comm/jobs/view/\d+[^"\']*)["\'][^>]*>(.*?)</a>',
        re.IGNORECASE | re.DOTALL,
    )
    for href, inner in anchor_re.findall(html):
        m = _LINKEDIN_JOB_URL_RE.search(href)
        if not m:
            continue
        job_id = m.group(1)
        if job_id in seen_ids:
            continue
        # Strip nested tags to get plain title text.
        title = re.sub(r"<[^>]+>", " ", inner)
        title = re.sub(r"\s+", " ", title).strip()
        if not title:
            continue
        try:
            jobs.append(SourceJob(
                source=JobSource.LINKEDIN_GMAIL,
                source_id=job_id,
                url=href,
                title=title,
                company="Unknown (LinkedIn)",
                location_raw="",
                description_snippet="",
                posted_at=_parse_relative_time(html, anchor),
                contract_type_raw="",
            ))
            seen_ids.add(job_id)
        except (ValueError, TypeError) as exc:
            logger.warning("linkedin_gmail: regex-fallback skip job_id=%s: %s", job_id, exc)
            continue
    return jobs


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def fetch(
    query: str | None = None,
    days: int = 2,
    max_emails: int = 20,
    max_jobs: int = 50,
    auth: str | None = None,
    label: str = "JobAlerts/LinkedIn",
) -> list[SourceJob]:
    """List LinkedIn alert emails matching the query, parse each, return SourceJobs.

    Args:
        query: full Gmail search string. If None, defaults to
               `label:{label} newer_than:{days}d` (only used by OAuth path).
        days: convenience knob — sets newer_than:{days}d in the default query AND
              acts as the IMAP SINCE window.
        max_emails: hard cap on how many alert emails we'll fetch.
        max_jobs: hard cap on emitted SourceJobs.
        auth: "imap" or "oauth". If None, dispatches to IMAP when
              GMAIL_SMTP_APP_PASSWORD is set (no Google Cloud bootstrap needed),
              otherwise falls back to OAuth. CLI / env override: GMAIL_AUTH_MODE.
        label: Gmail label to read from. Used by both auth paths.

    Returns:
        list[SourceJob], possibly empty. Auth failure raises LinkedInGmailAuthError.
        Per-message failures are logged + skipped, not raised.
    """
    if auth is None:
        auth = os.environ.get("GMAIL_AUTH_MODE", "").strip().lower() or None
    if auth is None:
        auth = "imap" if os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip() else "oauth"

    if auth == "imap":
        logger.info("linkedin_gmail: using IMAP path (App Password)")
        return fetch_via_imap(label=label, days=days, max_emails=max_emails, max_jobs=max_jobs)

    if auth != "oauth":
        raise LinkedInGmailAuthError(f"unknown auth mode {auth!r} — expected 'imap' or 'oauth'")

    logger.info("linkedin_gmail: using OAuth REST path")
    if query is None:
        query = f"label:{label} newer_than:{days}d"

    try:
        service = _build_gmail_service()
    except LinkedInGmailAuthError:
        raise
    except Exception as exc:
        raise LinkedInGmailAuthError(f"Unexpected error building Gmail service: {exc}") from exc

    jobs: list[SourceJob] = []
    try:
        list_resp = (
            service.users()
            .messages()
            .list(userId="me", q=query, maxResults=max_emails)
            .execute()
        )
    except Exception as exc:  # googleapiclient raises HttpError; treat as transient/log+skip.
        logger.error("linkedin_gmail: messages.list failed (q=%r): %s", query, exc)
        return jobs

    msg_refs = list_resp.get("messages", []) or []
    logger.info("linkedin_gmail: %d matching email(s) for query %r", len(msg_refs), query)

    seen_ids_global: set[str] = set()
    for ref in msg_refs:
        if len(jobs) >= max_jobs:
            logger.info("linkedin_gmail: max_jobs=%d reached, stopping", max_jobs)
            break
        msg_id = ref.get("id")
        if not msg_id:
            continue
        try:
            msg = (
                service.users()
                .messages()
                .get(userId="me", id=msg_id, format="full")
                .execute()
            )
        except Exception as exc:
            logger.warning("linkedin_gmail: messages.get failed for id=%s: %s", msg_id, exc)
            continue

        payload = msg.get("payload", {}) or {}
        headers = payload.get("headers", []) or []
        anchor = _get_message_date(headers)
        html = _walk_payload_for_html(payload)
        if not html:
            logger.warning("linkedin_gmail: no HTML/plain part found in message id=%s", msg_id)
            continue

        parsed = _parse_linkedin_html(html, anchor)
        if not parsed:
            logger.warning(
                "linkedin_gmail: parsed 0 jobs from message id=%s — LinkedIn template may have changed",
                msg_id,
            )

        for job in parsed:
            if job.source_id in seen_ids_global:
                continue
            seen_ids_global.add(job.source_id)
            jobs.append(job)
            if len(jobs) >= max_jobs:
                break

    logger.info("linkedin_gmail: emitted %d SourceJob(s)", len(jobs))
    return jobs


def fetch_via_imap(
    label: str = "JobAlerts/LinkedIn",
    days: int = 2,
    max_emails: int = 20,
    max_jobs: int = 50,
) -> list[SourceJob]:
    """Read LinkedIn alert emails from Gmail via IMAP using an App Password.

    Why IMAP over OAuth REST: the user already has GMAIL_SMTP_APP_PASSWORD provisioned
    for v1's outbound notify. Gmail IMAP accepts the same App Password. This avoids the
    Google Cloud Console + OAuth bootstrap flow entirely.

    Required env: GMAIL_SMTP_USER, GMAIL_SMTP_APP_PASSWORD.

    Mailbox name: Gmail exposes custom labels as IMAP mailboxes with the literal label
    name (nested via '/'). 'JobAlerts/LinkedIn' is correct.

    Note: Gmail IMAP supports App Passwords today but Google is gradually pushing OAuth.
    If this ever stops working, fall back to the OAuth path via fetch() proper.
    """
    import imaplib
    import email as email_lib
    from email.policy import default as email_default_policy

    user = os.environ.get("GMAIL_SMTP_USER", "").strip()
    pw = os.environ.get("GMAIL_SMTP_APP_PASSWORD", "").strip()
    if not (user and pw):
        raise LinkedInGmailAuthError(
            "GMAIL_SMTP_USER and GMAIL_SMTP_APP_PASSWORD must be set in .env for IMAP mode."
        )

    jobs: list[SourceJob] = []
    seen_ids_global: set[str] = set()

    try:
        imap = imaplib.IMAP4_SSL("imap.gmail.com", 993, timeout=30)
        imap.login(user, pw)
    except (imaplib.IMAP4.error, OSError) as exc:
        raise LinkedInGmailAuthError(f"IMAP login failed: {exc}") from exc

    try:
        # Mailbox names with '/' must be quoted in the IMAP SELECT verb.
        status, _ = imap.select(f'"{label}"', readonly=True)
        if status != "OK":
            logger.error("linkedin_gmail [imap]: label %r not found (IMAP SELECT returned %s). "
                         "Create the label in Gmail web first.", label, status)
            return jobs

        since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%d-%b-%Y")
        status, data = imap.search(None, f'SINCE {since}')
        if status != "OK":
            logger.error("linkedin_gmail [imap]: SEARCH failed: %s", status)
            return jobs

        ids = (data[0] or b"").split()
        logger.info("linkedin_gmail [imap]: %d email(s) since %s in label %r", len(ids), since, label)
        ids = ids[-max_emails:]  # newest N (Gmail returns ascending by UID)

        for msg_id in reversed(ids):  # process newest first
            if len(jobs) >= max_jobs:
                break
            status, msg_data = imap.fetch(msg_id, "(RFC822)")
            if status != "OK" or not msg_data or not msg_data[0]:
                logger.warning("linkedin_gmail [imap]: FETCH failed for id=%s", msg_id)
                continue
            raw = msg_data[0][1]
            try:
                msg = email_lib.message_from_bytes(raw, policy=email_default_policy)
            except Exception as exc:  # noqa: BLE001 — email surface is broad; log + skip
                logger.warning("linkedin_gmail [imap]: parse failure id=%s: %s", msg_id, exc)
                continue

            date_str = msg.get("Date", "")
            try:
                anchor = parsedate_to_datetime(date_str) if date_str else None
                if anchor is not None and anchor.tzinfo is None:
                    anchor = anchor.replace(tzinfo=timezone.utc)
            except (TypeError, ValueError):
                anchor = None

            # Prefer HTML; fall back to plain.
            html = ""
            for part in msg.walk():
                ctype = part.get_content_type()
                if ctype == "text/html":
                    try:
                        html = part.get_content()
                        break
                    except Exception as exc:  # noqa: BLE001
                        logger.warning("linkedin_gmail [imap]: get_content failed id=%s: %s", msg_id, exc)
            if not html:
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        try:
                            html = part.get_content()
                            break
                        except Exception as exc:  # noqa: BLE001
                            logger.warning("linkedin_gmail [imap]: get_content failed id=%s: %s", msg_id, exc)
            if not html:
                logger.warning("linkedin_gmail [imap]: no body content for id=%s", msg_id)
                continue

            parsed = _parse_linkedin_html(html, anchor)
            if not parsed:
                logger.warning(
                    "linkedin_gmail [imap]: parsed 0 jobs from email id=%s — LinkedIn template may have shifted",
                    msg_id,
                )
            for job in parsed:
                if job.source_id in seen_ids_global:
                    continue
                seen_ids_global.add(job.source_id)
                jobs.append(job)
                if len(jobs) >= max_jobs:
                    break
    finally:
        try:
            imap.logout()
        except Exception:  # noqa: BLE001 — best-effort cleanup
            pass

    logger.info("linkedin_gmail [imap]: emitted %d SourceJob(s)", len(jobs))
    return jobs


def fetch_from_fixture(fixture_path: Path) -> list[SourceJob]:
    """Offline mode: parse a recorded HTML file as if it were a single alert email body.

    Used by the front-door synthetic and by unit tests so we never burn a Gmail API
    call (or risk an OAuth token issue) in CI.
    """
    html = fixture_path.read_text(encoding="utf-8")
    # No real Date header in the fixture; anchor relative-time parsing to "now" so the
    # synthetic still produces tz-aware posted_at when the fixture contains "2 hours ago".
    anchor = datetime.now(timezone.utc)
    return _parse_linkedin_html(html, anchor)


def _write_jsonl(jobs: list[SourceJob], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for job in jobs:
            f.write(job.model_dump_json() + "\n")


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="LinkedIn Job-Alert email ingestion (via Gmail API).")
    parser.add_argument(
        "--query",
        default=None,
        help="Gmail search query. Default: label:JobAlerts/LinkedIn newer_than:{--days}d",
    )
    parser.add_argument("--days", type=int, default=2, help="newer_than:Nd window for the default query / IMAP SINCE.")
    parser.add_argument("--max-emails", type=int, default=20)
    parser.add_argument("--max-jobs", type=int, default=50)
    parser.add_argument("--auth", choices=["imap", "oauth"], default=None,
                        help="Force auth path. Default: imap if GMAIL_SMTP_APP_PASSWORD set, else oauth.")
    parser.add_argument("--label", default="JobAlerts/LinkedIn",
                        help="Gmail label to read from. Default: JobAlerts/LinkedIn.")
    parser.add_argument(
        "--fixture",
        type=Path,
        help="Parse this HTML file instead of hitting Gmail (offline mode).",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output JSONL path (default: .tmp/job_search_v2/linkedin_gmail_<run_id>.jsonl)",
    )
    args = parser.parse_args()

    if args.fixture:
        fixture_path: Path = args.fixture
        if not fixture_path.exists():
            logger.error("linkedin_gmail: fixture not found: %s", fixture_path)
            return 2
        jobs = fetch_from_fixture(fixture_path)
        logger.info("linkedin_gmail: %d jobs from fixture %s", len(jobs), fixture_path)
    else:
        try:
            jobs = fetch(
                query=args.query,
                days=args.days,
                max_emails=args.max_emails,
                max_jobs=args.max_jobs,
                auth=args.auth,
                label=args.label,
            )
        except LinkedInGmailAuthError as exc:
            logger.error("linkedin_gmail: auth failure — %s", exc)
            return 2

    run_id = uuid.uuid4().hex[:8]
    out_path = args.out or (TMP_DIR / f"linkedin_gmail_{run_id}.jsonl")
    _write_jsonl(jobs, out_path)
    logger.info("linkedin_gmail: wrote %d jobs to %s", len(jobs), out_path)

    for job in jobs:
        sys.stdout.write(job.model_dump_json() + "\n")
    return 0 if jobs else 1


if __name__ == "__main__":
    sys.exit(main())
