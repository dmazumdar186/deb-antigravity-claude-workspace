"""anthropic_watch — daily watcher for Anthropic / Claude Code releases & announcements.

Usage:
    py run.py [--dry-run] [--source <name>] [--verbose]

--dry-run is fetch-only: prints per-source counts to stderr, does NOT call Claude,
does NOT touch the ledger. Use this to confirm sources return data before a real run.

Real run (no --dry-run):
    1. Loads ledger (.claude/watch/anthropic_ledger.jsonl) into a set of seen URLs.
    2. Fetches all sources via fetch.py.
    3. New items = fetched - seen.
    4. Sends new items to Claude Sonnet 4.6 to assign {tag, priority, tldr}.
    5. Writes digest to .claude/watch/digests/YYYY-MM-DD.md (HIGH > MED > LOW).
    6. Appends new items to ledger.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

# Make sibling modules importable when run as `py run.py` from any cwd.
SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR))

import fetch as fetch_mod  # noqa: E402

log = logging.getLogger("anthropic_watch")

WORKSPACE_ROOT = SCRIPT_DIR.parent.parent.parent
LEDGER_PATH = WORKSPACE_ROOT / ".claude" / "watch" / "anthropic_ledger.jsonl"
DIGEST_DIR = WORKSPACE_ROOT / ".claude" / "watch" / "digests"

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
SUMMARIZER_MODEL = "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# Ledger I/O
# ---------------------------------------------------------------------------

def _item_hash(item: dict) -> str:
    """Stable hash on (source, url) — title/excerpt may change harmlessly."""
    key = f"{item['source']}|{item['url']}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:16]


def load_seen() -> set[str]:
    if not LEDGER_PATH.exists():
        return set()
    seen: set[str] = set()
    with LEDGER_PATH.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
                seen.add(row["hash"])
            except (json.JSONDecodeError, KeyError):
                # Skip malformed lines; do not silently corrupt the ledger.
                log.warning("skipping malformed ledger line: %s", line[:80])
    return seen


def append_to_ledger(new_items: list[dict]) -> None:
    LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
    today = dt.date.today().isoformat()
    with LEDGER_PATH.open("a", encoding="utf-8") as f:
        for item in new_items:
            row = {
                "hash": item["__hash__"],
                "source": item["source"],
                "url": item["url"],
                "title": item["title"],
                "first_seen": today,
            }
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


# ---------------------------------------------------------------------------
# Summarizer (inline per skeptic challenge #10)
# ---------------------------------------------------------------------------

SUMMARIZER_SYSTEM = """You are tagging Anthropic-ecosystem announcements for a busy operator's morning digest.

For each item, return a JSON object with:
- "priority": "high" | "med" | "low"
- "tag": "release" | "deprecation" | "announcement" | "docs" | "other"
- "tldr": ONE sentence, max 25 words, plain English, no marketing. Lead with the verb.

Priority guidance:
- HIGH: new model release, model deprecation, breaking API change, new CLI flag/hook/skill, security fix.
- MED: substantive feature add (new product surface, new tool, new SDK method), pricing change.
- LOW: blog posts on research/policy, minor docs edits, small SDK patch releases.

