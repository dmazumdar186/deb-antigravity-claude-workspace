# A. Gaia Talent: candidate sourcing / Radar / Shortlist Check / website redesign (Aug to Nov 2026)

Reconstructed 2026-11-20, read-only, from tracked files. Rule applied: recorded client feedback in commits and directives outranks transcripts. Anything not written down is marked UNCERTAIN.

**Source caveat (read first).** In this clone, `git log --all` holds only 144 commits, and the oldest is dated 2026-11-16 (`git log --all --reverse` starts at `b233006`, 2026-11-16). Every Aug/Sep commit the Gaia files cite (`a626381`, `6a67814`, `e016643`, `57cbac1` and others) is missing: `git cat-file -t a626381` returns "Not a valid object name". Those commits are therefore cited second-hand, through the tracked files that quote them, chiefly `deliverables/gaia_2026-09-10/ENGAGEMENT_RECORD_2026-09-11.md` (below, "ER"). The `git log | grep gaia|keith|radar|shortlist|pool` search returns only four commits, all for GreenJobs (Nov 16 to 20).

People: Keith Molony, Managing Director of Gaia Talent Ltd. Isadora is a senior consultant. Gaia is a 5-person B Corp (`radar_design_draft_for_panel.md:5`, per ER:200, stated once). Maddie is the developer who built Gaia's inbound screener. The Fathom transcript garbled her name as "Steph", and per the operator no one named Steph exists (`transcript_2026-09-10_fathom.md:9`; `gaia_poc_check/PLAN.md:26`). Isadora appears only in Keith's call quote and as a review lens. No message from her is recorded.

---

## 1. Timeline

