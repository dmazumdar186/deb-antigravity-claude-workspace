# ProdCraft: 50-week LinkedIn messaging system

**Purpose:** build a founder-led audience for ProdCraft with specific, useful, human posts—not 50 variations of an AI-services ad. This pack contains 50 banner headlines, supporting lines, a companion post angle, visual direction and publishing guardrails.

## 1. Executive finding

The current 20-card set has a strong editorial visual identity, but the campaign is over-commercialised and its evidence governance is not acceptable as written. The repository source-of-truth file explicitly labels some numbers as stretched or modeled. Correct the claims before publishing or redesigning the set.

### Quantitative messaging audit (editorial rubric, not platform analytics)

| Dimension | Current set (estimate) | Target gate | Why |
|---|---:|---:|
| Audience specificity | 4/10 | 8/10 | Many cards pitch to “founders” or “buyers” generally instead of one problem-owner.
| Natural, human voice | 4/10 | 8/10 | Repeated slogan structures, contrasts, and “ship fast/no agency” formulations feel templated.
| Useful insight for the reader | 3/10 | 8/10 | Most cards assert the offer or the proof rather than teaching a decision, test or lesson.
| Distinctiveness of the point of view | 5/10 | 8/10 | The “not an agency / no slide deck / live in weeks” territory is familiar in AI marketing.
| Evidence integrity | 2/10 | 10/10 required | The repository documents public values that are scaled, modeled or otherwise stretched relative to underlying sources.
| Conversation potential | 3/10 | 7/10 | Few cards offer a useful trade-off or concrete question worth discussing.
| Visual consistency | 8/10 | 8/10 | The editorial typography and palette are coherent; repetition and footer clutter weaken the series.
| Mobile action clarity | 4/10 | 8/10 | Repeated footer with website, GitHub, booking URL and QR code creates multiple competing actions; QR is awkward when viewing on the same phone.

These are expert editorial judgements, not measured performance scores. Do not call them a measured “10× improvement.” A performance lift can only be assessed after a baseline and controlled publishing tests.

## 2. The 20 existing cards: specific problems

| # | Problem in the current card | Reframe |
|---|---|---|
| 01 receipts | Three unrelated proof points in one graphic; “all three are live” is ambiguous. The $1M+ and +45% figures need evidence correction. | Choose one case and one buyer problem per post; label each result accurately. |
| 02 48k-emails | Uses a 2× volume figure and modeled pipeline as if measured; adds SDR replacement and cost claim in one breath. | Use verified operating volume and reply definitions; call pipeline modeled if it is modeled. |
| 03 latency | The before/after story repeats the adoption/latency claims that the repo says were uplifted. “Six weeks later” needs a documented timeline. | Use a factual mechanism story or the defensible source metrics only. |
| 04 not-an-agency | Leans on attacks on agencies, junior staff and discovery fees. “Weeks, not quarters” is too broad without a scoped example. | State the client advantage positively: direct access to the person making and building the product. |
| 05 walk-away | Potentially strong trust differentiator, but ownership/no-retainer/exit-fee lines are contractual promises. | Publish only terms ProdCraft actually guarantees; show the handover checklist. |
| 06 cv-optimizer | Combines language checks, recruiter-proxy evaluation and screenshot-regression claims; the “95% fields pass” phrasing can conflate different tests. | Define each evaluation and demonstrate it on screen; avoid mixing success criteria. |
| 07 video-studio | Interesting build note, but “eight minutes” and “$0 marginal cost” need repeatable measurements and cost boundaries. | Show the pipeline and label timings/costs as a specific run or measured average. |
| 08 mobile-14-days | The 14-day claim can be read as client delivery when it may describe a reusable pipeline/template. | State exactly what reached TestFlight, for whom, and what was included. |
| 09 operator-stack | A list of tools is not a buyer problem; it reads like a capability inventory. | Show one workflow and why a tool was chosen over the alternatives. |
| 10 sdr-math | Substantially repeats card 02; cost savings and “four SDRs worth” risk implying measured headcount displacement. | Retire as a standalone claim unless verified; explain cost-equivalent assumptions transparently. |
| 11 voice-agent | Generic feature list (“answers, qualifies, books”) with no example of failure handling or real call. | Show a call snippet and the moment the agent correctly escalates to a person. |
| 12 before-you-hire | Sets up a simplistic comparison with a full-time hire and promises a first commit this week before scoping. | Help the reader decide when to hire, prototype or buy a scoped build. |
| 13 shipped-list | Five products and several metrics compete for attention; it mixes differing levels of readiness and proof. | Give each build its own story and clearly label live product, internal tool, prototype or concept. |
| 14 kill-switch | “Idempotent,” “dual path” and “0 duplicate sends” are too implementation-heavy for a general audience; zero duplicates needs evidence. | Lead with the failure the safeguard prevents, then show the technical detail. |
| 15 paris-founder | Most personal and differentiating card, but “founders done waiting on roadmaps” is still a familiar slogan. | Add one specific change in how you work or a real decision that motivated ProdCraft. |
| 16 three-things | Service menu rather than a message; nine tags dilute the point. | One target buyer and one use case per card. |
| 17 hours-saved | $10K/week and 100+ hours/week are described internally as extrapolated. They should not appear as measured savings. | Remove until backed by client time tracking or present an explicitly modeled scenario with assumptions. |
| 18 objections | Three generic objections and broad “every system” guarantees create a sales-deck feel. | Address one real objection with a concrete example and a limit/exception. |
| 19 how-it-starts | Fixed Day 0/2/Week 2/Week 4 sequence can be mistaken for a delivery promise independent of scope. | Show the discovery decisions and dependencies; timelines follow the scope. |
| 20 book-call | Generic CTA and a promise to “leave with a build plan” that may not fit every 30-minute conversation. | Offer a specific low-friction action: map one workflow and decide whether it is worth automating. |

