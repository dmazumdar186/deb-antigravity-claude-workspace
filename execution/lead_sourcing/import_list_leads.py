"""
import_list_leads.py
description: Turn an operator-supplied contact export (Apollo-style CSV: First Name, Last Name, Company Name, Company
             Domain, Email, Title, Industry, Employees Count, Company State, Company Market Cap, ...) into campaign-ready
             lead CSVs, one per vertical x state, with non-personalized merge columns and one evidence-backed
             personalization line. Steps (every drop counted with a reason in funnel.md):
               1. normalize + dedupe (email, then person); drop rows with no company domain; drop list
               2. company gates: headcount floor/ceiling, public (market cap), industry (keep / Jev noul / drop)
               3. person gates (trigger_batch_leads): buyer-title allowlist (Jev for edge titles), role inbox,
                  email domain = company domain (or an alias the homepage shows), public listing on the homepage
               4. email check, free: syntax + MX via DNS-over-HTTPS; cap 2 per company (one chief exec, stale second
                  CEO resolved on the company's own pages); LeadOcean people search (`q` = name, `domain`) for the
                  kept people -> email_check verified_leadocean / mx_ok, catch_all flag. No SMTP probing.
                  When the input carries an email-verifier verdict column (--verifier-status-col, default
                  `status`), it replaces MX + LeadOcean: keep --verifier-keep (safe,catch_all) = email_tier, drop
                  the rest and any is_spamtrap=true.
               5. personalization per company: (a) cached public trigger (FDA 510(k) / federal award) matched by
                  resolved domain or exact name + state, homepage silent on it (finder + blind verifier from
                  trigger_batch_leads); else (b) a hard homepage fact confirmed on a rendered page: footer copyright
                  year <= --copyright-max, an old CMS version in the generator meta, or no viewport meta; else
                  (c) company_description: a factual "Saw that / Noticed {company} ..." line from the company's own
                  description (subscription bulk tier, 25 per call, cached), gated by rules + two Jev nouls; else none.
               Construction keeps bare VP / SVP / EVP titles (operator 2026-11-17), ranked after exec + growth leads.
inputs:  --job VERTICAL:STATES:PATH (repeatable, e.g. medtech:CA,TX,NY:.tmp/x.csv); --out DIR; --drop-list JSON
         {"domains": [], "names": []}; --cache-dir (default .tmp/import_list/cache; jev.json/site.json/pages.json are
         shared with trigger_batch_leads when pointed at its cache); --min-emp 20 --max-emp 500; --max-fetch N (new
         homepage fetches per run); --workers 12 (static fetch) --render-workers 8 (Playwright);
         --max-jev 3000; --max-lo 6000 (LeadOcean person lookups per run); --offline (caches only, no network);
         --fda-since 2026-08-01 (cached openFDA pull); --award-csv GLOB (construction_award_triggers output);
         --award-days 90; --trigger-map GLOB (trigger_batch_leads *_companies.csv: trigger -> resolved domain);
         --copy-to DIR (copy every output there); --max-usd 5 (first-line generation guard, notional USD). env LEADOCEAN_API_KEY, OPENROUTER_API_KEY.
outputs: OUT/{vertical}_{STATE}.csv (+ _other.csv for rows whose company HQ / person state is outside STATES; split
         into _partN when > 2 MB), OUT/companies.csv (every company with outcome), OUT/funnel.md.
usage:   python3 execution/lead_sourcing/import_list_leads.py --job medtech:CA,TX,NY:in.csv --out .tmp/x
         python3 execution/lead_sourcing/import_list_leads.py ... --offline      # rebuild from caches (no network)
Directive: directives/lead_sourcing/import_list_leads.md
Spend: company sites, DNS-over-HTTPS, openFDA/USAspending re-checks: free. LeadOcean people search bills fair-use
       records (no ceiling), capped by --max-lo. Jev ~$0.00002/call, capped by --max-jev, ledgered in
       .tmp/jev_ledger.jsonl. Never calls Reoon, Prospeo, Instantly or any sender; no SMTP.
"""

from __future__ import annotations

import argparse, csv, datetime as dt, glob, hashlib, json, re, shutil, sys, threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "execution" / "lead_sourcing"))
sys.path.insert(0, str(ROOT / "execution" / "gtm_icp_filters"))
load_dotenv(ROOT / ".env")

import trigger_batch_leads as tb  # noqa: E402
from leadocean_leads import LeadOcean, has_mx, jload, jsave, norm_domain  # noqa: E402
from execution.modules.pipeline_utils import csv_safe_row  # noqa: E402

mt = tb.mt
_lock = threading.Lock()
TODAY = dt.date.today()
EMAIL_RE = re.compile(r"^[a-z0-9._%+'\-]+@[a-z0-9.\-]+\.[a-z]{2,}$")
FREE_MAIL = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "aol.com", "icloud.com", "msn.com", "live.com",
             "comcast.net", "att.net", "sbcglobal.net", "verizon.net", "me.com", "protonmail.com"}

# ---- industry gate: keep outright / ask Jev / drop (anything not listed is asked)
INDUSTRY = {
    "medtech": {
        "keep": {"medical devices"},
        "drop": {"venture capital & private equity", "financial services", "information technology & services",
                 "investment management", "investment banking", "insurance", "banking", "medical practice",
                 "staffing & recruiting", "management consulting", "logistics & supply chain",
                 "transportation/trucking/railroad", "package/freight delivery", "nonprofit organization management",
                 "retail", "marketing & advertising", "individual & family services", "construction", "real estate",
                 "accounting", "legal services", "law practice", "mental health care", "hospitality",
                 "public relations & communications", "market research", "human resources", "higher education",
                 "government administration", "education management"},
        "question": ("Does this company design or manufacture its own medical devices, diagnostic tests/instruments or "
                     "medical equipment?",
                     "it makes medical devices, diagnostics, surgical or medical equipment (a manufacturer/developer)",
                     "it is a hospital, clinic or care provider, pharmacy, drug developer, distributor or reseller only, "
                     "software/IT services, investor, staffing, consulting or anything else that does not make devices"),
    },
    "construction": {
        "keep": {"construction", "civil engineering"},
        "drop": {"information technology & services", "financial services", "venture capital & private equity",
                 "insurance", "professional training & coaching", "staffing & recruiting", "marketing & advertising",
                 "investment management", "computer software"},
        "question": ("Does this company build: is it a general contractor, design-build firm, construction manager, "
                     "home builder or specialty trade contractor that performs construction work itself?",
                     "it performs construction (general/design-build contractor, builder, construction manager or a "
                     "specialty trade such as electrical, mechanical, roofing, concrete, steel)",
                     "it is a broker, property manager, investor/developer that hires builders, architect or designer "
                     "that does not build, materials manufacturer or supplier, software or any non-construction firm"),
    },
}
JEV_INDUSTRY_NOUL = 0.6

# ---- homepage facts
COPYRIGHT = re.compile(r"(?:©|&copy;|\(c\)|copyright)\s*(?:©|\(c\))?\s*((?:19|20)\d{2})(?:\s*[-–—]\s*((?:19|20)\d{2}))?",
                       re.I)
GENERATOR = re.compile(r"<meta[^>]+name=[\"']generator[\"'][^>]*content=[\"']([^\"']+)|"
                       r"<meta[^>]+content=[\"']([^\"']+)[\"'][^>]*name=[\"']generator[\"']", re.I)
VIEWPORT = re.compile(r"<meta[^>]+name=[\"']viewport[\"']", re.I)
FOOTER = re.compile(r"<footer\b.*?</footer>", re.I | re.S)
MAILDOM = re.compile(r"[a-z0-9._%+\-]+@([a-z0-9\-]+(?:\.[a-z0-9\-]+)+\.?[a-z]{2,})", re.I)
CMS_OLD = [  # (regex on generator content, display name, is_old(version_tuple))
    (re.compile(r"^wordpress\s+(\d+)\.(\d+)(?:\.(\d+))?", re.I), "WordPress", lambda v: v[0] < 6),
    (re.compile(r"^drupal\s+(\d+)", re.I), "Drupal", lambda v: v[0] <= 7),
    (re.compile(r"^joomla!?\s*(\d+)\.(\d+)", re.I), "Joomla", lambda v: v[0] <= 3),
]
PTYPES = ["trigger_fda", "trigger_award", "site_copyright", "site_cms", "site_viewport", "company_description", "none"]

# ---- construction: bare VP titles (operator decision 2026-11-17). Ranked after chief exec and growth leads.
BARE_VP = re.compile(r"^(?:(?:senior|sr|executive|exec)\s+)?(?:vice president|vp)$|^(?:svp|evp)$")
RANK = {**tb.RANK_OF, "vp_general": 3}


def bare_vp(title: str) -> bool:
    t = re.sub(r"\s+", " ", re.sub(r"[^a-z ]+", " ", (title or "").lower().replace("-", " "))).strip()
    return bool(BARE_VP.match(t))


# ---- company_description first line (operator decision 2026-11-17, option a)
DESC_PROMPT_VERSION = "v1"
DESC_BATCH = 25
DESC_CHAIN = (("claude-sonnet-5-5", "low"),)  # bulk tier on the subscription
DESC_SUPPORTED_MIN, DESC_OPINION_MAX = 0.7, 0.3
DESC_BANNED = re.compile(r"\b(leading|innovative|premier|top|best|great|impressive|amazing|world[- ]class|trusted|"
                         r"needs?|needed|needing|struggl\w*|grow|grows|growing|growth|scale|scales|scaling)\b", re.I)
