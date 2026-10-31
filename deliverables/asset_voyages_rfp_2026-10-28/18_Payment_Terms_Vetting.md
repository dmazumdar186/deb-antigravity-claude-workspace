# 18 — Payment terms vetting (point 6 of the 31 Oct reply)

Sources: `01c_Reply_to_clarifications_2026-10-31.md` (point 6), RFP §7 milestones J0–J6 and "payments negotiated against accepted milestones; balance depends on acceptance", §8, panel lenses 5 (Hormozi) and 6 (Saraev), `02_Panel_Debate.md` Common ground §1 (30/30/20/20 schedule, now **superseded** by the 50/50 rule).

**Conflict to resolve in the proposal:** Common ground says "Accounts, code and data stay ASSET's throughout: no technical lock-in." Keep that promise for *data and accounts ASSET already owns*; the **new build** (code, design, deploy rights) transfers on full payment. Say so precisely, or a hostile client cites our own words.

## 1. Hormozi lens (offer, risk reversal)

- The draft reads as policy, which is good ("same on every ProdCraft project" = confidence, not suspicion of ASSET). Keep it; never justify it with past bad clients.
- Missing: what the deposit *buys*. A high-ticket buyer pays 50% without flinching when the deposit reserves capacity and starts a dated plan. Name it: "reserves the build slot and starts the audit".
- Risk reversal must run both ways: we commit to a dated schedule and fix every defect against T01–T15 at no cost; the commitment holds **as long as ASSET's inputs arrive on the agreed dates**. That is the conditional guarantee.
- "What happens if either side is late" is good: symmetric, signals fairness, hides the mechanics.

## 2. Saraev lens (boundaries)

- Human decision: one only — ASSET's written acceptance (or written defect list) at J5. Everything else is documented/automatic: invoice dates, deemed acceptance after the window, go-live trigger = cleared funds.
- Error channel for late payment: automatic reminder at D+1, formal notice at D+8, suspension of work/hosting at D+15, each in the contract. No ad-hoc chasing by the founder.
- Template: the email paragraph below is client-agnostic except "T01 to T15" and "J0/J5"; swap those two tokens per client.

## 3. RFP and French-law compatibility

- RFP asks for milestone payments and an acceptance-dependent balance. 50/50 **is** milestone-based: 50% at **J0 (signature/kickoff)**, 50% at **J5 acceptance, before cutover**. J6 stabilisation is covered by the build fee (no third invoice), so the "balance on acceptance and outstanding items" clause is respected: minor outstanding items go in a J6 list, they do not hold back the balance.
- Reader risk: a French buyer may balk at "go-live only after payment" if it reads as hostage-taking. Phrase it as the cutover condition RFP already sets: "cutover follows written authorisation from ASSET management and settlement of the acceptance invoice".
- Private buyer (ASSET is a company, not a public body): no Code de la commande publique avance cap applies. B2B: payment term max 60 days from invoice (L441-10 I C. com.); we set 7 days, which is lawful by agreement. Late penalties are mandatory on invoices: rate ≥ 3× legal interest rate (default: ECB rate + 10 points) plus **indemnité forfaitaire pour frais de recouvrement 40 €** (L441-10 II and D441-5 C. com.). **Vérifier** current article numbering with the comptable before signature.
- Avoid: "non-refundable" in French consumer sense is fine B2B, but word it as "acquis, il rémunère les travaux engagés" rather than "penalty".

## 4. MECE guardrail table

E = email (principle only), P = proposal, C = contract/CGV.

