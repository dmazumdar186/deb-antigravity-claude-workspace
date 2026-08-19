#!/usr/bin/env python3
"""YouTube Tracker — Daily competitor tracking + idea mining."""

import json
import os
import sqlite3
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode

import requests

YOUTUBE_API_KEYS = [
    k.strip() for k in os.environ.get("YOUTUBE_API_KEYS", os.environ.get("YOUTUBE_API_KEY", "")).split(",") if k.strip()
]
if not YOUTUBE_API_KEYS:
    sys.exit("No YouTube API keys found. Set YOUTUBE_API_KEYS or YOUTUBE_API_KEY.")
_current_key_idx = 0
WEBHOOK_URL = os.environ.get("WEBHOOK_URL", "")
BASE_URL = "https://www.googleapis.com/youtube/v3"

SCRIPT_DIR = Path(__file__).parent
DB_PATH = SCRIPT_DIR / "data" / "tracker.db"
CHANNELS_FILE = SCRIPT_DIR / "channels.json"
KEYWORDS_FILE = SCRIPT_DIR / "keywords.json"

DISCOVERY_MIN_SUBS = 1_000
DISCOVERY_MAX_SUBS = 25_000
DISCOVERY_MIN_VIEWS_PER_SUB = 5
DISCOVERY_MIN_DURATION_SECS = 60  # exclude Shorts
SEARCH_DAYS_BACK = 7


def _parse_duration(iso):
    """Parse ISO 8601 duration (PT1H2M3S) to seconds."""
    import re
    m = re.match(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?", iso)
    if not m:
        return 0
    h, mi, s = (int(x) if x else 0 for x in m.groups())
    return h * 3600 + mi * 60 + s


def init_db(conn):
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS channels (
            channel_id TEXT PRIMARY KEY,
            handle TEXT,
            name TEXT,
            tier TEXT
        );
        CREATE TABLE IF NOT EXISTS channel_snapshots (
            channel_id TEXT,
            date TEXT,
            subscriber_count INTEGER,
            view_count INTEGER,
            video_count INTEGER,
            PRIMARY KEY (channel_id, date)
        );
        CREATE TABLE IF NOT EXISTS discoveries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            discovered_date TEXT,
            channel_id TEXT,
            channel_name TEXT,
            subscriber_count INTEGER,
            video_id TEXT,
            video_title TEXT,
            video_views INTEGER,
            views_per_sub REAL,
            keyword TEXT,
            UNIQUE(channel_id, video_id)
        );
    """)


def yt_api(endpoint, params):
    global _current_key_idx
    start_idx = _current_key_idx
    while True:
        params["key"] = YOUTUBE_API_KEYS[_current_key_idx]
        resp = requests.get(f"{BASE_URL}/{endpoint}", params=params, timeout=30)
        if resp.status_code == 403 and "quotaExceeded" in resp.text:
            _current_key_idx = (_current_key_idx + 1) % len(YOUTUBE_API_KEYS)
            if _current_key_idx == start_idx:
                resp.raise_for_status()  # all keys exhausted
            print(f"Quota exceeded, rotating to key {_current_key_idx + 1}/{len(YOUTUBE_API_KEYS)}")
            continue
        resp.raise_for_status()
        return resp.json()


def resolve_handles(conn, channels_config):
    """Resolve @handles to channel IDs, caching in DB."""
    resolved = []
    for ch in channels_config:
        handle = ch["handle"]
        name = ch.get("name", handle)

        # Check cache
        row = conn.execute(
            "SELECT channel_id, name FROM channels WHERE handle = ?", (handle,)
        ).fetchone()
        if row:
            resolved.append({"channel_id": row[0], "handle": handle, "name": row[1]})
            continue

        # Support direct channel IDs (UC...)
        if handle.startswith("UC") and len(handle) == 24:
            data = yt_api("channels", {"part": "snippet", "id": handle})
        else:
            h = handle.lstrip("@")
            data = yt_api("channels", {"part": "snippet", "forHandle": h})

        if not data.get("items"):
            print(f"WARNING: Could not resolve '{handle}', skipping")
            continue

        channel_id = data["items"][0]["id"]
        channel_name = data["items"][0]["snippet"]["title"]

        conn.execute(
            "INSERT OR REPLACE INTO channels (channel_id, handle, name, tier) VALUES (?, ?, ?, 'competitor')",
            (channel_id, handle, channel_name),
        )
        conn.commit()
        resolved.append({"channel_id": channel_id, "handle": handle, "name": channel_name})

    return resolved


def track_competitors(conn, channels):
    """Fetch current stats for all competitor channels and store daily snapshot."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    yesterday = (datetime.now(timezone.utc) - timedelta(days=1)).strftime("%Y-%m-%d")

    channel_ids = [ch["channel_id"] for ch in channels]
    id_to_name = {ch["channel_id"]: ch["name"] for ch in channels}
    results = []

    for i in range(0, len(channel_ids), 50):
        batch = channel_ids[i : i + 50]
        data = yt_api("channels", {"part": "statistics", "id": ",".join(batch)})

        for item in data.get("items", []):
            cid = item["id"]
            stats = item["statistics"]
            sub_count = int(stats.get("subscriberCount", 0))
            view_count = int(stats.get("viewCount", 0))
            video_count = int(stats.get("videoCount", 0))

            conn.execute(
                "INSERT OR REPLACE INTO channel_snapshots VALUES (?, ?, ?, ?, ?)",
                (cid, today, sub_count, view_count, video_count),
            )

            prev = conn.execute(
                "SELECT subscriber_count FROM channel_snapshots WHERE channel_id = ? AND date = ?",
                (cid, yesterday),
            ).fetchone()

            prev_subs = prev[0] if prev else None
            abs_growth = sub_count - prev_subs if prev_subs is not None else None
            rel_growth = (abs_growth / prev_subs * 100) if prev_subs else None

            results.append({
                "channel_id": cid,
                "name": id_to_name.get(cid, cid),
                "subscriber_count": sub_count,
                "abs_growth": abs_growth,
                "rel_growth": rel_growth,
            })

    conn.commit()
    return results


