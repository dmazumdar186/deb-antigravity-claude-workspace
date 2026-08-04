"""Scaffold a new Astro + Cloudflare Pages web app from the workspace template.

Usage:
    py execution/templates/scaffold_web_app.py \
        --name my-new-site \
        --domain my-new-site.example.com \
        --output execution/personal_workflows/my_new_site

Effects:
    1. Copy execution/templates/web_app_astro_cf/ -> <output>.
    2. Substitute <PROJECT_NAME> and <PROJECT_DOMAIN> placeholders in
       every text file (README, HANDOFF, HARDENING, wrangler.toml,
       astro.config.mjs, .env.example, tests/*, etc.).
    3. Rename tests/acceptance_PROJECT_NAME.py + tests/front_door_PROJECT_NAME.sh
       to use the project slug.
    4. Rewrite package.json script references to use the slug.
    5. `git init` in <output>, install pre-commit via `git config
       core.hooksPath .githooks`.
    6. Create initial commit (unless --no-commit).
    7. Print the next-steps runbook.

Does NOT:
    - Install npm dependencies (leave that to the operator; can be slow).
    - Deploy anything.
    - Touch any file outside <output>.

Follows:
    ~/.claude/rules/python-hardening.md — subprocess encoding=utf-8, no
    bare-except.
    ~/.claude/rules/security.md — never prints secrets.
"""

from __future__ import annotations

import argparse
import re
import shutil
import subprocess
import sys
from pathlib import Path

TEMPLATE_VERSION = "0.1.0"

TEMPLATE_DIR = Path(__file__).resolve().parent / "web_app_astro_cf"

# File extensions that get placeholder substitution. Binary files (favicon,
# etc.) are excluded to avoid corrupting them.
TEXT_EXTENSIONS = {
    ".astro", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json",
    ".md", ".mdx", ".yml", ".yaml", ".toml", ".sh", ".py", ".html",
    ".css", ".txt", ".env", ".example", ".gitignore",
}
# Also include specific dotfile names by exact match.
TEXT_BASENAMES = {".env.example", ".gitignore", "_headers", "pre-commit", "robots.txt"}


def is_text_file(p: Path) -> bool:
    if p.name in TEXT_BASENAMES:
        return True
    if p.suffix in TEXT_EXTENSIONS:
        return True
    # Files with no extension at repo root (Makefile, LICENSE, …)
    if not p.suffix and p.is_file() and p.stat().st_size < 1_000_000:
        try:
            p.read_text(encoding="utf-8")
            return True
        except (UnicodeDecodeError, OSError):
            return False
    return False


def validate_slug(name: str) -> str:
    if not re.match(r"^[a-z][a-z0-9_-]{1,63}$", name):
        raise SystemExit(
            f"Invalid --name {name!r}: must be lowercase, start with a letter, "
            "and contain only [a-z0-9_-] (2-64 chars)."
        )
    return name


def copy_template(dst: Path) -> None:
    if dst.exists() and any(dst.iterdir()):
        raise SystemExit(f"Output directory {dst} exists and is non-empty. Aborting.")
    shutil.copytree(TEMPLATE_DIR, dst, dirs_exist_ok=True)
    print(f"[copy] {TEMPLATE_DIR} -> {dst}")


def substitute_placeholders(root: Path, name: str, domain: str) -> None:
    count = 0
    for p in root.rglob("*"):
        if not p.is_file():
            continue
        # Skip node_modules etc. (defensive; the template shouldn't have them).
        if any(part in {"node_modules", ".git", "dist", ".astro", ".wrangler"} for part in p.parts):
            continue
        if not is_text_file(p):
            continue
        try:
            content = p.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        new_content = content.replace("<PROJECT_NAME>", name).replace("<PROJECT_DOMAIN>", domain)
        if new_content != content:
            p.write_text(new_content, encoding="utf-8")
            count += 1
    print(f"[subst] Placeholder substitution applied to {count} files")


