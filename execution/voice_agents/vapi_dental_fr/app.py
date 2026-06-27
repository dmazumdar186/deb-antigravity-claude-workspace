"""
description: Modal-hosted backend for the Vapi-driven French dental voice receptionist. Serves
the demo HTML widget (Vapi Web SDK) at `/`, and exposes two Vapi tool-call webhooks that proxy
to Cal.com v2 API: `/vapi/tools/list_slots` (GET /v2/slots/...) and `/vapi/tools/book_slot`
(POST /v2/bookings). Cal.com event-type is the operator's existing slug
`debanjan-mazumdar-ben5rd/30min` (overridable via env CALCOM_USERNAME + CALCOM_EVENT_SLUG).

inputs:
    Modal CLI:
        py -m modal deploy execution/voice_agents/vapi_dental_fr/app.py

    Modal secrets (deploy-time, set via `modal secret create`):
        vapi-dental-secret    bundles all keys:
                                CALCOM_API_KEY=cal_xxx (prefixed cal_, from cal.com/settings/developer/api-keys)
                                CALCOM_USERNAME=debanjan-mazumdar-ben5rd
                                CALCOM_EVENT_SLUG=30min
                                CALCOM_TIMEZONE=Europe/Paris
                                VAPI_PUBLIC_KEY=pk_... (browser-safe; from dashboard.vapi.ai → Web Calls)
                                VAPI_ASSISTANT_ID=asst_... (filled in by create_assistant.py)
                                WORKER_SECRET=... (random; gates /api/health auth)

    Static config (in this file):
        CLINIC_NAME, CLINIC_PHONE, DEMO_MODE

outputs:
    Public URLs after deploy:
        https://<workspace>--vapi-dental-fr-fastapi-app.modal.run/
            -> demo widget (loads Vapi Web SDK)
        /vapi/tools/list_slots, /vapi/tools/book_slot
            -> Vapi server-tool webhooks (referenced in the assistant config)
        /api/health
            -> readiness JSON

This file is intentionally LLM-free. The LLM lives at Vapi (BYO Gemini 3.1 Flash Live). This server's
only job is to translate Vapi tool-call payloads into Cal.com v2 REST calls.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import modal

APP_NAME = "vapi-dental-fr"
CLINIC_NAME = "Cabinet Dentylis"
CLINIC_PHONE = "01 85 00 57 05"
DEMO_MODE = True

CAL_API_BASE = "https://api.cal.com/v2"
CAL_API_VERSION = "2026-02-25"

image = (
    modal.Image.debian_slim(python_version="3.12")
    .pip_install(
        "fastapi==0.115.4",
        "uvicorn==0.32.0",
        "httpx==0.27.2",
        "pydantic==2.9.2",
    )
    .add_local_dir(
        Path(__file__).parent / "static",
        remote_path="/app/static",
    )
)

app = modal.App(APP_NAME, image=image)


# ---------------------------------------------------------------------------
# Cal.com client

def _cal_headers() -> dict[str, str]:
    return {
        "Authorization": f"Bearer {os.environ['CALCOM_API_KEY']}",
        "cal-api-version": CAL_API_VERSION,
        "Content-Type": "application/json",
    }


async def cal_list_slots(treatment: str, days_offset: int = 0) -> list[dict[str, Any]]:
    """Hit Cal.com /v2/slots; return up to 3 next slots as {slot_id, start_iso, human_fr}."""
    import httpx
    username = os.environ.get("CALCOM_USERNAME", "debanjan-mazumdar-ben5rd")
    slug = os.environ.get("CALCOM_EVENT_SLUG", "30min")
    tz = os.environ.get("CALCOM_TIMEZONE", "Europe/Paris")

    start = (datetime.now(timezone.utc) + timedelta(days=max(0, days_offset))).isoformat()
    end = (datetime.now(timezone.utc) + timedelta(days=max(0, days_offset) + 14)).isoformat()

    params = {
        "eventTypeSlug": slug,
        "username": username,
        "start": start,
        "end": end,
        "timeZone": tz,
    }
    async with httpx.AsyncClient(timeout=10.0) as cx:
        r = await cx.get(f"{CAL_API_BASE}/slots", headers=_cal_headers(), params=params)
        r.raise_for_status()
        body = r.json()

    # Cal.com v2 returns slots grouped by date. Flatten to a sorted list of ISO starts.
    data = body.get("data", body)
    flat: list[str] = []
    if isinstance(data, dict):
        for _date, day_slots in sorted(data.items()):
            if isinstance(day_slots, list):
                for s in day_slots:
                    iso = s.get("time") or s.get("start")
                    if iso:
                        flat.append(iso)
    elif isinstance(data, list):
        for s in data:
            iso = s.get("time") or s.get("start") if isinstance(s, dict) else None
            if iso:
                flat.append(iso)

    flat.sort()
    out = []
    for iso in flat[:3]:
        dt = datetime.fromisoformat(iso.replace("Z", "+00:00"))
        out.append({
            "slot_id": iso,  # iso string is the canonical slot id for Cal.com bookings
            "start_iso": iso,
            "human_fr": _human_fr(dt.astimezone()),
            "treatment": treatment,
        })
    return out


async def cal_book_slot(slot_id: str, caller_name: str, callback: str, treatment: str) -> dict[str, Any]:
    """POST /v2/bookings."""
    import httpx
    username = os.environ.get("CALCOM_USERNAME", "debanjan-mazumdar-ben5rd")
    slug = os.environ.get("CALCOM_EVENT_SLUG", "30min")
    tz = os.environ.get("CALCOM_TIMEZONE", "Europe/Paris")

    # Synthetic email from callback number — Cal.com v2 requires attendee.email.
    digits = "".join(c for c in callback if c.isdigit())
    fake_email = f"patient-{digits or 'demo'}@cabinet-dentylis-demo.local"

    payload = {
        "start": slot_id,
        "attendee": {
            "name": caller_name,
            "email": fake_email,
            "timeZone": tz,
        },
        "eventTypeSlug": slug,
        "username": username,
        "metadata": {
            "treatment": treatment,
            "callback_phone": callback,
            "source": "voice_agent_lisa",
            "demo_mode": str(DEMO_MODE).lower(),
        },
        # Cal.com supports "bookingFieldsResponses" for custom fields; left empty for demo
    }

    async with httpx.AsyncClient(timeout=10.0) as cx:
        r = await cx.post(f"{CAL_API_BASE}/bookings", headers=_cal_headers(), json=payload)
        if r.status_code == 409:
            return {"status": "duplicate", "reason": r.text[:200]}
        r.raise_for_status()
        body = r.json()

    data = body.get("data", body)
    event_id = data.get("id") or data.get("uid") or "unknown"
    iso_start = data.get("start") or slot_id
    dt = datetime.fromisoformat(iso_start.replace("Z", "+00:00"))
    return {
        "status": "confirmed",
        "event_id": str(event_id),
        "human_fr": _human_fr(dt.astimezone()),
    }


# ---------------------------------------------------------------------------
# FR date helpers

_FR_DAY = {0: "lundi", 1: "mardi", 2: "mercredi", 3: "jeudi", 4: "vendredi", 5: "samedi", 6: "dimanche"}
_FR_MONTH = {
    1: "janvier", 2: "février", 3: "mars", 4: "avril", 5: "mai", 6: "juin",
    7: "juillet", 8: "août", 9: "septembre", 10: "octobre", 11: "novembre", 12: "décembre",
}


def _human_fr(dt: datetime) -> str:
    h = f"{dt.hour}h" if dt.minute == 0 else f"{dt.hour}h{dt.minute:02d}"
    return f"{_FR_DAY[dt.weekday()]} {dt.day} {_FR_MONTH[dt.month]} à {h}"


# ---------------------------------------------------------------------------
# FastAPI app

@app.function(
    secrets=[modal.Secret.from_name("vapi-dental-secret")],
    min_containers=0,
    scaledown_window=300,
    timeout=120,
)
@modal.asgi_app()
def fastapi_app():
    from fastapi import FastAPI, Request, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from fastapi.staticfiles import StaticFiles

    api = FastAPI(title="Lisa — Cabinet Dentylis (Vapi)")
    api.mount("/static", StaticFiles(directory="/app/static"), name="static")

    @api.get("/", response_class=HTMLResponse)
    async def index():
        html = Path("/app/static/index.html").read_text(encoding="utf-8")
        html = html.replace("{{VAPI_PUBLIC_KEY}}", os.environ.get("VAPI_PUBLIC_KEY", ""))
        html = html.replace("{{VAPI_ASSISTANT_ID}}", os.environ.get("VAPI_ASSISTANT_ID", ""))
        html = html.replace("{{CLINIC_NAME}}", CLINIC_NAME)
        return html

    @api.get("/api/health")
    async def health(request: Request):
        secret = request.headers.get("X-Voice-Agent-Secret", "")
        expected = os.environ.get("WORKER_SECRET", "")
        body = {
            "ok": True,
            "build": APP_NAME,
            "demo_mode": DEMO_MODE,
            "secrets_present": {
                "calcom": bool(os.environ.get("CALCOM_API_KEY")),
                "vapi_public": bool(os.environ.get("VAPI_PUBLIC_KEY")),
                "vapi_assistant_id": bool(os.environ.get("VAPI_ASSISTANT_ID")),
                "worker": bool(expected),
            },
        }
        if secret and secret == expected:
            try:
                slots = await cal_list_slots("consultation", 0)
                body["cal_reachable"] = True
                body["sample_slot"] = slots[0]["human_fr"] if slots else None
            except Exception as exc:
                body["cal_reachable"] = False
                body["cal_error"] = str(exc)[:200]
        return JSONResponse(body)

    @api.post("/vapi/tools/list_slots")
    async def t_list_slots(request: Request):
        # Vapi tool-call shape: { message: { toolCalls: [{ id, function: { name, arguments } }] } }
        payload = await request.json()
        results = []
        for tc in _extract_tool_calls(payload):
            try:
                args = _parse_args(tc)
                slots = await cal_list_slots(
                    treatment=args.get("treatment", "consultation"),
                    days_offset=int(args.get("days_offset", 0)),
                )
                results.append({"toolCallId": tc["id"], "result": {"slots": slots}})
            except Exception as exc:
                results.append({"toolCallId": tc["id"], "error": str(exc)[:200]})
        return {"results": results}

    @api.post("/vapi/tools/book_slot")
    async def t_book_slot(request: Request):
        payload = await request.json()
        results = []
        for tc in _extract_tool_calls(payload):
            try:
                args = _parse_args(tc)
                booking = await cal_book_slot(
                    slot_id=args["slot_id"],
                    caller_name=args["caller_name"],
                    callback=args["callback"],
                    treatment=args.get("treatment", "consultation"),
                )
                results.append({"toolCallId": tc["id"], "result": booking})
            except Exception as exc:
                results.append({"toolCallId": tc["id"], "error": str(exc)[:200]})
        return {"results": results}

    return api


def _extract_tool_calls(payload: dict[str, Any]) -> list[dict[str, Any]]:
    msg = payload.get("message", payload)
    calls = msg.get("toolCalls") or msg.get("tool_calls") or []
    return [c for c in calls if isinstance(c, dict) and c.get("id")]


def _parse_args(tc: dict[str, Any]) -> dict[str, Any]:
    fn = tc.get("function", {})
    raw = fn.get("arguments", "{}")
    if isinstance(raw, str):
        return json.loads(raw or "{}")
    return raw or {}


# ---------------------------------------------------------------------------
# Local CLI: smoke-test the Cal.com proxy without going through Vapi

@app.local_entrypoint()
def cli(treatment: str = "consultation"):
    import asyncio
    slots = asyncio.run(cal_list_slots(treatment, 0))
    for s in slots:
        print(f"  {s['human_fr']}  ({s['slot_id']})")
