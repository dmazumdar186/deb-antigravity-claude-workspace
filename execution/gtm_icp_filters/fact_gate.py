"""
fact_gate.py
description: Reliability layer (fact gate) between a prospect-trigger finder and anything that renders outward text.
             Re-derives every candidate claim from primary sources with its OWN fetch and matcher (shares no code with
             the finder), passes only claims it can prove, and drops FALSE / UNVERIFIABLE / UNSUPPORTED claims with a
             reason and an evidence quote. Fails closed: anything it cannot reach or parse is dropped.
claim types:
  fda_clearance        k_number, company, product, date  -> openFDA 510(k) by K number: applicant fuzzy-matches the
                       company, device_name contains the product, decision_date == date
  federal_award        award_id, company, agency, date   -> USAspending award(s) with that id: recipient matches the
                       company, agency named in toptier/subtier/office, date_signed ("awarded on") == date
  site_copyright       domain, year                      -> fresh Chromium render: newest year in the copyright line == year
  site_viewport_missing domain                           -> no <meta name=viewport> in raw HTML (desktop + mobile UA)
                                                            nor in the rendered DOM
  site_not_mention     domain, product | agency          -> home (rendered, incl. hidden menus) + nav/header/footer links
                       + sitemap.xml pages (<= --max-pages) searched for distinctive tokens of the product (a product
                       family / brand token counts) or the agency's names/acronyms; ANY hit -> FALSE
inputs:  --claims CSV, one row per claim: claim_id,row_id,company,domain,claim_type,k_number,award_id,product,agency,
         date (YYYY-MM-DD),year,claim_text   (unknown columns are carried through)
outputs: <out>/pass.csv (claim + evidence_url + evidence_quote), <out>/reject.csv (+ verdict, reason),
         <out>/rows.csv (finder rows rendered ONLY from passed claims; a row needs its trigger claim passed),
         <out>/summary.json. Fetch cache: .tmp/fact_gate/cache/ (re-runs reuse it; --refresh bypasses).
usage:   python3 execution/gtm_icp_filters/fact_gate.py --claims claims.csv --out .tmp/fact_gate/run1
         python3 execution/gtm_icp_filters/fact_gate.py --claims claims.csv --limit 5      # first 5 claims only
         python3 execution/gtm_icp_filters/fact_gate.py --claims claims.csv --offline      # cache only, no network
Directive: directives/gtm_icp_filters/fact_gate.md
Spend: none. Read-only (GETs to openFDA, api.usaspending.gov, company sites; one POST search to USAspending).
       No LLM calls, no sends.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import hashlib
import html as htmllib
import json
import re
import subprocess
import sys
import time
import unicodedata
import urllib.parse
from difflib import SequenceMatcher
from html.parser import HTMLParser
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()  # no keys needed (public APIs); workspace convention

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / ".tmp/fact_gate/cache"
RENDER_JS = Path(__file__).with_name("fact_gate_render.js")
FDA_API = "https://api.fda.gov/device/510k.json"
FDA_HUMAN = "https://www.accessdata.fda.gov/scripts/cdrh/cfdocs/cfpmn/pmn.cfm?ID={}"
AWARD_SEARCH = "https://api.usaspending.gov/api/v2/search/spending_by_award/"
AWARD_API = "https://api.usaspending.gov/api/v2/awards/{}/"
AWARD_HUMAN = "https://www.usaspending.gov/award/{}"
UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"
UA_MOBILE = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) "
    "Version/17.0 Mobile/15E148 Safari/604.1"
)

# ---- floors / ceilings (build contract: every filter has both) ----
NAME_MATCH_FLOOR = (
    0.80  # company vs applicant/recipient similarity needed to accept a record
)
PRODUCT_COVER_FLOOR = (
    0.80  # share of claim-product tokens that must appear in the FDA device_name
)
MIN_HOME_TEXT = (
    200  # rendered home text below this = blocked / JS shell -> UNVERIFIABLE
)
MAX_PAGES_FLOOR, MAX_PAGES_CEILING = 1, 40  # --max-pages bounds (default 25)
MAX_SITEMAPS = 6  # nested sitemap files read per site
MAX_SITEMAP_URLS = 5000  # URLs read from sitemaps per site
REJECT_RATE_ALARM_MIN_N = 20  # with >= this many claims ...
UNVERIFIABLE_CEILING = (
    0.50  # ... more than this share UNVERIFIABLE = fetch layer broken -> exit 2
)
QUOTE_CHARS = 90  # evidence quote context window

PASS_COLS = [
    "claim_id",
    "row_id",
    "company",
    "domain",
    "claim_type",
    "claim_text",
    "evidence_url",
    "evidence_quote",
]
REJECT_COLS = PASS_COLS[:6] + ["verdict", "reason", "evidence_url", "evidence_quote"]
TRIGGER_TYPES = {"fda_clearance", "federal_award"}
MONTHS = [dt.date(2000, m, 1).strftime("%B").lower() for m in range(1, 13)]

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
    "pc",
    "pllc",
    "dba",
    "l",
    "p",
    "c",
}
# Device-category / anatomy / filler words: never distinctive on their own (a brand or family token is).
_GENERIC_WORDS = """
a an and or of for with the in on to by from new plus pro ii iii iv mini max ultra advanced next gen generation
system systems device devices kit kits set sets assay test tests cassette instrument instruments accessory accessories
tray trays pack component components unit model series family platform solution solutions product products
implant implants screw screws plate plates plating rod rods cage cages anchor anchors pin pins wire wires nail nails
liner liners cup cups stem stems head heads insert inserts spacer spacers graft grafts mesh suture sutures staple
staples clip clips catheter catheters needle needles syringe syringes cannula tube tubing tubes sheath guidewire
guide guides introducer dilator dilators balloon stent stents valve valves pump pumps filter filters port ports
electrode electrodes sensor sensors monitor monitoring monitors probe probes lead leads cable cables adapter connector
software app application module image imaging scanner ultrasound camera endoscope scope laser light lamp
dressing dressings bandage gauze sponge pad pads foam gel gels paste cream spray solution wash irrigation
glove gloves gown gowns mask masks drape drapes cover covers bag bags container containers bottle cap caps
handpiece blade blades bur burs drill drills saw reamer reamers rasp rasps forceps scissors retractor retractors
clamp clamps holder holders instrument driver drivers handle handles tip tips
cervical lumbar thoracic spinal spine sacral interbody fusion fixation posterior anterior lateral total partial
hip knee shoulder elbow wrist ankle foot hand dental oral orthodontic acetabular femoral tibial humeral
cranial cardiac vascular venous arterial coronary peripheral surgical surgery medical clinical diagnostic diagnostics
disposable reusable sterile single use patient home hospital portable wireless digital electronic automated manual
decompression stabilization reconstruction repair replacement treatment therapy obturation antimicrobial
electrocardiograph ecg ekg skin clinic wart warts tag tags clear care health wound
hearing aid eye lens contact nasal ear throat breast
eeg emg analysis analyzer matrix control controls box identifier reprocessed reperfusion aspiration
panel alignment isolation chamber negative protection embolic heat elite full length technology limb salvage blood glucose urine pressure temperature oxygen
"""
GENERIC = set(_GENERIC_WORDS.split())
# Agency labels -> extra regexes that count as a "mention" of that agency on a website.
AGENCY_ALIASES = {
    "coast guard": [r"\bCoast Guard\b", r"\bUSCG\b"],
    "forest service": [
        r"\bForest Service\b",
        r"\bUSFS\b",
        r"\bUSDA\b",
        r"\bDepartment of Agriculture\b",
    ],
    "agricultural research service": [
        r"\bAgricultural Research Service\b",
        r"\bUSDA\b",
        r"\bARS\b",
    ],
    "public buildings service": [
        r"\bPublic Buildings Service\b",
        r"\bGSA\b",
        r"\bGeneral Services Administration\b",
    ],
    "gsa": [r"\bGSA\b", r"\bGeneral Services Administration\b"],
    "nasa": [r"\bNASA\b", r"\bNational Aeronautics\b"],
    "national park service": [
        r"\bNational Park Service\b",
        r"\bNPS\b",
        r"\bNational Parks?\b",
    ],
    "national institutes of health": [r"\bNational Institutes of Health\b", r"\bNIH\b"],
    "department of state": [
        r"\bDepartment of State\b",
        r"\bState Department\b",
        r"\bU\.?S\.? Embass(y|ies)\b",
    ],
    "bureau of reclamation": [r"\bBureau of Reclamation\b", r"\bUSBR\b"],
    "veterans affairs": [
        r"\bVeterans Affairs\b",
        r"\bthe VA\b",
        r"\bVA (Medical|Hospital|Health|Clinic)",
        r"\bVAMC\b",
    ],
    "army corps of engineers": [
        r"\bCorps of Engineers\b",
        r"\bUSACE\b",
        r"\bArmy Corps\b",
    ],
    "navfac": [r"\bNAVFAC\b", r"\bNaval Facilities\b"],
    "navy": [r"\bU\.?S\.? Navy\b", r"\bNavy\b"],
    "air force": [r"\bAir Force\b", r"\bUSAF\b"],
    "army": [r"\bU\.?S\.? Army\b", r"\bArmy\b"],
    "national guard": [r"\bNational Guard\b"],
    "indian health service": [r"\bIndian Health Service\b", r"\bIHS\b"],
    "fish and wildlife": [r"\bFish (and|&) Wildlife\b", r"\bUSFWS\b"],
    "federal highway": [r"\bFederal Highway\b", r"\bFHWA\b"],
    "bureau of prisons": [r"\bBureau of Prisons\b", r"\bBOP\b"],
    "bureau of indian affairs": [r"\bBureau of Indian Affairs\b", r"\bBIA\b"],
    "homeland security": [r"\bHomeland Security\b", r"\bDHS\b"],
    "department of energy": [r"\bDepartment of Energy\b", r"\bDOE\b"],
    "smithsonian": [r"\bSmithsonian\b"],
    "fema": [r"\bFEMA\b"],
}
BLOCK_MARKERS = re.compile(
    r"just a moment|attention required|access denied|verify you are human|enable javascript "
    r"and cookies|request unsuccessful|403 forbidden|captcha",
    re.I,
)
SKIP_EXT = re.compile(
    r"\.(pdf|jpe?g|png|gif|svg|webp|zip|docx?|xlsx?|pptx?|mp4|mp3|ico|css|js|xml)(\?|$)",
    re.I,
)


# ============================================================ utilities
def norm_text(s: str) -> str:
    """NFKC, marks (R)(TM) removed, whitespace collapsed."""
    s = unicodedata.normalize("NFKC", htmllib.unescape(s or ""))
    s = re.sub(r"[®™©℠]|\((?:R|TM|SM)\)", "", s)
    return re.sub(r"\s+", " ", s).strip()


def name_tokens(name: str) -> list[str]:
    s = re.sub(r"[^a-z0-9 ]+", " ", norm_text(name).lower().replace("&", " and "))
    return [t for t in s.split() if t not in SUFFIX]


def name_score(a: str, b: str) -> float:
    """Similarity of two company names, 0..1 (legal suffixes ignored)."""
    ta, tb = name_tokens(a), name_tokens(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    if sa == sb or "".join(ta) == "".join(tb):
        return 1.0
    jac = len(sa & sb) / len(sa | sb)
    # shorter name fully contained in the longer one ("Urgo" vs "Urgo Medical North America")
    small, big = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    contain = 0.9 if small <= big and any(t not in GENERIC for t in small) else 0.0
    seq = SequenceMatcher(None, "".join(ta), "".join(tb)).ratio()
    return round(max(jac, contain, seq), 3)


def quote_at(text: str, m: re.Match) -> str:
    a, b = max(0, m.start() - QUOTE_CHARS // 2), min(
        len(text), m.end() + QUOTE_CHARS // 2
    )
    return ("..." if a else "") + text[a:b].strip() + ("..." if b < len(text) else "")


def parse_date(s: str) -> str | None:
    s = (s or "").strip()
    try:
        return dt.date.fromisoformat(s[:10]).isoformat()
    except ValueError:
        return None


def site_root(domain: str) -> str:
    d = (
        re.sub(r"^https?://", "", (domain or "").strip().lower())
        .split("/")[0]
        .split(":")[0]
    )
    return re.sub(r"^www\.", "", d)


def same_site(url: str, root: str) -> bool:
    h = urllib.parse.urlparse(url).netloc.lower().split(":")[0]
    h = re.sub(r"^www\.", "", h)
    return bool(root) and (h == root or h.endswith("." + root))


def slug_text(url: str) -> str:
    p = urllib.parse.unquote(urllib.parse.urlparse(url).path)
    return re.sub(r"[/_\-.]+", " ", p).strip()


# ============================================================ cached fetch layer (own, independent of the finder)
class Fetcher:
    def __init__(self, refresh: bool = False, offline: bool = False):
        self.refresh, self.offline = refresh, offline
        CACHE.mkdir(parents=True, exist_ok=True)
        self.s = requests.Session()

    def _path(self, kind: str, key: str) -> Path:
        return CACHE / kind / (hashlib.sha1(key.encode("utf-8")).hexdigest() + ".json")

    def _load(self, p: Path) -> dict | None:
        if p.exists() and not self.refresh:
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                return None
        return None

    def _save(self, p: Path, d: dict) -> None:
        if d.get("error"):  # never cache failures: a re-run retries them
            return
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(d), encoding="utf-8")

    def get(self, url: str, ua: str = UA, timeout: int = 25, tries: int = 3) -> dict:
        """-> {status, final_url, text, error?}. 404 is a valid answer (cached)."""
        p = self._path("http", f"{ua[:20]}|{url}")
        if (c := self._load(p)) is not None:
            return c
        if self.offline:
            return {"status": 0, "error": "offline: not cached", "text": ""}
        err = ""
        for i in range(tries):
            try:
                r = self.s.get(
                    url,
                    headers={"User-Agent": ua, "Accept-Language": "en-US,en;q=0.9"},
                    timeout=timeout,
                    allow_redirects=True,
                )
                if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
                    time.sleep(2 * (i + 1))
                    continue
                r.encoding = r.encoding or "utf-8"
                d = {
                    "status": r.status_code,
                    "final_url": r.url,
                    "text": r.text[:3_000_000],
                }
                if r.status_code >= 500 or r.status_code == 429:
                    d["error"] = f"HTTP {r.status_code}"
                self._save(p, d)
                return d
            except requests.RequestException as e:
                err = f"{type(e).__name__}: {str(e)[:160]}"
                time.sleep(1.5 * (i + 1))
        return {"status": 0, "error": err or "unreachable", "text": ""}

    def post_json(self, url: str, body: dict, tries: int = 4) -> dict:
        key = url + json.dumps(body, sort_keys=True)
        p = self._path("post", key)
        if (c := self._load(p)) is not None:
            return c
        if self.offline:
            return {"error": "offline: not cached"}
        err = ""
        for i in range(tries):
            try:
                r = self.s.post(url, json=body, timeout=60)
                if r.status_code in (429, 500, 502, 503, 504) and i < tries - 1:
                    time.sleep(2 * (i + 1))
                    continue
                if r.status_code >= 400:
                    return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
                d = r.json()
                self._save(p, d)
                return d
            except (requests.RequestException, ValueError) as e:
                err = f"{type(e).__name__}: {str(e)[:160]}"
                time.sleep(2 * (i + 1))
        return {"error": err or "unreachable"}

    def render(self, urls: list[str]) -> dict[str, dict]:
        """Chromium render (fact_gate_render.js), cached per URL. -> {url: result}"""
        out, todo = {}, []
        for u in urls:
            c = self._load(self._path("render", u))
            if c is not None:
                out[u] = c
            elif self.offline:
                out[u] = {"url": u, "error": "offline: not cached"}
            else:
                todo.append(u)
        if todo:
            try:
                cp = subprocess.run(
                    ["node", str(RENDER_JS)],
                    input=json.dumps({"jobs": [{"url": u} for u in todo]}),
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    timeout=90 * len(todo) + 60,
                    cwd=str(RENDER_JS.parent),
                )
                res = (
                    json.loads(cp.stdout)
                    if cp.returncode == 0 and cp.stdout.strip()
                    else []
                )
                if not res:
                    res = [
                        {"url": u, "error": f"render failed: {cp.stderr[:200]}"}
                        for u in todo
                    ]
            except (subprocess.TimeoutExpired, OSError, json.JSONDecodeError) as e:
                res = [
                    {"url": u, "error": f"render failed: {type(e).__name__}"}
                    for u in todo
                ]
            for r in res:
                if not r.get("error") and (r.get("status") or 0) >= 400:
                    r["error"] = f"HTTP {r['status']}"
                self._save(self._path("render", r["url"]), r)
                out[r["url"]] = r
        return out


class _Extract(HTMLParser):
    """Visible-ish text + links + img alt/title/src from raw HTML (scripts/styles dropped)."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.links, self.imgs, self._skip, self._a = [], [], [], 0, None
        self.viewport = False

    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag in ("script", "style", "noscript", "template"):
            self._skip += 1
        elif tag == "a" and a.get("href"):
            self._a = {"href": a["href"], "text": ""}
        elif tag == "img":
            self.imgs.append(
                {
                    "alt": a.get("alt") or "",
                    "title": a.get("title") or "",
                    "src": a.get("src") or "",
                }
            )
        elif tag == "meta" and (a.get("name") or "").lower() == "viewport":
            self.viewport = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript", "template") and self._skip:
            self._skip -= 1
        elif tag == "a" and self._a is not None:
            self.links.append(self._a)
            self._a = None

    def handle_data(self, data):
        if not self._skip:
            self.parts.append(data)
            if self._a is not None:
                self._a["text"] += data


