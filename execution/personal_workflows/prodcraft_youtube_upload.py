"""
description: Upload an approved ProdCraft video to YouTube via Data API v3 (resumable upload). Reads the oldest approved item from .tmp/prodcraft/queue/approved/, uploads it, then marks the metadata.json with youtube_video_id + uploaded_at and moves the directory to .tmp/prodcraft/queue/uploaded/.
inputs:
    CLI:
        --slug X              upload a specific slug (optional; default = oldest approved)
        --client-secret PATH  Google OAuth desktop client_secret.json (default: .tmp/prodcraft/youtube_client_secret.json or $YOUTUBE_CLIENT_SECRET)
        --token PATH          OAuth token cache (default: .tmp/prodcraft/youtube_token.json or $YOUTUBE_TOKEN)
        --dry-run             validate metadata + token, do not upload
    env:
        YOUTUBE_CLIENT_SECRET / YOUTUBE_TOKEN — override default paths
outputs:
    Uploaded YouTube video at videos.youtube.com/watch?v=<id>; queue dir moved to .tmp/prodcraft/queue/uploaded/<slug>/; metadata.json gets youtube_video_id + uploaded_at + youtube_url
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import InstalledAppFlow
    from google.auth.transport.requests import Request
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    from googleapiclient.http import MediaFileUpload
except ImportError as exc:
    raise SystemExit(
        "Missing Google client libs. Install: py -m pip install google-auth google-auth-oauthlib google-api-python-client"
    ) from exc

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
QUEUE_ROOT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "queue"
DEFAULT_CLIENT_SECRET = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "youtube_client_secret.json"
DEFAULT_TOKEN = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "youtube_token.json"

SCOPES = ["https://www.googleapis.com/auth/youtube.upload"]


def _get_credentials(client_secret: Path, token: Path) -> Credentials:
    creds: Credentials | None = None
    if token.exists():
        creds = Credentials.from_authorized_user_file(str(token), SCOPES)
    if creds and creds.valid:
        return creds
    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token.write_text(creds.to_json(), encoding="utf-8")
        return creds
    if not client_secret.exists():
        raise SystemExit(
            f"OAuth not initialized. Place desktop OAuth client_secret JSON at {client_secret} (see "
            f"https://console.cloud.google.com/apis/credentials → Create Credentials → OAuth client ID "
            f"→ Desktop). Add your YouTube account as a test user under the OAuth consent screen. Then re-run."
        )
    flow = InstalledAppFlow.from_client_secrets_file(str(client_secret), SCOPES)
    creds = flow.run_local_server(port=0)
    token.parent.mkdir(parents=True, exist_ok=True)
    token.write_text(creds.to_json(), encoding="utf-8")
    return creds


def _pick_item(slug: str | None) -> tuple[Path, dict]:
    approved = QUEUE_ROOT / "approved"
    if not approved.is_dir():
        raise SystemExit(f"No approved/ dir: {approved}")
    candidates: list[tuple[str, Path, dict]] = []
    for sub in approved.iterdir():
        if not sub.is_dir():
            continue
        meta_path = sub / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if slug and meta.get("slug") != slug:
            continue
        ts = meta.get("approved_at") or meta.get("added_at") or ""
        candidates.append((ts, sub, meta))
    candidates.sort(key=lambda x: x[0])
    if not candidates:
        raise SystemExit(f"No approved items matching slug={slug!r}" if slug else "No approved items to upload")
    _, sub, meta = candidates[0]
    return sub, meta


def upload(youtube, item_dir: Path, meta: dict) -> str:
    body = {
        "snippet": {
            "title": meta["title"][:100],
            "description": meta.get("description", "")[:5000],
            "tags": meta.get("tags", []),
            "categoryId": str(meta.get("category_id", "27")),
            "defaultLanguage": meta.get("language", "en"),
            "defaultAudioLanguage": meta.get("language", "en"),
        },
        "status": {
            "privacyStatus": meta.get("privacy", "private"),
            "selfDeclaredMadeForKids": False,
            "embeddable": True,
        },
    }
    if meta.get("scheduled_at"):
        body["status"]["publishAt"] = meta["scheduled_at"]
        body["status"]["privacyStatus"] = "private"
    mp4 = item_dir / "final.mp4"
    if not mp4.is_file():
        raise SystemExit(f"Missing video: {mp4}")
    media = MediaFileUpload(str(mp4), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            pct = int(status.progress() * 100)
            print(f"uploading… {pct}%", file=sys.stderr, flush=True)
    return response["id"]


def main() -> int:
    p = argparse.ArgumentParser(description="Upload an approved ProdCraft video to YouTube.")
    p.add_argument("--slug", default=None)
    p.add_argument(
        "--client-secret",
        default=os.environ.get("YOUTUBE_CLIENT_SECRET", str(DEFAULT_CLIENT_SECRET)),
    )
    p.add_argument(
        "--token",
        default=os.environ.get("YOUTUBE_TOKEN", str(DEFAULT_TOKEN)),
    )
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    item_dir, meta = _pick_item(args.slug)
    print(json.dumps({"selected": meta["slug"], "mp4": str(item_dir / "final.mp4"), "title": meta["title"]}, indent=2))

    client_secret = Path(args.client_secret).resolve()
    token = Path(args.token).resolve()

    if args.dry_run:
        ok_secret = client_secret.exists()
        ok_token = token.exists()
        print(json.dumps({"dry_run": True, "client_secret_present": ok_secret, "token_present": ok_token}, indent=2))
        return 0

    creds = _get_credentials(client_secret, token)
    youtube = build("youtube", "v3", credentials=creds, cache_discovery=False)

    try:
        video_id = upload(youtube, item_dir, meta)
    except HttpError as exc:
        raise SystemExit(f"YouTube API error: {exc}")

    meta["youtube_video_id"] = video_id
    meta["youtube_url"] = f"https://www.youtube.com/watch?v={video_id}"
    meta["uploaded_at"] = datetime.now(timezone.utc).isoformat()
    (item_dir / "metadata.json").write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    uploaded_root = QUEUE_ROOT / "uploaded"
    uploaded_root.mkdir(parents=True, exist_ok=True)
    dst = uploaded_root / item_dir.name
    shutil.move(str(item_dir), str(dst))

    print(json.dumps({"ok": True, "video_id": video_id, "url": meta["youtube_url"], "moved_to": str(dst)}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
