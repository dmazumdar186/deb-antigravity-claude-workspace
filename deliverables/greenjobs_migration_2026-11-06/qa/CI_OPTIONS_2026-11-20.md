# GreenJobs release pipeline: GitHub Actions vs CircleCI (read 2026-11-20)

All "read" dates are 2026-11-20 via WebFetch/WebSearch. UNVERIFIED = not confirmed on a live page.

## Comparison

| Need | GitHub Actions | CircleCI | Source |
|---|---|---|---|
| Monthly cost | Free plan: $12 included compute (~2,000 min at $0.006/min, derived); Pro/Team $18 (~3,000 min). Linux 2-core $0.006/min. Dependabot runs do not use included compute | Free: 30,000 credits/mo, 5 active users, 30 concurrent. Performance from $15/mo (+$15 per 25,000 credits). Private-repo use on free credits per pricing FAQ. Credits per minute: UNVERIFIED (resource-class page not read) | docs.github.com/.../about-billing-for-github-actions; circleci.com/pricing/ |
| Manual approval gate, PRIVATE repo | Required reviewers/wait timers: only public repos on Free/Pro/Team; private needs Enterprise (search summary) | `type: approval` job, no plan restriction stated; anyone with push access can approve; limit approvers via restricted context on downstream deploy job; 90-day approval window | docs.github.com/en/actions/reference/workflows-and-actions/deployments-and-environments; circleci.com/docs/guides/orchestrate/workflows/ |
| Env secrets / restrictions | Environment secrets on private repos need Pro/Team/Enterprise; branch restrictions on private need Pro/Team | Contexts on Free+; restrict by security group (GitHub orgs), project, expression (e.g. branch==main); fail closed; 100 vars/context | same GH page; circleci.com/docs/guides/security/contexts/ |
| Cloudflare auth | API token + account ID (CF GitHub Actions guide). No OIDC found | Same: API token in context. CircleCI OIDC documents AWS/GCP only; no Cloudflare statement | developers.cloudflare.com/workers/ci-cd/external-cicd/github-actions/; circleci.com/docs/guides/permissions-authentication/openid-connect-tokens/ |
| Monorepo path filter | `on.push.paths` native, one file | Dynamic config (setup workflow, path-filtering orb), on Free; one workflow per setup pipeline, 6h continuation window, no rerun of continued workflow | circleci.com/docs/guides/orchestrate/dynamic-config/ |
| Dependabot | Native; Dependabot-triggered runs see only Dependabot secrets (duplicate them), read-only token | No official doc found; support article on "No configuration found" for dependabot[bot] PRs (UNVERIFIED fix) | github.blog changelog 2021-11-30; support.circleci.com article 15091489 |
| Weekly audit job | `schedule:` cron | Scheduled workflows not for GitHub App pipelines; use Schedule Triggers; up to 15 min delay | circleci.com/docs/guides/orchestrate/workflows/ |
| Audit logs | Plan-dependent (not researched, UNVERIFIED) | Request-only on Free (1/day, org admins), 3/day Performance, S3 streaming Scale only; 12 months | circleci.com/docs/guides/security/audit-logs/ |
| Handover to client org | Transfer repo; secrets/environments must be recreated (UNVERIFIED on live page) | New org via GitHub App, recreate contexts, history not carried; paid plan transfer downgrades to Free | circleci.com/docs/guides/plans-pricing/plan-overview/; users-organizations-and-integrations-guide |
| Reliability extras | Re-run failed jobs | Flaky detection (Free: 5 tests), test splitting, SSH rerun (SSH not verified) | plan-overview |
| Ops overhead | One system | Second vendor, second login, second secret store | n/a |

## Claim -> Objection -> Resolution

1. Claim: keep GitHub Actions. Objection: required-reviewer gate is unavailable on private repos below Enterprise, so `environment: production` in greenjobs_promote.yml may not gate at all. Resolution: amend; verify our plan and test the gate before trusting it.
2. Claim: add CircleCI only for the gate. Objection: two systems, two secret stores, split audit trail, for one feature. Resolution: drop unless the GH gate cannot be fixed cheaply.
3. Claim: CircleCI reliability features help. Objection: ~5-minute suite, solo operator; splitting and flaky detection add little. Resolution: drop.

## Recommendation

Stay on GitHub Actions; do not run CircleCI alongside. First fix the one real gap: confirm the repo's GitHub plan and whether the `production` required-reviewer rule is actually enforced on this private repo (docs say it is not below Enterprise). If not enforced, cheapest fixes are (a) move GreenJobs to its own repo or org at handover, where plan and visibility are a client decision, or (b) a `workflow_dispatch` plus a self-check that the promote job fails unless a signed approval (e.g. a merged approval PR or a protected-branch tag by a named user) exists. Only if neither works, move just the promote stage to CircleCI (Free: approval job plus restricted context, about $0). Cloudflare gets an API token either way, so OIDC favours neither. Cost: GHA about $0 to $4/mo (Team seat price UNVERIFIED); CircleCI Free $0, Performance from $15/mo.
