"""
trigger_batch_leads.py
description: Trigger-first cold-email batch builder for an agency referral program: dated public triggers (medtech = FDA
             510(k) clearances, construction = new federal contract awards) for companies HQ'd in a region -> LeadOcean
             company match (Jev choice for ambiguous names) -> size + vertical gate (LeadOcean headcount + Jev noul) ->
             homepage site fact ("homepage does not mention the trigger", finder + blind verifier) -> decision-maker
             contacts with a LeadOcean-verified work email (max 2 per company) -> drop list + dedupe -> CSVs + funnel.
inputs:  --region west|east|midwest|south|mountain (or --states CA,OR); --verticals medtech,construction;
         --batch NAME (output folder); --since (510(k) decisions, default 2026-08-01); --days (awards, default 90);
         --drop-list JSON {"domains": [...], "names": [...]}; --max-jev; --try-export (one <=50-domain export when the
         per-person email lookup is down); --check (offline: caches only); --min-emp medtech=20,construction=10;
         --max-emp 500; --apollo-below 10 + --max-apollo 300 (Apollo org-enrich second-opinion headcount);
         --discover on|off + --max-serper 300 (web domain discovery for names LeadOcean cannot match);
         --end YYYY-MM-DD (pin the award window); --size-flag drop|flag; --allow-net pages,jev,email (with --check:
         the only stages allowed online). Contact gates: title allowlist (Jev for edge titles), one chief exec per
         company (about/leadership pages), role-inbox drop, cap 2; display columns company_display/device_display.
         env LEADOCEAN_API_KEY, OPENROUTER_API_KEY, optional SERPER_API_KEY (else DuckDuckGo HTML).
outputs: .tmp/referral/<batch>/<batch>_<vertical>.csv (one row per contact, personalized columns), <batch>_companies.csv
         (every trigger company with its funnel outcome and drop reason), funnel.md; caches in .tmp/referral/cache/
         (match, gate, site, contacts, email, pages; keyed by name+state / domain / K number or award id / person id).
usage:   python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1
         python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1 --check   # rebuild offline
Directive: directives/lead_sourcing/trigger_batch_leads.md
Spend: openFDA, USAspending, company sites, DuckDuckGo: free. Serper: free-tier credits, capped by --max-serper.
       Apollo organizations/enrich: free plan via the proxy-injected key, capped by --max-apollo. LeadOcean search/company/email lookups bill "records" against a
       fair-use plan with no ceiling (whenOver: never); exports bill rows against the 10k/day quota. Jev ~$0.00002/call,
       capped by --max-jev, ledgered in .tmp/jev_ledger.jsonl. Never calls Reoon, Instantly or any sender.
"""

from __future__ import annotations

import argparse, csv, datetime as dt, html as html_lib, json, os, re, sys, threading, time, urllib.parse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "execution" / "lead_sourcing"))
sys.path.insert(0, str(ROOT / "execution" / "gtm_icp_filters"))
load_dotenv(ROOT / ".env")

import medtech_510k_triggers as mt  # noqa: E402
import construction_award_triggers as ct  # noqa: E402
from leadocean_leads import LeadOcean, jload, jsave, norm_domain  # noqa: E402

CACHE = ROOT / ".tmp" / "referral" / "cache"
MONTHS = mt.MONTHS
VERTICAL = {
    "medtech": {"label": "medical device, diagnostics or medtech manufacturer",
                "industry_hint": "Medical Equipment Manufacturing, Medical Device, Biotechnology",
                "search_word": "medical device"},
    "construction": {"label": "construction contractor (general, heavy/civil or specialty trade)",
                     "industry_hint": "Construction, Civil Engineering, Specialty Trade Contractors",
                     "search_word": "contractor"},
}
MIN_EMP = {"medtech": 20, "construction": 10}  # LinkedIn undercounts field crews; override with --min-emp
MAX_EMP = 500
APOLLO_BELOW = 10      # ask Apollo for a second-opinion headcount when LinkedIn staff < this (or missing)
JEV_MATCH_CONF = 0.7   # choice confidence needed to accept an ambiguous name match
JEV_GATE_NOUL = 0.6    # probability "real operating company, 20-500 staff, in this vertical"
CONTACT_SENIORITY = ["owner", "founder", "c_suite", "partner", "vp", "head", "director"]
EXCL_TITLE = ["Assistant", "Intern", "Former", "Retired", "Advisor", "Board Member", "Student", "Volunteer",
              "Executive Assistant", "Product Owner", "Process Owner"]
MAX_PER_CO = 2
_lock = threading.Lock()


# ------------------------------------------------------------------ helpers
US_STATES = dict(zip(
    "alabama alaska arizona arkansas california colorado connecticut delaware florida georgia hawaii idaho illinois "
    "indiana iowa kansas kentucky louisiana maine maryland massachusetts michigan minnesota mississippi missouri "
    "montana nebraska nevada new_hampshire new_jersey new_mexico new_york north_carolina north_dakota ohio oklahoma "
    "oregon pennsylvania rhode_island south_carolina south_dakota tennessee texas utah vermont virginia washington "
    "west_virginia wisconsin wyoming district_of_columbia".split(),
    "AL AK AZ AR CA CO CT DE FL GA HI ID IL IN IA KS KY LA ME MD MA MI MN MS MO MT NE NV NH NJ NM NY NC ND OH OK OR PA "
    "RI SC SD TN TX UT VT VA WA WV WI WY DC".split()))


def state_code(s: str) -> str:
    s = (s or "").strip()
    return US_STATES.get(s.lower().replace(" ", "_"), s.upper())


def norm_name(s: str) -> str:
    return " ".join(mt.norm_tokens(s))


LEGAL = re.compile(r"[,\s]+(inc|incorporated|llc|l\.l\.c|corp|corporation|co|company|ltd|limited|lp|llp|pc|plc)\.?$", re.I)


def strip_legal(name: str) -> str:
    s = (name or "").strip()
    while LEGAL.search(s):
        s = LEGAL.sub("", s).strip(" ,.")
    return s


def display_company(org: str, lo_name: str) -> str:
    """Merge-ready company name. Mixed-case public-record names (FDA) are the company's own spelling; ALL-CAPS
    records (USAspending) take the LeadOcean name when it is the same name, never a LinkedIn tagline."""
    base = strip_legal(org)
    if not base.isupper():
        return base
    lo = strip_legal(lo_name)
    if lo and set(mt.norm_tokens(lo)) == set(mt.norm_tokens(base)):
        return lo
    return " ".join(w if len(w) <= 2 else w.capitalize() for w in base.split())


def person_case(s: str) -> str:
    s = (s or "").strip()
    if s.islower() or s.isupper():
        return " ".join(p[:1].upper() + p[1:].lower() for p in s.split())
    return s


def nice_date(iso: str) -> str:
    d = dt.date.fromisoformat(iso[:10])
    return f"{MONTHS[d.month - 1]} {d.day}"


SHORT_WORDS = {"gel", "and", "for", "kit", "set", "tip", "cap", "the", "of", "with", "bag", "pad", "rod", "pin", "cup",
               "net", "arm", "leg", "hip", "eye", "ear", "jaw", "toe", "lip", "gum", "mat", "box", "bed", "hub",
               "lid", "fix", "air", "ice", "use", "one", "two", "pen", "wire", "dry", "wet", "hot", "low", "top"}


def short_device(raw: str, company: str = "") -> str:
    """Subject-line device name: clean_device(), parentheticals dropped, cut at a dash/colon if still long."""
    raw = re.sub(r"[\x80-\x9f\u2122\u00ae\u00a9]", "", raw)  # FDA records carry mis-encoded TM bytes (\x99)
    s = mt.clean_device(raw)
    if raw.split(";")[0].isupper():  # clean_device keeps <=3-letter words upper (codes); real words read badly
        s = " ".join(w.capitalize() if w.lower() in SHORT_WORDS else w for w in s.split())
    s = re.sub(r"\s*\([^)]*\)", "", s).strip(" ,;-")
    if len(s) > 45:
        for sep in (" - ", " – ", ": ", ", ", " and ", " with ", " for "):
            head = s.split(sep)[0].strip()
            if len(head.split()) >= 2 and len(head) >= 8:
                s = head
                if len(s) <= 45:
                    break
    if len(s) > 45 and company:  # "Acme Medical Foo Catheter System" -> "Foo Catheter System"
        co = set(mt.norm_tokens(company)) | {"medical"}
        words = s.split()
        i = 0
        while i < len(words) - 2 and (words[i].lower().strip(",.") in co or words[i].isdigit()):
            i += 1
        s = " ".join(words[i:]) if i else s
    return re.sub(r"\s+", " ", s)


def contact_rank(title: str) -> int | None:
    """0 CEO/President/Owner/Founder, 1 CMO/VP or Director/Head of Marketing, 2 other exec; None = not a decision-maker."""
    t = (title or "").lower()
    vp = re.search(r"\bvice[- ]president\b|\bvp\b|\bsvp\b|\bevp\b", t)
    if re.search(r"\bassistant to\b|\bexecutive assistant\b|\bintern\b|\bformer\b", t):
        return None
    if not vp and re.search(r"\b(ceo|chief executive|president|owner|founder|co-founder|cofounder)\b", t):
        return 0
    if re.search(r"\bcmo\b|chief marketing", t) or (re.search(r"marketing|brand|communications", t)
                                                    and (vp or re.search(r"\b(director|head)\b", t))):
        return 1
    if (vp or re.search(r"\bchief\b|\b(coo|cfo|cto|cro|cco)\b|\bpartner\b|\bprincipal\b|\bgeneral manager\b"
                        r"|\bmanaging director\b", t)):
        return 2
    return None


# ------------------------------------------------------------------ 1. triggers
def medtech_triggers(states: list[str], since: str, offline: bool) -> list[dict]:
    fda = mt.pull_fda(since, refresh=False, offline=offline)
    by: dict[str, dict] = {}
    for r in sorted(fda, key=lambda r: r["decision_date"], reverse=True):
        if (r.get("state") or "").upper() not in states:
            continue
        key = norm_name(r["applicant"]) + "|" + r["state"].upper()
        t = by.setdefault(key, {"vertical": "medtech", "org": r["applicant"], "state": r["state"].upper(),
                                "city": r.get("city") or "", "street": r.get("address_1") or "",
                                "zip": (r.get("zip_code") or "")[:5], "recs": []})
        t["recs"].append(r)
    out = []
    for t in by.values():
        rec = t["recs"][0]  # newest clearance
        t.update(key=rec["k_number"], date=rec["decision_date"], k_number=rec["k_number"],
                 device_raw=rec["device_name"], device=short_device(rec["device_name"], rec["applicant"]),
                 n_triggers=len(t["recs"]),
                 evidence_url=f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={rec['k_number']}")
        out.append(t)
    return out


def construction_triggers(states: list[str], region: str, days: int, offline: bool, end: str = "") -> list[dict]:
    label = region or "-".join(states).lower()
    path = ROOT / ".tmp/referral/triggers/construction" / f"construction_triggers_{label}.csv"
    cmd = [sys.executable, str(ROOT / "execution/gtm_icp_filters/construction_award_triggers.py"),
           "--days", str(days)] + (["--region", region] if region else ["--states", ",".join(states)])
    if end:
        cmd += ["--end", end]
    if offline:
        cmd.append("--check")
    import subprocess
    cp = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=1800)
    print(cp.stdout.strip() or cp.stderr.strip()[-400:])
    if cp.returncode != 0 or not path.exists():
        raise SystemExit(f"construction triggers failed: {cp.stderr[-400:]}")
    out = []
    for r in csv.DictReader(open(path, newline="", encoding="utf-8")):
        out.append({"vertical": "construction", "org": r["recipient"], "state": r["state"], "city": "",
                    "key": r["award_id"], "date": r["action_date"], "award_id": r["award_id"],
                    "agency": r["agency"], "agency_raw": r["subagency_raw"], "amount": r["amount"],
                    "description": r["description"], "parent": r["parent"], "uei": r["uei"],
                    "evidence_url": r["evidence_url"], "n_triggers": 1})
    return out


