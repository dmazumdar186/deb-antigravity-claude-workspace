# Directive — French Dental Voice Receptionist

**Category:** voice_agents
**Two implementations, same contract:**

| Path | Script | When to use |
|---|---|---|
| **A. Vapi + Cal.com (primary)** | `execution/voice_agents/vapi_dental_fr/app.py` + `create_assistant.py` | Operator pitch demo; clinic pilot. Uses operator's existing Vapi + Cal.com accounts. |
| **B. Gemini Live + Modal (self-host fallback)** | `execution/voice_agents/gemini_live_dental_fr/app.py` | Clinic refuses third-party voice platform; or portability test. |

**Status:** Phase 1 pitch-stub. Phase 4 production gated on first paying clinic. Phase 5 RGPD hard gate before any real patient call.

## Prior art pass

**Public API check (Vapi path).** Vapi REST API: `POST https://api.vapi.ai/assistant` creates the assistant programmatically (no GUI). BYO Gemini key (`model.provider="google", model.customApiKey=...`). Built-in transcriber (Deepgram FR `transcriber.language="fr"`) and voice (Cartesia FR via catalogue). Tools fire as POST webhooks to `tools[].server.url`. Vapi Web SDK (`@vapi-ai/web` from esm.sh) embeds in any HTML page using the public key.

**Public API check (Gemini Live path).** Current Live API model (June 2026): `gemini-3.1-flash-live-preview` (ai.google.dev/gemini-api/docs/models/gemini-3.1-flash-live-preview). Single WebSocket handles ASR + LLM + native-audio TTS in one stream. Voice: Aoede (FR-proven on 2026-06-19 in `execution/personal_workflows/prodcraft_orchestrate.py:40-44`).

**Cal.com v2.** `GET /v2/slots/get-available-time-slots-for-an-event-type` + `POST /v2/bookings`. Header `cal-api-version: 2026-02-25`, auth `Bearer cal_xxx`. Operator's existing username: `debanjan-mazumdar-ben5rd`. Default event slug: `30min` (already wired into portfolio site CTAs).

**GitHub prior-art.** `vapi-ai/server-sdk-python`, `livekit/agents`, `kirklandsig/AIReceptionist`. No dedicated French-dental project.

**Recommended architecture (Path A — primary).** Vapi handles all audio + speech + LLM via BYO Gemini 3.1 Flash Live. Modal-hosted FastAPI proxies the 2 tool calls to Cal.com v2. Static HTML widget embeds the Vapi Web SDK. Demo URL = the Modal `/` page.

**Recommended architecture (Path B — fallback).** Modal-hosted FastAPI with `/ws` WebSocket bridging browser audio ↔ Gemini Live ↔ Google Calendar service account. Same UX, zero third-party voice dependency.

## Goal

A French-speaking AI agent reachable from any browser that:

1. Greets the caller in FR with the clinic name and assistant name "Lisa".
2. Asks for caller name + reason (consultation / détartrage / urgence / contrôle).
3. Calls `list_slots(treatment)` → returns 3 next slots within the next 14 working days.
4. Reads the 3 slots aloud; lets caller pick or ask for alternatives.
5. Calls `book_slot(slot_id, caller_name, callback_number, treatment)` → returns booking ID.
6. Confirms the booking ID + slot + clinic phone for human follow-up.
7. Hands off to "opérateur" on urgence keywords or on caller request.

## Inputs

- **Env (from `.env`):**
  - `GEMINI_API_KEY` — Gemini Live access (free tier acceptable for demo).
  - `GOOGLE_SERVICE_ACCOUNT_PATH` — path to `credentials/service_account.json`. Service account must have edit access to the demo Google Calendar (`vitry-dental-demo@<...>.iam.gserviceaccount.com` shared into the calendar with "Make changes to events" permission).
  - `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` — Modal CLI auth (already present).
- **Modal secrets** (deploy-time): `gemini-secret` (GEMINI_API_KEY), `gcal-secret` (base64-encoded service-account JSON), `voice-agent-secret` (WORKER_SECRET for `/api/health` auth).
- **Static config (`app.py` constants):**
  - `CLINIC_NAME` — defaults to "Cabinet Dentylis" for the pitch demo. Per-clinic deploys override.
  - `CALENDAR_ID` — Google Calendar ID for the demo calendar (or clinic calendar in Phase 4).
  - `BUSINESS_HOURS` — `{"start": "09:00", "end": "19:00", "lunch": ["12:30", "14:00"], "closed": ["sun"]}`.
  - `TREATMENT_DURATIONS_MIN` — `{"consultation": 20, "detartrage": 30, "urgence": 30, "controle": 20}`.

## Conversation graph

```
START
  → greet (FR, clinic name, "Lisa", consent line, "opérateur" + "urgence" escape words)
  → collect_intent (treatment classification + caller name)
       ├─ urgence keywords ("très mal", "abcès", "saigne", "cassé")
       │     → handoff_message ("Je vous transfère immédiatement au cabinet.")
       │     → END (no booking)
       └─ other treatments
              → ask_callback (collect FR phone number, validate 10 digits starting 0)
              → tool: list_slots(treatment, today_iso)
              → read_slots (TTS reads 3 slots in natural FR)
              → ask_choice
                    ├─ caller picks #1/#2/#3 or "le premier qui se libère"
                    │     → tool: book_slot(...)
                    │     → confirm (booking ID + slot + clinic phone)
                    │     → END
                    ├─ caller asks for other slots
                    │     → tool: list_slots(treatment, days_offset=+7)
                    │     → loop (max 2 iterations, then handoff)
                    └─ caller says "opérateur"
                          → handoff_message → END
```

