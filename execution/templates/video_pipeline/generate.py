"""
description: Generation stage of the video pipeline template. Reads analysis.json
             (asset_plan[]) and calls Higgsfield MCP for image / video / audio
             generation, with an HF-Space fallback per feedback_check_hf_spaces_first.
             Hash-based cache: identical prompts on identical models reuse prior
             output. EUR-denominated cost tracking with per-invocation + daily
             kill switch per ~/.claude/rules/currency-eur.md and mandatory-audit-stack.
inputs:
  - --plan PATH                      (analysis.json produced by analyze.py)
  - --slug NAME                      (project slug; default from config)
  - --live                           (real MCP calls — burns credits)
  - --dry-run                        (default; returns cost estimate + would_generate)
  - --config PATH                    (default config/pipeline.json)
  - --model NAME                     (override default_model from config)
  - --n INT                          (override n_candidates from config)
  - --refresh                        (ignore hash cache)
  - Env: HIGGSFIELD_API_KEY (optional; MCP OAuth is preferred)
outputs:
  - .tmp/<slug>/assets/gen_<hash>.<ext>   (per-generation assets)
  - .tmp/<slug>/assets/manifest.json      (asset -> plan-index mapping)
  - .tmp/<slug>/run_log.jsonl             (append-only)
  - .tmp/video/spend_log.jsonl            (workspace-shared rolling spend)
  - stdout: JSON summary
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
except Exception:  # noqa: BLE001
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("generate")

HERE = Path(__file__).resolve().parent
CONFIG_PATH_DEFAULT = HERE / "config" / "pipeline.json"

USD_TO_EUR = 0.92

# Per-model EUR cost rough estimates. Update when Higgsfield pricing changes.
# Source: higgsfield.ai catalog + feedback_higgsfield_free_tier memory.
MODEL_COST_EUR = {
    "veo3_1_lite":    {"video": 0.37, "notes": "4 credits, 4s, 720p — free-tier escape hatch"},
    "veo3_1_fast":    {"video": 0.75, "notes": "8 credits, 8s"},
    "gemini_omni":    {"video": 0.46, "notes": "paid tier only"},
    "kling_3":        {"video": 0.20, "notes": "Basic-plan-gated on free tier"},
    "sora_2":         {"video": 1.10, "notes": "premium"},
    "image_default":  {"image": 0.04, "notes": "SDXL-equivalent"},
    "audio_default":  {"audio": 0.02, "notes": "TTS / music, per 10s"},
    "hf_space_free":  {"video": 0.0,  "notes": "free HF Space fallback, flaky"},
}


def _load_config(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _asset_hash(prompt: str, model: str, kind: str, duration: int, aspect: str) -> str:
    h = hashlib.sha256()
    payload = f"{prompt}|{model}|{kind}|{duration}|{aspect}"
    h.update(payload.encode("utf-8"))
    return h.hexdigest()[:16]


def _estimate_cost_eur(asset_plan: list[dict], model: str, n_candidates: int) -> float:
    total = 0.0
    for asset in asset_plan:
        kind = asset.get("kind", "video")
        model_costs = MODEL_COST_EUR.get(model, {})
        per_gen = model_costs.get(kind, 0.5)
        total += per_gen * n_candidates
    return round(total, 4)


def _read_today_spend_eur(spend_log: Path, slug: str) -> float:
    if not spend_log.exists():
        return 0.0
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    total = 0.0
    with spend_log.open("r", encoding="utf-8") as f:
        for line in f:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue  # skip malformed lines; log entries are best-effort append.
            if entry.get("slug") == slug and entry.get("ts", "").startswith(today):
                total += float(entry.get("cost_eur", 0.0))
    return round(total, 4)


def _append_run_log(log_path: Path, entry: dict) -> None:
    log_path.parent.mkdir(parents=True, exist_ok=True)
    with log_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def _generate_asset_live(asset: dict, model: str, out_path: Path) -> dict:
    """
    Live generation path — STUB in the template. Scaffolded projects wire
    Higgsfield MCP here. Per feedback_higgsfield_free_tier: call-shapes for
    generate_video are model-specific; validate via models_explore first.

    Real integration pattern:

        # from an interactive Claude session with the higgsfield MCP OAuth'd:
        result = mcp__higgsfield__generate_video(
            prompt=asset["prompt"],
            model=model,
            duration_seconds=asset.get("duration_seconds", 4),
            aspect_ratio=asset.get("aspect_ratio", "9:16"),
        )
        # then mcp__higgsfield__jobs_wait(job_ids=[result["job_id"]])
        # then mcp__higgsfield__show_generation_by_ids(...)
        # then download the URL to out_path

    Because MCP tools are only callable from an interactive Claude session
    (not from a bare Python subprocess), scaffolded projects should either:
      (a) invoke this stage from within a Claude session and pipe through
          the assistant, OR
      (b) fall back to the direct Higgsfield HTTP API using HIGGSFIELD_API_KEY.
    """
    log.warning(
        "generate.py: live generation is stubbed. Scaffolded projects "
        "implement Higgsfield MCP or HF-Space fallback here."
    )
    # Emit a zero-byte placeholder so downstream stages can be tested.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(b"")
    return {
        "output_path": str(out_path),
        "is_stub": True,
        "provider": "stub",
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Video pipeline: generate stage")
    ap.add_argument("--plan", type=Path, required=True,
                    help="analysis.json produced by analyze.py")
    ap.add_argument("--slug", default=None)
    ap.add_argument("--live", action="store_true",
                    help="real MCP calls — burns credits (respects cost ceiling)")
    ap.add_argument("--dry-run", action="store_true", default=None,
                    help="(default when --live absent) cost estimate only")
    ap.add_argument("--config", type=Path, default=CONFIG_PATH_DEFAULT)
    ap.add_argument("--model", default=None)
    ap.add_argument("--n", type=int, default=None, help="candidates per asset")
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()

    # Explicit safety: --dry-run wins over --live if operator passed both.
    is_dry_run = args.dry_run is True or not args.live

    if not args.plan.exists():
        log.error("plan not found: %s", args.plan)
        return 2
    cfg = _load_config(args.config)
    slug = args.slug or cfg.get("slug", "video")
    model = args.model or cfg["generation"]["default_model"]
    n_candidates = args.n or cfg["generation"]["n_candidates"]

    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    asset_plan = plan.get("asset_plan", [])
    if not asset_plan:
        log.error("analysis.json has empty asset_plan[]")
        return 2

    out_dir = HERE / ".tmp" / slug / "assets"
    out_dir.mkdir(parents=True, exist_ok=True)
    run_log = HERE / ".tmp" / slug / "run_log.jsonl"

    workspace_root = HERE.parents[2] if (HERE.parents[2] / ".tmp").exists() else HERE
    spend_log = Path(os.environ.get("SPEND_LOG_PATH",
                                    workspace_root / ".tmp" / "video" / "spend_log.jsonl"))
    spend_log.parent.mkdir(parents=True, exist_ok=True)

    est_cost = _estimate_cost_eur(asset_plan, model, n_candidates)
    ceiling_eur = float(cfg["cost"]["daily_cost_ceiling_eur"])
    confirm_over = float(cfg["cost"]["per_invocation_confirm_over_eur"])
    today_spend = _read_today_spend_eur(spend_log, slug)

    plan_summary = {
        "slug": slug,
        "model": model,
        "n_candidates": n_candidates,
        "n_assets": len(asset_plan),
        "would_generate": len(asset_plan) * n_candidates,
        "cost_eur_estimate": est_cost,
        "today_spend_eur": today_spend,
        "daily_ceiling_eur": ceiling_eur,
        "would_exceed_ceiling": (today_spend + est_cost) > ceiling_eur,
        "would_prompt_operator_confirm": est_cost > confirm_over,
    }

    if is_dry_run:
        _append_run_log(run_log, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": "generate", "slug": slug, "mode": "dry-run",
            "plan": plan_summary,
        })
        print(json.dumps({"mode": "dry-run", "plan": plan_summary}, indent=2))
        return 0

    # Kill switch: refuse if projected total > daily ceiling.
    if plan_summary["would_exceed_ceiling"]:
        log.error(
            "DAILY_COST_CEILING_HIT: today=%.4f€ + est=%.4f€ > ceiling=%.2f€",
            today_spend, est_cost, ceiling_eur,
        )
        _append_run_log(run_log, {
            "ts": datetime.now(timezone.utc).isoformat(),
            "stage": "generate", "slug": slug, "mode": "live-blocked",
            "reason": "DAILY_COST_CEILING_HIT", "plan": plan_summary,
        })
        return 3

    # Live path
    manifest = []
    total_cost = 0.0
    for idx, asset in enumerate(asset_plan):
        prompt = asset.get("prompt", "")
        kind = asset.get("kind", "video")
        duration = int(asset.get("duration_seconds", 4))
        aspect = asset.get("aspect_ratio", cfg["aspect_ratio"])

        for cand in range(n_candidates):
            asset_hash = _asset_hash(f"{prompt}|cand{cand}", model, kind, duration, aspect)
            ext = {"video": "mp4", "image": "png", "audio": "mp3"}.get(kind, "bin")
            out_path = out_dir / f"gen_{asset_hash}.{ext}"

            if out_path.exists() and out_path.stat().st_size > 0 and not args.refresh:
                log.info("cache hit: %s", out_path.name)
                manifest.append({"asset_idx": idx, "candidate": cand,
                                 "path": str(out_path), "cached": True})
                continue

            t0 = time.monotonic()
            try:
                result = _generate_asset_live(asset, model, out_path)
            except Exception as e:  # noqa: BLE001 — log + continue; per-asset failure isolated.
                log.error("asset %d cand %d failed: %s", idx, cand, e)
                _append_run_log(run_log, {
                    "ts": datetime.now(timezone.utc).isoformat(),
                    "stage": "generate", "slug": slug, "mode": "live",
                    "asset_idx": idx, "candidate": cand, "error": str(e),
                })
                continue
            elapsed_ms = int((time.monotonic() - t0) * 1000)

            per_cost = MODEL_COST_EUR.get(model, {}).get(kind, 0.5)
            total_cost += per_cost

            manifest.append({
                "asset_idx": idx, "candidate": cand,
                "path": str(out_path), "cost_eur": per_cost,
                "elapsed_ms": elapsed_ms, "cached": False,
                "is_stub": result.get("is_stub", False),
            })

            entry = {
                "ts": datetime.now(timezone.utc).isoformat(),
                "stage": "generate", "slug": slug, "mode": "live",
                "model": model, "kind": kind,
                "prompt": prompt[:200], "cost_eur": per_cost,
                "elapsed_ms": elapsed_ms, "cache": "miss",
                "output": str(out_path),
            }
            _append_run_log(run_log, entry)
            _append_run_log(spend_log, {**entry, "slug": slug})

    manifest_path = out_dir / "manifest.json"
    manifest_path.write_text(json.dumps({
        "slug": slug, "model": model, "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_cost_eur": round(total_cost, 4),
        "assets": manifest,
    }, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps({
        "mode": "live", "slug": slug, "manifest": str(manifest_path),
        "total_cost_eur": round(total_cost, 4), "n_generated": len(manifest),
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
