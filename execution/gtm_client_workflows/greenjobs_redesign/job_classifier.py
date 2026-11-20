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
    ):
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
        names, {n.lower(): n for n in names}, f"build_site-{digest}", False, None
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
    return Taxonomy(
        sectors,
        aliases,
        f"frozen-{version}"[:64],
        bool(data.get("frozen", True)),
        str(path),
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
        "taxonomy_frozen": tax.frozen,
        "classifier_version": CLASSIFIER_VERSION,
    }


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