def mine_ideas(conn, keywords):
    """Search for breakout videos from small channels."""
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    after = (datetime.now(timezone.utc) - timedelta(days=SEARCH_DAYS_BACK)).strftime(
        "%Y-%m-%dT%H:%M:%SZ"
    )

    videos = []
    seen = set()

    for kw in keywords:
        try:
            data = yt_api("search", {
                "part": "snippet",
                "type": "video",
                "q": kw,
                "order": "viewCount",
                "publishedAfter": after,
                "relevanceLanguage": "en",
                "maxResults": 50,
            })
        except requests.HTTPError as e:
            print(f"WARNING: Search failed for '{kw}': {e}")
            continue

        for item in data.get("items", []):
            vid = item["id"]["videoId"]
            if vid not in seen:
                seen.add(vid)
                videos.append({
                    "video_id": vid,
                    "video_title": item["snippet"]["title"],
                    "channel_id": item["snippet"]["channelId"],
                    "channel_name": item["snippet"]["channelTitle"],
                    "keyword": kw,
                })

    if not videos:
        return []

    # Batch fetch channel sub counts
    unique_cids = list({v["channel_id"] for v in videos})
    channel_subs = {}
    for i in range(0, len(unique_cids), 50):
        batch = unique_cids[i : i + 50]
        try:
            data = yt_api("channels", {"part": "statistics", "id": ",".join(batch)})
            for item in data.get("items", []):
                channel_subs[item["id"]] = int(item["statistics"].get("subscriberCount", 0))
        except requests.HTTPError as e:
            print(f"WARNING: Channel batch lookup failed: {e}")
            break

    # Batch fetch video view counts + duration (to filter Shorts)
    video_ids = [v["video_id"] for v in videos]
    video_views = {}
    video_durations = {}
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i : i + 50]
        try:
            data = yt_api("videos", {"part": "statistics,contentDetails", "id": ",".join(batch)})
            for item in data.get("items", []):
                video_views[item["id"]] = int(item["statistics"].get("viewCount", 0))
                video_durations[item["id"]] = _parse_duration(item["contentDetails"]["duration"])
        except requests.HTTPError as e:
            print(f"WARNING: Video batch lookup failed: {e}")
            break

    # Filter for breakout small channels
    discoveries = []
    for v in videos:
        subs = channel_subs.get(v["channel_id"], 0)
        views = video_views.get(v["video_id"], 0)

        duration = video_durations.get(v["video_id"], 0)
        if duration < DISCOVERY_MIN_DURATION_SECS:
            continue  # skip Shorts
        if not (DISCOVERY_MIN_SUBS <= subs <= DISCOVERY_MAX_SUBS):
            continue
        views_per_sub = views / subs if subs > 0 else 0
        if views_per_sub < DISCOVERY_MIN_VIEWS_PER_SUB:
            continue

        try:
            conn.execute(
                """INSERT INTO discoveries
                   (discovered_date, channel_id, channel_name, subscriber_count,
                    video_id, video_title, video_views, views_per_sub, keyword)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (today, v["channel_id"], v["channel_name"], subs,
                 v["video_id"], v["video_title"], views, views_per_sub, v["keyword"]),
            )
            discoveries.append({
                "channel_name": v["channel_name"],
                "channel_id": v["channel_id"],
                "subscriber_count": subs,
                "video_id": v["video_id"],
                "video_title": v["video_title"],
                "video_views": views,
                "views_per_sub": views_per_sub,
                "keyword": v["keyword"],
            })
        except sqlite3.IntegrityError:
            pass  # already discovered

    conn.commit()
    return discoveries


def fmt(n):
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}M"
    if n >= 1_000:
        return f"{n / 1_000:.1f}K"
    return str(n)


def get_recent_discoveries(conn, days=7):
    """Get all discoveries from the last N days."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d")
    rows = conn.execute(
        """SELECT channel_name, channel_id, subscriber_count, video_id,
                  video_title, video_views, views_per_sub, keyword, discovered_date
           FROM discoveries WHERE discovered_date >= ?
           ORDER BY views_per_sub DESC LIMIT 10""",
        (cutoff,),
    ).fetchall()
    return [
        {"channel_name": r[0], "channel_id": r[1], "subscriber_count": r[2],
         "video_id": r[3], "video_title": r[4], "video_views": r[5],
         "views_per_sub": r[6], "keyword": r[7], "discovered_date": r[8]}
        for r in rows
    ]


