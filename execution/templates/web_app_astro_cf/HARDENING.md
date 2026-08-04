# HARDENING.md — <PROJECT_NAME>

Punch list of security / reliability / discipline gaps against the
workspace's always-active rules.

Read-only until the operator approves fixes. Sorted by leverage.

---

## Enforcement gates (baked in by the template)

| Gate | Where | Runs when |
|---|---|---|
| Pre-commit: untracked Pages Functions | `.githooks/pre-commit` | Every `git commit` (after `git config core.hooksPath .githooks`) |
| CI: SAST for untracked Functions | `.github/workflows/ci.yml` | Every push |
| CI: unit tests | Vitest | Every push |
| CI: acceptance gate against preview URL | `tests/acceptance_*.py` | Every push (after preview deploy) |
| CI: front-door synthetic against preview URL | `tests/front_door_*.sh` | Every push (after preview deploy) |
| Workspace SAST | `execution/infrastructure/workspace_sast.py` | Manual + optional pre-push hook |

## Project-specific gaps

*(fill in after first audit)*

| # | Gap | Rule | Severity | Fix effort |
|---|---|---|---|---|
| 1 | ??? | ??? | ??? | ??? |

## Rules this project claims compliance with

- [x] `front-door-synthetic.md` — hits LIVE URL via `tests/front_door_*.sh`
- [x] `output-acceptance-gate.md` — hard-failing corpus-backed gate at `tests/acceptance_*.py`
- [x] `live-artifact-acceptance.md` — git-tracked-functions check in acceptance gate + pre-commit hook
- [x] `model-tier.md` — Gemini free default, Anthropic Sonnet 4.6 fallback, GLM 5.2 forbidden for PII
- [x] `currency-eur.md` — cost logs in EUR via `src/lib/telemetry.ts`
- [x] `python-hardening.md` — subprocess calls in tests use `encoding="utf-8"`
- [x] `powershell-ascii-only.md` — no PowerShell in the template
- [x] `security.md` — no secrets in code; `.env` gitignored; wrangler.toml has no inline secrets
- [x] `always-parallelize.md` — CI job steps parallelize where independent

## Rules that need per-project verification

- [ ] `prior-art-first.md` — write a `## Prior-art pass` block in the directive for every external integration
- [ ] `panel-pass.md` — invoke the 4-lens stack before every "done" claim (see HANDOFF.md)
- [ ] `mandatory-audit-stack.md` — all 6 auditors before shipped/live/ready
