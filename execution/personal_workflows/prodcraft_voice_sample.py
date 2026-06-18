"""
description: Extract a clean 6-30s voice sample + matching transcript from a ProdCraft YouTube video for F5-TTS voice cloning. Downloads audio + auto-vtt via yt-dlp, picks a continuous-speech window from the middle of the video (skips intro/outro), trims with ffmpeg to 24kHz mono WAV.
inputs:
    CLI:
        --video-id ID          YouTube ID (default: R_pFOlfiW5s, the Product Metrics video)
        --out-dir PATH         output dir (default: .tmp/prodcraft/voice_sample)
        --duration SECONDS     target sample length, clamped to [6, 30] (default: 15)
        --skip-edges SECONDS   skip first/last N seconds when picking window (default: 30)
        --keep-audio           keep the full m4a download (default: delete after trim)
    Env:
        (none required; public YouTube)
outputs:
    {out_dir}/voice_sample.wav     24kHz mono WAV, F5-TTS-ready
    {out_dir}/voice_sample.txt     matching transcript text for that window
    {out_dir}/voice_sample.json    metadata (video_id, start, end, duration, source title)
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
DEFAULT_OUT_DIR = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "voice_sample"
YTDLP_CACHE_DIR = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "ytdlp_cache"

VTT_TS_RE = re.compile(
    r"(\d{2}):(\d{2}):(\d{2})\.(\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})\.(\d{3})"
)


def _ts_to_seconds(h: str, m: str, s: str, ms: str) -> float:
    return int(h) * 3600 + int(m) * 60 + int(s) + int(ms) / 1000.0


def _seconds_to_ffmpeg_ts(sec: float) -> str:
    h = int(sec // 3600)
    m = int((sec % 3600) // 60)
    s = sec - h * 3600 - m * 60
    return f"{h:02d}:{m:02d}:{s:06.3f}"


def _get_ffmpeg_bin() -> str:
    """Use imageio_ffmpeg's bundled ffmpeg — avoids PATH dependency on Windows."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError as e:
        raise SystemExit("Run: py -m pip install imageio-ffmpeg") from e


def _download_audio_and_vtt(video_id: str, work_dir: Path) -> tuple[Path, Path, str]:
    """Use yt-dlp to fetch m4a audio + auto-generated English VTT. Returns (audio_path, vtt_path, title)."""
    try:
        import yt_dlp
    except ImportError as e:
        raise SystemExit("Run: py -m pip install yt-dlp") from e

    work_dir.mkdir(parents=True, exist_ok=True)
    url = f"https://www.youtube.com/watch?v={video_id}"
    out_template = str(work_dir / f"{video_id}.%(ext)s")

    ydl_opts = {
        "format": "bestaudio[ext=m4a]/bestaudio",
        "outtmpl": out_template,
        "writeautomaticsub": True,
        "writesubtitles": True,
        "subtitleslangs": ["en", "en-US", "en-GB"],
        "subtitlesformat": "vtt",
        "skip_download": False,
        "quiet": True,
        "no_warnings": True,
        "cachedir": str(YTDLP_CACHE_DIR),
    }

    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=True)
        title = info.get("title", "")

    # Find what got written.
    audio_candidates = sorted(work_dir.glob(f"{video_id}.*"))
    audio_path = None
    vtt_path = None
    for p in audio_candidates:
        if p.suffix.lower() in (".m4a", ".webm", ".opus", ".mp3"):
            audio_path = p
        elif p.suffix.lower() == ".vtt":
            vtt_path = p
    if audio_path is None:
        raise SystemExit(f"yt-dlp did not produce an audio file for {video_id}. Found: {[p.name for p in audio_candidates]}")
    if vtt_path is None:
        raise SystemExit(f"yt-dlp did not produce a VTT subtitle file for {video_id}. Found: {[p.name for p in audio_candidates]}")
    return audio_path, vtt_path, title


def _parse_vtt(vtt_path: Path) -> list[tuple[float, float, str]]:
    """Parse a VTT file into [(start_sec, end_sec, text), ...].

    YouTube auto-captions use a rolling-caption format where each cue has two
    lines: line 1 holds the previously-finalized text (carryover) and line 2
    holds the *new* spoken content with inline word-timing tags. To get the
    actual transcript without duplication, we take only the LAST non-empty
    line of each cue, strip word-timing tags, and dedupe consecutive identical
    entries (which removes YouTube's 0.01s "stable" phantom cues).
    """
    raw = vtt_path.read_text(encoding="utf-8", errors="replace")
    lines = raw.splitlines()
    cues: list[tuple[float, float, str]] = []
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = VTT_TS_RE.search(line)
        if m:
            start = _ts_to_seconds(*m.group(1, 2, 3, 4))
            end = _ts_to_seconds(*m.group(5, 6, 7, 8))
            i += 1
            text_lines: list[str] = []
            while i < len(lines) and lines[i].strip():
                text_lines.append(lines[i])
                i += 1
            if not text_lines:
                continue
            # Take only the last non-empty line — that holds the new content.
            text = text_lines[-1]
            text = re.sub(r"<\d{2}:\d{2}:\d{2}\.\d{3}>", "", text)
            text = re.sub(r"</?c[^>]*>", "", text)
            text = re.sub(r"\s+", " ", text).strip()
            if text:
                cues.append((start, end, text))
        i += 1

    # Drop consecutive duplicate-text cues (kills YT's phantom 0.01s stable cues).
    deduped: list[tuple[float, float, str]] = []
    for cue in cues:
        if deduped and deduped[-1][2] == cue[2]:
            # Same text as prior; extend the prior cue's end time instead.
            ps, _, pt = deduped[-1]
            deduped[-1] = (ps, cue[1], pt)
            continue
        deduped.append(cue)
    return deduped


