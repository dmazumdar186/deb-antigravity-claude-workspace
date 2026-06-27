# Cabinet Dentylis — Lisa (Vapi + Cal.com)

French dental voice receptionist on **Vapi** (programmatic, no GUI), with **Gemini 3.1 Flash Live** as the LLM (BYO key) and **Cal.com v2** as the booking backend (operator's existing `debanjan-mazumdar-ben5rd` account).

## Architecture (1 image, 0 words)

```
browser ── Vapi Web SDK ── Vapi audio backend ── Gemini 3.1 Flash Live (BYO)
                                  │
                                  ↓  (tool calls, server-side)
                          Modal app /vapi/tools/*
                                  │
                                  ↓
                            Cal.com v2 API
```

## Files

| File | Purpose |
|---|---|
| `app.py` | Modal-hosted FastAPI: serves the HTML widget + 2 Vapi tool webhooks → Cal.com |
| `create_assistant.py` | One-shot Vapi REST POST to create / update the assistant |
| `static/index.html` | Browser widget loading the Vapi Web SDK |
| (`system_prompt_fr.md` lives at `../gemini_live_dental_fr/system_prompt_fr.md` — shared with the self-host fallback) |

## Prerequisites (.env)

The following must be present in the workspace `.env`:

| Key | Where to get it | Already present? |
|---|---|---|
| `VAPI_API_KEY` | dashboard.vapi.ai → API Keys (private) | **gap** |
| `VAPI_PUBLIC_KEY` | dashboard.vapi.ai → API Keys (web, public) | **gap** |
| `CALCOM_API_KEY` | cal.com/settings/developer/api-keys (prefixed `cal_`) | **gap** |
| `GEMINI_API_KEY` | Google AI Studio | ✓ present |
| `MODAL_TOKEN_ID`, `MODAL_TOKEN_SECRET` | Modal CLI | ✓ present |

## Operator decisions owed (one-time)

1. **Cal.com event-type slug.** Default in `app.py` is `30min` (the slug from the portfolio site). For a dental demo we'd ideally use a dedicated event type like `cabinet-dentaire-consultation`. Either:
   - Keep `30min` for the demo (re-uses the existing portfolio CTA event), OR
   - Create a fresh event type in Cal.com (5-min UI click) and set `CALCOM_EVENT_SLUG` to its slug.
2. **Vapi voice id.** `create_assistant.py` ships with a placeholder Cartesia FR voice id. Verify against your Vapi catalogue before first call — the dashboard at dashboard.vapi.ai shows the actual ids of currently-available FR voices.
3. **CNIL recording.** Vapi records calls by default for transcript debugging. For the demo this is acceptable (no patient data). For Phase 5 (production) the `recordingEnabled: false` flag must be added to the assistant config OR storage must move to HDS.

## Deploy

```bash
# 1. Set the Modal secret bundle (one-time, before first deploy)
py -m modal secret create vapi-dental-secret \
   CALCOM_API_KEY=cal_xxx \
   CALCOM_USERNAME=debanjan-mazumdar-ben5rd \
   CALCOM_EVENT_SLUG=30min \
   CALCOM_TIMEZONE=Europe/Paris \
   VAPI_PUBLIC_KEY=pk_xxx \
   VAPI_ASSISTANT_ID=placeholder_for_now \
   WORKER_SECRET=$(openssl rand -hex 32)

# 2. Deploy the Modal app (gets you the tools URL)
py -m modal deploy execution/voice_agents/vapi_dental_fr/app.py
#   prints something like:
#     https://debanjan186--vapi-dental-fr-fastapi-app.modal.run

# 3. Create the Vapi assistant pointing to the Modal tools URL
TOOLS_SERVER_URL=https://debanjan186--vapi-dental-fr-fastapi-app.modal.run \
py execution/voice_agents/vapi_dental_fr/create_assistant.py
#   prints something like:
#     OK    assistant_id=asst_abc123...

# 4. Re-create the Modal secret with the real VAPI_ASSISTANT_ID and re-deploy
py -m modal secret create vapi-dental-secret \
   CALCOM_API_KEY=cal_xxx \
   ... \
   VAPI_ASSISTANT_ID=asst_abc123 \
   WORKER_SECRET=$(openssl rand -hex 32)
py -m modal deploy execution/voice_agents/vapi_dental_fr/app.py

# 5. Open the URL printed in step 2 → click "Parler à Lisa"
```

## Test

The `tests/acceptance_voice_agent.py` corpus is **stack-agnostic** — it asserts on tool-call logic, not on Vapi or Modal specifics. It passes against both paths.

```bash
py tests/acceptance_voice_agent.py
```

The front-door synthetic for this build is `tests/front_door_voice_agent.sh` (works against any deployed app exposing `/api/health` + `/` widget; no Vapi-specific calls).

## Smoke-test Cal.com proxy locally (no deploy needed)

```bash
# requires CALCOM_API_KEY in env or .env
py -m modal run execution/voice_agents/vapi_dental_fr/app.py::cli --treatment consultation
```

Prints 3 next available slots from your Cal.com `30min` event type.

## Fallback path

The companion build `execution/voice_agents/gemini_live_dental_fr/` is the **self-host fallback** (Modal + Gemini Live native audio, no third-party platform). Use it if a client refuses Vapi, or as a portable demo for clinics outside France.