## 3. The creative changes to make once—not 50 times

- **These are 4:5 feed creatives (1080×1350), not a LinkedIn profile-header banner.** Call them feed cards or post creatives in the codebase.
- Keep the ProdCraft wordmark small. Remove the repeated QR code and the three-link footer from most cards. The post text can carry one relevant link; the image should carry one idea.
- Remove “01 / 20” from the artboard or change it to a restrained editorial series label. A year-long feed should not look like a batch of 20 assets exported together.
- Use the handwritten annotation sparingly. Repeating a script font to manufacture a human touch becomes another template cue.
- Keep the cream/ink/brass palette, but vary the composition across at least six families: editorial headline, annotated workflow, failure checklist, before/after, code-to-outcome, real product screenshot, founder note and case receipt.
- Banner rule: one headline, one supporting line, one visual proof/diagram at most. No tool salad. Use the caption for context and caveats.
- Not every week should ask for a call. Use explicit conversion prompts in roughly 4–6 of the 50 posts; the rest should earn attention by being useful.
- Never invent a founder anecdote, customer quote, measured number or claim of production usage. Ask Debanjan for the actual event/evidence if absent.

## 4. Claim governance — required before any banner is rendered

The current repository file `execution/personal_workflows/personal_brand/metrics_canonical.md` says these public claims are stretched or modeled relative to their underlying sources: 48,000/month vs 24,000/month baseline; $1M+ pipeline is modeled from assumptions; +45% adoption vs +30% in the cited source; −55% latency vs −40% in the cited source; $10K/week and 100+ hours/week are extrapolated. Do not publish these as measured actuals without fresh evidence. Prefer verified source values and plain labels: **measured**, **modeled estimate**, **cost-equivalent estimate**, or **illustrative scenario**.

Before a proof card ships, attach: source file/log/dashboard, date range, denominator, definition of metric, role/attribution, disclosure permission, and exact approved wording. If any field is missing, render a non-numeric insight card instead.

## 5. The 50-week message bank

Each banner has a headline, one supporting line and a companion-post angle. The caption should add a real example or useful explanation; it should not merely repeat the banner. Creative directions are cues for a varied series, not a request to create 50 identical layouts.

### Week 01 — Product judgment
**Banner headline:** Before you automate it, follow one real case.
**Supporting line:** The exceptions hide in the handoffs—not in the happy-path flowchart.
**Companion post:** Tell a short story about shadowing a real workflow before deciding what to automate. Show the steps and the surprise.
**Visual direction:** minimal_editorial · **CTA:** No CTA
**Publish guardrail:** none