| # | Phase | Failure path | Guardrail | Where |
|---|---|---|---|---|
| A1 | Before start | Signs, delays deposit, expects work to start | No work, no slot reserved, until deposit funds cleared; dates run from receipt | E (principle), P |
| A2 | Before start | Claims deposit covers more than the written scope | Price tied to annexed scope + T01–T15; anything else is a change request | E, P, C |
| A3 | Before start | Negotiates 30/70 or "balance after launch" | Standard terms, not negotiated; flex only on price of scope, never on schedule | P |
| B1 | During build | Late inputs (content, CSV, approvals) stretch project while deposit is spent | Schedule shifts day-for-day; input > 10 working days late = project paused, restart slot on next availability, restart fee; > 30 days = J5 invoice for work done becomes due | E ("either side late"), P, C |
| B2 | During build | Scope creep before acceptance | Written change request, quoted, accepted and paid before work starts; never folded into T-tests | E, P, C |
| B3 | During build | New decision-maker reopens approved milestones | Written milestone approvals are final; reopening = change request | P, C |
| B4 | During build | Stalls milestone approvals (J1–J4) | Deemed approved after 5 working days without written comments | P, C |
| B5 | During build | Takes the staging build/repo and walks | ASSET-owned org/accounts for its data; ProdCraft holds admin/deploy rights and the IP of new code/design until full payment; licence of use granted on full payment | P (one line), C |
| B6 | During build | Terminates mid-project | Deposit acquired; work done beyond 50% billed at hourly rate; no licence to the build without settlement | C |
| C1 | Acceptance | Never confirms acceptance | Deemed acceptance after 5 working days on staging with no written defect list | P, C |
| C2 | Acceptance | "One more fix" loops | Defects only against T01–T15; one correction round per defect list; non-T items = J6 list or change request | P, C |
| C3 | Acceptance | Refuses or redefines T-tests | T01–T15 frozen in the annex at signature; changes = change request | P, C |
| C4 | Acceptance | Disputes whole invoice over a minor item | Disputes limited to blocking items in the acceptance report; minor items go to J6 list, balance stays due | P, C |
| C5 | Acceptance | Demands go-live before paying | Cutover on cleared funds + written authorisation (RFP's own condition) | E, P, C |
| D1 | After go-live | Goes live elsewhere with our design/code | IP transfers on full payment only; unpaid use = infringement, licence fee | C |
| D2 | After go-live | Stops paying maintenance | Monthly in advance; unpaid at D+15 = service suspended; minimum-term remainder due | P, C |
| D3 | After go-live | Treats J6 as open-ended free work | J6 = fixed window (e.g. 30 days) for T-defects only | P |
| E1 | Commercial-legal | Late payment / "processing" delays | Due 7 days from invoice; L441-10 penalties + 40 € indemnity; reminders D+1, notice D+8, suspension D+15 | C (invoice mentions) |
| E2 | Commercial-legal | Partial payment then dispute | Payment applied to oldest invoice; no licence/cutover until 100% cleared | C |
| E3 | Commercial-legal | Bank fees, FX, VAT deductions | Euros HT + VAT 20%; SEPA transfer, all bank fees borne by payer; net amount must equal invoice | P, C |
| E4 | Commercial-legal | Chargeback (card) | Bank transfer only for build invoices; no card | C |
| E5 | Commercial-legal | Insolvency | Reservation of IP until full payment (clause de réserve de propriété on deliverables); deposit covers exposure to J5 | C |
| E6 | Commercial-legal | Jurisdiction games | French law, Tribunal de commerce de Paris (or founder's seat); written notices by email with receipt | C |

## 5a. FINAL point 6 (email, 196 words)

**6. Fixed price, payment milestones, maintenance costs and rates for future changes**
Yes. The proposal will give a fixed price for the core scope (audit, core site, congress catalogue), tied to a written scope so the price holds; the monthly maintenance plan with its contents and measured commitments; and an hourly rate with a simple change procedure for anything outside the scope.
Payment follows two of your milestones, as on every ProdCraft project: 50% at J0, on signature, which reserves the build slot and starts the audit; and 50% at J5, on acceptance, before cutover. Acceptance means the tests in your brief (T01 to T15) pass on the staging site and ASSET confirms it in writing; the site then goes live on your domain once that payment is settled, together with management's authorisation. Stabilisation (J6) is included. Maintenance is invoiced at the start of each month.
In return, we commit to a dated schedule and correct anything that fails a test at no cost. The proposal sets out the acceptance procedure and what happens if either side runs late, so there are no surprises in either direction.
I would rather not put figures in an email ahead of the proposal: a price only means something next to the scope it covers, and several of your 30 answers change that scope. The proposal follows within 24 to 48 working hours of your answers, or by 10 November on the stated assumptions if the answers come later.

(Last paragraph is unchanged from the draft; the new text proper is 160 words.)

## 5b. Proposal "Payment terms" block

1. 50% of the build fee at J0 (signature), due on receipt; work and dates start when funds clear. This instalment is acquired and pays for work undertaken.
2. 50% at J5 acceptance: T01–T15 pass on staging and ASSET confirms in writing, or no written defect list within 5 working days (deemed acceptance). Cutover follows cleared payment and management's written authorisation; J6 stabilisation is included.
3. Milestone approvals J1–J4 in writing within 5 working days; inputs late by more than 10 working days pause the project and move the schedule.
4. Changes are quoted in writing and paid before work starts; the maintenance plan is invoiced monthly in advance.
5. Invoices in euros HT + VAT, payable by SEPA transfer within 7 days, bank fees borne by the payer; late payment incurs the penalties and 40 € recovery indemnity of art. L441-10 Code de commerce. Rights to the new code and design transfer to ASSET on full payment.

## 5c. Standing rule (workspace memory)

**Payment rule (operator, 2026-10-31):** every ProdCraft project is 50% of the agreed fee on signature (work starts on cleared funds; acquired, pays for work done) and 50% on complete delivery, defined as written acceptance against a frozen test list or deemed acceptance after 5 working days with no written defect list; go-live, IP transfer and admin/deploy hand-over happen only after the balance clears. Assume worst-case client behaviour: every failure path (late inputs, approval stalls, fix loops, scope creep, partial payment, walk-away, insolvency) has a written consequence in the contract. Emails state the principle warmly and firmly; mechanics live in the proposal and contract. Template and guardrail table: `deliverables/asset_voyages_rfp_2026-10-28/18_Payment_Terms_Vetting.md`.
