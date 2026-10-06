"""Tag competitor ads from the Meta Ad Library with Jev (TypeSafe decisions via OpenRouter).

description: Reads an ad export (Apify `apify/facebook-ads-scraper` shape or a flat JSON/CSV
             list), asks Jev ONE typed-decision call per ad (format, cta_type, funnel_stage,
             hook_strength, has_offer) and writes a tagged JSON + swipe-file CSV, optionally
             appending rows to a Google Sheet. Directive:
             directives/custom_scrapers/jev_ad_library_tagger.md
inputs: --input PATH (JSON list or CSV) or --fetch-apify "<search terms | page url>"
        (needs env APIFY_API_TOKEN; raw items saved to .tmp/ad_library_raw.json).
        --output PATH (default <input>.tagged.json), --csv-out PATH, --sheet-id ID --tab NAME,
        --min-confidence F (default 0.55), --limit N, --dry-run, --workers N.
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: tagged JSON, swipe CSV, optional Sheet rows, stdout summary, a row in
         .tmp/jev_ledger.jsonl via jev_client.append_ledger (caller "jev_ad_library_tagger").
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.modules import jev_client  # noqa: E402
from execution.modules.jev_client import choice, noul, score  # noqa: E402

APIFY_ACTOR = "apify~facebook-ads-scraper"
APIFY_RUN_SYNC = f"https://api.apify.com/v2/acts/{APIFY_ACTOR}/run-sync-get-dataset-items"
APIFY_RAW_PATH = WORKSPACE / ".tmp" / "ad_library_raw.json"
APIFY_TOKEN_VAR = "APIFY_API_TOKEN"

BODY_PREVIEW_CHARS = 160
TAG_NAMES = ("format", "cta_type", "funnel_stage", "hook_strength", "has_offer")
HOOK_LEVELS = [
    "no hook — opens with the brand or a generic statement",
    "weak hook — mildly interesting, easy to scroll past",
    "solid hook — a clear pain point, question or curiosity gap",
    "stops the scroll — bold claim, surprising number or pattern interrupt in the first line",
]
CSV_COLUMNS = [
    "id", "brand", "headline", "body_preview",
    "format", "format_confidence",
    "cta_type", "cta_type_confidence",
    "funnel_stage", "funnel_stage_confidence",
    "hook_strength", "hook_strength_confidence",
    "has_offer", "has_offer_confidence",
    "min_confidence", "low_confidence",
    "media_type", "cta", "start_date", "platforms", "link",
]


# ---- questions ----------------------------------------------------------------------------

def build_questions() -> dict[str, dict[str, Any]]:
    """The five tags, as Decisions-API questions. One call per ad answers all of them."""
    return {
        "format": choice("What creative format is this ad?", {
            "ugc_testimonial": "a customer or creator talking about their own experience",
            "product_demo": "shows the product in use, features, before/after",
            "founder_talking_head": "the founder or an employee speaks to camera about the company",
            "static_offer": "a single image or short copy built around a deal, price or launch",
            "carousel_listicle": "numbered tips, multiple items, 'N ways to…', swipe-through",
            "meme_humor": "joke, meme template, ironic or playful tone",
            "educational": "teaches a concept, how-to, myth-busting, no hard sell",
            "other": "none of the above fits",
        }),
        "cta_type": choice("What is the primary call to action?", {
            "shop_now": "buy, order, shop, get yours, add to cart",
            "sign_up": "sign up, create an account, join, subscribe, start free trial",
            "learn_more": "learn more, read, discover, see how",
            "book_call": "book a call, schedule a demo, talk to sales, get a quote",
            "download": "download an app, guide, ebook, template",
            "message_us": "DM us, WhatsApp us, send a message, contact us",
            "none": "no call to action at all",
        }),
        "funnel_stage": choice("Which funnel stage does this ad target?", {
            "awareness": "introduces the brand or problem to cold audiences, no offer or urgency",
            "consideration": "compares, educates, builds trust, social proof, 'why us'",
            "conversion": "direct response: price, discount, urgency, buy/sign-up now",
            "retention": "speaks to existing customers: upgrade, reorder, loyalty, new feature",
        }),
        "hook_strength": score("How strong is the opening hook (first line / headline)?", HOOK_LEVELS),
        "has_offer": noul(
            "Does the ad contain an explicit offer?",
            true="states a discount, price, free trial, bonus, bundle or limited-time deal",
            false="no explicit discount, price, bonus or deal is mentioned",
        ),
    }


# ---- input normalisation ------------------------------------------------------------------

def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _dig(d: Any, *path: str) -> Any:
    cur = d
    for p in path:
        if not isinstance(cur, dict):
            return None
        cur = cur.get(p)
    return cur if cur not in ("",) else None


def _join_list(v: Any) -> str:
    if isinstance(v, list):
        return ", ".join(str(x) for x in v if x not in (None, ""))
    return str(v) if v not in (None,) else ""


def normalize_ad(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Map an Apify facebook-ads-scraper item OR a flat dict onto the internal ad shape.

    Internal shape: id, brand, headline, body, cta, link, media_type, start_date, platforms.
    Missing fields become "" — never None — so downstream CSV/Jev state is stable.
    """
    snap = raw.get("snapshot") if isinstance(raw.get("snapshot"), dict) else {}
    body = _first(raw, "body", "text", "ad_text", "primary_text")
    if isinstance(body, dict):  # flat exports sometimes keep body as {"text": ...}
        body = body.get("text")
    if body is None:
        body = _dig(snap, "body", "text")
    if body is None:
        body = _first(snap, "body_text", "text")
    if body is None:
        # Some exports list the cards (carousel) with per-card bodies.
        cards = snap.get("cards") if isinstance(snap, dict) else None
        if isinstance(cards, list):
            body = " | ".join(str(c.get("body") or "") for c in cards if isinstance(c, dict)).strip(" |")
    headline = _first(raw, "headline", "title") or _first(snap, "title", "link_title") or ""
    ad_id = _first(raw, "id", "ad_id", "ad_archive_id", "adArchiveID") or f"ad_{index + 1}"
    brand = _first(raw, "brand", "page_name", "pageName", "advertiser") or _first(snap, "page_name") or ""
    cta = _first(raw, "cta", "cta_text") or _first(snap, "cta_text", "cta_type") or ""
    link = _first(raw, "link", "url", "link_url") or _first(snap, "link_url") or _first(raw, "ad_library_url") or ""
    media_type = _first(raw, "media_type", "display_format") or _first(snap, "display_format") or ""
    start_date = _first(raw, "start_date", "startDate", "start_date_string", "startDateFormatted") or ""
    platforms = _join_list(_first(raw, "platforms", "publisher_platform", "publisherPlatform") or "")
    return {
        "id": str(ad_id),
        "brand": str(brand),
        "headline": str(headline),
        "body": str(body or ""),
        "cta": str(cta),
        "link": str(link),
        "media_type": str(media_type),
        "start_date": str(start_date),
        "platforms": platforms,
    }


