"""
recruiter_leads.py

description: LeadOcean -> hygiene -> Jev recruiter gate (+ segment, specialty) -> Reoon -> per-location Instantly CSVs
             for the Candidate Outreach System campaign (recruiters in New York, New Jersey, Boston, Houston).
inputs: subcommand (count | export | gate | verify | build) + flags; env LEADOCEAN_API_KEY, OPENROUTER_API_KEY (Jev),
        REOON_API_KEY or REOON_TOKEN (verify).
outputs: .tmp/recruiters/{counts.json, exports.json, raw/*.csv, jev_cache.json, gate.json, summary.json,
         recruiters_all_YYYY-MM-DD.csv, rejects.csv, campaigns/Recruitment_{Loc}_{Personalized|NoPersonalization}.csv,
         campaigns/catchall/*.csv, campaigns/_campaign_index.csv}
usage:
    python3 execution/lead_sourcing/recruiter_leads.py count
    python3 execution/lead_sourcing/recruiter_leads.py export --plan-only
    python3 execution/lead_sourcing/recruiter_leads.py export --budget 10000 [--sample 30]
    python3 execution/lead_sourcing/recruiter_leads.py gate [--limit 50]
    python3 execution/lead_sourcing/recruiter_leads.py verify --max-credits 9000      # spends Reoon credits
    python3 execution/lead_sourcing/recruiter_leads.py build

Every step is idempotent: exports are keyed by location:status, Jev and Reoon results are cached per person/email.
Directive: directives/lead_sourcing/recruiter_leads.md
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import threading
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from execution.lead_sourcing import leadocean_leads as lol  # noqa: E402
from execution.modules.pipeline_utils import csv_safe_row  # noqa: E402

TMP = ROOT / ".tmp" / "recruiters"
RAW = TMP / "raw"
OUT = TMP / "campaigns"
TODAY = lol.TODAY
COMPANY_CAP = 2          # final senders per company domain (playbook)
COMPANY_RESERVE = 3      # kept per company before Reoon, so a Reoon drop can be replaced
SEARCH_STATUSES = ("verified", "untested")  # LeadOcean catch_all never came back Reoon-safe (wave 2)

TITLES = ["Recruiter", "Recruiting", "Talent Acquisition", "Sourcer", "Staffing", "Headhunter", "Executive Search",
          "Talent Partner"]
EXCL_TITLES = ["Intern", "Student", "Coordinator", "Assistant", "Volunteer", "Army", "Navy", "Marine", "Air Force",
               "Military", "Retired", "Former", "Seeking", "Open to Work", "Candidate"]
EXCL_COMPANY = ["US Army", "U.S. Army", "United States Army", "US Navy", "U.S. Navy", "Marine Corps", "Air Force",
                "National Guard", "Space Force"]

LOCATIONS: dict[str, dict[str, Any]] = {
    "new_york": {"label": "New York", "file": "NewYork", "states": ["NY", "NEW YORK"],
                 "city": ["New York", "Brooklyn", "Queens", "Bronx", "Staten Island", "Long Island City", "Yonkers",
                          "White Plains", "Manhattan"]},
    "new_jersey": {"label": "New Jersey", "file": "NewJersey", "states": ["NJ", "NEW JERSEY"],
                   "city": ["Jersey City", "Hoboken", "Newark", "Princeton", "Parsippany", "Morristown", "Edison",
                            "Iselin", "Secaucus", "Paramus", "Hackensack", "Red Bank", "Somerset", "Piscataway",
                            "Bridgewater", "Florham Park", "Woodbridge", "Fort Lee", "Mahwah", "Montvale",
                            "Basking Ridge", "New Brunswick", "Cherry Hill", "Mount Laurel", "Trenton",
                            "East Brunswick", "Rutherford", "Englewood Cliffs", "Short Hills", "Livingston",
                            "Roseland", "Whippany", "Berkeley Heights", "Summit", "Clifton", "Wayne", "Toms River",
                            "Freehold", "Matawan", "Holmdel", "Eatontown", "Princeton Junction", "Plainsboro",
                            "Lawrenceville", "Weehawken", "New Jersey"]},
    "boston": {"label": "Boston", "file": "Boston", "states": ["MA", "MASSACHUSETTS"],
               "city": ["Boston", "Cambridge", "Somerville", "Waltham", "Woburn", "Burlington", "Quincy", "Needham",
                        "Newton", "Wellesley", "Framingham", "Lexington", "Braintree", "Marlborough", "Wakefield",
                        "Andover", "Bedford", "Medford", "Watertown", "Natick", "Dedham", "Norwood", "Canton",
                        "Westborough"]},
    "houston": {"label": "Houston", "file": "Houston", "states": ["TX", "TEXAS"],
                "city": ["Houston", "Sugar Land", "The Woodlands", "Katy", "Spring", "Pearland", "Cypress", "Humble",
                         "Stafford", "Missouri City", "Tomball", "Bellaire", "Conroe", "Pasadena", "League City",
                         "Kingwood", "Friendswood"]},
}

# Specialty menu for Jev. `phrase` is what the copy may say ("{{specialty}}"); `evidence` words must appear in the
# person's title/headline/summary or employer name/industry, so no specialty claim ships on Jev's word alone.
SPECIALTIES: dict[str, dict[str, Any]] = {
    "tech": {"desc": "software, IT, data, cybersecurity or engineering-for-tech hiring",
             "phrase": "tech hiring",
             "evidence": ["tech", "software", "it ", " it", "information technology", "engineer", "developer", "data",
                          "cyber", "cloud", "devops", "saas", "ai ", "digital"]},
    "healthcare": {"desc": "nurses, physicians, allied health, hospitals or healthcare staffing",
                   "phrase": "healthcare hiring",
                   "evidence": ["health", "nurs", "medical", "physician", "clinical", "hospital", "allied", "pharma",
                                "rn ", "therap", "care"]},
    "finance": {"desc": "finance, accounting, banking, insurance or fintech hiring",
                "phrase": "finance and accounting hiring",
                "evidence": ["financ", "accounting", "accountant", "bank", "cpa", "insurance", "fintech", "audit",
                             "tax", "investment", "wealth", "capital"]},
    "legal": {"desc": "attorneys, paralegals, law firms or legal staffing",
              "phrase": "legal hiring", "evidence": ["legal", "law", "attorney", "paralegal", "counsel"]},
    "engineering": {"desc": "engineering, manufacturing, construction, industrial or skilled trades hiring",
                    "phrase": "engineering and manufacturing hiring",
                    "evidence": ["engineer", "manufactur", "construction", "industrial", "trades", "mechanical",
                                 "electrical", "civil", "skilled"]},
    "energy": {"desc": "oil & gas, energy, utilities, petrochemical or renewables hiring",
               "phrase": "energy hiring",
               "evidence": ["energy", "oil", "gas", "petro", "utilit", "renewable", "solar", "chemical", "upstream",
                            "midstream", "downstream", "drilling", "power"]},
    "life_sciences": {"desc": "biotech, pharma, life sciences, research or lab hiring",
                      "phrase": "life sciences hiring",
                      "evidence": ["biotech", "pharma", "life science", "scientif", "laborator", "lab ", "research",
                                   "clinical", "biolog", "chemist"]},
    "sales_marketing": {"desc": "sales, marketing, creative, advertising or media hiring",
                        "phrase": "sales and marketing hiring",
                        "evidence": ["sales", "marketing", "creative", "advertis", "media", "brand", "design",
                                     "go-to-market", "gtm", "revenue"]},
    "executive": {"desc": "executive search: C-suite, VP and board-level placements",
                  "phrase": "executive search",
                  "evidence": ["executive search", "executive recruit", "c-suite", "c-level", "leadership",
                               "board", "retained", "headhunt", "executive"]},
    "light_industrial": {"desc": "light industrial, warehouse, logistics, hourly or high-volume staffing",
                         "phrase": "high-volume hiring",
                         "evidence": ["industrial", "warehouse", "logistic", "hourly", "high volume", "high-volume",
                                      "distribution", "supply chain", "temp"]},
    "general": {"desc": "no clear specialty / many functions / cannot tell", "phrase": "", "evidence": []},
}
SEGMENTS = {
    "agency": "works at a staffing, recruiting or search firm placing candidates with client companies",
    "in_house": "recruits for their own employer (corporate talent acquisition team)",
    "rpo": "recruitment process outsourcing provider embedded with client companies",
    "freelance": "independent / solo recruiter or contract recruiter",
    "unclear": "cannot tell",
}
TITLE_RANK = [(r"\b(owner|founder|co-?founder|ceo|president|managing (partner|director)|principal)\b", 0),
              (r"\b(chief|vp|vice president|svp|evp|head of|partner)\b", 1),
              (r"\b(director)\b", 2),
              (r"\b(manager|lead|senior|sr\.?)\b", 3)]


LOCAL_EXCL_TITLE = re.compile(r"\b(assistant|intern|internship|coordinator|admissions|student|scheduler)\b", re.I)


def title_rank(t: str) -> int:
    t = (t or "").lower()
    t = re.sub(r"\b(talent|recruiting|recruitment|people|hr|business) (acquisition )?partner\b", "recruiter", t)
    for pat, rank in TITLE_RANK:
        if re.search(pat, t):
            return rank
    return 4


# Profile "agency" (wave 2, 2026-11-10): the prior DM_Recruitment copy sells to agencies, and the general pool
# ranks in-house corporate TA first. Agency rows = recruiting/staffing/search employers, recruiter titles plus the
# agency's owners, partners, consultants and BD; people already exported sit on the viewed list and are skipped.
AGENCY_INDUSTRY = ["Staffing and Recruiting", "Executive Search Services"]
AGENCY_TITLES = TITLES + ["Account Manager", "Business Development", "Owner", "Founder", "President",
                          "Managing Director", "Partner", "Principal", "Consultant"]
VIEWED_SET = "recruiters_w1"
PROFILE = "general"


def filters(loc: str, status: str) -> dict[str, Any]:
    f = {"title": TITLES, "excludeTitle": EXCL_TITLES, "excludeCompanyName": EXCL_COMPANY, "country": "US",
         "city": LOCATIONS[loc]["city"], "emailStatus": [status], "emailType": ["work"]}
    if PROFILE == "agency":
        f.update(title=AGENCY_TITLES, industry=AGENCY_INDUSTRY, excludeViewed="true", viewedSet=VIEWED_SET)
    return f


def pkey(loc: str, status: str) -> str:
    return f"{loc}:{status}" if PROFILE == "general" else f"{PROFILE}:{loc}:{status}"


def cmd_mark_viewed(_: argparse.Namespace) -> None:
    """Put every exported person_id on the LeadOcean viewed list (free), so later profiles never re-bill them."""
    ids = sorted({r["person_id"] for r in load_raw() if r.get("person_id")})
    lo = lol.LeadOcean()
    for i in range(0, len(ids), 2000):  # 10,000 ids per call hits HTTP 413 "Body too large"
        lo.req("POST", "/v1/people/viewed", body={"ids": ids[i:i + 2000], "set": VIEWED_SET})
    print(f"viewed list {VIEWED_SET}: sent {len(ids)} person_ids")


# ------------------------------------------------------------------------------------------------ count / export
def cmd_count(_: argparse.Namespace) -> None:
    lo = lol.LeadOcean()
    out = {}
    for loc in LOCATIONS:
        for st in SEARCH_STATUSES:
            out[pkey(loc, st)] = lo.count(filters(loc, st))
            print(f"{loc:11s} {st:9s} {out[pkey(loc, st)]}")
    counts = lol.jload(TMP / "counts.json", {})
    counts.update(out)
    lol.jsave(TMP / "counts.json", counts)


def build_plan(counts: dict[str, Any], budget: int) -> list[dict[str, Any]]:
    """Every verified row first; the rest of the budget goes to untested rows in proportion to each pool."""
    plan, left = [], budget
    for loc in LOCATIONS:
        n = int(counts[pkey(loc, "verified")]["total"] or 0)
        take = min(n, left)
        if take:
            plan.append({"key": pkey(loc, "verified"), "loc": loc, "status": "verified", "limit": take})
        left -= take
    pools = {loc: int(counts[pkey(loc, "untested")]["total"] or 0) for loc in LOCATIONS}
    total = sum(pools.values()) or 1
    for loc, n in pools.items():
        take = min(n, int(left * n / total))
        if take:
            plan.append({"key": pkey(loc, "untested"), "loc": loc, "status": "untested", "limit": take})
    return plan


def cmd_export(args: argparse.Namespace) -> None:
    counts = lol.jload(TMP / "counts.json", {})
    if not counts:
        raise SystemExit("run `count` first")
    state_path = TMP / "exports.json"
    state = lol.jload(state_path, {})
    plan = build_plan(counts, args.budget)
    print(f"plan: {sum(c['limit'] for c in plan)} rows")
    for c in plan:
        print(f"  {c['key']:22s} limit={c['limit']}" + ("  (done)" if c["key"] in state else ""))
    if args.plan_only:
        return
    lo = lol.LeadOcean()
    left = lol.export_rows_left_today(lo)
    for c in plan:
        if c["key"] in state:
            continue
        limit = min(c["limit"], args.sample or c["limit"], left)
        if limit <= 0:
            print(f"skip {c['key']}: no export rows left today")
            continue
        body = {"name": f"recruiters {c['key']} {TODAY}",
                "filters": lol.export_body_filters(filters(c["loc"], c["status"])),
                "limit": limit, "columns": lol.EXPORT_COLUMNS, "caps": {"emails": 3}}
        data = lo.req("POST", "/v1/exports", body=body)["data"]
        state[c["key"]] = {"id": data["id"], "requested": limit, "status": data.get("status"), "niche": c["loc"],
                           "metro": c["status"]}
        left -= limit
        lol.jsave(state_path, state)
        print(f"queued {c['key']} id={data['id']} limit={limit}")
    lol.RAW = RAW
    lol.ROOT = ROOT
    lol.poll_and_download(lo, state, state_path)
    cmd_mark_viewed(args)


def load_raw() -> list[dict[str, Any]]:
    rows, seen_files = [], set()
    for key, s in lol.jload(TMP / "exports.json", {}).items():
        if s.get("status") != "downloaded" or s["file"] in seen_files:
            continue  # same file under two keys (a sample re-exported in full) would double-count rows
        seen_files.add(s["file"])
        with open(ROOT / s["file"], newline="", encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                r["_src"] = key
                rows.append(r)
    return rows


# ------------------------------------------------------------------------------------------------ gate
def location_of(r: dict[str, Any]) -> str | None:
    st = (r.get("state") or "").strip().upper()
    for loc, d in LOCATIONS.items():
        if st in d["states"]:
            return loc
    if st or (r.get("country_code") or "").upper() not in ("US", ""):
        return None
    # Blank state: fall back to an exact city match (e.g. "Houston"); ambiguous names like Pasadena stay out.
    city = (r.get("city") or "").strip().lower()
    hits = [loc for loc, d in LOCATIONS.items() if city in {c.lower() for c in d["city"]} - {"pasadena", "newark",
                                                                                          "cambridge", "spring"}]
    return hits[0] if len(hits) == 1 else None


def hygiene(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    keep, rejects, staged = [], [], []
    seen_email, seen_person = set(), set()

    def reject(r: dict[str, Any], why: str) -> None:
        r["reject_reason"] = why
        rejects.append(r)

    for r in rows:
        email, status, vdate, _ = lol.pick_email(r)
        dom = lol.norm_domain(r.get("current_company_domain")) or lol.norm_domain(r.get("current_company_website"))
        r.update(_email=email, _email_status=status, _email_verified_date=vdate, _company_domain=dom,
                 _loc=location_of(r))
        pid = r.get("person_id") or r.get("profile_url") or email
        if not email or "@" not in email:
            reject(r, "no_email")
            continue
        if email in seen_email or pid in seen_person:
            reject(r, "duplicate")
            continue
        seen_email.add(email)
        seen_person.add(pid)
        if status not in SEARCH_STATUSES:
            reject(r, f"status_{status or 'blank'}")
            continue
        if not r["_loc"]:
            reject(r, "out_of_area")
            continue
        if LOCAL_EXCL_TITLE.search(r.get("current_job_title") or ""):
            reject(r, "excluded_title")
            continue
        local, edom = email.split("@", 1)
        if edom in lol.FREE_MAIL:
            reject(r, "free_mail")
            continue
        if lol.is_role(local):
            reject(r, "role_address")
            continue
        if dom:
            ok = (edom == dom or edom.endswith("." + dom) or dom.endswith("." + edom)
                  or lol.base_label(edom) == lol.base_label(dom))
        else:
            ok = len(lol.base_label(edom)) >= 4 and lol.base_label(edom) in lol.slug(r.get("current_company_name", ""))
            if ok:
                r["_company_domain"] = edom
        if not ok:
            reject(r, "domain_mismatch")
            continue
        if edom.endswith((".mil", ".gov")):
            reject(r, "gov_mil")
            continue
        staged.append(r)
    domains = sorted({r["_email"].split("@", 1)[1] for r in staged})
    with ThreadPoolExecutor(max_workers=16) as pool:
        mx = dict(zip(domains, pool.map(lol.has_mx, domains)))
    for r in staged:
        m = mx.get(r["_email"].split("@", 1)[1])
        if m is False:
            reject(r, "no_mx")
        elif m is None:
            reject(r, "mx_unresolved")
        else:
            keep.append(r)
    return keep, rejects


def jev_questions() -> dict[str, dict[str, Any]]:
    from execution.modules import jev_client as jev
    return {
        "recruiter": jev.noul(
            "Does this person personally recruit: find, contact and screen candidates for open roles?",
            "true for recruiters, sourcers, talent acquisition partners/managers/leads, recruiting managers, "
            "agency recruiters, staffing account managers who recruit, search consultants and owners of "
            "recruiting/staffing firms",
            "false for HR generalists, payroll, nurse/shift scheduling ('staffing coordinator' in a hospital), "
            "job seekers, military recruiters, sales reps selling HR software, and people whose title only "
            "mentions recruiting in passing"),
        "segment": jev.choice("Which kind of recruiter is this?", SEGMENTS),
        "specialty": jev.choice("What does this person mainly recruit for?",
                                {k: v["desc"] for k, v in SPECIALTIES.items()}),
    }


def person_state(r: dict[str, Any]) -> dict[str, Any]:
    return {"title": r.get("current_job_title", ""), "headline": (r.get("profile_headline") or "")[:300],
            "summary_snippet": (r.get("profile_summary") or "")[:600],
            "employer": r.get("current_company_name", ""), "employer_industry": r.get("current_company_industry", ""),
            "employer_size": r.get("current_company_employees", "")}


def cmd_gate(args: argparse.Namespace) -> None:
    from execution.modules import jev_client as jev
    rows = load_raw()
    if not rows:
        raise SystemExit("no downloaded exports; run `export` first")
    keep, rejects = hygiene(rows)
    print(f"hygiene: {len(rows)} raw -> {len(keep)} kept; rejects {dict(Counter(r['reject_reason'] for r in rejects))}")
    cache_path = TMP / "jev_cache.json"
    cache = lol.jload(cache_path, {})
    todo = [r for r in keep if r["_email"] not in cache]
    if args.limit:
        todo = todo[: args.limit]
    qs, cost = jev_questions(), 0.0
    for i in range(0, len(todo), 200):
        chunk = todo[i:i + 200]
        for r, res in zip(chunk, jev.decide_many([person_state(r) for r in chunk], qs, workers=8)):
            cost += res.cost_usd
            cache[r["_email"]] = ({"error": res.error[:200]} if res.error else
                                  {"recruiter": res.noul("recruiter"), "segment": res.choice("segment"),
                                   "segment_conf": res.confidence("segment"), "specialty": res.choice("specialty"),
                                   "specialty_conf": res.confidence("specialty")})
        lol.jsave(cache_path, cache)
        print(f"jev: {min(i + 200, len(todo))}/{len(todo)}, ${cost:.4f}", flush=True)
    jev.append_ledger({"caller": "recruiter_leads.gate", "items": len(todo), "cost_usd": cost})
    gated = []
    for r in keep:
        j = cache.get(r["_email"])
        if j is None:
            continue  # not yet asked (only with --limit)
        if "error" in j:
            r["_flags"] = "jev_unchecked"
        elif j["recruiter"] < 0.4:
            r["reject_reason"] = "jev_not_recruiter"
            rejects.append(r)
            continue
        gated.append(r)
    # Pre-Reoon reserve per company: rank verified first, then seniority.
    by_co: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for r in gated:
        by_co[r["_company_domain"]].append(r)
    final = []
    for people in by_co.values():
        people.sort(key=lambda p: (p["_email_status"] != "verified", title_rank(p.get("current_job_title", ""))))
        for i, p in enumerate(people):
            if i < COMPANY_RESERVE:
                final.append(p)
            else:
                p["reject_reason"] = f"company_reserve_{COMPANY_RESERVE}"
                rejects.append(p)
    lol.jsave(TMP / "gate.json", {"kept": final, "rejects": rejects})
    print(f"gate: kept {len(final)}; rejects {dict(Counter(r['reject_reason'] for r in rejects))}")


# ------------------------------------------------------------------------------------------------ verify
def cmd_verify(args: argparse.Namespace) -> None:
    from execution.lead_sourcing import reoon_verify as rv
    kept = lol.jload(TMP / "gate.json", {}).get("kept", [])
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
    lock, done = threading.Lock(), 0

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
    n_ok = sum(1 for e in todo if cache.get(e, {}).get("status") != "error")
    rv.append_ledger({"ts": TODAY, "src": "recruiter_leads.verify", "n_verified": n_ok,
                      "n_errors": len(todo) - n_ok, "credits_est": n_ok})
    b = Counter(rv.bucket(cache[r["_email"]]) if r["_email"] in cache else "pending" for r in kept)
    print(f"reoon buckets over gated rows {dict(b)}")


# ------------------------------------------------------------------------------------------------ build
COLS = ["email", "first_name", "last_name", "title", "company_name", "website", "city", "state", "location",
        "segment", "specialty", "specialty_evidence", "personalization", "linkedin_url", "company_domain",
        "leadocean_status", "reoon_status", "reoon_score", "send_bucket", "source"]
CO_SUFFIX = re.compile(r"[,\s]+(inc\.?|llc|l\.l\.c\.|ltd\.?|corp\.?|corporation|co\.|lp|llp|pllc|pc|group inc\.?)$", re.I)


def company_casual(name: str) -> str:
    n = lol.clean(name)
    for _ in range(2):
        n = CO_SUFFIX.sub("", n).strip()
    return n


def specialty_for(r: dict[str, Any], j: dict[str, Any]) -> tuple[str, str]:
    """(phrase, evidence word) when Jev is confident AND the person's/employer's own text backs it; else blanks."""
    k = j.get("specialty", "general")
    spec = SPECIALTIES.get(k)
    if not spec or k == "general" or j.get("specialty_conf", 0) < 0.6:
        return "", ""
    text = " ".join(str(r.get(f) or "") for f in ("current_job_title", "profile_headline", "profile_summary",
                                                     "current_company_name", "current_company_industry")).lower()
    text = f" {text} "
    for w in spec["evidence"]:
        if w in text:
            return spec["phrase"], w.strip()
    return "", ""


def segment_of(r: dict[str, Any], j: dict[str, Any]) -> str:
    """Agency | InHouse. Employer industry decides when it is a staffing/search firm; else Jev's segment."""
    if (r.get("current_company_industry") or "") in AGENCY_INDUSTRY:
        return "Agency"
    if j.get("segment") in ("agency", "rpo", "freelance") and j.get("segment_conf", 0) >= 0.6:
        return "Agency"
    return "InHouse"


