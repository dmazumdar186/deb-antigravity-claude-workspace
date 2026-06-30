"""
description: One-shot script to create (or update) a Retell Conversation Flow + Agent for the
dental POC. Tests whether Retell's node-based architecture structurally prevents the
eager-tool-call bug (production incident 2026-06-30 11:47 on Vapi: Lisa fired list_slots
after hearing "Consultation" before collecting name/phone, races killed the call).

The flow forces this exact order:
  greet -> get_reason -> get_first_name -> get_last_name -> get_phone -> confirm_phone ->
  list_slots (function node) -> pick_slot -> book_slot (function node) -> close.

list_slots and book_slot are bound to FUNCTION nodes -- conversation nodes can't see them,
so the LLM physically cannot fire list_slots from the get_reason node even if it wanted to.

inputs (env, from .env):
    RETELL_API_KEY            required
    RETELL_FLOW_ID            optional (set after first creation; reuses on update)
    RETELL_AGENT_ID           optional (set after first creation; reuses on update)
    TOOLS_SERVER_URL          required (https://vapi-dental-fr.debanjan186.workers.dev)

outputs:
    stdout: flow_id, agent_id, and the call-creation curl one-liner for the operator
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path

try:
    from dotenv import load_dotenv  # type: ignore[import-untyped]
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass


RETELL_BASE = "https://api.retellai.com"
CLINIC_NAME = "Cabinet Dentylis"


def build_flow_payload(tools_url: str) -> dict:
    """The Conversation Flow that enforces booking step order via node structure.

    Each conversation node asks exactly ONE thing. Tools are only attached to function
    nodes (list_slots_call, book_slot_call), so the LLM physically cannot call list_slots
    from the get_reason node or earlier. This is the structural difference from Vapi's
    free-form assistant.
    """
    return {
        "model_choice": {
            # gemini-3.5-flash is what the Vapi build uses; same model so any difference
            # in behavior is purely from the flow architecture, not from the model.
            "type": "cascading",
            "model": "gemini-3.5-flash",
        },
        "model_temperature": 0.4,
        "start_speaker": "agent",
        "global_prompt": (
            f"You are Lisa, the voice assistant of {CLINIC_NAME}. You speak only English (American). "
            "Warm, professional, brief. Never invent appointment times, prices, or dentist names. "
            "Foreign names (Debanjan, Mazumdar, Patel, Diallo, etc.) are NORMAL data, not language switches; "
            "if a name sounds unclear, ASK THE CALLER TO SPELL IT, never offer to end the call. "
            "Never use bare filler phrases (no 'one moment', 'just a sec', 'let me check') "
            "-- the flow handles transitions; do not narrate them. "
            "Never offer to end the call. "
            "If the line goes quiet for a few seconds, prompt: 'Are you still there?'"
        ),
        "tools": [
            {
                "type": "custom",
                "tool_id": "list_slots",
                "name": "list_slots",
                "description": "List the next 3 available appointment slots.",
                "url": f"{tools_url}/retell/tools/list_slots",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "treatment": {
                            "type": "string",
                            "enum": ["consultation", "detartrage", "controle", "urgence"],
                        },
                        "days_offset": {"type": "integer"},
                    },
                    "required": ["treatment"],
                },
                "response_variables": {
                    "slots_summary": "summary",
                    "first_slot_id": "slots.0.slot_id",
                    "second_slot_id": "slots.1.slot_id",
                    "third_slot_id": "slots.2.slot_id",
                },
                "speak_during_execution": False,
                "speak_after_execution": True,
                "timeout_ms": 15000,
            },
            {
                "type": "custom",
                "tool_id": "book_slot",
                "name": "book_slot",
                "description": "Book the chosen slot.",
                "url": f"{tools_url}/retell/tools/book_slot",
                "method": "POST",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "slot_id": {"type": "string"},
                        "caller_name": {"type": "string"},
                        "callback": {"type": "string"},
                        "treatment": {"type": "string"},
                    },
                    "required": ["slot_id", "caller_name", "callback", "treatment"],
                },
                "response_variables": {
                    "booking_summary": "summary",
                    "booking_status": "booking.status",
                    "event_id": "booking.event_id",
                },
                "speak_during_execution": False,
                "speak_after_execution": True,
                "timeout_ms": 15000,
            },
        ],
        "start_node_id": "greet",
        "nodes": [
            {
                "id": "greet",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        f"Greet the caller exactly: 'Hi, you've reached {CLINIC_NAME}. I'm Lisa, "
                        "your assistant. This call is handled by an AI. If you'd rather speak to "
                        "a human, just say operator at any time. For an emergency with severe pain, "
                        "say emergency. How can I help you today?' Then wait. Do not ask anything else."
                    ),
                },
                "edges": [
                    {
                        "id": "to_reason",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller said anything other than 'operator' or 'emergency'.",
                        },
                        "destination_node_id": "get_reason",
                    },
                    {
                        "id": "to_handoff_op",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller asked for operator or said 'human'.",
                        },
                        "destination_node_id": "handoff",
                    },
                    {
                        "id": "to_handoff_em",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller said 'emergency' or mentioned severe pain, bleeding, broken tooth, abscess.",
                        },
                        "destination_node_id": "handoff",
                    },
                ],
            },
            {
                "id": "get_reason",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Acknowledge what the caller said, then map their reason to one of: "
                        "consultation, cleaning (detartrage), checkup (controle), emergency. "
                        "Store the result as the variable {{treatment}}. "
                        "If unclear, ask them to choose one of the four. "
                        "Do NOT ask for their name yet. Do NOT call any tool."
                    ),
                },
                "edges": [
                    {
                        "id": "reason_done",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller's reason has been clearly identified and stored.",
                        },
                        "destination_node_id": "get_first_name",
                    },
                    {
                        "id": "reason_emergency",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller's reason is emergency / severe pain.",
                        },
                        "destination_node_id": "handoff",
                    },
                ],
            },
            {
                "id": "get_first_name",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Ask: 'May I have your first name, please?' Store as {{first_name}}. "
                        "If the response is unclear or sounds like 'Goodbye', 'Hello', or any single "
                        "ambiguous word, DO NOT exit -- ask them to spell it letter by letter, "
                        "then assemble. Ask for the first name ONLY. Do NOT ask for last name yet. "
                        "Do NOT call any tool."
                    ),
                },
                "edges": [
                    {
                        "id": "first_name_done",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "First name is captured and stored in {{first_name}}.",
                        },
                        "destination_node_id": "get_last_name",
                    },
                ],
            },
            {
                "id": "get_last_name",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Acknowledge by saying 'Thank you, {{first_name}}.' then ask: 'And your last name?' "
                        "Store as {{last_name}}. Same spell-back rule for unclear/foreign-origin names. "
                        "Do NOT ask for phone yet. Do NOT call any tool."
                    ),
                },
                "edges": [
                    {
                        "id": "last_name_done",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Last name is captured and stored in {{last_name}}.",
                        },
                        "destination_node_id": "get_phone",
                    },
                ],
            },
            {
                "id": "get_phone",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Acknowledge: 'Perfect, {{first_name}} {{last_name}}.' Then ask: "
                        "'What's the best phone number to reach you?' "
                        "Wait for ALL 10 digits; do not interrupt -- people pause mid-number. "
                        "Store as {{phone}}. Do NOT call any tool."
                    ),
                },
                "edges": [
                    {
                        "id": "phone_done",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "A 10-digit phone number was given and stored in {{phone}}.",
                        },
                        "destination_node_id": "confirm_phone",
                    },
                ],
            },
            {
                "id": "confirm_phone",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Read the phone number back slowly in pairs of digits "
                        "(e.g. 'zero six, one two, three four, five six, seven eight'). "
                        "Ask: 'Is that correct?' If they say no or correct a digit, ask again and re-read. "
                        "Do NOT proceed without an explicit 'yes'."
                    ),
                },
                "edges": [
                    {
                        "id": "phone_confirmed",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller confirmed the phone number with a clear yes.",
                        },
                        "destination_node_id": "list_slots_call",
                    },
                    {
                        "id": "phone_rejected",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller said no or corrected a digit; phone needs to be re-collected.",
                        },
                        "destination_node_id": "get_phone",
                    },
                ],
            },
            {
                "id": "list_slots_call",
                "type": "function",
                "tool_id": "list_slots",
                "tool_type": "local",
                "wait_for_result": True,
                "speak_during_execution": False,
                "speak_after_execution": False,
                "instruction": {
                    "type": "prompt",
                    "text": "Call list_slots with treatment={{treatment}}.",
                },
                "edges": [
                    {
                        "id": "slots_returned",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "list_slots returned successfully.",
                        },
                        "destination_node_id": "read_slots",
                    },
                ],
            },
            {
                "id": "read_slots",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Read the slots aloud in natural English: '{{slots_summary}}'. "
                        "Then ask: 'Which one works for you?' "
                        "Map their answer to first_slot_id, second_slot_id, or third_slot_id, "
                        "and store the chosen slot_id as {{chosen_slot_id}}. "
                        "If they want different times, say so and transition to reroll."
                    ),
                },
                "edges": [
                    {
                        "id": "slot_chosen",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "Caller picked one of the three slots; {{chosen_slot_id}} is set.",
                        },
                        "destination_node_id": "book_slot_call",
                    },
                ],
            },
            {
                "id": "book_slot_call",
                "type": "function",
                "tool_id": "book_slot",
                "tool_type": "local",
                "wait_for_result": True,
                "speak_during_execution": False,
                "speak_after_execution": False,
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Call book_slot with slot_id={{chosen_slot_id}}, "
                        "caller_name={{first_name}} {{last_name}}, "
                        "callback={{phone}}, treatment={{treatment}}."
                    ),
                },
                "edges": [
                    {
                        "id": "booked",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "book_slot returned successfully with status confirmed.",
                        },
                        "destination_node_id": "close",
                    },
                    {
                        "id": "book_failed",
                        "transition_condition": {
                            "type": "prompt",
                            "prompt": "book_slot returned status duplicate or an error.",
                        },
                        "destination_node_id": "handoff",
                    },
                ],
            },
            {
                "id": "close",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Confirm: 'All set, {{first_name}}. Your appointment is booked. "
                        "Thank you, see you soon at " + CLINIC_NAME + ". Have a good day.' "
                        "Then end the call."
                    ),
                },
                "edges": [],
            },
            {
                "id": "handoff",
                "type": "conversation",
                "instruction": {
                    "type": "prompt",
                    "text": (
                        "Say exactly: 'I understand, I'm transferring you to the clinic right now. "
                        "Please stay on the line, a human will be with you shortly.' "
                        "Do NOT call any tool. Then end the call."
                    ),
                },
                "edges": [],
            },
        ],
    }


def build_agent_payload(flow_id: str) -> dict:
    """Agent ties the flow to a voice + transcriber + keyword boost + STT config."""
    return {
        "agent_name": "Lisa Dentylis (Retell POC)",
        "response_engine": {
            "type": "conversation-flow",
            "conversation_flow_id": flow_id,
        },
        # 11Labs voice closest to en-US-AriaNeural in feel. Retell default voices listed at
        # docs.retellai.com -- the prefix 'eleven_' uses 11Labs.
        "voice_id": "11labs-Adrian",
        "voice_speed": 1.0,
        "language": "en-US",
        # Boost Deepgram for foreign-origin names that the Vapi build had to keyword-boost.
        "boosted_keywords": [
            "Debanjan", "Mazumdar", "Patel",
            "Singh", "Kumar", "Sharma", "Khan",
            "Diallo", "Yacoub", "Benali",
            "Chen", "Tanaka", "Nguyen",
            "Garcia", "Rodriguez",
        ],
        # End-of-utterance tuning; 500ms is the documented default and a good baseline.
        "responsiveness": 1.0,
        "interruption_sensitivity": 0.7,
        "enable_backchannel": False,
        "ambient_sound": None,
        "max_call_duration_ms": 600000,
    }


def retell_request(method: str, path: str, api_key: str, body: dict | None = None) -> dict:
    url = f"{RETELL_BASE}{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
    }
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as exc:
        body_text = exc.read().decode("utf-8", errors="replace")
        print(f"FAIL  {method} {path} -> HTTP {exc.code}: {body_text[:500]}", file=sys.stderr)
        raise


def main() -> int:
    api_key = os.environ.get("RETELL_API_KEY")
    tools_url = os.environ.get("TOOLS_SERVER_URL", "https://vapi-dental-fr.debanjan186.workers.dev")
    if not api_key:
        print("RETELL_API_KEY required in .env", file=sys.stderr)
        return 2

    flow_id = os.environ.get("RETELL_FLOW_ID")
    agent_id = os.environ.get("RETELL_AGENT_ID")
    flow_payload = build_flow_payload(tools_url)

    if flow_id:
        print(f"updating flow {flow_id} ...")
        flow = retell_request("PATCH", f"/update-conversation-flow/{flow_id}", api_key, flow_payload)
    else:
        print("creating conversation flow ...")
        flow = retell_request("POST", "/create-conversation-flow", api_key, flow_payload)
    flow_id = flow.get("conversation_flow_id") or flow.get("id") or flow.get("flow_id")
    print(f"OK    flow_id={flow_id}")

    agent_payload = build_agent_payload(flow_id or "")
    if agent_id:
        print(f"updating agent {agent_id} ...")
        agent = retell_request("PATCH", f"/update-agent/{agent_id}", api_key, agent_payload)
    else:
        print("creating agent ...")
        agent = retell_request("POST", "/create-agent", api_key, agent_payload)
    agent_id = agent.get("agent_id") or agent.get("id")
    print(f"OK    agent_id={agent_id}")
    print()
    print("Next steps:")
    print(f"  1. Add to .env:  RETELL_FLOW_ID={flow_id}")
    print(f"                   RETELL_AGENT_ID={agent_id}")
    print(f"  2. Create a web-call access token (operator side):")
    print(f"     curl -X POST {RETELL_BASE}/create-web-call \\")
    print(f"       -H 'Authorization: Bearer $RETELL_API_KEY' \\")
    print(f"       -H 'Content-Type: application/json' \\")
    print(f"       -d '{{\"agent_id\":\"{agent_id}\"}}' ")
    print(f"  3. Or run: py tests/listen_test_retell.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