def load_ads(path: Path) -> list[dict[str, Any]]:
    """Read a JSON list (or {items: [...]}) or a CSV and return normalised ads."""
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data = data.get("items") or data.get("ads") or data.get("data") or []
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON list, got {type(data).__name__}")
        rows = [r for r in data if isinstance(r, dict)]
    return [normalize_ad(r, i) for i, r in enumerate(rows)]


# ---- Apify fetch --------------------------------------------------------------------------

def fetch_apify(query: str, limit: int, token: str, timeout_s: float = 300.0) -> list[dict[str, Any]]:
    """Run apify/facebook-ads-scraper synchronously and return the dataset items.

    `query` is a page URL (ad library or facebook.com page) or free search terms.
    """
    import requests

    if query.startswith("http"):
        run_input: dict[str, Any] = {"startUrls": [{"url": query}], "resultsLimit": limit}
    else:
        run_input = {"searchTerms": [query], "resultsLimit": limit, "activeStatus": "active"}
    resp = requests.post(
        APIFY_RUN_SYNC,
        params={"token": token, "timeout": int(timeout_s)},
        json=run_input,
        timeout=timeout_s + 30,
    )
    if resp.status_code not in (200, 201):
        raise RuntimeError(f"apify HTTP {resp.status_code}: {resp.text[:300]}")
    items = resp.json()
    if not isinstance(items, list):
        raise RuntimeError(f"apify returned {type(items).__name__}, expected list")
    APIFY_RAW_PATH.parent.mkdir(parents=True, exist_ok=True)
    APIFY_RAW_PATH.write_text(json.dumps(items, ensure_ascii=False, indent=2), encoding="utf-8")
    return items


