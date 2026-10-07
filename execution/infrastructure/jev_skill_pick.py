#!/usr/bin/env python3
"""Jev skill picker -- RoboNuggets use case 9 ("Let Jev pick the right skill").

Same menu and same Jev `choice` call as the UserPromptSubmit router
(`jev_router.skills_menu()` / `classify()`); this CLI exists for manual picks and
benchmarking. Directive: directives/infrastructure/jev_skill_pick.md

  python3 execution/infrastructure/jev_skill_pick.py pick "make my inbox tidy" [--json]
      [--top-k 3] [--min-confidence 0.5]
  python3 execution/infrastructure/jev_skill_pick.py bench [--compare-llm] [--json]
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from execution.infrastructure import jev_router as R  # noqa: E402
from execution.modules import jev_client as jev  # noqa: E402

BENCH_PATH = PROJECT_ROOT / "execution" / "infrastructure" / "jev_specs" / "skill_bench.json"
LEDGER = PROJECT_ROOT / ".tmp" / "jev_ledger.jsonl"
CALLER = "jev_skill_pick"
BODY_CHARS = 800
LLM_MODEL = "anthropic/claude-sonnet-5.5"
LLM_CAP = 20
NONE_DESC = "No listed skill fits; the agent should work without loading a skill."
INSTR = ("Which workspace skill should the agent load first for this request? "
         "Pick 'none' unless a skill clearly matches the task.")


def skill_paths() -> dict[str, Path]:
    """Frontmatter name (or dir name) -> SKILL.md path."""
    out: dict[str, Path] = {}
    if not R.SKILLS_DIR.is_dir():
        return out
    for p in sorted(R.SKILLS_DIR.glob("*/SKILL.md")):
        try:
            head = p.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        out[R._frontmatter_field(head, "name") or p.parent.name] = p
    return out


def skill_path(name: str, paths: dict[str, Path] | None = None) -> str | None:
    if not name or name == "none":
        return None
    p = (paths if paths is not None else skill_paths()).get(name)
    if p is None:
        cand = (R.SKILLS_DIR / name / "SKILL.md").resolve()
        # Jev-supplied name: never resolve outside the skills dir.
        inside = cand.is_relative_to(R.SKILLS_DIR.resolve())
        p = cand if inside and cand.is_file() else None
    if p is None:
        return None
    return str(p.relative_to(PROJECT_ROOT)) if p.is_relative_to(PROJECT_ROOT) else str(p)


def skill_body(name: str, paths: dict[str, Path], chars: int = BODY_CHARS) -> str:
    p = paths.get(name)
    if not p:
        return ""
    try:
        text = p.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    text = R._FM_RE.sub("", text, count=1)
    return re.sub(r"\s+", " ", text).strip()[:chars]


def _top(probs: dict[str, float], k: int) -> list[tuple[str, float]]:
    return sorted(probs.items(), key=lambda kv: kv[1], reverse=True)[:k]


def _ask(prompt: str, options: dict[str, str]) -> jev.JevResult:
    return jev.decide({"user_prompt": prompt[:6000]}, {"skill": jev.choice(INSTR, options)}, timeout_s=15.0)


def pick(prompt: str, *, top_k: int = 3, min_conf: float = 0.5,
         menu: dict[str, str] | None = None, paths: dict[str, Path] | None = None) -> dict[str, Any]:
    """Stage 1: full menu. Stage 2 (only if conf < min_conf): shortlist with SKILL.md bodies."""
    menu = R.skills_menu() if menu is None else menu
    paths = skill_paths() if paths is None else paths
    options = {"none": NONE_DESC, **menu}
    t0 = time.perf_counter()
    r1 = _ask(prompt, options)
    probs = r1.probabilities("skill")
    out: dict[str, Any] = {
        "prompt": prompt, "skill": r1.choice("skill", "none"), "confidence": r1.confidence("skill"),
        "top5": _top(probs, 5), "stage1_skill": r1.choice("skill", "none"), "stage2": None,
        "shortlist": [], "cost": r1.cost_usd, "latency_ms": r1.latency_ms, "error": r1.error,
    }
    if r1.ok and out["confidence"] < min_conf and top_k > 1:
        shortlist = [n for n, _ in _top(probs, top_k)] or [out["skill"]]
        out["shortlist"] = shortlist
        opts2 = {n: (skill_body(n, paths) or options.get(n, n)) if n != "none" else NONE_DESC
                 for n in shortlist}
        if "none" not in opts2:
            opts2["none"] = NONE_DESC
        r2 = _ask(prompt, opts2)
        out["cost"] += r2.cost_usd
        if r2.ok:
            out["stage2"] = {"skill": r2.choice("skill", "none"), "confidence": r2.confidence("skill"),
                             "changed": r2.choice("skill", "none") != out["stage1_skill"]}
            out["skill"], out["confidence"] = out["stage2"]["skill"], out["stage2"]["confidence"]
    out["path"] = skill_path(out["skill"], paths)
    out["wall_ms"] = int((time.perf_counter() - t0) * 1000)
    jev.append_ledger({"caller": CALLER, "cost": out["cost"], "latency_ms": out["wall_ms"],
                       "error": out["error"]}, LEDGER)
    return out


# ---- bench ------------------------------------------------------------------------------

def score_bench(rows: list[dict[str, Any]]) -> dict[str, Any]:
    """rows: {expected, skill, top (list of names)} -> accuracy, top3 accuracy, mismatches."""
    n = len(rows)
    if not n:
        return {"n": 0, "accuracy": 0.0, "top3_accuracy": 0.0, "mismatches": []}
    hit = sum(1 for r in rows if r["skill"] == r["expected"])
    hit3 = sum(1 for r in rows if r["expected"] == r["skill"] or r["expected"] in (r.get("top") or [])[:3])
    mism = [r for r in rows if r["skill"] != r["expected"]]
    return {"n": n, "accuracy": hit / n, "top3_accuracy": hit3 / n, "mismatches": mism}


def load_bench(path: Path = BENCH_PATH) -> list[dict[str, str]]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def llm_pick(prompt: str, menu: dict[str, str]) -> str:
    import os
    os.environ.setdefault("OPENROUTER_API_KEY", jev.api_key())  # llm_client reads only this name
    from execution.modules.llm_client import chat_completion
    lines = "\n".join(f"- {k}: {v}" for k, v in {"none": NONE_DESC, **menu}.items())
    system = (f"{INSTR}\nSkills:\n{lines}\n\nReply with ONLY the skill name, exactly as listed.")
    raw = chat_completion(system, prompt, model=LLM_MODEL, max_tokens=20)
    ans = (raw or "").strip().strip("`'\" .").splitlines()[0] if raw else "none"
    return ans if ans in menu or ans == "none" else ans


def bench(compare_llm: bool = False, path: Path = BENCH_PATH) -> dict[str, Any]:
    cases = load_bench(path)
    menu, paths = R.skills_menu(), skill_paths()
    rows, cost, lat = [], 0.0, []
    t0 = time.perf_counter()
    for c in cases:
        r = pick(c["prompt"], menu=menu, paths=paths)
        rows.append({"prompt": c["prompt"], "expected": c["expected"], "skill": r["skill"],
                     "stage1_skill": r["stage1_skill"], "conf": r["confidence"],
                     "top": [n for n, _ in r["top5"]], "stage2": r["stage2"], "error": r["error"]})
        cost += r["cost"]
        lat.append(r["wall_ms"])
    wall = time.perf_counter() - t0
    s = score_bench(rows)
    s1 = score_bench([{**r, "skill": r["stage1_skill"]} for r in rows])
    rep: dict[str, Any] = {
        "menu_size": len(menu), "jev": {**s, "stage1_accuracy": s1["accuracy"],
        "stage2_runs": sum(1 for r in rows if r["stage2"]),
        "stage2_changed": sum(1 for r in rows if r["stage2"] and r["stage2"]["changed"]),
        "mean_latency_ms": int(sum(lat) / len(lat)) if lat else 0, "wall_s": round(wall, 2),
        "cost_usd": round(cost, 6), "errors": sum(1 for r in rows if r["error"])},
    }
    if compare_llm:
        if not jev.available():
            rep["llm"] = {"skipped": "no OpenRouter key"}
        else:
            lrows, t1 = [], time.perf_counter()
            try:
                for c in cases[:LLM_CAP]:
                    lrows.append({"prompt": c["prompt"], "expected": c["expected"],
                                  "skill": llm_pick(c["prompt"], menu), "top": []})
                ls = score_bench(lrows)
                rep["llm"] = {"model": LLM_MODEL, "n": ls["n"], "accuracy": ls["accuracy"],
                              "wall_s": round(time.perf_counter() - t1, 2), "mismatches": ls["mismatches"]}
            except Exception as exc:  # noqa: BLE001 -- comparison is optional; skip gracefully
                rep["llm"] = {"skipped": f"{exc.__class__.__name__}: {str(exc)[:200]}"}
    return rep


def _fmt_bench(rep: dict[str, Any]) -> str:
    j = rep["jev"]
    lines = [f"Menu: {rep['menu_size']} skills + none | cases: {j['n']}",
             f"Jev  accuracy {j['accuracy']:.0%} (stage1 {j['stage1_accuracy']:.0%}) | top-3 {j['top3_accuracy']:.0%}"
             f" | mean {j['mean_latency_ms']} ms | wall {j['wall_s']} s | cost ${j['cost_usd']:.5f}"
             f" | stage2 ran {j['stage2_runs']}, changed {j['stage2_changed']} | errors {j['errors']}"]
    llm = rep.get("llm")
    if llm:
        lines.append(f"LLM  skipped: {llm['skipped']}" if "skipped" in llm else
                     f"LLM  {llm['model']} accuracy {llm['accuracy']:.0%} | wall {llm['wall_s']} s ({llm['n']} calls)")
    lines += ["", "| prompt | expected | jev | conf |", "|---|---|---|---|"]
    lines += [f"| {m['prompt'][:50]} | {m['expected']} | {m['skill']} | {m['conf']:.2f} |" for m in j["mismatches"]]
    if llm and llm.get("mismatches"):
        lines += ["", "| prompt | expected | llm |", "|---|---|---|"]
        lines += [f"| {m['prompt'][:50]} | {m['expected']} | {m['skill']} |" for m in llm["mismatches"]]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv
        load_dotenv(PROJECT_ROOT / ".env")
    except ImportError:
        pass
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pick")
    p.add_argument("prompt")
    p.add_argument("--json", action="store_true")
    p.add_argument("--top-k", type=int, default=3)
    p.add_argument("--min-confidence", type=float, default=0.5)
    b = sub.add_parser("bench")
    b.add_argument("--compare-llm", action="store_true")
    b.add_argument("--json", action="store_true")
    b.add_argument("--spec", type=Path, default=BENCH_PATH)
    a = ap.parse_args(argv)
    if not jev.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    if a.cmd == "pick":
        r = pick(a.prompt, top_k=a.top_k, min_conf=a.min_confidence)
        if a.json:
            print(json.dumps(r, indent=2))
        elif r["error"]:
            print(f"error: {r['error']}", file=sys.stderr)
            return 1
        else:
            print(f"skill: {r['skill']}  confidence: {r['confidence']:.2f}  path: {r['path'] or '-'}")
            print("top5: " + ", ".join(f"{n}={pr:.2f}" for n, pr in r["top5"]))
            if r["shortlist"]:
                print(f"shortlist: {r['shortlist']}  stage2: {r['stage2']}")
        return 0
    rep = bench(a.compare_llm, a.spec)
    print(json.dumps(rep, indent=2) if a.json else _fmt_bench(rep))
    return 0


if __name__ == "__main__":
    sys.exit(main())
