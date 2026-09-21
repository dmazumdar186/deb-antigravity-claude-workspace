# Panel pass — ProdCraft "0.5 Website" med-spa pipeline spec (2026-09-10)

Subject: `execution/personal_workflows/prodcraft_medspa/PROJECT_SPEC.md` (spec as uploaded, pre-build).
Roster: `.claude/memory/panel_roster.md` (six lenses; Hormozi and Saraev added this session).
Verdict per lens: **PASS / PASS-WITH-CHANGES / FAIL**. Every change marked **[BUILD]** is implemented in this
session; **[DEFER]** items need the operator or real-world data and are listed under Honest gaps.

The spec's "decisions already made" table is honoured everywhere except where a panelist found a hard
blocker (one case: Cloudflare Pages project-per-preview, see Cherny #2). Deviations are named, not silent.

---

## 1. Karpathy — measurement · PASS-WITH-CHANGES

What is measured well: `metro_stats` sample audit replaces the 40% qualification assumption; `email_source`
logging; baseline booking count before the guarantee clock starts.

Findings:
1. **Vision "dated design" score is unmeasured.** 15 of 100 points depend on an LLM opinion with no reference set.
   **[BUILD]** a labelled golden set (`audit/fixtures/vision_golden/`, 12 synthetic screenshots with expected
   score bands) and a regression test that fails when the prompt or model drifts outside the band.
   **[DEFER]** replace synthetic with 20 real screenshots scored by the operator after the first metro run.
2. **Rubric weights are asserted, not fitted.** **[BUILD]** every signal is stored as its own column plus
   `score_version`; `outreach` rows link back to the audit so weights can be re-fit against reply outcomes after
   50 sends (`scripts/fit_weights.py` produces the correlation table; it does not auto-change weights).
3. **Phase 0 gate at n=5 cannot distinguish a 5% from a 30% call rate.** Kept as a smoke test (the spec's decision)
   but **[BUILD]** the gate is mechanical: `config.phase0` records sends and calls; `daily_queue` caps at 5 prospects
   until `calls_booked >= 1`, then lifts to 20. **[DEFER]** operator decides whether to widen the smoke test to 10.
4. **Reply-rate benchmarks are third-party.** **[BUILD]** `outreach` stores touch, sent_at, replied_at so the
   pipeline computes its own reply rate per touch and per gap type; dashboard shows it.

## 2. Cherny — Claude Code / tooling craft · PASS-WITH-CHANGES

1. **Language.** The spec sketches a TypeScript monorepo; this workspace's contract is deterministic Python under
   `execution/` with hardening rules, a registry and a shared `million_verifier.py`. **[BUILD]** pipeline packages in
   Python (3.11-compatible so cloud and local both run them); Next.js only where the browser is the product
   (template) and TypeScript for the Cloudflare Worker (preview host + expiry cron) and dashboard Pages Functions.
2. **Cloudflare Pages "project per preview" hits the account project cap** (Pages limits projects per account; at
   100 prospects/month it is exhausted in the first quarter) and makes takedown/expiry N separate deploys.
   **[BUILD]** one Worker on `*.preview.prodcraft.fyi` serving static exports from R2 under `previews/{slug}/`.
   Same URL shape, same 30-day expiry, takedown = delete a prefix, zero per-preview infrastructure. This is the one
   deviation from the decisions table; the decision's intent (own domain, per-preview subdomain, zero marginal
   cost, expiry, noindex) is fully kept.
3. **Nothing in the spec runs without secrets.** The cloud session has none. **[BUILD]** every stage has a `--mock`
   path backed by fixtures, a `LocalStore` (JSON on disk) that implements the same interface as `SupabaseStore`,
   and a `doctor.py` that lists every required secret, which stage needs it, and whether the live API answers.
4. **Idempotency.** **[BUILD]** upsert on `place_id`; audits are append-only with `audited_at`; re-running discovery
   or audit never duplicates or double-counts; deploy is content-addressed (skip if hash unchanged).
5. **Re-run in a fresh session.** **[BUILD]** one directive (`directives/personal_workflows/prodcraft_medspa_pipeline.md`)
   with the exact command sequence, plus `scripts/run_metro.py` that chains discovery → audit → enrich → preview.

## 3. Amodei — safety, honesty, legal · PASS-WITH-CHANGES

The spec already handles the big ones (stock imagery, no logo, no review text, watermark, noindex, opt-out,
physical address, no medical claims). Gaps:
1. **Takedown SLA (1 hour) has no automated path**; reply handling is described as manual. **[BUILD]**
   `outreach/scan_replies.py` runs on a 30-minute GitHub Actions cron, classifies replies, and a reply containing
   "remove"/"take down"/"unsubscribe"/"stop" flips `previews.takedown`, `businesses.do_not_contact`, deletes the R2
   prefix, and closes all outreach for that business, without waiting for a human.
2. **The preview itself needs an exit** for an owner who finds it without the email. **[BUILD]** footer watermark
   links to `/remove` which POSTs to the Worker and marks takedown immediately.
3. **Medical-claim leakage from LLM-inferred services.** **[BUILD]** a content linter over `business.json` and the
   rendered HTML that blocks a forbidden-term list ("cure", "guaranteed results", "permanent", "FDA approved",
   "safe for everyone", "no side effects", "clinically proven") and any price or before/after language.
4. **Demo booking widget must not collect PHI.** **[BUILD]** the widget is client-side only, shows a mock calendar,
   never submits, and states "demo — no data is sent".
5. **CAN-SPAM is a checklist, not a linter.** **[BUILD]** `outreach/lint_draft.py` refuses a draft missing the
   postal address, the opt-out line, a From name, or containing a second link; drafts fail closed.
6. **Domain reputation.** Bounce target < 2% is stated; **[BUILD]** only `deliverable` emails enter the queue and the
   dashboard shows rolling bounce rate; the queue halts itself above 2%.
7. **Scraping owner names.** Public records and public web pages only; no login-walled sources. Apollo use stays
   within its licence. **[DEFER]** confirm Apollo seat terms allow export to Supabase (operator).

## 4. Anthropic research team — rigor · PASS-WITH-CHANGES

1. **Rubric boundaries are fuzzy.** **[BUILD]** exact definitions in `audit/scoring.py`: PSI mobile `< 50` → 15,
   `50–69` → 10, `≥ 70` → 0; stale footer year `<= current_year - 2`; jQuery legacy `< 3.0.0`; WordPress theme year
   `< 2018`; buckets `>= 45`, `25–44`, `< 25`; "no website" short-circuits to 100 with every other signal null.
2. **Nondeterminism must be recorded.** **[BUILD]** every LLM call stores `model_id`, `temperature`, `prompt_sha256`
   and raw response in `audits.raw` / `previews.content`; scoring is a pure function of stored signals so it can be
   recomputed offline.
3. **Schema gaps.** **[BUILD]** add `audits.score_version`, `previews.slug_suffix`, `previews.content_hash`,
   `outreach.gap_primary`, `outreach.template_variant`, `businesses.slug unique`, a `config` table for the Phase 0
   gate and proof lines, and `events` (append-only audit log of every status transition).
4. **State machine is implicit.** **[BUILD]** `outreach/state_machine.py` with an explicit transition table
   (`queued → sent → replied | sent(next touch) | closed_lost`, `replied → call_booked → closed_won | closed_lost`,
   any → `dnc`) and a test that enumerates every transition.
5. **Sample audit is a statistic without an interval.** **[BUILD]** `metro_stats` stores `n` and a Wilson 95% interval
   alongside `pct_qualified`.

## 5. Hormozi — offer & unit economics · PASS-WITH-CHANGES

1. **Value equation.** Dream outcome named ("book at 11pm"), time delay and effort collapsed by the built preview,
   risk reversed by paying the balance only at go-live. Strong. **Perceived likelihood is the weak term**: there is no
   proof yet and the spec admits it. **[BUILD]** `deals.tier` accepts a `founding` tier and `config.proof_lines`
   holds citable results; touch 3 and 4 templates read from it and fall back to industry statistics when empty.
   **[DEFER]** operator decision: offer the first 2–3 clients Growth at the Starter price in exchange for a
   before/after booking number and a testimonial. Hormozi's ordering: proof first, price second.
2. **The guarantee must be measurable or it is a liability.** **[BUILD]** onboarding captures
   `baseline_online_bookings_30d`; `deals.guarantee_met` is computed from `bookings_60d` against the baseline, not
   entered by hand.
3. **Scarcity must be true.** The breakup email says the concept comes down Friday. **[BUILD]** expiry is enforced by
   the Worker cron, and touch 4's date is computed from the real `expires_at`, so the deadline is never fictional.
4. **The lead magnet is the preview; its quality is the conversion rate.** **[BUILD]** the template is judged by a
   Playwright acceptance test at 390×844 and 1440×900 (no horizontal overflow, booking CTA visible in the first
   viewport, images lazy, Lighthouse-style budget on total transfer). The reference site the operator likes fails on
   phones; the template must not.
5. **Unit economics.** Growth LTV ≈ $4,500 + 24 × $199 ≈ $9,300. At ~75 sends per close and ~8 minutes per manual
   send, one close costs ~10 operator-hours and ~$30 of tools. Clears any sane threshold. Where it breaks: if reply
   rate lands at the 3–4% platform average instead of 15%, sends per close quadruple. **[BUILD]** the dashboard shows
   sends-per-reply live so the operator sees which case they are in by prospect 30.

## 6. Saraev — automation maturity & boundaries · PASS-WITH-CHANGES

1. **Ladder position.** Phase 0 is the "prompt" rung, run by hand: correct ("start at the end"). Building steps 6–10
   before the gate passes is what the operator asked for; Saraev's objection is to *running* them at scale, not to
   building them. **[BUILD]** everything is built; the Phase 0 gate is enforced in code (see Karpathy #3), so the
   daily queue cannot exceed 5 until the gate is met.
2. **Bottleneck.** The deliberate constraint is the human sending 10–20/day. Everything upstream (discovery, audit,
   enrichment, preview) is over-provisioned and cheap; nothing downstream of the send is automated except reply
   detection and takedown. Correct shape.
3. **Customer-felt steps stay human.** Sending, replying, the call, delivering results: human. Drafting: AI.
   Reply *classification*: AI, but the dashboard shows the classification and the human replies. Takedown is the
   only auto-executed customer-facing action, and it is the one the customer asked for. Consistent with
   `.claude/rules/automation-boundaries.md`.
4. **Fuzzy variables.** `{gap_2}` is a fuzzy variable with a lazy name. **[BUILD]** rename to
   `oneSentenceSpecificBookingGapObservedOnTheirSite` (≈ 12 words), plus
   `fiveWordPlainDescriptionOfTheirBusiness`; the surrounding email is a human-written template pool of three
   variants rotated per prospect (`prompts/email_touch_1_{a,b,c}.md`), never a whole-email generation.
5. **Maintenance trio.** **[BUILD]** `doctor.py` (auth first: every secret present and live), an error channel
   (`notify.py` → Telegram, fixed shape `service / environment / error / count`, with a `--sample` send for the
   wire-up check), and a self-healing change log section in the directive.
6. **Probability multiplication.** Discovery → audit → enrich → preview → draft is five chained steps. **[BUILD]**
   each step writes a status and a reason for every dropped row (no silent drops); `run_metro.py` prints a funnel
   table (found → operational → audited → qualified → owner found → email verified → preview built) so a collapse
   at any step is visible immediately.

---

## Consolidated build decisions (beyond the spec)

| # | Decision | Lens |
|---|----------|------|
| D1 | Python pipeline (`execution/personal_workflows/prodcraft_medspa/`), Next.js template, TS Worker + Pages Functions | Cherny |
| D2 | One Worker + R2 for previews, wildcard subdomain, not a Pages project per preview | Cherny |
| D3 | `LocalStore` + `--mock` fixtures at every stage; `doctor.py` | Cherny, Saraev |
| D4 | Automated takedown path (reply scan cron + `/remove` link), 1-hour SLA met mechanically | Amodei |
| D5 | Content linter (medical claims) + draft linter (CAN-SPAM) fail closed | Amodei |
| D6 | Explicit outreach state machine + append-only `events` table | Research |
| D7 | Phase 0 gate enforced in code (queue cap 5 → 20) | Karpathy, Saraev |
| D8 | `proof_lines` config feeds touches 3–4; `founding` deal tier | Hormozi |
| D9 | Template acceptance test on mobile and desktop viewports | Hormozi |
| D10 | Template pool of three human-written email-1 variants with two named fuzzy variables | Saraev |
| D11 | Wilson interval on `metro_stats`; `score_version` on audits | Research, Karpathy |

## Honest gaps (things this session cannot close)

- No secrets exist in the cloud environment, so every live integration (Places, PSI, Claude vision, Apollo,
  Findymail, MillionVerifier, Supabase, Cloudflare, Gmail) is exercised only through fixtures and `--mock`.
  First live run happens on the operator's machine after `doctor.py` is green.
- The `preview.prodcraft.fyi` DNS zone, the R2 bucket, the Supabase project and the Telegram error channel must be
  created by the operator once; the directive lists the exact commands.
- State-registry lookups (IL SOS, MN SOS, OH SOS, MI LARA, IN INBiz) have no public APIs. The enrichment step
  implements the search-page scrapers with fixtures; they are the most likely step to rot and carry the
  self-healing change-log instruction.
- Vision golden set is synthetic until the operator labels 20 real screenshots.
- Phase 0 (five hand-sent emails) is a human act by definition; the pipeline prepares it but cannot pass it.
