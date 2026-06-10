"""
description: Scaffold a new Remotion project using the official --three template, apply workspace overlay, junction-symlink node_modules outside OneDrive, and register in registry.json.
inputs: CLI: --slug <slug>, --dry-run, --title "...", --fps 30, --width 1920, --height 1080, --duration-frames 900, --force; or --remove <slug> [--purge-cache]
outputs: execution/video/remotion-projects/{slug}/, C:/Users/deban/dev/remotion-node-cache/{slug}/node_modules, execution/video/registry.json entry
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

# ── Constants ────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

PROJECTS_DIR = ROOT / "execution" / "video" / "remotion-projects"
OVERLAY_DIR  = ROOT / "execution" / "video" / "remotion_template_overlay"
REGISTRY_PATH = ROOT / "execution" / "video" / "registry.json"
NODE_CACHE_BASE = Path(r"C:\Users\deban\dev\remotion-node-cache")

# Pinned upstream SHA — used as offline fallback; fetched live at bootstrap time.
UPSTREAM_SHA_FALLBACK = "c92bcbf7a6e09f9064c79d36e3a562b2cb5ee9eb"

# Slugs that are allowed through slug validation only in forced/test scenarios.
_RESERVED_SLUGS = {"_template"}      # _smoketest is allowed via --force / any caller

# Module-level lock guards concurrent registry writes (Windows hardening rule #2).
_REGISTRY_LOCK = threading.Lock()

SLUG_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,48}[a-z0-9]$|^[a-z0-9]$")


# ── Helpers ──────────────────────────────────────────────────────────────────

def validate_slug(slug: str, *, force: bool = False) -> None:
    """Lowercase letters / digits / hyphens / underscores; no path traversal.
    Windows hardening rule #3: resolve + containment check."""
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}'. Use lowercase letters, digits, hyphens, "
            "underscores only (1-50 chars)."
        )
    if slug in _RESERVED_SLUGS and not force:
        raise ValueError(
            f"Slug '{slug}' is reserved. Use --force to override."
        )
    # Path-traversal guard
    candidate = (PROJECTS_DIR / slug).resolve()
    if not candidate.is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError(
            f"Path-traversal attempt: '{slug}' resolves outside projects dir."
        )


def humanize_slug(slug: str) -> str:
    """'my-cool-video_2' -> 'My Cool Video 2'"""
    return re.sub(r"[-_]+", " ", slug).title()


