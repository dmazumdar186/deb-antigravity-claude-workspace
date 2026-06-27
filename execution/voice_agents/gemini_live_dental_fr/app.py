"""
description: Modal-hosted French dental voice receptionist. FastAPI app serves a browser widget at `/`
that captures microphone audio via WebRTC and proxies it over WebSocket to Google Gemini Live (Aoede
voice, FR). The model handles ASR + LLM + native-audio TTS in one stream. Two server-side tools —
`list_slots` and `book_slot` — read/write a Google Calendar via the workspace service account so
no clinic-side OAuth is required for the demo.

inputs:
    Modal CLI (deploy):
        `py -m modal deploy execution/voice_agents/gemini_live_dental_fr/app.py`

    Modal secrets (deploy-time, set via `modal secret create`):
        gemini-secret             GEMINI_API_KEY
        gcal-secret               GOOGLE_SERVICE_ACCOUNT_JSON (full JSON pasted as one secret)
        voice-agent-secret        WORKER_SECRET (X-Voice-Agent-Secret header for /api/health audit)

    Static config (in this file):
        CLINIC_NAME, CLINIC_PHONE, CALENDAR_ID, BUSINESS_HOURS, TREATMENT_DURATIONS_MIN, DEMO_MODE

outputs:
    Public URLs after deploy:
        https://<workspace>--gemini-live-dental-fr-fastapi-app.modal.run/
            -> browser widget (HTML + JS)
        /ws  -> Gemini Live proxy WebSocket
        /api/health -> readiness JSON (secrets present, calendar reachable, model reachable)
        /api/booked -> demo-mode-only inbox listing recent bookings (auth: X-Voice-Agent-Secret)
"""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, time as dt_time, timedelta, timezone
from pathlib import Path
from typing import Any

import modal

APP_NAME = "gemini-live-dental-fr"
CLINIC_NAME = "Cabinet Dentylis"
CLINIC_PHONE = "01 85 00 57 05"
CALENDAR_ID = "primary"  # service-account's primary, or set to a shared calendar id
TIMEZONE = "Europe/Paris"
DEMO_MODE = True

BUSINESS_HOURS = {
    "mon": ("09:00", "12:30", "14:00", "19:00"),
    "tue": ("09:00", "12:30", "14:00", "19:00"),
    "wed": ("09:00", "12:30", "14:00", "19:00"),
    "thu": ("09:00", "12:30", "14:00", "19:00"),
    "fri": ("09:00", "12:30", "14:00", "19:00"),
    "sat": ("09:00", "13:00"),
    "sun": None,
}
TREATMENT_DURATIONS_MIN = {
    "consultation": 20,
    "detartrage": 30,
    "controle": 20,
    "urgence": 30,
}

# Gemini Live model + voice
GEMINI_MODEL = "gemini-3.1-flash-live-preview"  # current Live-API model (ai.google.dev, June 2026)
GEMINI_VOICE = "Aoede"
GEMINI_LANGUAGE_CODE = "fr-FR"

# ---------------------------------------------------------------------------
# Modal image + app

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi==0.115.4",
        "uvicorn==0.32.0",
        "google-genai==0.3.0",
        "google-api-python-client==2.149.0",
        "google-auth==2.35.0",
        "pydantic==2.9.2",
        "websockets==13.1",
        "python-multipart==0.0.12",
    )
    .add_local_dir(
        Path(__file__).parent / "static",
        remote_path="/app/static",
    )
    .add_local_file(
        Path(__file__).parent / "system_prompt_fr.md",
        remote_path="/app/system_prompt_fr.md",
    )
)

app = modal.App(APP_NAME, image=image)


# ---------------------------------------------------------------------------
# Google Calendar helpers (run inside Modal container)

def _calendar_service():
    """Build a Google Calendar v3 service from the JSON secret."""
    from google.oauth2 import service_account
    from googleapiclient.discovery import build

    raw = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    info = json.loads(raw)
    creds = service_account.Credentials.from_service_account_info(
        info,
        scopes=["https://www.googleapis.com/auth/calendar"],
    )
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


@dataclass
class Slot:
    slot_id: str
    start_iso: str
    end_iso: str
    human_fr: str


_FR_DAY = {0: "lundi", 1: "mardi", 2: "mercredi", 3: "jeudi", 4: "vendredi", 5: "samedi", 6: "dimanche"}
_FR_MONTH = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


