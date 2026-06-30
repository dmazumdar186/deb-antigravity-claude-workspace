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


def stage(audio: Path, plan_path: Path, words_path: Path, project_dir: Path, plan_filename: str = "living_prd_plan.json") -> dict:
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
    (public / plan_filename).write_text(json.dumps(plan, indent=2), encoding="utf-8")

    # Trim word list to the plan's duration so captions stop with the comp.
    duration = plan.get("audio_duration_sec", 0)
    words = json.loads(words_path.read_text(encoding="utf-8")).get("words", [])
    trimmed = [w for w in words if w["start"] < duration]
    (public / "words.json").write_text(json.dumps(trimmed), encoding="utf-8")

    return {
        "audio": str(public / "audio.wav"),
        "plan_file": plan_filename,
        "ops_or_scenes": len(plan.get("ops", plan.get("scenes", []))),
        "duration_sec": duration,
        "words_trimmed": len(trimmed),
    }


def _get_ffmpeg_bin() -> str:
    """Bundled ffmpeg via imageio_ffmpeg — avoids PATH dependency on Windows."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise SystemExit("Run: py -m pip install imageio-ffmpeg") from e


def _windows_player_fix(src: Path, dst: Path) -> None:
    """Re-encode Remotion's yuvj420p+bt470bg output to yuv420p(tv)+bt709 so
    Windows Films & TV / Media Player render the video instead of showing a
    near-black screen. VLC/Chrome/QuickTime tolerate the Remotion default; native
    Windows players don't. ~30s for a 2-3min 1080p MP4 at CRF 20."""
    ffmpeg = _get_ffmpeg_bin()
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-vf", "scale=in_range=full:out_range=tv,format=yuv420p",
        "-color_range", "tv",
        "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
        "-movflags", "+faststart",
        "-c:a", "copy",
        str(dst),
    ]
    result = subprocess.run(
        cmd, capture_output=True, encoding="utf-8", errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"player-fix ffmpeg failed (code {result.returncode}):\n{result.stderr[-1500:]}")


def render(project_dir: Path, comp_id: str, out_path: Path, concurrency: int, skip_player_fix: bool = False) -> None:
    cmd_npx = "npx.cmd"
    # Render to a .raw.mp4 alongside the final out so the player-fix pass can
    # produce the final file at the user-requested path.
    raw_out = out_path.with_suffix(".raw.mp4")
    cmd = [
        cmd_npx, "remotion", "render",
        comp_id, str(raw_out),
        "--concurrency", str(concurrency),
        "--log", "info",
    ]
    print(f"\n>>> {' '.join(cmd)}\n    (cwd={project_dir})\n", file=sys.stderr)
    t0 = time.monotonic()
    r = subprocess.run(cmd, cwd=str(project_dir), encoding="utf-8", errors="replace")
    elapsed = time.monotonic() - t0
    if r.returncode != 0:
        raise SystemExit(f"Remotion render failed (code {r.returncode}) after {elapsed:.1f}s")
    print(f"\nOK | remotion render | elapsed={elapsed:.1f}s | raw={raw_out}", file=sys.stderr)

    if skip_player_fix:
        shutil.move(str(raw_out), str(out_path))
        return

    t1 = time.monotonic()
    _windows_player_fix(raw_out, out_path)
    fix_elapsed = time.monotonic() - t1
    try:
        raw_out.unlink()
    except OSError as exc:
        # Cleanup-only; .raw.mp4 is regenerable on next run.
        print(f"WARN: could not delete {raw_out}: {exc}", file=sys.stderr)
    print(
        f"OK | player-fix (yuv420p+bt709) | elapsed={fix_elapsed:.1f}s | out={out_path}",
        file=sys.stderr,
    )


def main() -> int:
    p = argparse.ArgumentParser(description="Render Living PRD POC.")
    p.add_argument("--audio", default=str(DEFAULT_AUDIO))
    p.add_argument("--plan", default=str(DEFAULT_PLAN))
    p.add_argument("--words", default=str(DEFAULT_WORDS))
    p.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--comp-id", default="ProdCraftLivingPRD")
    p.add_argument("--plan-filename", default="living_prd_plan.json",
                   help="Filename under public/ where the plan JSON is staged. "
                        "Must match the file the Remotion composition fetches.")
    p.add_argument("--concurrency", type=int, default=4)
    p.add_argument("--no-render", action="store_true")
    args = p.parse_args()

    project_dir = Path(args.project_dir).resolve()
    info = stage(
        Path(args.audio).resolve(),
        Path(args.plan).resolve(),
        Path(args.words).resolve(),
        project_dir,
        plan_filename=args.plan_filename,
    )
    print(json.dumps(info, indent=2))

    if not args.no_render:
        render(project_dir, args.comp_id, Path(args.out).resolve(), args.concurrency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
