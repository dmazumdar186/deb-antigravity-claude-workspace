#!/usr/bin/env python3
"""
casualize_and_city_split.py
description: Finalize a scraped lead CSV for cold-email launch: dedupe by email, add `Short Company Name`
             (deterministic legal-suffix stripping) and `Personalized Name` (one friendly brand word/phrase,
             LLM via OpenRouter, guarded so every output word comes from the original name — no invention),
             then split into one CSV per person `City`. Rows whose `Company City`/`Company State` lie outside
             that city's metro go to a separate `{city}__hq_outside_metro.csv` so no city file mixes metros.
inputs:  --input CSV (Apollo-style columns: Email, Company Name, City, State, Company City, Company State);
         --outdir; --model (default anthropic/claude-sonnet-5.5, bulk tier); --no-llm (short name only);
         env OPENROUTER_API_KEY (or OPENROUTER_API_TOEKN cloud alias)
outputs: {outdir}/{city_slug}.csv, {outdir}/{city_slug}__hq_outside_metro.csv, {outdir}/summary.json
usage:   python3 execution/enrichment/casualize_and_city_split.py --input .tmp/x/mx_verified.csv --outdir .tmp/x/out
"""
import argparse
import csv
import json
import os
import re
import sys

from dotenv import load_dotenv
from collections import Counter, OrderedDict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
load_dotenv(ROOT / ".env")
sys.path.insert(0, str(ROOT))

# Legal / corporate suffixes and trailing generic descriptors. Order matters: stripped repeatedly from the end.
SUFFIX_WORDS = [
    "llc", "l.l.c.", "l.l.c", "inc", "inc.", "incorporated", "corp", "corp.", "corporation", "co", "co.",
    "ltd", "ltd.", "limited", "plc", "llp", "l.l.p.", "lp", "l.p.", "pllc", "pc", "p.c.", "pvt", "pvt.",
    "pvt ltd", "private limited", "gmbh", "ag", "sa", "s.a.", "bv", "b.v.", "pty", "pty.", "pty ltd",
    "company", "companies", "group", "holdings", "international", "intl", "intl.", "technologies",
    "technology", "enterprises", "worldwide", "and", "&",
]
# Words that are never stripped if they would leave the name empty.
_SUFFIX_RE = re.compile(
    r"[\s,\-–—|&/]*\b(" + "|".join(re.escape(w) for w in sorted(SUFFIX_WORDS, key=len, reverse=True)) + r")\.?\s*$",
    re.IGNORECASE,
)
_PAREN_RE = re.compile(r"\s*[\(\[][^\)\]]*[\)\]]\s*")
_SEP_RE = re.compile(r"\s+[|/]\s+|\s+[-–—]\s+")


def short_company_name(name: str) -> str:
    """Deterministic: drop parentheticals, take the part before ' | ' / ' - ', strip legal + generic suffixes."""
    s = _PAREN_RE.sub(" ", (name or "").strip())
    s = _SEP_RE.split(s)[0].strip() if s else s
    s = re.sub(r"^(the)\s+", "", s, flags=re.IGNORECASE)
    prev = None
    while s and s != prev:
        prev = s
        cand = _SUFFIX_RE.sub("", s).strip(" ,.-–—|&/")
        if cand and cand.lower() != s.lower() and len(cand) >= 2:
            s = cand
        else:
            break
    s = s.strip(" ,.-–—|&/")
    return s or (name or "").strip()


SYSTEM = (
    "You create short, friendly brand nicknames for cold-email personalization. For each company, return the "
    "shortest natural way a person would refer to it in conversation: usually one or two words, e.g. "
    "'Grayson Healthcare Recruitment and Staffing' -> 'Grayson', 'Keller Williams Realty Inc' -> 'Keller Williams', "
    "'fullcircleHR' -> 'fullcircle'. Rules: use ONLY words or tokens that appear in the given name (you may drop words, "
    "never add, translate or reorder them); keep original capitalization of kept tokens; drop legal suffixes and "
    "generic words like Staffing, Recruiting, Group, Solutions, Consulting, Partners, Search, Talent, HR; keep an "
    "acronym or coined word as-is; if the name is only generic words (e.g. 'Staffing Solutions'), return 'you guys'. "
    "Respond with a JSON object mapping id -> nickname and nothing else."
)


def _tokens(s: str) -> set:
    return set(re.findall(r"[a-z0-9]+", (s or "").lower()))


