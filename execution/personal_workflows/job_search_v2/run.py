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

from dotenv import load_dotenv

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
from execution.personal_workflows.job_search_v2.normalizer.location_filter import (  # noqa: E402
    filter_by_location,
    load_config,
)
from execution.personal_workflows.job_search_v2.normalizer.normalize import (  # noqa: E402
    batch_normalize,
)
from execution.personal_workflows.job_search_v2.notifier import email as email_notifier  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier import sheet as sheet_notifier  # noqa: E402
from execution.personal_workflows.job_search_v2.ranker import score as ranker  # noqa: E402

load_dotenv()
logger = logging.getLogger("run")

PROJECT_ROOT = _WORKSPACE
TMP_RUNS = PROJECT_ROOT / ".tmp" / "job_search_v2" / "runs"
RUN_LOG = PROJECT_ROOT / ".tmp" / "job_search_v2" / "run_log.jsonl"

# Email-lock state lives inside seen.db's meta KV table, NOT a separate file.
# This is the autonomous-deploy workaround for the workflow YAML being unable to
# add new cache paths (PAT lacks `workflow` scope). seen.db is already cached by
# the existing GH Actions cache step, so the lock state piggy-backs on it for free.
EMAIL_LOCK_KEY = "last_email_sent_utc"


def _email_lock_blocks_send(
    min_hours_between_emails: float,
    now_utc: datetime,
    db_path: Path = DEFAULT_DB_PATH,
) -> tuple[bool, str]:
    """Check whether the email lock should block this send.

    Returns (blocked, reason). Blocked=True if the last send was less than
    min_hours_between_emails ago. State lives in seen.db meta KV (cached across cron).
    """
    if min_hours_between_emails <= 0:
        return False, "email_lock disabled (min_hours_between_emails <= 0)"
    try:
        prior_iso = get_meta(db_path, EMAIL_LOCK_KEY)
    except Exception as exc:  # noqa: BLE001 — seen.db absent / corrupt → treat as no prior send.
        return False, f"meta read failed ({exc}); treating as no prior send"
    if not prior_iso:
        return False, "no prior send recorded"
    try:
        prior = datetime.fromisoformat(prior_iso.replace("Z", "+00:00"))
    except ValueError as exc:
        return False, f"state value unreadable ({exc}); treating as no prior send"
    if prior.tzinfo is None:
        prior = prior.replace(tzinfo=timezone.utc)
    delta_hours = (now_utc - prior).total_seconds() / 3600.0
    if delta_hours < min_hours_between_emails:
        return True, (
            f"email lock: last send was {delta_hours:.1f}h ago "
            f"(< {min_hours_between_emails:.1f}h floor) — skipping to prevent dual-cron spam"
        )
    return False, f"email lock cleared: last send was {delta_hours:.1f}h ago"


def _stamp_email_sent(now_utc: datetime, db_path: Path = DEFAULT_DB_PATH) -> None:
    set_meta(db_path, EMAIL_LOCK_KEY, now_utc.isoformat())


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


def _fetch_linkedin_guest_api(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import linkedin_guest_api as lga
    if mode == "fixture":
        return lga.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "linkedin_guest_api_sample.html")
    try:
        return lga.fetch(max_pages_per_keyword=max_pages, posted_within_hours=48)
    except lga.LinkedInBlockedError as exc:
        logger.warning("run: linkedin_guest_api blocked — %s. Skipping source.", exc)
        return []


def _fetch_wttj_algolia(mode: str, max_pages: int) -> list[SourceJob]:
    from execution.personal_workflows.job_search_v2.sources import wttj_algolia
    if mode == "fixture":
        return wttj_algolia.fetch_from_fixture(PROJECT_ROOT / "tests" / "fixtures" / "wttj_algolia_sample.json")
    try:
        return wttj_algolia.fetch(max_pages=max_pages, posted_within_hours=48)
    except wttj_algolia.WttjAlgoliaBlockedError as exc:
        logger.warning("run: wttj_algolia blocked — %s. Skipping source.", exc)
        return []