# ------------------------------------------------------------------ 2. LeadOcean company match
def name_variants(org: str) -> list[str]:
    parts = re.split(r"\b(?:d/?b/?a|doing business as)\b", org, flags=re.I)
    out = []
    for p in parts:
        n = norm_name(p)
        if n:
            out.append(n)
    return list(dict.fromkeys(out))


def lo_company_candidates(lo: LeadOcean, org: str, state: str, cache: dict, offline: bool) -> list[dict]:
    key = f"{norm_name(org)}|{state}"
    if key in cache:
        return cache[key]
    if offline:
        return []
    cands: dict[str, dict] = {}
    for nm in name_variants(org):
        for params in ({"name": nm, "hqState": state}, {"name": nm, "hqCountry": "US"}):
            try:
                j = lo.req("GET", "/v1/companies/search", params=dict(params, limit=8, slim="true"))
            except RuntimeError as exc:
                print(f"company search failed for a trigger org: {str(exc)[:120]}")
                continue
            for c in j.get("data") or []:
                d = c.get("company_data") or {}
                dom = norm_domain(d.get("company_domain"))
                if not dom or dom in cands:
                    continue
                addr = d.get("company_primary_address") or {}
                emp = (d.get("company_employees") or {}).get("number_of_employees")
                cands[dom] = {"domain": dom, "name": d.get("company_name") or "", "city": addr.get("city") or "",
                              "state": addr.get("state") or "", "employees": emp,
                              "industries": ", ".join(i.get("name3", "") for i in (d.get("company_industries") or [])[:3]),
                              "description": (d.get("company_description") or "")[:600],
                              "linkedin": ((d.get("company_social_links") or {}).get("linkedin") or {}).get("url") or "",
                              "decision_makers": d.get("company_number_of_decision_makers")}
            if cands:
                break  # in-state hits found; skip the US-wide fallback
        if cands:
            break
    with _lock:
        cache[key] = list(cands.values())
    return cache[key]


def match_trigger(t: dict, cands: list[dict], jev_cache: dict, budget: list[int], offline: bool) -> tuple[dict | None, str]:
    """Exact normalized name (+ same state) with no rival = auto; anything else = one Jev choice with a none option."""
    if not cands:
        return None, "no LeadOcean company found by name"
    tn = set(name_variants(t["org"]))
    exact = [c for c in cands if norm_name(c["name"]) in tn]
    exact_st = [c for c in exact if state_code(c["state"]) in (t["state"], "")]
    rival = [c for c in exact if c not in exact_st]  # same name in another state
    if len(exact_st) == 1 and (not rival or (t.get("city") and exact_st[0]["city"].lower() == t["city"].lower())):
        return exact_st[0], "exact name + state"
    # LeadOcean holds stub records (0 staff, odd domains) beside the real one; with exactly one staffed exact
    # in-state record and no staffed same-name rival elsewhere, the stubs are not a real ambiguity.
    staffed = [c for c in exact_st if (c.get("employees") or 0) > 0]
    if len(exact_st) > 1 and len(staffed) == 1 and not any((c.get("employees") or 0) > 0 for c in rival):
        return staffed[0], "exact name + state (only staffed record)"
    ck = f"match|{t['vertical']}|{t['key']}"
    if ck not in jev_cache:
        if offline or budget[0] <= 0:
            return None, "ambiguous match (no Jev budget/offline)"
        from execution.modules import jev_client as jev
        if not jev.available():
            return None, "ambiguous match (Jev unavailable)"
        opts = {f"c{i}": f"{c['name']} | {c['domain']} | HQ {c['city']}, {c['state']} | {c['industries']} | "
                         f"{c['employees']} staff | {c['description'][:160]}" for i, c in enumerate(cands[:8])}
        opts["none"] = "none of these is the same organisation"
        state = {"source": "FDA 510(k) applicant" if t["vertical"] == "medtech" else "federal contract recipient",
                 "name": t["org"], "city": t.get("city"), "state": t["state"],
                 "context": t.get("device_raw") or t.get("description") or ""}
        r = jev.decide(state, {"m": jev.choice("Which company record is the same organisation as the named "
                                               "applicant/recipient (same legal business, not just a similar name)?",
                                               opts)})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "match", "cost": r.cost_usd})
        with _lock:
            jev_cache[ck] = {"pick": r.choice("m") if not r.error else "", "conf": r.confidence("m"),
                             "error": (r.error or "")[:200]}
    j = jev_cache[ck]
    if j.get("error"):
        return None, "ambiguous match (Jev error)"
    if j["pick"] and j["pick"] != "none" and j["conf"] >= JEV_MATCH_CONF:
        i = int(j["pick"][1:])
        if i < len(cands):
            return cands[i], f"jev {j['conf']:.2f}"
    return None, f"ambiguous match rejected by Jev ({j['pick'] or '-'} {j['conf']:.2f})"


# ------------------------------------------------------------------ 2b. web domain discovery (unmatched companies)
SEARCH_SKIP = re.compile(
    r"(^|\.)(linkedin|facebook|instagram|twitter|x|youtube|yelp|bbb|zoominfo|dnb|bloomberg|buzzfile|opencorporates|"
    r"bizapedia|manta|crunchbase|pitchbook|cbinsights|rocketreach|signalhire|apollo|glassdoor|indeed|wikipedia|"
    r"yellowpages|chamberofcommerce|buildzoom|houzz|angi|homeadvisor|thumbtack|porch|nextdoor|google|amazon|"
    r"mapquest|govtribe|goveagle|highergov|contractology|contractstackpro|sweetspot|usaspending|govspend|"
    r"opengovus|corporationwiki|owler|tracxn|cortera|fdazilla|globaldata|medicaldevicesnews|fda|sam|"
    r"dandb|companieslist|allbiz|birdeye|procore|levelset|reddit|quora|ziprecruiter|salary|comparably|"
    r"prnewswire|businesswire|globenewswire|newswire|issuu|scribd|pdf|govcb|federalcompass|bidnet)\.[a-z.]+$"
    r"|\.(gov|mil|edu)$")
GENERIC_NAME = {"construction", "constructors", "contractors", "contracting", "contractor", "services", "service",
                "group", "company", "solutions", "systems", "medical", "industries", "enterprises", "general",
                "builders", "building", "engineering", "the", "and", "of", "usa", "us", "america", "american",
                "international", "technologies", "technology", "national", "pacific", "western", "northwest"}


def _visible_text(html: str) -> tuple[str, str]:
    title = re.search(r"<title[^>]*>(.*?)</title>", html or "", flags=re.S | re.I)
    body = re.sub(r"<script.*?</script>|<style.*?</style>|<noscript.*?</noscript>", " ", html or "", flags=re.S | re.I)
    body = html_lib.unescape(re.sub(r"<[^>]+>", " ", body))
    title_s = html_lib.unescape(re.sub(r"\s+", " ", title.group(1)).strip()[:150]) if title else ""
    return title_s, re.sub(r"\s+", " ", body).strip()


def homepage_text(dom: str) -> dict:
    """Static fetch first (cheap), rendered fetch when the static page is thin or blocked."""
    for url in (f"https://{dom}", f"https://www.{dom}"):
        try:
            h = requests.get(url, headers={"User-Agent": mt.UA}, timeout=20)
            if h.status_code < 400:
                title, text = _visible_text(h.text)
                if len(text) >= 200:
                    return {"url": h.url, "title": title, "text": text}
        except requests.RequestException:
            pass
    r = mt.pw_fetch([{"url": f"https://{dom}", "mode": "text"}])[0]
    if not r.get("error") and (r.get("status") or 0) < 400 and (r.get("text") or "").strip():
        return {"url": r.get("final_url") or f"https://{dom}", "title": "", "text": re.sub(r"\s+", " ", r["text"])}
    return {"url": "", "title": "", "text": ""}


def web_search(q: str, counter: dict) -> tuple[list[dict] | None, str]:
    """Serper (Google) while under the cap and not out of credits; DuckDuckGo HTML otherwise. Returns organic
    [{link,title,snippet}], or None when no search engine answered (so the caller does not cache a false miss)."""
    key = os.environ.get("SERPER_API_KEY", "")
    with _lock:
        use_serper = bool(key) and not counter.get("serper_dead") and counter["serper"] < counter["serper_cap"]
        if use_serper:
            counter["serper"] += 1
    if use_serper:
        try:
            r = requests.post("https://google.serper.dev/search", json={"q": q, "num": 10}, timeout=20,
                              headers={"X-API-KEY": key, "Content-Type": "application/json"})
            if r.status_code == 200:
                return [{"link": o.get("link", ""), "title": o.get("title", ""), "snippet": o.get("snippet", "")}
                        for o in r.json().get("organic", [])], "serper"
            with _lock:  # 400 "Not enough credits" / 401 / 403: stop calling it this run
                counter["serper"] -= 1
                counter["serper_dead"] = f"HTTP {r.status_code} {r.text[:80]}"
        except (requests.RequestException, ValueError):
            pass
    if counter.get("ddg_dead"):
        return None, "none"
    try:
        with _lock:
            counter["ddg"] += 1
        h = requests.post("https://html.duckduckgo.com/html/", data={"q": q}, headers={"User-Agent": mt.UA}, timeout=20)
        if h.status_code != 200 or "result__a" not in h.text and "No results" not in h.text:
            raise requests.RequestException(f"HTTP {h.status_code}")
        out = []
        for m in re.finditer(r'class="result__a" href="([^"]+)"[^>]*>(.*?)</a>', h.text, flags=re.S):
            link = urllib.parse.unquote(re.sub(r"^.*?uddg=([^&]+).*$", r"\1", m.group(1)))
            out.append({"link": link, "title": re.sub(r"<[^>]+>", "", m.group(2)), "snippet": ""})
        return out, "ddg"
    except requests.RequestException as exc:
        with _lock:
            counter["ddg_dead"] = str(exc)[:80]  # blocked/unreachable: do not retry every company
        return None, "none"


def guess_domains(org: str) -> list[str]:
    """Free fallback when search is unavailable: the name written as a .com (with/without generic words)."""
    out = []
    for v in name_variants(org):
        w = v.split()
        core = [x for x in w if x not in GENERIC_NAME]
        for parts in (w, core, w + ["inc"]):
            if parts and len("".join(parts)) >= 6:
                out.append("".join(parts) + ".com")
    return list(dict.fromkeys(out))[:4]


def static_homepage(dom: str) -> dict:
    for url in (f"https://{dom}", f"https://www.{dom}"):
        try:
            h = requests.get(url, headers={"User-Agent": mt.UA}, timeout=12)
            if h.status_code < 400:
                title, text = _visible_text(h.text)
                if len(text) >= 200:
                    return {"url": h.url, "title": title, "text": text}
        except requests.RequestException:
            pass
    return {"url": "", "title": "", "text": ""}


def recipient_location(t: dict, cache: dict, offline: bool) -> None:
    """Construction triggers carry no city: read the recipient address from the USAspending award (free)."""
    if t["vertical"] != "construction" or t.get("city"):
        return
    gid = t["evidence_url"].rsplit("/", 1)[-1]
    if gid not in cache and not offline:
        try:
            loc = (requests.get(ct.AWARD_API.format(gid), timeout=60).json().get("recipient") or {}).get("location") or {}
            with _lock:
                cache[gid] = {"city": (loc.get("city_name") or "").title(), "street": loc.get("address_line1") or "",
                              "zip": loc.get("zip5") or ""}
        except (requests.RequestException, ValueError):
            return
    t.update(cache.get(gid) or {})