DESC_SYSTEM = """You write the first line of a cold email from a company's OWN description. Return JSON only.

Input: a JSON array of companies: {"id", "company", "opener", "description"}.
Output: a JSON array with one object per input, same order: {"id": <id>, "first_line": "<line or empty>"}.

Hard rules for first_line:
- One sentence, 8-22 words, ends with a period. Start EXACTLY with the given opener followed by the company name as
  given: opener "Saw that" -> "Saw that {company} ...", opener "Noticed" -> "Noticed {company} ...".
- State only WHAT THE COMPANY DOES / MAKES / BUILDS / WHERE, taken from its description. Prefer the most specific
  thing stated (a product line, project type, niche, region) over a generic summary.
  Good: "Saw that Acme Builders specializes in tilt-up warehouses across the Central Valley."
- NEVER: claims about intent, needs, plans, growth, pain or their website; praise or adjectives of quality
  (leading, innovative, premier, top, best, great, trusted, impressive, quality, award-winning...); numbers, years,
  awards or client names unless the description states them verbatim; anything not in the description. Do not use
  the words need, struggle, grow, growth or scale. No questions, no exclamation marks, plain ASCII punctuation only,
  no em dashes, no quotes.
- Write in plain present tense ("builds", "makes", "designs", "focuses on", "works on", "specializes in").
- Aim for 10-18 words: name the one or two most specific things, not every item in a list. Avoid "-scale" compounds
  (large-scale, utility-scale): say "large" or drop it.
- An input may carry "fix": the reason an earlier line was rejected. Write a new line that avoids it.
- If the description is missing, too vague ("we provide quality services"), a list of buzzwords with no concrete
  activity, or clearly about a different company, return "first_line": "".
"""

OUT_COLS = ["first_name", "last_name", "email", "title", "company_display", "company_casual", "website", "city", "state", "employees",
            "linkedin", "vertical", "email_check", "email_tier", "personalization_type", "first_line", "evidence",
            "trigger_date", "trigger_subject", "trigger_id", "trigger_url"]
CO_COLS = ["vertical", "company", "company_display", "company_casual", "casual_source", "domain", "state", "employees", "industry", "contacts_in",
           "contacts_out", "outcome", "personalization_type", "first_line", "evidence"]
STEPS = ["raw rows", "unique email + person", "has company domain", "not on drop list",
         "headcount in range", "not public (market cap)", "industry fits", "buyer title", "not a role inbox",
         "email on company domain", "not public (homepage listing)", "email check passed", "cap 2 per company",
         "US headquarters", "maker / builder fit"]

# Fit cleanup (operator hand-read 2026-11-17): keep makers / builders only. One Jev call per company: a noul gates
# (drop below FIT_MIN), a choice labels the reason counted in funnel.md.
FIT_MIN = 0.5  # below: drop unless the kind pick says maker / builder (conf >= FIT_KIND_CONF)
FIT_SOFT, FIT_KIND_CONF = 0.65, 0.6  # below FIT_SOFT: drop when the kind pick names a non-maker kind
FIT = {
    "medtech": (
        "Is this company a maker: does it design, develop or manufacture its own medical products?",
        "the description says the company designs, develops, makes or manufactures medical or health products itself "
        "(devices, implants, instruments, diagnostics, equipment, supplies, digital health or medical software), "
        "including contract manufacturers, device reprocessors, custom orthotics / prosthetics fabricators and "
        "medical software or AI products",
        "the company is an incubator, accelerator, venture capital or private equity firm, an independent sales-rep "
        "agency, a distributor or reseller of other companies' products only, a consultancy, a regulatory / CRO / "
        "service provider, staffing, or a clinic, hospital or care provider that makes no products"),
    "construction": (
        "Is this company a builder: does it perform construction work itself?",
        "the company builds: general contractor, construction manager or design-build firm, home or commercial "
        "builder, or specialty trade contractor (electrical, mechanical, plumbing, HVAC, roofing, concrete, steel, "
        "glazing, paving, excavation, restoration, controls / systems installation...), or it manufactures or "
        "fabricates construction or building products, materials or equipment",
        "the company does not build: an engineering, architecture, design, inspection, testing or consulting firm "
        "without construction work, a construction-management / estimating / safety / permitting consultant, a "
        "distributor, dealer, supplier or sales-rep agency that makes nothing, a labor union, trade association or "
        "training nonprofit, an incubator or accelerator, a venture capital or private equity firm, or staffing"),
}
FIT_KIND = {"maker_or_builder": "makes or manufactures products (incl. building products or medical software) or "
                                "performs construction work itself",
            "incubator_accelerator": "incubator, accelerator or startup studio",
            "sales_rep_distributor": "sales-rep agency, distributor, reseller or supplier only",
            "consultancy_engineering_design": "consulting, engineering, architecture, design, testing or inspection "
                                              "firm that does not build or make",
            "investor_vc_pe": "venture capital, private equity or investment firm",
            "union_association": "labor union or trade association",
            "service_provider": "service provider (care, staffing, regulatory, CRO, software services) making no "
                                "product and doing no construction",
            "none": "none of these"}


# ------------------------------------------------------------------ helpers
REGIONAL = re.compile(r"\b(regional|region|territory|district|area (sales|manager|director|vice)|emea|apac|latam|"
                      r"middle east|africa|asia|europe|latin america|north america|canada|mexico|"
                      r"(north|south|east|west)(east|west)?(ern)? (us|region|zone|division))\b", re.I)
MID_LEGAL = re.compile(r",?\s+(inc|llc|corp|ltd)\.?(?=\s+\S)", re.I)


def clean_company(name: str) -> str:
    """Record name for display: marks dropped, text after a mid-string legal suffix dropped ("Acme Inc. Acme")."""
    s = re.sub(r"[\u00ae\u2122\u00a9]", "", name or "").strip()
    m = MID_LEGAL.search(s)
    if m and set(mt.norm_tokens(s[m.end():])) & set(mt.norm_tokens(s[:m.start()])):
        s = s[:m.start()]  # the tail repeats the name: a merged record, not part of the brand
    return s.strip(" ,-|")


def fix_name_case(s: str) -> str:
    """O'hara -> O'Hara, El-gohary -> El-Gohary (only a lowercase letter right after ' or - is raised)."""
    return re.sub(r"(?<=[A-Za-z]['’\-])([a-z])", lambda m: m.group(1).upper(), s or "")


# ------------------------------------------------------------------ company_casual (operator 2026-11-17: "Brandon
# Lever LLC has to be referred to as Brandon Lever only in mails and communication")
CASUAL_LEGAL = re.compile(r"[,\s]+(inc|incorporated|llc|l\.\s?l\.\s?c|corp|corporation|co|company|ltd|limited|lp|l\.p|"
                          r"llp|pllc|pc|p\.c|plc|gmbh|ag|ab|bv|b\.v|s\.a|sa|srl|pty|pte|oy|as|a/s|aps)\.?$", re.I)
CASUAL_GENERIC = {"group", "holdings", "holding", "enterprises", "enterprise", "services", "service", "solutions",
                  "associates", "industries", "international", "intl", "usa", "us", "u.s.", "america", "americas",
                  "technologies", "technology"}
CASUAL_TAG = re.compile(r"\s+[|–—/]\s+|\s+-\s+|\s*\|\s*")
JEV_CASUAL_CONF = 0.6


def _initial_tok(w: str) -> bool:
    k = tb._key(w)
    return len(k) <= 3 and (w.isupper() or "." in w or len(k) == 1)


def casual_weak(s: str) -> bool:
    """True when `s` alone may not identify a company: initials only, or one plain word (a surname, first name or
    dictionary word cannot be told apart without a word list, so every single plain word counts as weak)."""
    toks = [w for w in tb._TOK.findall(s) if tb._key(w)]
    if not toks or all(_initial_tok(w) for w in toks):
        return True
    if len(toks) == 1:
        w = toks[0]
        coined = bool(re.search(r"\d", w)) or any(c.isupper() for c in w[1:]) and any(c.islower() for c in w)
        return not coined
    return False


def casual_strip(raw: str) -> tuple[str, str]:
    """(conservative, aggressive) casual forms of a record name. Conservative keeps a generic tail word when removing
    it would leave a weak name; aggressive always removes it (a candidate for the Jev pick only)."""
    s = html_unescape(clean_company(raw))
    def initials(x: str) -> bool:
        toks = [w for w in tb._TOK.findall(x) if tb._key(w)]
        return bool(toks) and all(_initial_tok(w) for w in toks)

    paren = re.match(r"^(.*?)\s*\(([^)]+)\)\s*$", s)
    if paren and initials(paren.group(1)) and len(paren.group(2).split()) >= 2:
        s = paren.group(2)  # "BCI (Berkeley Cement, Inc.)" -> the spelled-out name
    parts = CASUAL_TAG.split(s)
    if len(parts) > 1 and initials(parts[0]) and len(parts[1].split()) >= 2:
        s = parts[1]  # "E2 - Endovascular Engineering", "SBI | Siegfried's Basement" -> the spelled-out name
    elif len(parts) > 1 and len(tb._key(parts[0])) >= 2:
        s = parts[0]  # "CARPL - Radiology AI Platform", "ClearFlow | Improve ..." -> the name before the tagline
    by = re.split(r",?\s+by\s+", s, maxsplit=1, flags=re.I)
    if len(by) == 2 and len(tb._key(by[0])) >= 3:
        s = by[0]  # "Perfect Derma Peel by Bella Medical Products", "Veev, By Lennar" -> the brand
    m = re.search(r"\b(?:d/?b/?a|doing business as)\b\.?\s+(.+)$", s, re.I)
    if m:
        s = m.group(1)
    s = re.sub(r"^the\s+", "", s.strip(), flags=re.I)
    s = re.sub(r"\s*\([^)]*\)", "", s).strip()  # "Aidite (Qinhuangdao) Technology"
    full = s
    while True:
        t = CASUAL_LEGAL.sub("", s).strip(" ,")
        t = re.sub(r"\s*(?:&|\+|\band)$", "", t, flags=re.I).strip(" ,")
        if t == s:
            break
        s = t
    if casual_weak(s):
        co = re.match(r"(.*?&\s*(?:co\b|company\b))", full, re.I)
        if co:  # "MG & Company": the "& Co" is part of the brand when the rest is initials / one word
            s = co.group(1).strip()
        elif s and all(_initial_tok(w) for w in s.split()) and full != s:
            nxt = full[len(s):].strip(" ,").split()
            w = nxt[0].strip(",.") if nxt else ""
            if w.lower() in ("corp", "corporation", "company", "co"):
                s = f"{s} {w.capitalize() if w.isupper() else w}"  # "CM CORP" -> "CM Corp"; "ZDG, LLC" -> "ZDG"
    s = re.sub(r"\.com$", "", s, flags=re.I) if not casual_weak(re.sub(r"\.com$", "", s, flags=re.I)) else s
    cons = aggr = s
    while True:
        toks = aggr.split()
        if len(toks) < 2 or toks[-1].lower().strip(",.") not in CASUAL_GENERIC:
            break
        aggr = " ".join(toks[:-1]).strip(" ,&")
        aggr = re.sub(r"\s*(?:&|\+|\band)$", "", aggr, flags=re.I).strip(" ,")
        if not casual_weak(aggr):
            cons = aggr
    return cons, aggr


