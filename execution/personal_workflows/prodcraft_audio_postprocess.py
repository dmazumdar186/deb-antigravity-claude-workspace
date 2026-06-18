"""
description: Post-process an existing TTS WAV to add introspection pauses + adjust speed, WITHOUT calling F5-TTS again. Uses the Whisper segments JSON to find sentence boundaries (segments ending in . ! ?) and inserts silence at those points. Then applies a single ffmpeg atempo for the final speed.
inputs:
    CLI:
        --audio PATH        input wav (24kHz mono PCM) — typically .tmp/prodcraft/phase1_audio.wav
        --words PATH        words+segments JSON from prodcraft_transcribe.py
        --out PATH          output wav (required)
        --script PATH       optional: original script .md/.txt. When provided, sentence-end detection runs on the SCRIPT punctuation (aligned to Whisper word timings), which is far more accurate than Whisper-segment punctuation.
        --pause-ms N        ms of silence to inject at each sentence boundary (default: 450)
        --speed-ratio FLOAT atempo multiplier applied to the spliced wav. E.g. to go from existing 0.85x effective to 0.7x effective, pass 0.8235 (=0.7/0.85). Default: 1.0 (no change).
        --paragraph-extra-ms N additional ms inserted at every paragraph boundary (default: 350). When --script is provided, paragraphs are detected from script blank lines; otherwise every Nth sentence-end is treated as a paragraph.
        --every-nth-paragraph N treat every Nth sentence boundary as a paragraph boundary (used only when --script is NOT given; default: 5)
    Env: none
outputs:
    {out}                   wav with injected pauses + speed adjustment
    {out}.json              sidecar metadata
"""
from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import wave
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]

SENTENCE_END_CHARS = (".", "!", "?")


def _get_ffmpeg() -> str:
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise SystemExit("Run: py -m pip install imageio-ffmpeg") from e


def _read_wav(path: Path) -> tuple[bytes, int, int, int, int]:
    """Read wav. Returns (samples, nchannels, sampwidth, sample_rate, n_frames)."""
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        nf = w.getnframes()
        samples = w.readframes(nf)
    return samples, nch, sw, sr, nf


def _bytes_per_sec(nch: int, sw: int, sr: int) -> int:
    return nch * sw * sr


def _is_sentence_end(text: str) -> bool:
    t = text.strip()
    return bool(t) and t[-1] in SENTENCE_END_CHARS


def find_pause_points(segments: list[dict], every_nth: int) -> list[tuple[float, int]]:
    """Whisper-segment punctuation path: low-recall but no script needed."""
    points: list[tuple[float, int]] = []
    sentence_count = 0
    for seg in segments:
        if _is_sentence_end(seg["text"]):
            sentence_count += 1
            extra = sentence_count if sentence_count % every_nth == 0 else 0
            points.append((float(seg["end"]), extra))
    return points


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _normalize(word: str) -> str:
    return "".join(c for c in word.lower() if c.isalnum())


