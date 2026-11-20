# Keith pack (2026-11-20): sources

Internal. Not for sending. Every factual line in the two drafts, mapped to file:line. Line numbers are raw file lines (`cat -n`), including for `transition_plan.html` (the RECORD's "Plan:" numbers are tag-stripped and differ).

Path keys:
- **M** = `deliverables/greenjobs_migration_2026-11-06/`
- **RECORD** = `deliverables/engagement_record_2026-11-20/RECORD.md`
- **GAIA** = `deliverables/engagement_record_2026-11-20/A_gaia_talent.md`
- **DECISION** = `M/rethink_2026-11-20/DECISION.md`
- **STATUS** = `M/STATUS_2026-11-20.md`
- **REVIEW** = `M/REVIEW_2026-11-16_keith_answers.md`
- **PLAN** = `M/transition_plan.html`
- **DIANA** = `M/replies_2026-11-20/SOURCE_diana_2026-11-19.txt`
- **DIANA-DRAFT** = `M/replies_2026-11-20/DRAFT_reply_to_diana_v2_async.txt`
- **ZONE** = `M/build/dns/ZONE_INVENTORY_2026-11-20.md`
- **CHECK** = `deliverables/greenjobs_redesign_2026-09-22/KEITH_CHANGES_CHECKLIST.md`
- **BRIEF** = `deliverables/greenjobs_redesign_2026-09-22/proposal/keith_costing_brief_2026-09-28.md`
- **PROPOSAL** = `deliverables/greenjobs_redesign_2026-09-22/proposal/GreenJobs_Proposal_v1.0_2026-09-30.md`

**Default dates are choices, not facts.** Each "if we don't hear by" date was set before the date that depends on it: Tue 24 Nov before the Cloudflare account (STATUS:57, before 30 Nov) and the notice (REVIEW:21, Wed 25 Nov); Wed 25 Nov before the import (STATUS:61, Wed 2 Dec) and the CHM/Mattinson notice; Fri 27 Nov to match sign-off (PLAN:22; RECORD:71).

## 1. QUESTIONS_FOR_KEITH.txt

| Line | Claim | Source |
|---|---|---|
| 1 | Switch on 3 December | PLAN:18; STATUS:6 |
| 6-7 | Async, written answers, no call | DECISION:41; PLAN:50; operator brain rule |
| 9 | Candidate records Keith chooses to keep; how far back | PLAN:30, PLAN:41; RECORD:48 (P5a); REVIEW:20 |
| 10 | Suggest two years | PLAN:41 ("I'd suggest two years") |
| 11 | Exports go into storage in GreenJobs' name | PLAN:33; RECORD:60 (P16) |
| 12 | Default: jobs and employers only; rest in the raw archive | REVIEW:20 ("Until then: download everything as a raw archive; import jobs and employers only") |
| 14 | The 8 domain names | DIANA:3 (123 Reg list); REVIEW:16; RECORD:56 (P12) |
| 15 | Six share the greenjobs.co.uk host; waste and water have no apex A | ZONE:12-21 (apex A 212.250.3.80 on co.uk and six; "none" on wastejobsuk.com, waterjobsuk.com); REVIEW:16 (same Strategies host) |
| 15 | They stop on 6 Dec | REVIEW:16 ("They go dark on 6 Dec"); keith_linkedin_thread:10, :13 |
| 16-17 | Forward each to its sector page on greenjobs.co.uk | REVIEW:33 ("minimum fix"); DECISION:23 |
| 18 | Default: leave as they are | DECISION:23, :37 and RECORD:56 (out of scope until Keith answers) |
| 20 | Employer logos from the current boards | PLAN:47; REVIEW:26 ("Need a one-line OK on logos from Keith"); RECORD:68 (P24) |
| 22 | Logo wall on the build | CHECK:10 (A4), CHECK:36 (E3) |
| 24 | 11 items waiting on Keith | PROPOSAL:60; RECORD:65 (P21); BRIEF:94 |
| 25-35 | Items a-k, in order | BRIEF:97-109 (a=97, b=98, c=99, d=100, e=101, f=102, g=103, h=106, i=107, j=108, k=109) |
| 28 | "with permission to name each client" | `deliverables/greenjobs_redesign_2026-09-22/src/templates/for-keith.html:56` |
| 32 | 14 sectors on 28 Sept | CHECK:8 (A2); BRIEF:106 |
| 37 | a-c read "figure supplied at launch" | CHECK:35 (E2) |
| 37 | d and g not shown | CHECK:40 (E7: testimonials collected for launch, no placement figures) |
| 37 | f keeps current numbers | CHECK:45 (F3) |
| 37 | h live count; i merged; j "Ask us" | BRIEF:106, :107, :108 |
| 37 | k salary guide only | CHECK:50 (G3) |
| 38 | Applied the day supplied | PROPOSAL:60 ("applied the day you supply the input"); BRIEF:114 |
| 40-41 | Recruit CRM vs Vincere conflict | GAIA:20 (Sept call, Recruit CRM); GAIA:100; `M/rethink_2026-11-20/FACTS.md:22` (Vincere, from the gaiatalent.com privacy policy) |
| 42 | Second-phase CRM link | PLAN:31; RECORD:54 (P10) |
| 44 | Two roles, delivered August | GAIA:17; RECORD:20 |
| 45 | Role 1 = 10 places; Role 2 = Transport Major Projects Manager, Cork | GAIA:15-16; GAIA:73 ("Role 2 (Cork Transport)"); RECORD:77-78 |
| 46-48 | Role 1 rules: seniority ceiling (Senior / Principal/Associate, salary band) and Ireland rule (RoI, Cork commute, relocators) | GAIA:72; RECORD:77 |
| 49 | Default: treat as closed | Choice. Status today: dormant, not closed in writing (GAIA:80; RECORD:75) |
| 51 | Inbox for jobs with no email/link | DIANA-DRAFT:11; RECORD:46 (P3, "Default inbox asked of Diana"); STATUS:54 (reply not yet sent) |
| 53 | rashieda.ely@greenjobs.ie; Rashieda posts most jobs | DIANA:3, :11; DIANA-DRAFT:11; REVIEW:21 ("Mostly Rashieda") |
| 56-58 | Cloudflare and Resend, in GreenJobs' name | PROPOSAL:144, :148-149; DECISION:7; REVIEW:48; RECORD:58 (P14); STATUS:57 (O7) |
| 57 | Resend: alerts, newsletter, other email | PROPOSAL:149 ("Job alerts, newsletter and transactional email") |
| 59-60 | Invite debanjan@prodcraft.fyi; written guide | Operator brief (20 Nov); REVIEW:35 (use debanjan@prodcraft.fyi); DECISION:41-46 (written, asynchronous guides) |
| 61 | Default: guides to Diana | Choice. Diana holds the domain logins (DIANA:3; REVIEW:17) |
| 63 | Sign-off by Fri 27 Nov | PLAN:22; RECORD:71 (P27); DECISION:39; STATUS:53 |
| 64 | Link to follow | RECORD:71 ("Staging URL to Keith via the operator") |
| 65 | Write the same day saying which items move | PLAN:33 |
| 67 | CHM and Mattinson: staff post for them from 3 Dec | DECISION:21; REVIEW:21; RECORD:55 (P11) |
| 68 | Notice by Wed 25 Nov | REVIEW:21; STATUS:59 (O9) |
| 69 | Jobs go to Rashieda | Operator brief ("email to Rashieda") |

## 2. NOTICE_CHM_MATTINSON.txt

| Line | Claim | Source |
|---|---|---|
| 1, 5 | From Thursday 3 December, GreenJobs staff post their jobs | DECISION:21; REVIEW:21, :49; RECORD:55 (P11) |
| 6 | They stop posting themselves | REVIEW:21 ("Those two lose self-posting on 3 Dec") |
| 8 | Email jobs to rashieda.ely@greenjobs.ie | Operator brief; address from DIANA:11 |
| 10 | Apply by each job's email or own link | DECISION:18; REVIEW:23; RECORD:46 (P3); STATUS:23 (B3) |
| 12 | Nothing else changes | Operator brief only. See note below |
| 14 | Unsigned; GreenJobs signs | Operator brief |

## 3. Not used, and why

- Contract, DPA, payment, pricing and legal items: excluded on the operator's instruction (RECORD:81-83).
- Employer logins (phase 2, PLAN:31): left out of the notice; no date can be promised.
- Posting freeze, Wed 2 Dec 17:00 (REVIEW:53): internal plan only, not agreed with Keith. Left out of the notice. Operator to decide.
- Role 2's paid data source (GAIA:73): a spending decision, left to the operator.
- The KEITH_CHANGES_CHECKLIST.md file does not list the 11 open items. Its open entries are E7, G3 and G4 only (CHECK:40, :50, :51). The list of 11 is taken from BRIEF:94-109, which the proposal's "remaining 11" (PROPOSAL:60) matches.