def casual_case(s: str, raw: str, texts: list[str]) -> str:
    """Casing as the company writes itself: its pages first, else deterministic fixes (ALL-CAPS records capitalised
    with acronyms kept upper, spaced single initials joined, a lowercase first word raised)."""
    base_raw = CASUAL_LEGAL.sub("", clean_company(raw)).strip(" ,.")
    caps = base_raw.isupper() and len(tb._key(base_raw)) > 3
    if caps:
        s = " ".join(w if len(tb._key(w)) <= 2 or re.search(r"\d", w) or w in ("USA", "U.S.") else w.capitalize()
                     for w in s.split())
    s = re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", s)  # "E A Davidovits" -> "EA Davidovits"
    out = tb.recase_name(s, caps, texts)
    if (len(out.split()) != len(s.split()) or (out.islower() and not s.islower())
            or out.replace("'", "") == s.replace("'", "").lower() or "-" in out and "-" not in s
            or any(sw[:1].isupper() and ow[:1].islower() and ow.lower() not in ("and", "of", "the", "for", "by")
                   for sw, ow in zip(s.split()[1:], out.split()[1:]))):  # "Allwin Medical devices"
        out = s  # a URL slug or handle on the page ("alpha mechanical", "think-construction"), not a spelling
    blob = " ".join(texts)
    toks = out.split()
    for i, w in enumerate(toks):  # a word the record and the site both write in capitals is an acronym (IBEW, WHPM)
        k = re.sub(r"[^A-Za-z]", "", w)
        if k and not w.isupper() and len(k) <= 5 and re.search(rf"\b{re.escape(w.upper())}\b", blob) \
                and w.upper() in base_raw:
            toks[i] = w.upper()
    out = " ".join(toks)
    if out.split()[0].islower() and not re.search(rf"\b{re.escape(out.split()[0])}\b", blob):
        out = out[:1].upper() + out[1:]  # "mai Services" -> "Mai Services" unless the site writes it lowercase
    return out


def casual_candidates(raw: str, cdisp: str, home_static: dict, dom: str, texts: list[str]) -> dict:
    """Deterministic casual name plus the options Jev picks from when they disagree."""
    cons, aggr = casual_strip(raw)
    rule = casual_case(cons, raw, texts)
    opts = {"rule": rule}
    if tb._key(aggr) != tb._key(cons):
        opts["short"] = casual_case(aggr, raw, texts)
    dom_key = tb._key(mt.domain_root(dom))
    base_tok = set(mt.norm_tokens(cons)) - tb.GENERIC_NAME
    for i, c in enumerate(tb.homepage_name_candidates(home_static)[:6]):
        hc, ha = casual_strip(c)
        if (c.isupper() and len(tb._key(c)) > 4) or (c.islower() and not rule.islower()):
            continue  # an all-caps banner is styling, not the spelling
        if tb._key(hc) == tb._key(rule) or tb._key(ha) == tb._key(rule):
            if hc != rule and not hc.isupper() and tb._key(hc) == tb._key(rule) and (not hc.islower() or rule.islower()) \
                    and len(hc.split()) == len(rule.split()) and not any(
                        sw[:1].isupper() and hw[:1].islower() for sw, hw in zip(rule.split()[1:], hc.split()[1:])):
                opts["rule"] = rule = hc  # the homepage's own spelling of the same name (L.C. -> LC)
            continue
        shares = bool(set(mt.norm_tokens(hc)) & base_tok) or (len(tb._key(hc)) >= 4 and tb._key(hc) in dom_key)
        if shares and not any(tb._key(hc) == tb._key(v) for v in opts.values()):
            opts[f"home{i}"] = hc
    if cdisp and not any(tb._key(cdisp) == tb._key(v) for v in opts.values()) and not re.search(r"[(|]| - ", cdisp):
        opts["display"] = cdisp
    return opts


def us_state(s: str) -> str:
    """Two-letter code for a US state name/code; '' when not a US state."""
    c = tb.state_code(s or "")
    return c if c in tb.US_STATES.values() else ""


def row_state(r: dict) -> tuple[str, str]:
    """(state, source): company HQ state when the company row has one, else the person's state."""
    cs = (r.get("Company State") or "").strip()
    cc = (r.get("Company Country") or "").strip()
    if cs:
        code = us_state(cs) if cc in ("", "United States") else ""
        return (code or cs), "company"
    return us_state(r.get("State") or "") or (r.get("State") or "").strip(), "person"


def clean_html_text(html: str) -> str:
    return tb._visible_text(html)[1]


def parse_page(html: str, final_url: str) -> dict:
    """Facts from one HTML document (static or rendered)."""
    text = clean_html_text(html)
    foot = " ".join(clean_html_text(m.group(0)) for m in FOOTER.finditer(html or ""))
    zone = foot if COPYRIGHT.search(foot) else text[-1500:]
    cr = []
    for m in COPYRIGHT.finditer(zone):
        after = zone[m.end():m.end() + 14]
        if re.match(r"\s*[-–—]?\s*(present|current|today|now|date)\b", after, re.I):
            continue  # "© 2018-present" renders as an open range: not a stale year
        tail = re.match(r"[\s,\-–—]*((?:19|20)\d{2})\b", after)  # "© 2012 2021": the later year is the shown one
        y = max(int(m.group(2) or m.group(1)), int(tail.group(1)) if tail else 0)
        if 1990 <= y <= TODAY.year:
            cr.append({"year": y, "snippet": re.sub(r"\s+", " ", zone[max(0, m.start() - 20):m.end() + 40]).strip()})
    gens = [html_unescape(a or b) for a, b in GENERATOR.findall(html or "")]
    title = tb._visible_text(html)[0]
    return {"meta_description": meta_content(html, "description"), "og_description": meta_content(html, "og:description"),
            "final_url": final_url, "text": text[:20000], "title": re.sub(r"\s+", " ", title or "")[:160],
            "og_site_name": tb._meta(html, "og:site_name"), "logo_alt": tb._logo_alt(html),
            "viewport": bool(VIEWPORT.search(html or "")), "generator": gens[:4], "copyright": cr[:6],
            "mail_domains": sorted({d.lower().rstrip(".") for d in MAILDOM.findall(html or "")})[:30],
            "ir_links": tb._page_record(final_url, final_url, html, text).get("ir_links", [])}


def html_unescape(s: str) -> str:
    import html as h
    return h.unescape(s or "").strip()


def static_get(dom: str) -> dict:
    for url in (f"https://{dom}", f"https://www.{dom}"):
        try:
            h = requests.get(url, headers={"User-Agent": mt.UA}, timeout=20)
        except requests.RequestException as exc:
            last = {"error": type(exc).__name__}
            continue
        if h.status_code < 400 and h.text:
            p = parse_page(h.text[:3_000_000], h.url)
            p["status"] = h.status_code
            return p
        last = {"error": f"HTTP {h.status_code}"}
    return last


def render_many(urls: list[str]) -> list[dict]:
    jobs = [{"url": u, "mode": "full", "no_mobile": True, "timeout_ms": 20000} for u in urls]
    out = []
    for r in mt.pw_fetch(jobs):
        if r.get("error") or (r.get("status") or 0) >= 400 or not r.get("html"):
            out.append({"error": (r.get("error") or f"HTTP {r.get('status')}")[:120]})
        else:
            p = parse_page(r["html"], r.get("final_url") or r["url"])
            p["status"] = r.get("status")
            out.append(p)
    return out


def max_copyright(p: dict) -> dict | None:
    cr = p.get("copyright") or []
    return max(cr, key=lambda c: c["year"]) if cr else None


def old_cms(p: dict) -> tuple[str, str] | None:
    for g in p.get("generator") or []:
        for rx, name, is_old in CMS_OLD:
            m = rx.search(g)
            if m:
                v = tuple(int(x) for x in m.groups() if x)
                if is_old(v):
                    return f"{name} {'.'.join(str(x) for x in v[:2])}", g
    return None


def candidates(p: dict, cr_max: int) -> list[str]:
    out = []
    c = max_copyright(p)
    if c and c["year"] <= cr_max:
        out.append("site_copyright")
    if old_cms(p):
        out.append("site_cms")
    if p.get("text") and not p.get("viewport"):
        out.append("site_viewport")
    return out


def site_fact(dom: str, e: dict, cr_max: int, name: str = "") -> dict:
    """Pick the first confirmed fact in brief order. A fact counts only when the rendered page shows it.
    `name` is the company_casual used in the line (the domain when absent)."""
    name = name or dom
    s, r = e.get("static") or {}, e.get("rendered") or {}
    if not r or r.get("error"):
        return {}
    if mt.domain_root(norm_domain(r.get("final_url") or "")) != mt.domain_root(dom):
        return {}  # homepage redirects to another site: a fact about it is not a fact about {dom}
    for kind in ["site_copyright", "site_cms", "site_viewport"]:
        if kind not in candidates(r, cr_max) or (s.get("text") and len(s["text"]) >= 200 and kind not in
                                                  candidates(s, cr_max)):
            continue  # both views must agree when the static page was readable
        url = r.get("final_url") or f"https://{dom}"
        if kind == "site_copyright":
            c = max_copyright(r)
            line = f"I noticed the copyright year in the {name} site footer is still {c['year']}."
            return {"type": kind, "first_line": line, "evidence": f"{url} | footer: \"{c['snippet'][:140]}\""}
        if kind == "site_cms":
            cms, g = old_cms(r)
            line = f"I noticed the {name} homepage is still built on {cms}."
            return {"type": kind, "first_line": line, "evidence": f"{url} | <meta name=\"generator\" content=\"{g[:80]}\">"}
        if len(r.get("text") or "") < 200:
            continue
        line = f"I noticed the {name} homepage has no mobile viewport tag, so phones get the desktop layout."
        return {"type": kind, "first_line": line, "evidence": f"{url} | no <meta name=\"viewport\"> in rendered HTML"}
    return {}