def run_cmd(
    args: list[str],
    cwd: Path | None = None,
    check: bool = True,
    live_output: bool = False,
    timeout: int | None = None,
) -> subprocess.CompletedProcess:
    """subprocess.run with mandatory utf-8 encoding (Windows hardening rule #1)."""
    kwargs: dict = dict(
        cwd=str(cwd) if cwd else None,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if live_output:
        result = subprocess.run(args, check=check, timeout=timeout, **kwargs)
    else:
        result = subprocess.run(
            args, capture_output=True, check=check, timeout=timeout, **kwargs
        )
    return result


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "projects": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def write_registry_atomic(data: dict) -> None:
    """Atomic write under threading lock (Windows hardening rule #2)."""
    with _REGISTRY_LOCK:
        tmp = REGISTRY_PATH.with_suffix(
            f".json.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        )
        try:
            with tmp.open("w", encoding="utf-8") as fh:
                json.dump(data, fh, indent=2, ensure_ascii=False)
                fh.write("\n")
            os.replace(tmp, REGISTRY_PATH)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    # Safe to swallow: stale tmp in same dir, no data loss.
                    pass


def find_project(registry: dict, slug: str) -> dict | None:
    for proj in registry.get("projects", []):
        if proj.get("slug") == slug:
            return proj
    return None


def fetch_upstream_sha() -> str:
    """Try to get the current HEAD SHA of remotion-dev/template-three.
    Falls back to the pinned constant if offline or git unavailable."""
    try:
        result = run_cmd(
            ["git", "ls-remote",
             "https://github.com/remotion-dev/template-three.git", "HEAD"],
            timeout=20,
        )
        sha = result.stdout.split()[0] if result.stdout.strip() else ""
        if re.match(r"^[0-9a-f]{40}$", sha):
            return sha
        print(
            "WARNING: git ls-remote returned unexpected output; "
            f"using pinned SHA {UPSTREAM_SHA_FALLBACK}",
            file=sys.stderr,
        )
    except (subprocess.SubprocessError, OSError, IndexError) as exc:
        print(
            f"WARNING: git ls-remote failed ({exc}); "
            f"using pinned SHA {UPSTREAM_SHA_FALLBACK}",
            file=sys.stderr,
        )
    return UPSTREAM_SHA_FALLBACK


def apply_overlay(project_dir: Path, slug: str, title: str,
                  fps: int, width: int, height: int,
                  duration_in_frames: int,
                  upstream_sha: str) -> None:
    """Copy all files from OVERLAY_DIR into project_dir, overwriting any that
    already exist (Root.tsx overwrite is intentional per plan)."""
    for src in OVERLAY_DIR.rglob("*"):
        if not src.is_file():
            continue
        rel = src.relative_to(OVERLAY_DIR)
        dst = project_dir / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if dst.exists():
            print(f"  overlay (overwrite): {rel}")
        else:
            print(f"  overlay (new):       {rel}")
        shutil.copy2(src, dst)

    # Substitute placeholders in project.json
    proj_json_path = project_dir / "project.json"
    content = proj_json_path.read_text(encoding="utf-8")
    content = content.replace("{{SLUG}}", slug).replace("{{TITLE}}", title)
    # Replace default fps/width/height/duration_in_frames values
    data = json.loads(content)
    data["fps"] = fps
    data["width"] = width
    data["height"] = height
    data["duration_in_frames"] = duration_in_frames
    proj_json_path.write_text(
        json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print(f"  substituted project.json: slug={slug} fps={fps} {width}x{height} dur={duration_in_frames}")

    # Substitute .template-version SHA
    tv_path = project_dir / ".template-version"
    tv_content = tv_path.read_text(encoding="utf-8")
    tv_content = tv_content.replace("PINNED_AT_BOOTSTRAP", upstream_sha)
    tv_path.write_text(tv_content, encoding="utf-8")
    print(f"  .template-version: SHA = {upstream_sha}")


# ── Create ───────────────────────────────────────────────────────────────────

def cmd_create(
    slug: str,
    *,
    dry_run: bool,
    force: bool,
    title: str,
    fps: int,
    width: int,
    height: int,
    duration_in_frames: int,
) -> int:
    validate_slug(slug, force=force)

    project_dir   = PROJECTS_DIR / slug
    cache_parent  = NODE_CACHE_BASE / slug
    cache_nm      = cache_parent / "node_modules"
    junction_path = project_dir / "node_modules"

    print(f"Remotion bootstrap: slug={slug}")
    print(f"  project_dir  : {project_dir}")
    print(f"  node_modules : {junction_path} -> {cache_nm}")
    print(f"  registry     : {REGISTRY_PATH}")

    # ── Guard: already exists ──────────────────────────────────────────────
    registry = load_registry()
    existing = find_project(registry, slug)

    if existing and not force:
        print(
            f"ERROR: slug '{slug}' already in registry. "
            "Use --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    if project_dir.exists() and not force:
        print(
            f"ERROR: {project_dir} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 2

    # ── Dry run ───────────────────────────────────────────────────────────
    if dry_run:
        print("\n[DRY RUN] Planned operations:")
        print(f"  1. mkdir -p {cache_parent}")
        print(f"  2. npx create-video@latest {slug} --yes --three  (cwd={PROJECTS_DIR})")
        print(f"  3. assert 'videoSrc' in {project_dir}/src/Scene.tsx")
        print(f"  4. mv {project_dir}/node_modules -> {cache_nm}")
        print(f"  5. mklink /J {junction_path} {cache_nm}")
        print(f"  6. apply overlay from {OVERLAY_DIR}")
        print(f"  7. substitute placeholders in project.json and .template-version")
        print(f"  8. write registry entry for '{slug}'")
        print("[DRY RUN] No filesystem or registry writes performed.")
        return 0

    # ── Remove existing if --force ─────────────────────────────────────────
    if project_dir.exists() and force:
        print(f"  removing existing {project_dir} (--force)")
        # Remove junction first (rmdir, not rmtree) to avoid recursing into cache
        if junction_path.exists() or junction_path.is_symlink():
            subprocess.run(
                ["cmd", "/c", "rmdir", str(junction_path)],
                encoding="utf-8", errors="replace", check=False,
            )
        shutil.rmtree(project_dir, ignore_errors=True)

    # ── Step 1: Create cache parent dir ───────────────────────────────────
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    cache_parent.mkdir(parents=True, exist_ok=True)
    print(f"  created cache parent: {cache_parent}")

    # ── Step 2: npx create-video ──────────────────────────────────────────
    print(f"\n  running: npx create-video@latest {slug} --yes --three")
    print(f"  cwd: {PROJECTS_DIR}")
    print("  (this downloads ~300 MB on first run — may take 3-5 min)\n")
    try:
        run_cmd(
            ["npx", "create-video@latest", slug, "--yes", "--three"],
            cwd=PROJECTS_DIR,
            live_output=True,
            timeout=600,   # 10-minute hard cap; plan says hang = ≥10min
        )
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: create-video exited with code {exc.returncode}.",
            file=sys.stderr,
        )
        return 1
    except subprocess.TimeoutExpired:
        print(
            "ERROR: npx create-video@latest timed out after 600 s. "
            "Check network connectivity and try again.",
            file=sys.stderr,
        )
        return 1

    # ── Step 3: Upstream drift canary ─────────────────────────────────────
    scene_path = project_dir / "src" / "Scene.tsx"
    if not scene_path.exists():
        print(
            f"ERROR: {scene_path} not found after create-video. "
            "Template structure may have changed.",
            file=sys.stderr,
        )
        return 1
    scene_src = scene_path.read_text(encoding="utf-8")
    if "videoSrc" not in scene_src:
        print(
            f"ERROR: upstream Scene.tsx no longer contains 'videoSrc'. "
            f"Template may have drifted from pinned SHA {UPSTREAM_SHA_FALLBACK}. "
            "Review the upstream template before proceeding.",
            file=sys.stderr,
        )
        return 1
    print("  drift canary OK: 'videoSrc' found in src/Scene.tsx")

    # ── Step 4: Move node_modules to cache, create junction ───────────────
    installed_nm = project_dir / "node_modules"
    if installed_nm.exists():
        print(f"  moving node_modules -> {cache_nm}")
        shutil.move(str(installed_nm), str(cache_nm))
    else:
        print(
            "WARNING: no node_modules found after create-video; "
            "junction will point to empty dir.",
            file=sys.stderr,
        )
        cache_nm.mkdir(parents=True, exist_ok=True)

    print(f"  creating junction: {junction_path} -> {cache_nm}")
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction_path), str(cache_nm)],
        encoding="utf-8", errors="replace", check=False,
    )
    if result.returncode != 0:
        print(
            f"ERROR: mklink /J failed (exit {result.returncode}). "
            f"stdout: {result.stdout!r}  stderr: {result.stderr!r}",
            file=sys.stderr,
        )
        return 1

    # Verify the junction works
    remotion_pkg = junction_path / "remotion" / "package.json"
    if not remotion_pkg.exists():
        print(
            f"ERROR: junction verification failed — {remotion_pkg} not found. "
            "The junction may not be pointing to the correct location.",
            file=sys.stderr,
        )
        return 1
    print(f"  junction verified: {remotion_pkg} exists")

    # ── Step 5+6: Fetch upstream SHA, apply overlay ────────────────────────
    print("\n  fetching upstream SHA…")
    upstream_sha = fetch_upstream_sha()

    print(f"\n  applying overlay from {OVERLAY_DIR}")
    apply_overlay(
        project_dir, slug, title, fps, width, height, duration_in_frames, upstream_sha
    )

    # ── Step 7: Register in registry.json ─────────────────────────────────
    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "slug": slug,
        "created_at": now_iso,
        "template_version": upstream_sha,
        "fps": fps,
        "width": width,
        "height": height,
        "duration_in_frames": duration_in_frames,
        "project_path": str(project_dir),
        "node_modules_symlink_target": str(cache_nm),
    }

    if existing:
        registry["projects"] = [
            p for p in registry["projects"] if p.get("slug") != slug
        ]
    registry.setdefault("projects", []).append(new_entry)
    write_registry_atomic(registry)
    print(f"\n  registry updated: {REGISTRY_PATH}")

    # ── Success ────────────────────────────────────────────────────────────
    print(f"""
Bootstrap complete for '{slug}'.

Next steps:
  cd {project_dir}
  npx remotion studio          # open live preview (localhost:3000)

Render:
  npx remotion render CompositionWithAlpha out/alpha.png --frame=15 --codec=png
  npx remotion render Scene out/scene.mp4 --codec=h264

AV whitelist reminder:
  Add {NODE_CACHE_BASE} to Windows Defender exclusions to avoid scan overhead.
""")
    return 0


