"""Generate the MISB cover backdrop canvas module via OpenRouter (GLM 5.3 -> GLM 5.2 -> Kimi K3).
Public facts only are sent (city names, colours, the visual brief). Logs cost to glm_log.md.
usage: python3 gen_backdrop.py [--model z-ai/glm-5.3] [--feedback "..."]"""
import os, sys, json, re, time, argparse, pathlib, requests

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE.parent / "site_v3" / "js" / "backdrop.js"
LOG = HERE / "glm_log.md"
KEY = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_TOKEN") or os.environ.get("OPENROUTER_API_TOEKN")
CHAIN = ["z-ai/glm-5.3", "z-ai/glm-5.2", "moonshotai/kimi-k3"]

SYSTEM = "You are a senior creative coder. You output ONLY one JavaScript file in a single ```js code block, no prose. Vanilla ES5/ES2015, no dependencies, no network, no eval/Function, no globals except the one module requested."

BRIEF = """Write a self-contained <canvas> 2D module for the opening cover of a business-school prospectus website (campuses: Paris and Lyon, France).

API (exact):
  window.MISBBackdrop = {
    init(canvas, opts),      // opts: {seed:number, dpr:number (cap, default 1.5), reducedMotion:boolean, autoplay:boolean (default true)}
    setProgress(p),          // 0..1 scroll progress of the cover; drives the journey
    render(tMs),             // draw one frame at absolute time tMs (used for deterministic recording; must not depend on Date/performance when called)
    pause(), resume(),       // stop/start the internal requestAnimationFrame loop
    destroy()                // remove listeners, cancel rAF
  }

Visual: an editorial, monochrome composition — fine particles and hairline strokes in cream rgba(245,241,234,…) on a dark ink background that the PAGE paints (the canvas is transparent; do NOT fill a background). Use ONE accent colour #3F7BBF (soft navy-blue) sparingly (≤ 3 % of marks).
Content, driven by progress p:
  p 0.00–0.30: Paris. A constellation of ~140 points forms a loose map-like figure: a meandering river line (the Seine, a gentle S-curve across the upper-left third) drawn by particles flowing along it, with a cluster of points marking a campus point north-east of the river (label-free). Particles drift slowly; hairlines connect near neighbours (max ~40 px) with low alpha.
  p 0.30–0.70: the journey. The constellation dissolves and particles travel diagonally down-right across the canvas along faint parallel rail lines, with occasional tiny letterforms (draw 2–4 capital letters 'M','I','S','B' as text in a light serif, 10–16 px, fading in/out at ~0.08 alpha) dissolving into dots.
  p 0.70–1.00: Lyon. Particles reassemble into a second map figure: two rivers converging (the Saône from the north and the Rhône from the north-east meeting in a Y), with a campus cluster east of the confluence; a faint ring pulses once around the cluster.
Interpolate smoothly between stages (ease in/out); never snap. Always keep a slow ambient drift so the frame is alive even when p is constant.

Engineering:
  - Seeded PRNG (mulberry32) from opts.seed so frames are deterministic for a given (seed, tMs, p).
  - Handle resize (ResizeObserver if available, else window resize); size the backing store to clientWidth*dpr capped at opts.dpr; scale the context.
  - Internal loop: requestAnimationFrame; pause automatically when document.hidden; expose pause/resume.
  - reducedMotion true: draw ONE static frame of the Paris stage at p and do not animate (but still re-render on setProgress).
  - Particle count scales with canvas area (≈ 1 per 9000 px², min 90, max 260).
  - No globals other than window.MISBBackdrop; wrap in an IIFE; strict mode; no console output; guard every canvas call if getContext fails.
  - Total size ≤ 11 KB unminified. Prefer compact code and short helper names; no comments longer than one line.
Output only the code block."""

def call(model, feedback=None):
    user = BRIEF + ("\n\nREVISION REQUEST — fix these issues and return the full file again:\n" + feedback if feedback else "")
    r = requests.post("https://openrouter.ai/api/v1/chat/completions",
        headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json",
                 "HTTP-Referer": "https://prodcraft.fyi", "X-Title": "misb-v3-backdrop"},
        json={"model": model, "messages": [{"role": "system", "content": SYSTEM}, {"role": "user", "content": user}],
              "max_tokens": 14000, "temperature": 0.6, "reasoning": {"effort": "low"}, "usage": {"include": True}}, timeout=900)
    r.raise_for_status(); d = r.json()
    if "error" in d: raise RuntimeError(d["error"])
    (HERE / ".tmp_backdrop_raw.json").write_text(json.dumps(d)[:200000], encoding="utf-8")
    msg = d["choices"][0]["message"]; text = msg.get("content") or msg.get("reasoning") or ""
    if not re.search(r"```", text): raise RuntimeError(f"no code block (finish={d['choices'][0].get('finish_reason')}, len={len(text)})")
    return text, d.get("usage", {}), d.get("id")

def extract(text):
    m = re.search(r"```(?:js|javascript)?\s*\n(.*?)```", text, re.S)
    return (m.group(1) if m else text).strip() + "\n"

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--model"); ap.add_argument("--feedback"); ap.add_argument("--out", default=str(OUT))
    a = ap.parse_args()
    if not KEY: sys.exit("no OpenRouter key in env")
    chain = [a.model] if a.model else CHAIN
    for model in chain:
        t0 = time.time()
        try:
            text, usage, gid = call(model, a.feedback)
        except Exception as e:  # noqa: BLE001
            print(f"{model}: failed: {str(e)[:200]}"); continue
        code = extract(text)
        pathlib.Path(a.out).write_text(code, encoding="utf-8")
        cost = usage.get("cost"); pt = usage.get("prompt_tokens"); ct = usage.get("completion_tokens")
        line = f"| {time.strftime('%Y-%m-%d %H:%M')} | {model} | {'revision' if a.feedback else 'initial'} | {pt} | {ct} | ${cost if cost is not None else '?'} | {len(code.encode())} B | {time.time()-t0:.0f}s | {gid} |\n"
        if not LOG.exists():
            LOG.write_text("# GLM / Kimi log — MISB v3 cover backdrop\n\nPayload: public visual brief only (city names, colours, API spec). No PII, no client data.\n\n| when | model | round | prompt tok | completion tok | cost | output | wall | generation id |\n|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
        with LOG.open("a", encoding="utf-8") as f: f.write(line)
        print(line.strip()); print("wrote", a.out); return 0
    sys.exit("all models failed")

if __name__ == "__main__":
    sys.exit(main())
