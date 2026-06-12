# Security Audit — 2-Pass Vibecoded-App Audit

Runs **after** the app has a working backend (Phase 4 onward) and **before** any TestFlight/Play submission. Encodes Nick Saraev's "security for vibecoded apps" audit prompt (transcript chapter 23 + 34), adapted with the workspace's `anneal` adversarial pass as a third pass when the stakes warrant it.

## Goal

Identify and fix the OWASP-adjacent vulnerabilities that AI-generated mobile/backend code reliably introduces, in two independent passes so that fixes from pass 1 don't mask new issues that only show up in pass 2.

Specifically:

- Hallucinated package imports
- Missing serverside input validation
- Default-open database policies (RLS missing/wide-open on Supabase, public R/W on KV/D1)
- Hardcoded secrets / `.env` leaks via console logs / public-prefix env leaks
- Inconsistent OAuth/auth middleware (some endpoints protected, others not)
- Error-information leaks (stack traces in 500 responses)
- Cost-amplification vectors (expensive paid-API calls on an unauthed endpoint → attacker can drain Anthropic/OpenRouter credits)
- Startup config validation (no fail-fast on missing required env vars)

## Inputs

- App slug
- App repo at `C:\Users\deban\dev\mobile-apps\<slug>` with backend phase shipped
- Audit prompt: `directives/mobile_apps/security_audit_prompt.md` (see "Steps" — checked into workspace as the canonical prompt; do not derive from memory)

## Tools/Scripts

- `claude /clear` (Claude Code built-in) — must be run between passes to ensure pass 2 has zero context from pass 1
- `anneal` (optional pass 3, see "Optional pass 3" below)

## Outputs

- `C:\Users\deban\dev\mobile-apps\<slug>\.audit\pass1_findings.md` — findings table + severity ranks
- `.audit\pass1_fixes.diff` — `git diff` snapshot of pass-1 fixes
- `.audit\pass2_findings.md` + `.audit\pass2_fixes.diff`
- One commit per pass: `security: pass <N> audit fixes`
- Updated `execution/mobile_apps/registry.json` field: `<slug>.last_security_audit_at`

## Steps

1. **Pre-conditions check.** Verify all three are true:
   - Phase 4 (backend) has shipped (CF Worker live OR Supabase project provisioned).
   - The app boots end-to-end on a real device (not just Expo Go preview).
   - Working tree is clean (`git status` shows no uncommitted changes). If dirty, commit or stash first.
2. **Open the audit prompt.** Read `directives/mobile_apps/security_audit_prompt.md` — this is the canonical "vibecoded apps audit" prompt Nick references. It lists the categories above with concrete checks per category and asks Claude to rank findings as critical / high / medium / low with a CWE reference where applicable.
3. **Pass 1 — fresh context.**
   ```
   cd C:\Users\deban\dev\mobile-apps\<slug>
   ```
   In Claude Code (or the Anti-Gravity Claude pane): `/clear`. Paste the audit prompt verbatim. Wait for the ranked findings list.
4. **Save findings.** Copy the findings into `.audit/pass1_findings.md`. Create the `.audit/` directory if missing.
5. **Pass 1 — fix.** In the same Claude session, ask: *"Run through and fix all of these issues end-to-end. After you're done, test and ensure they're 100% solved."* Let it apply the diffs.
6. **Diff snapshot.** `git diff > .audit/pass1_fixes.diff`. Review the diff yourself for any change that *introduces* a new vulnerability (e.g., a permissive CORS header added "to fix the auth issue"). If anything looks wrong, push back before committing.
7. **Commit pass 1.** `git add -A && git commit -m "security: pass 1 audit fixes"`.
8. **Pass 2 — fresh context.** `/clear` again. Paste the **exact same audit prompt** verbatim. Pass 2's job is to find issues pass 1 either missed or introduced. Do not reference pass 1 in the prompt.
9. **Save pass 2 findings.** `.audit/pass2_findings.md`. Compare against pass 1: anything that escalated in severity (e.g., went from partial to fail) is a regression from pass 1's fix and must be addressed urgently.
10. **Pass 2 — fix.** Ask Claude: *"Fix all findings, even partials. Once sorted, let me know if the changes produced new vulnerabilities."* Apply diffs.
11. **Commit pass 2.** `git diff > .audit/pass2_fixes.diff && git add -A && git commit -m "security: pass 2 audit fixes"`.
12. **Update registry.** Set `<slug>.last_security_audit_at` in `execution/mobile_apps/registry.json` to ISO timestamp. Note `<slug>.audit_passes_run = 2`.
13. **Report.** Summarize for the user: critical findings count (pass 1 → pass 2), categories that hit fail/partial, anything Claude flagged as out-of-scope for AI fix (e.g., infra-level RLS that requires a Supabase console click). Outstanding items go in the report.

