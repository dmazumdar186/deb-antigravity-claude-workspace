# Legal review: GreenJobs Proposal v1.0 (30 September 2026)

Reviewer lens: senior commercial counsel acting for Debanjan Mazumdar / ProdCraft. Document reviewed: `GreenJobs_Proposal_v1.0_2026-09-30.docx`. Source of every fact: the workspace record only (`.tmp/keith_factsheet.md`, `deliverables/greenjobs_redesign_2026-09-22/proposal/keith_costing_brief_2026-09-28.md`, `HANDOFF.md`, `KEITH_CHANGES_CHECKLIST.md`, `src/data/brief.md`). Nothing below is invented; where the record is silent it says so.

## 1. Verdict

Send-ready **after the nine bracketed items in section 4 are filled in**. As drafted the document is internally consistent (every figure reconciles), the scope is bounded, the guarantees are conditioned, liability is capped, and the data-protection role split is stated. It is not yet signable because the contracting entities are not identified and the DPA annex is missing.

## 2. What the document commits ProdCraft to (read this before signing)

| Commitment | Where | Exposure | Mitigation in the text |
|---|---|---|---|
| Front end live on both domains within 15 working days or Milestone 1 (€2,750) waived | §06, Terms cl. 3(a) | €2,750 | Clock pauses while client inputs 5 to 10 are late; DNS-provider and Strategies delays excluded |
| Milestone 4 (€1,300) not charged if a confirmed posting route fails acceptance | Terms cl. 3(b) | €1,300 | Applies only to routes the Client has confirmed in writing; M2 + M3 (€5,200) stay payable |
| 99.9% uptime with 10% credit per 0.1% shortfall | §05 | Up to 100% of one month's fee (€450 or €650) | Capped; sole remedy; third-party and client-caused outages excluded; Cloudflare credits do not flow through (stated in the costing brief §8, reflected as ProdCraft's own margin) |
| 4-hour response to a posting outage, 1 business day otherwise | §05, §04 | Reputational; no penalty attached | Response, not resolution, is what is promised |
| Quarterly restore drill with written result | §05 | Time | None needed |
| Free full data export within 10 working days, on request, at any time | §05, cl. 6 | Time | Standard formats only |
| 30-day defect correction after acceptance | cl. 10 | Time | Limited to defects, not new requests |
| Liability capped at 12 months' fees | cl. 11 | Max ≈ €13,275 in year 1 | Mutual; carve-outs only where law requires |

Total fee at risk under the guarantees if everything goes wrong: **€4,050** (M1 + M4). The migration build itself (€5,200) is protected.

## 3. Numbers reconciled against the record

| Figure in the proposal | Source in the record | Match |
|---|---|---|
| €2,750 front end (both editions + polish list) | costing brief §2 Line 1 and §8 line C | yes |
| €6,500 migration, split 40/40/20 = 2,600 / 2,600 / 1,300 | §8 line B (€6,500); §2 Line 2 (40/40/20) | yes; the split percentages were only ever stated for the €7,500 version, applied here to €6,500 |
| €450 Care / €650 Grow per month | §8 line A | yes |
| €1,375 bundle credit for 12-month commitment | §8 line C ("waive C's second half") | yes |
| Year 1 €13,275; year 2+ €5,400 | §8 | yes (7,875 + 5,400 = 13,275) |
| Year 1 Grow €15,675; year 2+ Grow €7,800 | derived: 7,875 + 12×650; 12×650 | arithmetic checked |
| €13,000 to €17,000 estimated spend today | §1 "derived" | yes, labelled as an estimate in three places |
| gaiatalent.com add-on €1,200 bundled / €1,500 standalone | §2 Line 1 | yes |
| 10% annual prepay discount; 3-month minimum; rolling monthly | §2 Line 3 | yes |
| 30-day parallel run; daily test job; no cut-over until acceptance | §8 guarantee table | yes |
| 99.9%, 10% credit per 0.1%, daily backups, quarterly restore, 4 h posting outage, 1 business day | §8 guarantee table | yes; the 100%-of-fee cap and the exclusions are additions by this review |
| 114 requests, 100 done, 11 need Keith | §7 addendum; requirements_matrix_v2 | yes |
| 195 pages, 165 roles, 3,047 checks, 76.9 KB CSS, 107.5 KB JS | HANDOFF.md | yes |
| Salary disclosure 33% IE (29/88), 57% UK (56/98) | summary.md / brief §11 | yes |
| Strategies from £899 ≈ €1,030; 8 to 12 weeks | costing brief §1 | yes |
| €85 per hour change rate | **not in the record**: set by this draft as a default | operator to confirm or change |
| Proposal validity 31 October 2026; signature assumption 6 October 2026; dates in the timeline | PM assumptions in this draft | shift day for day, stated in the text |

