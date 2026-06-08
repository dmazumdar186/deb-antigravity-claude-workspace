# Phase 4c — Supabase Setup (parallel backend track)

## Goal

Stand up a Supabase project for this app — Postgres schema, Row-Level Security enabled by default, auto-generated REST API, and a typed JS client wired into the Expo bundle. This is the **parallel** track to Phase 4a (Cloudflare Worker). Apps pick one or the other based on whether they need user-owned data + auth (Supabase) or webhook + KV state (CF Worker). For apps that need both, run Phase 4a and 4c on top of each other.

Encodes Nick Saraev's transcript: `Claude Code Mobile App Dev 1.pdf`, chapters 16-17.

## Inputs

- App slug (kebab-case, from registry)
- Phase 1-3 complete (Expo app boots, local AsyncStorage state shape known)
- `APP_SPEC.md` at `C:\Users\deban\dev\mobile-apps\<slug>\APP_SPEC.md` — Section 3 (accessory features) names the data nouns that become tables
- Docker Desktop installed + running (required by `supabase start` local stack)
- Supabase account at `supabase.com` (free tier — no card required for Phase 4c)
- DB password generated and stored in `.env` as `SUPABASE_DB_PASSWORD` (you generate it, never echo to chat)

## Tools/Scripts

- `npm i -g supabase` — the Supabase CLI
- `supabase init` — scaffolds `supabase/` directory inside the app repo (migrations, config)
- `supabase start` — boots the local Postgres + GoTrue + PostgREST stack via Docker
- `supabase db push` — applies local migrations to the remote project
- `supabase link --project-ref <ref>` — binds the local repo to the remote project
- Web console at `https://supabase.com/dashboard` — project creation (one click)
- New file in app repo: `C:\Users\deban\dev\mobile-apps\<slug>\src\lib\supabase.ts`

## Outputs

- A Supabase project named `<slug>` (region: closest to user — Oregon `us-west-1` default)
- `supabase/` directory in the app repo with `config.toml` + `migrations/<timestamp>_init.sql`
- One Postgres table per spec noun (e.g. `habits`, `completions`, `challenges`, `profiles`) with `user_id uuid references auth.users` foreign key on every user-owned row
- RLS enabled on every table; default-deny + per-table policy (`auth.uid() = user_id`)
- `src/lib/supabase.ts` exporting a `createClient(...)` instance with `AsyncStorage` as the auth persistence layer
- `.env` entries (additive): `EXPO_PUBLIC_SUPABASE_URL`, `EXPO_PUBLIC_SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` (server-only — see Edge Cases)
- Registry updated with `supabase_project_ref`, `supabase_url`, and `last_db_push_at`

## Steps

1. **Create the Supabase project.** Web console → New project → name `<slug>`, paste `SUPABASE_DB_PASSWORD` from `.env`, pick region. **At creation, tick the "enable automatic RLS" checkbox** (Nick chapter 17 — this is the single biggest footgun; if unchecked, every new table defaults to public read/write). Wait ~2 min for the database + GoTrue + PostgREST + Realtime + Edge Functions to all show `healthy` in the console.
2. **Capture the keys.** From the project's `Settings → API` page, copy:
   - Project URL → `EXPO_PUBLIC_SUPABASE_URL`
   - `anon` public key → `EXPO_PUBLIC_SUPABASE_ANON_KEY` (the `EXPO_PUBLIC_` prefix is **safe** here — anon key is designed for client exposure and is gated by RLS)
   - `service_role` key → `SUPABASE_SERVICE_ROLE_KEY` (no `EXPO_PUBLIC_` prefix — see Edge Cases for why)
   - Project ref (the `xyzabc.supabase.co` subdomain stub) → registry as `supabase_project_ref`
3. **Install + init the CLI in the app repo.**
   ```
   npm i -g supabase
   cd C:\Users\deban\dev\mobile-apps\<slug>
   supabase init
   supabase link --project-ref <ref>
   ```
   `init` creates `supabase/config.toml` + a `migrations/` folder. `link` binds the local repo to the remote project so `db push` knows where to send schema changes.
4. **Design the schema from `APP_SPEC.md`.** One table per noun. Postgres types: `text` (not `varchar`), `timestamptz` (not `timestamp` — always store TZ), `boolean`, `int4`, `numeric` for money. Every user-owned table gets `id uuid primary key default gen_random_uuid()` and `user_id uuid not null references auth.users(id) on delete cascade`. Write the SQL into `supabase/migrations/<timestamp>_init.sql`.
5. **Enable RLS + write policies per table.** For each table, in the same migration:
   ```sql
   alter table public.habits enable row level security;
   create policy "habits: owner read"   on public.habits for select using (auth.uid() = user_id);
   create policy "habits: owner insert" on public.habits for insert with check (auth.uid() = user_id);
   create policy "habits: owner update" on public.habits for update using (auth.uid() = user_id);
   create policy "habits: owner delete" on public.habits for delete using (auth.uid() = user_id);
   ```
   Default-deny is implicit when RLS is on and no policy matches.
