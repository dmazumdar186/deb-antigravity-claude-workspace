"""
cv_ats_score_jd.py
description: JD-driven, hard-fail ATS acceptance gate for a targeted CV. Models a strict
    enterprise ATS (Workday / SuccessFactors / SmartRecruiters class) the way a large luxury
    group would configure it, and reports TWO numbers so neither is misread:
      - ATS-PROXY (0-100): keyword coverage + parsed-title family match + date-based tenure —
        the only things a real ATS scores. Weighted pools are hand-extracted from the JD.
      - HYGIENE (0-100): the proxy plus the recruiter-facing checks no ATS awards (live links,
        metric density, sections, contact block, 2 pages) — this is the gate's pass/fail number.
    Hard rules (any one fails the gate): banned buzzwords, credential / client leaks, missing
    required entries, unparseable bullet glyphs, >1 separator in a title line, month-without-
    year date ranges, no +33 phone, missing CECRL label, title / metrics missing above the fold.
    Also prints an informational literal-coverage line (exact JD n-grams that are absent) so a
    lost literal is visible on the diff between builds even when a lenient alias still hits.

    Title detection uses the char stream: a position title is a line whose glyphs are all in
    the bold face and whose NEXT line carries " | " plus a year — the predicate a font-weight
    segmenting parser (Textkernel / Sovren class) applies. Built from the ATS-engineer audit of
    2026-08-28 (substring false positives, headline-vs-title confusion, build/read race).

inputs: --cv <pdf> (required), --jd <pdf> (optional; sanity-checks pools against JD text),
    --min-score (default 85, applies to HYGIENE), --min-proxy (default 80, applies to ATS-PROXY)
outputs: stdout report; exit 0 = PASS, 1 = FAIL, 2 = file error

Usage:
    py tests/cv_ats_score_jd.py --cv ".tmp/cv_dior_itlead_en.pdf" --jd "C:/Users/deban/Downloads/IT lead job Desc.pdf"

Dependencies: pip install pdfplumber
"""

from __future__ import annotations

import argparse
import re
import sys
import time
from datetime import date
from pathlib import Path

import pdfplumber

# ── JD keyword pools (hand-extracted from the Dior / D_NEXT JD) ────────────────
# Each entry: acceptable surface forms (any one counts; case-insensitive; text is reflowed).
MANDATORY = {
    "IT program / project management": ["it program", "program management", "project management"],
    "digital transformation": ["digital transformation"],
    # "enterprise-wide" / "complex" deliberately NOT scored: bare adjectives are not evidence, and
    # scoring them pushed unsupported wording into the CV (2026-08-28 review, recruiter + fact-checker).
    "transformation program (bigram)": ["transformation program", "generative ai program"],
    "multidisciplinary teams": ["multidisciplinary"],
    "agile": ["agile", "scrum"],
    "product-oriented delivery": ["product-oriented delivery", "product oriented delivery"],
    "communication": ["communication"],
    "facilitation": ["facilitat"],
    "international environments": ["international environment", "us–eu–india", "us-eu-india", "distributed"],
    "english proficiency": ["english"],
}

DESIRABLE = {
    "generative AI": ["generative ai", "genai"],
    "AI-assisted software engineering tools": ["ai-assisted software engineering"],
    "GitHub Copilot": ["copilot"],
    "agentic development": ["agentic development", "agentic"],
    "AI SDLC": ["ai sdlc"],
    "specification driven development": ["specification-driven", "specification driven"],
    "retail": ["retail"],
    "luxury": ["luxury"],
    "digital commerce": ["digital-commerce", "digital commerce", "e-commerce"],
    "global corporate IT": ["global corporate it", "global enterprise"],
}

