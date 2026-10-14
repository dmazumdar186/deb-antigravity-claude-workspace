#!/usr/bin/env python3
"""
instantly_lead_cleaner.py
description: Clean a dirty lead CSV (Google-Maps titles / studio names in the "First name" column) into an
             Instantly-ready file: validate websites, extract the person's given name from the website,
             email username, URL path and raw name (LLM-assisted, deterministic fallback), dedupe on email.
inputs: --input CSV (utf-8-sig; needs 'First name','City','Email','Website','Found on' + verifier columns
        email,status,overall_score,is_safe_to_send,is_valid_syntax,is_disabled,...), --output, --workers,
        --limit, --no-llm; env: OPENROUTER_API_KEY|OPENROUTER_API_TOEKN (LLM pass), REQUESTS_CA_BUNDLE (optional)
outputs: cleaned CSV (unique emails, first_name/company/website_status/send_recommended...) +
         report.json next to it (counts, blank-name rows, LLM cost estimate)
usage:
    python3 execution/lead_sourcing/instantly_lead_cleaner.py --input .tmp/yoga_fr/input.csv \
        --output .tmp/yoga_fr/Yoga_Teachers_France_instantly_ready.csv --workers 16
    python3 execution/lead_sourcing/instantly_lead_cleaner.py --input in.csv --output out.csv --no-llm --limit 20
"""

import argparse
import csv
import html as html_mod
import json
import logging
import os
import re
import sys
import threading
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.parse import unquote, urljoin, urlparse

import requests

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:  # pragma: no cover
    pass

try:
    from bs4 import BeautifulSoup
except ImportError:  # pragma: no cover
    BeautifulSoup = None

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("instantly_lead_cleaner")

# llm_client only reads OPENROUTER_API_KEY; the workspace env sometimes carries the misspelt TOEKN name.
for _alt in ("OPENROUTER_API_TOEKN", "OPENROUTER_API_TOKEN"):
    if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get(_alt):
        os.environ["OPENROUTER_API_KEY"] = os.environ[_alt]

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/126.0.0.0 Safari/537.36")
HEADERS = {"User-Agent": UA, "Accept-Language": "fr-FR,fr;q=0.9,en;q=0.8",
           "Accept": "text/html,application/xhtml+xml,*/*;q=0.8"}
LLM_MODEL = "anthropic/claude-sonnet-5.5"
LLM_BATCH = 10
LLM_MAX_TOKENS_PER_LEAD = 120
# Rough OpenRouter price for the sonnet tier (USD per 1M tokens) for the cost estimate only.
LLM_PRICE_IN, LLM_PRICE_OUT = 3.0, 15.0