def _pick_window(
    cues: list[tuple[float, float, str]],
    target_sec: float,
    skip_edges: float,
) -> tuple[float, float, str]:
    """Pick a continuous-speech window of ~target_sec, starting at a cue boundary, skipping the first/last skip_edges seconds."""
    if not cues:
        raise SystemExit("No usable cues parsed from VTT.")

    total_end = cues[-1][1]
    min_start = skip_edges
    max_start = max(total_end - skip_edges - target_sec, skip_edges + 1.0)

    best: tuple[float, float, str] | None = None
    best_score = -1.0
    for idx, (s, _, _) in enumerate(cues):
        if s < min_start or s > max_start:
            continue
        # Build the window from this cue forward until duration >= target_sec.
        window_text_parts: list[str] = []
        window_end = s
        for s2, e2, t2 in cues[idx:]:
            if s2 - s > target_sec:
                break
            window_text_parts.append(t2)
            window_end = e2
            if window_end - s >= target_sec:
                break
        actual_dur = window_end - s
        text = " ".join(window_text_parts).strip()
        if actual_dur < 6.0 or actual_dur > 30.0:
            continue
        # Score: prefer text density (chars per second) — penalize silence/short clips.
        density = len(text) / actual_dur
        # Also weakly prefer windows nearer the middle of the video.
        mid = total_end / 2.0
        center_bonus = 1.0 - abs((s + actual_dur / 2.0) - mid) / mid
        score = density + 5.0 * center_bonus
        if score > best_score:
            best_score = score
            best = (s, window_end, text)

    if best is None:
        raise SystemExit(
            f"Could not find a {target_sec}s continuous-speech window with skip-edges={skip_edges}s. "
            f"Video duration ~{total_end:.1f}s; try lowering --skip-edges or --duration."
        )
    return best


def _ffmpeg_trim(src: Path, dst: Path, start_sec: float, end_sec: float) -> None:
    ffmpeg = _get_ffmpeg_bin()
    dst.parent.mkdir(parents=True, exist_ok=True)
    duration = end_sec - start_sec
    cmd = [
        ffmpeg,
        "-y",
        "-ss", _seconds_to_ffmpeg_ts(start_sec),
        "-t", f"{duration:.3f}",
        "-i", str(src),
        "-ac", "1",          # mono
        "-ar", "24000",      # 24kHz, F5-TTS reference rate
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
        raise SystemExit(f"ffmpeg failed (code {result.returncode}):\n{result.stderr[-1500:]}")


def extract(video_id: str, out_dir: Path, target_sec: float, skip_edges: float, keep_audio: bool) -> dict:
    work_dir = YTDLP_CACHE_DIR / video_id
    audio_path, vtt_path, title = _download_audio_and_vtt(video_id, work_dir)
    cues = _parse_vtt(vtt_path)
    start_sec, end_sec, text = _pick_window(cues, target_sec, skip_edges)

    out_dir.mkdir(parents=True, exist_ok=True)
    wav_path = out_dir / "voice_sample.wav"
    txt_path = out_dir / "voice_sample.txt"
    meta_path = out_dir / "voice_sample.json"

    _ffmpeg_trim(audio_path, wav_path, start_sec, end_sec)
    txt_path.write_text(text, encoding="utf-8")

    meta = {
        "video_id": video_id,
        "title": title,
        "start_sec": round(start_sec, 3),
        "end_sec": round(end_sec, 3),
        "duration_sec": round(end_sec - start_sec, 3),
        "transcript": text,
        "source_audio": str(audio_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "source_vtt": str(vtt_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "out_wav": str(wav_path.relative_to(WORKSPACE_ROOT)).replace("\\", "/"),
        "format": "24kHz mono PCM s16le",
    }
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    if not keep_audio:
        try:
            audio_path.unlink()
        except OSError as exc:
            # Safe to ignore: cleanup-only; the cache dir is regenerable.
            print(f"WARN: could not delete cached audio {audio_path}: {exc}", file=sys.stderr)

    return meta


def main() -> int:
    p = argparse.ArgumentParser(description="Extract a 6-30s voice sample + transcript for F5-TTS voice cloning.")
    p.add_argument("--video-id", default="R_pFOlfiW5s", help="YouTube ID (default: Product Metrics video)")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT_DIR), help="Output directory")
    p.add_argument("--duration", type=float, default=15.0, help="Target sample length in seconds [6-30]")
    p.add_argument("--skip-edges", type=float, default=30.0, help="Skip first/last N seconds when picking window")
    p.add_argument("--keep-audio", action="store_true", help="Keep the full m4a download instead of deleting after trim")
    args = p.parse_args()

    if not (6.0 <= args.duration <= 30.0):
        raise SystemExit("--duration must be between 6 and 30 seconds (F5-TTS reference range)")

    out_dir = Path(args.out_dir)
    meta = extract(args.video_id, out_dir, args.duration, args.skip_edges, args.keep_audio)
    print(json.dumps(meta, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
