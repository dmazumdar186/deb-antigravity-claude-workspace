# HANDOFF.md — {{APP_SLUG}}

**Read the following note carefully before writing any status update here:**

> Per `~/.claude/rules/front-door-synthetic.md` and `~/.claude/rules/live-artifact-acceptance.md`:
> **Do NOT write "shipped", "live", "ready", "wrapped", "100%", "good to go", "all set" until:**
> 1. The app is `approved` in **both** App Store Connect and Google Play Console.
> 2. `tests/front_door_{{APP_SLUG}}.sh` has passed **5 consecutive days** against the production backend.
> 3. The mandatory audit stack has run (`front-door` + `customer-POV` + `anneal` + `panel-pass` + `test-suite` + `adversarial-loop`) with a verdict table logged in this file.
>
> Until then, the acceptable status framing is: **`PRE-STORE: <phase>`** or **`IN-STORE-REVIEW: submitted YYYY-MM-DD`** or **`LIVE-PROBATIONARY: day N of 5`**.

---

## Current status

**Framing:** `PRE-STORE: scaffolded, no code yet`

**Reason:** The app has just been scaffolded from `execution/templates/mobile_app_expo/`. No screens beyond the starter `HomeScreen`. No backend paired. Not yet submitted to any store.

**Next action:** Choose a backend track (`cf_modal` or `supabase`) and paste it into `execution/mobile_apps/registry.json:apps[<this-slug>].backend_stack`, then follow `directives/mobile_apps/phase1_local_standalone.md`.

---

## Audit-stack verdict table

Update this table every time you make a "done" claim. Any single FAIL blocks the claim.

_(no audit-stack run yet — expected: after first store submission)_

| Auditor | Verdict | Blocking? | Evidence |
|---|---|---|---|
| Front-door synthetic | — | yes | not yet run |
| Customer-POV / acceptance-gate | — | yes | not yet run |
| Anneal (classic or adversarial) | — | yes if FAIL | not yet run |
| Panel (Karpathy — evidence) | — | yes | not yet run |
| Panel (Cherny — dogfood) | — | yes | not yet run |
| Panel (Amodei — deployment) | — | yes | not yet run |
| Panel (Research team — honest gaps) | — | yes | not yet run |
| Test suite (jest + Maestro) | — | yes | not yet run |
| Adversarial (anneal-adv or pipeline-auditor) | — | yes if FAIL | not yet run |

---

## Known blockers / dependencies on operator

- [ ] Apple Developer Program enrollment status: check `.env:APPLE_ENROLLMENT_STATUS`. Must be `active` before EAS iOS builds work.
- [ ] Google Play Console account (~€22 one-time). Personal Developer accounts hit the 12-tester + 14-day gate before public listing eligibility.
- [ ] Paired backend deployed at `EXPO_PUBLIC_API_BASE_URL`. Until the backend responds to `/api/health`, the app's HomeScreen shows "Backend unreachable".
- [ ] Bundle identifiers registered in `.env` (`IOS_BUNDLE_ID`, `ANDROID_PACKAGE`).
- [ ] (Optional) Sentry DSN + PostHog key filled if error reporting / analytics are wanted.

---

## Honest gaps

Per `~/.claude/rules/panel-pass.md`, list every gap on every status update. For each: (a) what, (b) why open, (c) next step.

- **No screens beyond starter HomeScreen** — the scaffolder produces a stack, not an app. Next: follow `directives/mobile_apps/phase1_local_standalone.md` for the first real feature.
- **Icons + splash are placeholders** — `assets/README.md` documents what's needed. Next: generate via `execution/image_generation/` or design tool of choice.
- **Maestro flow is smoke-only** — proves the app launches and the health payload renders. Next: expand once real user flows exist.
- **No CI-side E2E** — Maestro Cloud costs money and iOS E2E from Windows CI is infeasible for free. Next: run Maestro locally against a dev-client build before each store submission.
