"""
audit_site.py
description: Orchestrate the per-business website audit (fetch, signals, PSI, screenshots, vision, score).
inputs: --metro X [--business-id ID] [--limit N] [--mock] [--store ...] [--store-root PATH]
        [--skip-vision] [--skip-screenshots] [--force]
outputs: One `audits` row per audited business (with `raw`), an `events` log entry, and a stdout stat line.
"""

from __future__ import annotations

import argparse
import json
import sys
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

from execution.personal_workflows.prodcraft_medspa.audit import (  # noqa: E402
    booking_detect,
    fetch,
    html_signals,
    psi,
    scoring,
    screenshots,
    tech_detect,
    vision,
)
from execution.personal_workflows.prodcraft_medspa.common import config, notify, store  # noqa: E402

MAX_WORKERS = 4
AUDIT_STALE_DAYS = 30
PACKAGE_ROOT = Path(__file__).resolve().parent
FIXTURES_ROOT = PACKAGE_ROOT / "fixtures"


def _load_mock_map() -> dict:
    path = FIXTURES_ROOT / "mock_map.json"
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _mock_fetch(website_url: str, mock_map: dict) -> tuple[fetch.FetchResult, str | None]:
    """Resolve a `*.test` mock website_url to a local fixture HTML file. Never touches the network.

    Returns (FetchResult, fixture_name). fixture_name is None when the host isn't in mock_map
    (treated as a 404-equivalent: no website).
    """
    host = urlparse(website_url).netloc if website_url else ""
    entry = mock_map.get(host)
    if not entry:
        return (
            fetch.FetchResult(
                final_url=website_url,
                status=404,
                html=None,
                has_website=False,
                has_ssl=None,
                ssl_error=None,
                error="mock host not in mock_map.json",
            ),
            None,
        )

    fixture_name = entry["fixture"]
    status = entry["status"]
    final_url = entry["final_url"]
    has_ssl = final_url.startswith("https://")

    if status >= 400:
        return (
            fetch.FetchResult(
                final_url=final_url,
                status=status,
                html=None,
                has_website=False,
                has_ssl=has_ssl,
                ssl_error=None,
                error=f"http {status}",
            ),
            fixture_name,
        )

    html = (FIXTURES_ROOT / f"{fixture_name}.html").read_text(encoding="utf-8")
    return (
        fetch.FetchResult(
            final_url=final_url,
            status=status,
            html=html,
            has_website=True,
            has_ssl=has_ssl,
            ssl_error=None,
        ),
        fixture_name,
    )


def _mock_psi(fixture_name: str, strategy: str) -> psi.PsiResult:
    path = FIXTURES_ROOT / "psi" / f"{fixture_name}_{strategy}.json"
    if not path.exists():
        return psi.PsiResult(None, None, reason="no mock psi fixture")
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    return psi._parse_psi_response(data)  # noqa: SLF001 — reuse the real parser on a fixture payload


