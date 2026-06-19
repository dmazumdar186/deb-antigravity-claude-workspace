"""
description: Manage the ProdCraft autopilot pending-approval queue. Add a rendered video + metadata to the queue, list pending items, approve (move to approved/), reject (move to rejected/).
inputs:
    CLI subcommands:
        add --slug X --mp4 PATH --title T --description D [--tags t1,t2] [--scheduled-at ISO8601]
        list [--state pending|approved|rejected|all]
        approve --slug X
        reject --slug X [--reason R]
        pop-approved      # print + remove the oldest approved item as JSON (Phase 3 uploader uses this)
outputs:
    .tmp/prodcraft/queue/{pending|approved|rejected}/<slug>/{final.mp4,metadata.json}
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
QUEUE_ROOT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "queue"
STATES = ("pending", "approved", "rejected")

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,62}$")


def _validate_slug(slug: str) -> str:
    if not SLUG_RE.match(slug):
        raise SystemExit(
            f"Invalid slug {slug!r}: must be lowercase alnum + _ - (1-63 chars, no leading dash)"
        )
    return slug


def _state_dir(state: str) -> Path:
    if state not in STATES:
        raise SystemExit(f"Unknown state: {state}")
    d = QUEUE_ROOT / state
    d.mkdir(parents=True, exist_ok=True)
    return d


def _find_item(slug: str) -> tuple[str, Path] | None:
    _validate_slug(slug)
    for state in STATES:
        d = _state_dir(state) / slug
        if d.is_dir():
            return state, d
    return None


def cmd_add(args: argparse.Namespace) -> int:
    slug = _validate_slug(args.slug)
    if _find_item(slug):
        raise SystemExit(f"Slug {slug!r} already in queue (run `list` to see state)")
    mp4 = Path(args.mp4).resolve()
    if not mp4.is_file():
        raise SystemExit(f"MP4 not found: {mp4}")
    pending = _state_dir("pending") / slug
    pending.mkdir(parents=True, exist_ok=False)
    shutil.copy2(mp4, pending / "final.mp4")

    metadata = {
        "slug": slug,
        "title": args.title,
        "description": args.description,
        "tags": [t.strip() for t in (args.tags or "").split(",") if t.strip()],
        "scheduled_at": args.scheduled_at,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "language": args.language,
        "category_id": args.category_id,
        "privacy": args.privacy,
        "source_mp4": str(mp4),
    }
    (pending / "metadata.json").write_text(
        json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps({"ok": True, "state": "pending", "slug": slug, "dir": str(pending)}, indent=2))
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    states = STATES if args.state == "all" else (args.state,)
    rows = []
    for state in states:
        d = _state_dir(state)
        for sub in sorted(d.iterdir()):
            if not sub.is_dir():
                continue
            meta_path = sub / "metadata.json"
            if meta_path.exists():
                meta = json.loads(meta_path.read_text(encoding="utf-8"))
            else:
                meta = {"slug": sub.name}
            meta["state"] = state
            rows.append(meta)
    print(json.dumps(rows, indent=2, ensure_ascii=False))
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    found = _find_item(args.slug)
    if not found:
        raise SystemExit(f"Slug not found: {args.slug}")
    state, src = found
    if state == "approved":
        print(json.dumps({"ok": True, "noop": True, "slug": args.slug}, indent=2))
        return 0
    if state == "rejected":
        raise SystemExit(f"Slug {args.slug!r} was rejected; remove from rejected/ first if you want to requeue")
    dst = _state_dir("approved") / args.slug
    shutil.move(str(src), str(dst))
    meta_path = dst / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["approved_at"] = datetime.now(timezone.utc).isoformat()
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "state": "approved", "slug": args.slug, "dir": str(dst)}, indent=2))
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    found = _find_item(args.slug)
    if not found:
        raise SystemExit(f"Slug not found: {args.slug}")
    state, src = found
    if state == "rejected":
        print(json.dumps({"ok": True, "noop": True, "slug": args.slug}, indent=2))
        return 0
    dst = _state_dir("rejected") / args.slug
    shutil.move(str(src), str(dst))
    meta_path = dst / "metadata.json"
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        meta["rejected_at"] = datetime.now(timezone.utc).isoformat()
        if args.reason:
            meta["rejected_reason"] = args.reason
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "state": "rejected", "slug": args.slug, "dir": str(dst)}, indent=2))
    return 0


def cmd_pop_approved(args: argparse.Namespace) -> int:
    """Print metadata + mp4 path of oldest approved item; do NOT delete (uploader marks uploaded)."""
    approved = _state_dir("approved")
    items = []
    for sub in approved.iterdir():
        if not sub.is_dir():
            continue
        meta_path = sub / "metadata.json"
        if not meta_path.exists():
            continue
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        added = meta.get("approved_at") or meta.get("added_at") or ""
        items.append((added, sub, meta))
    items.sort(key=lambda x: x[0])
    if not items:
        print(json.dumps({"ok": False, "reason": "no approved items"}, indent=2))
        return 1
    _, sub, meta = items[0]
    meta["mp4_path"] = str(sub / "final.mp4")
    meta["queue_dir"] = str(sub)
    print(json.dumps(meta, indent=2, ensure_ascii=False))
    return 0


def main() -> int:
    QUEUE_ROOT.mkdir(parents=True, exist_ok=True)
    for s in STATES:
        (QUEUE_ROOT / s).mkdir(exist_ok=True)

    p = argparse.ArgumentParser(description="ProdCraft pending/approved/rejected queue.")
    sub = p.add_subparsers(dest="cmd", required=True)

    p_add = sub.add_parser("add", help="Add a rendered video to the pending queue.")
    p_add.add_argument("--slug", required=True)
    p_add.add_argument("--mp4", required=True)
    p_add.add_argument("--title", required=True)
    p_add.add_argument("--description", required=True)
    p_add.add_argument("--tags", default="")
    p_add.add_argument("--scheduled-at", default=None, help="ISO8601 publish time (optional)")
    p_add.add_argument("--language", default="en")
    p_add.add_argument("--category-id", default="27", help="YouTube category (27=Education)")
    p_add.add_argument("--privacy", default="private", choices=["private", "unlisted", "public"])
    p_add.set_defaults(func=cmd_add)

    p_list = sub.add_parser("list")
    p_list.add_argument("--state", default="pending", choices=("pending", "approved", "rejected", "all"))
    p_list.set_defaults(func=cmd_list)

    p_app = sub.add_parser("approve")
    p_app.add_argument("--slug", required=True)
    p_app.set_defaults(func=cmd_approve)

    p_rej = sub.add_parser("reject")
    p_rej.add_argument("--slug", required=True)
    p_rej.add_argument("--reason", default=None)
    p_rej.set_defaults(func=cmd_reject)

    p_pop = sub.add_parser("pop-approved", help="Print oldest approved item as JSON (for Phase 3 uploader).")
    p_pop.set_defaults(func=cmd_pop_approved)

    args = p.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
