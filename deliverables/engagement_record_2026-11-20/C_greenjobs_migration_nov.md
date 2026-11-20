# C. GreenJobs migration off Strategies: factual record, Nov 2026

Internal. Built 2026-11-20 from repo sources only. `G/` = `deliverables/greenjobs_migration_2026-11-06/`; `T/` = `deliverables/titre_sejour_entrepreneur_2026-11-10/`. Nothing inferred without an UNCERTAIN mark. The repo holds no mailbox; "SENT" means a repo source says so.

## 1. Timeline

| Date | Who → who | What | Source | Sent? |
|---|---|---|---|---|
| undated (before 29 Oct) | Keith → Deb (LinkedIn) | Blocker is "the initial investment of 1500. It may be Q1 next year before the budget is there for it." | `G/keith_linkedin_thread_2026-11-06.txt:3` | n/a |
| undated (before 29 Oct) | Deb → Keith (LinkedIn) | Offer: €600/month starting now, €1,500 in Q1, written into the contract; start "as early as November 1st week" | thread:4-5 | SENT (in pasted thread) |
| 29 Oct | Keith → Deb | "yes it should be doable. Let me talk with Strategies…" | thread:6 | n/a |
| "Thursday" (UNCERTAIN, likely 5 Nov) | Deb → Keith | "Did you happen to hear back?" | thread:7 | SENT |
| undated | Keith → Deb | "waiting to get final details to push ahead with the transfer" | thread:8 | n/a |
| before 6 Nov (date UNCERTAIN) | Strategies → Keith | 30-day notice; contract ends **6 Dec 2026**, billed to end; export via "Download Reports" CSV; DNS not managed by Strategies; temporary URLs charged | thread:10-13 | n/a (we never wrote to Strategies; no record of any direct contact) |
| 6 Nov | Keith → Deb | Forwards Strategies note; has "informed we will be changing contracts"; "let me know what you need" | thread:9 | n/a |
| 6 Nov | Deb → Keith; Keith → Deb | Deb promises reply over weekend; Keith: "Perfect Deb." | thread:14-15 | SENT |
| 9 Nov (Mon) | Deb → Keith (email + PDF plan) | `G/EMAIL_TO_KEITH.txt` + `G/transition_plan.html` / PDF | Sent status: commit 167b73c (REVIEW v1 l.12 "On 9 Nov the email told Keith…"); lesson `.claude/brain/lessons/2026-11-16-sending-payment-terms-invoice-client-check.md:14` | SENT (per those sources) |
| 9 Nov | Deb → Keith (LinkedIn nudge) | `G/LINKEDIN_TO_KEITH.txt` | no record | UNCERTAIN |
| 10 Nov | Rashieda → us | Answers to the 12 questions | `G/REVIEW_2026-11-16_keith_answers.md:6` | n/a (channel UNCERTAIN) |
| 11 Nov | Diana → us | Answers; went to `dmazumdar@teamprodcraft.com`, "five working days were lost" | REVIEW:5,35 | n/a |
| 16 Nov | Keith → us | Forwards Diana's 11 Nov email | REVIEW:5 | n/a |
| 16 Nov 16:42 | UNCERTAIN sender (reads as ours) | Email asking for Q1, 2, 7, 12, already answered | REVIEW:35; 167b73c REVIEW v1 §2 item 4 | UNCERTAIN |
| 16-19 Nov | us → Diana/Keith (UNCERTAIN) | An outbound message asking for export header rows, the applications inbox, "don't change any domain settings", DNS logins via password manager, Broadbean use. Diana's 19 Nov reply quotes these asks; the text is not in the repo | `G/replies_2026-11-20/SOURCE_diana_2026-11-19.txt:3,7` | Implied SENT; text, date, sender UNCERTAIN |
| 18 or 19 Nov | operator ↔ lawyer | Planned call; legal question "parked" until then | REVIEW:3,97 | Outcome NOT recorded anywhere in the repo |
| 19 Nov (3 emails, cc Rashieda, Keith) | Diana → Deb | Header rows (IE/UK xlsx); registrars (Hosting Ireland .ie; Lets Host .co.uk; 123 Reg for 8 sector domains); "I can login to all"; applications: "not sure what you mean - rashieda.ely… main person diana…"; "I wont do any change"; no Broadbean; 15:17 "Gaia talent is posting jobs by themself - manually"; 16:39 "share the DNS logins through a password manager? How will I do this?" | SOURCE_diana:3,5,7 | n/a |
| 20 Nov | Deb → Diana | `DRAFT_reply_to_diana.txt` (v1, superseded) and `DRAFT_reply_to_diana_v2_async.txt` (passed gate 4/4 round 10, commit 1c8aeaf; text 078f537) | | DRAFTED; sending not recorded: UNCERTAIN |
| as of 20 Nov | Deb → Keith | Contract, DPA, first invoice | REVIEW:87 ("nothing sent", 16 Nov); `rethink_2026-11-20/DECISION.md:51` still lists contract+DPA as needed | NOT SENT (as recorded) |

