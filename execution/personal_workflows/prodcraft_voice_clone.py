"""
description: F5-TTS voice clone via the public mrfakename/E2-F5-TTS HuggingFace Space. Free path (no Replicate billing); rate-limited by the Space's queue. Uses .tmp/prodcraft/voice_sample/ as the reference (created by prodcraft_voice_sample.py).
inputs:
    CLI:
        --text "..."             direct text to synthesize (stdin if omitted)
        --in PATH                read text from file (markdown frontmatter auto-stripped)
        --out PATH               output wav path (required)
        --sample-dir PATH        reference dir containing voice_sample.wav + voice_sample.txt
                                 (default: .tmp/prodcraft/voice_sample)
        --first-n-words N        truncate input text to first N words (for short tests; default: no truncation)
        --remove-silence         pass remove_silence=True to F5-TTS (default: False)
        --speed FLOAT            playback speed multiplier [0.5-2.0]; <1 slows, pitch preserved
        --space NAME             HF Space to call (default: mrfakename/E2-F5-TTS)
        --chunk-by MODE          none (default; single call) | paragraph (split on blank lines; one F5 call per paragraph, silence padded between)
        --pause-ms N             inter-chunk silence in ms when chunk-by != none (default: 700)
    Env:
        HF_API_TOKEN             optional; used for higher queue priority on HF Spaces
outputs:
    {out}                        WAV file (24kHz mono PCM after concat + speed)
    {out}.json                   sidecar metadata: chars, reference video, chunk count, timing
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SAMPLE_DIR = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_sample"
DEFAULT_SPACE = "mrfakename/E2-F5-TTS"


def _strip_frontmatter(text: str) -> str:
    if not text.startswith("---"):
        return text
    end = text.find("\n---", 3)
    if end == -1:
        return text
    return text[end + 4 :].lstrip()


def _first_n_words(text: str, n: int) -> str:
    return " ".join(text.split()[:n])


def _get_ffmpeg_bin() -> str:
    """Bundled ffmpeg via imageio_ffmpeg — avoids PATH dependency on Windows."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise SystemExit("Run: py -m pip install imageio-ffmpeg") from e


