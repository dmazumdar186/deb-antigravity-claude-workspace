"""
leadocean_leads.py

description: LeadOcean -> verified, Jev-gated, site-enriched, icebreaker-personalised cold email leads (Instantly CSV) for the AI Proposal Engine niches (event production/AV, commercial interior fit-out, incentive travel/DMC).
inputs: [--wave 1|2] subcommand (count | export | topup | gate | verify | enrich | icebreak | build) + flags (see --help); env LEADOCEAN_API_KEY, OPENROUTER_API_KEY (alias OPENROUTER_API_TOEKN), SERPER_API_KEY (optional fallback), REOON_API_KEY (wave 2 verify).
outputs: .tmp/leadocean/{counts.json, export_plan.json, exports.json, raw/*.csv, topup_*.json, jev_cache.json, gate.json, sites/*.json, enrich.json, icebreak.json, prodcraft_leads_YYYY-MM-DD.csv, rejects.csv, summary.json}
usage:
    python3 execution/lead_sourcing/leadocean_leads.py count
    python3 execution/lead_sourcing/leadocean_leads.py export --plan-only        # write export_plan.json, no rows spent
    python3 execution/lead_sourcing/leadocean_leads.py export --budget 5000
    python3 execution/lead_sourcing/leadocean_leads.py topup --budget 5000 [--plan-only]  # leftover rows, company-first
    python3 execution/lead_sourcing/leadocean_leads.py gate [--limit 20]
    python3 execution/lead_sourcing/leadocean_leads.py enrich [--limit 20]
    python3 execution/lead_sourcing/leadocean_leads.py icebreak [--limit 20]
    python3 execution/lead_sourcing/leadocean_leads.py build
    # wave 2: national US+UK, verified/untested + Reoon, wave-1 people excluded (outputs in .tmp/leadocean/wave2/)
    python3 execution/lead_sourcing/leadocean_leads.py --wave 2 topup --niches av,fitout,dmc --max-pages 40 --max-per-domain 4
    python3 execution/lead_sourcing/leadocean_leads.py --wave 2 gate && ... --wave 2 verify && ... --wave 2 enrich
    python3 execution/lead_sourcing/leadocean_leads.py --wave 2 icebreak --max-usd 13 && ... --wave 2 build

Every step is idempotent and resumable: results are cached under .tmp/leadocean/ keyed by
export key, company domain or person id, so a re-run only does the missing work.
Directive: directives/lead_sourcing/leadocean_leads.md
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import html
import json
import logging
import os
import re
import sys
import threading
import time
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")
# Cloud sessions expose the OpenRouter key under a misspelt alias; llm_client reads only the canonical name.
if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get("OPENROUTER_API_TOEKN"):
    os.environ["OPENROUTER_API_KEY"] = os.environ["OPENROUTER_API_TOEKN"]

log = logging.getLogger("leadocean_leads")

TMP = ROOT / ".tmp" / "leadocean"
RAW = TMP / "raw"
SITES = TMP / "sites"
API = "https://api.leadocean.io"
UA = "Mozilla/5.0 (compatible; ProdcraftResearchBot/1.0; +https://prodcraft.ai)"
LLM_MODEL = "anthropic/claude-sonnet-5.5"  # bulk tier, effort low via llm_client.default_effort
LLM_PRICE_IN, LLM_PRICE_OUT = 2.0 / 1e6, 10.0 / 1e6  # OpenRouter list price, USD per token (2026-11-02)
ACCEPT_STATUSES = ("verified",)  # strictest deliverable LeadOcean status; see directive
# LeadOcean statuses that may be rescued when Reoon (power mode) independently rated the address safe.
RESCUE_STATUSES = ("untested", "catch_all")
REOON_CACHE = ROOT / ".tmp" / "reoon" / "cache.jsonl"

# Wave 2 (2026-11-02): national US + UK, LeadOcean verified/untested/catch_all, every address re-checked by
# Reoon, wave-1 people excluded. `--wave 2` moves every cache/output under .tmp/leadocean/wave2/.
WAVE = 1
W1_TMP = ROOT / ".tmp" / "leadocean"
W1_LEADS = W1_TMP / "prodcraft_leads_reoon.csv"
W2_STATUSES = ("verified", "untested", "catch_all")
# Exported in wave 2: LeadOcean `catch_all` never came back Reoon-safe in the 2026-11-02 test (6/6 catch_all,
# 1 unknown), so export rows go to verified + untested only; hygiene still accepts catch_all if one appears.
W2_SEARCH_STATUSES = ("verified", "untested")
STATUSES: tuple[str, ...] = ACCEPT_STATUSES  # LeadOcean statuses accepted by hygiene this wave
SEARCH_STATUSES: tuple[str, ...] = ACCEPT_STATUSES  # statuses asked for in counts/exports this wave
VIEWED_SET = "prodcraft_w1"  # LeadOcean viewed list holding every wave-1 person_id (excludeViewed on wave-2 calls)
W2_METROS = {"us_all": 1, "uk_all": 1}
# Company-first universes (industries where wave-1 Jev-kept leads actually came from; free counts 2026-11-02:
# AV 3,611 US / 1,400 UK, fit-out 6,219 / 1,178, DMC 1,920 / 682 companies).
W2_INDUSTRY = {
    "av": ["Events Services", "Media Production", "Broadcast Media Production and Distribution",
           "Entertainment Providers", "Audio and Video Equipment Manufacturing"],
    "fitout": ["Construction", "Building Construction", "Nonresidential Building Construction",
               "Building Finishing Contractors", "Specialty Trade Contractors"],
    "dmc": ["Events Services", "Travel Arrangements", "Hospitality", "Leisure; Travel and Tourism"],
}


def set_wave(n: int) -> None:
    """Point every cache/output path at the wave's own folder (wave 1 = legacy .tmp/leadocean/)."""
    global WAVE, TMP, RAW, SITES, STATUSES, SEARCH_STATUSES
    WAVE = n
    if n == 2:
        TMP = W1_TMP / "wave2"
        STATUSES, SEARCH_STATUSES = W2_STATUSES, W2_SEARCH_STATUSES
    else:
        TMP = W1_TMP
        STATUSES = SEARCH_STATUSES = ACCEPT_STATUSES
    RAW, SITES = TMP / "raw", TMP / "sites"


def load_reoon_safe() -> set[str]:
    """Emails Reoon rated safe with score >= 90 (written by reoon_verify.py)."""
    safe: set[str] = set()
    if not REOON_CACHE.exists():
        return safe
    for line in REOON_CACHE.read_text(encoding="utf-8").splitlines():
        try:
            d = json.loads(line)
        except json.JSONDecodeError:
            log.warning("skipping bad reoon cache line")
            continue
        if d.get("status") == "safe" and isinstance(d.get("score"), int) and d["score"] >= 90 and not d.get("role"):
            safe.add(d["email"].lower())
    return safe
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()

# --------------------------------------------------------------------------------------
# Targeting config (operator playbook). Metros: hqCity keywords AND hqState (AND hqCountry).
# --------------------------------------------------------------------------------------
M: dict[str, dict[str, Any]] = {
    "las_vegas": {"label": "Las Vegas", "hqCity": ["Las Vegas", "Henderson"], "hqState": ["NV"]},
    "orlando": {"label": "Orlando", "hqCity": ["Orlando", "Kissimmee", "Winter Park", "Lake Mary", "Sanford",
                                                "Altamonte Springs", "Maitland", "Winter Garden", "Apopka"],
                "hqState": ["FL"]},
    "chicago": {"label": "Chicago", "hqCity": ["Chicago", "Evanston", "Schaumburg", "Oak Brook", "Naperville",
                                                "Elk Grove Village", "Itasca", "Des Plaines", "Rosemont", "Northbrook",
                                                "Skokie", "Lombard", "Wheeling", "Addison", "Elmhurst",
                                                "Arlington Heights", "Downers Grove", "Wood Dale", "Bensenville",
                                                "Oakbrook Terrace", "Lisle", "Glenview", "Lincolnshire"],
                "hqState": ["IL"]},
    "nashville": {"label": "Nashville", "hqCity": ["Nashville", "Franklin", "Brentwood", "Hendersonville",
                                                    "Mount Juliet", "Murfreesboro", "Antioch"], "hqState": ["TN"]},
    "dallas": {"label": "Dallas-Fort Worth", "hqCity": ["Dallas", "Fort Worth", "Irving", "Plano", "Addison",
                                                         "Carrollton", "Richardson", "Grapevine", "Arlington",
                                                         "Frisco", "Garland", "Coppell", "Lewisville", "Farmers Branch",
                                                         "Grand Prairie", "Southlake", "Allen", "McKinney", "Mesquite"],
               "hqState": ["TX"]},
    "atlanta": {"label": "Atlanta", "hqCity": ["Atlanta", "Marietta", "Alpharetta", "Norcross", "Duluth", "Roswell",
                                                "Smyrna", "Kennesaw", "Peachtree Corners", "Decatur", "Doraville",
                                                "Tucker", "Sandy Springs", "Lawrenceville", "Suwanee", "Buford"],
                "hqState": ["GA"]},
    "new_york": {"label": "New York", "hqCity": ["New York", "Brooklyn", "Long Island City", "Queens", "Bronx",
                                                  "Jersey City", "Hoboken", "Secaucus", "Carlstadt", "Moonachie",
                                                  "Newark", "Yonkers", "White Plains", "Mount Vernon", "Astoria",
                                                  "Maspeth", "Hackensack", "Englewood", "East Rutherford", "Kearny"],
                 "hqState": ["NY", "NJ"]},
    "washington_dc": {"label": "Washington DC", "hqCity": ["Washington", "Arlington", "Alexandria", "Bethesda",
                                                            "Rockville", "Silver Spring", "Gaithersburg", "Fairfax",
                                                            "Reston", "Herndon", "Chantilly", "Falls Church", "Vienna",
                                                            "McLean", "Springfield", "Lanham", "Beltsville",
                                                            "Landover", "Upper Marlboro", "Sterling", "Manassas",
                                                            "Hyattsville", "Capitol Heights", "Lorton", "Columbia"],
                      "hqState": ["DC", "VA", "MD"]},
    "boston": {"label": "Boston", "hqCity": ["Boston", "Cambridge", "Somerville", "Waltham", "Woburn", "Canton",
                                              "Quincy", "Needham", "Newton", "Braintree", "Burlington", "Norwood",
                                              "Medford", "Everett", "Wilmington", "Marlborough", "Framingham",
                                              "Dedham", "Natick", "Wakefield", "Peabody", "Stoughton", "Avon"],
               "hqState": ["MA"]},
    "sf_bay": {"label": "San Francisco Bay Area", "hqCity": ["San Francisco", "Oakland", "San Jose", "Emeryville",
                                                              "Hayward", "San Leandro", "South San Francisco",
                                                              "Burlingame", "San Mateo", "Redwood City", "Palo Alto",
                                                              "Santa Clara", "Sunnyvale", "Fremont", "Walnut Creek",
                                                              "Pleasanton", "Concord", "Milpitas", "San Carlos",
                                                              "Brisbane", "Berkeley", "Dublin", "San Ramon", "Union City"],
               "hqState": ["CA"]},
    "los_angeles": {"label": "Los Angeles", "hqCity": ["Los Angeles", "Culver City", "Santa Monica", "Burbank",
                                                        "Glendale", "Pasadena", "Irvine", "Long Beach", "Torrance",
                                                        "El Segundo", "Gardena", "Commerce", "City of Industry",
                                                        "Santa Ana", "Anaheim", "Costa Mesa", "Van Nuys",
                                                        "North Hollywood", "Sun Valley", "Chatsworth", "Valencia",
                                                        "Carson", "Compton", "Orange", "Tustin", "Newport Beach"],
                    "hqState": ["CA"]},
    "houston": {"label": "Houston", "hqCity": ["Houston", "Sugar Land", "The Woodlands", "Katy", "Pasadena",
                                                "Stafford", "Spring", "Pearland", "Missouri City", "Humble",
                                                "Cypress", "Tomball", "Bellaire", "Conroe"], "hqState": ["TX"]},
    "austin": {"label": "Austin", "hqCity": ["Austin", "Round Rock", "Cedar Park", "Pflugerville", "Georgetown",
                                              "Leander", "Buda", "Dripping Springs"], "hqState": ["TX"]},
    "phoenix": {"label": "Scottsdale/Phoenix", "hqCity": ["Scottsdale", "Phoenix", "Tempe", "Mesa", "Chandler",
                                                           "Gilbert", "Paradise Valley", "Glendale", "Peoria"],
                "hqState": ["AZ"]},
    "miami": {"label": "Miami", "hqCity": ["Miami", "Miami Beach", "Coral Gables", "Doral", "Fort Lauderdale",
                                            "Aventura", "Boca Raton", "Hollywood", "Key Biscayne", "Hialeah",
                                            "West Palm Beach", "Pompano Beach"], "hqState": ["FL"]},
    "san_diego": {"label": "San Diego", "hqCity": ["San Diego", "Carlsbad", "La Jolla", "Del Mar", "Oceanside",
                                                    "Escondido", "Coronado", "Chula Vista", "Encinitas", "Poway"],
                  "hqState": ["CA"]},
    "new_orleans": {"label": "New Orleans", "hqCity": ["New Orleans", "Metairie", "Kenner", "Harahan", "Gretna"],
                    "hqState": ["LA"]},
    "hawaii": {"label": "Hawaii", "hqState": ["HI"]},
    "napa": {"label": "Napa/Sonoma", "hqCity": ["Napa", "Sonoma", "Santa Rosa", "St. Helena", "Saint Helena",
                                                 "Healdsburg", "Yountville", "Calistoga", "Petaluma"],
             "hqState": ["CA"]},
    "minneapolis": {"label": "Minneapolis", "hqCity": ["Minneapolis", "St. Paul", "Saint Paul", "Bloomington",
                                                        "Eden Prairie", "Edina", "Minnetonka", "Plymouth",
                                                        "Golden Valley", "Wayzata", "Eagan", "Maple Grove"],
                    "hqState": ["MN"]},
    "st_louis": {"label": "St. Louis", "hqCity": ["St. Louis", "Saint Louis", "Clayton", "Chesterfield",
                                                   "Maryland Heights", "Creve Coeur", "Kirkwood", "St. Charles"],
                 "hqState": ["MO"]},
    "london": {"label": "London", "hqCity": ["London"], "hqCountry": ["GB"]},
    "london_edinburgh": {"label": "London/Edinburgh", "hqCity": ["London", "Edinburgh"], "hqCountry": ["GB"]},
    "us_other": {"label": "US (other)", "hqCountry": ["US"]},
    "us_all": {"label": "US (other)", "hqCountry": ["US"]},
    "uk_all": {"label": "UK (other)", "hqCountry": ["GB"]},
}

FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.uk", "ymail.com", "hotmail.com", "hotmail.co.uk",
    "outlook.com", "live.com", "msn.com", "aol.com", "icloud.com", "me.com", "mac.com", "comcast.net",
    "verizon.net", "att.net", "sbcglobal.net", "bellsouth.net", "cox.net", "charter.net", "earthlink.net",
    "protonmail.com", "proton.me", "gmx.com", "gmx.net", "mail.com", "zoho.com", "btinternet.com",
    "sky.com", "virginmedia.com", "talktalk.net", "ntlworld.com", "blueyonder.co.uk", "yandex.com",
    "optonline.net", "roadrunner.com", "rocketmail.com", "inbox.com", "fastmail.com", "hey.com",
}
ROLE_LOCALS = {
    "info", "sales", "office", "hello", "admin", "contact", "contactus", "support", "team", "events", "event",
    "bookings", "booking", "enquiries", "enquiry", "inquiries", "inquiry", "marketing", "hr", "jobs", "careers",
    "accounts", "accounting", "billing", "service", "services", "help", "mail", "general", "reception",
    "estimating", "bids", "bid", "projects", "operations", "ops", "media", "press", "pr", "noreply", "no-reply",
    "webmaster", "postmaster", "studio", "production", "productions", "travel", "reservations", "rsvp", "dmc",
    "design", "newbusiness", "new.business", "biz", "business", "welcome", "orders", "quotes", "quote", "rfp",
    "proposals", "hi", "ask", "talk", "connect", "letstalk",
}

COMMON_EXCL_TITLE = ["Assistant", "Intern", "Coordinator", "Product Owner", "Student", "Volunteer",
                     "Board Member", "Advisor", "Board of Directors", "Retired", "Former", "Freelance",
                     "Art Director", "Creative Director", "Technical Director", "Director of Photography",
                     "Music Director", "Musical Director", "Account Director", "HR Director", "Human Resources",
                     "Finance Director", "Director of Finance", "IT Director", "Talent", "Recruit"]
# Industries that keyword matches drag in but never buy custom event/build/program work (from free facets).
NOISE_INDUSTRIES = [
    "Food and Beverage Services", "Education Administration Programs", "Primary and Secondary Education", "Education",
    "Higher Education", "Professional Training and Coaching", "Non-profit Organizations", "Consumer Services",
    "Spectator Sports", "Museums; Historical Sites; and Zoos", "Wellness and Fitness Services", "Software Development",
    "Accounting", "Executive Search Services", "Religious Institutions", "Musicians", "Retail", "Restaurants",
    "Hospitals and Health Care", "Financial Services", "Investment Management", "Consumer Goods",
    "Book and Periodical Publishing", "Staffing and Recruiting", "IT Services and IT Consulting",
    "Technology; Information and Internet", "Artists and Writers", "Government Administration", "Insurance",
    "Law Practice", "Retail Apparel and Fashion", "Food and Beverage Manufacturing", "Beverage Manufacturing",
]
# Decision-maker bands. The playbook title lists below are used to rank contacts within a company
# (owner/C-level first); as an export filter they shrank the verified pool ~2x, so seniority is the filter.
SENIORITY = ["owner", "founder", "c_suite", "partner", "vp", "director"]

NICHES: dict[str, dict[str, Any]] = {
    "av": {
        "label": "Event production / AV",
        "target": 1350,
        "companyKeywords": ["event production", "audio visual production", "AV production", "corporate events",
                            "LED wall", "staging", "general session", "experiential"],
        "excludeIndustry": NOISE_INDUSTRIES + ["Hospitality", "Leisure; Travel and Tourism", "Architecture and Planning"],
        "excludeKeywords": ["wedding", "DJ", "party rental", "church", "worship", "concert touring", "tour manager"],
        "excludeCompanyName": ["wedding", "DJ", "party rental", "church", "bridal"],
        "title": ["Owner", "Founder", "CEO", "Chief Executive", "President", "VP Sales", "Vice President of Sales",
                  "Vice President, Sales", "Director of Business Development", "Business Development Director",
                  "Executive Producer", "Managing Partner", "Managing Director", "Partner", "Principal"],
        "excludeTitle": COMMON_EXCL_TITLE,
        "minEmployees": 11, "maxEmployees": 200,
        "metros": {"las_vegas": 1, "orlando": 1, "chicago": 1, "nashville": 1, "dallas": 1, "atlanta": 1,
                   "new_york": 1, "washington_dc": 1, "london": 0.10},
    },
    "fitout": {
        "label": "Commercial interior fit-out",
        "target": 1050,
        # Bare "fit out"/"fit-out" matched fitness and apparel brands; phrases below are construction-specific.
        "companyKeywords": ["interior construction", "tenant improvement", "tenant improvements",
                            "commercial interiors", "interior fit-out", "fit-out contractor", "office build-out",
                            "design-build interiors", "hospitality fit-out", "interior contractor",
                            "commercial construction", "office fit-out", "office interiors", "interior build-out",
                            "workplace interiors"],
        "industry": ["Construction", "Building Construction", "Nonresidential Building Construction",
                     "Building Finishing Contractors", "Building Equipment Contractors", "Specialty Trade Contractors",
                     "Architecture and Planning", "Design Services", "Commercial Real Estate"],
        "excludeKeywords": ["residential remodel", "roofing", "restoration", "home builder", "homebuilder"],
        "excludeCompanyName": ["Roofing", "Restoration", "Remodel", "Homes", "Home Builder", "STO Building Group",
                               "Structure Tone", "J.T. Magen", "JT Magen", "HITT", "Clune", "JRM", "Rand Construction",
                               "Swinerton", "Skyline Construction", "Gilbane", "Turner Construction"],
        "title": ["Owner", "President", "CEO", "Chief Executive", "Principal", "Founder",
                  "VP Preconstruction", "Vice President of Preconstruction", "Vice President, Preconstruction",
                  "Director of Estimating", "Chief Estimator", "Estimating Director", "VP Operations",
                  "Vice President of Operations", "Vice President, Operations", "Managing Director", "Partner"],
        "excludeTitle": COMMON_EXCL_TITLE,
        "minEmployees": 11, "maxEmployees": 200,
        "metros": {"new_york": 1, "chicago": 1, "washington_dc": 1, "dallas": 1, "boston": 1, "atlanta": 1,
                   "sf_bay": 1, "los_angeles": 1, "houston": 1, "austin": 1, "london": 0.15},
    },
    "dmc": {
        "label": "Incentive travel / DMC",
        "target": 600,
        "companyKeywords": ["destination management", "DMC", "incentive travel", "incentive programs",
                            "corporate travel programs", "meetings and incentives", "group travel"],
        "excludeIndustry": NOISE_INDUSTRIES + ["Airlines and Aviation", "Construction", "Real Estate",
                                               "Transportation; Logistics; Supply Chain and Storage"],
        "excludeKeywords": ["honeymoon", "cruise", "travel advisor", "host agency", "leisure travel"],
        "excludeCompanyName": ["Cruise", "Honeymoon", "Vacations", "Travel Advisor"],
        "title": ["Owner", "Managing Director", "President", "CEO", "Founder", "VP Sales", "Vice President of Sales",
                  "Vice President, Sales", "Director of Program Development", "Director of Operations",
                  "Partner", "General Manager", "Principal"],
        "excludeTitle": COMMON_EXCL_TITLE,
        "minEmployees": 5, "maxEmployees": 200,
        # Playbook metros held ~310 verified decision-makers at ~117 companies (2026-11-02 count), too thin
        # for 600, so DMC is exported US-wide and labelled back to a playbook metro by the contact's city.
        "metros": {"us_other": 1, "london_edinburgh": 1},
        "label_metros": ["orlando", "las_vegas", "nashville", "phoenix", "miami", "san_diego", "new_orleans",
                         "hawaii", "napa", "chicago", "dallas", "minneapolis", "st_louis"],
    },
}

EXPORT_COLUMNS = [
    "person_id", "profile_url", "profile_full_name", "profile_first_name", "profile_last_name", "profile_headline",
    "profile_summary", "profile_is_decision_maker", "city", "state", "country_code", "has_email", "email_status",
    "email_type", "email_N_address", "email_N_type", "email_N_status", "email_N_verified_date",
    "current_company_name", "current_company_domain", "current_company_industry", "current_company_id",
    "current_company_linkedin_url", "current_company_website", "current_company_employees",
    "current_company_employees_range", "current_job_title", "current_job_level", "contact_still_at_company_status",
]


# --------------------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------------------
def jload(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return default
    except json.JSONDecodeError as exc:
        log.warning("corrupt cache %s (%s); starting empty", path, exc)
        return default


_save_lock = threading.Lock()


def jsave(path: Path, data: Any) -> None:
    with _save_lock:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".part")
        tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)


def norm_domain(value: str | None) -> str:
    if not value:
        return ""
    v = value.strip().lower()
    if "://" not in v:
        v = "http://" + v
    host = urlparse(v).hostname or ""
    return host.removeprefix("www.")


def base_label(domain: str) -> str:
    parts = domain.split(".")
    if len(parts) >= 3 and parts[-2] in {"co", "com", "org", "net", "ac", "gov"} and len(parts[-1]) == 2:
        return parts[-3]
    return parts[-2] if len(parts) >= 2 else domain


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (text or "").lower())


