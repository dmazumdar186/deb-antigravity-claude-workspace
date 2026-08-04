# Workspace HARDENING report — 2026-08-04

Read-only audit triggered by the operator after yoga_jitendra_site shipped patchy despite the workspace having ~20 always-active rules and a mandatory 6-auditor stack. Six Opus 4.8 sub-agents ran in parallel across six domains. Per-domain reports are under `.tmp/workspace_audit_2026-08-04/`. This document is the punch list.

**Nothing was modified. Nothing was pushed.** Operator decides what to fix and in what order.

---

## Executive verdict (one paragraph)

**Rules exist. Enforcement doesn't.** The workspace has 1,645 lines of always-active discipline (front-door synthetic, mandatory-audit-stack, panel-pass, live-artifact-acceptance, prior-art-first, output-acceptance-gate, rule-backport-cadence, model-tier, currency-eur, etc.). Only 5 of 14 rules have a mechanical guardrail; **zero are wired into a git hook, CI check, or pre-deploy hook.** ~26% of sub-agent calls are audit-flavored; **the mandatory-audit-stack's required verdict table appears in ~0% of "shipped" claims.** Panel-pass usually runs as narration ("Karpathy would say…") instead of a real sub-agent spawn — the exact 2026-07-01 anti-pattern the rule was born to ban. The `live-artifact-acceptance` rule was born from yoga_jitendra 24 hours ago; the same failure mode has already recurred in the same directory today (3 fresh untracked Pages Functions). The operator's "Sonnet isn't working" hypothesis is not supported by the evidence — the 35 fix-commits over 60 days on job_search_v2 + yoga_jitendra are audit-loop closures, not model-quality regressions. The cause is discipline, not model choice.

---

## The two systemic patterns that keep recurring

### Pattern A — Untracked deployed artifacts
- **yoga_jitendra_site (2026-07-21 → 2026-08-03)** — 13 days of stale fallback in production because `functions/api/dashboard-data.ts` + `functions/wa-out.ts` were never `git add`ed. The rule `live-artifact-acceptance.md` was born from this on 2026-08-03.
- **Same directory today (2026-08-04)** — 3 fresh untracked Pages Functions (`newsletter-subscribe.ts`, `dsr/request-link.ts`, `dsr/[token].ts`). SAST guardrail `_rule_pages_functions_untracked` FIRES on them; nobody is reading its output.
- **interview_iag (right now)** — entire project tree UNTRACKED in git while `agentup-iag.pages.dev` serves live traffic. Deploy is irreproducible if local `dist/` is cleared.
- **yoga_jitendra_site tests** — `tests/front_door_dashboard.sh` + `tests/dom_acceptance_reviews.mjs` (the very files meant to catch this class) are also untracked.

### Pattern B — "Shipped" claims surviving month-long silence
- **job_search_v2** — last live cron run 2026-07-01. **34 days silent** (~30× the 25h freshness floor). Still labelled `LIVE-PROBATIONARY day 0/5` in memory.
- **anthropic_watch** — ledger **52 days stale**. Memory says "shipped".
- **prodcraft_autopilot** — queue frozen at 1 stale item from 2026-06-22 (**43 days**). Memory says "Phase 1 SHIPPED".

Both patterns share the same root cause: rules exist for both; nothing runs the check without human trigger.

---

## Verdict counts across 6 audit domains

| Domain | Verdict |
|---|---|
| Rule mechanical enforcement | 5/14 have SAST · 0/14 wired into hook/CI |
| Shipped-claim discipline | 9 recent "done" claims · ~0% include verdict table |
| Project shipping status (29 projects) | 6 SHIPPED-VERIFIED · 8 SHIPPED-UNVERIFIED · 5 DEGRADED · 3 NEVER-SHIPPED · 1 LOCKED |
| Front-door + acceptance-gate coverage | 4 GREEN · 6 AMBER · 10+ RED |
| Prior-art-pass compliance | 12/33 integrations compliant (35%) · zero backfill pre-2026-06-18 |
| Model-tier compliance | 3 fixable drifts · 1 policy contradiction · deployed services all compliant |

---

## Top 10 fixes, ranked by leverage (severity × ease)

