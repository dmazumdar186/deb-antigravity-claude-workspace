"""
description: Generate a Living PRD doc-ops plan from a script + word timings via Gemini Flash (default), GLM 5.2 (personal mode), or Sonnet 4.6 (client mode).
inputs:
    CLI:
        --script PATH        script.md (frontmatter stripped automatically; default: stdin if omitted)
        --words PATH         word timings JSON (provides audio_duration_sec)
        --topic "..."        topic one-liner (for fallback if script frontmatter lacks `topic`)
        --out PATH           output plan JSON (default: .tmp/prodcraft/living_prd_plan.json)
        --model NAME         Gemini model (default: gemini-2.5-flash; ignored unless --provider=gemini)
        --max-sections N     plan section count (default: 6)
        --provider NAME      gemini (default, free) | personal (GLM 5.2 via OR) | client (Sonnet 4.6 via Anthropic)
    env: GEMINI_API_KEY (gemini); OPENROUTER_API_KEY (personal); ANTHROPIC_API_KEY (client)
outputs:
    {out}                    JSON conforming to LivingPRDPlan schema in living-prd/types.ts
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = WORKSPACE_ROOT / ".tmp" / "prodcraft" / "living_prd_plan.json"

PLAN_SCHEMA = {
    "type": "object",
    "properties": {
        "doc_title": {"type": "string"},
        "doc_subtitle": {"type": "string"},
        "audio_duration_sec": {"type": "number"},
        "ops": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "t": {"type": "number"},
                    "op": {
                        "type": "string",
                        "enum": ["title_in", "add_section", "typewriter_lines", "highlight_section", "checklist"],
                    },
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "lines": {"type": "array", "items": {"type": "string"}},
                    "items": {"type": "array", "items": {"type": "string"}},
                    "body_style": {"type": "string", "enum": ["paragraph", "list", "checklist"]},
                    "end_t": {"type": "number"},
                },
                "required": ["t", "op"],
            },
        },
    },
    "required": ["doc_title", "audio_duration_sec", "ops"],
}


def _strip_frontmatter(text: str) -> tuple[str, dict]:
    if not text.startswith("---"):
        return text, {}
    end = text.find("\n---", 4)
    if end < 0:
        return text, {}
    fm_block = text[4:end]
    body = text[end + 4 :].lstrip("\n")
    fm = {}
    for line in fm_block.splitlines():
        m = re.match(r"^([\w_]+):\s*(.+)$", line.strip())
        if m:
            fm[m.group(1)] = m.group(2).strip()
    return body, fm


def _topic_to_subtitle(topic: str) -> str:
    t = topic.strip().rstrip(".")
    if len(t) > 80:
        t = t[:77] + "…"
    return t


def _build_prompt(script_body: str, audio_duration: float, topic: str, max_sections: int) -> str:
    return f"""You are designing a "Living PRD" visual plan for a ProdCraft educational YouTube video. The visual is a document that builds itself in real time, in lock-step with the narrator's voice.

TOPIC: {topic}
AUDIO DURATION: {audio_duration:.1f} seconds
TARGET SECTION COUNT: ~{max_sections} (intro title + body sections + closing CTA)

SCRIPT (this is what the narrator says, in order):
---
{script_body.strip()}
---

YOUR TASK: emit a doc-ops plan that drives the on-screen document.

CONSTRAINTS:
1. Output ONLY valid JSON matching the schema below. No prose, no markdown fences.
2. Exactly ONE `title_in` op at t=0.5 (sets doc_title).
3. Sections appear staggered 2-3 seconds BEFORE the narrator references them — never after.
4. Each `add_section` must be followed by a `typewriter_lines` op (same `id`) within 1-2 seconds.
5. Distribute section start times evenly across the audio duration so the document reveals smoothly. Leave the last ~5-8 seconds for the CTA section.
6. The CTA section must be a `checklist` with 2-3 short subscribe/like/comment lines.
7. Body styles: "paragraph" for prose explanations (1-3 short sentences), "list" for grouped points (3-5 items, each <60 chars), "checklist" for advice/rules/steps.
8. Each typewriter_lines op MUST include `end_t` = `t + (estimated_reveal_seconds)` where reveal speed is ~25 chars/sec.
9. Use 4-{max_sections} body sections, ordered to match the script's flow.
10. Keep doc_title short (≤55 chars). doc_subtitle is a 1-line tagline (≤80 chars).
11. Section ids are kebab-case short slugs (≤20 chars).

SCHEMA:
{json.dumps(PLAN_SCHEMA, indent=2)}

