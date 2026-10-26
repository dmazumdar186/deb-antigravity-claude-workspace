#!/usr/bin/env python3
"""Produce the Sūrya Namaskāra hero film: Kling image-to-video legs between keyframes via Higgsfield, stitched by ffmpeg.

description: For each consecutive keyframe pair (start, end image URLs) submits one Kling image-to-video job on
  Higgsfield, polls, downloads, extracts review frames, then concatenates the legs with short crossfades into
  hero.mp4 (+ hero-m.mp4 portrait centre crop, poster.jpg, hero.json). Estimate-first: refuses to submit when the
  summed estimate exceeds --max-usd. Idempotent: legs already downloaded are skipped; --legs limits to a subset.
inputs: --frames-base URL (hosted keyframes frame-01..12.jpg), --out DIR, --model ID
  (default kling-video/v3.0/std/image-to-video), --duration 5, --aspect 16:9, --max-usd 8, --legs 1-11 or "1,2",
  --go (spend), --concurrency 4. Env HIGGSFIELD_API_KEY (key_id:secret).
outputs: <out>/leg-NN.mp4, <out>/leg-NN.json, <out>/frames/leg-NN-fXX.jpg, <out>/hero.mp4, hero-m.mp4, poster.jpg,
  hero.json, ledger.jsonl (one row per job with usd). Exit 2 over budget / insufficient credits, 1 on API/ffmpeg error.
"""
from __future__ import annotations
import argparse, json, os, subprocess, sys, time, urllib.error, urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

API = "https://api.higgsfield.ai"
UA = "Mozilla/5.0 jeevana-film/1.0"
POSES = ["Praṇāmāsana, standing, palms together at the chest",
         "Hasta Uttānāsana, arms raised overhead, gentle backbend",
         "Pādahastāsana, standing forward fold, hands to the floor",
         "Aśva Sañcālanāsana, low lunge, one knee down, chest lifted",
         "Parvatāsana, downward-facing V, hips high",
         "Aṣṭāṅga Namaskāra, knees chest and chin lowered to the floor, hips raised",
         "Bhujaṅgāsana, cobra, chest lifted from the floor",
         "Parvatāsana, downward-facing V, hips high",
         "Aśva Sañcālanāsana, low lunge with the other leg",
         "Pādahastāsana, standing forward fold",
         "Hasta Uttānāsana, arms raised overhead",
         "Praṇāmāsana, standing, palms together at the chest"]
STYLE = (" One slow continuous yoga movement with the breath, nothing else moves. Fixed camera, eye level, full body always in "
         "frame, feet on the same ground line. Plain warm cream paper studio background, soft even daylight, no props, no "
         "text, no other people. Photoreal, her face unchanged, hair tied back the whole time, clothing and body unchanged throughout, hands and feet keep contact with the floor when they are on it. Calm editorial pacing.")

def call(method, url, key, body=None, timeout=60):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Key {key}"); req.add_header("User-Agent", UA)
    if data is not None: req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r: return r.status, json.loads(r.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        try: return e.code, json.loads(e.read().decode() or "{}")
        except json.JSONDecodeError: return e.code, {"detail": "non-json"}

def find_url(o):
    if isinstance(o, dict):
        if isinstance(o.get("url"), str) and o["url"].startswith("http"): return o["url"]
        for v in o.values():
            u = find_url(v)
            if u: return u
    if isinstance(o, list):
        for v in o:
            u = find_url(v)
            if u: return u
    return None

def leg_body(n, base, duration, aspect):
    extra = {}
    rp = Path(os.environ.get("RETAKE_PROMPTS", "")) if os.environ.get("RETAKE_PROMPTS") else None
    if rp and rp.exists(): extra = json.loads(rp.read_text())
    return {"prompt": f"The same woman moves slowly from {POSES[n-1]} into {POSES[n]}." + STYLE + extra.get(str(n), ""),
            "duration": duration, "aspect_ratio": aspect, "sound": "off",
            "image_url": f"{base}/frame-{n:02d}.jpg", "last_image_url": f"{base}/frame-{n+1:02d}.jpg", "cfg_scale": 0.7}

def run_leg(n, a, key, out):
    mp4, meta = out / f"leg-{n:02d}.mp4", out / f"leg-{n:02d}.json"
    if mp4.exists() and mp4.stat().st_size > 50_000: return n, "cached", 0.0
    body = leg_body(n, a.frames_base, a.duration, a.aspect)
    s, sub = call("POST", f"{API}/{a.model}", key, body)
    if s == 403 and sub.get("detail") == "not_enough_credits": return n, "no_credits", 0.0
    if s not in (200, 201, 202) or "request_id" not in sub: return n, f"submit {s} {json.dumps(sub)[:160]}", 0.0
    rec = {"leg": n, "body": body, "submit": sub, "model": a.model}
    for _ in range(80):
        time.sleep(15)
        s, st = call("GET", sub["status_url"], key)
        if st.get("status") in ("completed", "failed", "error", "cancelled"): break
    rec["status"] = st; meta.write_text(json.dumps(rec, indent=1))
    url = find_url(st) if st.get("status") == "completed" else None
    if not url: return n, f"{st.get('status')} {str(st.get('error',''))[:120]}", 0.0
    subprocess.run(["curl", "-s", "-L", "-A", UA, "-o", str(mp4), url], check=True)
    fr = out / "frames"; fr.mkdir(exist_ok=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp4), "-vf", "fps=2,scale=640:-2", str(fr / f"leg-{n:02d}-f%02d.jpg")])
    return n, "ok", 0.0