def cmd_build(_: argparse.Namespace) -> None:
    from execution.lead_sourcing import reoon_verify as rv
    g = lol.jload(TMP / "gate.json", {})
    kept, rejects = g.get("kept", []), g.get("rejects", [])
    jc, rc = lol.jload(TMP / "jev_cache.json", {}), rv.load_cache()
    rows = []
    for r in kept:
        res = rc.get(r["_email"])
        if not res:
            r["reject_reason"] = "reoon_pending"
            rejects.append(r)
            continue
        b = rv.bucket(res)
        if b == "drop":
            r["reject_reason"] = f"reoon_{res.get('status') or 'error'}"
            rejects.append(r)
            continue
        j = jc.get(r["_email"], {})
        phrase, ev = specialty_for(r, j)
        rows.append({
            "email": r["_email"], "first_name": lol.name_case(r.get("profile_first_name")),
            "last_name": lol.name_case(r.get("profile_last_name")), "title": lol.clean(r.get("current_job_title")),
            "company_name": company_casual(r.get("current_company_name")),
            "website": lol.clean(r.get("current_company_website")) or f"https://{r['_company_domain']}",
            "city": lol.clean(r.get("city")), "state": lol.clean(r.get("state")),
            "location": LOCATIONS[r["_loc"]]["label"], "segment": segment_of(r, j), "specialty": phrase,
            "specialty_evidence": ev, "personalization": "Personalized" if phrase else "NoPersonalization",
            "linkedin_url": lol.clean(r.get("profile_url")), "company_domain": r["_company_domain"],
            "leadocean_status": r["_email_status"], "reoon_status": res.get("status"),
            "reoon_score": res.get("score"), "send_bucket": b, "source": r.get("_flags", "") or "leadocean",
            "_rank": (b != "main", r["_email_status"] != "verified", title_rank(r.get("current_job_title", ""))),
            "_loc": r["_loc"]})
    # Final cap: COMPANY_CAP per company, main bucket preferred.
    by_co: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_co[row["company_domain"]].append(row)
    final = []
    for people in by_co.values():
        people.sort(key=lambda p: p["_rank"])
        final.extend(people[:COMPANY_CAP])
        for p in people[COMPANY_CAP:]:
            rejects.append({"_email": p["email"], "reject_reason": f"company_cap_{COMPANY_CAP}",
                            "current_company_name": p["company_name"], "_loc": p["_loc"]})
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "catchall").mkdir(exist_ok=True)
    for f in list(OUT.glob("*.csv")) + list((OUT / "catchall").glob("*.csv")):
        f.unlink()

    def write(path: Path, data: list[dict[str, Any]], cols: list[str]) -> None:
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
            w.writeheader()
            for d in data:
                w.writerow(csv_safe_row({c: d.get(c, "") for c in cols}))

    write(TMP / f"recruiters_all_{TODAY}.csv", final, COLS)
    index = []
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in final:
        groups[(row["_loc"], row["personalization"], row["send_bucket"])].append(row)
    # Operator 2026-11-10: one campaign per location x personalization; segment stays a column only.
    for (loc, pers, b), data in sorted(groups.items()):
        name = f"Recruitment_{LOCATIONS[loc]['file']}_{pers}" + ("_CatchAll" if b == "catchall" else "")
        path = (OUT / "catchall" if b == "catchall" else OUT) / f"{name}.csv"
        write(path, data, COLS)
        index.append({"file": str(path.relative_to(TMP)), "location": LOCATIONS[loc]["label"],
                      "personalization": pers, "bucket": b, "leads": len(data)})
    write(OUT / "_campaign_index.csv", index, ["file", "location", "personalization", "bucket", "leads"])
    write(TMP / "rejects.csv", [{"email": r.get("_email", ""), "title": r.get("current_job_title", ""),
                                 "company_name": r.get("current_company_name", ""),
                                 "location": LOCATIONS.get(r.get("_loc") or "", {}).get("label", ""),
                                 "leadocean_status": r.get("_email_status", ""),
                                 "reject_reason": r.get("reject_reason", "")} for r in rejects],
          ["email", "title", "company_name", "location", "leadocean_status", "reject_reason"])
    summary = {
        "date": TODAY, "raw_rows": len(load_raw()), "final": len(final),
        "by_location_segment_bucket": {f"{LOCATIONS[k[0]]['label']}|{k[1]}|{k[2]}": n for k, n in
                                       sorted(Counter((r["_loc"], r["segment"], r["send_bucket"])
                                                      for r in final).items())},
        "personalized_share": round(sum(r["personalization"] == "Personalized" for r in final) / max(len(final), 1), 3),
        "segments": dict(Counter(r["segment"] for r in final)),
        "specialties": dict(Counter(r["specialty"] or "-" for r in final)),
        "rejects": dict(Counter(r.get("reject_reason", "") for r in rejects).most_common()),
        "campaign_files": index,
    }
    lol.jsave(TMP / "summary.json", summary)
    print(json.dumps({k: v for k, v in summary.items() if k != "campaign_files"}, indent=1))
    for i in index:
        print(f"  {i['file']}: {i['leads']}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    ap.add_argument("--profile", choices=["general", "agency"], default="general",
                    help="export profile: general recruiter titles, or agency-only (staffing/search firms)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("count")
    e = sub.add_parser("export")
    e.add_argument("--budget", type=int, default=10000)
    e.add_argument("--sample", type=int, default=0)
    e.add_argument("--plan-only", action="store_true")
    g = sub.add_parser("gate")
    g.add_argument("--limit", type=int, default=0)
    v = sub.add_parser("verify")
    v.add_argument("--max-credits", type=int, default=500)
    v.add_argument("--workers", type=int, default=8)
    v.add_argument("--limit", type=int, default=0)
    sub.add_parser("build")
    sub.add_parser("mark-viewed")
    a = ap.parse_args()
    global PROFILE
    PROFILE = a.profile
    TMP.mkdir(parents=True, exist_ok=True)
    {"count": cmd_count, "export": cmd_export, "gate": cmd_gate, "verify": cmd_verify, "build": cmd_build,
     "mark-viewed": cmd_mark_viewed}[a.cmd](a)


if __name__ == "__main__":
    import logging
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    main()
