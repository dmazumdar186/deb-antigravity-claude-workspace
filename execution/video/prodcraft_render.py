"""
description: Stage Phase 1 assets into the Remotion project's public/ directory and run `npx remotion render ProdCraftPhase1` to produce the final MP4. Idempotent: overwrites prior staging, never deletes node_modules.
inputs:
    CLI:
        --audio PATH         input audio (default: .tmp/prodcraft/phase1_audio.wav)
        --beats PATH         visual_beats.json (default: .tmp/prodcraft/visual_beats.json)
        --words PATH         word timings JSON (default: .tmp/prodcraft/phase1_audio_words.json)
        --visuals-dir PATH   per-beat assets (default: .tmp/prodcraft/visuals)
        --project-dir PATH   Remotion project root (default: execution/video/remotion-projects/prodcraft_smoke)
        --out PATH           final MP4 path (default: .tmp/prodcraft/phase1_final.mp4)
        --comp-id NAME       composition id to render (default: ProdCraftPhase1)
        --concurrency N      Remotion render concurrency (default: 2)
        --no-render          stage only; don't invoke `npx remotion render`
    Env:
        (none)
outputs:
    {project_dir}/public/audio.wav
    {project_dir}/public/beats.json   beats with asset_file paths relative to public/
    {project_dir}/public/words.json   flat list of {w,start,end}
    {project_dir}/public/visuals/*.jpg|png
    {out}                              final mp4
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
DEFAULT_AUDIO = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_audio.wav"
DEFAULT_BEATS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visual_beats.json"
DEFAULT_WORDS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_audio_words.json"
DEFAULT_VISUALS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visuals"
DEFAULT_PROJECT = WORKSPACE_ROOT / "execution" / "video" / "remotion-projects" / "prodcraft_smoke"
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "phase1_final.mp4"


def stage_assets(
    audio: Path,
    beats_path: Path,
    words_path: Path,
    visuals_dir: Path,
    project_dir: Path,
) -> dict:
    public_dir = project_dir / "public"
    public_visuals = public_dir / "visuals"
    public_dir.mkdir(parents=True, exist_ok=True)
    public_visuals.mkdir(parents=True, exist_ok=True)

    if not audio.exists():
        raise SystemExit(f"Audio not found: {audio}")
    if not beats_path.exists():
        raise SystemExit(f"Beats not found: {beats_path}")
    if not words_path.exists():
        raise SystemExit(f"Words not found: {words_path}")

    # 1) Audio.
    shutil.copy2(audio, public_dir / "audio.wav")

    # 2) Per-beat visuals + beats.json rewritten with relative asset_file paths.
    beats_data = json.loads(beats_path.read_text(encoding="utf-8"))
    for b in beats_data["beats"]:
        if b["type"] == "text_card":
            b["asset_file"] = None
            continue
        asset_path = b.get("asset_path")
        if not asset_path:
            # Should be guarded by visuals fetcher; defensive fallback.
            b["asset_file"] = None
            b["type"] = "text_card"
            b["card_text"] = b.get("card_text") or b.get("text", "")[:60]
            continue
        src = Path(asset_path)
        if not src.exists():
            # Try resolving relative to visuals_dir as a backup.
            src = visuals_dir / Path(asset_path).name
        if not src.exists():
            print(f"WARN: missing asset for {b['id']}; falling back to text_card", file=sys.stderr)
            b["asset_file"] = None
            b["type"] = "text_card"
            b["card_text"] = b.get("card_text") or b.get("text", "")[:60]
            continue
        dst = public_visuals / src.name
        shutil.copy2(src, dst)
        b["asset_file"] = f"visuals/{src.name}"

    (public_dir / "beats.json").write_text(json.dumps(beats_data, indent=2), encoding="utf-8")

    # 3) words.json: flat list of {w,start,end}.
    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    words = words_data.get("words", [])
    (public_dir / "words.json").write_text(json.dumps(words), encoding="utf-8")

    return {
        "audio": str(public_dir / "audio.wav"),
        "beats_count": len(beats_data["beats"]),
        "words_count": len(words),
        "visuals_count": len(list(public_visuals.glob("*"))),
    }


def render(project_dir: Path, comp_id: str, out_path: Path, concurrency: int) -> None:
    if shutil.which("npx") is None and not (project_dir / "node_modules" / ".bin" / "remotion.cmd").exists():
        raise SystemExit(
            "Neither `npx` on PATH nor a local Remotion binary found. "
            f"Run `npm install` inside {project_dir} first."
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Remotion CLI: `npx remotion render <serve-url|entry> <comp-id> <out-path>`
    # When run from the project dir, it auto-resolves src/index.ts as the entry.
    cmd_npx = "npx.cmd" if (Path("C:/") / "Windows").exists() else "npx"
    cmd = [
        cmd_npx,
        "remotion", "render",
        comp_id,
        str(out_path),
        "--concurrency", str(concurrency),
        "--log", "verbose",
    ]
    print(f"\n>>> {' '.join(cmd)}\n    (cwd={project_dir})\n", file=sys.stderr)
    t0 = time.monotonic()
    result = subprocess.run(
        cmd,
        cwd=str(project_dir),
        encoding="utf-8",
        errors="replace",
    )
    elapsed = time.monotonic() - t0
    if result.returncode != 0:
        raise SystemExit(f"Remotion render failed (code {result.returncode}) after {elapsed:.1f}s")
    print(f"\nOK | render | {comp_id} | elapsed={elapsed:.1f}s | out={out_path}", file=sys.stderr)


def main() -> int:
    p = argparse.ArgumentParser(description="Stage assets + render ProdCraft Phase 1 MP4.")
    p.add_argument("--audio", default=str(DEFAULT_AUDIO))
    p.add_argument("--beats", default=str(DEFAULT_BEATS))
    p.add_argument("--words", default=str(DEFAULT_WORDS))
    p.add_argument("--visuals-dir", default=str(DEFAULT_VISUALS))
    p.add_argument("--project-dir", default=str(DEFAULT_PROJECT))
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--comp-id", default="ProdCraftPhase1")
    p.add_argument("--concurrency", type=int, default=2)
    p.add_argument("--no-render", action="store_true", help="Stage only; skip render")
    args = p.parse_args()

    project_dir = Path(args.project_dir).resolve()
    info = stage_assets(
        Path(args.audio).resolve(),
        Path(args.beats).resolve(),
        Path(args.words).resolve(),
        Path(args.visuals_dir).resolve(),
        project_dir,
    )
    print(json.dumps(info, indent=2))

    if not args.no_render:
        render(project_dir, args.comp_id, Path(args.out).resolve(), args.concurrency)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
