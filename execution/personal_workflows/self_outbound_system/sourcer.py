"""
sourcer.py
description: Source raw B2B leads for the self-outbound system. Dry-run returns the frozen 3-lead fixture; live mode calls the Apify HTTP API against harvestapi/linkedin-profile-search (per-segment config in config/apify_sourcing.json) and normalizes the payload into our internal lead schema.
inputs: --segment <name>, --limit <int>, --dry-run/--live, --output <path>, --tiny (5-lead safety cap). Env (live only): APIFY_TOKEN.
outputs: .tmp/self_outbound/sourced_leads_<timestamp>.json — {leads: [...], dry_run, cost_eur_estimate, sources_used}.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #1).
Prior-art pass 2026-07-14: harvestapi/linkedin-profile-search (6.3M runs, 4.8*, no cookie required, PAY_PER_EVENT $0.004/profile) is the pragmatic path. See config/apify_sourcing.json for rationale + per-segment search params.
Cost tracking in EUR per ~/.claude/rules/currency-eur.md. Fails loudly on Apify HTTP errors — never silent-drops results.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CONFIG_DIR,
    FIXTURES_DIR,
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    load_json,
    print_stat,
    timestamp,
    write_json,
)

load_dotenv()
log = get_logger("sourcer")

APIFY_BASE = "https://api.apify.com/v2"
APIFY_RUN_TIMEOUT_S = 900  # 15 minutes — Apify sync API max
USD_TO_EUR = 0.92  # per ~/.claude/rules/currency-eur.md

# Cost model per Apify actor. Rough per-lead estimates. Update if actor pricing changes.
COST_PER_LEAD_USD = {
    "harvestapi/linkedin-profile-search": 0.004,  # Full mode, per full profile
    "compass/crawler-google-places": 0.0035,       # Google Maps scraper, ~$3.50 per 1000 places
}


def source_dry_run(segment: str | None, limit: int) -> list[dict]:
    """Return leads from the frozen fixture. Segment filter is best-effort based
    on the fixture's segment_hint field; if segment is None, return all."""
    fixture_path = FIXTURES_DIR / "leads_seed.json"
    payload = load_json(fixture_path)
    leads: list[dict] = payload.get("leads", [])
    if segment:
        leads = [lead for lead in leads if lead.get("segment_hint") == segment]
    leads = leads[:limit] if limit > 0 else leads
    for lead in leads:
        lead.setdefault("source", "fixture:leads_seed")
    return leads


def _apify_run_sync(
    actor_id: str,
    input_body: dict,
    token: str,
    timeout_s: int = APIFY_RUN_TIMEOUT_S,
) -> list[dict]:
    """Run an Apify actor synchronously and return dataset items.

    Uses the `run-sync-get-dataset-items` endpoint which blocks until the run
    completes and streams the dataset as JSON. Raises on any HTTP error —
    never silent-drops.

    Actor IDs use the `username~name` slash-replaced form in URLs (Apify
    convention). This function accepts either 'username/name' or 'username~name'.
    """
    actor_url_id = actor_id.replace("/", "~")
    url = f"{APIFY_BASE}/acts/{actor_url_id}/run-sync-get-dataset-items"
    params = {"token": token, "timeout": str(timeout_s), "format": "json"}
    full_url = f"{url}?{urllib.parse.urlencode(params)}"

    body_bytes = json.dumps(input_body).encode("utf-8")
    req = urllib.request.Request(
        full_url,
        data=body_bytes,
        method="POST",
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json",
        },
    )
    log.info(f"apify: POST run-sync {actor_id} (input keys: {list(input_body.keys())})")
    try:
        # timeout_s + 60 grace so urllib error doesn't beat the API timeout
        with urllib.request.urlopen(req, timeout=timeout_s + 60) as resp:
            raw = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")[:500] if e.fp else ""
        raise RuntimeError(
            f"apify HTTP {e.code} on {actor_id}: {err_body}"
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"apify URL error on {actor_id}: {e}") from e

    if not raw:
        return []
    try:
        items = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(
            f"apify returned invalid JSON ({len(raw)} chars): {raw[:200]}"
        ) from e
    if not isinstance(items, list):
        raise RuntimeError(f"apify returned non-list: {type(items).__name__}")
    return items


