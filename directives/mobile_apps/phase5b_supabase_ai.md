# Phase 5b — Supabase Edge Functions for AI (secure server-side Anthropic path)

## Goal

Add AI features (coaching nudges, reflection summaries, classification, generation) via Supabase Edge Functions calling Anthropic with `claude-sonnet-4-6`. The Anthropic key stays server-side as a Supabase secret, every request verifies the user's JWT, every response is logged to a Postgres table (with RLS), and the mobile client invokes the function via the typed Supabase SDK. This is the **secure** AI path. Phase 5a (OpenRouter direct from app) is the simpler-but-leaky alternative; pick 5a only when the app explicitly accepts the cost-drain risk.

Encodes Nick Saraev's transcript: `Claude Code Mobile App Dev 1.pdf`, chapters 19 + 22.

## Inputs

- Phase 4c + 4d complete (Supabase project + auth working; every request from the app carries a valid JWT)
- App spec naming the AI tasks — e.g. "daily coaching nudge", "weekly reflection summary", "habit classification"
- `ANTHROPIC_API_KEY` in `.env` at the workspace root (canonical name — see Edge Cases on the `enthropic` typo)
- Per CLAUDE.md hardening rule #4: cache-aware pricing table will be needed (see Step 6)

## Tools/Scripts

- `supabase functions new <name>` — scaffolds `supabase/functions/<name>/index.ts` (Deno runtime, TypeScript)
- `supabase functions deploy <name>` — pushes the function to the project's edge runtime
- `supabase secrets set KEY=value` — sets a runtime secret (NOT `Deno.env` defaults in the function code itself)
- `supabase functions invoke <name> --body '{...}'` — local test (JWT verification is fixed at deploy time via the deploy flag below, not at invoke time)
- New tables in app repo migration: `coaching_messages`, `reflection_summaries` (or whatever the spec needs)
- Client SDK helper: `supabase.functions.invoke('<name>', { body: {...} })` — already typed via Phase 4c's client

## Outputs

- Per AI feature, one deployed Edge Function at `https://<project-ref>.supabase.co/functions/v1/<name>`
- Every function deployed with `--no-verify-jwt false` (default — JWT verification ON)
- `ANTHROPIC_API_KEY` set via `supabase secrets set`, NOT hardcoded in `Deno.env.get` defaults or committed to source
- One Postgres table per AI artifact (e.g. `coaching_messages`, `reflection_summaries`) with RLS policies matching Phase 4c's pattern (`auth.uid() = user_id`)
- Client-side invocation from the app via `supabase.functions.invoke(...)` with the session JWT auto-attached by the SDK
- Cost-per-call logged into the message-table row (`tokens_in`, `tokens_out`, `cost_usd`) for the canary + monthly-spend dashboard
- Registry updated with `edge_functions: ["generate-coaching", "generate-reflection"]`

## Steps

1. **Schema for AI artifacts.** New migration `supabase/migrations/<ts>_ai_tables.sql`:
   ```sql
   create table public.coaching_messages (
     id uuid primary key default gen_random_uuid(),
     user_id uuid not null references auth.users(id) on delete cascade,
     title text not null,
     body text not null,
     model text not null,
     tokens_in int4 not null default 0,
     tokens_out int4 not null default 0,
     cost_usd numeric(10,6) not null default 0,
     created_at timestamptz not null default now()
   );
   alter table public.coaching_messages enable row level security;
   create policy "coaching_messages: owner read" on public.coaching_messages
     for select using (auth.uid() = user_id);
   ```
   No INSERT/UPDATE policies for the client — only the Edge Function (running with the service-role key) writes rows. Repeat for `reflection_summaries`. `supabase db push`.
2. **Scaffold the function.**
   ```
   cd C:\Users\deban\dev\mobile-apps\<slug>
   supabase functions new generate-coaching
   ```
   Creates `supabase/functions/generate-coaching/index.ts`.
