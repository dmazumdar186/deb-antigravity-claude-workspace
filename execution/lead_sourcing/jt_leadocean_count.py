"""
jt_leadocean_count.py

description: Free LeadOcean sizing for the Jacob Tyler (San Diego brand + web agency) cold email ICP: people and distinct companies per vertical x geography (US / California / San Diego county) x decision-maker title group, plus what an export of each cell would cost in rows. Count calls only; never exports, never calls Reoon, OpenRouter or Instantly.
inputs: env LEADOCEAN_API_KEY; subcommand `export` (see directive); flags --out PATH (default .tmp/les/jt_leadocean_counts.json), --refresh (ignore cached cells), --only VERTICAL[,VERTICAL].
outputs: JSON at --out (config, account export allowance, cells, totals) and a Markdown table beside it (same stem, .md).
usage:
    python3 execution/lead_sourcing/jt_leadocean_count.py
    python3 execution/lead_sourcing/jt_leadocean_count.py --only medtech --refresh

Reuses leadocean_leads.LeadOcean (x-api-key auth, pacing, 429/5xx retries). The sizing call is
GET /v1/people/search?count=true&limit=1, which returns meta.credits = 0 (free; verified 2026-11-12).
An export (POST /v1/exports) bills 1 record per row written, so the cost of exporting a cell = its row count
(capped by the account's 5,000 export rows/day). Idempotent: each cell is cached in the output JSON and
skipped on re-run unless --refresh.
Directive: directives/lead_sourcing/jt_leadocean_count.md
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import random
import re
import sys
import time
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))
from leadocean_leads import (EXPORT_COLUMNS, ROOT, TODAY, LeadOcean, jload, jsave,  # noqa: E402
                             norm_domain, slug, title_rank)

log = logging.getLogger("jt_leadocean_count")

DEFAULT_OUT = ROOT / ".tmp" / "les" / "jt_leadocean_counts.json"
SIZE = {"minEmployees": 20, "maxEmployees": 500}  # proxy for $5M-$100M revenue

# Jacob Tyler's proven verticals (.tmp/les/research_jacobtyler.md section 2). Industry names come from the free
# facets on a sizing call; keyword-only verticals (RIA, credit unions, supplements) also need an industry list,
# otherwise keywords match staff profiles at unrelated employers.
VERTICALS: dict[str, dict[str, Any]] = {
    "medtech": {
        "label": "Medical devices / diagnostics / life sciences manufacturers",
        "industry": ["Medical Equipment Manufacturing", "Medical Device", "Biotechnology Research", "Biotechnology",
                     "Pharmaceutical Manufacturing"],
    },
    "construction": {
        "label": "Commercial construction + specialty trade contractors",
        "industry": ["Construction", "Building Construction", "Nonresidential Building Construction",
                     "Specialty Trade Contractors", "Building Equipment Contractors",
                     "Building Finishing Contractors", "Civil Engineering", "Utility System Construction"],
        "excludeCompanyName": ["Homes", "Home Builder", "Roofing", "Remodel"],
    },
    "finserv": {
        "label": "Wealth advisory / RIAs / credit unions",
        "industry": ["Financial Services", "Investment Management", "Investment Advice", "Banking",
                     "Credit Intermediation"],
        "companyKeywords": ["wealth management", "wealth advisor", "registered investment advisor",
                            "financial planning", "private wealth", "family office", "credit union"],
    },
    "consumer": {
        "label": "Consumer & wellness products (supplements, skincare)",
        "industry": ["Personal Care Product Manufacturing", "Food and Beverage Manufacturing",
                     "Wellness and Fitness Services", "Consumer Goods", "Cosmetics", "Pharmaceutical Manufacturing",
                     "Manufacturing", "Retail", "Retail Health and Personal Care Products"],
        "companyKeywords": ["supplements", "dietary supplement", "nutraceutical", "sports nutrition", "skincare",
                            "skin care", "cosmetics", "wellness products", "personal care products"],
    },
    "profservices": {
        "label": "Engineering, environmental consulting, PR / public affairs",
        "industry": ["Engineering Services", "Civil Engineering", "Environmental Services",
                     "Public Relations and Communications Services", "Government Relations Services"],
    },
}

SD_CITIES = ["San Diego", "Carlsbad", "La Jolla", "Del Mar", "Oceanside", "Escondido", "Coronado", "Chula Vista",
             "Encinitas", "Poway", "Vista", "San Marcos", "El Cajon", "La Mesa", "Santee", "National City",
             "Solana Beach", "Rancho Santa Fe", "Rancho Bernardo", "Sorrento Valley", "Lakeside", "Spring Valley",
             "Imperial Beach", "Lemon Grove", "Ramona", "Fallbrook", "Bonita", "Alpine", "Rancho San Diego",
             "Cardiff", "Cardiff by the Sea", "Valley Center", "Otay Mesa"]
# Fallback for California when the API drops hqState: SD county + LA/OC/Inland Empire + Bay Area + Sacramento +
# Central Valley + Central Coast metros.
CA_CITIES = SD_CITIES + [
    "Los Angeles", "Long Beach", "Santa Monica", "Culver City", "Burbank", "Glendale", "Pasadena", "Torrance",
    "El Segundo", "Gardena", "Carson", "Commerce", "City of Industry", "Van Nuys", "Chatsworth", "Valencia",
    "Santa Clarita", "Irvine", "Santa Ana", "Anaheim", "Costa Mesa", "Newport Beach", "Tustin", "Orange",
    "Huntington Beach", "Fullerton", "Brea", "Lake Forest", "Aliso Viejo", "Mission Viejo", "Rancho Santa Margarita",
    "Riverside", "San Bernardino", "Ontario", "Rancho Cucamonga", "Corona", "Temecula", "Murrieta", "Fontana",
    "Redlands", "Palm Desert", "Palm Springs", "San Francisco", "Oakland", "San Jose", "Hayward", "Fremont",
    "Pleasanton", "Dublin", "San Ramon", "Walnut Creek", "Concord", "Santa Clara", "Sunnyvale", "Milpitas",
    "Redwood City", "San Mateo", "Burlingame", "South San Francisco", "Palo Alto", "San Carlos", "Berkeley",
    "Emeryville", "Richmond", "Livermore", "Santa Rosa", "Petaluma", "Napa", "Sacramento", "Rancho Cordova",
    "Roseville", "Rocklin", "West Sacramento", "Folsom", "Elk Grove", "Stockton", "Modesto", "Fresno", "Clovis",
    "Bakersfield", "Visalia", "Santa Barbara", "Ventura", "Oxnard", "Camarillo", "Thousand Oaks", "Simi Valley",
    "San Luis Obispo", "Salinas", "Monterey", "Santa Cruz", "Chico", "Redding"]
GEOS: dict[str, dict[str, Any]] = {
    "us": {"label": "US", "hqCountry": ["US"]},
    "ca": {"label": "California", "hqCountry": ["US"], "hqState": ["CA"]},
    "sd": {"label": "San Diego county", "hqCountry": ["US"], "hqState": ["CA"], "hqCity": SD_CITIES},
}

BASE_EXCL_TITLE = ["Assistant", "Intern", "Former", "Retired", "Advisor", "Board Member", "Student", "Volunteer"]
TITLE_GROUPS: dict[str, dict[str, Any]] = {
    "exec": {"label": "CEO / Founder / President / Owner",
             "title": ["CEO", "Chief Executive", "Founder", "Co-Founder", "President", "Owner"],
             # "President" would match every Vice President; product/process owners are not buyers.
             "excludeTitle": BASE_EXCL_TITLE + ["Vice President", "VP", "Product Owner", "Process Owner",
                                                "Owner Representative", "Owner's Representative"],
             "seniority": ["owner", "founder", "c_suite"]},
    "marketing": {"label": "CMO / VP or Head of Marketing",
                  "title": ["CMO", "Chief Marketing Officer", "VP Marketing", "VP of Marketing",
                            "Vice President of Marketing", "Vice President Marketing",
                            "Head of Marketing", "SVP Marketing", "Senior Vice President of Marketing"],
                  "excludeTitle": BASE_EXCL_TITLE, "seniority": ["c_suite", "vp", "director"]},
}

# Title values match as phrases (free-count probes 2026-11-12, US medical equipment 20-500: "CEO" 2,993,
# "Owner" 5,039, "VP Marketing" 103); seniority is ANDed on to drop entry/manager-level noise.

# pool = which contacts are counted. any = every matching person; verified = LeadOcean-verified work email
# (wave-1 send standard); verified_untested = the wave-2 pool that still needs Reoon before sending.
POOLS: dict[str, dict[str, Any]] = {
    "any": {},
    "verified": {"emailStatus": ["verified"], "emailType": ["work"]},
    "verified_untested": {"emailStatus": ["verified", "untested"], "emailType": ["work"]},
}


def cell_filters(vertical: str, geo: str, group: str, pool: str) -> dict[str, Any]:
    v, g, t = VERTICALS[vertical], GEOS[geo], TITLE_GROUPS[group]
    f: dict[str, Any] = dict(SIZE)
    for k in ("industry", "companyKeywords", "excludeIndustry", "excludeCompanyName"):
        if v.get(k):
            f[k] = v[k]
    for k in ("hqCountry", "hqState", "hqCity"):
        if g.get(k):
            f[k] = g[k]
    f["title"], f["excludeTitle"], f["seniority"] = t["title"], t["excludeTitle"], t["seniority"]
    f.update(POOLS[pool])
    # LeadOcean.count joins list values with commas, so a comma inside a value ("Vice President, Marketing")
    # silently splits it into two looser terms (that one matched every "Marketing" title: 22.9k vs ~0.7k).
    bad = [x for v in f.values() if isinstance(v, list) for x in v if "," in x]
    if bad:
        raise ValueError(f"filter values must not contain commas: {bad}")
    return f


SIZE_BANDS = [(20, 50), (51, 200), (201, 500)]


def count_cell(lo: LeadOcean, f: dict[str, Any]) -> dict[str, Any]:
    """Free count; when LeadOcean drops a filter (meta.unsupportedFilters, e.g. hqState on US Construction),
    re-count per employee band and sum. Bands split companies disjointly, so people and companies both add up."""
    c = lo.count(f)
    if not c.get("unsupported"):
        return c
    if "hqState" in c["unsupported"] and "hqCity" not in f and f.get("hqState") == ["CA"]:
        # Observed 2026-11-12: hqState is dropped for the "Construction" industry at any size band, while
        # hqState + hqCity works, so CA falls back to its main metros (a lower bound for the state).
        # hqCity takes at most 50 values (HTTP 400); a company has one HQ city, so chunk sums are disjoint.
        total = cos = 0
        for i in range(0, len(CA_CITIES), 50):
            m = lo.count(dict(f, hqCity=CA_CITIES[i:i + 50]))
            if m.get("unsupported"):
                break
            total += int(m.get("total") or 0)
            cos += int(m.get("companies") or 0)
        else:
            return {"total": total, "companies": cos, "unsupported": [],
                    "note": "hqState dropped by API; counted CA_CITIES metros only (lower bound)"}
    total = cos = 0
    for lo_n, hi_n in SIZE_BANDS:
        b = lo.count(dict(f, minEmployees=lo_n, maxEmployees=hi_n))
        if b.get("unsupported"):
            return {"total": None, "companies": None, "unsupported": b["unsupported"],
                    "note": f"filter dropped even in band {lo_n}-{hi_n}"}
        total += int(b.get("total") or 0)
        cos += int(b.get("companies") or 0)
    return {"total": total, "companies": cos, "unsupported": [], "note": "summed over employee bands"}


def account_allowance(lo: LeadOcean) -> dict[str, Any]:
    """Export rows left today and plan balances (GET /v1/account is a free read)."""
    try:
        data = lo.req("GET", "/v1/account").get("data") or {}
    except RuntimeError as exc:
        log.warning("account read failed: %s", exc)
        return {"error": str(exc)[:300]}
    day = (data.get("exports") or {}).get("day") or {}
    rec = data.get("records") or {}
    return {"plan": (data.get("account") or {}).get("plan"),
            "export_rows_day_limit": day.get("limit"), "export_rows_day_used": day.get("used"),
            "records_ceiling": rec.get("ceiling"), "records_used_this_period": rec.get("used"),
            "records_remaining": rec.get("remaining"), "records_when_over": rec.get("whenOver"),
            "records_resets_at": rec.get("resetsAt")}


def write_md(doc: dict[str, Any], path: Path) -> None:
    cells, acct = doc["cells"], doc.get("account") or {}
    lines = [f"# Jacob Tyler LeadOcean sizing ({doc['date']})", "",
             "Free count calls only (`meta.credits` = 0 on every call). Size 20-500 employees. "
             "Export cost = 1 LeadOcean record per row; daily export cap "
             f"{acct.get('export_rows_day_limit', '?')} rows (used today: {acct.get('export_rows_day_used', '?')}).",
             "", "people / companies. `verified` = LeadOcean-verified work email (send-ready standard); "
             "`v+u` adds untested work emails (needs Reoon). Export cost in rows = the people count of the pool "
             "you export. `Verified @2/co` = usable rows after the workspace's 2-contacts-per-company cap "
             "(a domain-filtered export can be sized to it).", "",
             "| Vertical | Geo | Titles | All people | All cos | Verified people | Verified cos | Verified @2/co | "
             "v+u people | v+u cos |",
             "|---|---|---|---:|---:|---:|---:|---:|---:|---:|"]
    for key, c in cells.items():
        if c.get("error"):
            lines.append(f"| {key} | | | error: {c['error'][:80]} | | | | | |")
            continue
        vt, geo, grp = key.split(":")

        def pc(pool: str) -> tuple[Any, Any]:
            x = c.get(pool) or {}
            return x.get("total"), x.get("companies")
        a, v, u = pc("any"), pc("verified"), pc("verified_untested")
        cap2 = min(v[0] or 0, 2 * (v[1] or 0))
        notes = {(c.get(p) or {}).get("note") for p in POOLS} - {None}
        geo_label = GEOS[geo]["label"] + (" (metros, lower bound)" if any("CA_CITIES" in n for n in notes) else "")
        lines.append(f"| {vt} | {geo_label} | {grp} | {a[0]} | {a[1]} | {v[0]} | {v[1]} | {cap2} | "
                     f"{u[0]} | {u[1]} |")
    t = doc.get("totals") or {}
    lines += ["", "## Totals (exec + marketing, may double-count a person holding both titles)", "",
              "| Geo | Pool | People (= export rows) | Companies (sum over verticals) | Export days at cap |",
              "|---|---|---:|---:|---:|"]
    for geo, pools in t.items():
        for pool, x in pools.items():
            lines.append(f"| {GEOS[geo]['label']} | {pool} | {x['people']} | {x['companies']} | {x['export_days']} |")
    unsupported = sorted({u for c in cells.values() for p in POOLS if isinstance(c.get(p), dict)
                          for u in c[p].get("unsupported") or []})
    lines += ["", f"Unsupported filters reported by the API: {unsupported or 'none'}."]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# --------------------------------------------------------------------------------------
# export: bulk-export medtech + construction (exec + marketing, verified work email, US), cap 2 contacts/company
# --------------------------------------------------------------------------------------
LEADS_DIR = ROOT / ".tmp" / "les" / "leads"
LEDGER = LEADS_DIR / "export_ledger.json"
RAW_DIR = LEADS_DIR / "raw"
DROP_FILE = LEADS_DIR / "drop_list.json"  # gitignored: {"domains": [...], "names": [...]}
EXPORT_VERTICALS = ["medtech", "construction"]  # priority order: medtech in full first, construction gets the rest
EXPORT_GROUPS = ["marketing", "exec"]  # smaller, higher-value group first so a truncated export keeps it
OUT_COLS = ["first_name", "last_name", "title", "email", "company", "domain", "website", "city", "state",
            "employees", "linkedin", "vertical"]
SUFFIX = re.compile(r"(incorporated|inc|llc|llp|ltd|corp|corporation|company|co|group|holdings|the)$")


def norm_name(name: str) -> str:
    s = slug(name)
    prev = None
    while prev != s:
        prev, s = s, SUFFIX.sub("", s) if len(s) > 6 else s
    return s


def job_filters(vertical: str, group: str) -> dict[str, Any]:
    """Export filter = exactly the count's `verified` cell for the US (single source of truth)."""
    return cell_filters(vertical, "us", group, "verified")


