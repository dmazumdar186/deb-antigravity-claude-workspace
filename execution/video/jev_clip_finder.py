"""Find the best short-form clips in a long video/podcast transcript with Jev.

description: Windows a timestamped transcript into candidate clips (--window/--stride seconds,
             extended to sentence boundaries), asks Jev ONE call per candidate (hook, value,
             self-contained, clip type), computes a weighted composite in code, drops
             overlapping windows (>=50% overlap, keep higher score) and writes the top N.
             Directive: directives/video/jev_clip_finder.md
inputs: --transcript path (.srt, .vtt, .json [{start,end,text}] seconds, or plain text with
        [mm:ss] / [hh:mm:ss] timestamps) OR --youtube URL (yt-dlp auto-subs into .tmp/);
        --window 30 --stride 15 --min-words 20 --top 10 --weights 0.4,0.4,0.2 --workers 8
        --limit --dry-run. env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / _TOEKN).
outputs: --output JSON (default <input>.clips.json) of top clips; optional --md shortlist and
         --csv-out; summary on stdout; ledger row in .tmp/jev_ledger.jsonl
         (caller "jev_clip_finder"). Exit 2 on input/download failure.
"""
from __future__ import annotations

import argparse
import csv
import glob
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402

HOOK_LEVELS = ["no hook", "mildly interesting opening", "curious opening that invites listening",
               "stops the scroll in the first sentence"]
VALUE_LEVELS = ["filler, small talk or logistics", "some information but generic",
                "useful specific point", "insight, story or strong claim people would share"]
CLIP_TYPES = {
    "story": "a personal anecdote or narrative with a beginning and payoff",
    "hot_take": "a bold, contrarian or opinionated claim",
    "how_to": "concrete steps or advice the viewer can apply",
    "stat_or_proof": "a number, result or evidence that proves a point",
    "joke": "humour, a funny moment or banter",
    "qa": "a crisp question and answer exchange",
    "none": "none of these; filler or transition",
}
QUESTIONS = {
    "hook": jev_client.score("How strong is the opening line of this clip as a hook for a short video?", HOOK_LEVELS),
    "self_contained": jev_client.noul(
        "Would this clip make sense to a viewer who has not seen the rest of the video?",
        "makes sense on its own without surrounding context",
        "depends on prior context (unclear references, mid-thought)"),
    "value": jev_client.score("How valuable or shareable is the content of this clip?", VALUE_LEVELS),
    "clip_type": jev_client.choice("What kind of short-form clip is this?", CLIP_TYPES),
}
_SENT_END = re.compile(r"[.!?][\"')\]]*\s*$")


# ---- parsing -----------------------------------------------------------------------------

def _ts(s: str) -> float:
    s = s.strip().replace(",", ".")
    parts = [float(p) for p in s.split(":")]
    total = 0.0
    for p in parts:
        total = total * 60 + p
    return total


def _clean(text: str) -> str:
    text = re.sub(r"<[^>]+>", "", text)
    return re.sub(r"\s+", " ", text).strip()


_CUE = re.compile(r"((?:\d+:)?\d+:\d+[.,]\d+)\s*-->\s*((?:\d+:)?\d+:\d+[.,]\d+)")


def parse_cues(raw: str) -> list[dict[str, Any]]:
    """SRT and WebVTT share the `a --> b` cue shape."""
    segs: list[dict[str, Any]] = []
    for block in re.split(r"\n\s*\n", raw.replace("\r\n", "\n")):
        lines = block.strip().split("\n")
        for i, line in enumerate(lines):
            m = _CUE.search(line)
            if m:
                text = _clean(" ".join(lines[i + 1:]))
                if text:
                    segs.append({"start": _ts(m.group(1)), "end": _ts(m.group(2)), "text": text})
                break
    # VTT auto-subs repeat rolling lines; drop exact consecutive duplicates.
    out: list[dict[str, Any]] = []
    for s in segs:
        if out and out[-1]["text"] == s["text"]:
            out[-1]["end"] = s["end"]
            continue
        out.append(s)
    return out


def parse_json(raw: str) -> list[dict[str, Any]]:
    data = json.loads(raw)
    if isinstance(data, dict):
        data = data.get("segments") or []
    return [{"start": float(d["start"]), "end": float(d.get("end", d["start"])), "text": _clean(str(d["text"]))}
            for d in data if str(d.get("text", "")).strip()]


_PLAIN = re.compile(r"\[((?:\d+:)?\d+:\d+)\]")


