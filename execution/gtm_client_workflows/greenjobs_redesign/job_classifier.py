"""Derived fields for any canonical GreenJobs job: sectors (+ confidence), regions, job type, workplace, contract tags.

description: One classifier for every source that writes D1 (Gaia feed, Strategies import, later feeds). It
    imports build_site.py's own functions (assign_sectors, loc_class, resolve_regions, workplace_of,
    contract_of, canon_type) so the D1 rows carry exactly what the static boards show, and adds a sector
    confidence. A sector the classifier is not sure of is never guessed: the result carries
    needs_review=True plus suggested sectors, and the caller queues it (job_review) instead of publishing.
    Vocabulary: the frozen taxonomy (platform_worker/src/taxonomy.json) when present, else build_site.TAXONOMY
    (marked not frozen; eval_report.md: until the taxonomy is frozen, a feed sector goes to review).
    Jev is optional (gaia_feed_sync.Jev, cached, fail open to the queue): asked only for a low-confidence
    sector, never trusted below the cut.
inputs: a job dict with any of: title, employer, location, region, country, summary, description_html or
    description (plain), job_type/type, source_sectors (the source's own labels); site 'ie'|'uk';
    optional hint {sectors: [...], confidence, method} from an upstream mapping (Gaia dictionary / Jev).
outputs: dict (see classify()). Pure: no network unless a Jev object with a key is passed, no file writes.
CLI (smoke test): python3 job_classifier.py --site ie --title "Senior Ecologist" --location Cork
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import sys
from functools import lru_cache
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import build_site as bs  # noqa: E402  (the vocabulary and every rule live there; imported, never copied)

CLASSIFIER_VERSION = "2026-11-20.1"
TAXONOMY_PATH = HERE / "platform_worker" / "src" / "taxonomy.json"
SRC_DIR = ROOT / "deliverables" / bs.PROJECT / "src"
SECTOR_CUT = 0.6  # same cut as gaia_feed_sync / eval_report.md
MAX_SECTORS = 3
FALLBACK_SECTOR = (
    "Environmental science & consulting"  # assign_sectors' answer when nothing scores
)


class TaxonomyError(ValueError):
    pass


class Taxonomy:
    """The sector vocabulary plus an alias map (lower-case alias -> canonical name)."""

    def __init__(
        self,
        sectors: list[str],
        aliases: dict[str, str],
        version: str,
        frozen: bool,
        path: str | None,
        number: int | None = None,
    ):
        self.number = number  # taxonomy.json "version" (int) -> job_facets.taxonomy_version; None = not that file's shape
        self.sectors = sectors
        self.aliases = aliases
        self.version = version
        self.frozen = frozen
        self.path = path

    def canon(self, name: str | None) -> str | None:
        if not name:
            return None
        return self.aliases.get(html.unescape(str(name)).strip().lower())


def _builtin() -> Taxonomy:
    names = [t[0] for t in bs.TAXONOMY]
    digest = hashlib.sha256(json.dumps(names).encode()).hexdigest()[:12]
    return Taxonomy(
        names, {n.lower(): n for n in names}, f"build_site-{digest}", False, None,
        int(bs.FROZEN_TAXONOMY["version"]),
    )


def load_taxonomy(path: Path | None = TAXONOMY_PATH) -> Taxonomy:
    """Frozen taxonomy if the file exists, else build_site.TAXONOMY (frozen=False).

    Tolerant of the shape: {"version", "frozen"?, "sectors": [name | {name|label|value, aliases|legacy|from|
    keywords: [...]}]}. Every build_site sector name that is not itself in the frozen list must be reachable
    through an alias, or it is simply not offered (the job then goes to review, never to a stray sector).
    A present but malformed file is an error (fail loud: a broken vocabulary must not mis-sector jobs).
    """
    if path is None or not Path(path).exists():
        return _builtin()
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise TaxonomyError(f"taxonomy {path}: unreadable ({e})") from e
    raw = data.get("sectors") if isinstance(data, dict) else None
    if not isinstance(raw, list) or not raw:
        raise TaxonomyError(f"taxonomy {path}: no 'sectors' list")
    sectors: list[str] = []
    aliases: dict[str, str] = {}
    for item in raw:
        if isinstance(item, str):
            name, alts = item, []
        elif isinstance(item, dict):
            name = item.get("name") or item.get("label") or item.get("value")
            alts = []
            for k in ("aliases", "legacy", "from", "keywords", "maps_from"):
                v = item.get(k)
                if isinstance(v, list):
                    alts += [str(x) for x in v]
        else:
            raise TaxonomyError(f"taxonomy {path}: bad sector entry {item!r:.60}")
        if not isinstance(name, str) or not 1 <= len(name.strip()) <= 80:
            raise TaxonomyError(f"taxonomy {path}: sector name missing or too long")
        name = name.strip()
        if name in sectors:
            raise TaxonomyError(f"taxonomy {path}: duplicate sector {name!r}")
        sectors.append(name)
        aliases.setdefault(name.lower(), name)
        for a in alts:
            aliases.setdefault(a.strip().lower(), name)
    version = (
        str(data.get("version") or "")
        or hashlib.sha256(Path(path).read_bytes()).hexdigest()[:12]
    )
    raw_v = data.get("version")
    number = raw_v if isinstance(raw_v, int) and not isinstance(raw_v, bool) and raw_v >= 1 else None
    return Taxonomy(
        sectors,
        aliases,
        f"frozen-{version}"[:64],
        bool(data.get("frozen", True)),
        str(path),
        number,
    )


def canonical_taxonomy() -> Taxonomy:
    """taxonomy.json, the one vocabulary every D1 writer uses (build_site.py loads the same file)."""
    return load_taxonomy(TAXONOMY_PATH)


def assert_canonical(tax: Taxonomy) -> None:
    """Fail loud when a D1 writer was handed a vocabulary other than taxonomy.json: job_facets rows must be
    written with the vocabulary the Worker renders and validates with (one source of truth)."""
    want = [s["name"] for s in bs.FROZEN_TAXONOMY["sectors"]]
    if tax.number != int(bs.FROZEN_TAXONOMY["version"]) or tax.sectors != want:
        raise TaxonomyError(
            f"taxonomy {tax.path or 'built-in'} is not platform_worker/src/taxonomy.json "
            f"(version {tax.number!r} vs {bs.FROZEN_TAXONOMY['version']}): D1 facets are written with taxonomy.json only"
        )


# ------------------------------------------------------------------ build_site adapters


@lru_cache(maxsize=None)
def _places() -> tuple[list[str], list[str], list[str]]:
    ie, uk = bs.place_words(SRC_DIR)
    return ie, uk, bs.ni_place_words(SRC_DIR)


@lru_cache(maxsize=None)
def _region_table(site: str) -> dict[str, Any]:
    return bs.load_region_table(SRC_DIR, site)


def to_board_job(job: dict[str, Any]) -> dict[str, Any]:
    """The dict shape build_site's functions read."""
    desc = job.get("description_html")
    if not desc:
        desc = html.escape(str(job.get("description") or ""))
    return {
        "title": str(job.get("title") or ""),
        "employer": str(job.get("employer") or ""),
        "location": str(job.get("location") or ""),
        "region": str(job.get("region") or ""),
        "country": str(job.get("country") or ""),
        "summary": str(job.get("summary") or ""),
        "description_html": str(desc),
        "type": str(job.get("job_type") or job.get("type") or ""),
        "sectors": [str(s) for s in (job.get("source_sectors") or [])],
    }


