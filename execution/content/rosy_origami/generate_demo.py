"""Rosy Origami — newsletter composer for community organizations.

Phase 0 happy-path script. Generates one monthly newsletter draft for a given
tenant (default: gio_paris) from Instagram (+ optional YouTube + Tavily news),
voice-matched via humanizer, rendered to HTML + markdown.

See directives/content/rosy_origami_composer.md for full spec.

This is a Phase 0 SKELETON — fetchers are stubbed; LLM/humanizer wiring is
pending. Run with --dry-run to validate the pipeline shape without API calls.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

ROOT = Path(__file__).resolve().parents[3]
WORKSPACE_HUMANIZER = ROOT / "execution" / "content" / "humanizer.py"
VOICES_DIR = ROOT / "execution" / "content" / "voices"
TEMPLATES_DIR = Path(__file__).parent / "templates"
TENANTS_DIR = Path(__file__).parent / "tenants"
TMP_DIR = ROOT / ".tmp" / "rosy_origami"


@dataclass
class ContentItem:
    """One unit of source content (IG post, YT video, or news article)."""
    source_type: str  # "ig_event" | "ig_upcoming" | "yt" | "news"
    title: str
    body: str
    timestamp: datetime
    url: str | None = None
    image_path: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Section:
    id: str
    title: str
    content: str
    sources: list[str]  # URLs/IDs of source items cited


def load_tenant(slug: str) -> dict[str, Any]:
    path = TENANTS_DIR / f"{slug}.yaml"
    if not path.exists():
        sys.exit(
            f"Tenant config not found: {path}\n"
            f"Create one based on the template in the directive."
        )
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_template(archetype: str) -> dict[str, Any]:
    path = TEMPLATES_DIR / f"{archetype}.yaml"
    if not path.exists():
        sys.exit(f"Template not found: {path}")
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def validate_voice(voice_name: str) -> Path:
    path = VOICES_DIR / f"{voice_name}.json"
    if not path.exists():
        sys.exit(
            f"Voice profile not found: {path}\n"
            f"Copy {VOICES_DIR / '_template.json'} and customize."
        )
    with path.open(encoding="utf-8") as f:
        voice = json.load(f)
    if not voice.get("examples") or "PLACEHOLDER" in voice["examples"][0]:
        print(
            f"WARN: voice profile {voice_name} has placeholder examples — "
            f"voice match will be weak. Add 8-12 real captions before pitch.",
            file=sys.stderr,
        )
    return path


def fetch_ig_manual(slug: str) -> list[ContentItem]:
    """Read IG content from manual export folder.

    Expected layout:
      .tmp/rosy_origami/{slug}/ig_export/captions.json
      .tmp/rosy_origami/{slug}/ig_export/*.jpg
    """
    export_dir = TMP_DIR / slug / "ig_export"
    captions_file = export_dir / "captions.json"
    if not captions_file.exists():
        print(
            f"WARN: no IG manual export found at {captions_file}. "
            f"IG sections will be empty.",
            file=sys.stderr,
        )
        return []
    with captions_file.open(encoding="utf-8") as f:
        raw = json.load(f)
    items = []
    for entry in raw:
        items.append(
            ContentItem(
                source_type=entry.get("type", "ig_event"),
                title=entry.get("title", ""),
                body=entry["caption"],
                timestamp=datetime.fromisoformat(entry["timestamp"]),
                url=entry.get("permalink"),
                image_path=str(export_dir / entry["image"]) if entry.get("image") else None,
            )
        )
    return items


def fetch_ig_api(handle: str, days: int) -> list[ContentItem]:
    """Meta Graph API fetcher — TODO Phase 0b."""
    raise NotImplementedError(
        "IG API fetcher pending Phase 0b Meta dev access. "
        "Use --ig-source manual for now."
    )


def fetch_yt(urls: list[str]) -> list[ContentItem]:
    """YouTube transcript fetcher — TODO.

    Use youtube-transcript-api directly with multilingual support:
      from youtube_transcript_api import YouTubeTranscriptApi
      transcript = YouTubeTranscriptApi.get_transcript(
          video_id, languages=["en", "en-US", "en-GB", "fr", "hi"]
      )
    Do NOT call execution/video/youtube_video_analyzer.fetch_transcript() —
    it raises SystemExit on failure and is English-only.
    """
    if not urls:
        return []
    raise NotImplementedError("YT fetcher pending.")


def fetch_news(query: str, days: int) -> list[ContentItem]:
    """Tavily news fetcher. Returns [] if TAVILY_API_KEY not set."""
    import os as _os

    # Make sure .env vars are loaded so TAVILY_API_KEY shows up
    env_path = ROOT / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.startswith("#"):
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in _os.environ:
                    _os.environ[k] = v

    if not query:
        return []
    if not _os.environ.get("TAVILY_API_KEY"):
        print(f"  [news] TAVILY_API_KEY not set; skipping", file=sys.stderr)
        return []

    try:
        from tavily import TavilyClient
    except ImportError:
        print(f"  [news] tavily-python not installed; skipping", file=sys.stderr)
        return []

    client = TavilyClient(api_key=_os.environ["TAVILY_API_KEY"])
    print(f"  [news] Tavily search: {query!r} (days={days})", file=sys.stderr)
    resp = client.search(
        query=query,
        max_results=5,
        topic="news",
        days=days,
        search_depth="basic",
    )
    items: list[ContentItem] = []
    for r in resp.get("results", []):
        ts_raw = r.get("published_date") or datetime.now().isoformat()
        try:
            ts = datetime.fromisoformat(ts_raw.replace("Z", "+00:00").split(".")[0])
        except ValueError:
            ts = datetime.now()
        items.append(ContentItem(
            source_type="news",
            title=r.get("title", "")[:200],
            body=r.get("content", "")[:1500],
            timestamp=ts,
            url=r.get("url"),
            meta={"source_name": r.get("source", "")},
        ))
    print(f"  [news] Tavily returned {len(items)} items", file=sys.stderr)
    return items


def call_humanizer(text: str, voice: str, platform: str = "email") -> str:
    """Subprocess wrapper around workspace humanizer.

    Per the plan-skeptic round 2 fix: explicit returncode check + UTF-8 encoding.
    """
    result = subprocess.run(
        [
            sys.executable,
            str(WORKSPACE_HUMANIZER),
            "--text", text,
            "--voice", voice,
            "--platform", platform,
            "--tier", "gemini",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"humanizer failed (returncode={result.returncode}): {result.stderr.strip()}"
        )
    return result.stdout.strip()


def compose_sections(
    pool: list[ContentItem],
    template: dict[str, Any],
    theme: str | None,
    spotlight: dict[str, Any] | None,
    dry_run: bool,
    voice: str = "gio_paris",
    cta: str = "Reply to this email with your feedback — we read every message.",
) -> tuple[list[Section], list[dict[str, Any]]]:
    """Map content pool to template sections, build prompts, call LLM.

    Returns (sections, hallucination_flags) where flags is a list of dicts
    {section, source_url, flagged_tokens} for any source-pinning violations
    detected during the run. Used by main() to persist to .meta.json.
    """
    sections = []
    resolved_theme = theme or "TBD"

    if dry_run:
        for spec in template["sections"]:
            items = _select_items(pool, spec, spotlight)
            if not items and spec.get("omit_if_empty"):
                print(f"  [omit] {spec['id']} (empty pool)", file=sys.stderr)
                continue
            preview = f"[DRY RUN] {spec['id']} — {len(items)} items"
            if spec.get("source") == "theme":
                preview += f" — theme={resolved_theme!r}"
            sections.append(
                Section(id=spec["id"], title=spec["title"], content=preview,
                        sources=[i.url or "" for i in items if i.url])
            )
        return sections, []

    from composer import (compose_intro, compose_event_recap, compose_closing,
                          compose_news_roundup, classify_event_section,
                          find_hallucinated_dates, _client)
    client = _client()
    hallucination_flags: list[dict[str, Any]] = []

    for spec in template["sections"]:
        section_id = spec["id"]
        items = _select_items(pool, spec, spotlight)
        if not items and spec.get("omit_if_empty"):
            print(f"  [omit] {section_id} (empty pool)", file=sys.stderr)
            continue

        if section_id == "intro":
            txt = compose_intro(resolved_theme, voice, client)
            sources_used: list[str] = []
        elif section_id == "event_recap":
            chunks = []
            sources_used = []
            today_iso = datetime.now().strftime("%Y-%m-%d")
            for item in items[: spec.get("max_items", 2)]:
                chunk = compose_event_recap(item.body, item.url or "", voice, client,
                                            today_iso=today_iso)
                hallucinated = find_hallucinated_dates(chunk, [item.body])
                if hallucinated:
                    print(f"  ⚠ {section_id}: possible hallucinated dates: {hallucinated}",
                          file=sys.stderr)
                    hallucination_flags.append({
                        "section": section_id,
                        "source_url": item.url,
                        "flagged_tokens": hallucinated,
                    })
                chunks.append(chunk)
                sources_used.append(item.url or "")
            txt = "\n\n".join(chunks)
            adaptive_title = classify_event_section(chunks)
            sections.append(
                Section(id=section_id, title=adaptive_title, content=txt, sources=sources_used)
            )
            print(f"  [ok] {section_id} -> '{adaptive_title}' ({len(txt)} chars)", file=sys.stderr)
            continue
        elif section_id == "news_roundup":
            news_items = [
                {"title": i.title, "body": i.body, "url": i.url or "",
                 "source_name": i.meta.get("source_name", "")}
                for i in items[: spec.get("max_items", 3)]
            ]
            txt = compose_news_roundup(news_items, voice, client)
            sources_used = [i["url"] for i in news_items if i["url"]]
        elif section_id == "closing":
            txt = compose_closing(cta, voice, client)
            sources_used = []
        else:
            # upcoming_events, community_spotlight not generated in V0
            print(f"  [skip-v0] {section_id} (composer for this section pending)",
                  file=sys.stderr)
            continue

        sections.append(
            Section(id=section_id, title=spec["title"], content=txt, sources=sources_used)
        )
        print(f"  [ok] {section_id} ({len(txt)} chars)", file=sys.stderr)

    return sections, hallucination_flags


def _select_items(
    pool: list[ContentItem],
    spec: dict[str, Any],
    spotlight: dict[str, Any] | None,
) -> list[ContentItem]:
    source = spec.get("source")
    if source == "manual_spotlight":
        return [_spotlight_to_item(spotlight)] if spotlight else []
    if source == "ig_event_posts":
        items = [i for i in pool if i.source_type == "ig_event"]
        items.sort(key=lambda x: x.timestamp, reverse=True)  # most recent first
        return items[: spec.get("max_items", 99)]
    if source == "ig_upcoming_posts":
        items = [i for i in pool if i.source_type == "ig_upcoming"]
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[: spec.get("max_items", 99)]
    if source == "tavily_news":
        items = [i for i in pool if i.source_type == "news"]
        items.sort(key=lambda x: x.timestamp, reverse=True)
        return items[: spec.get("max_items", 99)]
    if source == "theme":
        return []
    return []


def _spotlight_to_item(spotlight: dict[str, Any]) -> ContentItem:
    return ContentItem(
        source_type="spotlight",
        title=spotlight.get("name", ""),
        body=spotlight.get("why", ""),
        timestamp=datetime.now(),
        image_path=spotlight.get("photo"),
    )


def render_markdown(sections: list[Section], tenant: dict[str, Any]) -> str:
    lines = [f"# {tenant.get('display_name', 'Newsletter')} — {datetime.now():%B %Y}", ""]
    for s in sections:
        lines.append(f"## {s.title}")
        lines.append("")
        lines.append(s.content)
        lines.append("")
    return "\n".join(lines)


_NEWSLETTER_CSS = """
body { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Helvetica, Arial,
       sans-serif; max-width: 640px; margin: 40px auto; padding: 0 20px;
       color: #1a1a1a; line-height: 1.6; }
h1 { color: #006400; border-bottom: 2px solid #FFD700; padding-bottom: 8px; }
h2 { color: #B8860B; margin-top: 32px; }
h3 { color: #006400; margin-top: 24px; }
a { color: #B8860B; }
ul { padding-left: 20px; }
li { margin: 8px 0; }
"""


def render_html(markdown_text: str) -> str:
    """Markdown → styled HTML email. Falls back to <pre> dump if markdown lib unavailable."""
    try:
        import markdown as md_lib
    except ImportError:
        return (f"<!doctype html><html><body>"
                f"<pre>{markdown_text}</pre></body></html>")
    body = md_lib.markdown(markdown_text, extensions=["extra"])
    return (
        f"<!doctype html><html><head><meta charset=\"utf-8\">"
        f"<style>{_NEWSLETTER_CSS}</style></head><body>{body}</body></html>"
    )


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--tenant", default="gio_paris")
    p.add_argument("--ig-handle", default=None)
    p.add_argument("--ig-source", choices=["api", "manual"], default="manual")
    p.add_argument("--yt-urls", default="")
    p.add_argument("--news-query", default=None)
    p.add_argument("--days", type=int, default=30)
    p.add_argument("--theme", default=None)
    p.add_argument("--spotlight-member", default=None,
                   help="JSON: {\"name\":..,\"photo\":..,\"why\":..}")
    p.add_argument("--archetype", default="cultural_community")
    p.add_argument("--mode", default="cheap",
                   choices=["cheap", "balanced", "premium"],
                   help="LLM tier: cheap (Gemini free), balanced (Sonnet via OR), "
                        "premium (Opus via OR). Renamed from --tier for workspace consistency.")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    tenant = load_tenant(args.tenant)
    template = load_template(args.archetype)
    validate_voice(tenant.get("voice_profile", args.tenant))

    pool: list[ContentItem] = []
    if args.ig_source == "manual":
        pool.extend(fetch_ig_manual(args.tenant))
    else:
        pool.extend(fetch_ig_api(
            args.ig_handle or tenant.get("ig_handle"),
            args.days,
        ))

    yt_urls = [u.strip() for u in args.yt_urls.split(",") if u.strip()]
    if yt_urls and not args.dry_run:
        pool.extend(fetch_yt(yt_urls))
    elif yt_urls:
        print(f"  [dry-run skip] YT fetch for {len(yt_urls)} URLs", file=sys.stderr)

    news_query = args.news_query or tenant.get("news_query")
    if news_query and not args.dry_run:
        pool.extend(fetch_news(news_query, args.days))
    elif news_query:
        print(f"  [dry-run skip] news fetch: {news_query!r}", file=sys.stderr)

    spotlight = json.loads(args.spotlight_member) if args.spotlight_member else None
    sections, hallucination_flags = compose_sections(
        pool, template, args.theme, spotlight, args.dry_run
    )

    md = render_markdown(sections, tenant)
    html = render_html(md)

    out_dir = TMP_DIR / args.tenant
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    out_html = Path(args.out) if args.out else out_dir / f"newsletter_{stamp}.html"
    out_md = out_html.with_suffix(".md")
    out_meta = out_html.with_suffix(".meta.json")

    out_html.write_text(html, encoding="utf-8")
    out_md.write_text(md, encoding="utf-8")
    out_meta.write_text(
        json.dumps(
            {
                "tenant": args.tenant,
                "generated_at": datetime.now().isoformat(),
                "dry_run": args.dry_run,
                "pool_size": len(pool),
                "sections_emitted": [s.id for s in sections],
                "hallucination_flags": hallucination_flags,
                "sources_cited": [{"section": s.id, "urls": s.sources}
                                  for s in sections if s.sources],
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    print(f"Wrote {out_html}")
    print(f"Wrote {out_md}")
    print(f"Wrote {out_meta}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
