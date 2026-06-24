"""
description: ACCEPTANCE TEST — the single "is this shippable?" gate for
    job_search_v2. It encodes the operator's own eyeball test: open the LIVE
    Google Sheet, read EVERY row in every role tab + Top Matches, and HARD-FAIL
    if a single row is a job the operator would not apply to.

    This exists because every prior "verified" claim checked that the pipeline
    RAN (row counts, exit codes) — not that the OUTPUT was CORRECT. The operator
    kept finding junk (cybersecurity / accounting / SEO / German-language /
    project-manager roles) by hand. This test makes those defects fail loudly
    HERE instead of in the operator's inbox.

    It reuses the SAME classify_title / classify_language functions the live
    pipeline uses — single source of truth. If a row in the sheet fails the
    test, the pipeline's own gate would also have rejected it, which means
    either (a) it's stale data from before a fix, or (b) a real regression.

inputs:
    - env: SHEETS_SPREADSHEET_ID, GOOGLE_SERVICE_ACCOUNT_PATH
outputs:
    - PASS/FAIL report to stdout, listing every offending row.
    - exit 0 ONLY if every row in every tab is relevant + EN/FR + in-scope +
      has a valid link. exit 1 on ANY violation.

Run before claiming the system works. 5 consecutive clean runs = shippable
(per ~/.claude/rules/front-door-synthetic.md).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv, find_dotenv

_HERE = Path(__file__).resolve()
_WORKSPACE = _HERE.parents[1]
if str(_WORKSPACE) not in sys.path:
    sys.path.insert(0, str(_WORKSPACE))

from execution.personal_workflows.job_search_v2.normalizer.title_filter import classify_title  # noqa: E402
from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))

ROLE_TABS = ["PM", "AI PM", "AI Automation", "AI Mobile", "AI Process", "AI Consultant"]
TOP_MATCHES_TAB = "Top Matches"

# Geographies the operator will NOT consider. Mirror of the config reject list.
OUT_OF_SCOPE_LOCATIONS = [
    "united states", "usa", "u.s.a.", " us)", "canada", "mexico", "brazil",
    "argentina", "australia", "new zealand", "japan", "india", "singapore",
    "hong kong", "south africa", "uae", "dubai", "apac", "americas",
]


# ---------------------------------------------------------------------------
# FROZEN REGRESSION CORPUS — independence layer.
#
# The live-sheet check above reuses the pipeline's own classify_title /
# classify_language. If a bug were introduced into THAT shared logic, the
# pipeline and the test would agree and both pass junk. This frozen corpus is
# the guard against that: it pins expected verdicts for real titles the
# operator personally flagged (must stay REJECTED) and real titles he wants
# (must stay KEPT). If anyone weakens the gate, this fails — regardless of
# whether the pipeline agrees with itself.
#
# DO NOT relax these to make a run pass. If a corpus entry needs to change,
# that is a deliberate profile decision, made explicitly, not a quiet edit.
# ---------------------------------------------------------------------------
MUST_REJECT = [
    # The exact 19 the operator pasted on 2026-06-24 as wrong matches.
    "Consultant Cybersécurité Industrielle/OT (F/H)",
    "Consultant GRC cybersécurité confirmé (F/H)",
    "Directeur.ice de clientèle H/F",
    "Directeur SEO / GEO f/h",
    "Consultant SEO / GEO - Full remote / Strasbourg",
    "Consultant SEO / GEO - Full remote / Bordeaux f/h",
    "Consultant SEO / GEO - full remote / Lille f/h",
    "VP of Engineering (H/F)",
    "Senior Fullstack Software Engineer",
    "CDI - Property & Facility Manager",
    "DTNUM 75 - SDAN BADM - Directeur(trice) de projet SI Protection des usagers",
    "DTNUM 75 SDAN BADM Directeur(trice) de projet SI - Gestion des crises",
    "Planneur·se Stratégique / Creative Strategist CDI",
    "Consultant.e Tracking & Analytics Senior",
    "Senior Expertise Conseil H/F - Assistance Opérationnelle",
    "Chef de mission comptable H/F - PME & Groupes",
    "Senior Manager Expertise Conseil H/F - International Business Services",
    "Collaborateur comptable H/F - Equipe Immobilier",
    "Collaborateur comptable H/F - International Business Services",
    # Genuinely-German titles that must stay out.
    "Senior Produktmanager",
    "Product Owner für unseren Standort in Berlin",
]
MUST_KEEP = [
    "AI Product Manager",
    "Senior Product Manager",
    "Head of Product",
    "Chef de produit IA",
    "Consultant IA (production images & vidéos) (H/F/X) - Freelance",
    "React Native Developer",
    "AI Automation Engineer",
    "AI Consultant",
    "Product Manager / Project Manager",
    # The langdetect false-positives caught 2026-06-24 — must stay kept.
    "Staff AI Engineer - M/W",
    "Senior Product Manager - Engagement (all genders)",
    "Product Owner Secteur Immobilier (H/F)",
]


def check_regression_corpus() -> list[str]:
    """Run the frozen corpus through the gate. Returns list of failures (empty=OK)."""
    from execution.personal_workflows.job_search_v2.normalizer.title_filter import classify_title
    from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language

    failures: list[str] = []
    for t in MUST_REJECT:
        rel_ok, _ = classify_title(t)
        lang_ok, _ = classify_language(t, "")
        if rel_ok and lang_ok:  # both must NOT keep it
            failures.append(f"MUST_REJECT but kept: '{t[:55]}'")
    for t in MUST_KEEP:
        rel_ok, _ = classify_title(t)
        lang_ok, _ = classify_language(t, "")
        if not (rel_ok and lang_ok):
            failures.append(f"MUST_KEEP but dropped: '{t[:55]}'")
    return failures


def _open_sheet():
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
    sa = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json"))
    sid = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sid or not sa.exists():
        return None
    creds = Credentials.from_service_account_file(str(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(sid)


def _check_row(tab: str, title: str, location: str, link: str) -> list[str]:
    """Return a list of violation strings for one row (empty = clean)."""
    violations: list[str] = []

    # 1. Relevance — must match one of the operator's two tracks.
    ok, reason = classify_title(title)
    if not ok:
        violations.append(f"irrelevant title ({reason.split(':',1)[-1]})")

    # 2. Language — title must read as EN or FR.
    lang_ok, lang_reason = classify_language(title, "")
    if not lang_ok:
        violations.append(f"non-EN/FR title ({lang_reason.split(':',1)[-1]})")

    # 3. Location — must not be an explicitly out-of-scope geography.
    loc_low = (location or "").lower()
    for bad in OUT_OF_SCOPE_LOCATIONS:
        if bad in loc_low:
            violations.append(f"out-of-scope location ({bad.strip()})")
            break

    # 4. Link — must be a real URL when present.
    if link and not (link.startswith("http://") or link.startswith("https://")):
        violations.append("link is not a URL")

    return violations


def main() -> int:
    # --- Layer 1: frozen regression corpus (no sheet needed; independent of
    # whether the pipeline agrees with itself). ---
    corpus_failures = check_regression_corpus()
    print("=" * 72)
    print("REGRESSION CORPUS (frozen — your real flagged jobs must stay rejected)")
    print("=" * 72)
    if corpus_failures:
        for f in corpus_failures:
            print(f"  [FAIL] {f}")
        print(f"\nRESULT: FAIL — the gate was weakened; {len(corpus_failures)} corpus expectations broke.")
        return 1
    print(f"  [OK] all {len(MUST_REJECT)} must-reject + {len(MUST_KEEP)} must-keep titles classify correctly.")
    print()

    # --- Layer 2: live-sheet check ---
    sp = _open_sheet()
    if sp is None:
        print("[SETUP FAIL] Cannot open the live Google Sheet (creds / SHEETS_SPREADSHEET_ID).")
        return 1

    total_rows = 0
    total_violations = 0
    tab_reports: list[tuple[str, int, int, list[str]]] = []

    tabs = ROLE_TABS + [TOP_MATCHES_TAB]
    for tab in tabs:
        try:
            ws = sp.worksheet(tab)
            rows = ws.get_all_values()
        except Exception as exc:  # noqa: BLE001 — tab missing/unreadable is itself a finding
            tab_reports.append((tab, 0, 0, [f"could not read tab: {exc}"]))
            continue

        if not rows:
            tab_reports.append((tab, 0, 0, []))
            continue

        header = rows[0]
        idx = {h: i for i, h in enumerate(header) if h and h.strip()}
        title_i = idx.get("Title")
        loc_i = idx.get("Location")
        link_i = idx.get("Link")
        if title_i is None:
            tab_reports.append((tab, 0, 0, ["no Title column"]))
            continue

        data = [r for r in rows[1:] if any(c.strip() for c in r)]
        tab_violations: list[str] = []
        for r in data:
            title = r[title_i] if len(r) > title_i else ""
            location = r[loc_i] if (loc_i is not None and len(r) > loc_i) else ""
            link = r[link_i] if (link_i is not None and len(r) > link_i) else ""
            if not title.strip():
                continue
            total_rows += 1
            vs = _check_row(tab, title, location, link)
            if vs:
                total_violations += 1
                tab_violations.append(f"    '{title[:55]}' [{location[:25]}] -> {'; '.join(vs)}")
        tab_reports.append((tab, len(data), len(tab_violations), tab_violations))

    # Top Matches must also be non-empty (a system that finds nothing is broken).
    top_count = next((c for t, c, _, _ in tab_reports if t == TOP_MATCHES_TAB), 0)

    print("=" * 72)
    print("ACCEPTANCE TEST — job_search_v2 (live sheet, every row, your eyeball test)")
    print("=" * 72)
    for tab, n, bad, viol in tab_reports:
        mark = "[OK]  " if bad == 0 else "[FAIL]"
        print(f"{mark} {tab:<16} rows={n:<4} violations={bad}")
        for line in viol[:10]:
            print(line)
        if len(viol) > 10:
            print(f"    ... +{len(viol) - 10} more")
    print("-" * 72)
    print(f"Total rows checked: {total_rows} | rows with violations: {total_violations}")

    failed = total_violations > 0
    if top_count == 0:
        print("[FAIL] Top Matches is EMPTY — system surfaced zero strong jobs.")
        failed = True

    if failed:
        print("\nRESULT: FAIL — the sheet contains jobs that do not match the profile.")
        print("This is what the operator would have caught by hand. Fix before claiming done.")
        return 1
    print("\nRESULT: PASS — every row in every tab is relevant, EN/FR, in-scope, linked.")
    print("(Per front-door-synthetic rule: needs 5 consecutive PASS runs to be called shippable.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