RESPONSIBILITY = {
    "implementation / deployment roadmap": ["roadmap"],
    "governance": ["governance"],
    "steering": ["steering"],
    "operational committee": ["operational committee"],
    "executive reporting": ["executive reporting"],
    "decision support": ["decision support"],
    "product managers / product owners": ["product manager", "product owner"],
    "architects": ["architect"],
    "security": ["security"],
    "partners": ["partner"],
    "dependency management": ["dependenc"],
    "escalation point": ["escalation"],
    "delivery risks": ["risk"],
    "identify and mitigate risks": ["mitigat"],
    "change management": ["change management"],
    "adoption strategy": ["adoption strategy"],
    "adoption metrics / KPIs": ["adoption"],
    "training / knowledge sharing": ["training", "knowledge sharing", "knowledge-sharing", "enablement"],
    "community / workshops": ["community", "workshop"],
    "ways of working": ["ways of working"],
    "continuous improvement": ["continuous improvement", "continuous-improvement"],
    "budget": ["budget"],
    "forecast": ["forecast"],
    "compliance / privacy": ["compliance", "privacy", "gdpr"],
    "vendor": ["vendor"],
    "measurable value": ["measurable"],
    "operating model": ["operating model"],
    "leadership without formal authority": ["without formal authority", "rather than formal authority",
                                            "no line authority", "without line authority"],
    "executive stakeholder management": ["executive stakeholder", "stakeholder management", "executive reporting"],
    "influence": ["influence"],
    "data-driven decision making": ["data-driven decision", "data driven decision"],
    "navigate ambiguity": ["ambigu"],
}

DELIVERABLES = {
    "program charter": ["program charter"],
    "deployment roadmap": ["deployment roadmap"],
    "governance framework": ["governance framework"],
    "stakeholder mapping": ["stakeholder mapping"],
    "risk & dependency register": ["dependency register"],
    "adoption & change management plan": ["adoption strategy & planning", "adoption planning", "change management plan"],
    "KPI & value measurement dashboard": ["kpi & value measurement", "value measurement", "kpi dashboard"],
    "steering committee materials / operational reporting": ["steering", "operational committee"],
    "deployment progress reports": ["progress report"],
}

# Exact JD n-grams — informational only; a miss here is visible even when an alias above hits.
JD_LITERALS = [
    "it program management", "digital transformation", "enterprise-wide", "transformation program",
    "multidisciplinary", "complex", "agile", "product-oriented delivery", "communication",
    "facilitat", "international", "english", "generative ai", "ai-assisted software engineering",
    "github copilot", "agentic development", "ai sdlc", "specification-driven development",
    "retail", "luxury", "digital commerce", "global corporate it", "program charter",
    "deployment roadmap", "governance framework", "stakeholder mapping", "dependency register",
    "change management", "value measurement", "steering committee", "operational committee",
    "progress report", "budget", "forecast", "vendor", "knowledge sharing", "community",
    "training", "adoption strategy", "operating model", "escalation", "decision support",
    "executive reporting", "without formal authority", "influence", "data-driven",
    "ambiguity", "measurable", "consultant", "project manag", "at scale", "large-scale",
    "enterprise architect", "platform team", "security team", "business value",
    "value creation", "governance bodies", "executive steering committee", "program leadership",
]

TARGET_TITLE_FORMS = ["senior it lead", "it program", "it lead", "program lead", "program manager",
                      "project manager", "lead consultant", "transformation lead"]
MIN_YEARS = 10

BANNED_BUZZWORDS = [
    "passionate", "spearheaded", "results-driven", "results driven", "synergy", "synergies",
    "proven track record", "go-getter", "detail-oriented", "team player", "thought leader",
    "delve", "fast-paced", "rockstar", "ninja", "wheelhouse", "best-in-class", "world-class",
    "seamless", "leverage synerg", "visionary", "guru", "responsible for",
]

FORBIDDEN_TOKENS = [
    "sk-", "Bearer ", "WORKER_SECRET", "INSTANTLY_API_KEY", "GHL_API_KEY",
    "ANYMAILFINDER_API_KEY", "MILLION_VERIFIER_API_KEY",
    "Accessory Masters", "Elite Broker", "Hedgestone",
]