def guard(original: str, nickname: str, fallback: str) -> tuple[str, bool]:
    """Accept the LLM nickname only if every token of it appears in the original name (or it is 'you guys')."""
    nickname = (nickname or "").strip().strip("\"'")
    if not nickname:
        return fallback, False
    if nickname.lower() == "you guys":
        return nickname, True
    orig = _tokens(original)
    toks = _tokens(nickname)
    if toks and toks <= orig and len(nickname) <= len(original) + 2:
        return nickname, True
    # allow concatenated coined tokens, e.g. 'fullcircle' from 'fullcirclehr'
    if toks and all(any(t in o for o in orig) for t in toks):
        return nickname, True
    return fallback, False


def llm_batch(items: list[tuple[str, str]], model: str) -> dict[str, str]:
    from execution.modules import llm_client

    payload = json.dumps({i: n for i, n in items}, ensure_ascii=False)
    out = llm_client.chat_completion(
        SYSTEM, payload, model=model, max_tokens=4000, effort=llm_client.default_effort(model)
    )
    out = out.strip()
    out = re.sub(r"^```(?:json)?\s*|\s*```$", "", out)
    try:
        data = json.loads(out)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", out, re.S)
        data = json.loads(m.group(0)) if m else {}
    return {str(k): str(v) for k, v in data.items()}


# Metro membership: cities whose HQ counts as "same market" as the person City. Lower-case.
METROS = {
    "san francisco": {"state": "california", "cities": {
        "san francisco", "oakland", "san jose", "palo alto", "sunnyvale", "pleasanton", "dublin", "walnut creek",
        "berkeley", "santa clara", "redwood city", "fremont", "san mateo", "novato", "mountain view", "livermore",
        "mill valley", "los altos", "san ramon", "cupertino", "menlo park", "san rafael", "kentfield", "emeryville",
        "alameda", "hayward", "burlingame", "south san francisco", "daly city", "san bruno", "millbrae", "foster city",
        "belmont", "san carlos", "menlo park", "atherton", "los gatos", "campbell", "saratoga", "milpitas",
        "santa cruz", "concord", "danville", "lafayette", "orinda", "moraga", "richmond", "el cerrito", "albany",
        "sausalito", "tiburon", "larkspur", "corte madera", "petaluma", "santa rosa", "napa", "sonoma", "vallejo",
        "benicia", "martinez", "pleasant hill", "antioch", "brentwood", "tracy", "union city", "newark",
        "san leandro", "castro valley", "half moon bay", "pacifica", "woodside", "portola valley", "east palo alto",
        "stanford", "morgan hill", "gilroy", "san anselmo", "fairfax", "healdsburg", "sebastopol", "rohnert park",
        "fairfield", "vacaville", "scotts valley", "capitola", "aptos", "los altos hills", "hillsborough",
        "sf", "bay area", "san francisco bay area", "west menlo park", "belvedere tiburon", "discovery bay",
    }},
    "seattle": {"state": "washington", "cities": {
        "seattle", "bellevue", "redmond", "kirkland", "issaquah", "federal way", "tacoma", "everett", "renton",
        "kent", "bothell", "lynnwood", "sammamish", "mercer island", "woodinville", "shoreline", "edmonds",
        "tukwila", "seatac", "burien", "auburn", "puyallup", "bainbridge island", "mukilteo", "mill creek",
        "snoqualmie", "north bend", "maple valley", "covington", "des moines", "lake forest park", "kenmore",
        "newcastle", "medina", "clyde hill", "duvall", "monroe", "marysville", "lake stevens", "gig harbor",
        "olympia", "lacey", "bremerton", "poulsbo", "silverdale", "lakewood", "fife", "sumner", "bonney lake",
        "kingston", "vashon", "lynwood", "fox island", "university place", "mountlake terrace", "brier", "arlington", "snohomish", "fall city",
    }},
    "san diego": {"state": "california", "cities": {
        "san diego", "la jolla", "carlsbad", "encinitas", "del mar", "solana beach", "oceanside", "vista",
        "san marcos", "escondido", "poway", "chula vista", "el cajon", "la mesa", "santee", "national city",
        "coronado", "imperial beach", "lemon grove", "rancho santa fe", "cardiff", "cardiff by the sea",
        "rancho bernardo", "carmel valley", "mira mesa", "sorrento valley", "point loma", "pacific beach",
        "ocean beach", "mission valley", "spring valley", "bonita", "alpine", "ramona", "fallbrook", "temecula",
        "murrieta", "bonsall", "valley center", "lakeside", "san ysidro", "otay mesa", "scripps ranch",
        "university city", "hillcrest", "north park", "la costa", "leucadia", "olivenhain", "4s ranch",
    }},
}