Emit the JSON now."""


def _gemini_generate(prompt: str, model: str) -> str:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing from environment")
    try:
        from google import genai
        from google.genai.types import GenerateContentConfig
        from google.genai import errors as genai_errors
    except ImportError as exc:
        raise SystemExit("Install: py -m pip install google-genai") from exc

    client = genai.Client(api_key=api_key)
    backoffs = [5, 20, 60]
    last_exc: Exception | None = None
    for attempt, delay in enumerate([0] + backoffs):
        if delay:
            import time
            print(f"  Gemini retry in {delay}s (attempt {attempt}/{len(backoffs)})...", file=sys.stderr)
            time.sleep(delay)
        try:
            resp = client.models.generate_content(
                model=model,
                contents=prompt,
                config=GenerateContentConfig(
                    response_mime_type="application/json",
                    temperature=0.6,
                ),
            )
            return resp.text
        except genai_errors.ServerError as exc:
            last_exc = exc
            continue
        except genai_errors.ClientError as exc:
            raise SystemExit(f"Gemini ClientError (not retried): {exc}") from exc
    raise SystemExit(f"Gemini failed after {len(backoffs)} retries: {last_exc}")


# JSON-mode for plan_gen requires precise op-level constraints. GLM / Sonnet don't have native
# response_mime_type, so we lean on the prompt itself + robust extraction (strip markdown fences).
_NON_GEMINI_SYSTEM = (
    "You are a precision JSON emitter. Return ONLY a single valid JSON object that conforms exactly "
    "to the schema given in the user prompt. No prose. No preamble. No markdown fences."
)


def _router_generate(prompt: str, provider: str) -> str:
    """Dispatch plan_gen to call_model (personal -> GLM 5.2, client -> Sonnet 4.6 via Anthropic)."""
    try:
        from execution.modules.model_router import call_model
    except ImportError:
        sys.path.insert(0, str(WORKSPACE_ROOT))
        from execution.modules.model_router import call_model

    mode = "personal" if provider == "personal" else "client"
    result = call_model(
        "sonnet",
        system=_NON_GEMINI_SYSTEM,
        user=prompt,
        max_tokens=4096,
        mode=mode,
        sensitivity="public",
    )
    print(f"  routed via {result['provider']} ({result['model']})", file=sys.stderr)
    return result["text"] or ""


def _llm_generate(prompt: str, model: str, provider: str) -> str:
    if provider == "gemini":
        return _gemini_generate(prompt, model)
    return _router_generate(prompt, provider)


def _validate_plan(plan: dict, audio_duration: float) -> None:
    if "doc_title" not in plan or "ops" not in plan:
        raise SystemExit("Plan missing doc_title or ops")
    if not plan["ops"]:
        raise SystemExit("Plan has zero ops")
    has_title = any(o.get("op") == "title_in" for o in plan["ops"])
    if not has_title:
        raise SystemExit("Plan missing title_in op")
    for op in plan["ops"]:
        if "t" not in op or "op" not in op:
            raise SystemExit(f"Op missing t or op field: {op}")
        if op["t"] > audio_duration + 1.0:
            raise SystemExit(f"Op t={op['t']} exceeds audio duration {audio_duration}")
        if op["op"] in ("typewriter_lines", "checklist") and "end_t" not in op:
            op["end_t"] = min(op["t"] + 10.0, audio_duration)


def generate_plan(script_path: Path, words_path: Path, topic: str, model: str, max_sections: int, provider: str = "gemini") -> dict:
    raw = script_path.read_text(encoding="utf-8")
    body, fm = _strip_frontmatter(raw)
    topic = topic or fm.get("topic") or "Untitled"
    words_data = json.loads(words_path.read_text(encoding="utf-8"))
    audio_duration = float(words_data.get("duration_sec") or 0)
    if audio_duration <= 0:
        raise SystemExit(f"words JSON has invalid duration_sec: {words_data.get('duration_sec')}")

    prompt = _build_prompt(body, audio_duration, topic, max_sections)
    raw_json = _llm_generate(prompt, model, provider)
    # Strip accidental ```json fences if any
    raw_json = re.sub(r"^\s*```(?:json)?\s*", "", raw_json)
    raw_json = re.sub(r"\s*```\s*$", "", raw_json)
    plan = json.loads(raw_json)
    plan["audio_duration_sec"] = audio_duration
    if "doc_subtitle" not in plan:
        plan["doc_subtitle"] = _topic_to_subtitle(topic)
    _validate_plan(plan, audio_duration)
    return plan


def main() -> int:
    p = argparse.ArgumentParser(description="Generate Living PRD doc-ops plan via Gemini.")
    p.add_argument("--script", required=True)
    p.add_argument("--words", required=True)
    p.add_argument("--topic", default="")
    p.add_argument("--out", default=str(DEFAULT_OUT))
    p.add_argument("--model", default="gemini-2.5-flash")
    p.add_argument("--max-sections", type=int, default=6)
    p.add_argument("--provider", default="gemini", choices=("gemini", "personal", "client"),
                   help="gemini (default, free) | personal (GLM 5.2 via OR) | client (Sonnet 4.6 via Anthropic).")
    args = p.parse_args()

    plan = generate_plan(
        Path(args.script).resolve(),
        Path(args.words).resolve(),
        args.topic,
        args.model,
        args.max_sections,
        args.provider,
    )
    out_path = Path(args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"ok": True, "out": str(out_path), "ops": len(plan["ops"]), "duration": plan["audio_duration_sec"]}, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
