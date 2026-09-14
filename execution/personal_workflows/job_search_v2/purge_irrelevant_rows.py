"""
description: Sheet hygiene — removes rows from each role tab + Top Matches
    whose Title fails the relevance gate (title_filter.classify_title) or the
    EN/FR language gate, and deletes retired tabs (the pre-2026-09-01
    AI Automation / AI Mobile / AI Process / AI Consultant tabs). Originally a
    one-shot cleanup; now also invoked by run.py before every sheet append so
    a filter-tightening (like the 2026-09-01 PM/PO-only rework) self-heals the
    live sheet on the next cron run instead of tripping the acceptance gate.
inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
    - CLI: --dry-run (preview), --tabs (subset), --keep-obsolete-tabs
outputs:
    - In-place rewrite of each tab keeping only relevant-title rows.
    - Deletion of retired tabs (unless --keep-obsolete-tabs / dry-run).
    - Stdout: per-tab kept/removed counts + sample removed titles.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve()
_WORKSPACE = _HERE.parents[3]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    canonicalize_url,
    compute_fingerprint,
)
from execution.personal_workflows.job_search_v2.normalizer.title_filter import classify_title  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.domain_filter import classify_domain  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.posting_verifier import (  # noqa: E402
    fetch_page, parse_posting_page, _is_listing_redirect,
)
from execution.personal_workflows.job_search_v2.profile import loader as _profile_loader  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.location_filter import load_config  # noqa: E402
from execution.personal_workflows.job_search_v2.notifier.sheet import (  # noqa: E402
    TOP_MATCHES_TAB,
    _col_index_to_letter,
    _open_sheet,
)

load_dotenv(find_dotenv(usecwd=False))
logger = logging.getLogger("purge_irrelevant_rows")

ROLE_TABS = ["PM", "AI PM", "PO", "AI PO"]

# Tabs retired by the 2026-09-01 PM/PO-only rework. Deleted outright (their
# engineer/consultant content is out of scope, per operator).
OBSOLETE_TABS = ["AI Automation", "AI Mobile", "AI Process", "AI Consultant"]


def _reject_location_patterns() -> list[str]:
    """config target_locations.reject_patterns_priority, lowercased. The purge
    must enforce the SAME location scope the acceptance gate checks — first
    live run of the PM/PO rework (2026-09-01, run 33534144028) failed exactly
    here: title/language purge left 175 historical Geneva/Switzerland rows in
    the PM tab, which the acceptance gate then (correctly) flagged."""
    try:
        cfg = load_config()
        return [p.lower() for p in cfg.get("target_locations", {}).get("reject_patterns_priority", [])]
    except Exception as exc:  # noqa: BLE001 — a broken config must not stop the
        # title/language purge; location enforcement just degrades to off and
        # the acceptance gate still catches any out-of-scope row downstream.
        logger.warning("purge: could not load location reject patterns: %s", exc)
        return []


def _purge_tab(ws, dry_run: bool) -> tuple[int, int, list[str]]:
    """Keep only rows whose Title passes the relevance gate. Returns
    (kept, removed, sample_removed_titles)."""
    all_rows = ws.get_all_values()
    if not all_rows:
        return 0, 0, []
    header = all_rows[0]
    idx = {h: i for i, h in enumerate(header) if h and h.strip()}
    title_i = idx.get("Title")
    if title_i is None:
        logger.warning("%s: no Title column — skipping", ws.title)
        return 0, 0, []
    loc_cols = [idx[c] for c in ("Country", "Location") if c in idx]
    reject_locs = _reject_location_patterns()

    data_rows = [r for r in all_rows[1:] if any(c.strip() for c in r)]
    kept_rows = []
    removed_titles = []
    for row in data_rows:
        title = row[title_i] if len(row) > title_i else ""
        rel_ok, _ = classify_title(title)
        lang_ok, _ = classify_language(title, "")
        # 2026-09-10: non-digital-product roles (hardware / electronics /
        # instrumentation / semiconductor / embedded …) fail the CURRENT gate
        # too, so historical rows self-heal on the next cron run.
        dom_ok, dom_reason = classify_domain(title, "", extra_anchors=_profile_loader.get_skip_domain_anchors())
        loc_hay = " ".join(row[i] for i in loc_cols if len(row) > i and row[i]).lower()
        loc_ok = not (loc_hay and any(p in loc_hay for p in reject_locs))
        if rel_ok and lang_ok and loc_ok and dom_ok:
            kept_rows.append(row)
        elif not dom_ok:
            removed_titles.append(f"{title} [{dom_reason}]")
        else:
            removed_titles.append(title if loc_ok else f"{title} [{loc_hay[:40]}]")

    removed = len(removed_titles)
    if dry_run or removed == 0:
        return len(kept_rows), removed, removed_titles[:5]

    n_cols = len(header)
    new_grid = [header] + kept_rows
    end_col = _col_index_to_letter(n_cols)
    # Clear the old body region then rewrite.
    old_last = len(all_rows)
    try:
        ws.batch_clear([f"A2:{end_col}{old_last}"])
    except Exception as exc:  # noqa: BLE001 — best-effort
        logger.warning("%s: clear failed: %s", ws.title, exc)
    if len(new_grid) > 1:
        ws.update(
            range_name=f"A1:{end_col}{len(new_grid)}",
            values=new_grid,
            value_input_option="USER_ENTERED",
        )
    return len(kept_rows), removed, removed_titles[:5]


class _UnionFind:
    """Minimal disjoint-set so rows connected by ANY of (_id, canonical Link,
    fingerprint) end up in the same duplicate group — e.g. row A and row B
    share a fingerprint, row B and row C share a Link, so A/B/C all group
    together even though A and C share neither key directly."""

    def __init__(self) -> None:
        self._parent: dict[int, int] = {}

    def find(self, x: int) -> int:
        self._parent.setdefault(x, x)
        while self._parent[x] != x:
            self._parent[x] = self._parent[self._parent[x]]
            x = self._parent[x]
        return x

    def union(self, a: int, b: int) -> None:
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self._parent[ra] = rb


def _read_tab_records(ws) -> list[dict]:
    """Read one tab's data rows into dicts carrying everything dedup_rows needs
    to group and rank duplicates: row_index (1-based sheet row), _id, link
    (canonicalized), fingerprint, status, first_seen, and the raw row values
    (for rewriting the tab)."""
    all_rows = ws.get_all_values()
    if not all_rows:
        return []
    header = all_rows[0]
    idx = {h: i for i, h in enumerate(header) if h and h.strip()}
    id_i = idx.get("_id")
    link_i = idx.get("Link")
    company_i = idx.get("Company")
    title_i = idx.get("Title")
    status_i = idx.get("Status")
    first_seen_i = idx.get("First Seen")

    def cell(row: list[str], i: int | None) -> str:
        return row[i].strip() if i is not None and len(row) > i else ""

    records = []
    for offset, row in enumerate(all_rows[1:]):
        if not any(c.strip() for c in row):
            continue
        row_index = offset + 2  # 1-based; +1 for header, +1 for 1-based
        raw_link = cell(row, link_i).lstrip("'")
        try:
            link = canonicalize_url(raw_link) if raw_link else ""
        except Exception:  # noqa: BLE001 — malformed URL already in the sheet; skip link-matching for this row
            link = ""
        title, company = cell(row, title_i), cell(row, company_i)
        fingerprint = compute_fingerprint(title, company) if title else ""
        records.append({
            "row_index": row_index,
            "row": row,
            "id": cell(row, id_i),
            "link": link,
            "fingerprint": fingerprint,
            "status": cell(row, status_i),
            "first_seen": cell(row, first_seen_i),
        })
    return records


def dedup_rows(sp, tabs: list[str] | None = None, dry_run: bool = False) -> dict:
    """Cross-tab exact/fuzzy duplicate purge: groups rows across ALL of `tabs`
    (default ROLE_TABS) by shared _id, canonical Link, or (Company, Title)
    fingerprint, and keeps exactly one row per group.

    Winner preference (highest wins):
      1. a non-empty Status (an operator edit — never silently discarded in
         favor of an untouched duplicate)
      2. earliest First Seen
      3. lowest row index (tab order in `tabs`, then row number)

    dry_run=True only computes and reports — no sheet writes.
    Returns {"removed_duplicates": int, "per_tab": {tab: removed_count}}.
    """
    import gspread  # type: ignore

    tabs = tabs or ROLE_TABS
    per_tab_records: dict[str, list[dict]] = {}
    for tab in tabs:
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            continue
        per_tab_records[tab] = _read_tab_records(ws)

    # Flat list of (tab, record) with a stable global order used as the final
    # tiebreak, and as the UnionFind node id.
    flat: list[tuple[str, dict]] = []
    for tab in tabs:
        for rec in per_tab_records.get(tab, []):
            flat.append((tab, rec))

    uf = _UnionFind()
    by_id: dict[str, int] = {}
    by_link: dict[str, int] = {}
    by_fp: dict[str, int] = {}
    for node, (_tab, rec) in enumerate(flat):
        for key_map, key in ((by_id, rec["id"]), (by_link, rec["link"]), (by_fp, rec["fingerprint"])):
            if not key:
                continue
            if key in key_map:
                uf.union(node, key_map[key])
            else:
                key_map[key] = node

    groups: dict[int, list[int]] = {}
    for node in range(len(flat)):
        groups.setdefault(uf.find(node), []).append(node)

    def rank(node: int) -> tuple[int, str, int]:
        _tab, rec = flat[node]
        has_status = 0 if rec["status"] else 1  # non-empty Status wins -> sorts first
        first_seen = rec["first_seen"] or "9999-99-99"  # empty sorts last
        return (has_status, first_seen, node)

    remove_nodes: set[int] = set()
    for nodes in groups.values():
        if len(nodes) < 2:
            continue
        winner = min(nodes, key=rank)
        for n in nodes:
            if n != winner:
                remove_nodes.add(n)

    per_tab_removed: dict[str, int] = {}
    per_tab_keep_rows: dict[str, list[list[str]]] = {t: [] for t in tabs}
    for node, (tab, rec) in enumerate(flat):
        if node in remove_nodes:
            per_tab_removed[tab] = per_tab_removed.get(tab, 0) + 1
        else:
            per_tab_keep_rows.setdefault(tab, []).append(rec["row"])

    total_removed = sum(per_tab_removed.values())
    if dry_run or total_removed == 0:
        return {"removed_duplicates": total_removed, "per_tab": per_tab_removed}

    # Rewrite each affected tab keeping only surviving rows, in original order
    # — same clear-then-rewrite pattern as _purge_tab, so indices never drift
    # (no row-by-row deletion, so "bottom-up" ordering concerns don't apply).
    for tab, removed in per_tab_removed.items():
        if removed == 0:
            continue
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            continue
        header = ws.row_values(1)
        if not header:
            continue
        kept_rows = per_tab_keep_rows.get(tab, [])
        n_cols = len(header)
        new_grid = [header] + kept_rows
        end_col = _col_index_to_letter(n_cols)
        old_last = max(ws.row_count, len(kept_rows) + 1)
        try:
            ws.batch_clear([f"A2:{end_col}{old_last}"])
        except Exception as exc:  # noqa: BLE001 — best-effort
            logger.warning("%s: dedup clear failed: %s", ws.title, exc)
        if len(new_grid) > 1:
            ws.update(
                range_name=f"A1:{end_col}{len(new_grid)}",
                values=new_grid,
                value_input_option="USER_ENTERED",
            )

    return {"removed_duplicates": total_removed, "per_tab": per_tab_removed}


# ---------------------------------------------------------------------------
# Re-verification of rows already on the sheet (2026-09-10).
#
# Operator complaint: ≥50% of sheet rows were expired / closed / months old.
# New rows are verified page-by-page in Stage 3.8 and carry a "Verified"
# stamp. Rows written BEFORE that stage exist have no stamp and unknown
# freshness — this pass opens each unstamped row's Link, reads the real
# posted date + liveness, and either stamps the row (Posted + Verified) or
# removes it (closed / older than max_age_days / undatable). Blocked hosts
# keep the row with an "unverified" stamp so a bot-block never wipes the sheet.
# Bounded per call (max_fetches) so a large backlog drains over a few runs.
# ---------------------------------------------------------------------------
STAMP_COL = "Verified"
POSTED_COL = "Posted"
DEFAULT_REVERIFY_MAX_FETCHES = 400


def _row_verdict(link: str, now, max_age_days: float, fetch) -> tuple[str, str, object]:
    """Return (decision, stamp, posted_date) for one existing sheet row.

    decision ∈ {"keep", "remove", "keep_unverified"}; stamp is the Verified
    cell text; posted_date is a datetime or None.
    """
    from execution.personal_workflows.job_search_v2.notifier.sheet import verification_stamp

    http_status, html, final_url = fetch(link)
    if http_status in (404, 410):
        return "remove", f"closed · http {http_status}", None
    blocked = http_status is None or http_status in (403, 429, 999) or (http_status and http_status >= 500)
    if blocked or not (html or "").strip():
        return "keep_unverified", verification_stamp("unverifiable", None, now, "ok_unverified_fresh"), None
    if _is_listing_redirect(final_url):
        return "remove", f"closed · redirect {final_url[:60]}", None
    verdict = parse_posting_page(html, final_url, now)
    if verdict.status == "closed":
        return "remove", f"closed · {verdict.evidence[:60]}", verdict.posted_at
    if verdict.posted_at is None:
        return "remove", "undatable", None
    age_days = (now - verdict.posted_at).total_seconds() / 86400.0
    if age_days > max_age_days:
        return "remove", f"stale · posted {verdict.posted_at.date().isoformat()} ({age_days:.0f}d)", verdict.posted_at
    return "keep", verification_stamp(verdict.status if verdict.status != "unknown" else "open",
                                       verdict.posted_at, now), verdict.posted_at


def reverify_rows(sp, tabs: list[str] | None = None, dry_run: bool = False, *,
                  max_age_days: float = 7.0, max_fetches: int = DEFAULT_REVERIFY_MAX_FETCHES,
                  concurrency: int = 6, only_unstamped: bool = True, fetch=fetch_page,
                  now=None) -> dict:
    """Open every (unstamped) row's Link; remove closed / stale / undatable rows,
    stamp the survivors. Returns {"checked", "removed", "stamped", "unverified",
    "remaining_unstamped", "per_tab", "sample_removed"}."""
    import gspread  # type: ignore
    from concurrent.futures import ThreadPoolExecutor
    from datetime import datetime, timezone
    from execution.personal_workflows.job_search_v2.notifier.sheet import _ensure_headers, STANDARD_HEADERS

    now = now or datetime.now(timezone.utc)
    stats: dict = {"checked": 0, "removed": 0, "stamped": 0, "unverified": 0,
                   "remaining_unstamped": 0, "per_tab": {}, "sample_removed": []}
    budget = max(0, int(max_fetches))
    for tab in (tabs or ROLE_TABS):
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            continue
        if not dry_run:
            _ensure_headers(ws, STANDARD_HEADERS)
        all_rows = ws.get_all_values()
        if not all_rows:
            continue
        header = list(all_rows[0])
        for col in (POSTED_COL, STAMP_COL):
            if col not in header:
                header.append(col)
        idx = {h: i for i, h in enumerate(header) if h and h.strip()}
        link_i, stamp_i, posted_i = idx.get("Link"), idx[STAMP_COL], idx[POSTED_COL]
        if link_i is None:
            continue
        width = len(header)
        rows = [list(r) + [""] * (width - len(r)) for r in all_rows[1:] if any(c.strip() for c in r)]

        todo = []
        for n, row in enumerate(rows):
            link = row[link_i].strip() if len(row) > link_i else ""
            stamped = bool(row[stamp_i].strip())
            if not link.startswith("http"):
                continue
            if only_unstamped and stamped:
                continue
            todo.append(n)
        stats["remaining_unstamped"] += max(0, len(todo) - budget)
        todo = todo[:budget]
        budget -= len(todo)

        verdicts: dict[int, tuple[str, str, object]] = {}
        if todo:
            with ThreadPoolExecutor(max_workers=max(1, concurrency)) as pool:
                for n, res in zip(todo, pool.map(lambda i: _row_verdict(rows[i][link_i].strip(), now, max_age_days, fetch), todo)):
                    verdicts[n] = res

        kept_rows, removed_here, stamped_here, unverified_here = [], [], 0, 0
        for n, row in enumerate(rows):
            v = verdicts.get(n)
            if v is None:
                kept_rows.append(row)
                continue
            decision, stamp, posted = v
            stats["checked"] += 1
            if decision == "remove":
                removed_here.append(f"{row[idx['Title']] if 'Title' in idx else ''} [{stamp}]")
                continue
            row[stamp_i] = stamp
            if posted is not None:
                row[posted_i] = posted.isoformat()[:10]
            if decision == "keep_unverified":
                unverified_here += 1
            else:
                stamped_here += 1
            kept_rows.append(row)

        stats["removed"] += len(removed_here)
        stats["stamped"] += stamped_here
        stats["unverified"] += unverified_here
        stats["per_tab"][tab] = {"checked": len(verdicts), "removed": len(removed_here),
                                 "stamped": stamped_here, "unverified": unverified_here}
        stats["sample_removed"].extend(removed_here[:5])
        logger.info("reverify %s: checked %d, removed %d, stamped %d, unverified %d",
                    tab, len(verdicts), len(removed_here), stamped_here, unverified_here)

        if dry_run or not verdicts:
            continue
        end_col = _col_index_to_letter(width)
        try:
            ws.batch_clear([f"A2:{end_col}{len(all_rows)}"])
        except Exception as exc:  # noqa: BLE001 — best-effort clear; the rewrite below still lands
            logger.warning("%s: clear failed: %s", ws.title, exc)
        ws.update(range_name=f"A1:{end_col}{len(kept_rows) + 1}", values=[header] + kept_rows,
                  value_input_option="USER_ENTERED")
    return stats


def purge_sheet(sp, tabs: list[str] | None = None, dry_run: bool = False,
                delete_obsolete: bool = True, dedup: bool = True,
                reverify: bool = True, max_age_days: float = 7.0,
                reverify_max_fetches: int = DEFAULT_REVERIFY_MAX_FETCHES) -> dict:
    """Purge irrelevant rows from `tabs` (default ROLE_TABS + Top Matches) and
    delete OBSOLETE_TABS. Callable from run.py (Stage 3.9 sheet hygiene).
    Returns {"removed_rows": int, "deleted_tabs": [..], "per_tab": {...},
    "removed_duplicates": int}."""
    import gspread  # type: ignore

    stats: dict = {"removed_rows": 0, "deleted_tabs": [], "per_tab": {}, "removed_duplicates": 0}
    for tab in (tabs or (ROLE_TABS + [TOP_MATCHES_TAB])):
        try:
            ws = sp.worksheet(tab)
        except gspread.WorksheetNotFound:
            continue
        kept, removed, sample = _purge_tab(ws, dry_run=dry_run)
        stats["removed_rows"] += removed
        stats["per_tab"][tab] = {"kept": kept, "removed": removed, "sample": sample}

    if dedup:
        # Cross-tab duplicate pass runs on ROLE_TABS specifically (Top Matches
        # is a derived dashboard, not a roster of record — deduping it is
        # meaningless since it's fully rewritten every run anyway).
        dedup_tabs = [t for t in (tabs or ROLE_TABS) if t != TOP_MATCHES_TAB]
        dedup_stats = dedup_rows(sp, tabs=dedup_tabs or ROLE_TABS, dry_run=dry_run)
        stats["removed_duplicates"] = dedup_stats["removed_duplicates"]
        stats["dedup_per_tab"] = dedup_stats["per_tab"]

    if reverify:
        # Liveness + freshness sweep of rows that pre-date Stage 3.8 (unstamped).
        rv_tabs = [t for t in (tabs or ROLE_TABS) if t != TOP_MATCHES_TAB]
        rv = reverify_rows(sp, tabs=rv_tabs or ROLE_TABS, dry_run=dry_run,
                           max_age_days=max_age_days, max_fetches=reverify_max_fetches)
        stats["reverify"] = rv
        stats["removed_rows"] += rv["removed"]

    if delete_obsolete and not dry_run:
        for tab in OBSOLETE_TABS:
            try:
                ws = sp.worksheet(tab)
            except gspread.WorksheetNotFound:
                continue
            try:
                sp.del_worksheet(ws)
                stats["deleted_tabs"].append(tab)
                logger.info("purge: deleted obsolete tab %r", tab)
            except Exception as exc:  # noqa: BLE001 — deletion is best-effort;
                # acceptance only audits ROLE_TABS, so a leftover obsolete tab
                # is cosmetic, not a gate failure. Log and continue.
                logger.warning("purge: could not delete obsolete tab %r: %s", tab, exc)
    return stats


def main() -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description="Purge irrelevant-title rows from job_search_v2 tabs.")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--tabs", default="")
    parser.add_argument("--keep-obsolete-tabs", action="store_true",
                        help="Skip deleting the retired AI Automation / Mobile / Process / Consultant tabs.")
    parser.add_argument("--dedup", action=argparse.BooleanOptionalAction, default=True,
                        help="Also run the cross-tab duplicate-row purge (default on; use --no-dedup to skip).")
    parser.add_argument("--reverify", action=argparse.BooleanOptionalAction, default=True,
                        help="Open each unstamped row's Link; remove closed / stale / undatable rows and "
                             "stamp the survivors (default on).")
    parser.add_argument("--max-age-days", type=float, default=7.0)
    parser.add_argument("--reverify-max-fetches", type=int, default=DEFAULT_REVERIFY_MAX_FETCHES)
    args = parser.parse_args()

    sp, err = _open_sheet(None, None)
    if sp is None:
        logger.error("Cannot open sheet: %s", err)
        return 1

    tabs = [t.strip() for t in args.tabs.split(",") if t.strip()] or None
    stats = purge_sheet(sp, tabs=tabs, dry_run=args.dry_run,
                        delete_obsolete=not args.keep_obsolete_tabs, dedup=args.dedup,
                        reverify=args.reverify, max_age_days=args.max_age_days,
                        reverify_max_fetches=args.reverify_max_fetches)

    tag = "[dry-run] " if args.dry_run else ""
    for tab, s in stats["per_tab"].items():
        print(f"{tag}{tab}: kept {s['kept']}, removed {s['removed']}")
        for t in s["sample"]:
            print(f"    removed e.g.: {t[:70]}")
    if stats["deleted_tabs"]:
        print(f"Deleted obsolete tabs: {', '.join(stats['deleted_tabs'])}")
    if args.dedup:
        print(f"{tag}Duplicate rows {'that would be removed' if args.dry_run else 'removed'}: {stats['removed_duplicates']}")
    if stats.get("reverify"):
        rv = stats["reverify"]
        print(f"{tag}Re-verified {rv['checked']} rows: removed {rv['removed']}, stamped {rv['stamped']}, "
              f"unverified {rv['unverified']}, still unstamped {rv['remaining_unstamped']}")
        for t in rv["sample_removed"][:10]:
            print(f"    removed e.g.: {t[:90]}")
    print(f"\nTotal {'would remove' if args.dry_run else 'removed'}: {stats['removed_rows']} irrelevant rows.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
