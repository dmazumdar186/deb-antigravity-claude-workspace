"""Gaia canonical feed (gaia_feed_sync.py feed.json) -> classified jobs -> GreenJobs D1 (SQL file and/or admin API).

description: Reads the canonical Gaia feed, runs every job through job_classifier (sectors with a confidence,
    regions, job type, workplace, contract tags), and builds one import batch per board site:
      - jobs upserted on the stable key source_id 'gaia:<wp id>' (D1 id '{site}:gaia:<wp id>', source 'feed');
      - a low-confidence / conflicting / unfrozen-taxonomy sector, or a possible duplicate (eval E2 'queue'),
        goes to the review queue and the job is held as 'draft' until staff approve it in /admin/review;
      - a job already on that board (eval E2 'dup') is linked to the board job (job_links), not listed twice;
      - jobs that left the feed are closed (status 'closed'), never deleted.
    Output: --emit-sql (idempotent SQL for `wrangler d1 execute`), --emit-json (the admin API payload), and/or
    --post URL (POST /api/admin/import, bearer BUILD_TOKEN). Dry run by default: --post sends dry_run=true
    (the Worker counts, writes nothing) unless --live; the Worker also needs FEED_IMPORT_ENABLED="1" to write.
    --once = fetch + map (gaia_feed_sync.run) + this, for a cron every 10 minutes.
inputs: --feed PATH | --once [--offline FIXTURE] [--board-jobs PATH ...] [--work-dir DIR] [--no-jev];
    --site ie|uk; --taxonomy PATH; --allow-unfrozen-taxonomy; --as-of YYYY-MM-DD; --emit-sql PATH;
    --emit-json PATH; --post URL [--live]; env BUILD_TOKEN (only with --post).
outputs: stdout JSON summary (no candidate data exists in the feed); optional SQL / JSON files (outside the
    repo or under <repo>/.tmp/). No network unless --once without --offline, or --post.
exit codes: 0 ok, 2 usage, 3 gate (empty feed for a site, fetch gate, API refusal or error)
CLI:
  python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_d1_sync.py --feed .tmp/gaia_feed/feed.json \\
      --emit-sql .tmp/gaia_d1.sql
  python3 execution/gtm_client_workflows/greenjobs_redesign/gaia_d1_sync.py --once --board-jobs .tmp/gj/ie.json \\
      --post https://greenjobs.ie/api/admin/import            # dry run; add --live to write
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

try:  # .env is optional (BUILD_TOKEN / OpenRouter key may already be in the environment)
    from dotenv import load_dotenv

    load_dotenv(ROOT / ".env")
except ImportError:  # stdlib-only fallback
    pass

import build_site as bs  # noqa: E402
import gaia_feed_sync as gfs  # noqa: E402
import job_classifier as jc  # noqa: E402
import strategies_import as si  # noqa: E402  (sql_lit / render / output-path guards: one implementation)

cjson = si.cjson

EXIT_OK, EXIT_USAGE, EXIT_GATE = 0, 2, 3
D1_DIR = ROOT / "deliverables" / "greenjobs_migration_2026-11-06" / "build" / "d1"
UPSERTS_0003 = D1_DIR / "upserts_0003.sql"
UPSERTS = D1_DIR / "upserts.sql"
SOURCE = "gaia"
SOURCE_PREFIX = "gaia:%"
EMPLOYER_NAME = "Gaia Talent"
MAX_JOBS_PER_BATCH = 500  # the Worker's ceiling; Gaia publishes ~83
TIMEOUT_S = 30


class GateError(RuntimeError):
    pass


# ------------------------------------------------------------------ SQL templates



def load_templates() -> dict[str, str]:
    t = si.load_named(UPSERTS_0003)
    base = si.load_upserts(UPSERTS)
    t["employers"] = base["employers"]
    body = re.sub(r"--[^\n]*", "", UPSERTS.read_text(encoding="utf-8"))
    audit = [
        re.sub(r"\s+", " ", s).strip() for s in body.split(";") if "INTO audit_log" in s
    ]
    if len(audit) != 1:
        raise si.UsageError("upserts.sql: expected one audit_log statement")
    t["audit"] = audit[0]
    return t


# ------------------------------------------------------------------ batch building


def name_norm(name: str) -> str:
    return si.name_norm(name)


def board_job_id(site: str, board_id: Any) -> str:
    """Board ids in the scrape are Strategies job ids; D1 holds them as '{site}:strat:{id}'."""
    s = str(board_id)
    return s if ":" in s else f"{site}:strat:{s}"


def closing_iso(raw: Any) -> str | None:
    """dd/mm/yyyy, yyyy-mm-dd, ISO, or WordPress ACF 'Ymd' (20261231) -> end-of-day UTC; None when unknown."""
    s = str(raw or "").strip()
    m = re.fullmatch(r"(\d{4})(\d{2})(\d{2})", s)
    if m:
        s = "-".join(m.groups())
    d = bs.parse_date(s) if s else ""
    try:
        date.fromisoformat(d)
    except ValueError:
        return None
    return f"{d}T23:59:59Z"


def record_to_job(
    rec: dict,
    site: str,
    tax: jc.Taxonomy,
    *,
    today: date,
    require_frozen: bool,
    dup_queue: list[str],
    jev: Any = None,
) -> tuple[dict | None, str | None]:
    """One feed record on one board -> API job dict, or (None, reject reason)."""
    title = re.sub(r"\s+", " ", str(rec.get("title") or "")).strip()
    if not 3 <= len(title) <= 160:
        return None, f"title length {len(title)} outside 3..160"
    text = gfs.plain_text(rec.get("description_html") or "")
    if len(text) < 20:
        return None, "description under 20 characters"
    closing = closing_iso(rec.get("expires_at"))
    if closing and closing[:10] < today.isoformat():
        return None, "closing date passed"
    apply = rec.get("apply") or {}
    email = str(apply.get("email") or "").strip().lower()
    url = str(apply.get("url") or rec.get("url") or "").strip()
    if (
        apply.get("method") == "email"
        and si.EMAIL_RE.fullmatch(email)
        and len(email) <= 254
    ):
        mode, a_email, a_url = "email", email, None
    elif url.startswith("https://") and len(url) <= 2000 and not re.search(r"\s", url):
        mode, a_email, a_url = "link", None, url
    else:
        return None, "no usable apply route (no valid email, no https link)"
    location = (
        str(rec.get("location") or "")
        or str(rec.get("region") or "")
        or bs.EDITIONS[site]["none"]
    )[:120]
    m = rec.get("mapping") or {}
    sm = m.get("sector") or {}
    hint = {
        "sectors": [sm.get("value")] if sm.get("value") else [],
        "confidence": sm.get("confidence"),
        "method": sm.get("method"),
    }
    gaia_terms = rec.get("gaia_terms") or {}
    job_in = {
        "title": title,
        "employer": EMPLOYER_NAME,
        "location": location,
        "summary": text[:300],
        "description_html": rec.get("description_html") or "",
        "job_type": (
            (m.get("job_type") or {}).get("value")
            if (m.get("job_type") or {}).get("method") != "queue"
            else ""
        ),
        "source_sectors": list(gaia_terms.get("sector") or [])
        + list(gaia_terms.get("category") or []),
    }
    c = jc.classify(
        job_in, site, tax, hint=hint, require_frozen=require_frozen, jev=jev
    )
    reasons = [c["review_reason"]] if c["needs_review"] else []
    reasons += [f"possible duplicate of {b}" for b in dup_queue]
    held = bool(reasons)
    job = {
        "source_id": rec["source_id"],
        "title": title,
        "location": location,
        "region": c["region"],
        "job_type": c["job_type"],
        "sal_text": (str(rec.get("salary_text") or "")[:120] or None),
        "sectors": c["suggested_sectors"] if held else c["sectors"],
        "summary": text[:300],
        "description": text[:20000],
        "apply_mode": mode,
        "apply_email": a_email,
        "apply_url": a_url,
        "status": "draft" if held else "live",
        "posted_at": rec.get("posted_at") or None,
        "closing_at": closing,
        "review": (
            {
                "reason": "; ".join(reasons)[:300],
                "suggested": c["suggested_sectors"],
                "confidence": c["sector_confidence"],
                "hold": 1,
            }
            if held
            else None
        ),
        "facets": {
            "regions": c["regions"],
            "loc_class": c["loc_class"],
            "workplace": c["workplace"],
            "contract": c["contract"],
            "source_sectors": c["source_sectors"],
            "sector_confidence": c["sector_confidence"],
            "sector_method": c["sector_method"],
            "taxonomy_version": c["taxonomy_version"],
        },
    }
    return job, None


def build_batches(
    feed: dict,
    *,
    tax: jc.Taxonomy,
    today: date,
    dedupe: dict | None = None,
    require_frozen: bool = True,
    sites: list[str] | None = None,
    jev: Any = None,
) -> dict[str, dict]:
    """feed.json (+ dedupe.json) -> {site: payload} for POST /api/admin/import (and the SQL emitter)."""
    records = feed.get("jobs") if isinstance(feed, dict) else None
    if not isinstance(records, list):
        raise si.UsageError(
            "feed has no 'jobs' list (expected gaia_feed_sync.py feed.json)"
        )
    queued: dict[tuple[str, str], list[str]] = {}
    for p in (dedupe or {}).get("pairs", []):
        if p.get("verdict") == "queue":
            queued.setdefault((p["source_id"], p["board_site"]), []).append(
                board_job_id(p["board_site"], p["board_id"])
            )
    want = sites or ["ie", "uk"]
    out: dict[str, dict] = {
        s: {
            "source": SOURCE,
            "site": s,
            "close_missing": True,
            "taxonomy": {
                "version": tax.version,
                "frozen": tax.frozen,
                "sectors": tax.sectors,
            },
            "jobs": [],
            "links": [],
            "rejects": [],
        }
        for s in want
    }
    for rec in sorted(records, key=lambda r: str(r.get("source_id"))):
        sid = str(rec.get("source_id") or "")
        if not re.fullmatch(r"gaia:\d{1,12}", sid):
            for s in want:
                out[s]["rejects"].append(
                    {"source_id": sid[:40], "reason": "source_id is not gaia:<wp id>"}
                )
            continue
        dups = rec.get("on_board") or []
        for d in dups:
            if d.get("site") in out:
                out[d["site"]]["links"].append(
                    {
                        "source_id": sid,
                        "board_job_id": board_job_id(d["site"], d["board_id"]),
                        "method": (
                            d.get("method")
                            if d.get("method") in ("rule", "jev")
                            else "rule"
                        ),
                    }
                )
        for site in rec.get("boards") or []:
            if site not in out:
                continue
            if any(d.get("site") == site for d in dups):
                continue  # already on this board: linked above, never listed twice
            job, why = record_to_job(
                rec,
                site,
                tax,
                today=today,
                require_frozen=require_frozen,
                dup_queue=queued.get((sid, site), []),
                jev=jev,
            )
            if job is None:
                out[site]["rejects"].append({"source_id": sid, "reason": why})
            else:
                out[site]["jobs"].append(job)
    for s, b in out.items():
        if len(b["jobs"]) > MAX_JOBS_PER_BATCH:
            raise GateError(
                f"{s}: {len(b['jobs'])} jobs exceed the batch ceiling {MAX_JOBS_PER_BATCH}"
            )
    return out


def check_gates(batches: dict[str, dict], feed_count: int) -> None:
    """Fail loud before anything could close a whole board: a site with nothing kept is refused."""
    if feed_count == 0:
        raise GateError(
            "feed holds 0 jobs: refusing (closing every Gaia job is never the right answer)"
        )
    for s, b in batches.items():
        if b["close_missing"] and not b["jobs"] and not b["links"] and b["rejects"]:
            raise GateError(
                f"{s}: every feed job was rejected ({len(b['rejects'])}); refusing to close the rest"
            )


# ------------------------------------------------------------------ SQL


def batch_sql(b: dict, t: dict[str, str], now: str) -> list[str]:
    site = b["site"]
    r = si.render
    lines = []
    sectors = b["taxonomy"]["sectors"]
    lines.append(
        r(t["taxonomy_deactivate"], ["sector", cjson(sectors)])
    )
    for s in sectors:
        lines.append(r(t["taxonomy_upsert"], ["sector", s, b["taxonomy"]["version"]]))
    emp_id = f"{site}:feed:{SOURCE}"
    lines.append(
        r(
            t["employers"],
            [
                emp_id,
                site,
                "feed",
                SOURCE,
                EMPLOYER_NAME,
                name_norm(EMPLOYER_NAME),
                None,
                None,
                None,
                "https://gaiatalent.com",
                None,
                None,
                now,
            ],
        )
    )
    for j in b["jobs"]:
        jid = f"{site}:{SOURCE}:{j['source_id'].split(':', 1)[1]}"
        lines.append(
            r(
                t["feed_job_upsert"],
                [
                    jid,
                    site,
                    j["source_id"],
                    emp_id,
                    name_norm(EMPLOYER_NAME),
                    j["title"],
                    j["location"],
                    j["region"],
                    j["job_type"],
                    j["sal_text"],
                    cjson(j["sectors"]),
                    j["summary"],
                    j["description"],
                    j["apply_mode"],
                    j["apply_email"],
                    j["apply_url"],
                    j["status"],
                    j["posted_at"],
                    j["closing_at"],
                    now,
                ],
            )
        )
        f = j["facets"]
        lines.append(
            r(
                t["job_facets_upsert"],
                [
                    jid,
                    site,
                    cjson(f["regions"]),
                    f["loc_class"],
                    f["workplace"],
                    cjson(f["contract"]),
                    cjson(f["source_sectors"]),
                    Real(f["sector_confidence"]),
                    f["sector_method"],
                    f["taxonomy_version"],
                    now,
                ],
            )
        )
        if j["review"]:
            rv = j["review"]
            lines.append(
                r(
                    t["review_upsert"],
                    [
                        jid,
                        site,
                        rv["reason"],
                        cjson(rv["suggested"]),
                        Real(rv["confidence"]),
                        rv["hold"],
                        now,
                    ],
                )
            )
        else:
            lines.append(r(t["review_clear"], [jid]))
    for lk in b["links"]:
        lines.append(
            r(
                t["link_upsert"],
                [site, lk["source_id"], lk["board_job_id"], lk["method"], now],
            )
        )
    if b["close_missing"]:
        keep = sorted(j["source_id"] for j in b["jobs"])
        lines.append(
            r(t["feed_close_missing"], [site, SOURCE_PREFIX, now, cjson(keep)])
        )
        pairs = sorted(f"{lk['source_id']}|{lk['board_job_id']}" for lk in b["links"])
        lines.append(r(t["link_prune"], [site, SOURCE_PREFIX, cjson(pairs)]))
    digest = hashlib.sha256(
        json.dumps(api_payload(b), sort_keys=True).encode()
    ).hexdigest()
    lines.append(
        r(
            t["audit"],
            [
                now,
                "import:gaia",
                "import.batch",
                "import",
                f"{SOURCE}:{site}",
                f"sql:{digest}",
                json.dumps(
                    {
                        "jobs": len(b["jobs"]),
                        "links": len(b["links"]),
                        "held": sum(1 for j in b["jobs"] if j["review"]),
                    }
                ),
            ],
        )
    )
    return lines


class Real(si.Raw):
    """A float literal (si.sql_lit renders int/str/None only)."""

    def __init__(self, v: float) -> None:
        super().__init__(repr(float(v)))


def emit_sql(batches: dict[str, dict], t: dict[str, str], now: str) -> str:
    head = [
        f"-- GreenJobs Gaia feed -> D1, generated {now}. Idempotent: re-running converges.",
        "-- Needs migrations/0003_classifier_feed_review_employers.sql. Apply: npx wrangler@4 d1 execute greenjobs --file=THIS_FILE",
    ]
    body = [line for s in sorted(batches) for line in batch_sql(batches[s], t, now)]
    return "\n".join(head + body) + "\n"


# ------------------------------------------------------------------ API


def api_payload(b: dict) -> dict:
    return {k: v for k, v in b.items() if k != "rejects"}


def post_batch(
    url: str,
    token: str,
    payload: dict,
    *,
    live: bool,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> dict:
    """POST one site batch. dry_run unless live. Any non-200 is a delivery failure (GateError: fail loud)."""
    if not url.startswith("https://") and not url.startswith("http://127.0.0.1"):
        raise si.UsageError("--post needs an https URL")
    body = json.dumps({**api_payload(payload), "dry_run": not live}).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=body,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "User-Agent": "GreenJobsGaiaD1Sync/1.0",
        },
    )
    try:
        with opener(req, timeout=TIMEOUT_S) as res:
            data = json.loads(res.read().decode("utf-8") or "{}")
            status = getattr(res, "status", 200)
    except urllib.error.HTTPError as e:
        raise GateError(
            f"import API answered {e.code} for site {payload['site']}"
        ) from e
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
        raise GateError(
            f"import API unreachable for site {payload['site']}: {type(e).__name__}"
        ) from e
    if status != 200:
        raise GateError(f"import API answered {status} for site {payload['site']}")
    return data


# ------------------------------------------------------------------ CLI


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(
        description="Gaia feed -> classified GreenJobs D1 import (dry run by default)"
    )
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument(
        "--feed",
        help="feed.json written by gaia_feed_sync.py (dedupe.json next to it is read too)",
    )
    src.add_argument(
        "--once",
        action="store_true",
        help="fetch + map with gaia_feed_sync, then import (cron entry point)",
    )
    ap.add_argument(
        "--offline", help="--once: gaia snapshot JSON instead of the live fetch"
    )
    ap.add_argument(
        "--board-jobs",
        action="append",
        default=[],
        help="--once: board jobs for duplicate detection",
    )
    ap.add_argument(
        "--work-dir",
        default=str(ROOT / ".tmp" / "gaia_feed"),
        help="--once: gaia_feed_sync output dir",
    )
    ap.add_argument(
        "--no-jev",
        action="store_true",
        help="never call Jev (upstream mapping and here)",
    )
    ap.add_argument(
        "--jev",
        action="store_true",
        help="also ask Jev for a low-confidence sector here (cached)",
    )
    ap.add_argument(
        "--site",
        choices=["ie", "uk"],
        action="append",
        help="only these boards (default both)",
    )
    ap.add_argument("--taxonomy", default=str(jc.TAXONOMY_PATH))
    ap.add_argument(
        "--allow-unfrozen-taxonomy",
        action="store_true",
        help="publish confident sectors without a frozen taxonomy (default: every sector reviewed)",
    )
    ap.add_argument(
        "--as-of",
        help="YYYY-MM-DD (default today UTC): jobs closing before it are not imported",
    )
    ap.add_argument("--emit-sql")
    ap.add_argument("--emit-json")
    ap.add_argument(
        "--post",
        metavar="URL",
        help="POST /api/admin/import (BUILD_TOKEN env); dry_run unless --live",
    )
    ap.add_argument(
        "--live",
        action="store_true",
        help="with --post: ask the Worker to write (it also needs FEED_IMPORT_ENABLED=1)",
    )
    return ap


def run(
    args: argparse.Namespace, *, opener: Callable[..., Any] = urllib.request.urlopen
) -> tuple[int, dict]:
    if args.live and not args.post:
        raise si.UsageError("--live only applies with --post")
    if args.live and os.environ.get("GAIA_FEED_ENABLED") != "1":
        # The Gaia feed was never promised for 3 Dec (engagement record §2): live writes stay off until the
        # operator turns the flag on. Dry runs, --emit-sql and --emit-json keep working.
        raise si.UsageError(
            "--live refused: the Gaia feed is off (set GAIA_FEED_ENABLED=1 to enable it)"
        )
    if args.offline and not args.once:
        raise si.UsageError("--offline applies to --once only")
    today = (
        date.fromisoformat(args.as_of)
        if args.as_of
        else datetime.now(timezone.utc).date()
    )
    try:
        tax = jc.load_taxonomy(Path(args.taxonomy))
    except jc.TaxonomyError as e:
        raise si.UsageError(str(e)) from e
    sql_out = si.check_output(args.emit_sql, True, []) if args.emit_sql else None
    json_out = si.check_output(args.emit_json, True, []) if args.emit_json else None
    token = os.environ.get("BUILD_TOKEN", "") if args.post else ""
    if args.post and not token:
        raise si.UsageError("--post needs BUILD_TOKEN in the environment")

    upstream = None
    if args.once:
        work = Path(args.work_dir)
        snap = (
            json.loads(Path(args.offline).read_text(encoding="utf-8"))
            if args.offline
            else gfs.fetch_live()
        )
        board: list[dict] = []
        for p in args.board_jobs:
            board += gfs.load_board(Path(p))
        try:
            upstream = gfs.run(snap, board, work, use_jev=not args.no_jev)
        except gfs.GateError as e:
            raise GateError(f"gaia_feed_sync gate: {e}") from e
        feed_path = work / "feed.json"
    else:
        feed_path = Path(args.feed)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    dd_path = feed_path.parent / "dedupe.json"
    dedupe = (
        json.loads(dd_path.read_text(encoding="utf-8")) if dd_path.exists() else None
    )
    jev = (
        gfs.Jev(Path(args.work_dir) / "jev_cache.json", True)
        if args.jev and not args.no_jev
        else None
    )

    batches = build_batches(
        feed,
        tax=tax,
        today=today,
        dedupe=dedupe,
        require_frozen=not args.allow_unfrozen_taxonomy,
        sites=args.site,
        jev=jev,
    )
    check_gates(batches, len(feed.get("jobs") or []))
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    summary: dict[str, Any] = {
        "tool": "gaia_d1_sync",
        "mode": "live" if args.live else "dry_run",
        "as_of": today.isoformat(),
        "taxonomy": {"version": tax.version, "frozen": tax.frozen},
        "upstream": upstream
        and {
            k: upstream.get(k)
            for k in ("jobs_in_feed", "new", "updated", "removed", "duplicates_found")
        },
        "sites": {
            s: {
                "jobs": len(b["jobs"]),
                "live": sum(1 for j in b["jobs"] if j["status"] == "live"),
                "held_for_review": sum(1 for j in b["jobs"] if j["review"]),
                "links": len(b["links"]),
                "rejected": len(b["rejects"]),
                "rejects": b["rejects"][:50],
            }
            for s, b in batches.items()
        },
        "sql_written": False,
        "json_written": False,
        "posted": {},
    }
    if sql_out:
        si.atomic_write(sql_out, emit_sql(batches, load_templates(), now))
        summary["sql_written"] = True
    if json_out:
        si.atomic_write(
            json_out,
            json.dumps(
                {s: api_payload(b) for s, b in batches.items()},
                indent=1,
                ensure_ascii=False,
            )
            + "\n",
        )
        summary["json_written"] = True
    if args.post:
        for s, b in batches.items():
            summary["posted"][s] = post_batch(
                args.post, token, b, live=args.live, opener=opener
            )
    return EXIT_OK, summary


def main(
    argv: list[str] | None = None,
    *,
    opener: Callable[..., Any] = urllib.request.urlopen,
) -> int:
    args = build_parser().parse_args(argv)
    try:
        code, summary = run(args, opener=opener)
    except si.UsageError as e:
        print(
            json.dumps(
                {
                    "tool": "gaia_d1_sync",
                    "status": "error",
                    "exit_code": EXIT_USAGE,
                    "error": str(e),
                }
            )
        )
        return EXIT_USAGE
    except GateError as e:
        print(
            json.dumps(
                {
                    "tool": "gaia_d1_sync",
                    "status": "gate_failed",
                    "exit_code": EXIT_GATE,
                    "error": str(e),
                }
            )
        )
        print(f"gate: {e}", file=sys.stderr)
        return EXIT_GATE
    print(json.dumps(summary, indent=1, ensure_ascii=False))
    return code


if __name__ == "__main__":
    sys.exit(main())
