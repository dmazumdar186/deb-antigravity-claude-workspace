#!/usr/bin/env python3
"""
cv_panel_audit.py
description: Score a CV PDF against a folder of researched job descriptions (ATS 0-10 per JD,
    deterministic) and, optionally, against a three-persona hiring panel (senior career
    counsellor, senior head-hunter, senior recruiter; LLM via OpenRouter, JSON rubric) plus a
    Jev "would they call?" gate. Writes a markdown report and a JSON file; exits 1 when any gate
    fails so it can drive an iterate-until-green loop.
inputs: --cv PDF, --jd-dir folder containing index.json + NN_*.txt (from the JD research
    workers), --lang fr|en, --out report path, --panel (run LLM panel), --jev (run Jev gate),
    --ats-min (default 9.0), --panel-min (default 8.0). Env: OPENROUTER_API_KEY or
    OPENROUTER_API_TOEKN for --panel/--jev.
outputs: <out>.md report, <out>.json raw scores; stdout summary; exit code 0 pass / 1 fail.

Usage:
    python3 execution/personal_workflows/cv_panel_audit.py --cv ".tmp/cv.pdf" \
        --jd-dir .tmp/jd_research/en --lang en --out .tmp/cv_audit_en --panel --jev
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pdfplumber
from dotenv import load_dotenv

load_dotenv()
# Cloud sessions expose the OpenRouter key under a misspelled alias; llm_client reads only the canonical name.
if not os.environ.get("OPENROUTER_API_KEY"):
    for _alias in ("OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN"):
        if os.environ.get(_alias):
            os.environ["OPENROUTER_API_KEY"] = os.environ[_alias]
            break

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from execution.modules import jev_client as jev  # noqa: E402
from execution.modules.llm_client import chat_completion  # noqa: E402

CANDIDATE_YEARS = 15

STOP = set("""
a an and the of to in for with on at by or from as is are be this that de des du la le les un une
et ou en au aux pour par sur avec dans vous nous vos nos votre notre est sont être avoir plus ans
years year experience expérience minimum least strong solid good excellent proven ability skills
skill compétences compétence capacité connaissance connaissances bonne bon maîtrise niveau
you your will our we work working environment équipe team teams across within including related
etc ideally idéalement required requis souhaité plus
reads read took take takes willing step outside traditional past large company demonstrated used
built build understands understand nuances discuss about care thrives small uses equivalent daily
himself herself pulls sets not managed owned define defines decides brought deep early stage
material disposition exceptional excellent strong compelling navigate simplify complex problems
mindset orientation oriented track record ability able comfortable savvy fluent fluency literacy
thinking focus focused driven empathy intuition taste judgement judgment before background
capable capacité force forte fort réelle vraie bonne excellente solide avéré avérée justifier
justifiez idéalement notamment ainsi aussi également très bien savoir faire être avoir sens goût
appétence esprit envie souhaitez aimez capacité aptitude démontrée reconnue significative
approach approche solides concrète concrete plusieurs several création creating
""".split())

# Equivalences so an EN JD term can be satisfied by the FR CV wording and vice-versa, and so
# common abbreviations count.
SYNONYMS: dict[str, list[str]] = {
    "ai": ["ia", "intelligence artificielle", "artificial intelligence", "genai", "llm"],
    "ia": ["ai", "genai", "llm", "intelligence artificielle"],
    "genai": ["generative ai", "ia générative", "gen ai", "llm"],
    "ml": ["machine learning", "apprentissage automatique"],
    "machine": ["ml"],
    "llm": ["large language model", "genai", "gpt", "claude"],
    "roadmap": ["feuille de route"],
    "stakeholder": ["stakeholders", "parties prenantes", "partie prenante"],
    "stakeholders": ["stakeholder", "parties prenantes"],
    "parties": ["stakeholders", "stakeholder"],
    "prenantes": ["stakeholders", "stakeholder"],
    "agile": ["scrum", "kanban"],
    "scrum": ["agile"],
    "data": ["données", "data-driven"],
    "données": ["data"],
    "kpi": ["kpis", "okr", "metrics", "indicateurs"],
    "kpis": ["kpi", "okr", "metrics", "indicateurs"],
    "metrics": ["kpi", "kpis", "okr", "indicateurs"],
    "discovery": ["découverte", "user research", "interviews"],
    "b2b": ["saas"],
    "saas": ["b2b"],
    "english": ["anglais", "bilingual", "bilingue", "c2"],
    "anglais": ["english", "bilingual", "bilingue", "c2"],
    "french": ["français", "bilingual", "bilingue", "c2"],
    "français": ["french", "bilingual", "bilingue", "c2"],
    "francais": ["french", "bilingual", "bilingue", "c2"],
    "cross-functional": ["cross functional", "transverse", "pluridisciplinaire", "squads"],
    "engineering": ["engineers", "developers", "dev", "tech", "ingénieurs"],
    "engineers": ["engineering", "developers", "dev", "ingénieurs"],
    "design": ["ux", "designers"],
    "ux": ["design", "user experience", "expérience utilisateur"],
    "analytics": ["analytique", "mixpanel", "amplitude", "sql"],
    "experimentation": ["a/b", "ab testing", "expérimentation"],
    "prioritization": ["prioritisation", "priorisation", "rice", "wsjf"],
    "prioritisation": ["prioritization", "priorisation"],
    "priorisation": ["prioritization", "prioritisation"],
    "backlog": ["user stories", "prd"],
    "specifications": ["prd", "spécifications", "specs", "user stories"],
    "spécifications": ["prd", "specs", "user stories"],
    "api": ["apis", "api integrations", "intégrations"],
    "apis": ["api"],
    "master": ["msc", "bac+5", "master's"],
    "bac+5": ["msc", "master"],
    "ingénieur": ["engineering degree", "be ", "msc"],
    "python": ["python"],
    "sql": ["sql"],
    "rag": ["rag", "retrieval"],
    "agents": ["agent", "agentic", "agents"],
    "prompt": ["prompt engineering", "prompting"],
    "evaluation": ["evals", "évaluation", "eval"],
    "évaluation": ["evals", "evaluation", "eval"],
    "gdpr": ["rgpd", "privacy"],
    "rgpd": ["gdpr", "privacy"],
    "leadership": ["led", "lead", "piloté", "dirigé", "management"],
    "communication": ["communicate", "présentation", "stakeholder"],
    "customer": ["client", "clients", "customers", "user", "utilisateurs"],
    "client": ["customer", "customers", "clients"],
    "clients": ["customer", "customers"],
    "customers": ["customer", "client", "clients"],
    "users": ["utilisateurs", "user", "customer"],
    "utilisateurs": ["users", "user", "customer"],
    "growth": ["adoption", "croissance"],
    "revenue": ["pipeline", "arr", "chiffre"],
    "strategy": ["stratégie", "vision", "roadmap"],
    "stratégie": ["strategy", "vision", "roadmap"],
    "go-to-market": ["gtm", "launch", "lancement", "go to market"],
    "gtm": ["go-to-market", "launch", "lancement"],
    "launch": ["lancement", "shipped", "launched", "rollout", "livré"],
    "scale": ["scalability", "scalabilité", "scaled"],
    "startup": ["scale-up", "studio", "founder"],
    "scale-up": ["startup", "studio"],
    "fintech": ["payments", "stripe", "marketplace"],
    "marketplace": ["marketplace", "stripe connect"],
    "platform": ["plateforme", "platform"],
    "plateforme": ["platform"],
    "automation": ["automatisation", "agentic", "n8n", "make"],
    "automatisation": ["automation", "agentic", "n8n", "make"],
    "mlops": ["drift monitoring", "monitoring", "ci/cd", "evals"],
    "cloud": ["cloudflare", "modal", "aws", "gcp", "azure"],
    "jira": ["jira", "scrum", "kanban"],
    "figma": ["figma", "ux"],
    "okr": ["okrs", "kpi", "kpis"],
    "okrs": ["okr", "kpi"],
    "international": ["paris, us, india", "global", "multi-country", "international"],
    "remote": ["remote", "distributed", "paris, us, india"],
    "mentoring": ["mentor", "coaching", "coached", "mentored"],
    "customer-driven": ["customer", "customers", "users", "clients"],
    "customer-focused": ["customer", "customers", "users", "clients"],
    "data-savvy": ["analytics", "sql", "data"],
    "data-fluent": ["analytics", "sql", "data"],
    "modeling": ["sql", "analytics", "data model"],
    "technical": ["engineering", "python", "api", "architecture"],
    "acumen": ["engineering", "python"],
    "engage": ["engineers", "engineering"],
    "written/spoken": ["communication", "stakeholder"],
    "problem": ["problem framing", "problems"],
    "framing": ["problem framing", "discovery"],
    "pitch": ["pitch", "business case", "go/no-go"],
    "success": ["success metrics", "outcome", "kpi"],
    "tools": ["tooling", "claude code", "n8n", "make"],
    "tooling": ["tools", "claude code"],
    "ai-generated": ["ai-generated", "claude code", "agentic development"],
    "prototyping": ["prototype", "prototypes", "prototyping"],
    "prototype": ["prototyping", "prototypes"],
    "design-system": ["design system", "figma", "ux"],
    "insights": ["insight", "analytics", "discovery"],
    "insight": ["insights", "discovery"],
    "workflows": ["workflow", "automation", "pipeline"],
    "production-level": ["production", "shipped", "live"],
    "production": ["shipped", "live", "rollout", "in production"],
    "ml-driven": ["ml", "llm", "model"],
    "ai/ml": ["ai", "ml", "llm", "genai"],
    "generative": ["genai", "llm", "generative"],
    "model": ["llm", "model"],
    "behaviour": ["evals", "evaluation", "guardrails"],
    "architectures": ["architecture", "rag", "orchestration"],
    "trade-offs": ["trade-off", "trade-offs", "prioritisation", "prioritization"],
    "trade-off": ["trade-offs", "prioritisation"],
    "safety": ["guardrails", "responsible ai", "pii"],
    "reliability": ["latency", "sla", "slo", "monitoring"],
    "feasibility": ["feasibility", "build vs. buy", "build vs buy", "estimate"],
    "infrastructure": ["platform", "api", "cloudflare", "modal", "infra"],
    "architecture": ["architecture", "rag", "orchestration", "platform"],
    "low-code": ["n8n", "make", "low-code"],
    "qualitative": ["interviews", "user research", "discovery"],
    "roadmaps": ["roadmap"],
    "outcome": ["outcome", "adoption", "kpi", "okr", "result"],
    "ownership": ["own", "owner", "owned", "end to end", "end-to-end"],
    "end-to-end": ["end to end", "end-to-end", "own"],
    "execution-oriented": ["shipped", "delivered", "delivery"],
    "evals": ["evals", "evaluation", "golden set", "llm-as-judge"],
    "non-deterministic": ["non-deterministic", "evals", "guardrails"],
    "guardrails": ["guardrails", "garde-fous"],
    "cost": ["cost", "coût", "cost per call"],
    "call": ["cost per call", "api"],
    "async": ["remote", "distributed", "paris, us, india"],
    "high-autonomy": ["autonomy", "autonomous", "founder", "without line authority"],
    "autonomy": ["autonomous", "founder", "independent", "without line authority"],
    "autonomie": ["autonome", "founder", "fondateur", "indépendant", "sans autorité"],
    "developer-facing": ["api", "apis", "developer", "sdk", "cli"],
    "sdks": ["api", "apis", "cli"],
    "coding": ["claude code", "python", "code"],
    "specs": ["prd", "specifications", "user stories"],
    "scale-up": ["scale-up", "saas", "scaleup"],
    "scaled": ["scale", "scaled", "scalability"],
    "funnel": ["funnel", "conversion", "analytics"],
    "measurement": ["metrics", "kpi", "analytics"],
    "experiments": ["a/b", "experiments", "feature flags", "experimentation"],
    "iteration": ["iteration", "iterations", "sprint"],
    "mvp": ["mvp", "poc", "pilot", "<30-day", "prototype"],
    "poc": ["poc", "mvp", "pilot", "prototype"],
    "continuous": ["continuous discovery", "discovery", "weekly"],
    "vision": ["vision", "strategy", "stratégie"],
    "impact": ["impact", "outcome", "adoption", "résultat"],
    "delivery": ["delivery", "shipped", "livré", "livraison"],
    "run": ["run", "production", "monitoring", "exploitation"],
    "rigueur": ["structuré", "structured", "cadence", "gates", "rigueur"],
    "structuration": ["structuré", "structured", "cadence", "framework"],
    "arbitrage": ["arbitrage", "priorisation", "trade-off"],
    "arbitrer": ["arbitrage", "priorisation"],
    "management": ["management", "pilotage", "led", "lead", "coaching"],
    "coaching": ["coaching", "mentor", "accompagnement", "onboarding"],
    "pédagogie": ["pédagogie", "formation", "support", "onboarding"],
    "conseil": ["consultant", "conseil", "consulting", "studio"],
    "consulting": ["consultant", "conseil", "studio"],
    "grands": ["enterprise", "grands comptes", "b2b"],
    "comptes": ["enterprise", "grands comptes", "b2b"],
    "métier": ["métier", "business", "bu"],
    "métiers": ["métier", "business", "bu"],
    "direction": ["cpo", "direction", "c-level", "codir", "comex"],
    "codir": ["cpo", "c-level", "direction"],
    "comex": ["cpo", "c-level", "direction"],
    "ia": ["ai", "genai", "llm", "intelligence artificielle", "ia"],
    "générative": ["genai", "générative", "llm"],
    "generative": ["genai", "générative", "llm"],
    "valeur": ["roi", "valeur", "impact", "adoption"],
    "roi": ["roi", "valeur", "cost", "coût", "pipeline", "$"],
    "lean": ["lean", "agile", "scrum", "kanban"],
    "squad": ["squad", "squads", "équipe"],
    "squads": ["squad", "équipe"],
    "équipe": ["squad", "squads", "team", "équipe"],
    "équipes": ["squad", "squads", "team", "équipes"],
    "test": ["tests", "a/b", "evals"],
    "tests": ["test", "a/b", "evals"],
    "mesure": ["kpi", "metrics", "mesure", "analytics"],
    "mesurer": ["kpi", "metrics", "mesure", "analytics"],
    "indicateurs": ["kpi", "okr", "metrics"],
    "performance": ["kpi", "latence", "latency", "performance"],
    "dashboard": ["dashboard", "analytics", "power bi", "mixpanel"],
    "bi": ["power bi", "analytics", "sql", "dashboard"],
    "science": ["data science", "data scientists", "ml", "model"],
    "scientists": ["data science", "data scientists", "ml"],
    "pipeline": ["pipeline", "pipelines"],
    "pipelines": ["pipeline", "data pipelines"],
    "anglais": ["english", "anglais", "bilingue", "c2"],
    "courant": ["bilingue", "c2", "bilingual"],
    "professionnel": ["bilingue", "c2", "bilingual"],
    "startup": ["scale-up", "studio", "founder", "startup", "fondateur"],
    "industrialisation": ["production", "rollout", "déploiement", "ci/cd"],
    "déploiement": ["rollout", "déploiement", "production"],
    "déployer": ["rollout", "déploiement", "production"],
    "cadrage": ["cadrage", "discovery", "problem framing", "prd"],
    "cadrer": ["cadrage", "discovery", "prd"],
    "spécifier": ["prd", "user stories", "spécifications"],
    "spécifications": ["prd", "user stories", "specs"],
    "fonctionnelles": ["prd", "user stories", "specs"],
    "ateliers": ["ateliers", "workshops", "interviews", "entretiens"],
    "workshops": ["ateliers", "workshops", "interviews"],
    "animation": ["animation", "ateliers", "facilitation", "rituels"],
    "animer": ["animation", "ateliers", "rituels"],
    "rituels": ["rituels", "cadence", "scrum", "sprint"],
    "cérémonies": ["rituels", "cadence", "scrum", "sprint"],
    "incréments": ["sprint", "release", "livraison"],
    "cas": ["use case", "cas d'usage", "use cases"],
    "usage": ["use case", "cas d'usage", "usage"],
    "usages": ["use case", "cas d'usage", "usage"],
    "gouvernance": ["gouvernance", "governance", "rgpd", "ai act"],
    "governance": ["gouvernance", "governance", "gdpr", "ai act"],
    "responsable": ["responsable", "owner", "responsible", "en charge"],
    "piloter": ["pilotage", "piloté", "led", "run"],
    "pilotage": ["pilotage", "piloté", "led"],
    "portefeuille": ["portefeuille", "portfolio", "ligne produit", "product line"],
    "portfolio": ["portfolio", "portefeuille", "product line"],
    "transformation": ["transformation", "rollout", "déploiement", "adoption", "change management"],
    "acculturation": ["acculturation", "onboarding", "formation", "adoption", "change management"],
    "évangélisation": ["acculturation", "onboarding", "adoption"],
    "accompagnement": ["accompagnement", "onboarding", "coaching", "change management"],
    "conduite": ["conduite du changement", "change management", "adoption"],
    "changement": ["conduite du changement", "change management", "adoption"],
    "curiosité": ["curiosité", "veille", "curious", "learning"],
    "veille": ["veille", "curiosité", "vendor evaluation", "évaluation"],
    "influence": ["influence", "sans autorité", "without line authority", "alignement"],
    "alignement": ["alignement", "aligned", "alignment", "roadmap"],
    "partenariat": ["partnership", "partenariat", "collaboration"],
    "partnership": ["partnership", "partenariat", "collaboration"],
    "collaboration": ["collaboration", "cross-functional", "squads", "partnership"],
    "communicate": ["communication", "presented", "stakeholder"],
    "présenter": ["présentation", "communication", "go/no-go", "comité"],
    "présentation": ["présentation", "communication", "comité"],
    "comité": ["comité", "go/no-go", "codir", "steering"],
    "sponsor": ["sponsor", "cpo", "direction", "c-level"],
    "sponsors": ["sponsor", "cpo", "direction", "c-level"],
    "coaching": ["mentor", "mentoring", "coached"],
}


# ── Text helpers ────────────────────────────────────────────────────────────────

def _norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"\s+", " ", s.lower())


def pdf_text(path: Path) -> tuple[str, int]:
    with pdfplumber.open(path) as pdf:
        pages = len(pdf.pages)
        txt = "\n".join(p.extract_text() or "" for p in pdf.pages)
    return txt, pages


def content_words(phrase: str) -> list[str]:
    words = re.findall(r"[a-zA-Zàâäéèêëïîôöùûüç0-9+/\-\.]{2,}", re.sub(r"[’']", " ", phrase.lower()))
    out = []
    for w in words:
        w = w.strip("'.")
        if len(w) < 3 and w not in {"ia", "ai", "ml", "ux", "b2b", "sql", "api", "kpi", "okr", "rag"}:
            continue
        if w in STOP or w.isdigit():
            continue
        out.append(w)
    return out


def word_hit(w: str, cv_norm: str) -> bool:
    wn = _norm(w)
    if wn in cv_norm:
        return True
    stem = wn[:-1] if wn.endswith("s") and len(wn) > 3 else wn
    if len(stem) >= 3 and re.search(r"\b" + re.escape(stem) + r"\b", cv_norm):
        return True
    # crude lemmatiser: a shared 7-letter prefix (prioriser ~ priorisation, négociation ~ négociés)
    if len(wn) >= 8 and re.search(r"\b" + re.escape(wn[:7]), cv_norm):
        return True
    for alt in SYNONYMS.get(w.lower(), []):
        if _norm(alt) in cv_norm:
            return True
    return False


def phrase_coverage(phrase: str, cv_norm: str) -> tuple[float, list[str]]:
    """Fraction of a requirement phrase's content words found in the CV, plus the misses."""
    words = content_words(phrase)
    if not words:
        return 1.0, []
    hits = [w for w in words if word_hit(w, cv_norm)]
    misses = [w for w in words if w not in hits]
    return len(hits) / len(words), misses