# --------------------------------------------------------------------------------------
# LeadOcean client (5 rps / 300 rpm; 429 -> Retry-After). Key never printed.
# --------------------------------------------------------------------------------------
class LeadOcean:
    def __init__(self) -> None:
        key = os.environ.get("LEADOCEAN_API_KEY", "")
        if not key:
            raise SystemExit("LEADOCEAN_API_KEY missing from env/.env")
        self.s = requests.Session()
        self.s.headers.update({"x-api-key": key, "accept": "application/json"})
        self._lock = threading.Lock()
        self._last = 0.0

    def _pace(self) -> None:
        with self._lock:
            wait = self._last + 0.25 - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()

    def req(self, method: str, path: str, *, params: dict | None = None, body: dict | None = None,
            timeout: float = 60, raw: bool = False) -> Any:
        for attempt in range(6):
            self._pace()
            try:
                r = self.s.request(method, API + path, params=params, json=body, timeout=timeout)
            except requests.RequestException as exc:
                log.warning("LeadOcean %s %s network error %s (attempt %d)", method, path,
                            exc.__class__.__name__, attempt + 1)
                time.sleep(2 ** attempt)
                continue
            if r.status_code == 429:
                try:
                    ra = float(r.headers.get("Retry-After") or 5)
                except ValueError:
                    ra = 5.0
                log.warning("429 on %s; sleeping %.0fs", path, min(ra, 120))
                time.sleep(min(ra, 120))
                continue
            if r.status_code >= 500:
                time.sleep(2 ** attempt)
                continue
            if raw:
                return r
            try:
                data = r.json()
            except ValueError:
                raise RuntimeError(f"LeadOcean {path}: HTTP {r.status_code} non-JSON") from None
            if r.status_code >= 400:
                raise RuntimeError(f"LeadOcean {path}: HTTP {r.status_code} {json.dumps(data)[:400]}")
            return data
        raise RuntimeError(f"LeadOcean {path}: gave up after retries")

    def count(self, filters: dict[str, Any]) -> dict[str, Any]:
        """Free sizing call: people search with count=true&limit=1."""
        params = {k: (",".join(v) if isinstance(v, list) else v) for k, v in filters.items()}
        params.update(count="true", limit=1)
        meta = self.req("GET", "/v1/people/search", params=params).get("meta", {})
        return {"total": meta.get("total"), "companies": meta.get("distinctCompanies"),
                "unsupported": meta.get("unsupportedFilters") or []}


def filters_for(niche: str, metro: str, *, email: bool = True, status: tuple[str, ...] | None = None,
                titles: bool = True) -> dict[str, Any]:
    n, m = NICHES[niche], M[metro]
    status = status or SEARCH_STATUSES
    f: dict[str, Any] = {"companyKeywords": n["companyKeywords"], "minEmployees": n["minEmployees"],
                         "maxEmployees": n["maxEmployees"]}
    for k in ("hqCity", "hqState", "hqCountry"):
        if m.get(k):
            f[k] = m[k]
    if "hqCountry" not in f:
        f["hqCountry"] = ["US"]
    for k in ("industry", "excludeIndustry", "excludeKeywords", "excludeCompanyName"):
        if n.get(k):
            f[k] = n[k]
    if titles:
        f["seniority"], f["excludeTitle"] = SENIORITY, n["excludeTitle"]
    if email:
        f["emailStatus"], f["emailType"] = list(status), ["work"]
    if WAVE == 2:
        f["excludeViewed"], f["viewedSet"] = "true", VIEWED_SET
    return f


# --------------------------------------------------------------------------------------
# 1. count
# --------------------------------------------------------------------------------------
def cmd_count(args: argparse.Namespace) -> None:
    lo = LeadOcean()
    path = TMP / "counts.json"
    counts = {} if args.refresh else jload(path, {})
    for niche, n in NICHES.items():
        for metro in n["metros"]:
            key = f"{niche}:{metro}"
            if key in counts and not counts[key].get("error"):
                continue
            try:
                row = {
                    "all_titles": lo.count(filters_for(niche, metro, email=False)),
                    "verified_work": lo.count(filters_for(niche, metro)),
                    "ccv_work": lo.count(filters_for(niche, metro, status=("catch_all_valid",))),
                    "verified_work_any_title": lo.count(filters_for(niche, metro, titles=False)),
                }
            except RuntimeError as exc:
                row = {"error": str(exc)[:300]}
            counts[key] = row
            jsave(path, counts)
            vw = row.get("verified_work", {})
            print(f"{key:28s} all={row.get('all_titles', {}).get('total')} verified_work={vw.get('total')} "
                  f"cos={vw.get('companies')} ccv={row.get('ccv_work', {}).get('total')} "
                  f"anytitle={row.get('verified_work_any_title', {}).get('total')} "
                  f"unsupported={vw.get('unsupported')}")
    print(f"wrote {path}")


# --------------------------------------------------------------------------------------
# 2. export
# --------------------------------------------------------------------------------------
def build_plan(counts: dict[str, Any], budget: int) -> list[dict[str, Any]]:
    """Rows per niche x metro. The verified pool is small, so each cell is exported whole (limit = total);
    share-capped cells (London, weight < 1) get weight x target x 1.1 rows. Scaled down if over budget."""
    plan = []
    for niche, n in NICHES.items():
        for metro, weight in n["metros"].items():
            c = counts.get(f"{niche}:{metro}", {}).get("verified_work") or {}
            if c.get("unsupported") or not c.get("total"):
                continue
            total, cos = int(c["total"]), int(c.get("companies") or 0)
            want = total if weight >= 1 else min(total, int(weight * n["target"] * 1.1))
            plan.append({"niche": niche, "metro": metro, "total": total, "companies": cos, "want": want})
    need_rows = sum(c["want"] for c in plan)
    scale = min(1.0, budget / need_rows) if need_rows else 1.0
    for c in plan:
        c["limit"] = max(1, int(c["want"] * scale))
    return plan


def cmd_export(args: argparse.Namespace) -> None:
    counts = jload(TMP / "counts.json", {})
    if not counts:
        raise SystemExit("run `count` first")
    plan_path = TMP / "export_plan.json"
    if args.replan or not plan_path.exists():
        plan = build_plan(counts, args.budget)
        jsave(plan_path, plan)
    plan = jload(plan_path, [])
    by_niche: dict[str, int] = defaultdict(int)
    for c in plan:
        by_niche[c["niche"]] += c["limit"]
    print(f"plan: {sum(c['limit'] for c in plan)} rows over {len(plan)} cells; by niche {dict(by_niche)}")
    for c in plan:
        print(f"  {c['niche']}:{c['metro']:18s} total={c['total']:5d} cos={c['companies']:4d} limit={c['limit']}")
    if args.plan_only:
        return
    lo = LeadOcean()
    RAW.mkdir(parents=True, exist_ok=True)
    state_path = TMP / "exports.json"
    state = jload(state_path, {})
    spent = sum(int(s.get("requested", 0)) for s in state.values())
    for c in plan:
        key = f"{c['niche']}:{c['metro']}"
        if args.only and key not in args.only.split(","):
            continue
        if key in state:
            continue
        limit = c["limit"] if not args.sample else min(args.sample, c["limit"])
        if spent + limit > args.budget:
            print(f"skip {key}: budget {args.budget} would be exceeded (spent {spent})")
            continue
        body = {"name": f"prodcraft {key} {TODAY}", "filters": export_body_filters(filters_for(c["niche"], c["metro"])),
                "limit": limit, "columns": EXPORT_COLUMNS, "caps": {"emails": 3}}
        try:
            data = lo.req("POST", "/v1/exports", body=body)["data"]
        except RuntimeError as exc:
            print(f"export {key} refused: {exc}")
            continue
        state[key] = {"id": data["id"], "requested": limit, "status": data.get("status"),
                      "niche": c["niche"], "metro": c["metro"]}
        spent += limit
        jsave(state_path, state)
        print(f"queued {key} id={data['id']} limit={limit} remaining={data.get('remaining')}")
    poll_and_download(lo, state, state_path)


def poll_and_download(lo: LeadOcean, state: dict[str, Any], state_path: Path) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    pending = [k for k, s in state.items() if s.get("status") not in ("downloaded", "failed", "cancelled")]
    while pending:
        for key in list(pending):
            s = state[key]
            try:
                d = lo.req("GET", f"/v1/exports/{s['id']}")["data"]
            except RuntimeError as exc:
                log.warning("poll %s: %s", key, exc)
                continue
            s.update(status=d.get("status"), rows=d.get("rows"), billed=d.get("billed"),
                     released=d.get("released"), error=d.get("error"))
            if d.get("status") == "done":
                r = lo.req("GET", f"/v1/exports/{s['id']}/download", raw=True, timeout=180)
                if r.status_code == 200 and r.text:
                    out = RAW / f"{key.replace(':', '__')}.csv"
                    out.write_text(r.text, encoding="utf-8")
                    s.update(status="downloaded", file=str(out.relative_to(ROOT)))
                    print(f"downloaded {key}: {d.get('rows')} rows (billed {d.get('billed')})")
                else:
                    log.warning("download %s HTTP %s", key, r.status_code)
                    continue
            if s["status"] in ("downloaded", "failed", "cancelled"):
                pending.remove(key)
                if s["status"] != "downloaded":
                    print(f"export {key} ended {s['status']}: {s.get('error')}")
            jsave(state_path, state)
        if pending:
            time.sleep(10)


# --------------------------------------------------------------------------------------
# 3. hygiene (deterministic) -> 4. gate (Jev ICP check)
# --------------------------------------------------------------------------------------
_mx_cache: dict[str, bool | None] = {}
_mx_lock = threading.Lock()


def has_mx(domain: str) -> bool | None:
    """MX via DNS-over-HTTPS (Google, then Cloudflare). True/False, None when undeterminable.
    DoH, not dnspython: the cloud sandbox resolver answers NoAnswer for real MX records."""
    with _mx_lock:
        if domain in _mx_cache:
            return _mx_cache[domain]
    result: bool | None = None
    for url, hdr in (("https://dns.google/resolve", {}),
                     ("https://cloudflare-dns.com/dns-query", {"accept": "application/dns-json"})):
        try:
            r = requests.get(url, params={"name": domain, "type": "MX"}, headers=hdr, timeout=8)
            j = r.json()
        except (requests.RequestException, ValueError) as exc:
            log.warning("DoH %s for %s failed: %s", url, domain, exc.__class__.__name__)
            continue
        if j.get("Status") == 3:  # NXDOMAIN
            result = False
            break
        if j.get("Status") == 0:
            answers = [a for a in j.get("Answer") or [] if a.get("type") == 15]
            # Null MX ("0 .") means the domain explicitly accepts no mail.
            result = any(a.get("data", "").strip() not in ("0 .", "0 ") for a in answers)
            break
    with _mx_lock:
        _mx_cache[domain] = result
    return result


TITLE_RANK = [
    ((r"\b(owner|founder|co-founder|cofounder|ceo|chief executive|president|managing partner|principal"
      r"|managing director)\b"), 0),
    (r"\b(chief|coo|cfo|cro|cmo|partner|general manager)\b", 1),
    (r"\b(vp|vice president|svp|evp|executive producer|chief estimator)\b", 2),
    (r"\b(director|head)\b", 3),
]


def title_rank(title: str) -> int:
    t = (title or "").lower()
    if re.search(r"\bvice president\b|\bvp\b", t):
        return 2
    for pat, rank in TITLE_RANK:
        if re.search(pat, t):
            return rank
    return 4


