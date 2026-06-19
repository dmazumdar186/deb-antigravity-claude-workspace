"""
description: Scheduler entrypoint. Picks the next unprocessed topic from config/prodcraft_topics.yml, runs prodcraft_orchestrate.py end-to-end, then marks the topic processed in the YAML. Designed to be called by a weekly cron (GitHub Actions or local Task Scheduler).
inputs:
    CLI:
        --topics-file PATH    default: config/prodcraft_topics.yml
        --max-topics N        max topics to process per invocation (default: 1)
        --dry-run             show what would run; don't execute
    env: GEMINI_API_KEY
outputs:
    Updates config/prodcraft_topics.yml in place (sets processed_at + queued_slug on processed items)
    Each processed topic lands in .tmp/prodcraft/queue/pending/<slug>/
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

try:
    import yaml
except ImportError as exc:
    raise SystemExit("Install: py -m pip install pyyaml") from exc

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_TOPICS_FILE = WORKSPACE_ROOT / "config" / "prodcraft_topics.yml"


def _load(path: Path) -> dict:
    if not path.is_file():
        raise SystemExit(f"Topics file not found: {path}")
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"topics": []}


def _save(path: Path, data: dict) -> None:
    path.write_text(yaml.safe_dump(data, sort_keys=False, allow_unicode=True), encoding="utf-8")


def _orchestrate(topic_item: dict, py: str) -> str:
    cmd = [
        py,
        "execution/personal_workflows/prodcraft_orchestrate.py",
        "--topic", topic_item["topic"],
        "--language", topic_item.get("language", "en"),
        "--target-duration", str(topic_item.get("target_duration", 180)),
    ]
    if topic_item.get("slug"):
        cmd += ["--slug", topic_item["slug"]]
    print(f"\n>>> [orchestrate] {' '.join(cmd)}\n", file=sys.stderr, flush=True)
    r = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace", capture_output=True)
    print(r.stdout, file=sys.stderr)
    if r.returncode != 0:
        print(r.stderr, file=sys.stderr)
        raise SystemExit(f"orchestrate failed with exit {r.returncode}")
    # Try to parse the final JSON line from stdout for the slug.
    for line_block in r.stdout.split("\n"):
        line_block = line_block.strip()
        if line_block.startswith("{") and "\"slug\":" in line_block:
            try:
                data = json.loads(line_block)
                if "slug" in data:
                    return data["slug"]
            except json.JSONDecodeError:
                continue
    # Fallback: scan for full JSON block in stdout
    try:
        data = json.loads(r.stdout[r.stdout.rfind("{") :])
        return data.get("slug", topic_item.get("slug") or "?")
    except json.JSONDecodeError:
        return topic_item.get("slug") or "?"


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft weekly scheduler.")
    p.add_argument("--topics-file", default=str(DEFAULT_TOPICS_FILE))
    p.add_argument("--max-topics", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    topics_path = Path(args.topics_file).resolve()
    data = _load(topics_path)
    topics = data.get("topics") or []

    pending = [(i, t) for i, t in enumerate(topics) if not t.get("processed_at")]
    if not pending:
        print(json.dumps({"ok": True, "noop": True, "reason": "no unprocessed topics"}, indent=2))
        return 0

    to_process = pending[: args.max_topics]
    print(json.dumps({"unprocessed_count": len(pending), "will_process": len(to_process)}, indent=2))

    if args.dry_run:
        print(json.dumps({"dry_run": True, "items": [t for _, t in to_process]}, indent=2, ensure_ascii=False))
        return 0

    py = sys.executable
    for idx, topic_item in to_process:
        try:
            slug = _orchestrate(topic_item, py)
        except SystemExit as exc:
            print(f"FAIL: {topic_item['topic']!r}: {exc}", file=sys.stderr)
            continue
        topics[idx]["processed_at"] = datetime.now(timezone.utc).isoformat()
        topics[idx]["queued_slug"] = slug
        _save(topics_path, data)
        print(json.dumps({"ok": True, "slug": slug, "topic": topic_item["topic"]}, indent=2, ensure_ascii=False))

    return 0


if __name__ == "__main__":
    sys.exit(main())