Letter of intent `T/lettre_intention_GreenJobs.md` (for Keith to sign): whether it was ever sent to or signed by Keith is UNCERTAIN; v1 review calls it the letter "which Keith would sign" (167b73c, l.17), and `T/INTERNE_sources_et_points_a_verifier.md:60` says letters were removed from the dossier.

## 2. What Keith agreed to, and what is unagreed

**Agreed, in his words** (only two sentences on record):
- Price/timing: to Deb's offer (€600/month "starting now", plus €1,500 in Q1, both in the contract; start "November 1st week", thread:4-5) Keith replied "I appreciate your offer and yes it should be doable" (thread:6, 29 Oct). Note "should be doable" is conditional wording.
- He told Strategies "we will be changing contracts" (thread:9).
- Signer: Keith (Q12 answer, REVIEW:27; answer given by his team, not quoted from Keith).

**Not agreed / no recorded reply from Keith:**
- Upfront monthly payment ("first month when you sign, then at the start of each month", EMAIL_TO_KEITH:11). No acceptance recorded. The €1,500 Q1 term is absent from the 9 Nov email (REVIEW:41).
- Any scope: the 3 Dec list, phase 2 list, trim order. No reply from Keith to the plan is recorded; the answers came from Rashieda and Diana.
- Contract, DPA: not sent, not signed.
- Contracting entity: GreenJobs Ltd (sites) vs Gaia Talent Ltd (payer) (REVIEW:27).
- Retention period ("Not sure", REVIEW:20).
- The 8 sector domains ("Not sure", REVIEW:16); plan said extra sites would be "quoted separately" (transition_plan.html:37).
- Logos "OK 'I suppose'" (Diana), Keith's word still needed (REVIEW:26).
- Alerts trim (REVIEW:34 says not first in trim order "without Keith's word").
- Applications fallback inbox (Diana named rashieda.ely@ but said "not sure what you mean", SOURCE_diana:3).
- Letter of intent amounts (€1,500 rebuild then €600/month from authorisation, `T/lettre_intention_GreenJobs.md:13-14`) differ from the LinkedIn deal; not agreed by Keith on record.
- "Keith will not pay for a third-party service" (DECISION.md:3) is the operator's ruling; no Keith quote for it in the repo: UNCERTAIN as a client statement.

## 3. What was promised for 3 Dec (verbatim)

Email (EMAIL_TO_KEITH.txt:7): "I'd aim to switch them over on Thursday 3 December. That leaves a working day in hand before the Strategies contract ends on Sunday 6 December. From the switch, your team posts jobs through a simple admin console I'll build. The candidate and employer log-ins and the feeds from the posting tools follow in a second phase, with target dates in the contract and the feeds depending on each provider's onboarding."

Email (:11): "The build starts once the contract is signed and the first month is paid, and the data exports once the data processing agreement is signed. If all of that is back by Wednesday 11 November, we're in good shape for 3 December."

Plan, 3 December row (transition_plan.html:30): "Both GreenJobs boards (greenjobs.ie and greenjobs.co.uk) on your domains with your current jobs, your team posting, editing and closing jobs through a simple admin console I'll build, applications reaching the inbox you choose, job alert emails, and the candidate records you choose to keep. Candidates browse and apply without an account at first."

Phase 2 (:31): "Second phase (target: December to late January) Candidate log-ins, employer log-ins for posting and editing their own jobs (not online purchasing or card payment), feeds from the posting tools you use (Broadbean, Idibu or LogicMelon), and posting from the one CRM you confirm, if you use one. Target dates go in the contract and depend on each provider's onboarding; any fees those providers charge are yours, not part of the monthly fee."

Floor and trims (:33): "The boards with your jobs, the posting console and applications come first for 3 December and are the last things I'd trim. That date depends on your answers, the signed contract and data processing agreement, and DNS access for both domains, all by Wednesday 11 November (Strategies don't manage DNS), and on your sign-off on the test address by Friday 27 November. If any of these comes in late, I'll keep 3 December wherever I can, since Strategies switch off on 6 December regardless, and write to you the same day saying which items move to the second phase, starting with the alert emails and the candidate import. Everything we export before 6 December goes into a folder in a storage account in GreenJobs' name, so you hold your own copy after Strategies switch off."

