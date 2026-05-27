"""
bootstrap_mobile_app.py
description: Clone C:/Users/deban/dev/mobile-apps/_template into C:/Users/deban/dev/mobile-apps/{slug}, replace slug placeholders, run `git init`, append an entry to registry.json. Also supports --remove with git-dirty / unpushed-commits guards.
inputs: CLI: slug (positional, kebab-case), --dry-run, --force, --remove <slug>, --force-remove
outputs: New repo dir at C:/Users/deban/dev/mobile-apps/{slug}; mutated execution/mobile_apps/registry.json
usage:
    py execution/mobile_apps/bootstrap_mobile_app.py my-new-app
    py execution/mobile_apps/bootstrap_mobile_app.py --dry-run my-new-app
    py execution/mobile_apps/bootstrap_mobile_app.py --force my-new-app
    py execution/mobile_apps/bootstrap_mobile_app.py --remove my-new-app
    py execution/mobile_apps/bootstrap_mobile_app.py --remove my-new-app --force-remove
"""

import argparse
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

# Module-level lock guards concurrent writes to REGISTRY_PATH within a single
# process. Windows hardening rule #2: shared mutable filesystem state (the
# registry file) must be lock-guarded. Cross-process contention is addressed by
# using a per-call unique tmp filename to avoid `.json.tmp` collisions during
# os.replace (Windows raises PermissionError if the destination is being held
# open by another thread/process).
_REGISTRY_WRITE_LOCK = threading.Lock()


def _rmtree_force(path: Path) -> None:
    """Windows-safe rmtree: clears read-only bit before unlinking.
    Required for .git/objects/pack files which git marks read-only on Windows."""
    def _on_error(func, fname, exc_info):
        try:
            os.chmod(fname, stat.S_IWRITE)
            func(fname)
        except FileNotFoundError:
            pass  # already gone
    shutil.rmtree(path, onexc=_on_error)

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"
MOBILE_APPS_BASE = Path("C:/Users/deban/dev/mobile-apps")
TEMPLATE_DIR = MOBILE_APPS_BASE / "_template"

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_PLACEHOLDER = "{{APP_SLUG}}"


# ---------- helpers ----------

def validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}'. Must be kebab-case: lowercase letters/digits, "
            "hyphen-separated, no leading/trailing/consecutive hyphens."
        )


def resolve_app_dir(slug: str) -> Path:
    """Resolve target app dir and assert containment within MOBILE_APPS_BASE."""
    base = MOBILE_APPS_BASE.resolve()
    candidate = (MOBILE_APPS_BASE / slug).resolve()
    if not candidate.is_relative_to(base):
        raise ValueError(
            f"Path-traversal attempt: {candidate} is not under {base}. Refusing."
        )
    return candidate


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "apps": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def write_registry_atomic(data: dict) -> None:
    # Per-call unique tmp filename + lock around the write+rename so concurrent
    # threads don't race on the same .json.tmp path (Windows PermissionError).
    with _REGISTRY_WRITE_LOCK:
        tmp = REGISTRY_PATH.with_suffix(f".json.tmp.{os.getpid()}.{uuid.uuid4().hex}")
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, REGISTRY_PATH)
        finally:
            # Best-effort cleanup if os.replace failed mid-flight
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    # Safe to swallow: stale tmp file in same dir, no data loss.
                    pass


def find_app(registry: dict, slug: str) -> dict | None:
    for app in registry.get("apps", []):
        if app.get("slug") == slug:
            return app
    return None


def run_cmd(args: list[str], cwd: Path | None = None, check: bool = True,
            input_text: str | None = None) -> subprocess.CompletedProcess:
    """subprocess.run with mandatory utf-8 encoding (Windows hardening rule #1)."""
    return subprocess.run(
        args,
        cwd=str(cwd) if cwd else None,
        input=input_text,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=check,
        shell=(sys.platform == "win32"),
    )


def replace_slug_in_tree(target: Path, slug: str) -> int:
    """Walk target dir, replace SLUG_PLACEHOLDER in text files. Returns file-modified count."""
    text_exts = {
        ".json", ".md", ".ts", ".tsx", ".js", ".jsx", ".sql", ".toml",
        ".yml", ".yaml", ".env", ".example", ".txt", ".html",
    }
    modified = 0
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        # Skip .git and node_modules
        if any(part in (".git", "node_modules") for part in path.parts):
            continue
        if path.suffix.lower() not in text_exts and path.name not in (".gitignore", ".env.example"):
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            # Binary file or unreadable — log and skip. Safe because slug replacement
            # only ever matters in text config files; binaries can't contain the placeholder.
            print(f"  skip non-text: {path.relative_to(target)} ({e.__class__.__name__})")
            continue
        if SLUG_PLACEHOLDER not in content:
            continue
        path.write_text(content.replace(SLUG_PLACEHOLDER, slug), encoding="utf-8")
        modified += 1
    return modified


# ---------- create ----------

