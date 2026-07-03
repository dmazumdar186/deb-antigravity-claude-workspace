#!/usr/bin/env python3
"""
jd_keyword_research.py
description: Collect >=25 FR + >=25 EN Product-Manager job descriptions from FREE reused
    job_search_v2 connectors (LinkedIn jobs-guest API, WTTJ Algolia, RemoteOK, WeWorkRemotely
    - no scraping, no credentials, EUR0 cost) and extract a ranked, CV-usable keyword "cloud"
    per language. Deterministic extraction (no LLM): a bilingual PM competency lexicon counted
    across the corpus, plus emergent stopword-filtered unigram/bigram frequency.
inputs:
  - CLI: --posted-within-hours (default 720 = 30d, wider window = bigger corpus),
         --min-per-lang (default 25), --li-pages (default 2)
  - env: none (all sources are public)
outputs:
  - .tmp/jd_research/corpus_{fr,en}.txt      (raw title+description text, one JD per block)
  - .tmp/jd_research/keywords_{fr,en}.md     (ranked lexicon table + frequency word cloud)
  - .tmp/jd_research/keywords.json           (machine-readable, consumed by the CV gate)
  - stdout: per-source counts, per-language totals, top-30 keywords, floor pass/fail

Prior-art: reuses execution/personal_workflows/job_search_v2/sources/* fetch() adapters
(the workspace already solved live PM-JD fetching at EUR0 - see prior-art-first rule).

Dependencies: httpx, beautifulsoup4 (via the reused sources); langdetect (optional, has a
FR-heuristic fallback). No paid API is called.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter
from pathlib import Path

# ── Path bootstrap so we can import the reused job_search_v2 source adapters ────
PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.personal_workflows.job_search_v2.sources import (  # noqa: E402
    linkedin_guest_api,
    wttj_algolia,
    remoteok,
    weworkremotely,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger("jd_keyword_research")

OUT_DIR = PROJECT_ROOT / ".tmp" / "jd_research"

# ── PM keyword set used to steer the (keyword-driven) sources ─────────────────
PM_QUERY_KEYWORDS = [
    "senior product manager", "product manager", "lead product manager",
    "head of product", "group product manager", "principal product manager",
    "product owner", "chef de produit", "responsable produit", "directeur produit",
]

# ── Title gate: keep only genuinely PM-ish postings in the corpus ─────────────
_PM_TITLE_RE = re.compile(
    r"\b("
    r"product manager|product owner|head of product|chief product|group product|"
    r"principal product|senior product|lead product|"
    r"chef(?:fe)? de produit|responsable produit|directeur produit|directrice produit|"
    r"product lead|vp product|product director"
    r")\b",
    re.IGNORECASE,
)

# ── Bilingual PM competency lexicon (the CV-usable, high-value keyword pool) ───
# Each canonical term maps to the regex variants that count toward it. Ordering here
# does not matter; output is ranked by measured frequency in the collected corpus.
LEXICON: dict[str, list[str]] = {
    # discovery & strategy
    "Product Discovery": [r"discovery", r"découverte produit", r"product discovery"],
    "Product Strategy": [r"product strategy", r"stratégie produit"],
    "Product Vision": [r"product vision", r"vision produit"],
    "Roadmap": [r"roadmap", r"feuille de route"],
    "User Research": [r"user research", r"recherche utilisateur", r"user interviews", r"entretiens utilisateurs"],
    "JTBD": [r"jobs[- ]to[- ]be[- ]done", r"jtbd"],
    "Market Research": [r"market research", r"étude de marché", r"competitive analysis", r"analyse concurrentielle"],
    # delivery & agile
    "Agile": [r"\bagile\b"],
    "Scrum": [r"\bscrum\b"],
    "Kanban": [r"\bkanban\b"],
    "Backlog": [r"backlog"],
    "Sprint": [r"\bsprint"],
    "Prioritization": [r"prioriti[sz]ation", r"priorisation", r"prioriti[sz]e", r"prioriser"],
    "User Stories": [r"user stor(?:y|ies)", r"user stories"],
    "PRD": [r"\bprd\b", r"product requirements", r"spécifications"],
    "Cross-functional": [r"cross[- ]functional", r"cross[- ]fonctionnel", r"transverse", r"pluridisciplinaire"],
    "Stakeholder Management": [r"stakeholder", r"parties prenantes"],
    # metrics & experimentation
    "KPI": [r"\bkpi", r"metrics", r"métriques", r"indicateurs"],
    "OKR": [r"\bokr"],
    "A/B Testing": [r"a/b test", r"a/b testing", r"experimentation", r"expérimentation"],
    "Data-Driven": [r"data[- ]driven", r"data[- ]informed", r"orienté données", r"piloté par la donnée"],
    "Analytics": [r"analytics", r"analytique"],
    "SQL": [r"\bsql\b"],
    # gtm & lifecycle
    "Go-To-Market": [r"go[- ]to[- ]market", r"\bgtm\b", r"mise sur le marché", r"lancement"],
    "Product Lifecycle": [r"product lifecycle", r"cycle de vie produit"],
    "Product-Market Fit": [r"product[- ]market fit", r"adéquation produit[- ]marché"],
    "Customer Experience": [r"customer experience", r"expérience client", r"\bux\b", r"user experience", r"expérience utilisateur"],
    # domain & governance
    "B2B": [r"\bb2b\b"],
    "B2C": [r"\bb2c\b"],
    "SaaS": [r"\bsaas\b"],
    "API": [r"\bapi\b", r"apis"],
    "GDPR": [r"gdpr", r"rgpd"],
    "AI/ML": [r"\bai\b", r"artificial intelligence", r"\bml\b", r"machine learning", r"\bia\b", r"intelligence artificielle", r"genai"],
    # ways of working
    "Leadership": [r"leadership", r"leader", r"management", r"encadrement"],
    "Communication": [r"communication", r"communicant"],
    "Ownership": [r"ownership", r"autonom"],
    "Collaboration": [r"collaborat"],
}

# ── Stopwords for the emergent-term frequency pass (FR + EN) ───────────────────
_STOP = set("""
a an and are as at be by for from has have in into is it its of on or that the to with we you
your our their this these those will can our us not but they he she them who what which when how
role team teams work working job jobs company companies experience years year skills ability
looking join build building help make new all more your you will about across per within via
d de la le les des du un une et en pour dans sur au aux avec ou nous vous votre notre leur ce
cette ces qui que quoi dont est sont être avoir plus poste équipe équipes entreprise expérience
ans compétences capacité rejoindre aider faire nouveau tous chez sein afin ainsi
""".split())

_WORD_RE = re.compile(r"[a-zàâäçéèêëîïôöùûüœ]+", re.IGNORECASE)


def _detect_lang(text: str) -> str:
    """Return 'fr' or 'en'. Uses langdetect if available, else a FR-function-word heuristic."""
    sample = text[:1500].strip()
    if len(sample) < 20:
        return "en"
    try:
        from langdetect import detect  # type: ignore
        code = detect(sample)
        return "fr" if code == "fr" else "en"
    except Exception as exc:  # noqa: BLE001 — langdetect missing OR undetectable; safe: fall back to heuristic
        logger.debug("langdetect unavailable/failed (%s); using FR-heuristic", exc)
        low = " " + sample.lower() + " "
        fr_hits = sum(low.count(f" {w} ") for w in
                      ("le", "la", "les", "des", "et", "pour", "vous", "nous", "produit", "équipe"))
        en_hits = sum(low.count(f" {w} ") for w in
                      ("the", "and", "for", "you", "we", "with", "product", "team"))
        return "fr" if fr_hits > en_hits else "en"


def _collect() -> list[tuple[str, str, str]]:
    """Return list of (title, text, source_name). Each source wrapped so one block
    (rate-limit, endpoint change) never aborts the whole corpus."""
    jobs: list[tuple[str, str, str]] = []
    dropped: list[str] = []

    def _add(source_name: str, source_jobs) -> None:
        n = 0
        for sj in source_jobs:
            title = (getattr(sj, "title", "") or "").strip()
            desc = (getattr(sj, "description_snippet", "") or "").strip()
            if not title:
                continue
            if not _PM_TITLE_RE.search(title):
                continue
            jobs.append((title, f"{title}. {desc}", source_name))
            n += 1
        logger.info("collect: %s -> %d PM postings kept", source_name, n)

    # 1. WTTJ Algolia (FR-heavy, descriptions inline, cheap) --------------------
    try:
        _add("wttj_algolia", wttj_algolia.fetch(
            keywords=PM_QUERY_KEYWORDS, country_code="FR",
            posted_within_hours=_ARGS.posted_within_hours, max_pages=3))
    except Exception as exc:  # noqa: BLE001 — one source failing must not kill the run
        logger.warning("wttj_algolia dropped: %s", exc)
        dropped.append(f"wttj_algolia ({exc})")

    # 2. LinkedIn jobs-guest (EN+FR mix, enriched descriptions) -----------------
    try:
        _add("linkedin_guest_api", linkedin_guest_api.fetch(
            keywords=PM_QUERY_KEYWORDS,
            posted_within_hours=_ARGS.posted_within_hours,
            max_pages_per_keyword=_ARGS.li_pages,
            enrich_descriptions=True))
    except Exception as exc:  # noqa: BLE001
        logger.warning("linkedin_guest_api dropped: %s", exc)
        dropped.append(f"linkedin_guest_api ({exc})")

    # 3. RemoteOK (EN remote) ---------------------------------------------------
    try:
        _add("remoteok", remoteok.fetch(max_jobs=200))
    except Exception as exc:  # noqa: BLE001
        logger.warning("remoteok dropped: %s", exc)
        dropped.append(f"remoteok ({exc})")

    # 4. WeWorkRemotely (EN remote) ---------------------------------------------
    try:
        _add("weworkremotely", weworkremotely.fetch(max_jobs=200))
    except Exception as exc:  # noqa: BLE001
        logger.warning("weworkremotely dropped: %s", exc)
        dropped.append(f"weworkremotely ({exc})")

    if dropped:
        logger.warning("SOURCES DROPPED (logged, not silently truncated): %s", "; ".join(dropped))
    return jobs


def _rank_lexicon(corpus: str) -> list[tuple[str, int]]:
    low = corpus.lower()
    scores: list[tuple[str, int]] = []
    for canon, variants in LEXICON.items():
        c = 0
        for pat in variants:
            c += len(re.findall(pat, low))
        if c:
            scores.append((canon, c))
    scores.sort(key=lambda kv: (-kv[1], kv[0]))
    return scores


def _emergent_terms(corpus: str, top: int = 40) -> list[tuple[str, int]]:
    tokens = [t.lower() for t in _WORD_RE.findall(corpus) if len(t) > 2 and t.lower() not in _STOP]
    uni = Counter(tokens)
    bi = Counter(f"{a} {b}" for a, b in zip(tokens, tokens[1:])
                 if a not in _STOP and b not in _STOP)
    merged = uni + bi
    return merged.most_common(top)


def _cloud(scores: list[tuple[str, int]], width: int = 40) -> str:
    if not scores:
        return "(no terms)"
    mx = scores[0][1]
    lines = []
    for term, n in scores:
        bar = "#" * max(1, round(width * n / mx))
        lines.append(f"  {term:<24} {bar} {n}")
    return "\n".join(lines)


def _write_lang(lang: str, blocks: list[str]) -> dict:
    corpus = "\n\n".join(blocks)
    (OUT_DIR / f"corpus_{lang}.txt").write_text(corpus, encoding="utf-8")

    lex = _rank_lexicon(corpus)
    emergent = _emergent_terms(corpus)

    md = [f"# PM job-description keywords — {lang.upper()}",
          f"\n**Corpus:** {len(blocks)} job descriptions "
          f"({sum(len(b) for b in blocks):,} chars).\n",
          "## Ranked PM competency lexicon (CV-usable, frequency word cloud)\n",
          "```", _cloud(lex), "```\n",
          "## Emergent high-frequency terms (uni+bigram, stopword-filtered)\n",
          "```"]
    md += [f"  {t:<28} {n}" for t, n in emergent]
    md += ["```\n"]
    (OUT_DIR / f"keywords_{lang}.md").write_text("\n".join(md), encoding="utf-8")

    return {
        "n_jds": len(blocks),
        "lexicon": lex,
        "emergent": emergent,
    }


def main() -> int:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    jobs = _collect()

    # Dedup by (title, first 120 chars of text) and language-bucket
    seen: set[str] = set()
    buckets: dict[str, list[str]] = {"fr": [], "en": []}
    for title, text, _src in jobs:
        key = (title + text[:120]).lower()
        if key in seen:
            continue
        seen.add(key)
        buckets[_detect_lang(text)].append(text)

    logger.info("corpus: FR=%d  EN=%d (after dedup + language split)",
                len(buckets["fr"]), len(buckets["en"]))

    result = {}
    for lang in ("fr", "en"):
        result[lang] = _write_lang(lang, buckets[lang])

    (OUT_DIR / "keywords.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    # Report + floor check
    print("\n" + "=" * 64)
    for lang in ("fr", "en"):
        r = result[lang]
        floor = "OK" if r["n_jds"] >= _ARGS.min_per_lang else "BELOW FLOOR"
        print(f"\n[{lang.upper()}] {r['n_jds']} JDs  ({floor}: need >={_ARGS.min_per_lang})")
        print("  top lexicon:", ", ".join(f"{t}({n})" for t, n in r["lexicon"][:15]))
    print("\nArtifacts in:", OUT_DIR)
    print("=" * 64)

    below = [l for l in ("fr", "en") if result[l]["n_jds"] < _ARGS.min_per_lang]
    if below:
        logger.warning("Below >=%d floor for: %s. Re-run later (JD volume varies by day) "
                       "or widen --posted-within-hours.", _ARGS.min_per_lang, below)
        return 2
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PM job-description keyword research (free sources).")
    parser.add_argument("--posted-within-hours", type=int, default=720)
    parser.add_argument("--min-per-lang", type=int, default=25)
    parser.add_argument("--li-pages", type=int, default=2)
    _ARGS = parser.parse_args()
    sys.exit(main())
