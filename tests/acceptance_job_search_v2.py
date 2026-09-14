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

import json
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
from execution.personal_workflows.job_search_v2.normalizer.domain_filter import classify_domain  # noqa: E402

load_dotenv(find_dotenv(usecwd=False))

ROLE_TABS = ["PM", "AI PM", "PO", "AI PO"]
TOP_MATCHES_TAB = "Top Matches"

# Geographies the operator will NOT consider. Mirror of the config reject list.
# 2026-09-01: Switzerland + UK added (scope is FR/BE/DE/PL/AT/LU + remote).
OUT_OF_SCOPE_LOCATIONS = [
    "united states", "usa", "u.s.a.", " us)", "canada", "mexico", "brazil",
    "argentina", "australia", "new zealand", "japan", "india", "singapore",
    "hong kong", "south africa", "uae", "dubai", "apac", "americas",
    "switzerland", "zurich", "zürich", "geneva", "genève", "united kingdom",
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
# Split into two per-gate corpora so each gate is verified INDEPENDENTLY.
# Prior form was a single MUST_REJECT list checked with `if rel_ok AND lang_ok`
# which only fired if BOTH gates accepted — a single-gate regression (title
# gate correctly rejects, but lang gate silently starts accepting foreign
# titles) would go undetected because the title gate would "save" us today.
# The split makes each gate carry its own guarantee.

# Titles the RELEVANCE (title) gate must reject. These are legitimate French /
# English titles for wrong roles (cybersecurity, SEO, accounting, engineering
# management). The language gate correctly accepts them as EN/FR — the title
# gate is the only line of defense, so we verify it independently.
MUST_REJECT_BY_TITLE = [
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
    # 2026-09-01 PM/PO-only rework (operator: "it sends full stack AI engineer
    # roles … this is noise, not music"). Every engineering / consulting /
    # builder title that the old Track-B anchors accepted MUST now reject.
    "Full Stack AI Engineer",
    "Senior Full Stack AI Engineer (H/F)",
    "AI Automation Engineer",
    "AI Engineer",
    "Machine Learning Engineer",
    "MLOps Engineer",
    "Prompt Engineer",
    "AI Consultant",
    "AI Advisor",
    "Fractional AI Advisor",
    "AI Advisory",
    "React Native Developer",
    "Staff AI Engineer - M/W",
    "AI Product Engineer",
    "AI Solutions Architect",
    "Consultant IA (production images & vidéos) (H/F/X) - Freelance",
    "Head of AI",
    "Product Marketing Manager",
    # A bare "PM" must NOT rescue a project-manager title (abbrev guard).
    "Chef de Projet PM",
]

# Titles the LANGUAGE gate must reject. These are genuinely-German (or other
# non-EN/FR) titles that the title gate could plausibly accept on keyword
# match — the language gate is the intended primary blocker.
MUST_REJECT_BY_LANGUAGE = [
    "Senior Produktmanager",
    "Product Owner für unseren Standort in Berlin",
]

# Titles the DOMAIN gate must reject (2026-09-10). The operator's CV is
# software-only; PM/PO roles for physical / electronic / instrumentation /
# semiconductor / embedded / systems-software products pass the title gate
# ("Product Manager") but do NOT match the profile. Verified independently.
MUST_REJECT_BY_DOMAIN = [
    "Product Manager – Semiconductor Test Solutions",
    "Hardware Product Manager",
    "Chef de Produit Instrumentation",
    "Product Manager Embedded Systems (H/F)",
    "Product Manager - Systems Software",
    "Product Owner Électronique de puissance",
    "Product Manager - Microchips & ASIC",
    "Senior Product Manager, Medical Devices",
    "Product Manager Firmware & Connectivity",
    "Chef de produit mécanique H/F",
    "Product Manager FPGA Platforms",
    "Product Manager – Test & Measurement Instruments",
]

# Combined view for the pipeline-outcome check (backwards compat).
MUST_REJECT = MUST_REJECT_BY_TITLE + MUST_REJECT_BY_LANGUAGE + MUST_REJECT_BY_DOMAIN
MUST_KEEP = [
    # 2026-09-01 PM/PO-only rework: the operator's target set is Product
    # Manager (plain / data / growth / technical / functional / platform / AI)
    # and Product Owner (plain / senior / AI), EN + FR.
    "AI Product Manager",
    "Senior Product Manager",
    "Product Manager",
    "Data Product Manager",
    "Growth Product Manager",
    "Technical Product Manager",
    "Platform Product Manager",
    "Group Product Manager",
    "Head of Product",
    "Product Lead",
    "Chef de produit IA",
    "Chef de produit senior",
    "Responsable Produit",
    "Directeur Produit",
    "Product Owner",
    "Senior Product Owner",
    "Lead Product Owner",
    "AI Product Owner",
    "Technical Product Owner",
    "Product Manager / Project Manager",
    # The langdetect false-positives caught 2026-06-24 — must stay kept.
    # ("Staff AI Engineer - M/W" moved to MUST_REJECT_BY_TITLE: still a
    # langdetect false-positive on language, but engineering titles are now
    # out of scope at the TITLE gate.)
    "Senior Product Manager - Engagement (all genders)",
    "Product Owner Secteur Immobilier (H/F)",
    # FR ads abbreviating the role (2026-09-01 recall hardening — Gate 2b).
    "PO Data (H/F)",
    "PM Senior - Fintech H/F",
]


# ---------------------------------------------------------------------------
# DESCRIPTION-LEVEL language corpus (audit 2026-06-24).
#
# The title-only corpus above passes classify_language(title, "") with an empty
# description, so it CANNOT catch false-positives that only fire on description
# text — e.g. the " per " tell wrongly flagging "90k per year" as Italian, which
# silently dropped English descriptions from RemoteOK / WeWorkRemotely. These
# entries exercise the description path explicitly. (title, description, keep?)
# ---------------------------------------------------------------------------
LANG_DESC_CORPUS = [
    # English descriptions with words that previously collided with tells.
    ("AI Product Manager", "Salary: 90k per year. You will own the product roadmap and work with engineering.", True),
    ("Senior Product Owner", "Compensation is per market rate. Ship features per sprint cycle.", True),
    ("Technical Product Manager", "We weigh the pros and cons of each approach. Own the mobile roadmap.", True),
    ("Senior Product Manager", "Reviewed per quarter. Manage stakeholders across the org.", True),
    # Genuinely non-EN/FR descriptions must still be rejected.
    ("Produktmanager", "Wir suchen einen erfahrenen Produktmanager für unseren Standort mit Verantwortung für die Produktstrategie.", False),
    ("Product Manager", "Cerchiamo un product manager con esperienza nella gestione della roadmap e degli stakeholder aziendali.", False),
    # Polish post with an English title (Poland is in scope, Polish is not).
    ("Product Owner", "Poszukujemy doświadczonego Product Ownera do naszego zespołu produktowego w Warszawie. Wymagania: doświadczenie w agile.", False),
]


# Evaluated with today=2026-09-14, strict=True, recheck limit 6d.
STAMP_CORPUS = [
    ("open · posted 2026-09-08 · checked 2026-09-10", True),
    ("open · posted 2026-09-08 · checked 2026-09-10 · rechecked 2026-09-13", True),
    ("unverified (source date) · posted 2026-09-09 · checked 2026-09-10", False),  # strict: never confirmed
    ("open · posted 2026-09-03 · checked 2026-09-10", True),   # exactly 7d = allowed
    ("open · posted 2026-09-02 · checked 2026-09-10", False),  # 8d = stale at insert
    ("open · posted 2026-09-01 · checked 2026-09-01", False),  # last check 13d ago, never re-confirmed
    ("open · posted 2026-09-01 · checked 2026-09-01 · rechecked 2026-09-12", True),
    ("open · posted unknown · checked 2026-09-10", False),
    ("closed · posted 2026-09-09 · checked 2026-09-10", False),
    ("", False),
    ("verified", False),
]
_STAMP_CORPUS_TODAY = __import__("datetime").date(2026, 9, 14)


def check_regression_corpus() -> list[str]:
    """Run the frozen corpus through the gate. Returns list of failures (empty=OK).

    Per-gate independent verification:
      - MUST_REJECT_BY_TITLE: the TITLE gate must reject. If the language gate
        accepts them (correctly — they're EN/FR text), that's not a bug, but
        if the title gate accepts them, the pipeline would ship a wrong role.
      - MUST_REJECT_BY_LANGUAGE: the LANGUAGE gate must reject. Title gate
        may or may not catch these — the language gate is the primary blocker.
      - MUST_KEEP: both gates must accept.

    2026-07-01 audit exhibit: the prior `if rel_ok AND lang_ok` check only
    fired when both gates accepted a MUST_REJECT title. If one gate silently
    regressed while the other still rejected, the pipeline behavior looked
    correct today but became a single-point-of-failure for tomorrow. The
    per-gate split catches that regression before it manifests in output.
    """
    from execution.personal_workflows.job_search_v2.normalizer.title_filter import classify_title
    from execution.personal_workflows.job_search_v2.normalizer.language_filter import classify_language

    failures: list[str] = []
    for t in MUST_REJECT_BY_TITLE:
        rel_ok, reason = classify_title(t)
        if rel_ok:
            failures.append(f"MUST_REJECT_BY_TITLE but title-gate accepted: '{t[:55]}' ({reason})")
    for t in MUST_REJECT_BY_LANGUAGE:
        lang_ok, reason = classify_language(t, "")
        if lang_ok:
            failures.append(f"MUST_REJECT_BY_LANGUAGE but lang-gate accepted: '{t[:55]}' ({reason})")
    for t in MUST_REJECT_BY_DOMAIN:
        dom_ok, reason = classify_domain(t, "")
        if dom_ok:
            failures.append(f"MUST_REJECT_BY_DOMAIN but domain-gate accepted: '{t[:55]}' ({reason})")
    for t in MUST_KEEP:
        rel_ok, rel_reason = classify_title(t)
        lang_ok, lang_reason = classify_language(t, "")
        dom_ok, dom_reason = classify_domain(t, "")
        if not rel_ok:
            failures.append(f"MUST_KEEP but title-gate dropped: '{t[:55]}' ({rel_reason})")
        if not lang_ok:
            failures.append(f"MUST_KEEP but lang-gate dropped: '{t[:55]}' ({lang_reason})")
        if not dom_ok:
            failures.append(f"MUST_KEEP but domain-gate dropped: '{t[:55]}' ({dom_reason})")
    # Verified-stamp parser must itself hold the line (frozen expectations).
    for stamp, want_clean in STAMP_CORPUS:
        got = check_verified_stamp(stamp, today=_STAMP_CORPUS_TODAY, strict=True, recheck_max_age_days=6)
        if (got is None) != want_clean:
            failures.append(f"STAMP want_clean={want_clean} but got {got!r} for {stamp!r}")
    # Description-level language checks (the title-only loop above can't see these).
    for title, desc, want_keep in LANG_DESC_CORPUS:
        lang_ok, reason = classify_language(title, desc)
        if lang_ok != want_keep:
            verb = "dropped" if want_keep else "kept"
            failures.append(f"LANG_DESC want_keep={want_keep} but {verb}: '{title[:40]}' ({reason})")
    return failures


# ---------------------------------------------------------------------------
# FRESHNESS / LIVENESS invariant (2026-09-10).
#
# Every role-tab row must carry a "Verified" stamp written either by Stage 3.8
# (new rows) or by the Stage 3.9 re-verification sweep (historical rows):
#     "open · posted YYYY-MM-DD · checked YYYY-MM-DD"
#     "unverified (source date) · posted YYYY-MM-DD · checked YYYY-MM-DD"
# A row is a violation when the stamp is missing, unparsable, its posted date
# is more than MAX_AGE_DAYS before its check date, or it was never dated.
# ---------------------------------------------------------------------------
MAX_AGE_DAYS = 7.0
# Strict mode (2026-09-14): every kept link must be positively confirmed open
# on its own page, and re-confirmed at least every RECHECK_MAX_AGE_DAYS
# (= 2 × config verification.recheck_after_days, leaving one missed cron day
# of slack). Read from config so the gate and the pipeline never drift.
_VER_CFG = {}
try:
    _VER_CFG = (json.loads((Path(__file__).resolve().parents[1] / "config" / "job_search_v2.json")
                           .read_text(encoding="utf-8")).get("verification", {}) or {})
except (OSError, json.JSONDecodeError):
    pass
STRICT = bool(_VER_CFG.get("strict", True))
RECHECK_MAX_AGE_DAYS = 2.0 * float(_VER_CFG.get("recheck_after_days", 3))
_STAMP_RE = __import__("re").compile(
    r"^(?P<label>open|closed|unknown|unverified \(source date\))\s*·\s*posted\s+(?P<posted>\d{4}-\d{2}-\d{2}|unknown)"
    r"\s*·\s*checked\s+(?P<checked>\d{4}-\d{2}-\d{2})(?:\s*·\s*rechecked\s+(?P<rechecked>\d{4}-\d{2}-\d{2}))?\s*$"
)


def check_verified_stamp(stamp: str, max_age_days: float = MAX_AGE_DAYS, *, today=None,
                         strict: bool | None = None, recheck_max_age_days: float | None = None) -> str | None:
    """Return a violation string for a Verified cell, or None when compliant.

    Rules: stamp present and parsable; not closed; posted date known; posted
    within `max_age_days` of the ORIGINAL check; strict → the "unverified
    (source date)" label is a violation; the latest check (rechecked, else
    checked) must be within `recheck_max_age_days` of `today`.
    """
    from datetime import date

    strict = STRICT if strict is None else strict
    recheck_max_age_days = RECHECK_MAX_AGE_DAYS if recheck_max_age_days is None else recheck_max_age_days
    today = today or date.today()

    text = (stamp or "").strip()
    if not text:
        return "no Verified stamp (row never liveness/freshness-checked)"
    m = _STAMP_RE.match(text)
    if not m:
        return f"unparsable Verified stamp ({text[:40]})"
    if m.group("label") == "closed":
        return "verified CLOSED (no longer accepting applications)"
    if strict and m.group("label").startswith("unverified"):
        return "link never positively confirmed open (strict mode forbids source-date-only rows)"
    if m.group("posted") == "unknown":
        return "posted date unknown at verification"
    try:
        posted = date.fromisoformat(m.group("posted"))
        checked = date.fromisoformat(m.group("checked"))
        last = date.fromisoformat(m.group("rechecked")) if m.group("rechecked") else checked
    except ValueError as exc:
        return f"bad date in Verified stamp ({exc})"
    age = (checked - posted).days
    if age > max_age_days:
        return f"stale at insert: posted {posted.isoformat()}, {age}d before check"
    if age < -1:
        return f"posted date in the future relative to check ({posted.isoformat()} > {checked.isoformat()})"
    since_last = (today - last).days
    if since_last > recheck_max_age_days:
        return f"not re-confirmed open for {since_last}d (last check {last.isoformat()}, limit {recheck_max_age_days:g}d)"
    return None


def _open_sheet():
    import gspread  # type: ignore
    from google.oauth2.service_account import Credentials  # type: ignore
    sa = Path(os.environ.get("GOOGLE_SERVICE_ACCOUNT_PATH", "credentials/service_account.json"))
    sid = os.environ.get("SHEETS_SPREADSHEET_ID", "").strip()
    if not sid or not sa.exists():
        return None
    creds = Credentials.from_service_account_file(str(sa), scopes=["https://www.googleapis.com/auth/spreadsheets"])
    return gspread.authorize(creds).open_by_key(sid)


def _check_row(tab: str, title: str, location: str, link: str, verified: str | None = None) -> list[str]:
    """Return a list of violation strings for one row (empty = clean).

    `verified` is the row's Verified cell; pass None to skip the freshness /
    liveness check (Top Matches is a derived dashboard without that column).
    """
    violations: list[str] = []

    # 1. Relevance — must match one of the operator's two tracks.
    ok, reason = classify_title(title)
    if not ok:
        violations.append(f"irrelevant title ({reason.split(':',1)[-1]})")

    # 1b. Domain — software / digital products only (2026-09-10).
    dom_ok, dom_reason = classify_domain(title, "")
    if not dom_ok:
        violations.append(f"non-software domain ({dom_reason.split(':',1)[-1]})")

    # 1c. Freshness + liveness stamp (2026-09-10).
    if verified is not None:
        stamp_violation = check_verified_stamp(verified)
        if stamp_violation:
            violations.append(stamp_violation)

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


# ---------------------------------------------------------------------------
# Layer 3: SILENT-DEGRADATION alarm (audit 2026-07-01).
#
# The prior two layers assert per-row correctness: every sheet row is relevant,
# EN/FR, in-scope, linked. But they do NOT catch pipeline-quality collapse: the
# case where every ROW passes filters, but the RANKER silently returned
# placeholder-B for 96% of them because Gemini truncated its JSON response.
# Result: 25 rows in Top Matches are effectively random.
#
# This layer reads the last pipeline_stats entry from run_log.jsonl and hard-
# fails if any of these regressed:
#   - ranker.placeholder / ranker.requested > 0.30 (LLM silently degraded)
#   - ranker.chunk_failures non-empty
#   - non-zero-sources < 3 (source diversity collapsed)
#   - sheet_ok == False (write path broken)
#   - top_matches_ok == False
#   - summary_ok == False
#
# Exhibit: 2026-07-01 morning run had 96% placeholder ratio; the operator
# would have received 25 random "top matches" if the layer hadn't existed.
# ---------------------------------------------------------------------------
RUN_LOG_PATH = Path(__file__).resolve().parents[1] / ".tmp" / "job_search_v2" / "run_log.jsonl"

DEGRADATION_THRESHOLDS = {
    "placeholder_ratio_max": 0.30,  # >30% placeholder = ranker silently failed
    # 2026-07-01 audit: raised from 3 to 4. Default --sources list runs 6
    # sources (france_travail, linkedin_guest_api, wttj_algolia, hellowork,
    # remoteok, weworkremotely). At threshold 3, losing HALF the sources on
    # a given day was treated as healthy — masking source-block regressions.
    # 4/6 = 66% source coverage minimum.
    "non_zero_sources_min": 4,
}


def check_pipeline_degradation() -> list[str]:
    """Read the CURRENT run's pipeline_stats and hard-fail on quality
    regressions. Returns [] if healthy.

    Two-source read (in priority order):
      1. CURRENT_RUN_STATS_PATH env var -> JSON tempfile written by run.py
         Stage 4c BEFORE the acceptance call. This is the authoritative
         source when acceptance runs inside a live pipeline: it captures the
         *current* run's stats, before the run_log.jsonl append at Stage 5.
      2. Fallback to run_log.jsonl's last live entry — for standalone /
         manual invocations of the acceptance test.

    Dry-run entries in the log are skipped: we only guard runs that touch
    the operator's inbox.
    """
    stats: dict | None = None

    # Path 1: run.py passes a tempfile with the current run's stats.
    # Path validation (workspace Python hardening rule 3): CURRENT_RUN_STATS_PATH
    # is env-supplied, so we must resolve() + check the resolved path is inside
    # .tmp/. Prevents a crafted env var from making the acceptance script open
    # a file outside the workspace (e.g., CURRENT_RUN_STATS_PATH=../.env).
    current_path = os.environ.get("CURRENT_RUN_STATS_PATH", "").strip()
    if current_path:
        try:
            resolved = Path(current_path).resolve()
            tmp_root = (Path(__file__).resolve().parents[1] / ".tmp").resolve()
            if not resolved.is_relative_to(tmp_root):
                return [
                    f"CURRENT_RUN_STATS_PATH points outside .tmp/ "
                    f"({resolved}); refusing to read as a safety guard."
                ]
        except (OSError, ValueError) as exc:
            return [f"CURRENT_RUN_STATS_PATH could not be resolved ({current_path}): {exc}"]
        if resolved.exists():
            try:
                stats = json.loads(resolved.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                return [f"CURRENT_RUN_STATS_PATH unreadable ({resolved}): {exc}"]

    # Path 2: fall back to run_log.jsonl's last live entry.
    #
    # WARNING to standalone/manual invokers: this fallback reads the last
    # LIVE run — which may be a prior BAD run (e.g. yesterday's degraded
    # ranker output before today's fix). If you're re-running acceptance
    # after a fix but before triggering a fresh pipeline run, the L3 gate
    # will report FAIL based on the stale prior run. The pipeline-invoked
    # path (CURRENT_RUN_STATS_PATH env var) does not have this issue.
    if stats is None:
        if not RUN_LOG_PATH.exists():
            # Nothing to check yet — first-ever run, no prior state.
            return []
        lines = RUN_LOG_PATH.read_text(encoding="utf-8").strip().splitlines()
        if not lines:
            return []
        for line in reversed(lines):
            try:
                candidate = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not candidate.get("dry_run", False) and candidate.get("mode") == "live":
                stats = candidate
                break
        if stats is None:
            return []
        # Flag the standalone-fallback read so operator knows the FAIL may
        # be about a prior run, not the run they just triggered.
        run_id = str(stats.get("run_id", "unknown"))
        print(f"  [INFO] Layer 3 reading STALE run_log.jsonl entry (run_id={run_id[:30]}); "
              f"pipeline-invoked path via CURRENT_RUN_STATS_PATH is the authoritative source.")

    failures: list[str] = []
    ranker = stats.get("ranker", {}) or {}
    requested = int(ranker.get("requested", 0) or 0)
    placeholder = int(ranker.get("placeholder", 0) or 0)
    chunk_failures = ranker.get("chunk_failures", []) or []

    if requested > 0:
        ratio = placeholder / requested
        if ratio > DEGRADATION_THRESHOLDS["placeholder_ratio_max"]:
            failures.append(
                f"RANKER DEGRADED: {placeholder}/{requested} = "
                f"{ratio:.0%} placeholder (threshold "
                f"{DEGRADATION_THRESHOLDS['placeholder_ratio_max']:.0%}). "
                f"Top Matches is effectively random. "
                f"chunk_failures={chunk_failures}"
            )
    if chunk_failures:
        failures.append(
            f"RANKER CHUNK FAILURES: {chunk_failures} — Gemini truncated or "
            f"errored on {len(chunk_failures)} chunk(s); those jobs fell to "
            f"heuristic-placeholder."
        )

    # 2026-09-10: Stage 3.8 posting verification must have RUN on a live run.
    # A run that skipped it (--no-verify, or config.verification.enabled=false)
    # can write unverified rows — the exact defect class this gate exists for.
    verification = stats.get("verification", {}) or {}
    if stats.get("mode") == "live" and (verification.get("disabled") or not verification):
        failures.append(
            "POSTING VERIFICATION SKIPPED on a live run (stats.verification missing or "
            "disabled) — every row must be page-checked for freshness + liveness."
        )
    elif stats.get("mode") == "live" and STRICT and verification.get("strict") is False:
        failures.append(
            "POSTING VERIFICATION RAN IN LENIENT MODE on a live run while config "
            "verification.strict is true — unconfirmed links may have been shipped."
        )
    for w in verification.get("warnings", []) or []:
        print(f"  [WARN] posting_verifier: {w}")

    per_source = stats.get("per_source", {}) or {}
    non_zero_sources = sum(1 for _, n in per_source.items() if int(n or 0) > 0)
    if non_zero_sources < DEGRADATION_THRESHOLDS["non_zero_sources_min"]:
        failures.append(
            f"SOURCE COVERAGE DEGRADED: only {non_zero_sources} of "
            f"{len(per_source)} sources returned data (threshold "
            f"{DEGRADATION_THRESHOLDS['non_zero_sources_min']}). "
            f"per_source={per_source}"
        )

    # 2026-07-01 pipeline-auditor fix: summary_ok is set at Stage 4e (after
    # email + after acceptance gate runs) in run.py, so via CURRENT_RUN_STATS_PATH
    # this key is ALWAYS None at gate time — check was dead code. Only
    # sheet_ok and top_matches_ok are computed BEFORE the gate. Summary tab
    # write failures surface on the NEXT day's run when Layer 3 falls back to
    # run_log.jsonl (the summary_ok field is present in the final run_log line).
    for key, label in (
        ("sheet_ok", "sheet append"),
        ("top_matches_ok", "Top Matches refresh"),
    ):
        if stats.get(key) is False:
            failures.append(f"WRITE FAILED: {label} returned False in the run-log.")
    # summary_ok check ONLY meaningful when reading a completed run_log entry
    # (via the fallback path). If stats came from CURRENT_RUN_STATS_PATH, the
    # field is None (not False) at this point and the check silently passes.
    if stats.get("summary_ok") is False:
        failures.append("WRITE FAILED: Summary refresh returned False in the run-log.")

    # Zero-new-jobs check (audit 2026-07-01, pipeline-auditor gap B).
    # per_source counts RAW fetched jobs pre-dedup. On a day where every
    # fetched job is already seen, non_zero_sources is > 0 (healthy) but
    # after_dedup_new is 0 and sheet_appended is 0 — the operator gets
    # silence and the acceptance gate previously showed green.
    #
    # A single "no new jobs" day is legitimate (weekend, low posting day).
    # Only fail hard when it recurs 3+ consecutive days — that's a structural
    # signal (all sources silently blocked, dedup DB stale, etc.). Consecutive
    # count tracked in .tmp/job_search_v2/zero_new_streak.txt (survives runs).
    after_dedup_new = int(stats.get("after_dedup_new", -1) or 0)
    sheet_appended = int(stats.get("sheet_appended", -1) or 0)
    if stats.get("mode") == "live":
        streak_path = Path(RUN_LOG_PATH.parent) / "zero_new_streak.txt"
        prior_streak = 0
        try:
            if streak_path.exists():
                prior_streak = int(streak_path.read_text(encoding="utf-8").strip() or "0")
        except (OSError, ValueError):
            prior_streak = 0
        is_zero = (after_dedup_new == 0 and sheet_appended == 0)
        new_streak = prior_streak + 1 if is_zero else 0
        try:
            streak_path.parent.mkdir(parents=True, exist_ok=True)
            streak_path.write_text(str(new_streak), encoding="utf-8")
        except OSError:
            pass  # best-effort — streak state is advisory
        ZERO_NEW_HARD_FAIL_AFTER = 3
        if is_zero and new_streak >= ZERO_NEW_HARD_FAIL_AFTER:
            failures.append(
                f"ZERO NEW JOBS ({new_streak} consecutive days): after_dedup_new=0 "
                f"and sheet_appended=0. Beyond the {ZERO_NEW_HARD_FAIL_AFTER}-day "
                f"soft-fail floor — this is structural (sources silently blocked "
                f"OR dedup DB stale). Operator inbox has been silent for {new_streak} days."
            )
        elif is_zero:
            # Soft-warn: informational log line only, not a failure.
            print(f"  [WARN] ZERO NEW JOBS today (streak={new_streak}/{ZERO_NEW_HARD_FAIL_AFTER}). "
                  f"Legitimate on weekends / low-posting days; escalates to FAIL at day "
                  f"{ZERO_NEW_HARD_FAIL_AFTER}.")

    return failures


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
        verified_i = idx.get("Verified")
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
            if tab == TOP_MATCHES_TAB:
                verified = None  # derived dashboard: no Verified column by design
            else:
                # A role tab WITHOUT the column (pre-migration) yields "" → violation,
                # which is the intended signal: the sheet was never verified.
                verified = r[verified_i] if (verified_i is not None and len(r) > verified_i) else ""
            vs = _check_row(tab, title, location, link, verified)
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

    # --- Layer 3: silent-degradation alarm (pipeline quality, not per-row). ---
    print()
    print("=" * 72)
    print("SILENT-DEGRADATION ALARM (run_log.jsonl -> last LIVE run's pipeline_stats)")
    print("=" * 72)
    degradation_failures = check_pipeline_degradation()
    if degradation_failures:
        for f in degradation_failures:
            print(f"  [FAIL] {f}")
        print("\nRESULT: FAIL — pipeline silently degraded on the last LIVE run.")
        print("The rows may look clean, but the ranker/coverage/write path is broken.")
        failed = True
    else:
        print("  [OK] ranker placeholder ratio, chunk failures, source coverage, "
              "and write paths all within thresholds.")

    if failed:
        print("\nRESULT: FAIL — see failures above. Fix before claiming done.")
        return 1
    print("\nRESULT: PASS — every row is clean AND the pipeline shipped ranked data.")
    print("(Per front-door-synthetic rule: needs 5 consecutive PASS runs to be called shippable.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