### Week 02 — Outbound systems
**Banner headline:** A sent email is an activity. A useful reply is progress.
**Supporting line:** The system matters most after someone answers.
**Companion post:** Explain how replies get classified, routed and followed up. Keep volume separate from qualified opportunities.
**Visual direction:** large_type_plus_flow · **CTA:** Ask a practical question, not “agree?”
**Publish guardrail:** none

### Week 03 — AI reliability
**Banner headline:** An AI demo works on the happy path.
**Supporting line:** A product has to handle missing fields, strange inputs and wrong answers.
**Companion post:** Share three failure cases you now test before trusting an AI workflow. Do not invent an incident; use real examples from your work.
**Visual direction:** failure_case_checklist · **CTA:** No CTA
**Publish guardrail:** none

### Week 04 — Operations
**Banner headline:** If a human still copies the answer into the CRM, the workflow isn’t finished.
**Supporting line:** Close the loop: update the record, assign an owner, show the next step.
**Companion post:** Map a before/after handoff without claiming time savings you have not measured.
**Visual direction:** workflow_diagram · **CTA:** No CTA
**Publish guardrail:** none

### Week 05 — Founder perspective
**Banner headline:** I moved closer to the code because handoffs hide too much.
**Supporting line:** Product decisions make more sense when you see what it takes to ship them.
**Companion post:** Describe a real moment from your product career that changed how you work. Add a specific detail only you would know.
**Visual direction:** founder_note · **CTA:** No CTA
**Publish guardrail:** none

### Week 06 — AI product strategy
**Banner headline:** Not every AI idea deserves an agent.
**Supporting line:** Sometimes a rule, an API call and one human check are enough.
**Companion post:** Give a decision test for choosing between rules, a workflow, RAG and an agent.
**Visual direction:** decision_tree · **CTA:** Invite thoughtful counterexamples
**Publish guardrail:** none

### Week 07 — Voice AI
**Banner headline:** A voice assistant needs to know when to stop talking.
**Supporting line:** Escalation is part of the experience—not a failure state.
**Companion post:** Explain what a good human handoff should preserve: caller context, reason and transcript.
**Visual direction:** call_flow · **CTA:** No CTA
**Publish guardrail:** none

### Week 08 — Trust / offer
**Banner headline:** Bring one repetitive task. Not a 40-slide AI strategy.
**Supporting line:** We’ll map the current steps and decide whether automation is worth it.
**Companion post:** Explain what happens in a ProdCraft discovery/build session and what you will not promise before scoping.
**Visual direction:** simple_offer_card · **CTA:** Soft invitation
**Publish guardrail:** Use this CTA only if the 30-minute session and described process are currently offered.

### Week 09 — Product delivery
**Banner headline:** A roadmap item is not a business outcome.
**Supporting line:** Name what should change for the user after the feature ships.
**Companion post:** Show how you would rewrite a vague AI roadmap item as an observable user or business change.
**Visual direction:** before_after · **CTA:** No CTA
**Publish guardrail:** none

### Week 10 — Operations
**Banner headline:** A workflow without an owner is just a script.
**Supporting line:** Who acts when the model is uncertain, the API fails or the customer needs a person?
**Companion post:** Walk through ownership across the workflow: trigger, automation, exception, human and audit trail.
**Visual direction:** swimlane · **CTA:** No CTA
**Publish guardrail:** none

### Week 11 — Outbound systems
**Banner headline:** More sends won’t fix a weak list.
**Supporting line:** Data quality and deliverability set the ceiling before copy gets a chance.
**Companion post:** Share a pre-flight checklist: source quality, domain health, validation, audience fit and stop conditions.
**Visual direction:** checklist_card · **CTA:** No CTA
**Publish guardrail:** none

### Week 12 — RAG / knowledge
**Banner headline:** RAG can retrieve the wrong truth very quickly.
**Supporting line:** If the source documents are stale or contradictory, retrieval won’t fix that.
**Companion post:** Explain document ownership, freshness, citations and what to do when sources conflict.
**Visual direction:** annotated_document · **CTA:** No CTA
**Publish guardrail:** none

