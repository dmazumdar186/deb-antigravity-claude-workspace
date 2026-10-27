"""Jev router — one typed decision per prompt picks the model tier and the skill (Level 1).

description: UserPromptSubmit hook. Sends each prompt to Jev (TypeSafe decision model via
             OpenRouter) with two questions in ONE call: how much model capacity the task
             needs (tiny / bulk / standard / hard) and which workspace skill fits (menu built
             from .claude/skills/*/SKILL.md). Injects a short routing instruction as
             additionalContext. Fails open: any error, timeout or missing key means the prompt
             goes through untouched. Also the backend of the /jev command (on|off|status|test|pick).
inputs: stdin hook JSON {prompt, session_id}; .claude/jev/config.json (routes, thresholds);
        .claude/jev/state.json (enabled flag); env OPENROUTER_API_KEY.
outputs: hook JSON on stdout (hookSpecificOutput.additionalContext); .tmp/jev_router_log.jsonl;
         .tmp/jev_ledger.jsonl rows (caller=jev_router).

Usage:
    python3 execution/infrastructure/jev_router.py hook        # called by the hook (stdin JSON)
    python3 execution/infrastructure/jev_router.py on|off|status|test
    python3 execution/infrastructure/jev_router.py pick "find the file where the router lives"

Tiers (operator order 2026-10-06, Haiku banned):
    tiny     -> answer inline (main model, Fable 5.1)
    bulk     -> sub-agent on claude-sonnet-5-5
    standard -> sub-agent on claude-opus-5-5
    hard     -> inline (Fable 5.1)

See also: directives/infrastructure/jev.md
"""
from __future__ import annotations

import json
import re
import sys
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv  # noqa: E402

load_dotenv(PROJECT_ROOT / ".env")

from execution.modules import jev_client as jev  # noqa: E402

JEV_DIR = PROJECT_ROOT / ".claude" / "jev"
CONFIG_PATH = JEV_DIR / "config.json"
STATE_PATH = JEV_DIR / "state.json"
SKILLS_DIR = PROJECT_ROOT / ".claude" / "skills"
TMP = PROJECT_ROOT / ".tmp"
LOG_PATH = TMP / "jev_router_log.jsonl"
MENU_CACHE = TMP / "jev_skills_menu.json"

DEFAULT_CONFIG: dict[str, Any] = {
    "model": jev.JEV_MODEL,
    "timeout_ms": 2500,
    "min_confidence": 0.55,
    "skill_min_confidence": 0.5,
    "max_prompt_chars": 6000,
    "min_prompt_chars": 12,
    "skill_pick": True,
    "log_keep": 500,
    "routes": {
        "tiny": {"mode": "inline", "model": "claude-fable-5-1"},
        "bulk": {"mode": "subagent", "model": "claude-sonnet-5-5"},
        "standard": {"mode": "subagent", "model": "claude-opus-5-5"},
        "hard": {"mode": "inline", "model": "claude-fable-5-1"},
    },
}

TIER_CRITERIA = {
    "tiny": "A greeting, thanks, yes/no, or a one-line follow-up that needs no file access or reasoning.",
    "bulk": "Mechanical work: find a file or symbol, list or search things, reformat, rename, bulk per-row "
            "classification, copy or move content, run a known command and report output.",
    "standard": "Routine coding or writing from clear instructions: implement a described function or "
                "script, write a directive or doc, fix a clearly located bug, add a test, draft an email.",
    "hard": "Architecture, ambiguous requirements, subtle debugging, security or cost judgement, audits, "
            "multi-file refactors, anything where a wrong call is expensive.",
}

# Prompts that must never be routed.
_SKIP_PREFIXES = ("/", "!", "#")


# ---------------------------------------------------------------------------------------
# config / state
# ---------------------------------------------------------------------------------------

def _read_json(path: Path, default: dict[str, Any]) -> dict[str, Any]:
    try:
        return {**default, **json.loads(path.read_text(encoding="utf-8"))}
    except (OSError, ValueError):
        return dict(default)