Return ONLY a JSON array, one object per input item, same order. No prose, no markdown."""


def summarize_items(items: list[dict]) -> list[dict]:
    """Sends items to Claude for tag+priority+tldr. Returns items annotated in place."""
    if not items:
        return items
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        log.warning("ANTHROPIC_API_KEY not set; falling back to heuristic tags")
        return _heuristic_tag(items)

    user_content = json.dumps([
        {"title": i["title"], "source": i["source"], "excerpt": i["raw_excerpt"][:1200]}
        for i in items
    ], ensure_ascii=False)

    payload = {
        "model": SUMMARIZER_MODEL,
        "max_tokens": 2000,
        "system": SUMMARIZER_SYSTEM,
        "messages": [{"role": "user", "content": user_content}],
    }
    req = urllib.request.Request(
        ANTHROPIC_API_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "anthropic-version": "2023-06-01",
            "x-api-key": api_key,
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            body = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, json.JSONDecodeError) as err:
        log.warning("Claude API call failed (%s); falling back to heuristic tags", err)
        return _heuristic_tag(items)

    text = "".join(block.get("text", "") for block in body.get("content", []))
    text = text.strip()
    # Strip code fences if present.
    if text.startswith("```"):
        text = text.split("\n", 1)[1].rsplit("```", 1)[0].strip()

    try:
        tagged = json.loads(text)
    except json.JSONDecodeError:
        log.warning("Claude returned non-JSON; falling back to heuristic tags")
        return _heuristic_tag(items)

    for item, tag in zip(items, tagged):
        item["priority"] = tag.get("priority", "low")
        item["tag"] = tag.get("tag", "other")
        item["tldr"] = tag.get("tldr", item["title"])
    return items


def _heuristic_tag(items: list[dict]) -> list[dict]:
    """Fallback when Claude is unavailable. Conservative — most items end up LOW."""
    for item in items:
        title_lower = (item["title"] + " " + item["raw_excerpt"][:200]).lower()
        if "deprecat" in title_lower or "sunset" in title_lower or "end of life" in title_lower:
            item["priority"], item["tag"] = "high", "deprecation"
        elif item["source"].startswith("npm/") or item["source"].startswith("github/"):
            item["priority"], item["tag"] = "high", "release"
        elif "model" in title_lower and ("new" in title_lower or "introducing" in title_lower or "launch" in title_lower):
            item["priority"], item["tag"] = "high", "release"
        else:
            item["priority"], item["tag"] = "low", "announcement"
        item["tldr"] = item["title"]
    return items


# ---------------------------------------------------------------------------
# Digest rendering
# ---------------------------------------------------------------------------

PRIORITY_ORDER = {"high": 0, "med": 1, "low": 2}


def render_digest(items: list[dict], run_date: str) -> str:
    lines = [f"# Anthropic Watch — {run_date}", ""]
    lines.append(f"**{len(items)} new items** across {len({i['source'] for i in items})} sources.")
    lines.append("")

    for label in ("high", "med", "low"):
        bucket = [i for i in items if i["priority"] == label]
        if not bucket:
            continue
        heading = {
            "high": "## HIGH priority (action recommended)",
            "med": "## MED priority",
            "low": "## LOW priority (FYI)",
        }[label]
        lines.append(heading)
        for item in bucket:
            tldr = item.get("tldr") or item["title"]
            lines.append(f"- [{item['tag']}] **{item['title']}** — {tldr}")
            lines.append(f"  source: `{item['source']}` · {item['url']}")
        lines.append("")

    if not items:
        lines.append("_No new items today. All sources clean._")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true",
                        help="Fetch-only. No Claude calls, no ledger writes, no digest writes.")
    parser.add_argument("--seed", action="store_true",
                        help="Bootstrap mode: write all fetched items to the ledger as 'seen' without "
                             "summarizing or producing a digest. Use on first ever run.")
    parser.add_argument("--source", default=None,
                        help=f"Restrict to one source. Choices: {list(fetch_mod.ALL_FETCHERS)}")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s %(message)s",
    )

    # Load .env from workspace root so we pick up keys without a shell pre-export.
    env_path = WORKSPACE_ROOT / ".env"
    if env_path.exists():
        for raw in env_path.read_text(encoding="utf-8").splitlines():
            if "=" not in raw or raw.lstrip().startswith("#"):
                continue
            key, _, val = raw.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            os.environ.setdefault(key, val)

    log.info("anthropic_watch start (dry_run=%s)", args.dry_run)

    fetched = fetch_mod.fetch_all(only=args.source)
    total = sum(len(v) for v in fetched.values())
    log.info("fetched %d items across %d sources", total, len(fetched))

    if args.dry_run:
        log.info("dry-run: skipping diff, summarize, digest, ledger write")
        for source, items in fetched.items():
            print(f"{source}: {len(items)} items")
        return 0

    is_first_run = not LEDGER_PATH.exists()
    seed_mode = args.seed or is_first_run
    if is_first_run and not args.seed:
        log.info("ledger does not exist — entering seed mode automatically")

    seen = load_seen()
    log.info("ledger has %d seen items", len(seen))

    new_items: list[dict] = []
    for source, items in fetched.items():
        for item in items:
            h = _item_hash(item)
            if h in seen:
                continue
            item["__hash__"] = h
            new_items.append(item)
    log.info("identified %d new items", len(new_items))

    run_date = dt.date.today().isoformat()

    if seed_mode:
        log.info("seed mode: writing %d items to ledger without summarizing", len(new_items))
        append_to_ledger(new_items)
        DIGEST_DIR.mkdir(parents=True, exist_ok=True)
        digest_path = DIGEST_DIR / f"{run_date}.md"
        seed_note = (
            f"# Anthropic Watch — {run_date}\n\n"
            f"_Seeded ledger with {len(new_items)} existing items across "
            f"{len({i['source'] for i in new_items})} sources. No deltas to surface; "
            f"future runs will only show new items since this seed._\n"
        )
        digest_path.write_text(seed_note, encoding="utf-8")
        log.info("seed digest written: %s", digest_path)
        print(seed_note)
        return 0

    new_items = summarize_items(new_items)

    DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    digest_path = DIGEST_DIR / f"{run_date}.md"
    digest_path.write_text(render_digest(new_items, run_date), encoding="utf-8")
    log.info("digest written: %s", digest_path)

    append_to_ledger(new_items)
    log.info("ledger updated: %s (+%d rows)", LEDGER_PATH, len(new_items))

    print(f"\n=== digest preview ({digest_path}) ===\n")
    print(render_digest(new_items, run_date))
    return 0


if __name__ == "__main__":
    sys.exit(main())
