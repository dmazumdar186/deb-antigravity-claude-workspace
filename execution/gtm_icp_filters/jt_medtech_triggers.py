"""
jt_medtech_triggers.py
description: FDA-first cold-email triggers for US medtech companies. Pulls every openFDA 510(k) decision since
             --since for US applicants, matches applicants to a companies CSV, checks each matched company's own
             site for ONE hard, checkable fact (site search for the device returns nothing, device absent from
             homepage, footer copyright year, CMS generator version, missing viewport meta), then re-derives every
             claim in an independent blind verifier pass. Only rows where finder and verifier agree ship.
inputs:  --companies CSV (columns company,domain,website[,city,state,vertical]); --vertical filter (default medtech
         when the column exists); --since YYYY-MM-DD (default 2026-08-01)
outputs: .tmp/les/triggers/medtech_triggers.csv (verified rows only), medtech_triggers_all.csv (every match +
         verifier verdict), fda_510k_<since>.json (raw pull), cache/*.json, shots/*.png
usage:   python3 execution/gtm_icp_filters/jt_medtech_triggers.py --companies .tmp/les/leads/jt_companies.csv
         python3 execution/gtm_icp_filters/jt_medtech_triggers.py --companies X.csv --check   # offline, caches only
         --controls  : assert the 4 positive controls are caught (exit 1 if not)
Directive: directives/gtm_icp_filters/jt_medtech_triggers.md
Spend: openFDA + company sites are free. Jev (paid, ~$0.00002/call) only for ambiguous name matches, capped by
       --max-jev (default 40), every call logged to .tmp/jev_ledger.jsonl. --no-jev disables it.
"""

from __future__ import annotations

import argparse, csv, datetime as dt, json, os, re, sys, time, urllib.parse
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
OUT = ROOT / ".tmp/les/triggers"
CACHE, SHOTS = OUT / "cache", OUT / "shots"
FDA = "https://api.fda.gov/device/510k.json"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
# Positive controls live in a gitignored fixture (repo is public): {"K_NUMBER": "label", ...}
SUFFIX = {
    "inc",
    "llc",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "lp",
    "llp",
    "plc",
    "the",
    "incorporated",
    "usa",
    "us",
    "na",
    "holdings",
    "group",
    "dba",
    "pc",
}
GENERIC = {
    "test",
    "tests",
    "cassette",
    "device",
    "devices",
    "system",
    "systems",
    "kit",
    "kits",
    "set",
    "assay",
    "large",
    "small",
    "screw",
    "screws",
    "plate",
    "plates",
    "the",
    "for",
    "and",
    "with",
    "of",
    "advanced",
    "surgical",
    "medical",
    "strip",
    "matrix",
    "disk",
    "model",
    "series",
    "family",
    "instrument",
    "instruments",
}
# Ordered by strength of the observation (first verified one wins).
FACT_ORDER = [
    "search_absent",
    "device_absent_homepage",
    "copyright_year",
    "generator",
    "viewport_missing",
]
MONTHS = "January February March April May June July August September October November December".split()


# ---------------------------------------------------------------- openFDA
def fda_get(params: dict, tries: int = 4) -> dict:
    for i in range(tries):
        r = requests.get(FDA, params=params, timeout=60)
        if r.status_code == 404:  # openFDA: no matches
            return {"meta": {"results": {"total": 0}}, "results": []}
        if r.status_code in (429, 500, 502, 503) and i < tries - 1:
            time.sleep(2 * (i + 1))
            continue
        r.raise_for_status()
        return r.json()
    raise RuntimeError("openFDA unreachable")


