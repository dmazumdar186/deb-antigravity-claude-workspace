"""
construction_award_triggers.py
description: Dated, checkable cold-email triggers for US construction firms: NEW federal contract awards (USAspending.gov,
             free, no key) to recipients in the given states over the last --days. "Awarded on" = the action_date of
             the award's ORIGINAL transaction (modification number "0"); later modifications of old awards are not
             triggers. One row per recipient (newest qualifying award), with a readable awarding agency.
inputs:  --states CA,OR,WA | --region west (see REGIONS); --days 90; --naics 23 (2/4/6-digit codes; 23 = 236+237+238);
         --min-amount 250000 --max-amount 100000000 (initial obligation, USD); --refresh; --check (offline, caches only)
outputs: <out-dir>/awards_<region>_<start>_<end>.json (raw original transactions), award_detail/<award>.json (cache),
         construction_triggers_<region>.csv (one row per recipient). Default out-dir .tmp/referral/triggers/construction
usage:   python3 execution/gtm_icp_filters/construction_award_triggers.py --region west
         python3 execution/gtm_icp_filters/construction_award_triggers.py --states WA --days 60 --check
Directive: directives/gtm_icp_filters/construction_award_triggers.md
Spend: none (USAspending is a free public API).
Known gap: DoD procurement (Army Corps, NAVFAC, Air Force) is published on USAspending with a 90-day delay, so a
           90-day window holds almost no DoD awards; OFFICE_RULES still name them when they appear.
"""

from __future__ import annotations

import argparse, csv, datetime as dt, json, re, sys, time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # no keys needed (public API); kept for workspace convention
ROOT = Path(__file__).resolve().parents[2]
TXN_API = "https://api.usaspending.gov/api/v2/search/spending_by_transaction/"
AWARD_API = "https://api.usaspending.gov/api/v2/awards/{}/"
AWARD_URL = "https://www.usaspending.gov/award/{}"
REGIONS = {
    "west": ["CA", "OR", "WA"],
    "east": ["ME", "NH", "VT", "MA", "RI", "CT", "NY", "NJ", "PA", "DE", "MD", "DC", "VA", "NC", "SC", "GA", "FL"],
    "midwest": ["OH", "MI", "IN", "IL", "WI", "MN", "IA", "MO", "ND", "SD", "NE", "KS"],
    "south": ["TX", "OK", "AR", "LA", "MS", "AL", "TN", "KY", "WV"],
    "mountain": ["MT", "ID", "WY", "CO", "UT", "NV", "AZ", "NM"],
}
FIELDS = ["Award ID", "Mod", "Recipient Name", "Recipient UEI", "Action Date", "Transaction Amount", "Awarding Agency",
          "Awarding Sub Agency", "Transaction Description", "naics_code", "generated_internal_id", "internal_id"]
# Readable agency names: sub-agency first (more specific), DoD branches resolved from the awarding office.
AGENCY_RENAME = {
    "Forest Service": "U.S. Forest Service",
    "National Park Service": "National Park Service",
    "U.S. Fish and Wildlife Service": "U.S. Fish and Wildlife Service",
    "Bureau of Reclamation": "Bureau of Reclamation",
    "Public Buildings Service": "GSA Public Buildings Service",
    "Department of the Air Force": "U.S. Air Force",
    "Department of the Army": "U.S. Army",
    "Department of the Navy": "U.S. Navy",
    "Department of Veterans Affairs": "Department of Veterans Affairs",
    "Indian Health Service": "Indian Health Service",
    "U.S. Coast Guard": "U.S. Coast Guard",
    "Federal Highway Administration": "Federal Highway Administration",
    "Bureau of Indian Affairs and Bureau of Indian Education": "Bureau of Indian Affairs",
    "Federal Prison System / Bureau of Prisons": "Federal Bureau of Prisons",
    "National Aeronautics and Space Administration": "NASA",
}
OFFICE_RULES = [  # (regex on awarding office name, readable agency)
    (r"\bENDIST\b|\bENG(INEER)?\s*DIST|\bUSACE\b|CORPS OF ENG|\bENGINEER DISTRICT", "U.S. Army Corps of Engineers"),
    (r"\bNAVFAC\b|NAVAL FACILITIES", "Naval Facilities Engineering Command (NAVFAC)"),
    (r"NATIONAL GUARD|\bUSPFO\b|\bNGB\b", "National Guard"),
]


def post(body: dict, tries: int = 5) -> dict:
    for i in range(tries):
        try:
            r = requests.post(TXN_API, json=body, timeout=90)
        except requests.RequestException:
            time.sleep(2 * (i + 1))
            continue
        if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
            time.sleep(2 * (i + 1))
            continue
        if r.status_code >= 400:
            raise RuntimeError(f"USAspending HTTP {r.status_code}: {r.text[:300]}")
        return r.json()
    raise RuntimeError("USAspending unreachable")