After 3 Dec (:24): "Daily checks for 10 working days on each item that went live on 3 December, against the acceptance list in the contract."

Q1 (:37): "If there are others, I'll quote those separately so this plan and the monthly fee stay as they are."

Internal floor (FEASIBILITY_MATRIX.md:109, not sent): never trimmed = boards, staff console, applications; trim order alerts, candidate import, newsletter.

## 4. Operator's legal / permit constraints (facts as recorded; the operator owns this)

- Permit dossier (10 Nov): "aucune prestation n'est réalisée ni facturée avant la délivrance du titre" (`T/business_plan_ProdCraft.md:150`); "Aucune facturation avant l'autorisation d'exercer" and "Ne rien joindre et ne pas citer GreenJobs dans le dossier" (`T/INTERNE_sources_et_points_a_verifier.md:61`).
- Letter of intent text for Keith: "Aucune prestation n'a été réalisée ni facturée à ce jour… Le contrat définitif sera signé après l'immatriculation de son entreprise"; start "à compter de la délivrance de son autorisation d'exercer" (`T/lettre_intention_GreenJobs.md:14,16`).
- Commit 167b73c (REVIEW v1 §0): the 9 Nov upfront-payment ask conflicts with the dossier; "do not send an invoice or a contract that starts paid work" until a lawyer confirms a lawful route; new permit "almost certainly comes after 6 Dec" (estimate); portage salarial UNVERIFIED. Fallback named: Keith asks Strategies for a short extension. The v2 review (07dd175) removed this section ("legal parked until lawyer call").
- Lesson: check permit/entity/VAT before sending payment terms (`.claude/brain/lessons/2026-11-16-sending-payment-terms-invoice-client-check.md:12`).
- Lawyer call outcome: NOT RECORDED. Whether any paid work or invoicing is lawful before 6 Dec: UNKNOWN.
- Open (167b73c, v1 l.53): whether unpaid preparation counts as "work" against the letter's "no work carried out" — build commits exist (e.g. 8baaae2, 0512b2b, 20 Nov).

## 5. Contradictions: promises vs `rethink_2026-11-20/DECISION.md`

1. **Candidate records.** Plan promised "the candidate records you choose to keep" on 3 Dec (html:30). DECISION:22: "Candidates and old applications go to GreenJobs' own raw archive, never into the new site." Plan said a trim would be written to Keith "the same day" (html:33); no such note to Keith is recorded.
2. **Job alerts.** Promised for 3 Dec (html:30). DECISION is silent on alert sending; only subscriber import "where consent allows, and they re-confirm" (:22); the 30 Nov gate (:28-32) does not test alerts. Status UNCERTAIN.
3. **Employer self-posting.** Plan: employer log-ins are phase 2 (html:31); FM:103 "On 3 December advertisers cannot post themselves". DECISION:21: CHM Recruit and Mattinson "keep self-posting through their own logins". Pulled forward; no change agreed with Keith on record.
4. **Sector domains.** Plan: other domains "quoted separately so this plan and the monthly fee stay as they are" (html:37). DECISION:23: 8 sector domains forward + ~1,200 redirects, no price stated.
5. **New scope not in the plan:** Gaia jobs auto-imported from gaiatalent.com every 10 min (DECISION:20); status page; weekly 5-line email to Keith (:47). Plan's phase-2 feeds were Broadbean/Idibu/LogicMelon/CRM; Diana says none are used (SOURCE_diana:3,5).
6. **Build start condition.** Email: build starts once contract signed and first month paid (EMAIL:11; html:18). Contract and DPA still unsent (DECISION:51), yet build work proceeds. DECISION drops the payment condition entirely (lists only contract + DPA). Also conflicts with the permit dossier's "no work before authorisation" (section 4).
7. **Exports and logins.** Plan: exports run by Keith's staff "with me", logins via password manager (html:50; FM:101). DECISION:42: one dedicated Strategies login via one-time link, an export bot downloads overnight. Diana draft v2 tells her she can "skip" the password manager. Whether bot downloads fit Strategies' terms: not checked (UNCERTAIN).
8. **Dates.** Plan inputs deadline Wed 11 Nov (html:33); missed (REVIEW:43). DECISION keeps 27 Nov sign-off and adds a 30 Nov gate; 3 Dec switch not restated in DECISION but not changed either.
9. **Price.** DECISION is silent on price; the €1,500 Q1 term is still absent from anything sent to Keith (REVIEW:41), and the letter of intent states a different structure.
