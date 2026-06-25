#!/usr/bin/env python3
"""
check_metric_coherence.py
description: Hard-fail gate asserting CV (EN/FR PDFs), LinkedIn copy, and the
             prodcraft.fyi site all use the ONE canonical metric set and contain
             no retired/contradicting variants. Enforces metrics_canonical.md.
inputs: none (reads sibling files + portfolio_site content + personal_brand/cv PDFs)
outputs: stdout report; exit 0 = coherent, exit 1 = contradiction found

Why this exists: a recruiter who cross-references surfaces and sees "24k here,
48k there" takes the credibility hit this gate kills. Public values only are
scanned — JSON keys prefixed with "_" (audit trail like _source_real) and
metrics_canonical.md itself are excluded by design.

Run: py execution/personal_workflows/personal_brand/check_metric_coherence.py
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[2]
SITE_CONTENT = REPO / "execution" / "personal_workflows" / "portfolio_site" / "src" / "content"
CV_DIR = HERE / "cv"


def normalize(text: str) -> str:
    """Fold unicode dashes/spaces to ASCII so patterns match regardless of typography."""
    for dash in ("−", "–", "—"):  # minus, en-dash, em-dash
        text = text.replace(dash, "-")
    for sp in (" ", " ", " ", " ", " "):  # nbsp, en/thin/narrow spaces
        text = text.replace(sp, " ")
    return text


# Public values that MUST NOT appear on any surface (the cross-reference killers).
# Each: (label, compiled regex). metrics_canonical.md is exempt (it lists them as retired).
RETIRED = [
    ("old volume 24,000",        re.compile(r"24[,\s]?000")),
    ("retired EUR 2M ARR",       re.compile(r"(?:eur|euro|€)\s?2\s?m|2\s?m\+?\s*arr", re.I)),
    ("retired retention claim",  re.compile(r"\bretention\b", re.I)),
    ("retired churn claim",      re.compile(r"\bchurn\b", re.I)),
    ("old adoption +30%",        re.compile(r"\+\s?30\s?%\s*(?:feature\s+)?adoption|adoption[^.]{0,12}\+\s?30\s?%", re.I)),
    ("old latency -40%",         re.compile(r"-\s?40\s?%\s*(?:p95\s+)?latency|latency[^.]{0,12}-\s?40\s?%", re.I)),
    ("forbidden client name",    re.compile(r"accessory\s*masters|elite\s*broker", re.I)),
]

# Canonical headline numbers each surface should carry (presence check).
CANON_CORE = [
    ("$1M pipeline",   re.compile(r"\$\s?1\s?m\+?", re.I)),
    ("48,000+ emails", re.compile(r"48[,\s]?000")),
    ("+45% adoption",  re.compile(r"\+\s?45\s?%")),
    ("-55% latency",   re.compile(r"-\s?55\s?%")),
]


def public_strings_from_json(path: Path) -> list[str]:
    """Collect string values, skipping any key whose name starts with '_' (audit trail)."""
    out: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if isinstance(k, str) and k.startswith("_"):
                    continue
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
        elif isinstance(node, str):
            out.append(node)

    walk(json.loads(path.read_text(encoding="utf-8")))
    return out


def pdf_text(path: Path) -> str:
    from pypdf import PdfReader
    return "\n".join(pg.extract_text() or "" for pg in PdfReader(str(path)).pages)


def gather_surfaces() -> dict[str, str]:
    """Return {surface_name: normalized_public_text}."""
    surfaces: dict[str, str] = {}

    # Website: public JSON strings only.
    site_chunks = []
    for jf in sorted(SITE_CONTENT.glob("*.json")):
        site_chunks.extend(public_strings_from_json(jf))
    if site_chunks:
        surfaces["website (prodcraft.fyi content)"] = normalize("\n".join(site_chunks))

    # LinkedIn copy doc (whole file — it is the public-copy source).
    li = HERE / "linkedin_profile.md"
    if li.exists():
        surfaces["linkedin_profile.md"] = normalize(li.read_text(encoding="utf-8"))

    # CV PDFs (the actual artifacts a recruiter reads).
    for pdf in sorted(CV_DIR.glob("*.pdf")):
        surfaces[f"CV {pdf.name}"] = normalize(pdf_text(pdf))

    return surfaces


def main() -> int:
    surfaces = gather_surfaces()
    if not surfaces:
        print("FAIL: no surfaces found to check.")
        return 1

    failures: list[str] = []
    print("=== Metric coherence gate (enforces metrics_canonical.md) ===\n")

    for name, text in surfaces.items():
        print(f"[{name}]")
        # 1) Retired/contradicting variants -> hard fail.
        for label, rx in RETIRED:
            m = rx.search(text)
            if m:
                ctx = text[max(0, m.start() - 30): m.end() + 30].replace("\n", " ")
                failures.append(f"{name}: retired/contradicting variant '{label}' -> ...{ctx}...")
                print(f"  X retired variant: {label}  -> ...{ctx.strip()}...")
        # 2) Canonical presence (CV + LinkedIn carry the full core; website too).
        missing = [lab for lab, rx in CANON_CORE if not rx.search(text)]
        if missing:
            # Presence is a soft signal for some surfaces (e.g. a single JSON tile),
            # but every primary surface here should carry all four. Treat as failure.
            failures.append(f"{name}: missing canonical value(s): {', '.join(missing)}")
            print(f"  X missing canonical: {', '.join(missing)}")
        if not missing and not any(f.startswith(name) for f in failures):
            print("  OK: canonical values present, no retired variants")
        print()

    if failures:
        print(f"RESULT: FAIL ({len(failures)} issue(s))")
        for f in failures:
            print(f"  - {f}")
        return 1

    print("RESULT: PASS - all surfaces coherent with canonical metric set.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