def parse_plain(raw: str) -> list[dict[str, Any]]:
    parts = _PLAIN.split(raw)
    segs = []
    for i in range(1, len(parts) - 1, 2):
        text = _clean(parts[i + 1])
        if text:
            segs.append({"start": _ts(parts[i]), "end": _ts(parts[i]), "text": text})
    for a, b in zip(segs, segs[1:]):
        a["end"] = b["start"]
    if segs:
        segs[-1]["end"] = segs[-1]["start"] + max(5.0, len(segs[-1]["text"].split()) / 2.5)
    return segs


def load_transcript(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    ext = path.suffix.lower()
    if ext == ".json":
        segs = parse_json(raw)
    elif ext in (".srt", ".vtt") or _CUE.search(raw):
        segs = parse_cues(raw)
    else:
        segs = parse_plain(raw)
    return sorted(segs, key=lambda s: s["start"])


def fetch_youtube(url: str, tmp: Path = _ROOT / ".tmp" / "jev_clips") -> Path:
    """Download auto-subs via yt-dlp. Raises RuntimeError with a readable message on failure."""
    exe = shutil.which("yt-dlp")
    if not exe:
        raise RuntimeError("yt-dlp not installed (pip install yt-dlp); or pass --transcript")
    tmp.mkdir(parents=True, exist_ok=True)
    cmd = [exe, "--write-auto-sub", "--write-sub", "--sub-langs", "en.*", "--sub-format", "vtt",
           "--skip-download", "-o", str(tmp / "%(id)s.%(ext)s"), url]
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=180, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"yt-dlp failed: {exc}") from exc
    files = sorted(glob.glob(str(tmp / "*.vtt")), key=lambda p: Path(p).stat().st_mtime)
    if proc.returncode != 0 or not files:
        tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-3:]
        raise RuntimeError("yt-dlp could not fetch subtitles (blocked network or no captions): "
                           + " | ".join(tail))
    return Path(files[-1])


# ---- windowing ---------------------------------------------------------------------------

def build_windows(segs: list[dict[str, Any]], window: float = 30, stride: float = 15,
                  min_words: int = 20) -> list[dict[str, Any]]:
    """Candidate clips starting every `stride` s at a segment start, ~`window` s long,
    extended (up to 1.5x window) to end on a sentence boundary when possible."""
    if not segs:
        return []
    cands: list[dict[str, Any]] = []
    seen: set[tuple[int, int]] = set()
    t, last = segs[0]["start"], segs[-1]["start"]
    while t <= last:
        i = next((k for k, s in enumerate(segs) if s["start"] >= t), None)
        if i is None:
            break
        j = i
        while j + 1 < len(segs) and segs[j + 1]["end"] - segs[i]["start"] <= window:
            j += 1
        while (not _SENT_END.search(segs[j]["text"]) and j + 1 < len(segs)
               and segs[j + 1]["end"] - segs[i]["start"] <= window * 1.5):
            j += 1
        if (i, j) not in seen:
            seen.add((i, j))
            text = " ".join(s["text"] for s in segs[i:j + 1])
            if len(text.split()) >= min_words:
                cands.append({"start": segs[i]["start"], "end": segs[j]["end"], "text": text})
        t += stride
    return cands


# ---- scoring -----------------------------------------------------------------------------

def parse_weights(spec: str) -> tuple[float, float, float]:
    parts = [float(x) for x in spec.split(",")]
    if len(parts) != 3 or any(p < 0 for p in parts) or sum(parts) <= 0:
        raise ValueError("--weights needs three non-negative numbers: hook,value,self_contained")
    total = sum(parts)
    return parts[0] / total, parts[1] / total, parts[2] / total


def composite(hook: float, value: float, self_contained: float,
              weights: tuple[float, float, float] = (0.4, 0.4, 0.2)) -> float:
    """hook/value are 0..3 score indices, self_contained 0..1; result 0..1."""
    h = min(max(hook / (len(HOOK_LEVELS) - 1), 0.0), 1.0)
    v = min(max(value / (len(VALUE_LEVELS) - 1), 0.0), 1.0)
    s = min(max(self_contained, 0.0), 1.0)
    w = weights
    return round((w[0] * h + w[1] * v + w[2] * s) / sum(w), 4)


def overlap_frac(a: dict[str, Any], b: dict[str, Any]) -> float:
    inter = min(a["end"], b["end"]) - max(a["start"], b["start"])
    shorter = min(a["end"] - a["start"], b["end"] - b["start"])
    return max(inter, 0.0) / shorter if shorter > 0 else 0.0


def dedupe(clips: list[dict[str, Any]], max_overlap: float = 0.5) -> list[dict[str, Any]]:
    kept: list[dict[str, Any]] = []
    for c in sorted(clips, key=lambda c: c["score"], reverse=True):
        if all(overlap_frac(c, k) < max_overlap for k in kept):
            kept.append(c)
    return kept


