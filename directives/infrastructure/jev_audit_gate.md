# Jev Audit Gate (confidence gate on the audit stack)

## Goal
An audit report that says PASS is not the same as a trustworthy PASS. Jev scores each reviewer report
(anneal-reviewer, code-reviewer, pipeline-auditor, qa) for verdict clarity, evidence quality and scope
coverage; weak reports escalate to a re-review instead of counting as audit evidence for a "done" claim.

## Operator prompts
- "Gate this audit report" → `python3 execution/infrastructure/jev_audit_gate.py gate --report <file>`
- "Why did the gate flag the last review" → read the tail of `.tmp/jev_audit_gate_log.jsonl` (reasons + signals),
  or re-run `transcript --path <session.jsonl> --last 3`.

## Inputs
- Report text (file or stdin `-`); optional `--asked-for "text"` or `--asked-for @brief.md` (the checks the auditor was asked for).
- Env `OPENROUTER_API_KEY` (cloud alias `OPENROUTER_API_TOEKN`).

## Tools
- `execution/infrastructure/jev_audit_gate.py` — `gate_report()` + CLI.
  - `gate --report path|- [--asked-for ...] [--json]` → exit 0 accept, 1 review, 3 reject, 2 usage error.
  - `transcript --path file.jsonl [--last 5] [--json] [--dry-run]` → gates the last N sub-agent hand-back
    reports (user entries with `[Subagent hand-back]`, or tool_result of Agent/Task calls); exit = worst decision.
- `/jev gate <file>` (`.claude/commands/jev.md`).

## What Jev scores (one call per report)
`verdict` (pass / pass_with_warnings / fail / inconclusive), `worst_severity` (none..critical),
`evidence` (score 0-3: claims only → every finding cites file:line and shows output), `scope_covered`,
`self_consistent` (verdict matches findings table), `unverified_claims` (ran-tests-without-output, "should work", "likely").

## Decision (code-side, `DEFAULT_CFG`)
- **reject**: verdict = fail (any confidence), or self_consistent < 0.4.
- **accept**: verdict ∈ {pass, pass_with_warnings}, confidence ≥ 0.7, evidence ≥ 2.0, self_consistent ≥ 0.6,
  unverified_claims < 0.4, scope_covered ≥ 0.6 (only when `asked_for` is given).
- **review**: everything else; each reason names the failing signal and value. Jev error → review "jev unavailable" (never silent accept).
- Override any threshold in `.claude/jev/config.json` → `"audit_gate": {"min_evidence": 1.5, ...}`.

## Tuning
Once ≥30 human-labelled reports exist (label = accept/review/reject), build a spec per signal (e.g. the
`evidence` score question) and run `jev_validate.py --spec ... --data ... --sweep` (directives/infrastructure/jev_validate.md).
Pick each threshold from the sweep, then set it under `audit_gate` in config.json.

## Stop-hook behaviour
`.claude/hooks/verdict-table-check.sh` keeps its shipped-claim check, then (unless `.claude/jev/state.json` has
`"enabled": false`) runs `transcript --last 3 --json` under `timeout 4` (calls in parallel, 2.5 s each). If any
report is review/reject it appends "> **Jev audit gate:** n of m recent audit reports scored below the acceptance
bar — ..." to `additionalContext`. Advisory and fail-safe: any failure exits 0 silently.

## Outputs / cost
Ledger row `caller=jev_audit_gate` in `.tmp/jev_ledger.jsonl`; decisions in `.tmp/jev_audit_gate_log.jsonl`.
Report text is sent to OpenRouter/TypeSafe — toggle `/jev off` for confidential sessions.

## Edge cases
- No hand-back reports in the transcript → no output, no Jev call.
- Reports longer than 24k chars are truncated (`max_report_chars`).
- Non-audit hand-backs (e.g. implementation summaries) are gated too and will usually land in review;
  the warning is advisory.

## Edge cases (added 2026-10-07)

- **Not every hand-back is an audit.** The same Jev call answers `is_audit`; transcript mode skips hand-backs below `min_is_audit` (0.5) with decision `skip` (exit 0), so implementation summaries never trigger the Stop-hook warning. Measured on this workspace's own transcript: four build hand-backs scored 0.14-0.26 and were skipped; the three sample audit reports scored 0.97-0.98.

## Changelog
- 2026-10-07: created (use-case-finder quick win "confidence gate").
- 2026-10-07: added `is_audit` signal + `skip` decision so only audit/review reports are gated in transcript mode.
