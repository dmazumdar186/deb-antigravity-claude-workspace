#!/usr/bin/env python3
"""
fr_instructor_finder.py
description: Find independent instructors in France (yoga, pilates, languages, music, tutoring...)
             via Superprof (Serper site: search), Google Maps (Serper maps) and Meetup (Playwright),
             optionally enrich with website/email/socials and classify with Jev.
inputs: --disciplines, --cities, --sources, --pages, --limit, --mock, --enrich, --jev, --sheet, --out;
        env: SERPER_API_KEY, OPENROUTER_API_KEY|OPENROUTER_API_TOEKN, GOOGLE_SERVICE_ACCOUNT_PATH (optional)
outputs: .tmp/fr_instructors.json + .tmp/fr_instructors.csv (optional Google Sheet tab "fr_instructors")
usage:
    python3 execution/lead_sourcing/fr_instructor_finder.py --mock
    python3 execution/lead_sourcing/fr_instructor_finder.py --disciplines yoga --cities Lyon --pages 1 --enrich --jev --limit 15
"""

import argparse
import os
import re
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import quote_plus, urljoin, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT / "execution"))

from modules.pipeline_utils import (  # noqa: E402
    load_leads,
    export_csv,
    generate_run_id,
    now_iso,
    retry_with_backoff,
    save_leads,
    setup_logging,
)

load_dotenv(ROOT / ".env")
logger = setup_logging("fr_instructor_finder", log_dir=ROOT / ".tmp")

SERPER_SEARCH_URL = "https://google.serper.dev/search"
SERPER_MAPS_URL = "https://google.serper.dev/maps"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
DEFAULT_DISCIPLINES = "yoga,pilates,méditation,anglais,espagnol,piano,guitare,maths,danse,fitness"
DEFAULT_CITIES = ("Paris,Marseille,Lyon,Toulouse,Nice,Nantes,Montpellier,Strasbourg,Bordeaux,Lille,Rennes,Reims,"
                  "Toulon,Saint-Étienne,Le Havre,Grenoble,Dijon,Angers,Nîmes,Villeurbanne,Clermont-Ferrand,"
                  "Le Mans,Aix-en-Provence,Brest,Tours,Amiens,Limoges,Annecy,Perpignan,Metz")
BLOCKED_DOMAINS = ("superprof", "meetup", "google", "pagesjaunes", "yelp", "linkedin",
                   # directories / booking platforms: their emails belong to the platform, not the teacher
                   "olybe", "wellhub", "momoyoga", "studiomaps", "consulteo", "ohmyresto", "lyon-entreprises",
                   "classpass", "doctolib", "tripadvisor", "societe.com", "youtube", "tiktok", "wikipedia")
EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
EMAIL_BAD = ("example.com", "domaine.com", "domain.com", "utilisateur@", "votre", "email@", "sentry", "wixpress", ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")
TITLE_RE = re.compile(
    r"^(?P<name>[^-–]+?)\s*[-–]\s*Prof(?:esseur)?\s+(?:de|d['’])\s*(?P<disc>.+?)\s+(?:à|a)\s+(?P<city>[^-–]+?)\s*(?:[-–]|$)",
    re.IGNORECASE,
)
PRICE_RE = re.compile(r"(\d+)\s*€\s*/\s*h")
STUDENTS_RE = re.compile(r"(\d+)\s+élèves?", re.IGNORECASE)
COLUMNS = ["source", "name", "first_name", "discipline", "city", "price_eur_h", "students", "website", "email",
           "email_source", "website_source", "instagram", "facebook", "phone", "address", "rating", "reviews", "category",
           "members", "organizer", "profile_url", "snippet", "jev_independent", "jev_web_presence",
           "jev_segment", "jev_confidence", "run_id", "scraped_at"]

STATS = {"serper_queries": 0}


@retry_with_backoff(max_retries=3, base_delay=1.0)
def _serper_post(url: str, body: dict) -> dict:
    key = os.getenv("SERPER_API_KEY", "")
    if not key:
        raise RuntimeError("SERPER_API_KEY not set")
    time.sleep(0.25)
    STATS["serper_queries"] += 1
    resp = requests.post(url, json=body, headers={"X-API-KEY": key, "Content-Type": "application/json"}, timeout=30)
    resp.raise_for_status()
    return resp.json()


def serper(url: str, body: dict) -> dict:
    """Serper call that never raises; returns {} on failure."""
    try:
        return _serper_post(url, body)
    except (requests.RequestException, RuntimeError, ValueError) as exc:
        logger.warning("Serper failed for %s: %s", body.get("q"), exc)
        return {}


def _base(source: str, discipline: str, city: str, run_id: str) -> dict:
    return {"source": source, "discipline": discipline, "city": city, "run_id": run_id, "scraped_at": now_iso()}


def is_superprof_profile(link: str) -> bool:
    path = urlparse(link).path
    return "superprof.fr" in link and path.endswith(".html") and not path.startswith("/cours/")


def parse_superprof_title(title: str) -> dict:
    m = TITLE_RE.search(title or "")
    if not m:
        return {}
    return {
        "first_name": m.group("name").strip(),
        "discipline_raw": m.group("disc").strip(),
        "city_raw": m.group("city").strip(),
        "price_eur_h": int(pm.group(1)) if (pm := PRICE_RE.search(title)) else None,
        "students": int(sm.group(1)) if (sm := STUDENTS_RE.search(title)) else None,
    }


def source_superprof(discipline: str, city: str, pages: int, run_id: str) -> list[dict]:
    leads = []
    for page in range(1, pages + 1):
        data = serper(SERPER_SEARCH_URL, {"q": f'site:superprof.fr "Prof de {discipline}" "{city}"',
                                          "gl": "fr", "hl": "fr", "num": 10, "page": page})
        organic = data.get("organic") or []
        for r in organic:
            link = r.get("link", "")
            if not is_superprof_profile(link):
                continue
            parsed = parse_superprof_title(r.get("title", ""))
            lead = _base("superprof", discipline, city, run_id)
            lead.update({"first_name": parsed.get("first_name", ""), "name": parsed.get("first_name", ""),
                         "price_eur_h": parsed.get("price_eur_h"), "students": parsed.get("students"),
                         "profile_url": link, "snippet": r.get("snippet", "")})
            leads.append(lead)
        if len(organic) < 10:
            break
    return leads


def source_maps(discipline: str, city: str, run_id: str) -> list[dict]:
    leads = []
    for q in (f"professeur de {discipline} {city}", f"cours de {discipline} {city}"):
        data = serper(SERPER_MAPS_URL, {"q": q, "gl": "fr", "hl": "fr"})
        for p in data.get("places") or []:
            lead = _base("maps", discipline, city, run_id)
            lead.update({"name": p.get("title", ""), "website": p.get("website", "") or "",
                         "phone": p.get("phoneNumber", ""), "address": p.get("address", ""),
                         "rating": p.get("rating"), "reviews": p.get("ratingCount"),
                         "category": p.get("category") or p.get("type", "")})
            leads.append(lead)
    return leads


def source_meetup(discipline: str, city: str, run_id: str, cap: int = 20) -> list[dict]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        logger.warning("playwright not importable; skipping meetup")
        return []
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")
    leads: list[dict] = []
    url = (f"https://www.meetup.com/find/?keywords={quote_plus(discipline)}"
           f"&location=fr--{quote_plus(city)}&source=GROUPS")
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page(user_agent=UA)
            page.goto(url, timeout=45000, wait_until="domcontentloaded")
            page.wait_for_timeout(3000)
            page.mouse.wheel(0, 6000)
            page.wait_for_timeout(2000)
            groups = page.evaluate("""() => {
                const out = {}; const re = /^https:\\/\\/www\\.meetup\\.com\\/([A-Za-z0-9-]+)\\/?$/;
                for (const a of document.querySelectorAll('a[href]')) {
                  const href = a.href.split('?')[0]; const m = href.match(re);
                  if (!m || ['find','topics','cities','apps','login','register','about','pro','lp','blog','help'].includes(m[1])) continue;
                  if (out[href]) continue;
                  const t = (a.innerText || '').trim(); const mm = t.match(/([\\d\\s.,]+k?)\\s*(membres|members)/i);
                  out[href] = {name: (a.querySelector('h3,h2') || a).innerText.split('\\n')[0].trim(), members: mm ? mm[1].trim() : ''};
                }
                return Object.entries(out).map(([href, v]) => ({href, ...v}));
            }""")
            for g in groups[:cap]:
                lead = _base("meetup", discipline, city, run_id)
                lead.update({"name": g.get("name", ""), "members": g.get("members", ""), "profile_url": g["href"]})
                try:
                    page.goto(g["href"], timeout=30000, wait_until="domcontentloaded")
                    page.wait_for_timeout(1500)
                    info = page.evaluate("""() => {
                        const org = document.querySelector('[data-testid*="organizer"], a[href*="/members/"]');
                        const ext = [...document.querySelectorAll('a[href^="http"]')].map(a => a.href)
                          .find(h => !/meetup\\.com|google|apple\\.com|facebook\\.com\\/meetup|twitter\\.com\\/meetup|instagram\\.com\\/meetup|medium\\.com|tiktok\\.com\\/@meetup|linkedin/.test(h));
                        return {organizer: org ? org.innerText.split('\\n')[0].trim() : '', ext: ext || ''};
                    }""")
                    lead["organizer"] = info.get("organizer", "")
                    lead["website"] = info.get("ext", "")
                except Exception as exc:  # playwright raises its own Error types
                    logger.debug("meetup group page failed %s: %s", g["href"], exc)
                leads.append(lead)
            browser.close()
    except Exception as exc:  # meetup must never kill the run
        logger.warning("meetup failed for %s/%s: %s", discipline, city, exc)
    return leads


def _domain(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def has_own_site(lead: dict) -> bool:
    w = lead.get("website") or ""
    return bool(w) and not any(b in _domain(w) for b in BLOCKED_DOMAINS + ("instagram", "facebook"))


def find_email(website: str) -> str:
    for path in ("", "/contact", "/contact/"):
        url = urljoin(website.rstrip("/") + "/", path.lstrip("/")) if path else website
        try:
            resp = requests.get(url, headers={"User-Agent": UA}, timeout=10)
        except requests.RequestException:
            continue
        if resp.status_code != 200:
            continue
        text = resp.content.decode(resp.encoding or "utf-8", errors="replace")
        for e in EMAIL_RE.findall(text):
            if not any(b in e.lower() for b in EMAIL_BAD):
                return e
    return ""


def enrich_one(lead: dict) -> None:
    if lead.get("_enriched"):
        return
    try:
        _enrich_one(lead)
    except (requests.RequestException, ValueError, KeyError) as exc:  # one bad lead never stops the run
        logger.warning("enrich failed for %s: %s", lead.get("first_name") or lead.get("name"), exc)
    lead["_enriched"] = True


def enrich(leads: list[dict], checkpoint: Path | None = None, workers: int = 8) -> None:
    from concurrent.futures import ThreadPoolExecutor, as_completed
    todo = [l for l in leads if not l.get("_enriched")]
    logger.info("enrich: %d leads to do (%d already done), %d workers", len(todo), len(leads) - len(todo), workers)
    done = 0
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(enrich_one, l): l for l in todo}
        for _ in as_completed(futures):
            done += 1
            if done % 25 == 0 or done == len(todo):
                logger.info("enrich: %d/%d (%d with email)", done, len(todo), sum(1 for l in leads if l.get("email")))
                if checkpoint:
                    save_leads(leads, checkpoint)


def _enrich_one(lead: dict) -> None:
    if True:
        w = lead.get("website") or ""
        if "instagram.com" in w:
            lead["instagram"], lead["website"] = w, ""
        elif "facebook.com" in w:
            lead["facebook"], lead["website"] = w, ""
        if not has_own_site(lead):
            who = lead.get("first_name") or lead.get("name") or ""
            if who:
                data = serper(SERPER_SEARCH_URL, {"q": f'"{who}" {lead["discipline"]} {lead["city"]}',
                                                  "gl": "fr", "hl": "fr", "num": 10})
                for r in data.get("organic") or []:
                    link = r.get("link", "")
                    d = _domain(link)
                    if not d or any(b in d for b in BLOCKED_DOMAINS):
                        continue
                    if "instagram.com" in d:
                        lead.setdefault("instagram", link)
                        continue
                    if "facebook.com" in d:
                        lead.setdefault("facebook", link)
                        continue
                    lead["website"] = link
                    lead["website_source"] = "serper_enrich"  # name-based guess: verify before sending
                    break
        if has_own_site(lead) and not lead.get("email"):
            email = find_email(lead["website"])
            if email:
                # Off-domain emails are usually the directory/platform's, not the teacher's: flag them.
                same = email.split("@")[-1].lower() in _domain(lead["website"])
                lead["email"], lead["email_source"] = email, ("website" if same else "website_offdomain")



def jev_classify(leads: list[dict]) -> None:
    from modules import jev_client
    if not jev_client.available():
        logger.warning("Jev unavailable (no OpenRouter key); skipping")
        return
    questions = {
        "independent": jev_client.noul("Is this a solo independent teacher rather than a studio, school or chain?",
                                       true="solo independent teacher", false="studio, school, chain or company"),
        "web_presence": jev_client.score("How strong is this teacher's own web presence?",
                                         ["none", "social_only", "platform_or_booking_page", "own_site"]),
        "segment": jev_client.choice("Which segment does this teaching business belong to?", {
            "wellness": "yoga, pilates, meditation", "fitness": "fitness, coaching, sport",
            "language": "language lessons", "music": "music lessons", "academic": "maths, school tutoring",
            "arts": "dance, drawing, theatre", "other": "anything else"}),
    }
    states = [{k: lead.get(k, "") or "" for k in ("name", "discipline", "city", "website", "snippet", "category")}
              for lead in leads]
    levels = ["none", "social_only", "platform_or_booking_page", "own_site"]
    t0 = time.perf_counter()
    results = jev_client.decide_many(states, questions)
    cost, errors = 0.0, 0
    for lead, r in zip(leads, results):
        cost += r.cost_usd
        if not r.ok:
            errors += 1
            continue
        # noul answers carry no confidence field; the noul value itself is P(true).
        p_ind = r.noul("independent", 0.5)
        lead["jev_confidence"] = round(max(p_ind, 1 - p_ind), 2)
        if p_ind >= 0.6:
            lead["jev_independent"] = True
        elif p_ind <= 0.4:
            lead["jev_independent"] = False
        idx = int(round(max(0.0, min(3.0, r.score("web_presence")))))
        lead["jev_web_presence"] = levels[idx]
        seg = r.choice("segment")
        if r.probabilities("segment").get(seg, r.confidence("segment")) >= 0.6:
            lead["jev_segment"] = r.choice("segment")
    jev_client.append_ledger({"caller": "fr_instructor_finder", "op": "classify", "items": len(leads),
                              "errors": errors, "cost_usd": cost,
                              "latency_ms": int((time.perf_counter() - t0) * 1000)},
                             path=ROOT / ".tmp" / "jev_ledger.jsonl")
    logger.info("Jev: %d leads, %d errors, $%.5f", len(leads), errors, cost)


def dedup(leads: list[dict]) -> list[dict]:
    seen, out = set(), []
    for lead in leads:
        key = ((lead.get("name") or lead.get("profile_url") or "").strip().lower(),
               (lead.get("city") or "").lower(), (lead.get("discipline") or "").lower())
        if key in seen:
            continue
        seen.add(key)
        out.append(lead)
    return out


def get_mock_data() -> list[dict]:
    run_id = generate_run_id()
    rows = [
        ("superprof", {"name": "Alban", "first_name": "Alban", "discipline": "yoga", "city": "Lyon", "price_eur_h": 40, "students": 3, "profile_url": "https://www.superprof.fr/cours-hatha-flow-lyon.html"}),
        ("superprof", {"name": "Claire", "first_name": "Claire", "discipline": "piano", "city": "Paris", "price_eur_h": 35, "students": 12, "profile_url": "https://www.superprof.fr/pianiste-paris.html"}),
        ("superprof", {"name": "Sofia", "first_name": "Sofia", "discipline": "espagnol", "city": "Bordeaux", "price_eur_h": 25, "students": 7, "profile_url": "https://www.superprof.fr/espagnol-natif-bordeaux.html"}),
        ("maps", {"name": "Yoga avec Marie", "discipline": "yoga", "city": "Lyon", "website": "https://yogamarie.fr", "email": "marie@yogamarie.fr", "email_source": "website", "phone": "06 12 34 56 78", "rating": 4.9, "reviews": 41, "category": "Yoga instructor"}),
        ("maps", {"name": "Pilates Studio Nice", "discipline": "pilates", "city": "Nice", "website": "https://pilatesnice.com", "phone": "04 93 00 00 00", "rating": 4.6, "reviews": 120, "category": "Pilates studio"}),
        ("maps", {"name": "Thomas Guitare", "discipline": "guitare", "city": "Nantes", "instagram": "https://instagram.com/thomasguitare", "rating": 5.0, "reviews": 9, "category": "Music instructor"}),
        ("meetup", {"name": "Méditation Lille", "discipline": "méditation", "city": "Lille", "members": "312", "organizer": "Julie", "profile_url": "https://www.meetup.com/meditation-lille/"}),
        ("meetup", {"name": "English Conversation Toulouse", "discipline": "anglais", "city": "Toulouse", "members": "1,204", "organizer": "Mark", "profile_url": "https://www.meetup.com/english-toulouse/"}),
    ]
    leads = []
    for src, fields in rows:
        lead = _base(src, fields["discipline"], fields["city"], run_id)
        lead.update(fields)
        leads.append(lead)
    return leads


def push_sheet(leads: list[dict], spreadsheet_id: str) -> None:
    if not os.getenv("GOOGLE_SERVICE_ACCOUNT_PATH"):
        logger.warning("GOOGLE_SERVICE_ACCOUNT_PATH not set; skipping sheet push")
        return
    import importlib.util  # path import: `google` collides with the google-auth namespace package
    spec = importlib.util.spec_from_file_location("google_sheets_writer",
                                                  ROOT / "execution" / "google" / "google_sheets_writer.py")
    gsw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gsw)
    open_workbook, write_tab = gsw.open_workbook, gsw.write_tab
    rows = [["" if lead.get(c) is None else str(lead.get(c)) for c in COLUMNS] for lead in leads]
    write_tab(open_workbook(spreadsheet_id), "fr_instructors", COLUMNS, rows, [], [])
    logger.info("Pushed %d rows to sheet tab fr_instructors", len(rows))