### Week 13 — AI evaluation
**Banner headline:** One good answer is not an evaluation set.
**Supporting line:** Keep real questions and past failures as regression tests.
**Companion post:** Show a tiny example of a test set: input, expected behaviour, failure mode and release threshold.
**Visual direction:** test_case_card · **CTA:** No CTA
**Publish guardrail:** none

### Week 14 — Build note
**Banner headline:** The boring code can protect the whole business process.
**Supporting line:** Deduplication prevents the same lead or invoice from being processed twice.
**Companion post:** Describe idempotency in plain English, with a harmless example from an automation.
**Visual direction:** code_to_outcome · **CTA:** No CTA
**Publish guardrail:** none

### Week 15 — Outbound proof
**Banner headline:** The work after send is where outbound gets operational.
**Supporting line:** In the documented baseline: about 24,000 emails a month and a 4% reply rate.
**Companion post:** Only publish the numbers if send logs and reply definitions are verified. Explain reply routing and lead ownership—not just volume.
**Visual direction:** evidence_receipt · **CTA:** No CTA
**Publish guardrail:** VERIFY against actual send logs and exact reply-rate denominator before publishing; use 24,000/month baseline only if still accurate.

### Week 16 — Product strategy
**Banner headline:** A pilot isn’t a product yet.
**Supporting line:** Production adds permissions, support, cost controls and failure handling.
**Companion post:** Use a pilot-to-production checklist with one concrete example per category.
**Visual direction:** pilot_vs_production · **CTA:** No CTA
**Publish guardrail:** none

### Week 17 — Voice AI
**Banner headline:** If the call gets unusual, can the assistant recover?
**Supporting line:** Test interruptions, unclear requests, silence and requests for a person.
**Companion post:** Describe a voice-agent test plan and the exact handoff conditions you would require.
**Visual direction:** call_test_matrix · **CTA:** No CTA
**Publish guardrail:** none

### Week 18 — Founder perspective
**Banner headline:** I don’t want AI in every workflow.
**Supporting line:** I want fewer repetitive decisions and clearer ownership.
**Companion post:** Explain one kind of task you would not automate and why. Be specific about risk or low frequency.
**Visual direction:** founder_note · **CTA:** No CTA
**Publish guardrail:** none

### Week 19 — GTM engineering
**Banner headline:** A reply in a shared inbox is a handoff waiting to fail.
**Supporting line:** Classify it, assign it and make the next action visible.
**Companion post:** Show a simple reply-routing taxonomy: interested, objection, referral, unsubscribe, out of office and needs review.
**Visual direction:** routing_map · **CTA:** No CTA
**Publish guardrail:** none

### Week 20 — Trust / build terms
**Banner headline:** Your software should not depend on your consultant staying forever.
**Supporting line:** The repo, cloud account, credentials and runbook should be yours.
**Companion post:** Explain what a clean handover includes. Only promise terms that your contracts and actual process support.
**Visual direction:** ownership_checklist · **CTA:** Soft invitation
**Publish guardrail:** Publish only if contract and actual delivery process guarantee these ownership/handover terms.

### Week 21 — AI product strategy
**Banner headline:** Start with the task, not the model.
**Supporting line:** What decision gets easier? What work disappears? What new risk appears?
**Companion post:** Apply those three questions to one real use case, without turning the post into a tool comparison.
**Visual direction:** three_questions · **CTA:** No CTA
**Publish guardrail:** none

### Week 22 — Outbound systems
**Banner headline:** A reply rate alone won’t tell you whether outbound works.
**Supporting line:** Track qualified conversations and next steps—not only sends and opens.
**Companion post:** Show the measurement chain from delivered message to reply, qualified conversation, meeting and opportunity. Clearly mark estimates.
**Visual direction:** funnel_diagram · **CTA:** No CTA
**Publish guardrail:** none

### Week 23 — AI reliability
**Banner headline:** A confident answer with no source is a product problem.
**Supporting line:** Show the evidence—or say the system cannot verify it.
**Companion post:** Describe when source links, citations or a refusal are more useful than a fluent answer.
**Visual direction:** source_trace · **CTA:** No CTA
**Publish guardrail:** none