def name_on_page(org: str, text: str) -> bool:
    page = " " + " ".join(mt.norm_tokens(text)) + " "
    for v in name_variants(org):
        if f" {v} " in page:
            return True
        core = [w for w in v.split() if w not in GENERIC_NAME and len(w) >= 3]
        if core and all(f" {w} " in page for w in core) and len(core) >= 2:
            return True
    return False


def address_on_page(t: dict, text: str) -> bool:
    page = " " + " ".join(mt.norm_tokens(text)) + " "
    street = " ".join(mt.norm_tokens(t.get("street") or ""))
    num = (re.match(r"\d+", street) or [""])[0]
    return bool((street and len(street) >= 8 and f" {street} " in page)
                or (t.get("zip") and num and f" {t['zip']} " in page and f" {num} " in page))


def candidate_domains(org: str, results: list[dict]) -> list[dict]:
    """Company homepages only: root-URL hits, or deeper hits whose domain spells a distinctive name word."""
    words = {w for v in name_variants(org) for w in v.split() if len(w) >= 4 and w not in GENERIC_NAME}
    out: dict[str, dict] = {}
    for o in results:
        dom = norm_domain(o["link"])
        if not dom or SEARCH_SKIP.search(dom) or dom in out:
            continue
        path = urllib.parse.urlparse(o["link"]).path.strip("/")
        label = mt.domain_root(dom)
        if path and not any(w in label for w in words):
            continue
        out[dom] = o
        if len(out) >= 3:
            break
    return [dict(o, domain=d) for d, o in out.items()]


def discover_domain(t: dict, cache: dict, counter: dict, budget: list[int], offline: bool) -> tuple[dict | None, str]:
    """Search name + city/state, keep homepages that show the name or the record's street address, Jev picks one
    (or none). Returns (candidate dict, note)."""
    ck = f"{t['vertical']}|{t['key']}"
    if ck in cache:
        e = cache[ck]
        return (e.get("pick_c"), e["note"])
    if offline:
        return None, "domain discovery not run (offline)"
    if counter["serper"] >= counter["serper_cap"] and counter.get("no_ddg"):
        return None, "domain discovery skipped (search cap)"
    name = strip_legal(re.split(r"\b(?:d/?b/?a|doing business as)\b", t["org"], flags=re.I)[0]).strip(" ,.")
    where = f"{t['city']} {t['state']}" if t.get("city") else t["state"]
    hint = "" if t.get("city") else (" contractor" if t["vertical"] == "construction" else " medical")
    queries = [f'"{name}" {where}{hint}', f"{name} {t['state']} {VERTICAL[t['vertical']]['search_word']}"]
    res, src, cands, answered = [], "", [], False
    for q in queries:  # second, looser query only when the first finds no homepage candidate
        got, src = web_search(q, counter)
        if got is None:
            continue
        answered, res = True, got
        cands = candidate_domains(t["org"], res)
        if cands:
            break
    if not cands:  # search unavailable or no homepage in results: try the name as a .com (validated like any hit)
        cands = [{"domain": d, "link": f"https://{d}", "title": "", "snippet": "", "guess": True}
                 for d in guess_domains(t["org"])]
        src = "domain guess"
    checked = []
    for c in cands:
        hp = static_homepage(c["domain"]) if c.get("guess") else homepage_text(c["domain"])
        if not hp["text"]:
            continue
        fdom = norm_domain(hp["url"]) or c["domain"]
        nm, ad = name_on_page(t["org"], hp["title"] + " " + hp["text"]), address_on_page(t, hp["text"])
        if nm or ad:
            checked.append(dict(c, final_domain=fdom, title=hp["title"], excerpt=hp["text"][:500], name_hit=nm,
                                addr_hit=ad))
    entry = {"source": src, "query_results": len(res), "candidates": [c["domain"] for c in cands],
             "validated": [{k: c[k] for k in ("domain", "final_domain", "name_hit", "addr_hit")} for c in checked]}
    pick = None
    if not checked and not answered:
        return None, "domain discovery: no search engine answered (not cached)"
    if not checked:
        entry["note"] = "no LeadOcean company; web search found no homepage naming it"
    elif budget[0] <= 0:
        entry["note"] = "domain discovery: no Jev budget"
    else:
        from execution.modules import jev_client as jev
        opts = {f"d{i}": f"{c['final_domain']} | title: {c['title']} | search snippet: {c['snippet'][:200]} | "
                         f"page shows name: {c['name_hit']}, shows record street address: {c['addr_hit']} | "
                         f"page text: {c['excerpt'][:300]}" for i, c in enumerate(checked)}
        opts["none"] = "none of these websites belongs to the named organisation"
        state = {"source": "FDA 510(k) applicant" if t["vertical"] == "medtech" else "federal contract recipient",
                 "name": t["org"], "city": t.get("city"), "state": t["state"], "street": t.get("street", ""),
                 "context": t.get("device_raw") or t.get("description") or ""}
        r = jev.decide(state, {"m": jev.choice("Which website is the official own website of this exact organisation "
                                               "(same business at that city/state, not a namesake, directory, "
                                               "parent group or customer)?", opts)})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "domain", "cost": r.cost_usd})
        pk, conf = (r.choice("m") if not r.error else ""), r.confidence("m")
        entry.update(jev_pick=pk, jev_conf=conf, jev_error=(r.error or "")[:200])
        if pk.startswith("d") and conf >= JEV_MATCH_CONF and int(pk[1:]) < len(checked):
            c = checked[int(pk[1:])]
            pick = {"domain": c["final_domain"], "name": c["title"] or name, "city": t.get("city", ""),
                    "state": t["state"], "employees": None, "industries": "", "description": c["excerpt"][:600],
                    "linkedin": "", "decision_makers": None, "domain_source": src}
            entry["note"] = f"web domain ({src}) + jev {conf:.2f}"
        else:
            entry["note"] = f"web candidates rejected by Jev ({pk or '-'} {conf:.2f})"
    entry["pick_c"] = pick
    with _lock:
        cache[ck] = entry
    return pick, entry["note"]


def lo_company_by_domain(lo: LeadOcean, dom: str, cache: dict, offline: bool) -> dict | None:
    key = f"domain|{dom}"
    if key not in cache:
        if offline:
            return None
        try:
            j = lo.req("GET", "/v1/companies/search", params={"domain": dom, "limit": 3, "slim": "true"})
        except RuntimeError:
            return None
        best = None
        for c in j.get("data") or []:
            d = c.get("company_data") or {}
            if norm_domain(d.get("company_domain")) != dom:
                continue
            emp = (d.get("company_employees") or {}).get("number_of_employees")
            if best is None or (emp or 0) > (best["employees"] or 0):
                addr = d.get("company_primary_address") or {}
                best = {"name": d.get("company_name") or "", "employees": emp, "lo_city": addr.get("city") or "",
                        "lo_state": addr.get("state") or "",
                        "industries": ", ".join(i.get("name3", "") for i in (d.get("company_industries") or [])[:3]),
                        "description": (d.get("company_description") or "")[:600],
                        "linkedin": ((d.get("company_social_links") or {}).get("linkedin") or {}).get("url") or ""}
        with _lock:
            cache[key] = best
    return cache[key]


# ------------------------------------------------------------------ 3a. Apollo second-opinion headcount
def apollo_size(dom: str, cache: dict, counter: dict, offline: bool) -> dict:
    """GET organizations/enrich (the only endpoint on this free key; the proxy injects the key). Cached by domain."""
    if dom in cache:
        return cache[dom]
    if offline or counter["apollo"] >= counter["apollo_cap"]:
        return {}
    with _lock:
        counter["apollo"] += 1
    try:
        r = requests.get("https://api.apollo.io/api/v1/organizations/enrich", params={"domain": dom},
                         headers={"X-Api-Key": "proxy-injected"}, timeout=30)
    except requests.RequestException as exc:
        return {"error": type(exc).__name__}  # not cached: retry next run
    if r.status_code != 200:
        return {"error": f"HTTP {r.status_code}"}
    o = (r.json() or {}).get("organization") or {}
    e = {"employees": o.get("estimated_num_employees"), "name": o.get("name") or "", "country": o.get("country") or "",
         "state": o.get("state") or "", "domain": norm_domain(o.get("primary_domain") or "")}
    with _lock:
        cache[dom] = e
    return e


# ------------------------------------------------------------------ 3. size + vertical gate
def size_check(t: dict, c: dict, cfg: dict, apollo_cache: dict, counter: dict, offline: bool) -> tuple[bool, str]:
    """LinkedIn (LeadOcean) headcount decides; when it is missing or below cfg['apollo_below'], an Apollo estimate for
    the same domain (US records only) decides instead. Records which source decided and whether Apollo flipped it."""
    lo_emp = c.get("employees")
    lo_emp = int(lo_emp) if lo_emp not in (None, "") else None
    lo_min, hi = cfg["min_emp"][t["vertical"]], cfg["max_emp"]
    size, src = lo_emp, "linkedin"
    t["size_linkedin"], t["size_apollo"] = lo_emp, ""
    if lo_emp is None or lo_emp < cfg["apollo_below"]:
        ap = apollo_size(c["domain"], apollo_cache, counter, offline)
        t["size_apollo"] = ap.get("employees") if ap.get("employees") is not None else (ap.get("error") or "none")
        us = (ap.get("country") or "United States") == "United States"
        if ap.get("employees") and us:
            size, src = int(ap["employees"]), "apollo"
        elif ap.get("employees"):
            t["size_apollo"] = f"{ap['employees']} (ignored: {ap.get('country')})"
    t["size_source"] = src
    ok = size is not None and lo_min <= size <= hi
    lo_ok = lo_emp is not None and lo_min <= lo_emp <= hi
    t["apollo_flipped"] = src == "apollo" and ok != lo_ok
    if size is None:
        return False, "size unknown (LinkedIn and Apollo)"
    if not ok:
        return False, f"size {size} ({src}) outside {lo_min}-{hi}"
    return True, f"size {size} ({src})"


def gate(t: dict, c: dict, jev_cache: dict, budget: list[int], offline: bool, cfg: dict, apollo_cache: dict,
         counter: dict) -> tuple[bool, str]:
    ok, note = size_check(t, c, cfg, apollo_cache, counter, offline)
    if not ok:
        return False, note
    emp, lo_min, hi = c.get("employees"), cfg["min_emp"][t["vertical"]], cfg["max_emp"]
    ck = f"gate|{t['vertical']}|{c['domain']}"
    if ck not in jev_cache:
        if offline or budget[0] <= 0:
            return False, "gate not run (no Jev budget/offline)"
        from execution.modules import jev_client as jev
        if not jev.available():
            return False, "gate not run (Jev unavailable)"
        v = VERTICAL[t["vertical"]]
        state = {"company": c["name"], "domain": c["domain"], "hq": f"{c['city']}, {c['state']}",
                 "linkedin_staff": emp, "apollo_staff_estimate": t.get("size_apollo") or "",
                 "industries": c["industries"], "description": c["description"],
                 "public_record_name": t["org"], "parent_in_public_record": t.get("parent") or ""}
        r = jev.decide(state, {"g": jev.noul(
            f"Is this a real, independent operating company of roughly {lo_min}-{hi} staff whose main business "
            f"is: {v['label']}?",
            f"an operating business in that line of work, roughly {lo_min}-{hi} staff, its own brand/website",
            "a shell or holding entity, a subsidiary/division of a large group, a university, hospital or health "
            "system, a government or tribal entity, a nonprofit, a consultancy/distributor, or a different industry")})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "gate", "cost": r.cost_usd})
        with _lock:
            jev_cache[ck] = {"noul": r.noul("g", -1.0) if not r.error else -1.0, "error": (r.error or "")[:200]}
    j = jev_cache[ck]
    if j.get("error"):
        return False, "gate Jev error"
    return (j["noul"] >= JEV_GATE_NOUL), f"{note}; jev gate {j['noul']:.2f}"


