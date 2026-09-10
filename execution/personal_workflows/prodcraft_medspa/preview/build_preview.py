"""
build_preview.py
description: Assembles business.json per CONTRACTS.md for each qualified/deliverable/contactable business,
    lints it, builds the Next.js template (or reuses/synthesizes a build under --skip-build/--mock), uploads
    the static export to R2, publishes it on the preview Worker, and upserts the `previews` row.
inputs: --metro X | --business-id ID (one required), --limit N, --mock, --store {local,supabase},
    --store-root PATH, --skip-build, --force. Env per CONTRACTS.md ("preview" stage): CLOUDFLARE_API_TOKEN,
    CLOUDFLARE_ACCOUNT_ID, R2_BUCKET, R2_ACCESS_KEY_ID, R2_SECRET_ACCESS_KEY, PREVIEW_PUBLISH_SECRET,
    PREVIEW_BASE_DOMAIN, ANTHROPIC_API_KEY (extract_services, live only).
outputs: template/business.json written + `npm run build` run (unless --skip-build/synthesized), files
    uploaded to R2 (or .tmp/prodcraft_medspa/r2/ under --mock), a `previews` row per built business, `events`
    rows for every skip/lint-failure/error, stdout JSON stat line
    {"script":"build_preview","in","built","uploaded","published","lint_failed","skipped_unchanged","errors",
    "llm_cost_usd"}.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[4]))  # repo root, for direct-script execution

from execution.personal_workflows.prodcraft_medspa.common import config, models, notify  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common import slug as slug_module  # noqa: E402
from execution.personal_workflows.prodcraft_medspa.common.store import (  # noqa: E402
    LocalStore,
    SupabaseStore,
    get_store,
)
from execution.personal_workflows.prodcraft_medspa.preview import content_lint, extract_services, publish, r2  # noqa: E402

PKG_ROOT = Path(__file__).resolve().parents[1]
TEMPLATE_DIR = PKG_ROOT / "template"
PROMPTS_FIXTURES_ROOT = PKG_ROOT / "prompts" / "fixtures"

# 6-color palette + 4-hero pool, both picked deterministically by sha256(slug) — never by Python's hash()
# (randomized per-process without PYTHONHASHSEED, which would break rebuild stability).
PALETTE = ["#7C5CFF", "#0C76B7", "#2E8B57", "#B5495B", "#3D5A80", "#C08552"]
HERO_IMAGES = ["hero-01.png", "hero-02.png", "hero-03.png", "hero-04.png"]
ACCENT_COLOR = "#F4F1EA"

_DAY_ORDER = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
_DAY_NAME_TO_ABBR = {
    "Monday": "Mon",
    "Tuesday": "Tue",
    "Wednesday": "Wed",
    "Thursday": "Thu",
    "Friday": "Fri",
    "Saturday": "Sat",
    "Sunday": "Sun",
}
_DIGITS_RE = re.compile(r"\d")
_DASH_CHARS = ("–", "—", "−")  # en dash, em dash, minus sign
_THIN_SPACE_CHARS = (" ", " ", " ")

_BUILD_LOCK = threading.Lock()  # `npm run build` writes to the shared template/ dir — serialize builds.


# ---------------------------------------------------------------------------
# Deterministic per-slug picks
# ---------------------------------------------------------------------------


def _hash_index(value: str, modulus: int) -> int:
    digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    return int(digest, 16) % modulus


def hero_image_for_slug(slug: str) -> str:
    return HERO_IMAGES[_hash_index(slug, len(HERO_IMAGES))]


def primary_color_for_slug(slug: str) -> str:
    return PALETTE[_hash_index(slug, len(PALETTE))]


# ---------------------------------------------------------------------------
# Phone formatting
# ---------------------------------------------------------------------------


def format_phone(raw: str | None) -> tuple[str, str]:
    """Return (display, phone_href). display is '(XXX) XXX-XXXX' for a confidently-parsed 10-digit US number;
    otherwise the original string is returned unchanged so content_lint's phone-format rule fails the build
    closed rather than fabricating a fake-looking number."""
    digits = "".join(_DIGITS_RE.findall(raw or ""))
    if len(digits) == 11 and digits.startswith("1"):
        digits = digits[1:]
    if len(digits) != 10:
        href = f"tel:+{digits}" if digits else "tel:+0000000000"
        return (raw or "", href)
    display = f"({digits[0:3]}) {digits[3:6]}-{digits[6:10]}"
    href = f"tel:+1{digits}"
    return (display, href)


# ---------------------------------------------------------------------------
# Google Maps URL
# ---------------------------------------------------------------------------


def google_maps_url(business: dict) -> str:
    explicit = business.get("google_maps_url")
    if explicit:
        return explicit
    place_id = business.get("place_id") or ""
    return f"https://www.google.com/maps/place/?q=place_id:{place_id}"


# ---------------------------------------------------------------------------
# Hours — from Places `regularOpeningHours.weekdayDescriptions`, wherever discovery/audit stashed it.
# discovery/enrich land raw Places payloads in different spots depending on how they're eventually wired;
# this checks every plausible location and falls back to 7 null rows rather than guessing.
# ---------------------------------------------------------------------------


def _normalize_hours_text(text: str) -> str:
    normalized = text
    for ch in _THIN_SPACE_CHARS:
        normalized = normalized.replace(ch, " ")
    for ch in _DASH_CHARS:
        normalized = normalized.replace(ch, "-")
    return normalized.strip()


def parse_weekday_descriptions(descriptions: list[str] | None) -> list[dict]:
    by_day: dict[str, dict] = {}
    for line in descriptions or []:
        if not isinstance(line, str) or ":" not in line:
            continue
        day_name, rest = line.split(":", 1)
        abbr = _DAY_NAME_TO_ABBR.get(day_name.strip())
        if not abbr:
            continue
        rest = _normalize_hours_text(rest)
        if not rest or rest.lower() == "closed":
            by_day[abbr] = {"day": abbr, "open": None, "close": None}
            continue
        parts = [p.strip() for p in rest.split("-", 1)]
        if len(parts) == 2 and all(parts):
            by_day[abbr] = {"day": abbr, "open": parts[0], "close": parts[1]}
        else:
            by_day[abbr] = {"day": abbr, "open": None, "close": None}
    return [by_day.get(day, {"day": day, "open": None, "close": None}) for day in _DAY_ORDER]


def _all_null_hours() -> list[dict]:
    return [{"day": d, "open": None, "close": None} for d in _DAY_ORDER]


def extract_hours(business: dict, audit: dict | None) -> list[dict]:
    candidates = [
        ((audit or {}).get("raw") or {}).get("places") or {},
        (audit or {}).get("raw") or {},
        (business or {}).get("raw") or {},
        business or {},
    ]
    for source in candidates:
        if not isinstance(source, dict):
            continue
        roh = source.get("regularOpeningHours") or source.get("regular_opening_hours")
        if isinstance(roh, dict):
            wd = roh.get("weekdayDescriptions") or roh.get("weekday_descriptions")
            if wd:
                return parse_weekday_descriptions(wd)
    return _all_null_hours()


# ---------------------------------------------------------------------------
# business.json assembly + content hash
# ---------------------------------------------------------------------------


def assemble_business_json(
    business: dict,
    audit: dict | None,
    services_result: dict,
    *,
    slug: str,
    slug_suffix: str,
    host: str,
    expires_at: str,
) -> dict:
    phone, phone_href = format_phone(business.get("phone"))
    name = business.get("name") or ""
    return {
        "schema_version": "1.0",
        "name": name,
        "slug": slug,
        "slug_suffix": slug_suffix,
        "city": business.get("city") or "",
        "state": (business.get("state") or "").strip()[:2].upper(),
        "address": business.get("address") or "",
        "phone": phone,
        "phone_href": phone_href,
        "hours": extract_hours(business, audit),
        "services": services_result["services"],
        "rating": business.get("rating") if business.get("rating") is not None else 0,
        "review_count": business.get("review_count") if business.get("review_count") is not None else 0,
        "google_maps_url": google_maps_url(business),
        "tagline": services_result["tagline"],
        "primary_color": primary_color_for_slug(slug),
        "accent_color": ACCENT_COLOR,
        "hero_image": hero_image_for_slug(slug),
        "preview": {
            "expires_at": expires_at,
            "remove_url": f"https://{host}/remove",
            "watermark": content_lint.watermark_for(name),
        },
        "booking_demo": True,
    }


def content_hash(business_json: dict) -> str:
    """sha256 of canonical JSON, with preview.expires_at excluded (rebuilds shouldn't churn just because
    the expiry date moved a day)."""
    clone = json.loads(json.dumps(business_json, default=str))
    preview = clone.get("preview")
    if isinstance(preview, dict):
        preview.pop("expires_at", None)
    canonical = json.dumps(clone, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Store helpers — Store protocol has no "previews by business_id" query; this reaches into each
# implementation's own internals (LocalStore._read / SupabaseStore._request) rather than editing
# common/store.py, which is out of this package's build scope. Flagged in the build report.
# ---------------------------------------------------------------------------


def find_previews_for_business(store, business_id: str) -> list[dict]:
    if isinstance(store, LocalStore):
        return [r for r in store._read("previews") if r.get("business_id") == business_id]  # noqa: SLF001
    if isinstance(store, SupabaseStore):
        resp = store._request(  # noqa: SLF001
            "GET", f"previews?business_id=eq.{business_id}", headers=store._headers()  # noqa: SLF001
        )
        return resp.json()
    return []


def eligibility_reason(business: dict, audit: dict | None) -> str | None:
    """None means eligible; otherwise the drop_reason-style string to log."""
    if business.get("do_not_contact"):
        return "do_not_contact"
    if business.get("email_status") != "deliverable":
        return "email_not_deliverable"
    if audit is None:
        return "no_audit"
    if audit.get("bucket") != "qualified":
        return f"bucket_{audit.get('bucket')}"
    return None


# ---------------------------------------------------------------------------
# Template build
# ---------------------------------------------------------------------------


def _synthesize_minimal_site(business_json: dict, build_dir: Path) -> None:
    """A minimal static site (index.html + robots.txt) carrying the watermark + noindex meta, used when
    the Next.js template isn't present yet or --skip-build is set with no cached build — keeps the pipeline
    exercisable end-to-end without Node, per CONTRACTS.md."""
    build_dir.mkdir(parents=True, exist_ok=True)
    watermark = business_json["preview"]["watermark"]
    name = business_json["name"]
    tagline = business_json["tagline"]
    html = (
        "<!doctype html>\n<html><head><meta charset=\"utf-8\">\n"
        '<meta name="robots" content="noindex,nofollow">\n'
        f"<title>{name}</title></head><body>\n"
        f"<main><h1>{name}</h1><p>{tagline}</p></main>\n"
        f'<footer data-watermark="true">{watermark}</footer>\n'
        "</body></html>\n"
    )
    (build_dir / "index.html").write_text(html, encoding="utf-8")
    (build_dir / "robots.txt").write_text("User-agent: *\nDisallow: /\n", encoding="utf-8")


def build_template_site(
    business_json: dict,
    *,
    template_dir: Path,
    build_dir: Path,
    skip_build: bool,
    force_synthetic: bool = False,
) -> Path:
    if skip_build and (build_dir / "index.html").exists():
        return build_dir

    template_present = (template_dir / "package.json").exists()
    if force_synthetic or not template_present:
        _synthesize_minimal_site(business_json, build_dir)
        return build_dir

    (template_dir / "business.json").write_text(json.dumps(business_json, indent=2), encoding="utf-8")
    with _BUILD_LOCK:  # builds share the template/ working dir — serialize (python-hardening.md #2)
        subprocess.run(
            ["npm", "run", "build"],
            cwd=template_dir,
            check=True,
            timeout=600,
            encoding="utf-8",
            errors="replace",
        )
    out_dir = template_dir / "out"
    if build_dir.exists():
        shutil.rmtree(build_dir)
    shutil.copytree(out_dir, build_dir)
    return build_dir


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def _process_business(
    business: dict,
    *,
    store,
    mock: bool,
    skip_build: bool,
    force: bool,
    template_dir: Path,
    base_domain: str,
    tmp_root: Path,
    stats: dict,
) -> None:
    business_id = business.get("id")
    audit = store.latest_audit(business_id)
    reason = eligibility_reason(business, audit)
    if reason:
        store.log_event("business", business_id, "preview_skip", {"reason": reason})
        return

    existing_previews = find_previews_for_business(store, business_id)
    existing_sorted = sorted(existing_previews, key=lambda p: p.get("created_at") or "")
    slug = business.get("slug") or slug_module.slugify(business.get("name") or "business")
    slug_suffix = existing_sorted[-1]["slug_suffix"] if existing_sorted else slug_module.random_suffix()

    services_result = extract_services.extract_services(
        business, audit, mock=mock, fixtures_root=PROMPTS_FIXTURES_ROOT
    )
    stats["llm_cost_usd"] += services_result["llm_cost_usd"]

    expiry_days = int(store.get_config("preview_expiry_days", 30) or 30)
    expires_at = (date.today() + timedelta(days=expiry_days)).isoformat()
    host = slug_module.preview_host(slug, slug_suffix, base_domain)

    business_json = assemble_business_json(
        business, audit, services_result, slug=slug, slug_suffix=slug_suffix, host=host, expires_at=expires_at
    )

    violations = content_lint.lint(business_json)
    if violations:
        stats["lint_failed"] += 1
        store.log_event("business", business_id, "preview_lint_failed", {"violations": violations})
        return

    hash_ = content_hash(business_json)
    unchanged = any(p.get("content_hash") == hash_ and not p.get("takedown") for p in existing_previews)
    if unchanged and not force:
        stats["skipped_unchanged"] += 1
        store.log_event("business", business_id, "preview_skip", {"reason": "unchanged_content"})
        return

    build_dir = tmp_root / "builds" / host
    build_template_site(
        business_json,
        template_dir=template_dir,
        build_dir=build_dir,
        skip_build=skip_build,
        force_synthetic=mock and skip_build,
    )
    stats["built"] += 1

    if mock:
        r2_client = r2.MockR2(root=tmp_root / "r2")
    else:
        r2_client = r2.R2Client(
            account_id=os.environ.get("CLOUDFLARE_ACCOUNT_ID", ""),
            access_key=os.environ.get("R2_ACCESS_KEY_ID", ""),
            secret_key=os.environ.get("R2_SECRET_ACCESS_KEY", ""),
            bucket=os.environ.get("R2_BUCKET", "prodcraft-previews"),
        )
    prefix = f"previews/{slug}-{slug_suffix}"
    r2_client.upload_dir(build_dir, prefix)
    stats["uploaded"] += 1

    preview_id = str(uuid.uuid4())
    publish.publish(host, expires_at, business_id, preview_id, mock=mock, meta_dir=tmp_root / "kv")
    stats["published"] += 1

    preview_row = {
        "id": preview_id,
        "business_id": business_id,
        "template_id": "medspa-v1",
        "slug_suffix": slug_suffix,
        "subdomain_url": f"https://{host}",
        "status": "review",
        "content": business_json,
        "content_hash": hash_,
        "deployed_at": models.now_iso(),
        "expires_at": expires_at,
        "takedown": False,
    }
    store.upsert_preview(preview_row)
    store.log_event(
        "preview", preview_id, "built", {"host": host, "used_fallback_services": services_result["used_fallback"]}
    )
    store.log_event("preview", preview_id, "published", {"host": host})


def main() -> None:
    settings = config.bootstrap()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--metro", default=None)
    parser.add_argument("--business-id", default=None)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--mock", action="store_true")
    parser.add_argument("--store", choices=["local", "supabase"], default=None)
    parser.add_argument("--store-root", default=None)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--force", action="store_true")
    args = parser.parse_args()

    if not args.metro and not args.business_id:
        parser.error("either --metro or --business-id is required")

    store_kind = args.store or ("local" if args.mock else None)
    store = get_store(kind=store_kind, root=args.store_root)

    stats = {
        "script": "build_preview",
        "in": 0,
        "built": 0,
        "uploaded": 0,
        "published": 0,
        "lint_failed": 0,
        "skipped_unchanged": 0,
        "errors": 0,
        "llm_cost_usd": 0.0,
    }

    if args.business_id:
        biz = store.get_business(args.business_id)
        businesses = [biz] if biz else []
    else:
        businesses = store.find_businesses(
            metro=args.metro, bucket="qualified", has_email=True, do_not_contact=False
        )

    if args.limit is not None:
        businesses = businesses[: args.limit]

    base_domain = os.environ.get("PREVIEW_BASE_DOMAIN") or "preview.prodcraft.fyi"

    for business in businesses:
        stats["in"] += 1
        business_id = business.get("id")
        try:
            _process_business(
                business,
                store=store,
                mock=args.mock,
                skip_build=args.skip_build,
                force=args.force,
                template_dir=TEMPLATE_DIR,
                base_domain=base_domain,
                tmp_root=settings.TMP,
                stats=stats,
            )
        except Exception as exc:  # noqa: BLE001 — one bad business must not abort the whole metro run
            stats["errors"] += 1
            try:
                store.log_event("business", business_id, "preview_error", {"error": str(exc)})
            except Exception:  # noqa: BLE001 — logging must never mask the original failure
                pass
            notify.error("build_preview", f"{business_id}: {exc}")

    stats["llm_cost_usd"] = round(stats["llm_cost_usd"], 6)
    print(json.dumps(stats))


if __name__ == "__main__":
    main()
