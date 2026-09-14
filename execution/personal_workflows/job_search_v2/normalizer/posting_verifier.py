"""
description: Posting-liveness verifier for NormalizedJobs. Opens each job's
    detail page, extracts the real posted date (JSON-LD JobPosting first, then
    meta/time tags, then relative/absolute text dates) and whether the posting
    is still open (JSON-LD validThrough, closed-text detection, HTTP status,
    redirect-to-search-page). Drops anything closed or older than
    `max_age_days`. Operator complaint (2026-09): >=50% of jobs landing in the
    sheet were expired / closed / months old — the prior pipeline trusted the
    source's own posted_at without ever loading the page.
inputs:
    - list[NormalizedJob]
outputs:
    - (kept, stats, records) where stats = {total_in, kept, rejected, by_reason,
      by_status, rejected_sample, unverifiable_ratio_by_host, warnings}
      records = {content_hash: VerificationRecord}

Design notes:
    - parse_posting_page() is pure (no I/O) so it is exhaustively unit-tested
      without a network.
    - fetch_page() is the only I/O boundary; verify_job()/verify_jobs() accept
      an injectable `fetch` callable so tests never touch the network.
    - HTTP mapping: 404/410 -> closed. 403/429/999/5xx/None (fetch failure) ->
      unverifiable (site is blocking us, not necessarily that the job is gone).
      A redirect landing on a listing/search page -> closed (the job page was
      pulled and the site bounced us to search results).
    - When the page itself can't be trusted (unverifiable) but the source's
      own posted_at is within the freshness window, we keep the job flagged
      `ok_unverified_fresh` rather than silently dropping good leads because a
      site rate-limited us. FRANCE_TRAVAIL and *_gmail sources are trusted on
      source date by default when the page has no date at all, because those
      dates come from an API/alert timestamp, not a scrape.
"""

from __future__ import annotations

import json
import logging
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Callable, Literal
from urllib.parse import urlsplit

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    JobSource,
    NormalizedJob,
)
from execution.personal_workflows.job_search_v2.normalizer.browser_fetch import (  # noqa: E402
    make_browser_fetcher,
)

logger = logging.getLogger("normalizer.posting_verifier")

_STATUS = Literal["open", "closed", "unknown"]
_RECORD_STATUS = Literal["open", "closed", "unverifiable", "unknown"]
_DATE_SOURCE = Literal["page", "source", "none"]
_DECISION = Literal["keep", "drop"]

_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
)
_ACCEPT_LANGUAGE = "fr-FR,fr;q=0.9,en;q=0.8"

# Sources whose posted_at is trusted straight from the API/alert when the
# fetched page carries no date of its own.
_TRUST_SOURCE_DATE_SOURCES = {
    JobSource.FRANCE_TRAVAIL,
    JobSource.LINKEDIN_GMAIL,
    JobSource.INDEED_GMAIL,
    JobSource.HELLOWORK_GMAIL,
    JobSource.JOBGETHER_GMAIL,
}


@dataclass(frozen=True)
class PageVerdict:
    status: _STATUS
    posted_at: datetime | None
    valid_through: datetime | None
    evidence: str
    http_status: int | None
    final_url: str


@dataclass(frozen=True)
class VerificationRecord:
    status: _RECORD_STATUS
    posted_at: datetime | None
    date_source: _DATE_SOURCE
    age_days: float | None
    checked_at: datetime
    evidence: str
    decision: _DECISION
    reason: str
    # Defaults to "" for verify_url() callers (e.g. the sheet re-verification
    # pass) that have no NormalizedJob / content_hash to attach.
    content_hash: str = ""


# ---------------------------------------------------------------------------
# Pure parsing
# ---------------------------------------------------------------------------

_CLOSED_PATTERNS = [
    # EN generic
    "no longer accepting applications",
    "this job is no longer available",
    "job has expired",
    "this job has expired",
    "this position has been filled",
    "applications for this job are closed",
    "job posting has closed",
    "this job posting is no longer active",
    "the job you are looking for is no longer available",
    "job not found",
    # FR generic
    "n'est plus disponible",
    "n'accepte plus de candidatures",
    "offre expiree",
    "cette offre a expire",
    "offre d'emploi a expire",
    "n'est plus en ligne",
    "offre pourvue",
    "poste pourvu",
    "cette annonce n'est plus d'actualite",
    "offre introuvable",
    "cette offre d'emploi n'existe plus",
    "les candidatures sont closes",
    # site-specific
    "no longer accepting applications",  # linkedin en (dup, harmless)
    "cette offre n'accepte plus de candidatures",  # linkedin fr
    "cette offre n'est plus disponible",  # wttj / hellowork / francetravail / apec
    "this job is no longer available",  # wttj en (dup, harmless)
    "offre expiree",  # hellowork
    "this job has expired on indeed",
    "cette offre d'emploi a expire",  # indeed fr
    "l'offre n'est plus disponible",  # france travail
    # Soft-404s: WTTJ serves HTTP 200 with an "Error 404 / Page not found"
    # body for a removed job (observed live 2026-09-10). Scripts/styles are
    # stripped before matching, so JS-bundle strings cannot trigger these.
    "error 404",
    "page not found",
    "404 not found",
    "page introuvable",
    "cette page n'existe pas",
    "this page doesn't exist",
    "this page does not exist",
]