# ------------------------------------------------------------------ 4. homepage site fact (finder + blind verifier)
def trigger_terms(t: dict, company: str) -> list[str]:
    """Strings whose presence on the homepage means it DOES mention the trigger."""
    if t["vertical"] == "medtech":
        terms = mt.search_queries(t["device"]) + [t["device"], t["k_number"]]
        co = set(mt.norm_tokens(company)) | set(mt.norm_tokens(t["org"]))
        # brand word: only coined-looking tokens (inner capital or digit, e.g. LOBO, iCare, X5), never plain words
        brand = [w for w in re.findall(r"[A-Za-z][A-Za-z0-9\-]{3,}", mt.clean_device(re.sub(r"[\x80-\x9f]", "", t["device_raw"])).split(";")[0])
                 if w.lower() not in mt.GENERIC and w.lower() not in co
                 and (re.search(r"[A-Z]", w[1:]) or re.search(r"\d", w)) and not w.isupper() or
                 (w.isupper() and len(w) <= 6 and w.lower() not in mt.GENERIC and w.lower() not in co
                  and t["device_raw"] != t["device_raw"].upper())]
        if brand:
            terms.append(brand[0])  # first distinctive word = product brand
    else:
        terms = [t["award_id"], t["agency"], t["agency_raw"]]
        if t["agency"] == "U.S. Forest Service":
            terms.append("Forest Service")
    return list(dict.fromkeys(x for x in terms if x and len(x) >= 4))


def find_terms(text: str, terms: list[str]) -> list[str]:
    low = re.sub(r"\s+", " ", text or "").lower()
    return [x for x in terms if re.search(r"(?<![a-z0-9])" + re.escape(x.lower()) + r"(?![a-z0-9])", low)]


def site_fact_text(t: dict, dom: str) -> str:
    if t["vertical"] == "medtech":
        return f"the {dom} homepage does not mention the {t['device']}"
    return f"the {dom} homepage does not mention the {t['agency']} award"


def finder(t: dict, c: dict) -> dict:
    url = f"https://{c['domain']}"
    r = mt.pw_fetch([{"url": url, "mode": "text"}])[0]
    if r.get("error") or not (r.get("text") or "").strip() or (r.get("status") or 0) >= 400:
        url = f"https://www.{c['domain']}"  # some hosts only answer on www
        r = mt.pw_fetch([{"url": url, "mode": "text"}])[0]
    if r.get("error") or not (r.get("text") or "").strip() or (r.get("status") or 0) >= 400:
        return {"ok": False, "reason": f"homepage unreachable ({r.get('status') or r.get('error', '')[:60]})"}
    terms = trigger_terms(t, c["name"])
    hits = find_terms(r["text"], terms)
    final = r.get("final_url") or url
    fdom = norm_domain(final)
    out = {"final_url": final, "final_domain": fdom, "terms": terms, "hits": hits, "chars": len(r["text"])}
    if len(r["text"]) < 200:
        return dict(out, ok=False, reason="homepage text too thin to judge (<200 chars)")
    if hits:
        return dict(out, ok=False, reason=f"homepage mentions the trigger ({hits[0]})")
    if mt.domain_root(fdom) != mt.domain_root(c["domain"]):
        return dict(out, ok=False, reason=f"homepage redirects to another site ({fdom})")
    return dict(out, ok=True, fact=site_fact_text(t, c["domain"]))


def verifier(t: dict, c: dict, claim: dict) -> tuple[bool, str]:
    """Blind re-derivation from public records + a fresh fetch; sees only domain, record id and the claim."""
    if t["vertical"] == "medtech":
        d = mt.fda_get({"search": f"k_number:{t['k_number']}"}).get("results", [])
        if len(d) != 1:
            return False, "K number not found in openFDA"
        r = d[0]
        if r["decision_date"] != t["date"] or short_device(r["device_name"], r["applicant"]) != t["device"]:
            return False, "openFDA date/device mismatch"
        if (r.get("state") or "").upper() != t["state"] or norm_name(r["applicant"]) != norm_name(t["org"]):
            return False, "openFDA applicant/state mismatch"
    else:
        gid = t["evidence_url"].rsplit("/", 1)[-1]
        try:
            a = requests.get(ct.AWARD_API.format(gid), timeout=60).json()
        except (requests.RequestException, ValueError) as exc:
            return False, f"award re-fetch failed {type(exc).__name__}"
        if (a.get("piid") or "") != t["award_id"]:
            return False, "award id mismatch"
        if (a.get("recipient") or {}).get("recipient_uei") != t["uei"] and t["uei"]:
            return False, "recipient UEI mismatch"
        if (a.get("date_signed") or "")[:10] != t["date"]:
            return False, f"award date_signed {a.get('date_signed')} != action_date"
    terms = trigger_terms(t, c["name"])
    r = mt.pw_fetch([{"url": claim["final_url"], "mode": "text"}])[0]
    if r.get("error") or not r.get("text"):
        return False, "verifier render failed"
    hits = find_terms(r["text"], terms)
    try:
        h = requests.get(claim["final_url"], headers={"User-Agent": mt.UA}, timeout=30)
        static = re.sub(r"<script.*?</script>|<style.*?</style>", " ", h.text, flags=re.S | re.I)
        hits += find_terms(re.sub(r"<[^>]+>", " ", static), terms)
    except requests.RequestException:
        pass  # static HTML is a second look only; the fresh render already decided
    if hits:
        return False, f"verifier found the trigger on the homepage ({hits[0]})"
    return True, "verifier: record re-confirmed, homepage silent on trigger"


def site_check(t: dict, c: dict, cache: dict, offline: bool) -> dict:
    ck = f"{t['key']}|{c['domain']}"
    if ck in cache:
        return cache[ck]
    if offline:
        return {"ok": False, "reason": "site not checked (offline)", "uncached": True}
    f = finder(t, c)
    if f.get("ok"):
        ok, note = verifier(t, c, f)
        f.update(verified=ok, verifier_note=note)
        if not ok:
            f.update(ok=False, reason=note)
    with _lock:
        cache[ck] = f
    return f


# ------------------------------------------------------------------ 5. contacts + emails
def contacts_for(lo: LeadOcean, dom: str, cache: dict, offline: bool) -> list[dict]:
    if dom in cache:
        return cache[dom]
    if offline:
        return []
    params = {"domain": dom, "emailStatus": "verified", "emailType": "work", "seniority": ",".join(CONTACT_SENIORITY),
              "excludeTitle": ",".join(EXCL_TITLE), "limit": 25, "slim": "true"}
    try:
        j = lo.req("GET", "/v1/people/search", params=params)
    except RuntimeError as exc:
        print(f"people search failed for a domain: {str(exc)[:120]}")
        return []
    out = []
    for p in j.get("data") or []:
        pd, cd = p.get("profile_data") or {}, p.get("contact_data") or {}
        cur = [e for e in cd.get("contact_current_experiences") or []
               if e.get("current") and norm_domain(e.get("company_domain")) == dom]
        if not cur:
            continue
        out.append({"person_id": ((p.get("meta") or {}).get("source_ids") or {}).get("person_id"),
                    "first_name": pd.get("profile_first_name") or "", "last_name": pd.get("profile_last_name") or "",
                    "title": cur[0].get("job_title") or "", "linkedin": pd.get("profile_url") or "",
                    "email_status": cd.get("email_status"), "email_type": cd.get("email_type"),
                    "has_email": cd.get("has_email")})
    with _lock:
        cache[dom] = out
    return out


def reveal_email(lo: LeadOcean, pid: str, cache: dict, breaker: dict, offline: bool) -> str:
    """GET /v2/people/email/work (1 record). Only successes are cached, so a re-run retries outages."""
    if pid in cache:
        return cache[pid].get("email") or ""
    if offline or breaker["open"]:
        return ""
    try:
        r = lo.s.get("https://api.leadocean.io/v2/people/email/work", params={"contact_id": pid}, timeout=60)
    except requests.RequestException as exc:
        breaker["last"] = type(exc).__name__
        return ""
    if r.status_code == 200:
        d = (r.json() or {}).get("data") or {}
        email = (d.get("address") or d.get("email") or "").lower() if isinstance(d, dict) else ""
        with _lock:
            cache[pid] = {"email": email, "status": d.get("status") if isinstance(d, dict) else None,
                          "raw_keys": sorted(d)[:12] if isinstance(d, dict) else []}
        return email
    with _lock:
        breaker["fails"] += 1
        breaker["last"] = f"HTTP {r.status_code}: {r.text[:160]}"
        if breaker["fails"] >= 5:
            breaker["open"] = True  # service down: stop spending calls, report pending
    return ""


def try_export(lo: LeadOcean, domains: list[str], ledger_path: Path) -> dict:
    """One domain-filtered export (<= 50 domains, the API max) as the email fallback. Ledgered; never re-queued
    unless the prior job failed (failed jobs bill 0)."""
    led = jload(ledger_path, {})
    doms = sorted(domains)[:50]
    key = "x" + str(abs(hash("|".join(doms))) % 10**10)
    job = led.get(key)
    left = lo.req("GET", "/v1/account")["data"]["exports"]["day"]
    if not job or job.get("status") in ("failed", "cancelled"):
        if int(left["limit"]) - int(left["used"]) < 200:
            return {"status": "skipped", "error": "export quota below 200 rows"}
        body = {"name": f"trigger batch {dt.date.today()}", "limit": 200,
                "filters": {"domain": doms, "emailStatus": ["verified"], "emailType": ["work"],
                            "seniority": CONTACT_SENIORITY, "excludeTitle": EXCL_TITLE},
                "columns": ["person_id", "profile_first_name", "current_company_domain", "current_job_title",
                            "email_N_address", "email_N_type", "email_N_status"], "caps": {"emails": 3}}
        try:
            data = lo.req("POST", "/v1/exports", body=body)["data"]
        except RuntimeError as exc:
            return {"status": "error", "error": str(exc)[:300]}
        job = {"id": data.get("id"), "status": data.get("status"), "domains": len(doms), "attempts":
               (job or {}).get("attempts", 0) + 1}
        led[key] = job
        jsave(ledger_path, led)
    for _ in range(40):  # ~4 min
        d = lo.req("GET", f"/v1/exports/{job['id']}")["data"]
        job.update(status=d.get("status"), error=str(d.get("error") or d.get("failureReason") or "")[:300],
                   rows=d.get("rows") or d.get("rowCount"))
        if job["status"] in ("completed", "done", "failed", "cancelled", "ready"):
            break
        time.sleep(6)
    led[key] = job
    jsave(ledger_path, led)
    if job["status"] in ("completed", "done", "ready"):
        r = lo.req("GET", f"/v1/exports/{job['id']}/download", raw=True, timeout=180)
        job["csv"] = r.text
    return job