def load_config() -> dict[str, Any]:
    cfg = _read_json(CONFIG_PATH, DEFAULT_CONFIG)
    cfg["routes"] = {**DEFAULT_CONFIG["routes"], **(cfg.get("routes") or {})}
    return cfg


def enabled() -> bool:
    return bool(_read_json(STATE_PATH, {"enabled": True}).get("enabled", True))


def set_enabled(flag: bool) -> None:
    JEV_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps({"enabled": flag, "changed": int(time.time())}) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------------------
# skills menu
# ---------------------------------------------------------------------------------------

_FM_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def _frontmatter_field(text: str, key: str) -> str:
    m = _FM_RE.match(text)
    if not m:
        return ""
    for line in m.group(1).splitlines():
        if line.startswith(key + ":"):
            return line.split(":", 1)[1].strip().strip("\"'")
    return ""


def skills_menu(max_desc: int = 220) -> dict[str, str]:
    """name -> description for every .claude/skills/*/SKILL.md (cached on mtime)."""
    if not SKILLS_DIR.is_dir():
        return {}
    paths = sorted(SKILLS_DIR.glob("*/SKILL.md"))
    stamp = max((p.stat().st_mtime for p in paths), default=0.0)
    try:
        cached = json.loads(MENU_CACHE.read_text(encoding="utf-8"))
        if cached.get("stamp") == stamp and cached.get("count") == len(paths):
            return cached["menu"]
    except (OSError, ValueError, KeyError):
        pass
    menu: dict[str, str] = {}
    for p in paths:
        try:
            text = p.read_text(encoding="utf-8", errors="replace")[:4000]
        except OSError:
            continue
        if "disable-model-invocation: true" in text:
            continue
        name = _frontmatter_field(text, "name") or p.parent.name
        desc = _frontmatter_field(text, "description") or ""
        desc = re.sub(r"\s+", " ", desc)[:max_desc]
        menu[name] = desc or name
    try:
        TMP.mkdir(exist_ok=True)
        MENU_CACHE.write_text(json.dumps({"stamp": stamp, "count": len(paths), "menu": menu}), encoding="utf-8")
    except OSError:
        pass
    return menu


# ---------------------------------------------------------------------------------------
# the decision
# ---------------------------------------------------------------------------------------

def classify(prompt: str, cfg: dict[str, Any] | None = None, *, with_skill: bool | None = None,
             session_id: str | None = None) -> dict[str, Any]:
    """One Jev call -> {tier, tier_conf, skill, skill_conf, cost, latency_ms, error}."""
    cfg = cfg or load_config()
    with_skill = cfg.get("skill_pick", True) if with_skill is None else with_skill
    questions: dict[str, Any] = {
        "tier": jev.choice("How much model capacity does this request to a coding agent need?", TIER_CRITERIA),
    }
    menu = skills_menu() if with_skill else {}
    if menu:
        options = {"none": "No listed skill fits; the agent should work without loading a skill."}
        options.update(menu)
        questions["skill"] = jev.choice(
            "Which workspace skill should the agent load first for this request? "
            "Pick 'none' unless a skill clearly matches the task.", options)
    res = jev.decide(
        {"user_prompt": prompt[: int(cfg.get("max_prompt_chars", 6000))]},
        questions,
        model=cfg.get("model", jev.JEV_MODEL),
        timeout_s=float(cfg.get("timeout_ms", 2500)) / 1000.0,
        session_id=session_id,
    )
    out: dict[str, Any] = {
        "tier": res.choice("tier", ""),
        "tier_conf": res.confidence("tier"),
        "tier_probs": res.probabilities("tier"),
        "skill": res.choice("skill", "none") if menu else "none",
        "skill_conf": res.confidence("skill") if menu else 0.0,
        "cost": res.cost_usd,
        "input_tokens": res.input_tokens,
        "latency_ms": res.latency_ms,
        "error": res.error,
    }
    return out


