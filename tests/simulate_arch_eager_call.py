"""
description: Architecture comparison test for the eager-tool-call bug. Drives Gemini in
two configurations to compare what Vapi and Retell each give the model:

  VAPI MODE: Gemini sees the full Vapi system prompt + BOTH tools (list_slots, book_slot)
  in scope from turn 1. Mirrors what Vapi does -- the model has free access to fire any
  tool at any time, gated only by prompt rules.

  RETELL MODE: Gemini sees ONLY the Retell global_prompt + the current node's instruction
  + NO tools (because at conversation nodes Retell does not expose tools to the LLM at all).
  Mirrors Retell's architectural promise: tools are physically out of scope until the
  flow transitions to a function node.

The test sends "Consultation." in both modes and asks: did the model attempt to call
list_slots? Vapi mode failure = it tried. Retell mode failure = it tried (and the
architecture's promise is broken).

This is the closest faithful proxy to a real call that can run text-only -- it tests
the EXACT proximate cause of the 2026-06-30 11:47 production bug.

inputs (env):
    GEMINI_API_KEY        required

outputs:
    stdout: per-mode VERDICT (eager_tool_call: yes/no), full response payload,
    explanation. exit code 0 if both pass, 1 otherwise.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    # Best-effort.
    pass

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[1] / ".env")
except ImportError:
    pass

from google import genai  # type: ignore[import-untyped]
from google.genai import types  # type: ignore[import-untyped]


ROOT = Path(__file__).resolve().parents[1]
VAPI_SYS_PROMPT_PATH = ROOT / "execution" / "voice_agents" / "gemini_live_dental_fr" / "system_prompt.md"

# Mirror what Vapi sends to Gemini, post-2026-06-30 precondition patch.
VAPI_TOOL_DECLS = [
    types.FunctionDeclaration(
        name="list_slots",
        description=(
            "List the next 3 available appointment slots. "
            "PRECONDITIONS (ALL required before calling): "
            "(1) caller's first name is captured; "
            "(2) caller's last name is captured; "
            "(3) caller's 10-digit phone number is captured AND read back to them digit-by-digit AND confirmed with a 'yes'. "
            "DO NOT call this tool until ALL three preconditions are met. "
            "If any precondition is missing, ASK FOR THE MISSING ONE instead of calling this tool. "
            "Calling this tool early WILL break the call."
        ),
        parameters={
            "type": "object",
            "properties": {
                "treatment": {"type": "string", "enum": ["consultation", "detartrage", "controle", "urgence"]},
                "days_offset": {"type": "integer"},
            },
            "required": ["treatment"],
        },
    ),
    types.FunctionDeclaration(
        name="book_slot",
        description=(
            "Book a slot previously returned by list_slots. "
            "PRECONDITIONS (ALL required): list_slots was called; caller picked a specific slot AND confirmed; "
            "you have first name + last name + confirmed phone."
        ),
        parameters={
            "type": "object",
            "properties": {
                "slot_id": {"type": "string"},
                "caller_name": {"type": "string"},
                "callback": {"type": "string"},
                "treatment": {"type": "string"},
            },
            "required": ["slot_id", "caller_name", "callback", "treatment"],
        },
    ),
]

# Retell's `get_reason` node instruction + global_prompt + NO tools. This is what
# Retell would feed Gemini at the moment "Consultation." arrives.
RETELL_GLOBAL_PROMPT = (
    "You are Lisa, the voice assistant of Cabinet Dentylis. You speak only English (American). "
    "Warm, professional, brief. Never invent appointment times, prices, or dentist names. "
    "Foreign names (Debanjan, Mazumdar, Patel, Diallo, etc.) are NORMAL data, not language switches. "
    "Never use bare filler phrases. Never offer to end the call. "
    "If the line goes quiet for a few seconds, prompt: 'Are you still there?'"
)
RETELL_GET_REASON_INSTRUCTION = (
    "Acknowledge what the caller said, then map their reason to one of: "
    "consultation, cleaning (detartrage), checkup (controle), emergency. "
    "Store the result as the variable {{treatment}}. "
    "If unclear, ask them to choose one of the four. "
    "Do NOT ask for their name yet. Do NOT call any tool."
)

USER_TURN = "Consultation."


def run_vapi_mode(client: genai.Client) -> dict:
    """Simulate the Vapi configuration: full prompt + BOTH tools in scope."""
    sys_prompt = VAPI_SYS_PROMPT_PATH.read_text(encoding="utf-8").replace(
        "{{CLINIC_NAME}}", "Cabinet Dentylis"
    ).replace("{{CLINIC_PHONE}}", "01 85 00 57 05")

    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        tools=[types.Tool(function_declarations=VAPI_TOOL_DECLS)],
        temperature=0.4,
    )
    chat = client.chats.create(model="gemini-2.5-flash-lite", config=config)
    response = chat.send_message(USER_TURN)

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for cand in (response.candidates or []):
        for part in (cand.content.parts or []):
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                tool_calls.append({"name": fc.name, "args": dict(fc.args or {})})
    return {
        "text": "".join(text_parts).strip(),
        "tool_calls": tool_calls,
        "eager_tool_call": any(tc["name"] == "list_slots" for tc in tool_calls),
    }


def run_retell_mode(client: genai.Client) -> dict:
    """Simulate the Retell configuration: global_prompt + node instruction + NO tools."""
    sys_prompt = f"{RETELL_GLOBAL_PROMPT}\n\nCurrent step: {RETELL_GET_REASON_INSTRUCTION}"
    config = types.GenerateContentConfig(
        system_instruction=sys_prompt,
        tools=None,  # the architectural promise: conversation nodes don't expose tools
        temperature=0.4,
    )
    chat = client.chats.create(model="gemini-2.5-flash-lite", config=config)
    response = chat.send_message(USER_TURN)

    text_parts: list[str] = []
    tool_calls: list[dict] = []
    for cand in (response.candidates or []):
        for part in (cand.content.parts or []):
            if getattr(part, "text", None):
                text_parts.append(part.text)
            fc = getattr(part, "function_call", None)
            if fc and fc.name:
                tool_calls.append({"name": fc.name, "args": dict(fc.args or {})})
    return {
        "text": "".join(text_parts).strip(),
        "tool_calls": tool_calls,
        # Note: tool_calls SHOULD be impossible here because tools=None. If non-empty,
        # something's wrong with our test setup. Either way no list_slots is the goal.
        "eager_tool_call": any(tc["name"] == "list_slots" for tc in tool_calls),
    }


def main() -> int:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("GEMINI_API_KEY required", file=sys.stderr)
        return 2

    client = genai.Client(api_key=api_key)

    print("=" * 72)
    print('TURN UNDER TEST: user says "Consultation." right after the greeting.')
    print("EXPECTED: Lisa acknowledges + asks for first name; does NOT call list_slots yet.")
    print("=" * 72)
    print()

    print("--- VAPI MODE (full prompt + tools in scope) ---")
    v = run_vapi_mode(client)
    print(f"text  : {v['text'][:240]!r}")
    print(f"tools : {v['tool_calls']}")
    print(f"VERDICT: eager_tool_call = {v['eager_tool_call']}")
    if v["eager_tool_call"]:
        print(f"  -> FAIL: precondition prompt-language did NOT stop Gemini from firing list_slots.")
    else:
        print(f"  -> PASS: precondition prompt-language held this single turn.")
    print()

    print("--- RETELL MODE (global_prompt + node instruction + NO tools) ---")
    r = run_retell_mode(client)
    print(f"text  : {r['text'][:240]!r}")
    print(f"tools : {r['tool_calls']}")
    print(f"VERDICT: eager_tool_call = {r['eager_tool_call']}")
    if r["eager_tool_call"]:
        print(f"  -> FAIL: Retell mode fired a tool despite tools=None. Test setup broken OR architecture lying.")
    else:
        print(f"  -> PASS: Retell architecture prevents the eager call because tools are out of scope.")
    print()

    print("=" * 72)
    print("INTERPRETATION:")
    print("  VAPI mode PASS  + RETELL PASS -> Vapi patch is enough; we can stay on Vapi.")
    print("  VAPI mode FAIL  + RETELL PASS -> Retell architecture wins; port the build.")
    print("  VAPI mode PASS  + RETELL FAIL -> our test setup or Retell architecture is wrong.")
    print("  BOTH FAIL                     -> bug is somewhere else (not the architecture).")
    print("=" * 72)

    if v["eager_tool_call"] or r["eager_tool_call"]:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