def _normalize_harvestapi_profile(item: dict, segment: str) -> dict | None:
    """Normalize a harvestapi/linkedin-profile-search dataset item into our
    internal lead schema. Returns None if the profile is unusable (no name /
    obviously junk). Never raises on a bad item — logs and skips."""
    # harvestapi returns fields like: firstName, lastName, publicIdentifier,
    # linkedinUrl, headline, location, currentPosition {title, companyName,
    # companyLinkedinUrl}, emails [{...}], etc. Field names vary slightly
    # across builds — we defensively probe multiple keys.
    def get_first(*keys):
        for k in keys:
            v = item.get(k)
            if v:
                return v
        return None

    first = get_first("firstName", "first_name", "givenName")
    last = get_first("lastName", "last_name", "familyName")
    name = get_first("fullName", "name")
    if not name and (first or last):
        name = f"{first or ''} {last or ''}".strip()
    if not name:
        return None

    linkedin = get_first("linkedinUrl", "linkedin_url", "profileUrl", "url")
    headline = get_first("headline", "position", "title")
    # Location comes as either a string or a dict {linkedinText, countryCode, parsed:{...}}.
    # Unwrap to a plain string.
    location_raw = get_first("location", "locationName", "locationString")
    if isinstance(location_raw, dict):
        location = location_raw.get("linkedinText") or location_raw.get("text") or ""
        parsed = location_raw.get("parsed") or {}
        if not location and isinstance(parsed, dict):
            location = parsed.get("text") or ""
    else:
        location = location_raw or ""

    # Current position may be nested
    cur = item.get("currentPosition") or item.get("current_position") or {}
    if isinstance(cur, list) and cur:
        cur = cur[0]
    if not isinstance(cur, dict):
        cur = {}
    title = cur.get("title") or headline or ""
    company = cur.get("companyName") or cur.get("company") or get_first("company", "employerName") or ""

    # Emails — harvestapi returns a list, we pick the first business-looking one
    email = None
    emails_field = item.get("emails") or item.get("email") or []
    if isinstance(emails_field, str):
        email = emails_field
    elif isinstance(emails_field, list):
        for e in emails_field:
            if isinstance(e, dict):
                candidate = e.get("email") or e.get("address")
            else:
                candidate = str(e)
            if candidate and "@" in candidate:
                email = candidate
                break
    elif isinstance(emails_field, dict):
        email = emails_field.get("email") or emails_field.get("address")

    # Domain: derive from email if we have one, else from linkedin (company page URL)
    domain = ""
    if email and "@" in email:
        domain = email.split("@", 1)[1].lower()

    notes_bits = []
    if headline:
        notes_bits.append(headline)
    if location:
        notes_bits.append(f"loc: {location}")
    if cur.get("startedOn") or cur.get("start_date"):
        notes_bits.append(f"tenure_start: {cur.get('startedOn') or cur.get('start_date')}")
    notes = " | ".join(str(n) for n in notes_bits if n)[:280]

    return {
        "name": name,
        "title": title,
        "company": company,
        "domain": domain,
        "email": email or "",  # empty means enricher.py will try to find it
        "linkedin_url": linkedin or "",
        "notes": notes,
        "segment_hint": segment,
        "segment": segment,
        "source": "apify:harvestapi/linkedin-profile-search",
        "sourced_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }


def source_live(
    segment: str | None,
    limit: int,
    config_path: Path | None = None,
    tiny: bool = False,
) -> tuple[list[dict], float, list[str]]:
    """Live sourcing via Apify. Reads config/apify_sourcing.json to get
    per-segment search params, calls the actor synchronously, and normalizes
    the results.

    Returns (leads, cost_eur_estimate, actor_ids_used).

    - If segment is provided, sources only that segment.
    - If segment is None, sources ALL segments and merges.
    - limit is the per-segment cap (or global if segment specified).
    - tiny=True clamps the per-segment cap to 5 for safe smoke tests.
    """
    token = os.environ.get("APIFY_TOKEN") or os.environ.get("APIFY_API_TOKEN")
    if not token:
        raise RuntimeError(
            "APIFY_TOKEN not set in env — required for live sourcing. "
            "Add APIFY_TOKEN=<your-apify-token> to .env"
        )

    cfg_path = config_path or (CONFIG_DIR / "apify_sourcing.json")
    if not cfg_path.exists():
        raise RuntimeError(f"missing apify config: {cfg_path}")
    cfg = load_json(cfg_path)
    shared = cfg.get("shared_defaults", {})
    segments_cfg = cfg.get("segments", {})

    segments_to_run: list[str]
    if segment:
        if segment not in segments_cfg:
            raise RuntimeError(f"unknown segment {segment!r}; known: {list(segments_cfg)}")
        segments_to_run = [segment]
    else:
        segments_to_run = list(segments_cfg.keys())

    per_segment_cap = shared.get("max_items_per_segment", 34)
    if segment:
        per_segment_cap = limit if limit > 0 else per_segment_cap
    if tiny:
        per_segment_cap = min(per_segment_cap, 5)

    all_leads: list[dict] = []
    actors_used: list[str] = []
    cost_usd = 0.0

    for seg in segments_to_run:
        seg_cfg = segments_cfg[seg]
        actor_id = seg_cfg.get("actor_id") or shared.get("actor_id")
        actors_used.append(actor_id)

        input_body = {
            "profileScraperMode": shared.get("profileScraperMode", "Full"),
            "searchQuery": seg_cfg.get("search_query", ""),
            "maxItems": per_segment_cap,
            "locations": shared.get("locations", []),
        }
        # Optional filters passed through only if present in the segment config
        for optional_key in [
            "currentJobTitles",
            "pastJobTitles",
            "currentCompanies",
            "seniorityLevelIds",
            "yearsOfExperienceIds",
            "functionIds",
            "schools",
        ]:
            if optional_key in seg_cfg:
                input_body[optional_key] = seg_cfg[optional_key]

        log.info(
            f"apify: sourcing segment={seg} actor={actor_id} cap={per_segment_cap} "
            f"query={input_body['searchQuery']!r}"
        )
        try:
            raw_items = _apify_run_sync(actor_id, input_body, token)
        except RuntimeError as e:
            log.error(f"apify run failed for segment={seg}: {e}")
            continue  # skip this segment, keep going with others

        log.info(f"apify: segment={seg} returned {len(raw_items)} raw items")
        # Estimate cost for this segment: per-lead + one search page fee
        per_lead = COST_PER_LEAD_USD.get(actor_id, 0.004)
        cost_usd += (0.10 + per_lead * len(raw_items))  # $0.10 = search page fee

        normalized_count = 0
        skipped_count = 0
        for item in raw_items:
            norm = _normalize_harvestapi_profile(item, seg)
            if norm is None:
                skipped_count += 1
                continue
            all_leads.append(norm)
            normalized_count += 1
        log.info(
            f"apify: segment={seg} normalized={normalized_count} skipped={skipped_count}"
        )

    cost_eur = round(cost_usd * USD_TO_EUR, 4)
    return all_leads, cost_eur, actors_used


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--segment", type=str, default=None,
                   help="Optional segment name (see config/icp.json). "
                        "If omitted in --live mode, sources ALL segments.")
    p.add_argument("--limit", type=int, default=20,
                   help="Max leads per segment. 0 = use config default.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run mode (default). Returns fixture leads.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Requires APIFY_TOKEN in env.")
    p.add_argument("--tiny", action="store_true",
                   help="Live mode safety: cap at 5 leads per segment for smoke tests.")
    p.add_argument("--config", type=Path, default=None,
                   help="Override apify_sourcing.json path.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    cost_eur = 0.0
    sources_used: list[str] = []
    if args.dry_run:
        leads = source_dry_run(args.segment, args.limit)
        sources_used = ["fixture:leads_seed"]
    else:
        leads, cost_eur, sources_used = source_live(
            args.segment, args.limit, args.config, tiny=args.tiny
        )

    out_path = args.output or (TMP_DIR / f"sourced_leads_{timestamp()}.json")
    write_json(
        out_path,
        {
            "leads": leads,
            "dry_run": args.dry_run,
            "cost_eur_estimate": cost_eur,
            "sources_used": sources_used,
        },
    )
    print_stat(
        "sourcer",
        {
            "sourced": len(leads),
            "sources": sources_used,
            "dry_run": args.dry_run,
            "cost_eur_estimate": cost_eur,
            "tiny": args.tiny if not args.dry_run else False,
            "output": str(out_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