def score_candidates(cands: list[dict[str, Any]], weights: tuple[float, float, float],
                     workers: int = 8) -> list[dict[str, Any]]:
    states = [{"task": "rate this transcript excerpt as a standalone short-form video clip",
               "clip": c["text"][:4000]} for c in cands]
    results = jev_client.decide_many(states, QUESTIONS, workers=workers)
    out = []
    for c, r in zip(cands, results):
        hook, value, sc = r.score("hook"), r.score("value"), r.noul("self_contained")
        out.append({**c, "hook": hook, "value": value, "self_contained": sc,
                    "clip_type": r.choice("clip_type", "none") or "none",
                    "score": 0.0 if r.error else composite(hook, value, sc, weights),
                    "cost_usd": r.cost_usd, "error": r.error})
    return out


# ---- outputs -----------------------------------------------------------------------------

def mmss(t: float) -> str:
    t = int(round(t))
    return f"{t // 3600}:{t % 3600 // 60:02d}:{t % 60:02d}" if t >= 3600 else f"{t // 60:02d}:{t % 60:02d}"


def to_markdown(clips: list[dict[str, Any]], source: str = "") -> str:
    lines = [f"# Clip shortlist{(' — ' + source) if source else ''}", "",
             "| # | Time | Type | Score | Opening |", "|---|---|---|---|---|"]
    for n, c in enumerate(clips, 1):
        snippet = c["text"][:120].replace("|", "/")
        lines.append(f"| {n} | {mmss(c['start'])}–{mmss(c['end'])} | {c['clip_type']} | "
                     f"{c['score']:.2f} | {snippet} |")
    return "\n".join(lines) + "\n"


def write_csv(clips: list[dict[str, Any]], path: Path) -> None:
    cols = ["rank", "start", "end", "start_mmss", "end_mmss", "clip_type", "score", "hook",
            "value", "self_contained", "text"]
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for n, c in enumerate(clips, 1):
            w.writerow({**c, "rank": n, "start_mmss": mmss(c["start"]), "end_mmss": mmss(c["end"])})


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--transcript", type=Path)
    src.add_argument("--youtube")
    ap.add_argument("--window", type=float, default=30)
    ap.add_argument("--stride", type=float, default=15)
    ap.add_argument("--min-words", type=int, default=20)
    ap.add_argument("--top", type=int, default=10)
    ap.add_argument("--weights", default="0.4,0.4,0.2")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--output", type=Path)
    ap.add_argument("--md", type=Path)
    ap.add_argument("--csv-out", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)

    try:
        weights = parse_weights(a.weights)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    if a.youtube:
        try:
            path = fetch_youtube(a.youtube)
        except RuntimeError as exc:
            print(f"error: {exc}", file=sys.stderr)
            return 2
    else:
        path = a.transcript
        if not path.is_file():
            print(f"error: transcript not found: {path}", file=sys.stderr)
            return 2
    try:
        segs = load_transcript(path)
    except (ValueError, KeyError, TypeError) as exc:
        print(f"error: could not parse {path}: {exc}", file=sys.stderr)
        return 2
    cands = build_windows(segs, a.window, a.stride, a.min_words)
    if a.limit:
        cands = cands[:a.limit]
    print(f"{len(segs)} segments -> {len(cands)} candidate clips")
    if a.dry_run:
        for c in cands[:5]:
            print(f"  {mmss(c['start'])}-{mmss(c['end'])}  {c['text'][:90]}")
        return 0
    if not cands:
        print("error: no candidates (transcript too short or --min-words too high)", file=sys.stderr)
        return 2
    if not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    t0 = time.perf_counter()
    scored = score_candidates(cands, weights, a.workers)
    wall = time.perf_counter() - t0
    errors = sum(1 for c in scored if c["error"])
    cost = sum(c["cost_usd"] for c in scored)
    top = dedupe([c for c in scored if not c["error"]])[:a.top]

    out = a.output or path.with_suffix(path.suffix + ".clips.json")
    out.write_text(json.dumps({"source": str(a.youtube or path), "weights": weights,
                               "candidates": len(cands), "errors": errors, "clips": top},
                              indent=2, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(top, str(a.youtube or path.name))
    if a.md:
        a.md.write_text(md, encoding="utf-8")
    if a.csv_out:
        write_csv(top, a.csv_out)
    jev_client.append_ledger({"caller": "jev_clip_finder", "items": len(cands), "errors": errors,
                              "cost_usd": round(cost, 6), "wall_s": round(wall, 2)})
    print(f"scored {len(cands)} candidates in {wall:.1f}s, cost ${cost:.6f}, errors {errors}")
    print(md)
    print(f"wrote {out}")
    if errors == len(cands):
        first = next(c["error"] for c in scored if c["error"])
        print(f"error: every Jev call failed: {first}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
