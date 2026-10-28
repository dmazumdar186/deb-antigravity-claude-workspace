# Legal review: ASSET Voyages proposal v1.0 (28 October 2026)

Internal, for Debanjan only. Reviews `ProdCraft_ASSET_Voyages_Proposal_v1.0_2026-10-28.docx` (built from `execution/gtm_client_workflows/proposal_system/proposals/asset-voyages-v1.json`). Sources: `03_Functional_Breakdown.md` (§Z2 and tables), `02_Panel_Debate.md` (Common ground), `research/infra_costs_2026.md`. This memo is a self-review, not legal advice.

## 1. Commitments made in the proposal

| # | Commitment | Section | Binding? | Measured by | Note |
|---|---|---|---|---|---|
| 1 | Deliver L0, L1, L2 to T01-T15 acceptance for €4,000 HT | 05, 06 | Yes (fixed price) | Acceptance report | Copy supplied by ASSET; 2 revision rounds per milestone |
| 2 | Up to 20 French content pages + 3 legal pages; up to 300 congress listings imported | 05 | Yes (cap) | Page and import count | Beyond cap = change request |
| 3 | No production work or DNS change without written authorisation | 05, 08 | Yes | Go email | |
| 4 | Planned launch Tue 9 Feb 2027; contractual latest launch Fri 12 Mar 2027 | 05 | Yes (latest date) | Calendar | Dates move day for day with late ASSET inputs or approvals over 3 working days |
| 5 | Payment 30/30/20/20 against accepted milestones | 06 | Yes | Invoices | |
| 6 | Monthly plan €600 HT, all tools paid by ProdCraft | 06 | Yes | Invoices | Tool cost risk sits with ProdCraft (expected €5-15, up to ≈ €30) |
| 7 | 12-month minimum term; remaining months due on early exit | 06, 08 | Yes | Contract | Must be in the contract body, not only the proposal |
| 8 | 99.5% monthly availability target; 5-minute external probe; no 100% guarantee | 06 | Target + credit | UptimeRobot | Credit 10% of month, cap one month a year |
| 9 | RPO 24 h / RTO 8 business hours; quarterly timed restore drill | 06 | Target | Drill log | Drill never yet run on this stack |
| 10 | Acknowledgement: outage or failed form 4 business hours; other 1 business day; Mon-Fri 9-18 Paris | 06, 08 | Yes | Ticket timestamps | No on-call |
| 11 | Up to 5 h/month of changes, done within 2 business days; no rollover | 06 | Yes | Change log | |
| 12 | Critical security patches within 2 business days of release | 06 | Yes | Patch log | |
| 13 | Lab speed targets per template (LCP ≤ 2.5 s, INP ≤ 200 ms, CLS ≤ 0.1), reported monthly | 04, 06 | Report, not guarantee of field data | Lighthouse | |
| 14 | Change requests at €70/h HT; written quote above one day; four-way impact assessment | 06, 08 | Yes | Signed change request | |
| 15 | All accounts in ASSET's name; code, data, design owned by ASSET; billing transfers at exit | 03, 06, 08 | Yes | Account register | |
| 16 | ProdCraft acts as processor; DPA annexed | 04, 08 | Yes | Signed DPA | DPA template not drafted yet |
| 17 | GM&E codes never exposed publicly; leak scan before each release | 03, 05 (T05) | Yes | Scanner report | Scanner not built yet |
| 18 | Prices valid 60 days | 06 | Yes | | Expires 27 December 2026 |

## 2. EUR reconciliation (every figure in the DOCX)

