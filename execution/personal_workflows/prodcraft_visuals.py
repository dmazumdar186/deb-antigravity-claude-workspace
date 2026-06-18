"""
description: Fetch visuals for each visual_beats.json beat. stock → Pexels API photo; diagram → FLUX.1-schnell on HuggingFace free tier; text_card → skipped (Remotion renders text natively). Re-runnable: skips beats whose asset already exists on disk.
inputs:
    CLI:
        --beats PATH         visual_beats.json (default: .tmp/prodcraft/visual_beats.json)
        --out-dir PATH       assets dir (default: .tmp/prodcraft/visuals)
        --width N            target landscape width (default: 1920)
        --height N           target landscape height (default: 1080)
        --skip-existing      skip beats whose asset already exists (default behavior; flag is for clarity)
        --force              re-fetch even if asset exists
        --only TYPE          only fetch one type: stock|diagram|text_card (default: all)
    Env:
        PEXELS_API_KEY       required for stock
        HF_API_TOKEN         required for diagram (FLUX)
outputs:
    {out_dir}/{beat_id}.jpg|png     per-beat asset
    {beats_path}                    updated in-place with asset_path + attribution
    Writes a sidecar .tmp/prodcraft/visuals_log.json with per-beat fetch status
"""
from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BEATS = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visual_beats.json"
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visuals"
LOG_PATH = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "visuals_log.json"

PEXELS_ENDPOINT = "https://api.pexels.com/v1/search"


def _fetch_pexels(query: str, out_path: Path, width: int, height: int) -> dict:
    """Search Pexels, pick one of top results, download to out_path. Returns attribution dict."""
    api_key = os.environ.get("PEXELS_API_KEY")
    if not api_key:
        raise RuntimeError("PEXELS_API_KEY missing in .env")

    r = requests.get(
        PEXELS_ENDPOINT,
        headers={"Authorization": api_key},
        params={"query": query, "per_page": 6, "orientation": "landscape", "size": "large"},
        timeout=30,
    )
    if r.status_code != 200:
        raise RuntimeError(f"Pexels search failed: {r.status_code} {r.text[:200]}")
    photos = r.json().get("photos", [])
    if not photos:
        raise RuntimeError(f"Pexels returned no photos for query={query!r}")

    photo = photos[min(random.randint(0, 2), len(photos) - 1)]
    img_url = photo["src"].get("large2x") or photo["src"]["large"]

    img_r = requests.get(img_url, timeout=60)
    if img_r.status_code != 200:
        raise RuntimeError(f"Pexels image download failed: {img_r.status_code}")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(img_r.content)

    return {
        "source": "pexels",
        "query": query,
        "photo_id": photo["id"],
        "photographer": photo["photographer"],
        "photographer_url": photo["photographer_url"],
        "pexels_url": photo["url"],
        "src_url": img_url,
    }