Removed on purpose: the €1,875 figure appears only inside clause 2 to state that it is superseded. The €250 "Care until Line 2 ships" figure from costing brief §2 is **not** used; §8 replaced it with €450 carrying the full SLA, and the timeline starts hosting at Phase 1 go-live.

## 4. Must be completed before sending (bracketed in the document)

1. ProdCraft legal form, registered address and registration number (cl. 1). The record does not say whether ProdCraft is a French micro-entreprise, SAS or other.
2. ProdCraft VAT status and number (§06 payment terms). Cross-border B2B services from France to Ireland are normally reverse-charged; confirm with your accountant and state it.
3. The Client's contracting entity: Gaia Talent Ltd (CRO 615983) or GreenJobs Ltd (Ennis). The public GreenJobs sites never name Keith or Gaia Talent as owner; the record only has the operator's statement. Ask Keith which entity signs and pays.
4. Keith's email address (cover, signature block, cl. 15). Not in the record.
5. Annex A, the Article 28 data processing agreement (cl. 8). Not drafted; use the EU standard contractual clauses for controller-to-processor or a short bespoke DPA. Without it the GDPR clause is a promise to attach, not a DPA.
6. Governing law: Ireland is chosen because the Client, the domains and the services are Irish. If you prefer French law and courts, change cl. 16.
7. The hourly change rate (€85) in cl. 4.
8. Which multiposting routes are "confirmed in use" must be recorded in writing at kick-off (client input 2), because the Milestone 4 guarantee turns on it.
9. Strategies contract terms (client input 1). Until known, the cut-over date and the notice date in the timeline are assumptions.

## 5. Risks flagged and how the draft handles them

- **Scope creep from the polish document.** Handled: only front-end items are in Phase 1; anything needing accounts or posting is in Phase 2; the 8 other network sites, Stripe billing and content writing are named out of scope.
- **SEO dip after migration.** Stated in cl. 10 (4 to 8 weeks normal) with the redirect map as the mitigation; rankings are expressly not warranted.
- **Broadbean onboarding on Broadbean's timeline.** Stated in the Timeline dependencies and cl. 12; cut-over waits rather than going live without a route.
- **Single-operator continuity.** Conceded openly in cl. 13 with the mitigations the record already lists (client-owned accounts, repo access, runbook).
- **EU data residency.** Preference only unless the paid Cloudflare add-on is bought; stated twice (§05 and out of scope).
- **Logos, testimonials and marks.** Client warrants the rights (cl. 7) and supplies permissions (client input 8); the demo currently shows 112 logos on a non-GreenJobs domain before written approval, which is why launch is conditioned on input 8.
- **E-signature.** Cl. 17 allows typed-name plus drawn signature and counterparts. Under Irish law (Electronic Commerce Act 2000) and eIDAS a simple electronic signature is admissible; for a contract of this size it is adequate.
- **Late payment.** Statutory interest under the Irish implementation of the Late Payment Directive; no need to state a rate.
- **Currency.** All EUR. Strategies bills in GBP; the proposal states the £899 figure only as context.

## 6. What the record does not settle (do not assert these to Keith)

- Whether the Gaia Talent redesign URL was ever sent to Keith; the proposal lists it as "demonstrated" only under Related Systems and as an add-on. If it was never sent, change "demonstrated" to "built".
- Gaia's CRM: Recruit CRM (call of 10 September) versus Vincere (gaiatalent.com privacy policy). The proposal says "to be confirmed".
- Whether the 28 September DM reply and the 29 September email reply were actually sent. The proposal does not depend on either.
- Keith's Finance Manager's name and the outcome of the "Wednesday" conversation.
- Whether Diana Lupu (Finance Administrator on the team page) is the Finance Manager.

## 7. Things this proposal deliberately does not contain

- No price or terms for the sourcing engagement (Gaia Radar, Shortlist Check). Nothing was ever quoted or invoiced for it; it is mentioned as related work only, at no fee.
- No non-compete or non-solicit (cl. 14 says so, to pre-empt the question).
- No automatic renewal of a fixed term; hosting is rolling monthly after three months, which is the "no lock-in" position taken in every message to Keith.