| Figure | Where in proposal | Calculation / source |
|---|---|---|
| €0 | L0 row, licences row, dependency costs | L0 included (Common ground §1); free tiers per `infra_costs_2026.md` |
| €2,500 | L1 | Common ground §1 |
| €1,500 | L2; L4 option | Common ground §1 (both) |
| €4,000 | Core total | 0 + 2,500 + 1,500 |
| €800 | Core VAT; 20% J4; 20% launch | 4,000 × 20%; 4,000 × 20% (×2) |
| €4,800 | Core incl. VAT | 4,000 + 800 |
| €1,200 | 30% J0; 30% J2; L3b option | 4,000 × 30% (×2); Common ground §1 options |
| Payment check | | 1,200 + 1,200 + 800 + 800 = 4,000 ✓ |
| €750 / €150 / €900 | English option | Common ground §1; × 20%; sum |
| €500 / €100 / €600 | CRM option | Common ground §1; § F; × 20%; sum |
| €400 / €80 / €480 | L3a option | Common ground §1; × 20%; sum |
| €1,200 / €240 / €1,440 | L3b option | Common ground §1; × 20%; sum |
| €1,500 / €300 / €1,800 | L4 option | Common ground §1; × 20%; sum |
| €600 / €120 / €720 | Monthly plan | Common ground §2; × 20%; sum |
| €21,600 / €25,920 | 36 months plan | 36 × 600; × 1.2 |
| €25,600 / €30,720 | Three-year total | 4,000 + 21,600; 4,800 + 25,920 (= Common ground §1) |
| €7,200 / €8,640 | Annual recurring | 12 × 600; × 1.2 (Common ground §1) |
| €70 | Change-request rate (§06, §08) | Common ground §1; Functional Breakdown A7 |
| €1,100 | Directus alternative set-up | P9: ≈ 16 h × €70 = €1,120, rounded |
| €10-30 | Directus extra hosting/month | P9; `infra_costs_2026.md` VPS + Postgres range |
| €5-15 | Tool cost/month inside the plan | P8; `infra_costs_2026.md` "Total monthly tool cost" |
| $5 (≈ €4.3) | Workers Paid | P8 (infra file says ≈ €4.5; FX rounding, immaterial) |
| €7-9 | Brevo Starter if cap reached | `infra_costs_2026.md` line 17 |

No figure in the DOCX lacks a source. No figure was changed from the fixed prices (€4,000 build, €600/month).

## 3. Bracketed items and open inputs

- `[` placeholders remaining in the `.md`: **none**.
- Client signatory shown as "Authorised signatory, ASSET Voyages Management" (no name given in the RFP); fill by hand at signature.
- Veena Khatri, Office Manager Assistant: verified from her email signature (operator confirmation).
- Site research (`research/facts.md`) does not exist; §01-§02 now rest only on the RFP's own statements. No claim about the current site is made.
- Response form (`form.txt`, Z2 item 28) does not exist in the deliverables folder; not filled.

## 4. Risks

1. **Economics (high).** Effective rate ≈ €14/h on the build and ≈ €40/h over three years (Common ground §1). Viable only if the 12-month term holds; the term and early-exit clause must appear in the signed contract.
2. **Tool cost borne by ProdCraft (low-medium).** Plan includes all tools; Brevo cap bursts, UptimeRobot paid SMS or L4 AI usage could push cost to ≈ €30/month. No cap is stated to the client.
3. **Single supplier (medium).** No named holiday/sickness cover; continuity rests on repository, runbook and open stack. Disclosed in Known limitations.
4. **Unbuilt tooling (medium).** Leak scanner, crawl-to-redirect tool, Lighthouse/axe gates, backup cron and restore drill don't exist yet but are promised (T05, T10-T13, plan). Build before J3.
5. **Contractual latest launch (medium).** 12 March 2027 is a hard date; it is protected only by the "day for day" delay clause. Keep written records of late ASSET inputs.
6. **Data protection (medium).** DPA template not drafted; CNIL 3-year prospect retention cited from memory (verify); Cloudflare EU jurisdiction and Brevo hosting location marked UNVERIFIED in research.
7. **Service credit (low).** 10% credit capped at one month a year; Cloudflare offers no SLA on the plans used, so platform outages are excluded only as "third-party host failures". Exclusion wording must match the contract.
8. **References (low).** Only Jitendra is labelled client work. Jeevana is labelled concept (no record of it being a commissioned project); correct if it was paid client work. No travel/MICE reference.
9. **AI disclosure (low).** AI-assisted engineering disclosed; L4 human approval stated.
10. **Validity.** Prices valid to 27 December 2026; the go-ahead date of 16 November drives every date.
