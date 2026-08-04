"""
description: Scaffold a new video-pipeline project from the template at
             execution/templates/video_pipeline/. Copies the template into
             a destination path, stamps the slug into config/pipeline.json
             and placeholder-substituted files, and creates the .tmp/<slug>/
             tree. Does NOT install npm deps or run tests — operator does
             that per README.
inputs:
  - --slug NAME                      (project slug; must be snake_case)
  - --dest DIR                       (destination parent dir; default
                                      execution/personal_workflows/<slug>_video/)
  - --deliverable                    (route to deliverables/videos/<slug>/ instead)
  - --force                          (overwrite existing dest)
outputs:
  - <dest>/                          (full scaffolded project tree)
  - stdout: absolute path + next-steps
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import shutil
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001
    pass

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("scaffold")

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_DIR = WORKSPACE_ROOT / "execution" / "templates" / "video_pipeline"
SLUG_RE = re.compile(r"^[a-z][a-z0-9_]{1,40}$")

IGNORE_PATTERNS = shutil.ignore_patterns(
    "node_modules", "__pycache__", "*.pyc", ".tmp", "out",
)


def _default_dest(slug: str, deliverable: bool) -> Path:
    if deliverable:
        return WORKSPACE_ROOT / "deliverables" / "videos" / slug
    return WORKSPACE_ROOT / "execution" / "personal_workflows" / f"{slug}_video"


def _stamp_config(dest: Path, slug: str, template_version: str) -> None:
    cfg_path = dest / "config" / "pipeline.json"
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    cfg["slug"] = slug
    cfg["publish"]["manual_publish_dir"] = f".tmp/{slug}/publish/"
    cfg_path.write_text(json.dumps(cfg, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    # Stamp HANDOFF.md placeholders
    handoff = dest / "HANDOFF.md"
    if handoff.exists():
        text = handoff.read_text(encoding="utf-8")
        text = text.replace("__SLUG__", slug)
        text = text.replace("__TEMPLATE_VERSION__", template_version)
        handoff.write_text(text, encoding="utf-8")


def _write_template_version(dest: Path) -> str:
    src = TEMPLATE_DIR / ".template-version"
    version = src.read_text(encoding="utf-8").strip() if src.exists() else "unknown"
    (dest / ".template-version").write_text(version + "\n", encoding="utf-8")
    return version


def main() -> int:
    ap = argparse.ArgumentParser(description="Scaffold a new video pipeline project")
    ap.add_argument("--slug", required=True)
    ap.add_argument("--dest", type=Path, default=None)
    ap.add_argument("--deliverable", action="store_true")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    if not SLUG_RE.match(args.slug):
        log.error("slug must be snake_case, 2-41 chars, start with letter: got %r", args.slug)
        return 2

    if not TEMPLATE_DIR.exists():
        log.error("template not found at %s", TEMPLATE_DIR)
        return 2

    dest = args.dest if args.dest else _default_dest(args.slug, args.deliverable)
    # Boundary check per python-hardening rule 3
    dest = dest.resolve()
    if not dest.is_relative_to(WORKSPACE_ROOT.resolve()):
        log.error("dest must be within workspace: %s", dest)
        return 2

    if dest.exists():
        if not args.force:
            log.error("dest already exists (use --force to overwrite): %s", dest)
            return 2
        log.warning("overwriting existing dest: %s", dest)
        shutil.rmtree(dest)

    log.info("scaffolding %s -> %s", args.slug, dest)
    shutil.copytree(TEMPLATE_DIR, dest, ignore=IGNORE_PATTERNS)

    # Create .tmp/<slug>/ tree so first run doesn't need to mkdir
    tmp = dest / ".tmp" / args.slug
    for sub in ("frames", "grids", "assets", "publish"):
        (tmp / sub).mkdir(parents=True, exist_ok=True)

    version = _write_template_version(dest)
    _stamp_config(dest, args.slug, version)

    print(json.dumps({
        "slug": args.slug,
        "dest": str(dest),
        "template_version": version,
        "next_steps": [
            f"cd {dest.relative_to(WORKSPACE_ROOT)}",
            "cp .env.example .env  # then edit with your keys",
            "cd compose && npm install && cd ..",
            "bash tests/front_door_video.sh",
            "py -m pytest tests/unit -v",
            "py analyze.py --input <youtube-url> --dry-run",
        ],
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
