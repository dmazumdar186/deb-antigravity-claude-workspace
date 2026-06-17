"""
description: Ingest a YouTube channel's public uploads + per-video captions via YT Data API v3 + youtube-transcript-api. Two modes — preflight (cheap count + caption-availability map) and ingest (full transcripts + voice-profile bundle).
inputs:
    CLI args:
        --handle / --channel-id  one of these (handle e.g. @ProdCraft)
        --mode {preflight,ingest}
        --top-n N                ingest mode: how many top-view videos to pull (default 8)
        --out-dir PATH           override output dir (default .tmp/prodcraft/)
    Env vars:
        YT_DATA_API_KEY          required
outputs:
    preflight: .tmp/{slug}/preflight.json with {channel_id, total_videos, captioned, not_captioned, sample[]}
    ingest:    .tmp/{slug}/videos/{video_id}.json (transcript + meta),
               .tmp/{slug}/voice_profile_seed.txt (concatenated transcripts joined for voice profile bundle),
               .tmp/{slug}/ingest_summary.json
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()


def _api_client():
    """Build a YouTube Data API v3 client. Fails fast if key missing."""
    key = os.environ.get("YT_DATA_API_KEY")
    if not key:
        raise SystemExit("YT_DATA_API_KEY missing in .env")
    try:
        from googleapiclient.discovery import build
    except ImportError as e:
        raise SystemExit("google-api-python-client not installed. Run: py -m pip install google-api-python-client") from e
    return build("youtube", "v3", developerKey=key, cache_discovery=False)


def resolve_channel_id(yt, handle: str | None, channel_id: str | None) -> tuple[str, str]:
    """Return (channel_id, channel_title). Prefer explicit channel_id; else resolve handle."""
    if channel_id:
        resp = yt.channels().list(part="snippet", id=channel_id).execute()
    else:
        h = handle.lstrip("@") if handle else None
        if not h:
            raise SystemExit("Provide --handle or --channel-id")
        # channels.list supports forHandle as of late 2023.
        resp = yt.channels().list(part="snippet", forHandle=h).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit(f"Channel not found (handle={handle}, channel_id={channel_id})")
    ch = items[0]
    return ch["id"], ch["snippet"]["title"]


def get_uploads_playlist(yt, channel_id: str) -> str:
    resp = yt.channels().list(part="contentDetails", id=channel_id).execute()
    items = resp.get("items", [])
    if not items:
        raise SystemExit(f"Channel {channel_id} has no contentDetails")
    return items[0]["contentDetails"]["relatedPlaylists"]["uploads"]


def list_uploads(yt, playlist_id: str) -> list[dict[str, Any]]:
    """Paginate through uploads playlist. Returns list of {video_id, title, published_at}."""
    videos: list[dict[str, Any]] = []
    page_token: str | None = None
    while True:
        resp = yt.playlistItems().list(
            part="snippet,contentDetails",
            playlistId=playlist_id,
            maxResults=50,
            pageToken=page_token,
        ).execute()
        for it in resp.get("items", []):
            videos.append({
                "video_id": it["contentDetails"]["videoId"],
                "title": it["snippet"]["title"],
                "published_at": it["contentDetails"].get("videoPublishedAt", ""),
            })
        page_token = resp.get("nextPageToken")
        if not page_token:
            break
    return videos


def fetch_video_stats(yt, video_ids: list[str]) -> dict[str, dict[str, Any]]:
    """Batch up to 50 IDs per call. Returns {video_id: {view_count, duration, caption_flag}}."""
    out: dict[str, dict[str, Any]] = {}
    for i in range(0, len(video_ids), 50):
        chunk = video_ids[i : i + 50]
        resp = yt.videos().list(
            part="statistics,contentDetails",
            id=",".join(chunk),
        ).execute()
        for it in resp.get("items", []):
            out[it["id"]] = {
                "view_count": int(it.get("statistics", {}).get("viewCount", 0)),
                "duration": it.get("contentDetails", {}).get("duration", ""),
                # contentDetails.caption is "true" / "false" string for MANUAL captions only.
                # Auto-captions aren't reflected — youtube-transcript-api is authoritative.
                "manual_caption_flag": it.get("contentDetails", {}).get("caption", "false") == "true",
            }
    return out


def check_transcript_available(video_id: str) -> tuple[bool, str]:
    """Try to fetch a transcript; return (available, reason). No retry — preflight is fast-fail."""
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api._errors import (
            NoTranscriptFound,
            TranscriptsDisabled,
            VideoUnavailable,
        )
    except ImportError as e:
        raise SystemExit("youtube-transcript-api not installed. Run: py -m pip install youtube-transcript-api") from e
    try:
        try:
            api = YouTubeTranscriptApi()
            api.fetch(video_id, languages=["en", "en-US", "en-GB", "fr", "fr-FR"])
        except AttributeError:
            YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB", "fr", "fr-FR"])
        return True, "ok"
    except NoTranscriptFound:
        return False, "no_transcript"
    except TranscriptsDisabled:
        return False, "transcripts_disabled"
    except VideoUnavailable:
        return False, "video_unavailable"
    except Exception as e:
        # Network blip / rate limit — don't crash the preflight; surface and move on.
        return False, f"error: {type(e).__name__}: {e}"


def fetch_full_transcript(video_id: str) -> str:
    """Pull the transcript text concatenated. Raises on failure (ingest mode wants ground truth)."""
    from youtube_transcript_api import YouTubeTranscriptApi
    try:
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["en", "en-US", "en-GB", "fr", "fr-FR"])
        entries = [{"start": s.start, "duration": s.duration, "text": s.text} for s in fetched]
    except AttributeError:
        entries = YouTubeTranscriptApi.get_transcript(video_id, languages=["en", "en-US", "en-GB", "fr", "fr-FR"])
    return " ".join(e["text"] for e in entries).strip()


def _parse_srt(srt_text: str) -> str:
    """Strip SRT sequence numbers, timestamps, and blank lines → plain concatenated text."""
    import re as _re
    out: list[str] = []
    for line in srt_text.splitlines():
        s = line.strip()
        if not s:
            continue
        # Pure-digit sequence numbers
        if s.isdigit():
            continue
        # Timestamps: 00:00:00,000 --> 00:00:02,000
        if "-->" in s:
            continue
        cleaned = _re.sub(r"<[^>]+>", "", s).strip()
        if cleaned and (not out or out[-1] != cleaned):
            out.append(cleaned)
    return " ".join(out)


def fetch_full_transcript_oauth(video_id: str, credentials) -> str:
    """Channel-owner caption fetch via YT Data API v3 captions.download.

    Most reliable path: no rate limits, no anti-bot challenges, no IP block —
    just the official API endpoint scoped to videos we own.
    """
    from googleapiclient.discovery import build
    yt = build("youtube", "v3", credentials=credentials, cache_discovery=False)
    resp = yt.captions().list(part="snippet", videoId=video_id).execute()
    items = resp.get("items", [])
    if not items:
        raise RuntimeError(f"No captions on {video_id}")

    def _rank(item: dict) -> tuple[int, str]:
        lang = item.get("snippet", {}).get("language", "")
        kind = item.get("snippet", {}).get("trackKind", "")
        # Lower rank wins: manual EN > auto EN > manual FR > auto FR > other.
        if lang.startswith("en") and kind != "asr":
            return (0, item["id"])
        if lang.startswith("en"):
            return (1, item["id"])
        if lang.startswith("fr") and kind != "asr":
            return (2, item["id"])
        if lang.startswith("fr"):
            return (3, item["id"])
        return (4, item["id"])

    items.sort(key=_rank)
    caption_id = items[0]["id"]
    raw = yt.captions().download(id=caption_id, tfmt="srt").execute()
    srt_text = raw.decode("utf-8", errors="replace") if isinstance(raw, (bytes, bytearray)) else str(raw)
    return _parse_srt(srt_text)


def _parse_vtt(vtt_path: Path) -> str:
    """Strip WEBVTT header + timestamps + cue settings → plain concatenated text. Dedup adjacent repeats."""
    lines = vtt_path.read_text(encoding="utf-8", errors="replace").splitlines()
    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s or s.startswith("WEBVTT") or s.startswith("NOTE") or s.startswith("Kind:") or s.startswith("Language:"):
            continue
        # Timestamp lines look like: 00:00:01.000 --> 00:00:03.500 align:start position:0%
        if "-->" in s:
            continue
        # Strip inline cue tags like <00:00:01.500><c> ... </c>
        import re as _re
        cleaned = _re.sub(r"<[^>]+>", "", s).strip()
        if not cleaned:
            continue
        # Skip if same as previous (auto-captions often repeat lines as the window slides)
        if out and out[-1] == cleaned:
            continue
        out.append(cleaned)
    return " ".join(out)


def fetch_full_transcript_ytdlp(video_id: str, tmp_dir: Path) -> str:
    """Fallback transcript fetcher via yt-dlp CLI.

    Used when youtube-transcript-api is IP-blocked (different network path,
    different parser, survives rate-limit windows that block the python API).
    """
    import subprocess
    tmp_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    # %(ext)s expands to e.g. en.vtt; output template puts file at tmp_dir/{video_id}.en.vtt
    out_template = str(tmp_dir / f"{video_id}.%(ext)s")
    cmd = [
        "yt-dlp",
        "--skip-download",
        "--write-auto-subs",
        "--write-subs",
        "--sub-langs", "en.*,fr.*",
        "--sub-format", "vtt",
        "--quiet",
        "--no-warnings",
        "--output", out_template,
        url,
    ]
    # Per Python hardening rule #1: encoding="utf-8", errors="replace" on Windows.
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        timeout=60,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"yt-dlp returncode={proc.returncode} stderr={proc.stderr[:300]}")

    # Find the .vtt file yt-dlp produced. Prefer English manual, then English auto, then French.
    candidates = list(tmp_dir.glob(f"{video_id}*.vtt"))
    if not candidates:
        raise RuntimeError(f"yt-dlp produced no .vtt for {video_id}")

    def _rank(p: Path) -> tuple[int, str]:
        name = p.name.lower()
        # Lower rank wins. Manual EN > auto EN > manual FR > auto FR > other.
        if ".en." in name and "auto" not in name:
            return (0, name)
        if ".en." in name:
            return (1, name)
        if ".fr." in name and "auto" not in name:
            return (2, name)
        if ".fr." in name:
            return (3, name)
        return (4, name)

    candidates.sort(key=_rank)
    text = _parse_vtt(candidates[0])
    return text


def cmd_preflight(args: argparse.Namespace) -> int:
    yt = _api_client()
    channel_id, channel_title = resolve_channel_id(yt, args.handle, args.channel_id)
    uploads_pl = get_uploads_playlist(yt, channel_id)
    videos = list_uploads(yt, uploads_pl)
    print(f"Channel: {channel_title} ({channel_id})  uploads: {len(videos)}", file=sys.stderr)

    if not videos:
        out_dir = Path(args.out_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "preflight.json").write_text(
            json.dumps({"channel_id": channel_id, "channel_title": channel_title, "total_videos": 0,
                        "captioned": [], "not_captioned": [], "branch": "manual_seed_only"}, indent=2),
            encoding="utf-8",
        )
        print("0 videos. Branch: manual_seed_only", file=sys.stderr)
        return 0

    stats = fetch_video_stats(yt, [v["video_id"] for v in videos])
    for v in videos:
        v.update(stats.get(v["video_id"], {}))
    videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)

    captioned: list[dict[str, Any]] = []
    not_captioned: list[dict[str, Any]] = []
    print("Checking transcripts (this takes ~2s/video)...", file=sys.stderr)
    for v in videos:
        avail, reason = check_transcript_available(v["video_id"])
        v["transcript_available"] = avail
        v["transcript_reason"] = reason
        if avail:
            captioned.append(v)
        else:
            not_captioned.append(v)
        print(f"  {'OK ' if avail else 'NO '} {v['video_id']} | {v['title'][:60]:60s} | views={v.get('view_count', 0):>7} | {reason}", file=sys.stderr)

    n_cap = len(captioned)
    if n_cap >= 5:
        branch = "standard"
    elif n_cap >= 3:
        branch = "partial_plus_seed"
    else:
        branch = "manual_seed_only"

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "total_videos": len(videos),
        "captioned_count": n_cap,
        "not_captioned_count": len(not_captioned),
        "branch": branch,
        "captioned": captioned[:10],
        "not_captioned": not_captioned[:10],
    }
    out_path = out_dir / "preflight.json"
    out_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== PREFLIGHT SUMMARY ===", file=sys.stderr)
    print(f"Channel:        {channel_title} ({channel_id})", file=sys.stderr)
    print(f"Total uploads:  {len(videos)}", file=sys.stderr)
    print(f"Captioned:      {n_cap}", file=sys.stderr)
    print(f"Branch:         {branch}", file=sys.stderr)
    print(f"Output:         {out_path}", file=sys.stderr)
    return 0


def cmd_ingest(args: argparse.Namespace) -> int:
    yt = _api_client()
    channel_id, channel_title = resolve_channel_id(yt, args.handle, args.channel_id)
    uploads_pl = get_uploads_playlist(yt, channel_id)
    videos = list_uploads(yt, uploads_pl)
    if not videos:
        raise SystemExit(f"No uploads for channel {channel_id}")
    stats = fetch_video_stats(yt, [v["video_id"] for v in videos])
    for v in videos:
        v.update(stats.get(v["video_id"], {}))
    videos.sort(key=lambda v: v.get("view_count", 0), reverse=True)

    out_dir = Path(args.out_dir)
    videos_dir = out_dir / "videos"
    videos_dir.mkdir(parents=True, exist_ok=True)

    seed_chunks: list[str] = []
    ingested: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []

    ytdlp_tmp = out_dir / "ytdlp_cache"
    # Try to load OAuth credentials once — used as primary fetcher when present.
    oauth_creds = None
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "personal_workflows"))
        from prodcraft_oauth import get_credentials  # type: ignore
        oauth_creds = get_credentials()
        print("OAuth credentials loaded — captions.download path is primary", file=sys.stderr)
    except Exception as e_oauth:
        print(f"OAuth not available ({type(e_oauth).__name__}); falling back to yta/yt-dlp only", file=sys.stderr)

    for v in videos[: args.top_n]:
        vid = v["video_id"]
        text = ""
        used = ""
        errors: list[str] = []

        # Path 1: OAuth captions.download (official, no rate limits, channel-owner scope).
        if oauth_creds is not None:
            try:
                text = fetch_full_transcript_oauth(vid, oauth_creds)
                used = "oauth_captions"
            except Exception as e_o:
                errors.append(f"oauth={type(e_o).__name__}: {str(e_o)[:120]}")

        # Path 2: youtube-transcript-api (currently IP-blocked but cheap to attempt).
        if not text.strip():
            try:
                text = fetch_full_transcript(vid)
                used = "youtube-transcript-api"
            except Exception as e_yta:
                errors.append(f"yta={type(e_yta).__name__}")

        # Path 3: yt-dlp (last resort, needs browser cookies to bypass bot check).
        if not text.strip():
            try:
                text = fetch_full_transcript_ytdlp(vid, ytdlp_tmp)
                used = "yt-dlp"
            except Exception as e_ytdlp:
                errors.append(f"ytdlp={type(e_ytdlp).__name__}: {str(e_ytdlp)[:120]}")

        if not text.strip():
            skipped.append({"video_id": vid, "title": v["title"], "reason": "; ".join(errors) or "empty transcript"})
            print(f"SKIP {vid} | {v['title'][:60]} | {'; '.join(errors) or 'empty transcript'}", file=sys.stderr)
            continue
        rec = {
            "video_id": vid,
            "title": v["title"],
            "published_at": v.get("published_at", ""),
            "view_count": v.get("view_count", 0),
            "transcript": text,
            "transcript_chars": len(text),
            "fetched_via": used,
        }
        (videos_dir / f"{vid}.json").write_text(json.dumps(rec, indent=2, ensure_ascii=False), encoding="utf-8")
        seed_chunks.append(f"## {v['title']}\n({v.get('view_count', 0):,} views)\n\n{text}\n")
        ingested.append({"video_id": vid, "title": v["title"], "transcript_chars": len(text), "fetched_via": used})
        print(f"OK   {vid} | {v['title'][:60]} | {len(text)} chars | via={used}", file=sys.stderr)

    seed_path = out_dir / "voice_profile_seed.txt"
    seed_path.write_text(
        f"# Voice profile seed — {channel_title} ({channel_id})\n"
        f"# {len(ingested)} videos, total {sum(s['transcript_chars'] for s in ingested):,} chars\n\n"
        + "\n---\n\n".join(seed_chunks),
        encoding="utf-8",
    )

    summary = {
        "channel_id": channel_id,
        "channel_title": channel_title,
        "ingested": ingested,
        "skipped": skipped,
        "seed_path": str(seed_path),
        "total_chars": sum(s["transcript_chars"] for s in ingested),
    }
    (out_dir / "ingest_summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")

    print(f"\n=== INGEST SUMMARY ===", file=sys.stderr)
    print(f"Ingested:  {len(ingested)} videos, {summary['total_chars']:,} chars", file=sys.stderr)
    print(f"Skipped:   {len(skipped)}", file=sys.stderr)
    print(f"Seed:      {seed_path}", file=sys.stderr)
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description="YouTube channel ingest — preflight + transcript pull")
    p.add_argument("--handle", help="Channel handle, e.g. @ProdCraft")
    p.add_argument("--channel-id", help="UC... channel ID (overrides handle)")
    p.add_argument("--mode", choices=["preflight", "ingest"], required=True)
    p.add_argument("--top-n", type=int, default=8, help="Ingest mode: how many top-view videos to pull")
    p.add_argument("--out-dir", default=".tmp/prodcraft", help="Output directory (default .tmp/prodcraft)")
    args = p.parse_args()

    if args.mode == "preflight":
        return cmd_preflight(args)
    return cmd_ingest(args)


if __name__ == "__main__":
    raise SystemExit(main())
