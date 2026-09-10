# Panel-pass roster (workspace copy — canonical rule: `~/.claude/rules/panel-pass.md`, local machine only)

Cloud sessions have no `~/.claude/` layer, so the roster lives here too. Keep both in sync.
Rule of use: before any "shipped/done" claim, every lens below is run as a real sub-agent (or a
written section per lens for spec-stage work), never narrated. Each lens ends with an explicit
**Honest gaps** list. Forbidden framings: "we're done", "all set", "100% complete".

| # | Lens | Question the panelist asks | Added |
|---|------|-----------------------------|-------|
| 1 | **Andrej Karpathy** — measurement | Where is the number? What did you measure, on what sample, and what would falsify the claim? No assumption survives without a `metro_stats`-style empirical row. | 2026-06-16 |
| 2 | **Boris Cherny** — Claude Code / tooling craft | Is it deterministic, idempotent, testable without secrets (`--mock`), scripted rather than narrated? Would a fresh session reproduce it from the directive alone? | 2026-06-16 |
| 3 | **Dario Amodei** — safety, honesty, legal exposure | What can this harm (recipient, third party, the operator's domain reputation, the law: CAN-SPAM, copyright, medical claims, HIPAA)? Is every claim in the copy true? | 2026-06-16 |
| 4 | **Anthropic research team** — rigor | Are the definitions precise (thresholds, boundaries, versions)? Are the prompts pinned (model id, temperature, prompt hash)? Is nondeterminism recorded? | 2026-06-16 |
| 5 | **Alex Hormozi** — offer & unit economics | Value = (dream outcome × perceived likelihood) ÷ (time delay × effort). Does the offer name the dream outcome, reverse the risk, and carry proof? Is the guarantee conditional on a measured baseline? Does LTV ÷ acquisition effort clear 3×? Is scarcity real (an enforced deadline) rather than claimed? | 2026-09-10 |
| 6 | **Nick Saraev** — automation maturity & boundaries | Which rung (prompt → skill → loop → routine) is this, and has the manual output been proven good before automating ("start at the end")? What is the bottleneck, and is anything downstream of it being over-automated? Do customer-felt steps keep a human? Are fuzzy variables few, well-named and inside a human-written template? Is there an error channel (`service / environment / error / count`) and a self-healing change log? | 2026-09-10 |

Sources: Hormozi — *$100M Offers* / *$100M Leads* (value equation, grand-slam offer, risk reversal, lead magnets).
Saraev — `docs/courses/claude_code_marketing_nick_saraev_2026-08.md` §1.3–1.7, §1.12–1.14; `.claude/rules/automation-boundaries.md`.
