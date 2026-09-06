"""
description: Write job_digest results to the friend's own Google Sheet — one
    tab per role title, plus a rebuilt "Top Matches" and a "Summary" tab.
inputs:
    - pairs: list[tuple[NormalizedJob, RankedJob]] for this run.
    - profile: Profile (role titles name the tabs; profile.sheet.enabled gates
      whether run.py calls this module at all).
    - spreadsheet_id: str, service_account_path: Path.
outputs:
    - write_jobs() -> str | None: the Sheet's edit URL on success, or None if
      sheet.enabled is effectively off / credentials are missing (soft-fail —
      never raised for missing config, only for a write actually attempted
      and failing, which raises SheetError so run.py can map it to exit 6).

Ported pattern from the operator's internal job pipeline (column-by-NAME writer,
formula-injection defuse) but deliberately smaller: one tab per profile role
(not a title-routing table), append-only dedup on content_hash (the row ID),
and a fixed column list rather than a config-driven header set. No imports
from the operator's internal pipeline — this package stays isolated per the
module docstring in ../__init__.py.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..contracts import JobTier, NormalizedJob, RankedJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.notifier.sheet")

_REQUEST_TIMEOUT_SECONDS = 60

COLUMNS = [
    "Date", "Tier", "Score", "Title", "Company", "Location", "Country",
    "Contract", "Remote", "Source", "URL", "Reasoning", "ID",
]
_ID_COL_INDEX = COLUMNS.index("ID") + 1  # 1-based

TOP_MATCHES_TAB = "Top Matches"
SUMMARY_TAB = "Summary"
_TOP_MATCHES_WINDOW_DAYS = 14

# Sheets treats a leading =/+/-/@ as a formula trigger under USER_ENTERED.
# Job text is untrusted external input, so every cell gets this defuse before
# being written — a single leading apostrophe forces text interpretation
# without breaking URL auto-hyperlinking or date parsing on legitimate cells.
_FORMULA_TRIGGER_CHARS = ("=", "+", "-", "@")


class SheetError(RuntimeError):
    """Raised when a Sheet write is attempted and fails (auth, quota, API)."""


def _defuse_formula(value: str) -> str:
    if value and value[0] in _FORMULA_TRIGGER_CHARS:
        return "'" + value
    return value


def _col_letter(idx: int) -> str:
    """1-based column index -> A1 letter (1->A, 27->AA)."""
    s = ""
    while idx > 0:
        idx, r = divmod(idx - 1, 26)
        s = chr(65 + r) + s
    return s


def _country_for(job: NormalizedJob, profile: Profile) -> str:
    """First profile-selected country whose registry.Country.matches() the
    job's location, else "" (unknown / no selected country matched)."""
    for country in profile.countries:
        if country.matches(job.location, job.description_snippet[:300]):
            return country.iso2
    return ""


def _row_for(job: NormalizedJob, ranked: RankedJob, run_date: str, profile: Profile) -> list[str]:
    values = {
        "Date": run_date,
        "Tier": ranked.tier.value,
        "Score": f"{ranked.score:.3f}",
        "Title": job.title,
        "Company": job.company,
        "Location": job.location,
        "Country": _country_for(job, profile),
        "Contract": job.contract_type.value,
        "Remote": job.remote_mode.value,
        "Source": job.source.value,
        "URL": str(job.url),
        "Reasoning": ranked.reasoning,
        "ID": job.content_hash,
    }
    return [_defuse_formula(str(values[c])) for c in COLUMNS]


def _short_id(spreadsheet_id: str) -> str:
    """H2: never let a full spreadsheet id land in an exception message that
    could be logged/serialized (summary.json, run_log.jsonl) — just enough of
    a prefix to eyeball which sheet without leaking the whole (sensitive) id.
    """
    return f"{spreadsheet_id[:4]}…" if spreadsheet_id else "<empty>"