USERNAME_STOP = {
    "contact", "hello", "info", "infos", "bonjour", "yoga", "studio", "admin", "serviceclient", "service",
    "salut", "mail", "email", "courrier", "secretariat", "accueil", "reservation", "reservations", "booking",
    "inscription", "inscriptions", "association", "asso", "centre", "center", "ecole", "atelier", "espace",
    "team", "equipe", "support", "office", "direction", "president", "presidente", "bureau", "exemple",
    "example", "johndoe", "test", "noreply", "no-reply", "newsletter", "pilates", "zen", "om", "namaste",
    "shanti", "coucou", "hi", "hey", "welcome", "bienvenue", "cours", "club", "salle", "gym", "sport",
    "yay", "bam", "pop", "flow", "joy", "small", "muse", "tribu",
    "wellness", "bienetre", "sante", "massage", "ayurveda", "meditation", "prana", "ashtanga", "vinyasa",
    "hatha", "iyengar", "kundalini", "nidra", "yin", "lotus", "shala", "sangha", "atma", "anahata",
}
STUDIO_WORDS = {
    "yoga", "studio", "centre", "center", "ecole", "école", "atelier", "espace", "association", "club",
    "pilates", "hatha", "vinyasa", "ashtanga", "iyengar", "kundalini", "yin", "nidra", "méditation",
    "meditation", "sophrologie", "bien-être", "bien", "être", "salle", "cours", "formation", "shala",
    "school", "the", "les", "le", "la", "l'", "du", "de", "des", "et", "and", "&", "à", "a", "au", "aux",
    "en", "sur", "chez", "maison", "institut", "academy", "académie", "yogi", "yogis", "yogini", "zen",
    "om", "prana", "namaste", "shanti", "lotus", "sangha", "bordeaux", "lille", "lyon", "paris", "nantes",
    "toulouse", "marseille", "nice", "montpellier", "strasbourg", "rennes", "grenoble", "annecy", "dijon",
    "tours", "angers", "reims", "metz", "nancy", "brest", "caen", "rouen", "orleans", "limoges", "pop",
    "flow", "home", "house", "corner", "room", "lab", "box", "loft", "garden", "jardin", "city", "in",
    "sophrologue", "coach", "professeur", "professeure", "prof", "enseignant", "enseignante", "therapeute",
    "thérapeute", "praticien", "praticienne", "naturopathe", "osteopathe", "ostéopathe", "massage",
    "ayurveda", "ayurvédique", "wellness", "fitness", "gym", "sport", "danse", "dance", "barre", "senses",
    "inspir", "nouveau", "nouvelle", "new", "depuis", "ans", "diplômée", "diplomee", "certifiée",
}
COMMON_WORDS = {
    "seance", "seances", "decouvrez", "decouvrir", "situation", "certifications", "certification", "bienvenue",
    "accueil", "nos", "notre", "votre", "vos", "tarifs", "tarif", "planning", "horaires", "contact", "mentions",
    "reserver", "reservation", "rejoignez", "venez", "pratique", "pratiquer", "presentation", "about", "home",
    "welcome", "page", "menu", "blog", "actualites", "news", "events", "evenements", "stages", "stage", "retraite",
    "retraites", "ateliers", "offre", "offres", "carte", "cartes", "abonnement", "abonnements", "inscription",
    "inscriptions", "cours", "professeurs", "equipe", "team", "lieu", "lieux", "adresse", "plan", "infos",
    "programme", "agenda", "boutique", "shop", "galerie", "photos", "video", "videos", "temoignages", "avis",
    "faq", "questions", "qui", "sommes", "nous", "vous", "pour", "avec", "sans", "tous", "toutes", "tout",
    "une", "des", "les", "mon", "mes", "ton", "ses", "leur", "leurs", "cette", "ces", "quel", "quelle",
    "premier", "premiere", "nouveau", "nouvelle", "nouveaux", "gratuit", "gratuite", "essai", "ouverture",
    "ouvert", "ferme", "vacances", "merci", "bonne", "bon", "belle", "beau", "grand", "grande", "petit",
    "petite", "respirer", "respiration", "souffle", "corps", "esprit", "ame", "energie", "equilibre", "harmonie",
    "serenite", "detente", "relaxation", "bien", "etre", "sante", "vie", "vivre", "mouvement", "force",
    "douceur", "lumiere", "nature", "terre", "ciel", "soleil", "lune", "espace", "temps", "moment", "instant",
    "yoga", "yogi", "yogis", "yogini", "yoginis", "mantra", "asana", "asanas", "pranayama", "chakra", "chakras",
    "cours", "professeur", "professeure", "enseignante", "enseignant", "formation", "formations", "pilates",
    "sophrologie", "meditation", "massages", "soins", "soin", "sportif", "sportive", "danse", "fitness",
    "studio", "studios", "centre", "ecole", "atelier", "association", "club", "salle", "maison", "espace",
    "ville", "quartier", "rue", "avenue", "place", "france", "french", "english", "francais", "anglais",
    "online", "ligne", "visio", "zoom", "live", "replay", "podcast", "newsletter", "instagram", "facebook",
    "sample", "index", "praticiens", "praticien", "praticienne", "therapeute", "intervenant", "intervenants",
    "finding", "space", "personal", "professeurdeyoga", "site", "web", "mail", "email",
}
NAME_RE = re.compile(r"^[A-Za-zÀ-ÖØ-öø-ÿ][a-zà-öø-ÿ]+(?:[-'][A-Za-zÀ-ÖØ-öø-ÿ][a-zà-öø-ÿ]+)?$")
TITLE_PERSON_RE = re.compile(
    r"^\s*(?P<first>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+)\s+(?P<last>[A-Za-zÀ-ÖØ-öø-ÿ][A-Za-zÀ-ÖØ-öø-ÿ'’-]+)"
    r"(?:\s*[-–|:(,]|\s+Prof|\s+Yoga|\s+Hatha|\s+Vinyasa|\s+Ashtanga|\s+Iyengar|\s*$)",
    re.IGNORECASE,
)
SEND_OK_STATUS = {"safe", "role_account", "catch_all"}
# Directory / booking / web-builder platforms: the address reaches the platform, not the teacher.
PLATFORM_DOMAINS = {
    "trainme.co", "feverup.com", "prontopro.fr", "lesmedecinesdouces.fr", "webador.fr", "readymag.com",
    "bookday.io", "juiceweb.fr", "abctalk.fr", "registreyogameditation.fr", "krenosport.com", "osteopol.ch",
    "upe-alsace.fr", "tropisme.coop", "superprof.fr", "wix.com", "wixpress.com", "squarespace.com",
}
PLACEHOLDER_DOMAINS = {"monsite.com", "email.fr", "xyz.com", "exemple.fr", "exemple.com", "example.com",
                       "martin.com", "domaine.com", "domain.com", "email.com", "mail.com"}
PLACEHOLDER_USERS = {"exemple", "example", "johndoe", "jean.dupont", "abc", "nom", "prenom", "votre", "test",
                     "jade", "jacques"}

_fetch_cache: dict = {}
_llm_cache: dict = {}
LLM_CACHE_PATH = ROOT / ".tmp" / "instantly_lead_cleaner_llm_cache.json"
_fetch_lock = threading.Lock()


# ---------------------------------------------------------------- helpers
def norm_email(e: str) -> str:
    return (e or "").strip().lower()