def audit_one_business(
    business: dict,
    *,
    settings,
    mock: bool,
    mock_map: dict | None,
    skip_vision: bool,
    skip_screenshots: bool,
    store_kind: str,
) -> tuple[dict, str | None]:
    """Run all audit steps for a single business. Returns (audit_row, error_or_none). Never raises."""
    website_url = business.get("website_url")
    raw: dict = {}

    if not website_url:
        signals = {"has_website": False}
        scored = scoring.score(signals)
        return (
            {
                "business_id": business["id"],
                "score_version": scored["score_version"],
                "has_website": False,
                "total_score": scored["total"],
                "bucket": scored["bucket"],
                "gaps": scored["gaps"],
                "raw": {"reason": "no website_url on business row"},
            },
            None,
        )

    fixture_name: str | None = None
    try:
        if mock:
            fetch_result, fixture_name = _mock_fetch(website_url, mock_map or {})
        else:
            fetch_result = fetch.fetch_site(website_url)
    except Exception as exc:  # noqa: BLE001 — a fetch failure degrades this business, not the whole run
        return (
            {
                "business_id": business["id"],
                "score_version": scoring.SCORE_VERSION,
                "has_website": False,
                "total_score": 100,
                "bucket": "qualified",
                "gaps": scoring.score({"has_website": False})["gaps"],
                "raw": {"error": str(exc)},
            },
            str(exc),
        )

    raw["fetch"] = {
        "final_url": fetch_result.final_url,
        "status": fetch_result.status,
        "has_ssl": fetch_result.has_ssl,
        "ssl_error": fetch_result.ssl_error,
        "error": fetch_result.error,
        "elapsed_ms": fetch_result.elapsed_ms,
    }

    if not fetch_result.has_website or not fetch_result.html:
        scored = scoring.score({"has_website": False})
        return (
            {
                "business_id": business["id"],
                "score_version": scored["score_version"],
                "has_website": False,
                "has_ssl": fetch_result.has_ssl,
                "final_url": fetch_result.final_url,
                "total_score": scored["total"],
                "bucket": scored["bucket"],
                "gaps": scored["gaps"],
                "raw": raw,
            },
            None,
        )

    html = fetch_result.html
    final_url = fetch_result.final_url or website_url

    html_has_viewport = html_signals.has_viewport_meta(html)
    footer_year = html_signals.footer_year(html)
    has_analytics = html_signals.has_analytics(html)

    booking = booking_detect.detect_booking(html)
    tech = tech_detect.detect_tech(html, final_url, fetch_theme=not mock)

    if mock and fixture_name:
        psi_mobile_result = _mock_psi(fixture_name, "mobile")
        psi_desktop_result = _mock_psi(fixture_name, "desktop")
    else:
        api_key = settings.PAGESPEED_API_KEY
        psi_mobile_result = psi.run_pagespeed(final_url, "mobile", api_key)
        psi_desktop_result = psi.run_pagespeed(final_url, "desktop", api_key)

    is_mobile_friendly = html_has_viewport and bool(psi_mobile_result.is_mobile_friendly)
    raw["psi"] = {
        "mobile": {
            "performance_score": psi_mobile_result.performance_score,
            "is_mobile_friendly": psi_mobile_result.is_mobile_friendly,
            "reason": psi_mobile_result.reason,
        },
        "desktop": {
            "performance_score": psi_desktop_result.performance_score,
            "reason": psi_desktop_result.reason,
        },
    }
    raw["tech"] = {
        "builder": tech.builder,
        "theme": tech.theme,
        "theme_year": tech.theme_year,
        "has_jquery_legacy": tech.has_jquery_legacy,
    }
    raw["booking"] = {"vendor": booking.vendor, "links": booking.booking_links}

    cta_above_fold: bool | None = None
    screenshot_mobile_url: str | None = None
    screenshot_desktop_url: str | None = None
    mobile_png: bytes | None = None
    desktop_png: bytes | None = None

    if not skip_screenshots:
        slug = business.get("slug") or business["id"]
        shot = screenshots.capture_screenshots(final_url, slug)
        cta_above_fold = shot.cta_above_fold
        raw["screenshots"] = {"error": shot.error}
        if shot.mobile_path:
            screenshot_mobile_url = screenshots.upload_screenshot(shot.mobile_path, slug, "mobile", store_kind)
            try:
                mobile_png = Path(shot.mobile_path).read_bytes()
            except OSError:
                mobile_png = None
        if shot.desktop_path:
            screenshot_desktop_url = screenshots.upload_screenshot(shot.desktop_path, slug, "desktop", store_kind)
            try:
                desktop_png = Path(shot.desktop_path).read_bytes()
            except OSError:
                desktop_png = None

    vision_dated_score: int | None = None
    vision_rationale: str | None = None
    vision_model_id: str | None = None
    vision_prompt_sha256: str | None = None
    llm_cost_usd = 0.0

    if not skip_vision:
        try:
            vresult = vision.run_vision_audit(
                business.get("name", ""),
                final_url,
                mobile_png,
                desktop_png,
                mock=mock,
            )
            vision_dated_score = vresult["vision_dated_score"]
            vision_rationale = vresult["vision_rationale"]
            vision_model_id = vresult["vision_model_id"]
            vision_prompt_sha256 = vresult["vision_prompt_sha256"]
            llm_cost_usd = vresult["cost_usd"]
            raw["vision"] = {"signals": vresult["vision_signals"], "usage": vresult["usage"]}
        except vision.VisionParseError as exc:
            raw["vision"] = {"error": str(exc)}

    signals = {
        "has_website": True,
        "booking_widget": booking.vendor,
        "is_mobile_friendly": is_mobile_friendly,
        "psi_mobile": psi_mobile_result.performance_score,
        "vision_dated_score": vision_dated_score,
        "has_cta_above_fold": cta_above_fold,
        "has_ssl": fetch_result.has_ssl,
        "builder": tech.builder,
        "theme_year": tech.theme_year,
        "has_jquery_legacy": tech.has_jquery_legacy,
        "has_analytics": has_analytics,
        "footer_year": footer_year,
    }
    scored = scoring.score(signals)

    audit_row = {
        "business_id": business["id"],
        "score_version": scored["score_version"],
        "psi_mobile": psi_mobile_result.performance_score,
        "psi_desktop": psi_desktop_result.performance_score,
        "has_website": True,
        "has_ssl": fetch_result.has_ssl,
        "is_mobile_friendly": is_mobile_friendly,
        "builder": tech.builder,
        "theme": tech.theme,
        "theme_year": tech.theme_year,
        "has_jquery_legacy": tech.has_jquery_legacy,
        "booking_widget": booking.vendor,
        "has_cta_above_fold": cta_above_fold,
        "has_analytics": has_analytics,
        "footer_year": footer_year,
        "vision_dated_score": vision_dated_score,
        "vision_rationale": vision_rationale,
        "vision_model_id": vision_model_id,
        "vision_prompt_sha256": vision_prompt_sha256,
        "total_score": scored["total"],
        "bucket": scored["bucket"],
        "gaps": scored["gaps"],
        "screenshot_mobile_url": screenshot_mobile_url,
        "screenshot_desktop_url": screenshot_desktop_url,
        "final_url": final_url,
        "raw": raw,
        "llm_cost_usd": llm_cost_usd,
    }
    return audit_row, None


