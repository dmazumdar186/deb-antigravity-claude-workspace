"""GreenJobs STAGING seed: current public jobs for D1 and the static boards, from ONE normalised job set.

description: Fixes the 2026-11-20 eye review (B1, B2, B3, M1, M4, M6). The old seed (release.py build_seed_sql) wrote
    the 22 Sep snapshot to D1 with closing_at NULL, posted_at = the seed time and only edition-currency salaries,
    while the static boards rendered the same file with its real dates: lists said "live", job pages said "closed",
    every card said "Today" and the explorer lost most salaries. Here both outputs come from build_site.normalise()
    of one dataset, so the static fallback equals the D1 live set at build time:
      1. Current public jobs: the Gaia Talent feed (gaia_feed_sync.py feed.json, real posted dates, apply on
         gaiatalent.com), records with status 'ready' only (the D1 sync holds the rest for review).
      2. Volume for filters and charts: the September board jobs with posted and closing dates moved forward by
         (seed date - snapshot date), so the board reads as it did on the snapshot day, every title prefixed
         "[Test data] ", the dataset flagged test_data (build_site refuses a production build of it) and
         created_by 'staging-seed-test'. Roles already closed on the snapshot stay out.
    Old-platform apply URLs (*.asp, strategies hosts) become email mode (site default inbox; no address is seeded).
inputs: --env staging (anything else refuses), --seed-date YYYY-MM-DD (default: today UTC), --gaia-feed PATH
    (optional; without it only the re-based test data is seeded), --september-dir DIR (default src/data),
    --out DIR (default .tmp/staging_seed; must be under the repo's .tmp/ or deliverables/).
outputs: {out}/data/{ie,uk}.json (build_site.py --data-dir {out}/data --today <seed date>), {out}/seed.sql
    (wrangler d1 execute --file; idempotent upserts + closes earlier seed rows no longer in the set),
    {out}/manifest.json (counts per site and source). Byte-identical on a re-run with the same inputs.
CLI:
  python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_feed_sync.py --no-jev --out .tmp/gaia_feed
  python3 execution/gtm_client_workflows/greenjobs_redesign/staging_seed.py --env staging \\
      --gaia-feed .tmp/gaia_feed/feed.json --out .tmp/staging_seed
Directive: directives/gtm_client_workflows/staging_seed.md
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import build_site as bs  # noqa: E402
import job_classifier as jc  # noqa: E402

SRC = ROOT / "deliverables" / "greenjobs_redesign_2026-09-22" / "src"
TEST_PREFIX = "[Test data] "
GAIA_EMPLOYER = "Gaia Talent"
CREATED_BY = {"gaia": "staging-seed", "test": "staging-seed-test"}
SEED_TABLES = ("employers", "jobs", "job_facets")
_PII_COLS = re.compile(
    r"\b(contact_email|contact_name|phone|candidate\w*|application\w*)\b"
)


class SeedError(RuntimeError):
    pass


# ── the dataset (raw scrape shape, read by build_site.normalise) ─────────────


def _shift(raw_date: Any, delta: timedelta) -> str:
    d = bs.parse_date(raw_date)
    return (date.fromisoformat(d) + delta).isoformat() if d else ""


_MONTH = r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
# A calendar date in advert prose: "19th October 2026", "5 October", "October 19, 2026", "October 2026", "19/10/2026".
DATE_IN_TEXT = re.compile(
    rf"\b\d{{1,2}}(?:st|nd|rd|th)?(?:\s+of)?\s+{_MONTH}\b\.?(?:,?\s+\d{{4}})?"
    rf"|\b{_MONTH}\s+\d{{1,2}}(?:st|nd|rd|th)?\b(?:,?\s+\d{{4}})?"
    rf"|\b{_MONTH}\s+\d{{4}}\b"
    r"|\b\d{1,2}[/.]\d{1,2}[/.]\d{2,4}\b",
    re.I,
)
# an innermost block: no other block tag inside it
_BLOCK = re.compile(r"(<(p|li|div|h[1-6])\b[^>]*>)((?:(?!</?(?:p|li|div|h[1-6]|ul|ol|table)\b).)*?)(</\2>)", re.S | re.I)
_SENTENCE_SPLIT = re.compile(r"(?<=[.!?])\s+")
_BR = re.compile(r"(<br\s*/?>)", re.I)


def _plain(x: str) -> str:
    return re.sub(r"<[^>]+>", " ", x)


def _strip_line(seg: str, rx: re.Pattern[str] = DATE_IN_TEXT) -> str:
    """One line of text (between <br>s): a short line matching rx goes; a long one loses its matching sentences."""
    if not rx.search(_plain(seg)):
        return seg
    if len(_plain(seg).strip()) < 160:
        return ""
    return " ".join(x for x in _SENTENCE_SPLIT.split(seg) if not rx.search(_plain(x)))


def _strip_lines(inner: str, rx: re.Pattern[str] = DATE_IN_TEXT) -> str:
    return "".join(part if _BR.fullmatch(part) else _strip_line(part, rx) for part in _BR.split(inner))


def strip_external_apply_sentences(markup: str) -> str:
    """Test data only (eye review r3 R3-7): the seed turns every old-platform apply URL into email mode (the on-page
    form), so a September advert that says "You will be taken to a simple CHM Recruit form" would contradict the
    page. Those sentences go (same block / line rules as the dates). Real imports never strip: they queue the job
    for staff (job_classifier.apply_route_review_reason). Idempotent."""
    return strip_date_sentences(markup, jc.EXTERNAL_APPLY_ANY)


def strip_date_sentences(markup: str, rx: re.Pattern[str] = DATE_IN_TEXT) -> str:
    """Test data only (eye review r2 N8): the September adverts quote their own deadlines and start dates
    ("Closing date: 23:59, Monday, 19th October 2026"), which contradict the re-based dates in the page header.
    Per innermost block and per <br> line: a short line that names a calendar date goes whole (a "Closing date:"
    fact), a long one loses only the sentences that name one, and a block left without text goes. Idempotent."""
    def block(m: re.Match[str]) -> str:
        open_, inner, close = m.group(1), m.group(3), m.group(4)
        if not rx.search(_plain(inner)):
            return m.group(0)
        kept = _strip_lines(inner, rx)
        return f"{open_}{kept}{close}" if _plain(kept).strip() else ""
    out = _BLOCK.sub(block, markup or "")
    if rx.search(_plain(out)):  # text outside any block (a bare <br>-separated advert)
        out = _strip_lines(out, rx)
    return out


def rebase_september(raw: dict[str, Any], seed_date: date) -> list[dict[str, Any]]:
    """The September jobs as test data: dates moved by (seed_date - fetched), titles flagged, snapshot-closed out."""
    fetched = date.fromisoformat(str(raw.get("fetched"))[:10])
    delta = seed_date - fetched
    out = []
    for j in raw.get("jobs") or []:
        closing = bs.parse_date(j.get("closing"))
        if closing and closing < fetched.isoformat():
            continue  # already closed on the snapshot day: never re-opened by the shift
        title = str(j.get("title") or "").strip()
        out.append(
            {
                **j,
                "title": (TEST_PREFIX + title)[:160],
                # the advert's own dates would contradict the shifted header dates (eye review r2 N8)
                "description_html": strip_external_apply_sentences(strip_date_sentences(str(j.get("description_html") or ""))),
                "summary": " ".join(x for x in _SENTENCE_SPLIT.split(str(j.get("summary") or "")) if not DATE_IN_TEXT.search(x)),
                "posted": _shift(j.get("posted"), delta),
                "closing": _shift(j.get("closing"), delta),
                "seed_source": "test",
            }
        )
    return out


def gaia_jobs(feed: dict[str, Any], site: str) -> list[dict[str, Any]]:
    """Gaia feed records (status 'ready', on this board) in the scrape shape; ids 'gaia-<wp id>' = the Worker slug."""
    out = []
    for r in feed.get("jobs") or []:
        if r.get("status") != "ready" or site not in (r.get("boards") or []):
            continue
        wp = str(r.get("source_id") or "").split(":", 1)[-1]
        if not re.fullmatch(r"[0-9]{1,12}", wp):
            continue
        apply = r.get("apply") or {}
        url = str(apply.get("url") or r.get("url") or "")
        mode = (
            "link"
            if apply.get("method") == "url"
            and url.startswith("https://")
            and not bs.is_old_platform_url(url)
            else "email"
        )
        out.append(
            {
                "id": f"gaia-{wp}",
                "slug": bs.slugify(r.get("title") or ""),
                "title": str(r.get("title") or "").strip()[:160],
                "url": str(r.get("url") or ""),
                "employer": GAIA_EMPLOYER,
                "location": str(r.get("location") or r.get("region") or ""),
                "region": str(r.get("region") or ""),
                "country": "Ireland" if site == "ie" else "United Kingdom",
                "type": str(r.get("job_type") or ""),
                "salary_text": str(r.get("salary_text") or ""),
                "posted": bs.parse_date(r.get("posted_at")),
                "closing": bs.parse_date(r.get("expires_at")),
                "summary": "",
                "description_html": str(r.get("description_html") or ""),
                "apply_mode": mode,
                "apply_url": url if mode == "link" else "",
                "seed_source": "gaia",
            }
        )
    return out


def build_datasets(
    seed_date: date, september_dir: Path, gaia_feed: dict[str, Any] | None
) -> dict[str, dict[str, Any]]:
    """{site: raw dataset} with fetched = the seed date; Gaia jobs first, then the flagged test data."""
    out = {}
    for site in ("ie", "uk"):
        raw = json.loads((september_dir / f"{site}.json").read_text(encoding="utf-8"))
        jobs = (gaia_jobs(gaia_feed, site) if gaia_feed else []) + rebase_september(
            raw, seed_date
        )
        out[site] = {
            **raw,
            "fetched": seed_date.isoformat(),
            "jobs": jobs,
            "test_data": True,
            "seed_note": "STAGING ONLY: Gaia Talent feed jobs plus September board jobs re-based to the seed date "
            "and flagged [Test data]. Never a production dataset.",
        }
    return out


# ── D1 rows from the normalised jobs (the static board renders the very same dicts) ─


def d1_id(site: str, jid: str) -> tuple[str, str]:
    """(D1 id, source_id) for a normalised job id; the Worker's slugOf(id) gives the static page's id back."""
    if re.fullmatch(r"[0-9]{1,20}", jid):
        return f"{site}:strat:{jid}", f"seed:{jid}"
    m = re.fullmatch(r"gaia-([0-9]{1,12})", jid)
    if m:
        return f"{site}:gaia:{m.group(1)}", f"gaia:{m.group(1)}"
    raise SeedError(
        f"job id {jid!r} has no Worker slug (only Strategies digits and gaia-<n> are served)"
    )


def _q(v: Any) -> str:
    if v is None:
        return "NULL"
    if isinstance(v, bool):
        return "1" if v else "0"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return repr(v)
    return (
        "'" + " ".join(str(v).split()).replace("'", "''") + "'"
    )  # one statement per line (seed invariant)


def _int(v: Any) -> int | None:
    return int(v) if isinstance(v, (int, float)) and v >= 0 else None


def _norm(name: str) -> str:
    s = re.sub(r"[^a-z0-9 ]", " ", name.lower())
    return " ".join(re.sub(r"\b(ltd|limited|plc)\b", " ", s).split())


def job_rows(
    site: str, data: dict[str, Any], tax_number: int, as_of: str
) -> tuple[list[dict], list[dict], list[tuple]]:
    """(employers, jobs, facets) for one normalised edition."""
    emps: dict[str, dict] = {}
    jobs, facets = [], []
    for j in data["jobs"]:
        jid, source_id = d1_id(site, j["id"])
        src = j.get("seed_source") or (
            "gaia" if j["id"].startswith("gaia-") else "test"
        )
        emp = j["employer"][:200]
        emp_id = (
            f"{site}:seed-emp-{_norm(emp).replace(' ', '-')[:80] or 'confidential'}"
        )
        e = emps.setdefault(
            emp_id,
            {
                "id": emp_id,
                "site": site,
                "source": "feed",
                "source_id": "seed-emp:" + _norm(emp),
                "name": emp,
                "name_norm": _norm(emp),
                "logo_key": None,
                "created_at": as_of,
                "updated_at": as_of,
            },
        )
        if j.get("logo") and not e["logo_key"]:
            e["logo_key"] = (
                f"seed/{j['logo']}"  # counts as "has a logo" (listing quality) like the static board's file
            )
        mode = j.get("apply_mode")
        url = (
            j.get("apply_url")
            if mode == "link"
            else (j.get("url") if mode == "legacy" else "")
        )
        if not (
            url and str(url).startswith("https://") and not bs.is_old_platform_url(url)
        ):
            mode, url = "email", None
        else:
            mode = "link"
        lo, hi = _int(j.get("sal_min")), _int(j.get("sal_max"))
        if lo is not None and hi is not None and lo > hi:
            lo = hi = None
        desc = (
            (j.get("description_html") or "").strip() or j.get("summary") or j["title"]
        )
        if len(desc) < 20:
            desc = (desc + " " + j["title"] + " " + j["location"]).strip()
        jobs.append(
            {
                "id": jid,
                "site": site,
                "source": "feed",
                "source_id": source_id,
                "employer_id": emp_id,
                "title": j["title"][:160],
                "location": (j["location"] or "")[:120] or bs.EDITIONS[site]["none"],
                "region": (j.get("regions") or [None])[0],
                "job_type": j.get("type") or None,
                "sal_min": lo,
                "sal_max": hi,
                "currency": (
                    j.get("cur") if j.get("cur") in ("EUR", "GBP") else None
                ),  # the advertised currency (eye M4)
                "period": (
                    j.get("period")
                    if j.get("period") in ("year", "day", "hour", "month")
                    else None
                ),
                "sal_text": j.get("sal_text") or None,
                "sectors_json": json.dumps(j["sectors"], ensure_ascii=False),
                "summary": (j.get("summary") or "")[:300] or None,
                "description": desc[:20000],
                "apply_mode": mode,
                "apply_email": None,
                "apply_url": url,
                "status": "live",
                "posted_at": (
                    f"{j['posted']}T00:00:00Z" if j.get("posted") else None
                ),  # the source's date (eye M1)
                "closing_at": j.get("closing")
                or None,  # kept: one live rule on both sides (eye B1)
                "created_by": CREATED_BY[src],
                "created_at": as_of,
                "updated_at": as_of,
            }
        )
        c = {
            "sectors": j["sectors"],
            "regions": j.get("regions") or [],
            "job_type": j.get("type") or None,
            "workplace": j.get("workplace"),
            "contract": j.get("contract") or [],
            "loc_class": j.get("loc_class"),
            "taxonomy_number": tax_number,
            "source_sectors": [],
            "sector_confidence": 1.0,
            "sector_method": "source",
        }
        f = jc.facet_row(
            {
                "title": j["title"],
                "employer": emp,
                "description_html": j.get("description_html") or "",
                "sal_min": lo,
                "sal_max": hi,
                "currency": jobs[-1]["currency"],
                "period": jobs[-1]["period"],
                "sal_text": j.get("sal_text") or "",
                "location": j["location"],
            },
            site,
            c,
            "import",
        )
        facets.append(tuple(jc.facet_params(jid, f, as_of)))
    return list(emps.values()), jobs, facets


FACET_COLS = (
    "job_id",
    "sectors_json",
    "regions_json",
    "job_type",
    "workplace",
    "contract_json",
    "loc_class",
    "level",
    "is_agency",
    "salary_display",
    "unverified_cur",
    "taxonomy_version",
    "set_by",
    "updated_at",
    "search_text",
    "source_sectors_json",
    "sector_confidence",
    "sector_method",
)


def _upsert(table: str, row: dict[str, Any], key: str) -> str:
    cols = list(row)
    sets = ", ".join(
        f"{c} = excluded.{c}"
        for c in cols
        if c not in (key, "created_at", "created_by")
    )
    return (
        f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(_q(row[c]) for c in cols)}) "
        f"ON CONFLICT ({key}) DO UPDATE SET {sets};"
    )


def seed_sql(
    env: str, normalised: dict[str, dict[str, Any]], as_of: str
) -> tuple[str, dict[str, Any]]:
    """Idempotent SQL: upsert every employer, job and job_facets row, then close earlier seed rows not in the set."""
    if env != "staging":
        raise SeedError(
            "the staging seed is staging-only: production data never comes from a seed"
        )
    tax = jc.canonical_taxonomy()
    jc.assert_canonical(tax)
    lines = [
        "-- GreenJobs STAGING seed: public job data only (no candidates, applications or contacts). Test data is flagged."
    ]
    counts: dict[str, Any] = {}
    ids: list[str] = []
    for site in sorted(normalised):
        emps, jobs, facets = job_rows(site, normalised[site], int(tax.number), as_of)
        assert_jobs_safe(jobs)
        lines += [_upsert("employers", e, "id") for e in emps]
        lines += [_upsert("jobs", j, "id") for j in jobs]
        lines += [
            _upsert("job_facets", dict(zip(FACET_COLS, f)), "job_id") for f in facets
        ]
        ids += [j["id"] for j in jobs]
        counts[site] = {
            "jobs": len(jobs),
            "gaia": sum(j["created_by"] == "staging-seed" for j in jobs),
            "test_data": sum(j["created_by"] == "staging-seed-test" for j in jobs),
        }
    lines.append(
        f"UPDATE jobs SET status = 'closed', closed_at = {_q(as_of)}, updated_at = {_q(as_of)} "
        f"WHERE created_by IN ('staging-seed', 'staging-seed-test') AND status <> 'closed' "
        f"AND id NOT IN (SELECT value FROM json_each({_q(json.dumps(sorted(ids)))}));"
    )
    sql = "\n".join(lines) + "\n"
    assert_seed_safe(sql)
    return sql, counts


def assert_jobs_safe(jobs: list[dict[str, Any]]) -> None:
    """Fail closed per row: live, no apply address stored, never a link into the retired platform."""
    for j in jobs:
        if j["status"] != "live" or j["apply_email"] is not None:
            raise SeedError(f"{j['id']}: a seed job is live and stores no apply email")
        if j["apply_mode"] == "link" and (not str(j["apply_url"] or "").startswith("https://") or bs.is_old_platform_url(j["apply_url"])):
            raise SeedError(f"{j['id']}: seed link into the retired platform or not https")
        if j["created_by"] not in ("staging-seed", "staging-seed-test"):
            raise SeedError(f"{j['id']}: seed rows are created_by staging-seed*")


def assert_seed_safe(sql: str) -> None:
    """Fail closed: upserts into the public tables, one scoped close of earlier seed rows, nothing personal."""
    for stmt in (
        s.strip() for s in sql.splitlines() if s.strip() and not s.startswith("--")
    ):
        if stmt.startswith("UPDATE jobs SET status = 'closed'"):
            if "WHERE created_by IN ('staging-seed', 'staging-seed-test')" not in stmt:
                raise SeedError("seed close must be scoped to earlier seed rows")
            continue
        m = re.match(r"INSERT INTO (\w+) \(([^)]*)\) VALUES \(", stmt)
        if (
            not m
            or m.group(1) not in SEED_TABLES
            or not stmt.endswith(";")
            or "ON CONFLICT" not in stmt
        ):
            raise SeedError(f"seed statement not allowed: {stmt[:80]}")
        if _PII_COLS.search(m.group(2)):
            raise SeedError("seed touches a personal-data column")


# ── CLI ──────────────────────────────────────────────────────────────────────


def prepare(
    env: str,
    seed_date: date,
    out: Path,
    september_dir: Path = SRC / "data",
    gaia_feed: Path | None = None,
) -> dict[str, Any]:
    if env != "staging":
        raise SeedError(
            "the staging seed is staging-only: production data never comes from a seed"
        )
    out = out.resolve()
    if not (
        out.is_relative_to(ROOT / ".tmp") or out.is_relative_to(ROOT / "deliverables")
    ):
        raise SeedError(
            f"--out {out} must be under {ROOT / '.tmp'} or {ROOT / 'deliverables'}"
        )
    feed = json.loads(gaia_feed.read_text(encoding="utf-8")) if gaia_feed else None
    if gaia_feed and not (feed or {}).get("jobs"):
        raise SeedError(
            f"{gaia_feed}: no jobs in the Gaia feed (refusing a seed that silently drops the current jobs)"
        )
    raw = build_datasets(seed_date, september_dir, feed)
    data_dir = out / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    for site, d in raw.items():
        _write(
            data_dir / f"{site}.json",
            json.dumps(d, ensure_ascii=False, indent=1, sort_keys=True),
        )
    normalised = {
        site: bs.normalise(
            raw[site], site, SRC, SRC / "assets" / "logos", seed_date, data_dir
        )
        for site in raw
    }
    as_of = f"{seed_date.isoformat()}T00:00:00Z"
    sql, counts = seed_sql(env, normalised, as_of)
    _write(out / "seed.sql", sql)
    manifest = {
        "env": env,
        "seed_date": seed_date.isoformat(),
        "gaia_feed": bool(feed),
        "counts": counts,
        # what the static board renders from the same normalised set: the parity test compares D1 against it
        "static": {site: {"ids": [j["id"] for j in normalised[site]["jobs"]],
                          "salary": {k: v for k, v in bs.salary_stats(normalised[site]["jobs"], bs.EDITIONS[site]).items()
                                     if k in ("n_jobs", "n_disc", "disc_pct", "median")}} for site in normalised},
        "build_site_args": [
            "--data-dir",
            str(data_dir),
            "--today",
            seed_date.isoformat(),
        ],
    }
    _write(out / "manifest.json", json.dumps(manifest, indent=1, sort_keys=True))
    return manifest


def _write(path: Path, text: str) -> None:
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    p.add_argument("--env", required=True)
    p.add_argument("--seed-date", type=date.fromisoformat, default=None)
    p.add_argument("--gaia-feed", type=Path, default=None)
    p.add_argument("--september-dir", type=Path, default=SRC / "data")
    p.add_argument("--out", type=Path, default=ROOT / ".tmp" / "staging_seed")
    a = p.parse_args(argv)
    try:
        m = prepare(
            a.env,
            a.seed_date or datetime.now(timezone.utc).date(),
            a.out,
            a.september_dir,
            a.gaia_feed,
        )
    except SeedError as exc:
        print(f"REFUSED: {exc}", file=sys.stderr)
        return 3
    print(json.dumps({k: m[k] for k in ('env', 'seed_date', 'gaia_feed', 'counts', 'build_site_args')}, indent=1))
    return 0


if __name__ == "__main__":
    sys.exit(main())
