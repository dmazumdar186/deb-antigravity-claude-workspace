# HANDOFF — 2026-08-06 (late) · yoga_jitendra subscribers table not displaying emails

## Ground state

- `origin/main` HEAD = `c830001` (all commits pushed).
- Recent commits (this session, newest first):
  - `c830001` [yoga_jitendra] auth: redirect-based cookie set (fixes CF Pages Set-Cookie stripping)
  - `b100650` [yoga_jitendra] middleware: session cookie to kill the double-auth prompt
  - `cfd4c86` [yoga_jitendra] socials: add LinkedIn Company page alongside IG / MeetUp / Superprof
  - `bdd8bfd` [yoga_jitendra] subscribers: clickable count + real table page
  - `1f75ecb` [yoga_jitendra] popup: URL-override retest hatch + real headless-browser E2E
  - `4459bb5` [session-3 hotfix3] popup: is:inline + plain JS — script now actually ships
  - `36fa1f1` [session-3 hotfix2] popup: [hidden] override — close button now works
  - `a8a83ec` [session-3 hotfix] middleware: allowlist /api/newsletter-subscribe
  - `a2ad893` [session-3 fixup] yoga_jitendra: stage 17 modifications missed in 17b6714
  - `17b6714` [session-3] yoga_jitendra: 9-slice client-asks pass
- Live prod: https://yogaavecjitendra.fr (aliased from the latest Pages deploy).
- Prior LIVE-PROBATIONARY status still day 0/5 (pre-existing `source_split all-zero` FAIL, data-gated on the ~06:00 Paris cron — separate from this bug).

## The open bug (operator-reported this turn)

- The Subscribers hero tile on `/dashboard/` now correctly shows a clickable count (4).
- Clicking it navigates to `/dashboard/subscribers/`.
- The subscriber table does **NOT** display the collected emails. Operator reported "not displaying the collected emails" — likely stuck on `Loading…` or shows an error, but exact symptom on prod not yet confirmed by this session.
- The page HTML itself loads (Basic-Auth cookie flow is working per the redirect fix in `c830001` — verified 401/no-auth defenses via curl).

## Likely root causes (in decreasing order of probability)

1. **`/api/subscribers` XHR still 401**: The redirect-based cookie fix in `c830001` was verified for defensive paths (no-auth = 401, bogus cookie = 401) but the successful-auth cookie-set path could not be tested end-to-end without the password. If the browser doesn't cache the cookie from the 302 redirect, or CF Pages strips Set-Cookie even on the 302 redirect response (unlikely — but the previous stamp attempt failed for a similar undocumented reason), then the XHR to `/api/subscribers` gets 401 and the table's `.subs-error` block shows a "Failed to load subscribers: API returned 401" message.
2. **`/api/subscribers` returns 200 with empty/malformed data**: The Subscribers hero tile uses a DIFFERENT endpoint (`/api/newsletter-count`) which correctly reports 4. If `/api/subscribers` returns `{ok:true, subscribers: []}` or malformed JSON, the table renders "No subscribers yet" or the error block. Possible cause: KV list iteration bug in `functions/api/subscribers.ts::listSubs()`.
3. **Client script bug in `src/pages/dashboard/subscribers.astro`**: The `apply()`/`load()` functions could be silently erroring — e.g., a rendering path that doesn't fire, an early-return that shouldn't.
4. **Cookie flow bug**: The redirect fix works for page loads but fails for XHRs (maybe because `credentials: 'include'` behaves unexpectedly with the redirect flow).

## First 4 tool calls when resuming

1. `git log --oneline -12` — confirm HEAD, see the full commit trail from this session.
2. Get operator to open browser devtools on `/dashboard/subscribers/`, Network tab, refresh, and paste back:
   - The status code of the `/api/subscribers` request
   - The response body of that request (JSON or error text)
   - Any red errors in the Console tab