def pull_fda(since: str, refresh: bool, offline: bool) -> list[dict]:
    path = OUT / f"fda_510k_{since}.json"
    if path.exists() and not refresh:
        return json.loads(path.read_text())["results"]
    if offline:
        sys.exit(f"--check: no cached pull at {path}")
    end = dt.date.today().strftime("%Y%m%d")
    q = f"decision_date:[{since.replace('-', '')} TO {end}] AND country_code:US"
    rows, skip, total = [], 0, None
    while (
        total is None or skip < total
    ):  # openFDA caps skip at 25000; 510(k) windows are far below
        d = fda_get({"search": q, "limit": 1000, "skip": skip})
        total = d["meta"]["results"]["total"]
        batch = d.get("results", [])
        for b in batch:
            b.pop("openfda", None)
        rows += batch
        skip += len(batch)
        if not batch:
            break
    if len(rows) != total:
        sys.exit(f"pagination mismatch: got {len(rows)} of total {total}")
    rows = list({r["k_number"]: r for r in rows}.values())
    OUT.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "query": q,
                "total": total,
                "pulled_at": dt.datetime.now().isoformat(),
                "results": rows,
            }
        )
    )
    return rows


# ---------------------------------------------------------------- naming
def norm_tokens(name: str) -> list[str]:
    s = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower().replace("&", " and "))
    return [t for t in s.split() if t not in SUFFIX]


def domain_root(d: str) -> str:
    d = re.sub(r"^https?://", "", (d or "").lower()).split("/")[0]
    d = re.sub(r"^www\.", "", d)
    return d.split(".")[0] if d else ""


def clean_device(name: str) -> str:
    """First listed variant, catalog codes and size suffixes dropped, marks removed, readable case."""
    s = name.split(";")[0]
    s = re.sub(r"\s*\([A-Z0-9][A-Z0-9\-x]*\)\s*$", "", s)  # trailing (CG-01AA)
    s = re.sub(
        r",\s*[\d.]+\s*(cc|ml|mm|cm)\b.*$", "", s, flags=re.I
    )  # , 1cc / , 125x25x2mm
    s = re.sub(r"[®™©]", "", s).strip(" ,")
    if (
        s.isupper() and len(s) > 4
    ):  # ALL-CAPS FDA record -> title case, keep short codes upper
        s = " ".join(
            w if (len(w) <= 3 or any(c.isdigit() for c in w)) else w.capitalize()
            for w in s.split()
        )
    return re.sub(r"\s+", " ", s)


def search_queries(device: str) -> list[str]:
    words = device.split()
    dist = [w for w in words if w.lower().strip(",.") not in GENERIC]
    qs = [device]
    if dist and len(dist) < len(words):
        qs.append(" ".join(dist))
    if len(dist) >= 3:
        qs.append(" ".join(dist[-2:]))
    return list(dict.fromkeys(q for q in qs if len(q) >= 4))


def trigger_line(rec: dict) -> str:
    d = dt.date.fromisoformat(rec["decision_date"])
    return f"the {MONTHS[d.month - 1]} {d.day} FDA clearance for the {clean_device(rec['device_name'])}"