def _needs_audit(business: dict, st, force: bool) -> bool:
    if business.get("is_chain"):
        return False
    if business.get("drop_reason") is not None:
        return False
    if force:
        return True
    latest = st.latest_audit(business["id"])
    if not latest:
        return True
    audited_at = latest.get("audited_at")
    if not audited_at:
        return True
    try:
        audited_dt = datetime.fromisoformat(str(audited_at).replace("Z", "+00:00"))
    except ValueError:
        return True
    return (datetime.now(timezone.utc) - audited_dt) > timedelta(days=AUDIT_STALE_DAYS)


def main() -> None:
    """description: Audit websites for businesses in a metro; write one audits row + event per business.
    inputs: --metro X [--business-id ID] [--limit N] [--mock] [--store ...] [--store-root PATH]
            [--skip-vision] [--skip-screenshots] [--force]
    outputs: audits rows, events rows, stdout stat line.
    """
    parser = argparse.ArgumentParser(description="Audit business websites for a metro")
    parser.add_argument("--metro", required=True)
    parser.add_argument("--business-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--skip-vision", action="store_true")
    parser.add_argument("--skip-screenshots", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    settings = config.bootstrap()
    store_kind = args.store or ("local" if args.mock else settings.store_kind)
    st = store.get_store(kind=store_kind, root=args.store_root)

    mock_map = _load_mock_map() if args.mock else None

    all_businesses = st.find_businesses(metro=args.metro, is_chain=False, drop_reason_is_null=True)
    if args.business_id:
        all_businesses = [b for b in all_businesses if b["id"] == args.business_id]

    candidates = [b for b in all_businesses if _needs_audit(b, st, args.force)]
    if args.limit is not None:
        candidates = candidates[: args.limit]

    stats = {
        "script": "audit_site",
        "in": len(all_businesses),
        "audited": 0,
        "buckets": {"qualified": 0, "borderline": 0, "skip": 0},
        "no_website": 0,
        "errors": 0,
        "llm_cost_usd": 0.0,
    }
    stats_lock = threading.Lock()

    def _run(business: dict) -> None:
        audit_row, error = audit_one_business(
            business,
            settings=settings,
            mock=args.mock,
            mock_map=mock_map,
            skip_vision=args.skip_vision,
            skip_screenshots=args.skip_screenshots,
            store_kind=store_kind,
        )
        with stats_lock:
            if error:
                stats["errors"] += 1
                notify.error("prodcraft_medspa.audit_site", error, count=1)
            st.insert_audit(audit_row)
            st.log_event("business", business["id"], "audited", {"bucket": audit_row.get("bucket")})
            stats["audited"] += 1
            bucket = audit_row.get("bucket")
            if bucket in stats["buckets"]:
                stats["buckets"][bucket] += 1
            if audit_row.get("has_website") is False:
                stats["no_website"] += 1
            stats["llm_cost_usd"] += audit_row.get("llm_cost_usd", 0.0)

    if candidates:
        with ThreadPoolExecutor(max_workers=MAX_WORKERS) as executor:
            futures = [executor.submit(_run, b) for b in candidates]
            for future in as_completed(futures):
                future.result()

    stats["llm_cost_usd"] = round(stats["llm_cost_usd"], 6)
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