def stitch(out, legs, aspect):
    files = [out / f"leg-{n:02d}.mp4" for n in legs]
    if not all(f.exists() for f in files): print("stitch skipped: missing legs"); return
    # concat with 0.35 s crossfades at each join
    args = ["ffmpeg", "-y", "-loglevel", "error"]
    for f in files: args += ["-i", str(f)]
    dur = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(files[0])], capture_output=True, text=True).stdout.strip() or 5)
    fc, prev, off = [], "[0:v]", 0.0
    for i in range(1, len(files)):
        off += dur - 0.35
        fc.append(f"{prev}[{i}:v]xfade=transition=fade:duration=0.35:offset={off:.2f}[v{i}]"); prev = f"[v{i}]"
    args += ["-filter_complex", ";".join(fc), "-map", prev, "-an", "-c:v", "libx264", "-preset", "slow", "-crf", "22", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "hero.mp4")]
    subprocess.run(args, check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "hero.mp4"), "-vf", "crop=ih*9/16:ih,scale=1080:1920:flags=lanczos", "-c:v", "libx264", "-preset", "slow", "-crf", "24", "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(out / "hero-m.mp4")], check=True)
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(out / "hero.mp4"), "-frames:v", "1", "-q:v", "3", str(out / "poster.jpg")], check=True)
    total = float(subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out / "hero.mp4")], capture_output=True, text=True).stdout.strip())
    (out / "hero.json").write_text(json.dumps({"ready": True, "legs": len(files), "leg_seconds": dur, "xfade": 0.35, "seconds": round(total, 2),
                                                "keyframes_s": [round(i * (dur - 0.35), 2) for i in range(len(files) + 1)], "aspect": aspect,
                                                "landscape": "hero.mp4", "portrait": "hero-m.mp4", "poster": "poster.jpg"}, indent=1))
    print(f"hero.mp4 {total:.1f}s, {len(files)} legs")

def main():
    p = argparse.ArgumentParser(); p.add_argument("--frames-base", required=True); p.add_argument("--out", required=True)
    p.add_argument("--model", default="kling-video/v3.0/std/image-to-video"); p.add_argument("--duration", type=int, default=5)
    p.add_argument("--aspect", default="16:9"); p.add_argument("--max-usd", type=float, default=8.0); p.add_argument("--legs", default="1-11")
    p.add_argument("--go", action="store_true"); p.add_argument("--concurrency", type=int, default=4); a = p.parse_args()
    key = os.environ.get("HIGGSFIELD_API_KEY", "").strip()
    if ":" not in key: sys.exit("HIGGSFIELD_API_KEY (key_id:secret) missing")
    out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
    legs = [int(x) for x in a.legs.split(",")] if "," in a.legs else list(range(int(a.legs.split("-")[0]), int(a.legs.split("-")[-1]) + 1))
    todo = [n for n in legs if not (out / f"leg-{n:02d}.mp4").exists()]
    s, est = call("POST", f"{API}/estimate/{a.model}", key, leg_body(1, a.frames_base, a.duration, a.aspect))
    if s != 200: sys.exit(f"estimate failed {s}: {est}")
    per = float(est.get("usd", 0)) - float((est.get("discount") or {}).get("usd", 0) or 0); total = per * len(todo)
    print(f"estimate: {len(todo)} legs × ${per:.3f} = ${total:.2f} (cap ${a.max_usd:.2f}); cached {len(legs)-len(todo)}")
    if total > a.max_usd: sys.exit(2)
    if not a.go: print("dry run; pass --go to spend"); return
    with ThreadPoolExecutor(max_workers=a.concurrency) as ex:
        for n, status, _ in ex.map(lambda n: run_leg(n, a, key, out), todo):
            print(f"leg {n:02d}: {status}")
            with open(out / "ledger.jsonl", "a") as f: f.write(json.dumps({"ts": time.strftime("%FT%T"), "leg": n, "status": status, "usd": per if status == "ok" else 0}) + "\n")
    stitch(out, legs, a.aspect)

if __name__ == "__main__": main()