def extract(raw_html: str) -> _Extract:
    p = _Extract()
    try:
        p.feed(raw_html or "")
        p.close()
    except (AssertionError, ValueError):  # malformed markup: keep what parsed
        pass
    return p


# ============================================================ needles (what counts as a "mention")
def product_needles(product: str, company: str = "") -> list[str]:
    """Distinctive tokens of a product name. Brand/family tokens count; generic category words do not."""
    s = norm_text(product)
    s = re.sub(r"\([^)]*\)", " ", s)  # FDA parenthetical codes/categories
    comp = set(name_tokens(company))
    out = []
    for t in re.findall(r"[A-Za-z0-9][A-Za-z0-9+\-]*[A-Za-z0-9+]|[A-Za-z0-9]", s):
        tl = t.lower()
        if tl in GENERIC or tl in comp or re.fullmatch(r"[\d.]+", t):
            continue
        if len(t) < 3 and not re.search(r"\d", t):
            continue
        out.append(t)
        if "-" in t:  # Brand-C -> Brand (family name), X-Tip stays whole
            stem = t.split("-")[0]
            if (
                len(stem) >= 4
                and stem.lower() not in GENERIC
                and stem.lower() not in comp
            ):
                out.append(stem)
    return list(dict.fromkeys(out))


def needle_regex(tok: str) -> re.Pattern:
    body = r"[\s\-]?".join(re.escape(p) for p in re.split(r"-", tok) if p)
    pat = r"(?<![A-Za-z0-9])" + body + r"(?![A-Za-z0-9])"
    short_alpha = len(tok) <= 4 and tok.isalpha()
    return re.compile(pat, 0 if short_alpha and tok.isupper() else re.I)