def routing_context(decision: dict[str, Any], cfg: dict[str, Any]) -> str:
    """Turn a decision into the short instruction injected into the agent's context."""
    if decision.get("error") or not decision.get("tier"):
        return ""
    lines: list[str] = []
    tier = decision["tier"]
    conf = float(decision.get("tier_conf", 0.0))
    route = cfg["routes"].get(tier, {})
    skill = decision.get("skill", "none")
    sconf = float(decision.get("skill_conf", 0.0))
    skill_hit = bool(skill and skill != "none" and sconf >= float(cfg.get("skill_min_confidence", 0.5)))
    if conf >= float(cfg.get("min_confidence", 0.55)) and route:
        if skill_hit:
            lines.append(
                f"[jev] Task tier: {tier} (confidence {conf:.2f}). Follow the matched skill; run its heavy "
                f"steps through sub-agents on `{route['model']}` where the skill delegates.")
        elif route.get("mode") == "subagent":
            lines.append(
                f"[jev] Task tier: {tier} (confidence {conf:.2f}). Delegate the work to ONE sub-agent with "
                f"model `{route['model']}` and a complete brief; keep only its conclusion in this context. "
                f"Stay inline only if the task needs your judgement after all.")
        else:
            lines.append(f"[jev] Task tier: {tier} (confidence {conf:.2f}). Handle inline on `{route.get('model', 'the main model')}`.")
    else:
        lines.append(f"[jev] Task tier unclear ({tier} at {conf:.2f}); use your own judgement on delegation.")
    if skill_hit:
        lines.append(f"[jev] Skill match: `{skill}` (confidence {sconf:.2f}). Load it with the Skill tool before working.")
    return "\n".join(lines)


def _log(row: dict[str, Any], cfg: dict[str, Any]) -> None:
    """Append one routing decision. Trimming happens in `status`, never in the hook path (no races)."""
    try:
        TMP.mkdir(exist_ok=True)
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps({"ts": int(time.time()), **row}, ensure_ascii=False) + "\n")
    except OSError as exc:
        print(f"jev log skipped: {exc}", file=sys.stderr)


def _trim_log(cfg: dict[str, Any]) -> None:
    try:
        keep = int(cfg.get("log_keep", 500))
        lines = LOG_PATH.read_text(encoding="utf-8").splitlines()
        if len(lines) > keep * 2:
            LOG_PATH.write_text("\n".join(lines[-keep:]) + "\n", encoding="utf-8")
    except OSError:
        return


# ---------------------------------------------------------------------------------------
# hook entry
# ---------------------------------------------------------------------------------------

def run_hook(stdin_text: str) -> str:
    """Return the JSON the hook prints. Empty string = pass through untouched."""
    if not enabled() or not jev.available():
        return ""
    try:
        payload = json.loads(stdin_text or "{}")
    except ValueError:
        return ""
    prompt = str(payload.get("prompt", "")).strip()
    cfg = load_config()
    if len(prompt) < int(cfg.get("min_prompt_chars", 12)) or prompt.startswith(_SKIP_PREFIXES):
        return ""
    decision = classify(prompt, cfg, session_id=str(payload.get("session_id") or "") or None)
    _log({"prompt": prompt[:120], **{k: v for k, v in decision.items() if k != "tier_probs"}}, cfg)
    jev.append_ledger({"caller": "jev_router", "cost": decision["cost"], "input_tokens": decision["input_tokens"],
                       "latency_ms": decision["latency_ms"], "tier": decision["tier"], "skill": decision["skill"]},
                      TMP / "jev_ledger.jsonl")
    ctx = routing_context(decision, cfg)
    if not ctx:
        return ""
    return json.dumps({"hookSpecificOutput": {"hookEventName": "UserPromptSubmit", "additionalContext": ctx}})


# ---------------------------------------------------------------------------------------
# /jev command backend
# ---------------------------------------------------------------------------------------