# ------------------------------------------------------------------ 6. contact + copy gates
# Title allowlist, role-inbox drop, one chief executive per company, company/device/person display names, size flag.
JEV_TITLE_CONF = 0.7   # choice confidence needed to keep an edge-case title (else dropped)
JEV_DISPLAY_CONF = 0.7  # choice confidence needed to replace the record name with a homepage name
_VP = re.compile(r"\bvice[- ]?president\b|\b[se]?vp\b|\bavp\b")
TITLE_FORMER = re.compile(r"\b(former|retired|emeritus)\b|\bex[- ]|\bassistant to\b|\bexecutive assistant\b|\bintern\b"
                          r"|\badvis[oe]r\b")
TITLE_EXEC = re.compile(r"\b(ceo|chief executive|president|owner|co-?owner|founder|co-?founder|cofounder)\b")
TITLE_SENIOR = re.compile(r"\b(managing partner|principal|general manager|gm|coo|chief operating officer|managing director)\b")
TITLE_GROWTH_CHIEF = re.compile(r"\bcmo\b|\bchief (marketing|commercial|revenue|growth|brand|communications|"
                                r"business development|sales) officer\b")
TITLE_GROWTH_AREA = re.compile(r"\b(marketing|brand|branding|communications|public relations|business development|"
                               r"growth)\b")
TITLE_SALES = re.compile(r"\b(sales|commercial|revenue)\b")
TITLE_DENY = re.compile(
    r"\b(hr|human resources?|people|talent|recruit\w*|finance|financial|cfo|accounting|accountant|controller|treasurer|"
    r"tax|payroll|compliance|quality|qa|qc|regulatory|clinical|r ?& ?d|research|engineering|engineer|cto|technology|"
    r"technical|it|information|data|software|product|products|operations|operational|safety|hse|ehs|legal|counsel|"
    r"procurement|purchasing|supply chain|manufacturing|production|estimat\w*|project manager|superintendent|"
    r"scien\w*|medical affairs|preconstruction)\b")
TITLE_EDGE = re.compile(r"\b(vp|vice president|director|head|chief|partner|chair\w*|executive)\b")
CHIEF_EXEC = re.compile(r"\bceo\b|\bchief executive\b")
RANK_OF = {"chief_exec": 0, "growth_lead": 1, "senior_general": 2}
ROLE_LOCAL = {"info", "contact", "contactus", "sales", "admin", "office", "hello", "hi", "marketing", "support", "team",
              "inquiries", "inquiry", "enquiries", "enquiry", "mail", "email", "general", "accounts", "accounting", "ar",
              "ap", "billing", "hr", "jobs", "careers", "service", "services", "customerservice", "webmaster",
              "noreply", "donotreply", "press", "media", "help", "orders", "estimating", "estimates", "bids", "bid",
              "projects", "reception", "frontdesk", "main", "ops", "operations", "postmaster", "careers", "info1"}
ROLE_PREFIX = re.compile(r"^(info|sales|admin|office|contact|support|hello|marketing|team|inquir|enquir|estimat|"
                         r"bids?|careers|customerservice|noreply|no-reply)([._\-+]|\d|$)")


def title_rule(title: str) -> tuple[str, str]:
    """Deterministic title class: chief_exec / growth_lead / senior_general (keep), drop, or edge (Jev decides)."""
    t = re.sub(r"\s+", " ", (title or "").lower().replace("&", " & "))
    if not t.strip():
        return "drop", "no title"
    if TITLE_FORMER.search(t):
        return "drop", "former/assistant/advisor title"
    vp = bool(_VP.search(t))
    allow = ""
    if TITLE_EXEC.search(_VP.sub(" ", t)):
        allow = "chief_exec"
    elif TITLE_GROWTH_CHIEF.search(t) or (TITLE_GROWTH_AREA.search(t) and (vp or re.search(r"\b(director|head)\b", t))):
        allow = "growth_lead"
    elif TITLE_SALES.search(t) and (vp or re.search(r"\b(chief|head)\b", t)):
        allow = "growth_lead"
    elif TITLE_SENIOR.search(t):
        allow = "senior_general"
    deny = TITLE_DENY.search(t)
    if allow and not deny:
        return allow, "allowlisted title"
    if allow and deny:
        return "edge", f"allowlisted + excluded word ({deny.group(0)})"
    if deny:
        return "drop", f"excluded function ({deny.group(0)})"
    if TITLE_SALES.search(t):
        return "drop", "sales below VP"
    if TITLE_EDGE.search(t):
        return "edge", "senior title outside the allowlist"
    return "drop", "not a buyer title"


def title_class(title: str, jev_cache: dict, budget: list[int], offline: bool) -> tuple[str, str]:
    """title_rule, then one cached Jev choice (with a none option) for edge cases. Returns (class|'drop', reason)."""
    cls, why = title_rule(title)
    if cls != "edge":
        return cls, f"rule: {why}"
    ck = "title|" + re.sub(r"\s+", " ", title.strip().lower())
    if ck not in jev_cache:
        if offline or budget[0] <= 0:
            return "drop", "edge title not judged (offline/no Jev budget)"
        from execution.modules import jev_client as jev
        if not jev.available():
            return "drop", "edge title not judged (Jev unavailable)"
        r = jev.decide({"job_title": title, "company_size": "20-500 staff"}, {"t": jev.choice(
            "Would a person with this job title buy or champion a new company website / brand project at a "
            "20-500 person company? Pick their role group, or none.",
            {"chief_exec": "CEO, president, owner or founder of the company (a founder who also holds another "
                           "title still counts)",
             "growth_lead": "marketing, brand, communications or business-development lead, or a sales leader at "
                            "VP level or above",
             "senior_general": "COO, general manager, managing partner or principal",
             "none": "not a buyer: finance, HR/people, compliance, quality, regulatory, R&D, engineering, CTO/IT, "
                     "product, operations below COO, sales below VP, a regional/account role, or a board, "
                     "advisory or former role"})})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "title", "cost": r.cost_usd})
        with _lock:
            jev_cache[ck] = {"pick": r.choice("t") if not r.error else "", "conf": r.confidence("t"),
                             "error": (r.error or "")[:200]}
    j = jev_cache[ck]
    if j.get("error"):
        return "drop", "edge title Jev error"
    if j["pick"] in RANK_OF and j["conf"] >= JEV_TITLE_CONF:
        return j["pick"], f"jev {j['pick']} {j['conf']:.2f}"
    return "drop", f"edge title: Jev {j['pick'] or '-'} {j['conf']:.2f}"


def is_role_inbox(email: str) -> bool:
    lp = (email or "").split("@")[0].lower()
    return bool(lp) and (lp in ROLE_LOCAL or re.sub(r"[\d._\-+]+", "", lp) in ROLE_LOCAL or bool(ROLE_PREFIX.match(lp)))


def chief_rank(title: str) -> int:
    t = (title or "").lower()
    if re.search(r"\b(chairman|chairwoman|chair|president)\b", t) and CHIEF_EXEC.search(t):
        return 3
    if re.search(r"\bceo\b|chief executive officer", t):
        return 2
    return 1


# ---- page fetches (homepage once per output company; about/leadership pages only to resolve two chief executives)
PEOPLE_LINK = re.compile(r"leadership|our-team|team|management|executive|people|who-we-are|about", re.I)