def send_webhook(competitors, new_discoveries, conn):
    if not WEBHOOK_URL:
        print("No WEBHOOK_URL set, skipping notification")
        return

    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    sorted_comp = sorted(
        competitors,
        key=lambda x: x["abs_growth"] if x["abs_growth"] is not None else -999999,
        reverse=True,
    )

    # Always show recent discoveries (last 7 days), not just new ones
    discoveries = get_recent_discoveries(conn)

    is_slack = "hooks.slack.com" in WEBHOOK_URL

    if is_slack:
        _send_slack(today, sorted_comp, competitors, discoveries, len(new_discoveries))
    else:
        _send_discord(today, sorted_comp, competitors, discoveries)


def _slack_escape(text):
    """Escape special chars for Slack mrkdwn, including | which breaks link syntax."""
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace("|", "/")


def _fmt_date(iso_date):
    """Format 2026-03-09 as March 9, 2026."""
    d = datetime.strptime(iso_date, "%Y-%m-%d")
    return d.strftime("%B %-d, %Y")


def _send_slack(today, sorted_comp, competitors, discoveries, new_count):
    # Sort by absolute sub count (highest first) for leaderboard
    by_subs = sorted(sorted_comp, key=lambda x: x["subscriber_count"], reverse=True)

    blocks = [
        {"type": "section", "text": {"type": "mrkdwn", "text": f"*{_fmt_date(today)}*"}},
        {"type": "divider"},
    ]

    # Top 10 by sub count
    comp_lines = []
    for i, r in enumerate(by_subs[:10], 1):
        yt_url = f"https://youtube.com/channel/{r['channel_id']}"
        name = _slack_escape(r["name"])
        subs = fmt(r["subscriber_count"])
        if r["abs_growth"] is not None:
            sign = "+" if r["abs_growth"] >= 0 else ""
            comp_lines.append(
                f"{i}. <{yt_url}|{name}> — {subs} ({sign}{r['abs_growth']:,} / {sign}{r['rel_growth']:.2f}%)"
            )
        else:
            comp_lines.append(f"{i}. <{yt_url}|{name}> — {subs}")

    blocks.append({
        "type": "section",
        "text": {"type": "mrkdwn", "text": "\n".join(comp_lines)},
    })

    remaining = len(sorted_comp) - 10
    if remaining > 0:
        blocks.append({
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": f"_{remaining} more tracked_"}],
        })

    # Milestones
    milestones = []
    for r in competitors:
        if r["abs_growth"] is None:
            continue
        prev = r["subscriber_count"] - r["abs_growth"]
        for t in [100_000, 250_000, 500_000, 750_000, 1_000_000]:
            if prev < t <= r["subscriber_count"]:
                yt_url = f"https://youtube.com/channel/{r['channel_id']}"
                name = _slack_escape(r["name"])
                milestones.append(f"<{yt_url}|{name}> crossed *{fmt(t)}*")
    if milestones:
        blocks.append({"type": "divider"})
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(milestones)},
        })

    # Discoveries (recent 7 days from DB)
    blocks.append({"type": "divider"})
    if discoveries:
        label = f"*Breakout Discoveries* ({len(discoveries)} this week"
        if new_count > 0:
            label += f", {new_count} new today"
        label += ")\n"
        disc_lines = [label]
        for j, d in enumerate(discoveries[:8], 1):
            title = _slack_escape(d["video_title"][:60])
            vid_url = f"https://youtu.be/{d['video_id']}"
            ch_url = f"https://youtube.com/channel/{d['channel_id']}"
            ch_name = _slack_escape(d["channel_name"])
            disc_lines.append(
                f"{j}. <{ch_url}|{ch_name}> ({fmt(d['subscriber_count'])} subs) — "
                f"{fmt(d['video_views'])} views — *{d['views_per_sub']:.0f}x*"
            )
            disc_lines.append(f"    <{vid_url}|{title}>\n")
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "\n".join(disc_lines)},
        })
    else:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": "_No breakout discoveries this week._"},
        })

    payload = {"blocks": blocks, "text": f"YouTube Tracker — {today}"}
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if resp.status_code not in (200, 204):
        print(f"WARNING: Webhook {resp.status_code}: {resp.text}")
    else:
        print("Slack notification sent")