def sector_scores(bj: dict[str, Any]) -> list[tuple[str, int]]:
    """Every sector's assign_sectors score (same weights, same word matcher), best first, ties as assign_sectors."""
    raw = " ".join(bj.get("sectors") or []).lower()
    title, employer, summary = (
        bj["title"].lower(),
        bj["employer"].lower(),
        bj["summary"].lower(),
    )
    body = bs.strip_tags(bj["description_html"])[:3000].lower()
    w = bs.SECTOR_W
    rows = []
    for pos, (name, _c, _d, words) in enumerate(bs.TAXONOMY):
        rh = bs._word_hits(raw, words)
        score = (
            w["raw"] * rh
            + w["title"] * bs._word_hits(title, words, 2)
            + w["employer"] * bs._word_hits(employer, words, 2)
            + w["summary"] * bs._word_hits(summary, words, 2)
            + w["body"] * bs._word_hits(body, words)
        )
        rows.append((-score, -rh, pos, name))
    rows.sort()
    return [(name, -neg) for neg, _rh, _p, name in rows]


def keyword_confidence(bj: dict[str, Any], sectors: list[str]) -> tuple[float, str]:
    """(confidence 0..1, method). 0.0 when nothing reached PRIMARY_MIN (assign_sectors' fallback guess).
    Otherwise 0.45 base, +0.30 when the title names the sector, +0.25 x the margin over the runner-up.
    """
    scores = sector_scores(bj)
    top_name, top = scores[0]
    if top < bs.PRIMARY_MIN:
        return 0.0, "fallback"
    primary = sectors[0] if sectors else top_name
    p_score = dict(scores).get(primary, top)
    rivals = [s for n, s in scores if n != primary]
    second = rivals[0] if rivals else 0
    margin = max(0.0, (p_score - second) / p_score) if p_score else 0.0
    title_hit = bs._title_hit(primary, bj["title"].lower())
    conf = 0.45 + (0.30 if title_hit else 0.0) + 0.25 * margin
    return round(min(1.0, conf), 3), "keyword"