def find_pause_points_from_script(script_text: str, whisper_words: list[dict]) -> list[tuple[float, int]]:
    """Align the (punctuated) script to the (timed-but-rarely-punctuated) Whisper words. For each script word ending in . ! ?, return the matched Whisper word's end-time. extra_index > 0 marks paragraph boundaries (detected from blank lines in the script).

    Alignment strategy: sequential pointer with a fuzzy skip window (Whisper may add a few artifacts like a leading "If"). For each script token, scan up to LOOK_AHEAD positions ahead in the Whisper stream for a normalized match.
    """
    LOOK_AHEAD = 6
    script = _strip_frontmatter(script_text)

    # Tokenize each paragraph separately so we can flag paragraph boundaries.
    import re
    paragraphs: list[list[str]] = []
    for raw in re.split(r"\n\s*\n", script):
        t = raw.strip()
        if not t or t.startswith("#"):
            continue
        # Normalize internal whitespace; keep punctuation.
        t = re.sub(r"\s+", " ", t).strip()
        toks = t.split(" ")
        paragraphs.append(toks)

    if not paragraphs:
        return []

    points: list[tuple[float, int]] = []
    wi = 0
    n_paragraphs = len(paragraphs)

    for p_i, para_tokens in enumerate(paragraphs):
        is_last_paragraph = (p_i == n_paragraphs - 1)
        for t_i, tok in enumerate(para_tokens):
            norm = _normalize(tok)
            if not norm:
                continue
            # Scan ahead in Whisper words for a matching normalized form.
            match_idx = -1
            for j in range(wi, min(wi + LOOK_AHEAD, len(whisper_words))):
                if _normalize(whisper_words[j]["w"]) == norm:
                    match_idx = j
                    break
            if match_idx < 0:
                # No match — skip this script token; pointer doesn't advance.
                continue
            wi = match_idx + 1
            ends_sentence = tok.rstrip().endswith(SENTENCE_END_CHARS)
            is_para_end = ends_sentence and t_i == len(para_tokens) - 1 and not is_last_paragraph
            if ends_sentence:
                end_time = float(whisper_words[match_idx]["end"])
                # extra > 0 => paragraph boundary
                points.append((end_time, p_i + 1 if is_para_end else 0))

    # Sort + de-dup near-coincident pause points (within 50ms).
    points.sort(key=lambda x: x[0])
    deduped: list[tuple[float, int]] = []
    for t, e in points:
        if deduped and abs(t - deduped[-1][0]) < 0.05:
            # Keep the one with the higher extra marker.
            if e > deduped[-1][1]:
                deduped[-1] = (t, e)
            continue
        deduped.append((t, e))
    return deduped


def splice_pauses(
    audio_path: Path,
    pause_points: list[tuple[float, int]],
    pause_ms: int,
    paragraph_extra_ms: int,
    out_tmp: Path,
) -> tuple[float, float]:
    """Insert silence into audio_path at each pause point. Writes a single wav at out_tmp. Returns (orig_duration, new_duration)."""
    samples, nch, sw, sr, nf = _read_wav(audio_path)
    orig_duration = nf / sr
    bps = _bytes_per_sec(nch, sw, sr)
    width = nch * sw  # bytes per frame

    # Compute byte offsets for each pause point.
    # IMPORTANT: pause_points are in time-of-original-audio. We sort and process in order.
    sorted_pts = sorted(pause_points, key=lambda x: x[0])
    pieces: list[bytes] = []
    last_byte = 0
    for t_sec, extra_marker in sorted_pts:
        offset = int(t_sec * sr) * width
        if offset <= last_byte:
            continue
        offset = min(offset, len(samples))
        pieces.append(samples[last_byte:offset])
        # Silence to insert at this boundary
        total_pause_ms = pause_ms + (paragraph_extra_ms if extra_marker > 0 else 0)
        sil_frames = int(sr * total_pause_ms / 1000)
        pieces.append(b"\x00" * (sil_frames * width))
        last_byte = offset
    pieces.append(samples[last_byte:])

    new_samples = b"".join(pieces)
    out_tmp.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(out_tmp), "wb") as out:
        out.setnchannels(nch)
        out.setsampwidth(sw)
        out.setframerate(sr)
        out.writeframes(new_samples)

    new_duration = len(new_samples) / bps
    return orig_duration, new_duration


