# HANDOFF — Dental voice agent (Vapi + Cal.com + CF Worker)

**Iteration 4** · **2026-06-26 late evening** · ENGLISH-ONLY pivot per operator decision

## ⚡ Latest decision (read first)

Operator: *"Ignore multilingual, just focus on English for now. Anyway this is for demo purposes."*

**Acted on in iteration 4 — already live:**
- Voice swapped to **Azure `en-US-AriaNeural`** (true native American English, NOT a multilingual model — this eliminates the accent-contamination problem at the source).
- Transcriber `language: "en"` (Deepgram nova-2 single-language English). Single-language ASR is significantly more accurate on proper nouns than `multi` mode.
- System prompt rewritten English-only at `execution/voice_agents/gemini_live_dental_fr/system_prompt.md`. Foreign-name handling rule kept (names are data, never trigger handoff). Spell-the-name fallback added explicitly to Step 2.
- Widget banner stripped to English-only.
- Vapi assistant PATCHed live, Worker redeployed.

**Awaiting operator listen-test.** If `en-US-AriaNeural` still doesn't sound right, next escalation tier in priority order: `en-US-JennyNeural` (alternative native Am-English female), `en-US-AndrewMultilingualNeural` (male), OpenAI `tts-1` `nova`, ElevenLabs `Sarah` (`EXAVITQu4vr4xnSDxMaL`).

**If "Debanjan" recognition still fails on English-only single-language ASR**, escalate as follows in this order: (1) lower Deepgram `endpointing` to 200ms to capture trailing characters, (2) make Lisa's Step 2 explicitly demand a spell-out ("Could you spell that, letter by letter?"), (3) raise the keyword boost weight from `:2` to `:3` for Debanjan/Mazumdar/Patel.

The bilingual-support corpus + simulator (12/12 green) is retained on disk for future revival — no need to delete. The live LIVE assistant is monolingual English; the corpus tests are stack-agnostic so they continue to pass.

---

## 🟢 Paste this into the new conversation (and nothing else)

> Read `docs/handoff/voice_agent_dental_2026-06-26.md` end-to-end before doing anything. The dental voice agent at https://vapi-dental-fr.debanjan186.workers.dev is **still broken** after three iterations:
>
> 1. The English voice has a heavy French accent
> 2. The French voice has an English accent in the closing bilingual sentence
> 3. Lisa cannot reliably understand foreign-origin names like "Debanjan" even with the Deepgram keyword boost
>
> The operator's verbatim listen-test reports are quoted in the doc — trust them as the only ground truth. You cannot hear the voice yourself.
>
> Three concrete architectural pivots are pre-evaluated in the doc (§ "Next session — choose ONE pivot"). Pick one, get the operator's blessing in two lines, execute, and tell the operator to refresh and listen. Do not iterate prompts again before changing the voice architecture.
>
> Account safety: this build runs on `debanjan186@gmail.com`'s Cloudflare account (NOT the AM-locked one). Always `wrangler whoami` to confirm `account_id=1bd372ca60ff5733565863799237e83b` before any deploy.

---

## What is live right now

- **URL:** https://vapi-dental-fr.debanjan186.workers.dev
- **Worker:** `vapi-dental-fr` on Cloudflare account `debanjan186@gmail.com` (cached OAuth — `.env` `CLOUDFLARE_API_TOKEN` is invalid, **always** `env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID ./node_modules/.bin/wrangler …` when shelling out)
- **Vapi assistant:** `5632bd9d-950e-4e8e-99da-e3717d8c3a2d` — current config: Azure `en-US-EmmaMultilingualNeural`, Deepgram `nova-2` with `language: "multi"` + 33-keyword boost list, Gemini `gemini-3.5-flash`, bilingual system prompt with strict 9-step turn-locked flow + foreign-name-is-not-language rule
- **Cal.com:** live, hitting operator's `debanjan-mazumdar-ben5rd/30min` event via header `cal-api-version: 2024-09-04`, date-only params
- **Acceptance corpus:** 12/12 must-pass green (`tests/acceptance_voice_agent.py`) — but **the corpus only tests tool-call sequencing, not voice quality**. The acceptance gate cannot catch the bugs the operator is hearing.

---

## What the operator has reported, verbatim

**Listen-test 1 (initial deploy):**
> "I tried to book and it asks for name when it asks how can it help me and then even if I tell it my name, it asks again my name and phone number, also the call ends once I give it my phone number, it cannot check my phone number, don't bundle 2 data items like name phone number, what they are looking for, also the English which is French accented when the operator starts talking is in a very bad accent and noone can understand it, make sure the accent is Parisian French and American English all throughout"

