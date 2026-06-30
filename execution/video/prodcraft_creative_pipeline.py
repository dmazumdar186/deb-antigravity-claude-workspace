"""
description: End-to-end ProdCraft creative pipeline with internal critique-reroll loop.
             1. Generates a beat-decomposed creative plan via GLM 5.2.
             2. Renders sample stills per scene.
             3. Runs the Gemini-vision critic on the stills + plan + narration.
             4. Re-rolls any scene where the critic returned REVISE, injecting the
                critic's surgical fix notes into the scene-author prompt.
             5. Re-renders stills, re-critiques.
             6. Loops until PASS or --max-iterations reached.
             7. Finally renders the full MP4 from the converged plan.
inputs:
    CLI:
        --script PATH           script.md
        --words PATH            words.json
        --audio PATH            audio.wav
        --topic "..."           topic line
        --out-dir PATH          working dir for plan + stills + critique + MP4
        --num-scenes N          (default 5)
        --max-iterations N      critique-reroll iterations cap (default 3)
        --no-render-final       skip the final full-MP4 render (debug)
        --provider NAME         personal | client (default personal -- GLM 5.2)
    env: OPENROUTER_API_KEY (personal), GEMINI_API_KEY (critic), ANTHROPIC_API_KEY (client)
outputs:
    {out_dir}/creative_plan.json
    {out_dir}/critique_iterN.json (one per iteration)
    {out_dir}/stills/crit_<scene>_<frame>.png
    {out_dir}/final_creative_v2.mp4
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
REMOTION_PROJ = WORKSPACE_ROOT / "execution" / "video" / "remotion-projects" / "prodcraft_smoke"


def _run_py(cmd: list[str], desc: str) -> None:
    print(f"\n>>> [{desc}] {' '.join(str(c) for c in cmd)}\n", file=sys.stderr, flush=True)
    r = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"[{desc}] failed with exit {r.returncode}")


def _frames_for_scene(scene: dict, fps: int = 30) -> list[int]:
    """Pick 1-3 stills per scene: one near the middle, one near the end of the
    first beat (concept-introduction moment), and one near the end of the scene
    (concept-completed moment). Avoid frame 0 of the scene (transition state)."""
    start_f = int(scene["start_t"] * fps) + 5
    end_f = int(scene["end_t"] * fps) - 5
    dur = end_f - start_f
    if dur <= 0:
        return [start_f]
    if scene.get("beats"):
        first_beat_end = scene["beats"][0]["phrase_end_t"]
        mid_f = int(first_beat_end * fps)
    else:
        mid_f = start_f + dur // 3
    last_f = start_f + int(dur * 0.85)
    # De-dup and clamp.
    frames = sorted({start_f + dur // 2, mid_f, last_f})
    frames = [max(start_f, min(end_f, f)) for f in frames]
    return frames


def render_stills(plan: dict, stills_dir: Path) -> None:
    stills_dir.mkdir(parents=True, exist_ok=True)
    # Stage assets so the Remotion bundle can fetch the latest plan.
    public = REMOTION_PROJ / "public"
    public.mkdir(parents=True, exist_ok=True)
    (public / "creative_plan.json").write_text(json.dumps(plan, indent=2), encoding="utf-8")

    print(f"\n>>> [render-stills] {len(plan['scenes'])} scenes", file=sys.stderr, flush=True)
    for s in plan["scenes"]:
        for frame in _frames_for_scene(s):
            out = stills_dir / f"crit_{s['id']}_{frame:05d}.png"
            cmd = [
                "npx.cmd", "remotion", "still", "ProdCraftCreative",
                str(out.resolve()), f"--frame={frame}", "--log=error",
            ]
            print(f"    still scene={s['id']} frame={frame}", file=sys.stderr, flush=True)
            r = subprocess.run(cmd, cwd=str(REMOTION_PROJ), encoding="utf-8", errors="replace")
            if r.returncode != 0:
                print(f"    WARN: still render failed (scene={s['id']} frame={frame})", file=sys.stderr)


def render_final_mp4(plan_path: Path, audio_path: Path, words_path: Path, out_mp4: Path) -> None:
    cmd = [
        sys.executable, "execution/video/prodcraft_render_living_prd.py",
        "--audio", str(audio_path),
        "--plan", str(plan_path),
        "--words", str(words_path),
        "--plan-filename", "creative_plan.json",
        "--comp-id", "ProdCraftCreative",
        "--out", str(out_mp4),
        "--concurrency", "4",
    ]
    _run_py(cmd, "render-final-mp4")


def run_critic(plan_path: Path, script_path: Path, words_path: Path, stills_dir: Path, out_path: Path) -> dict | None:
    """Run the critic. Returns the critique dict, or None if the critic itself failed
    (e.g. Gemini 503'd through all retries). Callers should treat None as "skip this
    iteration's critique" rather than crashing the whole pipeline."""
    cmd = [
        sys.executable, "execution/video/prodcraft_creative_critic.py",
        "--plan", str(plan_path),
        "--script", str(script_path),
        "--words", str(words_path),
        "--stills-dir", str(stills_dir),
        "--out", str(out_path),
    ]
    print(f"\n>>> [critic] {' '.join(str(c) for c in cmd)}\n", file=sys.stderr, flush=True)
    r = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"WARN: critic failed (exit {r.returncode}). Will skip critique for this iteration.", file=sys.stderr)
        return None
    return json.loads(out_path.read_text(encoding="utf-8"))