def load_raw_rows() -> list[dict[str, Any]]:
    state = jload(TMP / "exports.json", {})
    rows = []
    for s in state.values():
        if s.get("status") != "downloaded":
            continue
        with open(ROOT / s["file"], newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_niche"], r["_metro"] = s["niche"], s["metro"]
                rows.append(r)
    return rows


def pick_email(r: dict[str, Any]) -> tuple[str, str, str, str]:
    """Primary email = first numbered email of type work; returns (address, status, verified_date, type)."""
    best = None
    for i in range(1, 4):
        addr = (r.get(f"email_{i}_address") or "").strip().lower()
        if not addr:
            continue
        cand = (addr, (r.get(f"email_{i}_status") or "").strip().lower(),
                (r.get(f"email_{i}_verified_date") or "").strip(), (r.get(f"email_{i}_type") or "").strip().lower())
        if best is None:
            best = cand
        if cand[3] == "work":
            return cand
    return best or ("", "", "", "")


def is_role(local: str) -> bool:
    toks = [t for t in re.split(r"[._+-]", local) if t]
    if local in ROLE_LOCALS or re.sub(r"\d+$", "", local) in ROLE_LOCALS or not toks:
        return True
    return toks[0] in ROLE_LOCALS and all(t in ROLE_LOCALS or t.isdigit() or len(t) <= 3 for t in toks[1:])


STATE_CODES = {"nevada": "NV", "florida": "FL", "tennessee": "TN", "arizona": "AZ", "california": "CA",
               "louisiana": "LA", "hawaii": "HI", "illinois": "IL", "texas": "TX", "minnesota": "MN",
               "missouri": "MO", "new york": "NY", "new jersey": "NJ", "district of columbia": "DC",
               "virginia": "VA", "maryland": "MD", "massachusetts": "MA", "georgia": "GA"}


def label_metro(r: dict[str, Any]) -> str:
    """US-wide DMC rows (and every wave-2 national row): map the contact's city/state onto a playbook metro."""
    niche = NICHES[r["_niche"]]
    city = (r.get("city") or "").lower()
    if r["_metro"] == "uk_all":
        return "london" if city == "london" else "uk_all"
    if r["_metro"] == "us_all":
        cands = [m for m, d in M.items() if "hqState" in d]
    elif r["_metro"] != "us_other" or not niche.get("label_metros"):
        return r["_metro"]
    else:
        cands = niche["label_metros"]
    st = (r.get("state") or "").strip()
    st = STATE_CODES.get(st.lower(), st.upper())
    for m in cands:
        d = M[m]
        if st not in d.get("hqState", []):
            continue
        if not d.get("hqCity") or any(c.lower() == city for c in d["hqCity"]):
            return m
    return "us_all" if r["_metro"] == "us_all" else "us_other"


def wave1_exclusions() -> dict[str, Any]:
    """Wave-1 people/emails (never re-contact) and per-company sending counts (2-per-company cap spans waves)."""
    emails: set[str] = set()
    people: set[str] = set()
    per_domain: Counter = Counter()
    if W1_LEADS.exists():
        with open(W1_LEADS, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                emails.add((r.get("email") or "").strip().lower())
                if r.get("linkedin_url"):
                    people.add(r["linkedin_url"].strip().lower().rstrip("/"))
                people.add(f"{slug(r.get('first_name'))}|{slug(r.get('last_name'))}|{r.get('company_domain', '')}")
                if r.get("send_bucket") in ("main", "catchall"):
                    per_domain[r.get("company_domain", "")] += 1
    ids: set[str] = set()
    for f in sorted((W1_TMP / "raw").glob("*.csv")):
        with open(f, newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if r.get("person_id"):
                    ids.add(r["person_id"])
                if r.get("profile_url"):
                    people.add(r["profile_url"].strip().lower().rstrip("/"))
    return {"emails": emails - {""}, "people": people, "person_ids": ids, "per_domain": per_domain}


def person_keys(r: dict[str, Any]) -> set[str]:
    keys = {f"{slug(r.get('profile_first_name'))}|{slug(r.get('profile_last_name'))}|{r.get('_company_domain', '')}"}
    if r.get("profile_url"):
        keys.add(r["profile_url"].strip().lower().rstrip("/"))
    if r.get("person_id"):
        keys.add(r["person_id"])
    return keys


def hygiene(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    keep, rejects = [], []

    def reject(r: dict[str, Any], reason: str) -> None:
        r["reject_reason"] = reason
        rejects.append(r)

    seen_email, seen_person = set(), set()
    reoon_safe = load_reoon_safe()
    w1 = wave1_exclusions() if WAVE == 2 else None
    staged = []
    for r in rows:
        r["_metro"] = label_metro(r)
        email, status, vdate, _etype = pick_email(r)
        r.update(_email=email, _email_status=status, _email_verified_date=vdate)
        comp_domain = norm_domain(r.get("current_company_domain")) or norm_domain(r.get("current_company_website"))
        r["_company_domain"] = comp_domain
        pid = r.get("person_id") or r.get("profile_url") or email
        if not email or "@" not in email:
            reject(r, "no_email")
            continue
        if status not in STATUSES and not (status in RESCUE_STATUSES and email.lower() in reoon_safe):
            reject(r, f"status_{status or 'blank'}")
            continue
        local, edom = email.split("@", 1)
        if edom in FREE_MAIL:
            reject(r, "free_mail")
            continue
        if is_role(local):
            reject(r, "role_address")
            continue
        if comp_domain:
            ok = (edom == comp_domain or edom.endswith("." + comp_domain) or comp_domain.endswith("." + edom)
                  or base_label(edom) == base_label(comp_domain))
        else:
            ok = len(base_label(edom)) >= 4 and base_label(edom) in slug(r.get("current_company_name", ""))
            if ok:
                r["_company_domain"] = edom
        if not ok:
            reject(r, "domain_mismatch")
            continue
        if email in seen_email or pid in seen_person:
            reject(r, "duplicate")
            continue
        if w1 and (email in w1["emails"] or person_keys(r) & (w1["people"] | w1["person_ids"])):
            seen_email.add(email)
            seen_person.add(pid)
            reject(r, "wave1_duplicate")
            continue
        seen_email.add(email)
        seen_person.add(pid)
        staged.append(r)
    # MX check, one lookup per domain, in parallel
    domains = sorted({r["_email"].split("@", 1)[1] for r in staged})
    with ThreadPoolExecutor(max_workers=16) as pool:
        mx = dict(zip(domains, pool.map(has_mx, domains)))
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in staged:
        edom = r["_email"].split("@", 1)[1]
        if mx.get(edom) is False:
            reject(r, "no_mx")
            continue
        if mx.get(edom) is None:
            reject(r, "mx_unresolved")
            continue
        by_company[r["_company_domain"]].append(r)
    for dom, people in by_company.items():
        people.sort(key=lambda p: (title_rank(p.get("current_job_title", "")),
                                   0 if (p.get("profile_is_decision_maker") or "").lower() == "true" else 1))
        # Wave 2 keeps one reserve per company: Reoon runs after this, and the final 2-per-company cap
        # (counting wave-1 senders) is applied in w2_select once the Reoon buckets are known.
        slots = 2
        if w1:
            left = max(0, 2 - w1["per_domain"][dom])
            slots = left + 1 if left else 0
        for i, p in enumerate(people):
            (keep if i < slots else rejects).append(p)
            if i >= slots:
                p["reject_reason"] = "company_cap_2"
    return keep, rejects


NICHE_Q = {
    "niche": {"type": "choice", "instructions": "Which line of business is this company in?",
              "options": {
                  "av": "corporate event production / audio-visual production / staging, LED, live experiential "
                        "events for brands and conferences",
                  "fitout": "commercial interior construction / tenant improvement / office or hospitality "
                            "fit-out general contractor",
                  "dmc": "destination management company, incentive travel or corporate meetings & incentives "
                         "program planner",
                  "none": "none of these (e.g. weddings, residential, leisure travel, retail, software, other)"}},
}


def jev_questions() -> dict[str, dict[str, Any]]:
    from execution.modules import jev_client as jev
    return {
        "niche": jev.choice(NICHE_Q["niche"]["instructions"], NICHE_Q["niche"]["options"]),
        "fit": jev.noul(
            "Is this a B2B firm that writes custom client proposals/bids for corporate projects "
            "(not weddings/residential/leisure)?",
            "true when it sells custom projects, events, builds or programs to businesses and must quote or "
            "propose each one",
            "false when it is consumer-facing (weddings, homeowners, leisure travellers), a product seller, "
            "a venue, a software company, or not a services firm"),
    }


def cmd_gate(args: argparse.Namespace) -> None:
    from execution.modules import jev_client as jev
    rows = load_raw_rows()
    if not rows:
        raise SystemExit("no downloaded exports; run `export` first")
    keep, rejects = hygiene(rows)
    print(f"hygiene: {len(rows)} raw -> {len(keep)} kept, rejects {dict(Counter(r['reject_reason'] for r in rejects))}")
    cache_path = TMP / "jev_cache.json"
    cache = jload(cache_path, {})
    companies: dict[str, dict[str, Any]] = {}
    for r in keep:
        companies.setdefault(r["_company_domain"], r)
    todo = [d for d in companies if d not in cache]
    if args.limit:
        todo = todo[: args.limit]
    states = []
    for d in todo:
        r = companies[d]
        states.append({
            "company_name": r.get("current_company_name", ""),
            "industry": r.get("current_company_industry", ""),
            "domain": d,
            "employees": r.get("current_company_employees", ""),
            "contact_headline": (r.get("profile_headline") or "")[:300],
            "contact_summary_snippet": (r.get("profile_summary") or "")[:700],
        })
    qs = jev_questions()
    cost = 0.0
    for i in range(0, len(states), 200):
        chunk_states, chunk_domains = states[i:i + 200], todo[i:i + 200]
        results = jev.decide_many(chunk_states, qs, workers=8)
        for d, res in zip(chunk_domains, results):
            cost += res.cost_usd
            if res.error:
                cache[d] = {"error": res.error[:200]}
            else:
                cache[d] = {"niche": res.choice("niche"), "niche_conf": res.confidence("niche"),
                            "probs": res.probabilities("niche"), "fit": res.noul("fit")}
        jsave(cache_path, cache)
        print(f"jev: {min(i + 200, len(states))}/{len(states)} companies, cost so far ${cost:.4f}")
    jev.append_ledger({"caller": "leadocean_leads.gate", "items": len(states), "cost_usd": cost})
    stats = jload(TMP / "costs.json", {})
    stats["jev_usd"] = round(stats.get("jev_usd", 0.0) + cost, 6)
    jsave(TMP / "costs.json", stats)

    gated, flagged = [], Counter()
    for r in keep:
        j = cache.get(r["_company_domain"])
        r["_jev_flags"] = []
        if j is None:
            r["_jev_flags"].append("jev_pending")
        elif "error" in j:
            r["_jev_flags"].append("jev_unchecked")
        else:
            assigned = r["_niche"]
            r["_jev_niche_conf"] = round(float((j.get("probs") or {}).get(assigned, 0.0)), 3)
            r["_jev_fit"] = round(float(j.get("fit", 0.0)), 3)
            if (j["niche"] in NICHES and j["niche"] != assigned and j["niche_conf"] >= 0.6
                    and j["fit"] >= 0.6):
                # Confidently another target niche (e.g. an AV keyword hit that is really a DMC): move, flag.
                r["_niche"], r["_metro_note"] = j["niche"], r["_metro"]
                r["_jev_niche_conf"] = round(float(j["niche_conf"]), 3)
                r["_jev_flags"].append("jev_reassigned")
                flagged.update(r["_jev_flags"])
                gated.append(r)
                continue
            if j["niche"] != assigned and j["niche_conf"] >= 0.6:
                r["reject_reason"] = f"jev_niche_{j['niche']}"
                rejects.append(r)
                continue
            if j["fit"] < 0.4:
                r["reject_reason"] = "jev_low_fit"
                rejects.append(r)
                continue
            if j["niche"] != assigned or j["fit"] < 0.6:
                r["_jev_flags"].append("jev_borderline")
        flagged.update(r["_jev_flags"])
        gated.append(r)
    jsave(TMP / "gate.json", {"kept": gated, "rejects": rejects})
    print(f"gate: kept {len(gated)}, flags {dict(flagged)}, rejects {dict(Counter(r['reject_reason'] for r in rejects))}")


# --------------------------------------------------------------------------------------
# 4b. verify (wave 2): Reoon power-mode on every gated address, then the final per-company selection
# --------------------------------------------------------------------------------------
def cmd_verify(args: argparse.Namespace) -> None:
    from execution.lead_sourcing import reoon_verify as rv
    kept = jload(TMP / "gate.json", {}).get("kept", [])
    if not kept:
        raise SystemExit("run `gate` first")
    cache = rv.load_cache()
    todo = sorted({r["_email"] for r in kept} - set(cache))
    if args.limit:
        todo = todo[: args.limit]
    if len(todo) > args.max_credits:
        raise SystemExit(f"{len(todo)} emails need Reoon credits; --max-credits is {args.max_credits}")
    key = rv.api_key()
    print(f"reoon: {len(kept)} gated rows, {len(todo)} new emails to verify", flush=True)
    lock = threading.Lock()
    done = 0

    def work(email: str) -> None:
        nonlocal done
        res = rv.verify_one(email, key)
        with lock:
            cache[email] = res
            done += 1
            if res["status"] != "error":
                with open(rv.CACHE, "a", encoding="utf-8") as fh:
                    fh.write(json.dumps(res) + "\n")
            if done % 250 == 0:
                print(f"reoon: {done}/{len(todo)}", flush=True)

    rv.CACHE.parent.mkdir(parents=True, exist_ok=True)
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(work, todo))
    stats = jload(TMP / "costs.json", {})
    stats["reoon_credits"] = stats.get("reoon_credits", 0) + sum(1 for e in todo if cache.get(e, {}).get("status") != "error")
    jsave(TMP / "costs.json", stats)
    b = Counter(rv.bucket(cache[r["_email"]]) if r["_email"] in cache else "pending" for r in kept)
    st = Counter(cache.get(r["_email"], {}).get("status", "pending") for r in kept)
    print(f"reoon buckets over gated rows {dict(b)}; statuses {dict(st)}")


def site_vetoed(e: dict[str, Any]) -> bool:
    """Site-based veto: the website clearly says another business (wedding, residential, leisure, other)."""
    js = e.get("jev_site")
    return bool(js and ((js["niche"] == "none" and js["niche_conf"] >= 0.7 and js["fit"] < 0.5) or js["fit"] < 0.25))


def w2_select(kept: list[dict[str, Any]], enrich: dict[str, Any] | None
              ) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    """Wave 2 final pick: Reoon bucket (drop -> reject), site veto (when enrich given), then the 2-per-company cap
    counting wave-1 senders, preferring Reoon `main` over `catchall`, then seniority.
    Returns (selected, rejects, reoon_dropped) where reoon_dropped is a subset of rejects."""
    from execution.lead_sourcing import reoon_verify as rv
    cache, w1 = rv.load_cache(), wave1_exclusions()
    selected, rejects, dropped = [], [], []
    by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in kept:
        res = cache.get(r["_email"])
        if not res:
            rejects.append({**r, "reject_reason": "reoon_pending"})
            continue
        r = {**r, "_reoon": res, "_bucket": rv.bucket(res)}
        if r["_bucket"] == "drop":
            r["reject_reason"] = f"reoon_{res.get('status') or 'error'}"
            rejects.append(r)
            dropped.append(r)
            continue
        if enrich is not None and site_vetoed(enrich.get(r["_company_domain"], {})):
            rejects.append({**r, "reject_reason": "jev_site_offniche"})
            continue
        by_company[r["_company_domain"]].append(r)
    for dom, people in by_company.items():
        people.sort(key=lambda p: (p["_bucket"] != "main", title_rank(p.get("current_job_title", "")),
                                   0 if (p.get("profile_is_decision_maker") or "").lower() == "true" else 1))
        slots = max(0, 2 - w1["per_domain"][dom])
        selected.extend(people[:slots])
        rejects.extend({**p, "reject_reason": "company_cap_2"} for p in people[slots:])
    return selected, rejects, dropped


# --------------------------------------------------------------------------------------
# 5. enrich (company sites)
# --------------------------------------------------------------------------------------
SUBPAGE_HINTS = ["about", "projects", "work", "portfolio", "case-studies", "case-study", "services", "clients",
                 "our-work", "events", "destinations", "experience"]
GENERIC_HEADINGS = re.compile(
    r"^(home|about( us)?|contact( us)?|services|our services|our work|work|projects|portfolio|news|blog|team|"
    r"our team|careers|menu|search|get in touch|let'?s talk|follow us|subscribe|newsletter|privacy policy|"
    r"read more|learn more|view (all|more|project)|see more|what we do|who we are|why us|testimonials|"
    r"case studies|clients|our clients|connect with us|quick links|navigation|social|resources|faq|"
    r"cookie.*|skip to.*|back to top|loading.*|request a quote|get a quote|sign up|log ?in|shop|cart)$", re.IGNORECASE)


def fetch(url: str) -> tuple[str, str]:
    """Return (final_url, html) or ('', '') on failure. HTTPS first (sandbox proxy is HTTPS-only)."""
    try:
        r = requests.get(url, headers={"User-Agent": UA, "Accept": "text/html"}, timeout=10, allow_redirects=True)
    except requests.RequestException as exc:
        log.debug("fetch %s: %s", url, exc.__class__.__name__)
        return "", ""
    ctype = r.headers.get("content-type", "")
    if r.status_code != 200 or "html" not in ctype:
        return "", ""
    return r.url, r.text[:600_000]


def page_text(markup: str) -> dict[str, Any]:
    from bs4 import BeautifulSoup
    soup = BeautifulSoup(markup, "html.parser")
    meta = ""
    for attrs in ({"name": "description"}, {"property": "og:description"}):
        tag = soup.find("meta", attrs=attrs)
        if tag and tag.get("content"):
            meta = html.unescape(tag["content"]).strip()
            break
    title = soup.title.get_text(" ", strip=True) if soup.title else ""
    links = [(a.get("href") or "", a.get_text(" ", strip=True)) for a in soup.find_all("a")]
    for t in soup(["script", "style", "noscript", "svg", "nav", "footer", "header", "form", "iframe"]):
        t.decompose()
    heads = []
    for h in soup.find_all(["h1", "h2", "h3", "h4"]):
        txt = re.sub(r"\s+", " ", h.get_text(" ", strip=True))
        if 3 <= len(txt) <= 80 and not GENERIC_HEADINGS.match(txt.strip(" .:!")):
            heads.append(txt)
    paras = [re.sub(r"\s+", " ", p.get_text(" ", strip=True)) for p in soup.find_all(["p", "li"])]
    paras = [p for p in paras if len(p) >= 40]
    return {"title": title, "meta": meta, "heads": heads, "paras": paras[:60], "links": links}


def site_for(domain: str, company: str) -> dict[str, Any]:
    cache = SITES / f"{re.sub(r'[^a-z0-9.-]', '_', domain)}.json"
    if not cache.resolve().is_relative_to(SITES.resolve()):
        raise ValueError("path traversal")
    got = jload(cache, None)
    if got is not None:
        return got
    pages: dict[str, dict[str, Any]] = {}
    home_url, home = "", ""
    for cand in (f"https://{domain}", f"https://www.{domain}"):
        home_url, home = fetch(cand)
        if home:
            break
    if home:
        pages[home_url] = page_text(home)
        host = urlparse(home_url).hostname or domain
        picked: list[str] = []
        for href, _txt in pages[home_url]["links"]:
            u = urljoin(home_url, href)
            pu = urlparse(u)
            if pu.scheme != "https" or (pu.hostname or "") != host:
                continue
            path = pu.path.lower().strip("/")
            if path and path.split("/")[0] in SUBPAGE_HINTS and path.count("/") <= 1:
                u = f"https://{host}/{pu.path.strip('/')}"
                if u not in picked:
                    picked.append(u)
        if len(picked) < 2:
            for p in ("about", "projects", "work", "portfolio"):
                u = f"https://{host}/{p}"
                if u not in picked:
                    picked.append(u)
        for u in picked[:4]:
            fu, body = fetch(u)
            if body and fu not in pages:
                pages[fu] = page_text(body)
    data: dict[str, Any] = {"domain": domain, "source": "site" if pages else "", "pages": {}}
    for u, p in pages.items():
        data["pages"][u] = {k: v for k, v in p.items() if k != "links"}
    has_text = any(p.get("paras") or p.get("heads") or p.get("meta") for p in data["pages"].values())
    if not has_text and os.environ.get("SERPER_API_KEY"):
        org = serper_site(domain, company)
        if org:
            data["source"] = "serper"
            data["pages"]["serper"] = {"title": "", "meta": "", "heads": [o.get("title", "") for o in org],
                                       "paras": [o.get("snippet", "") for o in org if o.get("snippet")]}
    jsave(cache, data)
    return data


def serper_site(domain: str, company: str) -> list[dict[str, Any]]:
    """Google results from the company's own domain only (third-party hits name the wrong entity)."""
    hits: list[dict[str, Any]] = []
    for q in (f"site:{domain}", f"\"{company}\" projects"):
        try:
            r = requests.post("https://google.serper.dev/search",
                              headers={"X-API-KEY": os.environ["SERPER_API_KEY"], "Content-Type": "application/json"},
                              json={"q": q, "num": 10}, timeout=15)
            org = r.json().get("organic", []) if r.status_code == 200 else []
        except (requests.RequestException, ValueError) as exc:
            log.warning("serper %s: %s", domain, exc.__class__.__name__)
            org = []
        hits = [o for o in org if norm_domain(o.get("link", "")).endswith(domain)]
        if hits:
            break
    return hits


def summarise_site(data: dict[str, Any]) -> tuple[str, str, str]:
    """Return (company_summary <=600 chars, site_facts semicolon list, context text for icebreaker)."""
    pages = list(data.get("pages", {}).values())
    if not pages:
        return "", "", ""
    home = pages[0]
    summ_parts = [home.get("meta", "")] + home.get("paras", [])[:4]
    for p in pages[1:]:
        if not summ_parts[0]:
            summ_parts[0] = p.get("meta", "")
    summary = ""
    for part in summ_parts:
        part = part.strip()
        if part and part not in summary:
            summary = (summary + " " + part).strip()
        if len(summary) >= 600:
            break
    summary = summary[:600].rsplit(" ", 1)[0] if len(summary) > 600 else summary
    facts: list[str] = []
    seen: set[str] = set()
    for p in pages[1:] + pages[:1]:  # sub-pages (projects/portfolio) first: named work lives there
        for h in p.get("heads", []):
            k = h.lower()
            if k not in seen and len(h.split()) <= 10:
                seen.add(k)
                facts.append(h.replace(";", ","))
    site_facts = "; ".join(facts[:15])[:500]
    context = " ".join(" ".join(p.get("paras", [])[:12]) for p in pages)[:3500]
    return summary, site_facts, context


def site_gate(out: dict[str, Any], companies: dict[str, str]) -> None:
    """Second Jev pass on the scraped site summary (a far richer state than a contact headline).
    Catches e.g. wedding producers that read as 'event production' from LinkedIn data alone."""
    from execution.modules import jev_client as jev
    todo = [d for d, v in out.items() if "jev_site" not in v and (v.get("company_summary") or v.get("site_facts"))]
    if not todo:
        return
    states = [{"company_name": companies.get(d, ""), "domain": d,
               "website_summary": out[d].get("company_summary", ""), "website_facts": out[d].get("site_facts", "")}
              for d in todo]
    cost = 0.0
    for d, res in zip(todo, jev.decide_many(states, jev_questions(), workers=8)):
        cost += res.cost_usd
        if not res.error:
            out[d]["jev_site"] = {"niche": res.choice("niche"), "niche_conf": round(res.confidence("niche"), 3),
                                  "fit": round(res.noul("fit"), 3)}
    stats = jload(TMP / "costs.json", {})
    stats["jev_usd"] = round(stats.get("jev_usd", 0.0) + cost, 6)
    jsave(TMP / "costs.json", stats)
    print(f"site gate: {len(todo)} companies, Jev ${cost:.4f}")


def cmd_enrich(args: argparse.Namespace) -> None:
    gate = jload(TMP / "gate.json", {})
    kept = gate.get("kept", [])
    if not kept:
        raise SystemExit("run `gate` first")
    if WAVE == 2:
        kept = w2_select(kept, None)[0]
    companies: dict[str, str] = {}
    for r in kept:
        companies.setdefault(r["_company_domain"], r.get("current_company_name", ""))
    out_path = TMP / "enrich.json"
    out = jload(out_path, {})
    todo = [d for d in companies if d not in out]
    if args.limit:
        todo = todo[: args.limit]
    SITES.mkdir(parents=True, exist_ok=True)
    done = 0
    lock = threading.Lock()

    def work(d: str) -> None:
        nonlocal done
        try:
            data = site_for(d, companies[d])
            summary, facts, context = summarise_site(data)
            rec = {"company_summary": summary, "site_facts": facts, "context": context,
                   "source": data.get("source", "")}
        except (ValueError, RuntimeError, OSError) as exc:
            log.warning("enrich %s: %s", d, exc)
            rec = {"company_summary": "", "site_facts": "", "context": "", "source": "error"}
        with lock:
            out[d] = rec
            done += 1
            if done % 50 == 0:
                jsave(out_path, out)
                print(f"enrich: {done}/{len(todo)}")

    with ThreadPoolExecutor(max_workers=16) as pool:
        list(pool.map(work, todo))
    jsave(out_path, out)
    site_gate(out, companies)
    jsave(out_path, out)
    src = Counter(v.get("source") or "none" for v in out.values())
    print(f"enrich: {len(out)} companies cached; sources {dict(src)}; "
          f"with facts {sum(1 for v in out.values() if v.get('site_facts'))}")


# --------------------------------------------------------------------------------------
# 6. icebreak
# --------------------------------------------------------------------------------------
BANNED = re.compile(r"impressive|came across|i noticed|amazing|incredible|love (what|how)|stumbled|distinctive|"
                    r"one of your favou?rites|standout|"
                    r"hope this|i was impressed|kudos|congrat|awesome|fantastic|stellar|remarkable|"
                    r"passion|journey|delve|testament|game[- ]chang|cutting[- ]edge", re.IGNORECASE)
ICE_SYSTEM = """You write one cold-email opening line for a B2B prospect. Output JSON only:
{"icebreaker": str, "project_reference": str, "pain_guess": str, "confidence": number 0-1}
Rules:
- icebreaker: ONE sentence, 8 to 20 words, a plain factual observation about their work, written to the person
  ("you"/"your team"). It goes right after "Hi {first name}," so never start with their name or a greeting.
- It must name ONE specific, checkable thing (a named project, client, venue, event, destination or program)
  that appears VERBATIM in SITE FACTS or SITE TEXT. Copy that exact phrase into project_reference and use the
  same phrase, unchanged, inside the icebreaker.
- Just state the observation. No evaluative adjectives ("distinctive", "standout") and no inference about their workload or pitches ("which means", "must be"), no
  flattery or filler ("impressive", "came across", "I noticed", "amazing", "love", "congrats"), no questions,
  no em or en dashes, no claims beyond the provided text, no mention of AI or proposals.
- pain_guess: max 15 words on the proposal/bid-writing pain this firm likely has (internal use only).
- confidence: 0.85-1 when project_reference is a proper-noun project, client, venue, event or destination
  copied verbatim; 0.5 when only a generic service line is available; 0 when the text is generic marketing
  copy or empty (then icebreaker "")."""
_ice_fail: Counter = Counter()
FIXABLE = {"too_long": "the icebreaker must be 20 words or fewer (aim for 15)",
           "dash": "no em or en dashes", "banned": "no flattery or filler words",
           "ref_not_in_line": "project_reference must appear unchanged inside the icebreaker",
           "question": "no questions"}


def _ice_prompt(r: dict[str, Any], e: dict[str, Any]) -> str:
    return (f"PERSON: {r.get('profile_first_name', '')} | {r.get('current_job_title', '')}\n"
            f"COMPANY: {r.get('current_company_name', '')} ({r['_company_domain']}) | niche: "
            f"{NICHES[r['_niche']]['label']}\n"
            f"SITE FACTS: {e.get('site_facts', '')}\n"
            f"COMPANY SUMMARY: {e.get('company_summary', '')}\n"
            f"SITE TEXT: {e.get('context', '')[:2500]}")


def _parse_json(text: str) -> dict[str, Any] | None:
    m = re.search(r"\{.*\}", text or "", re.DOTALL)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError:
        return None


def validate_ice(obj: dict[str, Any] | None, e: dict[str, Any]) -> tuple[dict[str, Any], str]:
    """Deterministic guard on the LLM output. Returns (record, status)."""
    rec = {"icebreaker": "", "project_reference": "", "pain_guess": "", "confidence": 0.0}
    if not obj:
        return rec, "template_only"
    ice = str(obj.get("icebreaker") or "").strip().strip('"')
    ref = str(obj.get("project_reference") or "").strip()
    try:
        conf = float(obj.get("confidence") or 0)
    except (TypeError, ValueError):
        conf = 0.0
    rec.update(pain_guess=str(obj.get("pain_guess") or "")[:150], confidence=conf, project_reference=ref)
    haystack = " ".join([e.get("site_facts", ""), e.get("company_summary", ""), e.get("context", "")]).lower()
    checks = {"empty": bool(ice), "low_conf": conf >= 0.7, "too_long": len(ice.split()) <= 20,
              "dash": "\u2014" not in ice and "\u2013" not in ice, "banned": not BANNED.search(ice),
              "ref_not_in_site": bool(ref) and len(ref) >= 3 and ref.lower() in haystack,
              "ref_not_in_line": bool(ref) and ref.lower() in ice.lower(), "question": "?" not in ice}
    failed = [k for k, v in checks.items() if not v]
    rec["fail"] = failed[0] if failed else ""
    if not failed:
        rec["icebreaker"] = ice
        return rec, "personalized"
    rec["project_reference"] = ref if ref and ref.lower() in haystack else ""
    return rec, "template_only"


def cmd_icebreak(args: argparse.Namespace) -> None:
    from execution.modules import llm_client
    kept = jload(TMP / "gate.json", {}).get("kept", [])
    enrich = jload(TMP / "enrich.json", {})
    out_path = TMP / "icebreak.json"
    out = jload(out_path, {})
    if WAVE == 2:
        kept = w2_select(kept, enrich)[0]
    todo = [r for r in kept if r["_email"] not in out and r["_company_domain"] in enrich]
    if args.limit:
        todo = todo[: args.limit]
    lock = threading.Lock()
    tokens = {"in": 0, "out": 0, "calls": 0}
    done = 0

    def work(r: dict[str, Any]) -> None:
        nonlocal done
        if args.max_usd and tokens["in"] * LLM_PRICE_IN + tokens["out"] * LLM_PRICE_OUT >= args.max_usd:
            return  # budget guard: leave the row uncached so a later run can finish it
        e = enrich[r["_company_domain"]]
        if not e.get("site_facts") and not e.get("context"):
            rec, status = validate_ice(None, e)
        else:
            prompt = _ice_prompt(r, e)
            try:
                text = llm_client.chat_completion(ICE_SYSTEM, prompt, model=LLM_MODEL, max_tokens=600)
            except Exception as exc:  # noqa: BLE001 - provider SDK raises many types; log and fall back to template
                log.warning("icebreak %s: %s", r["_email"], exc.__class__.__name__)
                text = ""
            rec, status = validate_ice(_parse_json(text), e)
            calls = [(prompt, text)]
            if rec.get("fail") in FIXABLE:  # one repair pass for format slips (length, dash, filler)
                fix = (f"{prompt}\n\nYOUR PREVIOUS ANSWER: {text}\nIt broke this rule: {FIXABLE[rec['fail']]}. "
                       "Return corrected JSON.")
                try:
                    text2 = llm_client.chat_completion(ICE_SYSTEM, fix, model=LLM_MODEL, max_tokens=600)
                except Exception as exc:  # noqa: BLE001 - provider SDK raises many types; keep first result
                    log.warning("icebreak repair %s: %s", r["_email"], exc.__class__.__name__)
                    text2 = ""
                calls.append((fix, text2))
                rec2, status2 = validate_ice(_parse_json(text2), e)
                if status2 == "personalized":
                    rec, status = rec2, status2
            with lock:
                _ice_fail[rec.get("fail") or "ok"] += 1
                for pr, tx in calls:
                    tokens["in"] += (len(ICE_SYSTEM) + len(pr)) // 4
                    tokens["out"] += max(len(tx) // 4, 1) + 150  # + low-effort reasoning allowance
                    tokens["calls"] += 1
        rec["personalization_status"] = status
        with lock:
            out[r["_email"]] = rec
            done += 1
            if done % 100 == 0:
                jsave(out_path, out)
                print(f"icebreak: {done}/{len(todo)}")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(work, todo))
    jsave(out_path, out)
    cost = tokens["in"] * LLM_PRICE_IN + tokens["out"] * LLM_PRICE_OUT
    stats = jload(TMP / "costs.json", {})
    stats["llm_usd_est"] = round(stats.get("llm_usd_est", 0.0) + cost, 4)
    stats["llm_calls"] = stats.get("llm_calls", 0) + tokens["calls"]
    jsave(TMP / "costs.json", stats)
    st = Counter(v["personalization_status"] for v in out.values())
    print(f"icebreak: {len(out)} cached; {dict(st)}; this run ~${cost:.3f} ({tokens['calls']} calls); "
          f"first failed check {dict(_ice_fail)}")


# --------------------------------------------------------------------------------------
# 2b. topup (company-first): spend leftover export rows only on Jev-approved ICP companies
# --------------------------------------------------------------------------------------
TOPUP_EXTRA_KEYWORDS = {
    "av": ["audio visual", "audiovisual", "live events", "event technology", "event agency", "brand experience",
           "event staging", "show production", "conference production", "meetings and events"],
    "fitout": ["interior general contractor", "commercial general contractor", "interior finishes",
               "office renovation", "restaurant construction", "retail construction", "build-out"],
}
COMPANY_EXCLUDE_KW = {
    "av": ["wedding", "DJ", "party rental", "church", "bridal", "home theater", "smart home"],
    "fitout": ["residential", "roofing", "restoration", "home builder", "remodeling", "kitchen and bath"],
}


def company_filters(niche: str, metro: str) -> dict[str, Any]:
    n, m = NICHES[niche], M[metro]
    f: dict[str, Any] = {"keywords": n["companyKeywords"] + TOPUP_EXTRA_KEYWORDS.get(niche, []),
                         "excludeKeywords": COMPANY_EXCLUDE_KW.get(niche, []),
                         "minEmployees": n["minEmployees"], "maxEmployees": n["maxEmployees"],
                         "hasMailableContacts": "true", "hqCountry": m.get("hqCountry", ["US"])}
    for k in ("hqCity", "hqState"):
        if m.get(k):
            f[k] = m[k]
    if n.get("excludeIndustry"):
        f["excludeIndustry"] = n["excludeIndustry"]
    if n.get("industry"):
        f["industry"] = n["industry"]
    if WAVE == 2:
        # hasMailableContacts ignores `untested`, which wave 2 accepts; the industry list replaces the
        # exclude list (company keywords alone gave 13.9k US "AV" firms, mostly ad agencies and venues).
        f.pop("hasMailableContacts")
        f.pop("excludeIndustry", None)
        f["industry"] = W2_INDUSTRY[niche]
        if niche == "dmc":
            f["excludeKeywords"] = n["excludeKeywords"] + ["wedding"]
    return f


def export_body_filters(f: dict[str, Any]) -> dict[str, Any]:
    """GET-style filters -> JSON export filters (booleans as JSON booleans)."""
    return {k: (v == "true") if k == "excludeViewed" else v for k, v in f.items()}


def mark_wave1_viewed(lo: LeadOcean) -> None:
    """Put every wave-1 exported person_id on the LeadOcean viewed list (free, idempotent), so wave-2 counts and
    exports with excludeViewed never bill a wave-1 person again."""
    ids = sorted(wave1_exclusions()["person_ids"])
    for i in range(0, len(ids), 10000):
        lo.req("POST", "/v1/people/viewed", body={"ids": ids[i:i + 10000], "set": VIEWED_SET})
    got = lo.req("GET", "/v1/people/viewed", params={"set": VIEWED_SET})
    print(f"viewed list {VIEWED_SET}: {len(ids)} wave-1 person_ids sent; list says {json.dumps(got.get('data'))[:200]}")


def export_rows_left_today(lo: LeadOcean) -> int:
    day = lo.req("GET", "/v1/account")["data"]["exports"]["day"]
    return max(0, int(day["limit"]) - int(day["used"]))


# Wave 2: a company with more matching decision-makers than --max-per-domain is re-counted with only the top
# seniority bands (owner/founder/C-suite/partner); most then fit, and the export uses the same tight filter.
TIGHT_SENIORITY = ["owner", "founder", "c_suite", "partner"]


def domain_filters(niche: str, metro: str, domains: list[str], tight: bool = False) -> dict[str, Any]:
    f = filters_for(niche, metro)
    for k in ("companyKeywords", "hqCity", "hqState", "hqCountry", "minEmployees", "maxEmployees",
              "industry", "excludeIndustry"):
        f.pop(k, None)
    f["domain"] = domains
    if tight:
        f["seniority"] = TIGHT_SENIORITY
    return f


def domain_count(lo: LeadOcean, niche: str, metro: str, domain: str, tight: bool = False) -> int:
    return int(lo.count(domain_filters(niche, metro, [domain], tight)).get("total") or 0)


def cmd_topup(args: argparse.Namespace) -> None:
    from execution.modules import jev_client as jev
    lo = LeadOcean()
    state_path = TMP / "exports.json"
    state = jload(state_path, {})
    spent = sum(int(s.get("requested", 0)) for s in state.values())
    left = args.budget - spent
    w1 = None
    if WAVE == 2:
        mark_wave1_viewed(lo)
        w1 = wave1_exclusions()
        # The daily export allowance is the real ceiling in wave 2; --budget caps this run on top of it.
        spent_today = sum(int(s.get("requested", 0)) for s in state.values() if s.get("day") == TODAY)
        left = min(args.budget - spent_today, export_rows_left_today(lo))
        seen_domains = {d for d, c in w1["per_domain"].items() if c >= 2}
        seen_domains |= {d for s in state.values() for d in s.get("domains", [])}
    else:
        seen_domains = {norm_domain(r.get("current_company_domain")) for r in load_raw_rows()}
    print(f"export rows spent {spent}, left for this run {left}")
    comp_path, jev_path = TMP / "topup_companies.json", TMP / "topup_jev.json"
    comps, jcache = jload(comp_path, {}), jload(jev_path, {})
    for niche in args.niches.split(","):
        metros = W2_METROS if WAVE == 2 else NICHES[niche]["metros"]
        for metro, weight in metros.items():
            key = f"{niche}:{metro}"
            if weight < 1 or key in comps:
                continue
            params = {k: (",".join(v) if isinstance(v, list) else v) for k, v in company_filters(niche, metro).items()}
            params.update(limit=100, slim="true")
            rows, cursor = [], None
            for _page in range(args.max_pages):
                if cursor:
                    params["cursor"] = cursor
                try:
                    j = lo.req("GET", "/v1/companies/search", params=params)
                except RuntimeError as exc:
                    log.warning("company search %s: %s", key, exc)
                    break
                if j.get("meta", {}).get("unsupportedFilters"):
                    log.warning("%s unsupported %s", key, j["meta"]["unsupportedFilters"])
                for c in j.get("data", []):
                    d = c.get("company_data", {})
                    rows.append({"domain": norm_domain(d.get("company_domain")), "name": d.get("company_name", ""),
                                 "industry": ", ".join(str(x) for x in (d.get("company_industries") or [])[:3]),
                                 "description": (d.get("company_description") or "")[:1500]})
                cursor = j.get("meta", {}).get("nextCursor")
                if not cursor or not j.get("data"):
                    break
            comps[key] = rows
            jsave(comp_path, comps)
            print(f"companies {key}: {len(rows)}", flush=True)
    # Jev gate on the company description (a much richer state than a contact headline)
    todo = [(k, c) for k, rows in comps.items() for c in rows
            if c["domain"] and c["domain"] not in seen_domains and c["domain"] not in jcache]
    uniq = {c["domain"]: (k, c) for k, c in todo}
    states = [{"company_name": c["name"], "industry": c["industry"], "domain": d, "description": c["description"]}
              for d, (_k, c) in uniq.items()]
    cost = 0.0
    doms = list(uniq)
    for i in range(0, len(states), 500):
        for d, res in zip(doms[i:i + 500], jev.decide_many(states[i:i + 500], jev_questions(), workers=8)):
            cost += res.cost_usd
            jcache[d] = ({"error": res.error[:200]} if res.error else
                         {"niche": res.choice("niche"), "niche_conf": res.confidence("niche"), "fit": res.noul("fit")})
        jsave(jev_path, jcache)
        print(f"topup jev: {min(i + 500, len(states))}/{len(states)} companies, ${cost:.4f}", flush=True)
    costs = jload(TMP / "costs.json", {})
    costs["jev_usd"] = round(costs.get("jev_usd", 0.0) + cost, 6)
    jsave(TMP / "costs.json", costs)
    # ICP companies not yet exported, with their free per-domain decision-maker count
    cands, seen_c = [], set()
    for key, rows in comps.items():
        niche, metro = key.split(":")
        for c in rows:
            j = jcache.get(c["domain"], {})
            if (not c["domain"] or c["domain"] in seen_domains or c["domain"] in seen_c or j.get("niche") != niche
                    or j.get("fit", 0) < 0.6):
                continue
            seen_c.add(c["domain"])
            cands.append((niche, metro, c["domain"], float(j.get("fit", 0))))
    print(f"topup: {len(cands)} Jev-approved new companies; Jev ${cost:.4f}", flush=True)
    cnt_path = TMP / "topup_counts.json"
    cnt = jload(cnt_path, {})
    lock = threading.Lock()

    def count_one(item: tuple[str, str, str, bool]) -> None:
        n, m, d, tight = item
        try:
            v = domain_count(lo, n, m, d, tight)
        except RuntimeError as exc:
            log.warning("count %s: %s", d, exc)
            return
        with lock:
            cnt[f"{n}|{d}" + ("|tight" if tight else "")] = v
            if len(cnt) % 200 == 0:
                jsave(cnt_path, cnt)
                print(f"domain counts: {len(cnt)}", flush=True)

    todo_c = [(n, m, d, False) for n, m, d, _f in cands if f"{n}|{d}" not in cnt]
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        list(pool.map(count_one, todo_c))
    if WAVE == 2:
        todo_t = [(n, m, d, True) for n, m, d, _f in cands
                  if (cnt.get(f"{n}|{d}") or 0) > args.max_per_domain and f"{n}|{d}|tight" not in cnt]
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(count_one, todo_t))
    jsave(cnt_path, cnt)
    counted = []
    for niche, metro, d, fit in cands:
        n, tight = cnt.get(f"{niche}|{d}") or 0, False
        if n > args.max_per_domain and f"{niche}|{d}|tight" in cnt:
            n, tight = cnt[f"{niche}|{d}|tight"], True
        # > max_per_domain usually means a big employer or a domain LeadOcean maps to another firm
        # (2026-11-02: one "Atlanta AV" domain returned 190 Crawford & Company insurance rows).
        if not 0 < n <= args.max_per_domain:
            continue
        slots = max(0, 2 - w1["per_domain"][d]) if w1 else 2
        if slots == 0:
            continue
        # rows bought beyond the per-company cap (+1 Reoon reserve in wave 2) are waste: fewest first
        waste = max(0, n - slots - (1 if w1 else 0))
        counted.append((waste, n, -fit, niche, f"{metro}|tight" if tight else metro, d))
    counted.sort()
    picked: list[tuple[int, str, str, str]] = []
    rows_needed = 0
    if WAVE == 2:
        # split the day's rows by what each niche still needs to reach its allocation
        have = Counter()
        if W1_LEADS.exists():
            with open(W1_LEADS, newline="", encoding="utf-8") as fh:
                have.update(r["niche"] for r in csv.DictReader(fh) if r.get("send_bucket") == "main")
        # --weights scales a niche's need by its measured safe-lead yield per row (2026-11-02 day-1 sample:
        # AV 33%, DMC 31%, fit-out 10%), so rows go where they buy the most safe leads.
        wts = {k: float(v) for k, _s, v in (x.partition("=") for x in args.weights.split(",") if x)}
        need = {k: max(1, NICHES[k]["target"] - have[k]) * wts.get(k, 1.0) for k in args.niches.split(",")}
        share = {k: int(left * v / sum(need.values())) for k, v in need.items()}
        used = Counter()
        for _w, n, _f, niche, metro, d in counted:
            if used[niche] + n <= share[niche] and rows_needed + n <= left:
                picked.append((n, niche, metro, d))
                used[niche] += n
                rows_needed += n
        taken = {d for *_x, d in picked}
        for _w, n, _f, niche, metro, d in counted:  # second pass: unspent share goes to any niche
            if d not in taken and rows_needed + n <= left:
                picked.append((n, niche, metro, d))
                rows_needed += n
        print(f"topup: niche need {need}, row share {share}")
    else:
        for _w, n, _f, niche, metro, d in counted:
            if rows_needed + n <= left:
                picked.append((n, niche, metro, d))
                rows_needed += n
    groups: dict[tuple[str, str], list[tuple[int, str]]] = defaultdict(list)
    for n, niche, metro, d in picked:
        groups[(niche, metro)].append((n, d))
    by_n = Counter(n for n, *_x in picked)
    print(f"topup: {len(counted)} companies hold contacts (rows {sum(c[1] for c in counted)}); exporting "
          f"{rows_needed} rows over {len(picked)} companies; contacts-per-domain {dict(sorted(by_n.items()))}; "
          f"by niche {dict(Counter(p[1] for p in picked))}", flush=True)
    if args.plan_only:
        return
    for (niche, metro_t), items in groups.items():
        metro, _sep, tight = metro_t.partition("|")
        for gi in range(0, len(items), args.chunk):
            chunk = items[gi:gi + args.chunk]
            # wave 2: run-unique keys (a re-run on the same day plans fresh domains; seen ones are skipped above)
            key = (f"{niche}:{metro}:topup" if WAVE == 1
                   else f"{niche}:{metro}:w2:{TODAY}:{len(state)}" + (":tight" if tight else ""))
            if key in state:
                continue
            domains = [d for _n, d in chunk]
            f = domain_filters(niche, metro, domains, bool(tight))
            limit = sum(n for n, _d in chunk)
            try:
                data = lo.req("POST", "/v1/exports", body={"name": f"prodcraft {key} {TODAY}",
                                                           "filters": export_body_filters(f), "limit": limit,
                                                           "columns": EXPORT_COLUMNS, "caps": {"emails": 3}})["data"]
            except RuntimeError as exc:
                print(f"topup export {key} refused: {exc}")
                continue
            state[key] = {"id": data["id"], "requested": limit, "status": data.get("status"), "niche": niche,
                          "metro": metro, "topup": True, "domains": domains, "day": TODAY}
            jsave(state_path, state)
            print(f"queued {key} limit={limit}", flush=True)
    poll_and_download(lo, state, state_path)


# --------------------------------------------------------------------------------------
# 7. build
# --------------------------------------------------------------------------------------
OUT_COLS = ["email", "first_name", "last_name", "title", "company_name", "company_domain", "website", "niche",
            "metro", "city", "state", "country", "employees", "linkedin_url", "email_status", "email_verified_date",
            "jev_niche_conf", "jev_fit_score", "company_summary", "site_facts", "project_reference", "icebreaker",
            "personalization_status", "source"]
REJECT_COLS = ["email", "first_name", "last_name", "title", "company_name", "company_domain", "niche", "metro",
               "email_status", "reject_reason", "linkedin_url"]


def clean(s: Any) -> str:
    return re.sub(r"\s+", " ", str(s or "")).replace("—", ", ").replace("–", "-").strip()


def name_case(s: Any) -> str:
    """Title-case only all-lower/all-upper names; keep 'McDonald', 'DeShawn' as given."""
    v = clean(s)
    return v.title() if v == v.lower() or v == v.upper() else v


def lead_row(r: dict[str, Any], e: dict[str, Any], i: dict[str, Any]) -> dict[str, Any]:
    flags = r.get("_jev_flags", [])
    return {
        "email": r["_email"], "first_name": name_case(r.get("profile_first_name")),
        "last_name": name_case(r.get("profile_last_name")), "title": clean(r.get("current_job_title")),
        "company_name": clean(r.get("current_company_name")), "company_domain": r["_company_domain"],
        "website": clean(r.get("current_company_website")) or f"https://{r['_company_domain']}",
        "niche": r["_niche"], "metro": M[r["_metro"]]["label"], "city": clean(r.get("city")),
        "state": clean(r.get("state")), "country": clean(r.get("country_code")),
        "employees": clean(r.get("current_company_employees")), "linkedin_url": clean(r.get("profile_url")),
        "email_status": r["_email_status"], "email_verified_date": r["_email_verified_date"],
        "jev_niche_conf": r.get("_jev_niche_conf", ""), "jev_fit_score": r.get("_jev_fit", ""),
        "company_summary": clean(e.get("company_summary")), "site_facts": clean(e.get("site_facts")),
        "project_reference": clean(i.get("project_reference")), "icebreaker": clean(i.get("icebreaker")),
        "personalization_status": i.get("personalization_status", "template_only"),
        "source": "leadocean_export" + ("|wave2" if WAVE == 2 else "") + ("|" + "|".join(flags) if flags else "")
                  + ("|site_serper" if e.get("source") == "serper" else ""),
    }


REOON_COLS = ["reoon_status", "reoon_score", "reoon_catch_all", "reoon_safe", "send_bucket"]
SPLIT_COLS = ["email", "first_name", "last_name", "title", "company_name", "website", "city", "state", "country",
              "niche", "metro", "project_reference", "icebreaker", "personalization_status", "reoon_score"]
SPLIT_NICHE = {"av": "EventAV", "fitout": "Fitout", "dmc": "DMC"}
SEND_WINDOW = {"US": "Mon-Thu 09:00-12:00 America/Chicago (= 10-1 ET, 7-10 PT)",
               "UK": "Mon-Thu 08:30-11:30 Europe/London"}


def campaign_country(row: dict[str, Any]) -> str:
    """US | UK | Other. Blank contact country falls back to the HQ market (London/UK metros -> UK)."""
    c = (row.get("country") or "").upper()
    if c == "US":
        return "US"
    if c in ("GB", "UK"):
        return "UK"
    if not c:
        return "UK" if row.get("metro", "").startswith(("London", "UK")) else "US"
    return "Other"


def write_campaign_split(rows: list[dict[str, Any]], outdir: Path) -> dict[str, int]:
    """Wave-1 campaign file layout: {Niche}_{US|UK}_{Personalized|NoPersonalization}.csv (main bucket),
    catchall/..._CatchAll.csv, REVIEW_OtherCountries_AllNiches.csv and _campaign_index.csv.
    Personalized = non-empty icebreaker AND project_reference."""
    files: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        if r.get("send_bucket") not in ("main", "catchall"):
            continue
        country = campaign_country(r)
        if country == "Other":
            files[("review", "REVIEW_OtherCountries_AllNiches")].append(r)
            continue
        pers = "Personalized" if r.get("icebreaker") and r.get("project_reference") else "NoPersonalization"
        name = f"{SPLIT_NICHE[r['niche']]}_{country}_{pers}"
        files[(r["send_bucket"], name + ("_CatchAll" if r["send_bucket"] == "catchall" else ""))].append(r)
    (outdir / "catchall").mkdir(parents=True, exist_ok=True)
    index = []
    order = {"review": 0, "catchall": 1, "main": 2}
    for (bucket, name), items in sorted(files.items(), key=lambda kv: (order[kv[0][0]], kv[0][1])):
        path = outdir / ("catchall" if bucket == "catchall" else "") / f"{name}.csv"
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=SPLIT_COLS, extrasaction="ignore")
            w.writeheader()
            w.writerows(items)
        if bucket == "review":
            index.append({"file": name, "bucket": "review", "niche": "mixed", "country": "Other",
                          "personalization": "mixed", "leads": len(items), "send_window": "manual / skip"})
        else:
            parts = name.split("_")
            index.append({"file": name, "bucket": bucket, "niche": parts[0], "country": parts[1],
                          "personalization": parts[2], "leads": len(items), "send_window": SEND_WINDOW[parts[1]]})
    with open(outdir / "_campaign_index.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["file", "bucket", "niche", "country", "personalization", "leads",
                                           "send_window"])
        w.writeheader()
        w.writerows(index)
    return {i["file"]: i["leads"] for i in index}


