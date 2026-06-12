"""
job_tracker_pm_france.py
description: Main daily orchestrator for the French PM/PO Job Tracker. Discovers jobs across
    configured boards, normalises and filters them, resolves companies via SIRENE, enriches
    contacts, persists everything to SQLite, and sends (or skips) an HTML digest email.
    Stages A→H as documented below. Run once per day via cron. Idempotent within a day.
inputs: CLI flags (--boards, --mock, --dry-run, --no-enrich, --no-resolve, --send, --db,
    --max-per-board); env vars loaded from .env; tests/fixtures/raw_<board>.json in mock mode.
outputs: SQLite DB rows (companies, jobs, contacts, notifications_log); .tmp/job_tracker/<run_id>/
    intermediates; .tmp/job_tracker_pm_france.log; digest HTML; optional email via Gmail SMTP.
"""

import argparse
import json
import os
import re
import statistics
import sys
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import (  # noqa: E402
    setup_logging,
    now_iso,
    generate_run_id,
    load_jt_config,
    save_json,
    load_json,
)
from execution.personal_workflows.job_tracker_db import (  # noqa: E402
    init_db,
    upsert_company,
    upsert_job,
    upsert_contact,
    mark_expired,
    recent_contact_cache_hit,
    log_notification,
)
from execution.custom_scrapers.job_filter import filter_jobs  # noqa: E402
from execution.custom_scrapers import (  # noqa: E402
    wttj_jobs,
    indeed_jobs,
    apec_jobs,
    france_travail_jobs,
    google_jobs_serper,
)
from execution.lead_sourcing.sirene_company_lookup import lookup_company  # noqa: E402
from execution.enrichment.firecrawl_linkedin_dork import find_contacts_for_company  # noqa: E402
from execution.personal_workflows.job_digest_renderer import render_digest_html  # noqa: E402
from execution.google.gmail_send_digest import send_digest  # noqa: E402


# ---------------------------------------------------------------------------
# Module-level logger (set up for real after run_id is known)
# ---------------------------------------------------------------------------

logger = setup_logging(
    "job_tracker",
    PROJECT_ROOT / ".tmp" / "job_tracker_pm_france.log",
)

# Board name → scraper module
_BOARD_MODULES = {
    "wttj": wttj_jobs,
    "indeed": indeed_jobs,
    "apec": apec_jobs,
    "francetravail": france_travail_jobs,
    "google": google_jobs_serper,
}


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _today_paris_str() -> str:
    """Return a human-readable Paris-timezone date string, e.g. 'Wed 14 May'."""
    paris_tz = ZoneInfo("Europe/Paris")
    now_paris = datetime.now(timezone.utc).astimezone(paris_tz)
    return now_paris.strftime("%a %d %b")


def _company_slug(name: str) -> str:
    """Convert a company name to a filesystem-safe slug (alphanum + dashes only)."""
    decomposed = unicodedata.normalize("NFKD", name)
    ascii_only = decomposed.encode("ascii", "ignore").decode("ascii")
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_only.lower()).strip("-")
    return slug or "unknown"


def _split_boards_arg(s: str) -> list[str]:
    """Parse comma-separated board names from CLI into a clean list."""
    return [b.strip().lower() for b in s.split(",") if b.strip()]


def _update_board_counts_history(
    project_root: Path,
    run_id: str,
    counts: dict[str, int],
) -> dict[str, float]:
    """Append today's board counts to the rolling history file; return 7-day medians.

    History file: <project_root>/.tmp/job_tracker/board_counts.json
    Keeps last 14 entries (each entry = {run_id, counts_by_board}).
    Returns {board_name: median_last_7_runs}.
    """
    history_path = project_root / ".tmp" / "job_tracker" / "board_counts.json"
    history_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing history
    history: list[dict] = []
    if history_path.exists():
        try:
            history = json.loads(history_path.read_text(encoding="utf-8"))
            if not isinstance(history, list):
                history = []
        except (json.JSONDecodeError, OSError):
            history = []

    # Append current run
    history.append({"run_id": run_id, "counts": counts})
    # Keep last 14 entries
    history = history[-14:]

    try:
        history_path.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
    except OSError as exc:
        logger.warning("Could not write board counts history: %s", exc)

    # Compute 7-day medians from the last 7 entries (excluding current)
    past_entries = history[:-1][-7:]  # up to 7 entries before current
    medians: dict[str, float] = {}
    all_boards = set(counts.keys())
    for entry in past_entries:
        all_boards.update(entry.get("counts", {}).keys())

    for board in all_boards:
        vals = [e["counts"].get(board, 0) for e in past_entries]
        medians[board] = statistics.median(vals) if vals else 0.0

    return medians