# ------------------------------------------------------------------ company_description first line
def meta_content(html: str, prop: str, limit: int = 500) -> str:
    for pat in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]*content=["\']([^"\']*)',
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{prop}["\']'):
        m = re.search(pat, html or "", flags=re.I)
        if m:
            return re.sub(r"\s+", " ", html_unescape(m.group(1))).strip()[:limit]
    return ""


def meta_get(dom: str, url: str) -> dict:
    """Homepage meta description / og:description (static GET, free). {} on failure (re-run retries)."""
    for u in [x for x in (url, f"https://{dom}", f"https://www.{dom}") if x]:
        try:
            h = requests.get(u, headers={"User-Agent": mt.UA}, timeout=15)
        except requests.RequestException:
            continue
        if h.status_code < 400 and h.text:
            if mt.domain_root(norm_domain(h.url)) != mt.domain_root(dom):
                return {"url": h.url, "description": "", "og_description": "", "note": "redirects off-domain"}
            html = h.text[:2_000_000]
            return {"url": h.url, "description": meta_content(html, "description"),
                    "og_description": meta_content(html, "og:description")}
    return {}


def _clean_desc(x: str) -> str:
    return re.sub(r"\s+", " ", (x or "").replace("’", "'")).strip()


def company_description(r: dict, home: dict) -> tuple[str, str, str]:
    """(description, keywords, source) for one company: the export's own description first, homepage meta second."""
    short, seo = _clean_desc(r.get("Company Short Description")), _clean_desc(r.get("Company SEO Description"))
    parts = [short] + ([seo] if seo and seo[:80].lower() not in short.lower() else [])
    desc = " ".join(p for p in parts if p)[:1500]
    kw = _clean_desc(r.get("Keywords"))[:400]
    if len(desc) >= 40:
        return desc, kw, "export description"
    meta = home.get("meta") or {}
    st = home.get("static") or {}
    md = [meta.get("description") or st.get("meta_description") or "",
          meta.get("og_description") or st.get("og_description") or ""]
    md = [m for i, m in enumerate(md) if m and (i == 0 or m[:60].lower() not in md[0].lower())]
    mdesc = _clean_desc(" ".join(md))
    if len(mdesc) >= 40:
        return mdesc[:1000], kw, f"homepage meta ({meta.get('url') or st.get('final_url') or ''})"
    return desc, kw, "export description"


def desc_opener(dom: str) -> str:
    return "Saw that" if int(hashlib.sha1(dom.encode()).hexdigest(), 16) % 2 == 0 else "Noticed"


def desc_key(dom: str, cdisp: str, desc: str, kw: str) -> str:
    h = hashlib.sha1(f"{DESC_PROMPT_VERSION}|{cdisp}|{desc}|{kw}".encode()).hexdigest()[:16]
    return f"{dom}|{h}"


def _parse_json_array(text: str) -> list:
    t = re.sub(r"^```(?:json)?|```$", "", (text or "").strip(), flags=re.M).strip()
    i, j = t.find("["), t.rfind("]")
    if i < 0 or j < i:
        raise ValueError("no JSON array in reply")
    data = json.loads(t[i:j + 1])
    if not isinstance(data, list):
        raise ValueError("reply is not a list")
    return data


def generate_lines(items: list[dict], cache: dict, max_usd: float, workers: int = 4) -> dict:
    """items: {key, dom, company, opener, description}. Batches of DESC_BATCH to the subscription bulk tier.
    Writes cache[key] = {"line", "model"}; returns stats. Stops new calls once notional spend >= max_usd."""
    from execution.modules import llm_client as llm
    todo = [it for it in items if it["key"] not in cache]
    batches = [todo[i:i + DESC_BATCH] for i in range(0, len(todo), DESC_BATCH)]
    stats = {"calls": 0, "failed": 0, "skipped_budget": 0, "start_usd": llm.notional_spent()}

    def run(batch: list[dict]) -> None:
        if llm.notional_spent() - stats["start_usd"] >= max_usd:
            with _lock:
                stats["skipped_budget"] += 1
            return
        payload = [{"id": i, "company": it["company"], "opener": it["opener"],
                    "description": (it["description"] + (f" Keywords: {it['keywords']}" if it["keywords"] else ""))[:1800],
                    **({"fix": it["fix"]} if it.get("fix") else {})}
                   for i, it in enumerate(batch)]
        try:
            reply = llm._claude_cli_completion(DESC_SYSTEM, json.dumps(payload, ensure_ascii=False), chain=DESC_CHAIN)
            data = _parse_json_array(reply)
        except Exception as exc:  # helper degrades: those companies stay `none` this run, re-run retries
            print(f"  first-line batch failed: {str(exc)[:160]}", flush=True)
            with _lock:
                stats["calls"] += 1
                stats["failed"] += 1
            return
        got = {}
        for d in data:
            try:
                got[int(d.get("id"))] = str(d.get("first_line") or "").strip()
            except (TypeError, ValueError, AttributeError):
                continue
        with _lock:
            stats["calls"] += 1
            for i, it in enumerate(batch):
                if i in got:
                    cache[it["key"]] = {"line": got[i], "model": DESC_CHAIN[0][0]}

    if batches:
        print(f"first-line generation: {len(todo)} companies in {len(batches)} calls", flush=True)
        with ThreadPoolExecutor(max_workers=workers) as pool:
            list(pool.map(run, batches))
    stats["usd"] = round(llm.notional_spent() - stats["start_usd"], 4)
    return stats


def line_rule_check(line: str, cdisp: str, desc: str) -> str:
    """Deterministic gate. Returns '' when the line passes, else the reject reason."""
    if not line:
        return "generator: no usable description"
    if not (line.startswith(f"Saw that {cdisp} ") or line.startswith(f"Noticed {cdisp} ")):
        return "rule: wrong opener / company name"
    if not line.isascii():
        return "rule: non-ASCII character"
    if "?" in line or "!" in line or not line.endswith("."):
        return "rule: punctuation"
    n = len(line.split())
    if not 8 <= n <= 22:
        return f"rule: {n} words (8-22)"
    rest = line.replace(cdisp, " ", 1)
    if re.search(r"[.;]\s+[A-Z]", rest[:-1]) and not re.search(r"\b(?:[A-Z]\.){2,}", rest):
        return "rule: more than one sentence"
    m = DESC_BANNED.search(rest)
    if m:
        return f"rule: banned word ({m.group(0).lower()})"
    for num in re.findall(r"\d[\d,.]*", rest):
        if num.rstrip(".,") not in desc:
            return f"rule: number not in description ({num})"
    return ""


def evidence_snippet(line: str, desc: str, source: str) -> str:
    sents = [x.strip() for x in re.split(r"(?<=[.!?])\s+", desc) if x.strip()] or [desc]
    lt = set(re.findall(r"[a-z]{4,}", line.lower()))
    best = max(sents, key=lambda x: len(lt & set(re.findall(r"[a-z]{4,}", x.lower()))))
    return f"{source}: {best[:300]}"


def verify_lines(items: list[dict], jev_cache: dict, budget: list[int], jev_on: bool) -> None:
    """Independent check (not the generator): two Jev nouls per line, cached by line + description."""
    from execution.modules import jev_client as jev
    q = {"supported": jev.noul(
            "Every fact in first_line is stated in description.",
            "every claim in first_line (what the company does, makes, builds, where, any name or number) is stated "
            "in the description or its keywords",
            "first_line says something the description does not state, or describes a different company"),
         "opinion": jev.noul(
            "first_line contains praise, a claim about the company's needs or intent, or an opinion.",
            "first_line praises the company, uses a quality adjective, or claims what it needs, wants, plans or "
            "struggles with, or gives an opinion",
            "first_line only states plain facts about what the company does, makes, builds or where")}
    for it in items:
        it["jkey"] = "descline|" + hashlib.sha1(f"{it['line']}|{it['description']}|{it['keywords']}".encode()).hexdigest()[:20]
    todo = [it for it in items if it["jkey"] not in jev_cache]
    if todo and jev_on:
        todo = todo[:max(0, budget[0])]
        states = [{"company": it["company"], "description": it["description"][:1500],
                   "keywords": it["keywords"][:400], "first_line": it["line"]} for it in todo]
        res = jev.decide_many(states, q, workers=8)
        budget[0] -= len(todo)
        for it, rr in zip(todo, res):
            jev.append_ledger({"script": "import_list_leads", "step": "first_line_verify", "cost": rr.cost_usd})
            if rr.error:
                continue  # not cached: re-run retries; this run the line is dropped
            jev_cache[it["jkey"]] = {"supported": rr.noul("supported"), "opinion": rr.noul("opinion")}


# ------------------------------------------------------------------ triggers
def load_triggers(vertical: str, states: list[str], a) -> list[dict]:
    if vertical == "medtech":
        try:
            return tb.medtech_triggers(states, a.fda_since, offline=True)
        except SystemExit as exc:
            print(f"no cached FDA pull ({exc}); medtech triggers skipped")
            return []
    if vertical != "construction":
        return []
    floor = (TODAY - dt.timedelta(days=a.award_days)).isoformat()
    by: dict[str, dict] = {}
    for f in sorted(glob.glob(str(ROOT / a.award_csv))):
        for r in csv.DictReader(open(f, newline="", encoding="utf-8")):
            if r["state"] not in states or r["action_date"] < floor:
                continue
            k = tb.norm_name(r["recipient"]) + "|" + r["state"]
            if k in by and by[k]["date"] >= r["action_date"]:
                continue
            by[k] = {"vertical": "construction", "org": r["recipient"], "state": r["state"], "city": "",
                     "key": r["award_id"], "date": r["action_date"], "award_id": r["award_id"], "agency": r["agency"],
                     "agency_raw": r["subagency_raw"], "amount": r["amount"], "description": r["description"],
                     "parent": r["parent"], "uei": r["uei"], "evidence_url": r["evidence_url"], "n_triggers": 1}
    return list(by.values())


def trigger_index(vertical: str, trigs: list[dict], a) -> tuple[dict, dict]:
    """(domain -> trigger, 'normname|ST' -> trigger). Domains come from earlier resolved trigger batches."""
    by_key = {t["key"]: t for t in trigs}
    by_name = {}
    for t in trigs:
        for n in tb.name_variants(t["org"]):
            by_name.setdefault(f"{n}|{t['state']}", t)
    by_dom = {}
    for f in sorted(glob.glob(str(ROOT / a.trigger_map))):
        for r in csv.DictReader(open(f, newline="", encoding="utf-8")):
            if r.get("vertical") == vertical and r.get("domain") and r.get("trigger_id") in by_key:
                by_dom.setdefault(norm_domain(r["domain"]), by_key[r["trigger_id"]])
    return by_dom, by_name


# ------------------------------------------------------------------ main
def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("inputs:")[0])
    ap.add_argument("--job", action="append", required=True, help="VERTICAL:STATES:PATH")
    ap.add_argument("--out", required=True)
    ap.add_argument("--drop-list", default="")
    ap.add_argument("--cache-dir", default=".tmp/import_list/cache")
    ap.add_argument("--min-emp", type=int, default=20)
    ap.add_argument("--max-emp", type=int, default=500)
    ap.add_argument("--max-fetch", type=int, default=5000)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--render-workers", type=int, default=8)
    ap.add_argument("--max-jev", type=int, default=3000)
    ap.add_argument("--max-lo", type=int, default=6000)
    ap.add_argument("--verifier-status-col", default="status",
                    help="column holding an email-verifier verdict; when present it replaces MX + LeadOcean checks")
    ap.add_argument("--verifier-keep", default="safe,catch_all", help="verifier statuses kept (= email_tier)")
    ap.add_argument("--copyright-max", type=int, default=2022)
    ap.add_argument("--fda-since", default="2026-08-01")
    ap.add_argument("--award-csv", default=".tmp/referral/triggers/construction/construction_triggers_*.csv")
    ap.add_argument("--award-days", type=int, default=90)
    ap.add_argument("--trigger-map", default=".tmp/referral/batch*/*_companies.csv")
    ap.add_argument("--offline", action="store_true", help="caches only: no fetch, Jev, MX or LeadOcean calls")
    ap.add_argument("--copy-to", default="")
    ap.add_argument("--max-usd", type=float, default=5.0,
                    help="budget guard for company_description first lines (notional USD of subscription calls)")
    a = ap.parse_args()

    cdir = ROOT / a.cache_dir
    out = ROOT / a.out
    out.mkdir(parents=True, exist_ok=True)
    paths = {k: cdir / f"{k}.json" for k in ("jev", "site", "pages", "home", "mx", "lo_person", "desc_line")}
    caches = {k: jload(p, {}) for k, p in paths.items()}

    def save() -> None:
        for k, p in paths.items():
            jsave(p, caches[k])

    drop = jload(ROOT / a.drop_list, {}) if a.drop_list else {}
    drop_dom = {norm_domain(d) for d in drop.get("domains", [])}
    drop_names = {tb.norm_name(n) for n in drop.get("names", [])}
    budget = [a.max_jev]
    desc_stats: dict[str, Counter] = {}
    llm_stats = {"calls": 0, "failed": 0, "skipped_budget": 0, "usd": 0.0}
    lo_budget = [a.max_lo]
    from execution.modules import jev_client as jev
    jev_on = not a.offline and jev.available()

    all_rows: list[dict] = []
    co_rows: list[dict] = []
    reports = []
    for spec in a.job:
        vertical, states_s, path = spec.split(":", 2)
        states = [s.strip().upper() for s in states_s.split(",") if s.strip()]
        rows = [dict(r) for r in csv.DictReader(open(ROOT / path, newline="", encoding="utf-8-sig"))]
        for r in rows:
            r["_v"] = vertical
            st, src = row_state(r)
            r["_state"] = st if st in states else "other"
            r["_state_raw"], r["_state_src"] = st, src
            r["_email"] = (r.get("Email") or "").strip().lower()
            r["_dom"] = norm_domain(r.get("Company Domain") or "") or norm_domain(r.get("Company Website") or "")
            r["_drop"], r["_step"] = "", len(STEPS)

        def kill(r: dict, step: str, reason: str) -> None:
            if not r["_drop"]:
                r["_drop"], r["_step"] = reason, STEPS.index(step)

        def alive() -> list[dict]:
            return [r for r in rows if not r["_drop"]]

        # 1. dedupe + domain + drop list
        seen_e, seen_p = set(), set()
        for r in rows:
            pk = (r.get("Person ID") or "").strip() or f"{r.get('First Name', '').lower()}|{r.get('Last Name', '').lower()}|{r['_dom']}"
            if r["_email"] and r["_email"] in seen_e:
                kill(r, STEPS[1], "duplicate email")
            elif pk in seen_p:
                kill(r, STEPS[1], "duplicate person")
            seen_e.add(r["_email"]); seen_p.add(pk)
        for r in alive():
            if not r["_dom"]:
                kill(r, STEPS[2], "no company domain")
            elif r["_dom"] in drop_dom or tb.norm_name(r.get("Company Name", "")) in drop_names:
                kill(r, STEPS[3], "on drop list")

        # 2. company gates
        cfg = INDUSTRY[vertical]
        for r in alive():
            try:
                emp = int(float((r.get("Employees Count") or "").replace(",", "")))
            except ValueError:
                emp = None
            r["_emp"] = emp
            if emp is None:
                kill(r, STEPS[4], "headcount blank")
            elif emp < a.min_emp:
                kill(r, STEPS[4], f"headcount < {a.min_emp}")
            elif emp > a.max_emp:
                kill(r, STEPS[4], f"headcount > {a.max_emp}")
            elif (r.get("Company Market Cap") or "").strip():
                kill(r, STEPS[5], "public (market cap listed)")
        ask: dict[str, dict] = {}
        for r in alive():
            ind = (r.get("Industry") or "").strip().lower()
            if ind in cfg["keep"]:
                continue
            if ind in cfg["drop"] or not ind:
                kill(r, STEPS[6], f"industry: {r.get('Industry') or 'blank'}")
                continue
            ask.setdefault(r["_dom"], r)
        todo = [d for d in ask if f"industry|{vertical}|{d}" not in caches["jev"]]
        if todo and jev_on:
            q, t, f = cfg["question"]
            todo = todo[:max(0, budget[0])]
            states_in = [{"company": ask[d].get("Company Name"), "domain": d, "linkedin_industry": ask[d].get("Industry"),
                          "description": ((ask[d].get("Company Short Description") or "") + " "
                                          + (ask[d].get("Company SEO Description") or ""))[:700],
                          "keywords": (ask[d].get("Keywords") or "")[:300]} for d in todo]
            res = jev.decide_many(states_in, {"fit": jev.noul(q, t, f)}, workers=8)
            budget[0] -= len(todo)
            for d, rr in zip(todo, res):
                caches["jev"][f"industry|{vertical}|{d}"] = {"noul": rr.noul("fit"), "error": (rr.error or "")[:200]}
                jev.append_ledger({"script": "import_list_leads", "step": "industry", "cost": rr.cost_usd})
            save()
        for r in alive():
            if r["_dom"] in ask:
                j = caches["jev"].get(f"industry|{vertical}|{r['_dom']}")
                if not j or j.get("error"):
                    kill(r, STEPS[6], "industry not confirmed (Jev unavailable)")
                elif j["noul"] < JEV_INDUSTRY_NOUL:
                    kill(r, STEPS[6], f"industry: {r.get('Industry')} (Jev no)")
                else:
                    r["_ind_note"] = f"Jev {j['noul']:.2f}"

        # 3. person gates: title + role inbox
        for r in alive():
            if vertical == "construction" and bare_vp(r.get("Title") or ""):
                cls, why = "vp_general", "rule: bare VP title (construction, operator 2026-11-17)"
            else:
                cls, why = tb.title_class(r.get("Title") or "", caches["jev"], budget, not jev_on)
            r["_cls"], r["_title_why"] = cls, why
            if cls not in RANK:
                kill(r, STEPS[7], "title: edge title, Jev not a buyer / unsure" if "Jev" in why else
                     "title: " + re.sub(r"\(.*?\)", "", why.split(": ", 1)[-1]).strip())
            elif REGIONAL.search(r.get("Title") or ""):
                kill(r, STEPS[7], "title: regional / territory role")
            elif tb.is_role_inbox(r["_email"]):
                kill(r, STEPS[8], "role inbox")
        save()

        # homepage static fetch for every company still alive (cached by domain)
        doms = sorted({r["_dom"] for r in alive()})
        new = [d for d in doms if d not in caches["home"]]
        if new and not a.offline:
            new = new[:a.max_fetch]
            print(f"[{vertical}] static fetch {len(new)} homepages ({len(doms) - len(new)} cached)", flush=True)

            def one(d: str) -> None:
                s = static_get(d)
                with _lock:
                    caches["home"][d] = {"static": s, "fetched": TODAY.isoformat()}

            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                for i, _ in enumerate(pool.map(one, new)):
                    if i and i % 200 == 0:
                        print(f"  static {i}/{len(new)}", flush=True)
                        jsave(paths["home"], caches["home"])
            jsave(paths["home"], caches["home"])

        # email domain alias + public listing on homepage
        for r in alive():
            ed = r["_email"].split("@")[-1] if "@" in r["_email"] else ""
            home = (caches["home"].get(r["_dom"]) or {}).get("static") or {}
            if ed in FREE_MAIL or not ed:
                kill(r, STEPS[9], "free-mail / no email domain")
            elif not (ed == r["_dom"] or ed.endswith("." + r["_dom"]) or r["_dom"].endswith("." + ed)
                      or mt.domain_root(ed) == mt.domain_root(r["_dom"]) or ed in (home.get("mail_domains") or [])
                      or ed == norm_domain(home.get("final_url") or "")):
                kill(r, STEPS[9], "email domain != company domain")
        probe = [d for d in sorted({r["_dom"] for r in alive()}) if "ir_probe" not in (caches["home"].get(d) or {})]
        if probe and not a.offline:
            def irp(d: str) -> None:
                hit = ""
                for host in (f"investors.{d}", f"ir.{d}"):
                    try:
                        h = requests.get(f"https://{host}", headers={"User-Agent": mt.UA}, timeout=10)
                    except requests.RequestException:
                        continue  # no such host / unreachable: not evidence either way
                    if h.status_code < 400 and host in h.url and re.search(
                            r"investor|stock|shareholder|sec filing", h.text[:200000], re.I):
                        hit = host
                        break
                with _lock:
                    caches["home"].setdefault(d, {})["ir_probe"] = hit
            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                list(pool.map(irp, probe))
            jsave(paths["home"], caches["home"])
        for r in alive():
            if (caches["home"].get(r["_dom"]) or {}).get("ir_probe"):
                kill(r, STEPS[10], "public listing (investor-relations site)")
        for r in alive():
            home = (caches["home"].get(r["_dom"]) or {}).get("static") or {}
            txt = f"{home.get('text', '')} {r.get('Company Short Description', '')} {r.get('Company SEO Description', '')}"
            m = tb.TICKER.search(txt)
            ir = [u for u in home.get("ir_links") or [] if re.match(r"https?://(investors?|ir)\.", u, re.I)
                  or "investor-relations" in u.lower()]
            if m:
                kill(r, STEPS[10], f"public listing ({m.group(0)})")
            elif ir:
                kill(r, STEPS[10], "public listing (investor-relations link on homepage)")
            elif re.search(r"publicly[- ]traded", txt, re.I):
                kill(r, STEPS[10], "public listing ('publicly traded' in description)")

        # 4a. email check: the operator's verifier columns when present, else syntax + MX
        vcol = a.verifier_status_col if rows and a.verifier_status_col in rows[0] else ""
        if vcol:
            keep_st = {x.strip() for x in a.verifier_keep.split(",") if x.strip()}
            for r in alive():
                st = (r.get(vcol) or "").strip().lower() or "blank"
                if not EMAIL_RE.match(r["_email"]):
                    kill(r, STEPS[11], "email syntax")
                elif (r.get("is_spamtrap") or "").strip().lower() == "true":
                    kill(r, STEPS[11], "verifier: spamtrap")
                elif st not in keep_st:
                    kill(r, STEPS[11], f"verifier: {st}")
                else:
                    r["_email_check"] = r["_tier"] = st
        mx_doms = [] if vcol else sorted({r["_email"].split("@")[-1] for r in alive() if "@" in r["_email"]})
        need = [d for d in mx_doms if d not in caches["mx"] or caches["mx"][d] is None]
        if need and not a.offline:
            with ThreadPoolExecutor(max_workers=8) as pool:
                for d, v in zip(need, pool.map(has_mx, need)):
                    caches["mx"][d] = v
            jsave(paths["mx"], caches["mx"])
        for r in ([] if vcol else alive()):
            if not EMAIL_RE.match(r["_email"]):
                kill(r, STEPS[11], "email syntax")
                continue
            v = caches["mx"].get(r["_email"].split("@")[-1])
            if v is False:
                kill(r, STEPS[11], "no MX record")
            elif v is None:
                kill(r, STEPS[11], "MX undeterminable")

        # 4b. cap 2 per company, one chief exec (stale second CEO resolved on the company pages)
        by_co: dict[str, list[dict]] = defaultdict(list)
        for r in alive():
            by_co[r["_dom"]].append(r)
        for dom, ppl in by_co.items():
            chiefs = [p for p in ppl if tb.CHIEF_EXEC.search((p.get("Title") or "").lower())]
            if len(chiefs) >= 2:
                pages = tb.site_pages(dom, caches["pages"], True, a.offline)
                texts = tb.page_texts(pages) + [((caches["home"].get(dom) or {}).get("static") or {}).get("text", "")]
                joined = tb._key(" ".join(texts))

                def seen(p: dict) -> int:
                    full = f"{p.get('First Name', '')} {p.get('Last Name', '')}"
                    k = tb._key(full)
                    if not k or k not in joined:
                        return 0
                    near = re.search(re.escape(k) + r".{0,60}?(ceo|chiefexecutive)|(ceo|chiefexecutive).{0,60}?"
                                     + re.escape(k), joined)
                    return 2 if near else 1

                sc = {id(p): seen(p) for p in chiefs}
                best = max(sc.values())
                top = [p for p in chiefs if sc[id(p)] == best]
                keep = top[0] if best > 0 and len(top) == 1 else max(
                    chiefs, key=lambda p: (tb.chief_rank(p.get("Title") or ""), -chiefs.index(p)))
                how = "not on company pages" if best > 0 and len(top) == 1 else "lower title rank"
                for p in chiefs:
                    if p is not keep:
                        kill(p, STEPS[12], f"stale second CEO ({how})")
            ranked = [p for p in ppl if not p["_drop"]]

            def key(p: dict) -> tuple:
                tl = (p.get("Title") or "").lower()
                return (RANK[p["_cls"]], 0 if tb.CHIEF_EXEC.search(tl) or "president" in tl else 1,
                        0 if re.search(r"cmo|chief marketing|marketing", tl) else 1, p.get("Last Name") or "")
            ranked.sort(key=key)
            first = [next((p for p in ranked if RANK[p["_cls"]] == k), None) for k in (0, 1)]
            first = [p for p in first if p]
            order = first + [p for p in ranked if p not in first]
            for p in order[2:]:
                kill(p, STEPS[12], "over 2 per company")
        save()

        # 4c. US headquarters only (operator 2026-11-17): a non-US company country drops from every output
        for r in alive():
            cc = (r.get("Company Country") or "").strip()
            if cc and cc not in ("United States", "United States of America", "USA", "US", "Puerto Rico"):
                kill(r, STEPS[13], f"HQ outside the US ({cc})")
        # 4d. maker / builder fit (Jev on the company's own description; threshold FIT_MIN in code)
        fit_q = {"fit": jev.noul(*FIT[vertical]), "kind": jev.choice("What kind of company is this?", FIT_KIND)}
        fit_ask = {}
        for r in alive():
            fit_ask.setdefault(r["_dom"], r)
        todo = [d for d in fit_ask if f"fit2|{vertical}|{d}" not in caches["jev"]]
        if todo and jev_on:
            todo = todo[:max(0, budget[0])]
            states_in = [{"company": fit_ask[d].get("Company Name"), "domain": d,
                          "linkedin_industry": fit_ask[d].get("Industry"),
                          "description": ((fit_ask[d].get("Company Short Description") or "") + " "
                                          + (fit_ask[d].get("Company SEO Description") or ""))[:900],
                          "keywords": (fit_ask[d].get("Keywords") or "")[:300]} for d in todo]
            res = jev.decide_many(states_in, fit_q, workers=8)
            budget[0] -= len(todo)
            for d, rr in zip(todo, res):
                jev.append_ledger({"script": "import_list_leads", "step": "fit", "cost": rr.cost_usd})
                if rr.error:
                    continue  # not cached: re-run retries; this run the company is kept (helper fails open)
                caches["jev"][f"fit2|{vertical}|{d}"] = {"noul": rr.noul("fit"), "kind": rr.choice("kind"),
                                                        "conf": rr.confidence("kind")}
            save()
        for r in alive():
            j = caches["jev"].get(f"fit2|{vertical}|{r['_dom']}")
            maker_pick = j and j["kind"] == "maker_or_builder" and j["conf"] >= FIT_KIND_CONF
            named_non = j and j["kind"] not in ("maker_or_builder", "none", "") and j["conf"] >= FIT_KIND_CONF
            if j and ((j["noul"] < FIT_MIN and not maker_pick) or (j["noul"] < FIT_SOFT and named_non)):
                kind = j["kind"] if j["kind"] not in ("maker_or_builder", "none", "") else "other / unclear"
                kill(r, STEPS[14], f"not a maker / builder: {kind}")

        final = alive()
        final_doms = sorted({r["_dom"] for r in final})

        # 4c. LeadOcean status for each kept person (free-ceiling records)
        lo = None
        if not a.offline and lo_budget[0] > 0 and not vcol:
            try:
                lo = LeadOcean()
            except SystemExit as exc:
                print(f"LeadOcean unavailable: {exc}")
        todo = [] if vcol else [r for r in final if r["_email"] not in caches["lo_person"]]
        if lo and todo:
            todo = todo[:lo_budget[0]]
            print(f"[{vertical}] LeadOcean person check {len(todo)}", flush=True)

            def lo_one(r: dict) -> None:
                q = f"{(r.get('First Name') or '').strip()} {(r.get('Last Name') or '').strip()}".strip()
                try:
                    j = lo.req("GET", "/v1/people/search", params={"q": q, "domain": r["_dom"], "limit": 5,
                                                                   "slim": "true"})
                except RuntimeError as exc:
                    print(f"LeadOcean person lookup failed: {str(exc)[:120]}")
                    return  # not cached: a re-run retries
                slug = (r.get("LinkedIn") or "").rstrip("/").rsplit("/", 1)[-1].lower()
                hit = None
                for p in j.get("data") or []:
                    pd, cd = p.get("profile_data") or {}, p.get("contact_data") or {}
                    ps = (pd.get("profile_url") or "").rstrip("/").rsplit("/", 1)[-1].lower()
                    same = (slug and ps == slug) or (
                        tb._key(pd.get("profile_first_name")) == tb._key(r.get("First Name"))
                        and tb._key(pd.get("profile_last_name")) == tb._key(r.get("Last Name")))
                    if same:
                        hit = {"status": cd.get("email_status") or "", "type": cd.get("email_type") or ""}
                        break
                with _lock:
                    caches["lo_person"][r["_email"]] = hit or {"status": "not_found"}
                    lo_budget[0] -= 1

            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(lo_one, todo))
            jsave(paths["lo_person"], caches["lo_person"])
        for r in final:
            lp = caches["lo_person"].get(r["_email"]) or {}
            st = lp.get("status", "")
            r["_lo_status"] = st or ("not used (verifier columns)" if vcol else "unchecked")
            if vcol:
                continue  # email_check / email_tier already set from the verifier status
            r["_email_check"] = "verified_leadocean" if st == "verified" and lp.get("type", "work").startswith("work") \
                else "mx_ok"
            r["_tier"] = "catch_all" if st in ("catch_all", "catch_all_valid") else r["_email_check"]

        def disp(r: dict) -> tuple[str, list[str]]:
            s = (caches["home"].get(r["_dom"]) or {}).get("static") or {}
            texts = [x for x in (s.get("title"), s.get("og_site_name"), s.get("logo_alt"), s.get("text")) if x]
            name = r.get("Company Name") or ""
            return tb.recase_name(tb.display_company(clean_company(name), ""), name.isupper(), texts), texts

        # 4e. company_casual: deterministic rules; Jev picks only when the candidates disagree
        co_first = {d: next(r for r in final if r["_dom"] == d) for d in final_doms}
        cas_opts = {}
        for d, r in co_first.items():
            cdisp, texts = disp(r)
            hs = (caches["home"].get(d) or {}).get("static") or {}
            cas_opts[d] = casual_candidates(r.get("Company Name") or "", cdisp, hs, d, texts)
        ambiguous = {d: o for d, o in cas_opts.items() if len(o) > 1}
        ckey = {d: "casual|" + d + "|" + "|".join(f"{k}={tb._key(v)}" for k, v in o.items()) for d, o in ambiguous.items()}
        todo = [d for d in ambiguous if ckey[d] not in caches["jev"]]
        if todo and jev_on:
            todo = todo[:max(0, budget[0])]
            hs_of = {d: (caches["home"].get(d) or {}).get("static") or {} for d in todo}
            states_in = [{"record_name": co_first[d].get("Company Name"), "domain": d,
                          "homepage_title": hs_of[d].get("title", ""), "og_site_name": hs_of[d].get("og_site_name", ""),
                          "homepage_start": (hs_of[d].get("text") or "")[:300],
                          "description": (co_first[d].get("Company Short Description") or "")[:300]} for d in todo]
            casual_q = ("Which option is how this company refers to itself in short form, the name a person would "
                        "use for it in a short email? It must still clearly identify this company: a bare common "
                        "word, bare surname or bare initials is not enough unless the company itself goes by that "
                        "form on its homepage. Legal suffixes (Inc, LLC, Corp) are never needed. Taglines, slogans, "
                        "page names, services and other companies are never the answer.")
            with ThreadPoolExecutor(max_workers=8) as pool:  # options differ per company: one call each
                res = list(pool.map(lambda x: jev.decide(x[1], {"name": jev.choice(casual_q, dict(ambiguous[x[0]]))}),
                                    zip(todo, states_in)))
            budget[0] -= len(todo)
            for d, rr in zip(todo, res):
                jev.append_ledger({"script": "import_list_leads", "step": "company_casual", "cost": rr.cost_usd})
                if not rr.error:
                    caches["jev"][ckey[d]] = {"pick": rr.choice("name"), "conf": rr.confidence("name")}
            save()
        casual: dict[str, tuple[str, str]] = {}
        for o in cas_opts.values():  # "K L Masters" -> "KL Masters" whichever option wins
            for k in o:
                o[k] = re.sub(r"\b([A-Z]) (?=[A-Z]\b)", r"\1", o[k])
        for d, o in cas_opts.items():
            j = caches["jev"].get(ckey.get(d, "")) if d in ambiguous else None
            pick = o.get(j["pick"], "") if j else ""
            to_initials = pick and all(_initial_tok(w) or (w.isupper() and len(w) <= 5) for w in pick.split()) \
                and not casual_weak(o["rule"])
            to_initials = to_initials or (j and j["pick"] == "short" and casual_weak(pick))  # "Petretti & Associates"
            if j and pick and j["conf"] >= JEV_CASUAL_CONF and not to_initials:
                casual[d] = (o[j["pick"]], f"jev {j['pick']} {j['conf']:.2f}")
            else:
                casual[d] = (o["rule"], "rule" + (f" (jev unsure {j['conf']:.2f})" if j else
                                                  " (not judged)" if d in ambiguous else ""))

        # 5. personalization per company
        trigs = load_triggers(vertical, states, a)
        by_dom_t, by_name_t = trigger_index(vertical, trigs, a)
        pers: dict[str, dict] = {}
        for d, r in co_first.items():
            t = by_dom_t.get(d)
            if not t:
                st = r["_state_raw"]
                for n in tb.name_variants(r.get("Company Name") or ""):
                    t = by_name_t.get(f"{n}|{st}")
                    if t:
                        break
            if not t:
                continue
            c = {"domain": d, "name": r.get("Company Name") or ""}
            sc = tb.site_check(t, c, caches["site"], a.offline)
            if sc.get("ok"):
                texts = [((caches["home"].get(d) or {}).get("static") or {}).get("text", "")]
                if vertical == "medtech":
                    subj = re.sub(r"^the\s+", "", tb.device_display(t["device_raw"], t["org"], texts), flags=re.I)
                    line = (f"Congratulations on the {tb.nice_date(t['date'])} FDA clearance for the {subj}. "
                            f"I noticed the {casual[d][0]} homepage doesn't mention it yet.")
                    ptype, tid = "trigger_fda", t["k_number"]
                else:
                    subj = t["agency"]
                    line = (f"Congratulations on the {subj} contract awarded on {tb.nice_date(t['date'])}. "
                            f"I noticed the {casual[d][0]} homepage doesn't mention it yet.")
                    ptype, tid = "trigger_award", t["award_id"]
                pers[d] = {"type": ptype, "first_line": line, "trigger_date": t["date"], "trigger_subject": subj,
                           "trigger_id": tid, "trigger_url": t["evidence_url"],
                           "evidence": f"{t['evidence_url']} | homepage {sc.get('final_url', '')} checked, no mention of "
                                       f"{'; '.join((sc.get('terms') or [])[:4])}"}
            else:
                r["_trigger_note"] = f"{t['key']}: {sc.get('reason', '')}"
        save()
        # 5b. rendered confirmation for site facts
        need_r = []
        for d in final_doms:
            if d in pers:
                continue
            e = caches["home"].get(d) or {}
            s = e.get("static") or {}
            if "rendered" in e:
                continue
            thin = not s.get("text") or len(s.get("text", "")) < 200
            if thin or candidates(s, a.copyright_max):
                need_r.append(d)
        if need_r and not a.offline:
            print(f"[{vertical}] render-confirm {len(need_r)} homepages", flush=True)
            chunks = [need_r[i:i + 6] for i in range(0, len(need_r), 6)]

            def rchunk(ch: list[str]) -> None:
                urls = [((caches["home"].get(d) or {}).get("static") or {}).get("final_url") or f"https://{d}"
                        for d in ch]
                res = render_many(urls)
                with _lock:
                    for d, rr in zip(ch, res):
                        caches["home"].setdefault(d, {})["rendered"] = rr

            with ThreadPoolExecutor(max_workers=a.render_workers) as pool:
                for i, _ in enumerate(pool.map(rchunk, chunks)):
                    if i and i % 20 == 0:
                        print(f"  render {i * 6}/{len(need_r)}", flush=True)
                        jsave(paths["home"], caches["home"])
            jsave(paths["home"], caches["home"])
        for d in final_doms:
            if d not in pers:
                f = site_fact(d, caches["home"].get(d) or {}, a.copyright_max, casual[d][0])
                if f:
                    pers[d] = f

        # 5c. company_description first line for every company still without one (generator + independent Jev gate)
        rej = desc_stats.setdefault(vertical, Counter())
        need_meta = []
        items = []
        for d in final_doms:
            if d in pers:
                continue
            r = co_first[d]
            home = caches["home"].get(d) or {}
            desc, kw, src = company_description(r, home)
            if len(desc) < 40 and "meta" not in home and not a.offline:
                need_meta.append(d)
            items.append({"dom": d, "r": r})
        if need_meta:
            print(f"[{vertical}] homepage meta fetch {len(need_meta)}", flush=True)

            def mg(d: str) -> None:
                m = meta_get(d, ((caches["home"].get(d) or {}).get("static") or {}).get("final_url") or "")
                if m:
                    with _lock:
                        caches["home"].setdefault(d, {})["meta"] = m
            with ThreadPoolExecutor(max_workers=a.workers) as pool:
                list(pool.map(mg, need_meta))
            jsave(paths["home"], caches["home"])
        gen = []
        for it in items:
            r = it["r"]
            desc, kw, src = company_description(r, caches["home"].get(it["dom"]) or {})
            cdisp, _ = disp(r)
            it.update(company=cdisp, description=desc, keywords=kw, source=src, opener=desc_opener(it["dom"]),
                      key=desc_key(it["dom"], cdisp, desc, kw))
            if len(desc) < 40:
                rej["no description"] += 1
                continue
            gen.append(it)
        if gen and not a.offline:
            st = generate_lines(gen, caches["desc_line"], a.max_usd - llm_stats["usd"])
            for k in ("calls", "failed", "skipped_budget"):
                llm_stats[k] += st[k]
            llm_stats["usd"] += st["usd"]
            jsave(paths["desc_line"], caches["desc_line"])
        # one repair pass for lines that fail the deterministic rules (cached under key|r1)
        retry = []
        for it in gen:
            c = caches["desc_line"].get(it["key"])
            if c and c["line"]:
                why = line_rule_check(c["line"], it["company"], it["description"] + " " + it["keywords"])
                if why:
                    retry.append({**it, "key": it["key"] + "|r1", "orig_key": it["key"],
                                  "fix": f"{why}; rejected line: {c['line']}"})
        if retry and not a.offline:
            st = generate_lines(retry, caches["desc_line"], a.max_usd - llm_stats["usd"])
            for k in ("calls", "failed", "skipped_budget"):
                llm_stats[k] += st[k]
            llm_stats["usd"] += st["usd"]
            jsave(paths["desc_line"], caches["desc_line"])
        for rt in retry:
            c = caches["desc_line"].get(rt["key"])
            if c and c["line"] and not line_rule_check(c["line"], rt["company"], rt["description"] + " " + rt["keywords"]):
                rej["repaired after rule fail"] += 1
                next(it for it in gen if it["key"] == rt["orig_key"])["key"] = rt["key"]
        checked = []
        for it in gen:
            c = caches["desc_line"].get(it["key"])
            if c is None:
                rej["generator: not run (offline / budget / failed batch)"] += 1
                continue
            it["line"] = c["line"]
            why = line_rule_check(it["line"], it["company"], it["description"] + " " + it["keywords"])
            if why:
                rej[re.sub(r" \(.*", "", why) if why.startswith("rule: number") else why] += 1
                continue
            checked.append(it)
        verify_lines(checked, caches["jev"], budget, jev_on)
        for it in checked:
            j = caches["jev"].get(it["jkey"])
            if not j:
                rej["jev: not verified (unavailable / budget)"] += 1
            elif j["supported"] < DESC_SUPPORTED_MIN:
                rej["jev: fact not in description"] += 1
            elif j["opinion"] > DESC_OPINION_MAX:
                rej["jev: praise / intent / opinion"] += 1
            else:
                # verified with the record display name (cache key); the mail says the casual name (operator
                # 2026-11-17). Substitution only: the facts do not change, so no new generator or Jev call.
                cn = casual[it["dom"]][0]
                line = it["line"].replace(it["company"], cn) if it["company"] in it["line"] else ""
                why = line_rule_check(line, cn, it["description"] + " " + it["keywords"]) if line else \
                    "casual swap: name not in line"
                if why:
                    rej["casual swap: " + why] += 1
                    continue
                rej["kept"] += 1
                pers[it["dom"]] = {"type": "company_description", "first_line": line,
                                   "evidence": evidence_snippet(it["line"], it["description"], it["source"])
                                   + f" | jev supported {j['supported']:.2f}, opinion {j['opinion']:.2f}"}
        save()

        # rows out
        for r in final:
            d = r["_dom"]
            cdisp, texts = disp(r)
            fn, ln = tb.person_display(r.get("First Name") or "", r.get("Last Name") or "", texts, cdisp)
            fn, ln = fix_name_case(fn), fix_name_case(ln)
            p = pers.get(d) or {}
            src_company = r["_state_src"] == "company"
            r["_casual_how"] = re.sub(r" [\d.]+$| \(.*", "", casual[d][1])
            r["_out"] = {
                "first_name": fn, "last_name": ln, "email": r["_email"], "title": (r.get("Title") or "").strip(),
                "company_display": cdisp, "company_casual": casual[d][0], "website": d,
                "city": (r.get("Company City") if src_company else r.get("City")) or "",
                "state": r["_state_raw"], "employees": r["_emp"], "linkedin": r.get("LinkedIn") or "",
                "vertical": vertical, "email_check": r["_email_check"], "email_tier": r["_tier"],
                "personalization_type": p.get("type", "none"), "first_line": p.get("first_line", ""),
                "evidence": p.get("evidence", ""), "trigger_date": p.get("trigger_date", ""),
                "trigger_subject": p.get("trigger_subject", ""), "trigger_id": p.get("trigger_id", ""),
                "trigger_url": p.get("trigger_url", "")}
        all_rows += rows

        # companies.csv rows
        cos: dict[str, list[dict]] = defaultdict(list)
        for r in rows:
            cos[r["_dom"] or f"(no domain) {r.get('Company Name', '')}"].append(r)
        for d, ppl in sorted(cos.items()):
            kept = [r for r in ppl if not r["_drop"]]
            r0 = kept[0] if kept else max(ppl, key=lambda r: r["_step"])
            p = pers.get(d) or {}
            co_rows.append({"vertical": vertical, "company": r0.get("Company Name"),
                            "company_display": (r0.get("_out") or {}).get("company_display", ""),
                            "company_casual": (r0.get("_out") or {}).get("company_casual", ""),
                            "casual_source": casual[d][1] if kept and d in casual else "", "domain": d,
                            "state": r0["_state_raw"], "employees": r0.get("Employees Count"),
                            "industry": r0.get("Industry"), "contacts_in": len(ppl), "contacts_out": len(kept),
                            "outcome": "kept" if kept else r0["_drop"],
                            "personalization_type": p.get("type", "none") if kept else "",
                            "first_line": p.get("first_line", "") if kept else "",
                            "evidence": p.get("evidence", "") if kept else (r0.get("_trigger_note") or "")})
        reports.append((vertical, states, rows))

    # ------------------------------------------------------------------ write
    files = []

    def write(path: Path, cols: list[str], data: list[dict]) -> list[Path]:
        def dump(p: Path, chunk: list[dict]) -> None:
            with open(p, "w", newline="", encoding="utf-8") as fh:
                w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
                w.writeheader()
                for x in chunk:
                    w.writerow(csv_safe_row(x))
        dump(path, data)
        if path.stat().st_size < 2_000_000:
            return [path]
        n = int(path.stat().st_size / 1_800_000) + 1
        path.unlink()
        while True:
            size = -(-len(data) // n)
            parts = [path.with_name(f"{path.stem}_part{i + 1}{path.suffix}") for i in range(n)]
            for i, p in enumerate(parts):
                dump(p, data[i * size:(i + 1) * size])
            if all(p.stat().st_size < 2_000_000 for p in parts):
                return parts
            n += 1

    for vertical, states, rows in reports:
        final = [r for r in rows if not r["_drop"]]
        for st in states + ["other"]:
            data = sorted((r["_out"] for r in final if r["_state"] == st),
                          key=lambda x: (x["personalization_type"] == "none", x["company_display"].lower(),
                                         x["last_name"]))
            files += write(out / f"{vertical}_{st}.csv", OUT_COLS, data)
    files += write(out / "companies.csv", CO_COLS, co_rows)

    # funnel.md
    md = [f"# Import list leads: funnel ({TODAY.isoformat()})", "",
          "People counts after each step, by state bucket (company HQ state, else person state; 'other' = outside "
          "the target states). Companies = distinct domains still alive.", ""]
    for vertical, states, rows in reports:
        buckets = states + ["other"]
        md += [f"## {vertical}", "", "| step | " + " | ".join(buckets) + " | total | companies |",
               "|---|" + "---|" * (len(buckets) + 2)]
        for i, step in enumerate(STEPS):
            alive_i = [r for r in rows if r["_step"] > i]
            cnt = Counter(r["_state"] for r in alive_i)
            ncos = len({r["_dom"] for r in alive_i if r["_dom"]})
            md.append(f"| {step} | " + " | ".join(str(cnt[b]) for b in buckets) + f" | {len(alive_i)} | {ncos} |")
        final = [r for r in rows if not r["_drop"]]
        md += ["", "**Drops by reason** (people):", "", "| reason | " + " | ".join(buckets) + " | total |",
               "|---|" + "---|" * (len(buckets) + 1)]
        rc = defaultdict(Counter)
        for r in rows:
            if r["_drop"]:
                rc[re.sub(r"\(NASDAQ.*|\(NYSE.*", "(ticker)", r["_drop"])][r["_state"]] += 1
        for reason, c in sorted(rc.items(), key=lambda x: -sum(x[1].values())):
            md.append(f"| {reason} | " + " | ".join(str(c[b]) for b in buckets) + f" | {sum(c.values())} |")
        md += ["", "**Personalization mix** (people / companies):", "", "| type | " + " | ".join(buckets) + " | people | companies |",
               "|---|" + "---|" * (len(buckets) + 2)]
        for pt in PTYPES:
            sel = [r for r in final if r["_out"]["personalization_type"] == pt]
            c = Counter(r["_state"] for r in sel)
            md.append(f"| {pt} | " + " | ".join(str(c[b]) for b in buckets) + f" | {len(sel)} | {len({r['_dom'] for r in sel})} |")
        md += ["", "**email_tier split** (final people / companies with >=1 such contact):", "",
               "| email_tier | " + " | ".join(buckets) + " | people | companies |", "|---|" + "---|" * (len(buckets) + 2)]
        for ec, _n in Counter(r["_tier"] for r in final).most_common():
            sel = [r for r in final if r["_tier"] == ec]
            c = Counter(r["_state"] for r in sel)
            md.append(f"| {ec} | " + " | ".join(str(c[b]) for b in buckets)
                      + f" | {len(sel)} | {len({r['_dom'] for r in sel})} |")
        dc = desc_stats.get(vertical) or Counter()
        md += ["", "**company_description first lines** (companies; generator then rule check then Jev):", "",
               "| outcome | companies |", "|---|---|"] + [f"| {k} | {v} |" for k, v in dc.most_common()]
        cs = Counter(r["_casual_how"] for r in final)
        md += ["", "company_casual source (people): " + ", ".join(f"{k} {v}" for k, v in cs.most_common())]
        lc = Counter(r["_lo_status"] for r in final)
        md += ["", "LeadOcean person status: " + ", ".join(f"{k} {v}" for k, v in lc.most_common()), ""]
    (out / "funnel.md").write_text("\n".join(md) + "\n", encoding="utf-8")
    files.append(out / "funnel.md")
    print("\n".join(md))
    if a.copy_to:
        dst = Path(a.copy_to)
        dst.mkdir(parents=True, exist_ok=True)
        for f in files:
            shutil.copy2(f, dst / f.name)
        print(f"copied {len(files)} files to {dst}")
    print(f"first-line LLM: {llm_stats['calls']} calls ({llm_stats['failed']} failed, {llm_stats['skipped_budget']} "
          f"skipped by budget), notional ${llm_stats['usd']:.4f} of ${a.max_usd:.2f} (subscription, not billed)")
    if llm_stats["calls"]:  # a cache-only re-run spends nothing and writes no row
        with open(ROOT / ".tmp" / "cost_ledger.jsonl", "a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": dt.datetime.now().isoformat(timespec="seconds"), "script": "import_list_leads",
                                 "step": "company_description first lines", "model": DESC_CHAIN[0][0],
                                 "billing": "subscription", "calls": llm_stats["calls"],
                                 "notional_usd": round(llm_stats["usd"], 4), "max_usd": a.max_usd}) + "\n")
    print(f"Jev calls left {budget[0]}/{a.max_jev}; LeadOcean person lookups left {lo_budget[0]}/{a.max_lo}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