| Date | Event | Source |
|---|---|---|
| before 2026-08-19 | Sessions 1 to 4 built the pipeline. The brief intake (TOBIN / AtkinsRéalis: Senior Structural Engineer; Transport Major Projects Manager, Cork) is **not recorded anywhere**. | ER:6-20; `execution/gtm_client_workflows/gaia_sourcing/HANDOFF.md:3-4` |
| 2026-08-19 | Handoff written: "Role 1 delivers 10 of 10. Role 2 delivers 3 of 5". 18-check acceptance gate passed. | `execution/.../gaia_sourcing/HANDOFF.md:1-7` |
| 2026-08-20 | **Delivered**: dossier of 13 candidates (10 + 3), `candidates.csv`, two pool maps. Role 1: 158 assessed, 18 gate-passers. Role 2: 21 assessed, 4 gate-passers. | `deliverables/gaia_2026-08-20/`; ER:27-28 |
| 2026-08-20 | Art. 14 candidate privacy notice live at `gaia-privacy.pages.dev/gaia-candidate-notice`. The `privacy.prodcraft.fyi` binding was still "pending". | `execution/.../HANDOFF.md:157-162` |
| 2026-09-10 (morning) | **Keith's written feedback** on the 20 Aug list: "too senior, some not in Ireland". Recorded in commit `a626381` (cited, not present in this clone). | ER:33,47-48; `monday_send.md:6` |
| 2026-09-10, 27 min | **Call with Keith** (Fathom). Keith praised the interface, said the candidates were too senior and that he had messaged "a handful". He described Maddie's screener and Recruit CRM's AI-sourcing upgrade. Deb quoted "3 days, call it 5 working days". Agreed: demo by **Mon 14 Sep 17:00 with a Loom**. | `transcript_2026-09-10_fathom.md:7-14` |
| 2026-09-10/11 | Rebuild as "Radar" (Recruit CRM adapter, reply classifier, brief controls, eval harness, spend ledger and more). Corrected campaign `gaia-2026-09-14`: Role 1 has 471 assessed and **2 of 10** delivered (Alicia Joyce / CSEA, John Alcaras / Arcadis). Role 2 has 65 assessed and **0 of 5**. Spend was EUR 25.69 of a EUR 26.50 cap. | `HANDOFF_SESSION_2026-09-11.md:9,16-17`; ER:36-39 |
| 2026-09-11 | Shortlist Check POC built. The 13 August names re-checked against the 10 Sep brief: 0 of 13 pass. | `gaia_poc_check/PLAN.md`; `HANDOFF_SESSION_2026-09-11.md:54-56` |
| 2026-09-13 | Operator instruction: the Shortlist Check POC "is the deliverable and must convince Keith he is worth paying for over Recruit CRM and Maddie's screener". The input grew to 15 names (13 + 2). | `HANDOFF_SESSION_2026-09-11.md:60-64` |
| 2026-09-14 | Public bundle (`gaia_site_2026-09-14/`: shortlist, check, brief-controls, next-30-days, for-maddie) served from gh-pages, all 7 paths returning 200. The addendum says "Keith could not open" the claude.ai artifacts. | `HANDOFF_SESSION_2026-09-11.md:71-73` |
| 2026-09-14 17:00 | **Monday email + Loom: sent? UNCERTAIN.** The draft exists with placeholders `{LOOM_URL}` and `{TIME}`. No sent copy, Loom URL or reply is recorded. The "Keith could not open" line hints that something reached him, but it does not prove the email went out. | `monday_send.md:10,59`; `HANDOFF_SESSION_2026-09-11.md:73` |
| 2026-09-17 | Gaia website redesign (gaiatalent.com concept) deployed to `gaia-talent-redesign.pages.dev`. The handoff says "Keith has NOT been sent anything". No later record of a send. | `gaia_redesign_2026-09-17/HANDOFF.md:3-4,63-67`; `directives/gtm_client_workflows/gaia_redesign.md:150-154` |
| 2026-09-22 | Hosting moved to Cloudflare only: Radar POC pages at `gaia-radar.pages.dev`. GreenJobs redesign demo built. | `.claude/notes/general.md:30`; `HANDOFF.md:199` |
| ~2026-09-22 | Deb proposed **€1,875 for a GreenJobs redesign**. Keith replied that he is considering moving off the vendor (Strategies) and is "not yet convinced €1,875 is value for money" (paraphrase). | `deliverables/greenjobs_redesign_2026-09-22/research/panel_pass.md:5` |
| 2026-09-28 | Keith's written document / notes on the GreenJobs demo (currency, UK labelling). | `directives/gtm_client_workflows/greenjobs_redesign.md:202-220` |
| 2026-10-19 | Operator order: Gaia Talent/GreenJobs counted among prospects "whose contract is unsigned". | `.claude/notes/general.md:46` |
| Oct 29 to Nov 6 | LinkedIn: Keith said the €1,500 "initial investment" may wait until Q1. Deb offered €600/month now plus €1,500 in Q1. Keith (Oct 29): "yes it should be doable". Nov 6: he gave Strategies notice, and the sites end on **6 Dec 2026**. | `greenjobs_migration_2026-11-06/keith_linkedin_thread_2026-11-06.txt:3-15` |
| 2026-11-16 | Review of Keith's team answers for the GreenJobs migration. | commit `167b73c`; `REVIEW_2026-11-16_keith_answers.md` |
| 2026-11-19 | Email from Diana (Gaia) about GreenJobs. Reply drafts exist. | `greenjobs_migration_2026-11-06/replies_2026-11-20/SOURCE_diana_2026-11-19.txt` |
| 2026-11-20 | GreenJobs commits: Gaia exec lens, decision (trial gate 23-24 Nov), **Gaia feed sync** (gaiatalent.com wp-json to GreenJobs). | commits `05f0de0`, `519fe91`, `0512b2b` |

No recorded contact about **sourcing / Radar / Shortlist Check** after 2026-09-14. There is no Keith reply, no threshold answers, and no Maddie answer.

## 2. Asked, promised, delivered, accepted/rejected, priced

