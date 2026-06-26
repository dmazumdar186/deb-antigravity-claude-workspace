"""
description: Customer-POV synthetic for job_search_v2. Opens the LIVE Google Sheet
    and asserts cell-level correctness — column alignment, no placeholder ranker
    output, dashboards populated. The original front_door_*.sh only watched the
    pipeline run-log; this is the box-at-the-end-of-the-conveyor check that the
    front-door rule was supposed to be.
inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
outputs:
    - exit 0 if every assertion passes
    - exit 1 + per-assertion failure lines on stdout otherwise
"""

from __future__ import annotations

import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv


def _open_sheet():
    load_dotenv()
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore

    sa = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json"))
    sid = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sid:
        print("FAIL: SHEETS_SPREADSHEET_ID is not set")
        sys.exit(1)
    if not sa.exists():
        print(f"FAIL: service account JSON not found at {sa}")
        sys.exit(1)
    creds = Credentials.from_service_account_file(
        str(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds).open_by_key(sid)


VALID_REMOTE = {"Yes", "No", "Remote", "Hybrid", "Onsite", "Unknown", ""}
VALID_CONTRACT = {"CDI", "CDD", "Stage", "Freelance", "Internship", "Unknown", ""}


def _retry_429(fn, *, attempts: int = 3, base_delay: float = 6.0):
    """Call fn(); on a Sheets 429 (read-quota), sleep and retry. The synthetic opens
    8 tabs in ~4s right after the writer made ~50 calls, so the 60/min read quota is
    often saturated. One backoff is enough — quota refills per-minute."""
    last_exc = None
    for n in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001 — gspread surface; inspect message
            msg = str(exc)
            if "429" in msg or "Quota exceeded" in msg:
                last_exc = exc
                time.sleep(base_delay * (n + 1))
                continue
            raise
    raise last_exc  # type: ignore[misc]


def check_role_tab(ws, failures: list[str]) -> None:
    """Assert per-role tab columns are aligned BY NAME. Headers were trimmed
    2026-06-24 per operator request — STANDARD_HEADERS is now
    ['Company', 'Title', 'Country', 'Location', 'Contract', 'Link']; _id / Source
    / Tier / Notes / Remote? / Status are no longer written. Column alignment is
    still validated via Contract values + Link URL shape."""
    name = ws.title
    header = _retry_429(lambda: ws.row_values(1))
    if not header:
        failures.append(f"{name}: header row is empty")
        return
    idx = {h: i for i, h in enumerate(header) if h}

    required = ["Company", "Title", "Contract", "Link"]
    missing = [r for r in required if r not in idx]
    if missing:
        failures.append(f"{name}: missing required headers {missing}")
        return

    all_rows = _retry_429(lambda: ws.get_all_values())
    data = [r for r in all_rows[1:] if any(c.strip() for c in r)][-10:]
    if not data:
        return

    for ri, row in enumerate(data):
        if len(row) <= max(idx[r] for r in required):
            failures.append(f"{name}: row {ri} too short to validate")
            continue

        contract = row[idx["Contract"]].strip()
        link = row[idx["Link"]].strip()
        remote = row[idx.get("Remote?", -1)].strip() if "Remote?" in idx else ""

        if contract not in VALID_CONTRACT:
            failures.append(
                f"{name}: row contains '{contract}' in Contract column — "
                f"expected one of {sorted(VALID_CONTRACT)}. Column-alignment likely broken."
            )
        if "Remote?" in idx and remote not in VALID_REMOTE:
            failures.append(
                f"{name}: row contains '{remote}' in Remote? column — "
                f"expected one of {sorted(VALID_REMOTE)}."
            )
        if link and not (link.startswith("http://") or link.startswith("https://")):
            failures.append(
                f"{name}: Link column value is not a URL: {link[:60]!r}"
            )


def check_top_matches(ws, failures: list[str]) -> None:
    """Top Matches schema was trimmed 2026-06-24: dropped Rank (row order conveys
    it), Identity, and Why. Current TOP_MATCHES_HEADERS in the writer is
    ['Fit', 'Title', 'Company', 'Location', 'Contract', 'Source Tab', 'Link']."""
    header = _retry_429(lambda: ws.row_values(1))
    expected = {"Fit", "Title", "Company", "Link"}
    missing = expected - set(header)
    if missing:
        failures.append(f"Top Matches: missing headers {sorted(missing)}")
        return

    all_rows = _retry_429(lambda: ws.get_all_values())
    data = [r for r in all_rows[1:] if any(c.strip() for c in r)]
    if not data:
        failures.append("Top Matches: 0 data rows — dashboard not populated")
        return

    idx = {h: i for i, h in enumerate(header) if h}
    for ri, row in enumerate(data[:5]):
        link = row[idx["Link"]] if idx.get("Link", -1) < len(row) else ""
        if link and not (link.startswith("http://") or link.startswith("https://")):
            failures.append(f"Top Matches row {ri}: Link is not a URL: {link[:60]!r}")
        fit = row[idx["Fit"]] if idx.get("Fit", -1) < len(row) else ""
        if fit and fit not in {"A", "B", "C"}:
            failures.append(f"Top Matches row {ri}: Fit '{fit}' not in A/B/C")


def check_summary(ws, failures: list[str]) -> None:
    """Summary dashboard was rewritten 2026-06-24 to be human-readable. Anchors:
    'Last updated' (lowercase 'u' now), 'TODAY' section header, 'SOURCES TODAY'.
    The old 'Total fetched' / 'Tier A' labels live in the technical footer."""
    all_rows = _retry_429(lambda: ws.get_all_values())
    if len(all_rows) < 5:
        failures.append(f"Summary: only {len(all_rows)} rows — dashboard not populated")
        return
    col_a = [r[0] if r else "" for r in all_rows]
    if not any("Last updated" in v or "Last Updated" in v for v in col_a):
        failures.append("Summary: 'Last updated' label missing — Summary tab not refreshed by this run")
    if not any("TODAY" == v.strip() for v in col_a):
        failures.append("Summary: 'TODAY' section header missing")
    if not any("SOURCES TODAY" in v for v in col_a):
        failures.append("Summary: 'SOURCES TODAY' section missing")


def main() -> int:
    sp = _open_sheet()
    failures: list[str] = []
    role_tabs = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]

    for tab in role_tabs:
        try:
            check_role_tab(sp.worksheet(tab), failures)
        except Exception as exc:
            failures.append(f"{tab}: could not open ({exc})")

    try:
        check_top_matches(sp.worksheet("Top Matches"), failures)
    except Exception as exc:
        failures.append(f"Top Matches: could not open ({exc})")

    try:
        check_summary(sp.worksheet("Summary"), failures)
    except Exception as exc:
        failures.append(f"Summary: could not open ({exc})")

    if failures:
        print(f"CUSTOMER-POV SYNTHETIC: FAIL — {len(failures)} assertion(s) failed")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("CUSTOMER-POV SYNTHETIC: PASS — all role tabs aligned, Top Matches populated, Summary refreshed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
