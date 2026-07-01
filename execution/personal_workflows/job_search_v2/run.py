"""
description: Orchestrator for job_search_v2. Calls the 4 sources in parallel, normalizes,
    runs persistent cross-day dedup, writes the v2_jobs sheet tab, and sends the daily digest.
    This is what the GitHub Actions cron should invoke once v1 is retired.
inputs:
    - CLI flags:
        --mode {live, fixture}   : live = hit real APIs (default); fixture = use tests/fixtures/
        --dry-run                : skip sheet append + email send (still writes JSONL + run log)
        --sources                : comma-separated subset of {france_travail,wttj,apec,linkedin_gmail}
        --max-pages              : passed to each source
        --posted-within-days     : passed to france_travail
    - env (live mode): FRANCE_TRAVAIL_CLIENT_ID/SECRET, GMAIL_TOKEN_PATH (linkedin_gmail),
                       SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH,
                       GMAIL_SMTP_USER/APP_PASSWORD/NOTIFY_TO
outputs:
    - .tmp/job_search_v2/runs/run_<utc-id>/{france_travail,wttj,apec,linkedin_gmail}.jsonl
    - .tmp/job_search_v2/runs/run_<utc-id>/normalized.jsonl
    - .tmp/job_search_v2/runs/run_<utc-id>/summary.json
    - Append-row API call to Google Sheets v2_jobs tab (unless --dry-run)
    - Email digest via SMTP (unless --dry-run)
    - .tmp/job_search_v2/run_log.jsonl appended with one summary line per run

Fault isolation: each source runs inside its own try/except. A source failing yields []
for that source; the pipeline still ships with what survives.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve()
_WORKSPACE = _HERE.parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    JobSource,
    SourceJob,
)
from execution.personal_workflows.job_search_v2.normalizer.dedup import (  # noqa: E402
    DEFAULT_DB_PATH,
    filter_new,
    get_meta,
    set_meta,
)
from execution.personal_workflows.job_search_v2.normalizer.contract_filter import (  # noqa: E402
    filter_by_contract,
)
from execution.personal_workflows.job_search_v2.normalizer.language_filter import (  # noqa: E402
    filter_by_language,
)
from execution.personal_workflows.job_search_v2.normalizer.location_filter import (  # noqa: E402
    filter_by_location,
    load_config,
)
from execution.personal_workflows.job_search_v2.normalizer.normalize import (  # noqa: E402
    batch_normalize,
)
from execution.personal_workflows.job_search_v2.normalizer.title_filter import (  # noqa: E402
    filter_by_title,
)
from execution.personal_workflows.job_search_v2.notifier import email as email_notifier  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_notifier  # noqa: E402
from execution.personal_workflows.job_search_v2.ranker import score as ranker  # noqa: E402
from execution.personal_workflows.job_search_v2.ranker import sonnet_rerank  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("run")

PROJECT_ROOT = _WORKSPACE
TMP_RUNS = PROJECT_ROOT / ".tmp" / "job_search_v2" / "runs"
RUN_LOG = PROJECT_ROOT / ".tmp" / "job_search_v2" / "run_log.jsonl"

# Email-lock state lives inside seen.db's meta KV table, NOT a separate file.
# This is the autonomous-deploy workaround for the workflow YAML being unable to
# add new cache paths (PAT lacks `workflow` scope). seen.db is already cached by
# the existing GH Actions cache step, so the lock state piggy-backs on it for free.
EMAIL_LOCK_KEY = "last_email_sent_utc"

# File-based fallback lock — survives even when seen.db is wiped because the
# GH Actions cache key for seen.db has been broken on origin/main (cache-key
# fix `7cae20a` is local-only pending workflow PAT scope). The Summary tab
# Gmail-side state OR the Google Sheets-side meta cell would be more robust
# still, but the simplest available durable surface that survives a cron
# invocation is the Google Sheet itself — see _gsheet_email_lock_get / _set
# below for that path. The local file is used in dev mode + as a belt-and-
# suspenders inside one process.
EMAIL_LOCK_FILE = PROJECT_ROOT / ".tmp" / "job_search_v2" / "last_email_sent_utc.txt"

# Google Sheets meta cell — Summary tab, cell `D1`. Persists across cron runs
# regardless of seen.db cache state. Empty if never written.
GSHEET_EMAIL_LOCK_CELL = "D1"


def _gsheet_email_lock_get() -> str | None:
    """Read the email-lock timestamp from the Summary tab's D1 cell. Returns
    None on any failure (creds missing / sheet unreachable / cell empty)."""
    try:
        from execution.personal_workflows.job_search_v2.notifier.sheet import _open_sheet
    except ImportError:
        return None
    try:
        sp, err = _open_sheet(None, None)
        if sp is None:
            return None
        ws = sp.worksheet("Summary")
        # FORMULA bypasses Sheets' display formatter, so a previously-USER_ENTERED
        # write that got coerced to a date is still readable as text. New writes go
        # in as RAW (see _gsheet_email_lock_set) so this matters mainly for the
        # transition cron after the TZ-bug fix.
        val = ws.acell(GSHEET_EMAIL_LOCK_CELL, value_render_option="FORMULA").value
        return str(val).strip() if val else None
    except Exception as exc:  # noqa: BLE001 — best-effort read
        logger.warning("email_lock: gsheet read failed: %s", exc)
        return None


def _gsheet_email_lock_set(now_iso: str) -> None:
    try:
        from execution.personal_workflows.job_search_v2.notifier.sheet import _open_sheet
    except ImportError:
        return
    try:
        sp, err = _open_sheet(None, None)
        if sp is None:
            return
        ws = sp.worksheet("Summary")
        # RAW (not USER_ENTERED) so Sheets stores the literal ISO string. USER_ENTERED
        # made Sheets parse the timestamp through the operator's locale (Europe/Paris),
        # dropping the UTC offset and replaying ~2-4h earlier on read-back — which made
        # next-day same-time runs trip the 22h floor and skip the digest. See incident
        # 2026-06-25: dual cron at 10:13+10:36 UTC both reported "19.8h ago" anchored
        # on yesterday's 10:44 UTC send rendered through Paris locale.
        ws.update(range_name=GSHEET_EMAIL_LOCK_CELL, values=[[now_iso]], value_input_option="RAW")
    except Exception as exc:  # noqa: BLE001 — best-effort write
        logger.warning("email_lock: gsheet write failed: %s", exc)


def _read_prior_iso(db_path: Path = DEFAULT_DB_PATH) -> tuple[str | None, str]:
    """Read the prior-email-sent timestamp from the most authoritative source
    that's available. Returns (prior_iso, source_label).

    Order: Google Sheets meta-cell → seen.db meta KV → local file.
    The Sheets cell is the only one that survives a cache-key-broken cron, so
    it wins ties. Sources that aren't available are silently skipped.
    """
    prior = _gsheet_email_lock_get()
    if prior:
        return prior, "gsheet:Summary!D1"

    try:
        prior = get_meta(db_path, EMAIL_LOCK_KEY)
    except Exception as exc:  # noqa: BLE001 — seen.db absent / corrupt
        logger.warning("email_lock: seen.db meta read failed: %s", exc)
        prior = None
    if prior:
        return prior, "seen.db:meta"

    try:
        if EMAIL_LOCK_FILE.exists():
            prior = EMAIL_LOCK_FILE.read_text(encoding="utf-8").strip()
            if prior:
                return prior, str(EMAIL_LOCK_FILE)
    except OSError as exc:
        logger.warning("email_lock: file read failed: %s", exc)
    return None, "none"


def _email_lock_blocks_send(
    min_hours_between_emails: float,
    now_utc: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[bool, str]:
    """Check whether the email lock should block this send.

    Returns (blocked, reason). Blocked=True if the last send was less than
    min_hours_between_emails ago. State lives in (priority order): Google
    Sheets Summary!D1 → seen.db meta KV → local file. The gsheet path
    survives even when the CI cache key for seen.db is broken.
    """
    if min_hours_between_emails <= 0:
        return False, "email_lock disabled (min_hours_between_emails <= 0)"
    prior_iso, source = _read_prior_iso(db_path)
    if not prior_iso:
        return False, "no prior send recorded across any source"
    try:
        prior = datetime.fromisoformat(prior_iso.replace("Z", "+00:00"))
    except ValueError as exc:
        return False, f"state value unreadable from {source} ({exc}); treating as no prior send"
    if prior.tzinfo is None:
        prior = prior.replace(tzinfo=timezone.utc)
    delta_hours = (now_utc - prior).total_seconds() / 3600.0
    if delta_hours < min_hours_between_emails:
        return True, (
            f"email lock [{source}]: last send was {delta_hours:.1f}h ago "
            f"(< {min_hours_between_emails:.1f}h floor) — skipping to prevent dual-cron spam"
        )
    return False, f"email lock cleared [{source}]: last send was {delta_hours:.1f}h ago"


def _stamp_email_sent(now_utc: datetime, db_path: Path = DEFAULT_DB_PATH) -> None:
    """Stamp ALL three persistence layers so any of them can answer the next
    check. Defense in depth: if Sheets is unreachable today, file and seen.db
    still record the send; if CI wipes seen.db, the Sheets cell still wins."""
    iso = now_utc.isoformat()
    try:
        set_meta(db_path, EMAIL_LOCK_KEY, iso)
    except Exception as exc:  # noqa: BLE001 — seen.db absent
        logger.warning("email_lock: seen.db meta write failed: %s", exc)
    try:
        EMAIL_LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
        EMAIL_LOCK_FILE.write_text(iso, encoding="utf-8")
    except OSError as exc:
        logger.warning("email_lock: file write failed: %s", exc)
    _gsheet_email_lock_set(iso)


# ----- source dispatch -----


def _fetch_france_travail(mode: str, max_pages: int, posted_within_days: int = 1) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import france_travail as ft
    if mode == "fixture":
        return ft.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "france_travail_sample.json")
    try:
        return ft.fetch(max_pages=max_pages, posted_within_days=posted_within_days)
    except ft.FranceTravailAuthError as exc:
        logger.warning("run: france_travail auth failure — %s. Skipping source.", exc)
        return []


def _fetch_wttj(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import wttj
    if mode == "fixture":
        return wttj.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "wttj_sample.html")
    return wttj.fetch(max_pages=max_pages)


def _fetch_apec(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import apec
    if mode == "fixture":
        return apec.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "apec_sample.html")
    return apec.fetch(max_pages=max_pages)


def _fetch_linkedin_gmail(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import linkedin_gmail
    if mode == "fixture":
        return linkedin_gmail.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "linkedin_email_sample.html")
    return linkedin_gmail.fetch()


def _fetch_indeed_gmail(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import indeed_gmail
    if mode == "fixture":
        return indeed_gmail.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "indeed_email_sample.html")
    try:
        return indeed_gmail.fetch()
    except indeed_gmail.IndeedGmailAuthError as exc:
        logger.warning("run: indeed_gmail auth failure — %s. Skipping source.", exc)
        return []


def _fetch_hellowork_gmail(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import hellowork_gmail
    if mode == "fixture":
        return hellowork_gmail.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "hellowork_email_sample.html")
    try:
        return hellowork_gmail.fetch()
    except hellowork_gmail.HelloworkGmailAuthError as exc:
        logger.warning("run: hellowork_gmail auth failure — %s. Skipping source.", exc)
        return []


def _fetch_jobgether_gmail(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import jobgether_gmail
    if mode == "fixture":
        return jobgether_gmail.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "jobgether_email_sample.html")
    try:
        return jobgether_gmail.fetch()
    except jobgether_gmail.JobgetherGmailAuthError as exc:
        logger.warning("run: jobgether_gmail auth failure — %s. Skipping source.", exc)
        return []


# LinkedIn geoIds for the 4 target countries (verified stable on linkedin.com/jobs).
# Île-de-France is preferred over France-wide so Paris-area jobs aren't drowned out.
LINKEDIN_GEO_IDS = {
    "FR_idf": "104246759",   # Île-de-France region (Paris)
    "DE":     "101282230",   # Germany
    "BE":     "100565514",   # Belgium
    "CH":     "106693272",   # Switzerland
}


def _fetch_linkedin_guest_api(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import linkedin_guest_api as lga
    if mode == "fixture":
        return lga.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "linkedin_guest_api_sample.html")

    # Fan out across all 4 country geoIds. Each call is rate-limited internally
    # (~1-2s per page) so 4 countries x ~9 keywords stays well below LinkedIn's
    # block threshold. Cross-region dedup happens in the normalizer.
    all_jobs: list[SourceJob] = []
    for label, geo_id in LINKEDIN_GEO_IDS.items():
        try:
            jobs = lga.fetch(
                geo_id=geo_id,
                max_pages_per_keyword=max_pages,
                posted_within_hours=48,
            )
            logger.info("run: linkedin_guest_api[%s geoId=%s] -> %d jobs", label, geo_id, len(jobs))
            all_jobs.extend(jobs)
        except lga.LinkedInBlockedError as exc:
            logger.warning("run: linkedin_guest_api[%s] blocked - %s. Continuing with other regions.", label, exc)
            # Don't return early — a block on DE doesn't mean FR is blocked too.
            continue
    return all_jobs


# WTTJ country codes. WTTJ has FR + BE + CH presence; DE is sparse but the
# Algolia index supports it (returns ~0 most days, costs ~0 to ask).
WTTJ_COUNTRY_CODES = ["FR", "BE", "CH", "DE"]


def _fetch_wttj_algolia(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import wttj_algolia
    if mode == "fixture":
        return wttj_algolia.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "wttj_algolia_sample.json")

    all_jobs: list[SourceJob] = []
    for cc in WTTJ_COUNTRY_CODES:
        try:
            jobs = wttj_algolia.fetch(country_code=cc, max_pages=max_pages, posted_within_hours=48)
            logger.info("run: wttj_algolia[%s] -> %d jobs", cc, len(jobs))
            all_jobs.extend(jobs)
        except wttj_algolia.WttjAlgoliaBlockedError as exc:
            logger.warning("run: wttj_algolia[%s] blocked - %s. Continuing.", cc, exc)
            continue
    return all_jobs


def _fetch_hellowork(mode: str, max_pages: int) -> list[SourceJob]:
    """Hellowork public web scrape (search → JobPosting JSON-LD).

    Every offer page reliably carries a schema.org JobPosting blob with the
    full description (verified 24/24 in 2026-06-30 smoke), giving us the
    third source whose rows reach the ranker with non-empty
    description_snippet. The hellowork_gmail flow above is the older
    alert-based source; this one is direct web.
    """
    from execution.personal_workflows.job_search_v2.sources import hellowork
    if mode == "fixture":
        return hellowork.fetch_from_fixture(
            PROJECT_ROOT / "tests" / "fixtures" / "hellowork_sample.html"
        )
    try:
        return hellowork.fetch(max_pages_per_keyword=max_pages, posted_within_hours=48)
    except hellowork.HelloworkBlockedError as exc:
        logger.warning("run: hellowork blocked - %s. Skipping source.", exc)
        return []


def _fetch_remoteok(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import remoteok
    if mode == "fixture":
        return remoteok.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "remoteok_sample.json")
    try:
        return remoteok.fetch(max_jobs=200)
    except remoteok.RemoteOKBlockedError as exc:
        logger.warning("run: remoteok blocked - %s. Skipping source.", exc)
        return []


def _fetch_weworkremotely(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import weworkremotely
    if mode == "fixture":
        return weworkremotely.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "weworkremotely_sample.xml")
    return weworkremotely.fetch(max_jobs=200)


_DISPATCH = {
    JobSource.FRANCE_TRAVAIL.value: _fetch_france_travail,
    JobSource.WTTJ.value: _fetch_wttj,
    JobSource.WTTJ_ALGOLIA.value: _fetch_wttj_algolia,
    JobSource.APEC.value: _fetch_apec,
    JobSource.LINKEDIN_GMAIL.value: _fetch_linkedin_gmail,
    JobSource.LINKEDIN_GUEST_API.value: _fetch_linkedin_guest_api,
    JobSource.INDEED_GMAIL.value: _fetch_indeed_gmail,
    JobSource.HELLOWORK_GMAIL.value: _fetch_hellowork_gmail,
    JobSource.HELLOWORK.value: _fetch_hellowork,
    JobSource.JOBGETHER_GMAIL.value: _fetch_jobgether_gmail,
    JobSource.REMOTEOK.value: _fetch_remoteok,
    JobSource.WEWORKREMOTELY.value: _fetch_weworkremotely,
}


def _call_source(name: str, mode: str, max_pages: int, posted_within_days: int) -> list[SourceJob]:
    """Wrapper so each source's failure can't kill the pipeline.

    Dispatches via _DISPATCH using a unified (mode, max_pages) signature. The one
    function that needs posted_within_days (france_travail) is bound via partial
    at dispatch-table construction time, not via a hand-rolled if-branch — the
    earlier if-branch caused the 2026-06-18 silent-zero-jobs regression.
    """
    try:
        fn = _build_dispatch(posted_within_days).get(name)
        if fn is None:
            logger.error("run: unknown source %s", name)
            return []
        return fn(mode, max_pages)
    except Exception as exc:  # noqa: BLE001 — per-source fault isolation; logged on next line.
        logger.error("run: source %s failed: %s", name, exc, exc_info=True)
        return []


def _build_dispatch(posted_within_days: int) -> dict:
    """Build the per-run dispatch dict. Binds posted_within_days into france_travail
    via functools.partial so every entry shares the same (mode, max_pages) signature.
    Module-level _DISPATCH (above) still exists for tests that introspect source coverage.
    """
    from functools import partial
    return {
        **_DISPATCH,
        JobSource.FRANCE_TRAVAIL.value: partial(_fetch_france_travail, posted_within_days=posted_within_days),
    }


# ----- main -----


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="job_search_v2 orchestrator.")
    parser.add_argument("--mode", choices=["live", "fixture"], default="live")
    parser.add_argument("--dry-run", action="store_true", help="Skip sheet append + email send.")
    parser.add_argument(
        "--sources",
        # Default = LIVE-VERIFIED sources that actually returned jobs in the
        # last 7 days of production run_log entries.
        #   france_travail        — official OAuth2 REST API (needs GH Secrets)
        #   linkedin_guest_api    — public unauthenticated jobs-guest endpoint
        #   wttj_algolia          — public Algolia backend
        #   hellowork             — public web scrape via JobPosting JSON-LD
        #   remoteok / weworkremotely — public JSON / RSS feeds
        # REMOVED FROM DEFAULT 2026-07-01: linkedin_gmail returned 0 rows every
        # day for the last 30 days per run_log; the IMAP call still takes 2-5s
        # per run and produces log noise. Opt back in via --sources when the
        # Gmail label / OAuth is confirmed healthy.
        # DARK / probationary sources (excluded from default):
        #   wttj                  — Playwright + __NEXT_DATA__, broken since WTTJ moved hydration
        #   apec                  — Playwright + Didomi consent gate blocks headless
        #   indeed_gmail / hellowork_gmail / jobgether_gmail — require user-side alert setup
        # Opt any back in by passing --sources explicitly.
        default="france_travail,linkedin_guest_api,wttj_algolia,hellowork,remoteok,weworkremotely",
        help="Comma-separated subset of sources to run.",
    )
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--posted-within-days", type=int, default=1)
    parser.add_argument("--no-location-filter", action="store_true",
                        help="Skip the FR-locked location filter. Useful for debugging.")
    parser.add_argument("--no-acceptance", action="store_true",
                        help="Skip the post-run acceptance gate (debugging only). "
                             "Normally the run EXITS NON-ZERO if the sheet ends up with "
                             "any irrelevant / non-EN-FR / out-of-scope row.")
    parser.add_argument("--no-ranker", action="store_true",
                        help="Skip Gemini ranking (jobs still flow through; all tier=B placeholder).")
    parser.add_argument("--no-sonnet-rerank", action="store_true",
                        help="Skip the Sonnet shortlist re-rank pass. Default: on iff "
                             "ANTHROPIC_API_KEY is in env. Costs ~$0.12 per run when active.")
    parser.add_argument("--sonnet-rerank-top-n", type=int, default=25,
                        help="How many top-of-first-pass jobs to send to Sonnet (default 25).")
    parser.add_argument("--max-digest-jobs", type=int, default=25,
                        help="Cap on jobs in the email digest + sheet append (default 25). "
                             "Sorted by ranker score descending if scored, else posted_at descending. "
                             "Excess jobs are still recorded in the dedup DB so they don't re-surface tomorrow.")
    parser.add_argument("--min-hours-between-emails", type=float, default=6.0,
                        help="Skip the email send if a digest was already sent in the last N hours "
                             "(default 22h). Stops the dual-cron-at-07:00+08:00-UTC double-send. "
                             "Idempotency state at .tmp/job_search_v2/last_email_sent_utc.txt.")
    args = parser.parse_args()

    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S") + "-" + uuid.uuid4().hex[:6]
    run_dir = TMP_RUNS / f"run_{run_id}"
    run_dir.mkdir(parents=True, exist_ok=True)
    logger.info("run: id=%s mode=%s dry_run=%s", run_id, args.mode, args.dry_run)

    sources = [s.strip() for s in args.sources.split(",") if s.strip()]
    unknown = [s for s in sources if s not in _DISPATCH]
    if unknown:
        logger.error("run: unknown sources %s. Valid: %s", unknown, list(_DISPATCH))
        return 2

    # Stage 1: fetch sources in parallel
    fetched: dict[str, list[SourceJob]] = {}
    with ThreadPoolExecutor(max_workers=len(sources)) as pool:
        future_to_name = {
            pool.submit(_call_source, name, args.mode, args.max_pages, args.posted_within_days): name
            for name in sources
        }
        for fut in as_completed(future_to_name):
            name = future_to_name[fut]
            jobs = fut.result()  # _call_source swallows exceptions
            fetched[name] = jobs
            logger.info("run: source %s → %d SourceJobs", name, len(jobs))
            # Persist per-source JSONL for the run dir
            (run_dir / f"{name}.jsonl").write_text(
                "\n".join(j.model_dump_json() for j in jobs) + ("\n" if jobs else ""),
                encoding="utf-8",
            )

    total_src = sum(len(v) for v in fetched.values())
    logger.info("run: total %d SourceJobs across %d sources", total_src, len(fetched))

    # Stage 2: normalize (in-batch cross-source dedup also happens here)
    all_src: list[SourceJob] = [j for jobs in fetched.values() for j in jobs]
    normalized = batch_normalize(all_src)
    (run_dir / "normalized.jsonl").write_text(
        "\n".join(j.model_dump_json() for j in normalized) + ("\n" if normalized else ""),
        encoding="utf-8",
    )
    logger.info("run: %d normalized (after in-batch dedup)", len(normalized))

    # Stage 3: persistent cross-day dedup
    new_jobs, dedup_stats = filter_new(normalized, db_path=DEFAULT_DB_PATH)
    logger.info("run: dedup stats %s", dedup_stats)

    # Stage 3.4: title filter — reject project-manager / alternance / internship /
    # graduate-program rows that the source keyword search fuzzy-matched into the PM set.
    title_kept, title_stats = filter_by_title(new_jobs)
    logger.info("run: title_filter %s", title_stats)

    # Stage 3.5: location filter (FR-locked unless --no-location-filter)
    cfg = load_config()
    if args.no_location_filter:
        loc_stats = {"total_in": len(title_kept), "kept": len(title_kept), "rejected": 0, "by_reason": {"disabled": len(title_kept)}}
        loc_kept = title_kept
    else:
        loc_kept, loc_stats = filter_by_location(title_kept, config=cfg)
    logger.info("run: location_filter %s", loc_stats)

    # Stage 3.6: contract filter — INTERNSHIP always dropped; UNKNOWN only when
    # source is FR-aware AND location is FR (otherwise the source legitimately
    # can't tell us the contract type for DE/BE/CH and we keep it).
    contract_kept, contract_stats = filter_by_contract(loc_kept)
    logger.info("run: contract_filter %s", contract_stats)

    # Stage 3.7: language filter — EN/FR only per operator hard constraint
    # (2026-06-24). Runs AFTER location because location-rejected jobs are
    # already gone; the cost is detection-per-kept-job only. A Berlin-based
    # role written in English passes here; one written in German is rejected.
    filtered_jobs, language_stats = filter_by_language(contract_kept)
    logger.info("run: language_filter %s", language_stats)

    # Stage 3.7: Gemini 2.5 Flash ranker (free tier)
    ranker_cfg = cfg.get("ranker", {}) if isinstance(cfg, dict) else {}
    ranker_enabled = bool(ranker_cfg.get("enabled", True)) and not args.no_ranker
    ranked_by_hash, ranker_stats = ranker.rank_jobs(filtered_jobs, enabled=ranker_enabled)
    logger.info("run: ranker %s", ranker_stats)

    # Stage 3.75: optional Sonnet shortlist re-rank. Auto-skips silently if
    # ANTHROPIC_API_KEY is not in env (so the code is safe to ship before the
    # console top-up clears). Refines only the top-N entries that actually end
    # up in Top Matches / email digest — the cheap upgrade for the cells the
    # operator actually reads.
    ranked_by_hash, rerank_stats = sonnet_rerank.rerank_shortlist(
        filtered_jobs,
        ranked_by_hash,
        top_n=args.sonnet_rerank_top_n,
        enabled=not args.no_sonnet_rerank,
    )
    logger.info("run: sonnet_rerank %s", rerank_stats)

    # Drop jobs the ranker tagged SKIP (still record them in the dedup DB so they don't
    # reappear, but don't push them to the sheet or digest).
    if ranker_enabled:
        ranked_filtered = [
            j for j in filtered_jobs
            if ranked_by_hash.get(j.content_hash) is None
            or ranked_by_hash[j.content_hash].tier.value != "SKIP"
        ]
    else:
        ranked_filtered = filtered_jobs

    # Stage 3.8: sort by best signal + cap to --max-digest-jobs. Without this, a daily
    # haul of 200+ PM jobs floods the operator's inbox. The cap is digest-grade UX, not
    # an information-loss event — excess jobs are STILL recorded in the dedup DB so they
    # don't re-surface tomorrow. To browse them, run with --max-digest-jobs 999.
    pre_cap_count = len(ranked_filtered)

    def _rank_key(job):
        ranked = ranked_by_hash.get(job.content_hash) if ranked_by_hash else None
        score = ranked.score if ranked is not None else 0.0
        # Posted_at as secondary sort: most recent first. Jobs without a posted_at
        # land at the bottom (epoch=0).
        ts = job.posted_at.timestamp() if job.posted_at is not None else 0.0
        return (-score, -ts)

    ranked_filtered.sort(key=_rank_key)
    cap = max(1, int(args.max_digest_jobs))
    ranked_filtered = ranked_filtered[:cap]
    cap_stats = {
        "pre_cap": pre_cap_count,
        "post_cap": len(ranked_filtered),
        "cap": cap,
        "dropped_for_cap": max(0, pre_cap_count - cap),
    }
    logger.info("run: digest_cap %s", cap_stats)

    # Stage 4: notify (route to PM / AI PM / etc. tabs via title synonyms)
    routing_cfg = cfg.get("tab_routing", {"fallback_tab": "PM", "titles": {}})
    sheet_count, per_tab_counts, sheet_ok = sheet_notifier.append_jobs(
        ranked_filtered,
        ranked_by_hash=ranked_by_hash,
        routing_config=routing_cfg,
        dry_run=args.dry_run,
    )

    # Stage 4b: refresh Top Matches + Summary dashboards. Both fully overwrite their tabs
    # on every run so they always reflect the latest pipeline state, never stale data.
    top_count, top_ok = sheet_notifier.refresh_top_matches(
        ranked_filtered,
        ranked_by_hash=ranked_by_hash,
        routing_config=routing_cfg,
        dry_run=args.dry_run,
    )
    pipeline_stats = {
        "run_id": run_id,
        "mode": args.mode,
        "dry_run": args.dry_run,
        "per_source": {name: len(jobs) for name, jobs in fetched.items()},
        "total_fetched": total_src,
        "after_normalize": len(normalized),
        "after_dedup_new": len(new_jobs),
        "already_seen": dedup_stats["already_seen"],
        "expired_swept": dedup_stats["expired_swept"],
        "title_filter": title_stats,
        "after_location_filter": loc_stats["kept"],
        "location_rejected": loc_stats["rejected"],
        "location_by_reason": loc_stats["by_reason"],
        "contract_filter": contract_stats,
        "language_filter": language_stats,
        "ranker": ranker_stats,
        "sonnet_rerank": rerank_stats,
        "after_ranker_skip": len(ranked_filtered),
        "sheet_appended": sheet_count,
        "sheet_per_tab": per_tab_counts,
        "sheet_ok": sheet_ok,
        "top_matches_written": top_count,
        "top_matches_ok": top_ok,
    }
    # Stage 4c: ACCEPTANCE GATE — runs BEFORE the email so a junk-output day
    # never reaches the operator's inbox. The gate reads every row actually on
    # the live sheet (post-Stage 4 append) and rejects irrelevant / non-EN-FR /
    # out-of-scope / broken-link rows against a frozen corpus.
    #   - PASS → email is allowed to fire (subject to the dual-cron lock).
    #   - FAIL → email is blocked, run exits non-zero (code 3) so the cron is red.
    #   - Skippable ONLY via --no-acceptance, a debugging escape hatch; never add
    #     it to the GH Actions cron YAML.
    #   - LIMITATION: rows are already on the sheet when the gate fails — the
    #     non-zero exit flags the run red but does not roll rows back. They get
    #     purged on the next clean run's Stage 4 clear; for an immediate scrub
    #     run purge_irrelevant_rows.py.
    acceptance_ok = True
    if not args.dry_run and not args.no_acceptance:
        try:
            import subprocess
            # Pass current-run stats to acceptance via tempfile — the run_log
            # append (Stage 5) happens AFTER acceptance runs, so without this
            # the L3 silent-degradation gate would read the *previous* run's
            # stats (or none on a fresh CI runner). Path is env-var, so the
            # acceptance script can also be invoked manually without it.
            current_stats_path = run_dir / "current_stats.json"
            current_stats_path.write_text(
                json.dumps(pipeline_stats), encoding="utf-8",
            )
            acceptance_env = dict(os.environ)
            acceptance_env["CURRENT_RUN_STATS_PATH"] = str(current_stats_path)
            proc = subprocess.run(
                [sys.executable, str(PROJECT_ROOT / "tests" / "acceptance_job_search_v2.py")],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=str(PROJECT_ROOT), timeout=180, env=acceptance_env,
            )
            acceptance_ok = proc.returncode == 0
            pipeline_stats["acceptance"] = "PASS" if acceptance_ok else "FAIL"
            # Surface the acceptance verdict + any violation lines into the log.
            tail = "\n".join((proc.stdout or "").strip().splitlines()[-15:])
            logger.info("run: ACCEPTANCE %s\n%s", pipeline_stats["acceptance"], tail)
        except Exception as exc:  # noqa: BLE001 — acceptance harness failure is itself a FAIL
            acceptance_ok = False
            pipeline_stats["acceptance"] = f"FAIL (harness error: {exc})"
            logger.error("run: acceptance harness error: %s", exc)
    else:
        pipeline_stats["acceptance"] = "skipped (dry_run or --no-acceptance)"
        if not args.dry_run and args.no_acceptance:
            logger.warning(
                "run: ACCEPTANCE GATE SKIPPED via --no-acceptance on a REAL run — "
                "output quality is UNVERIFIED. This flag is for debugging only and "
                "must never be set in the cron."
            )

    # Stage 4d: Email — gated on the acceptance result above. Dry-run runs never
    # check the lock and never stamp it (so manual workflow_dispatch tests don't
    # clobber the production state).
    now_utc = datetime.now(timezone.utc)
    if args.dry_run:
        email_sent, subject, body = email_notifier.send_digest(
            ranked_filtered, pipeline_stats, dry_run=True, ranked_by_hash=ranked_by_hash,
        )
        pipeline_stats["email_lock"] = "skipped (dry_run)"
    elif not acceptance_ok:
        # Acceptance failed — build the body for the run-log but do NOT send.
        # The operator gets silence + a red cron instead of a junk inbox.
        subject, body = email_notifier.build_digest(
            ranked_filtered, pipeline_stats,
            os.environ.get("SHEETS_SPREADSHEET_ID", "").strip() or None,
            ranked_by_hash=ranked_by_hash,
        )
        email_sent = False
        pipeline_stats["email_lock"] = "skipped (acceptance gate FAIL — see acceptance field)"
        logger.warning(
            "notifier.email: skipped because acceptance gate FAILED — "
            "operator would otherwise receive a junk digest."
        )
    else:
        blocked, reason = _email_lock_blocks_send(args.min_hours_between_emails, now_utc)
        pipeline_stats["email_lock"] = reason
        if blocked:
            logger.info("notifier.email: %s", reason)
            # Still build the body so we have it in the run-log for debugging, but don't send.
            subject, body = email_notifier.build_digest(
                ranked_filtered, pipeline_stats,
                os.environ.get("SHEETS_SPREADSHEET_ID", "").strip() or None,
                ranked_by_hash=ranked_by_hash,
            )
            email_sent = False
        else:
            email_sent, subject, body = email_notifier.send_digest(
                ranked_filtered, pipeline_stats, dry_run=False, ranked_by_hash=ranked_by_hash,
            )
            if email_sent:
                _stamp_email_sent(now_utc)
    pipeline_stats["email_sent"] = email_sent
    pipeline_stats["email_subject"] = subject

    # Stage 4e: refresh Summary tab with full pipeline_stats + all-time totals.
    # Runs AFTER email so the Summary tab reflects the final email/acceptance status.
    role_tabs = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]
    per_tab_totals: dict[str, int] = {}
    if not args.dry_run:
        try:
            per_tab_totals = sheet_notifier.count_existing_rows(role_tabs)
        except Exception as exc:  # noqa: BLE001 — best-effort summary input
            logger.warning("run: count_existing_rows failed: %s", exc)
    summary_ok = sheet_notifier.refresh_summary(
        pipeline_stats,
        per_tab_totals=per_tab_totals,
        dry_run=args.dry_run,
    )
    pipeline_stats["summary_ok"] = summary_ok
    pipeline_stats["per_tab_totals"] = per_tab_totals

    # Reliability counter — n=1 is not reliability. Track CONSECUTIVE acceptance
    # PASS runs in a small JSON state file. A PASS increments; any FAIL resets to
    # 0. "Shippable" per ~/.claude/rules/front-door-synthetic.md = 5 consecutive.
    # This makes the reliability claim MEASURED, not asserted. Skipped on dry-run.
    if not args.dry_run and not args.no_acceptance:
        streak_path = PROJECT_ROOT / ".tmp" / "job_search_v2" / "acceptance_streak.json"
        prior_streak = 0
        try:
            if streak_path.exists():
                prior_streak = int(json.loads(streak_path.read_text(encoding="utf-8")).get("consecutive_pass", 0))
        except (OSError, ValueError, json.JSONDecodeError):
            prior_streak = 0
        new_streak = (prior_streak + 1) if acceptance_ok else 0
        try:
            streak_path.parent.mkdir(parents=True, exist_ok=True)
            streak_path.write_text(json.dumps({
                "consecutive_pass": new_streak,
                "last_run_id": run_id,
                "last_verdict": pipeline_stats["acceptance"],
                "shippable": new_streak >= 5,
                "updated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            }), encoding="utf-8")
        except OSError as exc:
            logger.warning("run: could not write acceptance streak: %s", exc)
        pipeline_stats["acceptance_streak"] = new_streak
        pipeline_stats["shippable"] = new_streak >= 5
        logger.info("run: acceptance streak = %d/5 consecutive PASS (shippable=%s)",
                    new_streak, new_streak >= 5)

    # Stage 5: write summary + append run-log
    (run_dir / "summary.json").write_text(json.dumps(pipeline_stats, indent=2), encoding="utf-8")
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pipeline_stats) + "\n")

    logger.info("run: done. summary at %s", run_dir / "summary.json")
    # Stdout = the digest body so caller can pipe / log it.
    # On Windows cp1252 consoles certain characters (em-dash, middle-dot) can't be
    # encoded — write through the stream's buffer with errors='replace' so we never crash.
    try:
        sys.stdout.write(body + "\n")
    except UnicodeEncodeError:
        sys.stdout.buffer.write((body + "\n").encode("utf-8", errors="replace"))
    # Non-zero exit conditions (richer than just acceptance) so the cron / caller
    # SEES every silent-failure class as a red run, not a green one. The sheet
    # write already happened in failure cases, but the alarm is loud and the
    # run-log records the verdict for forensics.
    #   exit 3 = acceptance gate FAILED (junk in output — email was blocked)
    #   exit 4 = email send was expected but did NOT happen for any unexpected
    #            reason (SMTP error, missing creds, etc.) — i.e. acceptance passed
    #            and the lock did not block, but email_sent is still false.
    #   exit 0 = all-good OR the skip was deliberate (dry-run, lock-blocked, or
    #            acceptance FAIL which already returned 3)
    if not acceptance_ok:
        return 3
    if not args.dry_run:
        lock_reason = str(pipeline_stats.get("email_lock", ""))
        deliberate_skip = (
            lock_reason.startswith("email lock [")  # lock fired — within floor
            or "skipped (acceptance" in lock_reason  # acceptance gate killed it (covered by exit 3 above)
        )
        if not email_sent and not deliberate_skip:
            logger.error(
                "run: email_sent=false on a real run with no deliberate skip "
                "(acceptance=%s, lock=%s). Surfacing as exit 4 so the cron is red.",
                pipeline_stats.get("acceptance"), lock_reason,
            )
            return 4
    return 0


if __name__ == "__main__":
    sys.exit(main())