# ---------------------------------------------------------------- matching
def match_companies(
    companies: list[dict], fda: list[dict], use_jev: bool, max_jev: int
) -> list[dict]:
    by_app: dict[str, list[dict]] = {}
    for r in fda:
        by_app.setdefault(r["applicant"], []).append(r)
    apps = [(a, set(norm_tokens(a)), "".join(norm_tokens(a))) for a in by_app]
    out, ambiguous = [], []
    for c in companies:
        ct, croot = set(norm_tokens(c["company"])), domain_root(
            c.get("domain") or c.get("website")
        )
        if not ct:
            continue
        best = []
        for a, at, acompact in apps:
            if not at:
                continue
            j = len(ct & at) / len(ct | at)
            exact = ct == at or (croot and acompact == croot)
            if exact or j >= 0.5:
                best.append((1.0 if exact else j, a))
        best.sort(reverse=True)
        if not best:
            continue
        score, a = best[0]
        rec0 = by_app[a][0]
        city_ok = None
        if c.get("state"):
            city_ok = c["state"].strip().upper() == (rec0.get("state") or "").upper()
        if (
            score >= 0.8
            and city_ok is not False
            and (len(best) == 1 or best[1][0] < score)
        ):
            out += [
                dict(company=c, rec=r, how=f"name score {score:.2f}") for r in by_app[a]
            ]
        else:
            ambiguous.append((c, [x[1] for x in best[:5]]))
    if ambiguous and use_jev:
        from execution.modules import jev_client as jev

        if not jev.available():
            print(
                f"jev unavailable: {len(ambiguous)} ambiguous matches dropped (fail closed)"
            )
        else:
            for c, cands in ambiguous[:max_jev]:
                opts = {
                    f"a{i}": f"{a} ({by_app[a][0].get('city')}, {by_app[a][0].get('state')})"
                    for i, a in enumerate(cands)
                }
                opts["none"] = "none of these is the same legal company"
                r = jev.decide(
                    {
                        "company": c["company"],
                        "domain": c.get("domain"),
                        "city": c.get("city"),
                        "state": c.get("state"),
                    },
                    {
                        "m": jev.choice(
                            "Which FDA 510(k) applicant is the same company?", opts
                        )
                    },
                )
                jev.append_ledger(
                    {
                        "script": "jt_medtech_triggers",
                        "company": c["company"],
                        "cost": r.cost_usd,
                    }
                )
                pick = r.choice("m") if not r.error else None
                if pick and pick != "none" and (r.confidence("m") or 0) >= 0.7:
                    a = cands[int(pick[1:])]
                    out += [
                        dict(company=c, rec=x, how=f"jev {r.confidence('m'):.2f}")
                        for x in by_app[a]
                    ]
    elif ambiguous:
        print(f"{len(ambiguous)} ambiguous matches skipped (--no-jev)")
    return out


# ---------------------------------------------------------------- site checks (shared primitives)
def site_url(c: dict) -> str:
    u = (c.get("website") or c.get("domain") or "").strip()
    return u if u.startswith("http") else f"https://{u}"


def page_markers(html: str) -> dict:
    years = [
        int(y)
        for y in re.findall(
            r"(?:©|&copy;|copyright)\s*(?:[^<]{0,40}?)(20\d\d)(?!\d)", html, re.I
        )
    ]
    # take the max year in the copyright line (ranges like 2010-2019 -> 2019)
    m = re.search(r"(?:©|&copy;|copyright)[^<]{0,60}", html, re.I)
    if m:
        years += [int(y) for y in re.findall(r"20\d\d", m.group(0))]
    gen = re.search(
        r'<meta[^>]+name=["\']generator["\'][^>]*content=["\']([^"\']+)', html, re.I
    ) or re.search(
        r'<meta[^>]+content=["\']([^"\']+)["\'][^>]*name=["\']generator', html, re.I
    )
    vp = re.search(r'<meta[^>]+name=["\']viewport["\']', html, re.I)
    return {
        "copyright_year": max(years) if years else None,
        "generator": gen.group(1).strip() if gen else None,
        "viewport": bool(vp),
    }


SEARCH_PATTERNS = [
    "/?s={q}",
    "/search?q={q}",
    "/search?query={q}",
    "/search/?q={q}",
    "/catalogsearch/result/?q={q}",
]
NONSENSE = "qzxwvjkplm"


def pw_fetch(jobs: list[dict]) -> list[dict]:
    """Run Node Playwright (the installed binding) via jt_pw_fetch.js; one Chromium per call."""
    import subprocess

    try:
        cp = subprocess.run(["node", str(Path(__file__).with_name("jt_pw_fetch.js"))], input=json.dumps({"jobs": jobs}),
                            capture_output=True, text=True, encoding="utf-8", errors="replace",
                            timeout=90 * len(jobs) + 30)
    except subprocess.TimeoutExpired:
        return [{"url": j["url"], "status": 0, "text": "", "error": "timeout"} for j in jobs]
    if cp.returncode != 0:
        return [{"url": j["url"], "status": 0, "text": "", "error": cp.stderr[:200]} for j in jobs]
    return json.loads(cp.stdout)


def _text(url: str) -> tuple[int, str]:
    r = pw_fetch([{"url": url, "mode": "text"}])[0]
    return r.get("status") or 0, r.get("text") or ""