def cmd_build(args: argparse.Namespace) -> None:
    gate = jload(TMP / "gate.json", {})
    enrich, ice = jload(TMP / "enrich.json", {}), jload(TMP / "icebreak.json", {})
    exports = jload(TMP / "exports.json", {})
    rows, rejects = [], list(gate.get("rejects", []))
    reoon_rows: list[dict[str, Any]] = []
    if WAVE == 2:
        from execution.lead_sourcing import reoon_verify as rv
        selected, sel_rejects, dropped = w2_select(gate.get("kept", []), enrich)
        rejects += sel_rejects
        for r in selected + dropped:
            row = lead_row(r, enrich.get(r["_company_domain"], {}), ice.get(r["_email"], {}))
            res = r["_reoon"]
            row.update(reoon_status=res.get("status", ""), reoon_score=res.get("score", ""),
                       reoon_catch_all=res.get("catch_all", ""), reoon_safe=res.get("safe", ""),
                       send_bucket=rv.bucket(res))
            if not row["country"]:
                row["country"] = "GB" if r.get("_metro") in ("uk_all", "london") else "US"
            reoon_rows.append(row)
        rows = [x for x in reoon_rows if x["send_bucket"] != "drop"]
    else:
        for r in gate.get("kept", []):
            e, i = enrich.get(r["_company_domain"], {}), ice.get(r["_email"], {})
            if site_vetoed(e):
                r["reject_reason"] = "jev_site_offniche"
                rejects.append(r)
                continue
            rows.append(lead_row(r, e, i))
    prefix = "prodcraft_leads_wave2" if WAVE == 2 else "prodcraft_leads"
    out = TMP / f"{prefix}_{TODAY}.csv"
    with open(out, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=OUT_COLS, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    with open(TMP / "rejects.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=REJECT_COLS)
        w.writeheader()
        for r in rejects:
            w.writerow({"email": r.get("_email", ""), "first_name": r.get("profile_first_name", ""),
                        "last_name": r.get("profile_last_name", ""), "title": r.get("current_job_title", ""),
                        "company_name": r.get("current_company_name", ""),
                        "company_domain": r.get("_company_domain", ""), "niche": r.get("_niche", ""),
                        "metro": M.get(r.get("_metro", ""), {}).get("label", ""),
                        "email_status": r.get("_email_status", ""), "reject_reason": r.get("reject_reason", ""),
                        "linkedin_url": r.get("profile_url", "")})
    split = {}
    if WAVE == 2:
        with open(TMP / "prodcraft_leads_wave2_reoon.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_COLS + REOON_COLS)
            w.writeheader()
            w.writerows(reoon_rows)
        split = write_campaign_split(reoon_rows, TMP / "campaigns_by_country")
    per_niche = Counter(r["niche"] for r in rows)
    per_metro: dict[str, Counter] = defaultdict(Counter)
    for r in rows:
        per_metro[r["niche"]][r["metro"]] += 1
    costs = jload(TMP / "costs.json", {})
    summary = {
        "date": TODAY, "wave": WAVE, "final_leads": len(rows), "per_niche": dict(per_niche),
        "targets": {k: v["target"] for k, v in NICHES.items()},
        "per_niche_metro": {k: dict(v.most_common()) for k, v in per_metro.items()},
        "rejects_total": len(rejects), "rejects_by_reason": dict(Counter(r.get("reject_reason") for r in rejects)),
        "personalized": sum(1 for r in rows if r["personalization_status"] == "personalized"),
        "personalized_pct": round(100 * sum(1 for r in rows if r["icebreaker"]) / max(len(rows), 1), 1),
        "jev_flags": dict(Counter(f for r in gate.get("kept", []) for f in r.get("_jev_flags", []))),
        "accepted_email_status": list(STATUSES),
        "send_buckets": dict(Counter(r["send_bucket"] for r in reoon_rows)) if reoon_rows else {},
        "per_niche_country_bucket": dict(Counter(f"{r['niche']}|{campaign_country(r)}|{r['send_bucket']}"
                                                 for r in reoon_rows)) if reoon_rows else {},
        "campaign_files": split,
        "leadocean_rows_requested": sum(int(s.get("requested", 0)) for s in exports.values()),
        "leadocean_records_billed": sum(int(s.get("billed") or 0) for s in exports.values()),
        "leadocean_rows_downloaded": sum(int(s.get("rows") or 0) for s in exports.values()),
        "exports": {k: {x: s.get(x) for x in ("requested", "rows", "billed", "status")} for k, s in exports.items()},
        "cost_usd": {"jev": costs.get("jev_usd", 0.0), "llm_est": costs.get("llm_usd_est", 0.0),
                     "llm_calls": costs.get("llm_calls", 0)},
        "reoon_credits": costs.get("reoon_credits", 0),
        "files": {"leads": str(out.relative_to(ROOT)), "rejects": str((TMP / "rejects.csv").relative_to(ROOT))},
    }
    jsave(TMP / "summary.json", summary)
    print(json.dumps({k: summary[k] for k in ("final_leads", "per_niche", "send_buckets", "rejects_by_reason",
                                              "personalized_pct", "leadocean_records_billed", "cost_usd")}, indent=1))


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    c = sub.add_parser("count", help="free sizing per niche x metro")
    c.add_argument("--refresh", action="store_true")
    e = sub.add_parser("export", help="run bulk exports and download CSVs")
    e.add_argument("--budget", type=int, default=5000, help="hard cap on exported rows (all exports)")
    e.add_argument("--plan-only", action="store_true")
    e.add_argument("--replan", action="store_true")
    e.add_argument("--only", default="", help="comma list of niche:metro keys")
    e.add_argument("--sample", type=int, default=0, help="cap each export at N rows (testing)")
    t = sub.add_parser("topup", help="company-first top-up with leftover export rows")
    t.add_argument("--budget", type=int, default=5000)
    t.add_argument("--niches", default="av,fitout")
    t.add_argument("--max-pages", type=int, default=6)
    t.add_argument("--plan-only", action="store_true")
    t.add_argument("--max-per-domain", type=int, default=8, help="skip domains with more matching people")
    t.add_argument("--workers", type=int, default=6, help="parallel free per-domain counts")
    t.add_argument("--chunk", type=int, default=50, help="domains per export (API max 50)")
    t.add_argument("--weights", default="", help="wave 2: niche row-share weights, e.g. av=1,dmc=1,fitout=0.3")
    for name in ("gate", "enrich", "icebreak", "verify"):
        s = sub.add_parser(name)
        s.add_argument("--limit", type=int, default=0, help="process at most N new items (testing)")
        if name == "icebreak":
            s.add_argument("--max-usd", type=float, default=0.0, help="stop new LLM calls past this estimate")
        if name == "verify":
            s.add_argument("--max-credits", type=int, default=6000, help="refuse to spend more Reoon credits")
            s.add_argument("--workers", type=int, default=8)
    sub.add_parser("build")
    p.add_argument("-v", "--verbose", action="store_true")
    p.add_argument("--wave", type=int, choices=(1, 2), default=1,
                   help="2 = national US+UK, verified/untested/catch_all + Reoon, wave-1 people excluded; "
                        "caches under .tmp/leadocean/wave2/")
    args = p.parse_args()
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.WARNING,
                        format="%(levelname)s %(name)s: %(message)s")
    set_wave(args.wave)
    if args.cmd == "verify" and WAVE != 2:
        raise SystemExit("`verify` is the wave-2 Reoon step; wave 1 uses reoon_verify.py on the final CSV")
    TMP.mkdir(parents=True, exist_ok=True)
    {"count": cmd_count, "export": cmd_export, "gate": cmd_gate, "enrich": cmd_enrich, "verify": cmd_verify,
     "icebreak": cmd_icebreak, "build": cmd_build, "topup": cmd_topup}[args.cmd](args)


if __name__ == "__main__":
    main()