def job_key(vertical: str, group: str, f: dict[str, Any]) -> str:
    h = hashlib.sha1(json.dumps(f, sort_keys=True).encode()).hexdigest()[:10]
    return f"{vertical}:{group}:{h}"


def pick_verified(r: dict[str, str]) -> str:
    for i in range(1, 4):
        if (r.get(f"email_{i}_status") or "").lower() == "verified" and (r.get(f"email_{i}_type") or "").lower() == "work":
            return (r.get(f"email_{i}_address") or "").strip().lower()
    return ""


MKT = re.compile(r"\b(cmo|chief marketing|marketing)\b", re.I)


def contact_rank(title: str) -> int:
    t = title or ""
    if re.search(r"\bvice president\b|\bvp\b", t, re.I) and not MKT.search(t):
        return 5
    r = title_rank(t)
    if r == 0:
        return 0
    if MKT.search(t) and re.search(r"\b(cmo|chief|vp|vice president|head|director|svp)\b", t, re.I):
        return 1
    return 2 + r


def load_drops() -> tuple[set[str], set[str]]:
    d = jload(DROP_FILE, {})
    return ({norm_domain(x) for x in d.get("domains", [])}, {norm_name(x) for x in d.get("names", [])})


def run_export(args: argparse.Namespace) -> None:
    counts = {}
    lo = LeadOcean()
    for v in EXPORT_VERTICALS:
        for g in EXPORT_GROUPS:
            c = count_cell(lo, job_filters(v, g))
            counts[(v, g)] = int(c.get("total") or 0)
            print(f"count {v}:{g} verified={counts[(v, g)]} companies={c.get('companies')} unsupported={c.get('unsupported')}")
    acct = account_allowance(lo)
    left = None
    if acct.get("export_rows_day_limit") is not None:
        left = int(acct["export_rows_day_limit"]) - int(acct.get("export_rows_day_used") or 0)
    print(f"quota: export rows/day limit={acct.get('export_rows_day_limit')} used={acct.get('export_rows_day_used')} "
          f"left={left}; records_remaining={acct.get('records_remaining')}")
    ledger = jload(LEDGER, {"jobs": {}})
    jobs = ledger["jobs"]
    # Failed/cancelled jobs billed nothing (observed: transient "person_id lookup unavailable"); retry them.
    spent = sum(int(j.get("requested") or 0) for j in jobs.values() if j.get("status") not in ("failed", "cancelled"))
    plan = []
    for v in EXPORT_VERTICALS:
        for g in EXPORT_GROUPS:
            f = job_filters(v, g)
            key = job_key(v, g, f)
            if key in jobs and jobs[key].get("status") not in ("failed", "cancelled"):
                plan.append((key, v, g, f, jobs[key]["requested"], "reuse"))
                continue
            limit = max(0, min(counts[(v, g)], args.budget - spent, left if left is not None else 10**9))
            plan.append((key, v, g, f, limit, "new" if limit else "skip"))
            spent += limit
    print(f"plan (budget {args.budget}, committed {spent}):")
    for key, v, g, _f, limit, st in plan:
        print(f"  {key:28s} rows={limit:5d} {st}")
    if args.plan_only:
        return
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for key, v, g, f, limit, st in plan:
        if st == "new":
            body = {"name": f"jt {v} {g} {TODAY}", "filters": f, "limit": limit, "columns": EXPORT_COLUMNS,
                    "caps": {"emails": 3}}
            data = lo.req("POST", "/v1/exports", body=body)["data"]
            jobs[key] = {"attempts": int((jobs.get(key) or {}).get("attempts", 0)) + 1,"id": data["id"], "requested": limit, "status": data.get("status"), "vertical": v,
                         "group": g, "filters": f, "date": TODAY}
            jsave(LEDGER, ledger)
            print(f"queued {key} id={data['id']} limit={limit}")
    while True:
        pending = [k for k, j in jobs.items() if j.get("status") not in ("downloaded", "failed", "cancelled")]
        if not pending:
            break
        for k in pending:
            j = jobs[k]
            d = lo.req("GET", f"/v1/exports/{j['id']}")["data"]
            j.update(status=d.get("status"), rows=d.get("rows"), billed=d.get("billed"), error=d.get("error"))
            if d.get("status") == "done":
                r = lo.req("GET", f"/v1/exports/{j['id']}/download", raw=True, timeout=180)
                if r.status_code == 200 and r.text:
                    out = RAW_DIR / (k.replace(":", "__") + ".csv")
                    out.write_text(r.text, encoding="utf-8")
                    j.update(status="downloaded", file=str(out.relative_to(ROOT)))
                    print(f"downloaded {k}: rows={d.get('rows')} billed={d.get('billed')}")
            jsave(LEDGER, ledger)
        if any(jobs[k].get("status") not in ("downloaded", "failed", "cancelled") for k in pending):
            time.sleep(10)
    build_outputs(ledger)