def _empty(t: str, t_non: str, q: str) -> bool:
    """Search 'returns nothing' = page text equals the nonsense-query page once both queries are blanked."""
    a = re.sub(re.escape(q), "§", t, flags=re.I)
    b = re.sub(NONSENSE, "§", t_non, flags=re.I)
    return abs(len(a) - len(b)) < 40 and a.count("§") == b.count("§")


def find_search(base: str) -> tuple[str, str] | None:
    """A search pattern counts only if a nonsense query returns 200 and echoes the query (a real search ran)."""
    for pat in SEARCH_PATTERNS:
        st, t = _text(base.rstrip("/") + pat.format(q=NONSENSE))
        if st == 200 and NONSENSE in t.lower():
            return pat, t
    return None


def check_site(c: dict, device: str, tag: str, shots: bool) -> dict:
    base = site_url(c)
    res: dict = {"base": base, "facts": {}}
    job = {"url": base, "mode": "full"}
    if shots:
        SHOTS.mkdir(parents=True, exist_ok=True)
        job.update(desk_png=str(SHOTS / f"{tag}_desk.png"), mob_png=str(SHOTS / f"{tag}_mob.png"))
    r = pw_fetch([job])[0]
    if r.get("error") or not r.get("html"):
        res["error"] = r.get("error") or "empty page"
        return res
    res.update(final_url=r["final_url"], status=r["status"], desk_png=r.get("desk_png"), mob_png=r.get("mob_png"))
    mk = page_markers(r["html"])
    if mk["copyright_year"]:
        res["facts"]["copyright_year"] = mk["copyright_year"]
    if mk["generator"]:
        res["facts"]["generator"] = mk["generator"]
    res["facts"]["viewport"] = mk["viewport"]
    res["facts"]["mobile_viewport"] = r.get("mobile_viewport")
    qs = search_queries(device)
    res["queries"] = qs
    res["facts"]["device_on_homepage"] = any(q.lower() in (r.get("text") or "").lower() for q in qs)
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(r["final_url"]))
    found = find_search(origin)
    res["search_pattern"] = found[0] if found else None
    if found:
        for q in reversed(qs):  # most distinctive (shortest) first: the strongest "returns nothing" claim
            u = origin + found[0].format(q=urllib.parse.quote_plus(q))
            st, t = _text(u)
            if st == 200 and q.lower() in t.lower() and _empty(t, found[1], q):
                res["facts"]["search_absent"] = {"query": q, "url": u}
                break
    return res


def pick_fact(site: dict, device: str) -> tuple[str, str, str] | None:
    f, year = site.get("facts", {}), dt.date.today().year
    dom = urllib.parse.urlparse(site.get("final_url") or site["base"]).netloc.replace(
        "www.", ""
    )
    for t in FACT_ORDER:
        if t == "search_absent" and f.get("search_absent"):
            s = f["search_absent"]
            return (
                t,
                f'a search on {dom} for "{s["query"]}" returns no results',
                s["url"],
            )
        if t == "device_absent_homepage" and f.get("device_on_homepage") is False:
            return (
                t,
                f"the {dom} homepage does not mention the {device}",
                site.get("final_url") or site["base"],
            )
        if (
            t == "copyright_year"
            and f.get("copyright_year")
            and f["copyright_year"] <= year - 2
        ):
            return (
                t,
                f'the {dom} footer still reads © {f["copyright_year"]}',
                site.get("final_url") or site["base"],
            )
        if t == "generator" and f.get("generator") and re.search(r"\d", f["generator"]):
            return (
                t,
                f'the {dom} homepage source declares generator "{f["generator"]}"',
                site.get("final_url") or site["base"],
            )
        if (
            t == "viewport_missing"
            and f.get("viewport") is False
            and f.get("mobile_viewport") is not True
        ):
            return (
                t,
                f"the {dom} homepage has no viewport meta tag (no mobile layout)",
                site.get("final_url") or site["base"],
            )
    return None