**Asked (verbatim, call 10 Sep, `transcript_2026-09-10_fathom.md`):**
- "the key word is accurately" and "speed and accuracy are the two most important elements in our work" (:10)
- "Is there a way of syncing what's being done with Maddie with the work that you're doing?" (:11)
- "how long ... where it's just literally like Maddie on our system, very straightforward for anybody to use?" (:13)
- Ambition: "50, 60, 70 ... 100 jobs, give them to Maddie and say screen" (:11)

**Promised:**
- 20 Aug: evidence-verified shortlists, 10 + 5 asked (`execution/.../HANDOFF.md:5-6`).
- 10 Sep: corrected list "the same way as before", a link plus a Loom, and a note for Maddie. "Nothing else. No auto-sending, no voice agent, no replacement of Recruit CRM." (`RUNBOOK_monday_delivery.md:1-4`, per ER:116-120)
- Re-cut the same day at no charge once Keith answers the 3 questions: "If it is not a clear improvement ... you owe nothing and we stop here." (`monday_send.md:53-57`)
- "A new name takes one working day" on the check page (`gaia_poc_check/keith_copy.md`, "Try a name").
- Wiring to Recruit CRM: 3 to 5 working days (`v2_proposal.md:57`).

**Delivered:**
- 20 Aug: 13 candidates (10 + 3, so Role 2 was 2 short).
- 11-14 Sep: built 2 of 10 and 0 of 5, the check page (15 in: 2 pass, 2 near miss, 11 out), Brief Controls, the Maddie page and the next-30-days page (`HANDOFF_SESSION_2026-09-11.md:64`).
- Whether the Sep set reached Keith is UNCERTAIN (see §1).

**Accepted / rejected:**
- 20 Aug list: **rejected on substance** ("too senior, some not in Ireland"). Interface and grading **praised** (`transcript:7`).
- No recorded verdict on the 14 Sep set, Radar, the pilot or the Gaia redesign.

**Priced:**
- Nothing was priced to Keith for sourcing. The email says "No price in this email; the follow-up call does that." (`monday_send.md:8`)
- The next-30-days page says "Terms for the 30 days are for the call, not this page".
- Internal suggestions only: a 30-day pilot at €1,500-2,500 and an own-it build at €6-9k plus €200-300/month (`call_brief_2026-09-10.md:82-83`, "Not raised on this call"). A Radar per-niche monthly fee at "€X" (`radar_final_spec.md:32`). Running cost of about €100 per role (`v2_proposal.md:57`).
- **Paid: nothing recorded** for sourcing or the Gaia redesign.
- The only agreed money is for GreenJobs: €600/month plus €1,500 in Q1 2027, agreed in principle and not signed (`rethink_2026-11-20/FACTS.md:8`).
- The Gaia redesign is described as "free, no-strings" (`directives/gtm_client_workflows/gaia_redesign.md:5`).

## 3. OPEN items today (sourcing side)

1. **Role 1 shortlist: 2 of 10 delivered, 8 open.** Near misses held: 14 on residence, 8 on chartership. Next step: re-cut and re-run `--check`. Input needed: Keith's (a) seniority ceiling (Senior only, or Principal/Associate; a salary band) and (b) Ireland rule (RoI only, Cork commute radius, relocators). (`monday_send.md:51-55`; `HANDOFF_SESSION_2026-09-11.md:69`)
2. **Role 2 (Cork Transport) shortlist: 0 of 5.** This needs a licensed people-data source, "a separate, paid step I have not taken without your say-so". Input needed: Keith's go-ahead and a budget. The PDL signup is blocked ("operator cannot sign up") and Apollo's free plan has no API access. (`monday_send.md:47`; `HANDOFF_SESSION_2026-09-11.md:6,30`)
3. **Monday 14 Sep send.** Confirm whether the email and Loom went out. If they did, find Keith's reply. Only the operator holds this.
4. **Maddie: Recruit CRM plan tier** (API needs Business or above), and confirmation that a "Sourced" stage won't double-fire her screener (`PLAN.md:110`).
5. **Unresolved compliance and ops items:** the LinkedIn-quote policy (2 delivered cards quote LinkedIn text, `HANDOFF_SESSION_2026-09-11.md:65`); `PRIVACY_NOTICE_URL` still on a pages.dev staging domain; no retention job for cached pages (:69).
6. **Pricing** for the check, pilot or Radar was never set (`PLAN.md:111`).
7. **Gaia redesign:** live, and HANDOFF step 4 is "Send Keith the Cloudflare Pages URL". No record that it was sent (`gaia_redesign_2026-09-17/HANDOFF.md:67`).