### Week 24 — Operations
**Banner headline:** Automation should remove a step, not add another dashboard.
**Supporting line:** If someone must copy the result by hand, close the loop.
**Companion post:** Pick one workflow and mark every manual handoff that remains after the proposed automation.
**Visual direction:** annotated_workflow · **CTA:** No CTA
**Publish guardrail:** none

### Week 25 — Marketplace / case study
**Banner headline:** A marketplace is more than a checkout page.
**Supporting line:** A partner build processed $85K in its first three months; payment edge cases mattered too.
**Companion post:** Use only with permission and accurate attribution to the partner agency. Explain one concrete payment or onboarding decision.
**Visual direction:** case_receipt · **CTA:** No CTA
**Publish guardrail:** Confirm partner permission, attribution and $85K / three-month figure before publishing.

### Week 26 — AI engineering
**Banner headline:** Every prompt change can break something that used to work.
**Supporting line:** Version prompts and rerun the failures you already know about.
**Companion post:** Explain a lightweight prompt regression process. Avoid suggesting that evaluation guarantees correctness.
**Visual direction:** version_diff · **CTA:** No CTA
**Publish guardrail:** none

### Week 27 — Operations
**Banner headline:** The useful part of an AI assistant is what happens after the answer.
**Supporting line:** Create the task, update the record or notify the right person.
**Companion post:** Show a simple end-to-end chain from request to action to confirmation and exception handling.
**Visual direction:** workflow_diagram · **CTA:** No CTA
**Publish guardrail:** none

### Week 28 — Product delivery
**Banner headline:** A green test suite doesn’t mean the feature is useful.
**Supporting line:** Test the real task, with messy inputs and the people who will use it.
**Companion post:** Contrast a technical pass with a user outcome; propose a small acceptance test.
**Visual direction:** two_column_comparison · **CTA:** No CTA
**Publish guardrail:** none

### Week 29 — AI case study
**Banner headline:** The latency fix wasn’t “use a bigger model.”
**Supporting line:** Routing, caching and evaluation can matter as much as the model choice.
**Companion post:** Use the Wiser-related experience only if disclosure is permitted; explain the mechanism and confirm every numeric result before adding it.
**Visual direction:** engineering_note · **CTA:** No CTA
**Publish guardrail:** Do not publish numerical Wiser outcomes unless supported by source documents and disclosure permission.

### Week 30 — Outbound systems
**Banner headline:** Personalization should be a fact, not a guess.
**Supporting line:** If you can’t point to the source, don’t put it in the email.
**Companion post:** Show how you would distinguish verified company facts from inferred or fabricated personalization.
**Visual direction:** good_bad_example · **CTA:** No CTA
**Publish guardrail:** none

### Week 31 — AI reliability
**Banner headline:** A failed tool call should not look like a successful answer.
**Supporting line:** Make failures visible, recover safely and give the human enough context.
**Companion post:** Describe status handling, retries, timeouts and the user-facing fallback.
**Visual direction:** system_state_diagram · **CTA:** No CTA
**Publish guardrail:** none

### Week 32 — Founder perspective
**Banner headline:** The stack is the easy part. Choosing what not to build is harder.
**Supporting line:** Scope one painful workflow before debating frameworks.
**Companion post:** Tell a short story about reducing scope or choosing a simpler solution. Use a real example.
**Visual direction:** founder_note · **CTA:** No CTA
**Publish guardrail:** none

### Week 33 — Product delivery
**Banner headline:** A prototype should answer one risky question.
**Supporting line:** Can this work with our data, our users and our constraints?
**Companion post:** Offer a three-question prototype brief: assumption, evidence, decision.
**Visual direction:** experiment_card · **CTA:** No CTA
**Publish guardrail:** none

### Week 34 — Operations
**Banner headline:** If an alert has no owner, it’s just another notification.
**Supporting line:** Every alert needs a next action, an escalation path and a runbook.
**Companion post:** Show a sample alert-to-resolution sequence, including what happens outside business hours.
**Visual direction:** incident_flow · **CTA:** No CTA
**Publish guardrail:** none

### Week 35 — AI reliability
**Banner headline:** The cheapest model can be expensive if it needs three retries.
**Supporting line:** Measure cost per successful task, not just cost per token.
**Companion post:** Explain the trade-off between model price, retries, latency and human review. Use measured costs only.
**Visual direction:** cost_breakdown · **CTA:** No CTA
**Publish guardrail:** none

