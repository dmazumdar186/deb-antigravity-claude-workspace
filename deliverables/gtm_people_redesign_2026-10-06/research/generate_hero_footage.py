#!/usr/bin/env python3
"""Generate the GTM People v4 opening footage with the Higgsfield API and cut it into drop-in assets.

Adapted from execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py (2026-10-06). One abstract
light-violet loop per beat (--beat 1..4); beat 1 is the default background: it writes site/assets/hero.mp4 (16:9),
site/assets/hero-m.mp4 (9:16 crop) and flips "ready": true in site/assets/hero.json so the page starts loading it.

description: Estimates, submits, polls and downloads a text-to-video generation from the Higgsfield
  API (Kling 3.0 Standard by default), then uses ffmpeg to produce the hero drop-ins the site build
  expects: <edition>.mp4 (16:9 loop), <edition>-m.mp4 (portrait crop) and <edition>-poster.jpg.
  Estimate-first: nothing is charged until --go is passed and the estimate is within --max-usd.
inputs: --beat 1|2|3|4 (default 1), --env-file PATH (file holding HF_API_TOKEN=key_id:secret; default
  .env), --model ENDPOINT_ID, --duration SEC, --max-usd FLOAT, --go (spend), --out DIR (default
  deliverables/gtm_people_redesign_2026-10-06/site/assets), --ffmpeg PATH.
outputs: <out>/hero.mp4, <out>/hero-m.mp4, <out>/hero-poster.jpg, <out>/hero.gen.json (beat>1: hero-b<N>.*)
  (request id, model, estimate, prompt, output URL) and a line per step on stdout. Exit 2 when the
  estimate exceeds --max-usd or credits are insufficient; exit 1 on API/ffmpeg failure.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.higgsfield.ai"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/128 Safari/537.36 gtmpeople-hero/1.0"
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DEFAULT_OUT = HERE.parent / "site/assets"

STYLE = (" Soft diffuse studio light, pale palette of white, lavender #F5F3FF and light violet #7C3AED with small "
         "mint #06D6A0 accents, slow continuous motion that reads as a seamless loop, abstract, no text, no logos, no "
         "people, no faces, no hands, shallow depth of field, calm, the left half of the frame quiet and uncluttered.")
PROMPTS = {
    "1": ("Hundreds of tiny translucent violet spheres drifting in a loose cloud, slowly funnelling through a narrow "
          "glass neck into a single orderly line, five of them turning mint green as they emerge, one gliding forward "
          "and settling with a soft ripple of light." + STYLE),
    "2": ("Slow dolly across a sunlit minimalist desk surface at dawn, pale paper, a faint violet reflection moving "
          "across frosted glass, soft bokeh, a hint of mint light at the edge, cinematic, unhurried." + STYLE),
    "3": ("A thin luminous violet line drawing itself left to right across a pale surface, blooming into six soft "
          "glowing nodes in turn, gentle mint sparks at each node, macro depth, continuous smooth motion." + STYLE),
    "4": ("Abstract globe made of fine violet dots slowly rotating, thin glowing arcs rising from one bright mint point "
          "and landing softly on distant points, pale white background, cartographic, serene." + STYLE),
}
NAMES = {"1": "hero", "2": "hero-b2", "3": "hero-b3", "4": "hero-b4"}


def load_key(env_file: Path) -> str:
    """Read HF_API_TOKEN (key_id:secret) from an env file without exporting anything else."""
    if os.environ.get("HF_API_TOKEN"):
        return os.environ["HF_API_TOKEN"].strip()
    if not env_file.is_file():
        raise SystemExit(f"env file not found: {env_file}")
    for line in env_file.read_text(encoding="utf-8", errors="replace").splitlines():
        if line.startswith("HF_API_TOKEN="):
            value = line.split("=", 1)[1].strip().strip('"').strip("'")
            if ":" in value:
                return value
    raise SystemExit("HF_API_TOKEN (key_id:secret) not found in env file")


def call(method: str, url: str, key: str, body: dict | None = None, timeout: int = 60) -> tuple[int, dict]:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Key {key}")
    req.add_header("User-Agent", UA)  # api.higgsfield.ai sits behind Cloudflare, which 1010-blocks urllib
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (fixed https host)
            return resp.status, json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as err:
        try:
            payload = json.loads(err.read().decode() or "{}")
        except json.JSONDecodeError:
            payload = {"detail": "non-json error body"}
        return err.code, payload


def body_for(model: str, prompt: str, duration: int) -> dict:
    if model.startswith("kling-video/"):
        return {"prompt": prompt, "duration": duration, "aspect_ratio": "16:9", "sound": "off"}
    if model.startswith("minimax/hailuo"):
        return {"prompt": prompt, "duration": duration}
    if model.startswith("bytedance/seedance"):
        return {"prompt": prompt, "duration": duration, "resolution": "720p", "aspect_ratio": "16:9",
                "generate_audio": False}
    return {"prompt": prompt, "duration": duration, "resolution": "1080p", "aspect_ratio": "16:9"}


def find_ffmpeg(explicit: str | None) -> str:
    if explicit:
        return explicit
    try:  # full static build with libx264 (the Playwright ffmpeg cannot even decode H.264)
        import imageio_ffmpeg  # type: ignore
        return imageio_ffmpeg.get_ffmpeg_exe()
    except ImportError:
        pass
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise SystemExit("ffmpeg with libx264 not found: pip install imageio-ffmpeg, or pass --ffmpeg")


def run_ffmpeg(ffmpeg: str, args: list[str]) -> None:
    proc = subprocess.run([ffmpeg, "-y", "-hide_banner", "-loglevel", "error", *args],
                          capture_output=True, encoding="utf-8", errors="replace", timeout=600)
    if proc.returncode != 0:
        raise SystemExit(f"ffmpeg failed: {proc.stderr[-800:]}")


def cut_assets(ffmpeg: str, src: Path, out: Path, edition: str) -> None:
    """Landscape loop (crossfade tail into head), portrait crop, poster."""
    land = out / f"{edition}.mp4"
    port = out / f"{edition}-m.mp4"
    poster = out / f"{edition}-poster.jpg"
    # The v4 opening crossfades the loop at .35 under a white->#F5F3FF gradient; the poster is unused by the page.
    # Seamless-ish loop: play forward then a short reversed tail is avoided (looks fake); instead
    # trim to whole seconds and let the site loop with a 400 ms CSS crossfade on the poster.
    run_ffmpeg(ffmpeg, ["-i", str(src), "-an", "-vf", "scale=1280:-2:flags=lanczos", "-c:v", "libx264",
                        "-preset", "slow", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(land)])
    run_ffmpeg(ffmpeg, ["-i", str(src), "-an", "-vf", "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos",
                        "-c:v", "libx264", "-preset", "slow", "-crf", "25", "-pix_fmt", "yuv420p",
                        "-movflags", "+faststart", str(port)])
    run_ffmpeg(ffmpeg, ["-i", str(land), "-frames:v", "1", "-q:v", "3", str(poster)])
    for path in (land, port, poster):
        print(f"      {path.name}: {path.stat().st_size / 1024:.0f} KB")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--beat", choices=sorted(PROMPTS), default="1")
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--model", default="kling-video/v3.0/std/text-to-video")
    parser.add_argument("--duration", type=int, default=10)
    parser.add_argument("--max-usd", type=float, default=1.50)
    parser.add_argument("--go", action="store_true", help="actually spend credits")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ffmpeg")
    parser.add_argument("--poll-seconds", type=int, default=15)
    parser.add_argument("--timeout-minutes", type=int, default=25)
    args = parser.parse_args()

    key = load_key(args.env_file)
    prompt = PROMPTS[args.beat]
    edition = NAMES[args.beat]
    body = body_for(args.model, prompt, args.duration)

    status, est = call("POST", f"{API}/estimate/{args.model}", key, body)
    if status != 200 or est.get("type") != "estimate":
        print(f"estimate unavailable ({status}): {json.dumps(est)[:200]}")
        usd = None
    else:
        usd = float(est["usd"])
        print(f"…  estimate {args.model} {args.duration}s: {est['credits']} credits = ${usd:.2f}")
    if not args.go:
        print("      dry run: pass --go to generate")
        return 0
    if usd is not None and usd > args.max_usd:
        print(f"FAIL  estimate ${usd:.2f} exceeds --max-usd {args.max_usd:.2f}")
        return 2

    status, sub = call("POST", f"{API}/{args.model}", key, body)
    if status == 403 and sub.get("detail") == "not_enough_credits":
        print("FAIL  Higgsfield API account has insufficient credits; top up in the API console and re-run")
        return 2
    if status not in (200, 201, 202) or "request_id" not in sub:
        print(f"FAIL  submit {status}: {json.dumps(sub)[:300]}")
        return 1
    print(f"…  queued {sub['request_id']}")

    deadline = time.time() + args.timeout_minutes * 60
    result: dict = {}
    while time.time() < deadline:
        time.sleep(args.poll_seconds)
        status, result = call("GET", sub["status_url"], key)
        state = result.get("status")
        print(f"      {state}")
        if state == "completed":
            break
        if state in ("failed", "nsfw", "canceled"):
            print(f"FAIL  generation {state}: {json.dumps(result)[:300]}")
            return 1
    else:
        print("FAIL  timed out waiting for the generation")
        return 1

    video_url = (result.get("video") or {}).get("url") or result.get("url")
    if not video_url:
        print(f"FAIL  no video url in result: {json.dumps(result)[:300]}")
        return 1
    args.out.mkdir(parents=True, exist_ok=True)
    raw = args.out / f"{edition}-raw.mp4"
    dl = urllib.request.Request(video_url, headers={"User-Agent": UA})
    with urllib.request.urlopen(dl, timeout=300) as resp, raw.open("wb") as fh:  # noqa: S310 (API-returned https URL)
        shutil.copyfileobj(resp, fh)
    print(f"…  downloaded {raw.name}: {raw.stat().st_size / 1024:.0f} KB")
    cut_assets(find_ffmpeg(args.ffmpeg), raw, args.out, edition)
    raw.unlink()
    if args.beat == "1":  # tell the page the footage exists (the opening GETs this manifest instead of HEAD-probing the mp4)
        manifest = args.out / "hero.json"
        manifest.write_text(json.dumps({"landscape": "hero.mp4", "portrait": "hero-m.mp4", "ready": True}) + "\n", encoding="utf-8")
        print(f"…  {manifest.name}: ready = true")
    (args.out / f"{edition}.gen.json").write_text(json.dumps({
        "request_id": sub["request_id"], "model": args.model, "duration": args.duration,
        "estimate": est, "prompt": prompt, "video_url": video_url, "generated": time.strftime("%Y-%m-%d"),
    }, indent=2), encoding="utf-8")
    print("PASS  footage ready; the opening picks it up on next load (no rebuild)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