# ── Remove ────────────────────────────────────────────────────────────────────

def cmd_remove(slug: str, *, purge_cache: bool) -> int:
    """Remove a project: rmdir junction, rmtree project dir, optionally purge cache."""
    validate_slug(slug, force=True)   # allow reserved names on remove

    project_dir  = PROJECTS_DIR / slug
    junction_path = project_dir / "node_modules"
    cache_nm     = NODE_CACHE_BASE / slug / "node_modules"
    cache_parent = NODE_CACHE_BASE / slug

    registry = load_registry()
    existing = find_project(registry, slug)

    print(f"Remove Remotion project: slug={slug}")
    print(f"  project_dir : {project_dir}")

    if not existing and not project_dir.exists():
        print("  nothing to remove (no registry entry, no dir)")
        return 0

    # Remove junction first (rmdir, not rm -rf — avoids recursing into cache)
    if junction_path.exists() or junction_path.is_symlink():
        print(f"  removing junction: {junction_path}")
        result = subprocess.run(
            ["cmd", "/c", "rmdir", str(junction_path)],
            encoding="utf-8", errors="replace", check=False,
        )
        if result.returncode != 0:
            print(
                f"  WARNING: rmdir junction returned {result.returncode}: "
                f"{result.stderr!r}",
                file=sys.stderr,
            )

    # Remove project dir
    if project_dir.exists():
        print(f"  removing project dir: {project_dir}")
        shutil.rmtree(project_dir, ignore_errors=True)

    # Optionally purge cache
    if purge_cache:
        if cache_nm.exists():
            print(f"  purging cache: {cache_nm}")
            shutil.rmtree(cache_nm, ignore_errors=True)
        if cache_parent.exists():
            try:
                cache_parent.rmdir()   # only succeeds if now empty
                print(f"  removed empty cache parent: {cache_parent}")
            except OSError:
                print(f"  cache parent not empty (other projects?): {cache_parent}")
    else:
        if cache_nm.exists():
            print(f"  node_modules cache retained: {cache_nm}  (use --purge-cache to remove)")

    # Remove registry entry
    if existing:
        registry["projects"] = [
            p for p in registry["projects"] if p.get("slug") != slug
        ]
        write_registry_atomic(registry)
        print(f"  removed registry entry for '{slug}'")

    print("Done.")
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="Bootstrap or remove a Remotion project with @remotion/three."
    )
    parser.add_argument(
        "--slug", metavar="SLUG",
        help="Project slug (lowercase letters/digits/hyphens/underscores).",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned operations without writing anything.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing project dir + registry entry.")
    parser.add_argument("--title", default=None,
                        help="Human-readable project title (default: humanized slug).")
    parser.add_argument("--fps", type=int, default=30)
    parser.add_argument("--width", type=int, default=1920)
    parser.add_argument("--height", type=int, default=1080)
    parser.add_argument("--duration-frames", type=int, default=900,
                        dest="duration_frames",
                        help="Duration in frames (default: 900 = 30 s at 30 fps).")
    parser.add_argument("--remove", metavar="SLUG",
                        help="Remove the named project (junction + dir + registry entry).")
    parser.add_argument("--purge-cache", action="store_true",
                        help="With --remove: also delete node_modules from the cache.")

    args = parser.parse_args()

    try:
        if args.remove:
            return cmd_remove(args.remove, purge_cache=args.purge_cache)

        if not args.slug:
            parser.error("--slug is required unless --remove is used")

        title = args.title if args.title else humanize_slug(args.slug)
        return cmd_create(
            args.slug,
            dry_run=args.dry_run,
            force=args.force,
            title=title,
            fps=args.fps,
            width=args.width,
            height=args.height,
            duration_in_frames=args.duration_frames,
        )

    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as exc:
        print(
            f"ERROR: subprocess failed with code {exc.returncode}.\n"
            f"stderr: {exc.stderr}",
            file=sys.stderr,
        )
        return 1
    except KeyboardInterrupt:
        print("\nInterrupted.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    sys.exit(main())