def job_type_of(bj: dict[str, Any], contract: list[str]) -> str | None:
    raw = bj.get("type") or ""
    if raw.strip():
        return bs.canon_type(raw)[:40]
    if "permanent" in contract:
        return "Permanent"
    if "contract" in contract or "fixed-term" in contract:
        return "Contract"
    if "part-time" in contract:
        return "Part-time"
    return None


# ------------------------------------------------------------------ classify


def _jev_sector(jev: Any, bj: dict[str, Any], cut: float) -> tuple[str | None, float]:
    """Ask Jev once (gaia_feed_sync.Jev: cached, ledgered). Any failure -> (None, 0.0) = stays queued."""
    try:
        import gaia_feed_sync as gfs

        state = {
            "title": bj["title"],
            "employer": bj["employer"] or "unknown",
            "opening": bs.strip_tags(bj["description_html"])[:600],
        }
        ans = jev.ask_many([(state, gfs.sector_question())])[0]
        if not ans:
            return None, 0.0
        a = ans.get("sector") or {}
        choice, conf = str(a.get("choice", "")), float(a.get("confidence", 0.0) or 0.0)
        name = next((n for n, *_ in bs.TAXONOMY if gfs._slug(n) == choice), None)
        return (name, conf) if name and conf >= cut else (None, conf)
    except (
        Exception
    ) as e:  # noqa: BLE001  helper degrades open: the job is queued, never guessed
        print(
            f"job_classifier: Jev sector call failed ({type(e).__name__}); job stays queued",
            file=sys.stderr,
        )
        return None, 0.0


def classify(
    job: dict[str, Any],
    site: str,
    taxonomy: Taxonomy | None = None,
    *,
    hint: dict | None = None,
    cut: float = SECTOR_CUT,
    require_frozen: bool = True,
    jev: Any = None,
) -> dict[str, Any]:
    """Derived fields for one job. Never raises on odd text; raises ValueError on a bad site."""
    if site not in bs.EDITIONS:
        raise ValueError(f"site must be ie|uk, got {site!r}")
    tax = taxonomy or load_taxonomy()
    bj = to_board_job(job)

    kw = bs.assign_sectors(bj)
    conf, method = keyword_confidence(bj, kw)
    reasons: list[str] = []
    sectors = list(kw)

    # Upstream hint (Gaia dictionary/Jev mapping, or Strategies' own label mapped through the taxonomy)
    h_names = [n for n in ((hint or {}).get("sectors") or []) if n]
    h_conf = float((hint or {}).get("confidence") or 0.0)
    h_method = (hint or {}).get("method")
    if h_names and h_method != "queue" and h_conf >= cut:
        h = h_names[0]
        if method == "fallback":
            sectors, conf, method = [h], round(h_conf, 3), "source"
        elif h in kw:
            sectors = [h] + [s for s in kw if s != h]
            conf, method = max(conf, 0.9), "source+keyword"
        elif h in bs.ENERGY_FAMILY and kw[0] in bs.ENERGY_FAMILY:
            # an umbrella energy label ("Renewable energy") on a solar/wind advert: same family, keep the
            # specific sector the text names first (build_site keeps the family together the same way)
            sectors = kw + [h]
            conf, method = max(conf, 0.85), "source+keyword"
        else:
            reasons.append(f"source label says {h!r}, text says {kw[0]!r}")
            sectors, conf, method = [h] + kw, min(conf, 0.5), "conflict"
    elif h_method == "queue":
        reasons.append("upstream mapping queued the sector")

    if conf < cut and method != "conflict" and jev is not None:
        name, jconf = _jev_sector(jev, bj, cut)
        if name:
            sectors = [name] + ([s for s in sectors if s != name] if method != "fallback" else [])
            conf, method = round(jconf, 3), "jev"

    if conf < cut and not reasons:
        reasons.append(
            "no sector keyword in the advert"
            if method == "fallback"
            else f"sector confidence {conf} below cut {cut}"
        )

    # Map onto the vocabulary in force; anything it does not hold is dropped, an unmappable primary is reviewed
    mapped: list[str] = []
    for s in sectors:
        c = tax.canon(s)
        if c and c not in mapped:
            mapped.append(c)
    if sectors and (not mapped or tax.canon(sectors[0]) is None):
        reasons.append(f"{sectors[0]!r} is not in the frozen taxonomy")
    if require_frozen and not tax.frozen:
        reasons.append(
            "taxonomy not frozen (eval_report.md: every feed sector is reviewed until it is)"
        )

    contract = bs.contract_of(bj)
    ie, uk, ni = _places()
    lc = bs.loc_class(bj, ie, uk, site, ni)
    regions = bs.resolve_regions(bj, _region_table(site), bs.EDITIONS[site])
    needs_review = bool(reasons) or conf < cut
    return {
        "sectors": mapped[:MAX_SECTORS] if not needs_review else [],
        "suggested_sectors": mapped[:MAX_SECTORS],
        "sector_confidence": round(float(conf), 3),
        "sector_method": method,
        "needs_review": needs_review,
        "review_reason": "; ".join(reasons)[:300] if needs_review else None,
        "region": regions[0] if regions else None,
        "regions": regions,
        "loc_class": lc,
        "job_type": job_type_of(bj, contract),
        "workplace": bs.workplace_of(bj),
        "contract": contract,
        "source_sectors": [str(s) for s in (job.get("source_sectors") or [])][:20],
        "taxonomy_version": tax.version,
        "taxonomy_number": tax.number,
        "taxonomy_frozen": tax.frozen,
        "classifier_version": CLASSIFIER_VERSION,
    }