_DISPATCH = {
    JobSource.FRANCE_TRAVAIL.value: _fetch_france_travail,
    JobSource.WTTJ.value: _fetch_wttj,
    JobSource.WTTJ_ALGOLIA.value: _fetch_wttj_algolia,
    JobSource.APEC.value: _fetch_apec,
    JobSource.LINKEDIN_GMAIL.value: _fetch_linkedin_gmail,
    JobSource.LINKEDIN_GUEST_API.value: _fetch_linkedin_guest_api,
    JobSource.INDEED_GMAIL.value: _fetch_indeed_gmail,
    JobSource.HELLOWORK_GMAIL.value: _fetch_hellowork_gmail,
    JobSource.JOBGETHER_GMAIL.value: _fetch_jobgether_gmail,
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
        # Default = LIVE-VERIFIED sources only (2026-06-18 smoke):
        #   france_travail        — official OAuth2 REST API (needs GH Secrets)
        #   linkedin_guest_api    — public unauthenticated jobs-guest endpoint, ~10 jobs/keyword/page
        #   wttj_algolia          — public Algolia backend, ~30 hits/keyword/page
        #   linkedin_gmail        — kept as belt-and-suspenders (already-configured Gmail label)
        # DARK / probationary sources (excluded from default):
        #   wttj                  — Playwright + __NEXT_DATA__, broken since WTTJ moved hydration
        #   apec                  — Playwright + Didomi consent gate blocks headless
        #   indeed_gmail / hellowork_gmail / jobgether_gmail — require user-side alert setup
        # Opt them back in by passing --sources explicitly.
        default="france_travail,linkedin_guest_api,wttj_algolia,linkedin_gmail",
        help="Comma-separated subset of sources to run.",
    )
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--posted-within-days", type=int, default=1)
    parser.add_argument("--no-location-filter", action="store_true",
                        help="Skip the FR-locked location filter. Useful for debugging.")
    parser.add_argument("--no-ranker", action="store_true",
                        help="Skip Gemini ranking (jobs still flow through; all tier=B placeholder).")
    parser.add_argument("--max-digest-jobs", type=int, default=25,
                        help="Cap on jobs in the email digest + sheet append (default 25). "
                             "Sorted by ranker score descending if scored, else posted_at descending. "
                             "Excess jobs are still recorded in the dedup DB so they don't re-surface tomorrow.")
    parser.add_argument("--min-hours-between-emails", type=float, default=22.0,
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

    # Stage 3.5: location filter (FR-locked unless --no-location-filter)
    cfg = load_config()
    if args.no_location_filter:
        loc_stats = {"total_in": len(new_jobs), "kept": len(new_jobs), "rejected": 0, "by_reason": {"disabled": len(new_jobs)}}
        filtered_jobs = new_jobs
    else:
        filtered_jobs, loc_stats = filter_by_location(new_jobs, config=cfg)
    logger.info("run: location_filter %s", loc_stats)

    # Stage 3.7: Gemini 2.5 Flash ranker (free tier)
    ranker_cfg = cfg.get("ranker", {}) if isinstance(cfg, dict) else {}
    ranker_enabled = bool(ranker_cfg.get("enabled", True)) and not args.no_ranker
    ranked_by_hash, ranker_stats = ranker.rank_jobs(filtered_jobs, enabled=ranker_enabled)
    logger.info("run: ranker %s", ranker_stats)

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
        "after_location_filter": loc_stats["kept"],
        "location_rejected": loc_stats["rejected"],
        "location_by_reason": loc_stats["by_reason"],
        "ranker": ranker_stats,
        "after_ranker_skip": len(ranked_filtered),
        "sheet_appended": sheet_count,
        "sheet_per_tab": per_tab_counts,
        "sheet_ok": sheet_ok,
        "top_matches_written": top_count,
        "top_matches_ok": top_ok,
    }
    # Email lock — prevents dual-cron (07:00 UTC + 08:00 UTC DST workaround) double-send.
    # Dry-run runs never check the lock and never stamp it (so manual workflow_dispatch
    # tests don't clobber the production state).
    now_utc = datetime.now(timezone.utc)
    if args.dry_run:
        email_sent, subject, body = email_notifier.send_digest(
            ranked_filtered, pipeline_stats, dry_run=True, ranked_by_hash=ranked_by_hash,
        )
        pipeline_stats["email_lock"] = "skipped (dry_run)"
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

    # Stage 4c: refresh Summary tab with full pipeline_stats + all-time totals.
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
    return 0


if __name__ == "__main__":
    sys.exit(main())