def agency_regexes(agency: str) -> list[re.Pattern]:
    a = norm_text(agency)
    al = a.lower()
    pats = []
    for key, rx in AGENCY_ALIASES.items():
        if key in al:
            pats += rx
    core = re.sub(r"^(the\s+)?(u\.?s\.?\s+)", "", a, flags=re.I).strip()
    if core:
        pats.append(r"\b" + r"\s+".join(re.escape(w) for w in core.split()) + r"\b")
    words = [
        w
        for w in re.findall(r"[A-Za-z]+", core)
        if w.lower() not in {"of", "the", "and", "for", "u", "s"}
    ]
    if len(words) >= 3:
        pats.append(r"\b" + "".join(w[0].upper() for w in words) + r"\b")
    seen, out = set(), []
    for p in pats:
        if p not in seen:
            seen.add(p)
            out.append(
                re.compile(p, 0 if re.fullmatch(r"\\b[A-Z]{2,6}\\b", p) else re.I)
            )
    return out


def find_mention(text: str, pats: list[re.Pattern]) -> tuple[str, str] | None:
    for rx in pats:
        m = rx.search(text)
        if m:
            return rx.pattern, quote_at(text, m)
    return None


# ============================================================ verdict helper
def V(verdict: str, reason: str, url: str = "", quote: str = "") -> dict:
    return {
        "verdict": verdict,
        "reason": reason,
        "evidence_url": url,
        "evidence_quote": quote,
    }