def _apply_speed(src: Path, dst: Path, speed: float) -> None:
    """Slow/speed audio without changing pitch using ffmpeg atempo.

    atempo's per-filter range is [0.5, 2.0]; outside that, chain multiple
    instances. For our use case (0.5 ≤ speed ≤ 2.0) a single filter is enough.
    """
    if not (0.5 <= speed <= 2.0):
        raise SystemExit(f"--speed must be in [0.5, 2.0]; got {speed}")
    ffmpeg = _get_ffmpeg_bin()
    cmd = [
        ffmpeg, "-y",
        "-i", str(src),
        "-filter:a", f"atempo={speed:.3f}",
        "-ac", "1",
        "-ar", "24000",
        "-acodec", "pcm_s16le",
        str(dst),
    ]
    result = subprocess.run(
        cmd,
        capture_output=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise SystemExit(f"ffmpeg atempo failed (code {result.returncode}):\n{result.stderr[-1500:]}")


def _split_paragraphs(text: str) -> list[str]:
    """Split on one-or-more blank lines. Skip markdown headers and empty chunks."""
    import re
    chunks: list[str] = []
    for raw in re.split(r"\n\s*\n", text):
        t = raw.strip()
        if not t:
            continue
        if t.startswith("#"):
            continue
        t = re.sub(r"\s+", " ", t).strip()
        if t:
            chunks.append(t)
    return chunks


def _split_sentences(text: str) -> list[str]:
    """Split text into sentences for F5-TTS. Each sentence becomes one API call.

    Strategy: first strip markdown/frontmatter via paragraph split, then within each
    paragraph split on . ! ? followed by whitespace. Preserves the terminating
    punctuation (F5-TTS needs it for natural prosody). Merges sentences shorter than
    25 chars with the next one to avoid micro-chunks.
    """
    import re
    sentences: list[str] = []
    for para in _split_paragraphs(text):
        # Split keeping the terminator.
        raw_parts = re.split(r"(?<=[.!?])\s+", para)
        buf = ""
        for part in raw_parts:
            part = part.strip()
            if not part:
                continue
            if buf:
                buf = f"{buf} {part}"
            else:
                buf = part
            if len(buf) >= 25:
                sentences.append(buf)
                buf = ""
        if buf:
            # Append any trailing short fragment to the previous sentence to avoid micro-chunks.
            if sentences:
                sentences[-1] = f"{sentences[-1]} {buf}"
            else:
                sentences.append(buf)
    return sentences


def _read_wav_pcm(path: Path) -> tuple[bytes, int, int, int]:
    """Read a WAV file, return (samples_bytes, n_channels, sample_width, sample_rate)."""
    import wave
    with wave.open(str(path), "rb") as w:
        nch = w.getnchannels()
        sw = w.getsampwidth()
        sr = w.getframerate()
        samples = w.readframes(w.getnframes())
    return samples, nch, sw, sr


def _concat_wavs_with_silence(chunk_paths: list[Path], pause_ms: int, out_path: Path) -> None:
    """Concatenate WAVs with `pause_ms` of silence between them. All inputs must share format."""
    import wave
    if not chunk_paths:
        raise SystemExit("No chunks to concatenate.")

    first_samples, nch, sw, sr = _read_wav_pcm(chunk_paths[0])
    out_path.parent.mkdir(parents=True, exist_ok=True)
    silence_frames = int(sr * pause_ms / 1000)
    silence_bytes = b"\x00" * (silence_frames * nch * sw)

    with wave.open(str(out_path), "wb") as out:
        out.setnchannels(nch)
        out.setsampwidth(sw)
        out.setframerate(sr)
        out.writeframes(first_samples)
        for p in chunk_paths[1:]:
            samples, nch2, sw2, sr2 = _read_wav_pcm(p)
            if (nch2, sw2, sr2) != (nch, sw, sr):
                raise SystemExit(
                    f"Chunk format mismatch: first={nch}ch/{sw*8}b/{sr}Hz, {p.name}={nch2}ch/{sw2*8}b/{sr2}Hz"
                )
            out.writeframes(silence_bytes)
            out.writeframes(samples)


def _call_f5(client, ref_wav: Path, ref_text: str, gen_text: str, remove_silence: bool) -> Path:
    """One F5-TTS call via HF Space. Returns local result wav path."""
    from gradio_client import handle_file
    result = client.predict(
        ref_audio=handle_file(str(ref_wav)),
        ref_text=ref_text,
        gen_text=gen_text,
        remove_silence=remove_silence,
        api_name="/predict",
    )
    if isinstance(result, tuple):
        result_path = result[0]
    elif isinstance(result, dict) and "path" in result:
        result_path = result["path"]
    else:
        result_path = result
    if not result_path or not Path(result_path).exists():
        raise SystemExit(f"F5-TTS Space returned unexpected result shape: {result!r}")
    return Path(result_path)


def _call_f5_modal(modal_cls, ref_wav: Path, ref_text: str, gen_text: str, remove_silence: bool) -> Path:
    """One F5-TTS call via the Modal deployment. Writes returned bytes to a temp wav and returns the path."""
    import tempfile
    instance = modal_cls()
    wav_bytes = instance.synthesize.remote(
        ref_audio_bytes=ref_wav.read_bytes(),
        ref_text=ref_text,
        gen_text=gen_text,
        remove_silence=remove_silence,
    )
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    tmp.write(wav_bytes)
    tmp.close()
    return Path(tmp.name)


def _load_reference(sample_dir: Path) -> tuple[Path, str, dict]:
    wav = sample_dir / "voice_sample.wav"
    txt = sample_dir / "voice_sample.txt"
    meta_path = sample_dir / "voice_sample.json"
    if not wav.exists():
        raise SystemExit(
            f"Reference audio missing: {wav}. "
            f"Run: py execution/personal_workflows/prodcraft_voice_sample.py"
        )
    if not txt.exists():
        raise SystemExit(f"Reference transcript missing: {txt}")
    ref_text = txt.read_text(encoding="utf-8").strip()
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    return wav, ref_text, meta


def clone(
    gen_text: str,
    out_path: Path,
    sample_dir: Path = DEFAULT_SAMPLE_DIR,
    space: str = DEFAULT_SPACE,
    remove_silence: bool = False,
    speed: float = 1.0,
    chunk_by: str = "none",
    pause_ms: int = 700,
    backend: str = "hf",
    modal_app: str = "prodcraft-f5-tts",
) -> dict:
    gen_text = gen_text.strip()
    if not gen_text:
        raise SystemExit("Empty text — nothing to synthesize.")

    ref_wav, ref_text, ref_meta = _load_reference(sample_dir)

    if chunk_by == "paragraph":
        chunks = _split_paragraphs(gen_text)
    elif chunk_by == "sentence":
        chunks = _split_sentences(gen_text)
    elif chunk_by == "none":
        chunks = [gen_text]
    else:
        raise SystemExit(f"Unknown --chunk-by mode: {chunk_by!r}")

    if not chunks:
        raise SystemExit("Chunking produced 0 chunks.")

    # Backend dispatch: connect once, reuse per-chunk.
    if backend == "hf":
        try:
            from gradio_client import Client
        except ImportError as e:
            raise SystemExit("Run: py -m pip install gradio_client") from e
        token = os.environ.get("HF_API_TOKEN") or None
        print(f"Connecting to HF Space: {space}...", file=sys.stderr)
        hf_client = Client(space, token=token, verbose=False)
        modal_cls = None
    elif backend == "modal":
        try:
            import modal as _modal
        except ImportError as e:
            raise SystemExit("Run: py -m pip install modal") from e
        print(f"Resolving Modal class on app={modal_app}...", file=sys.stderr)
        modal_cls = _modal.Cls.from_name(modal_app, "F5TTSModal")
        hf_client = None
    elif backend == "chatterbox":
        try:
            import modal as _modal
        except ImportError as e:
            raise SystemExit("Run: py -m pip install modal") from e
        # Default to chatterbox app name; the --modal-app flag overrides when needed.
        app_name = modal_app if modal_app != "prodcraft-f5-tts" else "prodcraft-chatterbox-tts"
        print(f"Resolving Modal class on app={app_name}...", file=sys.stderr)
        modal_cls = _modal.Cls.from_name(app_name, "ChatterboxModal")
        hf_client = None
    else:
        raise SystemExit(f"Unknown --backend: {backend!r} (expected hf|modal|chatterbox)")

    t0 = time.monotonic()
    chunk_paths: list[Path] = []
    for i, chunk in enumerate(chunks):
        print(
            f"  [{i+1}/{len(chunks)}] {backend} | gen={len(chunk)} chars | "
            f"remove_silence={remove_silence}",
            file=sys.stderr,
        )
        if backend == "hf":
            result_path = _call_f5(hf_client, ref_wav, ref_text, chunk, remove_silence)
        else:
            result_path = _call_f5_modal(modal_cls, ref_wav, ref_text, chunk, remove_silence)
        chunk_paths.append(result_path)

    api_elapsed = time.monotonic() - t0

    # Concatenate chunks (or pass through if single chunk), then apply speed.
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if len(chunk_paths) == 1 and abs(speed - 1.0) < 1e-3:
        shutil.copy2(chunk_paths[0], out_path)
    elif len(chunk_paths) == 1:
        _apply_speed(chunk_paths[0], out_path, speed)
    else:
        # Multi-chunk path: concat into a tmp wav, then atempo (or copy) to out_path.
        concat_tmp = out_path.with_suffix(".concat.wav")
        _concat_wavs_with_silence(chunk_paths, pause_ms, concat_tmp)
        if abs(speed - 1.0) < 1e-3:
            shutil.move(str(concat_tmp), str(out_path))
        else:
            _apply_speed(concat_tmp, out_path, speed)
            try:
                concat_tmp.unlink()
            except OSError as exc:
                # Cleanup-only; .concat.wav is regenerable on next run.
                print(f"WARN: could not delete {concat_tmp}: {exc}", file=sys.stderr)

    out_resolved = out_path.resolve()
    try:
        out_rel = str(out_resolved.relative_to(WORKSPACE_ROOT)).replace("\\", "/")
    except ValueError:
        out_rel = str(out_resolved).replace("\\", "/")

    meta = {
        "space": space,
        "model": "F5-TTS",
        "reference_video_id": ref_meta.get("video_id"),
        "reference_video_title": ref_meta.get("title"),
        "reference_duration_sec": ref_meta.get("duration_sec"),
        "gen_chars": len(gen_text),
        "chunk_count": len(chunks),
        "chunk_by": chunk_by,
        "pause_ms": pause_ms if len(chunks) > 1 else 0,
        "out_path": out_rel,
        "api_elapsed_sec": round(api_elapsed, 2),
        "remove_silence": remove_silence,
        "speed": speed,
    }
    sidecar = out_path.with_suffix(out_path.suffix + ".json")
    sidecar.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    print(
        f"OK | voice_clone | space={space} | chunks={len(chunks)} | "
        f"api_elapsed={api_elapsed:.1f}s | chars={len(gen_text)} | speed={speed} | out={out_path}",
        file=sys.stderr,
    )
    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="F5-TTS voice clone via HF Space (free path).")
    src = p.add_mutually_exclusive_group()
    src.add_argument("--text", help="Direct text input")
    src.add_argument("--in", dest="in_path", help="Read text from file (markdown frontmatter auto-stripped)")
    p.add_argument("--out", required=True, help="Output WAV path")
    p.add_argument("--sample-dir", default=str(DEFAULT_SAMPLE_DIR), help="Reference voice sample directory")
    p.add_argument("--first-n-words", type=int, default=0, help="Truncate to first N words (0 = no truncate)")
    p.add_argument("--remove-silence", action="store_true", help="Ask F5-TTS to remove silence in output")
    p.add_argument("--speed", type=float, default=1.0, help="Playback speed multiplier [0.5-2.0]; <1 slows, pitch preserved")
    p.add_argument("--space", default=DEFAULT_SPACE, help=f"HF Space (default: {DEFAULT_SPACE})")
    p.add_argument("--chunk-by", choices=["none", "paragraph", "sentence"], default="none",
                   help="paragraph = one F5 call per blank-line-separated paragraph; sentence = one F5 call per . ! ? (smallest chunks, most resilient to F5 long-context drift)")
    p.add_argument("--pause-ms", type=int, default=700, help="Inter-chunk silence (ms) when chunk-by != none")
    p.add_argument("--backend", choices=["hf", "modal", "chatterbox"], default="hf",
                   help="hf = public F5 HF Space; modal = F5 on Modal; chatterbox = ChatterboxTTS on Modal (better long-form)")
    p.add_argument("--modal-app", default="prodcraft-f5-tts",
                   help="Modal app name (default: prodcraft-f5-tts; chatterbox auto-routes to prodcraft-chatterbox-tts)")
    args = p.parse_args()

    if args.text:
        text = args.text
    elif args.in_path:
        text = _strip_frontmatter(Path(args.in_path).read_text(encoding="utf-8"))
    else:
        text = sys.stdin.read()

    if args.first_n_words > 0:
        text = _first_n_words(text, args.first_n_words)

    meta = clone(
        text,
        Path(args.out),
        sample_dir=Path(args.sample_dir),
        space=args.space,
        remove_silence=args.remove_silence,
        speed=args.speed,
        chunk_by=args.chunk_by,
        pause_ms=args.pause_ms,
        backend=args.backend,
        modal_app=args.modal_app,
    )
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
