# AgentUp — Over-Deliver Playbook

**Purpose:** Everything you could build on top of the shipped baseline to move from "matches PRD" to "makes the panel lean forward." Ranked by **wow-per-hour**.

**Baseline shipped:** 75/75 PRD reqs pass (see `prd_traceability_matrix.md`), 91 automated tests, live at https://agentup-iag.pages.dev.

---

## Part 1 — Triage of the research you shared (candid)

The article gave you 5 architectural layers framed through the "elite panel" lens. My take:

| # | Article's suggestion | Honest verdict | Why |
|---|---|---|---|
| 1 | **Streaming + chunked TTS** (Brockman/Murati) | 🟢 **BUILD** — genuine UX win | Anthropic natively supports SSE streaming. Time-to-first-audio drops from ~2s to <500ms. Direct win. |
| 2 | **Client-side PII redaction + DPDPA consent** (Amodei) | 🟢 **BUILD** — India-market differentiator | India-specific compliance angle nobody else will build for a hiring exercise. Cheap, high signal. |
| 3 | **Prompt caching + cost widget** (Cherny) | 🟡 **PARTIAL — build the widget, skip the fake formula** | Anthropic prompt caching is real, but the article's Vertex-specific $1→$0.08 math doesn't map cleanly to Anthropic-direct. Build the *cost/telemetry widget* using real observed numbers, not the theoretical formula. |
| 4 | **G-Eval playtest + predictive ROI** (Sutskever) | 🟡 **BUILD G-Eval, label ROI as simulation** | G-Eval-style scoring-consistency harness is real and impressive. "Predicted CSAT +N%" without real training data is hype — build it but label it clearly as *illustrative*, not empirical. |
| 5 | **Developer overlay panel** (Karpathy) | 🟢 **BUILD** — biggest wow-per-hour | Ctrl+` opens a live-metrics HUD (tokens, latency, provider, active prompt). Screams "I understand what I built." ~90 min of work. |

**Wrong/overstated in the article (don't cite):**
- "Reasoning under-allocation on Claude 3.5 Sonnet" — extended-thinking toggle is more of an Opus concern; non-issue for our scoring path where we already set `thinkingBudget: 0` on Gemini.
- Vertex AI framing throughout — you're on Anthropic-direct + Gemini free-tier. Same primitives, different SDK. Adapt the story.

---

## Part 2 — Beyond the article (my adds)

Nine items the article missed. Each is genuinely differentiating.

### A. Rubric-anchored feedback (educational, not just scored)

**Today:** Scorecard shows 4 numbers + 1-line strength + 1-line improvement.
**Upgrade:** Modify scoring prompt to also return `perTurnFeedback[]` — which specific turn earned/lost points, tagged by dimension. Then color-code the transcript: green highlights on empathy wins, amber on accuracy misses, etc. Users see *where* they succeeded/failed, not just a number.

**Wow signal:** Product-design panel sees you thought about the *learning*, not the *scoring*.

### B. "Model answer" reveal

After the scorecard, a `See an A+ reply` button spawns Claude in a different mode: "given this scenario, produce an ideal 5-turn agent transcript." Show it side-by-side with the user's transcript. The learning loop closes: score → see gap → see model → try again tomorrow.

**Wow signal:** Product panel loves closed learning loops. Zero net new infra.

### C. Real cost + telemetry surface (the Cherny widget, done properly)

A live dashboard tile: "This session cost you €0.043 (Sonnet 42k in / 620 out + Gemini 12k in / 340 out) — projected €12.90/agent/month at 30 sessions." Numbers from actual measured usage, not a formula. Add a monthly rollup + provider mix chart.

**Wow signal:** Founder lens — you can talk unit economics without hand-waving.

### D. G-Eval scoring-consistency harness

A `tests/g_eval_scoring.py` script that runs the SAME transcript through the scoring endpoint N times, computes score variance per dimension, and flags dimensions where the model is inconsistent (variance > threshold). Ships with a golden set: 5 known-A+ transcripts (must score ≥80) and 5 known-fail transcripts (must score ≤50).

**Wow signal:** Sutskever/AI-safety lens — you take LLM-as-judge instability seriously. Also gives you a real ROI story for choosing Sonnet over free tiers.

### E. Developer overlay HUD (Ctrl+`)

Floating panel showing per-turn:
- Provider used (Anthropic / Gemini)
- Latency (ms) with p50/p95 rolling window
- Input/output token counts
- Active system prompt (collapsible)
- Speech recognition confidence (0.0–1.0) on Call channel
- Rate-limit budget remaining (from response headers)
- Copyable request/response JSON for the last 5 calls

**Wow signal:** Karpathy/eng-lead lens instantly. High wow/effort.

### F. Session replay + share URL