def status_text() -> str:
    rows: list[dict[str, Any]] = []
    try:
        for line in LOG_PATH.read_text(encoding="utf-8").splitlines():
            try:
                rows.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    tiers: dict[str, int] = {}
    skills: dict[str, int] = {}
    cost = 0.0
    lat: list[int] = []
    errors = 0
    for r in rows:
        tiers[r.get("tier") or "?"] = tiers.get(r.get("tier") or "?", 0) + 1
        if r.get("skill") and r["skill"] != "none":
            skills[r["skill"]] = skills.get(r["skill"], 0) + 1
        cost += float(r.get("cost") or 0.0)
        if r.get("latency_ms"):
            lat.append(int(r["latency_ms"]))
        if r.get("error"):
            errors += 1
    cfg = load_config()
    _trim_log(cfg)
    out = [
        f"jev router: {'ON' if enabled() else 'OFF'}  key: {'present' if jev.available() else 'MISSING'}  model: {cfg.get('model')}",
        "routes: " + ", ".join(f"{k}->{v['model']}({v['mode']})" for k, v in cfg["routes"].items()),
        f"skills in menu: {len(skills_menu())}  skill_pick: {cfg.get('skill_pick', True)}",
        f"decisions logged: {len(rows)}  errors: {errors}  total cost: ${cost:.5f}  "
        f"median latency: {sorted(lat)[len(lat)//2] if lat else 0} ms",
        f"tiers: {tiers}",
        f"skills picked: {dict(sorted(skills.items(), key=lambda kv: -kv[1])[:8])}",
    ]
    return "\n".join(out)


_TEST_PROMPTS = [
    "thanks, that works",
    "find the file path where the jev router script lives",
    "rename every occurrence of fetch_leads to load_leads across execution/",
    "write a directive for the new ad tagger script following the template",
    "add a --limit flag to jev_sheet_categorize.py and a test for it",
    "the enrichment pipeline silently drops 20% of rows on Windows only, figure out why",
    "design how we should split the gaia sourcing pipeline into stages with retries",
    "label my gmail inbox into action required / waiting on / reference",
    "find viral youtube videos in the b2b lead gen niche from the last 30 days",
    "scrape 200 dental clinics in Austin from google maps with emails",
]


def run_test() -> str:
    cfg = load_config()
    lines = []
    t0 = time.perf_counter()
    cost = 0.0
    for p in _TEST_PROMPTS:
        d = classify(p, cfg)
        cost += d["cost"]
        lines.append(f"{d['tier']:<8} {d['tier_conf']:.2f}  skill={d['skill']:<24} {d['skill_conf']:.2f}  "
                     f"{d['latency_ms']:>4}ms  {p[:60]}" + (f"  ERR {d['error']}" if d['error'] else ""))
    lines.append(f"-- {len(_TEST_PROMPTS)} prompts, {time.perf_counter()-t0:.1f}s, ${cost:.5f}")
    return "\n".join(lines)


def main(argv: list[str]) -> int:
    cmd = (argv[0] if argv else "status").lower()
    if cmd == "hook":
        sys.stdout.write(run_hook(sys.stdin.read()))
        return 0
    if cmd == "on":
        set_enabled(True)
        print("jev router ON — every prompt is now routed (tier + skill) by Jev.")
        return 0
    if cmd == "off":
        set_enabled(False)
        print("jev router OFF — prompts pass through untouched (use for confidential work).")
        return 0
    if cmd == "status":
        print(status_text())
        return 0
    if cmd == "test":
        print(run_test())
        return 0
    if cmd == "pick":
        d = classify(" ".join(argv[1:]), load_config())
        print(json.dumps(d, indent=2))
        print(routing_context(d, load_config()))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except Exception as exc:  # the hook must never block a prompt
        if (sys.argv[1:2] or [""])[0] == "hook":
            print(f"jev_router hook error (fail-open): {exc}", file=sys.stderr)
            sys.exit(0)
        print(f"jev_router error: {exc}", file=sys.stderr)
        sys.exit(1)