# Eye review r3 R3-7: an advert whose text sends applicants to an external form / ATS while the job applies by email
# (the on-page GreenJobs form) is queued for staff. The mode is never changed here: staff decide. Only phrases that
# name an off-site route count ("click apply" alone is the on-page button, never flagged). Every flag quotes its sentence.
EXTERNAL_APPLY_RES = [
    re.compile(r"\b(?:you will|you'll|applicants will|candidates will) be (?:taken|redirected|directed|forwarded|sent) to\b", re.I),
    re.compile(r"\bredirected to complete\b", re.I),
    re.compile(r"\bto apply\b[^.]{0,60}?\b(?:visit|go to|see) (?:our|the) (?:website|careers|portal|site|recruitment)", re.I),
    re.compile(r"\b(?:visit|go to) (?:our|the) (?:website|careers site|careers page|portal)\b[^.]{0,40}?\bto apply\b", re.I),
    re.compile(r"\bapply online\b\s*(?:at|via|:)\s*(?:www\.|https?://)", re.I),
    re.compile(r"\bapply (?:via|through|using|on) (?:the|our) (?:link|website|portal|online (?:form|system|portal)|careers (?:site|page))\b", re.I),
    re.compile(r"\b(?:on|via) the link below\b", re.I),
    re.compile(r"\b(?:applicant tracking system|our ATS)\b|myworkdayjobs\.com|taleo\.net|smartrecruiters\.com|icims\.com|applytojob\.com", re.I),
]
EXTERNAL_APPLY_ANY = re.compile("|".join(f"(?:{r.pattern})" for r in EXTERNAL_APPLY_RES), re.I)
_SENTENCE_RE = re.compile(r"[^.!?\n]*[.!?]?")