**Status judgement:** sourcing has been dormant since 14 Sep, with no recorded client action. It is not closed in writing. Nothing records the operator or Keith dropping it.

## 4. Standing instructions

- **Hard rules I1-I9.** Verbatim-quote evidence. Deterministic gates. Off-limits employers. Email-status labels never collapsed. Fixed Art. 14 string. **Prodcraft never contacts candidates.** LinkedIn-first channel. One run lock. (`execution/.../HANDOFF.md:174-196`; `directives/gtm_client_workflows/gaia_sourcing.md:31-44`)
- Every gate has a floor **and** a ceiling, plus a delivery composition guard (`.claude/notes/general.md:24`).
- "Client feedback authority is the commit message, not a re-read transcript" (`.claude/notes/log.md:115`).
- Run cache branch `gaia-run-cache-2026-09-14`: **never merge** (`log.md:123-124`).
- Don't re-run extract/deepen: they are paid. The offline `--check` is the zero-spend path (`HANDOFF_SESSION_2026-09-11.md:9`; `log.md:119`).
- Keith cannot open claude.ai links. Use Cloudflare Pages only, never github.io (`gaia_redesign.md:121-122`; `general.md:30`).
- Keith-facing copy must not use the words AI, LLM, model, platform, pipeline, automated, system, agent or algorithm (`keith_copy.md:3`).
- Public redesign pages carry no AI wording, no "Hidden Depth" comparison and no CRO number (`gaia_redesign_2026-09-17/HANDOFF.md:76-80`).
- Do not name Gaia/GreenJobs in the prodcraft.fyi portfolio while the contract is unsigned (`general.md:46`). Treat them as pitch concepts, not clients (`.claude/memory/client_confidentiality.md:4`).
- `KEY_INSTRUCTIONS.md` is **not** a client instruction file. It is a guide to getting PDL/Crustdata/Apollo API keys (`deliverables/gaia_2026-09-10/KEY_INSTRUCTIONS.md:1-15`).

## 5. Connection to GreenJobs

- **Same client.** Gaia Talent Ltd owns greenjobs.ie and greenjobs.co.uk. Keith is the signer, and "Gaia Talent Ltd pays" (`REVIEW_2026-11-16_keith_answers.md:27`; `rethink_2026-11-20/FACTS.md:6`).
- **Lineage.** GreenJobs grew out of the Gaia work. Its directive is a "companion to `gaia_redesign.md`" (`greenjobs_redesign.md:5-7`). The Gaia redesign was framed as a "credibility play alongside the Radar sourcing engagement" (`gaia_redesign.md:7-8`).
- **Code link today.** `gaia_feed_sync.py` pulls Gaia's 83 gaiatalent.com jobs into GreenJobs to end double posting: "81 of Gaia's 83 jobs are on both" (`greenjobs_redesign.md:122-160`; `BRIEFING.md:20`; commit `0512b2b`). The feed sync does not use the sourcing/Radar code.
- **FACTS.md is wrong on one point.** `FACTS.md:22` says "Gaia's CRM is Vincere", citing gaiatalent.com's privacy policy (`gaiatalent_com_audit.md:141`). Keith and Maddie use **Recruit CRM** (`transcript:8-9`). The Radar hand-off and the Maddie questions all assume Recruit CRM. Treat this as unresolved, possibly a stale privacy policy. UNCERTAIN.
