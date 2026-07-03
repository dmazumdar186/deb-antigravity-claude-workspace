#!/usr/bin/env python3
"""
cv_ats_check_pm.py
description: PM-calibrated, hard-fail acceptance gate for the GENERIC Senior-Product-Manager
    CVs (cv_builder_pm_{en,fr}.py). Distinct from cv_ats_check.py, which is AI-role calibrated.
    Asserts on the OUTPUT a recruiter reads: 2 pages, PM keyword coverage >=90% (pool drawn from
    the JD keyword research), metric density, correct language, no credential leak, ZERO
    banned buzzwords, client anonymization, and 3-second-scan guardrails (above-the-fold density
    + front-loaded metrics). Exit 0 = clean, 1 = at least one finding.
inputs: --lang {pm_en, pm_fr} (default pm_en), --pdf <path>
outputs: stdout report; exit code

Usage:
    py tests/cv_ats_check_pm.py --lang pm_en --pdf "deliverables/cv_generic_pm/CV MAZUMDAR Debanjan EN.pdf"
    py tests/cv_ats_check_pm.py --lang pm_fr --pdf "deliverables/cv_generic_pm/CV MAZUMDAR Debanjan FR.pdf"

Dependencies: pip install pdfplumber ; langdetect (optional, has a heuristic fallback)
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

import pdfplumber


# ── Metric marker regex: %, $/€ amounts (K/M), "N+", "<N"/">N" ─────────────────
_METRIC_RE = re.compile(
    r"(?:[+\-−]?\s?\d+(?:[.,]\d+)?\s?%"          # percentages (optionally signed)
    r"|[$€£]\s?\d+(?:[.,]\d+)?\s?[KkMmBb]?\+?"   # currency amounts w/ optional K/M and +
    r"|\b\d+\+"                                   # "12+" style counts
    r"|[<>]\s?\d+)",                              # "<30" / ">N"
    re.IGNORECASE,
)

# ── Banned buzzwords (LLM/filler tells + brand_strategy.md forbidden list) ─────
BANNED_BUZZWORDS = [
    "passionate", "spearheaded", "results-driven", "results driven", "synergy",
    "synergies", "proven track record", "dynamic ", "go-getter", "detail-oriented",
    "team player", "thought leader", "delve", "fast-paced", "rockstar", "ninja",
    "wheelhouse", "best-in-class", "world-class", "seamless", "leverage synerg",
    "passionné", "dynamique et", "force de proposition rare",
]

# ── Credential / client-leak guard ────────────────────────────────────────────
FORBIDDEN_TOKENS = [
    "sk-", "Bearer ", "WORKER_SECRET", "INSTANTLY_API_KEY", "GHL_API_KEY",
    "ANYMAILFINDER_API_KEY", "MILLION_VERIFIER_API_KEY",
    "Accessory Masters",          # client anonymization — must NEVER appear
    "Elite Broker", "Hedgestone",
]

CHECKLISTS = {
    "pm_en": {
        "REQUIRED_SECTIONS": [
            "PROFESSIONAL EXPERIENCE", "SKILLS", "EDUCATION",
            "LANGUAGES", "SELECTED PROJECTS",
        ],
        "REQUIRED_ENTRIES": [
            "ProdCraft", "Wiser", "InfoTnT", "Pitney Bowes", "Evolent", "Avaya",
            "Toulouse Business School", "15 years", "Stripe Connect", "85K", "1M",
            "Senior Product Manager",
        ],
        "ATS_KEYWORDS": [
            "product discovery", "roadmap", "okr", "kpi", "backlog", "priorit",
            "stakeholder", "cross-functional", "product strategy", "product lifecycle",
            "a/b test", "agile", "scrum", "prd", "user stories", "jtbd",
            "go-to-market", "data-driven", "analytics", "sql", "b2b", "saas",
            "product-market fit", "customer experience", "collaboration",
        ],
        "TITLE": "senior product manager",
        "LANG": "en",
        "TOP_KEYWORDS": [  # for the front-loaded (accroche + first role) check
            "product", "discovery", "roadmap", "okr", "delivery", "b2b", "saas",
        ],
        "DEFAULT_PDF": "deliverables/cv_generic_pm/CV MAZUMDAR Debanjan EN.pdf",
    },
    "pm_fr": {
        "REQUIRED_SECTIONS": [
            "EXPÉRIENCES PROFESSIONNELLES", "COMPÉTENCES", "FORMATION",
            "LANGUES", "PROJETS SÉLECTIONNÉS",
        ],
        "REQUIRED_ENTRIES": [
            "ProdCraft", "Wiser", "InfoTnT", "Pitney Bowes", "Evolent", "Avaya",
            "Toulouse Business School", "15 ans", "Stripe Connect", "85K", "1M",
            "Senior Product Manager",
        ],
        "ATS_KEYWORDS": [
            "discovery", "roadmap", "okr", "kpi", "backlog", "priorisation",
            "parties prenantes", "cross-fonctionnel", "stratégie", "cycle de vie",
            "a/b test", "agile", "scrum", "prd", "user stories", "jtbd",
            "go-to-market", "data", "analytics", "sql", "b2b", "saas",
            "rgpd", "expérimentation", "recherche utilisateur", "adéquation produit-marché",
            "collaboration",
        ],
        "TITLE": "senior product manager",
        "LANG": "fr",
        "TOP_KEYWORDS": [
            "produit", "discovery", "roadmap", "okr", "delivery", "b2b", "saas",
        ],
        "DEFAULT_PDF": "deliverables/cv_generic_pm/CV MAZUMDAR Debanjan FR.pdf",
    },
}

ATS_COVERAGE_MIN = 0.90   # >=90% of the PM keyword pool
MIN_METRICS = 18          # quantified markers a recruiter scans for
ABOVE_FOLD_CHARS = 1300   # top-of-page-1 slice (name -> impact strip -> first role)
ABOVE_FOLD_MIN_KEYWORDS = 4
ABOVE_FOLD_MIN_METRICS = 4
FRONTLOAD_MIN_METRICS = 6  # accroche + first role region must carry the numbers


def _detect_lang(text: str) -> str:
    try:
        from langdetect import detect  # type: ignore
        return detect(text[:3000])
    except Exception:  # noqa: BLE001 — missing/undetectable; safe: FR-function-word heuristic
        low = " " + text[:3000].lower() + " "
        fr = sum(low.count(f" {w} ") for w in ("le", "la", "les", "des", "et", "pour", "vous", "nous"))
        en = sum(low.count(f" {w} ") for w in ("the", "and", "for", "you", "we", "with"))
        return "fr" if fr > en else "en"


def _extract(pdf_path: Path) -> tuple[str, str, int]:
    """Return (full_text, page1_text, n_pages)."""
    pages = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
    return "\n".join(pages), (pages[0] if pages else ""), len(pages)


def audit(pdf_path: Path, lang_key: str) -> list[str]:
    cl = CHECKLISTS[lang_key]
    findings: list[str] = []

    if not pdf_path.exists():
        return [f"PDF not found at {pdf_path}"]

    text, page1, n_pages = _extract(pdf_path)
    low = text.lower()
    page1_low = page1.lower()
    above_fold = page1_low[:ABOVE_FOLD_CHARS]

    # 1. Page count (overflow guard)
    if n_pages != 2:
        findings.append(f"page_count: expected 2, got {n_pages}")

    # 2. Sections
    for sec in cl["REQUIRED_SECTIONS"]:
        if sec.lower() not in low:
            findings.append(f"missing_section: {sec!r}")

    # 3. Required entries (content integrity + ProdCraft + 15 yrs + $ proofs)
    for e in cl["REQUIRED_ENTRIES"]:
        if e.lower() not in low:
            findings.append(f"missing_entry: {e!r}")

    # 4. PM keyword coverage >=90%
    kws = cl["ATS_KEYWORDS"]
    hits = [k for k in kws if k.lower() in low]
    misses = [k for k in kws if k.lower() not in low]
    coverage = len(hits) / len(kws)
    if coverage < ATS_COVERAGE_MIN:
        findings.append(
            f"ats_keyword_coverage: {len(hits)}/{len(kws)} = {coverage:.0%} "
            f"(need >={ATS_COVERAGE_MIN:.0%}). Missing: {misses}"
        )

    # 5. Metric density
    metrics = _METRIC_RE.findall(text)
    if len(metrics) < MIN_METRICS:
        findings.append(f"metric_density: {len(metrics)} quantified markers (need >={MIN_METRICS})")

    # 6. Language (catches language bleed)
    detected = _detect_lang(text)
    if detected != cl["LANG"]:
        findings.append(f"language: detected {detected!r}, expected {cl['LANG']!r}")

    # 7. Credential / client-leak guard
    for tok in FORBIDDEN_TOKENS:
        if tok.lower() in low:
            findings.append(f"FORBIDDEN_TOKEN_LEAK: {tok!r}")

    # 8. Banned buzzwords = 0 (keep it human, not LLM-flavored)
    for bw in BANNED_BUZZWORDS:
        if bw.lower() in low:
            findings.append(f"banned_buzzword: {bw!r}")

    # 9. Bilingual C2 label (recruiter norm)
    label = "bilingual (c2)" if cl["LANG"] == "en" else "bilingue (c2)"
    if label not in low:
        findings.append(f"missing_cecrl_label: {label!r}")

    # 10. 3-second-scan: above-the-fold density
    if cl["TITLE"] not in above_fold:
        findings.append(f"above_fold: target title {cl['TITLE']!r} not in top {ABOVE_FOLD_CHARS} chars of page 1")
    af_kw = sum(1 for k in cl["ATS_KEYWORDS"] if k.lower() in above_fold)
    if af_kw < ABOVE_FOLD_MIN_KEYWORDS:
        findings.append(f"above_fold_keywords: {af_kw} in top slice (need >={ABOVE_FOLD_MIN_KEYWORDS})")
    af_metrics = len(_METRIC_RE.findall(above_fold))
    if af_metrics < ABOVE_FOLD_MIN_METRICS:
        findings.append(f"above_fold_metrics: {af_metrics} in top slice (need >={ABOVE_FOLD_MIN_METRICS})")

    # 11. 3-second-scan: metrics front-loaded (accroche + first role region on page 1)
    front = page1[:2200]
    front_metrics = len(_METRIC_RE.findall(front))
    if front_metrics < FRONTLOAD_MIN_METRICS:
        findings.append(f"frontloaded_metrics: {front_metrics} in page-1 top region (need >={FRONTLOAD_MIN_METRICS})")

    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["pm_en", "pm_fr"], default="pm_en")
    parser.add_argument("--pdf", type=Path, default=None)
    args = parser.parse_args()

    cl = CHECKLISTS[args.lang]
    pdf_path = (args.pdf or Path(cl["DEFAULT_PDF"])).resolve()

    print(f"Auditing ({args.lang}): {pdf_path}")
    print("-" * 64)
    findings = audit(pdf_path, args.lang)

    if pdf_path.exists():
        text, page1, n_pages = _extract(pdf_path)
        kws = cl["ATS_KEYWORDS"]
        hits = sum(1 for k in kws if k.lower() in text.lower())
        print(f"Pages              : {n_pages}")
        print(f"PM keyword coverage: {hits}/{len(kws)} = {hits/len(kws):.0%}")
        print(f"Quantified metrics : {len(_METRIC_RE.findall(text))} (need >={MIN_METRICS})")
        print(f"Language detected  : {_detect_lang(text)}")
        print()

    if findings:
        print(f"FINDINGS ({len(findings)}):")
        for f in findings:
            print(f"  - {f}")
        return 1

    print("CLEAN — 0 findings. PM CV passes the ATS + 3-second-scan gate.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
