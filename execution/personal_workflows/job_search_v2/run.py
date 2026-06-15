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

load_dotenv()
logger = logging.getLogger("run")

PROJECT_ROOT = _WORKSPACE
TMP_RUNS = PROJECT_ROOT / ".tmp" / "job_search_v2" / "runs"
RUN_LOG = PROJECT_ROOT / ".tmp" / "job_search_v2" / "run_log.jsonl"


# ----- source dispatch -----


def _fetch_france_travail(mode: str, max_pages: int, posted_within_days: int) -> list[SourceJob]:
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


_DISPATCH = {
    JobSource.FRANCE_TRAVAIL.value: _fetch_france_travail,
    JobSource.WTTJ.value: _fetch_wttj,
    JobSource.APEC.value: _fetch_apec,
    JobSource.LINKEDIN_GMAIL.value: _fetch_linkedin_gmail,
}


def _call_source(name: str, mode: str, max_pages: int, posted_within_days: int) -> list[SourceJob]:
    """Wrapper so each source's failure can't kill the pipeline."""
    try:
        if name == JobSource.FRANCE_TRAVAIL.value:
            return _fetch_france_travail(mode, max_pages, posted_within_days)
        if name == JobSource.WTTJ.value:
            return _fetch_wttj(mode, max_pages)
        if name == JobSource.APEC.value:
            return _fetch_apec(mode, max_pages)
        if name == JobSource.LINKEDIN_GMAIL.value:
            return _fetch_linkedin_gmail(mode, max_pages)
    except Exception as exc:  # noqa: BLE001 — per-source fault isolation
        logger.error("run: source %s failed: %s", name, exc, exc_info=True)
    return []


# ----- main -----


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="job_search_v2 orchestrator.")
    parser.add_argument("--mode", choices=["live", "fixture"], default="live")
    parser.add_argument("--dry-run", action="store_true", help="Skip sheet append + email send.")
    parser.add_argument(
        "--sources",
        default="france_travail,wttj,apec,linkedin_gmail",
        help="Comma-separated subset of sources to run.",
    )
    parser.add_argument("--max-pages", type=int, default=3)
    parser.add_argument("--posted-within-days", type=int, default=1)
    parser.add_argument("--no-location-filter", action="store_true",
                        help="Skip the FR-locked location filter. Useful for debugging.")
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
    if args.no_location_filter:
        loc_stats = {"total_in": len(new_jobs), "kept": len(new_jobs), "rejected": 0, "by_reason": {"disabled": len(new_jobs)}}
        filtered_jobs = new_jobs
    else:
        cfg = load_config()
        filtered_jobs, loc_stats = filter_by_location(new_jobs, config=cfg)
    logger.info("run: location_filter %s", loc_stats)

    # Stage 4: notify
    sheet_count, sheet_ok = sheet_notifier.append_jobs(filtered_jobs, dry_run=args.dry_run)
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
        "sheet_appended": sheet_count,
        "sheet_ok": sheet_ok,
    }
    email_sent, subject, body = email_notifier.send_digest(filtered_jobs, pipeline_stats, dry_run=args.dry_run)
    pipeline_stats["email_sent"] = email_sent
    pipeline_stats["email_subject"] = subject

    # Stage 5: write summary + append run-log
    (run_dir / "summary.json").write_text(json.dumps(pipeline_stats, indent=2), encoding="utf-8")
    RUN_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUN_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(pipeline_stats) + "\n")

    logger.info("run: done. summary at %s", run_dir / "summary.json")
    # Stdout = the digest body so caller can pipe / log it
    sys.stdout.write(body + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