def apply_speed(src: Path, dst: Path, ratio: float) -> None:
    ffmpeg = _get_ffmpeg()
    if not (0.5 <= ratio <= 2.0):
        raise SystemExit(f"--speed-ratio must be in [0.5, 2.0]; got {ratio}")
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-filter:a", f"atempo={ratio:.4f}",
        "-ac", "1",
        "-ar", "24000",
        "-acodec", "pcm_s16le",
        str(dst),
    ]
    r = subprocess.run(cmd, capture_output=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise SystemExit(f"ffmpeg atempo failed (code {r.returncode}):\n{r.stderr[-1500:]}")


def postprocess(
    audio: Path,
    words_json: Path,
    out_path: Path,
    pause_ms: int,
    speed_ratio: float,
    paragraph_extra_ms: int,
    every_nth: int,
    script_path: Path | None = None,
) -> dict:
    if not audio.exists():
        raise SystemExit(f"Audio not found: {audio}")
    if not words_json.exists():
        raise SystemExit(f"Words JSON not found: {words_json}")
    data = json.loads(words_json.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    words = data.get("words", [])
    if not segments:
        raise SystemExit(f"No segments in {words_json}.")

    if script_path is not None:
        if not script_path.exists():
            raise SystemExit(f"Script not found: {script_path}")
        script_text = script_path.read_text(encoding="utf-8")
        pause_points = find_pause_points_from_script(script_text, words)
    else:
        pause_points = find_pause_points(segments, every_nth)
    print(
        f"Found {len(pause_points)} sentence boundaries; "
        f"{sum(1 for _,e in pause_points if e > 0)} treated as paragraph breaks (every {every_nth}th)",
        file=sys.stderr,
    )

    spliced_tmp = out_path.with_suffix(".spliced.wav")
    orig_dur, new_dur = splice_pauses(audio, pause_points, pause_ms, paragraph_extra_ms, spliced_tmp)
    print(f"Spliced audio: {orig_dur:.2f}s -> {new_dur:.2f}s (added {new_dur-orig_dur:.2f}s of pauses)", file=sys.stderr)

    if abs(speed_ratio - 1.0) < 1e-3:
        shutil.move(str(spliced_tmp), str(out_path))
        final_dur = new_dur
    else:
        apply_speed(spliced_tmp, out_path, speed_ratio)
        try:
            spliced_tmp.unlink()
        except OSError as exc:
            print(f"WARN: could not delete {spliced_tmp}: {exc}", file=sys.stderr)
        final_dur = new_dur / speed_ratio

    meta = {
        "input_audio": str(audio.resolve()).replace("\\", "/"),
        "orig_duration_sec": round(orig_dur, 3),
        "spliced_duration_sec": round(new_dur, 3),
        "final_duration_sec": round(final_dur, 3),
        "pause_ms_per_sentence": pause_ms,
        "paragraph_extra_ms": paragraph_extra_ms,
        "every_nth_paragraph": every_nth,
        "speed_ratio": speed_ratio,
        "sentence_breaks": len(pause_points),
        "paragraph_breaks": sum(1 for _, e in pause_points if e > 0),
        "out": str(out_path.resolve()).replace("\\", "/"),
    }
    sidecar = out_path.with_suffix(out_path.suffix + ".json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(
        f"OK | postprocess | {orig_dur:.1f}s -> {final_dur:.1f}s | "
        f"pauses={len(pause_points)} | speed_ratio={speed_ratio} | out={out_path}",
        file=sys.stderr,
    )
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Inject pauses + adjust speed on a TTS WAV.")
    p.add_argument("--audio", required=True)
    p.add_argument("--words", required=True)
    p.add_argument("--out", required=True)
    p.add_argument("--script", help="Original script .md/.txt for accurate sentence detection (recommended)")
    p.add_argument("--pause-ms", type=int, default=450)
    p.add_argument("--speed-ratio", type=float, default=1.0)
    p.add_argument("--paragraph-extra-ms", type=int, default=350)
    p.add_argument("--every-nth-paragraph", type=int, default=5)
    args = p.parse_args()

    postprocess(
        Path(args.audio).resolve(),
        Path(args.words).resolve(),
        Path(args.out).resolve(),
        args.pause_ms,
        args.speed_ratio,
        args.paragraph_extra_ms,
        args.every_nth_paragraph,
        Path(args.script).resolve() if args.script else None,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