def metro_ok(person_city: str, person_state: str, company_city: str, company_state: str) -> bool:
    pc, ps = (person_city or "").strip().lower(), (person_state or "").strip().lower()
    cc, cs = (company_city or "").strip().lower(), (company_state or "").strip().lower()
    if not cc and not cs:
        return True  # unknown HQ: nothing contradicts
    metro = METROS.get(pc)
    if metro is None:
        return (not cc or cc == pc) and (not cs or cs == ps)
    if cs and cs != metro["state"]:
        return False
    if not cc:
        return True
    return cc in metro["cities"]


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", s.lower()).strip("_") or "unknown"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True)
    ap.add_argument("--outdir", required=True)
    ap.add_argument("--model", default="anthropic/claude-sonnet-5.5")
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--batch", type=int, default=40)
    ap.add_argument("--workers", type=int, default=6)
    args = ap.parse_args()

    for alias in ("OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN"):
        if not os.environ.get("OPENROUTER_API_KEY") and os.environ.get(alias):
            os.environ["OPENROUTER_API_KEY"] = os.environ[alias]

    with open(args.input, encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    total = len(rows)

    # 1. dedupe by email (case-insensitive), keep first
    seen, deduped = set(), []
    for r in rows:
        key = (r.get("Email") or "").strip().lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(r)
    rows = deduped

    # 2. short name (deterministic) + 3. personalized name (LLM, guarded)
    companies = OrderedDict()
    for r in rows:
        companies.setdefault((r.get("Company Name") or "").strip(), None)
    short = {c: short_company_name(c) for c in companies}
    personalized = dict(short)
    guard_fallbacks = 0
    llm_errors = 0
    if not args.no_llm:
        ids = {f"c{i}": c for i, c in enumerate(companies)}
        id_items = list(ids.items())
        batches = [id_items[i:i + args.batch] for i in range(0, len(id_items), args.batch)]

        def run(b):
            try:
                return llm_batch(b, args.model), None
            except Exception as e:  # noqa: BLE001 - fail open per batch, fall back to short name
                return {}, e

        with ThreadPoolExecutor(max_workers=args.workers) as ex:
            for result, err in ex.map(run, batches):
                if err is not None:
                    llm_errors += 1
                    print(f"[llm] batch failed: {err}", file=sys.stderr)
                    continue
                for cid, nick in result.items():
                    c = ids.get(cid)
                    if c is None:
                        continue
                    val, ok = guard(c, nick, short[c])
                    if not ok:
                        guard_fallbacks += 1
                    personalized[c] = val

    for r in rows:
        c = (r.get("Company Name") or "").strip()
        r["Short Company Name"] = short[c]
        r["Personalized Name"] = personalized[c]
    out_fields = fieldnames + [c for c in ("Short Company Name", "Personalized Name") if c not in fieldnames]

    # 4. split by person City, with metro guard
    outdir = Path(args.outdir)
    outdir.mkdir(parents=True, exist_ok=True)
    buckets: dict[str, list] = {}
    for r in rows:
        city = (r.get("City") or "").strip() or "unknown"
        ok = metro_ok(city, r.get("State", ""), r.get("Company City", ""), r.get("Company State", ""))
        buckets.setdefault(slug(city) + ("" if ok else "__hq_outside_metro"), []).append(r)

    summary = {"input_rows": total, "after_dedupe": len(rows), "duplicates_removed": total - len(rows),
               "unique_companies": len(companies), "llm_model": None if args.no_llm else args.model,
               "llm_batches_failed": llm_errors, "personalized_guard_fallbacks": guard_fallbacks, "files": {}}
    for name, rs in sorted(buckets.items()):
        p = outdir / f"{name}.csv"
        with open(p, "w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
            w.writeheader()
            w.writerows(rs)
        summary["files"][p.name] = {"rows": len(rs), "cities": dict(Counter(r.get("City") for r in rs)),
                                    "email_status": dict(Counter(r.get("email_status", "") for r in rs))}
    (outdir / "summary.json").write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
