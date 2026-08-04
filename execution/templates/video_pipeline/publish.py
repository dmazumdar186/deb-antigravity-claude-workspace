"""
description: Publish stage of the video pipeline template. Takes a finished
             video file (typically compose/out/final.mp4) plus a metadata JSON
             and either publishes to configured platforms via MCP tools
             (mcp__higgsfield__tiktok_publish for TikTok) or emits a
             manual-publish bundle when MCP isn't available. Never publishes
             on --dry-run. Cost is $0 for platform uploads themselves.
inputs:
  - --video PATH                     (finished .mp4)
  - --metadata PATH                  (title / description / hashtags / thumbnail)
  - --platforms LIST                 (comma-separated: tiktok,youtube,instagram)
  - --slug NAME
  - --dry-run                        (default true per config; validates only)
  - --live                           (actually publish)
  - --config PATH
outputs:
  - .tmp/<slug>/publish/<platform>/  (manual-publish bundle: renamed video + metadata)
  - .tmp/<slug>/publish/receipts.jsonl (per-platform post URL + timestamp)
  - stdout: JSON summary
"""

from __future__ import annotations

import argparse
import json
import logging
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("publish")

HERE = Path(__file__).resolve().parent
CONFIG_PATH_DEFAULT = HERE / "config" / "pipeline.json"


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_metadata(meta: dict, platform: str) -> list[str]:
    """Return list of validation errors for platform-specific metadata."""
    errors: list[str] = []
    if platform == "tiktok":
        if not meta.get("title") and not meta.get("caption"):
            errors.append("tiktok: 'title' or 'caption' required")
        if len(meta.get("caption", meta.get("title", ""))) > 2200:
            errors.append("tiktok: caption > 2200 chars")
    elif platform == "youtube":
        if not meta.get("title"):
            errors.append("youtube: 'title' required")
        if len(meta.get("title", "")) > 100:
            errors.append("youtube: title > 100 chars")
        if len(meta.get("description", "")) > 5000:
            errors.append("youtube: description > 5000 chars")
    elif platform == "instagram":
        if not meta.get("caption"):
            errors.append("instagram: 'caption' required")
        if len(meta.get("caption", "")) > 2200:
            errors.append("instagram: caption > 2200 chars")
    return errors


def _emit_manual_bundle(video: Path, meta: dict, platform: str,
                        publish_dir: Path) -> dict:
    """
    Emit a manual-publish bundle for platforms without an MCP integration
    or when --dry-run. Bundle = renamed video + metadata JSON in a per-platform
    directory the operator can zip and upload manually.
    """
    plat_dir = publish_dir / platform
    plat_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")
    target_video = plat_dir / f"{ts}_{platform}.mp4"
    shutil.copy2(video, target_video)
    meta_path = plat_dir / f"{ts}_{platform}_metadata.json"
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2),
                         encoding="utf-8")
    return {
        "platform": platform, "mode": "manual-bundle",
        "video": str(target_video), "metadata": str(meta_path),
    }


def _publish_tiktok(video: Path, meta: dict, live: bool) -> dict:
    """
    Real integration goes through mcp__higgsfield__tiktok_publish when invoked
    from an interactive Claude session. This function is a STUB in the template
    — scaffolded projects call the MCP tool from the assistant layer, then
    invoke this script with the resulting post URL for receipt logging.
    """
    if not live:
        return {"platform": "tiktok", "mode": "dry-run", "would_publish": True}
    log.warning("tiktok publish is stubbed — invoke mcp__higgsfield__tiktok_publish "
                "from an interactive Claude session, then log the URL here.")
    return {"platform": "tiktok", "mode": "stub", "url": None}


def _publish_youtube(video: Path, meta: dict, live: bool) -> dict:
    """
    Real integration: YouTube Data API v3 videos.insert (resumable upload).
    Requires OAuth via YOUTUBE_CLIENT_SECRETS_PATH + YOUTUBE_TOKEN_PATH.
    STUB in the template.
    """
    if not live:
        return {"platform": "youtube", "mode": "dry-run", "would_publish": True}
    log.warning("youtube publish is stubbed — implement google-api-python-client "
                "videos().insert(...) in the scaffolded project.")
    return {"platform": "youtube", "mode": "stub", "url": None}


def _publish_instagram(video: Path, meta: dict, live: bool) -> dict:
    """
    Real integration: Meta Graph API /media (video container) + /media_publish.
    Requires INSTAGRAM_ACCESS_TOKEN + INSTAGRAM_ACCOUNT_ID.
    STUB in the template.
    """
    if not live:
        return {"platform": "instagram", "mode": "dry-run", "would_publish": True}
    log.warning("instagram publish is stubbed.")
    return {"platform": "instagram", "mode": "stub", "url": None}


PLATFORMS = {
    "tiktok": _publish_tiktok,
    "youtube": _publish_youtube,
    "youtube_shorts": _publish_youtube,
    "instagram": _publish_instagram,
    "instagram_reels": _publish_instagram,
}


def main() -> int:
    ap = argparse.ArgumentParser(description="Video pipeline: publish stage")
    ap.add_argument("--video", type=Path, required=True)
    ap.add_argument("--metadata", type=Path, default=None,
                    help="JSON with title/description/caption/hashtags; if omitted "
                         "derives minimal metadata from --slug + timestamp")
    ap.add_argument("--platforms", default=None,
                    help="comma-separated; default from config target_platforms")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--dry-run", action="store_true", default=None)
    ap.add_argument("--live", action="store_true")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH_DEFAULT)
    args = ap.parse_args()

    is_dry_run = args.dry_run is True or not args.live

    if not args.video.exists() or args.video.stat().st_size == 0:
        log.error("video not found or empty: %s", args.video)
        return 2

    cfg = _load_config(args.config)
    slug = args.slug or cfg.get("slug", "video")
    platforms = (args.platforms.split(",") if args.platforms
                 else cfg["target_platforms"])

    if args.metadata and args.metadata.exists():
        meta = json.loads(args.metadata.read_text(encoding="utf-8"))
    else:
        meta = {
            "title": f"{slug} — {datetime.now(timezone.utc).strftime('%Y-%m-%d')}",
            "caption": f"Auto-generated with the workspace video pipeline. Slug: {slug}",
            "hashtags": [],
        }

    # Per-platform metadata validation
    validation_errors: list[str] = []
    for p in platforms:
        validation_errors.extend(_validate_metadata(meta, p.split("_")[0]))
    if validation_errors:
        log.error("metadata validation failed:")
        for e in validation_errors:
            log.error("  - %s", e)
        return 2

    publish_dir = HERE / ".tmp" / slug / "publish"
    publish_dir.mkdir(parents=True, exist_ok=True)
    receipts_path = publish_dir / "receipts.jsonl"

    results = []
    for platform in platforms:
        handler = PLATFORMS.get(platform)
        if handler is None:
            log.warning("no handler for platform %s — emitting manual bundle", platform)
            r = _emit_manual_bundle(args.video, meta, platform, publish_dir)
        else:
            r = handler(args.video, meta, live=(not is_dry_run))
            # Always emit the manual bundle as a fallback record.
            _emit_manual_bundle(args.video, meta, platform, publish_dir)
        r["ts"] = datetime.now(timezone.utc).isoformat()
        with receipts_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
        results.append(r)

    print(json.dumps({
        "mode": "dry-run" if is_dry_run else "live",
        "slug": slug, "platforms": platforms,
        "results": results, "receipts": str(receipts_path),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
