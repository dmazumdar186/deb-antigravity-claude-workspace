#!/usr/bin/env python3
"""
cv_ats_check.py
description: Audit the generated CV PDF for page count, ATS readability, keyword coverage, dates, and new-entry presence
inputs: --pdf path (default .tmp/cv_master_debanjan_mazumdar.pdf)
outputs: stdout report; exit 0 = all checks pass, 1 = at least one finding

Usage:
    py tests/cv_ats_check.py
    py tests/cv_ats_check.py --pdf .tmp/cv_master_debanjan_mazumdar.pdf
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pdfplumber


# ─ Cached audit checklist ────────────────────────────────────────────────────

CHECKLISTS = {
    "fr": {
        "REQUIRED_SECTIONS": [
            "EXPÉRIENCES PROFESSIONNELLES",
            "COMPÉTENCES",
            "FORMATION",
            "LANGUES",
            "PROJETS PERSONNELS",
        ],
        "REQUIRED_NEW_ENTRIES": [
            "Mission Freelance",
            "Accessory Masters",
            "job_search_v2",          # ship of 2026-06-15, must be visible
            "Anneal",
            "YouTube Video Analyzer",
            "Job Tracker PM France",
            "Self-Outbound Engine",
            "CV Optimizer Agent",
            "ProdCraft",
            "15 ans",
        ],
        "ATS_KEYWORDS": [
            # 2026 AI/PM keyword pool — extended for FR recruiters
            "LLM", "RAG", "Agentic", "Multi-Agents", "MCP", "A2A",
            "Roadmap", "PRD", "Discovery", "JTBD", "OKR", "KPI",
            "A/B", "ML supervisé", "RGPD", "GTM", "Backlog",
            "Cross-fonctionnel", "Vision", "Stakeholder",
            # 2026 additions
            "Pydantic", "Gemini", "audit-loop", "gouvernance",
            "Cloudflare Workers", "Modal cron", "garde-fous",
            "évaluation", "non-déterminisme", "privacy-by-design",
        ],
        "REQUIRED_DATES": [
            "juin 2026",       # job_search_v2 ship date
            "Déc. 2025",
            "Mars 2026",
            "Nov. 2022",
            "Juin 2021",
            "Nov. 2010",
        ],
        "BILINGUE_LABEL": "Bilingue (C2)",  # CECRL scale per FR norms 2026
        "DEFAULT_PDF": ".tmp/cv_master_debanjan_mazumdar.pdf",
    },
    "en": {
        "REQUIRED_SECTIONS": [
            "PROFESSIONAL EXPERIENCE",
            "SKILLS",
            "EDUCATION",
            "LANGUAGES",
            "PERSONAL PROJECTS",
        ],
        "REQUIRED_NEW_ENTRIES": [
            "Freelance Engagement",
            "Accessory Masters",
            "job_search_v2",          # ship of 2026-06-15
            "Anneal",
            "YouTube Video Analyzer",
            "Job Tracker PM France",
            "Self-Outbound Engine",
            "CV Optimizer Agent",
            "ProdCraft",
            "15 years",
        ],
        "ATS_KEYWORDS": [
            "LLM", "RAG", "Agentic", "Multi-Agent", "MCP", "A2A",
            "Roadmap", "PRD", "Discovery", "JTBD", "OKR", "KPI",
            "A/B", "supervised", "GDPR", "GTM", "Backlog",
            "Cross-functional", "Vision", "Stakeholder",
            # 2026 additions
            "Pydantic", "Gemini", "audit-loop", "governance",
            "Cloudflare Workers", "Modal cron", "guardrails",
            "evaluation", "non-determinism", "privacy-by-design",
        ],
        "REQUIRED_DATES": [
            "Jun. 2026",
            "Dec. 2025",
            "Mar. 2026",
            "Nov. 2022",
            "Jun. 2021",
            "Nov. 2010",
        ],
        "BILINGUE_LABEL": "Bilingual (C2)",
        "DEFAULT_PDF": ".tmp/cv_master_debanjan_mazumdar_en.pdf",
    },
}

ATS_MIN_HITS = 27  # ≥ 90 % of the 30-keyword pool
MIN_BOLDED_METRICS = 18  # density check — at least 18 numeric-with-%/d/€/k markers

# Tokens that must NOT appear (credential / leak guard).
FORBIDDEN_TOKENS = [
    "sk-",          # generic API key prefix
    "Bearer ",
    "WORKER_SECRET",
    "INSTANTLY_API_KEY",
    "GHL_API_KEY",
    "ANYMAILFINDER_API_KEY",
    "MILLION_VERIFIER_API_KEY",
]


def extract_text(pdf_path: Path) -> tuple[str, int]:
    pages_text = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages_text.append(page.extract_text() or "")
    return "\n".join(pages_text), len(pages_text)


_METRIC_RE = __import__("re").compile(
    r"[+\-−]?\s*\d+(?:[.,]\d+)?\s*(?:%|€|/jour|/day|/mois|/month|emails?/(?:mois|month|day|jour))",
    __import__("re").IGNORECASE,
)


def audit(pdf_path: Path, lang: str):
    cl = CHECKLISTS[lang]
    findings: list[str] = []

    if not pdf_path.exists():
        return [f"PDF not found at {pdf_path}"], 0, 0, "", 0

    text, n_pages = extract_text(pdf_path)
    text_lower = text.lower()

    if n_pages != 2:
        findings.append(f"page_count: expected 2, got {n_pages}")

    for sec in cl["REQUIRED_SECTIONS"]:
        if sec.lower() not in text_lower:
            findings.append(f"missing_section: {sec!r}")

    for entry in cl["REQUIRED_NEW_ENTRIES"]:
        if entry.lower() not in text_lower:
            findings.append(f"missing_entry: {entry!r}")

    hits = [kw for kw in cl["ATS_KEYWORDS"] if kw.lower() in text_lower]
    misses = [kw for kw in cl["ATS_KEYWORDS"] if kw.lower() not in text_lower]
    if len(hits) < ATS_MIN_HITS:
        findings.append(
            f"ats_keywords: {len(hits)}/{len(cl['ATS_KEYWORDS'])} hits "
            f"(need >={ATS_MIN_HITS}). Missing: {misses}"
        )

    for d in cl["REQUIRED_DATES"]:
        if d not in text:
            findings.append(f"missing_date: {d!r}")

    for tok in FORBIDDEN_TOKENS:
        if tok in text:
            findings.append(f"FORBIDDEN_TOKEN_LEAK: {tok!r}")

    # 2026 addition: CECRL language label (Bilingue/Bilingual C2) — French recruiter norm
    if cl["BILINGUE_LABEL"] not in text:
        findings.append(f"missing_cecrl_label: {cl['BILINGUE_LABEL']!r} not found in text")

    # 2026 addition: metric-density check — recruiters scan for bolded numbers
    metric_count = len(_METRIC_RE.findall(text))
    if metric_count < MIN_BOLDED_METRICS:
        findings.append(
            f"metric_density: only {metric_count} quantified metrics (need >={MIN_BOLDED_METRICS})"
        )

    return findings, len(hits), n_pages, text, metric_count


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["fr", "en"], default="fr")
    parser.add_argument("--pdf", type=Path, default=None)
    args = parser.parse_args()

    cl = CHECKLISTS[args.lang]
    pdf_path = (args.pdf or Path(cl["DEFAULT_PDF"])).resolve()

    print(f"Auditing ({args.lang}): {pdf_path}")
    print("-" * 60)

    findings, kw_hits, n_pages, _text, metric_count = audit(pdf_path, args.lang)

    print(f"Pages              : {n_pages}")
    print(f"ATS keyword hits   : {kw_hits}/{len(cl['ATS_KEYWORDS'])}")
    print(f"Quantified metrics : {metric_count} (need >={MIN_BOLDED_METRICS})")
    print()

    if findings:
        print(f"FINDINGS ({len(findings)}):")
        for f in findings:
            print(f"  - {f}")
        return 1

    print("CLEAN — 0 findings.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
