"""
description: TTS wrapper for the ProdCraft pipeline. OpenAI tts-1 by default; voice + model configurable. Tracks monthly char-count to KV file (per plan §Cost circuit-breakers — 220k char/mo hard-stop).
inputs:
    CLI:
        --text "..."              direct text input (stdin if omitted)
        --in PATH                 read text from file (e.g. .tmp/prodcraft/scripts/foo.md — frontmatter stripped)
        --out PATH                output mp3 path (required)
        --voice NAME              alloy|echo|fable|onyx|nova|shimmer (default onyx)
        --model NAME              tts-1 (default, fast) | tts-1-hd (higher quality, 2x cost)
        --first-n-words N         truncate to first N words (for 30s tests; default: no truncation)
        --dry-run                 don't call API; write silence wav; bump counter as 0
    Env:
        OPENAI_API_KEY            required
outputs:
    {out}                         mp3 file
    .tmp/prodcraft/tts_counter.json   monthly char-count tracker
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
COUNTER_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "tts_counter.json"

MONTHLY_HARD_STOP_CHARS = 220_000  # per plan cost circuit-breaker

PRICE_PER_M_CHARS = {"tts-1": 15.0, "tts-1-hd": 30.0}  # USD


def _strip_frontmatter(text: str) -> str:
    """Strip YAML frontmatter (--- ... ---) from a markdown file."""
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _first_n_words(text: str, n: int) -> str:
    words = text.split()
    return " ".join(words[:n])


def _load_counter() -> dict:
    if not COUNTER_PATH.exists():
        return {"month": "", "chars": 0, "calls": 0}
    try:
        return json.loads(COUNTER_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # Treat corruption as fresh start; log it.
        print(f"WARN: tts_counter.json corrupt; resetting", file=sys.stderr)
        return {"month": "", "chars": 0, "calls": 0}


def _save_counter(counter: dict) -> None:
    COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    tmp = COUNTER_PATH.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(counter, indent=2), encoding="utf-8")
    os.replace(tmp, COUNTER_PATH)


def _bump_counter(n_chars: int) -> dict:
    counter = _load_counter()
    cur_month = datetime.now(timezone.utc).strftime("%Y-%m")
    if counter.get("month") != cur_month:
        counter = {"month": cur_month, "chars": 0, "calls": 0}
    counter["chars"] += n_chars
    counter["calls"] += 1
    _save_counter(counter)
    return counter


def _check_circuit_breaker(n_chars: int) -> None:
    counter = _load_counter()
    cur_month = datetime.now(timezone.utc).strftime("%Y-%m")
    projected = (counter.get("chars", 0) if counter.get("month") == cur_month else 0) + n_chars
    if projected > MONTHLY_HARD_STOP_CHARS:
        raise SystemExit(
            f"Monthly char-count circuit-breaker tripped: "
            f"projected {projected:,} > limit {MONTHLY_HARD_STOP_CHARS:,}. "
            f"Refusing TTS call. Adjust hard-stop or wait for month reset."
        )


def _write_silence_wav(path: Path, n_chars: int) -> None:
    """Write a tiny silence WAV (per plan dry-run mode). Stub for Modal retries."""
    import struct
    # 1 second of silence at 8kHz mono: 8000 frames of 0
    sample_rate = 8000
    n_samples = sample_rate
    data = b"\x00\x00" * n_samples
    # WAV header
    header = b"RIFF" + struct.pack("<I", 36 + len(data)) + b"WAVE"
    header += b"fmt " + struct.pack("<IHHIIHH", 16, 1, 1, sample_rate, sample_rate * 2, 2, 16)
    header += b"data" + struct.pack("<I", len(data))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(header + data)
    print(f"DRY-RUN: silence stub written to {path} ({n_chars} chars would have been billed)", file=sys.stderr)


def synthesize(text: str, out_path: Path, voice: str = "onyx", model: str = "tts-1", dry_run: bool = False) -> dict:
    """Synthesize text to mp3 at out_path. Returns {chars, cost_usd, voice, model, dry_run}."""
    text = text.strip()
    if not text:
        raise SystemExit("Empty text — nothing to synthesize.")
    n_chars = len(text)

    if dry_run:
        # Dry-runs bypass the circuit-breaker — the whole point is to test the pipeline
        # plumbing on Modal retries without billing constraints. Counter not bumped either.
        _write_silence_wav(out_path.with_suffix(".wav"), n_chars)
        _bump_counter(0)
        return {"chars": n_chars, "cost_usd": 0.0, "voice": voice, "model": model, "dry_run": True}

    # Real-call path: gate fires before any API hit.
    _check_circuit_breaker(n_chars)

    try:
        from openai import OpenAI
    except ImportError as e:
        raise SystemExit("Run: py -m pip install openai") from e

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise SystemExit("OPENAI_API_KEY missing in .env")

    client = OpenAI(api_key=api_key)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    # Use streaming response to write directly to disk — lower memory + handles long inputs.
    with client.audio.speech.with_streaming_response.create(
        model=model,
        voice=voice,
        input=text,
        response_format="mp3",
    ) as response:
        response.stream_to_file(str(out_path))

    counter = _bump_counter(n_chars)
    cost = (n_chars / 1_000_000) * PRICE_PER_M_CHARS.get(model, 15.0)
    print(
        f"OK | tts | voice={voice} | model={model} | chars={n_chars} | cost=${cost:.4f} | "
        f"month_total={counter['chars']:,} chars ({counter['calls']} calls) | out={out_path}",
        file=sys.stderr,
    )
    return {"chars": n_chars, "cost_usd": cost, "voice": voice, "model": model, "dry_run": False,
            "month_chars": counter["chars"], "month_calls": counter["calls"]}


def main() -> int:
    p = argparse.ArgumentParser(description="ProdCraft TTS (OpenAI tts-1, with monthly char circuit-breaker)")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="Direct text input")
    src.add_argument("--in", dest="in_path", help="Read text from file (markdown frontmatter auto-stripped)")
    p.add_argument("--out", required=True, help="Output mp3 path")
    p.add_argument("--voice", default="onyx", choices=["alloy", "echo", "fable", "onyx", "nova", "shimmer"])
    p.add_argument("--model", default="tts-1", choices=["tts-1", "tts-1-hd"])
    p.add_argument("--first-n-words", type=int, default=0, help="Truncate to first N words (0 = no truncate)")
    p.add_argument("--dry-run", action="store_true", help="Stub silence WAV; don't call API")
    args = p.parse_args()

    if args.text:
        text = args.text
    elif args.in_path:
        text = _strip_frontmatter(Path(args.in_path).read_text(encoding="utf-8"))
    else:
        text = sys.stdin.read()

    if args.first_n_words > 0:
        text = _first_n_words(text, args.first_n_words)

    synthesize(text, Path(args.out), voice=args.voice, model=args.model, dry_run=args.dry_run)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