# ============================================================ public-record checks
def check_fda(c: dict, f: Fetcher) -> dict:
    k = (c.get("k_number") or "").strip().upper()
    if not re.fullmatch(r"(?:K|DEN)\d{6}", k):
        return V("UNSUPPORTED", f"k_number missing or malformed: {k!r}")
    if k.startswith("DEN") and re.search(r"510\(k\)|clearance|cleared", c.get("claim_text") or "", re.I):
        return V("FALSE", f"{k} is a De Novo grant, not a 510(k) clearance", FDA_HUMAN.format(k),
                 (c.get("claim_text") or "")[:200])
    url = f"{FDA_API}?search=k_number:{k}"
    r = f.get(url)
    if r.get("error"):
        return V("UNVERIFIABLE", f"openFDA unreachable: {r['error']}", url)
    if r["status"] == 404:
        return V("FALSE", f"no 510(k) record for {k}", url, "openFDA: NOT_FOUND")
    try:
        recs = json.loads(r["text"]).get("results") or []
    except json.JSONDecodeError:
        return V("UNVERIFIABLE", "openFDA returned non-JSON", url)
    recs = [x for x in recs if (x.get("k_number") or "").upper() == k]
    if not recs:
        return V("FALSE", f"no 510(k) record for {k}", url, "openFDA: 0 results")
    rec = recs[0]
    app, dev, dd = (
        rec.get("applicant") or "",
        rec.get("device_name") or "",
        rec.get("decision_date") or "",
    )
    q = f"applicant '{app}' | device_name '{dev}' | decision_date {dd}"
    human = FDA_HUMAN.format(k)
    sc = name_score(c.get("company", ""), app)
    if sc < NAME_MATCH_FLOOR:
        return V(
            "FALSE",
            f"applicant does not match company (score {sc} < {NAME_MATCH_FLOOR})",
            human,
            q,
        )
    prod = c.get("product") or ""
    if prod:
        pt = [t for t in re.findall(r"[a-z0-9]+", norm_text(prod).lower())]
        dtoks = set(re.findall(r"[a-z0-9]+", norm_text(dev).lower()))
        cover = sum(t in dtoks for t in pt) / max(1, len(pt))
        dist_missing = [t for t in pt if t not in GENERIC and t not in dtoks]
        if cover < PRODUCT_COVER_FLOOR or dist_missing:
            return V(
                "FALSE",
                f"device_name does not contain product (cover {cover:.2f}, missing {dist_missing})",
                human,
                q,
            )
    want = parse_date(c.get("date", ""))
    if c.get("date") and not want:
        return V("UNSUPPORTED", f"date not ISO: {c.get('date')!r}")
    if want and want != dd:
        return V("FALSE", f"decision_date {dd} != claimed {want}", human, q)
    return V("PASS", "openFDA record matches", human, q)