def _send_discord(today, sorted_comp, competitors, discoveries):
    lines = [f"**YouTube Tracker — {today}**\n", "**TOP MOVERS (24h)**", "```"]
    for i, r in enumerate(sorted_comp[:15], 1):
        name = r["name"][:20]
        subs = fmt(r["subscriber_count"]).rjust(6)
        if r["abs_growth"] is not None:
            sign = "+" if r["abs_growth"] >= 0 else ""
            delta = f"{sign}{r['abs_growth']:,}".rjust(8)
            pct = f"{sign}{r['rel_growth']:.2f}%".rjust(8)
            lines.append(f"{i:>2}. {name:<20} {subs}  {delta}  {pct}")
        else:
            lines.append(f"{i:>2}. {name:<20} {subs}     —         —")
    lines.append("```")

    if discoveries:
        lines.append(f"\n**BREAKOUT DISCOVERIES** ({len(discoveries)} found)")
        for d in sorted(discoveries, key=lambda x: x["views_per_sub"], reverse=True)[:8]:
            lines.append(
                f"- **{d['channel_name']}** ({fmt(d['subscriber_count'])} subs) — "
                f"[{d['video_title'][:50]}](https://youtu.be/{d['video_id']}) — "
                f"{fmt(d['video_views'])} views ({d['views_per_sub']:.0f}x subs)"
            )

    payload = {"content": "\n".join(lines)}
    resp = requests.post(WEBHOOK_URL, json=payload, timeout=30)
    if resp.status_code not in (200, 204):
        print(f"WARNING: Webhook {resp.status_code}: {resp.text}")
    else:
        print("Discord notification sent")


def main():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)

    with open(CHANNELS_FILE) as f:
        channels_config = json.load(f)
    with open(KEYWORDS_FILE) as f:
        keywords = json.load(f)

    conn = sqlite3.connect(DB_PATH)
    init_db(conn)

    try:
        print(f"Resolving {len(channels_config)} handles...")
        channels = resolve_handles(conn, channels_config)
        print(f"Resolved {len(channels)} channels")

        print("Fetching competitor stats...")
        comp = track_competitors(conn, channels)
        print(f"Tracked {len(comp)} channels")

        print(f"Mining ideas ({len(keywords)} keywords)...")
        disc = mine_ideas(conn, keywords)
        print(f"Found {len(disc)} breakout discoveries")

        send_webhook(comp, disc, conn)

        print("\n--- Summary ---")
        for r in sorted(comp, key=lambda x: x["abs_growth"] or 0, reverse=True):
            if r["abs_growth"] is not None:
                print(f"  {r['name']}: {r['subscriber_count']:,} (+{r['abs_growth']:,} / {r['rel_growth']:.2f}%)")
            else:
                print(f"  {r['name']}: {r['subscriber_count']:,} (first day)")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
