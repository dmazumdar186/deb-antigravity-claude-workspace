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
         per-person email lookup is down); --check (offline: caches only). env LEADOCEAN_API_KEY, OPENROUTER_API_KEY.
outputs: .tmp/referral/<batch>/<batch>_<vertical>.csv (one row per contact, personalized columns), <batch>_companies.csv
         (every trigger company with its funnel outcome and drop reason), funnel.md; caches in .tmp/referral/cache/
         (match, gate, site, contacts, email; keyed by name+state / domain / K number or award id / person id).
usage:   python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1
         python3 execution/lead_sourcing/trigger_batch_leads.py --region west --batch batch1 --check   # rebuild offline
Directive: directives/lead_sourcing/trigger_batch_leads.md
Spend: openFDA, USAspending, company sites: free. LeadOcean search/company/email lookups bill "records" against a
       fair-use plan with no ceiling (whenOver: never); exports bill rows against the 10k/day quota. Jev ~$0.00002/call,
       capped by --max-jev, ledgered in .tmp/jev_ledger.jsonl. Never calls Reoon, Instantly or any sender.
"""

from __future__ import annotations

import argparse, csv, datetime as dt, json, re, sys, threading, time, urllib.parse
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
                "industry_hint": "Medical Equipment Manufacturing, Medical Device, Biotechnology"},
    "construction": {"label": "construction contractor (general, heavy/civil or specialty trade)",
                     "industry_hint": "Construction, Civil Engineering, Specialty Trade Contractors"},
}
MIN_EMP, MAX_EMP = 20, 500
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
                                "city": r.get("city") or "", "recs": []})
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


def construction_triggers(states: list[str], region: str, days: int, offline: bool) -> list[dict]:
    label = region or "-".join(states).lower()
    path = ROOT / ".tmp/referral/triggers/construction" / f"construction_triggers_{label}.csv"
    cmd = [sys.executable, str(ROOT / "execution/gtm_icp_filters/construction_award_triggers.py"),
           "--days", str(days)] + (["--region", region] if region else ["--states", ",".join(states)])
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


# ------------------------------------------------------------------ 3. size + vertical gate
def gate(t: dict, c: dict, jev_cache: dict, budget: list[int], offline: bool) -> tuple[bool, str]:
    emp = c.get("employees")
    if emp is None:
        return False, "size unknown in LeadOcean"
    if not (MIN_EMP <= int(emp) <= MAX_EMP):
        return False, f"size {emp} outside {MIN_EMP}-{MAX_EMP}"
    ck = f"gate|{t['vertical']}|{c['domain']}"
    if ck not in jev_cache:
        if offline or budget[0] <= 0:
            return False, "gate not run (no Jev budget/offline)"
        from execution.modules import jev_client as jev
        if not jev.available():
            return False, "gate not run (Jev unavailable)"
        v = VERTICAL[t["vertical"]]
        state = {"company": c["name"], "domain": c["domain"], "hq": f"{c['city']}, {c['state']}",
                 "linkedin_staff": emp, "industries": c["industries"], "description": c["description"],
                 "public_record_name": t["org"], "parent_in_public_record": t.get("parent") or ""}
        r = jev.decide(state, {"g": jev.noul(
            f"Is this a real, independent operating company of roughly {MIN_EMP}-{MAX_EMP} staff whose main business "
            f"is: {v['label']}?",
            f"an operating business in that line of work, roughly {MIN_EMP}-{MAX_EMP} staff, its own brand/website",
            "a shell or holding entity, a subsidiary/division of a large group, a university, hospital or health "
            "system, a government or tribal entity, a nonprofit, a consultancy/distributor, or a different industry")})
        budget[0] -= 1
        jev.append_ledger({"script": "trigger_batch_leads", "step": "gate", "cost": r.cost_usd})
        with _lock:
            jev_cache[ck] = {"noul": r.noul("g", -1.0) if not r.error else -1.0, "error": (r.error or "")[:200]}
    j = jev_cache[ck]
    if j.get("error"):
        return False, "gate Jev error"
    return (j["noul"] >= JEV_GATE_NOUL), f"jev gate {j['noul']:.2f}"


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


# ------------------------------------------------------------------ main
P_COLS = {
    "medtech": ["first_name", "last_name", "title", "email", "linkedin", "company", "website", "date", "device",
                "k_number", "site_fact", "evidence_urls"],
    "construction": ["first_name", "last_name", "title", "email", "linkedin", "company", "website", "agency", "date",
                     "amount", "award_id", "site_fact", "evidence_url"],
}
STEPS = ["triggers in region", "matched to a domain", "not on drop list / not duplicate",
         "passed size + vertical gate", "site fact verified", ">=1 verified-email decision-maker",
         "email address revealed (workable)"]


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
    ap.add_argument("--check", action="store_true", help="offline: caches only, no network, no spend")
    a = ap.parse_args()
    states = ct.REGIONS[a.region] if a.region else [s.strip().upper() for s in a.states.split(",")]
    outdir = ROOT / ".tmp" / "referral" / a.batch
    outdir.mkdir(parents=True, exist_ok=True)
    paths = {k: CACHE / f"{k}.json" for k in ("match", "jev", "site", "contacts", "email")}
    caches = {k: jload(p, {}) for k, p in paths.items()}
    drop = jload(Path(a.drop_list), {"domains": [], "names": []})
    drop_dom = {norm_domain(d) for d in drop.get("domains", [])}
    drop_names = {norm_name(n) for n in drop.get("names", [])}
    lo = None if a.check else LeadOcean()
    budget = [a.max_jev]
    breaker = {"open": False, "fails": 0, "last": ""}
    acct0 = lo.req("GET", "/v1/account")["data"] if lo else {}

    def save() -> None:
        for k, p in paths.items():
            jsave(p, caches[k])

    all_companies, funnel, reasons, contact_rows = [], {}, {}, {}
    seen_domains: set[str] = set()
    seen_emails: set[str] = set()
    for vert in [v.strip() for v in a.verticals.split(",") if v.strip()]:
        trig = (medtech_triggers(states, a.since, a.check) if vert == "medtech"
                else construction_triggers(states, a.region, a.days, a.check))
        cnt = Counter()
        why = Counter()
        cnt[STEPS[0]] = len(trig)

        def stage_match(t: dict) -> None:
            cands = lo_company_candidates(lo, t["org"], t["state"], caches["match"], a.check)
            t["co"], t["match_how"] = match_trigger(t, cands, caches["jev"], budget, a.check)

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
        cnt[STEPS[2]] = len(alive)

        def stage_gate(t: dict) -> None:
            ok, note = gate(t, t["co"], caches["jev"], budget, a.check)
            t["gate"] = note
            if not ok:
                t["outcome"] = note

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_gate, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[STEPS[3]] = len(alive)

        def stage_site(t: dict) -> None:
            s = site_check(t, t["co"], caches["site"], a.check)
            t["site"] = s
            if not s.get("ok"):
                t["outcome"] = s.get("reason", "site check failed")

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_site, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[STEPS[4]] = len(alive)

        def stage_contacts(t: dict) -> None:
            ppl = contacts_for(lo, t["co"]["domain"], caches["contacts"], a.check)
            ranked, seen_p = [], set()
            for p in sorted([p for p in ppl if contact_rank(p["title"]) is not None],
                            key=lambda p: (contact_rank(p["title"]), p["title"].strip().lower() == "owner",
                                           p["last_name"])):
                k = (p["first_name"].strip().lower(), p["last_name"].strip().lower())
                if k in seen_p:  # LeadOcean can hold one person twice (two title records)
                    continue
                seen_p.add(k)
                ranked.append(p)
            t["contacts"] = ranked
            if not ranked:
                t["outcome"] = ("no LeadOcean people at domain" if not ppl
                                else "no decision-maker title among verified-email people")

        with ThreadPoolExecutor(max_workers=a.workers) as pool:
            list(pool.map(stage_contacts, alive))
        save()
        alive = [t for t in alive if not t["outcome"]]
        cnt[STEPS[5]] = len(alive)

        rows = []
        for t in alive:
            kept = 0
            for p in t["contacts"]:
                if kept >= MAX_PER_CO:
                    break
                email = reveal_email(lo, str(p["person_id"]), caches["email"], breaker, a.check) if p["person_id"] else ""
                if email and not (email.endswith("@" + t["co"]["domain"]) or email.endswith("." + t["co"]["domain"])):
                    continue  # address not at the company domain
                if email and email in seen_emails:
                    continue
                kept += 1
                if email:
                    seen_emails.add(email)
                co = t["co"]
                row = {"first_name": person_case(p["first_name"]), "last_name": person_case(p["last_name"]),
                       "title": person_case(p["title"]) if p["title"].islower() else p["title"], "email": email,
                       "linkedin": p["linkedin"], "company": display_company(t["org"], co["name"]),
                       "website": co["domain"], "_leadocean_name": co["name"],
                       "date": nice_date(t["date"]), "site_fact": t["site"]["fact"],
                       "_rank": contact_rank(p["title"]), "_person_id": p["person_id"], "_iso_date": t["date"],
                       "_trigger_org": t["org"], "_match": t["match_how"]}
                if vert == "medtech":
                    row.update(device=t["device"], k_number=t["k_number"],
                               evidence_urls=f"{t['evidence_url']} {t['site']['final_url']}", _device_raw=t["device_raw"])
                else:
                    row.update(agency=t["agency"], amount=t["amount"], award_id=t["award_id"],
                               evidence_url=t["evidence_url"], _homepage=t["site"]["final_url"],
                               _description=t["description"])
                rows.append(row)
            t["n_contacts"] = kept
            t["n_emails"] = sum(1 for r in rows if r["website"] == t["co"]["domain"] and r["email"])
            if not t["n_emails"]:
                t["outcome"] = "email lookup unavailable (pending)" if breaker["open"] or breaker["fails"] else "no email returned"
            else:
                t["outcome"] = "WORKABLE"
        save()
        cnt[STEPS[6]] = sum(1 for t in alive if t["outcome"] == "WORKABLE")
        for t in trig:
            if t["outcome"] != "WORKABLE":
                why[re.sub(r"\(.*?\)|\d+(\.\d+)?", "#", t["outcome"]).strip()] += 1
        funnel[vert], reasons[vert], contact_rows[vert] = cnt, why, rows
        for t in trig:
            co = t.get("co") or {}
            all_companies.append({"vertical": vert, "trigger_org": t["org"], "state": t["state"],
                                  "trigger_id": t["key"], "trigger_date": t["date"], "company": co.get("name", ""),
                                  "domain": co.get("domain", ""), "employees": co.get("employees", ""),
                                  "match": t.get("match_how", ""), "gate": t.get("gate", ""),
                                  "site_fact": (t.get("site") or {}).get("fact", ""),
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
    write_funnel(outdir / "funnel.md", a, states, funnel, reasons, contact_rows, breaker, acct0, acct1, budget, export)
    print((outdir / "funnel.md").read_text())
    return 0


def write_funnel(path: Path, a, states, funnel, reasons, contact_rows, breaker, acct0, acct1, budget, export) -> None:
    L = [f"# Trigger batch funnel: {a.batch} ({', '.join(states)})", "",
         f"Built {dt.date.today()}. 510(k) decisions since {a.since}; federal awards (original action) last {a.days} "
         f"days. Size gate {MIN_EMP}-{MAX_EMP} LinkedIn staff + Jev noul >= {JEV_GATE_NOUL}; match Jev conf >= "
         f"{JEV_MATCH_CONF}; max {MAX_PER_CO} contacts/company.", "",
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
    L += ["## Personalized column fill (contact rows)", ""]
    for v, rows in contact_rows.items():
        if rows:
            L.append(f"**{v}**: " + ", ".join(f"{c} {sum(1 for r in rows if str(r.get(c) or '').strip())}/{len(rows)}"
                                              for c in P_COLS[v]))
            L.append("")
    if breaker["fails"]:
        L += ["## Email lookup", "", f"LeadOcean /v2/people/email/work failed {breaker['fails']}x "
              f"(breaker {'open' if breaker['open'] else 'closed'}): {breaker['last']}", ""]
    if export is not None:
        L += [f"Export fallback: {json.dumps(export)[:400]}", ""]
    if acct0 and acct1:
        L += [f"LeadOcean records used: {acct0['records']['used']} -> {acct1['records']['used']} "
              f"(fair use, ceiling {acct0['records']['ceiling']}); export rows today "
              f"{acct1['exports']['day']['used']}/{acct1['exports']['day']['limit']}. Jev calls this run "
              f"{a.max_jev - budget[0]}.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
