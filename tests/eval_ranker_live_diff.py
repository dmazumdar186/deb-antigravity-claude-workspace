"""
description: Pull recent jobs from the LIVE Google Sheet (Top Matches +
    selected role tabs) and re-score each with the NEW profile-grounded ranker.
    Print a side-by-side OLD-tier (from the sheet's Fit column) vs NEW-tier
    (from the heuristic OR LLM path), flag every flip, and summarize the delta.

    This is the operator's REAL data — no synthetic JDs. Limit: the sheet
    stores title + company + location + contract but NOT the full description.
    The new ranker therefore relies on title + minimal context for these
    comparisons, so skill_overlap will be lower than on real JDs. Treat this
    as a TITLE-FIT diff, not a full-ranker diff.

inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH (same as the
      customer-POV synthetic)
    - CLI: --max-rows N (default 30), --tabs TAB1,TAB2,...
      (default: "Top Matches,PM,AI PM")

outputs:
    - human-readable diff table on stdout (only flips shown)
    - JSON report at .tmp/job_search_v2/live_diff_<ts>.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(WORKSPACE_ROOT))

load_dotenv()
logger = logging.getLogger("eval.live_diff")

from execution.personal_workflows.job_search_v2.contracts import (  # noqa: E402
    ContractType, JobSource, NormalizedJob, RemoteMode, compute_content_hash,
)
from execution.personal_workflows.job_search_v2.ranker.score import (  # noqa: E402
    rank_jobs,
)

REPORT_DIR = WORKSPACE_ROOT / ".tmp" / "job_search_v2"


def _open_sheet():
    import gspread
    from google.oauth2.service_account import Credentials

    sa = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH",
                              "credentials/service_account.json"))
    sid = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sid:
        raise RuntimeError("SHEETS_SPREADSHEET_ID is not set in env")
    if not sa.exists():
        raise RuntimeError(f"service account JSON not found at {sa}")
    creds = Credentials.from_service_account_file(
        str(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"]
    )
    return gspread.authorize(creds).open_by_key(sid)


def _retry_429(fn, *, attempts: int = 4, base_delay: float = 12.0):
    last_exc = None
    for n in range(attempts):
        try:
            return fn()
        except Exception as exc:  # noqa: BLE001
            if "429" in str(exc) or "Quota exceeded" in str(exc):
                last_exc = exc
                time.sleep(base_delay * (n + 1))
                continue
            raise
    raise last_exc  # type: ignore[misc]


CONTRACT_MAP = {
    "cdi": ContractType.CDI, "freelance": ContractType.FREELANCE,
    "cdd": ContractType.CDD, "stage": ContractType.INTERNSHIP,
    "internship": ContractType.INTERNSHIP,
    "unknown": ContractType.UNKNOWN, "": ContractType.UNKNOWN,
}


def _row_to_normalized_job(row: dict) -> NormalizedJob | None:
    title = row.get("Title", "").strip()
    company = row.get("Company", "").strip()
    link = row.get("Link", "").strip() or "https://eval.test/none"
    if not title or not company:
        return None
    location = row.get("Location", "").strip() or "Unknown"
    contract_str = row.get("Contract", "").strip().lower()
    ct = CONTRACT_MAP.get(contract_str, ContractType.UNKNOWN)
    h = compute_content_hash(title, company, link)
    return NormalizedJob(
        source=JobSource.LINKEDIN_GUEST_API,
        source_id=h[:10],
        url=link if link.startswith("http") else "https://eval.test/none",
        canonical_url=link,
        title=title, company=company, location=location,
        # The sheet doesn't carry a description; pass the title as a
        # minimal stand-in so skill_overlap has *some* signal.
        description_snippet=title,
        posted_at=None,
        contract_type=ct, remote_mode=RemoteMode.UNKNOWN,
        fetched_at=datetime.now(timezone.utc),
        content_hash=h,
    )


def _pull_tab(sp, tab_name: str, max_rows: int) -> list[dict]:
    """Read up to max_rows from a tab. For Top Matches we also pull the Fit
    column; for role tabs there's no Fit (jobs there are tier-A/B by virtue
    of having been routed). For role tabs we synthesize Fit='B' as a
    placeholder so the diff is interpretable."""
    ws = _retry_429(lambda: sp.worksheet(tab_name))
    all_rows = _retry_429(lambda: ws.get_all_values())
    if not all_rows:
        return []
    header = all_rows[0]
    idx = {h: i for i, h in enumerate(header) if h}
    data_rows = [r for r in all_rows[1:] if any(c.strip() for c in r)]
    data_rows = data_rows[-max_rows:]  # most recent N

    out: list[dict] = []
    for r in data_rows:
        row = {}
        for h, i in idx.items():
            row[h] = r[i] if i < len(r) else ""
        if tab_name == "Top Matches":
            row["_old_fit"] = row.get("Fit", "").strip()
        else:
            row["_old_fit"] = "B"  # role tab placeholder
        row["_tab"] = tab_name
        out.append(row)
    return out


def _fold(t: str) -> str:
    """Same 3-class fold as eval_ranker_precision."""
    return "A" if t == "A" else ("SKIP" if t == "SKIP" else "B")


def main() -> int:
    logging.basicConfig(level=logging.INFO,
                        format="%(asctime)s %(name)s %(levelname)s %(message)s")
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[1].strip())
    parser.add_argument("--max-rows", type=int, default=30,
                        help="Rows per tab to pull (default 30)")
    parser.add_argument("--tabs", default="Top Matches,PM,AI PM",
                        help="Comma-separated tab names")
    args = parser.parse_args()

    sp = _open_sheet()
    tab_names = [t.strip() for t in args.tabs.split(",") if t.strip()]
    all_rows: list[dict] = []
    for tab in tab_names:
        try:
            rows = _pull_tab(sp, tab, args.max_rows)
            logger.info("pulled %d rows from %r", len(rows), tab)
            all_rows.extend(rows)
            time.sleep(1.5)
        except Exception as exc:  # noqa: BLE001
            logger.warning("could not pull %r: %s", tab, exc)

    if not all_rows:
        print("FAIL: no rows pulled from any tab")
        return 1

    # Build NormalizedJobs.
    jobs: list[NormalizedJob] = []
    job_to_row: dict[str, dict] = {}
    for r in all_rows:
        nj = _row_to_normalized_job(r)
        if nj is None:
            continue
        if nj.content_hash in job_to_row:
            continue  # dedup across tabs
        jobs.append(nj)
        job_to_row[nj.content_hash] = r

    print(f"Re-scoring {len(jobs)} unique rows with the NEW ranker "
          f"(Gemini may be quota-locked; profile-aware heuristic fallback "
          f"will run otherwise)...")
    ranked, stats = rank_jobs(jobs)
    print(f"Ranker stats: {stats}")

    flips_a_to_skip = 0
    flips_a_to_b = 0
    flips_b_to_a = 0
    flips_b_to_skip = 0
    same = 0
    rows_report: list[dict] = []
    for nj in jobs:
        row = job_to_row[nj.content_hash]
        old = _fold(row.get("_old_fit", "B"))
        rj = ranked.get(nj.content_hash)
        new = _fold(rj.tier.value) if rj else "SKIP"
        flip = f"{old}->{new}" if old != new else "same"
        if flip == "same":
            same += 1
        elif old == "A" and new == "SKIP":
            flips_a_to_skip += 1
        elif old == "A" and new == "B":
            flips_a_to_b += 1
        elif old == "B" and new == "A":
            flips_b_to_a += 1
        elif old == "B" and new == "SKIP":
            flips_b_to_skip += 1
        rows_report.append({
            "tab": row.get("_tab"),
            "title": row.get("Title", ""),
            "company": row.get("Company", ""),
            "location": row.get("Location", ""),
            "contract": row.get("Contract", ""),
            "old_fit": old,
            "new_tier": new,
            "new_score": rj.score if rj else 0.0,
            "flip": flip,
            "reasoning": rj.reasoning if rj else "(no ranker output)",
        })

    print("\n" + "=" * 78)
    print(f"LIVE SHEET DIFF — {len(jobs)} unique rows from "
          f"{', '.join(tab_names)}")
    print("=" * 78)
    print(f"  same                : {same}")
    print(f"  A -> SKIP (newly rejected)        : {flips_a_to_skip}")
    print(f"  A -> B    (downgraded)            : {flips_a_to_b}")
    print(f"  B -> A    (upgraded)              : {flips_b_to_a}")
    print(f"  B -> SKIP (newly rejected)        : {flips_b_to_skip}")
    print()

    flips = [r for r in rows_report if r["flip"] != "same"]
    if flips:
        print(f"Flips ({len(flips)} of {len(jobs)}):")
        print(f"  {'tab':<14}{'title':<40}{'old':>5}{'new':>5}{'score':>7}")
        for r in flips[:60]:
            t = r["title"][:37] + "..." if len(r["title"]) > 37 else r["title"]
            print(f"  {r['tab']:<14}{t:<40}{r['old_fit']:>5}{r['new_tier']:>5}"
                  f"{r['new_score']:>7.2f}")
            # one-line truncated reasoning
            print(f"      {r['reasoning'][:120]}...")
    else:
        print("(no flips — new ranker agrees with the sheet across the board)")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    report_path = REPORT_DIR / f"live_diff_{ts}.json"
    report_path.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "tabs_pulled": tab_names,
        "n_rows": len(jobs),
        "ranker_stats": stats,
        "summary": {
            "same": same,
            "A_to_SKIP": flips_a_to_skip,
            "A_to_B": flips_a_to_b,
            "B_to_A": flips_b_to_a,
            "B_to_SKIP": flips_b_to_skip,
        },
        "rows": rows_report,
    }, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nReport: {report_path.relative_to(WORKSPACE_ROOT)}")
    print("=" * 78)
    return 0


if __name__ == "__main__":
    sys.exit(main())