# ---------------------------------------------------------------- blind verifier
def verify(company: str, domain: str, k: str, claim_type: str, claim: dict
) -> tuple[bool, str]:
    """Independent re-derivation. Sees only company, domain, K number and the claim; re-queries openFDA by K
    number and re-fetches the page with plain HTTP (search claims re-run in a fresh browser context).
    """
    d = fda_get({"search": f"k_number:{k}"}).get("results", [])
    if len(d) != 1:
        return False, "K number not found in openFDA"
    r = d[0]
    if r["decision_date"] != claim["decision_date"]:
        return False, f"date mismatch {r['decision_date']}"
    if clean_device(r["device_name"]) != claim["device"]:
        return False, "device name mismatch"
    if r.get("country_code") != "US":
        return False, "not a US applicant"
    if set(norm_tokens(r["applicant"])) & set(
        norm_tokens(company)
    ) == set() and "".join(norm_tokens(r["applicant"])) != domain_root(domain):
        return (
            False,
            f"applicant {r['applicant']} does not share a name token with {company}",
        )
    url = claim["url"]
    if claim_type == "search_absent":
        q = claim["query"]
        # verifier's own nonsense baseline on the same URL; also requires the query echoed (search really ran)
        st, t = _text(url)
        st2, t_non = _text(url.replace(urllib.parse.quote_plus(q), NONSENSE))
        if st != 200 or st2 != 200:
            return False, f"search page status {st}/{st2}"
        ok = q.lower() in t.lower() and _empty(t, t_non, q)
        return ok, ("search empty re-confirmed" if ok else "search returned content or no echo")
    try:
        h = requests.get(url, headers={"User-Agent": UA}, timeout=30).text
    except Exception as exc:
        return False, f"refetch failed {type(exc).__name__}"
    mk = page_markers(h)
    if claim_type == "copyright_year":
        return (
            mk["copyright_year"] == claim["value"],
            f"copyright {mk['copyright_year']}",
        )
    if claim_type == "generator":
        return mk["generator"] == claim["value"], f"generator {mk['generator']}"
    if claim_type == "viewport_missing":
        return not mk["viewport"], f"viewport {mk['viewport']}"
    if claim_type == "device_absent_homepage":
        # static HTML text and the rendered text must both lack the device name
        txt = re.sub(r"<[^>]+>", " ", h).lower()
        ok = claim["device"].lower() not in txt
        return ok, (
            "device absent in static HTML" if ok else "device found in static HTML"
        )
    return False, "unknown claim type"