def reroll_scene(plan_path: Path, words_path: Path, scene_id: str, notes: str, provider: str) -> bool:
    """Run one scene reroll. Returns True if it succeeded; False if the reroll
    exhausted its retries (e.g. typography or invisibility validators kept
    failing). On failure the existing scene in the plan is preserved as-is so
    the rest of the iteration can continue."""
    cmd = [
        sys.executable, "execution/video/prodcraft_creative_plan_gen.py",
        "--words", str(words_path),
        "--out", str(plan_path),
        "--provider", provider,
        "--reroll", scene_id,
        "--reroll-notes", notes,
    ]
    print(f"\n>>> [reroll[{scene_id}]] {' '.join(str(c) for c in cmd)}\n", file=sys.stderr, flush=True)
    r = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"WARN: reroll[{scene_id}] failed (exit {r.returncode}). Keeping prior scene; iteration continues.", file=sys.stderr)
        return False
    return True


def main() -> int:
    p = argparse.ArgumentParser(description="End-to-end ProdCraft creative pipeline w/ critique loop.")
    p.add_argument("--script", required=True)
    p.add_argument("--words", required=True)
    p.add_argument("--audio", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--out-dir", required=True)
    p.add_argument("--num-scenes", type=int, default=5)
    p.add_argument("--max-iterations", type=int, default=3)
    p.add_argument("--no-render-final", action="store_true")
    p.add_argument("--provider", default="personal", choices=("personal", "client"))
    p.add_argument("--resume", action="store_true",
                   help="If plan.json exists at --out-dir, skip iteration 0 and resume the critique loop.")
    args = p.parse_args()

    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    stills_dir = out_dir / "stills"
    plan_path = out_dir / "creative_plan.json"

    # Initial generation (skipped if --resume + plan_path already exists).
    t0 = time.monotonic()
    if args.resume and plan_path.exists():
        print(f"\n=== ITERATION 0: SKIPPED (resuming from existing plan at {plan_path}) ===", file=sys.stderr)
    else:
        print(f"\n=== ITERATION 0: initial creative plan generation ===", file=sys.stderr)
        _run_py(
            [
                sys.executable, "execution/video/prodcraft_creative_plan_gen.py",
                "--script", args.script,
                "--words", args.words,
                "--topic", args.topic,
                "--out", str(plan_path),
                "--num-scenes", str(args.num_scenes),
                "--provider", args.provider,
            ],
            "creative-plan-gen",
        )

    # Iterate critique -> reroll until PASS or budget exhausted.
    final_verdict = "REVISE"
    for it in range(1, args.max_iterations + 1):
        print(f"\n=== ITERATION {it}: render stills + critique ===", file=sys.stderr)
        # Clear old stills so the critic only sees the latest.
        for old in stills_dir.glob("crit_*.png"):
            old.unlink()
        plan = json.loads(plan_path.read_text(encoding="utf-8"))
        render_stills(plan, stills_dir)

        critique_path = out_dir / f"critique_iter{it}.json"
        critique = run_critic(plan_path, Path(args.script), Path(args.words), stills_dir, critique_path)
        if critique is None:
            # Critic was unavailable for this iteration -- ship the plan as-is.
            print(f"\n=== ITERATION {it}: critic unavailable, exiting loop and shipping current plan ===", file=sys.stderr)
            final_verdict = "UNKNOWN"
            break
        final_verdict = critique["verdict"]

        revise_scenes = [s for s in critique["scenes"] if s["verdict"] == "REVISE"]
        print(f"\n=== ITERATION {it} verdict: {final_verdict} ({len(revise_scenes)} scenes to reroll) ===", file=sys.stderr)
        for s in critique["scenes"]:
            mark = "OK " if s["verdict"] == "PASS" else "RV "
            print(
                f"  {mark} {s['id']:35s} art={s.get('score_artistic',0)}/10 tech={s.get('score_technical',0)}/10",
                file=sys.stderr,
            )

        if final_verdict == "PASS":
            print(f"\nPASS in {it} iteration(s). Total elapsed: {time.monotonic() - t0:.1f}s", file=sys.stderr)
            break

        if it == args.max_iterations:
            print(
                f"\nMax iterations ({args.max_iterations}) hit; shipping best-available plan with verdict={final_verdict}.",
                file=sys.stderr,
            )
            break

        for s in revise_scenes:
            reroll_scene(plan_path, Path(args.words), s["id"], s["fixes"], args.provider)

    # Final MP4 render.
    if not args.no_render_final:
        final_mp4 = out_dir / "final_creative_v2.mp4"
        print(f"\n=== FINAL RENDER -> {final_mp4} ===", file=sys.stderr)
        render_final_mp4(plan_path, Path(args.audio), Path(args.words), final_mp4)

    summary = {
        "ok": True,
        "verdict": final_verdict,
        "iterations_used": min(it, args.max_iterations) if 'it' in locals() else 0,
        "plan": str(plan_path),
        "out_dir": str(out_dir),
        "final_mp4": str(out_dir / "final_creative_v2.mp4") if not args.no_render_final else None,
        "elapsed_sec": time.monotonic() - t0,
    }
    print(json.dumps(summary, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:  # noqa: BLE001
        pass
    sys.exit(main())