Compact-encode a completed session (base64-gz of the JSON) into a URL fragment (`#s=…`). Anyone with the link sees the transcript + scorecard, read-only. No login, no server storage. Enables "share your best" and post-mortem coaching without a backend.

**Wow signal:** Design/product panel — thoughtful shareability without inventing auth.

### G. Client-side PII redaction (Indian formats)

Regex-based masking BEFORE the payload leaves the browser: Aadhaar (12-digit block), PAN (5 letters + 4 digits + letter), Indian mobile (+91 / 10-digit), credit card (Luhn-checked 13-19 digits), UPI IDs. Replace with `[AADHAAR_REDACTED]` etc. Show a small chip in the UI: "PII redacted before leaving your device."

**Wow signal:** DPDPA safety + India-context awareness. Concrete artifact of "AI safety" beyond hand-waving.

### H. Voice-activity detection + interruption ("barge-in")

Today: user presses mic, speaks, releases. Enterprise call floors need natural: mic auto-stops on 500ms silence (VAD via `AudioContext.createAnalyser` + RMS threshold), and pressing space during customer TTS interrupts it. Feels 10× more like a real call.

**Wow signal:** Voice-UX credibility — Brockman/Murati lens beyond just "we stream tokens."

### I. Streaming Sonnet responses (the real version)

Anthropic supports SSE via `stream: true`. Rewrite the Pages Function to proxy the stream to the browser. Client renders text token-by-token *and* pipes complete sentences to `SpeechSynthesisUtterance` as they arrive (chunked TTS from the article, but built on real Anthropic streaming). Time-to-first-token drops to ~400ms, time-to-first-audio ~500ms.

**Wow signal:** The single biggest UX difference. Feels like a live call, not a batch response.

---

## Part 3 — Ranked over-deliver menu (by wow × feasibility)

| Rank | Feature | Est. effort | Wow signal | Panel lens |
|---|---|---:|---|---|
| **★1** | **Developer overlay HUD (Ctrl+`)** — item E | 1.5h | Massive | Karpathy / eng lead |
| **★2** | **Streaming Sonnet + chunked TTS** — item I + article #1 | 2.5h | Massive | Brockman / Murati / voice |
| **★3** | **Model-answer reveal + rubric-anchored transcript colouring** — items A+B | 2h | High (learning-loop) | Product panel |
| **★4** | **Cost + telemetry surface on dashboard** — item C + article #3 | 1h | High (unit economics) | Founder / Cherny |
| **★5** | **G-Eval scoring-consistency harness + golden set** — item D + article #4 | 2h | High (AI-safety) | Sutskever |
| **★6** | **Client-side PII redaction + DPDPA chip** — item G + article #2 | 1.5h | High (India-market) | Amodei / compliance |
| ★7 | Session replay + share URL — item F | 1h | Medium | Design |
| ★8 | Voice-activity detection + barge-in — item H | 2h | High (voice UX) | Brockman / Murati |
| ★9 | Predictive ROI card (labelled "illustrative") — article #4 partial | 45m | Medium | BPO ops story |

---

## Part 4 — Recommended packages

Pick one; I execute autonomously per your auto-mode.

### Package A — "Wow the eng panel" (~4h build)
★1 Dev HUD + ★2 Streaming + ★3 Model-answer + rubric colouring + ★4 Cost surface.
**Story:** "I built the training platform, then I built the tools I'd want if I ran it."

### Package B — "Wow the safety / India panel" (~5h build)
★1 Dev HUD + ★5 G-Eval + ★6 PII/DPDPA + ★9 ROI card + light Package A extras.
**Story:** "Enterprise-ready from day one for the Indian market."

### Package C — "Everything above ★7" (~9h build)
All 6 top-ranked. Longest but leaves nothing on the table.

### Package D — "Wildcard" — you pick specific items
Tell me the item numbers.

---

## Part 5 — Also worth doing regardless (small, cheap)

- **Provider badge in UI footer** — "Powered by Claude Sonnet 4.6 (with Gemini 2.5 fallback)" — turns the multi-provider architecture into visible sophistication (5 min).
- **Copy PRD-traceability link into README** — link the interviewer straight from README → the matrix (2 min).
- **`ROADMAP.md` in repo** — list of items above with time estimates. Signals product-thinking beyond the task (10 min). Even for items you *don't* build, listing them shows you *saw* them.

---

## What I need from you

Tell me which package (or which specific ★ items). I'll execute end-to-end: build → tests → redeploy → refresh the traceability matrix with the new capabilities → give you the updated live URL for the interview.

If you want to think in terms of *interview time*, remember: the interviewer spends 3-8 minutes on your live URL. Every ★ item is a demo beat. Package A gives 4-5 demo beats. Package C gives 6-7. You physically can't demo more than ~7 in an interview.