### Week 36 — GTM / CRM
**Banner headline:** The fastest response is useless if it reaches the wrong person.
**Supporting line:** Routing and CRM hygiene are part of the product.
**Companion post:** Show the minimum fields and ownership rules needed to route an inbound or outbound reply.
**Visual direction:** crm_routing_map · **CTA:** No CTA
**Publish guardrail:** none

### Week 37 — AI product strategy
**Banner headline:** Human review isn’t the problem. Surprise review is.
**Supporting line:** Decide in advance which cases need a person.
**Companion post:** Define escalation triggers such as low confidence, sensitive data, high-value actions or contradictory sources.
**Visual direction:** decision_matrix · **CTA:** No CTA
**Publish guardrail:** none

### Week 38 — Build note
**Banner headline:** The first version should be small enough to learn from.
**Supporting line:** Keep the scope narrow; keep the acceptance criteria real.
**Companion post:** Explain what you would include—and explicitly exclude—from a first release for one use case.
**Visual direction:** scope_card · **CTA:** No CTA
**Publish guardrail:** none

### Week 39 — Operations
**Banner headline:** The hardest automation bugs live between systems.
**Supporting line:** A webhook fires twice. A record changes late. A reply arrives out of order.
**Companion post:** Use a real or clearly labelled illustrative sequence to explain deduplication, retries and reconciliation.
**Visual direction:** sequence_diagram · **CTA:** No CTA
**Publish guardrail:** none

### Week 40 — Founder perspective
**Banner headline:** After 15 years in product, I still start with the same question.
**Supporting line:** What is the user trying to get done—and what gets in the way?
**Companion post:** Personal reflection connecting product management to hands-on building. Avoid generic career inspiration.
**Visual direction:** founder_note · **CTA:** No CTA
**Publish guardrail:** none

### Week 41 — Voice AI
**Banner headline:** “Can I speak to a person?” is a core test case.
**Supporting line:** A good voice assistant makes the handoff easier, not awkward.
**Companion post:** Write the exact handoff behaviour you would test and what context must follow the caller.
**Visual direction:** conversation_snippet · **CTA:** No CTA
**Publish guardrail:** none

### Week 42 — RAG / knowledge
**Banner headline:** Your document assistant needs a plan for stale documents.
**Supporting line:** Show dates, source ownership and what happens when two documents disagree.
**Companion post:** Give readers a four-point document hygiene checklist before any RAG build.
**Visual direction:** document_checklist · **CTA:** No CTA
**Publish guardrail:** none

### Week 43 — Product delivery
**Banner headline:** A timeline is not a plan until the risks are visible.
**Supporting line:** Data access, integrations, permissions and ownership often decide the schedule.
**Companion post:** Share a scoping template that names assumptions, dependencies, unknowns and a first milestone.
**Visual direction:** project_map · **CTA:** No CTA
**Publish guardrail:** none

### Week 44 — Trust / delivery
**Banner headline:** Speed is not skipping the controls.
**Supporting line:** It is removing unnecessary handoffs while keeping checks that catch real failures.
**Companion post:** Explain the minimum release safeguards you believe every automation needs. Distinguish must-haves from context-dependent choices.
**Visual direction:** release_checklist · **CTA:** No CTA
**Publish guardrail:** none

### Week 45 — GTM engineering
**Banner headline:** Outbound needs an off switch.
**Supporting line:** Pause safely when deliverability drops or an integration starts misbehaving.
**Companion post:** Explain stop conditions and monitoring in a responsible outbound system; avoid presenting volume as the goal.
**Visual direction:** control_panel · **CTA:** No CTA
**Publish guardrail:** none

### Week 46 — Proof / product
**Banner headline:** A live demo beats a paragraph saying “production-ready.”
**Supporting line:** Try the multilingual CV optimizer with a real role and your own criteria.
**Companion post:** Show a short screen recording of the live tool, the input, the output and one limitation. Link to the demo in the post text.
**Visual direction:** annotated_screenshot · **CTA:** Demo link
**Publish guardrail:** Verify demo still works and show a real screen recording; do not overstate evaluation claims.

