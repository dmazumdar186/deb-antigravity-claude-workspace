"""
description: Main orchestrator for the job-search-sheet pipeline. Runs the full DAG (Stages 0-6): bootstrap + idempotency check, multi-source discovery via Adzuna+Jooble+FranceTravail, keyword filter, LLM relevance gate, dedup with Jaccard guard, sheet materialization with Status/Notes preservation.
inputs:  Optional CLI flags --mock, --dry-run, --title <name>, --geo <iso2>, --sheet-id <override>, --no-llm. Env vars: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH, ADZUNA_APP_*, JOOBLE_API_KEY, ANTHROPIC_API_KEY, GEMINI_API_KEY.
outputs: Writes the Google Sheet 'Job Applications' (6 visible tabs + _meta). Appends a run summary line to .tmp/job_search/job_search_runs.jsonl.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows._jt_utils import (  # noqa: E402
    compute_job_hash,
    normalize_company,
    normalize_title,
    now_iso,
    generate_run_id,
    setup_logging,
    load_json,
    save_json,
)
from execution.custom_scrapers.job_filter import filter_jobs  # noqa: E402
from execution.personal_workflows.job_search_llm_gate import classify_batch, GateVerdict  # noqa: E402
from execution.google.google_sheets_writer import (  # noqa: E402
    get_client,
    open_workbook,
    ensure_workbook_initialized,
    read_meta_last_run_at,
    write_meta_last_run_at,
    read_tab,
    write_tab,
)

# ---------------------------------------------------------------------------
# Top-level constants
# ---------------------------------------------------------------------------

CONFIG_PATH = PROJECT_ROOT / "config" / "job_search.json"
RUNS_LOG = PROJECT_ROOT / ".tmp" / "job_search" / "job_search_runs.jsonl"
MOCK_FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"

logger = setup_logging("job_search_sheet")

# ---------------------------------------------------------------------------
# Jaccard trigram helper
# ---------------------------------------------------------------------------


def _trigrams(text: str) -> set[str]:
    """Return the set of character trigrams for *text*."""
    t = text.lower()
    if len(t) < 3:
        return {t} if t else set()
    return {t[i : i + 3] for i in range(len(t) - 2)}


def _jaccard_trigram(a: str, b: str) -> float:
    """Jaccard similarity of two strings by character trigrams.

    Returns 0.0 if either (or both) inputs are empty — a missing snippet
    should never trigger an automatic merge; that is the dedup hash's job.
    """
    ta, tb = _trigrams(a), _trigrams(b)
    if not ta or not tb:
        return 0.0
    intersection = len(ta & tb)
    union = len(ta | tb)
    return intersection / union if union else 0.0


# ---------------------------------------------------------------------------
# Title assignment helper
# ---------------------------------------------------------------------------


def _assign_titles(job: dict, titles_config: dict) -> list[str]:
    """Return list of tab names this job matches via synonym substring check."""
    raw_title = job.get("title", "")
    norm = normalize_title(raw_title)
    matched: list[str] = []
    for title_key, title_cfg in titles_config.items():
        tab = title_cfg.get("tab", title_key)
        synonyms = title_cfg.get("synonyms", [])
        for syn in synonyms:
            if normalize_title(syn) in norm:
                matched.append(tab)
                break
    return matched


# ---------------------------------------------------------------------------
# Scraper dispatch helpers
# ---------------------------------------------------------------------------


def _load_mock_fixture(fixture_name: str) -> list[dict]:
    """Load a JSON fixture file and coerce it to a flat list of jobs."""
    path = MOCK_FIXTURES_DIR / fixture_name
    if not path.exists():
        logger.warning("Mock fixture not found: %s", path)
        return []
    raw = load_json(path)
    # Fixtures may be a dict {"results": [...]} or {"jobs": [...]} or a plain list
    if isinstance(raw, list):
        return raw
    for key in ("results", "jobs"):
        if key in raw and isinstance(raw[key], list):
            return raw[key]
    logger.warning("Unrecognised fixture structure in %s; returning []", fixture_name)
    return []


def _scrape_source(
    source: str,
    queries: list[str],
    geo: str,
    geo_cfg: dict,
    run_id: str,
    mock: bool,
) -> list[dict]:
    """Dispatch to the correct scraper (or fixture loader in --mock mode).

    Returns a list of RawJob dicts, each tagged with the geo's country code.
    """
    results: list[dict] = []

    if source == "adzuna":
        if mock:
            # Best-effort: load raw_adzuna_fr.json for FR; empty for others
            fixture = f"raw_adzuna_{geo.lower()}.json"
            results = _load_mock_fixture(fixture)
            logger.info("mock: adzuna(%s) → %d jobs from fixture", geo, len(results))
        else:
            try:
                import execution.custom_scrapers.adzuna_jobs as az  # noqa: PLC0415

                country_code = geo_cfg.get("adzuna_country", geo.lower())
                results = az.scrape(
                    queries=queries,
                    run_id=run_id,
                    country=country_code,
                )
            except Exception as exc:  # noqa: BLE001 — per-source fault isolation
                logger.warning("Stage 1: adzuna(%s) scrape failed: %s", geo, exc)
                return []

    elif source == "jooble":
        if mock:
            fixture = f"raw_jooble_{geo.lower()}.json"
            results = _load_mock_fixture(fixture)
            logger.info("mock: jooble(%s) → %d jobs from fixture", geo, len(results))
        else:
            try:
                import execution.custom_scrapers.jooble_jobs as jb  # noqa: PLC0415

                country_name = geo_cfg.get("jooble_country", geo)
                results = jb.scrape(
                    queries=queries,
                    run_id=run_id,
                    country=country_name,
                )
            except Exception as exc:  # noqa: BLE001 — per-source fault isolation
                logger.warning("Stage 1: jooble(%s) scrape failed: %s", geo, exc)
                return []

    # Tag each job with the geo's ISO2 country code (if not already set)
    for job in results:
        if not job.get("country"):
            job["country"] = geo.upper()

    return results


# ---------------------------------------------------------------------------
# Dedup logic
# ---------------------------------------------------------------------------


def _dedup_jobs(
    candidate_jobs: list[dict],
    jaccard_threshold: float = 0.4,
    snippet_chars: int = 200,
) -> list[dict]:
    """Dedup within a single run using hash + Jaccard guard.

    Hash = compute_job_hash(normalize_company, normalize_title, location).
    First-seen wins. On hash collision:
    - Jaccard trigram >= threshold → merge (append board to also_seen_on of winner).
    - Jaccard trigram < threshold → keep both as separate rows (append a numeric suffix
      to the second's dedup_hash to make it unique).

    Mutates jobs in-place by adding/updating 'dedup_hash' and 'also_seen_on' fields.
    Returns deduplicated list.
    """
    # Map: dedup_hash → job dict (winner)
    seen: dict[str, dict] = {}
    deduped: list[dict] = []

    for job in candidate_jobs:
        company = normalize_company(job.get("company_name", ""))
        title = normalize_title(job.get("title", ""))
        location = job.get("location") or ""
        h = compute_job_hash(company, title, location)

        snippet = (job.get("description_snippet") or "")[:snippet_chars]
        board = job.get("board", "")

        if h not in seen:
            job["dedup_hash"] = h
            job.setdefault("also_seen_on", [])
            seen[h] = job
            deduped.append(job)
        else:
            winner = seen[h]
            winner_snippet = (winner.get("description_snippet") or "")[:snippet_chars]
            similarity = _jaccard_trigram(snippet, winner_snippet)

            if similarity >= jaccard_threshold:
                # Same role — merge boards
                if board and board not in winner.get("also_seen_on", []):
                    winner.setdefault("also_seen_on", [])
                    winner["also_seen_on"].append(board)
                logger.debug(
                    "dedup: merged '%s' @ '%s' (Jaccard=%.2f) into winner from %s",
                    job.get("title"),
                    job.get("company_name"),
                    similarity,
                    winner.get("board"),
                )
            else:
                # Different roles at same (company, title, location) — keep both
                # Disambiguate by appending a suffix to the duplicate's hash
                suffix = 1
                new_hash = f"{h}_{suffix}"
                while new_hash in seen:
                    suffix += 1
                    new_hash = f"{h}_{suffix}"
                job["dedup_hash"] = new_hash
                job.setdefault("also_seen_on", [])
                seen[new_hash] = job
                deduped.append(job)
                logger.debug(
                    "dedup: kept distinct '%s' @ '%s' (Jaccard=%.2f, hash=%s)",
                    job.get("title"),
                    job.get("company_name"),
                    similarity,
                    new_hash,
                )

    return deduped


# ---------------------------------------------------------------------------
# Row materialisation helpers
# ---------------------------------------------------------------------------

_CONTRACT_TYPE_NORMALISE = {
    "cdi": "CDI",
    "cdd": "CDD",
    "freelance": "Freelance",
    "free-lance": "Freelance",
    "contract": "Contract",
    "permanent": "Permanent",
}


def _normalise_contract(raw: str | None) -> str:
    if not raw:
        return "Unknown"
    return _CONTRACT_TYPE_NORMALISE.get(raw.lower().strip(), raw)


def _build_sheet_row(
    job: dict,
    carry_forward: dict | None,
    now: str,
) -> list[str]:
    """Build a 14-element list in column order A-N.

    Columns: _id, First Seen, Posted, Company, Title, Country, Location,
             Remote?, Contract, Source, Also Seen On, Link, Status, Notes.

    If carry_forward is not None, Status/Notes/first_seen/also_seen_on are preserved.
    """
    dedup_hash = job.get("dedup_hash", "")

    # First Seen: preserve from carry-forward; fall back to raw_extracted_at; then today
    if carry_forward and carry_forward.get("first_seen"):
        first_seen = carry_forward["first_seen"]
    else:
        raw_ts = job.get("raw_extracted_at") or ""
        first_seen = raw_ts[:10] if len(raw_ts) >= 10 else now

    # Also Seen On: merge carry_forward boards + current_run boards
    cf_boards: list[str] = []
    if carry_forward:
        cf_boards = carry_forward.get("also_seen_on", [])
    current_boards: list[str] = job.get("also_seen_on", [])
    current_source = job.get("board", "")
    all_boards = sorted(set(cf_boards) | set(current_boards))
    also_seen_str = ", ".join(b for b in all_boards if b != current_source)

    # Status / Notes
    status = ""
    notes = ""
    if carry_forward:
        status = carry_forward.get("status", "")
        notes = carry_forward.get("notes", "")
    if not status:
        status = "New"

    # Contract: scraper-level wins; LLM gate only fills None values (applied upstream)
    contract = _normalise_contract(job.get("contract_type"))

    # Remote? heuristic
    location_raw = (job.get("location") or "").lower()
    snippet_raw = (job.get("description_snippet") or "").lower()
    if "remote" in location_raw or "télétravail" in location_raw or "full remote" in snippet_raw:
        remote = "Yes"
    elif "hybrid" in location_raw or "hybride" in location_raw:
        remote = "Hybrid"
    else:
        remote = "Unknown"

    return [
        dedup_hash,                                      # A: _id
        first_seen[:10],                                 # B: First Seen (date portion)
        (job.get("posted_at") or "")[:10],              # C: Posted
        job.get("company_name", ""),                     # D: Company
        job.get("title", ""),                            # E: Title
        job.get("country", ""),                          # F: Country
        job.get("location") or "",                       # G: Location
        remote,                                          # H: Remote?
        contract,                                        # I: Contract
        current_source,                                  # J: Source
        also_seen_str,                                   # K: Also Seen On
        job.get("source_url", ""),                       # L: Link
        status,                                          # M: Status
        notes,                                           # N: Notes
    ]


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------


def run_pipeline(args: argparse.Namespace) -> None:  # noqa: C901 — long but linear DAG
    """Execute the full 7-stage job-search-sheet DAG."""
    cfg = load_json(CONFIG_PATH)
    run_id = generate_run_id()
    run_start = datetime.now(timezone.utc)

    visible_tabs: list[str] = cfg["visible_tabs"]
    column_headers: list[str] = cfg["column_headers"]
    titles_config: dict = cfg["titles"]
    geos_config: dict = cfg["geos"]
    filter_config: dict = cfg["filter"]
    llm_gate_cfg: dict = cfg.get("llm_gate", {})
    dedup_cfg: dict = cfg.get("dedup", {})
    status_dropdown: list[str] = cfg.get("status_dropdown_values", [])

    # Sheet ID override
    sheet_id = args.sheet_id or os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sheet_id and not args.dry_run:
        logger.error("SHEETS_SPREADSHEET_ID not set and --sheet-id not provided.")
        sys.exit(1)

    # -----------------------------------------------------------------------
    # Stage 0: Bootstrap + idempotency
    # -----------------------------------------------------------------------
    logger.info("=== Stage 0: Bootstrap + idempotency ===")

    sp = None
    if not args.dry_run or sheet_id:
        try:
            sp = open_workbook(sheet_id)
            ensure_workbook_initialized(sp, visible_tabs, column_headers)
        except Exception as exc:  # noqa: BLE001 — surface clearly
            logger.error("Stage 0: failed to open/init workbook: %s", exc)
            if not args.dry_run:
                sys.exit(1)

    if sp:
        last_run_at = read_meta_last_run_at(sp)
        if last_run_at is not None:
            age = run_start - last_run_at
            idempotency_window = timedelta(hours=cfg.get("schedule", {}).get("idempotency_window_hours", 23))
            if age < idempotency_window:
                if args.dry_run:
                    logger.info(
                        "Stage 0: would exit (already ran %s ago < %sh window) — dry-run continues.",
                        age,
                        idempotency_window.total_seconds() / 3600,
                    )
                else:
                    logger.info(
                        "Stage 0: already ran %s ago (< %sh window). Exiting cleanly.",
                        age,
                        idempotency_window.total_seconds() / 3600,
                    )
                    print(f"Already ran today ({last_run_at.isoformat()}). Exiting.")
                    sys.exit(0)

    # Apply geo / title filters from CLI args
    active_geos: dict[str, dict] = {
        geo: gcfg
        for geo, gcfg in geos_config.items()
        if gcfg.get("phase") == "1a"  # Phase 1a only; 1b geos activated later
    }
    if args.geo:
        active_geos = {
            geo: gcfg
            for geo, gcfg in active_geos.items()
            if geo.upper() == args.geo.upper()
        }

    active_titles: dict[str, dict] = dict(titles_config)
    if args.title:
        # Match by key or by tab name
        active_titles = {
            k: v
            for k, v in titles_config.items()
            if k.lower() == args.title.lower() or v.get("tab", "").lower() == args.title.lower()
        }

    # -----------------------------------------------------------------------
    # Stage 1: Discover
    # -----------------------------------------------------------------------
    logger.info("=== Stage 1: Discover (%d geos × %d titles) ===", len(active_geos), len(active_titles))

    all_raw_jobs: list[dict] = []

    for geo, geo_cfg in active_geos.items():
        sources: list[str] = ["adzuna", "jooble"]

        for title_key, title_cfg in active_titles.items():
            queries = title_cfg.get("synonyms", [title_key])

            for source in sources:
                logger.info("Stage 1: %s / %s / %s", geo, title_key, source)
                batch = _scrape_source(source, queries, geo, geo_cfg, run_id, args.mock)
                # Tag with the title key that fetched them (for tab assignment later)
                for job in batch:
                    job.setdefault("_fetched_by_title", title_key)
                all_raw_jobs.extend(batch)

    logger.info("Stage 1: discovered %d raw jobs total.", len(all_raw_jobs))

    # -----------------------------------------------------------------------
    # Stage 2: Normalize + keyword-filter
    # -----------------------------------------------------------------------
    logger.info("=== Stage 2: Normalize + keyword-filter ===")

    candidate_jobs = filter_jobs(all_raw_jobs, filter_config)
    kept_candidates = [j for j in candidate_jobs if j.get("passed_filters")]
    logger.info(
        "Stage 2: %d → %d passed keyword filter (%d rejected).",
        len(all_raw_jobs),
        len(kept_candidates),
        len(candidate_jobs) - len(kept_candidates),
    )

    # -----------------------------------------------------------------------
    # Stage 2.5: LLM relevance gate
    # -----------------------------------------------------------------------
    logger.info("=== Stage 2.5: LLM relevance gate ===")

    after_llm: list[dict] = []
    llm_dropped = 0
    llm_irrelevant_log = PROJECT_ROOT / ".tmp" / "job_search" / run_id / "llm_irrelevant.jsonl"

    if args.no_llm:
        logger.info("Stage 2.5: --no-llm set; skipping LLM gate.")
        after_llm = kept_candidates
    else:
        max_jobs_gate = llm_gate_cfg.get("max_jobs_per_run", 200)
        primary_model = llm_gate_cfg.get("primary", "claude-haiku-4-5")
        failover_model = llm_gate_cfg.get("failover", "gemini-2.0-flash")

        verdicts: list[GateVerdict | None] = classify_batch(
            kept_candidates,
            max_jobs=max_jobs_gate,
            primary_model=primary_model,
            failover_model=failover_model,
        )

        contract_filter_geos: set[str] = {
            geo.upper()
            for geo, gcfg in active_geos.items()
            if gcfg.get("contract_filter") is not None
        }

        for job, verdict in zip(kept_candidates, verdicts):
            if verdict is None:
                # Exceeded cap — pass through without LLM classification
                after_llm.append(job)
                continue

            # Scraper-level contract_type wins; LLM fills only None values
            if job.get("contract_type") is None and verdict.contract_type is not None:
                job["contract_type"] = verdict.contract_type

            if verdict.relevance == "irrelevant":
                # Phase 1a: drop irrelevant rows entirely.
                # Phase 2 will add Archive range (rows 1000+); for now we just drop.
                # TODO(phase2): write irrelevant rows to Archive range instead of dropping.
                llm_dropped += 1
                logger.debug(
                    "Stage 2.5: dropped '%s' @ '%s' as irrelevant (%s)",
                    job.get("title"),
                    job.get("company_name"),
                    verdict.reason,
                )
                # Write to recovery log so users can inspect/restore LLM-dropped jobs
                llm_irrelevant_log.parent.mkdir(parents=True, exist_ok=True)
                with llm_irrelevant_log.open("a", encoding="utf-8") as _fh:
                    _fh.write(json.dumps({
                        "run_id": run_id,
                        "title": job.get("title"),
                        "company": job.get("company_name"),
                        "link": job.get("source_url"),
                        "verdict": {
                            "relevance": verdict.relevance,
                            "reason": verdict.reason,
                        },
                    }, default=str) + "\n")
                continue

            # CA/US contract_filter: after LLM fills contract_type, drop non-freelance/contract
            geo = (job.get("country") or "").upper()
            if geo in contract_filter_geos:
                ct = (job.get("contract_type") or "").lower()
                if ct not in {"contract", "freelance"}:
                    llm_dropped += 1
                    logger.debug(
                        "Stage 2.5: dropped '%s' — geo %s requires contract/freelance, got '%s'",
                        job.get("title"),
                        geo,
                        job.get("contract_type"),
                    )
                    continue

            after_llm.append(job)

        logger.info(
            "Stage 2.5: %d → %d after LLM gate (%d dropped: irrelevant or wrong contract).",
            len(kept_candidates),
            len(after_llm),
            llm_dropped,
        )

    # -----------------------------------------------------------------------
    # Stage 3: Dedup
    # -----------------------------------------------------------------------
    logger.info("=== Stage 3: Dedup ===")

    jaccard_threshold = dedup_cfg.get("jaccard_threshold", 0.4)
    snippet_chars = dedup_cfg.get("snippet_chars", 200)
    deduped_jobs = _dedup_jobs(after_llm, jaccard_threshold=jaccard_threshold, snippet_chars=snippet_chars)
    logger.info("Stage 3: %d → %d after dedup.", len(after_llm), len(deduped_jobs))

    # -----------------------------------------------------------------------
    # Stage 4: Read existing sheet → carry-forward map + user rows
    # -----------------------------------------------------------------------
    logger.info("=== Stage 4: Read existing sheet ===")

    # carry_forward_map[tab_name][dedup_hash] = {status, notes, also_seen_on, first_seen}
    carry_forward_map: dict[str, dict[str, dict]] = {}
    user_rows_map: dict[str, list[list[str]]] = {}

    if sp:
        for tab in visible_tabs:
            try:
                cf, ur = read_tab(sp, tab)
                # read_tab returns {hash: {first_seen, status, notes, also_seen_on}}
                # first_seen (col B) is preserved across runs — _build_sheet_row uses it.
                carry_forward_map[tab] = cf
                user_rows_map[tab] = ur
            except Exception as exc:  # noqa: BLE001 — tab read fail is non-fatal
                logger.warning("Stage 4: read_tab(%s) failed: %s", tab, exc)
                carry_forward_map[tab] = {}
                user_rows_map[tab] = []
    else:
        for tab in visible_tabs:
            carry_forward_map[tab] = {}
            user_rows_map[tab] = []

    # -----------------------------------------------------------------------
    # Stage 5: Materialize each title tab
    # -----------------------------------------------------------------------
    logger.info("=== Stage 5: Materialize ===")

    today_str = run_start.strftime("%Y-%m-%d")
    write_counts: dict[str, int] = {}
    dropped_no_tab_match = 0

    for tab in visible_tabs:
        # Find the title key(s) that map to this tab
        tab_title_keys = [k for k, v in titles_config.items() if v.get("tab") == tab]

        # Collect all synonyms for this tab's title keys
        tab_synonyms: list[str] = []
        for tk in tab_title_keys:
            tab_synonyms.extend(titles_config[tk].get("synonyms", []))

        # Assign jobs to this tab
        tab_jobs: list[dict] = []
        for job in deduped_jobs:
            # Check if any synonym appears in the normalised job title
            job_title_norm = normalize_title(job.get("title", ""))
            matched = any(normalize_title(syn) in job_title_norm for syn in tab_synonyms)
            if matched:
                tab_jobs.append(job)

        if not tab_jobs and not carry_forward_map.get(tab):
            logger.debug("Stage 5: tab '%s' → no jobs to write.", tab)
            write_counts[tab] = 0
            continue

        # Sort by first_seen desc (new jobs first)
        # For jobs not in carry-forward, first_seen = today
        def _sort_key(j: dict) -> str:
            h = j.get("dedup_hash", "")
            cf = carry_forward_map.get(tab, {}).get(h)
            if cf and cf.get("first_seen"):
                return cf["first_seen"]
            return today_str

        tab_jobs.sort(key=_sort_key, reverse=True)

        computed_rows: list[list[str]] = []
        for job in tab_jobs:
            h = job.get("dedup_hash", "")
            cf = carry_forward_map.get(tab, {}).get(h)
            row = _build_sheet_row(job, cf, today_str)
            computed_rows.append(row)

        user_added = user_rows_map.get(tab, [])
        write_counts[tab] = len(computed_rows)

        if args.dry_run:
            logger.info(
                "Stage 5 [dry-run]: tab '%s' → would write %d computed + %d user rows.",
                tab,
                len(computed_rows),
                len(user_added),
            )
            # Print preview of first 3 rows
            for row in computed_rows[:3]:
                print(f"  [{tab}] {row[4]!r} @ {row[3]!r} [{row[8]}] {row[11]}")
        else:
            if sp:
                try:
                    write_tab(sp, tab, column_headers, computed_rows, user_added, status_dropdown)
                    logger.info(
                        "Stage 5: tab '%s' → wrote %d computed + %d user rows.",
                        tab,
                        len(computed_rows),
                        len(user_added),
                    )
                except Exception as exc:  # noqa: BLE001 — tab write fail is non-fatal
                    logger.error("Stage 5: write_tab(%s) failed: %s", tab, exc)

    # Count jobs that passed all prior stages but matched no tab at all
    dropped_no_tab_match = sum(
        1 for job in deduped_jobs if not _assign_titles(job, titles_config)
    )
    logger.info(
        "Stage 5: %d jobs did not match any tab synonym (dropped)",
        dropped_no_tab_match,
    )

    # -----------------------------------------------------------------------
    # Stage 6: Update _meta + log + exit
    # -----------------------------------------------------------------------
    logger.info("=== Stage 6: Update _meta + log ===")

    if not args.dry_run and sp:
        try:
            write_meta_last_run_at(sp, run_start)
        except Exception as exc:  # noqa: BLE001 — meta update failure is non-fatal
            logger.error("Stage 6: write_meta_last_run_at failed: %s", exc)

    # Build run summary
    summary = {
        "run_id": run_id,
        "run_at": run_start.isoformat(),
        "dry_run": args.dry_run,
        "mock": args.mock,
        "no_llm": args.no_llm,
        "discovered": len(all_raw_jobs),
        "after_keyword_filter": len(kept_candidates),
        "after_llm_gate": len(after_llm),
        "llm_dropped": llm_dropped,
        "after_dedup": len(deduped_jobs),
        "dropped_no_tab_match": dropped_no_tab_match,
        "written_per_tab": write_counts,
    }

    RUNS_LOG.parent.mkdir(parents=True, exist_ok=True)
    with RUNS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(summary, default=str) + "\n")

    print(
        f"\nRun {run_id} complete:\n"
        f"  discovered={summary['discovered']}"
        f"  keyword-kept={summary['after_keyword_filter']}"
        f"  llm-dropped={summary['llm_dropped']}"
        f"  deduped={summary['after_dedup']}"
        f"  written={write_counts}"
    )


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Job-search-sheet pipeline orchestrator."
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Use fixture files instead of live API calls.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        dest="dry_run",
        help="Run the full DAG but skip Google Sheets writes; print what would be written.",
    )
    parser.add_argument(
        "--title",
        default=None,
        metavar="NAME",
        help="Restrict to one title tab (e.g. 'PM').",
    )
    parser.add_argument(
        "--geo",
        default=None,
        metavar="ISO2",
        help="Restrict to one geo (e.g. 'FR').",
    )
    parser.add_argument(
        "--sheet-id",
        default=None,
        dest="sheet_id",
        metavar="ID",
        help="Override SHEETS_SPREADSHEET_ID env var (for sandbox testing).",
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        dest="no_llm",
        help="Skip Stage 2.5 (LLM gate). Useful when quota is exhausted or for fast dry runs.",
    )
    return parser


if __name__ == "__main__":
    _args = _build_parser().parse_args()
    run_pipeline(_args)