REQUIRED_SECTIONS = ["PROFESSIONAL EXPERIENCE", "SKILLS", "EDUCATION", "LANGUAGES", "SELECTED PROJECTS"]
REQUIRED_LINKS = ["linkedin.com/in/", "github.com/", "prodcraft.fyi"]
REQUIRED_ENTRIES = ["Wiser", "ProdCraft", "InfoTnT", "Pitney Bowes", "Evolent", "Avaya",
                    "Toulouse Business School", "15 years"]

_METRIC_RE = re.compile(
    r"(?:[+\-−]?\s?\d+(?:[.,]\d+)?\s?%"
    r"|[$€£]\s?\d+(?:[.,]\d+)?\s?[KkMmBb]?\+?"
    r"|\b\d[\d,]*\+"
    r"|[<>]\s?\d+)",
    re.IGNORECASE,
)
_DATE_RANGE_RE = re.compile(r"\b([A-Z][a-z]{2} )?(20\d{2}|19\d{2}) – (([A-Z][a-z]{2} )?(20\d{2}|19\d{2})|Present)\b")
_MONTHS = {m: i for i, m in enumerate(
    ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"], 1)}

ABOVE_FOLD_CHARS = 1300
MIN_METRICS = 18


# ── Extraction ────────────────────────────────────────────────────────────────

def _extract(pdf_path: Path):
    """Return (full_text, page1_text, n_pages, links, lines) where lines is a list of
    (text, all_bold) tuples in reading order, built from the char stream."""
    pages, links, lines = [], [], []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            pages.append(page.extract_text() or "")
            for a in (page.hyperlinks or []):
                uri = a.get("uri") or ""
                if uri:
                    links.append(uri)
            words = page.extract_words(extra_attrs=["fontname"], keep_blank_chars=False)
            rows: dict[int, list] = {}
            for w in words:
                rows.setdefault(round(w["top"] / 2), []).append(w)
            for key in sorted(rows):
                ws = sorted(rows[key], key=lambda w: w["x0"])
                text = " ".join(w["text"] for w in ws)
                bold = all("bold" in w["fontname"].lower() for w in ws)
                lines.append((text, bold))
    return "\n".join(pages), (pages[0] if pages else ""), len(pages), links, lines


def _position_titles(lines) -> list[tuple[str, str]]:
    """(title_line, next_line) pairs: a bold-only line followed by a line with ' | ' + a year."""
    out = []
    for i in range(len(lines) - 1):
        text, bold = lines[i]
        nxt = lines[i + 1][0]
        # " — " excludes education lines (degree / "school | years"), which are bold too.
        if bold and len(text) > 8 and " — " in text and " | " in nxt \
                and re.search(r"(19|20)\d{2}", nxt) and not text.isupper():
            out.append((text, nxt))
    return out


def _months(rng: str) -> int:
    m = _DATE_RANGE_RE.search(rng)
    if not m:
        return 0
    sm = _MONTHS.get((m.group(1) or "Jan ").strip(), 1)
    sy = int(m.group(2))
    if m.group(3) == "Present":
        today = date.today()
        ey, em = today.year, today.month
    else:
        em = _MONTHS.get((m.group(4) or "Dec ").strip(), 12)
        ey = int(m.group(5))
    return max(0, (ey - sy) * 12 + (em - sm) + 1)


def _pool_hits(pool: dict[str, list[str]], low: str):
    hits, misses = [], []
    for name, forms in pool.items():
        (hits if any(f in low for f in forms) else misses).append(name)
    return hits, misses


# ── Scoring ───────────────────────────────────────────────────────────────────

def score(cv_path: Path, jd_path: Path | None):
    hard: list[str] = []
    rep: list[str] = []

    if time.time() - cv_path.stat().st_mtime < 2:
        time.sleep(2)  # never read a PDF the builder may still be writing

    text, page1, n_pages, links, lines = _extract(cv_path)
    # Real ATS parsers reflow line breaks before matching.
    low = re.sub(r"\s+", " ", text.lower().replace("\u2011", "-").replace("\u00a0", " "))
    above_fold = re.sub(r"\s+", " ", page1.lower())[:ABOVE_FOLD_CHARS]

    if jd_path and jd_path.exists():
        jd_text = _extract(jd_path)[0].lower()
        probes = {"program charter", "governance", "steering", "copilot", "agentic", "luxury",
                  "budget", "adoption", "stakeholder mapping", "without formal authority"}
        rep.append(f"JD sanity probes missing from JD text: {[p for p in probes if p not in jd_text] or 'none'}")

    # ── ATS-PROXY: keywords (70) + title (20) + tenure (10) → 0-100 ─────────────
    weights = {"MANDATORY": 25, "DESIRABLE": 20, "RESPONSIBILITY": 15, "DELIVERABLES": 10}
    pools = {"MANDATORY": MANDATORY, "DESIRABLE": DESIRABLE,
             "RESPONSIBILITY": RESPONSIBILITY, "DELIVERABLES": DELIVERABLES}
    kw_points = 0.0
    for name, pool in pools.items():
        hits, misses = _pool_hits(pool, low)
        frac = len(hits) / len(pool)
        kw_points += weights[name] * frac
        rep.append(f"{name:<15} {len(hits):>2}/{len(pool):<2} = {frac:5.0%}  -> {weights[name]*frac:4.1f}/{weights[name]}  missing: {misses}")

    titles = _position_titles(lines)
    title_texts = [t for t, _ in titles]
    # A real ATS weights the PRIMARY (first / most recent) position; a hit on a secondary,
    # concurrent role counts less; the headline counts least (per ATS-engineer audit).
    primary_hit = bool(title_texts) and any(f in title_texts[0].lower() for f in TARGET_TITLE_FORMS)
    other_hit = any(f in t.lower() for t in title_texts[1:] for f in TARGET_TITLE_FORMS)
    headline_hit = any(f in above_fold for f in TARGET_TITLE_FORMS)
    title_hit = primary_hit or other_hit
    title_pts = 20 if primary_hit else (12 if other_hit else (8 if headline_hit else 0))
    rep.append(f"Parsed position titles ({len(titles)}): {title_texts}")
    rep.append(f"Title-family match: primary={primary_hit} other={other_hit} headline={headline_hit} -> {title_pts}/20")

    years_in_dates = [int(y) for y in re.findall(r"\b(20\d{2}|19\d{2})\b", "\n".join(n for _, n in titles))]
    span = (2026 - min(years_in_dates)) if years_in_dates else 0
    fam_months = sum(_months(n) for t, n in titles if any(f in t.lower() for f in TARGET_TITLE_FORMS))
    tenure_pts = 10 if span >= MIN_YEARS else round(10 * span / MIN_YEARS)
    rep.append(f"Tenure: span {span} yrs from dates (need >={MIN_YEARS}); "
               f"under a program/lead/consultant title: {fam_months/12:.1f} yrs -> {tenure_pts}/10")
    proxy = round(kw_points + title_pts + tenure_pts)

    # ── HYGIENE additions (recruiter-facing; no ATS awards these) ───────────────
    struct_pts = 0
    if all(s.lower() in low for s in REQUIRED_SECTIONS):
        struct_pts += 3
    else:
        hard.append(f"missing_section: {[s for s in REQUIRED_SECTIONS if s.lower() not in low]}")
    phone_ok = re.search(r"(\+33\s?\d(?:\s?\d{2}){4}|\b0\d(?:\s?\d{2}){4})", text) is not None
    if "@" in low and phone_ok and "paris" in low:
        struct_pts += 2
    else:
        hard.append("contact_block: email / phone / city not all parseable")
    if n_pages == 2:
        struct_pts += 2
    else:
        hard.append(f"page_count: expected 2, got {n_pages}")

    link_hits = [l for l in REQUIRED_LINKS if any(l in u for u in links)]
    link_pts = round(5 * len(link_hits) / len(REQUIRED_LINKS))
    if len(link_hits) < len(REQUIRED_LINKS):
        hard.append(f"hyperlinks: missing {[l for l in REQUIRED_LINKS if l not in link_hits]}")
    metrics = _METRIC_RE.findall(text)
    metric_pts = 5 if len(metrics) >= MIN_METRICS else round(5 * len(metrics) / MIN_METRICS)
    rep.append(f"Hygiene: structure {struct_pts}/7, links {len(links)} annot / required {len(link_hits)}/3 -> {link_pts}/5, "
               f"metrics {len(metrics)} -> {metric_pts}/5")
    # Recruiter-facing checks reported on their own 0-100 scale (17 raw points), not blended
    # into the proxy — blending made the two numbers coincide whenever hygiene passed.
    hygiene = round(100 * (struct_pts + link_pts + metric_pts) / 17)

    # ── Literal coverage (informational) ────────────────────────────────────────
    missing_lit = [l for l in JD_LITERALS if l not in low]
    rep.append(f"JD literal n-grams absent ({len(missing_lit)}/{len(JD_LITERALS)}): {missing_lit}")

    # ── Hard rules ──────────────────────────────────────────────────────────────
    for bw in BANNED_BUZZWORDS:
        if bw in low:
            hard.append(f"banned_buzzword: {bw!r}")
    for tok in FORBIDDEN_TOKENS:
        if tok.lower() in low:
            hard.append(f"FORBIDDEN_TOKEN_LEAK: {tok!r}")
    for e in REQUIRED_ENTRIES:
        if e.lower() not in low:
            hard.append(f"missing_entry: {e!r}")
    if len(_METRIC_RE.findall(above_fold)) < 4:
        hard.append("above_fold_metrics: <4 in top slice of page 1")
    if not headline_hit:
        hard.append("above_fold_title: no target-title form in top slice of page 1")
    if "bilingual (c2)" not in low:
        hard.append("missing_cecrl_label: 'bilingual (c2)'")
    if "(cid:" in text:
        hard.append("parser_glyph: '(cid:' in extracted text — a glyph has no ToUnicode map")
    for t, n in titles:
        if t.count(" — ") > 1:
            hard.append(f"title_line_separators: >1 em dash in {t[:70]!r}")
        if re.search(r"\b[A-Z][a-z]{2}\.? – [A-Z][a-z]{2}\.? 20\d{2}", n):
            hard.append(f"date_range: start month without year in {n[:60]!r}")
    if not re.search(r"\+33\s?\d", text):
        hard.append("phone: no +33 country code")
    if not titles:
        hard.append("no_position_titles_parsed: bold-title + '| date' predicate found nothing")

    return proxy, hygiene, hard, rep


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # report carries U+2212 / em dashes
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", type=Path, required=True)
    ap.add_argument("--jd", type=Path, default=None)
    ap.add_argument("--min-score", type=int, default=85, help="HYGIENE threshold")
    ap.add_argument("--min-proxy", type=int, default=80, help="ATS-PROXY threshold")
    args = ap.parse_args()

    if not args.cv.exists():
        print(f"ERROR: CV not found: {args.cv}")
        return 2

    proxy, hygiene, hard, rep = score(args.cv, args.jd)
    print(f"ATS (JD-driven) audit: {args.cv}")
    print("-" * 72)
    for line in rep:
        print("  " + line)
    print("-" * 72)
    print(f"ATS-PROXY (keywords + title + tenure):        {proxy}/100  (threshold {args.min_proxy})")
    print(f"HYGIENE   (recruiter checks only, 17 raw pts): {hygiene}/100  (threshold {args.min_score})")
    if hard:
        print(f"HARD FAILURES ({len(hard)}):")
        for h in hard:
            print(f"  - {h}")
    ok = hygiene >= args.min_score and proxy >= args.min_proxy and not hard
    print("VERDICT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