# ---- tagging -------------------------------------------------------------------------------

def ad_state(ad: dict[str, Any]) -> dict[str, Any]:
    """The state Jev sees for one ad. Only the text signals — no ids or links."""
    return {
        "brand": ad["brand"],
        "headline": ad["headline"],
        "body": ad["body"][:6000],
        "cta_button": ad["cta"],
        "media_type": ad["media_type"],
    }


def _answer_value(res: jev_client.JevResult, name: str, qtype: str) -> Any:
    if qtype == "choice":
        return res.choice(name, "")
    if qtype == "score":
        s = res.score(name, 0.0)
        return int(round(s))
    return res.noul(name, 0.0) >= 0.5


def apply_tags(ads: list[dict[str, Any]], results: list[jev_client.JevResult],
               questions: dict[str, dict[str, Any]], min_confidence: float) -> list[dict[str, Any]]:
    """Merge Jev results into ad dicts: tags, confidences, min_confidence, low_confidence, error."""
    tagged: list[dict[str, Any]] = []
    for ad, res in zip(ads, results):
        row = dict(ad)
        row["tags"] = {}
        row["confidence"] = {}
        for name, q in questions.items():
            if res.ok:
                row["tags"][name] = _answer_value(res, name, q["type"])
                conf = res.confidence(name, 0.0)
                if q["type"] == "noul" and not conf:
                    # noul answers carry no `confidence`; distance from 0.5 is the natural proxy.
                    conf = abs(res.noul(name, 0.5) - 0.5) * 2
                row["confidence"][name] = round(conf, 3)
            else:
                row["tags"][name] = "" if q["type"] == "choice" else None
                row["confidence"][name] = 0.0
        row["jev_error"] = res.error
        row["cost_usd"] = res.cost_usd
        confs = [c for n, c in row["confidence"].items() if questions[n]["type"] != "noul"]
        row["min_confidence"] = round(min(confs), 3) if confs else 0.0
        row["low_confidence"] = (not res.ok) or row["min_confidence"] < min_confidence
        tagged.append(row)
    return tagged


def fake_results(ads: list[dict[str, Any]]) -> list[jev_client.JevResult]:
    """Dry-run stand-in: deterministic answers, zero cost."""
    out = []
    for _ in ads:
        out.append(jev_client.JevResult(answers={
            "format": {"choice": "other", "confidence": 1.0},
            "cta_type": {"choice": "none", "confidence": 1.0},
            "funnel_stage": {"choice": "awareness", "confidence": 1.0},
            "hook_strength": {"score": 0.0, "confidence": 1.0},
            "has_offer": {"noul": 0.0},
        }, model="dry-run"))
    return out


# ---- outputs -------------------------------------------------------------------------------