def _detect_degraded_boards(
    counts_today: dict[str, int],
    medians: dict[str, float],
) -> list[str]:
    """Return board names where today's count < 30 % of the 7-day median.

    Boards with median == 0 are never flagged as degraded (no baseline yet).
    """
    degraded: list[str] = []
    for board, count in counts_today.items():
        median = medians.get(board, 0.0)
        if median > 0 and count < 0.3 * median:
            degraded.append(board)
    return degraded


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline(args: argparse.Namespace) -> int:
    """Execute stages A→H. Returns 0 on success, 1 on hard failure.

    Refactored from main() so tests can import and call it directly with a
    constructed argparse.Namespace — avoids subprocess-level orchestration.
    """
    # ---- Setup ---------------------------------------------------------------
    run_id = generate_run_id()
    config = load_jt_config()

    tmp_dir = PROJECT_ROOT / config["tmp_dir"] / run_id
    tmp_dir.mkdir(parents=True, exist_ok=True)

    logger.info(json.dumps({"event": "run_start", "run_id": run_id, "args": vars(args)}))

    # Resolve DB path: CLI flag > env var > config
    if args.db:
        db_path = Path(args.db)
    else:
        env_db = os.environ.get(config.get("db_path_env", "JOB_TRACKER_DB_PATH"), "")
        db_path = (
            Path(env_db)
            if env_db
            else (PROJECT_ROOT / config["default_db_path"])
        )

    # Resolve recipient
    recipient_env = config.get("recipient_email_env", "JOB_TRACKER_RECIPIENT")
    resolved_recipient = os.environ.get(recipient_env, "")

    # Enabled boards (from config)
    config_boards_by_name: dict[str, dict] = {
        b["name"]: b for b in config.get("boards", [])
    }

    # Boards to run (CLI arg may subset; default = all enabled in config)
    requested_boards = (
        _split_boards_arg(args.boards)
        if args.boards
        else [b["name"] for b in config.get("boards", []) if b.get("enabled", True)]
    )
    active_boards = [
        name for name in requested_boards
        if config_boards_by_name.get(name, {}).get("enabled", True)
    ]

    # ---- Stage A: Discover ---------------------------------------------------
    per_board_raw: dict[str, list[dict]] = {}
    per_board_counts: dict[str, int] = {}
    _board_lock = threading.Lock()

    def _scrape_board(board: str) -> tuple[str, list[dict]]:
        """Scrape a single board; returns (board_name, raw_results).

        Failure-isolated: any exception returns an empty list so one bad
        scraper cannot abort the whole run.
        """
        board_cfg = config_boards_by_name.get(board, {})
        try:
            if args.mock:
                fixture_path = PROJECT_ROOT / "tests" / "fixtures" / f"raw_{board}.json"
                raw: list[dict] = load_json(fixture_path)
                logger.info(
                    json.dumps(
                        {"event": "board_scraped_mock", "board": board, "count": len(raw)}
                    )
                )
            else:
                module = _BOARD_MODULES.get(board)
                if module is None:
                    raise ValueError(f"No scraper module registered for board '{board}'")
                raw = module.scrape(
                    queries=board_cfg.get("queries", []),
                    output_path=tmp_dir / f"raw_{board}.json",
                    run_id=run_id,
                    max_results=args.max_per_board,
                )
                logger.info(
                    json.dumps(
                        {"event": "board_scraped", "board": board, "count": len(raw)}
                    )
                )
            return board, raw
        except Exception as exc:
            logger.error(
                json.dumps(
                    {
                        "event": "board_failed",
                        "board": board,
                        "error": str(exc),
                    }
                )
            )
            return board, []

    max_workers = min(args.max_workers, len(active_boards)) if active_boards else 1
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(_scrape_board, board): board for board in active_boards}
        for future in as_completed(futures):
            board_name, raw_results = future.result()
            with _board_lock:
                per_board_raw[board_name] = raw_results
                per_board_counts[board_name] = len(raw_results)

    # Degraded-board detection
    medians = _update_board_counts_history(PROJECT_ROOT, run_id, per_board_counts)
    degraded_boards = _detect_degraded_boards(per_board_counts, medians)
    if degraded_boards:
        logger.warning(
            json.dumps({"event": "degraded_boards_detected", "boards": degraded_boards})
        )

    # ---- Stage B: Normalize + Filter -----------------------------------------
    all_raw: list[dict] = []
    for raw_list in per_board_raw.values():
        all_raw.extend(raw_list)

    try:
        candidates: list[dict] = filter_jobs(all_raw, config)
    except Exception as exc:
        logger.error(
            json.dumps({"event": "filter_failed", "error": str(exc)})
        )
        return 1

    kept = [c for c in candidates if c.get("passed_filters")]
    dropped = [c for c in candidates if not c.get("passed_filters")]

    try:
        save_json(kept, tmp_dir / "candidates.json")
        save_json(dropped, tmp_dir / "dropped.json")
    except Exception as exc:
        logger.warning("Could not save candidate/dropped JSON: %s", exc)

    logger.info(
        json.dumps({"event": "filter_done", "kept": len(kept), "dropped": len(dropped)})
    )

    # ---- Stage C: Dedupe vs DB -----------------------------------------------
    try:
        conn = init_db(db_path)
    except Exception as exc:
        logger.error(json.dumps({"event": "db_init_failed", "error": str(exc)}))
        return 1

    new_candidates: list[dict] = []
    existing_jobs: list[dict] = []  # already in DB — last_seen_at updated in F3

    for candidate in kept:
        job_hash = candidate.get("job_hash", "")
        row = conn.execute(
            "SELECT id, last_seen_at FROM jobs WHERE job_hash = ?", (job_hash,)
        ).fetchone()
        if row:
            existing_jobs.append({"id": row["id"], "candidate": candidate})
        else:
            new_candidates.append(candidate)

    logger.info(
        json.dumps(
            {
                "event": "dedupe_done",
                "new": len(new_candidates),
                "existing": len(existing_jobs),
            }
        )
    )

    # ---- Stage D: Resolve company via SIRENE (skip if --no-resolve) ----------
    if not args.no_resolve and new_candidates:
        distinct_names = {
            c["company_normalized"]: c.get("company_name", c["company_normalized"])
            for c in new_candidates
        }
        resolution_cache: dict[str, dict] = {}

        for norm_name, display_name in distinct_names.items():
            if norm_name in resolution_cache:
                continue
            try:
                resolution = lookup_company(display_name)
                resolution_cache[norm_name] = resolution or {}
            except Exception as exc:
                logger.warning(
                    json.dumps(
                        {
                            "event": "sirene_failed",
                            "company": display_name,
                            "error": str(exc),
                        }
                    )
                )
                resolution_cache[norm_name] = {
                    "siren": None,
                    "naf_code": None,
                    "is_digital_sector": None,
                }

        # Annotate new candidates with resolution fields
        for candidate in new_candidates:
            norm = candidate.get("company_normalized", "")
            res = resolution_cache.get(norm, {})
            candidate["siren"] = res.get("siren")
            candidate["naf_code"] = res.get("naf_code")
            candidate["is_digital_sector"] = res.get("is_digital_sector")
            candidate["website"] = res.get("website")

        logger.info(
            json.dumps(
                {
                    "event": "resolve_done",
                    "resolved": len(resolution_cache),
                }
            )
        )
    else:
        for candidate in new_candidates:
            candidate.setdefault("siren", None)
            candidate.setdefault("naf_code", None)
            candidate.setdefault("is_digital_sector", None)
            candidate.setdefault("website", None)

    # ---- Stages F1 / E / F2 / F3: Persist ------------------------------------
    try:
        # F1: Upsert companies (get company_ids for new candidates)
        company_id_cache: dict[str, int] = {}  # name_normalized → company_id

        for candidate in new_candidates:
            norm = candidate.get("company_normalized", "")
            if norm in company_id_cache:
                continue
            company_id = upsert_company(
                conn,
                name=candidate.get("company_name", norm),
                name_normalized=norm,
                siren=candidate.get("siren"),
                naf_code=candidate.get("naf_code"),
                website=candidate.get("website"),
                is_digital_sector=candidate.get("is_digital_sector"),
            )
            company_id_cache[norm] = company_id

        logger.info(
            json.dumps(
                {"event": "f1_companies_upserted", "count": len(company_id_cache)}
            )
        )

        # E: Enrich contacts (skip if --no-enrich)
        if not args.no_enrich and new_candidates:
            new_company_norms = set(
                c["company_normalized"] for c in new_candidates
            )
            for norm in new_company_norms:
                company_id = company_id_cache.get(norm)
                if company_id is None:
                    continue
                # Check cache: if we enriched contacts recently, skip
                cache_days = config.get("contact_cache_days", 60)
                if recent_contact_cache_hit(conn, company_id, cache_days):
                    logger.info(
                        json.dumps(
                            {
                                "event": "contact_cache_hit",
                                "company_normalized": norm,
                            }
                        )
                    )
                    continue

                # Find display name from any candidate
                display_name = norm
                for c in new_candidates:
                    if c.get("company_normalized") == norm:
                        display_name = c.get("company_name", norm)
                        break

                slug = _company_slug(display_name)
                try:
                    contacts = find_contacts_for_company(display_name, max_total=5)
                    save_json(contacts, tmp_dir / f"contacts_{slug}.json")
                    logger.info(
                        json.dumps(
                            {
                                "event": "contacts_enriched",
                                "company": display_name,
                                "count": len(contacts),
                            }
                        )
                    )
                except Exception as exc:
                    logger.warning(
                        json.dumps(
                            {
                                "event": "enrich_failed",
                                "company": display_name,
                                "error": str(exc),
                            }
                        )
                    )
                    contacts = []

                # F2: Upsert contacts
                for contact in contacts:
                    try:
                        upsert_contact(
                            conn,
                            company_id=company_id,
                            full_name=contact.get("full_name", ""),
                            title=contact.get("title"),
                            seniority=contact.get("seniority"),
                            linkedin_url=contact.get("linkedin_url"),
                            source=contact.get("source", "firecrawl_dork"),
                        )
                    except Exception as exc:
                        logger.warning(
                            "Could not upsert contact '%s': %s",
                            contact.get("full_name"),
                            exc,
                        )

        logger.info(json.dumps({"event": "e_enrich_done"}))

        # F3: Upsert new jobs + update last_seen_at for existing
        new_job_ids: list[int] = []
        for candidate in new_candidates:
            norm = candidate.get("company_normalized", "")
            company_id = company_id_cache.get(norm)
            if company_id is None:
                logger.warning(
                    "company_id not found for '%s' — skipping job upsert", norm
                )
                continue
            try:
                job_id, is_new = upsert_job(
                    conn,
                    job_hash=candidate.get("job_hash", ""),
                    company_id=company_id,
                    title=candidate.get("title", ""),
                    title_normalized=candidate.get("title_normalized", ""),
                    location=candidate.get("location"),
                    language=candidate.get("language"),
                    board=candidate.get("board", ""),
                    source_url=candidate.get("source_url", ""),
                    description_snippet=candidate.get("description_snippet", ""),
                )
                if is_new:
                    new_job_ids.append(job_id)
            except Exception as exc:
                logger.warning(
                    "Could not upsert job '%s': %s",
                    candidate.get("title"),
                    exc,
                )

        # Update last_seen_at for already-known jobs
        for existing in existing_jobs:
            conn.execute(
                "UPDATE jobs SET last_seen_at = ? WHERE id = ?",
                (now_iso(), existing["id"]),
            )

        logger.info(
            json.dumps(
                {
                    "event": "f3_jobs_upserted",
                    "new_inserted": len(new_job_ids),
                    "existing_refreshed": len(existing_jobs),
                }
            )
        )

    except Exception as exc:
        logger.error(json.dumps({"event": "persist_failed", "error": str(exc)}))
        return 1

    # ---- Housekeeping --------------------------------------------------------
    try:
        expired_count = mark_expired(conn, window_days=config["digest_window_days"])
        logger.info(
            json.dumps({"event": "housekeeping_done", "expired": expired_count})
        )
    except Exception as exc:
        logger.warning("mark_expired failed: %s", exc)

    # ---- Stage G: Compose digest ---------------------------------------------
    html = ""
    included_job_ids: list[int] = []
    try:
        html, included_job_ids = render_digest_html(
            db_path,
            window_days=config["digest_window_days"],
            generated_at=now_iso(),
            degraded_boards=degraded_boards,
        )
        digest_path = tmp_dir / "digest.html"
        digest_path.write_text(html, encoding="utf-8")
        logger.info(
            json.dumps(
                {
                    "event": "digest_rendered",
                    "jobs_included": len(included_job_ids),
                    "path": str(digest_path),
                }
            )
        )
    except Exception as exc:
        logger.error(json.dumps({"event": "digest_failed", "error": str(exc)}))
        # Non-fatal: continue to send/skip decision

    # ---- Stage H: Send email -------------------------------------------------
    sent = False
    if args.send and not args.dry_run and html:
        today_str = _today_paris_str()
        subject = (
            f"PM/PO France — {len(included_job_ids)} openings — {today_str}"
        )
        try:
            success, err = send_digest(html, subject=subject)
            status = "sent" if success else "failed"
            log_notification(
                conn,
                run_id=run_id,
                recipient=resolved_recipient,
                job_ids=included_job_ids,
                status=status,
                error=err,
            )
            sent = success
            logger.info(
                json.dumps(
                    {
                        "event": "send_done",
                        "status": status,
                        "recipient": resolved_recipient,
                        "error": err,
                    }
                )
            )
        except Exception as exc:
            logger.error(json.dumps({"event": "send_error", "error": str(exc)}))
    else:
        reason = "dry_run" if args.dry_run else "send_flag_not_set"
        logger.info(json.dumps({"event": "send_skipped", "reason": reason}))

    # ---- Wrap-up -------------------------------------------------------------
    logger.info(
        json.dumps(
            {
                "event": "run_done",
                "run_id": run_id,
                "per_board": per_board_counts,
                "new_jobs": len(new_candidates),
                "degraded": degraded_boards,
                "sent": sent,
            }
        )
    )

    conn.close()
    return 0


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "French PM/PO Job Tracker — daily orchestrator. "
            "Runs once per day; idempotent (duplicate jobs suppressed via job_hash UNIQUE)."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--boards",
        metavar="BOARDS",
        default="",
        help=(
            "Comma-separated list of boards to scrape "
            "(wttj,indeed,apec,francetravail,google). "
            "Default: all boards enabled in config."
        ),
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Read from tests/fixtures/raw_<board>.json instead of live scraping.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Persist to DB but do NOT send the digest email (default behaviour).",
    )
    parser.add_argument(
        "--no-enrich",
        action="store_true",
        default=False,
        help="Skip Stage E (contact enrichment).",
    )
    parser.add_argument(
        "--no-resolve",
        action="store_true",
        default=False,
        help="Skip Stage D (SIRENE company resolution).",
    )
    parser.add_argument(
        "--send",
        action="store_true",
        default=False,
        help="Send the digest email. Required to actually send; without it, behaves as --dry-run.",
    )
    parser.add_argument(
        "--db",
        metavar="PATH",
        default="",
        help="Override SQLite DB path (default: JOB_TRACKER_DB_PATH env or config default_db_path).",
    )
    parser.add_argument(
        "--max-per-board",
        type=int,
        default=200,
        metavar="N",
        help="Cap raw results per board (default: 200).",
    )
    parser.add_argument(
        "--max-workers",
        type=int,
        default=4,
        metavar="N",
        help=(
            "Max parallel workers for Stage A board scraping "
            "(default: 4). Capped at the number of active boards."
        ),
    )
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # Default behaviour: dry-run unless --send is explicitly passed
    if not args.send:
        args.dry_run = True

    try:
        return run_pipeline(args)
    except Exception as exc:
        logger.error(json.dumps({"event": "unhandled_exception", "error": str(exc)}))
        return 1


if __name__ == "__main__":
    sys.exit(main())