def years_in(phrase: str) -> int | None:
    m = re.search(r"(\d{1,2})\s*\+?\s*(?:ans|years|yrs|year)", phrase.lower())
    return int(m.group(1)) if m else None


# ── ATS scoring ─────────────────────────────────────────────────────────────────

def ats_score(cv_text: str, pages: int, jd: dict, core_terms: list[str], lang: str) -> dict:
    cvn = _norm(cv_text)
    detail: dict = {"id": jd.get("id"), "title": jd.get("title"), "company": jd.get("company"),
                    "type": jd.get("type")}

    # 1. Must-have requirements (50%) — a phrase counts as met at ≥60% content-word coverage;
    #    partial credit below that; a years-of-experience phrase is met if the candidate has them.
    must = jd.get("must_have") or []
    must_scores, must_gaps = [], []
    for ph in must:
        yrs = years_in(ph)
        if yrs is not None and yrs <= CANDIDATE_YEARS and len(content_words(ph)) <= 6:
            must_scores.append(1.0)
            continue
        cov, misses = phrase_coverage(ph, cvn)
        must_scores.append(1.0 if cov >= 0.6 else cov)
        if cov < 0.6:
            must_gaps.append({"requirement": ph, "coverage": round(cov, 2), "missing": misses})
    s_must = sum(must_scores) / len(must_scores) if must_scores else 1.0

    # 2. Named tools / technologies (20%)
    tools = jd.get("tools_named") or []
    tool_hits = [t for t in tools if phrase_coverage(t, cvn)[0] >= 0.6]
    s_tools = len(tool_hits) / len(tools) if tools else 1.0

    # 3. Core terms across the whole JD set (20%)
    core_hits = [t for t in core_terms if word_hit(t, cvn)]
    s_core = len(core_hits) / len(core_terms) if core_terms else 1.0

    # 4. Format / parseability (10%)
    fmt_checks = {
        "max_2_pages": pages <= 2,
        "text_extractable": len(cv_text) > 1500,
        "has_email": "@" in cv_text,
        "has_phone": bool(re.search(r"\+33|0[67]\s?\d{2}", cv_text)),
        "title_has_product_manager": "product manager" in cvn,
        "has_experience_section": any(k in cvn for k in ("experience", "experiences")),
        "has_skills_section": any(k in cvn for k in ("skills", "competences")),
        "has_education_section": any(k in cvn for k in ("education", "formation")),
        "has_languages": any(k in cvn for k in ("languages", "langues")),
        "no_tables_or_columns_breaking_lines": "\n\n\n\n" not in cv_text,
    }
    s_fmt = sum(fmt_checks.values()) / len(fmt_checks)

    # Years gate: a JD asking for more years than the candidate has is a hard miss.
    yrs_req = jd.get("years_required")
    try:
        yrs_req = int(re.search(r"\d+", str(yrs_req)).group()) if yrs_req else None
    except AttributeError:
        yrs_req = None
    years_ok = yrs_req is None or yrs_req <= CANDIDATE_YEARS

    score10 = 10 * (0.5 * s_must + 0.2 * s_tools + 0.2 * s_core + 0.1 * s_fmt)
    if not years_ok:
        score10 = min(score10, 5.0)

    detail.update({
        "ats_score": round(score10, 2),
        "must_have_score": round(s_must, 2), "must_have_gaps": must_gaps,
        "tools_score": round(s_tools, 2),
        "tools_missing": [t for t in tools if t not in tool_hits],
        "core_score": round(s_core, 2),
        "core_missing": [t for t in core_terms if t not in core_hits],
        "format_score": round(s_fmt, 2),
        "format_failed": [k for k, v in fmt_checks.items() if not v],
        "years_required": yrs_req, "years_ok": years_ok,
    })
    return detail


