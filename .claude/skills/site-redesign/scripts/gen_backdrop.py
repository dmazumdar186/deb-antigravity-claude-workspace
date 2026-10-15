#!/usr/bin/env python3
"""Generate a cover backdrop <canvas> module for a prospectus concept via OpenRouter.

description: Sends a PUBLIC visual brief (brand name, palette, motif, API spec) to the model chain
  z-ai/glm-5.3 -> z-ai/glm-5.2 -> moonshotai/kimi-k3 and writes the returned JavaScript module.
  Generalised from deliverables/misb_redesign_2026-10-15/research/gen_backdrop.py (MISB v3).
inputs: --brand NAME (used only to name the global window.<Brand>Backdrop), --palette "cream,accent"
  (two hex or rgba colours), --motif "place -> journey -> place" (what the particles form at p 0/0.5/1),
  --out PATH (default ./js/backdrop.js), --log PATH (cost log, default <out dir>/../research/glm_log.md),
  --model ID (pin one model instead of the chain), --feedback TEXT (revision round), --dry-run (print
  the brief, call nothing), --help. Key: OPENROUTER_API_KEY or OPENROUTER_API_TOEKN (env typo alias).
outputs: the module at --out, one Markdown table row appended to --log (model, tokens, cost, bytes,
  wall, generation id), the same line on stdout. Exit 2 on refused input, 1 when all models fail.
guardrail: public facts only. Any argument containing an '@' or a phone-number pattern is refused;
  never pass names of people, addresses, emails or client data (directives/infrastructure/glm_5_2_integration.md).
usage: python3 -I gen_backdrop.py --brand Acme --palette "#F5F1EA,#E64626" --motif "Paris -> rail journey -> Lyon" --out site/js/backdrop.js
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import re
import sys
import time

CHAIN = ["z-ai/glm-5.3", "z-ai/glm-5.2", "moonshotai/kimi-k3"]
PHONE = re.compile(r"(\+?\d[\d\s().-]{7,}\d)")
SYSTEM = ("You are a senior creative coder. You output ONLY one JavaScript file in a single ```js code block, "
          "no prose. Vanilla ES5/ES2015, no dependencies, no network, no eval/Function, no globals except the one module requested.")

BRIEF = """Write a self-contained <canvas> 2D module for the opening cover of a designed-document ("prospectus") website for the brand "{brand}".

API (exact):
  window.{glob} = {{
    init(canvas, opts),      // opts: {{seed:number, dpr:number (cap, default 1.5), reducedMotion:boolean, autoplay:boolean (default true)}}
    setProgress(p),          // 0..1 scroll progress of the cover; drives the journey
    render(tMs),             // draw one frame at absolute time tMs (deterministic; must not read Date/performance when called)
    pause(), resume(),       // stop/start the internal requestAnimationFrame loop
    destroy()                // remove listeners, cancel rAF
  }}

Visual: an editorial, monochrome composition of fine particles and hairline strokes in {cream} on a dark ink background that the PAGE paints (the canvas is transparent; do NOT fill a background). Use ONE accent colour {accent} sparingly (<= 3 % of marks).
Content, driven by progress p, follows this motif: {motif}
  p 0.00-0.30: the first place/state — a constellation of ~140 points forms a loose map-like figure with a cluster marking the subject (label-free); particles drift slowly; hairlines connect near neighbours (max ~40 px) with low alpha.
  p 0.30-0.70: the journey — the figure dissolves and particles travel diagonally down-right along faint parallel lines; 2-4 capital letters of the brand initials ({initials}) appear as light serif text, 10-16 px, fading in/out at ~0.08 alpha, dissolving into dots.
  p 0.70-1.00: the second place/state — particles reassemble into the second figure; a faint ring pulses once around its cluster.
Interpolate smoothly between stages (ease in/out); never snap. Always keep a slow ambient drift so the frame is alive when p is constant.

Engineering:
  - Seeded PRNG (mulberry32) from opts.seed so frames are deterministic for a given (seed, tMs, p).
  - Handle resize (ResizeObserver if available, else window resize); backing store = clientWidth*dpr capped at opts.dpr; scale the context.
  - Internal loop: requestAnimationFrame; pause when document.hidden; expose pause/resume.
  - reducedMotion true: draw ONE static frame of the first stage at p and do not animate (still re-render on setProgress).
  - Particle count scales with canvas area (~1 per 9000 px^2, min 90, max 260).
  - No globals other than window.{glob}; IIFE; strict mode; no console output; guard every canvas call if getContext fails.
  - Total size <= 11 KB unminified. Compact code, short helper names; no comments longer than one line.