def build_outputs(ledger: dict[str, Any]) -> None:
    drop_dom, drop_names = load_drops()
    stats: dict[str, dict[str, int]] = {}
    seen_email: set[str] = set()
    companies: dict[str, dict[str, Any]] = {}
    by_v: dict[str, list[dict[str, Any]]] = {v: [] for v in EXPORT_VERTICALS}
    for v in EXPORT_VERTICALS:  # medtech first: an overlapping company stays in medtech
        st = stats[v] = {"exported": 0, "no_verified_email": 0, "dropped": 0, "dup_email": 0, "overlap": 0, "cap2": 0}
        pool: dict[str, list[tuple[int, dict[str, Any]]]] = {}
        for j in ledger["jobs"].values():
            if j.get("vertical") != v or j.get("status") != "downloaded":
                continue
            with open(ROOT / j["file"], newline="", encoding="utf-8") as fh:
                for r in csv.DictReader(fh):
                    st["exported"] += 1
                    email = pick_verified(r)
                    if not email:
                        st["no_verified_email"] += 1
                        continue
                    dom = norm_domain(r.get("current_company_domain") or r.get("current_company_website"))
                    name = r.get("current_company_name") or ""
                    if (dom and dom in drop_dom) or norm_name(name) in drop_names:
                        st["dropped"] += 1
                        continue
                    if email in seen_email:
                        st["dup_email"] += 1
                        continue
                    ckey = dom or "name:" + norm_name(name)
                    if v != "medtech" and ckey in companies and companies[ckey]["vertical"] == "medtech":
                        st["overlap"] += 1
                        continue
                    seen_email.add(email)
                    row = {"first_name": (r.get("profile_first_name") or "").strip(),
                           "last_name": (r.get("profile_last_name") or "").strip(),
                           "title": (r.get("current_job_title") or "").strip(), "email": email, "company": name.strip(),
                           "domain": dom, "website": (r.get("current_company_website") or "").strip(),
                           "city": r.get("city", ""), "state": r.get("state", ""),
                           "employees": r.get("current_company_employees", ""),
                           "linkedin": r.get("profile_url", ""), "vertical": v}
                    pool.setdefault(ckey, []).append((contact_rank(row["title"]), row))
        for ckey, lst in pool.items():
            lst.sort(key=lambda x: (x[0], x[1]["email"]))
            st["cap2"] += max(0, len(lst) - 2)
            for _rk, row in lst[:2]:
                by_v[v].append(row)
                companies.setdefault(ckey, dict(row, contacts=0))["contacts"] += 1
        st["after_cap"] = len(by_v[v])
        st["companies"] = len({r["domain"] or r["company"] for r in by_v[v]})
    LEADS_DIR.mkdir(parents=True, exist_ok=True)
    for v, rows in by_v.items():
        with open(LEADS_DIR / f"jt_{v}.csv", "w", newline="", encoding="utf-8") as fh:
            w = csv.DictWriter(fh, fieldnames=OUT_COLS)
            w.writeheader()
            w.writerows(rows)
    with open(LEADS_DIR / "jt_companies.csv", "w", newline="", encoding="utf-8") as fh:
        cols = ["company", "domain", "website", "city", "state", "employees", "vertical", "contacts"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for c in companies.values():
            w.writerow({k: c[k] for k in cols})
    print("outputs:", json.dumps(stats))


def sample_rows(n: int = 15) -> None:
    rng = random.Random(7)
    for v in EXPORT_VERTICALS:
        rows = list(csv.DictReader(open(LEADS_DIR / f"jt_{v}.csv", encoding="utf-8")))
        print(f"--- {v} ({len(rows)} rows)")
        for r in rng.sample(rows, min(n, len(rows))):
            print(f"{r['title'][:40]} | {r['company']} | {r['domain']} | {r['state']}")


def main() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "export":
        ep = argparse.ArgumentParser(prog="jt_leadocean_count.py export")
        ep.add_argument("cmd")
        ep.add_argument("--budget", type=int, default=6000, help="hard cap on total exported rows")
        ep.add_argument("--plan-only", action="store_true")
        ep.add_argument("--rebuild", action="store_true", help="only rebuild CSVs from downloaded raw files")
        ep.add_argument("--sample", type=int, default=0, help="print N random rows per vertical")
        ea = ep.parse_args()
        logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
        if ea.sample:
            sample_rows(ea.sample)
        elif ea.rebuild:
            build_outputs(jload(LEDGER, {"jobs": {}}))
        else:
            run_export(ea)
        return
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[3])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--refresh", action="store_true", help="re-count cached cells")
    ap.add_argument("--only", default="", help="comma list of vertical keys")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    only = {s for s in args.only.split(",") if s}
    bad = only - set(VERTICALS)
    if bad:
        raise SystemExit(f"unknown vertical(s) {sorted(bad)}; choose from {sorted(VERTICALS)}")

    lo = LeadOcean()
    doc = jload(args.out, {})
    cells: dict[str, Any] = {} if args.refresh and not only else doc.get("cells", {})
    for vertical in VERTICALS:
        if only and vertical not in only:
            continue
        for geo in GEOS:
            for group in TITLE_GROUPS:
                key = f"{vertical}:{geo}:{group}"
                done = key in cells and not cells[key].get("error") and all(
                    (cells[key].get(p) or {}).get("total") is not None for p in POOLS)
                if done and not args.refresh:
                    continue
                row: dict[str, Any] = {}
                try:
                    for pool in POOLS:
                        row[pool] = count_cell(lo, cell_filters(vertical, geo, group, pool))
                except RuntimeError as exc:
                    row = {"error": str(exc)[:300]}
                cells[key] = row
                doc["cells"] = cells
                jsave(args.out, doc)
                v = row.get("verified") or {}
                print(f"{key:32s} any={row.get('any', {}).get('total')} verified={v.get('total')} "
                      f"cos={v.get('companies')} v+u={row.get('verified_untested', {}).get('total')} "
                      f"unsupported={v.get('unsupported')}", flush=True)

    acct = account_allowance(lo)
    cap = acct.get("export_rows_day_limit") or 5000
    totals: dict[str, dict[str, dict[str, Any]]] = {}
    for geo in GEOS:
        totals[geo] = {}
        for pool in POOLS:
            ppl = cos = 0
            for key, c in cells.items():
                if key.split(":")[1] != geo or c.get("error"):
                    continue
                ppl += int((c.get(pool) or {}).get("total") or 0)
                cos += int((c.get(pool) or {}).get("companies") or 0)
            totals[geo][pool] = {"people": ppl, "companies": cos, "export_days": round(ppl / int(cap), 2)}
    doc.update({
        "date": TODAY, "cells": cells, "totals": totals, "account": acct,
        "config": {"size": SIZE, "verticals": VERTICALS, "geos": {k: v["label"] for k, v in GEOS.items()},
                   "sd_cities": SD_CITIES, "title_groups": TITLE_GROUPS, "pools": POOLS},
        "cost_model": "count calls free (meta.credits=0); export bills 1 record per row written; "
                      "rows/export = people in the cell's pool; exports dedupe only within themselves",
    })
    jsave(args.out, doc)
    md = args.out.with_suffix(".md")
    write_md(doc, md)
    print(f"wrote {args.out} and {md}")


if __name__ == "__main__":
    main()
