"""
description: RemoteOK source adapter. Hits the public unauthenticated JSON
    feed at remoteok.com/api. Returns ~500 active remote jobs across all
    categories; we filter to PM / AI / automation / product / engineering and
    map each to a SourceJob. No auth, no rate limit.
inputs:
  - CLI: --max-jobs (cap, default 200), --fixture
  - env: none
outputs:
  - stdout: JSON-lines of SourceJob records
  - .tmp/job_search_v2/remoteok_<uuid>.jsonl when run standalone

Endpoint: GET https://remoteok.com/api
Anti-bot posture: send a User-Agent identifying us (remoteok requests this).
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import httpx
from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import JobSource, SourceJob  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("remoteok")

PROJECT_ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = PROJECT_ROOT / ".tmp" / "job_search_v2"

API_URL = "https://remoteok.com/api"

HEADERS = {
    "User-Agent": "job_search_v2 aggregator (https://github.com/dmazumdar186/deb-antigravity-claude-workspace; contact debanjan186@gmail.com)",
    "Accept": "application/json",
}

# Tag/keyword matchers — RemoteOK uses lowercase single-word tags. Match against
# both `tags` (array) and `position` (title) so a job tagged just "engineer"
# whose title says "AI Engineer" still gets through.
RELEVANT_TAGS = {
    "product", "product manager", "pm", "product owner",
    "ai", "artificial intelligence", "ml", "machine learning",
    "llm", "genai", "generative ai",
    "automation", "rpa", "process automation",
    "consultant", "consulting",
    "engineer", "engineering",  # broad — many AI engineer roles tagged just "engineer"
}

RELEVANT_TITLE_SUBSTRS = (
    "product manager", "product owner", "head of product",
    "ai engineer", "ml engineer", "machine learning",
    "ai automation", "automation engineer", "rpa",
    "ai consultant", "ai strategy", "ai transformation",
    "ai mobile", "mobile ai",
    "ai process",
    "ai product",
)


class RemoteOKBlockedError(RuntimeError):
    """Raised when RemoteOK serves a non-JSON response (Cloudflare challenge etc.)."""


def _is_relevant(job: dict) -> bool:
    title_low = (job.get("position", "") or "").lower()
    if any(s in title_low for s in RELEVANT_TITLE_SUBSTRS):
        return True
    tags = {str(t).lower() for t in (job.get("tags") or [])}
    if tags & RELEVANT_TAGS:
        return True
    return False


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

    # Construct a URL: prefer `url`/`apply_url`, fallback to remoteok canonical.
    url = (job.get("url") or job.get("apply_url") or "").strip()
    if not url:
        slug = job.get("slug") or job_id
        url = f"https://remoteok.com/remote-jobs/{slug}"

    location_raw = (job.get("location") or "Remote").strip()
    description = (job.get("description") or "")
    # RemoteOK descriptions can be HTML; rough strip + truncate.
    if "<" in description:
        import re as _re
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


def fetch(max_jobs: int = 200) -> list[SourceJob]:
    """Pull the RemoteOK feed, filter to PM/AI/automation, map to SourceJob."""
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
            raise RemoteOKBlockedError(
                "RemoteOK returned HTML instead of JSON (Cloudflare challenge?)"
            ) from exc
        logger.error("remoteok: JSON parse failed: %s", exc)
        return []

    # First element is feed metadata; skip it.
    if not isinstance(data, list) or len(data) < 2:
        logger.warning("remoteok: unexpected feed shape, got %s entries", len(data) if isinstance(data, list) else "non-list")
        return []
    jobs_raw = data[1:]

    out: list[SourceJob] = []
    relevant_count = 0
    for j in jobs_raw:
        if not _is_relevant(j):
            continue
        relevant_count += 1
        sj = _to_source_job(j)
        if sj is not None:
            out.append(sj)
            if len(out) >= max_jobs:
                break
    logger.info("remoteok: %d total in feed, %d relevant, %d mapped (cap=%d)",
                len(jobs_raw), relevant_count, len(out), max_jobs)
    return out


def fetch_from_fixture(fixture_path: Path, max_jobs: int = 200) -> list[SourceJob]:
    if not fixture_path.exists():
        return []
    data = json.loads(fixture_path.read_text(encoding="utf-8"))
    if not isinstance(data, list) or len(data) < 2:
        return []
    out: list[SourceJob] = []
    for j in data[1:]:
        if not _is_relevant(j):
            continue
        sj = _to_source_job(j)
        if sj is not None:
            out.append(sj)
            if len(out) >= max_jobs:
                break
    return out


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="RemoteOK source adapter.")
    parser.add_argument("--max-jobs", type=int, default=200)
    parser.add_argument("--fixture", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    if args.fixture:
        jobs = fetch_from_fixture(args.fixture, max_jobs=args.max_jobs)
    else:
        try:
            jobs = fetch(max_jobs=args.max_jobs)
        except RemoteOKBlockedError as exc:
            logger.error("remoteok: aborted - %s", exc)
            return 1

    out_path = args.out or (TMP_DIR / f"remoteok_{uuid.uuid4().hex[:8]}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        for job in jobs:
            line = job.model_dump_json()
            f.write(line + "\n")
            try:
                sys.stdout.write(line + "\n")
            except UnicodeEncodeError:
                sys.stdout.buffer.write((line + "\n").encode("utf-8", errors="replace"))
    logger.info("remoteok: wrote %d to %s", len(jobs), out_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
