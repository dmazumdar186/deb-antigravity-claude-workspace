"""
description: Comprehensive end-to-end synthetic for job_search_v2. Opens the LIVE
    Google Sheet, reads the local run log, and checks 8 dimensions:
        A. Cell-level column alignment (Contract holds contract, Source holds source...)
        B. Sheet freshness (Summary Last-Updated <25h, recent First-Seen dates)
        C. Source diversity (latest run had >=2 sources contributing)
        D. Ranker health (scored>0 or heuristic-tier-diversity ok)
        E. Dashboard integrity (Top Matches has data, Summary has rows)
        F. Cross-day dedup behavior (already_seen>0 once warm; new<total)
        G. Sheet vs run-log consistency (PM row count >= reported per_tab_totals)
        H. No silent failures (sheet_ok, summary_ok, email handled)
inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
    - .tmp/job_search_v2/run_log.jsonl (if present)
outputs:
    - human-readable PASS/FAIL/WARN report on stdout
    - exit 0 if all PASS; exit 1 if any FAIL; WARN does not fail
"""

from __future__ import annotations

import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv

VALID_REMOTE = {"Yes", "No", "Remote", "Hybrid", "Onsite", "Unknown", ""}
VALID_CONTRACT = {"CDI", "CDD", "Stage", "Freelance", "Internship", "Unknown", ""}
KNOWN_SOURCES = {
    "france_travail", "wttj", "wttj_algolia", "apec",
    "linkedin_gmail", "linkedin_guest_api",
    "indeed_gmail", "hellowork_gmail", "jobgether_gmail",
    "fixture", "",
}
ROLE_TABS = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]

PLACEHOLDER_RX = re.compile(r"(parse error|no GEMINI_API_KEY|ranker unavailable)", re.IGNORECASE)


@dataclass
class Check:
    name: str
    severity: str  # PASS | FAIL | WARN | INFO
    detail: str = ""


@dataclass
class Report:
    checks: list[Check] = field(default_factory=list)

    def add(self, name: str, severity: str, detail: str = "") -> None:
        self.checks.append(Check(name, severity, detail))

    def fail(self, name: str, detail: str) -> None:
        self.add(name, "FAIL", detail)

    def warn(self, name: str, detail: str) -> None:
        self.add(name, "WARN", detail)

    def passed(self, name: str, detail: str = "") -> None:
        self.add(name, "PASS", detail)

    def info(self, name: str, detail: str) -> None:
        self.add(name, "INFO", detail)

    @property
    def failures(self) -> list[Check]:
        return [c for c in self.checks if c.severity == "FAIL"]

    @property
    def warnings(self) -> list[Check]:
        return [c for c in self.checks if c.severity == "WARN"]