_APPLY_SIGNALS = (
    "easy apply",
    "je postule",
    "apply now",
    "apply for this job",
    ">apply<",
    "postuler",
    "candidater",
)

# LinkedIn guest-page open signals: class-name fragments that show up on a
# live posting's apply CTA / top-card, even when the page variant carries no
# JSON-LD JobPosting and no apply-text match (observed live 2026-09:
# LinkedIn intermittently serves this lighter variant, which a second
# request typically resolves to the full page).
_CLASS_OPEN_SIGNALS = (
    "apply-button",
    "top-card-layout",
    "jobs-apply-button",
)


def _detect_class_open_signal(html: str) -> bool:
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
    except Exception as exc:  # noqa: BLE001 — bs4 parse surface, never fatal
        logger.warning("posting_verifier: class-signal scan failed (%s)", exc)
        return False
    for el in soup.find_all(class_=True):
        classes = el.get("class") or []
        joined = " ".join(classes).lower()
        if any(sig in joined for sig in _CLASS_OPEN_SIGNALS):
            return True
    return False


def _strip_accents(text: str) -> str:
    replacements = {
        "é": "e", "è": "e", "ê": "e", "ë": "e",
        "à": "a", "â": "a",
        "î": "i", "ï": "i",
        "ô": "o",
        "ù": "u", "û": "u", "ü": "u",
        "ç": "c",
        "É": "e", "È": "e", "Ê": "e",
        "À": "a", "Â": "a",
        "Î": "i", "Ï": "i",
        "Ô": "o",
        "Ù": "u", "Û": "u",
        "Ç": "c",
    }
    for src, dst in replacements.items():
        text = text.replace(src, dst)
    return text


def _visible_text(html: str) -> str:
    """Strip scripts/styles and return lowercased, accent-folded visible text."""
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text(separator=" ")
    except Exception as exc:  # noqa: BLE001 — bs4 parse surface, never fatal
        logger.warning("posting_verifier: visible-text extraction failed (%s)", exc)
        text = html
    return _strip_accents(text.lower())


def _detect_closed(visible_text_low: str) -> str | None:
    for pattern in _CLOSED_PATTERNS:
        needle = _strip_accents(pattern.lower())
        if needle in visible_text_low:
            return pattern
    return None


def _detect_apply_signal(visible_text_low: str) -> bool:
    return any(sig in visible_text_low for sig in _APPLY_SIGNALS)


def _parse_iso_datetime(value: str) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    v = value.strip()
    if not v:
        return None
    try:
        # Date-only (YYYY-MM-DD) -> midnight UTC.
        if re.fullmatch(r"\d{4}-\d{2}-\d{2}", v):
            dt = datetime.strptime(v, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            return dt
        v2 = v.replace("Z", "+00:00")
        dt = datetime.fromisoformat(v2)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError):
        return None


def _iter_jobposting_nodes(node) -> list[dict]:
    """Recursively find every dict that looks like schema.org JobPosting."""
    found: list[dict] = []
    if isinstance(node, dict):
        types = node.get("@type")
        type_list = types if isinstance(types, list) else [types]
        if any(isinstance(t, str) and t.lower() == "jobposting" for t in type_list):
            found.append(node)
        # @graph nesting
        if isinstance(node.get("@graph"), list):
            for sub in node["@graph"]:
                found.extend(_iter_jobposting_nodes(sub))
        # mainEntity nesting
        if isinstance(node.get("mainEntity"), (dict, list)):
            found.extend(_iter_jobposting_nodes(node["mainEntity"]))
    elif isinstance(node, list):
        for sub in node:
            found.extend(_iter_jobposting_nodes(sub))
    return found


def _extract_jsonld_jobpostings(html: str) -> list[dict]:
    try:
        from bs4 import BeautifulSoup  # type: ignore

        soup = BeautifulSoup(html, "html.parser")
        scripts = soup.find_all("script", attrs={"type": "application/ld+json"})
    except Exception as exc:  # noqa: BLE001 — bs4 parse surface, never fatal
        logger.warning("posting_verifier: json-ld script scan failed (%s)", exc)
        return []

    postings: list[dict] = []
    for script in scripts:
        raw = script.string or script.get_text() or ""
        raw = raw.strip()
        if not raw:
            continue
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError):
            # Malformed JSON-LD must never raise — skip this block.
            continue
        try:
            postings.extend(_iter_jobposting_nodes(data))
        except Exception as exc:  # noqa: BLE001 — defensive, structure can be anything
            logger.warning("posting_verifier: json-ld traversal failed (%s)", exc)
            continue
    return postings