def truthy(v) -> bool:
    return str(v).strip().lower() in {"true", "1", "yes", "y"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def title_name(s: str) -> str:
    """Proper-case a given name, keeping accents and hyphen/apostrophe compounds (Jean-Marc, D'Arcy)."""
    s = s.strip()
    if not s:
        return ""
    parts = re.split(r"([-'’ ])", s.lower())
    return "".join(p[:1].upper() + p[1:] if p and p not in "-'’ " else p for p in parts)


def looks_like_given_name(tok: str) -> bool:
    t = tok.strip()
    if len(t) < 3 or len(t) > 20:
        return False
    if not NAME_RE.match(title_name(t)):
        return False
    low = strip_accents(t.lower())
    if low in USERNAME_STOP or low in {strip_accents(w) for w in STUDIO_WORDS}:
        return False
    if re.search(r"\d", t):
        return False
    if low in COMMON_WORDS:
        return False
    # concatenated brand handles like cocoonyoga / puppyyogabordeaux / yogabss
    if any(w in low for w in ("yoga", "yogi", "pilates", "studio", "zen", "bordeaux", "lille", "lyon", "paris", "club", "centre")):
        return False
    return True


def domain_of(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
    except ValueError:
        return ""
    return host[4:] if host.startswith("www.") else host


# ---------------------------------------------------------------- website
def fetch_url(url: str) -> dict:
    """GET a URL once (cached). Returns {status, final, html, error}."""
    url = (url or "").strip()
    if not url:
        return {"status": "", "final": "", "html": "", "error": ""}
    if not re.match(r"^https?://", url, re.I):
        url = "http://" + url
    with _fetch_lock:
        if url in _fetch_cache:
            return _fetch_cache[url]
    result = {"status": "dead", "final": "", "html": "", "error": ""}
    for attempt in range(2):
        try:
            r = requests.get(url, timeout=12, allow_redirects=True, headers=HEADERS)
            result["final"] = r.url
            if 200 <= r.status_code < 300:
                result["status"] = "redirect" if domain_of(r.url) != domain_of(url) else "live"
                if "text/html" in r.headers.get("content-type", "") or r.text[:200].lstrip().startswith("<"):
                    result["html"] = r.text[:400_000]
            else:
                result["status"] = "dead"
                result["error"] = f"http {r.status_code}"
            break
        except requests.Timeout:
            result["error"] = "timeout"
            if attempt == 0:
                continue
        except requests.RequestException as exc:
            result["error"] = type(exc).__name__
            break
    with _fetch_lock:
        _fetch_cache[url] = result
    return result


def parse_html(html: str) -> dict:
    """Extract title / og:title / meta description / headings / visible text snippet."""
    out = {"title": "", "og_title": "", "description": "", "headings": [], "text": ""}
    if not html:
        return out
    if BeautifulSoup is not None:
        soup = BeautifulSoup(html, "html.parser")
        for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "iframe"]):
            t.decompose()
        if soup.title and soup.title.string:
            out["title"] = soup.title.string.strip()
        og = soup.find("meta", attrs={"property": "og:title"})
        if og and og.get("content"):
            out["og_title"] = og["content"].strip()
        md = soup.find("meta", attrs={"name": "description"}) or soup.find("meta", attrs={"property": "og:description"})
        if md and md.get("content"):
            out["description"] = md["content"].strip()
        out["headings"] = [h.get_text(" ", strip=True) for h in soup.find_all(["h1", "h2"])][:12]
        out["text"] = re.sub(r"\s+", " ", soup.get_text(" ", strip=True))[:3000]
    else:
        m = re.search(r"<title[^>]*>(.*?)</title>", html, re.I | re.S)
        out["title"] = html_mod.unescape(m.group(1)).strip() if m else ""
        m = re.search(r'property=["\']og:title["\'][^>]*content=["\']([^"\']*)', html, re.I)
        out["og_title"] = html_mod.unescape(m.group(1)).strip() if m else ""
        m = re.search(r'name=["\']description["\'][^>]*content=["\']([^"\']*)', html, re.I)
        out["description"] = html_mod.unescape(m.group(1)).strip() if m else ""
        out["headings"] = [html_mod.unescape(re.sub(r"<[^>]+>", " ", h)).strip()
                           for h in re.findall(r"<h[12][^>]*>(.*?)</h[12]>", html, re.I | re.S)][:12]
        body = re.sub(r"<(script|style|noscript)[^>]*>.*?</\1>", " ", html, flags=re.I | re.S)
        out["text"] = re.sub(r"\s+", " ", html_mod.unescape(re.sub(r"<[^>]+>", " ", body)))[:3000]
    return out


# ---------------------------------------------------------------- candidates
def cand_from_raw(raw: str) -> str:
    """'Claire Gómez - Professeure…' → Claire; 'ANNA ZINGARELLI HATHA YOGA…' → Anna; 'Audrey' → Audrey."""
    raw = (raw or "").strip()
    if not raw:
        return ""
    if " " not in raw and looks_like_given_name(raw):
        return title_name(raw)
    m = TITLE_PERSON_RE.match(raw)
    if m and looks_like_given_name(m.group("first")) and not any(
        strip_accents(m.group("last").lower()) == strip_accents(w) for w in STUDIO_WORDS
    ):
        return title_name(m.group("first"))
    return ""