def check_award(c: dict, f: Fetcher) -> dict:
    aid = (c.get("award_id") or "").strip().upper()
    if not re.fullmatch(r"[A-Z0-9\-]{6,40}", aid):
        return V("UNSUPPORTED", f"award_id missing or malformed: {aid!r}")
    body = {
        "filters": {"award_ids": [aid], "award_type_codes": ["A", "B", "C", "D"]},
        "fields": [
            "Award ID",
            "Recipient Name",
            "generated_internal_id",
            "Awarding Agency",
            "Awarding Sub Agency",
        ],
        "limit": 100,
        "page": 1,
    }
    d = f.post_json(AWARD_SEARCH, body)
    if d.get("error"):
        return V(
            "UNVERIFIABLE",
            f"USAspending search unreachable: {d['error']}",
            AWARD_SEARCH,
        )
    hits = [
        x for x in d.get("results") or [] if (x.get("Award ID") or "").upper() == aid
    ]
    if (d.get("page_metadata") or {}).get("hasNext"):
        return V(
            "UNVERIFIABLE",
            f"more than 100 awards share id {aid}; refusing to guess",
            AWARD_SEARCH,
        )
    if not hits:
        return V(
            "FALSE",
            f"no contract award with id {aid}",
            AWARD_SEARCH,
            "USAspending: 0 results",
        )
    scored = sorted(
        (
            (name_score(c.get("company", ""), x.get("Recipient Name") or ""), x)
            for x in hits
        ),
        key=lambda t: -t[0],
    )
    sc, hit = scored[0]
    if sc < NAME_MATCH_FLOOR:
        names = "; ".join(sorted({x.get("Recipient Name") or "" for x in hits}))[:250]
        return V(
            "FALSE",
            f"no recipient of {aid} matches company (best {sc})",
            AWARD_SEARCH,
            f"recipients: {names}",
        )
    gid = hit["generated_internal_id"]
    url = AWARD_API.format(gid)
    r = f.get(url)
    if r.get("error") or r["status"] != 200:
        return V(
            "UNVERIFIABLE",
            f"award detail unreachable: {r.get('error') or r['status']}",
            url,
        )
    try:
        det = json.loads(r["text"])
    except json.JSONDecodeError:
        return V("UNVERIFIABLE", "award detail non-JSON", url)
    ag = det.get("awarding_agency") or {}
    top, sub = ag.get("toptier_agency") or {}, ag.get("subtier_agency") or {}
    names = " | ".join(
        x
        for x in [
            top.get("name"),
            top.get("abbreviation"),
            sub.get("name"),
            sub.get("abbreviation"),
            ag.get("office_agency_name"),
        ]
        if x
    )
    signed = det.get("date_signed") or ""
    recip = (det.get("recipient") or {}).get("recipient_name") or hit.get(
        "Recipient Name"
    )
    q = f"recipient '{recip}' | agency '{names}' | date_signed {signed}"
    human = AWARD_HUMAN.format(gid)
    agency = c.get("agency") or ""
    if agency and not find_mention(names, agency_regexes(agency)):
        return V(
            "FALSE", f"awarding agency does not match claimed '{agency}'", human, q
        )
    want = parse_date(c.get("date", ""))
    if c.get("date") and not want:
        return V("UNSUPPORTED", f"date not ISO: {c.get('date')!r}")
    if want and want != signed:
        return V("FALSE", f"date_signed {signed} != claimed {want}", human, q)
    return V("PASS", "USAspending award matches", human, q)