# ---------------------------------------------------------------- main
COLS = [
    "company",
    "domain",
    "k_number",
    "device_name",
    "decision_date",
    "trigger_line",
    "site_fact",
    "site_fact_type",
    "evidence_urls",
    "verified",
]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--companies", required=True)
    ap.add_argument("--vertical", default="medtech")
    ap.add_argument("--since", default="2026-08-01")
    ap.add_argument("--out", default=str(OUT / "medtech_triggers.csv"))
    ap.add_argument(
        "--refresh", action="store_true", help="re-pull openFDA and redo site checks"
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="offline: caches only, no network, no spend",
    )
    ap.add_argument("--no-jev", action="store_true")
    ap.add_argument("--max-jev", type=int, default=40)
    ap.add_argument("--no-shots", action="store_true")
    ap.add_argument("--controls", default="", help="JSON fixture {k_number: label}; exit 1 unless all are verified")
    a = ap.parse_args()
    CACHE.mkdir(parents=True, exist_ok=True)

    fda = pull_fda(a.since, a.refresh, a.check)
    with open(a.companies, newline="", encoding="utf-8") as fh:
        comps = [r for r in csv.DictReader(fh)]
    if comps and "vertical" in comps[0] and a.vertical:
        comps = [
            r for r in comps if (r.get("vertical") or "").strip().lower() == a.vertical
        ]
    comps = list(
        {
            (r.get("domain") or r["company"]).lower(): r
            for r in comps
            if r.get("company")
        }.values()
    )
    matches = match_companies(
        comps, fda, use_jev=not (a.no_jev or a.check), max_jev=a.max_jev
    )
    print(
        f"510k_pulled={len(fda)} since={a.since} companies={len(comps)} matches={len(matches)} "
        f"matched_companies={len({m['company']['company'] for m in matches})}"
    )

    rows = []
    if True:
        for m in matches:
            c, rec = m["company"], m["rec"]
            dom = domain_root(c.get("domain") or c.get("website")) or "x"
            key = (
                CACHE
                / f"{rec['k_number']}_{re.sub(r'[^a-z0-9.]', '', (c.get('domain') or dom).lower())}.json"
            )
            if key.exists() and not a.refresh:
                rows.append(json.loads(key.read_text()))
                continue
            if a.check:
                print(
                    f"--check: no cache for {rec['k_number']} {c['company']} (would fetch)"
                )
                continue
            device = clean_device(rec["device_name"])
            site = check_site(c, device, f"{rec['k_number']}_{dom}", not a.no_shots
            )
            fact = pick_fact(site, device) if "error" not in site else None
            row = {
                "company": c["company"],
                "domain": c.get("domain") or "",
                "k_number": rec["k_number"],
                "device_name": device,
                "decision_date": rec["decision_date"],
                "trigger_line": trigger_line(rec),
                "fda_applicant": rec["applicant"],
                "fda_city_state": f"{rec.get('city')}, {rec.get('state')}",
                "match_how": m["how"],
                "site": site,
                "site_fact": "",
                "site_fact_type": "",
                "evidence_urls": f"https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={rec['k_number']}",
                "verified": False,
                "verifier_notes": "",
            }
            if fact:
                ftype, text, url = fact
                row.update(
                    site_fact=text,
                    site_fact_type=ftype,
                    evidence_urls=row["evidence_urls"] + " " + url,
                )
                f = site["facts"]
                claim = {
                    "decision_date": rec["decision_date"],
                    "device": device,
                    "url": url,
                    "query": (f.get("search_absent") or {}).get("query"),
                    "value": (
                        f.get("copyright_year")
                        if ftype == "copyright_year"
                        else f.get("generator")
                    ),
                }
                ok, note = verify(c["company"],
                    c.get("domain") or "",
                    rec["k_number"],
                    ftype,
                    claim,
                )
                row.update(verified=ok, verifier_notes=note)
            else:
                row["verifier_notes"] = site.get("error") or "no hard site fact found"
            key.write_text(json.dumps(row, default=str))
            rows.append(row)
    # one line per company: newest verified clearance
    best: dict[str, dict] = {}
    for r in sorted(rows, key=lambda r: r["decision_date"], reverse=True):
        if r["verified"] and r["company"] not in best:
            best[r["company"]] = r
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    for path, data in (
        (a.out, list(best.values())),
        (a.out.replace(".csv", "_all.csv"), rows),
    ):
        with open(path, "w", newline="", encoding="utf-8") as fh:
            w = csv.writer(fh)
            w.writerow(
                COLS
                + (
                    ["verifier_notes", "fda_applicant", "match_how"]
                    if path != a.out
                    else []
                )
            )
            for r in data:
                w.writerow(
                    [r.get(k) for k in COLS]
                    + (
                        [
                            r.get("verifier_notes"),
                            r.get("fda_applicant"),
                            r.get("match_how"),
                        ]
                        if path != a.out
                        else []
                    )
                )
    print(
        f"rows={len(rows)} verified_rows={sum(r['verified'] for r in rows)} companies_verified={len(best)} -> {a.out}"
    )
    if a.controls:
        ctl = json.loads(Path(a.controls).read_text())
        got = {r["k_number"] for r in rows if r["verified"]}
        miss = [f"{k} {n}" for k, n in ctl.items() if k not in got]
        print(f"controls: {len(ctl) - len(miss)}/{len(ctl)} verified" + (f"; MISSING {miss}" if miss else ""))
        return 1 if miss else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
