"""
description: Render a Remotion composition to video via `npx remotion render`.
inputs: CLI: --slug <slug> [--composition <id>] [--out <path>] [--frames <range>]
outputs: .tmp/remotion-renders/<slug>-<timestamp>.mp4 (or caller-supplied path); prints path, size, render time.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:
    load_dotenv = None  # type: ignore[assignment]

# ── Constants ─────────────────────────────────────────────────────────────────

ROOT = Path(__file__).resolve().parent.parent.parent
if load_dotenv is not None:
    load_dotenv(ROOT / ".env")

PROJECTS_DIR = ROOT / "execution" / "video" / "remotion-projects"
REGISTRY_PATH = ROOT / "execution" / "video" / "registry.json"
RENDERS_DIR = ROOT / ".tmp" / "remotion-renders"

SLUG_RE = re.compile(r"^[a-z0-9_][a-z0-9_-]{0,48}[a-z0-9]$|^[a-z0-9_]$")

RENDER_TIMEOUT_S = 600   # 10 min hard cap


# ── Helpers ───────────────────────────────────────────────────────────────────

def validate_slug(slug: str) -> Path:
    """Validate slug format and return the resolved project dir.

    Windows hardening rule #3: resolve + containment check.
    Raises ValueError on any invalid or traversal input.
    """
    if not SLUG_RE.match(slug):
        raise ValueError(
            f"Invalid slug '{slug}'. Use lowercase letters, digits, "
            "hyphens, or underscores (1-50 chars)."
        )
    candidate = (PROJECTS_DIR / slug).resolve()
    if not candidate.is_relative_to(PROJECTS_DIR.resolve()):
        raise ValueError(
            f"Path-traversal attempt: '{slug}' resolves outside projects dir."
        )
    return candidate


def validate_out_path(out: str) -> Path:
    """Validate a caller-supplied output path.

    Windows hardening rule #3: must stay within ROOT (the workspace boundary).
    Raises ValueError on traversal.
    """
    candidate = Path(out).resolve()
    if not candidate.is_relative_to(ROOT.resolve()):
        raise ValueError(
            f"--out path '{out}' resolves outside the workspace boundary "
            f"({ROOT}). Use a relative path under the workspace."
        )
    return candidate


def load_registry() -> dict:
    if not REGISTRY_PATH.exists():
        return {"schema_version": 1, "projects": []}
    with REGISTRY_PATH.open("r", encoding="utf-8") as fh:
        return json.load(fh)


def find_project(registry: dict, slug: str) -> dict | None:
    for proj in registry.get("projects", []):
        if proj.get("slug") == slug:
            return proj
    return None


def pick_composition(project_dir: Path) -> str:
    """Return the first composition ID found in Root.tsx / src/Root.tsx.

    Looks for patterns like:  id="SceneName"  or  id={'SceneName'}
    Falls back to 'Scene' if nothing found (the template default).
    """
    for root_candidate in [
        project_dir / "Root.tsx",
        project_dir / "src" / "Root.tsx",
    ]:
        if not root_candidate.exists():
            continue
        text = root_candidate.read_text(encoding="utf-8", errors="replace")
        # Match:  id="Name"  |  id='Name'  |  id={'Name'}  |  id={"Name"}
        for match in re.finditer(
            r"""id=(?:"([A-Za-z0-9_]+)"|'([A-Za-z0-9_]+)'|\{['"]([A-Za-z0-9_]+)['"]\})""",
            text,
        ):
            # One of the three groups will be set
            return match.group(1) or match.group(2) or match.group(3)
    return "Scene"


def default_out_path(slug: str) -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return RENDERS_DIR / f"{slug}-{ts}.mp4"


# ── Render ────────────────────────────────────────────────────────────────────

def render(
    slug: str,
    *,
    composition: str | None,
    out: str | None,
    frames: str | None,
) -> int:
    """Core render logic. Returns 0 on success, non-zero on failure."""

    # 1. Resolve project dir via slug validation (rule #3)
    try:
        project_dir = validate_slug(slug)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2

    # 2. Resolve output path (rule #3 for caller-supplied value)
    if out is not None:
        try:
            out_path = validate_out_path(out)
        except ValueError as exc:
            print(f"ERROR: {exc}", file=sys.stderr)
            return 2
    else:
        out_path = default_out_path(slug)

    # 3. Registry lookup — project must be registered
    registry = load_registry()
    entry = find_project(registry, slug)
    if entry is None:
        print(
            f"ERROR: slug '{slug}' not found in registry ({REGISTRY_PATH}). "
            "Run remotion_bootstrap.py --slug <slug> first.",
            file=sys.stderr,
        )
        return 2

    # 4. Validate project directory exists
    if not project_dir.exists():
        print(
            f"ERROR: project dir does not exist: {project_dir}\n"
            "Re-run remotion_bootstrap.py --slug <slug> to recreate it.",
            file=sys.stderr,
        )
        return 2

    # 5. Validate node_modules present (junction or real dir)
    nm = project_dir / "node_modules"
    if not nm.exists():
        print(
            f"ERROR: node_modules not found at {nm}.\n"
            "Run 'npm install' inside the project dir or re-bootstrap.",
            file=sys.stderr,
        )
        return 2

    # 6. Validate Root.tsx exists
    root_tsx = None
    for candidate in [project_dir / "Root.tsx", project_dir / "src" / "Root.tsx"]:
        if candidate.exists():
            root_tsx = candidate
            break
    if root_tsx is None:
        print(
            f"ERROR: neither Root.tsx nor src/Root.tsx found in {project_dir}.",
            file=sys.stderr,
        )
        return 2

    # 7. Pick composition name
    comp_id = composition or pick_composition(project_dir)

    # 8. Ensure output dir exists
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # 9. Build npx remotion render command
    cmd = [
        "npx", "remotion", "render",
        comp_id,
        str(out_path),
        "--concurrency", "2",
        "--log", "warn",
    ]
    if frames:
        cmd += ["--frames", frames]

    print(f"Rendering '{comp_id}' from slug '{slug}'")
    print(f"  project : {project_dir}")
    print(f"  out     : {out_path}")
    if frames:
        print(f"  frames  : {frames}")
    print(f"  cmd     : {' '.join(cmd)}\n")

    t_start = time.monotonic()

    # 10. Run render — subprocess with required hardening (rule #1)
    # Use shell=True on Windows so npx.cmd wrapper resolves.
    # dict(os.environ) per environ-not-copy-copy rule (rule #6).
    env = dict(os.environ)
    try:
        result = subprocess.run(
            cmd,
            cwd=str(project_dir),
            capture_output=False,    # stream stdout/stderr live
            text=True,
            shell=True,
            encoding="utf-8",
            errors="replace",
            timeout=RENDER_TIMEOUT_S,
            env=env,
        )
    except subprocess.TimeoutExpired:
        print(
            f"\nERROR: render timed out after {RENDER_TIMEOUT_S}s.",
            file=sys.stderr,
        )
        return 1
    except (FileNotFoundError, OSError) as exc:
        print(
            f"\nERROR: failed to launch npx: {exc}\n"
            "Make sure Node.js is installed and 'npx' is on PATH.",
            file=sys.stderr,
        )
        return 1

    elapsed = time.monotonic() - t_start

    if result.returncode != 0:
        print(
            f"\nERROR: npx remotion render exited with code {result.returncode}.",
            file=sys.stderr,
        )
        return result.returncode

    # 11. Assert output exists and is non-empty
    if not out_path.exists():
        print(
            f"\nERROR: render returned 0 but output file not found: {out_path}",
            file=sys.stderr,
        )
        return 1

    size_bytes = out_path.stat().st_size
    if size_bytes == 0:
        print(
            f"\nERROR: render returned 0 but output file is empty: {out_path}",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nRender complete.\n"
        f"  out   : {out_path}\n"
        f"  size  : {size_bytes:,} bytes ({size_bytes / 1024 / 1024:.2f} MB)\n"
        f"  time  : {elapsed:.1f}s"
    )
    return 0


# ── CLI ───────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Render a Remotion composition to video. "
            "Wraps `npx remotion render` with workspace registry integration."
        )
    )
    parser.add_argument(
        "--slug", required=True, metavar="SLUG",
        help="Project slug (must exist in registry.json).",
    )
    parser.add_argument(
        "--composition", default=None, metavar="COMP_ID",
        help="Composition ID to render (default: first <Composition> in Root.tsx).",
    )
    parser.add_argument(
        "--out", default=None, metavar="PATH",
        help=(
            "Output file path (default: .tmp/remotion-renders/<slug>-<ts>.mp4). "
            "Must be within the workspace directory."
        ),
    )
    parser.add_argument(
        "--frames", default=None, metavar="RANGE",
        help="Frame range to render, e.g. '0-29' or '15'. Default: full composition.",
    )

    args = parser.parse_args()
    return render(
        args.slug,
        composition=args.composition,
        out=args.out,
        frames=args.frames,
    )


if __name__ == "__main__":
    sys.exit(main())