def summary(leads: list[dict]) -> None:
    print(f"\n{'=' * 60}\nTotal leads: {len(leads)}")
    for field in ("source", "city", "discipline"):
        print(f"\nBy {field}:")
        for k, v in Counter(lead.get(field, "") for lead in leads).most_common(15):
            print(f"  {k:<30} {v}")
    print(f"\nWith website: {sum(1 for x in leads if has_own_site(x))}  "
          f"With email: {sum(1 for x in leads if x.get('email'))}  "
          f"With instagram/facebook: {sum(1 for x in leads if x.get('instagram') or x.get('facebook'))}")
    q = STATS["serper_queries"]
    print(f"Serper queries: {q}  est. cost: ${q / 1000:.3f}\n{'=' * 60}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--disciplines", default=DEFAULT_DISCIPLINES)
    ap.add_argument("--cities", default=DEFAULT_CITIES)
    ap.add_argument("--sources", default="superprof,maps")
    ap.add_argument("--pages", type=int, default=3)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--mock", action="store_true")
    ap.add_argument("--enrich", action="store_true")
    ap.add_argument("--resume", help="skip scraping; load this JSON (a checkpoint) and continue enrich/jev")
    ap.add_argument("--workers", type=int, default=8, help="parallel enrichment threads")
    ap.add_argument("--jev", action="store_true")
    ap.add_argument("--sheet", default="")
    ap.add_argument("--out", default=str(ROOT / ".tmp" / "fr_instructors.json"))
    args = ap.parse_args()

    if args.mock:
        leads = get_mock_data()
    elif args.resume:
        leads = load_leads(args.resume)
        logger.info("resumed %d leads from %s", len(leads), args.resume)
        if args.enrich:
            enrich(leads, checkpoint=Path(args.out), workers=args.workers)
    else:
        run_id = generate_run_id()
        sources = {s.strip() for s in args.sources.split(",") if s.strip()}
        disciplines = [d.strip() for d in args.disciplines.split(",") if d.strip()]
        cities = [c.strip() for c in args.cities.split(",") if c.strip()]
        leads = []
        for d in disciplines:
            for c in cities:
                if "superprof" in sources:
                    leads += source_superprof(d, c, args.pages, run_id)
                if "maps" in sources:
                    leads += source_maps(d, c, run_id)
                if "meetup" in sources:
                    leads += source_meetup(d, c, run_id)
                logger.info("%s / %s -> %d leads so far", d, c, len(leads))
        leads = dedup(leads)
        if args.limit:
            leads = leads[: args.limit]
        save_leads(leads, Path(args.out))  # raw scrape lands on disk before the slow enrichment starts
        if args.enrich:
            enrich(leads, checkpoint=Path(args.out), workers=args.workers)
    leads = dedup(leads)
    if args.limit:
        leads = leads[: args.limit]
    if args.jev and not args.mock:
        jev_classify(leads)

    out = Path(args.out)
    save_leads(leads, out)
    export_csv(leads, out.with_suffix(".csv"), COLUMNS)
    logger.info("Saved %s and %s", out, out.with_suffix(".csv"))
    if args.sheet:
        push_sheet(leads, args.sheet)
    summary(leads)
    return 0


if __name__ == "__main__":
    sys.exit(main())
