"""
description: End-to-end ProdCraft autopilot orchestrator. Takes a topic, runs script_gen → voice_clone (gemini) → transcribe → living_prd_plan_gen → render_living_prd → thumbnail → queue add. Outputs a ready-for-review video in the pending queue.
inputs:
    CLI:
        --topic "..."          topic prompt (required)
        --slug NAME            output slug (default: derived from topic)
        --language LANG        en | fr (default: en) — drives voice + style prompt
        --gemini-voice NAME    default: Orus (EN) or Aoede (FR)
        --target-duration N    seconds (default: 180)
        --skip RENDERING       comma list of phases to skip (script,audio,transcribe,plan,render,thumbnail,queue)
        --provider NAME        gemini (default, free Flash) | personal (GLM 5.2 via OR) | client (Sonnet 4.6 via Anthropic). LLM steps only — TTS stays on Gemini.
        --dry-run              show what would run; don't execute
    env: GEMINI_API_KEY (always — TTS); OPENROUTER_API_KEY (--provider personal); ANTHROPIC_API_KEY (--provider client)
outputs:
    .tmp/prodcraft/scripts/<slug>.md
    .tmp/prodcraft/runs/<slug>/audio.wav
    .tmp/prodcraft/runs/<slug>/words.json
    .tmp/prodcraft/runs/<slug>/plan.json
    .tmp/prodcraft/runs/<slug>/final.mp4
    .tmp/prodcraft/runs/<slug>/thumb.png
    .tmp/prodcraft/queue/pending/<slug>/{final.mp4,metadata.json}
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
RUNS_ROOT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "runs"
SCRIPTS_ROOT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "scripts"

DEFAULT_VOICE = {"en": "Orus", "fr": "Aoede"}
DEFAULT_STYLE = {
    "en": "Read this in a warm, conversational tone, like explaining to a curious learner. Pause naturally at punctuation and take breath between sentences.",
    "fr": "Lis ce texte sur un ton chaleureux et conversationnel, comme si tu expliquais à un apprenant curieux. Marque des pauses naturelles à la ponctuation et reprends ton souffle entre les phrases.",
}

PHASES = ("script", "audio", "transcribe", "plan", "render", "thumbnail", "queue")


def _slug_from_topic(topic: str) -> str:
    s = re.sub(r"[^a-zA-Z0-9 -]", "", topic.lower())
    s = re.sub(r"\s+", "-", s.strip())
    s = re.sub(r"-+", "-", s).strip("-")
    return s[:55] or "untitled"


def _run(cmd: list[str], desc: str) -> None:
    print(f"\n>>> [{desc}] {' '.join(str(c) for c in cmd)}\n", file=sys.stderr, flush=True)
    r = subprocess.run(cmd, cwd=str(WORKSPACE_ROOT), encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"[{desc}] failed with exit {r.returncode}")


def _ensure_voice_assets(language: str) -> None:
    profile = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_profile.json"
    if not profile.exists():
        raise SystemExit(
            f"Voice profile missing: {profile}. Run `py execution/personal_workflows/prodcraft_voice_profile.py --build` first."
        )


def orchestrate(args: argparse.Namespace) -> dict:
    skip = set(s.strip() for s in (args.skip or "").split(",") if s.strip())
    for s in skip:
        if s not in PHASES:
            raise SystemExit(f"Unknown skip phase: {s} (valid: {PHASES})")

    slug = args.slug or _slug_from_topic(args.topic)
    language = args.language
    voice = args.gemini_voice or DEFAULT_VOICE[language]
    style = DEFAULT_STYLE[language]

    run_dir = RUNS_ROOT / slug
    run_dir.mkdir(parents=True, exist_ok=True)
    SCRIPTS_ROOT.mkdir(parents=True, exist_ok=True)

    script_path = SCRIPTS_ROOT / f"{slug}.md"
    audio_path = run_dir / "audio.wav"
    words_path = run_dir / "words.json"
    plan_path = run_dir / "plan.json"
    final_mp4 = run_dir / "final.mp4"
    thumb_path = run_dir / "thumb.png"

    py = sys.executable

    if args.dry_run:
        return {"dry_run": True, "slug": slug, "voice": voice, "language": language, "skip": sorted(skip)}

    _ensure_voice_assets(language)

    if "script" not in skip:
        _run(
            [
                py,
                "execution/personal_workflows/prodcraft_script_gen.py",
                "--topic", args.topic,
                "--length-sec", str(args.target_duration),
                "--language", language,
                "--provider", args.provider,
                "--out", str(script_path),
            ],
            "script_gen",
        )

    if "audio" not in skip:
        _run(
            [
                py,
                "execution/personal_workflows/prodcraft_voice_clone.py",
                "--in", str(script_path),
                "--backend", "gemini",
                "--gemini-voice", voice,
                "--gemini-style", style,
                "--out", str(audio_path),
            ],
            "voice_clone",
        )

    if "transcribe" not in skip:
        _run(
            [
                py,
                "execution/personal_workflows/prodcraft_transcribe.py",
                "--audio", str(audio_path),
                "--out", str(words_path),
                "--model", "small.en" if language == "en" else "small",
                "--lang", language,
            ],
            "transcribe",
        )

    if "plan" not in skip:
        _run(
            [
                py,
                "execution/video/prodcraft_living_prd_plan_gen.py",
                "--script", str(script_path),
                "--words", str(words_path),
                "--topic", args.topic,
                "--provider", args.provider,
                "--out", str(plan_path),
            ],
            "plan_gen",
        )

    if "render" not in skip:
        _run(
            [
                py,
                "execution/video/prodcraft_render_living_prd.py",
                "--audio", str(audio_path),
                "--plan", str(plan_path),
                "--words", str(words_path),
                "--out", str(final_mp4),
            ],
            "render",
        )

    # Read title from script frontmatter
    title = args.topic
    if script_path.exists():
        head = script_path.read_text(encoding="utf-8")[:1024]
        m = re.search(r"^title:\s*(.+)$", head, re.MULTILINE)
        if m:
            title = m.group(1).strip()

    if "thumbnail" not in skip:
        _run(
            [
                py,
                "execution/image_generation/prodcraft_thumbnail.py",
                "--title", title,
                "--subtitle", args.topic,
                "--out", str(thumb_path),
            ],
            "thumbnail",
        )

    if "queue" not in skip:
        description = (
            f"{args.topic}\n\nSubscribe for weekly Product Manager Foundations content.\n\n@ProdCraft"
            if language == "en"
            else f"{args.topic}\n\nAbonne-toi pour du contenu Product Manager hebdomadaire.\n\n@ProdCraft"
        )
        tags = "product management,product manager,PM,PRD,how to" if language == "en" else "product management,product manager,PM"
        _run(
            [
                py,
                "execution/personal_workflows/prodcraft_queue.py",
                "add",
                "--slug", slug,
                "--mp4", str(final_mp4),
                "--title", title,
                "--description", description,
                "--tags", tags,
                "--language", language,
                "--privacy", "private",
            ],
            "queue_add",
        )

    return {
        "ok": True,
        "slug": slug,
        "language": language,
        "voice": voice,
        "script": str(script_path),
        "audio": str(audio_path),
        "words": str(words_path),
        "plan": str(plan_path),
        "final_mp4": str(final_mp4),
        "thumbnail": str(thumb_path),
    }


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft end-to-end orchestrator.")
    p.add_argument("--topic", required=True)
    p.add_argument("--slug", default=None)
    p.add_argument("--language", default="en", choices=("en", "fr"))
    p.add_argument("--gemini-voice", default=None)
    p.add_argument("--target-duration", type=int, default=180)
    p.add_argument("--skip", default="")
    p.add_argument("--provider", default="gemini", choices=("gemini", "personal", "client"),
                   help="LLM provider for script_gen + plan_gen. gemini=Flash free; personal=GLM 5.2 via OR; client=Sonnet 4.6 via Anthropic. TTS stays on Gemini.")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    result = orchestrate(args)
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