3. **Implement the function.** TypeScript / Deno (uses `Deno.serve`, the current Supabase Edge runtime entrypoint — `std/http/server` is deprecated and will eventually be removed):
   ```ts
   import { createClient } from 'https://esm.sh/@supabase/supabase-js@2'

   const ANTHROPIC = Deno.env.get('ANTHROPIC_API_KEY')!
   const SUPABASE_URL = Deno.env.get('SUPABASE_URL')!
   const SERVICE_ROLE = Deno.env.get('SUPABASE_SERVICE_ROLE_KEY')!

   Deno.serve(async (req) => {
     // 1. Extract + verify JWT from Authorization header
     const jwt = req.headers.get('Authorization')?.replace('Bearer ', '')
     if (!jwt) return new Response('unauthorized', { status: 401 })
     const userClient = createClient(SUPABASE_URL, Deno.env.get('SUPABASE_ANON_KEY')!,
       { global: { headers: { Authorization: `Bearer ${jwt}` } } })
     const { data: { user }, error } = await userClient.auth.getUser(jwt)
     if (error || !user) return new Response('unauthorized', { status: 401 })

     // 2. Read user's habit/completion data with the user-scoped client (RLS enforced)
     const { data: habits } = await userClient.from('habits').select('*')
     const { data: completions } = await userClient.from('completions').select('*').gte('created_at', new Date(Date.now() - 7*86400*1000).toISOString())

     // 3. Call Anthropic
     const sys = `You are a coach. Write a short nudge (≤2 sentences, no em-dashes, no marketing fluff). Voice: warm, direct.`
     const userMsg = `Habits: ${JSON.stringify(habits)}\nLast 7d completions: ${JSON.stringify(completions)}`
     const aResp = await fetch('https://api.anthropic.com/v1/messages', {
       method: 'POST',
       headers: { 'x-api-key': ANTHROPIC, 'anthropic-version': '2023-06-01', 'content-type': 'application/json' },
       body: JSON.stringify({ model: 'claude-sonnet-4-6', max_tokens: 256, system: sys, messages: [{ role: 'user', content: userMsg }] })
     })
     const ai = await aResp.json()
     const body = ai.content?.[0]?.text ?? "Keep going."

     // 4. Write to coaching_messages with the SERVICE ROLE client (bypasses RLS for the insert)
     const adminClient = createClient(SUPABASE_URL, SERVICE_ROLE)
     const row = {
       user_id: user.id,
       title: 'Coaching nudge',
       body,
       model: 'claude-sonnet-4-6',
       tokens_in: ai.usage?.input_tokens ?? 0,
       tokens_out: ai.usage?.output_tokens ?? 0,
       cost_usd: estimateCost(ai.usage),
     }
     await adminClient.from('coaching_messages').insert(row)

     return Response.json({ message: body })
   })
   ```
   Note: `Deno.serve` returns immediately and registers the handler; the Supabase Edge runtime takes over from there. Do not wrap it in `await`.
   `user.id` comes from the verified JWT — **never** trust a `user_id` field in the request body (the security audit will flag CRITICAL otherwise).
4. **Set secrets.**
   ```
   supabase secrets set ANTHROPIC_API_KEY=<paste-from-.env>
   ```
   Do **not** put the key as a default in `Deno.env.get('ANTHROPIC_API_KEY') ?? 'sk-...'` — Nick chapter 22 audit catches that pattern. The secret must be set via the CLI; the function reads it at runtime.
5. **Deploy with JWT verification ON.**
   ```
   supabase functions deploy generate-coaching --no-verify-jwt false
   ```
   `--no-verify-jwt false` (the default) means the Supabase edge runtime rejects requests without a valid JWT *before* the function code runs. This is a defense-in-depth layer on top of the explicit `getUser(jwt)` check in step 3. **Never deploy with `--no-verify-jwt true`** — it removes the auth gate and turns the function into a public Anthropic credit drain (see Edge Cases).
6. **Cache-aware cost estimation.** Implement `estimateCost(usage)` in the function. Per CLAUDE.md hardening rule #4 — four entries for Sonnet:
   ```ts
   // Reference implementation lives at C:\Users\deban\dev\anneal\src\anneal\cost.py
   // (Python). The TS port below is a 1:1 transcription kept in sync MANUALLY —
   // when Sonnet pricing changes, update both this snippet AND cost.py, or one will drift.
   const PRICING = {
     'claude-sonnet-4-6': { input: 3.00, cache_read: 0.30, cache_write: 3.75, output: 15.00 },
   } // USD per 1M tokens
   function estimateCost(u) {
     const m = PRICING['claude-sonnet-4-6']
     return ((u.input_tokens ?? 0) * m.input
           + (u.cache_read_input_tokens ?? 0) * m.cache_read
           + (u.cache_creation_input_tokens ?? 0) * m.cache_write
           + (u.output_tokens ?? 0) * m.output) / 1_000_000
   }
   ```
   Flat-rate pricing under-estimates 5-10x once caching kicks in. **Drift risk**: the canonical pricing table is in `anneal/src/anneal/cost.py`; this TS copy must track it. If you change one without the other, the canary's monthly-cost report will diverge from anneal's. Future improvement: generate this TS from a shared JSON dumped by cost.py at build time.
7. **Client-side invocation.** From the app:
   ```ts
   const { data, error } = await supabase.functions.invoke('generate-coaching', {
     body: { habit_id: someId }, // optional payload
   })
   ```
   The SDK auto-attaches the current session's JWT in the `Authorization` header. No client-side Anthropic key.
8. **Test end-to-end.**
   - `supabase functions invoke generate-coaching --body '{}'` (CLI test — picks up your dev JWT) → response with text + a row appearing in `coaching_messages`.
   - In the app: tap "Get today's coaching nudge" button → response renders → row visible in dashboard.
   - Repeat with a logged-out user (manually drop JWT) → 401.
9. **Update registry.** Append `edge_functions: ["generate-coaching", ...]` to the slug's entry. Add a `last_ai_cost_check_at` timestamp.
10. **Commit.** App repo: `supabase/functions/generate-coaching/index.ts`, migration file, client invocation hook.

