"""
description: Scaffold a new mobile app from the workspace-native template at execution/templates/mobile_app_expo/. Copies to C:/Users/deban/dev/mobile-apps/<slug>/ per CLAUDE.md convention (mobile app source lives outside the workspace), replaces {{APP_SLUG}} placeholders in text files, appends an entry to execution/mobile_apps/registry.json, and initializes git in the new repo.
inputs: CLI: slug (positional, kebab-case), --dry-run, --force, --backend-stack {cf_modal,supabase}
outputs: New repo dir at C:/Users/deban/dev/mobile-apps/<slug>; mutated execution/mobile_apps/registry.json; git repo initialized with one initial commit; printed next-steps checklist.
usage:
    py execution/templates/scaffold_mobile_app.py my-app-slug
    py execution/templates/scaffold_mobile_app.py my-app-slug --backend-stack cf_modal
    py execution/templates/scaffold_mobile_app.py my-app-slug --dry-run
    py execution/templates/scaffold_mobile_app.py my-app-slug --force
"""

from __future__ import annotations

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

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None

# ---- constants ----

ROOT = Path(__file__).resolve().parent.parent.parent  # workspace root
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

TEMPLATE_DIR = ROOT / "execution" / "templates" / "mobile_app_expo"
REGISTRY_PATH = ROOT / "execution" / "mobile_apps" / "registry.json"
MOBILE_APPS_BASE = Path("C:/Users/deban/dev/mobile-apps")

SLUG_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
SLUG_PLACEHOLDER = "{{APP_SLUG}}"
VALID_BACKEND_STACKS = ("cf_modal", "supabase")

# Text extensions we walk for slug replacement. Binary files skipped.
TEXT_EXTS = {
    ".json", ".md", ".ts", ".tsx", ".js", ".jsx", ".sql", ".toml",
    ".yml", ".yaml", ".env", ".example", ".txt", ".html", ".sh", ".py",
}
TEXT_FILENAMES = {".gitignore", ".env.example"}

# Guards concurrent registry writes within a single process (Python hardening rule #2).
_REGISTRY_WRITE_LOCK = threading.Lock()


# ---- helpers ----

def _rmtree_force(path: Path) -> None:
    """Windows-safe rmtree: clears read-only bit before unlinking.
    Required for .git/objects/pack files which git marks read-only on Windows."""
    def _on_error(func, fname, exc_info):
        try:
            os.chmod(fname, stat.S_IWRITE)
            func(fname)
        except FileNotFoundError:
            # Safe: file already removed by another walk step.
            pass
    shutil.rmtree(path, onexc=_on_error)


def _run(args: list[str], cwd: Path | None = None, check: bool = True,
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


def validate_slug(slug: str) -> None:
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug {slug!r}. Must be kebab-case: lowercase letters/digits, "
            "hyphen-separated, no leading/trailing/consecutive hyphens."
        )


def resolve_app_dir(slug: str) -> Path:
    """Resolve target app dir and assert containment within MOBILE_APPS_BASE.
    Guards against ../.. slug values (Python hardening rule #3)."""
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
    """Atomic replace with per-call unique tmp filename + lock (Windows-safe)."""
    with _REGISTRY_WRITE_LOCK:
        tmp = REGISTRY_PATH.with_suffix(
            f".json.tmp.{os.getpid()}.{uuid.uuid4().hex}"
        )
        try:
            with tmp.open("w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")
            os.replace(tmp, REGISTRY_PATH)
        finally:
            if tmp.exists():
                try:
                    tmp.unlink()
                except OSError:
                    # Safe: stale tmp in the workspace tree; will be cleaned by
                    # next run or by the operator. Not a data-loss condition.
                    pass


def find_app(registry: dict, slug: str) -> dict | None:
    for app in registry.get("apps", []):
        if app.get("slug") == slug:
            return app
    return None