def _open_sheet():
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
    sa = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json"))
    sid = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sid or not sa.exists():
        return None
    creds = Credentials.from_service_account_file(str(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(sid)


def _last_run_summary() -> dict | None:
    log = Path(".tmp/job_search_v2/run_log.jsonl")
    if not log.exists():
        return None
    last = None
    for line in log.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            last = json.loads(line)
        except json.JSONDecodeError:
            continue
    return last


# ---------- A. Column alignment ----------

def _snapshot_role_tabs(sp) -> dict[str, list[list[str]]]:
    """Read every role tab once; return {tab: rows}. Halves the API call count
    (vs reading the same tab in 2 different checks) and dodges per-minute throttles."""
    out: dict[str, list[list[str]]] = {}
    for tab in ROLE_TABS:
        try:
            ws = sp.worksheet(tab)
            out[tab] = ws.get_all_values()
        except Exception:
            out[tab] = []
    return out


def check_alignment(snapshots: dict[str, list[list[str]]], report: Report) -> None:
    """For each role tab: assert Contract/Source/Remote?/Link/Notes cells hold the
    right kind of value. Catches positional shifts and ranker-failure leakage."""
    bad_tabs: list[str] = []
    for tab in ROLE_TABS:
        all_rows = snapshots.get(tab) or []
        if not all_rows:
            report.warn(f"alignment[{tab}]", "tab unreadable or empty (transient quota?)")
            continue
        header = all_rows[0] if all_rows else []
        idx = {h: i for i, h in enumerate(header) if h}
        if "_id" not in idx or "Contract" not in idx or "Source" not in idx or "Link" not in idx:
            report.fail(f"alignment[{tab}]", f"missing canonical headers (got {header})")
            bad_tabs.append(tab)
            continue
        data = [r for r in all_rows[1:] if any(c.strip() for c in r)][-10:]
        if not data:
            continue
        violations = []
        for row in data:
            if len(row) <= max(idx.get(k, 0) for k in ("Contract", "Source", "Link")):
                violations.append("row too short")
                continue
            contract = row[idx["Contract"]].strip()
            source = row[idx["Source"]].strip()
            link = row[idx["Link"]].strip()
            notes = row[idx.get("Notes", -1)].strip() if "Notes" in idx else ""
            remote = row[idx.get("Remote?", -1)].strip() if "Remote?" in idx else ""

            if contract and contract not in VALID_CONTRACT:
                violations.append(f"Contract='{contract}' not in enum")
            if source and source not in KNOWN_SOURCES:
                violations.append(f"Source='{source}' not in enum")
            if remote and remote not in VALID_REMOTE:
                violations.append(f"Remote?='{remote}' not in enum")
            if link and not (link.startswith("http://") or link.startswith("https://")):
                violations.append(f"Link not URL: {link[:30]}...")
            if notes and PLACEHOLDER_RX.search(notes):
                violations.append(f"Notes shows ranker failure: {notes[:40]}...")
        if violations:
            report.fail(f"alignment[{tab}]", "; ".join(sorted(set(violations))[:3]))
            bad_tabs.append(tab)
    if not bad_tabs:
        report.passed("A. column alignment", f"{len(ROLE_TABS)} role tabs aligned")


# ---------- B. Freshness ----------

def check_freshness(sp, report: Report, last_run: dict | None, pm_snapshot: list[list[str]]) -> None:
    """Summary 'Last Updated' within 25h; at least one role tab has rows with
    First Seen <= 2 days ago."""
    try:
        sm = sp.worksheet("Summary")
        rows = sm.get_all_values()
    except Exception as exc:
        report.fail("B. summary freshness", f"cannot open Summary: {exc}")
        return

    last_updated_str = ""
    for r in rows:
        if r and "Last Updated" in (r[0] or ""):
            last_updated_str = r[1] if len(r) > 1 else ""
            break

    if not last_updated_str:
        report.fail("B. summary freshness", "no 'Last Updated' row in Summary")
    else:
        try:
            ts = datetime.fromisoformat(last_updated_str.replace("Z", "+00:00"))
            age_h = (datetime.now(timezone.utc) - ts).total_seconds() / 3600
            if age_h > 25:
                report.fail("B. summary freshness", f"Summary last updated {age_h:.1f}h ago (>25h)")
            else:
                report.passed("B. summary freshness", f"Summary updated {age_h:.1f}h ago")
        except ValueError as exc:
            report.warn("B. summary freshness", f"could not parse Last Updated '{last_updated_str}': {exc}")

    # Check First Seen dates on PM tab (reuse cached snapshot)
    pm_rows = pm_snapshot
    if not pm_rows:
        report.warn("B. PM First Seen check", "PM snapshot empty (transient?)")
        return
    header = pm_rows[0]
    fs_idx = header.index("First Seen") if "First Seen" in header else None
    if fs_idx is None:
        report.warn("B. PM First Seen check", "no 'First Seen' header found")
        return
    body = [r for r in pm_rows[1:] if any(c.strip() for c in r)]
    recent_dates = set()
    cutoff = (datetime.now(timezone.utc) - timedelta(days=3)).date()
    for r in body[-30:]:
        if len(r) <= fs_idx:
            continue
        try:
            d = datetime.strptime(r[fs_idx], "%Y-%m-%d").date()
            if d >= cutoff:
                recent_dates.add(d.isoformat())
        except (ValueError, IndexError):
            continue
    if not recent_dates:
        report.fail("B. PM recent rows", f"no rows with First Seen in the last 3 days (cutoff {cutoff})")
    else:
        report.passed("B. PM recent rows", f"rows seen on {sorted(recent_dates)}")


# ---------- C. Source diversity ----------

def check_source_diversity(report: Report, last_run: dict | None) -> None:
    if not last_run:
        report.warn("C. source diversity", "no local run_log.jsonl; cannot verify")
        return
    per_source = last_run.get("per_source", {}) or {}
    nonzero = [s for s, n in per_source.items() if n and n > 0]
    if len(nonzero) >= 2:
        report.passed("C. source diversity", f"{len(nonzero)} sources contributed: {sorted(nonzero)}")
    elif len(nonzero) == 1:
        report.warn("C. source diversity", f"only 1 source ({nonzero[0]}) — others returned 0")
    else:
        report.fail("C. source diversity", "0 sources returned data in latest run")

    total = last_run.get("total_fetched", 0)
    if total < 5:
        report.fail("C. fetch floor", f"total_fetched={total} (<5)")
    else:
        report.passed("C. fetch floor", f"total_fetched={total}")


# ---------- D. Ranker health ----------

def check_ranker_health(report: Report, last_run: dict | None) -> None:
    if not last_run:
        report.warn("D. ranker health", "no run_log to inspect")
        return
    r = last_run.get("ranker", {}) or {}
    requested = r.get("requested", 0)
    scored = r.get("scored", 0)
    placeholder = r.get("placeholder", 0)
    by_tier = r.get("by_tier", {}) or {}

    if requested == 0:
        report.info("D. ranker health", "no jobs needed ranking this run")
        return

    if scored > 0:
        report.passed("D. ranker health", f"LLM scored {scored}/{requested} jobs ({by_tier})")
        return

    # All placeholder — check heuristic tier diversity. If everything is tier B
    # the heuristic isn't differentiating and Top Matches becomes meaningless.
    a = by_tier.get("A", 0)
    b = by_tier.get("B", 0)
    c = by_tier.get("C", 0)
    if a + c == 0 and b > 5:
        report.fail("D. ranker health",
                    f"all {b} jobs flat at tier B — heuristic not differentiating (LLM quota'd?)")
    else:
        report.warn("D. ranker health",
                    f"LLM skipped, heuristic gave A:{a} B:{b} C:{c} (quota likely; "
                    f"check GEMINI_API_KEY plumbed in CI)")


# ---------- E. Dashboard integrity ----------

def check_dashboards(sp, report: Report) -> None:
    # Top Matches
    try:
        tm = sp.worksheet("Top Matches")
        rows = tm.get_all_values()
        data = [r for r in rows[1:] if any(c.strip() for c in r)]
        if len(data) < 10:
            report.warn("E. Top Matches population", f"only {len(data)} rows (<10)")
        else:
            report.passed("E. Top Matches population", f"{len(data)} rows present")

        # tier-A entries should have a valid URL in their Link cell
        header = rows[0] if rows else []
        if "Link" in header and "Fit" in header:
            link_i = header.index("Link")
            fit_i = header.index("Fit")
            a_count = 0
            a_with_link = 0
            for r in data:
                if len(r) <= max(link_i, fit_i):
                    continue
                if r[fit_i] == "A":
                    a_count += 1
                    if r[link_i].startswith("http"):
                        a_with_link += 1
            if a_count and a_with_link < a_count:
                report.fail("E. Top Matches tier-A links",
                            f"{a_count - a_with_link}/{a_count} tier-A rows missing a URL")
            elif a_count:
                report.passed("E. Top Matches tier-A links", f"{a_count} tier-A entries all have URLs")
    except Exception as exc:
        report.fail("E. Top Matches population", f"could not open: {exc}")

    # Summary
    try:
        sm = sp.worksheet("Summary")
        rows = sm.get_all_values()
        body = [r for r in rows[1:] if any(c.strip() for c in r)]
        if len(body) < 20:
            report.warn("E. Summary detail", f"only {len(body)} rows (<20)")
        else:
            report.passed("E. Summary detail", f"{len(body)} rows present")
    except Exception as exc:
        report.fail("E. Summary detail", f"could not open: {exc}")


# ---------- F. Cross-day dedup ----------

def check_dedup(report: Report, last_run: dict | None) -> None:
    if not last_run:
        return
    new = last_run.get("after_dedup_new", 0)
    seen = last_run.get("already_seen", 0)
    total = last_run.get("after_normalize", 0)
    if total == 0:
        report.info("F. cross-day dedup", "no jobs to dedup this run")
        return
    if new == total and seen == 0 and total > 10:
        report.warn("F. cross-day dedup",
                    f"all {total} jobs were 'new' (already_seen=0) — seen.db likely reset; "
                    "expected after a fresh wipe but otherwise indicates dedup persistence is broken")
    else:
        report.passed("F. cross-day dedup", f"new={new} already_seen={seen} of {total}")


# ---------- G. Sheet vs run-log consistency ----------

def check_consistency(snapshots: dict[str, list[list[str]]], report: Report, last_run: dict | None) -> None:
    if not last_run:
        return
    reported = last_run.get("per_tab_totals", {}) or {}
    if not reported:
        return
    actual: dict[str, int] = {}
    missing_snapshots = []
    for tab in reported:
        rows = snapshots.get(tab)
        if rows is None or not rows:
            missing_snapshots.append(tab)
            continue
        ids = [r[0] for r in rows[1:] if r and r[0] and r[0].strip()]
        actual[tab] = len(ids)
    if missing_snapshots:
        report.warn("G. sheet/run-log consistency",
                    f"could not snapshot {missing_snapshots} (transient quota?)")
        return
    mismatches = []
    for tab, n in reported.items():
        a = actual.get(tab, -1)
        if a < n:
            mismatches.append(f"{tab}: sheet={a} reported>={n}")
    if mismatches:
        report.fail("G. sheet/run-log consistency", "; ".join(mismatches))
    else:
        report.passed("G. sheet/run-log consistency", f"all {len(reported)} tabs &gt;= reported totals")


# ---------- H. No silent failures ----------

def check_no_silent_failures(report: Report, last_run: dict | None) -> None:
    if not last_run:
        return
    if not last_run.get("sheet_ok", True):
        report.fail("H. sheet_ok", "last run reported sheet_ok=False")
    else:
        report.passed("H. sheet_ok", "last run sheet_ok=true")
    if not last_run.get("summary_ok", True):
        report.fail("H. summary_ok", "last run reported summary_ok=False")
    else:
        report.passed("H. summary_ok", "last run summary_ok=true")
    if not last_run.get("top_matches_ok", True):
        report.fail("H. top_matches_ok", "last run reported top_matches_ok=False")
    else:
        report.passed("H. top_matches_ok", "last run top_matches_ok=true")

    # Email lock should either be cleared or have a sensible "skipped" reason.
    email_lock = last_run.get("email_lock", "")
    if "fail" in email_lock.lower() or "error" in email_lock.lower():
        report.warn("H. email_lock", f"unusual reason: {email_lock}")


def main() -> int:
    load_dotenv()
    report = Report()

    try:
        sp = _open_sheet()
    except Exception as exc:
        report.fail("setup", f"could not open Google Sheet: {exc}")
        sp = None

    last_run = _last_run_summary()

    if sp is not None:
        snapshots = _snapshot_role_tabs(sp)
        check_alignment(snapshots, report)
        check_freshness(sp, report, last_run, snapshots.get("PM", []))
        check_dashboards(sp, report)
        check_consistency(snapshots, report, last_run)
    else:
        report.fail("setup", "Google Sheet unavailable — skipping live checks")

    check_source_diversity(report, last_run)
    check_ranker_health(report, last_run)
    check_dedup(report, last_run)
    check_no_silent_failures(report, last_run)

    # Render
    fails = report.failures
    warns = report.warnings
    passes = [c for c in report.checks if c.severity == "PASS"]
    infos = [c for c in report.checks if c.severity == "INFO"]

    print("=" * 70)
    print(f"COMPREHENSIVE SYNTHETIC — job_search_v2 — {datetime.now(timezone.utc).isoformat(timespec='seconds')}")
    print("=" * 70)
    for c in report.checks:
        marker = {"PASS": "[OK]", "FAIL": "[FAIL]", "WARN": "[WARN]", "INFO": "[..]"}[c.severity]
        line = f"{marker} {c.name}"
        if c.detail:
            line += f" — {c.detail}"
        print(line)
    print("-" * 70)
    print(f"Total: {len(passes)} PASS, {len(warns)} WARN, {len(fails)} FAIL, {len(infos)} INFO")
    if last_run:
        print(f"Latest local run: {last_run.get('run_id')} "
              f"(mode={last_run.get('mode')}, dry={last_run.get('dry_run')})")
        print(f"Sheet link: https://docs.google.com/spreadsheets/d/"
              f"{os.environ.get('SHEETS_SPREADSHEET_ID', '').strip()}/edit")
    print("=" * 70)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