_RELATIVE_EN_RE = re.compile(
    r"\bposted\s+today\b"
    r"|\bposted\s+yesterday\b"
    r"|\bjust\s+now\b"
    r"|\b(?:posted|reposted)?\s*(\d+)\+?\s*(hour|hours|day|days|week|weeks|month|months)\s+ago\b",
    re.IGNORECASE,
)

_RELATIVE_FR_RE = re.compile(
    r"\bil\s+y\s+a\s+(\d+)\s*(heure|heures|jour|jours|semaine|semaines|mois)\b"
    r"|\b(aujourd'?hui)\b"
    r"|\b(hier)\b",
    re.IGNORECASE,
)

_FR_MONTHS = {
    "janvier": 1, "janv": 1,
    "fevrier": 2, "fevr": 2, "févr": 2,
    "mars": 3,
    "avril": 4, "avr": 4,
    "mai": 5,
    "juin": 6,
    "juillet": 7, "juil": 7,
    "aout": 8, "août": 8,
    "septembre": 9, "sept": 9,
    "octobre": 10, "oct": 10,
    "novembre": 11, "nov": 11,
    "decembre": 12, "dec": 12, "déc": 12,
}

_FR_ABSOLUTE_NUMERIC_RE = re.compile(
    r"(?:publi[ée]e?\s+le|date\s+de\s+publication\s*:|actualis[ée]e?\s+le)\s*"
    r"(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})",
    re.IGNORECASE,
)

_FR_ABSOLUTE_MONTHNAME_RE = re.compile(
    r"(?:publi[ée]e?\s+le)\s*(\d{1,2})\s+([a-zA-Zéû.]+)\s+(\d{4})",
    re.IGNORECASE,
)


def _relative_to_datetime(now: datetime, qty: int, unit: str) -> datetime:
    unit = unit.lower()
    if unit.startswith("hour"):
        return now - timedelta(hours=qty)
    if unit.startswith("day") or unit.startswith("jour"):
        return now - timedelta(days=qty)
    if unit.startswith("week") or unit.startswith("semaine"):
        return now - timedelta(weeks=qty)
    if unit.startswith("month") or unit.startswith("mois"):
        return now - timedelta(days=30 * qty)
    return now


def _find_relative_or_absolute_date(text_raw: str, now: datetime) -> tuple[datetime | None, str | None]:
    """Scan raw (accent-preserved-but-lowered) text in document order for the
    FIRST matching relative/absolute date pattern. Returns (datetime, evidence).
    """
    candidates: list[tuple[int, datetime, str]] = []

    for m in _RELATIVE_EN_RE.finditer(text_raw):
        span_start = m.start()
        whole = m.group(0).lower()
        if "today" in whole:
            candidates.append((span_start, now, "text:posted today"))
            continue
        if "yesterday" in whole:
            candidates.append((span_start, now - timedelta(days=1), "text:posted yesterday"))
            continue
        if "just now" in whole:
            candidates.append((span_start, now, "text:just now"))
            continue
        qty_s, unit = m.group(1), m.group(2)
        if qty_s is None or unit is None:
            continue
        qty = int(qty_s)
        if "30+" in whole or re.search(r"\d+\+\s*days", whole):
            qty = 31
        dt = _relative_to_datetime(now, qty, unit)
        candidates.append((span_start, dt, f"text:'{m.group(0).strip()}'"))

    for m in _RELATIVE_FR_RE.finditer(text_raw):
        span_start = m.start()
        whole = m.group(0)
        low = whole.lower()
        if "aujourd" in low:
            candidates.append((span_start, now, "text:aujourd'hui"))
            continue
        if low == "hier":
            candidates.append((span_start, now - timedelta(days=1), "text:hier"))
            continue
        qty_s, unit = m.group(1), m.group(2)
        if qty_s is None or unit is None:
            continue
        qty = int(qty_s)
        dt = _relative_to_datetime(now, qty, unit)
        candidates.append((span_start, dt, f"text:'{whole.strip()}'"))

    for m in _FR_ABSOLUTE_NUMERIC_RE.finditer(text_raw):
        day, month, year = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 100:
            year += 2000
        try:
            dt = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        candidates.append((m.start(), dt, f"text:'{m.group(0).strip()}'"))

    for m in _FR_ABSOLUTE_MONTHNAME_RE.finditer(text_raw):
        day = int(m.group(1))
        month_raw = _strip_accents(m.group(2).lower()).rstrip(".")
        year = int(m.group(3))
        month = _FR_MONTHS.get(month_raw)
        if month is None:
            continue
        try:
            dt = datetime(year, month, day, tzinfo=timezone.utc)
        except ValueError:
            continue
        candidates.append((m.start(), dt, f"text:'{m.group(0).strip()}'"))

    if not candidates:
        return None, None
    candidates.sort(key=lambda c: c[0])
    _, dt, evidence = candidates[0]
    return dt, evidence