### Week 47 — Trust / handover
**Banner headline:** A good build should leave your team more capable.
**Supporting line:** Documentation, access and a clear runbook are part of delivery.
**Companion post:** Show what the handover checklist includes and what the client owns afterwards. Promise only what your engagement terms guarantee.
**Visual direction:** handover_checklist · **CTA:** Soft invitation
**Publish guardrail:** Publish only if contract and actual delivery process guarantee these ownership/handover terms.

### Week 48 — Offer
**Banner headline:** Bring me the task that lives in three tabs and one person’s head.
**Supporting line:** We’ll map the workflow and decide whether automation is worth the complexity.
**Companion post:** Describe the 30-minute session: map current state, identify risks, decide whether to prototype. Avoid implying a guaranteed build plan for every case.
**Visual direction:** simple_offer_card · **CTA:** Book session
**Publish guardrail:** Use this CTA only if the 30-minute session and described process are currently offered.

### Week 49 — Offer / qualification
**Banner headline:** Before hiring for an AI project, define the result you’re buying.
**Supporting line:** A job title and a tech stack are not a business case.
**Companion post:** Give a short brief template: user, problem, current cost, desired change, constraints and success measure.
**Visual direction:** brief_template · **CTA:** Soft invitation
**Publish guardrail:** none

### Week 50 — Offer / wrap-up
**Banner headline:** No AI pitch deck. One real workflow.
**Supporting line:** Bring a repetitive task; leave with a clearer decision on what to build—or not build.
**Companion post:** End the series by explaining how ProdCraft scopes a small first step and when you would advise a client not to automate.
**Visual direction:** simple_offer_card · **CTA:** Book session
**Publish guardrail:** Use this CTA only if the 30-minute session and described process are currently offered.

## 6. A measurable “10× better” process (not a promise of 10× reach)

Score every draft from 0–5 on six criteria: (1) one identifiable reader, (2) one specific situation, (3) a clear point of view, (4) a useful lesson/test/checklist, (5) natural voice, (6) visual clarity. Maximum 30. Publish only at **24/30 or higher** and only if the proof/claims gate passes. Any unsupported numeric claim is an automatic fail regardless of score.

Track per post: impressions, members reached if available, reactions, substantive comments, reposts, profile views, new relevant followers, link clicks with UTM tags, qualified DMs and booked calls. Calculate per 1,000 impressions where possible. Review in 4-week blocks; change one variable at a time (hook, creative family, caption angle or CTA). Compare medians, not just one viral post. The objective is better qualified attention, not just likes.

Recommended mix: 60–70% practical thinking/teardowns, 15–20% build notes and proof, 10–15% founder point of view, and no more than 10% direct offer. Keep the content relevant to founders, product/operations leaders and sales/revenue operators; make each post speak to only one of them.

LinkedIn’s 2026 guidance says it is reducing repetitive, generic and engagement-bait content and taking action on engagement pods and automated comments. Do not use engagement pods or automated commenting. Earn discussion with specific observations and respond personally. Source: https://news.linkedin.com/2026/ImprovingTheFeed and https://news.linkedin.com/2026/keeping-conversations-real-on-linkedin

## 7. Claude Code implementation brief

Use `prodcraft_50_week_messages.json` as the source of truth for copy. Render each week with a varied creative family; do not rewrite, embellish or invent claims. Requirements:
- Generate PNGs at 1080×1350, with a smaller wordmark and generous mobile-safe margins.
- Use six to eight different layouts and repeat each layout no more than twice consecutively.
- Put only the headline, supporting line, and necessary visual evidence on the image. Keep URL/CTA in the caption unless that week is explicitly marked as an offer or demo.
- Add a validation script that rejects unsupported numeric claims, checks text overflow and enforces the six-part 30-point review score.
- Keep a claim registry with status, source, date range, denominator, disclosure permission and exact approved phrasing. When a metric is not approved, choose a non-numeric fallback message.
- Export: numbered PNG, editable source data, suggested caption angle, proof checklist and a preview/contact sheet. Do not publish automatically.

**North star:** a reader should think “this person has seen the problem up close and has a useful point of view,” not “another AI consultant is advertising.”