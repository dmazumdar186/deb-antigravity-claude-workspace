"""War room — OpenAI Sol and Claude Opus co-build the Jeevana site through OpenRouter (credits, not the subscription).

description: Two senior "researchers" alternate as author and critic. Round 1: Sol drafts the page from the brief +
             handoff. Then: Claude critiques (design + code), Sol revises; Sol critiques, Claude revises; each round
             ends by writing the files into site/. Gate results and eye-review defects are fed back as critique.
inputs: --root (deliverable dir), brief_v4.md, research/sol_handoff.md, research/content_fixture.json,
        site/assets/photos/manifest.json, teardown excerpt; env OPENROUTER_API_KEY / OPENROUTER_API_TOEKN.
outputs: site/index.html, site/css/styles.css, site/js/main.js, site/js/i18n.js; research/warroom/round_NN_*.md
         (critiques, notes, usage); research/warroom/ledger.md (model, tokens, cost, wall per call).

Usage (from the deliverable dir):
    python3 research/warroom.py draft                       # Sol writes the first version
    python3 research/warroom.py critique --by claude        # Claude reviews current site/ -> round_NN_critique.md
    python3 research/warroom.py revise --by sol --notes research/warroom/round_02_critique.md [--extra gates.txt]
    python3 research/warroom.py critique --by sol ; python3 research/warroom.py revise --by claude --notes ...
    python3 research/warroom.py status
"""
from __future__ import annotations
import argparse, json, os, re, sys, time
from pathlib import Path
import requests

MODELS = {"sol": "openai/gpt-6.1-sol-pro", "claude": "anthropic/claude-opus-5.5", "fable": "anthropic/claude-fable-5.1", "glm": "z-ai/glm-5.3"}
FILES = ["site/index.html", "site/css/styles.css", "site/js/main.js", "site/js/i18n.js"]
OR = "https://openrouter.ai/api/v1/chat/completions"

def key() -> str:
    k = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_TOEKN") or os.environ.get("OPENROUTER_API_TOKEN")
    if not k:
        sys.exit("no OpenRouter key in env")
    return k

def read(p: Path, limit: int | None = None) -> str:
    t = p.read_text(encoding="utf-8", errors="replace") if p.exists() else ""
    return t[:limit] if limit else t