## Optional pass 3 — anneal adversarial

For apps with paid AI features (Phase 5/5b), apps storing PII, or apps about to ship to production at scale: run anneal adversarial against the cumulative audit diff. This adds the Red-vs-Blue duel from anneal v0.1 — different model coverage than two passes of the same Claude family.

```
git -C C:\Users\deban\dev\mobile-apps\<slug> rev-parse HEAD~2  # base ref = before pass 1
cd C:\Users\deban\dev\anneal
py -m anneal.cli adversarial <base-ref-sha> --repo C:\Users\deban\dev\mobile-apps\<slug>
```

(Adversarial mode does NOT accept `--diff-file`. Pass the base-ref SHA positionally per anneal cli.py:529.)

Skip pass 3 for hobby apps with no paid APIs or PII.

## Edge Cases

- **Pass 1 fixes break the app.** Common — `/clear` after committing pass 1 doesn't restore app functionality if the fixes broke a flow. Run the 3-tier test (Chrome → mirror → phone) after pass 1 *before* pass 2. If anything broke, fix it under a `security: pass 1 functional regression` commit before pass 2.
- **Pass 2 finds zero issues.** Possible but rare on a vibe-coded app. Likely means the audit prompt was watered down or the codebase is genuinely small. Double-check by spot-grepping the codebase for `process.env.` and `SUPABASE_SERVICE_ROLE_KEY` to make sure the prompt actually loaded the relevant files.
- **A finding requires infra change (e.g., Supabase RLS policy in the console).** Claude can write the SQL but can't apply it. List the SQL + console steps in `.audit/pass<N>_findings.md` under `## Manual follow-ups` and surface to the user. Do not mark the audit complete until the user confirms they applied the manual change.
- **Critical findings remain after pass 2.** Do not ship. Either fix manually, escalate to anneal pass 3, or reduce scope (e.g., remove the AI feature that's the cost-amplification vector until v2).
- **Hardcoded `.env` values found.** Rotate the leaked secret IMMEDIATELY at the provider (Anthropic, OpenRouter, Supabase service-role). Pass-1 fix only removes the value from the repo; the leaked secret remains valid until rotated.
- **App uses Supabase Edge Functions.** Confirm Edge Function secrets are set via `supabase secrets set`, not env vars in the function code. Pass-1 commonly catches the literal env-var-in-code case but misses *unset* secrets that fall back to undefined at runtime — add a runtime startup-validation check.
- **CWE references in findings.** Common Weakness Enumeration IDs (e.g., CWE-798 hardcoded credentials) are informational only — useful for severity calibration, not required for the fix. If Claude doesn't include them, do not re-ask.

## Exit Criteria

The directive is "done" when ALL of these hold (each must be machine-verifiable):

- `.audit/pass1_findings.md` exists in the app repo with a findings table containing severity rankings (critical / high / medium / low).
- `.audit/pass1_fixes.diff` exists and is non-empty (`git diff` snapshot of pass-1 changes).
- Pass-1 commit exists: `git log --oneline` includes a commit with "security: pass 1 audit fixes".
- `.audit/pass2_findings.md` exists (written after a `/clear` to ensure zero context bleed from pass 1).
- `.audit/pass2_fixes.diff` exists and is non-empty.
- Pass-2 commit exists: `git log --oneline` includes a commit with "security: pass 2 audit fixes".
- Zero CRITICAL findings remain after pass 2 (`.audit/pass2_findings.md` contains no rows ranked `critical`). If any CRITICAL persists, it must be listed under `## Manual follow-ups` with an explicit owner action required.
- `execution/mobile_apps/registry.json` entry for `<slug>` has non-null `last_security_audit_at` (ISO timestamp) and `audit_passes_run = 2` (or `3` if anneal adversarial pass was run).
- For Phase 5 apps: `last_security_audit_at` timestamp is newer than the Phase 5b deploy commit timestamp.

If any predicate fails, fix before claiming the security audit complete. Do NOT submit to TestFlight or Play Console with outstanding CRITICAL findings.

## Notes

- Two passes minimum is non-negotiable per Nick chapter 23. The whole point is that fixes-introduce-new-bugs happens reliably, and the only catch is an independent re-audit with zero context bleed.
- The canonical prompt at `directives/mobile_apps/security_audit_prompt.md` is the source of truth. If you discover a new vulnerability class (e.g., new Supabase RLS pattern, new Edge Function secret leak), update the prompt file first — never rely on memory or per-session adaptation.
- After ship, re-run this directive whenever a Phase 4 or Phase 5 change ships. App-only changes (Phase 1-3 UI tweaks) don't require re-audit.
- Companion directive: `directives/mobile_apps/app_design.md` runs *before* Phase 1.