**Listen-test 2 (after first prompt rewrite + Ava → Emma):**
> "Hello, I'm Lisa. Everything else. She is talking in a French accent. Hello, this code is intended by a system and then it continues like that. That is not what I said. That is not the expectation."

**Listen-test 3 (after foreign-name fix + Deepgram keywords + ask-don't-handoff prompt):**
> "It is still not recognizing my first name. I don't know, it is totally broken. The second thing is regarding the accent. It is very much a French accent and then in the last sentence where it says that you can either speak in English or vous parler only, that is again like French in an English accent, someone who doesn't know how to speak French. It's a mixed bag. It is very broken. This entire system is broken."

Three iterations, three failures. **Stop patching prompts. The architecture is wrong.**

---

## Why the architecture is wrong (read this before doing anything)

I tried to make ONE Azure multilingual voice do both Parisian French AND American English. This is fundamentally a known limitation:

- **Azure `en-US-AvaMultilingualNeural`** is primarily American-English-trained. Vapi's TTS pipeline appears to be sending it French-locale-hinted text, so its English output gets accent-contaminated.
- **Azure `en-US-EmmaMultilingualNeural`** is the same model family, different voice id. Same problem — operator confirmed English is still French-accented.
- **Both voices** when asked to speak FR text produce passable French but with English-sounding consonants in places. Operator quote (iteration 3): "the last sentence where it says that you can either speak in English or vous parler only, that is again like French in an English accent".

**A multilingual voice that sounds genuinely native in BOTH languages does not exist in Azure's catalogue.** The next session must accept this constraint and pick a different architecture.

---

## Next session — choose ONE pivot (pre-evaluated, do not invent a fourth)

### Pivot A — Two voices, dynamic per-language routing  ⭐ recommended

Vapi assistants support an `assistantOverrides` or `voice.fallbackPlan` style per-language voice config. Use a **true native Parisian French voice** for FR output and a **true native American English voice** for EN output, switched dynamically by the transcriber's per-turn language detection.

Concrete config to try first:
```python
"voice": {
    "provider": "azure",
    "voiceId": "fr-FR-DeniseNeural",   # native Parisian FR — operator approved it as a sound previously
    "fallbackPlan": {
        "voices": [
            {"provider": "azure", "voiceId": "en-US-AriaNeural"},  # native American EN
        ],
    },
},
```

If Vapi's `fallbackPlan` doesn't switch by language (check the Vapi assistant docs at https://docs.vapi.ai/assistants — the field name keeps shifting), the alternative is **two assistants + a router**: one FR-only with `fr-FR-DeniseNeural`, one EN-only with `en-US-AriaNeural`, a tiny landing page asking "Français? English?" that dispatches to the right assistant id. Slightly more code but bulletproof.

**Pros:** Each language sounds genuinely native. Operator's stated requirement ("Parisian French and American English all throughout") is literally achievable.
**Cons:** More config; requires Vapi API knowledge of per-language routing.

### Pivot B — ElevenLabs `eleven_multilingual_v2`

ElevenLabs has voices specifically rated as "bilingual native" by their own community. Best candidates: **Charlotte** (`XB0fDUnXU5powFXDhCwa`) or **Sarah** (`EXAVITQu4vr4xnSDxMaL`). Config:
```python
VOICE_PROVIDER = "11labs"
VOICE_ID = "XB0fDUnXU5powFXDhCwa"  # Charlotte
# Add: "model": "eleven_multilingual_v2"
```

**Prereq:** operator's Vapi account must have ElevenLabs API key wired (dashboard.vapi.ai → Providers → ElevenLabs). Ask the operator BEFORE attempting — if they haven't, it's a 30-second UI click.

**Pros:** Single voice config, no routing complexity, known good multilingual quality.
**Cons:** ElevenLabs is the most expensive Vapi voice provider (~$0.10/min on top of the other components — fine for a demo, watch costs in production).

### Pivot C — Monolingual flow, caller picks language at start

Greet caller with a short bilingual ask: *"For French press one or say 'français'. For English press two or say 'English'."* On detection, switch the assistant's `language`, `voice`, and system prompt to the chosen language. Rest of the call is **monolingual** — Lisa speaks only the picked language with a true native voice (`fr-FR-DeniseNeural` OR `en-US-AriaNeural`), with no accent contamination.

**Pros:** Each call uses a native single-language voice. No multilingual contamination possible. Implementation is the simplest of the three.
**Cons:** Slightly higher friction for the caller (one extra choice). Doesn't satisfy "feel free to switch languages mid-call" — but no one asked for that anyway.

### How to decide

Open the new context window, paste the operator opener at the top, and ask them this single question:

> "Three options for the voice fix: (A) two voices switched dynamically per-utterance, (B) one ElevenLabs Charlotte voice if your Vapi account has the ElevenLabs provider wired, (C) monolingual — caller picks French or English at the start of the call. Which one do we ship?"

Then execute. Single PATCH cycle (~30 seconds), have the operator refresh and listen, iterate the voice ID once or twice if the chosen pivot still doesn't satisfy them. **Do not touch the system prompt this round** — the operator's complaint is purely auditory now.

---

## The foreign-name problem (Bug C from iteration 3)

Independent of the accent fix, the operator reports Lisa still doesn't recognize "Debanjan" reliably. What was tried:

- Deepgram `keywords` boost list added with 33 entries including Debanjan:2, Mazumdar:2, Patel:2, Diallo:2, etc. (boost weight `:2` per Deepgram's docs)
- ASCII-only (Vapi rejected the original list because it contained `é` and `'` — Deepgram keyword syntax requires ASCII)
- System prompt rule rewritten: foreign names are NEVER a language signal; ask-to-spell if unclear

If after the voice pivot the name recognition is STILL broken, the next escalation tier is:
1. **Tighten the transcriber language** — drop `multi` mode and fix language explicitly to `fr` or `en` after Pivot C makes the call monolingual. Deepgram single-language models are noticeably more accurate than multi-language detect mode for proper nouns.
2. **Spell-the-name fallback in the prompt** — make Lisa's Step 2 (first name) explicitly say: *"Quel est votre prénom ? Pouvez-vous me l'épeler, s'il vous plaît ? — Could you spell your first name for me?"*. Spelled letter-by-letter, ASR accuracy on names goes near 100%.
3. **Vapi `endpointing`** — lower it to capture trailing characters of a name that the caller pronounces softly.

Don't preemptively do all three — try Pivot C (monolingual) first; if `transcriber.language: "fr"` alone solves the name issue, you're done.

---

## Lockdown reminder — do not touch

Per `CLAUDE.local.md`: **Accessory Masters is fully locked**.
- ✅ This build runs under `debanjan186@gmail.com`'s CF account (`1bd372ca60ff5733565863799237e83b`). Confirm via `wrangler whoami` every session.
- ❌ Never deploy under any other CF account.
- ❌ Never modify anything under `execution/infrastructure/api-proxy/`.
- ❌ Never use any AM credentials (Instantly, GHL, Million Verifier, AnyMailFinder, AM Worker secrets).

---

## Key files

| Path | Role |
|---|---|
| `execution/voice_agents/vapi_dental_fr/create_assistant.py` | POSTs/PATCHes the Vapi assistant. Edit voice provider + id here. Idempotent — reads `VAPI_ASSISTANT_ID` from `.env`, PATCHes if set, POSTs if not. |
| `execution/voice_agents/gemini_live_dental_fr/system_prompt.md` | The shared bilingual system prompt. Lisa's persona, the 9-step turn-locked flow, urgence keywords, hard rules, foreign-name rule. |
| `execution/voice_agents/vapi_dental_fr/worker/src/{index,calcom,widget}.ts` | Worker (router, Cal.com client, HTML widget). |
| `tests/fixtures/voice_agent/corpus.json` | 12 frozen conversations (FR ×3, EN ×2 including foreign-name regression, urgence × 2, operator handoff, German full-sentence OOS, hostile, dedup, +1 soft Maghrebi accent). |
| `tests/acceptance_voice_agent.py` | Stack-agnostic acceptance gate. 12/12 must-pass green when handed off. **Does not test voice quality** — that's the operator's job. |
| `directives/voice_agents/dental_receptionist_fr.md` | Full directive — documents both Vapi (primary) and Gemini Live (fallback) paths. |

---

## Deploy commands (copy-paste)

### PATCH the Vapi assistant after editing voice / prompt
```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
py - <<'PY'
import sys, os, subprocess
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
from dotenv import load_dotenv
load_dotenv(".env")
env = os.environ.copy()
env["TOOLS_SERVER_URL"] = "https://vapi-dental-fr.debanjan186.workers.dev"
r = subprocess.run(["py", "execution/voice_agents/vapi_dental_fr/create_assistant.py"],
                   capture_output=True, text=True, env=env,
                   encoding="utf-8", errors="replace")
print(r.stdout or ""); print(r.stderr or "", file=sys.stderr)
sys.exit(r.returncode)
PY
```

### Redeploy the Worker (only if you edit `worker/src/*.ts`)
```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/voice_agents/vapi_dental_fr/worker"
env -u CLOUDFLARE_API_TOKEN -u CLOUDFLARE_ACCOUNT_ID ./node_modules/.bin/wrangler deploy
```

### Acceptance corpus
```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
py tests/acceptance_voice_agent.py
```

### Front-door synthetic against live Worker
```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
py - <<'PY'
import sys, os, json, urllib.request
try: sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception: pass
from dotenv import load_dotenv
load_dotenv(".env")
URL = "https://vapi-dental-fr.debanjan186.workers.dev"
UA  = "vapi-dental-fr-frontdoor/1.0"
S   = os.environ["VOICE_AGENT_WORKER_SECRET"]
def get(p, auth=False):
    r = urllib.request.Request(URL+p); r.add_header("User-Agent", UA)
    if auth: r.add_header("X-Voice-Agent-Secret", S)
    return urllib.request.urlopen(r, timeout=20).read().decode("utf-8", errors="replace")
print("index ok:", "Cabinet Dentylis" in get("/"))
print("health:", json.loads(get("/api/health"))["secrets_present"])
print("cal sample:", json.loads(get("/api/health", auth=True)).get("sample_slot"))
PY
```

---

## .env keys

```
VAPI_API_KEY=…
VAPI_PUBLIC_KEY=…
VAPI_ASSISTANT_ID=5632bd9d-950e-4e8e-99da-e3717d8c3a2d
CALCOM_API_KEY=cal_…
GEMINI_API_KEY=AIza…
MODAL_TOKEN_ID=ak-…   # not used (CF Workers is the host)
MODAL_TOKEN_SECRET=as-…
VOICE_AGENT_WORKER_SECRET=…  # auto-generated; gates /api/health auth
CLOUDFLARE_API_TOKEN=…       # ⚠️ INVALID — wrangler uses cached OAuth instead
```

---

## What's been tried (don't repeat)

1. **Modal + Gemini Live native audio** — abandoned due to Modal workspace billing cap. Code preserved at `execution/voice_agents/gemini_live_dental_fr/` as self-host fallback.
2. **Cartesia voice ids** — rejected by Vapi ("voice not found").
3. **Azure FR-only voice (`fr-FR-DeniseNeural`)** — worked but only handled FR; abandoned for bilingual pivot.
4. **Azure `en-US-AvaMultilingualNeural`** — English heavy French accent per operator.
5. **Azure `en-US-EmmaMultilingualNeural`** — same problem, operator confirms still French-accented English AND English-accented French in the bilingual transition.
6. **Three system-prompt rewrites** — strict turn-taking, foreign-name-is-not-language, ask-don't-handoff. Logic is correct (12/12 corpus green). Prompt is not the bottleneck anymore.
7. **Deepgram keyword boost** — added 33 non-FR/EN names + clinic terms with `:2` boost weight, ASCII-only. Operator says it's still not recognizing his first name → either the boost is too weak, or Deepgram `multi` mode is too lossy, or both.
8. **Silence timeout 12 → 30s** — fixed the call-ends-mid-phone-number bug; not regressed.
9. **endCallPhrases tightened** — only Lisa's own confirmation goodbye triggers hangup.

---

## What the corpus does NOT test

- Voice accent (operator's ear only)
- ASR accuracy on proper nouns
- TTS naturalness
- Turn-taking latency
- Barge-in behavior

Anyone iterating on this build must remember: **a 12/12 green acceptance gate does not mean the demo is good**. The operator's listen-test is the only ground truth that matters.

---

## Open follow-ups beyond the immediate bugs

- Refresh `CLOUDFLARE_API_TOKEN` in `.env` so non-interactive deploys work without cached OAuth.
- Operator may want a dedicated dental Cal.com event type (instead of reusing the `30min` portfolio CTA event). Currently demo bookings land in the same calendar.
- Phase 5 RGPD hard gate (DPA + DPIA + HDS hosting) before any real-patient call. Templates at `docs/compliance/`.
- EU AI Act high-risk transparency notice due 2026-08-02 (5 weeks).
- Nothing committed to git — entire build is uncommitted local files per `CLAUDE.local.md` "Always ask before pushing to remote on this repo". Ask the operator before `git add`.