def _open_client(spreadsheet_id: str, service_account_path: Path | str):
    """Authenticate and return the gspread Spreadsheet. Raises SheetError on any failure."""
    # C1: run.py may still hand us a str (env var default is a str) — coerce
    # defensively here too so `.exists()` below never raises AttributeError.
    service_account_path = Path(service_account_path)

    try:
        import gspread  # type: ignore
        from google.oauth2.service_account import Credentials  # type: ignore
    except ImportError as exc:
        raise SheetError(f"gspread / google-auth not installed: {exc}") from exc

    if not service_account_path.exists():
        raise SheetError(f"service account JSON not found at {service_account_path}")

    try:
        creds = Credentials.from_service_account_file(
            str(service_account_path),
            scopes=["https://www.googleapis.com/auth/spreadsheets"],
        )
        client = gspread.authorize(creds)
        try:
            client.set_timeout(_REQUEST_TIMEOUT_SECONDS)  # gspread >= 6.x
        except AttributeError:
            # Older gspread — no per-client timeout knob available; the
            # request still goes through, just without our explicit cap.
            logger.warning("notifier.sheet: gspread has no set_timeout (old version); using library default")
        return client.open_by_key(spreadsheet_id)
    except Exception as exc:  # noqa: BLE001 — auth/open surface from gspread+google-auth
        raise SheetError(f"could not open spreadsheet {_short_id(spreadsheet_id)}: {exc}") from exc


def _get_or_create_tab(spreadsheet, title: str, *, cols: list[str]):
    import gspread  # type: ignore

    try:
        ws = spreadsheet.worksheet(title)
    except gspread.WorksheetNotFound:
        ws = spreadsheet.add_worksheet(title=title, rows="1000", cols=str(max(len(cols), 2)))
        ws.update(
            range_name=f"A1:{_col_letter(len(cols))}1",
            values=[cols],
            value_input_option="USER_ENTERED",
        )
        logger.info("notifier.sheet: created tab %r with headers", title)
        return ws

    # Tab exists — make sure the header row matches; if blank, seed it.
    header = ws.row_values(1)
    if not header:
        ws.update(
            range_name=f"A1:{_col_letter(len(cols))}1",
            values=[cols],
            value_input_option="USER_ENTERED",
        )
    return ws


def _existing_ids(ws) -> set[str]:
    try:
        col = ws.col_values(_ID_COL_INDEX)
    except Exception as exc:  # noqa: BLE001 — best-effort read; treat as empty on failure
        logger.warning("notifier.sheet: could not read existing IDs from %s: %s", ws.title, exc)
        return set()
    return {v.strip() for v in col[1:] if v and v.strip()}


def _append_rows(spreadsheet, tab: str, rows: list[list[str]], dedup_ids: list[str]) -> int:
    """Append rows to `tab`, skipping any whose ID already exists there."""
    if not rows:
        return 0
    ws = _get_or_create_tab(spreadsheet, tab, cols=COLUMNS)
    existing = _existing_ids(ws)
    fresh_rows = [r for r, i in zip(rows, dedup_ids) if i not in existing]
    if not fresh_rows:
        return 0
    try:
        all_values = ws.get_all_values()
        start_row = len(all_values) + 1
        end_row = start_row + len(fresh_rows) - 1
        end_col = _col_letter(len(COLUMNS))
        if ws.row_count < end_row:
            ws.resize(rows=end_row + 100, cols=ws.col_count)
        ws.update(
            range_name=f"A{start_row}:{end_col}{end_row}",
            values=fresh_rows,
            value_input_option="USER_ENTERED",
        )
    except Exception as exc:  # noqa: BLE001 — gspread/Sheets API surface
        raise SheetError(f"append to tab {tab!r} failed: {exc}") from exc
    return len(fresh_rows)


def _posted_at_utc(job: NormalizedJob) -> datetime | None:
    """job.posted_at, coerced to an aware UTC datetime if a source adapter's
    own tz handling slipped and left it naive (N3b) — otherwise a naive-vs-
    aware comparison against `cutoff` in _rebuild_top_matches would raise and
    either drop the row silently or crash the whole rebuild.
    """
    posted_at = job.posted_at
    if posted_at is not None and posted_at.tzinfo is None:
        posted_at = posted_at.replace(tzinfo=timezone.utc)
    return posted_at


