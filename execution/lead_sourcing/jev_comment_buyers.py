"""Find buyers in social comments with Jev (TypeSafe decisions via OpenRouter).

description: Reads a comment export (Apify TikTok / Instagram / YouTube comment scrapers or a
             flat JSON/CSV list), asks Jev ONE typed-decision call per comment (intent,
             buy_temperature, needs_reply, objection), ranks by priority =
             temperature x (1 + log1p(likes)/4) and writes a JSON, CSV and a markdown priority
             list with a suggested reply TYPE per row. Directive:
             directives/lead_sourcing/jev_comment_buyers.md
inputs: --input PATH (JSON list or CSV) or --fetch-apify ACTOR --post-urls URL1,URL2
        (needs env APIFY_API_TOKEN; raw items saved to .tmp/comments_raw.json).
        --output PATH (default <input>.buyers.json), --csv-out PATH, --md PATH, --top N (25),
        --min-confidence F (0.55), --limit N, --workers N (8), --dry-run.
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: ranked JSON, optional CSV + markdown priority list, stdout summary, a row in
         .tmp/jev_ledger.jsonl via jev_client.append_ledger (caller "jev_comment_buyers").
"""
from __future__ import annotations

import argparse
import csv
import json
import math
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

APIFY_TOKEN_VAR = "APIFY_API_TOKEN"
APIFY_RAW_PATH = WORKSPACE / ".tmp" / "comments_raw.json"
TEXT_PREVIEW_CHARS = 140
HOT_TEMPERATURE = 0.66
HOT_NEEDS_REPLY = 0.5

TEMPERATURE_LEVELS = [
    "no purchase signal — chatter, jokes, unrelated",
    "mild interest — likes the product, no intent stated",
    "considering — asks about price, stock, sizes or details",
    "explicitly asking how or where to buy, or saying they want to order",
]

REPLY_TYPE = {
    "ready_to_buy": "DM with checkout link",
    "price_or_availability_question": "answer price/availability",
    "product_question": "answer question",
    "complaint": "resolve complaint",
    "praise": "thank",
}

CSV_COLUMNS = [
    "rank", "id", "author", "platform", "intent", "intent_confidence", "buy_temperature",
    "needs_reply", "objection", "objection_confidence", "likes", "priority", "hot_lead",
    "review", "reply_type", "text", "url", "post", "created",
]


# ---- questions ----------------------------------------------------------------------------

def build_questions() -> dict[str, dict[str, Any]]:
    """Four questions, one Jev call per comment."""
    return {
        "intent": choice("What is this social-media comment on a seller's post mainly doing?", {
            "ready_to_buy": "wants to buy or order now: 'I need this', 'how do I order', 'take my money'",
            "price_or_availability_question": "asks the price, stock, shipping region, restock or sizes available",
            "product_question": "asks how the product works, materials, usage, compatibility",
            "complaint": "unhappy: bad order, late delivery, broken product, bad service",
            "praise": "compliments the product, post or seller without asking anything",
            "spam_or_bot": "promotion of another account, links, giveaways, emoji-only bot text",
            "other": "off-topic chatter, tagging friends, jokes unrelated to buying",
        }),
        "buy_temperature": score("How close is this commenter to buying?", TEMPERATURE_LEVELS),
        "needs_reply": noul(
            "Would a reply from the seller move this person forward?",
            true="a seller reply would answer them, resolve an issue or move them toward buying",
            false="no reply needed: spam, chatter, or nothing to answer",
        ),
        "objection": choice("What purchase objection, if any, does the comment raise?", {
            "price": "too expensive, asks for discount, compares price",
            "shipping": "delivery time, cost or region, tracking",
            "trust": "doubts legitimacy, scam worries, quality doubts, reviews",
            "fit_or_size": "sizing, fit, compatibility, will it work for me",
            "none": "no objection raised",
        }),
    }


# ---- input normalisation ------------------------------------------------------------------

def _first(d: dict[str, Any], *keys: str) -> Any:
    for k in keys:
        v = d.get(k)
        if v not in (None, ""):
            return v
    return None


def _to_int(v: Any) -> int:
    try:
        return max(0, int(float(v)))
    except (TypeError, ValueError):
        return 0


