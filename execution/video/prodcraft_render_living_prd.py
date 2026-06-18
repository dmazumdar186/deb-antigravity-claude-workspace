"""
description: Stage Living PRD assets into the Remotion project's public/ dir and render the ProdCraftLivingPRD composition. Trims words.json to the POC duration so captions don't overrun.
inputs:
    CLI:
        --audio PATH       input audio (default: .tmp/prodcraft/phase1_audio_v2.wav)
        --plan PATH        living_prd_plan.json (default: .tmp/prodcraft/living_prd_plan.json)
        --words PATH       word timings JSON (default: .tmp/prodcraft/phase1_audio_v2_words.json)
        --project-dir PATH Remotion project root (default: execution/video/remotion-projects/prodcraft_smoke)
        --out PATH         final MP4 (default: .tmp/prodcraft/living_prd_poc.mp4)
        --comp-id NAME     composition (default: ProdCraftLivingPRD)
        --concurrency N    Remotion render concurrency (default: 4)
        --no-render        stage only
outputs:
    {project_dir}/public/audio.wav
    {project_dir}/public/living_prd_plan.json
    {project_dir}/public/words.json
    {out}                  final mp4
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_AUDIO = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_audio_v2.wav"
DEFAULT_PLAN = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "living_prd_plan.json"
DEFAULT_WORDS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_audio_v2_words.json"
DEFAULT_PROJECT = WORKSPACE_ROOT / "execution" / "video" / "remotion-projects" / "prodcraft_smoke"
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "living_prd_poc.mp4"


def stage(audio: Path, plan_path: Path, words_path: Path, project_dir: Path) -> dict:
    public = project_dir / "public"
    public.mkdir(parents=True, exist_ok=True)

    if not audio.exists():
        raise SystemExit(f"Audio not found: {audio}")
    if not plan_path.exists():
        raise SystemExit(f"Plan not found: {plan_path}")
    if not words_path.exists():
        raise SystemExit(f"Words not found: {words_path}")

    shutil.copy2(audio, public / "audio.wav")

    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    (public / "living_prd_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # Trim word list to the plan's duration so captions stop with the comp.
    duration = plan.get("audio_duration_sec", 0)
    words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])
    trimmed = [w for w in words if w["start"] < duration]
    (public / "words.json").write_text(json.dumps(trimmed), encoding="utf-8")

    return {
        "audio": str(public / "audio.wav"),
        "ops": len(plan.get("ops", [])),
        "duration_sec": duration,
        "words_trimmed": len(trimmed),
    }


def render(project_dir: Path, comp_id: str, out_path: Path, concurrency: int) -> None:
    cmd_npx = "npx.cmd"
    cmd = [
        cmd_npx, "remotion", "render",
        comp_id, str(out_path),
        "--concurrency", str(concurrency),
        "--log", "info",
    ]
    print(f"\n>>> {' '.join(cmd)}\n    (cwd={project_dir})\n", file=sys.stderr)
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=str(project_dir), encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - t0
    if r.returncode != 0:
        raise SystemExit(f"Remotion render failed (code {r.returncode}) after {elapsed:.1f}s")
    print(f"\nOK | living_prd render | elapsed={elapsed:.1f}s | out={out_path}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="Render Living PRD POC.")
    p.add_argument("--audio", default=str(DEFAULT_AUDIO))
    p.add_argument("--plan", default=str(DEFAULT_PLAN))
    p.add_argument("--words", default=str(DEFAULT_WORDS))
    p.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--comp-id", default="ProdCraftLivingPRD")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--no-render", action="store_true")
    args = p.parse_args()

    project_dir = Path(args.project_dir).resolve()
    info = stage(
        Path(args.audio).resolve(),
        Path(args.plan).resolve(),
        Path(args.words).resolve(),
        project_dir,
    )
    print(json.dumps(info, indent=2))

    if not args.no_render:
        render(project_dir, args.comp_id, Path(args.out).resolve(), args.concurrency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