def cmd_create(slug: str, dry_run: bool, force: bool) -> int:
    validate_slug(slug)
    target = resolve_app_dir(slug)

    print(f"Bootstrap mobile app: slug={slug}")
    print(f"  template: {TEMPLATE_DIR}")
    print(f"  target  : {target}")

    if not TEMPLATE_DIR.exists():
        print(
            f"ERROR: Template not found at {TEMPLATE_DIR}. "
            "Run plan Section 1 setup first (clone _template).",
            file=sys.stderr,
        )
        return 2

    registry = load_registry()
    existing = find_app(registry, slug)
    if existing and not force:
        print(
            f"ERROR: slug '{slug}' already in registry. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    if target.exists() and not force:
        print(f"ERROR: target dir {target} already exists. Use --force to overwrite.",
              file=sys.stderr)
        return 2

    if dry_run:
        print("[DRY RUN] Planned operations:")
        print(f"  - copytree({TEMPLATE_DIR}, {target})")
        print(f"  - replace '{SLUG_PLACEHOLDER}' -> '{slug}' in text files")
        print(f"  - git init {target}")
        print(f"  - append registry entry for {slug}")
        print("[DRY RUN] No filesystem or registry writes performed.")
        return 0

    # Remove existing target if force
    if target.exists() and force:
        print(f"  removing existing {target} (--force)")
        _rmtree_force(target)

    # Copy template
    print(f"  copying template -> {target}")
    shutil.copytree(TEMPLATE_DIR, target, dirs_exist_ok=False)

    # Drop any inherited .git from template (will git-init fresh below)
    inherited_git = target / ".git"
    if inherited_git.exists():
        _rmtree_force(inherited_git)

    # Replace slug placeholders
    n_modified = replace_slug_in_tree(target, slug)
    print(f"  replaced placeholder in {n_modified} file(s)")

    # git init
    print(f"  git init in {target}")
    result = run_cmd(["git", "init", "-b", "main"], cwd=target, check=False)
    if result.returncode != 0:
        print(f"  git stderr: {result.stderr}", file=sys.stderr)
        print("WARNING: git init returned non-zero. Continuing anyway.", file=sys.stderr)

    # Update registry
    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "slug": slug,
        "repo_path": str(target),
        "ios_bundle_id": None,
        "android_package": None,
        "eas_project_id": None,
        "last_build_sha": None,
        "health_url": None,
        "play_tester_gate_started_at": None,
        "play_tester_count_manual": None,
        "created_at": now_iso,
    }

    if existing:
        # force overwrite path
        registry["apps"] = [a for a in registry["apps"] if a.get("slug") != slug]
    registry.setdefault("apps", []).append(new_entry)
    write_registry_atomic(registry)
    print(f"  registry updated -> {REGISTRY_PATH}")

    print(f"\nDone. Next: cd {target} && npx expo start")
    return 0


# ---------- remove ----------

def cmd_remove(slug: str, force_remove: bool) -> int:
    validate_slug(slug)
    target = resolve_app_dir(slug)
    registry = load_registry()
    existing = find_app(registry, slug)

    print(f"Remove mobile app: slug={slug}")
    print(f"  target  : {target}")

    if not existing and not target.exists():
        print(f"  nothing to remove (no registry entry, no dir)")
        return 0

    # Git safety checks (skip if dir doesn't have a .git subfolder)
    git_dir = target / ".git"
    if target.exists() and git_dir.exists() and not force_remove:
        # Check uncommitted changes
        result = run_cmd(["git", "status", "--porcelain"], cwd=target, check=False)
        if result.returncode == 0 and result.stdout.strip():
            print(
                "ERROR: working tree has uncommitted changes:\n"
                f"{result.stdout}"
                "Use --force-remove to override.",
                file=sys.stderr,
            )
            return 2

        # Check unpushed commits ahead of origin (only if remote exists)
        remotes = run_cmd(["git", "remote"], cwd=target, check=False)
        if remotes.returncode == 0 and "origin" in remotes.stdout:
            # Fetch silently so we know remote state; non-fatal if it fails (offline).
            run_cmd(["git", "fetch", "origin"], cwd=target, check=False)
            ahead = run_cmd(
                ["git", "rev-list", "--count", "@{u}..HEAD"],
                cwd=target,
                check=False,
            )
            if ahead.returncode == 0 and ahead.stdout.strip().isdigit():
                n_ahead = int(ahead.stdout.strip())
                if n_ahead > 0:
                    print(
                        f"ERROR: {n_ahead} unpushed commit(s) ahead of origin. "
                        "Use --force-remove to override.",
                        file=sys.stderr,
                    )
                    return 2

    # Remove dir
    if target.exists():
        print(f"  removing dir {target}")
        _rmtree_force(target)

    # Remove registry entry
    if existing:
        registry["apps"] = [a for a in registry["apps"] if a.get("slug") != slug]
        write_registry_atomic(registry)
        print(f"  removed registry entry for {slug}")

    print("Done.")
    return 0


# ---------- main ----------

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[2])
    parser.add_argument("slug", nargs="?", help="App slug (kebab-case).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned operations, do not write anything.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing target dir and registry entry on create.")
    parser.add_argument("--remove", metavar="SLUG",
                        help="Remove the given app (dir + registry entry).")
    parser.add_argument("--force-remove", action="store_true",
                        help="Allow remove even if working tree dirty or unpushed commits.")
    args = parser.parse_args()

    try:
        if args.remove:
            return cmd_remove(args.remove, force_remove=args.force_remove)

        if not args.slug:
            parser.error("slug is required unless --remove is used")
        return cmd_create(args.slug, dry_run=args.dry_run, force=args.force)

    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"ERROR: subprocess failed: {e}\nstderr: {e.stderr}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
