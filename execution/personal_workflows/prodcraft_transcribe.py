"""
description: Word-level transcription using faster-whisper. Produces a JSON of (word, start_sec, end_sec) tuples that drives visual-beat timing for ProdCraft Phase 1.
inputs:
    CLI:
        --audio PATH        input audio (wav/mp3/m4a/flac/ogg)
        --out PATH          output JSON path (default: same dir as --audio, suffix _words.json)
        --model NAME        faster-whisper model (default: base.en — small + fast on CPU)
                            Options: tiny.en, base.en, small.en, medium.en, large-v3, distil-large-v3
        --lang CODE         language hint (default: en); use "auto" to detect
        --compute-type X    int8 (default, CPU) | float16 (GPU) | float32
    Env:
        (none required; model auto-downloads to ~/.cache/huggingface/hub)
outputs:
    {out}                   {
                              "audio": "...wav",
                              "duration_sec": float,
                              "language": "en",
                              "words": [{"w": "Hello", "start": 0.12, "end": 0.34}, ...],
                              "segments": [{"start": ..., "end": ..., "text": "..."}, ...]
                            }
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]


def transcribe(
    audio: Path,
    out_path: Path,
    model_name: str = "base.en",
    language: str = "en",
    compute_type: str = "int8",
) -> dict:
    if not audio.exists():
        raise SystemExit(f"Audio not found: {audio}")

    try:
        from faster_whisper import WhisperModel
    except ImportError as e:
        raise SystemExit("Run: py -m pip install faster-whisper") from e

    print(f"Loading faster-whisper model={model_name} compute={compute_type}...", file=sys.stderr)
    t0 = time.monotonic()
    model = WhisperModel(model_name, device="cpu", compute_type=compute_type)
    print(f"Model loaded in {time.monotonic() - t0:.1f}s. Transcribing {audio.name}...", file=sys.stderr)

    t1 = time.monotonic()
    lang_arg = None if language == "auto" else language
    segments_iter, info = model.transcribe(
        str(audio),
        language=lang_arg,
        word_timestamps=True,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 300},
    )

    words_out: list[dict] = []
    segments_out: list[dict] = []
    for seg in segments_iter:
        segments_out.append({
            "start": round(seg.start, 3),
            "end": round(seg.end, 3),
            "text": seg.text.strip(),
        })
        if seg.words:
            for w in seg.words:
                words_out.append({
                    "w": w.word.strip(),
                    "start": round(w.start, 3),
                    "end": round(w.end, 3),
                })

    elapsed = time.monotonic() - t1

    out = {
        "audio": str(audio.resolve()).replace("\\", "/"),
        "duration_sec": round(info.duration, 3),
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "model": model_name,
        "compute_type": compute_type,
        "word_count": len(words_out),
        "segment_count": len(segments_out),
        "transcribe_elapsed_sec": round(elapsed, 2),
        "words": words_out,
        "segments": segments_out,
    }

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(
        f"OK | transcribe | {audio.name} | {info.duration:.1f}s audio | "
        f"{len(words_out)} words | {elapsed:.1f}s | out={out_path}",
        file=sys.stderr,
    )
    return out


def main() -> int:
    p = argparse.ArgumentParser(description="Word-level transcription via faster-whisper.")
    p.add_argument("--audio", required=True, help="Input audio file")
    p.add_argument("--out", help="Output JSON path (default: <audio>_words.json)")
    p.add_argument("--model", default="base.en",
                   help="faster-whisper model: tiny.en|base.en|small.en|medium.en|large-v3|distil-large-v3")
    p.add_argument("--lang", default="en", help="Language code or 'auto'")
    p.add_argument("--compute-type", default="int8", choices=["int8", "float16", "float32"])
    args = p.parse_args()

    audio = Path(args.audio).resolve()
    out_path = Path(args.out) if args.out else audio.with_name(audio.stem + "_words.json")

    transcribe(audio, out_path, args.model, args.lang, args.compute_type)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