def _rebuild_top_matches(
    spreadsheet, pairs: list[tuple[NormalizedJob, RankedJob]], run_date: str, profile: Profile
) -> None:
    """Rebuild the Top Matches tab from scratch with tier-A rows of the last
    14 days. This run's tier-A rows are always included; older rows persisted
    from prior runs are NOT read back in (this module has no cross-run store
    of its own — seen.json / state ownership lives in normalizer/state.py) so
    the window in practice covers "this run's tier-A rows", which is what
    run.py has in hand. Kept as a distinct rebuild step (not append) so a
    profile change that drops a role cleanly clears its old Top Matches rows
    on the next run.
    """
    ws = _get_or_create_tab(spreadsheet, TOP_MATCHES_TAB, cols=COLUMNS)
    cutoff = datetime.now(timezone.utc) - timedelta(days=_TOP_MATCHES_WINDOW_DAYS)

    top_pairs = [
        (job, ranked)
        for job, ranked in pairs
        if ranked.tier == JobTier.A and ((pa := _posted_at_utc(job)) is None or pa >= cutoff)
    ]
    # Sort by the NUMERIC score before formatting — sorting the already-
    # formatted "%.3f" string happens to agree for this value range, but
    # sorting the number itself is the actually-correct operation.
    top_pairs.sort(key=lambda pair: pair[1].score, reverse=True)
    top_rows = [_row_for(job, ranked, run_date, profile) for job, ranked in top_pairs]

    try:
        end_col = _col_letter(len(COLUMNS))
        ws.batch_clear([f"A2:{end_col}{max(ws.row_count, len(top_rows) + 5)}"])
        if top_rows:
            end_row = 1 + len(top_rows)
            if ws.row_count < end_row:
                ws.resize(rows=end_row + 20, cols=ws.col_count)
            ws.update(range_name=f"A2:{end_col}{end_row}", values=top_rows, value_input_option="USER_ENTERED")
    except Exception as exc:  # noqa: BLE001 — Top Matches is a convenience view; log, don't fail the run
        logger.warning("notifier.sheet: rebuild Top Matches failed: %s", exc)


def _rebuild_summary(spreadsheet, stats: dict, run_date: str) -> None:
    ws = _get_or_create_tab(spreadsheet, SUMMARY_TAB, cols=["Metric", "Value"])
    try:
        ws.batch_clear([f"A2:B{max(ws.row_count, 60)}"])
        rows: list[list[str]] = [["Last run", run_date]]
        for key, value in stats.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    rows.append([_defuse_formula(f"{key}.{sub_key}"), _defuse_formula(str(sub_value))])
            else:
                rows.append([_defuse_formula(str(key)), _defuse_formula(str(value))])
        end_row = 1 + len(rows)
        if ws.row_count < end_row:
            ws.resize(rows=end_row + 20, cols=max(ws.col_count, 2))
        ws.update(range_name=f"A2:B{end_row}", values=rows, value_input_option="USER_ENTERED")
    except Exception as exc:  # noqa: BLE001 — Summary is a convenience view; log, don't fail the run
        logger.warning("notifier.sheet: rebuild Summary failed: %s", exc)


def write_jobs(
    pairs: list[tuple[NormalizedJob, RankedJob]],
    profile: Profile,
    spreadsheet_id: str,
    service_account_path: Path | str,
    *,
    stats: dict | None = None,
) -> str | None:
    """Write this run's jobs to the friend's Sheet. Returns the Sheet's edit URL.

    Returns None (soft-fail, no exception) only when sheet writing is not
    configured for this run (empty spreadsheet_id). Any write actually
    attempted that fails raises SheetError.
    """
    if not spreadsheet_id:
        logger.info("notifier.sheet: no spreadsheet_id configured — skipping")
        return None

    spreadsheet = _open_client(spreadsheet_id, service_account_path)
    run_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    by_role_title: dict[str, list[tuple[NormalizedJob, RankedJob]]] = {r.title: [] for r in profile.roles}
    fallback_title = profile.roles[0].title
    for job, ranked in pairs:
        # Route by the role keyword the title actually matches; default to
        # the first role if none of the role titles/synonyms appear (should
        # be rare — the acceptance gate already requires a keyword match).
        placed = False
        title_lower = job.title.lower()
        for role in profile.roles:
            if any(t.lower() in title_lower for t in role.all_titles):
                by_role_title[role.title].append((job, ranked))
                placed = True
                break
        if not placed:
            by_role_title[fallback_title].append((job, ranked))

    for role_title, role_pairs in by_role_title.items():
        rows = [_row_for(job, ranked, run_date, profile) for job, ranked in role_pairs]
        ids = [job.content_hash for job, _ in role_pairs]
        written = _append_rows(spreadsheet, role_title, rows, ids)
        logger.info("notifier.sheet: wrote %d/%d rows to tab %r", written, len(rows), role_title)

    _rebuild_top_matches(spreadsheet, pairs, run_date, profile)
    _rebuild_summary(spreadsheet, stats or {}, run_date)

    return f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}/edit"
