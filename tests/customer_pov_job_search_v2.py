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
KNOWN_SOURCES = {
    "france_travail", "wttj", "wttj_algolia", "apec",
    "linkedin_gmail", "linkedin_guest_api",
    "indeed_gmail", "hellowork_gmail", "jobgether_gmail",
    "fixture", "",
}


def check_role_tab(ws, failures: list[str]) -> None:
    """Assert per-role tab columns are aligned BY NAME — Contract holds contract
    values, Source holds source values, Link holds URLs."""
    name = ws.title
    header = ws.row_values(1)
    if not header:
        failures.append(f"{name}: header row is empty")
        return
    idx = {h: i for i, h in enumerate(header) if h}

    required = ["_id", "Contract", "Source", "Link", "Tier"]
    missing = [r for r in required if r not in idx]
    if missing:
        failures.append(f"{name}: missing required headers {missing}")
        return

    # Sample the latest 10 data rows.
    all_rows = ws.get_all_values()
    data = [r for r in all_rows[1:] if any(c.strip() for c in r)][-10:]
    if not data:
        # Empty role tab is allowed (e.g. AI Mobile until a match arrives).
        return

    for ri, row in enumerate(data):
        if len(row) <= max(idx[r] for r in required):
            failures.append(f"{name}: row {ri} too short to validate")
            continue

        contract = row[idx["Contract"]].strip()
        source = row[idx["Source"]].strip()
        link = row[idx["Link"]].strip()
        remote = row[idx.get("Remote?", -1)].strip() if "Remote?" in idx else ""
        notes = row[idx.get("Notes", -1)].strip() if "Notes" in idx else ""

        if contract not in VALID_CONTRACT:
            failures.append(
                f"{name}: row contains '{contract}' in Contract column — "
                f"expected one of {sorted(VALID_CONTRACT)}. Column-alignment likely broken."
            )
        if source not in KNOWN_SOURCES:
            failures.append(
                f"{name}: row contains '{source}' in Source column — "
                f"expected a JobSource enum value. Column-alignment likely broken."
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
        if "parse error" in notes.lower() or "no gemini_api_key" in notes.lower():
            failures.append(
                f"{name}: Notes column shows ranker-failure placeholder: {notes!r} — "
                f"ranker is dead in production"
            )


def check_top_matches(ws, failures: list[str]) -> None:
    header = ws.row_values(1)
    expected = {"Rank", "Fit", "Title", "Company", "Link"}
    missing = expected - set(header)
    if missing:
        failures.append(f"Top Matches: missing headers {sorted(missing)}")
        return

    all_rows = ws.get_all_values()
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
    all_rows = ws.get_all_values()
    if len(all_rows) < 5:
        failures.append(f"Summary: only {len(all_rows)} rows — dashboard not populated")
        return
    # Expect "Last Updated (UTC)" somewhere in column A and some numeric values.
    col_a = [r[0] if r else "" for r in all_rows]
    if not any("Last Updated" in v for v in col_a):
        failures.append("Summary: 'Last Updated' label missing — Summary tab not refreshed by this run")
    if not any("Total fetched" in v for v in col_a):
        failures.append("Summary: 'Total fetched' label missing")
    if not any("Tier A" in v for v in col_a):
        failures.append("Summary: 'Tier A' breakdown missing")


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
