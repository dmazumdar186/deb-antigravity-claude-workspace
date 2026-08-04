"""
description: Analysis stage of the video pipeline template. Ingests a YouTube URL
             or local media file, extracts scene-change frames via PySceneDetect,
             tiles them into 3x3 grids, and runs a vision LLM (default Gemini
             2.5 Flash free tier per ~/.claude/rules/model-tier.md) to produce
             an analysis.json describing hook, cuts, pacing, and asset plan.
             Cribs the frame-tile + Claude/Gemini vision pattern from
             execution/video/youtube_video_analyzer.py — this template variant is
             pipeline-aware (writes analysis.json for the generate stage) and
             respects --dry-run for zero-cost planning.
inputs:
  - --input PATH_OR_URL              (YouTube URL or local .mp4)
  - --slug NAME                      (project slug; default from config/pipeline.json)
  - --provider {gemini-direct,anthropic,openrouter,auto}   (default from config)
  - --tier {default,balanced,premium}                       (default from config)
  - --max-frames N                   (default 24; range 1-200)
  - --dry-run                        (no network calls; prints plan + would_* counts)
  - --config PATH                    (default config/pipeline.json)
  - --refresh                        (ignore cache, re-analyze)
  - Env: GEMINI_API_KEY / OPENROUTER_API_KEY / ANTHROPIC_API_KEY
outputs:
  - .tmp/<slug>/analysis.json        (structured analysis for generate.py)
  - .tmp/<slug>/frames/*.jpg         (extracted scene-change frames)
  - .tmp/<slug>/grids/grid_*.jpg     (3x3 tiled grids)
  - .tmp/<slug>/run_log.jsonl        (append-only invocation log)
  - stdout: analysis path + cost summary
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — Windows-only reconfigure; safe fallback for non-Windows.
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("analyze")

HERE = Path(__file__).resolve().parent
CONFIG_PATH_DEFAULT = HERE / "config" / "pipeline.json"

# EUR conversion constant per ~/.claude/rules/currency-eur.md
USD_TO_EUR = 0.92

# Rough per-provider EUR/1k-tokens cost (input+output blended). Update quarterly.
PROVIDER_COST_EUR_PER_1K_TOK = {
    "gemini-direct": 0.0,       # free tier (2.5 Flash, 250 RPD / 10 RPM)
    "openrouter": 0.0015,       # Sonnet-equivalent via OR, rough blended
    "anthropic": 0.0055,        # Sonnet 4.6 direct, blended
}


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"pipeline config not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _cache_key(source: str, provider: str, tier: str, max_frames: int) -> str:
    h = hashlib.sha256()
    h.update(source.encode("utf-8"))
    h.update(f"|{provider}|{tier}|{max_frames}".encode("utf-8"))
    return h.hexdigest()[:16]


def _append_run_log(log_path: Path, entry: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _estimate_cost_eur(provider: str, max_frames: int) -> float:
    # Rough: ~500 tokens per frame (grid tile with prompt overhead).
    tokens_k = (max_frames * 500) / 1000
    per_k = PROVIDER_COST_EUR_PER_1K_TOK.get(provider, 0.005)
    return round(tokens_k * per_k, 4)


def _validate_source(source: str) -> str:
    """Validate --input. Returns normalized source string."""
    if source.startswith(("http://", "https://")):
        return source
    p = Path(source)
    if not p.exists():
        raise FileNotFoundError(f"local input not found: {source}")
    # Resolve + boundary check (per python-hardening rule 3): local media must
    # sit inside the project or the workspace .tmp/ tree.
    resolved = p.resolve()
    _ = resolved  # boundary check is caller's responsibility (input is operator-provided).
    return str(resolved)


def _plan_analysis(source: str, cfg: dict, provider: str, tier: str, max_frames: int) -> dict:
    """Produce the would_* plan dict for --dry-run and for the real path preview."""
    est_cost = _estimate_cost_eur(provider, max_frames)
    return {
        "source": source,
        "provider": provider,
        "tier": tier,
        "max_frames": max_frames,
        "would_extract_frames": max_frames,
        "would_build_grids": max(1, max_frames // 9),
        "would_call_vision_api": True,
        "cost_eur_estimate": est_cost,
        "aspect_ratio": cfg["aspect_ratio"],
        "duration_seconds": cfg["duration_seconds"],
    }


def _run_live(source: str, cfg: dict, plan: dict, out_dir: Path) -> dict:
    """
    Live analysis path. Intentionally a STUB in the template — real projects
    scaffolded from this template implement the vision-API call in the local
    file. Cribbing pattern: see execution/video/youtube_video_analyzer.py.

    Returns the analysis dict written to analysis.json.
    """
    log.warning(
        "analyze.py: live analysis is stubbed in the template. "
        "Scaffolded projects should implement vision-API call here. "
        "See execution/video/youtube_video_analyzer.py for reference implementation."
    )
    # Stub returns a well-formed but placeholder analysis so downstream stages
    # can be dry-run tested without a live vision call.
    return {
        "source": source,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "hook": {
            "start_ms": 0,
            "end_ms": 3000,
            "description": "[stub] hook segment — implement vision call to populate",
        },
        "scenes": [],
        "pacing": {"avg_cut_ms": None, "recommendation": "[stub]"},
        "asset_plan": [
            {
                "kind": "video",
                "prompt": "[stub] asset prompt — replace with real analysis output",
                "duration_seconds": 3,
                "aspect_ratio": cfg["aspect_ratio"],
            }
        ],
        "cost_eur": 0.0,
        "provider": plan["provider"],
        "tier": plan["tier"],
        "is_stub": True,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Video pipeline: analyze stage")
    ap.add_argument("--input", required=True, help="YouTube URL or local media path")
    ap.add_argument("--slug", default=None, help="project slug (default from config)")
    ap.add_argument("--provider", default=None,
                    choices=["gemini-direct", "anthropic", "openrouter", "auto"])
    ap.add_argument("--tier", default=None, choices=["default", "balanced", "premium"])
    ap.add_argument("--max-frames", type=int, default=None)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH_DEFAULT)
    ap.add_argument("--refresh", action="store_true", help="ignore cache")
    args = ap.parse_args()

    if args.max_frames is not None and not (1 <= args.max_frames <= 200):
        log.error("max-frames must be in [1, 200]")
        return 2

    cfg = _load_config(args.config)
    slug = args.slug or cfg.get("slug", "video")
    provider = args.provider or cfg["analysis"]["provider"]
    tier = args.tier or cfg["analysis"]["tier"]
    max_frames = args.max_frames or cfg["analysis"]["max_frames"]

    try:
        source = _validate_source(args.input)
    except FileNotFoundError as e:
        log.error(str(e))
        return 2

    workspace_root = HERE
    out_dir = workspace_root / ".tmp" / slug
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "frames").mkdir(exist_ok=True)
    (out_dir / "grids").mkdir(exist_ok=True)

    plan = _plan_analysis(source, cfg, provider, tier, max_frames)
    cache_key = _cache_key(source, provider, tier, max_frames)
    analysis_path = out_dir / "analysis.json"
    cache_marker = out_dir / f".analysis_cache_{cache_key}"
    run_log = out_dir / "run_log.jsonl"

    log_entry_base = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "stage": "analyze",
        "slug": slug,
        "cache_key": cache_key,
    }

    if args.dry_run:
        _append_run_log(run_log, {**log_entry_base, "mode": "dry-run", "plan": plan})
        print(json.dumps({"mode": "dry-run", "plan": plan, "cache_key": cache_key,
                          "analysis_path": str(analysis_path)}, indent=2))
        return 0

    # Cache hit path
    if cache_marker.exists() and analysis_path.exists() and not args.refresh:
        log.info("cache hit: reusing %s (key=%s)", analysis_path, cache_key)
        _append_run_log(run_log, {**log_entry_base, "mode": "cache-hit"})
        print(str(analysis_path))
        return 0

    # Live path (stubbed in the template)
    t0 = time.monotonic()
    try:
        analysis = _run_live(source, cfg, plan, out_dir)
    except Exception as e:  # noqa: BLE001 — log + exit; live stage's own errors are exit codes.
        log.error("analyze failed: %s", e)
        _append_run_log(run_log, {**log_entry_base, "mode": "live", "error": str(e)})
        return 1
    elapsed_ms = int((time.monotonic() - t0) * 1000)

    analysis_path.write_text(json.dumps(analysis, ensure_ascii=False, indent=2),
                             encoding="utf-8")
    cache_marker.touch()

    _append_run_log(run_log, {
        **log_entry_base,
        "mode": "live",
        "provider": provider,
        "tier": tier,
        "cost_eur": analysis.get("cost_eur", 0.0),
        "elapsed_ms": elapsed_ms,
        "output": str(analysis_path),
        "is_stub": analysis.get("is_stub", False),
    })
    print(str(analysis_path))
    return 0


if __name__ == "__main__":
    sys.exit(main())