def _meta(html: str, prop: str) -> str:
    for pat in (rf'<meta[^>]+(?:property|name)=["\']{prop}["\'][^>]*content=["\']([^"\']*)',
                rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*(?:property|name)=["\']{prop}["\']'):
        m = re.search(pat, html or "", flags=re.I)
        if m:
            return html_lib.unescape(m.group(1)).strip()[:120]
    return ""


def _logo_alt(html: str) -> str:
    for m in re.finditer(r"<img\b[^>]*>", html or "", flags=re.I):
        tag = m.group(0)
        if re.search(r"logo", tag, re.I):
            a = re.search(r'\balt=["\']([^"\']{2,80})["\']', tag, flags=re.I)
            if a:
                return html_lib.unescape(a.group(1)).strip()
    return ""


def _page_record(url: str, final: str, html: str, text: str) -> dict:
    title, _ = _visible_text(html) if html else ("", "")
    links = []
    for m in re.finditer(r'<a\b[^>]*href=["\']([^"\'#]+)["\']', html or "", flags=re.I):
        links.append(urllib.parse.urljoin(final or url, html_lib.unescape(m.group(1))))
    root = mt.domain_root(norm_domain(final or url))
    people = [u for u in dict.fromkeys(links) if PEOPLE_LINK.search(urllib.parse.urlparse(u).path or "")
              and mt.domain_root(norm_domain(u)) == root]
    ir = [u for u in dict.fromkeys(links) if re.match(r"https?://(investors?|ir)\.", u, re.I)
          or re.search(r"/investor-relations", urllib.parse.urlparse(u).path or "", re.I)]
    ir += [m.group(0) for m in re.finditer(r"investor relations", text or "", flags=re.I)][:1]
    return {"url": final or url, "title": title, "og_site_name": _meta(html, "og:site_name"),
            "og_title": _meta(html, "og:title"), "logo_alt": _logo_alt(html), "text": (text or "")[:30000],
            "people_links": people[:12], "ir_links": ir[:4]}


def fetch_page(url: str, rendered: bool = True) -> dict:
    """Static GET first; rendered (Playwright) fallback when the static page is thin or blocked."""
    try:
        h = requests.get(url, headers={"User-Agent": mt.UA}, timeout=15)
        if h.status_code < 400:
            _, text = _visible_text(h.text)
            if len(text) >= 200:
                return _page_record(url, h.url, h.text, text)
    except requests.RequestException:
        pass
    if not rendered:
        return {}
    r = mt.pw_fetch([{"url": url, "mode": "full"}])[0]
    if not r.get("error") and (r.get("status") or 0) < 400 and len((r.get("text") or "").strip()) >= 200:
        return _page_record(url, r.get("final_url") or url, r.get("html") or "", re.sub(r"\s+", " ", r["text"]))
    return {}


def site_pages(dom: str, cache: dict, need_people: bool, offline: bool) -> dict:
    """Cached per domain: {'home': page, 'people': [pages]}. Failures are cached too (re-run = no network)."""
    e = dict(cache.get(dom) or {})
    changed = False
    if "home" not in e and not offline:
        e["home"] = fetch_page(f"https://{dom}") or fetch_page(f"https://www.{dom}")
        changed = True
    if "ir_probe" not in e and not offline:  # listed companies run investors.<domain> / ir.<domain>
        e.pop("ir_host", None)
        e["ir_probe"] = ""
        for host in (f"investors.{dom}", f"ir.{dom}"):
            try:
                h = requests.get(f"https://{host}", headers={"User-Agent": mt.UA}, timeout=10)
            except requests.RequestException:
                continue  # no such host / unreachable: not evidence either way
            if h.status_code in (401, 403) and host in h.url:
                e["ir_probe"] = f"{host} (HTTP {h.status_code}, bot-blocked)"
                break
            if h.status_code < 400 and host in h.url and re.search(
                    r"investor|stock|shareholder|sec filing", h.text[:200000], re.I):
                e["ir_probe"] = host
                break
        changed = True
    if need_people and "people" not in e and not offline:
        home = e.get("home") or {}
        links = sorted(home.get("people_links") or [], key=lambda u: next(
            (i for i, k in enumerate(("leadership", "team", "management", "executive", "people", "about"))
             if k in u.lower()), 9))[:3]
        pages = []
        for u in links:
            p = fetch_page(u)
            if p:
                pages.append({"url": p["url"], "text": p["text"]})
        if not pages:  # no nav links found: try the usual paths, static only
            base = (home.get("url") or f"https://{dom}").rstrip("/")
            base = re.match(r"https?://[^/]+", base).group(0)
            for path in ("about", "about-us", "leadership", "team", "our-team", "company"):
                p = fetch_page(f"{base}/{path}", rendered=False)
                if p:
                    pages.append({"url": p["url"], "text": p["text"]})
                if len(pages) >= 2:
                    break
        e["people"] = pages
        changed = True
    if changed:
        with _lock:
            cache[dom] = e
    return e


def page_texts(pages: dict) -> list[str]:
    home = pages.get("home") or {}
    return [x for x in [home.get("title", ""), home.get("og_site_name", ""), home.get("logo_alt", ""),
                        home.get("text", "")] + [p.get("text", "") for p in pages.get("people") or []] if x]


# ---- spelling from the company's own pages
_TOK = re.compile(r"[A-Za-z0-9][A-Za-z0-9&'’.\-]*")


def _key(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower().replace("&", "and"))


def site_spellings(name: str, texts: list[str]) -> Counter:
    """Every way the pages write `name` (same letters/digits, any case/punctuation, +-1 token)."""
    target, n = _key(name), len(_TOK.findall(name))
    out: Counter = Counter()
    if not target or n == 0:
        return out
    for text in texts:
        if target not in _key(text):
            continue
        toks = _TOK.findall(text)
        for w in {max(1, n - 1), n, n + 1}:
            for i in range(len(toks) - w + 1):
                seg = " ".join(toks[i:i + w])
                if _key(seg) == target:
                    last = toks[i + w - 1]
                    out[seg.rstrip(".,") if len(_key(last)) > 2 else seg] += 1
    return out


def _has_inner_case(s: str) -> bool:
    return any(c.isupper() for w in s.split() for c in w[1:]) and any(c.islower() for c in s) or "'" in s or "’" in s


ROMAN = re.compile(r"^(ii|iii|iv|vi|vii|viii|ix|xi|xii)$", re.I)


def recase_name(base: str, from_caps_record: bool, texts: list[str]) -> str:
    """The company's own spelling of `base` from its pages; else deterministic fixes for capitalized ALL-CAPS records
    (roman numerals and vowel-less acronyms upper-cased)."""
    s = base
    if from_caps_record:
        s = " ".join(w.upper() if ROMAN.match(w) or (w.isalpha() and 2 <= len(w) <= 4 and not re.search(r"[aeiouy]", w,
                                                                                                         re.I)) else w
                     for w in s.split())
    cnt = site_spellings(s, texts)
    ntok = len(s.split())
    mixed = [(n, v) for v, n in cnt.items() if not v.isupper()]
    if mixed:  # most frequent; ties -> same token count as the record, then the variant with inner capitals
        best = max(mixed, key=lambda x: (x[0], len(x[1].split()) == ntok, _has_inner_case(x[1])))[1].replace("’", "'")
        if best != s and (best.lower() != s.lower() or _has_inner_case(best) or best.istitle() or s.isupper()
                          or s.islower()):
            return best
        return s
    caps = [v for v in cnt if v.isupper() and len(v.split()) == len(s.split())]
    if caps:  # only ALL-CAPS on the site: take its short words (acronyms) only
        return " ".join(c if len(_key(c)) <= 3 else w for c, w in zip(caps[0].split(), s.split()))
    return s


TITLE_SEP = re.compile(r"\s+[|\-–—:•·]\s+|\s*\|\s*")
NOT_NAME = re.compile(r"^(home|homepage|welcome|about|about us|contact|official site|official website|index|company|"
                      r"site|main|header|footer|image|untitled)$", re.I)


def homepage_name_candidates(home: dict) -> list[str]:
    raw = [home.get("og_site_name", ""), home.get("logo_alt", "")]
    for t in (home.get("title", ""), home.get("og_title", "")):
        raw += TITLE_SEP.split(t or "")
    out = []
    for c in raw:
        c = re.sub(r"^(welcome to|home of)\s+", "", html_lib.unescape(c or "").strip(), flags=re.I)
        c = re.sub(r"[\s_\-]*logo([\s_\-]*(new|white|black|dark|light|color|colour|main|header|footer|\d+))*$", "", c,
                   flags=re.I)
        c = re.sub(r"\s+(home|homepage)$", "", c, flags=re.I)
        c = strip_legal(c.strip(" ,.-|"))
        if c and not NOT_NAME.match(c) and 2 <= len(c) <= 40 and len(c.split()) <= 5 and re.search(r"[A-Za-z]", c):
            out.append(c)
    return list(dict.fromkeys(out))


def company_display_name(t: dict, co: dict, pages: dict, jev_cache: dict, budget: list[int], offline: bool) -> tuple[str, str]:
    """Merge-ready company name: record name (d/b/a part preferred) recased from the company's own pages; a homepage
    brand name (og:site_name / <title> / logo alt) replaces it only through a Jev choice that includes keep_original."""
    base = display_company(t["org"], co["name"])
    parts = re.split(r"\s+\b(?:d/?b/?a|doing business as)\b\.?\s+", base, flags=re.I)
    if len(parts) > 1:
        base = strip_legal(parts[-1].strip(" ,"))
    texts = page_texts(pages)
    rec = recase_name(base, t["org"].isupper(), texts)
    home = pages.get("home") or {}
    dom_key = _key(mt.domain_root(co["domain"]))
    base_tok = set(mt.norm_tokens(base)) - GENERIC_NAME
    cands = []
    for c in homepage_name_candidates(home):
        ck = _key(c)
        if ck == _key(rec):
            if c != rec and not c.isupper() and _has_inner_case(c) and not site_spellings(rec, texts).get(rec):
                rec = c  # the homepage's own casing of the same name (only when the pages never write rec itself)
            continue
        shares = bool(set(mt.norm_tokens(c)) & base_tok) or (len(ck) >= 4 and (ck in dom_key or dom_key in ck))
        if shares:
            cands.append(c)
    cands = cands[:4]
    if not cands:
        return rec, "record name" + (" (recased)" if rec != base else "")
    opts = {"keep_original": rec}
    opts.update({f"c{i}": c for i, c in enumerate(cands)})
    ck = "display|" + co["domain"] + "|" + "|".join(_key(v) for v in opts.values())
    if ck not in jev_cache:
        if offline or budget[0] <= 0:
            return rec, "record name (homepage names not judged: offline/no Jev budget)"
        from execution.modules import jev_client as jev
        if not jev.available():
            return rec, "record name (Jev unavailable)"
        state = {"public_record_name": t["org"], "leadocean_name": co["name"], "domain": co["domain"],
                 "homepage_title": home.get("title", ""), "og_site_name": home.get("og_site_name", ""),
                 "logo_alt": home.get("logo_alt", "")}
        r = jev.decide(state, {"d": jev.choice(
            "Which name should a cold email use for this company: the name it calls itself on its own homepage "
            "(its brand), with its own capitalisation and without Inc/LLC/Corp? Pick keep_original unless another "
            "option is clearly this same company's own name and better (fixes a truncated, mis-cased or bare-word "
            "name, or is the brand it trades under). Taglines, slogans, page names, services and other companies "
            "are never the answer.", {k: v for k, v in opts.items()})})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "display", "cost": r.cost_usd})
        with _lock:
            jev_cache[ck] = {"pick": r.choice("d") if not r.error else "", "conf": r.confidence("d"),
                             "error": (r.error or "")[:200]}
    j = jev_cache[ck]
    if not j.get("error") and j["pick"] in opts and j["pick"] != "keep_original" and j["conf"] >= JEV_DISPLAY_CONF:
        return recase_name(opts[j["pick"]], False, texts), f"homepage name (jev {j['conf']:.2f})"
    if not (j["pick"] == "keep_original" and j["conf"] >= JEV_DISPLAY_CONF):
        dom_name = [v for k, v in opts.items() if k != "keep_original" and _key(v) == dom_key]
        if dom_name:  # Jev unsure; the homepage name that spells the domain is the brand (legal name differs)
            return dom_name[0], f"homepage name = domain (jev unsure {j['conf']:.2f})"
    return rec, "record name" + (" (recased)" if rec != base else "") + f" (jev keep {j.get('conf', 0):.2f})"


def person_display(first: str, last: str, texts: list[str], company_display: str) -> tuple[str, str]:
    f, l = person_case(first), person_case(last)
    f = re.sub(r"^([A-Za-z])\.\s?([A-Za-z])\.?$", lambda m: f"{m.group(1).upper()}.{m.group(2).upper()}.", f)
    l = re.sub(r"\bMc([a-z])", lambda m: "Mc" + m.group(1).upper(), l)
    full = site_spellings(f"{f} {l}", texts)
    good = [(n, v) for v, n in full.items() if not v.isupper() and v != f"{f} {l}"]
    if good:
        v = max(good)[1].replace("’", "'").split()
        nf = len(_TOK.findall(f))
        if len(v) == len(_TOK.findall(f)) + len(_TOK.findall(l)) and _has_inner_case(" ".join(v)):
            return " ".join(v[:nf]), " ".join(v[nf:])
    if len(_key(l)) >= 4:
        for v, _n in site_spellings(l, texts).most_common():
            if not v.isupper() and _has_inner_case(v) and len(v.split()) == 1:
                return f, v.replace("’", "'")
    for w in company_display.split():
        if _key(w) == _key(l) and w != l and not w.isupper() and _has_inner_case(w):
            return f, w
    return f, l


CONNECT = {"and", "for", "with", "of", "the", "to", "in", "on", "&", "-", "a"}


def device_display(raw: str, company: str, texts: list[str]) -> str:
    """<= 45 chars, faithful to the FDA device name: short_device(), then a word-boundary cut that never ends on a
    connector; brand casing as the company's own pages write it; an all-lowercase record gets word capitals."""
    s = re.sub(r"\s+", " ", short_device(raw, company)).strip()
    full = re.sub(r"\s+", " ", re.sub(r"\s*\([^)]*\)", "", mt.clean_device(re.sub(r"[\x80-\x9f]", "", raw)))).strip(" ,;-")
    if len(full) > 45 and full != s:  # prefer dropping a leading company-name word over cutting the device's tail
        co, words = set(mt.norm_tokens(company)), full.split()
        i = 0
        while i < len(words) - 2 and words[i].lower().strip(",.") in co:
            i += 1
        if i and len(" ".join(words[i:])) <= 45:
            s = " ".join(words[i:])
    if len(s) > 45:
        out = []
        for w in s.split():
            if len(" ".join(out + [w])) > 45:
                break
            out.append(w)
        while out and out[-1].lower().strip(",;:") in CONNECT:
            out.pop()
        s = " ".join(out).rstrip(",;:-")
    letters = re.sub(r"[^A-Za-z]", "", raw.split(";")[0])
    toks = []
    for w in s.split():
        if letters.islower() and w.isalpha():
            w = w.capitalize()
        if len(w) >= 3 and w.isalpha():
            for v, _n in site_spellings(w, texts).most_common():
                if len(v.split()) == 1 and not v.isupper() and _has_inner_case(v) and v[0].isalpha():
                    w = v
                    break
        toks.append(w)
    return " ".join(toks)


TICKER = re.compile(r"\b(?:NASDAQ|Nasdaq|NYSE(?: American)?)\s*(?:GS|GM|CM)?\s*[:\-]\s*\(?([A-Z]{1,5})\b")


