# CAN-SPAM lint rules

Enforced by `outreach/lint_draft.py` on every generated draft before it reaches the dashboard queue. Fails
closed: any violation blocks the draft from being sent (per `CONTRACTS.md` D5, Amodei #5 in the panel pass).
Not a suggestion list — these are the exact checks the linter runs.

| # | Rule | Check |
|---|---|---|
| 1 | From name present | `{{sender_name}}` (or configured From display name) is non-empty and resolved (no literal `{{...}}` left in output) |
| 2 | Honest subject, no false urgency | Subject line does not start with `RE:` / `Re:` / `re:` on **touch 1** (touches 2–4 legitimately use `Re:` per §8.2 of `PROJECT_SPEC.md`) |
| 3 | Physical postal address present | `{{sender_physical_address}}` resolved and non-empty, present in the signature block |
| 4 | Opt-out line present, verbatim | Body contains exactly: `Reply 'no' and I won't follow up.` |
| 5 | Link cap by touch | Touches 1–2: **at most 1** URL in the body. Touches 3–4: **0** URLs in the body. |
| 6 | No ALL-CAPS words | No word of 3+ letters is fully uppercase anywhere in subject or body (case-insensitive scan for exceptions: none — the fixed brand token `ProdCraft` never appears in outreach copy) |
| 7 | No "free" in subject | Subject line does not contain the substring `free` (case-insensitive) |
| 8 | Body length cap | Body word count ≤ 120 words (the spec's per-file cap in this build is ≤ 110 for touch-1/2 variants; the linter's hard ceiling is 120 across all touches) |

Any failed row is written with a `drop_reason` naming the rule number (e.g. `"can_spam:5"`); nothing is
silently skipped, per `CONTRACTS.md`'s "every dropped row" rule.