def derive_core_terms(jds: list[dict], min_docs: int = 5) -> list[str]:
    """Content words present in the must_have/tools/soft_skills of ≥ min_docs JDs."""
    counts: dict[str, int] = {}
    for jd in jds:
        bag = set()
        for ph in (jd.get("must_have") or []) + (jd.get("tools_named") or []) + (jd.get("soft_skills") or []):
            bag.update(content_words(ph))
        for w in bag:
            counts[w] = counts.get(w, 0) + 1
    core = [w for w, c in counts.items() if c >= min_docs]
    return sorted(core, key=lambda w: -counts[w])


# ── Panel (LLM) ─────────────────────────────────────────────────────────────────

PANEL_SYSTEM = """You are a hiring panel of three people, each with more than twenty years in the field:
(1) a senior career counsellor based in Lyon who has coached product managers since before 2005;
(2) a senior head-hunter who places Senior Product Managers and AI Product Managers in France and Europe;
(3) a senior in-house recruiter who screens CVs for this exact job.
You read the CANDIDATE CV and the JOB DESCRIPTION and each person answers independently and strictly.
Judge only what is on the CV. Be concrete: name the line that convinced or worried you.
Return ONLY JSON of this shape, no prose outside it:
{"counsellor":{"fit":0-10,"would_call":true|false,"objection":"...","fix":"..."},
 "headhunter":{"fit":0-10,"would_call":true|false,"objection":"...","fix":"..."},
 "recruiter":{"fit":0-10,"would_call":true|false,"objection":"...","fix":"..."},
 "verbosity":{"too_verbose":true|false,"note":"..."},
 "reads_human":{"score":0-10,"ai_tells":["..."]},
 "truthfulness_flags":["any claim that sounds inflated or unverifiable"]}
"too_verbose" is judged by the recruiter standard for a 10-15 year profile: true only if bullets run
over two lines, describe duties instead of results, repeat each other, or the CV exceeds two pages;
a two-page CV with one-to-two-line achievement bullets is NOT verbose.
"fit" = how strongly the CV matches this JD; "would_call" = whether that person would pick up the phone
after a 30-second read. A fix must be a change to wording, order or emphasis, never a fabricated
experience."""


