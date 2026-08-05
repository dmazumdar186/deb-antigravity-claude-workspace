# HANDOFF — 2026-08-05 evening: yoga_jitendra client asks (session 3)

**Purpose:** the prior turn in this session (a) deployed the 5-slice UX
redesign to yoga-jitendra.pages.dev (commit `518413f`, 12/13 acceptance
gate PASS — check 3 data-gated on tomorrow's 06:00 cron), then (b)
scoped and plan-skepticked a new 9-slice build for two fresh Jitendra
WhatsApp asks + dashboard-side work. **Plan approved by operator; execution
started but may not be complete.** This handoff captures resume state.

---

## Ground state right now

- `origin/main` HEAD = `518413f` (last deploy — Pages+Worker BOTH live).
- Acceptance gate against yogaavecjitendra.fr: **12/13 PASS**. Missing check = `source_split.values all-zero` (waits on next 06:00 Paris cron).
- LIVE-PROBATIONARY day 0/5.
- **New session-3 plan approved** at `C:\Users\deban\.claude\plans\cuddly-knitting-lagoon.md` — 9 slices. Plan-skeptic verdict = **CONVINCED_WITH_NOTED_CONCERNS** (round 2).

## Feedback memories saved this session

- `feedback_deploy_retry_prompt.md` — when auto-mode classifier blocks a deploy command, ALWAYS retry so the permission prompt surfaces. Operator: "B, always B."

## Jitendra's WhatsApp asks (verbatim)

1. **Email opt-in popup**: pops up on first visit, close-X on right, email-only, non-mandatory. Operator overrode Jitendra's "email+name" → email-only. Storage: **KV-only fallback for today** (operator picked from 3 options; Brevo swap deferred).
2. **Reviews update**: 5 verified-source links at bottom (Instagram/Airbnb/Superprof/Meetup/Google + 2 IG posts).
3. **5 new companies** on homepage: Chloé, FTI Consulting, FIPAM, WeWork, Sick France. Operator asked for a **reusable carousel component** (4-per-page, JSON-driven, future-proof), NOT hardcoded pills.
4. **Instagram URL bug**: personal (`jitendrakuma`) instead of business (`yogaavecjitendra`) on the site. Found in 3 files: `Base.astro:91`, `i18n_ui.fr.json:16`, `i18n_ui.en.json:16`.

---

## The 9 slices (execution order)

Read the plan file for full detail. TL;DR:

| # | Slice | Files (representative) | State |
|---|---|---|---|
| 0 | Fix personal-IG bug (3 files) | `Base.astro:91`, `i18n_ui.{fr,en}.json:16` | pending |
| 1 | Rewrite `newsletter-subscribe.ts` → KV-only + fix `NewsletterPopup.astro` thanks copy (was "check your inbox" — LIE under KV-only) + append "Backend note" to both privacy notice pages | `functions/api/newsletter-subscribe.ts`, `functions/api/newsletter-count.ts` (new), `src/components/NewsletterPopup.astro`, `src/pages/privacy/newsletter.astro`, `src/pages/en/privacy/newsletter.astro` | pending |
| 2 | Wire `NewsletterPopup` into `Base.astro` gated on `!dashboard` | `src/layouts/Base.astro` | pending |
| 3 | Build `ClientsCarousel.astro` reusable component + `clients.{fr,en}.json` + migrate `Hero.astro` (60-90 min) | `src/components/ClientsCarousel.astro` (new), `src/content/clients.{fr,en}.json` (new), `src/components/Hero.astro` | pending |
| 4 | Build `ReviewSources.astro` + wire into both `/reviews/` pages | `src/components/ReviewSources.astro` (new), `src/pages/reviews/index.astro`, `src/pages/en/reviews.astro` | pending |
| 5 | Add "Subscribers" hero tile to dashboard | `functions/api/dashboard-data.ts`, `src/pages/dashboard.astro` | pending |
| 6 | HARDENING.md history entry + KV-plaintext + Brevo-swap catchup | `HARDENING.md` | pending |
| 7 | Extend acceptance-gate (checks 14-18) + mirror in unit_dashboard.py | `tests/acceptance_dashboard.py`, `tests/unit_dashboard.py` | pending |
| 8 | Mandatory Audit Stack — 6 auditors in parallel | (spawns sub-agents) | pending |
| 9 | Rebuild + Pages deploy + live gate + browser dogfood | `dist/`, live URL | pending |

---

## Critical context you'd otherwise lose

**Slice 1 truth-in-copy fix** — the pre-built `NewsletterPopup.astro` has hardcoded thanks copy that says "Check your inbox — click the confirmation link" (FR: "Vérifiez votre boîte mail…"). Under KV-only, no email is sent. Copy MUST change to:
- FR: `"Merci ! Votre inscription est enregistrée. Vous recevrez la prochaine newsletter mensuelle."`
- EN: `"Thanks! Your subscription is saved. You'll receive the next monthly newsletter."`
Skeptic caught this — it was NOT in the original plan. Fixed in revision.

**Slice 0 completeness** — the personal-IG bug is in 3 files. Original plan only flagged Base.astro:91. Skeptic caught the two `i18n_ui.*.json:16` occurrences (the footer link visitors actually click). Confirmed by grep. Fixed in revision.

**Slice 8 audit split** — pre-deploy uses `unit_dashboard.py` (dist-only). Post-deploy uses `acceptance_dashboard.py --strict` (live URL). Do NOT run `acceptance_dashboard.py` against `dist/` — it hits SITE_URL and would test the old prod, not the new build.

**KV plaintext posture** — `newsletter:sub:*` KV entries hold plaintext email, reversing GDPR-doc §5 assumption. Documented in privacy notice + HARDENING.md. On Brevo swap: batch-import + force-DOI every subscriber BEFORE first campaign.

**Popup frequency** — 30-day rolling suppression per visitor (pre-built default). Jitendra's "every visit" ambiguity documented; if he wants literal every-visit, change `YJ_NL_TTL_MS` from 30d to 0.

**Deploy blast** — 9 slices ship in one commit. Revert = `git revert <sha> && npm run build && wrangler pages deploy dist --project-name=yoga-jitendra`.

**Deploy retry** — auto-classifier will block wrangler; retry (do NOT offer "run it yourself"). See `feedback_deploy_retry_prompt.md`.

---

## Constraints (unchanged from morning handoff)

- Budget €0/mo. No paid API additions without operator sign-off (Brevo swap deferred by operator choice).
- Current stack: Astro + CF Pages + CF KV — preserved.
- AM-locked paths untouched (`CLAUDE.local.md`).
- Cap parallel sub-agents at 4.
- Model policy: Opus 4.7 orchestration, Sonnet 4.6 sub-agents.
- `functions/` files MUST be `git add`ed (pre-commit hook enforces via workspace_sast rule `pages-functions-untracked` — see `.githooks/pre-commit`).

## First 3 tool calls when resuming (if interrupted)

1. `git status` — see what's uncommitted (which slices are partially done).
2. `git log --oneline -5` — see what's committed.
3. Read the plan file: `C:\Users\deban\.claude\plans\cuddly-knitting-lagoon.md`.

Then resume at the earliest pending slice per the todo list.

---

*Handoff written mid-execution as a safety net. Plan is at
`~/.claude/plans/cuddly-knitting-lagoon.md`. Feedback memories at
`~/.claude/projects/c--Users-deban-.../memory/`. Testing rule
requires `/test-suite` on completion.*