# ============================================================ site checks
def render_home(domain: str, f: Fetcher) -> tuple[dict | None, str]:
    root = site_root(domain)
    if not root:
        return None, "no domain"
    last = ""
    for u in (f"https://{root}/", f"https://www.{root}/", f"http://{root}/"):
        r = f.render([u])[u]
        if r.get("error"):
            last = r["error"]
            continue
        txt = r.get("text") or ""
        if len(txt) < MIN_HOME_TEXT and len(r.get("all_text") or "") < MIN_HOME_TEXT:
            last = f"home text {len(txt)} chars < {MIN_HOME_TEXT}"
            continue
        if BLOCK_MARKERS.search(txt[:600]) and len(txt) < 1500:
            last = "bot wall / block page"
            continue
        return r, ""
    return None, last


def cr_text(s: str) -> str:
    """Like norm_text but keeps the copyright sign (norm_text drops marks)."""
    s = unicodedata.normalize("NFKC", htmllib.unescape(s or ""))
    return re.sub(r"\s+", " ", s).strip()


def check_copyright(c: dict, f: Fetcher) -> dict:
    try:
        year = int(str(c.get("year") or "").strip())
    except ValueError:
        return V("UNSUPPORTED", f"year missing: {c.get('year')!r}")
    home, why = render_home(c.get("domain", ""), f)
    if not home:
        return V("UNVERIFIABLE", f"site unreachable: {why}", c.get("domain", ""))
    url = home.get("final_url") or home["url"]
    best = None
    for src in (
        cr_text(home.get("text") or ""),
        cr_text(home.get("all_text") or ""),
    ):
        for m in re.finditer(
            r"(?:©|&copy;|\(c\)|copyright)[^\n]{0,60}?((?:19|20)\d\d)(?:\s*[-–—]\s*((?:19|20)\d\d))?"
            r"(?![\d])",
            src,
            re.I,
        ):
            yrs = [int(y) for y in m.groups() if y]
            line = quote_at(src, m)
            cand = (max(yrs), line)
            if best is None or cand[0] > best[0]:
                best = cand
    if not best:
        return V("FALSE", "no copyright year found in the rendered page", url)
    if best[0] != year:
        return V(
            "FALSE",
            f"newest copyright year is {best[0]}, claim says {year}",
            url,
            best[1],
        )
    return V("PASS", "rendered copyright year matches", url, best[1])


def check_viewport(c: dict, f: Fetcher) -> dict:
    home, why = render_home(c.get("domain", ""), f)
    if not home:
        return V("UNVERIFIABLE", f"site unreachable: {why}", c.get("domain", ""))
    url = home.get("final_url") or home["url"]
    if home.get("viewport_meta"):
        m = re.search(
            r"<meta[^>]+name=[\"']?viewport[^>]*>", home.get("html") or "", re.I
        )
        return V(
            "FALSE",
            "rendered DOM has a viewport meta tag",
            url,
            m.group(0)[:160] if m else "meta[name=viewport]",
        )
    for ua, label in ((UA, "desktop"), (UA_MOBILE, "mobile")):
        r = f.get(url, ua=ua)
        if r.get("error") or r["status"] >= 400:
            return V(
                "UNVERIFIABLE",
                f"raw HTML ({label} UA) unreachable: {r.get('error') or r['status']}",
                url,
            )
        m = re.search(r"<meta[^>]+name=[\"']?viewport[^>]*>", r["text"], re.I)
        if m:
            return V(
                "FALSE",
                f"raw HTML ({label} UA) has a viewport meta tag",
                r.get("final_url") or url,
                m.group(0)[:160],
            )
    return V(
        "PASS",
        "no viewport meta in rendered DOM or raw HTML (desktop + mobile UA)",
        url,
        "meta[name=viewport]: absent (rendered DOM, raw desktop, raw mobile)",
    )


def sitemap_urls(origin: str, root: str, f: Fetcher) -> list[str]:
    queue = [
        origin + "/sitemap.xml",
        origin + "/sitemap_index.xml",
        origin + "/wp-sitemap.xml",
    ]
    rb = f.get(origin + "/robots.txt")
    if rb.get("status") == 200:
        queue = re.findall(r"(?im)^\s*sitemap:\s*(\S+)", rb.get("text") or "") + queue
    seen, urls = set(), []
    while queue and len(seen) < MAX_SITEMAPS and len(urls) < MAX_SITEMAP_URLS:
        sm = queue.pop(0)
        if sm in seen:
            continue
        seen.add(sm)
        r = f.get(sm)
        if r.get("error") or r["status"] != 200 or "<loc" not in (r.get("text") or ""):
            continue
        for loc in re.findall(r"<loc>\s*(?:<!\[CDATA\[)?\s*([^<\]\s]+)", r["text"]):
            loc = htmllib.unescape(loc)
            if loc.lower().split("?")[0].endswith(".xml"):
                queue.append(loc)
            elif same_site(loc, root):
                urls.append(loc)
    return list(dict.fromkeys(urls))[:MAX_SITEMAP_URLS]