def replace_placeholders(target: Path, slug: str) -> int:
    """Walk target dir, replace SLUG_PLACEHOLDER in text files. Returns file-modified count."""
    modified = 0
    for path in target.rglob("*"):
        if not path.is_file():
            continue
        # Skip .git and node_modules (should not exist yet, but defensive).
        if any(part in (".git", "node_modules") for part in path.parts):
            continue
        if path.suffix.lower() not in TEXT_EXTS and path.name not in TEXT_FILENAMES:
            continue
        try:
            content = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError) as e:
            # Binary or unreadable — skip. Placeholder is text-only so this is safe.
            print(f"  skip non-text: {path.relative_to(target)} ({e.__class__.__name__})")
            continue
        if SLUG_PLACEHOLDER not in content:
            continue
        path.write_text(content.replace(SLUG_PLACEHOLDER, slug), encoding="utf-8")
        modified += 1
    return modified


def rename_placeholder_paths(target: Path, slug: str) -> int:
    """Rename any path whose name contains {{APP_SLUG}}. Returns rename count."""
    renamed = 0
    # Two passes: files, then dirs (bottom-up), so parent renames don't invalidate child paths.
    all_paths = list(target.rglob("*"))
    files = [p for p in all_paths if p.is_file() and SLUG_PLACEHOLDER in p.name]
    dirs = sorted(
        (p for p in all_paths if p.is_dir() and SLUG_PLACEHOLDER in p.name),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for p in files + dirs:
        new_name = p.name.replace(SLUG_PLACEHOLDER, slug)
        new_path = p.with_name(new_name)
        p.rename(new_path)
        renamed += 1
    return renamed


# ---- main ops ----

def cmd_create(slug: str, dry_run: bool, force: bool,
               backend_stack: str | None = None) -> int:
    # Validate all inputs BEFORE any side effects.
    validate_slug(slug)
    if backend_stack is not None and backend_stack not in VALID_BACKEND_STACKS:
        raise ValueError(
            f"invalid --backend-stack: {backend_stack!r} "
            f"(expected one of {VALID_BACKEND_STACKS})"
        )

    target = resolve_app_dir(slug)

    print(f"Scaffold mobile app: slug={slug}")
    print(f"  template : {TEMPLATE_DIR}")
    print(f"  target   : {target}")
    print(f"  backend  : {backend_stack or '(deferred)'}")

    if not TEMPLATE_DIR.exists():
        print(
            f"ERROR: Template not found at {TEMPLATE_DIR}. "
            "Expected execution/templates/mobile_app_expo/ (phase 4b deliverable).",
            file=sys.stderr,
        )
        return 2

    registry = load_registry()
    existing = find_app(registry, slug)
    if existing and not force:
        print(
            f"ERROR: slug {slug!r} already in registry. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 2
    if target.exists() and not force:
        print(
            f"ERROR: target dir {target} already exists. Use --force to overwrite.",
            file=sys.stderr,
        )
        return 2

    if dry_run:
        print("\n[DRY RUN] Planned operations:")
        print(f"  1. copytree({TEMPLATE_DIR}, {target})")
        print(f"  2. rename paths containing {SLUG_PLACEHOLDER!r} -> {slug!r}")
        print(f"  3. replace {SLUG_PLACEHOLDER!r} -> {slug!r} in text files")
        print(f"  4. git init + initial commit in {target}")
        print(f"  5. append registry entry for {slug} to {REGISTRY_PATH}")
        print("\n[DRY RUN] No filesystem or registry writes performed.")
        return 0

    # ---- 1. Copy template ----
    if target.exists() and force:
        print(f"  removing existing {target} (--force)")
        _rmtree_force(target)

    MOBILE_APPS_BASE.mkdir(parents=True, exist_ok=True)
    print(f"  copying template -> {target}")
    shutil.copytree(TEMPLATE_DIR, target, dirs_exist_ok=False)

    # Drop any inherited .git from the source template (defensive; shouldn't exist)
    inherited_git = target / ".git"
    if inherited_git.exists():
        _rmtree_force(inherited_git)

    # ---- 2. Rename placeholder paths ----
    n_renamed = rename_placeholder_paths(target, slug)
    print(f"  renamed {n_renamed} path(s) containing {SLUG_PLACEHOLDER!r}")

    # ---- 3. Replace placeholders in file contents ----
    n_modified = replace_placeholders(target, slug)
    print(f"  replaced placeholder in {n_modified} file(s)")

    # ---- 4. git init + initial commit ----
    print(f"  git init in {target}")
    result = _run(["git", "init", "-b", "main"], cwd=target, check=False)
    if result.returncode != 0:
        print(f"  git init stderr: {result.stderr}", file=sys.stderr)
        print("WARNING: git init returned non-zero. Continuing anyway.", file=sys.stderr)
    else:
        # Initial commit so the operator has a clean baseline to diff against.
        _run(["git", "add", "-A"], cwd=target, check=False)
        commit_msg = f"chore: initial scaffold from mobile_app_expo template for {slug}"
        commit_res = _run(
            ["git", "commit", "-m", commit_msg, "--no-verify"],
            cwd=target,
            check=False,
        )
        if commit_res.returncode != 0:
            # Common cause: no git user.email configured. Non-fatal — the operator
            # can commit manually. Print but continue.
            print(
                f"  git commit skipped (returncode={commit_res.returncode}). "
                "Configure git user.name / user.email and commit manually.",
                file=sys.stderr,
            )
        else:
            print("  initial commit created")

    # ---- 5. Update registry ----
    now_iso = datetime.now(timezone.utc).isoformat()
    new_entry = {
        "slug": slug,
        "repo_path": str(target),
        "backend_stack": backend_stack,
        "spec_summary": None,
        "ios_bundle_id": None,
        "android_package": None,
        "eas_project_id": None,
        "last_build_sha": None,
        "health_url": None,
        "play_tester_gate_started_at": None,
        "play_tester_count_manual": None,
        "last_security_audit_at": None,
        "audit_passes_run": 0,
        "template_source": "execution/templates/mobile_app_expo",
        "created_at": now_iso,
    }

    if existing:
        registry["apps"] = [a for a in registry["apps"] if a.get("slug") != slug]
    registry.setdefault("apps", []).append(new_entry)
    write_registry_atomic(registry)
    print(f"  registry updated -> {REGISTRY_PATH}")

    # ---- Next steps banner ----
    print("\n" + "=" * 68)
    print("SCAFFOLD COMPLETE. Next steps:")
    print("=" * 68)
    print(f"  1. cd {target}")
    print("  2. npm install")
    print("  3. cp .env.example .env  # fill required vars (API_BASE_URL, bundle IDs)")
    print("  4. npm run typecheck && npm run test:unit  # sanity")
    print("  5. npx expo start  # local dev on your phone via Expo Go")
    print()
    print("  Before first EAS build:")
    print("     a. npm i -g eas-cli && eas login")
    print("     b. eas init  # links project to your Expo account")
    print(f"     c. Copy the returned projectId into {REGISTRY_PATH}")
    print("     d. Fill IOS_BUNDLE_ID + ANDROID_PACKAGE in .env")
    print()
    print("  Gates before Phase 4-5 (per execution/mobile_apps/preflight.py):")
    print("     - Apple Developer Program active  (~9 EUR/mo)")
    print("     - Google Play Console account     (~22 EUR one-time)")
    print()
    print("  Ship discipline (per ~/.claude/rules/front-door-synthetic.md):")
    print(f"     Do NOT write 'shipped/live' in {target / 'HANDOFF.md'} until:")
    print("     - Both stores approved AND")
    print(f"     - tests/front_door_{slug}.sh passes 5 consecutive days")
    print("=" * 68)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Scaffold a new mobile app from execution/templates/mobile_app_expo/."
    )
    parser.add_argument("slug", help="App slug (kebab-case, e.g. 'my-fitness-tracker').")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print planned operations, do not write anything.")
    parser.add_argument("--force", action="store_true",
                        help="Overwrite existing target dir and registry entry.")
    parser.add_argument("--backend-stack", choices=VALID_BACKEND_STACKS, default=None,
                        help="Backend track: cf_modal (CF Worker + Modal cron) OR "
                             "supabase (Postgres + Auth + Edge Functions). "
                             "Optional; can be set later via /mobile-app skill.")
    args = parser.parse_args()

    try:
        return cmd_create(
            args.slug,
            dry_run=args.dry_run,
            force=args.force,
            backend_stack=args.backend_stack,
        )
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 2
    except subprocess.CalledProcessError as e:
        print(f"ERROR: subprocess failed: {e}\nstderr: {e.stderr}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