def parse_posting_page(html: str, url: str, now: datetime) -> PageVerdict:
    """Pure extraction of liveness + posted date from a fetched HTML page.

    Never raises: malformed JSON-LD, unparsable dates, and bad markup all
    degrade to "no signal found" rather than propagating an exception.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    posted_at: datetime | None = None
    valid_through: datetime | None = None
    evidence = ""
    has_jsonld_jobposting = False

    # 1. JSON-LD JobPosting.
    postings = _extract_jsonld_jobpostings(html)
    for posting in postings:
        has_jsonld_jobposting = True
        date_posted = posting.get("datePosted")
        vt = posting.get("validThrough")
        parsed_posted = _parse_iso_datetime(date_posted) if isinstance(date_posted, str) else None
        parsed_vt = _parse_iso_datetime(vt) if isinstance(vt, str) else None
        if parsed_posted and posted_at is None:
            posted_at = parsed_posted
            evidence = f"jsonld:datePosted={date_posted}"
        if parsed_vt and (valid_through is None or parsed_vt < valid_through):
            valid_through = parsed_vt
        if posted_at is not None:
            break

    if valid_through is not None and valid_through < now:
        return PageVerdict(
            status="closed",
            posted_at=posted_at,
            valid_through=valid_through,
            evidence=f"jsonld:validThrough={valid_through.isoformat()}",
            http_status=None,
            final_url=url,
        )

    # 2. meta/time tags, if JSON-LD gave no date.
    if posted_at is None:
        try:
            from bs4 import BeautifulSoup  # type: ignore

            soup = BeautifulSoup(html, "html.parser")
            meta_candidates = []
            m1 = soup.find("meta", attrs={"property": "article:published_time"})
            if m1 and m1.get("content"):
                meta_candidates.append(("meta:article:published_time", m1["content"]))
            m2 = soup.find("meta", attrs={"name": "date"})
            if m2 and m2.get("content"):
                meta_candidates.append(("meta:date", m2["content"]))
            for t in soup.find_all("time"):
                dt_attr = t.get("datetime")
                if dt_attr:
                    meta_candidates.append(("time:datetime", dt_attr))
            itemprop = soup.find(attrs={"itemprop": "datePosted"})
            if itemprop is not None:
                val = itemprop.get("content") or itemprop.get("datetime") or itemprop.get_text()
                if val:
                    meta_candidates.append(("itemprop:datePosted", val))
            for label, raw_val in meta_candidates:
                parsed = _parse_iso_datetime(raw_val)
                if parsed:
                    posted_at = parsed
                    evidence = f"{label}={raw_val}"
                    break
        except Exception as exc:  # noqa: BLE001 — bs4 parse surface, never fatal
            logger.warning("posting_verifier: meta/time date extraction failed (%s)", exc)

    visible_low = _visible_text(html)

    # 3. Closed-text detection.
    closed_hit = _detect_closed(visible_low)
    if closed_hit:
        return PageVerdict(
            status="closed",
            posted_at=posted_at,
            valid_through=valid_through,
            evidence=f"text:'{closed_hit}'",
            http_status=None,
            final_url=url,
        )

    # 4. Relative/absolute text dates, if still no date.
    if posted_at is None:
        text_dt, text_evidence = _find_relative_or_absolute_date(visible_low, now)
        if text_dt is not None:
            posted_at = text_dt
            evidence = text_evidence or evidence

    if not evidence and posted_at is not None:
        evidence = "date_found"

    # 5. Status resolution: open if JobPosting JSON-LD, an apply text signal,
    # or an apply/top-card class-name fragment (LinkedIn guest-page variant)
    # exists; else unknown.
    has_class_signal = False
    if not (has_jsonld_jobposting or _detect_apply_signal(visible_low)):
        has_class_signal = _detect_class_open_signal(html)

    if has_jsonld_jobposting or _detect_apply_signal(visible_low) or has_class_signal:
        status: _STATUS = "open"
        if not evidence:
            if has_jsonld_jobposting:
                evidence = "jsonld:jobposting"
            elif has_class_signal:
                evidence = "class:apply_signal"
            else:
                evidence = "text:apply_signal"
    else:
        status = "unknown"
        if not evidence:
            evidence = "no_signal"

    return PageVerdict(
        status=status,
        posted_at=posted_at,
        valid_through=valid_through,
        evidence=evidence,
        http_status=None,
        final_url=url,
    )


# ---------------------------------------------------------------------------
# I/O boundary
# ---------------------------------------------------------------------------


# Statuses that mean "try once more after a pause" rather than a verdict:
# 429 (rate limit), 503 (overload) and 202 (WTTJ's anti-bot challenge answers
# 202 with an EMPTY body; the real page comes back on the next request).
_RETRY_STATUSES = {202, 429, 503}
_RETRY_DELAY_SECONDS = 3.0
# Below this many characters a 2xx body is not a job page (empty challenge
# response / interstitial) — treated as blocked, never as "no signal".
_MIN_PAGE_CHARS = 500


def fetch_page(url: str, client=None, timeout: float = 15.0, retries: int = 1) -> tuple[int | None, str, str]:
    """Fetch `url`, following redirects. Never raises — network/timeout/parse
    failures collapse to (None, "", url) so verify_job() can treat them as
    "unverifiable" instead of crashing the batch. Retries once (after a short
    pause) on 429 / 503 / 202-with-empty-body, which are throttles, not verdicts."""
    try:
        import httpx

        headers = {
            "User-Agent": _USER_AGENT,
            "Accept-Language": _ACCEPT_LANGUAGE,
        }
        owns_client = client is None
        if owns_client:
            client = httpx.Client(follow_redirects=True, timeout=timeout, headers=headers)
        try:
            attempt = 0
            while True:
                resp = client.get(url, headers=headers, timeout=timeout)
                status, text, final = resp.status_code, resp.text, str(resp.url)
                soft_block = status in _RETRY_STATUSES or (
                    200 <= status < 300 and len(text.strip()) < _MIN_PAGE_CHARS
                )
                if soft_block and attempt < retries:
                    attempt += 1
                    time.sleep(_RETRY_DELAY_SECONDS * attempt)
                    continue
                return status, text, final
        finally:
            if owns_client:
                client.close()
    except Exception as exc:  # noqa: BLE001 — network surface, must never raise
        logger.warning("posting_verifier: fetch failed for %s (%s)", url, exc)
        return None, "", url


_LISTING_PATH_RE = re.compile(
    r"/jobs/search"
    r"|/emploi/recherche"
    r"|/jobs\?"
    r"|/offres/recherche"
    # LinkedIn sends an expired job to "/jobs/<title-slug>-jobs?trk=expired_jd_redirect"
    # (observed live 2026-09-10); the query marker is the strongest signal, the
    # "-jobs" slug listing is the belt-and-braces path check.
    r"|expired_jd_redirect"
    r"|/jobs/[^/?]+-jobs(?:\?|$)"
    r"|/jobs/collections",
)


def _is_listing_redirect(final_url: str) -> bool:
    parts = urlsplit(final_url)
    path_and_query = parts.path + ("?" + parts.query if parts.query else "")
    if _LISTING_PATH_RE.search(path_and_query):
        return True
    if parts.path in ("", "/"):
        return True
    return False


# ---------------------------------------------------------------------------
# Per-job verification
# ---------------------------------------------------------------------------


_FetchFn = Callable[[str], tuple[int | None, str, str]]


def _classify_fetch(
    http_status: int | None, html: str, final_url: str, now: datetime
) -> tuple[str, object]:
    """Map a raw (status, html, final_url) triple onto one of:
    - ("closed", evidence: str)
    - ("blocked", evidence: str)          -- host blocked us, retry-worthy
    - ("verdict", PageVerdict)             -- got a real page to reason about
    Never raises: this is the shared classification used by both the direct
    fetch and any browser-fallback / re-fetch attempt.
    """
    if http_status in (404, 410):
        return "closed", f"http:{http_status}"

    if http_status is None or http_status in (403, 429, 999) or (http_status and http_status >= 500):
        return "blocked", f"http:{http_status if http_status is not None else 'error'}"

    if _is_listing_redirect(final_url):
        return "closed", f"redirect:{final_url}"

    if not _visible_text(html or "").strip():
        # WTTJ answers its anti-bot challenge with "202 Accepted" and an empty
        # body; other hosts serve blank interstitials. No page → blocked,
        # never "no signal" (which would drop a live job as undatable).
        return "blocked", f"http:{http_status}:empty_body"

    return "verdict", parse_posting_page(html, final_url, now)


def _ignore_future_date(verdict: PageVerdict, now: datetime, url: str) -> PageVerdict:
    # A page date more than a day in the FUTURE is a site bug / placeholder,
    # not a posting date: ignore it and fall through to the source date.
    if verdict.posted_at is not None and (verdict.posted_at - now) > timedelta(days=1):
        logger.info("posting_verifier: ignoring future page date %s for %s", verdict.posted_at, url)
        return PageVerdict(
            status=verdict.status, posted_at=None, valid_through=verdict.valid_through,
            evidence=verdict.evidence + "+future_date_ignored",
            http_status=verdict.http_status, final_url=verdict.final_url,
        )
    return verdict


def verify_url(
    url: str,
    *,
    source_posted_at: datetime | None,
    source: JobSource | None,
    now: datetime,
    fetch: _FetchFn = fetch_page,
    max_age_days: int = 7,
    strict: bool = True,
    browser_fetch: _FetchFn | None = None,
) -> VerificationRecord:
    """Core liveness check for a single URL. No NormalizedJob required — the
    sheet re-verification pass calls this directly, so the returned record's
    `content_hash` defaults to "" (verify_job() attaches the real hash).

    Strict mode (the default, matching the operator's "manual tester" bar):
    - a host that stays blocked even after one browser-fallback attempt is
      dropped (`unverifiable_blocked`) instead of trusted on source date.
    - a dated page with no positive open signal ("unknown") gets exactly one
      re-fetch; if it is still unconfirmed, it is dropped
      (`unconfirmed_open`) instead of kept.

    Lenient mode (`strict=False`) reproduces the pre-strict-mode behaviour:
    blocked-with-fresh-source-date and unconfirmed-but-dated pages are both
    kept.
    """
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if source_posted_at is not None and source_posted_at.tzinfo is None:
        source_posted_at = source_posted_at.replace(tzinfo=timezone.utc)
    trust_source = source in _TRUST_SOURCE_DATE_SOURCES

    def _finalize(
        status: _RECORD_STATUS,
        posted_at: datetime | None,
        date_source: _DATE_SOURCE,
        evidence: str,
    ) -> VerificationRecord:
        age_days = (now - posted_at).total_seconds() / 86400.0 if posted_at is not None else None

        if status == "closed":
            decision: _DECISION = "drop"
            reason = "closed"
        elif posted_at is None:
            decision = "drop"
            reason = "unverifiable_no_date" if status == "unverifiable" else "age_unknown"
        elif age_days is not None and age_days > max_age_days:
            decision = "drop"
            reason = "stale"
        elif status == "unverifiable":
            if strict:
                decision, reason = "drop", "unverifiable_blocked"
            else:
                decision, reason = "keep", "ok_unverified_fresh"
        elif status == "unknown":
            if strict:
                decision, reason = "drop", "unconfirmed_open"
            else:
                decision, reason = "keep", "ok"
        else:
            decision = "keep"
            reason = "ok"

        record = VerificationRecord(
            status=status,
            posted_at=posted_at,
            date_source=date_source,
            age_days=age_days,
            checked_at=now,
            evidence=evidence,
            decision=decision,
            reason=reason,
        )
        logger.info(
            "posting_verifier: decision=%s reason=%s status=%s age_days=%s url=%s",
            record.decision, record.reason, record.status, record.age_days, url,
        )
        return record

    http_status, html, final_url = fetch(url)
    kind, payload = _classify_fetch(http_status, html, final_url, now)

    if kind == "blocked" and browser_fetch is not None:
        b_status, b_html, b_final = browser_fetch(url)
        b_kind, b_payload = _classify_fetch(b_status, b_html, b_final, now)
        if b_kind == "closed":
            return _finalize("closed", None, "none", f"browser:{b_payload}")
        if b_kind == "blocked":
            kind, payload = "blocked", f"browser:{b_payload}"
        else:  # "verdict" — the browser got past the block.
            bv = b_payload  # type: PageVerdict
            kind, payload = "verdict", PageVerdict(
                status=bv.status, posted_at=bv.posted_at, valid_through=bv.valid_through,
                evidence=f"browser:{bv.evidence}", http_status=bv.http_status, final_url=bv.final_url,
            )

    if kind == "closed":
        return _finalize("closed", None, "none", payload)  # type: ignore[arg-type]

    if kind == "blocked":
        evidence = payload  # type: ignore[assignment]
        if source_posted_at is not None:
            return _finalize("unverifiable", source_posted_at, "source", evidence)
        return _finalize("unverifiable", None, "none", evidence)

    verdict: PageVerdict = payload  # type: ignore[assignment]

    if verdict.status == "closed":
        return _finalize("closed", verdict.posted_at, "page" if verdict.posted_at else "none", verdict.evidence)

    verdict = _ignore_future_date(verdict, now, url)

    # Strict mode: an "unknown" page (dated but no positive open signal, or
    # no signal at all) gets exactly one re-fetch — LinkedIn intermittently
    # serves a lighter guest-page variant that comes back complete on the
    # next request. Take the better verdict; open/closed beats unknown.
    if strict and verdict.status == "unknown":
        r_status, r_html, r_final = fetch(url)
        r_kind, r_payload = _classify_fetch(r_status, r_html, r_final, now)
        if r_kind == "closed":
            return _finalize("closed", None, "none", f"refetch:{r_payload}")
        if r_kind == "verdict":
            refetched: PageVerdict = _ignore_future_date(r_payload, now, url)  # type: ignore[arg-type]
            if refetched.status in ("open", "closed"):
                verdict = refetched
        # r_kind == "blocked" (or still-unknown refetch): keep original verdict.

    if verdict.status == "closed":
        return _finalize("closed", verdict.posted_at, "page" if verdict.posted_at else "none", verdict.evidence)

    # Page date wins over source date whenever present, even if it makes the
    # job look staler (or fresher) than the source claimed.
    if verdict.posted_at is not None:
        return _finalize("open" if verdict.status == "open" else "unknown", verdict.posted_at, "page", verdict.evidence)

    # No page date. Fall back to source date for trusted sources, or any
    # source when we at least got a page to confirm liveness.
    if source_posted_at is not None and (trust_source or verdict.status == "open"):
        return _finalize(
            "open" if verdict.status == "open" else "unknown",
            source_posted_at,
            "source",
            f"{verdict.evidence}+source_date",
        )

    return _finalize("unknown" if verdict.status != "open" else "open", None, "none", verdict.evidence)


def verify_job(
    job: NormalizedJob,
    now: datetime,
    fetch: _FetchFn = fetch_page,
    max_age_days: int = 7,
    strict: bool = True,
    browser_fetch: _FetchFn | None = None,
) -> VerificationRecord:
    from dataclasses import replace as _dc_replace

    record = verify_url(
        str(job.url),
        source_posted_at=job.posted_at,
        source=job.source,
        now=now,
        fetch=fetch,
        max_age_days=max_age_days,
        strict=strict,
        browser_fetch=browser_fetch,
    )
    record = _dc_replace(record, content_hash=job.content_hash)
    logger.info(
        "posting_verifier: %s decision=%s reason=%s status=%s age_days=%s url=%s",
        job.title, record.decision, record.reason, record.status, record.age_days, job.url,
    )
    return record


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------


def verify_jobs(
    jobs: list[NormalizedJob],
    *,
    max_age_days: int = 7,
    now: datetime | None = None,
    fetch: _FetchFn = fetch_page,
    concurrency: int = 8,
    enabled: bool = True,
    strict: bool = True,
    browser_fallback: bool = True,
    browser_fetch: _FetchFn | None = None,
) -> tuple[list[NormalizedJob], dict, dict[str, VerificationRecord]]:
    """Fan out verify_job() over `jobs` (pass 1, threaded) and partition kept
    vs dropped. Then, SERIALLY (pass 2 — a shared browser session is not
    thread-safe), retries every record left `unverifiable` or `unknown`:
    unverifiable records get one attempt through a headless-Chromium fetch
    (bypasses hosts like weworkremotely.com that block httpx), unknown
    records get one more plain re-fetch (LinkedIn's guest-page variant often
    resolves on a second request). A record is replaced only when pass 2 is
    more decisive than pass 1.

    Returns (kept, stats, records) where records maps content_hash ->
    VerificationRecord for every job that was checked.
    """
    from dataclasses import replace as _dc_replace

    if now is None:
        now = datetime.now(timezone.utc)
    elif now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)

    if not enabled:
        records = {
            job.content_hash: VerificationRecord(
                content_hash=job.content_hash,
                status="unknown",
                posted_at=job.posted_at,
                date_source="source" if job.posted_at else "none",
                age_days=None,
                checked_at=now,
                evidence="disabled",
                decision="keep",
                reason="disabled",
            )
            for job in jobs
        }
        return list(jobs), {"disabled": True}, records

    def _host(u: str) -> str:
        try:
            return urlsplit(u).netloc.lower()
        except Exception:  # noqa: BLE001 — defensive, url shape unknown
            return ""

    def _run_one(job: NormalizedJob) -> tuple[NormalizedJob, VerificationRecord]:
        try:
            return job, verify_job(job, now, fetch=fetch, max_age_days=max_age_days, strict=strict)
        except Exception as exc:  # noqa: BLE001 — one bad page must never kill the cron
            logger.warning("posting_verifier: verify_job crashed for %s (%s) — treating as unverifiable", job.url, exc)
            posted = job.posted_at
            age = (now - posted).total_seconds() / 86400.0 if posted is not None else None
            fresh = age is not None and age <= max_age_days
            return job, VerificationRecord(
                content_hash=job.content_hash, status="unverifiable", posted_at=posted,
                date_source="source" if posted is not None else "none", age_days=age,
                checked_at=now, evidence=f"error:{type(exc).__name__}",
                decision="keep" if fresh else "drop",
                reason="ok_unverified_fresh" if fresh else ("stale" if posted is not None else "unverifiable_no_date"),
            )

    # --- Pass 1: threaded, no browser fallback (a shared Chromium instance
    # is not thread-safe by design). ---
    results: list[tuple[NormalizedJob, VerificationRecord]] = []
    if not jobs:
        results = []
    elif concurrency <= 1:
        results = [_run_one(job) for job in jobs]
    else:
        with ThreadPoolExecutor(max_workers=concurrency) as pool:
            futures = [pool.submit(_run_one, job) for job in jobs]
            for fut in as_completed(futures):
                results.append(fut.result())

    results_by_hash: dict[str, tuple[NormalizedJob, VerificationRecord]] = {
        job.content_hash: (job, record) for job, record in results
    }

    # --- Pass 2: serial re-check of anything pass 1 could not confirm. ---
    pass2_attempted = 0
    pass2_recovered = 0
    used_browser = False

    candidates = [
        (job, record) for job, record in results
        if record.status in ("unverifiable", "unknown")
    ]

    run_pass2 = bool(candidates) and (browser_fetch is not None or browser_fallback)
    if run_pass2:
        owns_browser_cm = False
        resolved_browser_fetch = browser_fetch
        browser_cm = None
        if resolved_browser_fetch is None and browser_fallback:
            browser_cm = make_browser_fetcher()
            resolved_browser_fetch = browser_cm.__enter__()
            owns_browser_cm = True
        try:
            used_browser = resolved_browser_fetch is not None
            for job, old_record in candidates:
                if old_record.status == "unverifiable":
                    if resolved_browser_fetch is None:
                        continue  # no browser available — nothing more to try
                    pass2_fetch = resolved_browser_fetch
                else:  # "unknown" — plain variant re-fetch
                    pass2_fetch = fetch

                try:
                    new_record = verify_url(
                        str(job.url),
                        source_posted_at=job.posted_at,
                        source=job.source,
                        now=now,
                        fetch=pass2_fetch,
                        max_age_days=max_age_days,
                        strict=strict,
                        browser_fetch=None,
                    )
                except Exception as exc:  # noqa: BLE001 — pass 2 must never kill the batch
                    logger.warning(
                        "posting_verifier: pass2 verify_url crashed for %s (%s) — keeping pass1 record",
                        job.url, exc,
                    )
                    continue

                pass2_attempted += 1
                new_record = _dc_replace(new_record, content_hash=job.content_hash)
                if new_record.status != old_record.status:
                    if new_record.status in ("open", "closed"):
                        pass2_recovered += 1
                    results_by_hash[job.content_hash] = (job, new_record)
                    logger.info(
                        "posting_verifier: pass2 %s -> %s for %s (reason=%s)",
                        old_record.status, new_record.status, job.url, new_record.reason,
                    )
                elif new_record.reason != old_record.reason or new_record.decision != old_record.decision:
                    results_by_hash[job.content_hash] = (job, new_record)
        finally:
            if owns_browser_cm:
                browser_cm.__exit__(None, None, None)

    # --- Final partition / stats over the merged pass1+pass2 records. ---
    kept: list[NormalizedJob] = []
    by_reason: dict[str, int] = {}
    by_status: dict[str, int] = {}
    rejected_sample: list[dict] = []
    records: dict[str, VerificationRecord] = {}
    host_attempts: dict[str, int] = {}
    host_unverifiable: dict[str, int] = {}
    _REJECT_SAMPLE_CAP = 300

    for job, record in results_by_hash.values():
        host = _host(str(job.url))
        host_attempts[host] = host_attempts.get(host, 0) + 1
        if record.status == "unverifiable":
            host_unverifiable[host] = host_unverifiable.get(host, 0) + 1

        records[job.content_hash] = record
        by_status[record.status] = by_status.get(record.status, 0) + 1
        by_reason[record.reason] = by_reason.get(record.reason, 0) + 1

        if record.decision == "keep":
            kept.append(job)
        else:
            logger.info(
                "posting_verifier: DROP '%s' at %s reason=%s evidence=%s",
                job.title, job.url, record.reason, record.evidence,
            )
            if len(rejected_sample) < _REJECT_SAMPLE_CAP:
                rejected_sample.append({
                    "title": (job.title or "")[:120],
                    "company": (job.company or "")[:120],
                    "url": str(job.url),
                    "reason": record.reason,
                    "evidence": record.evidence,
                    "status": record.status,
                })

    unverifiable_ratio_by_host = {
        host: host_unverifiable.get(host, 0) / attempts
        for host, attempts in host_attempts.items()
        if attempts > 0
    }

    warnings: list[str] = []
    for host, attempts in host_attempts.items():
        if attempts >= 5:
            ratio = unverifiable_ratio_by_host.get(host, 0.0)
            if ratio >= 0.8:
                warnings.append(
                    f"host {host} blocked {host_unverifiable.get(host, 0)}/{attempts} — "
                    "liveness unverifiable; source-date fallback used"
                )

    stats = {
        "total_in": len(jobs),
        "kept": len(kept),
        "rejected": len(jobs) - len(kept),
        "by_reason": by_reason,
        "by_status": by_status,
        "rejected_sample": rejected_sample,
        "unverifiable_ratio_by_host": unverifiable_ratio_by_host,
        "warnings": warnings,
        "pass2_attempted": pass2_attempted,
        "pass2_recovered": pass2_recovered,
        "browser_used": used_browser,
        "strict": strict,
    }
    logger.info(
        "posting_verifier: total_in=%s kept=%s rejected=%s pass2_attempted=%s pass2_recovered=%s",
        stats["total_in"], stats["kept"], stats["rejected"], pass2_attempted, pass2_recovered,
    )
    return kept, stats, records


def records_to_jsonl(records: dict[str, VerificationRecord]) -> str:
    """Serialize records to newline-delimited JSON for persisting to the run dir."""
    lines = []
    for record in records.values():
        payload = {
            "content_hash": record.content_hash,
            "status": record.status,
            "posted_at": record.posted_at.isoformat() if record.posted_at else None,
            "date_source": record.date_source,
            "age_days": record.age_days,
            "checked_at": record.checked_at.isoformat(),
            "evidence": record.evidence,
            "decision": record.decision,
            "reason": record.reason,
        }
        lines.append(json.dumps(payload, ensure_ascii=False))
    return "\n".join(lines)