def pull_originals(states: list[str], start: str, end: str, naics: list[str], path: Path, refresh: bool,
                   offline: bool) -> list[dict]:
    """Every contract transaction in the window for recipients in `states`; keep only original awards (Mod 0)."""
    if path.exists() and not refresh:
        return json.loads(path.read_text())["results"]
    if offline:
        sys.exit(f"--check: no cached pull at {path}")
    rows, seen = [], 0
    for st in states:  # one walk per state keeps each result set small enough to page fully
        page = 1
        while True:
            d = post({"filters": {"award_type_codes": ["A", "B", "C", "D"],
                                  "time_period": [{"start_date": start, "end_date": end}],
                                  "naics_codes": {"require": naics},
                                  "recipient_locations": [{"country": "USA", "state": st}]},
                      "fields": FIELDS, "limit": 100, "page": page, "sort": "Action Date", "order": "desc"})
            res = d.get("results") or []
            seen += len(res)
            for r in res:
                if str(r.get("Mod") or "").strip() in ("0", "00", "000") and start <= (r.get("Action Date") or "") <= end:
                    r["recipient_state"] = st
                    rows.append(r)
            if not (d.get("page_metadata") or {}).get("hasNext") or not res:
                break
            page += 1
    rows = list({(r["generated_internal_id"]): r for r in rows}.values())
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"states": states, "start": start, "end": end, "naics": naics,
                                "transactions_seen": seen, "pulled_at": dt.datetime.now().isoformat(),
                                "results": rows}))
    return rows


def award_detail(gid: str, cache: Path, offline: bool) -> dict:
    p = cache / f"{re.sub(r'[^A-Za-z0-9_.-]', '_', gid)}.json"
    if p.exists():
        return json.loads(p.read_text())
    if offline:
        return {}
    for i in range(4):
        try:
            r = requests.get(AWARD_API.format(gid), timeout=60)
            if r.status_code == 200:
                d = r.json()
                keep = {"date_signed": d.get("date_signed"), "piid": d.get("piid"),
                        "awarding_agency": d.get("awarding_agency"),
                        "recipient_name": (d.get("recipient") or {}).get("recipient_name"),
                        "recipient_uei": (d.get("recipient") or {}).get("recipient_uei"),
                        "parent_name": (d.get("recipient") or {}).get("parent_recipient_name"),
                        "parent_uei": (d.get("recipient") or {}).get("parent_recipient_uei")}
                cache.mkdir(parents=True, exist_ok=True)
                p.write_text(json.dumps(keep))
                return keep
        except requests.RequestException:
            pass
        time.sleep(2 * (i + 1))
    return {}


def readable_agency(sub: str, top: str, office: str) -> str:
    for pat, name in OFFICE_RULES:
        if office and re.search(pat, office, re.I):
            return name
    if sub.startswith("Office of") or not sub:  # internal admin offices read badly; the department reads fine
        return AGENCY_RENAME.get(top) or top
    return AGENCY_RENAME.get(sub) or sub


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--region", choices=sorted(REGIONS))
    g.add_argument("--states", help="comma-separated 2-letter codes")
    ap.add_argument("--days", type=int, default=90)
    ap.add_argument("--end", default=dt.date.today().isoformat())
    ap.add_argument("--naics", default="23", help="comma-separated NAICS codes, 2/4/6 digits")
    ap.add_argument("--min-amount", type=float, default=250_000)
    ap.add_argument("--max-amount", type=float, default=100_000_000)
    ap.add_argument("--out-dir", default=str(ROOT / ".tmp/referral/triggers/construction"))
    ap.add_argument("--refresh", action="store_true")
    ap.add_argument("--check", action="store_true", help="offline: caches only")
    a = ap.parse_args()
    states = REGIONS[a.region] if a.region else [s.strip().upper() for s in a.states.split(",") if s.strip()]
    label = a.region or "-".join(states).lower()
    end = dt.date.fromisoformat(a.end)
    start = (end - dt.timedelta(days=a.days)).isoformat()
    out = Path(a.out_dir)
    raw = pull_originals(states, start, end.isoformat(), [n.strip() for n in a.naics.split(",")],
                         out / f"awards_{label}_{start}_{end}.json", a.refresh, a.check)
    sized = [r for r in raw if a.min_amount <= float(r.get("Transaction Amount") or 0) <= a.max_amount]
    best: dict[str, dict] = {}  # newest qualifying award per recipient (UEI, else name)
    for r in sorted(sized, key=lambda r: (r["Action Date"], float(r["Transaction Amount"] or 0)), reverse=True):
        key = r.get("Recipient UEI") or (r.get("Recipient Name") or "").upper()
        best.setdefault(key, r)
    rows = []
    for r in best.values():
        det = award_detail(r["generated_internal_id"], out / "award_detail", a.check)
        aa = det.get("awarding_agency") or {}
        office = aa.get("office_agency_name") or ""
        rows.append({
            "recipient": r["Recipient Name"], "uei": r.get("Recipient UEI") or "", "state": r["recipient_state"],
            "parent": det.get("parent_name") or "", "award_id": r["Award ID"], "action_date": r["Action Date"],
            "date_signed": det.get("date_signed") or "", "amount": round(float(r["Transaction Amount"] or 0), 2),
            "agency": readable_agency(r.get("Awarding Sub Agency") or "", r.get("Awarding Agency") or "", office),
            "agency_raw": r.get("Awarding Agency") or "", "subagency_raw": r.get("Awarding Sub Agency") or "",
            "office_raw": office, "naics": r.get("naics_code") or "",
            "description": re.sub(r"\s+", " ", r.get("Transaction Description") or "").strip()[:300],
            "evidence_url": AWARD_URL.format(r["generated_internal_id"]),
        })
    rows.sort(key=lambda x: x["action_date"], reverse=True)
    path = out / f"construction_triggers_{label}.csv"
    out.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0]) if rows else ["recipient"])
        w.writeheader()
        w.writerows(rows)
    print(f"states={','.join(states)} window={start}..{end} original_awards={len(raw)} "
          f"in_amount_band={len(sized)} recipients={len(rows)} -> {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