def detect_platform(raw: dict[str, Any]) -> str:
    if "uniqueId" in raw or "diggCount" in raw or "videoWebUrl" in raw:
        return "tiktok"
    if "ownerUsername" in raw or "postUrl" in raw:
        return "instagram"
    if "comment" in raw and ("voteCount" in raw or "pageUrl" in raw or "publishedTimeText" in raw):
        return "youtube"
    return str(raw.get("platform") or "flat")


def normalize_comment(raw: dict[str, Any], index: int = 0) -> dict[str, Any]:
    """Map a TikTok / Instagram / YouTube Apify item or a flat dict to the internal shape.

    Internal shape: id, author, text, likes, url, post, created, platform. Never None.
    """
    user = raw.get("user") if isinstance(raw.get("user"), dict) else {}
    text = _first(raw, "text", "comment", "body", "message") or ""
    author = (_first(raw, "author", "uniqueId", "ownerUsername", "username")
              or _first(user, "uniqueId", "username", "nickname") or "")
    if isinstance(author, dict):
        author = _first(author, "uniqueId", "username", "name") or ""
    likes = _first(raw, "likes", "diggCount", "likesCount", "voteCount", "likeCount")
    post = _first(raw, "post", "videoWebUrl", "postUrl", "pageUrl", "inputUrl") or ""
    url = _first(raw, "url", "commentUrl") or post
    created = _first(raw, "created", "createTimeISO", "timestamp", "publishedTimeText", "date") or ""
    cid = _first(raw, "id", "cid", "commentId") or f"c_{index + 1}"
    return {
        "id": str(cid),
        "author": str(author),
        "text": str(text),
        "likes": _to_int(likes),
        "url": str(url),
        "post": str(post),
        "created": str(created),
        "platform": detect_platform(raw),
    }