## Tool contracts

### `list_slots(treatment: str, days_offset: int = 0) -> list[Slot]`

Returns up to 3 `{slot_id, start_iso, end_iso, human_fr}` objects.

- Reads Google Calendar `freeBusy` over `now+days_offset` → `now+days_offset+14d`.
- Skips `BUSINESS_HOURS.closed` days, lunch windows, and busy intervals.
- Generates 20- or 30-minute slots per `TREATMENT_DURATIONS_MIN[treatment]`.
- Returns the 3 earliest.
- `human_fr` example: `"mardi 30 juin à 9h30"`.

### `book_slot(slot_id: str, caller_name: str, callback: str, treatment: str) -> dict`

- Inserts a Google Calendar event:
  - Title: `f"{treatment.title()} — {caller_name}"`
  - Description: `f"Téléphone: {callback}\nRéservé par l'assistante IA Lisa\nDémo — donnée simulée"` (Phase 1)
  - Start/end: from `slot_id` decode.
  - Reminder: 1 day before, email.
- Idempotency: hash `(callback, slot_id)` → if same hash booked in last 24 h, return existing event ID without double-booking.
- Returns `{"event_id": "...", "human_fr": "...", "status": "confirmed" | "duplicate"}`.

## Edge cases & failure modes

| Case | Handling |
|---|---|
| Caller silent for > 8 s | Re-prompt once. After 2nd silence, polite close + hangup. |
| Caller speaks English only | Auto-detect via Gemini Live; respond `"I'll connect you to a human, please hold."` + `END`. |
| Caller speaks accented FR (Maghrebi, sub-Saharan) | Gemini Live handles natively per published benchmarks; if intent classification drops, fall back to "opérateur" rather than guess. Acceptance corpus includes 1 accented sample. |
| Off-hours / Sunday | `list_slots` returns next valid slot regardless. Greet line acknowledges if outside business hours: `"Nous sommes fermés pour le moment, mais je peux quand même vous proposer un rendez-vous."`. |
| Caller says "euh" (FR filler) | Gemini Live's voice activity detection handles this natively; do not enable Pipecat's aggressive barge-in. |
| Google Calendar 5xx | Server-side retry × 2 with backoff. On final failure: `"Je rencontre un problème technique, un humain vous rappelle dans l'heure. Pouvez-vous me confirmer votre numéro ?"` + log to Modal stderr. |
| Same caller phones twice within 24 h | Idempotency hash → `"Bonjour, je vois que vous avez déjà rendez-vous le X. Souhaitez-vous le modifier ?"` |

## CNIL / RGPD note (in greeting)

Opening line MUST include the demo disclaimer:

> *"Bonjour, vous êtes au Cabinet Dentylis. Je suis Lisa, votre assistante. Cet appel est traité par une intelligence artificielle. Si vous préférez un humain, dites « opérateur » à tout moment. Pour une urgence avec forte douleur, dites « urgence »."*

**Phase 1 (demo, browser, no real patient data):** no recording. No data persisted beyond the booking row in the demo Google Calendar.
**Phase 5 (production, real patients):** explicit consent prompt, recording stored on HDS-certified host, DPIA filed, EU AI Act high-risk notice published. Hard gate per the plan.

## System prompt

Lives in `execution/voice_agents/gemini_live_dental_fr/system_prompt_fr.md`. Loaded at Modal app startup.

## Acceptance

Frozen 9-conversation corpus in `tests/fixtures/voice_agent/corpus.json`. `tests/acceptance_voice_agent.py` exits non-zero on any drift (per `~/.claude/rules/output-acceptance-gate.md`). Front-door synthetic `tests/front_door_voice_agent.sh` hits `/api/health` + the static `/index.html` and the WebSocket handshake.

## How to deploy

```bash
# Phase 1 — demo
py -m modal deploy execution/voice_agents/gemini_live_dental_fr/app.py
# Outputs: https://<workspace>--gemini-live-dental-fr-fastapi-app.modal.run/
```

The URL is the demo. Share it via QR code on the pitch one-pager.

## How to test

```bash
bash tests/front_door_voice_agent.sh       # health + handshake
py tests/acceptance_voice_agent.py         # 9-conversation corpus
```

Manual pre-pitch dogfood: open the demo URL in a phone browser, run the 5 FR scenarios in `tests/fixtures/voice_agent/pre_pitch_scripts_fr.md`, listen back, confirm Google Calendar events.

## Per-clinic clone procedure (Phase 4+)

1. Copy `execution/voice_agents/gemini_live_dental_fr/` → `execution/voice_agents/gemini_live_<clinic_slug>/`.
2. Edit `CLINIC_NAME`, `CALENDAR_ID`, `BUSINESS_HOURS` in `app.py`.
3. If clinic provides their own Google Calendar: clinic owner shares the calendar with the workspace service account email (no OAuth flow — service-account model bypasses Phase 4's planned OAuth pain).
4. Redeploy: `modal deploy`. New URL.
5. Update Pitch one-pager with new URL + QR. New `tests/acceptance_voice_agent_<slug>.py` references the same corpus with clinic-name substitution.
