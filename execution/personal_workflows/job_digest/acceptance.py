"""
description: Generic acceptance gate for job_digest — a final sanity check run
    just before sending, independent of the ranker's own tiering AND of
    normalizer/filters.py's implementation. This is deliberate: filters.py is a
    profile-driven filter (owned by another agent) and a bug there could pass
    its own tautological re-check trivially. acceptance.check() re-derives its
    verdicts from profile + registry data using its own tokenization and its
    own alias-matching, so a shared bug in filters.py's regex/substring logic
    does not also hide from this gate.
inputs: digest: list[tuple[NormalizedJob, RankedJob]] (the rows about to be
    emailed/sheeted), profile_schema.Profile
outputs: (passed: bool, problems: list[str]) — problems is empty when passed.

Rules (from directives/personal_workflows/job_digest.md), each INDEPENDENTLY
re-implemented here (no imports from normalizer/filters.py or ranker/heuristic.py):
    (a) >= 80% of digest rows must have >=1 role keyword whose every token
        appears in the title's token set (token-set overlap, not substring).
    (b) >= 80% of digest rows must match a selected country (via registry
        Country.aliases + location_regex, checked with plain `in`-on-token-list
        matching) or be remote when the profile allows remote.
    (c) every row must have a non-empty company AND a URL whose host is non-empty.
    (d) if >= 50% of rows carry posted_at, then >= 80% of THOSE must be within
        the last 45 days (skipped entirely when fewer than 50% carry a date —
        not enough signal to judge staleness).
    (e) zero rows may contain an excluded title substring.
    An empty digest is a PASS (nothing to object to), with an informational note.
"""

from __future__ import annotations

import logging
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

from .contracts import NormalizedJob, RankedJob, RemoteMode
from .profile_schema import Profile

logger = logging.getLogger("job_digest.acceptance")

_TITLE_MATCH_THRESHOLD = 0.80
_LOCATION_MATCH_THRESHOLD = 0.80
_POSTED_AT_COVERAGE_THRESHOLD = 0.50
_POSTED_AT_FRESH_THRESHOLD = 0.80
_POSTED_AT_MAX_AGE_DAYS = 45

_TOKEN_RE = re.compile(r"[a-z0-9]+")


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def _tokens(s: str) -> list[str]:
    """Own tokenizer: fold accents, lowercase, split on non-alphanumerics."""
    return _TOKEN_RE.findall(_fold(s))


def _title_matches_keyword(title: str, keywords: list[str]) -> bool:
    """A row passes if >=1 keyword whose tokens ALL appear in the title's
    token set — e.g. keyword "Sales Manager" requires both "sales" and
    "manager" to be present in the title, in any order, as whole tokens.
    """
    title_tokens = set(_tokens(title))
    if not title_tokens:
        return False
    for kw in keywords:
        kw_tokens = _tokens(kw)
        if kw_tokens and all(t in title_tokens for t in kw_tokens):
            return True
    return False


def _matches_country_or_remote(job: NormalizedJob, profile: Profile) -> bool:
    loc = (job.location or "").strip()
    if not loc or loc.lower() == "unknown":
        return True  # unknown location is not evidence of a WRONG country
    if job.remote_mode == RemoteMode.REMOTE and profile.locations.remote_ok:
        return True

    haystack_tokens = _tokens(f"{loc} {job.description_snippet[:300]}")
    padded = " " + " ".join(haystack_tokens) + " "

    for country in profile.countries:
        for alias in country.aliases:
            alias_tokens = _tokens(alias)
            if alias_tokens and (" " + " ".join(alias_tokens) + " ") in padded:
                return True
        if country.location_regex is not None and country.location_regex.search(loc):
            return True
    return False


def _has_excluded_title(title: str, exclude_titles: list[str]) -> bool:
    folded_title = _fold(title)
    return any(_fold(sub) in folded_title for sub in exclude_titles if sub)


def _has_company_and_host(job: NormalizedJob) -> bool:
    if not (job.company and job.company.strip()):
        return False
    host = urlsplit(str(job.url)).netloc
    return bool(host)


def _aware_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _posted_at_problem(digest: list[tuple[NormalizedJob, RankedJob]]) -> str | None:
    total = len(digest)
    dated = [job for job, _ in digest if job.posted_at is not None]
    if not dated or (len(dated) / total) < _POSTED_AT_COVERAGE_THRESHOLD:
        return None  # not enough dated rows to judge staleness

    cutoff = datetime.now(timezone.utc) - timedelta(days=_POSTED_AT_MAX_AGE_DAYS)
    fresh = sum(1 for job in dated if _aware_utc(job.posted_at) >= cutoff)
    ratio = fresh / len(dated)
    if ratio < _POSTED_AT_FRESH_THRESHOLD:
        return (
            f"only {fresh}/{len(dated)} ({ratio:.0%}) dated digest rows are within "
            f"{_POSTED_AT_MAX_AGE_DAYS} days — below the {_POSTED_AT_FRESH_THRESHOLD:.0%} threshold"
        )
    return None


def check(digest: list[tuple[NormalizedJob, RankedJob]], profile: Profile) -> tuple[bool, list[str]]:
    """Run the acceptance gate over the final digest rows."""
    if not digest:
        logger.info("acceptance: empty digest — PASS (nothing to send)")
        return True, []

    problems: list[str] = []
    keywords = profile.keywords
    exclude_titles = profile.exclude.title_substrings

    total = len(digest)
    title_hits = 0
    location_hits = 0
    excluded_rows: list[str] = []
    missing_company_or_host: list[str] = []

    for job, _ranked in digest:
        if _title_matches_keyword(job.title, keywords):
            title_hits += 1
        if _matches_country_or_remote(job, profile):
            location_hits += 1
        if _has_excluded_title(job.title, exclude_titles):
            excluded_rows.append(job.title)
        if not _has_company_and_host(job):
            missing_company_or_host.append(job.title or job.content_hash[:12])

    title_ratio = title_hits / total
    location_ratio = location_hits / total

    if title_ratio < _TITLE_MATCH_THRESHOLD:
        problems.append(
            f"only {title_hits}/{total} ({title_ratio:.0%}) digest rows title-match a role "
            f"keyword — below the {_TITLE_MATCH_THRESHOLD:.0%} threshold"
        )
    if location_ratio < _LOCATION_MATCH_THRESHOLD:
        problems.append(
            f"only {location_hits}/{total} ({location_ratio:.0%}) digest rows match a selected "
            f"country or remote — below the {_LOCATION_MATCH_THRESHOLD:.0%} threshold"
        )
    if excluded_rows:
        problems.append(
            f"{len(excluded_rows)} digest row(s) contain an excluded title substring: "
            + "; ".join(excluded_rows[:5])
        )
    if missing_company_or_host:
        problems.append(
            f"{len(missing_company_or_host)} digest row(s) missing company or a URL host: "
            + "; ".join(missing_company_or_host[:5])
        )
    stale_problem = _posted_at_problem(digest)
    if stale_problem:
        problems.append(stale_problem)

    passed = not problems
    if passed:
        logger.info("acceptance: PASS (%d rows, title=%.0f%%, location=%.0f%%)", total, title_ratio * 100, location_ratio * 100)
    else:
        logger.warning("acceptance: FAIL — %s", problems)
    return passed, problems