6. **Push the schema.**
   ```
   supabase db push
   ```
   Verify in the console's Table Editor that every table appears + the `RLS enabled` badge is green next to each.
7. **Wire the client.** Create `src/lib/supabase.ts`:
   ```ts
   import { createClient } from '@supabase/supabase-js'
   import AsyncStorage from '@react-native-async-storage/async-storage'
   import 'react-native-url-polyfill/auto'

   export const supabase = createClient(
     process.env.EXPO_PUBLIC_SUPABASE_URL!,
     process.env.EXPO_PUBLIC_SUPABASE_ANON_KEY!,
     {
       auth: {
         storage: AsyncStorage,
         autoRefreshToken: true,
         persistSession: true,
         detectSessionInUrl: false,
       },
     }
   )
   ```
   `npm i @supabase/supabase-js @react-native-async-storage/async-storage react-native-url-polyfill` in the app repo.
8. **Local stack (optional but recommended for dev).** `supabase start` boots Postgres + GoTrue + PostgREST in Docker on `localhost:54321`. For local-only dev, swap `EXPO_PUBLIC_SUPABASE_URL` to `http://localhost:54321` and use the local anon key printed by `supabase start`. Stop with `supabase stop`.
9. **Update registry.** Append `supabase_project_ref`, `supabase_url`, `last_db_push_at` (ISO timestamp) to the slug's entry.
10. **Commit.** App repo: `src/lib/supabase.ts`, `supabase/config.toml`, `supabase/migrations/*.sql`, `.env.example` updated with all three keys.

## Edge Cases

- **RLS-disabled-on-new-tables footgun.** If the "enable automatic RLS" checkbox was missed at project creation, every table you create later defaults to RLS-off (public read/write to anyone with the anon key — which ships in your bundle). Fix: `alter table <name> enable row level security;` for every table, then add policies. Audit pass 1 (`directives/mobile_apps/security_audit.md`) catches this; don't ship without verifying.
- **`SUPABASE_SERVICE_ROLE_KEY` with an `EXPO_PUBLIC_` prefix.** Service-role key bypasses RLS entirely. If it lands in `app.config.js`, `.env`, or any file with `EXPO_PUBLIC_` prefix, it bundles into the shipped app and any user can extract it from the binary. **NEVER** use `EXPO_PUBLIC_` on service-role. The key only belongs in server-side environments (Edge Functions, Modal, or a Worker — never the React Native bundle).
- **Free-tier 500MB DB cap + 1GB egress / 2 vCPU shared.** Apps with image blobs in tables (vs Storage buckets) hit the cap fast. Always store large binaries in Supabase Storage (separate cap) and the row keeps the storage path only.
- **Postgres timezone defaults to UTC.** All `timestamptz` columns store UTC. Display logic converts on the client. If you need a row's "wall-clock local time", store a separate `text` field with the user's IANA tz (e.g. `Europe/Paris`) — don't try to coerce `timestamp` (no TZ) into doing the work.
- **`supabase start` fails because Docker isn't running.** Friendly error from the CLI but easy to miss in a sub-agent. Preflight check: `docker ps` returns exit 0 before running `supabase start`.
- **`supabase db push` writes to the wrong project.** If `supabase link` was skipped or pointed at a stale ref, the migration lands in another project. Always run `supabase status` first; verify `Linked project: <expected-ref>`.
- **Concurrent migration drift.** Two devs (or two sub-agents) writing migrations at the same time produce conflicting `timestamp_init.sql` files. For solo dev this rarely bites, but if it does: `supabase db reset` locally, then re-push.
- **`gen_random_uuid()` requires the `pgcrypto` extension.** Supabase enables it by default in new projects, but old / migrated projects may not. If `gen_random_uuid()` errors at push time: `create extension if not exists pgcrypto;` at the top of the migration.
- **`auth.uid()` returns null when called from the service-role key.** RLS policies using `auth.uid() = user_id` fail-deny under service-role calls. That's correct behavior — service-role bypasses RLS deliberately. If you need authenticated calls, use the anon key + a JWT.

## Notes

- Anneal mode for this phase: **adversarial**. The Worker has paid infra and auth at stake even on the free tier — RLS holes, service-key leaks, and policy regressions are exactly the bug class that the Red-vs-Blue duel catches better than a single-pass audit.
  ```
  cd C:\Users\deban\dev\anneal
  py -m anneal.cli adversarial <base-ref-sha> --repo C:\Users\deban\dev\mobile-apps\<slug>
  ```
- Phase 4c is the entry point for Phase 4d (auth) and Phase 5b (Edge Functions for AI). Do **not** call Anthropic / OpenRouter directly from the React Native client even at this stage — the security audit will flag it CRITICAL. Phase 5b is the secure path.
- Parallel to: `directives/mobile_apps/phase4a_cf_worker.md` (CF Worker + KV). Pick one; doubling up only makes sense for apps that genuinely need both (e.g. user data in Supabase + edge webhook receivers in a Worker).
- Companion: `directives/mobile_apps/phase4d_supabase_auth.md` (next), `directives/mobile_apps/phase5b_supabase_ai.md`, `directives/mobile_apps/security_audit.md` (runs after Phase 4 ships).
