# Proposal carryover: must-do items for the priced proposal (28 Oct 2026)

Source: `14_Audit_Round3_11_Lenses.md`, Part D, fixes 4–5. These were not applied to the pages; the priced proposal must carry them.

| # | Must do in the proposal | Why | Source |
|---|---|---|---|
| 1 | The optional maintenance plan states **support response times and resolution times** (per severity, within the support hours of Q30), not only the restore aim. | Brief p7 asks for "response and resolution times"; Q30 gives only a restore aim. | `14_` fix 4 |
| 2 | The proposal (and its JSON) says **one workshop of up to 2 hours** for L0, matching the page (§07, J1). Remove the "2 workshops × 1.5 h" wording from `03_Functional_Breakdown.md` L0.8 before it feeds the proposal. | The page is what ASSET will hold us to; `03_` L0.8 still says 2 × 1.5 h. | `14_` fix 5 |
| 3 | Name the project lead and give the **effort by role** (now promised in §09). | §09 now says both come with the proposal. | `15_` fix 4 |
| 4 | Restate the GM&E visibility rule in the role/access section: only Veena and management see GM&E fare codes and evidence; the backup editor cannot (Q28 default; acceptance test T05). | T05 needs a defined set of authorised roles. | `15_` fix 1 |
- Proposal draft (asset-voyages-v1.json, timeline ~line 198) still assumes go-ahead Mon 16 Nov 2026: re-base all dates on 'start within 5 working days of the signed proposal' before pricing (verification 17_, 2026-10-28).
- Payment terms are 50% at J0 (signature) / 50% at J5 (acceptance, before cutover): replace the 30/30/20/20 table in asset-voyages-v1.json; add the guardrail clauses from 18_Payment_Terms_Vetting.md (deemed acceptance 5 working days; rights + admin/deploy pass on cleared final payment; pause/restart on late inputs; changes paid first; L441-10 late penalties; monthly plan suspension). Narrow "accounts, code and data stay ASSET's throughout" to existing accounts/data only (2026-10-31).
- Promised in the 31 Oct reply: one-page prototype table (included / optional / illustration only); congress spreadsheet template + dry-run validation; fixed list of editable section types; transfer package contents and duration of transfer assistance.
- Asked in the 31 Oct reply (optional, after delivery, no bearing on price): a discreet "Site by ProdCraft" footer credit, and a LinkedIn post by ASSET mentioning Debanjan Mazumdar and ProdCraft once live. Put both in the proposal as an optional clause the client can strike, never as a condition.