def cand_from_email(email: str) -> str:
    user = email.split("@")[0]
    for tok in re.split(r"[._\-+]", user):
        tok = re.sub(r"\d+$", "", tok)
        if looks_like_given_name(tok):
            return title_name(tok)
    return ""


def cand_from_url(url: str) -> str:
    path = unquote(urlparse(url or "").path)
    for seg in reversed([s for s in path.split("/") if s]):
        seg = re.sub(r"\.\w+$", "", seg)
        toks = re.split(r"[-_]", seg)
        for i, tok in enumerate(toks):
            # skip slugs like "professeur-de-yoga-vinyasa-camille": pick first given-name-looking token
            if looks_like_given_name(tok):
                return title_name(tok)
    return ""


def cand_from_site(meta: dict, email: str = "", url: str = "") -> str:
    """Name from page title/og:title/headings. Headings are noisy ("Séances de yoga"), so a candidate is
    accepted only when the field has a person-style separator ("Claire Gómez - Professeure…") or the
    token also shows up in the email username / URL path."""
    corroborate = strip_accents((email.split("@")[0] + " " + unquote(urlparse(url or "").path)).lower())
    for field in [meta.get("title", ""), meta.get("og_title", "")] + meta.get("headings", []):
        c = cand_from_raw(field)
        if not c:
            continue
        strong = bool(re.search(r"\s[-–|:]\s|\bprof", field, re.I))
        if strong or strip_accents(c.lower()) in corroborate:
            return c
    return ""


# ---------------------------------------------------------------- company heuristics
def company_from_raw(raw: str) -> str:
    s = re.sub(r"\(.*?\)", " ", raw or "")
    s = re.split(r"\s[-–|:]\s|\s[-–|]|[-–|]\s", s)[0]
    s = re.sub(r"\bdepuis\s+\d+\s+ans\b", " ", s, flags=re.I)
    toks = [t for t in s.split() if strip_accents(t.lower()) not in {strip_accents(w) for w in STUDIO_WORDS}]
    out = " ".join(toks).strip(" ,.-")
    return out if 2 <= len(out) <= 30 else ""


# ---------------------------------------------------------------- LLM
SYSTEM_PROMPT = (
    "You are cleaning a French cold-email list of yoga teachers / studios for a campaign that opens with "
    "'Bonjour {{firstName}}'. For each lead return a strict JSON array of objects "
    '{"id": <int>, "first_name": <str>, "company": <str>, "confidence": <float 0-1>}. No prose, no markdown.\n'
    "Rules:\n"
    "- first_name = the PERSON's given name only (never a surname, never a studio word), properly cased "
    "(Anna, Claire, Cyril, Jean-Marc), French accents kept. Use website text, URL path, email username and "
    "the raw name as evidence. If the email is generic (contact@, hello@, info@) but the page or URL clearly "
    "names ONE teacher, use that teacher. If the lead is a studio/directory/platform with no single identifiable "
    "person, or you are unsure (several teachers, a listing site), first_name = \"\". A wrong name is worse "
    "than none.\n"
    "- company = casual short studio/brand name a friend would use: drop 'Yoga <City>', city names, 'Centre', "
    "'Studio', 'depuis 23 ans', legal words, locations in parentheses. E.g. 'Studio Nataraja Yoga' -> 'Nataraja', "
    "'Yoga Pop Bordeaux (Jardin Public)' -> 'Yoga Pop', 'Centre de Yoga Iyengar de Bordeaux Chartons CYIB' -> "
    "'Yoga Iyengar Bordeaux'. If nothing sensible, \"\".\n"
    "- confidence = how sure you are of first_name (0 if blank)."
)


