# Cabinet Dentylis — Lisa (Gemini Live + Modal)

French dental voice receptionist. Modal-hosted FastAPI app proxying browser audio to Google Gemini Live, with two server-side tools (`list_slots`, `book_slot`) that read/write a Google Calendar via the workspace service account.

## One-shot deploy

```bash
# 1. Create three Modal secrets (one-time)
py -m modal secret create gemini-secret GEMINI_API_KEY=$(grep ^GEMINI_API_KEY ../../../.env | cut -d= -f2-)
py -m modal secret create gcal-secret GOOGLE_SERVICE_ACCOUNT_JSON="$(cat ../../../credentials/service_account.json)"
py -m modal secret create voice-agent-secret WORKER_SECRET=$(openssl rand -hex 32)

# 2. Share the demo calendar with the service-account email (gives it edit rights)
#    (manual step in Google Calendar UI — one-time)

# 3. Deploy
py -m modal deploy app.py
```

Modal prints the public URL. That URL is the demo. Open it in any browser.

## Files

| File | Purpose |
|---|---|
| `app.py` | Modal app + FastAPI + Gemini Live bridge + Calendar tools |
| `system_prompt_fr.md` | Lisa's persona, conversation rules, urgence transfer logic |
| `static/index.html` | Browser widget (vanilla JS, no build step) |
| `requirements.txt` | Pinned versions (Modal builds the image from these via `pip_install`) |

## Test

```bash
# From workspace root
bash tests/front_door_voice_agent.sh
py tests/acceptance_voice_agent.py
```

## Per-clinic clone

See `directives/voice_agents/dental_receptionist_fr.md` § "Per-clinic clone procedure".

## Phase 5 (production, real patients) hard gate

Before flipping `DEMO_MODE = False`:
1. RGPD data-processing agreement signed.
2. KV / event storage migrated to HDS-certified host (OVH HDS or Outscale).
3. DPIA filed per CNIL+HAS Feb-2026 guide.
4. Greeting recording-consent line activated.
5. EU AI Act high-risk transparency notice published (deadline 2026-08-02).