def panel_one(cv_text: str, jd_text: str, model: str) -> dict:
    user = f"JOB DESCRIPTION:\n{jd_text[:9000]}\n\n=====\nCANDIDATE CV:\n{cv_text[:9000]}"
    try:
        raw = chat_completion(PANEL_SYSTEM, user, model=model, max_tokens=2000)
    except Exception as e:  # noqa: BLE001 — network/provider error; recorded, not swallowed
        return {"error": f"{type(e).__name__}: {e}"}
    m = re.search(r"\{.*\}", raw, re.S)
    if not m:
        return {"error": "no JSON in panel reply", "raw": raw[:400]}
    try:
        return json.loads(m.group())
    except json.JSONDecodeError as e:
        return {"error": f"bad JSON: {e}", "raw": raw[:400]}


def jev_gate(cv_text: str, jds: list[dict], jd_texts: dict[str, str]) -> dict[str, dict]:
    if not jev.available():
        return {}
    states = [{"job_description": jd_texts.get(jd["id"], "")[:12000], "cv": cv_text[:12000]} for jd in jds]
    qs = {
        "call": jev.noul(
            "A recruiter with 20 years of experience hiring for this job reads this CV for 30 seconds. "
            "Would they phone the candidate?",
            "true when the CV's title, years and results plainly match the job's must-haves",
            "false when a must-have is missing or the CV reads as a different job"),
        "verbose": jev.noul("Is this CV too verbose for a French recruiter?",
                             "true when bullets are long, repetitive or padded",
                             "false when bullets are short and factual"),
        "fit": jev.score("How well does the CV fit this job?", ["poor", "weak", "fair", "good", "excellent"]),
    }
    rs = jev.decide_many(states, qs, workers=4)
    out = {}
    for jd, r in zip(jds, rs):
        if r.error:
            out[jd["id"]] = {"error": r.error}
        else:
            out[jd["id"]] = {"call_p": round(r.noul("call"), 3), "verbose_p": round(r.noul("verbose"), 3),
                             "fit": r.score("fit"), "cost": r.cost_usd}
    return out