def _plain_text(markup: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", str(markup or "")))).strip()


def external_apply_evidence(description: str) -> str | None:
    """The first sentence of the advert that names an off-site application route, or None."""
    text = _plain_text(description)
    for m in _SENTENCE_RE.finditer(text):
        sent = m.group(0).strip()
        if sent and any(r.search(sent) for r in EXTERNAL_APPLY_RES):
            return sent[:100]
    return None


def apply_route_review_reason(description: str, apply_mode: str | None) -> str | None:
    """Review reason when an email-mode job's own text sends applicants elsewhere (R3-7), else None."""
    if (apply_mode or "email") not in ("email", "", None):
        return None
    ev = external_apply_evidence(description)
    return f'apply route: advert says "{ev}" but the job applies by email here; confirm the mode'[:150] if ev else None


def extra_review_reasons(job: dict[str, Any]) -> list[str]:
    """Non-sector reasons to queue a job for staff (job_review, hold 0: the job stays live): R3-7 and r3 m3."""
    out = []
    r = apply_route_review_reason(job.get("description") or job.get("description_html") or "", job.get("apply_mode"))
    if r:
        out.append(r)
    loc = bs.location_review_reason(job.get("location") or "")
    if loc:
        out.append(loc)
    return out


def facet_row(job: dict[str, Any], site: str, c: dict[str, Any], set_by: str) -> dict[str, Any]:
    """The job_facets row (migration 0002) for one classified job: the classifier's taxonomy fields plus the
    display fields build_site.normalise() derives (level, agency, salary label, unverified-currency flag,
    search text). Params order = upserts_0003.sql job_facets_upsert, see facet_params().

    job: title, employer, description_html | description, sal_min, sal_max, currency, period, sal_text.
    Sectors: the confident sectors, else the suggestion (a held feed job is draft and never shown; a queued
    Strategies job stays live with its best guess until staff decide, exactly as jobs.sectors_json).
    """
    if set_by not in ("import", "feed"):
        raise ValueError("set_by must be import|feed (console rows are written by the Worker)")
    if c.get("taxonomy_number") is None:
        raise TaxonomyError("facets need taxonomy.json's integer version (job_facets.taxonomy_version)")
    bj = to_board_job(job)
    lo = job.get("sal_min") if isinstance(job.get("sal_min"), (int, float)) else None
    hi = job.get("sal_max") if isinstance(job.get("sal_max"), (int, float)) else None
    cur = job.get("currency") or None
    sal = {"sal_min": lo, "sal_max": hi, "cur": cur, "period": job.get("period") or None,
           "sal_text": str(job.get("sal_text") or "")}
    lc = c.get("loc_class") or "unspecified"
    unverified = int(site == "ie" and lc == "uk" and cur == "EUR" and (lo is not None or hi is not None))
    text = bs.strip_tags(bs.sanitise_html(bj["description_html"], "https://greenjobs.invalid/"))[:1500]
    sectors = (c.get("sectors") or c.get("suggested_sectors") or [])[:MAX_SECTORS]
    return {
        "sectors": sectors,
        "regions": list(c.get("regions") or [])[:10],
        "job_type": c.get("job_type"),
        "workplace": c.get("workplace") or "unspecified",
        "contract": list(c.get("contract") or []),
        "loc_class": lc,
        "level": bs.level_of(bj["title"]) or None,
        "is_agency": int(bool(bs.is_agency(bj["employer"]))),
        "salary_display": bs.salary_label(sal, bs.EDITIONS[site]["currency"]) or None,
        "unverified_cur": unverified,
        "taxonomy_version": int(c["taxonomy_number"]),
        "set_by": set_by,
        "search_text": text or None,
        "source_sectors": list(c.get("source_sectors") or [])[:20],
        "sector_confidence": float(c.get("sector_confidence") or 0.0),
        "sector_method": str(c.get("sector_method") or "keyword")[:40],
    }


def facet_params(job_id: str, f: dict[str, Any], now: str) -> list[Any]:
    """?1..?18 of upserts_0003.sql job_facets_upsert (= sql_0003.js JOB_FACETS_UPSERT)."""
    def dumps(v: Any) -> str:
        return json.dumps(v, ensure_ascii=False, separators=(",", ":"))
    return [job_id, dumps(f["sectors"]), dumps(f["regions"]), f["job_type"], f["workplace"], dumps(f["contract"]),
            f["loc_class"], f["level"], f["is_agency"], f["salary_display"], f["unverified_cur"], f["taxonomy_version"],
            f["set_by"], now, f["search_text"], dumps(f["source_sectors"]), f["sector_confidence"], f["sector_method"]]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--site", choices=["ie", "uk"], required=True)
    ap.add_argument("--title", required=True)
    ap.add_argument("--location", default="")
    ap.add_argument("--description", default="")
    ap.add_argument("--type", default="")
    ap.add_argument("--taxonomy", default=str(TAXONOMY_PATH))
    a = ap.parse_args(argv)
    try:
        tax = load_taxonomy(Path(a.taxonomy))
    except TaxonomyError as e:
        print(json.dumps({"error": str(e)}))
        return 2
    out = classify(
        {
            "title": a.title,
            "location": a.location,
            "description": a.description,
            "job_type": a.type,
        },
        a.site,
        tax,
        require_frozen=False,
    )
    print(json.dumps(out, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