def check_not_mention(c: dict, f: Fetcher, max_pages: int) -> dict:
    product, agency = (c.get("product") or "").strip(), (c.get("agency") or "").strip()
    if product:
        toks = product_needles(product, c.get("company", ""))
        pats = [needle_regex(t) for t in toks]
        label = f"tokens {toks}"
    elif agency:
        pats = agency_regexes(agency)
        label = f"agency patterns {[p.pattern for p in pats][:6]}"
    else:
        return V("UNSUPPORTED", "site_not_mention needs product or agency")
    if not pats:
        return V(
            "UNSUPPORTED",
            f"no distinctive token in '{product or agency}' (only generic words): unprovable",
        )
    home, why = render_home(c.get("domain", ""), f)
    if not home:
        return V("UNVERIFIABLE", f"site unreachable: {why}", c.get("domain", ""))
    home_url = home.get("final_url") or home["url"]
    root = site_root(urllib.parse.urlparse(home_url).netloc) or site_root(
        c.get("domain", "")
    )
    origin = "{0.scheme}://{0.netloc}".format(urllib.parse.urlparse(home_url))

    # 1. home: visible text, hidden menus (textContent), link texts/slugs, image alt/title/src
    links = home.get("links") or []
    surfaces = [
        ("home text", norm_text(home.get("text") or "")),
        ("home menus/hidden text", norm_text(home.get("all_text") or "")),
    ]
    surfaces += [
        (
            "home link",
            norm_text(f"{l.get('text', '')} | {slug_text(l.get('href', ''))}"),
        )
        for l in links
    ]
    surfaces += [
        (
            "home image",
            norm_text(
                f"{i.get('alt', '')} {i.get('title', '')} {slug_text(i.get('src', ''))}"
            ),
        )
        for i in home.get("imgs") or []
    ]
    for where, txt in surfaces:
        if hit := find_mention(txt, pats):
            return V(
                "FALSE",
                f"mentioned on homepage ({where}; pattern {hit[0]})",
                home_url,
                hit[1],
            )

    # 2. sitemap URL slugs are themselves mentions (a /vantage/ page)
    smap = sitemap_urls(origin, root, f)
    for u in smap:
        if hit := find_mention(slug_text(u), pats):
            return V(
                "FALSE",
                f"site has a page named for it (sitemap; pattern {hit[0]})",
                u,
                u,
            )

    # 3. pages: nav/header/footer links first, then other home links, then sitemap pages ranked by slug relevance
    def ok(u: str) -> bool:
        return (
            u.startswith("http")
            and same_site(u, root)
            and not SKIP_EXT.search(u)
            and "#" not in u.split("/")[-1][:1]
        )

    nav = [
        l["href"].split("#")[0]
        for l in links
        if l.get("region") == "navfoot" and ok(l.get("href", ""))
    ]
    body = [
        l["href"].split("#")[0]
        for l in links
        if l.get("region") != "navfoot" and ok(l.get("href", ""))
    ]
    words = {w.lower() for w in re.findall(r"[A-Za-z]{4,}", product or agency)} | {
        "product",
        "products",
        "solutions",
        "news",
        "press",
        "clients",
        "projects",
    }
    smap_rank = sorted(
        (u for u in smap if ok(u)), key=lambda u: -sum(w in u.lower() for w in words)
    )
    pages, seen = [], {home_url.rstrip("/"), origin.rstrip("/")}
    for u in nav + body + smap_rank:
        k = u.rstrip("/")
        if k not in seen:
            seen.add(k)
            pages.append(u)
        if len(pages) >= max_pages - 1:
            break
    fetched, failed = 1, 0
    for u in pages:
        r = f.get(u)
        if r.get("error") or r["status"] >= 400:
            failed += 1
            continue
        fetched += 1
        ex = extract(r["text"])
        txt = norm_text(" ".join(ex.parts))
        extra = [norm_text(f"{i['alt']} {i['title']}") for i in ex.imgs]
        for where, t in [("page text", txt)] + [("page image", e) for e in extra if e]:
            if hit := find_mention(t, pats):
                return V(
                    "FALSE",
                    f"mentioned on a linked page ({where}; pattern {hit[0]})",
                    r.get("final_url") or u,
                    hit[1],
                )
    if fetched < MAX_PAGES_FLOOR:
        return V("UNVERIFIABLE", "no page fetched", home_url)
    return V(
        "PASS",
        "not mentioned on any searched page",
        home_url,
        f"searched {fetched} pages (home + {len(nav)} nav/footer links, {len(smap)} sitemap URLs; "
        f"{failed} failed) for {label}: 0 hits",
    )


# ============================================================ claim-text consistency
def text_consistent(c: dict) -> str:
    """The rendered text must not contradict the structured fields the gate checked. Returns '' or a reason."""
    t = c.get("claim_text") or ""
    for fld in ("k_number", "award_id"):
        v = (c.get(fld) or "").strip()
        ids = re.findall(r"\b(?:K|DEN)\d{6}\b", t) if fld == "k_number" else []
        if v and ids and any(i.upper() != v.upper() for i in ids):
            return f"claim_text names {ids} but {fld} is {v}"
    want = parse_date(c.get("date", ""))
    if want:
        d = dt.date.fromisoformat(want)
        for m in re.finditer(r"\b(" + "|".join(MONTHS) + r")\s+(\d{1,2})\b", t, re.I):
            if (MONTHS.index(m.group(1).lower()) + 1, int(m.group(2))) != (
                d.month,
                d.day,
            ):
                return f"claim_text date '{m.group(0)}' != structured date {want}"
    if c.get("claim_type") == "site_copyright" and c.get("year"):
        ys = re.findall(r"\b(?:19|20)\d\d\b", t)
        if ys and str(c["year"]) not in ys:
            return f"claim_text years {ys} != year {c['year']}"
    return ""


# ============================================================ driver
CHECKS = {
    "fda_clearance": lambda c, f, n: check_fda(c, f),
    "federal_award": lambda c, f, n: check_award(c, f),
    "site_copyright": lambda c, f, n: check_copyright(c, f),
    "site_viewport_missing": lambda c, f, n: check_viewport(c, f),
    "site_not_mention": check_not_mention,
}


