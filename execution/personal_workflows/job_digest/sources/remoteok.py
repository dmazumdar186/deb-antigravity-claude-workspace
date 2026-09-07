"""
description: RemoteOK source adapter for job_digest. Hits the public unauthenticated
    JSON feed at remoteok.com/api and maps relevant rows to SourceJob. Ported from
    the operator's internal job pipeline, generalized off profile.keywords instead of a hardcoded
    PM-only title list.
inputs:
  - profile: Profile — profile.keywords are matched against each job's title/tags
  - country: registry.Country | None — ignored; RemoteOK is a global remote feed
  - dry: bool — when True, returns SourceJob rows from fixtures/remoteok.jsonl,
    no network
outputs:
  - list[SourceJob]

Endpoint: GET https://remoteok.com/api (no auth, no documented rate limit).
"""

from __future__ import annotations

import json
import logging
import re as _re
from datetime import datetime, timezone
from pathlib import Path

import httpx

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.remoteok")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

API_URL = "https://remoteok.com/api"

HEADERS = {
    "User-Agent": "job-digest/0.1 (+https://github.com/)",
    "Accept": "application/json",
}

MAX_JOBS = 200


class RemoteOKBlockedError(RuntimeError):
    """Raised when RemoteOK serves a non-JSON response (Cloudflare challenge etc.)."""


def _is_relevant(job: dict, keywords_lower: list[str]) -> bool:
    title_low = (job.get("position", "") or "").lower()
    if any(kw in title_low for kw in keywords_lower):
        return True
    tags = {str(t).lower() for t in (job.get("tags") or [])}
    keyword_tokens = {tok for kw in keywords_lower for tok in kw.split()}
    return bool(tags & keyword_tokens)


def _to_source_job(job: dict) -> SourceJob | None:
    job_id = str(job.get("id") or job.get("slug") or "").strip()
    if not job_id:
        return None
    title = (job.get("position") or "").strip()
    company = (job.get("company") or "Unknown").strip()
    if not title:
        return None

    posted_at = None
    raw_date = job.get("date") or job.get("epoch") or ""
    if isinstance(raw_date, (int, float)):
        try:
            posted_at = datetime.fromtimestamp(float(raw_date), tz=timezone.utc)
        except (ValueError, OSError):
            posted_at = None
    elif isinstance(raw_date, str) and raw_date:
        try:
            posted_at = datetime.fromisoformat(raw_date.replace("Z", "+00:00"))
            if posted_at.tzinfo is None:
                posted_at = posted_at.replace(tzinfo=timezone.utc)
        except ValueError:
            posted_at = None

    url = (job.get("url") or job.get("apply_url") or "").strip()
    if not url:
        slug = job.get("slug") or job_id
        url = f"https://remoteok.com/remote-jobs/{slug}"

    location_raw = (job.get("location") or "Remote").strip()
    description = job.get("description") or ""
    if "<" in description:
        description = _re.sub(r"<[^>]+>", " ", description)
    description = description.strip()[:1500]

    contract_raw = ""
    job_type = (job.get("job_type") or "").lower()
    if "contract" in job_type or "freelance" in job_type:
        contract_raw = "Freelance"
    elif "full" in job_type or "permanent" in job_type:
        contract_raw = "Permanent"

    try:
        return SourceJob(
            source=JobSource.REMOTEOK,
            source_id=job_id,
            url=url,
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=contract_raw,
        )
    except ValueError as exc:
        logger.warning("remoteok: skip job %s (validation): %s", job_id, exc)
        return None


def _filter_and_map(jobs_raw: list[dict], keywords_lower: list[str], max_jobs: int) -> list[SourceJob]:
    out: list[SourceJob] = []
    for j in jobs_raw:
        if not _is_relevant(j, keywords_lower):
            continue
        sj = _to_source_job(j)
        if sj is not None:
            out.append(sj)
            if len(out) >= max_jobs:
                break
    return out


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Fetch the RemoteOK feed and keep rows matching any of profile.keywords."""
    if dry:
        return _load_fixture(profile)
    keywords_lower = [k.lower() for k in profile.keywords]
    try:
        with httpx.Client(headers=HEADERS, timeout=30.0) as client:
            resp = client.get(API_URL)
    except httpx.HTTPError as exc:
        logger.error("remoteok: HTTP error: %s", exc)
        return []

    if resp.status_code != 200:
        logger.error("remoteok: status %d, first 200 bytes: %r", resp.status_code, resp.text[:200])
        return []

    try:
        data = resp.json()
    except (ValueError, json.JSONDecodeError) as exc:
        if "<html" in resp.text[:500].lower():
            raise RemoteOKBlockedError("RemoteOK returned HTML instead of JSON (Cloudflare challenge?)") from exc
        logger.error("remoteok: JSON parse failed: %s", exc)
        return []

    if not isinstance(data, list) or len(data) < 2:
        logger.warning("remoteok: unexpected feed shape, got %s entries", len(data) if isinstance(data, list) else "non-list")
        return []

    out = _filter_and_map(data[1:], keywords_lower, MAX_JOBS)
    logger.info("remoteok: %d total in feed, %d mapped (cap=%d)", len(data) - 1, len(out), MAX_JOBS)
    return out


def _load_fixture(profile: Profile) -> list[SourceJob]:
    path = _FIXTURES_DIR / "remoteok.jsonl"
    if not path.exists():
        logger.warning("remoteok: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