def size_flag(c: dict, apollo_cache: dict, pages: dict) -> tuple[str, bool]:
    """(flag text, hard). Hard = headcount > 500 from any source, or evidence of a public listing (ticker or
    investor-relations link on the homepage, or 'publicly traded' in the LeadOcean description)."""
    flags, hard = [], False
    li = c.get("employees")
    li = int(li) if li not in (None, "") else None
    ap = (apollo_cache.get(c["domain"]) or {})
    ap_n = ap.get("employees") if (ap.get("country") or "United States") == "United States" else None
    if li is not None and li > 500:
        flags.append(f"headcount {li} (LinkedIn) > 500")
        hard = True
    if ap_n and int(ap_n) > 500:
        flags.append(f"headcount {ap_n} (Apollo) > 500")
        hard = True
    home = pages.get("home") or {}
    text = f"{home.get('text', '')} {c.get('description', '')}"
    m = TICKER.search(text)
    ir = [u for u in home.get("ir_links") or [] if re.match(r"https?://(investors?|ir)\.", u, re.I)
          or "investor-relations" in u.lower() or u.lower() == "investor relations"]
    if m:
        flags.append(f"publicly listed ({m.group(0)})")
        hard = True
    elif pages.get("ir_probe"):
        flags.append(f"publicly listed? (investor site {pages['ir_probe']})")
        hard = True
    elif ir:
        flags.append(f"publicly listed? (investor relations: {ir[0][:60]})")
        hard = True
    elif re.search(r"publicly[- ]traded|\bIPO\b", c.get("description", "") or ""):
        flags.append("publicly listed? (LeadOcean description)")
        hard = True
    if not hard and li is not None and li >= 400:
        flags.append(f"near 500 ceiling ({li} LinkedIn)")
    return "; ".join(flags), hard


# ------------------------------------------------------------------ main
P_COLS = {
    "medtech": ["first_name", "last_name", "title", "email", "linkedin", "company", "company_display", "website", "date",
                "device", "device_display", "device_raw", "k_number", "site_fact", "evidence_urls", "size_flag"],
    "construction": ["first_name", "last_name", "title", "email", "linkedin", "company", "company_display", "website",
                     "agency", "date", "amount", "award_id", "site_fact", "evidence_url", "size_flag"],
}
STEPS = ["triggers in region", "matched to a domain", "  of which via web domain discovery", "not on drop list / not duplicate",
         "passed size + vertical gate", "site fact verified", "not listed / not >500 (size flag)",
         ">=1 allowlisted decision-maker (title + one chief exec)", "email address revealed (workable)"]
