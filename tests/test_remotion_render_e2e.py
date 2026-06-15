"""E2E render test for execution/video/remotion_render.py.

GATED: only runs when environment variable REMOTION_LIVE=1 is set.

When enabled:
  1. Bootstraps the '_smoketest' project if not already registered.
  2. Renders 30 frames (~1 second of video) via remotion_render.py.
  3. Asserts: mp4 produced, file > 50 KB, ffprobe duration ~1 s (if ffprobe available).
  4. Cleans up the render artifact (keeps the bootstrap project for reuse).

Usage:
  REMOTION_LIVE=1 py -m pytest tests/test_remotion_render_e2e.py -v
"""

from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

# ── Skip gate ─────────────────────────────────────────────────────────────────

REMOTION_LIVE = os.environ.get("REMOTION_LIVE", "").strip() == "1"
skip_unless_live = pytest.mark.skipif(
    not REMOTION_LIVE,
    reason="Set REMOTION_LIVE=1 to run the E2E render test",
)

# ── Module paths ──────────────────────────────────────────────────────────────

WORKSPACE = Path(__file__).resolve().parents[1]
_RR_PATH = WORKSPACE / "execution" / "video" / "remotion_render.py"
_BS_PATH = WORKSPACE / "execution" / "video" / "remotion_bootstrap.py"
REGISTRY_PATH = WORKSPACE / "execution" / "video" / "registry.json"
RENDERS_DIR = WORKSPACE / ".tmp" / "remotion-renders"

# ── Load modules ──────────────────────────────────────────────────────────────

def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


rr = _load_module(_RR_PATH, "remotion_render")
bs = _load_module(_BS_PATH, "remotion_bootstrap")

SMOKETEST_SLUG = "_smoketest"
RENDER_FRAMES = "0-29"    # 30 frames = 1 s at 30 fps — fast to render


# ── Helpers ───────────────────────────────────────────────────────────────────

def _ensure_smoketest_bootstrapped() -> None:
    """Bootstrap _smoketest if not already in the registry."""
    if REGISTRY_PATH.exists():
        reg = json.loads(REGISTRY_PATH.read_text(encoding="utf-8"))
        if any(p.get("slug") == SMOKETEST_SLUG for p in reg.get("projects", [])):
            print(f"\n  [e2e] _smoketest already in registry — skipping bootstrap")
            return

    print(f"\n  [e2e] Bootstrapping '{SMOKETEST_SLUG}' project (this may take 3-5 min)…")
    code = bs.cmd_create(
        SMOKETEST_SLUG,
        dry_run=False,
        force=True,
        title="Smoketest",
        fps=30,
        width=1920,
        height=1080,
        duration_in_frames=90,   # 3 s — minimal for smoke purposes
    )
    if code != 0:
        pytest.fail(
            f"Bootstrap of '{SMOKETEST_SLUG}' failed with code {code}. "
            "Check that Node.js and npx are installed."
        )


def _ffprobe_duration(path: Path) -> float | None:
    """Return duration in seconds from ffprobe, or None if ffprobe unavailable."""
    if shutil.which("ffprobe") is None:
        return None
    try:
        result = subprocess.run(
            [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration",
                "-of", "default=noprint_wrappers=1:nokey=1",
                str(path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=30,
        )
        raw = result.stdout.strip()
        return float(raw) if raw else None
    except (subprocess.SubprocessError, ValueError):
        return None


# ── E2E test ──────────────────────────────────────────────────────────────────

@skip_unless_live
def test_e2e_render_smoketest_30_frames(tmp_path):
    """Full render pipeline: bootstrap → render 30 frames → validate → cleanup."""

    # 1. Bootstrap if needed
    _ensure_smoketest_bootstrapped()

    # 2. Resolve output path inside tmp_path (pytest auto-cleans it)
    out_mp4 = tmp_path / f"{SMOKETEST_SLUG}-e2e.mp4"

    # 3. Run render wrapper
    code = rr.render(
        SMOKETEST_SLUG,
        composition=None,       # auto-detect from Root.tsx
        out=str(out_mp4),
        frames=RENDER_FRAMES,
    )

    assert code == 0, (
        f"remotion_render.render() returned non-zero exit code {code}. "
        "Check stderr above for the Remotion render log."
    )

    # 4. Assert file produced
    assert out_mp4.exists(), f"Output file not found: {out_mp4}"

    # 5. Assert file > 50 KB (a zero-frame or corrupt render would be tiny)
    size = out_mp4.stat().st_size
    assert size > 50 * 1024, (
        f"Output file suspiciously small: {size} bytes (expected > 50 KB). "
        "The render may have produced no frames."
    )

    # 6. Optional ffprobe duration check (~1 s for 30 frames at 30 fps)
    duration = _ffprobe_duration(out_mp4)
    if duration is not None:
        assert 0.5 <= duration <= 2.0, (
            f"ffprobe duration {duration:.2f}s is outside expected range [0.5, 2.0]. "
            "Composition fps or frame range may be misconfigured."
        )
        print(f"\n  [e2e] ffprobe duration: {duration:.2f}s ✓")
    else:
        print("\n  [e2e] ffprobe not available — duration check skipped")

    print(f"\n  [e2e] render OK: {out_mp4} ({size:,} bytes)")
    # tmp_path is cleaned up automatically by pytest — no explicit deletion needed.