## Edge Cases

- **`--no-verify-jwt true` deployment.** **CRITICAL.** Removes the runtime auth gate. Any internet caller can POST to the function URL and burn Anthropic credits at the function's rate. Cost amplification: a $5/mo app turns into a $5k bill in 6 hours if the URL leaks. Fix: redeploy with `--no-verify-jwt false`. Audit pass 1 + 2 both catch this; the canary (`mobile_app_canary.py`) should also assert it via a no-JWT probe expecting 401.
- **`ANTHROPIC_API_KEY` typo.** Nick's transcript renders it as `enthropic` in voice transcription. The canonical name is **`ANTHROPIC_API_KEY`** (no e-prefix typo). If the function reads `ENTHROPIC_API_KEY` it silently falls through to undefined and every call returns 500. Always confirm the secret name matches via `supabase secrets list`.
- **Edge Function 50s execution cap.** Supabase Edge Functions hard-stop at 50 seconds (CPU + wall-clock combined depending on plan tier). Long Claude completions (e.g. 4000-token reflection summaries with reasoning) can flirt with the cap. Mitigations: cap `max_tokens` at a known-safe ceiling (1500-2000 for Sonnet ≈ 30-40s), split into multiple smaller calls, or pre-compute via Modal cron (`directives/mobile_apps/phase4b_modal_cron.md`) + serve cached results from the function.
- **No streaming in Edge Functions to React Native.** Even though Anthropic supports SSE streaming, the Supabase Edge runtime doesn't proxy SSE cleanly to the RN SDK's `functions.invoke()` (which awaits the full response). Nick mentions this in chapter 22. If streaming matters: either use a Worker + custom client, or accept "wait for full response" UX (typically 3-15s for Sonnet). For most apps in this workspace, accept the wait — streaming adds significant complexity for marginal UX.
- **Service-role key bleed into client.** If the function returns the wrong shape (e.g. `JSON.stringify(adminClient)` for debug) the service-role key can leak in the response body. Sanitize every error path; never `Response.json(err)` where `err` includes the client. Test by triggering a malformed request and reading the 500 body.
- **Service-role key in `Deno.env.get(...)` defaults.** Same pattern as Anthropic — never embed a default. Set via `supabase secrets set SUPABASE_SERVICE_ROLE_KEY=...` (Supabase actually provides this one automatically at the function runtime, but other apps' projects sometimes override it; verify with `supabase secrets list`).
- **Em-dash leakage.** Nick chapter 22 specifically calls out em-dashes (`—`) as an AI tell. Add `no em-dashes` to the system prompt explicitly. The model still slips occasionally — post-process with a regex covering every dash codepoint Sonnet emits, not just U+2014: `text.replace(/[—–―−]|--+/g, ', ')` (em-dash, en-dash, horizontal bar, minus sign, plain ASCII double-hyphen).
- **Token-cost spike during testing.** Iterating on the prompt with real Sonnet calls runs up costs fast. Add a `--dry-run` body field that returns a mocked response without hitting Anthropic — same pattern as Phase 5a's dry-run.
- **JWT verification skipped via misconfigured CORS proxy.** If a CORS-permissive Worker sits in front of the Edge Function (e.g. for browser access), it can strip the `Authorization` header on cross-origin preflight. Verify the proxy passes Authorization through; otherwise the Edge Function 401s on every browser-origin call.
- **PII in coaching prompts.** Habit data is mildly sensitive. Don't send raw email addresses or display names into Anthropic if the spec doesn't require them. Filter the payload to only what the prompt needs.

## Notes

- Anneal mode for this phase: **adversarial**. Paid AI on a deployed Worker with auth gates and cost-amplification vectors is exactly the class the Red-vs-Blue duel catches better than a single audit pass. Run:
  ```
  cd C:\Users\deban\dev\anneal
  py -m anneal.cli adversarial <base-ref-sha> --repo C:\Users\deban\dev\mobile-apps\<slug>
  ```
- This is the **secure** AI path. Phase 5a (`directives/mobile_apps/phase5a_openrouter_routing.md`) hits OpenRouter directly from the React Native client — simpler but ships the OpenRouter key in the bundle, which is a CRITICAL finding in any security audit. Use 5a only for throwaway prototypes; ship-grade apps use 5b.
- Depends on: `directives/mobile_apps/phase4c_supabase_setup.md` (RLS + tables) + `directives/mobile_apps/phase4d_supabase_auth.md` (JWTs the function verifies).
- Re-run the security audit (`directives/mobile_apps/security_audit.md`) after this phase ships — Phase 5b is the most cost-amplification-vector-heavy phase in the workspace and the two-pass audit is non-negotiable per Nick chapter 23.
- The `coaching_messages` + `reflection_summaries` tables feed the in-app history UI directly via standard RLS-gated `supabase.from(...).select()` from the client. The client never invokes the function on every render — the function writes; the client reads.
