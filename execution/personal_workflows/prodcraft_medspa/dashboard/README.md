# ProdCraft Med Spa — Operator Dashboard

Cloudflare Pages (static HTML/JS + Pages Functions in TypeScript). Daily
outreach queue, preview approval gate, funnel stats, config editor. See
`PROJECT_SPEC.md` §7-§8 and `CONTRACTS.md` (Layout, state machine, queue cap
rules) one level up for the why.

Vanilla frontend (`public/`), no framework, no CDN — everything is local so
it works under a strict CSP. Every path is behind HTTP Basic Auth
(`functions/_middleware.ts`).

## Deploy

```bash
npm i
npx wrangler pages project create prodcraft-medspa-dashboard
npx wrangler pages secret put DASHBOARD_USER       --project-name prodcraft-medspa-dashboard
npx wrangler pages secret put DASHBOARD_PASS       --project-name prodcraft-medspa-dashboard
npx wrangler pages secret put SUPABASE_URL         --project-name prodcraft-medspa-dashboard
npx wrangler pages secret put SUPABASE_SERVICE_KEY --project-name prodcraft-medspa-dashboard
npm run deploy
```

`SUPABASE_SERVICE_KEY` bypasses Row Level Security (per `db/schema.sql`,
RLS is enabled with "anon gets nothing" — the dashboard's server-side
functions are the only thing that should ever hold this key). It is read
only in `functions/_lib/supabase.ts` and is never logged, never sent to the
browser, and never appears in a response body.

## Local dev

```bash
npx wrangler pages dev public
```

Wrangler dev prompts for the same 4 secrets locally (or put them in
`.dev.vars`, gitignored, `KEY=value` per line) — see
`.claude/rules/security.md`: never commit secrets, use env vars.

## Verify

```bash
npm install
npm run typecheck
npm test
```

## Layout

```
dashboard/
  wrangler.toml            # project name, pages_build_output_dir, secret docs
  functions/
    _middleware.ts          # HTTP Basic Auth on every path (mirrors yoga_jitendra_site pattern)
    _lib/
      state.ts              # outreach state machine (mirrors outreach/state_machine.py — CONTRACTS.md)
      queue.ts               # pure: cap rules, halt/bounce math, next_touch_at math
      supabase.ts            # tiny PostgREST client (service key)
      http.ts                # json()/errorJson()/readJsonBody() helpers
    api/
      queue.ts                       # GET  /api/queue?date=
      previews/index.ts              # GET  /api/previews?status=
      previews/[id]/status.ts        # POST /api/previews/:id/status
      outreach/[id]/transition.ts    # POST /api/outreach/:id/transition
      outreach/[id]/draft.ts         # POST /api/outreach/:id/draft
      stats.ts                       # GET  /api/stats
      config.ts                      # GET/POST /api/config
  public/
    index.html, app.js, style.css   # Queue / Previews / Stats / Config tabs
  test/                              # vitest — state, queue, middleware
```

## Assumptions made while building

- **"Latest audit" for the queue** is read via `outreach.audit_id` (the FK
  already on the row — set when the row was drafted against a specific
  audit) rather than a fresh "most recent audit for this business" query.
  This pins the score/gaps a queue card shows to the audit the draft was
  actually written against, even if a newer audit has since landed. The
  Previews tab, by contrast, has no audit FK on `previews`, so it does query
  the business's most-recent audit row directly.
- **Queue status filter** uses `queued, drafted, sent` (not just
  `queued, sent` as CONTRACTS.md's Store interface docstring says) — the
  more detailed endpoint spec in the build task explicitly listed
  `drafted` too, and a card mid-edit (drafted, not yet sent) still needs to
  show up in the daily queue.
- **`computeNextTouchAt` is only defined for touch 1-3.** Touch 4 has no
  touch 5 to schedule, so `touch_days[4]` doesn't exist; on a touch-4
  `sent` transition the row's existing `next_touch_at` (set when it was
  queued, at day 12) is left untouched, and `sent→closed_lost` eligibility
  is `next_touch_at + 5 days` (see `touch4GraceExpired` in
  `functions/_lib/queue.ts`) — matching CONTRACTS.md's
  `sent→closed_lost (touch 4 and next_touch_at + 5d passed)`.
- **`events.entity_id` is `uuid not null`** (`db/schema.sql`), but config
  changes are keyed by a text `key` (`proof_lines`/`sender`/`phase0`), not a
  uuid. `functions/api/config.ts` logs those events against a nil-uuid
  sentinel (`00000000-0000-0000-0000-000000000000`) with the real key in
  `payload.key`, rather than changing the schema (out of this task's scope
  — other agents own `db/`).
- **Preview status transitions** beyond `review→approved`,
  `approved→review`, and `*→takedown` (the three the task named) are
  restricted to a narrow extra set (`live→takedown`, `expired→takedown`)
  rather than left wide open, since the task only specified those three and
  `previews.status` also has `live`/`expired` values set by other parts of
  the pipeline (preview deploy + the expiry cron, per PROJECT_SPEC.md §7)
  that this dashboard doesn't otherwise touch.
- **`outreach.draft` endpoint** also flips `queued → drafted` when saving a
  draft on a still-`queued` row, since `queued→drafted` is the only legal
  edge out of `queued` in the state machine and "Save draft" is the
  dashboard's only affordance for making that edge happen.
- **DNC cascade**: per CONTRACTS.md ("`dnc` also sets
  `businesses.do_not_contact`, `previews.takedown`, and cancels all other
  touches"), transitioning any outreach row to `dnc` also takes down that
  business's preview (if any) and moves every other non-terminal outreach
  row for the same business to `dnc` too.
- **Bounce-rate window for the halt check** pulls `outreach` rows with
  `sent_at` in the 35 days before the queue's `date` param (30-day window +
  5 days slack) rather than every row ever, to keep `/api/queue` from
  scanning the full table as the pipeline grows.