def to_csv_row(row: dict[str, Any]) -> dict[str, Any]:
    body = " ".join(row["body"].split())
    out: dict[str, Any] = {
        "id": row["id"],
        "brand": row["brand"],
        "headline": row["headline"],
        "body_preview": body[:BODY_PREVIEW_CHARS],
        "min_confidence": row["min_confidence"],
        "low_confidence": int(bool(row["low_confidence"])),
        "media_type": row["media_type"],
        "cta": row["cta"],
        "start_date": row["start_date"],
        "platforms": row["platforms"],
        "link": row["link"],
    }
    for name in TAG_NAMES:
        val = row["tags"].get(name)
        if isinstance(val, bool):
            val = int(val)
        out[name] = "" if val is None else val
        out[f"{name}_confidence"] = row["confidence"].get(name, 0.0)
    return out


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(to_csv_row(r))


def append_to_sheet(rows: list[dict[str, Any]], sheet_id: str, tab: str) -> str:
    """Append swipe-file rows to a Google Sheet tab (header written when the tab is empty).

    Returns a one-line status; never raises (missing creds are a graceful skip).
    """
    try:
        from execution.google.google_sheets_writer import get_client
    except ImportError as exc:
        return f"sheet skipped: gspread not installed ({exc})"
    try:
        client = get_client()
        ss = client.open_by_key(sheet_id)
        try:
            ws = ss.worksheet(tab)
        except Exception as exc:  # gspread.WorksheetNotFound; create the tab instead.
            if exc.__class__.__name__ != "WorksheetNotFound":
                raise
            ws = ss.add_worksheet(title=tab, rows=max(100, len(rows) + 10), cols=len(CSV_COLUMNS))
        values = [[to_csv_row(r)[c] for c in CSV_COLUMNS] for r in rows]
        if not ws.row_values(1):
            values.insert(0, CSV_COLUMNS)
        ws.append_rows(values, value_input_option="RAW")
        return f"sheet: appended {len(rows)} rows to {sheet_id}/{tab}"
    except (ValueError, FileNotFoundError) as exc:
        return f"sheet skipped: {exc}"
    except Exception as exc:  # network/auth: report, don't crash the tagging run
        return f"sheet failed: {exc.__class__.__name__}: {str(exc)[:200]}"


def summarize(tagged: list[dict[str, Any]], cost_usd: float, wall_s: float,
              min_confidence: float) -> dict[str, Any]:
    brands = Counter(r["brand"] or "(unknown)" for r in tagged)
    fmt = Counter(r["tags"].get("format") or "(none)" for r in tagged)
    cta = Counter(r["tags"].get("cta_type") or "(none)" for r in tagged)
    funnel = Counter(r["tags"].get("funnel_stage") or "(none)" for r in tagged)
    offers = sum(1 for r in tagged if r["tags"].get("has_offer") is True)
    errors = sum(1 for r in tagged if r.get("jev_error"))
    return {
        "ads_tagged": len(tagged) - errors,
        "ads_total": len(tagged),
        "jev_errors": errors,
        "per_brand": dict(brands.most_common()),
        "format": dict(fmt.most_common()),
        "cta_type": dict(cta.most_common()),
        "funnel_stage": dict(funnel.most_common()),
        "with_offer": offers,
        "low_confidence": sum(1 for r in tagged if r["low_confidence"]),
        "min_confidence_threshold": min_confidence,
        "cost_usd": round(cost_usd, 6),
        "wall_s": round(wall_s, 2),
    }


def print_summary(s: dict[str, Any]) -> None:
    def dist(d: dict[str, int]) -> str:
        return ", ".join(f"{k}={v}" for k, v in d.items()) or "-"
    print(f"ads tagged: {s['ads_tagged']}/{s['ads_total']}  (jev errors: {s['jev_errors']})")
    print(f"per brand: {dist(s['per_brand'])}")
    print(f"format: {dist(s['format'])}")
    print(f"cta: {dist(s['cta_type'])}")
    print(f"funnel: {dist(s['funnel_stage'])}")
    print(f"with explicit offer: {s['with_offer']}")
    print(f"low confidence (< {s['min_confidence_threshold']}): {s['low_confidence']}")
    print(f"cost: ${s['cost_usd']:.6f}   wall: {s['wall_s']}s")