def call(model: str, system: str, user: str, max_tokens: int, json_mode: bool, effort: str = "high") -> tuple[str, dict]:
    """Streamed completion (keeps the proxy connection alive on 10-minute generations); retries on resets."""
    body = {"model": model, "max_tokens": max_tokens, "reasoning": {"effort": effort}, "stream": True,
            "stream_options": {"include_usage": True},
            "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    t0 = time.time()
    for attempt in range(3):
        try:
            r = requests.post(OR, headers={"Authorization": f"Bearer {key()}", "HTTP-Referer": "https://prodcraft.fyi", "X-Title": "jeevana-warroom"},
                              json=body, timeout=(30, 600), stream=True)
            if r.status_code in (429, 500, 502, 503) and attempt < 2:
                time.sleep(8 * (attempt + 1)); continue
            r.raise_for_status()
            text, usage, finish, gid = [], {}, None, None
            for raw in r.iter_lines(decode_unicode=False):  # bytes per line, decoded whole: no chars lost at chunk edges
                if not raw:
                    continue
                line = raw.decode("utf-8", errors="strict")
                if not line.startswith("data: "):
                    continue
                data = line[6:]
                if data.strip() == "[DONE]":
                    break
                try:
                    d = json.loads(data)
                except json.JSONDecodeError:
                    continue
                gid = gid or d.get("id")
                for ch in d.get("choices") or []:
                    delta = ch.get("delta") or {}
                    if delta.get("content"):
                        text.append(delta["content"])
                    if ch.get("finish_reason"):
                        finish = ch["finish_reason"]
                if d.get("usage"):
                    usage = d["usage"]
            usage = usage | {"wall_s": round(time.time() - t0, 1), "gen": gid, "finish": finish}
            return "".join(text), usage
        except (requests.exceptions.ChunkedEncodingError, requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            if attempt == 2:
                raise
            print(f"stream broke ({e.__class__.__name__}); retry {attempt + 1}", file=sys.stderr); time.sleep(10)
    raise RuntimeError("unreachable")

def ledger(root: Path, step: str, model: str, usage: dict) -> None:
    p = root / "research/warroom/ledger.md"
    if not p.exists():
        p.write_text("| when | step | model | prompt tok | completion tok | cost $ | wall s | finish | gen |\n|---|---|---|---|---|---|---|---|---|\n", encoding="utf-8")
    cost = usage.get("cost")
    with p.open("a", encoding="utf-8") as f:
        f.write(f"| {time.strftime('%Y-%m-%d %H:%M')} | {step} | {model} | {usage.get('prompt_tokens')} | {usage.get('completion_tokens')} | "
                f"{'' if cost is None else round(float(cost), 4)} | {usage.get('wall_s')} | {usage.get('finish')} | {usage.get('gen')} |\n")

def next_round(root: Path) -> int:
    rs = [int(m.group(1)) for p in (root / "research/warroom").glob("round_*") if (m := re.match(r"round_(\d+)", p.name))]
    return (max(rs) + 1) if rs else 1

def context(root: Path, with_site: bool) -> str:
    parts = [
        "# BRIEF (the contract)\n" + read(root / "research/brief_v4.md"),
        "# HANDOFF (assets, API contracts, CSP, beacon, i18n keys)\n" + read(root / "research/sol_handoff.md"),
        "# PHOTO MANIFEST\n" + read(root / "site/assets/photos/manifest.json", 12000),
        "# CONTENT FIXTURE (positions + sutras, EN/FR)\n" + read(root / "research/content_fixture.json"),
        "# CSP (_headers)\n" + read(root / "site/_headers"),
        "# REFERENCE: what 'flow' felt like on a page the operator admires (teardown excerpt; inspiration, not copy)\n"
        + read(root / "research/warroom/reference_excerpt.md"),
    ]
    if with_site:
        for f in FILES:
            parts.append(f"# CURRENT FILE {f}\n```\n{read(root / f)}\n```")
    return "\n\n".join(parts)

AUTHOR_SYS = """You are a senior front-end engineer and designer in a two-lab war room (OpenAI + Anthropic) building a
production website for a yoga teacher in Paris. Output quality must make a senior UX/UI designer at Higgsfield say "wow":
editorial typography, real photographs in frames that look placed (never pasted), a living hairline backdrop, motion that
is restrained and 60 fps, flawless responsive behaviour, accessibility, and a CSP-clean static build (no CDN, no inline
scripts except JSON-LD, no frameworks). Follow the BRIEF as a contract; the HANDOFF gives the exact asset keys, API field
names, consent strings, CSP and beacon tag — use them verbatim. Never invent facts, prices, hours, credentials or reviews.
Never mention any other teacher. Return ONLY a JSON object: {"files": {"site/index.html": "...", "site/css/styles.css": "...",
"site/js/main.js": "...", "site/js/i18n.js": "..."}, "notes": "what you did and why, ≤ 200 words"}. Every file complete, no
placeholders, no truncation; `main.js` is one IIFE; `i18n.js` holds EN and FR dictionaries and the toggle."""

CRITIC_SYS = """You are a senior researcher-designer from the other lab in a two-lab war room. Review the current site
files against the BRIEF and HANDOFF as a picky senior UX/UI designer and a strict front-end lead would. Return a numbered
list, most important first, each item: [severity P1/P2/P3] [file:selector or line hint] what is wrong → the exact change.
Cover: does it make a senior designer say wow; photo treatment (placed, never pasted; no dark plates); backdrop behind/
beside not under; type never over the figure; hierarchy and rhythm; the twelve-breaths strip mechanics; responsive
390/1024/1440; motion restraint and reduced-motion; a11y (alt, focus, contrast ≥ 4.5:1); CSP compliance; API contract
and consent strings verbatim; i18n completeness; performance (lazy, srcset, weight); any invented fact. Also list the
3 things that are already excellent and must not be lost. ≤ 900 words. No code dumps longer than 6 lines."""

def write_files(root: Path, obj: dict) -> list[str]:
    out = []
    for f, content in obj.get("files", {}).items():
        if f not in FILES or not isinstance(content, str) or len(content) < 200:
            continue
        p = root / f; p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8", newline="\n"); out.append(f"{f} ({len(content)} B)")
    return out

def parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    return json.loads(text)

def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["draft", "critique", "revise", "status"])
    ap.add_argument("--by", choices=list(MODELS), default="sol")
    ap.add_argument("--notes", help="critique file(s) to apply, comma-separated")
    ap.add_argument("--extra", help="extra text file (gate output, eye-review defects)")
    ap.add_argument("--root", default=".")
    a = ap.parse_args()
    root = Path(a.root).resolve(); (root / "research/warroom").mkdir(parents=True, exist_ok=True)
    n = next_round(root); model = MODELS[a.by]
    if a.cmd == "status":
        print(read(root / "research/warroom/ledger.md")); return
    if a.cmd in ("draft", "revise"):
        user = context(root, with_site=(a.cmd == "revise"))
        if a.cmd == "revise":
            notes = "\n\n".join(read(root / p.strip()) for p in (a.notes or "").split(",") if p.strip())
            extra = read(Path(a.extra)) if a.extra else ""
            user += ("\n\n# CRITIQUE TO APPLY (apply every P1 and P2; P3 at your judgement; keep what is marked excellent)\n"
                     + notes + ("\n\n# GATE / EYE-REVIEW OUTPUT (fix every failure)\n" + extra if extra else "")
                     + "\n\nReturn ONLY the files you changed, each complete (unchanged files omitted). Keep the output compact: no comments longer than one line, no blank-line padding.")
        else:
            user += "\n\nWrite the first complete version now."
        text, usage = call(model, AUTHOR_SYS, user, max_tokens=120000, json_mode=True, effort=("medium" if a.cmd == "revise" else "high"))
        ledger(root, f"{n:02d} {a.cmd}", model, usage)
        try:
            obj = parse_json(text)
        except json.JSONDecodeError as e:
            (root / f"research/warroom/round_{n:02d}_{a.cmd}_{a.by}_RAW.txt").write_text(text, encoding="utf-8")
            sys.exit(f"model returned non-JSON ({e}); raw saved")
        written = write_files(root, obj)
        (root / f"research/warroom/round_{n:02d}_{a.cmd}_{a.by}.md").write_text(
            f"# Round {n} {a.cmd} by {model}\n\n{obj.get('notes','')}\n\nFiles: {', '.join(written)}\n\nUsage: {usage}\n", encoding="utf-8")
        print(f"round {n} {a.cmd} by {a.by}: {', '.join(written)} | {usage}")
    else:
        user = context(root, with_site=True)
        extra = read(Path(a.extra)) if a.extra else ""
        if extra:
            user += "\n\n# GATE / EYE-REVIEW OUTPUT (fold into your critique)\n" + extra
        text, usage = call(model, CRITIC_SYS, user, max_tokens=24000, json_mode=False, effort="medium")
        ledger(root, f"{n:02d} critique", model, usage)
        p = root / f"research/warroom/round_{n:02d}_critique_{a.by}.md"
        p.write_text(f"# Round {n} critique by {model}\n\n{text}\n", encoding="utf-8")
        print(f"round {n} critique by {a.by} -> {p.relative_to(root)} | {usage}")

if __name__ == "__main__":
    main()
