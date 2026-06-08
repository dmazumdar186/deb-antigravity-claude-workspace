"""Pull a public Instagram profile's recent posts via instaloader.

Output layout (matches generate_demo.py's fetch_ig_manual expectation):
  .tmp/rosy_origami/{slug}/ig_export/
    captions.json      [{type, caption, timestamp, permalink, image}, ...]
    <shortcode>.jpg    one image per post

Only use this on profiles where the user has consent / insider access.

Usage:
  py execution/content/rosy_origami/fetchers/ig_instaloader.py \\
      --handle giofranceparis --tenant gio_paris --max 20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import instaloader

ROOT = Path(__file__).resolve().parents[4]
TMP_DIR = ROOT / ".tmp" / "rosy_origami"


def _classify(caption: str, post_date: datetime) -> str:
    """Heuristic event/upcoming/post classifier — refined by LLM later."""
    lc = caption.lower()
    upcoming_signals = [
        "join us", "rsvp", "register", "save the date", "coming up",
        "upcoming", "this saturday", "this sunday", "next week",
        "à venir", "rejoignez", "inscrivez",
    ]
    event_signals = [
        "thank you", "great evening", "wonderful", "wrapped up",
        "recap", "highlights", "what an", "merci", "soirée",
    ]
    if any(s in lc for s in upcoming_signals):
        return "ig_upcoming"
    if any(s in lc for s in event_signals):
        return "ig_event"
    if (datetime.now(timezone.utc) - post_date).days < 14:
        return "ig_upcoming"
    return "ig_event"


def fetch_profile(handle: str, tenant_slug: str, max_posts: int) -> None:
    L = instaloader.Instaloader(
        download_pictures=True,
        download_videos=False,
        download_video_thumbnails=False,
        download_geotags=False,
        download_comments=False,
        save_metadata=False,
        compress_json=False,
        post_metadata_txt_pattern="",
    )

    out_dir = TMP_DIR / tenant_slug / "ig_export"
    out_dir.mkdir(parents=True, exist_ok=True)

    profile = instaloader.Profile.from_username(L.context, handle)
    print(
        f"Profile loaded: @{profile.username} "
        f"({profile.full_name!r}, {profile.followers} followers, "
        f"{profile.mediacount} posts, is_business={profile.is_business_account}, "
        f"category={profile.business_category_name!r})",
        file=sys.stderr,
    )

    captions: list[dict] = []
    count = 0
    for post in profile.get_posts():
        if count >= max_posts:
            break
        shortcode = post.shortcode
        try:
            L.download_pic(
                str(out_dir / shortcode),
                post.url,
                mtime=post.date_utc,
            )
            image_filename = f"{shortcode}.jpg"
        except Exception as e:
            print(f"  WARN: image download failed for {shortcode}: {e}", file=sys.stderr)
            image_filename = None

        caption_text = post.caption or ""
        item = {
            "type": _classify(caption_text, post.date_utc),
            "title": "",
            "caption": caption_text,
            "timestamp": post.date_utc.isoformat(),
            "permalink": f"https://www.instagram.com/p/{shortcode}/",
            "image": image_filename,
            "shortcode": shortcode,
            "likes": post.likes,
        }
        captions.append(item)
        count += 1
        print(f"  [{count}/{max_posts}] {shortcode} ({post.date_utc:%Y-%m-%d}): "
              f"{caption_text[:80].strip()!r}...", file=sys.stderr)

    captions_file = out_dir / "captions.json"
    captions_file.write_text(
        json.dumps(captions, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nWrote {len(captions)} posts to {captions_file}", file=sys.stderr)

    profile_meta = out_dir / "profile.json"
    profile_meta.write_text(
        json.dumps(
            {
                "handle": handle,
                "full_name": profile.full_name,
                "bio": profile.biography,
                "external_url": profile.external_url,
                "followers": profile.followers,
                "post_count": profile.mediacount,
                "is_business_account": profile.is_business_account,
                "business_category_name": profile.business_category_name,
                "fetched_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"Wrote profile meta to {profile_meta}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--handle", required=True, help="IG handle without @")
    p.add_argument("--tenant", required=True, help="Tenant slug (e.g. gio_paris)")
    p.add_argument("--max", type=int, default=20, help="Max posts to fetch")
    args = p.parse_args()
    fetch_profile(args.handle, args.tenant, args.max)
    return 0


if __name__ == "__main__":
    sys.exit(main())