def gate_claim(c: dict, f: Fetcher, max_pages: int = 25) -> dict:
    ct = (c.get("claim_type") or "").strip()
    if ct not in CHECKS:
        return V("UNSUPPORTED", f"unknown claim_type {ct!r} (fail closed)")
    if bad := text_consistent(c):
        return V("FALSE", bad, "", c.get("claim_text", "")[:200])
    try:
        return CHECKS[ct](c, f, max_pages)
    except (
        requests.RequestException,
        KeyError,
        ValueError,
        TypeError,
        json.JSONDecodeError,
    ) as e:
        return V("UNVERIFIABLE", f"checker error {type(e).__name__}: {str(e)[:150]}")


def render_rows(passed: list[dict], all_claims: list[dict]) -> list[dict]:
    """A finder row renders only if its trigger claim passed; it carries only passed claim texts."""
    by_row: dict[str, list[dict]] = {}
    for c in passed:
        by_row.setdefault(c.get("row_id") or c["claim_id"], []).append(c)
    rows = []
    for rid, cs in by_row.items():
        trig = [c for c in cs if c["claim_type"] in TRIGGER_TYPES]
        if not trig:
            continue
        rows.append(
            {
                "row_id": rid,
                "company": trig[0]["company"],
                "domain": trig[0]["domain"],
                "trigger": trig[0]["claim_text"],
                "site_facts": " || ".join(
                    c["claim_text"] for c in cs if c["claim_type"] not in TRIGGER_TYPES
                ),
                "claim_ids": ",".join(c["claim_id"] for c in cs),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict], cols: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def run(
    claims: list[dict], out: Path, f: Fetcher, max_pages: int = 25, quiet: bool = False
) -> dict:
    passed, rejected = [], []
    for i, c in enumerate(claims, 1):
        c = {k: (v or "").strip() if isinstance(v, str) else v for k, v in c.items()}
        c.setdefault("claim_id", str(i))
        v = gate_claim(c, f, max_pages)
        row = {**c, **v}
        (passed if v["verdict"] == "PASS" else rejected).append(row)
        if not quiet:
            print(
                f"[{i}/{len(claims)}] {c.get('claim_id')} {c.get('claim_type')} {c.get('domain')}: {v['verdict']} "
                f"- {v['reason'][:110]}",
                flush=True,
            )
    rows = render_rows(passed, claims)
    write_csv(out / "pass.csv", passed, PASS_COLS)
    write_csv(out / "reject.csv", rejected, REJECT_COLS)
    write_csv(
        out / "rows.csv",
        rows,
        ["row_id", "company", "domain", "trigger", "site_facts", "claim_ids"],
    )
    counts: dict[str, int] = {}
    for r in passed + rejected:
        counts[r["verdict"]] = counts.get(r["verdict"], 0) + 1
    by_type: dict[str, dict] = {}
    for r in passed + rejected:
        b = by_type.setdefault(r.get("claim_type", ""), {})
        b[r["verdict"]] = b.get(r["verdict"], 0) + 1
    summary = {
        "claims": len(claims),
        "verdicts": counts,
        "by_type": by_type,
        "rows_rendered": len(rows),
        "rows_in": len({c.get("row_id") or c.get("claim_id") for c in claims}),
        "ran_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
    }
    (out / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    return summary


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[1])
    ap.add_argument("--claims", required=True, help="input claims CSV")
    ap.add_argument("--out", default=str(ROOT / ".tmp/fact_gate/out"))
    ap.add_argument(
        "--limit", type=int, default=0, help="gate only the first N claims (0 = all)"
    )
    ap.add_argument(
        "--max-pages",
        type=int,
        default=25,
        help=f"pages per site for site_not_mention "
        f"[{MAX_PAGES_FLOOR}..{MAX_PAGES_CEILING}]",
    )
    ap.add_argument("--refresh", action="store_true", help="ignore the fetch cache")
    ap.add_argument(
        "--offline",
        action="store_true",
        help="cache only; uncached fetches become UNVERIFIABLE",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="no-op flag kept for the build contract (gate is read-only)",
    )
    a = ap.parse_args(argv)
    if not MAX_PAGES_FLOOR <= a.max_pages <= MAX_PAGES_CEILING:
        ap.error(f"--max-pages must be in [{MAX_PAGES_FLOOR}, {MAX_PAGES_CEILING}]")
    with open(a.claims, newline="", encoding="utf-8") as fh:
        claims = list(csv.DictReader(fh))
    if a.limit:
        claims = claims[: a.limit]
    if not claims:
        print("no claims: nothing to do")
        return 0
    s = run(claims, Path(a.out), Fetcher(a.refresh, a.offline), a.max_pages)
    print(json.dumps(s, indent=2))
    n, unv = s["claims"], s["verdicts"].get("UNVERIFIABLE", 0)
    if n >= REJECT_RATE_ALARM_MIN_N and unv / n > UNVERIFIABLE_CEILING:
        print(
            f"ALARM: {unv}/{n} UNVERIFIABLE > {UNVERIFIABLE_CEILING:.0%}: fetch layer likely broken",
            file=sys.stderr,
        )
        return 2
    if n >= REJECT_RATE_ALARM_MIN_N and s["verdicts"].get("PASS", 0) == n:
        print(
            f"ALARM: 0 of {n} claims rejected; a gate that drops nothing is not gating",
            file=sys.stderr,
        )
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main())