def rename_test_files(root: Path, name: str) -> None:
    for pattern, ext in [("acceptance_PROJECT_NAME", ".py"), ("front_door_PROJECT_NAME", ".sh")]:
        old = root / "tests" / f"{pattern}{ext}"
        if old.exists():
            new = root / "tests" / f"{pattern.replace('PROJECT_NAME', name)}{ext}"
            old.rename(new)
            print(f"[rename] {old.name} -> {new.name}")


def init_git(root: Path, do_commit: bool) -> None:
    def _run(cmd: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            cmd, cwd=root, encoding="utf-8", errors="replace",
            capture_output=True, check=check,
        )

    if (root / ".git").exists():
        print("[git] .git already exists — skipping init")
    else:
        _run(["git", "init", "-q"])
        print("[git] initialized")

    # Wire the pre-commit hook via core.hooksPath (no symlink needed on Windows).
    _run(["git", "config", "core.hooksPath", ".githooks"])
    print("[git] core.hooksPath -> .githooks")

    # Make the hook executable (Unix); on Windows this is a noop but doesn't hurt.
    hook = root / ".githooks" / "pre-commit"
    if hook.exists():
        try:
            hook.chmod(0o755)
        except OSError:
            pass

    if do_commit:
        _run(["git", "add", "."])
        # First commit bypasses the pre-commit hook because at this point
        # everything is being added anyway.
        res = _run(
            ["git", "commit", "-q", "--no-verify", "-m", f"chore: scaffold from web_app_astro_cf v{TEMPLATE_VERSION}"],
            check=False,
        )
        if res.returncode == 0:
            print("[git] initial commit created (no-verify — bootstrap only)")
        else:
            print(f"[git] initial commit skipped: {res.stderr.strip() or res.stdout.strip()}")


def print_next_steps(root: Path, name: str, domain: str) -> None:
    print("")
    print("=" * 60)
    print(f"  Scaffolded: {name}  (domain: {domain})")
    print(f"  Location:   {root}")
    print(f"  Template:   v{TEMPLATE_VERSION}")
    print("=" * 60)
    print("")
    print("Next steps:")
    print(f"  cd {root}")
    print("  npm install                          # first-time only")
    print("  cp .env.example .env                 # then fill in values")
    print("  npm run dev                          # localhost:4321")
    print("  npm run test:unit                    # tier 1")
    print("")
    print(f"  npx wrangler pages project create {name} --production-branch=main")
    print(f"  npx wrangler pages secret put DASHBOARD_PASS --project-name={name}")
    print(f"  npx wrangler pages deploy dist --project-name={name}")
    print("")
    print("  # After first deploy, verify liveness:")
    print(f"  SITE_URL=https://{domain} bash tests/front_door_{name}.sh")
    print(f"  SITE_URL=https://{domain} py tests/acceptance_{name}.py")
    print("")
    print("Update HANDOFF.md with the deploy URL. Do NOT write 'shipped'")
    print("until the front-door synthetic passes 5 consecutive days.")
    print("")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0] if __doc__ else "")
    ap.add_argument("--name", required=True, help="Project slug (lowercase, [a-z0-9_-]).")
    ap.add_argument("--domain", required=True, help="Production domain (no scheme, no path).")
    ap.add_argument("--output", required=True, help="Output directory (must not exist or be empty).")
    ap.add_argument("--no-commit", action="store_true", help="Skip the initial git commit.")
    args = ap.parse_args()

    name = validate_slug(args.name)
    domain = args.domain.strip().replace("https://", "").replace("http://", "").rstrip("/")
    output = Path(args.output).resolve()

    if not TEMPLATE_DIR.exists():
        raise SystemExit(f"Template not found: {TEMPLATE_DIR}")

    copy_template(output)
    substitute_placeholders(output, name, domain)
    rename_test_files(output, name)
    init_git(output, do_commit=not args.no_commit)
    print_next_steps(output, name, domain)
    return 0


if __name__ == "__main__":
    sys.exit(main())