# ── Main ────────────────────────────────────────────────────────────────────────

def load_jds(jd_dir: Path) -> tuple[list[dict], dict[str, str]]:
    idx = json.loads((jd_dir / "index.json").read_text(encoding="utf-8"))
    if isinstance(idx, dict):
        idx = idx.get("jds") or idx.get("jobs") or list(idx.values())[0]
    texts: dict[str, str] = {}
    for jd in idx:
        jid = str(jd.get("id"))
        jd["id"] = jid
        cands = sorted(jd_dir.glob(f"{jid.zfill(2)}_*.txt")) or sorted(jd_dir.glob(f"{jid}_*.txt"))
        texts[jid] = cands[0].read_text(encoding="utf-8", errors="replace") if cands else ""
    return idx, texts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cv", type=Path, required=True)
    ap.add_argument("--jd-dir", type=Path, required=True)
    ap.add_argument("--lang", choices=["fr", "en"], required=True)
    ap.add_argument("--out", type=Path, required=True, help="path stem; .md and .json are appended")
    ap.add_argument("--panel", action="store_true")
    ap.add_argument("--jev", action="store_true")
    ap.add_argument("--panel-model", default="anthropic/claude-sonnet-5.5")
    ap.add_argument("--ats-min", type=float, default=9.0)
    ap.add_argument("--panel-min", type=float, default=8.0)
    ap.add_argument("--workers", type=int, default=5)
    a = ap.parse_args()

    cv_text, pages = pdf_text(a.cv)
    jds, jd_texts = load_jds(a.jd_dir)
    core = derive_core_terms(jds)
    ats = [ats_score(cv_text, pages, jd, core, a.lang) for jd in jds]

    panel: dict[str, dict] = {}
    if a.panel:
        with ThreadPoolExecutor(max_workers=a.workers) as ex:
            futs = {jd["id"]: ex.submit(panel_one, cv_text, jd_texts[jd["id"]], a.panel_model) for jd in jds}
            panel = {k: f.result() for k, f in futs.items()}
    jevr = jev_gate(cv_text, jds, jd_texts) if a.jev else {}

    # Gates
    fails: list[str] = []
    for d in ats:
        if d["ats_score"] < a.ats_min:
            fails.append(f"ATS {d['ats_score']} < {a.ats_min} on JD {d['id']} ({d['title']} — {d['company']})")
    for jid, p in panel.items():
        if "error" in p:
            fails.append(f"panel error on JD {jid}: {p['error']}")
            continue
        for who in ("counsellor", "headhunter", "recruiter"):
            r = p.get(who, {})
            if not r.get("would_call", False):
                fails.append(f"{who} would NOT call on JD {jid}: {r.get('objection', '')}")
            if float(r.get("fit", 0)) < a.panel_min:
                fails.append(f"{who} fit {r.get('fit')} < {a.panel_min} on JD {jid}")
        if p.get("verbosity", {}).get("too_verbose"):
            fails.append(f"too verbose per panel on JD {jid}: {p['verbosity'].get('note', '')}")
        if float(p.get("reads_human", {}).get("score", 10)) < 8:
            fails.append(f"reads_human {p['reads_human'].get('score')} < 8 on JD {jid}: {p['reads_human'].get('ai_tells')}")

    # Report
    mean_ats = sum(d["ats_score"] for d in ats) / len(ats)
    lines = [f"# CV audit — {a.cv.name} vs {len(jds)} {a.lang.upper()} JDs", "",
             f"Pages: {pages} · words: {len(cv_text.split())} · mean ATS: {mean_ats:.2f}/10 · "
             f"min ATS: {min(d['ats_score'] for d in ats):.2f} · gate: {'PASS' if not fails else 'FAIL'}", "",
             f"Core terms (≥5 of {len(jds)} JDs): {', '.join(core)}", "",
             "| # | JD | Type | ATS | must | tools | core | fmt | panel fit (c/h/r) | call | Jev call p |",
             "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d in ats:
        p = panel.get(d["id"], {})
        fit = "/".join(str(p.get(w, {}).get("fit", "-")) for w in ("counsellor", "headhunter", "recruiter")) if p and "error" not in p else "-"
        call = "".join("Y" if p.get(w, {}).get("would_call") else "n" for w in ("counsellor", "headhunter", "recruiter")) if p and "error" not in p else "-"
        jv = jevr.get(d["id"], {}).get("call_p", "-")
        lines.append(f"| {d['id']} | {d['title']} — {d['company']} | {d['type']} | **{d['ats_score']}** | "
                     f"{d['must_have_score']} | {d['tools_score']} | {d['core_score']} | {d['format_score']} | {fit} | {call} | {jv} |")
    lines += ["", "## Gaps per JD", ""]
    for d in ats:
        gaps = d["must_have_gaps"]
        tm = d["tools_missing"]
        if gaps or tm or d["format_failed"]:
            lines.append(f"**JD {d['id']} — {d['title']} ({d['company']})**")
            for g in gaps:
                lines.append(f"- must-have not met ({g['coverage']}): {g['requirement']} → missing words: {', '.join(g['missing'])}")
            if tm:
                lines.append(f"- tools missing: {', '.join(tm)}")
            if d["format_failed"]:
                lines.append(f"- format: {', '.join(d['format_failed'])}")
            lines.append("")
    if panel:
        lines += ["## Panel objections and fixes", ""]
        for jid, p in panel.items():
            if "error" in p:
                lines.append(f"- JD {jid}: ERROR {p['error']}")
                continue
            for who in ("counsellor", "headhunter", "recruiter"):
                r = p.get(who, {})
                lines.append(f"- JD {jid} · {who} · fit {r.get('fit')} · call={r.get('would_call')} · "
                             f"objection: {r.get('objection')} · fix: {r.get('fix')}")
            if p.get("reads_human", {}).get("ai_tells"):
                lines.append(f"  - AI tells: {p['reads_human']['ai_tells']}")
            if p.get("truthfulness_flags"):
                lines.append(f"  - truthfulness flags: {p['truthfulness_flags']}")
    lines += ["", "## Gate result", ""] + ([f"- {f}" for f in fails] or ["All gates passed."])

    a.out.parent.mkdir(parents=True, exist_ok=True)
    Path(str(a.out) + ".md").write_text("\n".join(lines), encoding="utf-8")
    Path(str(a.out) + ".json").write_text(json.dumps({"ats": ats, "panel": panel, "jev": jevr, "core": core,
                                                      "fails": fails}, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"mean ATS {mean_ats:.2f}, min {min(d['ats_score'] for d in ats):.2f}; "
          f"{len(fails)} gate failures; report {a.out}.md")
    for f in fails[:40]:
        print(" -", f)
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
