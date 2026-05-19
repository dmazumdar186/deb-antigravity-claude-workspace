"""
description: Strip AI-tells from text and rewrite it in a personal voice profile.
             Four-stage pipeline: deterministic pre-pass (free) -> voice profile lookup
             (free) -> LLM rewrite via OpenRouter/Anthropic tool-use (cheap) ->
             platform post-processing. Supports linkedin, email, slack, tweet, generic.
inputs:
  - --text <str>      direct text input (mutually exclusive with --file; stdin if neither)
  - --file <path>     read input from a file
  - --voice <name>    voice profile name (default: debanjan)
  - --platform <name> linkedin|email|slack|tweet|generic (default: generic)
  - --max-length <n>  character cap (tweet defaults to 280)
  - --show-diff       print before/after to stderr
  - --keep-em-dashes  skip em-dash replacement
  - --tier <name>     default|premium|gemini (default: default)
  - --dry-run         skip LLM, show pre-pass output + cost estimate
  - Env: OPENROUTER_API_KEY (preferred), ANTHROPIC_API_KEY (fallback), GEMINI_API_KEY (for gemini tier free path)
outputs:
  - stdout: humanized text
  - stderr: log lines, cost estimate (dry-run), before/after diff (--show-diff)
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

# Fix Unicode crash on Windows cp1252 before any other output
try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

from dotenv import load_dotenv

load_dotenv()

# ---------------------------------------------------------------------------
# Module-level import: model_registry — support running from workspace root
# ---------------------------------------------------------------------------
try:
    from execution.modules.model_registry import resolve_model
except ImportError:
    _workspace_root = Path(__file__).resolve().parents[2]
    if str(_workspace_root) not in sys.path:
        sys.path.insert(0, str(_workspace_root))
    try:
        from execution.modules.model_registry import resolve_model
    except ImportError:
        _mod_path = Path(__file__).resolve().parents[1] / "modules"
        if str(_mod_path) not in sys.path:
            sys.path.insert(0, str(_mod_path))
        from model_registry import resolve_model

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s")
log = logging.getLogger("humanizer")

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
WORKSPACE_ROOT = Path(__file__).resolve().parents[2]
VOICES_DIR = Path(__file__).resolve().parent / "voices"
MAX_INPUT_CHARS = 5000
DEFAULT_VOICE = "debanjan"

# ---------------------------------------------------------------------------
# Regex AI-tell patterns
# ---------------------------------------------------------------------------
RE_OPENING_FLUFF = re.compile(
    r"^(Certainly!?|Absolutely!?|Great question!?|Sure!|Of course!?|"
    r"I['‘’]d be happy to[^.!]{0,40}[.!]|Happy to help!?)\s*",  # R10-1: bound to 40 chars; include straight apostrophe
    re.IGNORECASE,
)
RE_CLOSING_FLUFF = re.compile(
    r"\s*(I hope this helps!?|Let me know if (you )?(have any )?questions[^.!]{0,60}[.!]?|Hope that helps!?|Feel free to[^.!]{0,60}[.!])$",  # R10-1: bound to 60 chars
    re.IGNORECASE,
)
RE_EM_DASH = re.compile(r"\s*[—–]\s*")
# Three-clause: "not just X, but Y, and even Z" / "...but Y, but also Z"
RE_TRIPLE_PARALLEL = re.compile(
    r"not just[^,.]+,\s*but[^,.]+?,\s*(?:and even|but also)[^,.]+",
    re.IGNORECASE,
)
# Two-clause "not just X but also Y" (comma optional)
RE_TWO_PART_BUT_ALSO = re.compile(
    r"not just[^,.]+(?:,\s*|\s+)but also[^,.]+",
    re.IGNORECASE,
)
RE_HEDGES = re.compile(
    r"\b(it's worth noting|generally speaking|broadly speaking|perhaps|arguably)\b",
    re.IGNORECASE,
)

DEFAULT_BANNED_VOCAB = [
    "delve", "leverage", "robust", "comprehensive", "key takeaways",
    "in conclusion", "absolutely", "let's dive in", "navigate the complexities",
    "in today's world", "game-changer", "synergy", "elevate", "unlock",
]

# ---------------------------------------------------------------------------
# Tool-use schema (OpenAI function format — used for OR and Anthropic direct)
# ---------------------------------------------------------------------------
TOOL_SCHEMA = {
    "type": "function",
    "function": {
        "name": "submit_humanized",
        "description": "Submit the humanized rewrite of the input text.",
        "parameters": {
            "type": "object",
            "required": ["humanized_text"],
            "properties": {
                "humanized_text": {
                    "type": "string",
                    "description": (
                        "The rewritten text in the target voice, with all AI-tells "
                        "removed and meaning preserved."
                    ),
                }
            },
        },
    },
}

# ---------------------------------------------------------------------------
# Fix 14: Tool format helpers
# TOOL_SCHEMA above is OpenAI-native ({"type": "function", "function": {...}}).
# _to_anthropic_tool_format converts it to Anthropic format for the direct path.
# ---------------------------------------------------------------------------

def _to_anthropic_tool_format(schema: dict) -> dict:
    """Convert OpenAI-native TOOL_SCHEMA to Anthropic tool format."""
    fn = schema["function"]
    return {
        "name": fn["name"],
        "description": fn["description"],
        "input_schema": fn["parameters"],
    }


# ---------------------------------------------------------------------------
# Tier pricing for cost estimation — separate input/output prices (USD per million tokens)
# ---------------------------------------------------------------------------
_TIER_COST_PER_M = {
    "default":  {"input": 3.0,  "output": 15.0},   # Sonnet-class
    "premium":  {"input": 5.0,  "output": 25.0},   # Opus-class
    "gemini":   {"input": 0.0,  "output": 0.0},    # Free tier
}


# ---------------------------------------------------------------------------
# Voice loader
# ---------------------------------------------------------------------------

def load_voice(voice_name: str) -> dict:
    """Load voice profile from voices/{name}.json. Raises SystemExit if not found."""
    voice_path = VOICES_DIR / f"{voice_name}.json"
    # Fix 2: Sandbox — ensure path stays inside VOICES_DIR (prevent ../traversal)
    try:
        voice_path_resolved = voice_path.resolve()
        if not voice_path_resolved.is_relative_to(VOICES_DIR.resolve()):
            raise SystemExit(f"Invalid voice name: {voice_name!r}")
    except (OSError, ValueError):
        raise SystemExit(f"Invalid voice name: {voice_name!r}")
    if not voice_path.exists():
        available = [p.stem for p in VOICES_DIR.glob("*.json") if not p.stem.startswith("_")]
        raise SystemExit(
            f"Voice profile '{voice_name}' not found at {voice_path}.\n"
            f"Available voices: {available or ['(none yet)']}\n"
            f"Create one by copying {VOICES_DIR / '_template.json'} and filling it in."
        )
    try:
        voice = json.loads(voice_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Voice profile '{voice_name}' is invalid JSON: {exc}") from exc
    # Fix 9: Warn on empty examples
    if not voice.get("examples"):
        log.warning("Voice profile '%s' has no examples — output quality will be lower", voice_name)
    return voice


# ---------------------------------------------------------------------------
# Fix 6: Triple-bullet-then-summary detector
# ---------------------------------------------------------------------------

def _detect_bullet_dump(text: str) -> bool:
    """Returns True if text has 3+ consecutive bullets followed by a summary sentence."""
    lines = text.split("\n")
    bullet_pat = re.compile(r"^\s*(?:[-*•]|\d+[.)])\s+")
    streak = 0
    for line in lines:
        if bullet_pat.match(line):
            streak += 1
        else:
            stripped = line.strip()
            if streak >= 3 and stripped and not bullet_pat.match(line):
                return True
            if not stripped:
                continue  # blank lines don't reset streak
            streak = 0
    return False


# ---------------------------------------------------------------------------
# Stage 1: Deterministic pre-pass
# ---------------------------------------------------------------------------

def _rules_pre_pass(
    text: str, voice: dict, keep_em_dashes: bool = False
) -> tuple[str, list[str]]:
    """
    Deterministic pre-cleanup. Returns (cleaned_text, flags).

    Strips opening/closing fluff, replaces em-dashes (unless keep_em_dashes),
    flags banned vocab + parallel structures + hedges for the LLM to address.
    Does NOT auto-replace banned vocab (could lose meaning).
    """
    if not text.strip():
        return text, []

    flags: list[str] = []
    cleaned = text

    # Strip opening fluff (loop: handle "Certainly! I'd be happy to..." chained openers)
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = RE_OPENING_FLUFF.sub("", cleaned)

    # Strip closing fluff (loop for chained closers)
    prev = None
    while prev != cleaned:
        prev = cleaned
        cleaned = RE_CLOSING_FLUFF.sub("", cleaned)

    # Em-dash replacement
    if not keep_em_dashes:
        cleaned = RE_EM_DASH.sub(" - ", cleaned)

    # Build combined banned vocab list (voice + defaults).
    # Guard against malformed voice JSON where "lexicon" is explicitly null
    # (JSON null becomes Python None, breaking the default-{} pattern).
    avoids = (voice.get("lexicon") or {}).get("avoids", []) or []
    combined_banned = list({*DEFAULT_BANNED_VOCAB, *avoids})

    # Flag banned vocab (case-insensitive word boundary)
    for word in combined_banned:
        pattern = re.compile(r'\b' + re.escape(word) + r'\b', re.IGNORECASE)
        if pattern.search(cleaned):
            flags.append(f"banned-vocab: '{word}'")

    # Flag triple-parallel structures (Fix 4: also catches two-part "but also")
    if RE_TRIPLE_PARALLEL.search(cleaned):
        flags.append("triple-parallel: 'not just X, but Y, and even Z' pattern detected")
    if RE_TWO_PART_BUT_ALSO.search(cleaned):
        flags.append("two-part-parallel: 'not just X but also Y' pattern detected")

    # Fix 6: Flag triple-bullet-then-summary structure
    if _detect_bullet_dump(cleaned):
        flags.append("triple-bullet-then-summary structure detected — consider replacing with flowing prose")

    # Flag hedges
    hedge_matches = RE_HEDGES.findall(cleaned)
    for match in set(m.lower() for m in hedge_matches):
        flags.append(f"hedge: '{match}'")

    return cleaned.strip(), flags


# ---------------------------------------------------------------------------
# Stage 2: Build LLM prompt
# ---------------------------------------------------------------------------

def _build_humanize_prompt(
    text: str, voice: dict, flags: list[str], platform: str
) -> tuple[str, str]:
    """Build (system_prompt, user_prompt) for the LLM call."""

    system_prompt = (
        "You are a writing-style editor. Your job is to rewrite text so it sounds like "
        "it was written by the person described in the voice profile below.\n\n"
        "STRICT RULES:\n"
        "1. Keep ALL meaning. Never add new claims or facts not in the original.\n"
        "2. Remove every flagged AI-tell phrase. They should not appear in the output.\n"
        "3. Match the sentence cadence shown in the examples. Short = short. "
        "Direct = direct. Do not pad or soften.\n"
        "4. Do not use words in the 'avoids' list.\n"
        "5. Do not start with a greeting or sign-off.\n"
        "6. Do not add transition phrases like 'In essence' or 'To summarize'.\n"
        "7. You MUST call submit_humanized exactly once with the rewritten text.\n"
        "8. CRITICAL — examples in the voice profile are STYLE REFERENCES ONLY. "
        "Do NOT copy, paraphrase, or blend their content into the output. "
        "The output must be a rewrite of the TEXT TO HUMANIZE, not a remix of example sentences.\n"
    )

    platform_note = {
        "linkedin": "Platform: LinkedIn post. Strip markdown formatting (**bold**, # headings). Keep bullets as prose sentences.",
        "slack": "Platform: Slack message. Strip markdown except *italic* and `code`. Casual tone.",
        "tweet": "Platform: Tweet. Hard 280-character cap. Be very concise.",
        "email": "Platform: Email. Preserve paragraph structure and any numbered lists.",
        "generic": "Platform: generic. Minimal formatting changes.",
    }.get(platform, "Platform: generic.")

    user_prompt = (
        f"=== VOICE PROFILE ===\n{json.dumps(voice, ensure_ascii=False, indent=2)}\n\n"
        f"=== AI-TELL FLAGS (address all of these) ===\n"
        + (
            "\n".join(f"- {f}" for f in flags) if flags else "(none detected in pre-pass)"
        )
        + f"\n\n=== PLATFORM NOTE ===\n{platform_note}\n\n"
        f"=== TEXT TO HUMANIZE ===\n{text}\n\n"
        "Call submit_humanized exactly once with the rewritten text."
    )

    return system_prompt, user_prompt


# ---------------------------------------------------------------------------
# Stage 3: LLM call
# ---------------------------------------------------------------------------

def _auto_detect_provider(tier: str) -> str:
    """Pick provider based on tier + which env vars are set."""
    has_or = bool(os.environ.get("OPENROUTER_API_KEY"))
    has_anthropic = bool(os.environ.get("ANTHROPIC_API_KEY"))
    has_gemini = bool(os.environ.get("GEMINI_API_KEY"))

    if tier == "gemini":
        if has_gemini:
            return "gemini-direct"
        if has_or:
            log.warning(
                "GEMINI_API_KEY not set -- routing --tier gemini via OpenRouter (PAID). "
                "Add GEMINI_API_KEY to .env for the free path."
            )
            return "openrouter"
        raise SystemExit(
            "--tier gemini requires GEMINI_API_KEY (free) or OPENROUTER_API_KEY (paid) in .env"
        )

    # default / premium
    if has_or:
        return "openrouter"
    if has_anthropic:
        return "anthropic"
    raise SystemExit(
        "--tier default/premium requires OPENROUTER_API_KEY (preferred) or ANTHROPIC_API_KEY in .env"
    )


def _call_llm_humanize(
    system: str, user_msg: str, tier: str, dry_run: bool = False
) -> str:
    """
    Call the LLM via OpenRouter (OpenAI SDK) or Anthropic direct with tool-use.
    Forces submit_humanized. Returns the humanized text string.
    On dry_run, returns a stub + estimated cost printed to stderr.
    """
    if dry_run:
        estimated_input_tokens = (len(system) + len(user_msg)) // 4 + 200
        prices = _TIER_COST_PER_M.get(tier, {"input": 5.0, "output": 25.0})
        # Fix 10: separate input/output pricing; estimate ~200 output tokens
        estimated_cost_usd = (
            estimated_input_tokens * prices["input"] + 200 * prices["output"]
        ) / 1_000_000
        log.info(
            "[dry-run] Estimated tokens: ~%d in, ~200 out | Cost: ~$%.5f",
            estimated_input_tokens,
            estimated_cost_usd,
        )
        return "[DRY-RUN: LLM call skipped]"

    provider = _auto_detect_provider(tier)
    log.info("Provider: %s | Tier: %s", provider, tier)

    # ---------------------------------------------------------------------------
    # OpenRouter path (OpenAI SDK compat)
    # ---------------------------------------------------------------------------
    if provider == "openrouter":
        from openai import OpenAI

        model_id = resolve_model("openrouter", tier if tier != "gemini" else "gemini",
                                  allow_network=True)
        log.info("Model: %s", model_id)

        client = OpenAI(
            api_key=os.environ["OPENROUTER_API_KEY"],
            base_url="https://openrouter.ai/api/v1",
        )

        # Fix 1: wrap API call in try/except
        try:
            response = client.chat.completions.create(
                model=model_id,
                max_tokens=2048,
                messages=[
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_msg},
                ],
                tools=[TOOL_SCHEMA],
                tool_choice={"type": "function", "function": {"name": "submit_humanized"}},
            )
        except Exception as exc:
            msg = str(exc)
            if "sk-or-v" in msg or "sk-ant-" in msg or "AIza" in msg:
                msg = "[redacted credentials]"
            raise SystemExit(f"OpenRouter API call failed: {msg[:200]}")

        # Fix 10: separate input/output pricing
        if response.usage:
            in_tok = response.usage.prompt_tokens or 0
            out_tok = response.usage.completion_tokens or 0
            prices = _TIER_COST_PER_M.get(tier, {"input": 5.0, "output": 25.0})
            cost = (in_tok * prices["input"] + out_tok * prices["output"]) / 1_000_000
            log.info(
                "Tokens: %d in + %d out = %d total | Est. cost: $%.5f",
                in_tok, out_tok, in_tok + out_tok, cost,
            )

        # Parse tool call — Fix 1: wrap JSON parse
        choice = response.choices[0]
        tool_calls = getattr(choice.message, "tool_calls", None) or []
        for tc in tool_calls:
            if tc.function.name == "submit_humanized":
                try:
                    args = json.loads(tc.function.arguments)
                except json.JSONDecodeError as exc:
                    raise SystemExit(f"LLM returned malformed tool_call JSON: {exc}")
                return args["humanized_text"]

        # Fallback: content
        content = choice.message.content or ""
        if content.strip():
            log.warning("Tool call not found in response; using raw content as fallback")
            return content.strip()
        raise RuntimeError("LLM returned empty response with no tool call")

    # ---------------------------------------------------------------------------
    # Anthropic direct path
    # ---------------------------------------------------------------------------
    elif provider == "anthropic":
        import anthropic

        model_id = resolve_model("anthropic", tier if tier in ("default", "premium") else "default",
                                  allow_network=True)
        log.info("Model: %s", model_id)

        client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

        # Fix 14: use _to_anthropic_tool_format helper (TOOL_SCHEMA is OpenAI-native)
        anthropic_tool = _to_anthropic_tool_format(TOOL_SCHEMA)

        # Fix 1: wrap API call in try/except
        try:
            response = client.messages.create(
                model=model_id,
                max_tokens=2048,
                system=system,
                messages=[{"role": "user", "content": user_msg}],
                tools=[anthropic_tool],
                tool_choice={"type": "tool", "name": "submit_humanized"},
            )
        except Exception as exc:
            msg = str(exc)
            if "sk-or-v" in msg or "sk-ant-" in msg or "AIza" in msg:
                msg = "[redacted credentials]"
            raise SystemExit(f"Anthropic API call failed: {msg[:200]}")

        # Fix 10: separate input/output pricing (Anthropic SDK: input_tokens/output_tokens)
        usage = response.usage
        if usage:
            in_tok = getattr(usage, "input_tokens", 0) or 0
            out_tok = getattr(usage, "output_tokens", 0) or 0
            prices = _TIER_COST_PER_M.get(tier, {"input": 5.0, "output": 25.0})
            cost = (in_tok * prices["input"] + out_tok * prices["output"]) / 1_000_000
            log.info(
                "Tokens: %d in + %d out = %d total | Est. cost: $%.5f",
                in_tok, out_tok, in_tok + out_tok, cost,
            )

        # Parse tool use block — Fix 1: tool_call JSON handled via block.input (dict, no JSON parse needed)
        for block in response.content:
            if getattr(block, "type", None) == "tool_use" and block.name == "submit_humanized":
                return block.input["humanized_text"]

        # Fallback: text block
        for block in response.content:
            if getattr(block, "type", None) == "text" and block.text.strip():
                log.warning("Tool use not found; using text block as fallback")
                return block.text.strip()

        raise RuntimeError("Anthropic returned empty response with no tool use block")

    # ---------------------------------------------------------------------------
    # Gemini direct path (for --tier gemini with GEMINI_API_KEY)
    # ---------------------------------------------------------------------------
    elif provider == "gemini-direct":
        from google import genai
        from google.genai import types as gtypes

        model_id = resolve_model("gemini", "default", allow_network=True)
        log.info("Model: %s (gemini-direct)", model_id)

        client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])

        gemini_tool = gtypes.Tool(
            function_declarations=[
                gtypes.FunctionDeclaration(
                    name="submit_humanized",
                    description=TOOL_SCHEMA["function"]["description"],
                    parameters=TOOL_SCHEMA["function"]["parameters"],
                )
            ]
        )

        # R6-1: use system_instruction param — do NOT concatenate system+user
        # into a single string. Concatenation caused Gemini to echo system-prompt
        # fragments (e.g. "submit_humanized", "rewrite text in voice") as output.
        try:
            response = client.models.generate_content(
                model=model_id,
                contents=user_msg,  # user input only
                config=gtypes.GenerateContentConfig(
                    system_instruction=system,  # system prompt via proper channel
                    tools=[gemini_tool],
                    tool_config=gtypes.ToolConfig(
                        function_calling_config=gtypes.FunctionCallingConfig(
                            mode=gtypes.FunctionCallingConfigMode.ANY,
                            allowed_function_names=["submit_humanized"],
                        )
                    ),
                ),
            )
        except Exception as exc:
            msg = str(exc)
            if "sk-or-v" in msg or "sk-ant-" in msg or "AIza" in msg:
                msg = "[redacted credentials]"
            raise SystemExit(f"Gemini API call failed: {msg[:200]}")

        # R2-3: log token usage + cost (Gemini usage_metadata)
        try:
            in_tok = response.usage_metadata.prompt_token_count
            out_tok = response.usage_metadata.candidates_token_count
        except (AttributeError, TypeError):
            in_tok = out_tok = 0
        prices = _TIER_COST_PER_M.get(tier, {"input": 0.0, "output": 0.0})
        cost = (in_tok * prices["input"] + out_tok * prices["output"]) / 1_000_000
        log.info(
            "Gemini usage: input=%d, output=%d tokens (~$%.4f, FREE tier)",
            in_tok, out_tok, cost,
        )

        # Fix 1: wrap function_call arg access (Gemini returns dict-like args, no JSON parse needed)
        for part in response.candidates[0].content.parts:
            fc = getattr(part, "function_call", None)
            if fc and fc.name == "submit_humanized":
                try:
                    return fc.args["humanized_text"]
                except (KeyError, TypeError) as exc:
                    raise SystemExit(f"LLM returned malformed tool_call JSON: {exc}")

        raise RuntimeError("Gemini returned no function call")

    else:
        raise RuntimeError(f"Unknown provider: {provider}")


# ---------------------------------------------------------------------------
# Stage 4: Platform post-processing
# ---------------------------------------------------------------------------

def _platform_post_process(
    text: str, platform: str, max_length: int | None
) -> str:
    """Apply platform-specific final adjustments."""
    if platform == "linkedin":
        # Strip markdown: **bold**, *italic*, # headings
        text = re.sub(r'\*\*(.+?)\*\*', r'\1', text)
        text = re.sub(r'\*(.+?)\*', r'\1', text)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Fix 5: strip backtick code spans, markdown links, blockquotes
        text = re.sub(r'`([^`]+)`', r'\1', text)                      # `code` -> code
        # R2-2: strip image markdown ![alt](url) BEFORE link sub (so ! isn't misread)
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)              # ![alt](url) -> ""
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)          # [text](url) -> text
        text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)         # > blockquote -> ""

    elif platform == "slack":
        # Strip markdown except *italic* and `code` (Slack supports backtick code spans)
        text = re.sub(r'\*\*(.+?)\*\*', r'*\1*', text)   # bold -> italic (slack style)
        text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
        # Fix 5: strip markdown links (keep backtick code spans for Slack)
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)          # [text](url) -> text

    elif platform == "tweet":
        # Fix 5: strip markdown links and backtick code spans (tweets don't render markdown)
        text = re.sub(r'`([^`]+)`', r'\1', text)
        # R2-2: strip image markdown ![alt](url) BEFORE link sub
        text = re.sub(r'!\[[^\]]*\]\([^)]+\)', '', text)              # ![alt](url) -> ""
        text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
        cap = max_length if max_length else 280
        if len(text) > cap:
            text = text[:cap - 1].rstrip() + "…"

    elif platform == "email":
        # Preserve structure; minimal changes
        pass

    # Generic: minimal changes — Fix 3: defense-in-depth guard
    if max_length is not None and max_length > 0 and platform != "tweet" and len(text) > max_length:
        text = text[:max_length - 1].rstrip() + "…"

    return text


# ---------------------------------------------------------------------------
# Diff display
# ---------------------------------------------------------------------------

def _show_diff(original: str, humanized: str) -> None:
    """Print a simple before/after to stderr."""
    sep = "-" * 60
    print(f"\n{sep}\nBEFORE:\n{sep}", file=sys.stderr)
    print(original, file=sys.stderr)
    print(f"\n{sep}\nAFTER:\n{sep}", file=sys.stderr)
    print(humanized, file=sys.stderr)
    print(sep, file=sys.stderr)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="humanizer",
        description="Strip AI-tells from text and rewrite it in a personal voice.",
    )
    input_group = parser.add_mutually_exclusive_group()
    input_group.add_argument("--text", metavar="TEXT", help="Direct text input -> humanize this string")
    input_group.add_argument("--file", metavar="PATH", help="Path to a file to humanize -> reads the file")

    parser.add_argument("--voice", default=DEFAULT_VOICE, help=f"Voice profile name (default: {DEFAULT_VOICE})")
    parser.add_argument(
        "--platform",
        choices=["linkedin", "email", "slack", "tweet", "generic"],
        default="generic",
        help="Target platform -> applies platform-specific post-processing",
    )
    parser.add_argument("--max-length", type=int, default=None, metavar="N",
                        help="Character cap on output (tweet defaults to 280)")
    parser.add_argument("--show-diff", action="store_true",
                        help="Print before/after to stderr -> see what changed. Note: emits full input/output text to stderr — be cautious with sensitive content.")
    parser.add_argument("--keep-em-dashes", action="store_true",
                        help="Skip em-dash replacement -> preserve intentional dashes")
    parser.add_argument(
        "--tier",
        choices=["default", "premium", "gemini"],
        default="default",
        help="Model tier -> default (Sonnet), premium (Opus), gemini (free Gemini)",
    )
    parser.add_argument("--dry-run", action="store_true",
                        help="Skip LLM call -> show pre-pass output and cost estimate")
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()

    # Fix 3: validate --max-length
    if args.max_length is not None and args.max_length < 1:
        parser.error("--max-length must be a positive integer >= 1")

    # ---------------------------------------------------------------------------
    # Read input text
    # ---------------------------------------------------------------------------
    if args.text is not None:
        raw_text = args.text
    elif args.file is not None:
        file_path = Path(args.file)
        if not file_path.exists():
            log.error("File not found: %s", file_path)
            return 1
        # Fix 11: size pre-check before reading
        file_size = file_path.stat().st_size
        if file_size > MAX_INPUT_CHARS * 4:
            parser.error(
                f"--file too large: {file_size} bytes (max ~{MAX_INPUT_CHARS * 4} bytes)"
            )
        raw_text = file_path.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        raw_text = sys.stdin.read()
    else:
        log.error("No input: provide --text, --file, or pipe text via stdin.")
        parser.print_help(sys.stderr)
        return 1

    # Empty input guard
    if not raw_text.strip():
        log.warning("Input text is empty -- nothing to humanize.")
        print("", end="")
        return 0

    # R2-4: capture original BEFORE truncation (used for --show-diff BEFORE panel)
    original_input = raw_text

    # Fix 11: hard cap input chars (truncate, don't just warn)
    if len(raw_text) > MAX_INPUT_CHARS:
        original_len = len(raw_text)
        raw_text = raw_text[:MAX_INPUT_CHARS]
        log.warning(
            "Input truncated from %d to %d chars (MAX_INPUT_CHARS limit).",
            original_len, MAX_INPUT_CHARS,
        )

    # ---------------------------------------------------------------------------
    # Stage 1: Load voice + pre-pass
    # ---------------------------------------------------------------------------
    voice = load_voice(args.voice)
    pre_cleaned, flags = _rules_pre_pass(raw_text, voice, keep_em_dashes=args.keep_em_dashes)

    # R10-2: Guard against pre-pass eating everything (e.g., opener regex over-matches)
    if not pre_cleaned.strip() and raw_text.strip():
        log.warning(
            "Pre-pass stripped the entire input (%d chars in, 0 out). "
            "Falling back to original text — opener regex may have over-matched.",
            len(raw_text),
        )
        pre_cleaned = raw_text

    if flags:
        log.info("Pre-pass flags: %s", "; ".join(flags))

    if args.dry_run:
        log.info("[dry-run] Pre-pass output:\n%s", pre_cleaned)
        if flags:
            log.info("[dry-run] Flags detected: %d", len(flags))

    # ---------------------------------------------------------------------------
    # Stage 2: Build prompt
    # ---------------------------------------------------------------------------
    system_prompt, user_prompt = _build_humanize_prompt(
        pre_cleaned, voice, flags, args.platform
    )

    # ---------------------------------------------------------------------------
    # Stage 3: LLM call (or dry-run stub)
    # ---------------------------------------------------------------------------
    humanized = _call_llm_humanize(system_prompt, user_prompt, args.tier, dry_run=args.dry_run)

    # ---------------------------------------------------------------------------
    # Stage 4: Platform post-processing
    # ---------------------------------------------------------------------------
    max_len = args.max_length
    if args.platform == "tweet" and max_len is None:
        max_len = 280

    humanized = _platform_post_process(humanized, args.platform, max_len)

    # ---------------------------------------------------------------------------
    # Output
    # ---------------------------------------------------------------------------
    if args.show_diff:
        _show_diff(original_input, humanized)

    print(humanized)
    return 0


if __name__ == "__main__":
    sys.exit(main())
