# h2 Recruit concept redesign — handoff (2026-09-30)

Live: https://h2recruit-redesign.pages.dev/  (Cloudflare Pages project `h2recruit-redesign`, noindex)
Target: https://www.h2recruit.co.uk/ — SaaS sales recruitment, London + New York, founded 2011 by Ian Harwood and Brian Hawkins.
Prospect: Ian Harwood (replied once to the candidate-outreach cold email, then went quiet). Same play as Keith / GreenJobs.

## What it is
One page, zero dependencies, in the Evolution Exhibits lens (pinned scroll-scrubbed hero, card-stack carousel, rotating drum, hover-accent list), re-cut for a recruiter:
- Hero: scroll scrubs a canvas "pipeline" (360 sellers → shortlist of 5 → one placed hire) through six copy states with a progress rail. Drop `assets/hero.mp4` (+`hero-m.mp4`) and the same scroll scrubs the footage instead (Kling/Higgsfield slot; no video key was available in this cloud session).
- Live roles: the 7 real open roles from the site as a pinned card stack.
- Approach drum, stats band, capabilities list, 2026 salary-report capture, about (founders + Hamish Scott), contact, footer with real addresses.
- **Outreach feed** (`#outreach`): simulated overnight candidate-outreach replay (sent / opened / replied) — the hook Ian originally bit on.
- **Ask h2** (`#ask`): brief a role → comp band, where the candidates are, shortlist time, network match. Runs on a local rule engine today; to make it a real LLM, deploy a Worker on the `greenjobs-ask` pattern (`execution/gtm_client_workflows/greenjobs_redesign/worker/`) with an OpenRouter key and set `data-ask-url` on the form. The `GLM_5_3_TOKEN` in the cloud env is rejected by Z.AI, Bigmodel and OpenRouter, so it was not wired.

## Redeploy
`npx -y wrangler@4 pages deploy deliverables/h2recruit_redesign_2026-09-30/site --project-name h2recruit-redesign --branch main --commit-dirty=true`

## Not done (by design, token budget)
No test suite, no human-eye-test, no audit stack. Verified: Playwright load at 1440 and 390 wide, no JS errors, screenshots of hero/roles/outreach/ask. Fonts (Archivo via Google Fonts) only load on the live URL, not in the cloud sandbox.