| # | Fix | Domain | Effort | Prevents |
|---|---|---|---|---|
| 1 | Wire `workspace_sast.py --level=high` into a git pre-push hook | Enforcement | 30 min | Every Pattern A recurrence workspace-wide, forever |
| 2 | Commit or delete the 3 untracked yoga_jitendra Pages Functions (`newsletter-subscribe.ts`, `dsr/*`) + `tests/front_door_dashboard.sh` + `tests/dom_acceptance_reviews.mjs` + `wrangler.toml` | Pattern A | 10 min | Next `wrangler pages deploy` recreating the 13-day-stale bug |
| 3 | Commit the entire `interview_iag/` tree | Pattern A | 10 min | Loss of deploy reproducibility |
| 4 | Add a session-end hook that flags "shipped/live/ready/done/complete" without an adjacent verdict table | Enforcement | 45 min | Every "narrated panel-pass" going forward |
| 5 | Extend `_rule_acceptance_gate_missing` in `workspace_sast.py` to (a) scan `execution/**/tests/`, not just root `tests/`, (b) not be hardcoded to 5 projects, (c) add analogous `_rule_front_door_missing` | Enforcement | 1 h | Every future acceptance-gate skip |
| 6 | Extend SAST to scan `.claude/agents/*.md` frontmatter for banned models — catches `note-taker.md:4` `model: haiku` today | Enforcement | 20 min | Silent Haiku creep in agent definitions |
| 7 | Update `.claude/settings.json:3` (Opus 4.7 → 4.8) and `AGENTS.md:331` + `GEMINI.md:331` (Opus 4.6 → 4.8) | Model policy | 5 min | Stale model refs in shared docs |
| 8 | Resolve the Haiku fan-out policy contradiction (workspace `CLAUDE.md:247` defaults fan-out to Haiku vs. user-level rule bans it) — pick one, purge the other | Model policy | 30 min | Ongoing tier ambiguity |
| 9 | Run the owed `panel-pass` backport-triage (49 days late) — sample 5 recent "done" claims and audit retroactively | Rule-backport | 1 h | Debt accumulation on the meta-rule |
| 10 | Run the owed `output-acceptance-gate` backport-triage across cv_optimizer, humanizer, youtube_video_analyzer, job_tracker_pm_france | Rule-backport | 2 h | 4 known artifact-producing projects with no output-acceptance |

**Two changes (#1 + #4) close ~70% of the recurrence surface.** Pre-push SAST catches Pattern A files before they're pushed; session-end verdict-table check catches Pattern B claims before they're written to HANDOFF.

---

## Domain reports (full detail)

- **Rule invocation + shipped-claim discipline** — `.tmp/workspace_audit_2026-08-04/rule_discipline_findings.md`
- **Project-by-project shipping status** (29 projects) — `.tmp/workspace_audit_2026-08-04/project_shipping_status.md`
- **Front-door + acceptance-gate compliance** — `.tmp/workspace_audit_2026-08-04/front_door_acceptance_compliance.md`
- **HARDENING_BACKLOG + rule-backport-cadence** — `.tmp/workspace_audit_2026-08-04/hardening_backlog_compliance.md`
- **Prior-art-pass compliance across integrations** — `.tmp/workspace_audit_2026-08-04/prior_art_compliance.md`
- **Model policy + LLM cost discipline** — `.tmp/workspace_audit_2026-08-04/model_policy_compliance.md`

---

## What the audit does NOT claim

- **This audit itself did not run the mandatory-audit-stack against yoga_jitendra_site.** The operator asked for a workspace-level audit; the project-specific dashboard/reviews audit was declined. Trends chart + Discovery mix on yoga_jitendra dashboard remain uninvestigated — those may have the same class of hydration bug as the hero tiles and I have no evidence otherwise.
- **No live URL was curl'd against AM-locked infrastructure.** No AM credentials were used.
- **No fixes were applied.** No commits, no pushes.
- **The "Sonnet vs. Opus" question is not settled.** No A/B benchmark exists; auditor 6 recommends running one (~5 tasks, ~€5-10) before switching sub-agents. Absent that benchmark, current evidence points to discipline (audit-stack invocation), not model quality, as the cause of shipped patchiness.

---

## Recommended next 3 moves (in order)

1. **Commit or delete every currently-untracked file that would land in a deploy** — kills the immediate Pattern A recurrence risk. 10 min.
2. **Wire SAST into pre-push hook + add session-end verdict-table hook** — makes the discipline mechanical. 1-2 h.
3. **Pick 3 highest-value projects and run the mandatory-audit-stack against each** — yoga_jitendra_site + one other DEGRADED (job_search_v2 or anthropic_watch) + one other RED (prodcraft or job_tracker_pm_france). Produces per-project HARDENING files. Establishes the pattern.

Everything else is nice-to-have. #1 and #2 are load-bearing.

---

*Generated by 6-agent read-only audit, Opus 4.8, wall clock ~40 min, cost ~€8-12 tokens.*