S_FLAG, S_DM, S_WORK = STEPS[6], STEPS[7], STEPS[8]


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--region", choices=sorted(ct.REGIONS))
    g.add_argument("--states")
    ap.add_argument("--verticals", default="medtech,construction")
    ap.add_argument("--batch", default="batch1")
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--drop-list", default=str(ROOT / ".tmp/referral/leads/drop_list.json"))
    ap.add_argument("--max-jev", type=int, default=600)
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--try-export", action="store_true")
    ap.add_argument("--min-emp", default=",".join(f"{k}={v}" for k, v in MIN_EMP.items()),
                    help="per-vertical headcount floor, e.g. medtech=20,construction=10")
    ap.add_argument("--max-emp", type=int, default=MAX_EMP)
    ap.add_argument("--apollo-below", type=int, default=APOLLO_BELOW,
                    help="ask Apollo org enrich when LinkedIn staff is below this or missing (0 = never)")
    ap.add_argument("--max-apollo", type=int, default=300, help="Apollo org-enrich calls per run")
    ap.add_argument("--discover", choices=["on", "off"], default="on",
                    help="web domain discovery for companies LeadOcean cannot match by name")
    ap.add_argument("--max-serper", type=int, default=300, help="Serper queries per run (then DuckDuckGo HTML)")
    ap.add_argument("--end", default="", help="award window end date for construction (default today); pin it to "
                                               "rebuild an earlier batch from its cached award pull")
    ap.add_argument("--size-flag", choices=["drop", "flag"], default="drop",
                    help="drop (default) or only flag companies listed publicly or > 500 staff")
    ap.add_argument("--check", action="store_true", help="offline: caches only, no network, no spend")
    ap.add_argument("--allow-net", default="",
                    help="with --check: stages still allowed online, any of pages,jev,email (new page fetches, Jev "
                         "for titles/display names, LeadOcean email reveal for newly chosen contacts); all else cached")
    a = ap.parse_args()
    allow_net = {x.strip() for x in a.allow_net.split(",") if x.strip()}

    def off(stage: str) -> bool:
        return a.check and stage not in allow_net
    states = ct.REGIONS[a.region] if a.region else [s.strip().upper() for s in a.states.split(",")]
    outdir = ROOT / ".tmp" / "referral" / a.batch
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {k: CACHE / f"{k}.json" for k in ("match", "jev", "site", "contacts", "email", "discover", "apollo",
                                                "recipient_loc", "pages")}
    caches = {k: jload(p, {}) for k, p in paths.items()}
    drop = jload(Path(a.drop_list), {"domains": [], "names": []})
    drop_dom = {norm_domain(d) for d in drop.get("domains", [])}
    drop_names = {norm_name(n) for n in drop.get("names", [])}
    lo = None if off("email") else LeadOcean()
    budget = [a.max_jev]
    breaker = {"open": False, "fails": 0, "last": ""}
    cfg = {"min_emp": dict(MIN_EMP, **{k.strip(): int(v) for k, v in
                                       (x.split("=") for x in a.min_emp.split(",") if "=" in x)}),
           "max_emp": a.max_emp, "apollo_below": a.apollo_below}
    counter = {"serper": 0, "serper_cap": a.max_serper, "ddg": 0, "apollo": 0, "apollo_cap": a.max_apollo}
    jev0 = budget[0]
    acct0 = lo.req("GET", "/v1/account")["data"] if lo else {}

    def save() -> None:
        for k, p in paths.items():
            jsave(p, caches[k])

    all_companies, funnel, reasons, contact_rows, contact_gates = [], {}, {}, {}, {}
    seen_domains: set[str] = set()
    seen_emails: set[str] = set()
    for vert in [v.strip() for v in a.verticals.split(",") if v.strip()]:
        trig = (medtech_triggers(states, a.since, a.check) if vert == "medtech"
                else construction_triggers(states, a.region, a.days, a.check, a.end))
        cnt = Counter()
        why = Counter()
        cnt[STEPS[0]] = len(trig)

        def stage_match(t: dict) -> None:
            cands = lo_company_candidates(lo, t["org"], t["state"], caches["match"], a.check)
            t["co"], t["match_how"] = match_trigger(t, cands, caches["jev"], budget, a.check)
            t["domain_source"] = "leadocean name" if t["co"] else ""
            if t["co"] or a.discover == "off":
                return
            recipient_location(t, caches["recipient_loc"], a.check)
            pick, note = discover_domain(t, caches["discover"], counter, budget, a.check)
            if not pick:
                t["match_how"] = f"{t['match_how']}; {note}"
                return
            lo_c = lo_company_by_domain(lo, pick["domain"], caches["match"], a.check) or {}
            t["co"] = dict(pick, **{k: v for k, v in lo_c.items() if v not in (None, "") and k in
                                    ("employees", "industries", "description", "linkedin")})
            t["co"]["name"] = lo_c.get("name") or pick["name"]
            t["match_how"], t["domain_source"] = note, pick["domain_source"]

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_match, trig))
        save()
        alive = []
        for t in sorted(trig, key=lambda t: t["date"], reverse=True):
            t["outcome"] = ""
            if not t["co"]:
                t["outcome"] = t["match_how"]
            elif t["co"]["domain"] in drop_dom or norm_name(t["co"]["name"]) in drop_names or norm_name(t["org"]) in drop_names:
                t["outcome"] = "on drop list"
            elif t["co"]["domain"] in seen_domains:
                t["outcome"] = "duplicate domain (newer trigger or other vertical kept)"
            if t["outcome"]:
                continue
            seen_domains.add(t["co"]["domain"])
            alive.append(t)
        cnt[STEPS[1]] = sum(1 for t in trig if t["co"])
        cnt[STEPS[2]] = sum(1 for t in trig if t["co"] and t["domain_source"] != "leadocean name")
        cnt[STEPS[3]] = len(alive)

        def stage_gate(t: dict) -> None:
            ok, note = gate(t, t["co"], caches["jev"], budget, a.check, cfg, caches["apollo"], counter)
            t["gate"] = note
            if not ok:
                t["outcome"] = note

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_gate, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[STEPS[4]] = len(alive)

        def stage_site(t: dict) -> None:
            s = site_check(t, t["co"], caches["site"], a.check)
            t["site"] = s
            if not s.get("ok"):
                t["outcome"] = s.get("reason", "site check failed")

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_site, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[STEPS[5]] = len(alive)

        def stage_pages(t: dict) -> None:  # homepage once per surviving company: size flag + display names
            t["pages"] = site_pages(t["co"]["domain"], caches["pages"], False, off("pages"))
            t["size_flag"], hard = size_flag(t["co"], caches["apollo"], t["pages"])
            if hard and a.size_flag == "drop":
                t["outcome"] = f"size flag: {t['size_flag']}"

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_pages, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[S_FLAG] = len(alive)
        cg = Counter()  # contact-level drops, one count per person per gate

        def stage_contacts(t: dict) -> None:
            ppl = contacts_for(lo, t["co"]["domain"], caches["contacts"], a.check)
            ranked, drops = [], Counter()
            best_rec: dict[tuple, tuple] = {}  # LeadOcean can hold one person twice (two title records): keep the best
            for p in ppl:  # person key: first name + last surname token ("Ann Lee Smith" == "Ann Smith")
                k = (p["first_name"].strip().lower(), (p["last_name"].strip().lower().split() or [""])[-1])
                cls, why = title_class(p["title"], caches["jev"], budget, off("jev"))
                lower = (p["first_name"] + p["last_name"]).islower()  # lowercase duplicates are the stale records
                if k not in best_rec or (RANK_OF.get(cls, 9), lower) < (RANK_OF.get(best_rec[k][1], 9),
                                                                      (best_rec[k][0]["first_name"] +
                                                                       best_rec[k][0]["last_name"]).islower()):
                    best_rec[k] = (p, cls, why)
            for p, cls, why in best_rec.values():
                if cls not in RANK_OF:
                    drops["title: " + ("Jev none/unsure" if why.startswith("edge") else
                                       re.sub(r"\(.*?\)", "", why.split(": ", 1)[-1]).strip())] += 1
                    continue
                ranked.append(dict(p, _cls=cls, _rank=RANK_OF[cls], _title_why=why))
            # one chief executive per company: the one the company's own pages name, else the higher title rank
            chiefs = [p for p in ranked if CHIEF_EXEC.search(p["title"].lower())]
            t["exec_check"] = ""
            if len(chiefs) >= 2:
                pages = site_pages(t["co"]["domain"], caches["pages"], True, off("pages"))
                t["pages"] = pages
                texts = page_texts(pages)
                joined = " ".join(texts)

                def seen(p: dict) -> int:
                    full = f"{p['first_name']} {p['last_name']}"
                    if not site_spellings(full, texts):
                        return 1 if len(p["last_name"]) >= 4 and re.search(
                            r"(?<![a-z])" + re.escape(p["last_name"].lower()) + r"(?![a-z])", joined.lower()) else 0
                    near = re.search(re.escape(_key(full)) + r".{0,60}?(ceo|chiefexecutive)|(ceo|chiefexecutive).{0,60}?"
                                     + re.escape(_key(full)), _key(joined))
                    return 3 if near else 2

                sc = {id(p): seen(p) for p in chiefs}
                best = max(sc.values())
                top = [p for p in chiefs if sc[id(p)] == best]
                if best > 0 and len(top) == 1:
                    keep, how = top[0], "named on company pages"
                else:
                    keep = max(chiefs, key=lambda p: (chief_rank(p["title"]), -chiefs.index(p)))
                    how = "UNVERIFIED: higher title rank kept, pages did not settle it"
                t["exec_check"] = f"{len(chiefs)} chief execs; kept {keep['first_name']} {keep['last_name']} ({how})"
                for p in chiefs:
                    if p is not keep:
                        ranked.remove(p)
                        drops["stale chief exec (" + ("not on company pages" if how.startswith("named")
                                                      else "lower title rank") + ")"] += 1
            # order: best chief exec, best growth lead, then the rest by rank
            def key(p: dict) -> tuple:
                tl = p["title"].lower()
                return (p["_rank"], 0 if CHIEF_EXEC.search(tl) or "president" in tl else 1,
                        0 if re.search(r"cmo|chief marketing|marketing", tl) else 1, p["last_name"])
            ranked.sort(key=key)
            first = [next((p for p in ranked if p["_rank"] == r), None) for r in (0, 1)]
            first = [p for p in first if p]
            t["contacts"] = first + [p for p in ranked if p not in first]
            t["contact_drops"] = drops
            with _lock:
                cg.update(drops)
            if not ranked:
                t["outcome"] = ("no LeadOcean people at domain" if not ppl else
                                "no allowlisted decision-maker (" + (drops.most_common(1)[0][0] if drops else "-") + ")")

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_contacts, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[S_DM] = len(alive)

        rows = []
        for t in alive:
            kept, co = 0, t["co"]
            pages = t.get("pages") or site_pages(co["domain"], caches["pages"], False, True)
            texts = page_texts(pages)
            cdisp, cdisp_how = company_display_name(t, co, pages, caches["jev"], budget, off("jev"))
            t["company_display"] = cdisp
            ddisp = device_display(t["device_raw"], t["org"], texts) if vert == "medtech" else ""
            drops = t["contact_drops"]
            for i, p in enumerate(t["contacts"]):
                if kept >= MAX_PER_CO:
                    drops["over cap (2 per company)"] += len(t["contacts"]) - i
                    cg["over cap (2 per company)"] += len(t["contacts"]) - i
                    break
                email = reveal_email(lo, str(p["person_id"]), caches["email"], breaker, off("email")) if p["person_id"] else ""
                bad = ""
                if email and not (email.endswith("@" + co["domain"]) or email.endswith("." + co["domain"])):
                    bad = "email not at company domain"
                elif email and is_role_inbox(email):
                    bad = "generic inbox"
                elif email and email in seen_emails:
                    bad = "duplicate email"
                if bad:
                    drops[bad] += 1
                    cg[bad] += 1
                    continue
                kept += 1
                if email:
                    seen_emails.add(email)
                fn, ln = person_display(p["first_name"], p["last_name"], texts, cdisp)
                row = {"first_name": fn, "last_name": ln,
                       "title": person_case(p["title"]) if p["title"].islower() else p["title"], "email": email,
                       "linkedin": p["linkedin"], "company": display_company(t["org"], co["name"]),
                       "company_display": cdisp, "website": co["domain"], "_leadocean_name": co["name"],
                       "date": nice_date(t["date"]), "site_fact": t["site"]["fact"], "size_flag": t.get("size_flag", ""),
                       "_rank": p["_rank"], "_title_class": p["_title_why"], "_person_id": p["person_id"],
                       "_iso_date": t["date"], "_company_display_how": cdisp_how, "_exec_check": t["exec_check"],
                       "_trigger_org": t["org"], "_match": t["match_how"], "_domain_source": t["domain_source"],
                       "_size_source": t.get("size_source", ""), "_size_linkedin": t.get("size_linkedin", ""),
                       "_size_apollo": t.get("size_apollo", "")}
                if vert == "medtech":
                    row.update(device=t["device"], device_display=ddisp, device_raw=t["device_raw"],
                               k_number=t["k_number"],
                               evidence_urls=f"{t['evidence_url']} {t['site']['final_url']}")
                else:
                    row.update(agency=t["agency"], amount=t["amount"], award_id=t["award_id"],
                               evidence_url=t["evidence_url"], _homepage=t["site"]["final_url"],
                               _description=t["description"])
                rows.append(row)
            t["n_contacts"] = kept
            t["n_emails"] = sum(1 for r in rows if r["website"] == co["domain"] and r["email"])
            if not t["n_emails"]:
                gated = {k: v for k, v in drops.items() if k in ("generic inbox", "email not at company domain",
                                                                 "duplicate email")}
                t["outcome"] = ("email lookup unavailable (pending)" if breaker["open"] or breaker["fails"] else
                                f"no usable email ({', '.join(gated)})" if gated else "no email returned")
            else:
                t["outcome"] = "WORKABLE"
        save()
        cnt[S_WORK] = sum(1 for t in alive if t["outcome"] == "WORKABLE")
        contact_gates[vert] = cg
        for t in trig:
            if t["outcome"] != "WORKABLE":
                why[re.sub(r"\(.*?\)|\d+(\.\d+)?", "#", t["outcome"]).strip()] += 1
        funnel[vert], reasons[vert], contact_rows[vert] = cnt, why, rows
        for t in trig:
            co = t.get("co") or {}
            all_companies.append({"vertical": vert, "trigger_org": t["org"], "state": t["state"],
                                  "trigger_id": t["key"], "trigger_date": t["date"], "company": co.get("name", ""),
                                  "domain": co.get("domain", ""), "domain_source": t.get("domain_source", ""),
                                  "employees": co.get("employees", ""), "size_apollo": t.get("size_apollo", ""),
                                  "size_source": t.get("size_source", ""), "apollo_flipped": t.get("apollo_flipped", ""),
                                  "match": t.get("match_how", ""), "gate": t.get("gate", ""),
                                  "site_fact": (t.get("site") or {}).get("fact", ""),
                                  "size_flag": t.get("size_flag", ""), "company_display": t.get("company_display", ""),
                                  "exec_check": t.get("exec_check", ""),
                                  "contact_drops": "; ".join(f"{k} {v}" for k, v in (t.get("contact_drops") or {}).items()),
                                  "contacts": t.get("n_contacts", 0), "emails": t.get("n_emails", 0),
                                  "outcome": t["outcome"]})
        with open(outdir / f"{a.batch}_{vert}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=P_COLS[vert], extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
        with open(outdir / f"{a.batch}_{vert}_audit.csv", "w", newline="", encoding="utf-8") as fh:
            cols = P_COLS[vert] + sorted({k for r in rows for k in r if k.startswith("_")})
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            w.writerows(rows)
    with open(outdir / f"{a.batch}_companies.csv", "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(all_companies[0]) if all_companies else ["vertical"])
        w.writeheader()
        w.writerows(all_companies)
    acct1 = lo.req("GET", "/v1/account")["data"] if lo else {}
    export = None
    if a.try_export and breaker["open"] and lo:
        doms = sorted({r["website"] for rows in contact_rows.values() for r in rows if not r["email"]})
        export = try_export(lo, doms, CACHE / "export_ledger.json")
        export.pop("csv", None)
    stats = {"counter": counter, "cfg": cfg, "jev_calls": jev0 - budget[0], "companies": all_companies,
             "contact_gates": contact_gates}
    write_funnel(outdir / "funnel.md", a, states, funnel, reasons, contact_rows, breaker, acct0, acct1, budget, export,
                 stats)
    print((outdir / "funnel.md").read_text())
    return 0


def write_funnel(path: Path, a, states, funnel, reasons, contact_rows, breaker, acct0, acct1, budget, export,
                 stats) -> None:
    cfg, counter = stats["cfg"], stats["counter"]
    floors = ", ".join(f"{k} {v}-{cfg['max_emp']}" for k, v in cfg["min_emp"].items() if k in funnel)
    L = [f"# Trigger batch funnel: {a.batch} ({', '.join(states)})", "",
         f"Built {dt.date.today()}. 510(k) decisions since {a.since}; federal awards (original action) last {a.days} "
         f"days. Size gate ({floors}) on LinkedIn staff, Apollo estimate when LinkedIn < {cfg['apollo_below']} or "
         f"missing, + Jev noul >= {JEV_GATE_NOUL}; match Jev conf >= {JEV_MATCH_CONF}; unmatched names get web domain "
         f"discovery ({a.discover}); max {MAX_PER_CO} contacts/company.", "",
         "| Step | " + " | ".join(funnel) + " |", "|---|" + "---:|" * len(funnel)]
    for s in STEPS:
        L.append(f"| {s} | " + " | ".join(str(funnel[v].get(s, 0)) for v in funnel) + " |")
    L.append("| contacts (after cap + dedupe) | " + " | ".join(str(len(contact_rows[v])) for v in funnel) + " |")
    L.append("| contacts with email (WORKABLE leads) | "
             + " | ".join(str(sum(1 for r in contact_rows[v] if r["email"])) for v in funnel) + " |")
    L += ["", "## Drop reasons (companies)", ""]
    for v in funnel:
        L.append(f"**{v}**: " + "; ".join(f"{k} = {n}" for k, n in reasons[v].most_common()))
        L.append("")
    L += ["## Contact gates (people dropped, one count per person per gate)", ""]
    for v, cg in stats.get("contact_gates", {}).items():
        L.append(f"**{v}**: " + ("; ".join(f"{k} = {n}" for k, n in cg.most_common()) or "none"))
        L.append("")
    flagged = [r for r in stats["companies"] if r.get("size_flag")]
    L.append(f"Size flags (public listing or > 500 staff; {'dropped' if a.size_flag == 'drop' else 'flag only'}): "
             + ("; ".join(f"{r['domain']}: {r['size_flag']}" for r in flagged) or "none"))
    L.append("")
    execs = [r for r in stats["companies"] if r.get("exec_check")]
    if execs:
        L.append("Chief-exec conflicts: " + "; ".join(f"{r['domain']}: {r['exec_check']}" for r in execs))
        L.append("")
    L += ["## Personalized column fill (contact rows)", ""]
    for v, rows in contact_rows.items():
        if rows:
            L.append(f"**{v}**: " + ", ".join(f"{c} {sum(1 for r in rows if str(r.get(c) or '').strip())}/{len(rows)}"
                                              for c in P_COLS[v]))
            L.append("")
    L += ["## Domain discovery and size sources", ""]
    for v in funnel:
        cs = [r for r in stats["companies"] if r["vertical"] == v]
        src = Counter(r["domain_source"] for r in cs if r["domain"])
        szs = Counter(r["size_source"] for r in cs if r["size_source"])
        flips = sum(1 for r in cs if r["apollo_flipped"] is True)
        L.append(f"**{v}**: domains by source {dict(src)}; size decided by {dict(szs)}; Apollo changed the size "
                 f"decision for {flips} companies")
        L.append("")
    L += [f"Serper queries {counter['serper']}/{counter['serper_cap']}"
          f"{' (stopped: ' + counter['serper_dead'] + ')' if counter.get('serper_dead') else ''}; DuckDuckGo queries "
          f"{counter['ddg']}{' (stopped: ' + counter['ddg_dead'] + ')' if counter.get('ddg_dead') else ''}; Apollo "
          f"org-enrich calls {counter['apollo']}/{counter['apollo_cap']} (cached domains not re-called).", ""]
    if breaker["fails"]:
        L += ["## Email lookup", "", f"LeadOcean /v2/people/email/work failed {breaker['fails']}x "
              f"(breaker {'open' if breaker['open'] else 'closed'}): {breaker['last']}", ""]
    if export is not None:
        L += [f"Export fallback: {json.dumps(export)[:400]}", ""]
    if acct0 and acct1:
        L += [f"LeadOcean records used: {acct0['records']['used']} -> {acct1['records']['used']} "
              f"(fair use, ceiling {acct0['records']['ceiling']}); export rows today "
              f"{acct1['exports']['day']['used']}/{acct1['exports']['day']['limit']}. Jev calls this run "
              f"{stats['jev_calls']}.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