# ---- CLI -----------------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Tag Meta Ad Library ads with Jev.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, help="JSON list / CSV of ads (Apify or flat shape)")
    src.add_argument("--fetch-apify", metavar="QUERY",
                     help="Search terms or a page URL; runs apify/facebook-ads-scraper (APIFY_API_TOKEN)")
    p.add_argument("--output", type=Path, help="Tagged JSON path (default <input>.tagged.json)")
    p.add_argument("--csv-out", type=Path, help="Swipe-file CSV path (default <output>.csv)")
    p.add_argument("--sheet-id", help="Google Sheet ID to append rows to")
    p.add_argument("--tab", default="Ads", help="Sheet tab name (default Ads)")
    p.add_argument("--min-confidence", type=float, default=0.55)
    p.add_argument("--limit", type=int, default=0, help="Tag only the first N ads")
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="No Jev / Apify / Sheet calls")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    t0 = time.perf_counter()

    if args.fetch_apify:
        token = os.environ.get(APIFY_TOKEN_VAR, "").strip()
        if args.dry_run:
            print("dry-run: skipping Apify fetch; nothing to tag")
            return 0
        if not token:
            print(f"{APIFY_TOKEN_VAR} is not set; export it or pass --input with a saved export", file=sys.stderr)
            return 2
        try:
            raw_items = fetch_apify(args.fetch_apify, args.limit or 100, token)
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"apify fetch failed: {exc}", file=sys.stderr)
            return 1
        print(f"apify: {len(raw_items)} items saved to {APIFY_RAW_PATH}")
        ads = [normalize_ad(r, i) for i, r in enumerate(raw_items) if isinstance(r, dict)]
        input_path = APIFY_RAW_PATH
    else:
        input_path = args.input
        if not input_path.exists():
            print(f"input not found: {input_path}", file=sys.stderr)
            return 1
        try:
            ads = load_ads(input_path)
        except (ValueError, OSError, csv.Error) as exc:
            print(f"could not read {input_path}: {exc}", file=sys.stderr)
            return 1

    ads = [a for a in ads if a["body"] or a["headline"]]
    if args.limit > 0:
        ads = ads[: args.limit]
    if not ads:
        print("no ads with text to tag", file=sys.stderr)
        return 1

    output = args.output or input_path.with_suffix(input_path.suffix + ".tagged.json")
    csv_out = args.csv_out or output.with_suffix(".csv")
    questions = build_questions()

    if args.dry_run:
        results = fake_results(ads)
    elif not jev_client.available():
        print("OPENROUTER_API_KEY is not set (or OPENROUTER_API_TOKEN); use --dry-run to test the pipeline",
              file=sys.stderr)
        return 2
    else:
        results = jev_client.decide_many([ad_state(a) for a in ads], questions, workers=args.workers)

    tagged = apply_tags(ads, results, questions, args.min_confidence)
    cost = sum(r.cost_usd for r in results)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(tagged, ensure_ascii=False, indent=2), encoding="utf-8")
    write_csv(tagged, csv_out)
    print(f"wrote {output}\nwrote {csv_out}")

    if args.sheet_id:
        if args.dry_run:
            print(f"dry-run: would append {len(tagged)} rows to sheet {args.sheet_id}/{args.tab}")
        else:
            print(append_to_sheet(tagged, args.sheet_id, args.tab))

    summary = summarize(tagged, cost, time.perf_counter() - t0, args.min_confidence)
    print_summary(summary)
    if not args.dry_run:
        jev_client.append_ledger({
            "caller": "jev_ad_library_tagger",
            "ads": summary["ads_total"],
            "errors": summary["jev_errors"],
            "cost_usd": summary["cost_usd"],
            "input_tokens": sum(r.input_tokens for r in results),
            "latency_ms": int(summary["wall_s"] * 1000),
            "model": next((r.model for r in results if r.model), jev_client.JEV_MODEL),
        })
    return 0 if summary["jev_errors"] < summary["ads_total"] else 1


if __name__ == "__main__":
    sys.exit(main())
