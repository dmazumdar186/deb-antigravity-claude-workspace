"""
description: Generate images through OpenRouter image-output models (default google/gemini-3-pro-image).
    Dry run by default (prints the plan and a cost ceiling, spends 0.00). --live spends, capped by
    --budget-usd; every live call appends one row to .tmp/image_gen_ledger.jsonl.
inputs:
    CLI:
        --prompt "..." | --prompt-file PATH   prompt text (one image per --n)
        --n N                 images to generate (default 1, max 8)
        --model ID            OpenRouter model id (default google/gemini-3-pro-image)
        --out-dir PATH        where PNGs go (default .tmp/image_gen/)
        --name SLUG           file name stem (default img)
        --budget-usd X        hard cap for this run (default 1.00); stops before a call that could exceed it
        --est-usd X           worst-case cost per image used for the cap (default 0.20)
        --live                actually call the API (otherwise dry run)
    env: OPENROUTER_API_KEY (cloud alias OPENROUTER_API_TOEKN also read)
outputs:
    {out_dir}/{name}-{i}.png, one JSON line per call in .tmp/image_gen_ledger.jsonl,
    stdout summary with total reported cost.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # optional: env vars may already be set (cloud)
    pass

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / ".tmp" / "image_gen_ledger.jsonl"
API = "https://openrouter.ai/api/v1/chat/completions"


def key() -> str:
    k = (
        os.environ.get("OPENROUTER_API_KEY")
        or os.environ.get("OPENROUTER_API_TOEKN")
        or ""
    )
    if not k:
        raise SystemExit("OPENROUTER_API_KEY is not set")
    return k


def call(
    model: str, prompt: str, timeout: int = 180
) -> tuple[bytes | None, float, dict]:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "modalities": ["image", "text"],
            "usage": {"include": True},
        }
    ).encode()
    req = urllib.request.Request(
        API,
        data=body,
        method="POST",
        headers={
            "Authorization": f"Bearer {key()}",
            "Content-Type": "application/json",
            "X-Title": "workspace-image-gen",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        data = json.loads(r.read().decode())
    usage = data.get("usage") or {}
    cost = float(usage.get("cost") or 0.0)
    msg = (data.get("choices") or [{}])[0].get("message") or {}
    for im in msg.get("images") or []:
        url = (im.get("image_url") or {}).get("url", "")
        if url.startswith("data:image"):
            return base64.b64decode(url.split(",", 1)[1]), cost, usage
    return None, cost, {"usage": usage, "text": (msg.get("content") or "")[:300]}


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--prompt")
    g.add_argument("--prompt-file")
    ap.add_argument("--n", type=int, default=1)
    ap.add_argument("--model", default="google/gemini-3-pro-image")
    ap.add_argument("--out-dir", default=str(ROOT / ".tmp" / "image_gen"))
    ap.add_argument("--name", default="img")
    ap.add_argument("--budget-usd", type=float, default=1.00)
    ap.add_argument("--est-usd", type=float, default=0.20)
    ap.add_argument("--live", action="store_true")
    a = ap.parse_args()
    prompt = a.prompt if a.prompt else Path(a.prompt_file).read_text(encoding="utf-8")
    n = max(1, min(8, a.n))
    ceiling = n * a.est_usd
    print(f"model={a.model} n={n} budget=${a.budget_usd:.2f} worst-case=${ceiling:.2f}")
    if not a.live:
        print("DRY RUN: no API call made, spend 0.00. Add --live to generate.")
        return 0
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    LEDGER.parent.mkdir(parents=True, exist_ok=True)
    spent = 0.0
    made = 0
    for i in range(1, n + 1):
        if spent + a.est_usd > a.budget_usd:
            print(
                f"budget guard: stopping before image {i} (spent ${spent:.4f}, cap ${a.budget_usd:.2f})"
            )
            break
        t0 = time.time()
        err = None
        img = None
        cost = 0.0
        info = {}
        try:
            img, cost, info = call(a.model, prompt)
        except urllib.error.HTTPError as e:
            err = f"HTTP {e.code}: {e.read().decode(errors='replace')[:300]}"
        except (
            Exception
        ) as e:  # network/timeout/parse: log and continue to the ledger row
            err = f"{type(e).__name__}: {e}"
        spent += cost
        path = None
        if img:
            path = out / f"{a.name}-{i}.png"
            path.write_bytes(img)
            made += 1
        row = {
            "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "script": "openrouter_image_gen",
            "model": a.model,
            "name": a.name,
            "i": i,
            "cost_usd": round(cost, 6),
            "secs": round(time.time() - t0, 1),
            "file": str(path) if path else None,
            "error": err or (None if img else f"no image: {json.dumps(info)[:200]}"),
        }
        with LEDGER.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        print(
            f"[{i}/{n}] {'OK ' + str(path) if path else 'FAIL ' + str(row['error'])} cost=${cost:.4f}"
        )
    print(f"done: {made}/{n} images, reported spend ${spent:.4f}")
    return 0 if made else 1


if __name__ == "__main__":
    sys.exit(main())