def load_comments(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".csv":
        with open(path, newline="", encoding="utf-8") as fh:
            rows = list(csv.DictReader(fh))
    else:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
        if isinstance(data, dict):
            data = data.get("items") or data.get("comments") or data.get("data") or []
        if not isinstance(data, list):
            raise ValueError(f"{path}: expected a JSON list, got {type(data).__name__}")
        rows = [r for r in data if isinstance(r, dict)]
    return [normalize_comment(r, i) for i, r in enumerate(rows)]


# ---- Apify fetch --------------------------------------------------------------------------

def apify_input(actor: str, urls: list[str], limit: int) -> dict[str, Any]:
    a = actor.lower()
    if "tiktok" in a:
        return {"postURLs": urls, "commentsPerPost": limit}
    if "youtube" in a:
        return {"startUrls": [{"url": u} for u in urls], "maxComments": limit}
    return {"directUrls": urls, "resultsLimit": limit}


def fetch_apify(actor: str, urls: list[str], limit: int, token: str,
                timeout_s: float = 300.0) -> list[dict[str, Any]]:
    """Run a comment-scraper actor synchronously and return its dataset items."""
    import requests

    actor_path = actor.replace("/", "~")
    resp = requests.post(
        f"https://api.apify.com/v2/acts/{actor_path}/run-sync-get-dataset-items",
        params={"token": token, "timeout": int(timeout_s)},
        json=apify_input(actor, urls, limit),
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


# ---- scoring -------------------------------------------------------------------------------

def comment_state(c: dict[str, Any]) -> dict[str, Any]:
    return {"platform": c["platform"], "comment": c["text"][:4000], "likes": c["likes"]}


def priority(temperature: float, likes: int) -> float:
    """temperature (0..1) x (1 + log1p(likes)/4)."""
    return round(max(0.0, temperature) * (1 + math.log1p(max(0, likes)) / 4), 4)


def is_hot(row: dict[str, Any]) -> bool:
    return row["buy_temperature"] >= HOT_TEMPERATURE and row["needs_reply"] >= HOT_NEEDS_REPLY


def reply_type(row: dict[str, Any]) -> str:
    if row["needs_reply"] < HOT_NEEDS_REPLY and row["intent"] != "praise":
        return "none"
    return REPLY_TYPE.get(row["intent"], "none")


def apply_results(comments: list[dict[str, Any]], results: list[jev_client.JevResult],
                  min_confidence: float) -> list[dict[str, Any]]:
    """Merge Jev answers, compute priority, sort descending, add rank."""
    max_level = len(TEMPERATURE_LEVELS) - 1
    rows: list[dict[str, Any]] = []
    for c, res in zip(comments, results):
        row = dict(c)
        if res.ok:
            row["intent"] = res.choice("intent", "other") or "other"
            row["intent_confidence"] = round(res.confidence("intent", 0.0), 3)
            row["buy_temperature"] = round(min(1.0, max(0.0, res.score("buy_temperature", 0.0) / max_level)), 3)
            row["needs_reply"] = round(res.noul("needs_reply", 0.0), 3)
            row["objection"] = res.choice("objection", "none") or "none"
            row["objection_confidence"] = round(res.confidence("objection", 0.0), 3)
        else:
            row.update(intent="", intent_confidence=0.0, buy_temperature=0.0, needs_reply=0.0,
                       objection="", objection_confidence=0.0)
        row["priority"] = priority(row["buy_temperature"], row["likes"])
        row["hot_lead"] = res.ok and is_hot(row)
        row["review"] = (not res.ok) or min(row["intent_confidence"], row["objection_confidence"]) < min_confidence
        row["reply_type"] = reply_type(row) if res.ok else "none"
        row["jev_error"] = res.error
        row["cost_usd"] = res.cost_usd
        rows.append(row)
    rows.sort(key=lambda r: (-r["priority"], -r["needs_reply"], -r["likes"]))
    for i, r in enumerate(rows, 1):
        r["rank"] = i
    return rows


def fake_results(comments: list[dict[str, Any]]) -> list[jev_client.JevResult]:
    return [jev_client.JevResult(answers={
        "intent": {"choice": "other", "confidence": 1.0},
        "buy_temperature": {"score": 0.0, "confidence": 1.0},
        "needs_reply": {"noul": 0.0},
        "objection": {"choice": "none", "confidence": 1.0},
    }, model="dry-run") for _ in comments]


# ---- outputs -------------------------------------------------------------------------------

def _preview(text: str) -> str:
    return " ".join(text.split())[:TEXT_PREVIEW_CHARS]


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            out = dict(r)
            out["hot_lead"] = int(bool(r["hot_lead"]))
            out["review"] = int(bool(r["review"]))
            w.writerow(out)


def render_md(rows: list[dict[str, Any]], top: int) -> str:
    lines = ["# Buyer priority list", "",
             "| # | author | intent | temp | objection | reply type | comment | link |",
             "|---|---|---|---|---|---|---|---|"]
    for r in rows[:top]:
        text = _preview(r["text"]).replace("|", "/")
        link = f"[open]({r['url']})" if r["url"] else ""
        flag = " (hot)" if r["hot_lead"] else ""
        flag += " (review)" if r["review"] else ""
        lines.append(f"| {r['rank']} | {r['author']}{flag} | {r['intent']} | {r['buy_temperature']:.2f} | "
                     f"{r['objection']} | {r['reply_type']} | {text} | {link} |")
    return "\n".join(lines) + "\n"


def summarize(rows: list[dict[str, Any]], cost_usd: float, wall_s: float) -> dict[str, Any]:
    errors = sum(1 for r in rows if r.get("jev_error"))
    return {
        "comments_total": len(rows),
        "jev_errors": errors,
        "per_intent": dict(Counter(r["intent"] or "(none)" for r in rows).most_common()),
        "hot_leads": sum(1 for r in rows if r["hot_lead"]),
        "review": sum(1 for r in rows if r["review"]),
        "cost_usd": round(cost_usd, 6),
        "wall_s": round(wall_s, 2),
    }


def print_summary(s: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    intents = ", ".join(f"{k}={v}" for k, v in s["per_intent"].items()) or "-"
    print(f"comments: {s['comments_total']}  (jev errors: {s['jev_errors']})")
    print(f"per intent: {intents}")
    print(f"hot leads: {s['hot_leads']}   review: {s['review']}")
    print(f"cost: ${s['cost_usd']:.6f}   wall: {s['wall_s']}s")
    for r in rows[:3]:
        print(f"  #{r['rank']} {r['author']} [{r['intent']}, temp {r['buy_temperature']:.2f}, "
              f"prio {r['priority']}] {r['reply_type']}: {_preview(r['text'])}")


# ---- CLI -----------------------------------------------------------------------------------

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Find buyers in social comments with Jev.")
    src = p.add_mutually_exclusive_group(required=True)
    src.add_argument("--input", type=Path, help="JSON list / CSV of comments (Apify or flat shape)")
    src.add_argument("--fetch-apify", metavar="ACTOR",
                     help="Apify comment actor, e.g. clockworks/tiktok-comments-scraper (APIFY_API_TOKEN)")
    p.add_argument("--post-urls", default="", help="Comma-separated post URLs for --fetch-apify")
    p.add_argument("--output", type=Path, help="JSON path (default <input>.buyers.json)")
    p.add_argument("--csv-out", type=Path)
    p.add_argument("--md", type=Path, help="Markdown priority list path")
    p.add_argument("--top", type=int, default=25)
    p.add_argument("--min-confidence", type=float, default=0.55)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--dry-run", action="store_true", help="No Jev / Apify calls")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    t0 = time.perf_counter()
    if args.fetch_apify:
        urls = [u.strip() for u in args.post_urls.split(",") if u.strip()]
        if not urls:
            print("--fetch-apify needs --post-urls", file=sys.stderr)
            return 2
        if args.dry_run:
            print("dry-run: skipping Apify fetch; nothing to score")
            return 0
        token = os.environ.get(APIFY_TOKEN_VAR, "").strip()
        if not token:
            print(f"{APIFY_TOKEN_VAR} is not set; export it or pass --input with a saved export",
                  file=sys.stderr)
            return 2
        try:
            raw = fetch_apify(args.fetch_apify, urls, args.limit or 200, token)
        except (RuntimeError, ValueError, OSError) as exc:
            print(f"apify fetch failed: {exc}", file=sys.stderr)
            return 1
        print(f"apify: {len(raw)} items saved to {APIFY_RAW_PATH}")
        comments = [normalize_comment(r, i) for i, r in enumerate(raw) if isinstance(r, dict)]
        input_path = APIFY_RAW_PATH
    else:
        input_path = args.input
        if not input_path.exists():
            print(f"input not found: {input_path}", file=sys.stderr)
            return 1
        try:
            comments = load_comments(input_path)
        except (ValueError, OSError, csv.Error) as exc:
            print(f"could not read {input_path}: {exc}", file=sys.stderr)
            return 1

    comments = [c for c in comments if c["text"].strip()]
    if args.limit > 0:
        comments = comments[: args.limit]
    if not comments:
        print("no comments with text", file=sys.stderr)
        return 1

    output = args.output or input_path.with_suffix(input_path.suffix + ".buyers.json")
    if args.dry_run:
        results = fake_results(comments)
    elif not jev_client.available():
        print("OPENROUTER_API_KEY is not set; use --dry-run to test the pipeline", file=sys.stderr)
        return 2
    else:
        results = jev_client.decide_many([comment_state(c) for c in comments], build_questions(),
                                         workers=args.workers)

    rows = apply_results(comments, results, args.min_confidence)
    cost = sum(r.cost_usd for r in results)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {output}")
    if args.csv_out:
        write_csv(rows, args.csv_out)
        print(f"wrote {args.csv_out}")
    if args.md:
        args.md.parent.mkdir(parents=True, exist_ok=True)
        args.md.write_text(render_md(rows, args.top), encoding="utf-8")
        print(f"wrote {args.md}")
    summary = summarize(rows, cost, time.perf_counter() - t0)
    print_summary(summary, rows)
    if not args.dry_run:
        jev_client.append_ledger({
            "caller": "jev_comment_buyers",
            "items": len(rows),
            "cost_usd": summary["cost_usd"],
            "wall_s": summary["wall_s"],
            "errors": summary["jev_errors"],
        })
    return 0


if __name__ == "__main__":
    sys.exit(main())
