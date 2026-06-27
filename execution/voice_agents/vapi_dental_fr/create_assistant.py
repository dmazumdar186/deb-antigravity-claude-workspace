"""
description: One-shot script to create (or update) the Vapi assistant for the French dental voice
receptionist via the Vapi REST API. Reads the FR system prompt from the sibling Gemini-Live build,
posts to https://api.vapi.ai/assistant, prints the assistant id. Idempotent: if VAPI_ASSISTANT_ID
is already in .env, it PATCHes that assistant instead of creating a new one.

inputs (env, read from project .env):
    VAPI_API_KEY              required (private key from dashboard.vapi.ai → API Keys)
    GEMINI_API_KEY            required (BYO Gemini key Vapi will use for the LLM)
    VAPI_ASSISTANT_ID         optional (if set, PATCHes instead of POSTing)
    TOOLS_SERVER_URL          required (the deployed Modal app URL, e.g.
                              https://<workspace>--vapi-dental-fr-fastapi-app.modal.run)

outputs:
    stdout: the assistant id + the configured tools URL
    side-effect: prints a one-line command to add VAPI_ASSISTANT_ID to .env

Run:
    py execution/voice_agents/vapi_dental_fr/create_assistant.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
except ImportError:
    pass

import httpx  # type: ignore[import-not-found]

ROOT = Path(__file__).resolve().parents[3]
SHARED_PROMPT = ROOT / "execution" / "voice_agents" / "gemini_live_dental_fr" / "system_prompt.md"

CLINIC_NAME = "Cabinet Dentylis"
CLINIC_PHONE = "01 85 00 57 05"

GEMINI_MODEL = "gemini-3.5-flash"  # Vapi catalogue June 2026; LLM only — audio is Deepgram + Azure
# OPERATOR DECISION 2026-06-26: English-only for demo. Drops accent-contamination risk
# from multilingual voices entirely. Bilingual support stays in the corpus / prompt history
# for future revival but the LIVE assistant runs monolingual American English.
TRANSCRIBER_LANG = "en"
VOICE_PROVIDER = "azure"
# Aria is Azure's flagship native American-English neural voice. Not multilingual —
# specifically chosen because monolingual voices avoid the locale-routing accent leak
# that plagued Ava + Emma.
VOICE_ID = "en-US-AriaNeural"

ASSISTANT_NAME = "Lisa Dentylis (English demo)"  # Vapi cap: 40 chars


def build_first_message() -> str:
    # English-only demo. The greeting MUST end with an open invitation; otherwise the
    # caller hears the AI-disclosure + escape words and then dead air (iteration-4 bug
    # surfaced 2026-06-26 listen-test). The Step-1 "what's the reason" question is asked
    # naturally here, not as a separate turn — it's an opener, not a forced-choice ask.
    return (
        f"Hi, you've reached {CLINIC_NAME}. I'm Lisa, your assistant. "
        "This call is handled by an AI. If you'd rather speak to a human, just say \"operator\" at any time. "
        "For an emergency with severe pain, say \"emergency\". "
        "How can I help you today?"
    )


def build_system_message() -> str:
    raw = SHARED_PROMPT.read_text(encoding="utf-8")
    return raw.replace("{{CLINIC_NAME}}", CLINIC_NAME).replace("{{CLINIC_PHONE}}", CLINIC_PHONE)


def build_assistant_payload(tools_url: str, gemini_key: str) -> dict:
    # Note: Gemini key is provisioned on the Vapi side (dashboard.vapi.ai → Providers → Google).
    # No BYO field needed on the assistant config — Vapi proxies calls under your Vapi balance.
    del gemini_key  # explicitly unused at the assistant level
    return {
        "name": ASSISTANT_NAME,
        "model": {
            "provider": "google",
            "model": GEMINI_MODEL,
            "temperature": 0.4,
            "messages": [{"role": "system", "content": build_system_message()}],
            "tools": [
                {
                    "type": "function",
                    "function": {
                        "name": "list_slots",
                        "description": "Liste les 3 prochains créneaux disponibles pour un type de RDV donné.",
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
                    },
                    "server": {"url": f"{tools_url}/vapi/tools/list_slots"},
                    "async": False,
                },
                {
                    "type": "function",
                    "function": {
                        "name": "book_slot",
                        "description": "Réserve un créneau retourné par list_slots.",
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
                    },
                    "server": {"url": f"{tools_url}/vapi/tools/book_slot"},
                    "async": False,
                },
            ],
        },
        "voice": {
            "provider": VOICE_PROVIDER,
            "voiceId": VOICE_ID,
        },
        "transcriber": {
            "provider": "deepgram",
            "model": "nova-2",
            "language": TRANSCRIBER_LANG,
            "smartFormat": True,
            # Keyword boosting: tells Deepgram these proper nouns are likely to appear, so
            # foreign-origin names common in the Vitry catchment area (Indian, West African,
            # Maghrebi, East Asian, Eastern European, Iberian, Anglo) are transcribed cleanly
            # instead of being garbled into "third-language" gibberish that triggers handoff.
            # See SYSTEM_PROMPT rule "Foreign names are NORMAL data, not a language switch."
            # Deepgram keyword constraint: ASCII-only, no apostrophes/accents.
            # Words with diacritics (Mbappé, détartrage) and apostrophes (O'Brien) are stripped.
            # Format optional ":N" appends a boost weight; 2 = strong boost for proper nouns
            # that the ASR systematically mishears in a FR/EN context.
            # Deepgram keywords — ASCII only, no apostrophes/accents. Boost weight `:N`
            # increases recognition likelihood. Operator-name and known-failing tokens
            # boosted to :3 (max useful weight per Deepgram docs) after iteration-5 listen-test
            # where "Debanjan" was mis-ASR'd into a goodbye-sounding word.
            "keywords": [
                "Debanjan:3", "Mazumdar:3", "Patel:3",
                "Singh", "Kumar", "Sharma", "Khan", "Krishnan", "Iyer", "Reddy",
                "Diallo:2", "Mbappe:2", "Diaby", "Konate", "Traore", "Doumbouya",
                "Yacoub:2", "Benali", "Mansouri", "Hadj", "Chouaib", "Belkacem",
                "Chen", "Tanaka", "Yamamoto", "Nguyen", "Tran",
                "Kowalski", "Nowak", "Petrov", "Sokolov",
                "Garcia", "Rodriguez", "Lopez", "Silva", "Santos",
                "McLeod", "Andersen", "Smith",
                "detartrage:2", "consultation:2", "controle:2", "urgence:2",
            ],
        },
        "firstMessage": build_first_message(),
        "firstMessageMode": "assistant-speaks-first",
        # End-call phrases tightened — only fire on Lisa's own goodbye lines from the
        # confirmation step. Caller speech (digits, names, "yes"/"yeah") must never end the call.
        "endCallPhrases": [
            f"see you soon at {CLINIC_NAME}. Have a good day",
            f"see you soon at {CLINIC_NAME}, have a good day",
        ],
        "endCallMessage": (
            f"Thank you, see you soon at {CLINIC_NAME}. Have a good day."
        ),
        # Bumped 12 -> 30 because callers dictate phone numbers with multi-second pauses
        # between digit groups; the prior 12s window cut calls mid-number.
        "silenceTimeoutSeconds": 30,
        "maxDurationSeconds": 600,
        "backgroundDenoisingEnabled": True,
        "modelOutputInMessagesEnabled": True,
        "metadata": {"build": "vapi-dental-fr", "version": "1.0"},
    }


def main() -> int:
    api_key = os.environ.get("VAPI_API_KEY")
    gemini_key = os.environ.get("GEMINI_API_KEY")
    tools_url = os.environ.get("TOOLS_SERVER_URL")
    existing_id = os.environ.get("VAPI_ASSISTANT_ID")

    missing = [k for k, v in {
        "VAPI_API_KEY": api_key,
        "GEMINI_API_KEY": gemini_key,
        "TOOLS_SERVER_URL": tools_url,
    }.items() if not v]
    if missing:
        print(f"missing env: {', '.join(missing)}", file=sys.stderr)
        print("  - VAPI_API_KEY:        dashboard.vapi.ai → API Keys (private)", file=sys.stderr)
        print("  - GEMINI_API_KEY:      already in .env if present", file=sys.stderr)
        print("  - TOOLS_SERVER_URL:    deploy the Modal app first; modal prints the URL", file=sys.stderr)
        return 2

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = build_assistant_payload(tools_url, gemini_key)

    with httpx.Client(timeout=20.0) as cx:
        if existing_id:
            print(f"updating Vapi assistant {existing_id} ...")
            r = cx.patch(f"https://api.vapi.ai/assistant/{existing_id}", headers=headers, json=payload)
        else:
            print("creating Vapi assistant ...")
            r = cx.post("https://api.vapi.ai/assistant", headers=headers, json=payload)
        if r.status_code >= 400:
            print(f"FAIL  {r.status_code}: {r.text[:500]}", file=sys.stderr)
            return 1
        body = r.json()

    assistant_id = body.get("id") or body.get("assistantId")
    print(f"OK    assistant_id={assistant_id}")
    print(f"      tools_url={tools_url}")
    print()
    print("Next steps:")
    print(f"  1. Add to .env:  VAPI_ASSISTANT_ID={assistant_id}")
    print(f"  2. Refresh the Modal secret:")
    print(f"     py -m modal secret create vapi-dental-secret \\")
    print(f"        CALCOM_API_KEY=... CALCOM_USERNAME=debanjan-mazumdar-ben5rd \\")
    print(f"        CALCOM_EVENT_SLUG=30min CALCOM_TIMEZONE=Europe/Paris \\")
    print(f"        VAPI_PUBLIC_KEY=pk_... VAPI_ASSISTANT_ID={assistant_id} \\")
    print(f"        WORKER_SECRET=...")
    print(f"  3. Re-deploy:  py -m modal deploy execution/voice_agents/vapi_dental_fr/app.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