def llm_batch(leads: list) -> dict:
    """Run one LLM call for a batch of leads; returns {id: {first_name, company, confidence}}."""
    from modules.llm_client import chat_completion

    cache_hit = {ld["id"]: _llm_cache[ld["cache_key"]] for ld in leads if ld["cache_key"] in _llm_cache}
    leads = [ld for ld in leads if ld["id"] not in cache_hit]
    if not leads:
        return {"_tokens": (0, 0), **cache_hit}

    items = []
    for ld in leads:
        meta = ld["meta"]
        items.append({
            "id": ld["id"],
            "raw_name": ld["original_name"],
            "email": ld["email"],
            "city": ld["city"],
            "url": ld["website"],
            "site_title": meta.get("title", "")[:150],
            "og_title": meta.get("og_title", "")[:150],
            "meta_description": meta.get("description", "")[:300],
            "headings": meta.get("headings", [])[:6],
            "page_text": meta.get("text", "")[:800],
            "candidates": ld["candidates"],
        })
    user = "Leads:\n" + json.dumps(items, ensure_ascii=False)
    try:
        text = chat_completion(SYSTEM_PROMPT, user, model=LLM_MODEL,
                               max_tokens=LLM_MAX_TOKENS_PER_LEAD * len(leads))
    except Exception as exc:  # noqa: BLE001 — any API failure falls back to heuristics
        logger.warning("LLM batch failed: %s", exc)
        return {"_error": str(exc), "_tokens": (0, 0)}
    est_in = len(SYSTEM_PROMPT + user) // 4
    est_out = len(text) // 4
    m = re.search(r"\[.*\]", text, re.S)
    if not m:
        logger.warning("LLM returned no JSON array: %r", text[:200])
        return {"_error": "no json", "_tokens": (est_in, est_out)}
    try:
        arr = json.loads(m.group(0))
    except json.JSONDecodeError:
        try:
            arr = json.loads(re.sub(r",\s*\]", "]", m.group(0)))
        except json.JSONDecodeError:
            logger.warning("LLM JSON parse failed: %r", text[:200])
            return {"_error": "bad json", "_tokens": (est_in, est_out)}
    out = {"_tokens": (est_in, est_out), **cache_hit}
    by_id = {ld["id"]: ld for ld in leads}
    for obj in arr if isinstance(arr, list) else []:
        if not isinstance(obj, dict) or "id" not in obj:
            continue
        try:
            conf = float(obj.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        rec = {
            "first_name": str(obj.get("first_name", "") or "").strip(),
            "company": str(obj.get("company", "") or "").strip(),
            "confidence": max(0.0, min(1.0, conf)),
        }
        out[int(obj["id"])] = rec
        if int(obj["id"]) in by_id:
            with _fetch_lock:
                _llm_cache[by_id[int(obj["id"])]["cache_key"]] = rec
    return out


# ---------------------------------------------------------------- deep pass (about/team pages)
ABOUT_RE = re.compile(r"a-?propos|about|qui-?suis|qui-?sommes|equipe|équipe|team|professeur|\bprofs?\b|fondat|"
                      r"\bmoi\b|presentation|présentation|histoire|\bbio\b", re.I)
DEEP_SYSTEM = (
    "You are cleaning a French cold-email list of yoga studios. For each lead you get the homepage plus "
    "'about/team' pages. Answer: who is the teacher or founder who RUNS this studio (the person the studio "
    "mailbox reaches)? Return a strict JSON array of {\"id\": <int>, \"first_name\": <str>, \"company\": <str>, "
    "\"confidence\": <float 0-1>}. first_name = given name only, properly cased, French accents kept. "
    "Leave first_name \"\" if unclear, if several teachers are listed with no clear owner, if the page is a "
    "directory/platform, or if the name is only a testimonial/author. company = casual short brand name. "
    "A wrong name is worse than none. No prose, no markdown."
)


def about_links(html: str, base_url: str) -> list:
    """Internal links whose href or anchor text looks like an about/team page (max 4, deduped)."""
    if not html:
        return []
    base_dom = domain_of(base_url)
    out = []
    if BeautifulSoup is not None:
        pairs = [(a.get("href", ""), a.get_text(" ", strip=True)) for a in BeautifulSoup(html, "html.parser").find_all("a", href=True)]
    else:
        pairs = [(h, re.sub(r"<[^>]+>", " ", t)) for h, t in re.findall(r'<a[^>]+href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', html, re.I | re.S)]
    for href, text in pairs:
        if not (ABOUT_RE.search(href) or ABOUT_RE.search(text or "")):
            continue
        if href.startswith(("mailto:", "tel:", "javascript:", "#")):
            continue
        full = urljoin(base_url, href).split("#")[0]
        if domain_of(full) != base_dom or full.rstrip("/") == base_url.rstrip("/"):
            continue
        if full not in out:
            out.append(full)
        if len(out) >= 4:
            break
    return out


def deep_batch(leads: list) -> dict:
    """LLM call over homepage + about pages for leads still lacking a name."""
    from modules.llm_client import chat_completion

    cache_hit = {ld["id"]: _llm_cache[ld["deep_key"]] for ld in leads if ld["deep_key"] in _llm_cache}
    leads = [ld for ld in leads if ld["id"] not in cache_hit]
    if not leads:
        return {"_tokens": (0, 0), **cache_hit}
    items = []
    for ld in leads:
        items.append({
            "id": ld["id"], "raw_name": ld["original_name"], "email": ld["email"], "url": ld["website"],
            "homepage": {"title": ld["meta"].get("title", "")[:150], "headings": ld["meta"].get("headings", [])[:6],
                         "text": ld["meta"].get("text", "")[:800]},
            "about_pages": [{"url": u, "title": m.get("title", "")[:150], "headings": m.get("headings", [])[:8],
                             "text": m.get("text", "")[:1500]} for u, m in ld["deep_pages"]],
        })
    user = "Leads:\n" + json.dumps(items, ensure_ascii=False)
    try:
        text = chat_completion(DEEP_SYSTEM, user, model=LLM_MODEL, max_tokens=LLM_MAX_TOKENS_PER_LEAD * len(leads))
    except Exception as exc:  # noqa: BLE001 — API failure just leaves the name blank
        logger.warning("Deep LLM batch failed: %s", exc)
        return {"_error": str(exc), "_tokens": (0, 0), **cache_hit}
    est = (len(DEEP_SYSTEM + user) // 4, len(text) // 4)
    m = re.search(r"\[.*\]", text, re.S)
    try:
        arr = json.loads(re.sub(r",\s*\]", "]", m.group(0))) if m else []
    except json.JSONDecodeError:
        logger.warning("Deep LLM JSON parse failed: %r", text[:200])
        return {"_error": "bad json", "_tokens": est, **cache_hit}
    out = {"_tokens": est, **cache_hit}
    by_id = {ld["id"]: ld for ld in leads}
    for obj in arr if isinstance(arr, list) else []:
        if not isinstance(obj, dict) or "id" not in obj or int(obj["id"]) not in by_id:
            continue
        try:
            conf = float(obj.get("confidence", 0) or 0)
        except (TypeError, ValueError):
            conf = 0.0
        rec = {"first_name": str(obj.get("first_name", "") or "").strip(),
               "company": str(obj.get("company", "") or "").strip(), "confidence": max(0.0, min(1.0, conf))}
        out[int(obj["id"])] = rec
        with _fetch_lock:
            _llm_cache[by_id[int(obj["id"])]["deep_key"]] = rec
    return out


def deep_pass(leads: list, workers: int) -> tuple:
    """Second pass for blank-name leads with a live site: crawl about/team pages, ask the LLM again."""
    targets = [ld for ld in leads if not ld["first_name"] and ld["website_status"] in ("live", "redirect")]
    for ld in targets:
        ld["about_urls"] = about_links(ld["html"], ld["website"])
    urls = list(dict.fromkeys(u for ld in targets for u in ld["about_urls"]))
    logger.info("Deep pass: %d blank leads, %d about/team pages to fetch", len(targets), len(urls))
    with ThreadPoolExecutor(max_workers=workers) as ex:
        list(ex.map(fetch_url, urls))
    for ld in targets:
        ld["deep_pages"] = [(u, parse_html(fetch_url(u)["html"])) for u in ld["about_urls"]]
        ld["deep_pages"] = [(u, m) for u, m in ld["deep_pages"] if m.get("text")]
        ld["deep_key"] = "deep|" + ld["cache_key"] + "|" + "|".join(u for u, _ in ld["deep_pages"])
    batches = [targets[i:i + 5] for i in range(0, len(targets), 5)]
    tokens = [0, 0]
    found = 0
    with ThreadPoolExecutor(max_workers=min(4, workers)) as ex:
        results = list(ex.map(deep_batch, batches))
    for batch, res in zip(batches, results):
        tokens[0] += res.get("_tokens", (0, 0))[0]
        tokens[1] += res.get("_tokens", (0, 0))[1]
        for ld in batch:
            rec = res.get(ld["id"])
            if not rec or rec["confidence"] < 0.6:
                continue
            name = sanitize_name(rec["first_name"])
            if not name:
                continue
            raw_single = cand_from_raw(ld["original_name"]) if " " not in ld["original_name"] else ""
            if raw_single and strip_accents(raw_single.lower()) != strip_accents(name.lower()):
                continue  # listing says "Cassandre", about page says "Daphné": conflicting evidence -> blank
            ld["first_name"], ld["name_source"], ld["name_confidence"] = name, "website_deep", rec["confidence"]
            if rec["company"] and not ld["company"]:
                ld["company"] = rec["company"][:40]
            found += 1
    return tokens, found


def corroborated(ld: dict) -> bool:
    """True when the chosen first name shows up in the email username, URL path or raw listing name."""
    hay = strip_accents(" ".join([ld["email"].split("@")[0], unquote(urlparse(ld["website"]).path),
                                  ld["original_name"]]).lower())
    name = strip_accents(ld["first_name"].lower())
    toks = set(re.split(r"[^a-z]+", hay))
    # concatenated handles (cyrilyoga@, emiliepiette@) count when the name is long enough to be unambiguous
    return name in toks or (len(name) >= 4 and name in re.sub(r"[^a-z]", "", hay))


def clean_company(c: str) -> str:
    """Collapse LLM stutter like 'Yogaaa' -> 'Yoga' (3+ repeated letters)."""
    return re.sub(r"([A-Za-zÀ-ÖØ-öø-ÿ])\1{2,}", r"\1", c or "")


# ---------------------------------------------------------------- pipeline
def heuristic_name(ld: dict) -> tuple:
    """Deterministic fallback: (first_name, source, confidence)."""
    c = cand_from_raw(ld["original_name"])
    if c:
        return c, "raw", 0.7
    c = cand_from_site(ld["meta"], ld["email"], ld["website"])
    if c:
        return c, "website", 0.5
    c = cand_from_url(ld["website"])
    if c:
        return c, "website", 0.5
    c = cand_from_email(ld["email"])
    if c:
        return c, "email", 0.5
    return "", "none", 0.0


def sanitize_name(name: str) -> str:
    """Final guard: single/compound given name, no studio words, properly cased; else blank."""
    name = (name or "").strip().strip("\"'")
    if not name:
        return ""
    toks = name.split()
    if len(toks) > 2:
        return ""
    if len(toks) == 2:  # LLM gave "First Last" despite instructions: keep first token only if plausible
        name = toks[0]
    if not looks_like_given_name(name):
        return ""
    return title_name(name)


def process(rows: list, workers: int, use_llm: bool, deep: bool = True) -> tuple:
    leads = []
    for i, r in enumerate(rows):
        leads.append({
            "id": i, "row": r,
            "original_name": (r.get("First name") or "").strip(),
            "city": (r.get("City") or "").strip(),
            "email": norm_email(r.get("email") or r.get("Email")),
            "website": (r.get("Website") or "").strip(),
            "found_on": (r.get("Found on") or "").strip(),
            "cache_key": f"{norm_email(r.get('email') or r.get('Email'))}|{(r.get('First name') or '').strip()}",
        })

    logger.info("Fetching %d websites with %d workers", len({ld["website"] for ld in leads if ld["website"]}), workers)
    with ThreadPoolExecutor(max_workers=workers) as ex:
        fetched = list(ex.map(lambda ld: fetch_url(ld["website"]), leads))
    for ld, f in zip(leads, fetched):
        ld["html"] = f["html"]
        ld["website_status"] = f["status"]
        ld["website_final"] = f["final"] if f["status"] == "redirect" else ""
        ld["meta"] = parse_html(f["html"])
        cands = [c for c in (cand_from_raw(ld["original_name"]), cand_from_site(ld["meta"], ld["email"], ld["website"]),
                             cand_from_url(ld["website"]), cand_from_email(ld["email"])) if c]
        ld["candidates"] = list(dict.fromkeys(cands))

    llm_tokens = [0, 0]
    llm_failures = 0
    if use_llm and leads:
        if LLM_CACHE_PATH.exists():
            try:
                _llm_cache.update(json.loads(LLM_CACHE_PATH.read_text(encoding="utf-8")))
            except (OSError, json.JSONDecodeError) as exc:
                logger.warning("LLM cache unreadable, ignoring: %s", exc)
        batches = [leads[i:i + LLM_BATCH] for i in range(0, len(leads), LLM_BATCH)]
        logger.info("LLM pass: %d batches of up to %d", len(batches), LLM_BATCH)
        with ThreadPoolExecutor(max_workers=min(4, workers)) as ex:
            results = list(ex.map(llm_batch, batches))
        for batch, res in zip(batches, results):
            llm_tokens[0] += res.get("_tokens", (0, 0))[0]
            llm_tokens[1] += res.get("_tokens", (0, 0))[1]
            if "_error" in res:
                llm_failures += 1
            for ld in batch:
                ld["llm"] = res.get(ld["id"])
        LLM_CACHE_PATH.parent.mkdir(parents=True, exist_ok=True)
        LLM_CACHE_PATH.write_text(json.dumps(_llm_cache, ensure_ascii=False, indent=1), encoding="utf-8")

    for ld in leads:
        llm = ld.get("llm")
        if llm is not None:
            name = sanitize_name(llm["first_name"])
            ld["first_name"] = name
            ld["name_source"] = "llm" if name else "none"
            ld["name_confidence"] = llm["confidence"] if name else 0.0
            ld["company"] = llm["company"][:40]
            raw = ld["original_name"]
            raw_cand = cand_from_raw(raw)
            strong_raw = bool(raw_cand and " " in raw and re.search(r"\s[-–|:]\s|\bprof", raw, re.I))
            if strong_raw and name and name != raw_cand:
                # "Lucie Dadillon - YOW" beats an email handle like luzi@: the raw listing names the person.
                ld["first_name"], ld["name_source"], ld["name_confidence"] = raw_cand, "raw", 0.9
            elif not name and raw_cand and " " not in raw:
                # Raw is a bare given name ("Camille"); accept only if the email/URL corroborates it.
                toks = set(re.split(r"[._\-+/]", strip_accents(ld["email"].split("@")[0].lower())))
                toks |= set(re.split(r"[-_/.]", strip_accents(unquote(urlparse(ld["website"]).path).lower())))
                if strip_accents(raw_cand.lower()) in toks:
                    ld["first_name"], ld["name_source"], ld["name_confidence"] = raw_cand, "raw", 0.8
        else:
            name, src, conf = heuristic_name(ld)
            ld["first_name"], ld["name_source"], ld["name_confidence"] = name, src, conf
            ld["company"] = company_from_raw(ld["original_name"])
        r = ld["row"]
        status = (r.get("status") or "").strip().lower()
        user, _, dom = ld["email"].partition("@")
        suspect = dom in PLATFORM_DOMAINS or dom in PLACEHOLDER_DOMAINS or user in PLACEHOLDER_USERS
        ok = (status in SEND_OK_STATUS and truthy(r.get("is_valid_syntax", "true"))
              and not truthy(r.get("is_disabled")) and status != "invalid" and not suspect)
        ld["send_recommended"] = "yes" if ok else "no"
        ld["email_status"] = status

    deep_found = 0
    if use_llm and deep:
        dtok, deep_found = deep_pass(leads, workers)
        llm_tokens[0] += dtok[0]
        llm_tokens[1] += dtok[1]
        LLM_CACHE_PATH.write_text(json.dumps(_llm_cache, ensure_ascii=False, indent=1), encoding="utf-8")

    for ld in leads:
        ld["company"] = clean_company(ld["company"])
        # An LLM-picked name that nothing else (email, URL, listing) corroborates stays visible as "unsure".
        if ld["first_name"] and ld["name_source"] in ("llm", "website_deep") and not corroborated(ld):
            ld["name_confidence"] = min(ld["name_confidence"], 0.6)

    # ---- dedupe on email
    groups: dict = {}
    for ld in leads:
        groups.setdefault(ld["email"], []).append(ld)
    kept = []
    dup_removed = 0
    rank = {"live": 0, "redirect": 1, "dead": 2, "": 3}
    for email, grp in groups.items():
        grp_sorted = sorted(grp, key=lambda l: (
            0 if l["first_name"] else 1,
            0 if l["email_status"] == "safe" else 1,
            rank.get(l["website_status"], 3),
            l["id"],
        ))
        best = grp_sorted[0]
        others = grp_sorted[1:]
        best["dup_count"] = len(grp)
        best["merged_from"] = " | ".join(o["original_name"] for o in others)
        if not best["company"]:
            best["company"] = next((o["company"] for o in others if o["company"]), "")
        dup_removed += len(others)
        kept.append(best)
    kept.sort(key=lambda l: l["id"])
    stats = {"llm_tokens_in": llm_tokens[0], "llm_tokens_out": llm_tokens[1],
             "llm_batches_failed": llm_failures, "duplicates_removed": dup_removed, "deep_found": deep_found}
    return kept, stats


LEAD_COLS = ["first_name", "company", "city", "email", "website", "website_status", "website_final",
             "email_status", "overall_score", "is_safe_to_send", "send_recommended", "name_source",
             "name_confidence", "original_name", "dup_count", "merged_from", "found_on"]
CONSUMED_INPUT_COLS = {"First name", "City", "Email", "Website", "Found on", "email", "status",
                       "overall_score", "is_safe_to_send"}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--input", required=True)
    ap.add_argument("--output", required=True)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--deep", dest="deep", action="store_true", default=True,
                    help="second LLM pass over about/team pages for blank names (default on)")
    ap.add_argument("--no-deep", dest="deep", action="store_false")
    args = ap.parse_args()

    with open(args.input, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        in_cols = reader.fieldnames or []
        rows = list(reader)
    if args.limit:
        rows = rows[:args.limit]
    logger.info("Loaded %d rows from %s", len(rows), args.input)

    use_llm = not args.no_llm
    if use_llm and not os.environ.get("OPENROUTER_API_KEY"):
        logger.warning("No OpenRouter key in env; falling back to --no-llm heuristics")
        use_llm = False

    kept, stats = process(rows, args.workers, use_llm, args.deep)

    extra_cols = [c for c in in_cols if c not in CONSUMED_INPUT_COLS]
    out_cols = LEAD_COLS + extra_cols
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=out_cols)
        w.writeheader()
        for ld in kept:
            r = ld["row"]
            row = {c: ld.get(c, "") for c in LEAD_COLS}
            row["overall_score"] = r.get("overall_score", "")
            row["is_safe_to_send"] = r.get("is_safe_to_send", "")
            row["name_confidence"] = f"{ld['name_confidence']:.2f}"
            for c in extra_cols:
                row[c] = r.get(c, "")
            w.writerow(row)

    cost = (stats["llm_tokens_in"] * LLM_PRICE_IN + stats["llm_tokens_out"] * LLM_PRICE_OUT) / 1_000_000
    report = {
        "input": str(args.input), "output": str(out_path),
        "rows_in": len(rows), "rows_out": len(kept),
        "duplicates_removed": stats["duplicates_removed"],
        "names_found": sum(1 for l in kept if l["first_name"]),
        "names_blank": sum(1 for l in kept if not l["first_name"]),
        "name_source": {s: sum(1 for l in kept if l["name_source"] == s) for s in ("llm", "website_deep", "website", "email", "raw", "none")},
        "deep_pass_names_found": stats["deep_found"],
        "deep_pass_rows": [{"email": l["email"], "first_name": l["first_name"], "confidence": l["name_confidence"],
                            "original_name": l["original_name"]} for l in kept if l["name_source"] == "website_deep"],
        "website": {s: sum(1 for l in kept if l["website_status"] == s) for s in ("live", "redirect", "dead", "")},
        "send_recommended": {s: sum(1 for l in kept if l["send_recommended"] == s) for s in ("yes", "no")},
        "llm": {"used": use_llm, "model": LLM_MODEL if use_llm else None,
                "est_tokens_in": stats["llm_tokens_in"], "est_tokens_out": stats["llm_tokens_out"],
                "est_cost_usd": round(cost, 4), "batches_failed": stats["llm_batches_failed"]},
        "blank_first_name_rows": [{"email": l["email"], "original_name": l["original_name"],
                                   "company": l["company"], "send_recommended": l["send_recommended"]}
                                  for l in kept if not l["first_name"]],
    }
    rep_path = out_path.parent / "report.json"
    rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    logger.info("Wrote %s (%d rows) and %s", out_path, len(kept), rep_path)
    print(json.dumps({k: v for k, v in report.items() if k != "blank_first_name_rows"}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