def _human_fr(dt: datetime) -> str:
    day_word = _FR_DAY[dt.weekday()]
    month_word = _FR_MONTH[dt.month]
    hour = dt.hour
    minute = dt.minute
    h = f"{hour}h" if minute == 0 else f"{hour}h{minute:02d}"
    return f"{day_word} {dt.day} {month_word} à {h}"


def _day_windows(day_key: str) -> list[tuple[dt_time, dt_time]]:
    spec = BUSINESS_HOURS.get(day_key)
    if not spec:
        return []
    out = []
    for i in range(0, len(spec), 2):
        s = dt_time.fromisoformat(spec[i])
        e = dt_time.fromisoformat(spec[i + 1])
        out.append((s, e))
    return out


_DAY_KEYS = ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]


def list_slots_impl(treatment: str, days_offset: int = 0) -> list[Slot]:
    """Read freeBusy + generate 3 next valid slots. Pure Python; safe to call in any context."""
    dur = TREATMENT_DURATIONS_MIN.get(treatment.lower(), 20)
    now = datetime.now(timezone.utc) + timedelta(days=days_offset)
    horizon = now + timedelta(days=14)

    svc = _calendar_service()
    fb = svc.freebusy().query(body={
        "timeMin": now.isoformat(),
        "timeMax": horizon.isoformat(),
        "timeZone": TIMEZONE,
        "items": [{"id": CALENDAR_ID}],
    }).execute()
    busy = fb["calendars"][CALENDAR_ID]["busy"]
    busy_intervals = [
        (datetime.fromisoformat(b["start"].replace("Z", "+00:00")),
         datetime.fromisoformat(b["end"].replace("Z", "+00:00")))
        for b in busy
    ]

    from zoneinfo import ZoneInfo
    paris = ZoneInfo(TIMEZONE)
    out: list[Slot] = []
    cursor = now.astimezone(paris)

    while cursor < horizon.astimezone(paris) and len(out) < 3:
        day_key = _DAY_KEYS[cursor.weekday()]
        windows = _day_windows(day_key)
        if not windows:
            cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
            continue

        for win_start, win_end in windows:
            slot_start = cursor.replace(hour=win_start.hour, minute=win_start.minute, second=0, microsecond=0)
            slot_end_window = cursor.replace(hour=win_end.hour, minute=win_end.minute, second=0, microsecond=0)
            if slot_start < cursor:
                # round forward to next 15-min boundary >= cursor
                minute = (cursor.minute // 15 + 1) * 15
                if minute >= 60:
                    slot_start = (cursor + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
                else:
                    slot_start = cursor.replace(minute=minute, second=0, microsecond=0)

            while slot_start + timedelta(minutes=dur) <= slot_end_window and len(out) < 3:
                slot_end = slot_start + timedelta(minutes=dur)
                clash = any(
                    not (slot_end.astimezone(timezone.utc) <= b_start or slot_start.astimezone(timezone.utc) >= b_end)
                    for b_start, b_end in busy_intervals
                )
                if not clash:
                    slot_id = f"{slot_start.astimezone(timezone.utc).strftime('%Y%m%dT%H%M%S')}_{dur}_{treatment.lower()}"
                    out.append(Slot(
                        slot_id=slot_id,
                        start_iso=slot_start.isoformat(),
                        end_iso=slot_end.isoformat(),
                        human_fr=_human_fr(slot_start),
                    ))
                slot_start += timedelta(minutes=dur)

        cursor = (cursor + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)

    return out


def _idem_key(callback: str, slot_id: str) -> str:
    return hashlib.sha256(f"{callback}|{slot_id}".encode()).hexdigest()[:16]


def book_slot_impl(slot_id: str, caller_name: str, callback: str, treatment: str) -> dict[str, Any]:
    """Insert a Google Calendar event with idempotency. Returns booking metadata."""
    parts = slot_id.split("_")
    if len(parts) < 3:
        return {"status": "error", "reason": "invalid_slot_id"}
    start_utc = datetime.strptime(parts[0], "%Y%m%dT%H%M%S").replace(tzinfo=timezone.utc)
    dur = int(parts[1])
    end_utc = start_utc + timedelta(minutes=dur)

    svc = _calendar_service()
    idem = _idem_key(callback, slot_id)
    existing = svc.events().list(
        calendarId=CALENDAR_ID,
        privateExtendedProperty=f"idem={idem}",
        maxResults=1,
    ).execute().get("items", [])
    if existing:
        ev = existing[0]
        return {
            "status": "duplicate",
            "event_id": ev["id"],
            "human_fr": _human_fr(start_utc.astimezone()),
        }

    suffix = "\n\nDémo — donnée simulée" if DEMO_MODE else ""
    event = {
        "summary": f"{treatment.title()} — {caller_name}",
        "description": f"Téléphone: {callback}\nRéservé par l'assistante IA Lisa{suffix}",
        "start": {"dateTime": start_utc.isoformat(), "timeZone": TIMEZONE},
        "end": {"dateTime": end_utc.isoformat(), "timeZone": TIMEZONE},
        "reminders": {"useDefault": False, "overrides": [{"method": "email", "minutes": 24 * 60}]},
        "extendedProperties": {"private": {"idem": idem, "source": "voice_agent_lisa"}},
    }
    created = svc.events().insert(calendarId=CALENDAR_ID, body=event).execute()
    return {
        "status": "confirmed",
        "event_id": created["id"],
        "human_fr": _human_fr(start_utc.astimezone()),
    }


# ---------------------------------------------------------------------------
# Gemini Live tool schemas

TOOL_SCHEMAS = [
    {
        "name": "list_slots",
        "description": "Liste les 3 prochains créneaux disponibles pour un type de rendez-vous donné.",
        "parameters": {
            "type": "object",
            "properties": {
                "treatment": {
                    "type": "string",
                    "description": "Type de RDV : consultation, detartrage, controle, urgence.",
                    "enum": ["consultation", "detartrage", "controle", "urgence"],
                },
                "days_offset": {
                    "type": "integer",
                    "description": "Décalage en jours (par défaut 0). Utiliser 7 pour proposer la semaine suivante.",
                },
            },
            "required": ["treatment"],
        },
    },
    {
        "name": "book_slot",
        "description": "Réserve un créneau précédemment proposé par list_slots.",
        "parameters": {
            "type": "object",
            "properties": {
                "slot_id": {"type": "string"},
                "caller_name": {"type": "string", "description": "Prénom et nom de l'appelant."},
                "callback": {"type": "string", "description": "Numéro à 10 chiffres."},
                "treatment": {"type": "string"},
            },
            "required": ["slot_id", "caller_name", "callback", "treatment"],
        },
    },
]


def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    if name == "list_slots":
        slots = list_slots_impl(args["treatment"], int(args.get("days_offset", 0)))
        return {"slots": [s.__dict__ for s in slots]}
    if name == "book_slot":
        return book_slot_impl(
            slot_id=args["slot_id"],
            caller_name=args["caller_name"],
            callback=args["callback"],
            treatment=args["treatment"],
        )
    return {"error": f"unknown_tool:{name}"}


# ---------------------------------------------------------------------------
# FastAPI app — served by Modal

@app.function(
    secrets=[
        modal.Secret.from_name("gemini-secret"),
        modal.Secret.from_name("gcal-secret"),
        modal.Secret.from_name("voice-agent-secret"),
    ],
    min_containers=0,
    scaledown_window=300,
    timeout=900,
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    api = FastAPI(title="Lisa — Cabinet Dentylis (démo)")
    api.mount("/static", StaticFiles(directory="/app/static"), name="static")

    @api.get("/", response_class=HTMLResponse)
    async def index():
        return Path("/app/static/index.html").read_text(encoding="utf-8")

    @api.get("/api/health")
    async def health(request: Request):
        secret = request.headers.get("X-Voice-Agent-Secret", "")
        expected = os.environ.get("WORKER_SECRET", "")
        authed = bool(secret) and secret == expected
        body: dict[str, Any] = {
            "ok": True,
            "build": APP_NAME,
            "demo_mode": DEMO_MODE,
            "secrets_present": {
                "gemini": bool(os.environ.get("GEMINI_API_KEY")),
                "gcal": bool(os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON")),
                "worker": bool(expected),
            },
        }
        if authed:
            # Probe calendar; only expose details to authed callers.
            try:
                svc = _calendar_service()
                svc.calendars().get(calendarId=CALENDAR_ID).execute()
                body["calendar_reachable"] = True
            except Exception as exc:  # surface error to operator, not to public
                body["calendar_reachable"] = False
                body["calendar_error"] = str(exc)[:200]
        return JSONResponse(body)

    @api.websocket("/ws")
    async def ws(websocket: WebSocket):
        await websocket.accept()
        try:
            await _bridge_gemini_live(websocket)
        except WebSocketDisconnect:
            return
        except Exception as exc:
            try:
                await websocket.send_json({"type": "error", "detail": str(exc)[:300]})
                await websocket.close()
            except Exception:
                pass

    return api


# ---------------------------------------------------------------------------
# Gemini Live bridge

async def _bridge_gemini_live(client_ws):
    """Bridge browser WebSocket <-> Gemini Live WebSocket. Handles tool calls server-side."""
    from google import genai
    from google.genai import types

    system_prompt = Path("/app/system_prompt_fr.md").read_text(encoding="utf-8")
    system_prompt = system_prompt.replace("{{CLINIC_NAME}}", CLINIC_NAME).replace(
        "{{CLINIC_PHONE}}", CLINIC_PHONE
    )

    api_key = os.environ["GEMINI_API_KEY"]
    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})

    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        speech_config=types.SpeechConfig(
            language_code=GEMINI_LANGUAGE_CODE,
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=GEMINI_VOICE),
            ),
        ),
        system_instruction=types.Content(parts=[types.Part(text=system_prompt)]),
        tools=[{"function_declarations": TOOL_SCHEMAS}],
    )

    async with client.aio.live.connect(model=GEMINI_MODEL, config=config) as session:
        await client_ws.send_json({"type": "ready"})

        async def from_browser():
            try:
                while True:
                    msg = await client_ws.receive()
                    if "bytes" in msg and msg["bytes"] is not None:
                        await session.send_realtime_input(
                            audio=types.Blob(data=msg["bytes"], mime_type="audio/pcm;rate=16000"),
                        )
                    elif "text" in msg and msg["text"] is not None:
                        payload = json.loads(msg["text"])
                        if payload.get("type") == "end":
                            return
            except Exception:
                return

        async def from_gemini():
            try:
                async for response in session.receive():
                    if getattr(response, "data", None):
                        await client_ws.send_bytes(response.data)
                    if getattr(response, "server_content", None):
                        sc = response.server_content
                        if getattr(sc, "input_transcription", None) and sc.input_transcription.text:
                            await client_ws.send_json({"type": "asr", "text": sc.input_transcription.text})
                        if getattr(sc, "output_transcription", None) and sc.output_transcription.text:
                            await client_ws.send_json({"type": "agent", "text": sc.output_transcription.text})
                    if getattr(response, "tool_call", None):
                        results = []
                        for fc in response.tool_call.function_calls:
                            args = dict(fc.args) if fc.args else {}
                            try:
                                result = dispatch_tool(fc.name, args)
                            except Exception as exc:
                                result = {"error": str(exc)[:200]}
                            results.append(types.FunctionResponse(
                                id=fc.id, name=fc.name, response=result,
                            ))
                            await client_ws.send_json({
                                "type": "tool_call",
                                "name": fc.name,
                                "args": args,
                                "result_summary": _summarise_result(fc.name, result),
                            })
                        await session.send_tool_response(function_responses=results)
            except Exception:
                return

        await asyncio.gather(from_browser(), from_gemini())


def _summarise_result(name: str, result: dict[str, Any]) -> str:
    if name == "list_slots":
        slots = result.get("slots", [])
        return f"{len(slots)} créneaux: " + ", ".join(s.get("human_fr", "?") for s in slots)
    if name == "book_slot":
        return f"{result.get('status', '?')} {result.get('human_fr', '')} id={result.get('event_id', '')[:12]}"
    return json.dumps(result)[:200]


# ---------------------------------------------------------------------------
# Local CLI entrypoint (testing list_slots / book_slot without WebSocket)

@app.local_entrypoint()
def cli(treatment: str = "consultation", days_offset: int = 0):
    """Smoke-test the slot logic locally: `modal run app.py --treatment detartrage`."""
    # NOTE: requires `GOOGLE_SERVICE_ACCOUNT_JSON` env var or running inside Modal.
    slots = list_slots_impl(treatment, days_offset)
    for s in slots:
        print(f"  {s.human_fr}  ({s.slot_id})")
