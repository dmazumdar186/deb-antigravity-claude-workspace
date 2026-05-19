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
            "Anneal",
            "YouTube Video Analyzer",
            "Job Tracker PM France",
            "Self-Outbound Engine",
            "CV Optimizer Agent",
            "ProdCraft",
            "15 ans",
        ],
        "ATS_KEYWORDS": [
            "LLM", "RAG", "Agentic", "Multi-Agents", "MCP", "A2A",
            "Roadmap", "PRD", "Discovery", "JTBD", "OKR", "KPI",
            "A/B", "ML supervisé", "RGPD", "GTM", "Backlog",
            "Cross-fonctionnel", "Vision", "Stakeholder",
        ],
        "REQUIRED_DATES": [
            "Déc. 2025",
            "Mars 2026",
            "Nov. 2022",
            "Juin 2021",
            "Nov. 2010",
        ],
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
        ],
        "REQUIRED_DATES": [
            "Dec. 2025",
            "Mar. 2026",
            "Nov. 2022",
            "Jun. 2021",
            "Nov. 2010",
        ],
        "DEFAULT_PDF": ".tmp/cv_master_debanjan_mazumdar_en.pdf",
    },
}

ATS_MIN_HITS = 18  # ≥ 90 %

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


def audit(pdf_path: Path, lang: str):
    cl = CHECKLISTS[lang]
    findings: list[str] = []

    if not pdf_path.exists():
        return [f"PDF not found at {pdf_path}"], 0, 0, ""

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
            f"(need ≥{ATS_MIN_HITS}). Missing: {misses}"
        )

    for d in cl["REQUIRED_DATES"]:
        if d not in text:
            findings.append(f"missing_date: {d!r}")

    for tok in FORBIDDEN_TOKENS:
        if tok in text:
            findings.append(f"FORBIDDEN_TOKEN_LEAK: {tok!r}")

    return findings, len(hits), n_pages, text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", choices=["fr", "en"], default="fr")
    parser.add_argument("--pdf", type=Path, default=None)
    args = parser.parse_args()

    cl = CHECKLISTS[args.lang]
    pdf_path = (args.pdf or Path(cl["DEFAULT_PDF"])).resolve()

    print(f"Auditing ({args.lang}): {pdf_path}")
    print("-" * 60)

    findings, kw_hits, n_pages, _text = audit(pdf_path, args.lang)

    print(f"Pages              : {n_pages}")
    print(f"ATS keyword hits   : {kw_hits}/{len(cl['ATS_KEYWORDS'])}")
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