def _fetch_flux(prompt: str, out_path: Path, width: int, height: int) -> dict:
    """Call FLUX.1-schnell via HuggingFace InferenceClient. Free tier."""
    from huggingface_hub import InferenceClient

    token = os.environ.get("HF_API_TOKEN")
    if not token:
        raise RuntimeError("HF_API_TOKEN missing in .env")
    client = InferenceClient(token=token)

    # FLUX.1-schnell supports 1024x1024 well; for 16:9 we use 1344x768 (the common SDXL 16:9 ratio).
    flux_w, flux_h = (1344, 768) if width / max(height, 1) > 1.5 else (1024, 1024)

    image = client.text_to_image(
        prompt=prompt,
        model="black-forest-labs/FLUX.1-schnell",
        width=flux_w,
        height=flux_h,
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(out_path)
    return {
        "source": "flux-schnell-hf",
        "prompt": prompt,
        "width": flux_w,
        "height": flux_h,
    }


def fetch_all(beats_path: Path, out_dir: Path, width: int, height: int, force: bool, only: str | None) -> dict:
    data = json.loads(beats_path.read_text(encoding="utf-8"))
    beats = data["beats"]
    out_dir.mkdir(parents=True, exist_ok=True)

    log: list[dict] = []
    n_ok = 0
    n_skip = 0
    n_fail = 0
    for b in beats:
        bid = b["id"]
        btype = b["type"]

        if only and btype != only:
            continue
        if btype in ("text_card", "concept_card"):
            # Both are Remotion-rendered; no asset needed.
            b["asset_path"] = None
            b["attribution"] = None
            log.append({"id": bid, "type": btype, "status": f"skip-{btype}"})
            n_skip += 1
            continue

        ext = ".jpg" if btype == "stock" else ".png"
        out_file = out_dir / f"{bid}{ext}"

        if out_file.exists() and not force:
            b["asset_path"] = str(out_file.resolve()).replace("\\", "/")
            log.append({"id": bid, "type": btype, "status": "skip-exists", "path": str(out_file)})
            n_skip += 1
            continue

        attempts = 3
        last_err: Exception | None = None
        for attempt in range(1, attempts + 1):
            try:
                t0 = time.monotonic()
                if btype == "stock":
                    attribution = _fetch_pexels(b["stock_query"], out_file, width, height)
                elif btype == "diagram":
                    attribution = _fetch_flux(b["diagram_prompt"], out_file, width, height)
                else:
                    raise RuntimeError(f"unknown beat type: {btype}")
                elapsed = time.monotonic() - t0
                b["asset_path"] = str(out_file.resolve()).replace("\\", "/")
                b["attribution"] = attribution
                log.append({
                    "id": bid, "type": btype, "status": "ok",
                    "attempt": attempt, "elapsed_sec": round(elapsed, 2),
                    "path": str(out_file),
                })
                print(f"  {bid} | {btype:8} | OK in {elapsed:.1f}s | {out_file.name}", file=sys.stderr)
                n_ok += 1
                break
            except Exception as e:
                last_err = e
                wait = 2 ** attempt + random.uniform(0, 1)
                print(f"  {bid} | {btype:8} | attempt {attempt}/{attempts} FAIL: {e}; sleep {wait:.1f}s", file=sys.stderr)
                time.sleep(wait)
        else:
            # Loop completed without break — all attempts failed. Substitute as text_card.
            b["asset_path"] = None
            b["attribution"] = None
            b["fallback_reason"] = f"{btype} fetch failed after {attempts} attempts: {last_err}"
            b["type"] = "text_card"
            short = (b.get("stock_query") or b.get("diagram_prompt") or b.get("text", ""))[:40]
            b["card_text"] = b.get("card_text") or short
            log.append({"id": bid, "type": btype, "status": "fallback-text-card", "error": str(last_err)})
            print(f"  {bid} | {btype:8} | FALLBACK to text_card after 3 failures", file=sys.stderr)
            n_fail += 1

    # Persist updated beats + log.
    beats_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text(json.dumps({"beats_fetched": log}, indent=2), encoding="utf-8")

    print(
        f"\nOK | visuals | fetched={n_ok} skipped={n_skip} fallback={n_fail} | "
        f"beats updated in {beats_path}",
        file=sys.stderr,
    )
    return {"ok": n_ok, "skip": n_skip, "fail": n_fail}


def main() -> int:
    p = argparse.ArgumentParser(description="Fetch visuals for visual_beats.json (Pexels + FLUX via HF).")
    p.add_argument("--beats", default=str(DEFAULT_BEATS), help="visual_beats.json path")
    p.add_argument("--out-dir", default=str(DEFAULT_OUT), help="Assets output dir")
    p.add_argument("--width", type=int, default=1920, help="Target landscape width")
    p.add_argument("--height", type=int, default=1080, help="Target landscape height")
    p.add_argument("--force", action="store_true", help="Re-fetch even if asset exists")
    p.add_argument("--only", choices=["stock", "diagram", "text_card"], help="Only fetch one type")
    args = p.parse_args()

    fetch_all(Path(args.beats), Path(args.out_dir), args.width, args.height, args.force, args.only)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