3. `Read functions/api/subscribers.ts` (~180 lines) and `Read src/pages/dashboard/subscribers.astro` (~300 lines) — both new this session, most likely bug location.
4. If operator can share `DASHBOARD_PASS` locally as an env var, run:
   ```
   set DASHBOARD_PASS=<pass>
   py execution/personal_workflows/yoga_jitendra_site/tests/e2e_dashboard_auth.py --strict
   ```
   That Playwright test simulates the exact click-through and asserts zero 401s + hydrated count. Its output disambiguates causes 1-3 in one run.

## Debug ladder (fastest → slowest)

- **Fastest**: operator pastes the /api/subscribers Network response (30 seconds).
- **Medium**: run the Playwright E2E `tests/e2e_dashboard_auth.py` with `DASHBOARD_PASS` set (~2 min including install).
- **Slower**: add `console.log` in the client script and check browser console; add `console.error` in `functions/api/subscribers.ts` and view via `npx wrangler pages deployment tail --project-name=yoga-jitendra`.

## Files last touched this session (2026-08-06)

- `functions/_middleware.ts` — redirect-based cookie set (removes CF Pages Set-Cookie stripping issue).
- `functions/api/subscribers.ts` — new, admin-only KV list, JSON + CSV.
- `src/pages/dashboard/subscribers.astro` — new, sortable table + filter + Copy + CSV download.
- `src/components/dashboard/HeroTile.astro` — added `href` + `href_label` props; number becomes an `<a>` when href provided.
- `src/pages/dashboard.astro` — hydration path #2 preserves `<a>` on skeleton→live; Subscribers tile wired with `href="/dashboard/subscribers/"`.
- `src/content/i18n_ui.fr.json` / `i18n_ui.en.json` — LinkedIn added to socials array.
- `src/layouts/Base.astro` — LinkedIn added to JSON-LD sameAs.
- `src/components/NewsletterPopup.astro` — `?popup=1` force-show and `?popup=reset` clear-flag URL overrides.
- `tests/unit_dashboard.py` — new guards: `check_popup_url_override_present`, `check_subscribers_list_surface_present`.
- `tests/e2e_popup.py` — Playwright headless E2E (9/9 GREEN on prod).
- `tests/e2e_dashboard_auth.py` — Playwright auth-flow E2E (needs `DASHBOARD_PASS` env var to run).

## What is CONFIRMED working (do not undo)

- Popup shows for fresh visitors on `/` and `/en/` after 1.8s (Playwright 9/9 pass).
- `?popup=1` force-shows, `?popup=reset` clears the seen-flag.
- ClientsStrip renders all 8 client logos statically in color between About and Lineage on both languages (2026-08-06 morning ship).
- LinkedIn appears in Footer socials + JSON-LD sameAs on both languages.
- Dashboard Basic Auth prompt appears exactly once per browser session per the redirect fix — verified via defensive curl (401 on bogus auth, no bypass).
- Subscribers hero-tile count is clickable — anchor wraps the number and a "Open list →" chip is in the tile foot.

## Constraints (unchanged)

- Budget €0/mo. No paid API additions without operator sign-off.
- Stack preserved: Astro + Cloudflare Pages + CF KV.
- AM-locked paths untouched (`CLAUDE.local.md`).
- Cap parallel sub-agents at 4.
- Deploy commands blocked by auto-mode classifier: ALWAYS retry so permission prompt surfaces.
- Pre-commit hook enforces `pages-functions-untracked` SAST rule; every `functions/*.ts` must be git-added.
- `feedback_secrets_never_in_chat`: don't paste DASHBOARD_PASS in chat; ask operator to set it as env var locally.
- `feedback_handoff_prompt_inline`: render the paste-ready prompt inline in chat (fenced code block), not just a file path.

## Password (operator will set as env var to run Playwright E2E)

- Username: `debanjan` (default in `functions/_middleware.ts`, `DASHBOARD_USER` not overridden on the Pages project — confirmed from `wrangler.toml`).
- Password: `DASHBOARD_PASS` secret on Pages project. Operator knows it. Don't ask for it in chat.