Output only the code block."""


def refuse(args: argparse.Namespace) -> str | None:
    for k in ("brand", "palette", "motif", "feedback"):
        v = getattr(args, k) or ""
        if "@" in v:
            return f"--{k} contains '@' (email-like); public facts only"
        if PHONE.search(v):
            return f"--{k} contains a phone-number pattern; public facts only"
    return None


def build_brief(a: argparse.Namespace) -> str:
    cream, _, accent = a.palette.partition(",")
    glob = re.sub(r"[^A-Za-z0-9]", "", a.brand) or "Brand"
    initials = ",".join(f"'{w[0].upper()}'" for w in re.findall(r"[A-Za-z]+", a.brand)[:4]) or "'A'"
    return BRIEF.format(brand=a.brand, glob=glob + "Backdrop", cream=cream.strip() or "rgba(245,241,234,…)",
                        accent=(accent.strip() or "#3F7BBF"), motif=a.motif, initials=initials)


def call(model: str, brief: str, key: str, feedback: str | None):
    import requests  # local import keeps --help/--dry-run dependency-free

    user = brief + (("\n\nREVISION REQUEST — fix these issues and return the full file again:\n" + feedback) if feedback else "")
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
                      headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json",
                               "HTTP-Referer": "https://prodcraft.fyi", "X-Title": "site-redesign-backdrop"},
                      json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
                            "max_tokens": 14000, "temperature": 0.6, "reasoning": {"effort": "low"}, "usage": {"include": True}},
                      timeout=900)
    r.raise_for_status()
    d = r.json()
    if "error" in d:
        raise RuntimeError(str(d["error"])[:200])
    msg = d["choices"][0]["message"]
    text = msg.get("content") or msg.get("reasoning") or ""
    if "```" not in text:
        raise RuntimeError(f"no code block (finish={d['choices'][0].get('finish_reason')}, len={len(text)})")
    return text, d.get("usage", {}), d.get("id")


def extract(text: str) -> str:
    m = re.search(r"```(?:js|javascript)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"


def main() -> int:
    ap = argparse.ArgumentParser(description="GLM/Kimi cover-backdrop generator (public brief only).")
    ap.add_argument("--brand", required=True)
    ap.add_argument("--palette", default="rgba(245,241,234,1),#3F7BBF", help='"cream,accent"')
    ap.add_argument("--motif", required=True, help='"place -> journey -> place"')
    ap.add_argument("--out", default="js/backdrop.js")
    ap.add_argument("--log", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--feedback", default=None)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    why = refuse(a)
    if why:
        print("REFUSED:", why, file=sys.stderr)
        return 2
    brief = build_brief(a)
    if a.dry_run:
        print(brief)
        return 0
    key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_TOEKN") or os.environ.get("OPENROUTER_API_TOKEN")
    if not key:
        print("no OpenRouter key in env (OPENROUTER_API_KEY / OPENROUTER_API_TOEKN)", file=sys.stderr)
        return 1
    out = pathlib.Path(a.out)
    log = pathlib.Path(a.log) if a.log else out.parent.parent.parent / "research" / "glm_log.md"
    for model in ([a.model] if a.model else CHAIN):
        t0 = time.time()
        try:
            text, usage, gid = call(model, brief, key, a.feedback)
        except Exception as e:  # noqa: BLE001 — try the next model in the chain
            print(f"{model}: failed: {str(e)[:200]}")
            continue
        code = extract(text)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(code, encoding="utf-8")
        cost = usage.get("cost")
        line = (f"| {time.strftime('%Y-%m-%d %H:%M')} | {model} | {'revision' if a.feedback else 'initial'} | "
                f"{usage.get('prompt_tokens')} | {usage.get('completion_tokens')} | ${cost if cost is not None else '?'} | "
                f"{len(code.encode())} B | {time.time() - t0:.0f}s | {gid} |\n")
        log.parent.mkdir(parents=True, exist_ok=True)
        if not log.exists():
            log.write_text(f"# GLM / Kimi log — {a.brand} cover backdrop\n\nPayload: public visual brief only (brand name, colours, motif, API spec). No PII, no client data.\n\n"
                           "| when | model | round | prompt tok | completion tok | cost | output | wall | generation id |\n|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
        with log.open("a", encoding="utf-8") as f:
            f.write(line)
        print(line.strip())
        print("wrote", out)
        return 0
    print("all models failed", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
