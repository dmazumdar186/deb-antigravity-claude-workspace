# Gaia Talent (Keith Molony) engagement — chronological record

Built only from this repo's git history and tracked files. The operator's chat
transcripts are not available; where the repo is silent, that is stated.

## 0. A gap the git history itself flags

The earliest commit in `git log --all` touching anything "gaia" is `e016643`
(2026-08-27), and it is **not** a gaia commit — it is
`[model_tier] Sweep every judgement literal to Fable 5`, an unrelated
model-pricing sweep that happens to add, in the same commit, the entire
pre-existing `execution/gtm_client_workflows/gaia_sourcing/` package and
`deliverables/gaia_2026-08-20/` wholesale (`git show --stat e016643`). That
commit has a parent (`ad4940d`), so it is not the repo's root commit — the
gaia work simply has no earlier commits of its own. Internally,
`HANDOFF.md` states it was "Written 2026-08-19, end of session 4" for a
"Deadline: Thursday 20 August 2026" — i.e. at least 4 working sessions of
build history predate the first git record of this package by about a week.
**No commit in this repo documents the actual start of the Gaia engagement,
the brief intake, or sessions 1–4.**

## 1. Timeline

| Date | Event | Source |
|---|---|---|
| ~2026-08-19 (session 4 end, per doc) | HANDOFF.md written; artifact "rendered and passing an 18-check acceptance gate"; Role 1 delivers 10/10, Role 2 delivers 3/5 | `execution/gtm_client_workflows/gaia_sourcing/HANDOFF.md:1-7` |
| 2026-08-20 | Deliverable date on the dossier: "13 candidates" shortlist for TOBIN/AtkinsRéalis, Senior Structural Engineer + Transport Major Projects Manager | `deliverables/gaia_2026-08-20/dossier.html` (rendered text) |
| 2026-08-20 (per pool maps) | Role 1: 158 profiles assessed, 18 passed gates, 10/10 delivered. Role 2: 21 profiles assessed, 4 passed gates, 3/5 delivered | `deliverables/gaia_2026-08-20/pool_map_role1.md`, `pool_map_role2.md` |
| 2026-08-25 | `logs/drops.jsonl` (candidate PII/quotes) committed by an unrelated `instantly_reply_notifier` commit `cad40c1` that happened to touch a same-named path — flagged later as a compliance leftover | HANDOFF.md 2026-09-10 addendum, `execution/.../HANDOFF.md:429-438` |
| 2026-08-27 | `e016643` — first commit in git history to include the gaia_sourcing package and the `gaia_2026-08-20` deliverable (as a side-effect of a model-tier sweep) | commit `e016643` |
| 2026-08-27 | `e4a73fa` — follow-up audit commit, pins gaia's judgement tier to Fable 5 in tests | commit `e4a73fa` |
| 2026-09-01 | `f153702` — gaia providers migrated to Claude Fable 5.1 | commit `f153702` |
| 2026-09-10 (call, before) | Keith's written feedback on the 20 Aug shortlist recorded: "too senior, some not in Ireland" | commit `a626381` subject line + body |
| 2026-09-10, 17:00, 27 min (Fathom recording) | Client call with Keith Molony. He says the list was "too senior"; praises the interface/grading/simplicity; describes Maddie's inbound screener and Recruit CRM's AI-sourcing upgrade email (from Julia); agrees to a Monday 14 Sep 17:00 demo delivery via Loom | `deliverables/gaia_2026-09-10/transcript_2026-09-10_fathom.md` |
| 2026-09-10 | `a626381` — brief-level seniority ceiling and residence-rule fix, citing the client feedback; adds Brief Controls page and call brief | commit `a626381` |
| 2026-09-10 | `887fbf1` runbook; `22d59ee` v2 proposal page; `6a67814` Recruit CRM sync adapter + reply classifier ("Promised on the 10 Sep call: sourced candidates land in Recruit CRM ... consultants and Maddie take over"); `0fcb48e` Radar design draft + final spec; `2128643` Radar contracts + directive draft; then 10 more commits building Radar components (identity resolution, sources, eval harness, console, spend ledger, opt-out registry, etc.) | commits `887fbf1`, `22d59ee`, `6a67814`, `0fcb48e`, `2128643`, `b8e7db3`, `3745d2d`, `a080589`, `ee4655c`, `9f4711c`, `a1fb8fe`, `cb08744`, `57cbac1` |
| 2026-09-10 | `04ed9c6` — Gaia Sourcing/Radar directive promoted to `directives/gtm_client_workflows/gaia_sourcing.md` | commit `04ed9c6` |
| 2026-09-10 evening → 2026-09-11 | Cloud session re-runs the pipeline on campaign `gaia-2026-09-14` under a new, stricter brief; result: Role 1 471 assessed / 2 gate-passers / **2 of 10 delivered** (Alicia Joyce, John Alcaras); Role 2 65 assessed / **0 of 5** delivered. Model spend EUR 25.69 of a EUR 26.50 cap | `deliverables/gaia_2026-09-10/RUNBOOK_monday_delivery.md` §1c; `HANDOFF_SESSION_2026-09-11.md` |
| 2026-09-11 | Nine further hardening commits to gaia_sourcing (local OCR, Playwright fallback, serper_people discovery, 58-firm directory widening, harvest_discovery stage, strict tool schemas, run-cache rescue commit `cb76b51`) | commits `3229b9a` … `cb76b51` |
| 2026-09-11 | `deliverables/gaia_poc_check/` — a same-day side project ("Shortlist Check" POC): re-checks the 13 Aug names against the 10 Sep brief offline; result 0 of 13 pass | `deliverables/gaia_poc_check/PLAN.md` |
| 2026-09-11 (operator correction, recorded in-repo) | Files corrected: the Fathom transcript's "Steph" was a mis-transcription; the real person is Maddie, the developer who built Gaia's inbound screener | `deliverables/gaia_2026-09-10/transcript_2026-09-10_fathom.md:9`, `monday_send.md:5`, `PLAN.md:26` |
| Monday 14 Sep 2026, 17:00 (future to the 11 Sep "today", promised, not yet delivered as of this record) | Planned send: corrected shortlist link, Brief Controls link, v2 page for Maddie, Loom | `deliverables/gaia_2026-09-10/monday_send.md`, `RUNBOOK_monday_delivery.md` §6 |

## 2. Keith's asks and feedback, verbatim where the repo has words

**Location/"not in Ireland" feedback on the 20 Aug list — resolved, cited:**
Commit `a626381` (2026-09-10) subject: *"gaia_sourcing: brief-level seniority ceiling and residence rule"*; body,
first line: **"Client feedback on the 20 Aug shortlist: too senior, some not in Ireland."**
This is echoed as a direct written record in `deliverables/gaia_2026-09-10/monday_send.md:5`
("Keith's feedback on the 20 August list, as recorded in commit a626381 on
the morning of the call, was 'too senior, some not in Ireland'") and in
`transcript_2026-09-10_fathom.md:6` ("his earlier written feedback ...
was 'too senior, some not in Ireland'"). On the call itself (per the Fathom
transcript) Keith **only repeated the seniority point** verbatim: *"The one
thing that was missed ... is they were too senior."* / *"They're all
excellent candidates per se, but they're too senior."* / *"I did message a
handful of them."* The location complaint is documented only as
pre-call written feedback quoted in the commit message, not as a verbatim
quote from Keith on the call recording itself.

Other verbatim Keith quotes (all from `transcript_2026-09-10_fathom.md`):
- "I like the simplicity of the interface of what you sent me, the grading system, the fact that I could look at them, I recognize a lot of the candidates."
- "the key word is accurately"; "cut the wheat from the chaff. Is this actually a value add or is this another AI headspace thing that's taking us away from doing our ABCs?"
- "speed and accuracy are the two most important elements in our work"; "I'm a recruiter, I'm not a techie guy."
- "Isadora and I would be mostly just working high level ... senior to director level roles ... we could have 50, 60, 70 ... 100 jobs, give them to Maddie and say screen."
- "Is there a way of syncing what's being done with Maddie with the work that you're doing?"
- "what's your pitch, is this to take over from LinkedIn Recruiter?" / "how long ... where it's just literally like Maddie on our system, very straightforward for anybody to use?" — Deb answered "3 days, call it 5 working days."
- Market colour: InMail response "previously 10 to 15 percent ... some people are talking about three"; enrichment tools "they're enriching, but they don't have the data."

**"Steph" vs "Maddie" — first appearances and resolution:**
- "Maddie" first appears chronologically in commit `6a67814` (2026-09-10):
  *"Promised on the 10 Sep call: sourced candidates land in Recruit CRM so
  consultants and Maddie take over"* — used from the start as a person/agent
  who receives hand-off, not further identified there.
- "Steph" appears only in three 2026-09-10 deliverable files
  (`RUNBOOK_monday_delivery.md`, `v2_proposal.md`/`v2_proposal/index.html`),
  originally as the addressee Keith should forward material to, alongside
  "Maddie" used elsewhere in the same documents for the inbound screener
  *tool*, e.g. `radar_design_draft_for_panel.md:5` (earlier revision, now
  corrected): *"Maddie (custom inbound screener + Irish-accent voice agent,
  built by freelancer Steph)"* — i.e. the original working model in the repo
  was **Steph = the human developer, Maddie = the tool she built.**
- On 2026-09-11 this is explicitly reversed by an operator correction
  recorded in-repo: `transcript_2026-09-10_fathom.md:9` — *"Maddie: the
  developer who built Gaia's inbound screener (operator's correction
  2026-09-11; Fathom's transcript garbles the name as 'Steph' and describes
  the screener itself as Maddie)."* `monday_send.md:5` repeats this
  ("Maddie is the developer ... the Fathom transcript garbles the name as
  'Steph'"). `deliverables/gaia_poc_check/PLAN.md:26` states the final
  position most bluntly: **"Maddie (the developer who built Gaia's inbound
  screener; per the operator, no one named Steph exists, Fathom garbled the
  name)."**
- As of this record, all `deliverables/gaia_2026-09-10/*` files
  (`RUNBOOK_monday_delivery.md`, `v2_proposal.md`, `v2_proposal/index.html`,
  `call_brief_2026-09-10.md`) have been edited in place to say "Maddie"
  throughout and no longer contain "Steph" — i.e. the correction has been
  propagated into the historical deliverable text itself, not kept as a
  separate errata note. **Net effect: "Maddie" denotes both the person (the
  developer) and, per the same sources, the screener/tool she built and
  that Keith operates day to day ("Maddie's screener", "Maddie takes over");
  the repo never resolves whether the tool is literally named after her or
  this is an artifact of loose language in the source material.**

## 3. What was promised at each point, and what was delivered

**20 Aug delivery** — Promised (per HANDOFF.md, written the day before):
evidence-verified shortlists, Role 1 10/10, Role 2 3/5, `dossier.html` (13
cards, 117 evidence claims, verbatim quotes), `candidates.csv`, pool maps,
Art. 14 privacy notice live. Delivered: exactly that — 13 candidates (10 + 3),
verified against an 18-check acceptance gate (`HANDOFF.md:1-31`). Known
delivery-time gaps stated in the same doc: Role 2 short by 2 (source
problem, not a bug); 25 of 51 image-scan documents recovered via OCR before
Anthropic balance hit €0; Art. 14 notice hosted on a Prodcraft domain, not
Gaia's (`HANDOFF.md §3-4`).

**10 Sep call** — Promised (per the transcript and `RUNBOOK_monday_delivery.md:1-4`):
"the sourcing system 'the same way as before'", a link plus a Loom, and a
note on how it works with Maddie and Recruit CRM that Keith can forward to
her — explicitly **"Nothing else. No auto-sending, no voice agent, no
replacement of Recruit CRM."** Delivery date promised on the call: Saturday
17:00 per the call brief's planned offer (`call_brief_2026-09-10.md` §2); the
actual commitment that stuck (per `monday_send.md`'s footnote and the
runbook) moved to **Monday 14 Sep 17:00** — the runbook explicitly instructs
never to say "Saturday" and to explain, if asked, "took the extra day to
check both cards by hand" (`monday_send.md`, Loom script recording notes).

**Monday 14 Sep** — Promised, per `monday_send.md` draft email: a corrected
shortlist link, the Brief Controls page (client-adjustable filters), a page
for Maddie on the Recruit CRM hand-off, a 5-minute Loom, and two questions
back from Keith (seniority ceiling, Ireland residence rule) plus one for
Maddie (Recruit CRM plan tier). As of the latest session note
(`HANDOFF_SESSION_2026-09-11.md` addendum), this had **not yet been sent**:
the corrected campaign's run cache (`run/gaia-2026-09-14/`) was stranded in
a different, idle container and a recovery procedure was documented but not
confirmed executed. The committed dossier/pool-map content for
`gaia_2026-09-14` reflects the 2-of-10 / 0-of-5 result; whether the actual
email/Loom went out to Keith by the promised time is **not evidenced in the
repo**.

## 4. What the system was built to do: 20 Aug vs the later Radar/v2 design

**Earliest doc (HANDOFF.md, written for the 20 Aug delivery)** describes a
single-shot, manually-run evidence pipeline: harvest → extract → validate →
gate → contact → messages → render, gated by hard-coded chartership /
seniority-floor / discipline / location gates, with a €30-per-run cost
ceiling, run against ACP oral-hearing documents and firm "our people" pages
only. Its own words: rules I1–I9 (verbatim-quote requirement, deterministic
gates, off-limits employer block, no collapsing of email-status labels,
fixed Art. 14 string, Prodcraft never contacts candidates, LinkedIn-first
channel, one-process run lock).

**Later design (`radar_final_spec.md`, `radar_design_draft_for_panel.md`,
2026-09-10)** reframes the same engine as "Radar, not Search": a *standing*,
weekly-refreshed niche pool with a structured, versioned Brief Contract per
role, a composition guard that refuses to deliver a list breaking the
brief, licensed people-data sources (PDL/Crustdata/Apollo) to reach the
8–15-year grade the original sources structurally could not reach (firm
leadership pages and oral-hearing witnesses are "senior by construction" —
`call_brief_2026-09-10.md` §1.3), an eval harness with Cohen's kappa and a
90% grade-precision ship threshold, a Recruit CRM sync adapter, a reply
classifier, an operator console, and a Modal live re-cut endpoint. Directive
`directives/gtm_client_workflows/gaia_sourcing.md` (created 2026-09-10, only
version in git) codifies this as the current goal: *"Deliver
evidence-verified, brief-matched shortlists of passive candidates ... hand
them into Recruit CRM, and never contact a candidate ourselves."*

**Drift between "what Keith asked for" and "what got built":** Keith's own
brief on the call was narrow — a like-for-like corrected list, no new
system, explicitly "no auto-sending, no voice agent, no replacement of
Recruit CRM" (`RUNBOOK_monday_delivery.md:1-4`). What was actually built in
the following 36 hours was a substantially larger system (source-provider
contract/registry, identity resolution, ICP sampling, opt-out registry,
approval-state machine, spend ledger, alert channel, eval harness, operator
console, Modal endpoint — ~15 commits, RADAR_CONTRACTS.md's full A–G scope)
that goes considerably beyond a "filter re-run." The `radar_design_draft_for_panel.md`
file itself states the intent plainly: **"Goal now: over-deliver without
breaking the promise."** This is a deliberate, self-acknowledged drift, not
an accidental one, but it is drift nonetheless relative to what Keith
literally asked for on the call.

## 5. Every number quoted to or about Keith

| Number | Context | Source | Conflict? |
|---|---|---|---|
| 13 candidates delivered 20 Aug (10 Role 1 + 3 Role 2) | dossier headline | `dossier.html`; `HANDOFF.md:6` | Consistent everywhere it appears |
| Role 1: 158 profiles assessed, 594 raw claims, 446 surviving validation, 18 passed gates, 10/10 delivered | pool map | `pool_map_role1.md` | — |
| Role 2: 21 profiles assessed, 333 raw claims, 280 surviving validation, 4 passed gates, 3/5 delivered | pool map | `pool_map_role2.md` | — |
| Quote-drop rate 0.9% | HANDOFF hallucination metric | `HANDOFF.md:177`; repeated in `v2_proposal.md:24` | Consistent |
| Full 20 Aug run cost: €0.60 against a €30 ceiling | HANDOFF budget table | `HANDOFF.md:152` | Ceiling later lowered to €12 per-run / €26.5(then €22 at one point)/cumulative — see below |
| "50 sent" | A figure Keith referenced (per call-brief framing) that no artifact supports | `call_brief_2026-09-10.md:17` ("Note on '50 sent': no artifact in the workspace supports 50; every file says 13. Use 13 on the call.") | **Flagged contradiction by the repo itself** — 50 vs the documented 13 |
| 4 named as not in Ireland: Taskov, Petho, Penco (London), Brady | call brief §0 | `call_brief_2026-09-10.md:13` (originally said "Brady (Horganlynch Belfast)") | **Corrected 2026-09-11**: Brady is Cork per the Aug dossier and current cache; the location miss is "three London names plus Brady with no residence evidence," not Belfast. Correction recorded at the top of `call_brief_2026-09-10.md` and in `monday_send.md:5`, `PLAN.md` |
| 5 of 13 emails inferred/never verified, 1 had none, 11 of 13 low movability | call brief §0 | `call_brief_2026-09-10.md:14` | — |
| Model spend, corrected campaign (`gaia-2026-09-14`): EUR 25.69 of a EUR 26.50 cap | session handoff | `HANDOFF_SESSION_2026-09-11.md`; `v2_proposal.md:37,53` | Commit `57cbac1` (earlier same day) states the cumulative cap as **"EUR 22"**; `core/config.py:134` (current code) sets `max_cost_eur_total = 26.5`. This reads as the cap being raised during the day's work, not a stable contradiction, but the two commit-message/doc figures disagree if read in isolation. |
| Per-run ceiling: €30 (20 Aug) → lowered to €12 | spend guardrail commit | commit `57cbac1`; `core/config.py:115` (`max_cost_eur: float = 12.0`) | Documented change, not a conflict |
| Role 1 corrected cut: 471 assessed, 2 gate-passers, 2/10 delivered (Alicia Joyce/CSEA, John Alcaras/Arcadis); 14 near-miss on residence, 9 on chartership | runbook §1c, handoff, monday_send, v2_proposal | `RUNBOOK_monday_delivery.md`, `HANDOFF_SESSION_2026-09-11.md`, `monday_send.md:31`, `v2_proposal/index.html:357` | Consistent across all four documents |
| Role 2 corrected cut: 65 assessed, 0/5 delivered | same set | same sources | Consistent |
| Test suite growth: 130→501 (Aug), 584 (a626381), 636 (6a67814), 853→927 (Radar landing/audit, 2026-09-10), 1,086 (09-11 runbook), 1,093 (09-11 addendum) | multiple commit messages and HANDOFF entries | `HANDOFF.md`, commits `a626381`, `6a67814`, `57cbac1`, `RUNBOOK_monday_delivery.md` §1c, `HANDOFF_SESSION_2026-09-11.md` addendum | Monotonically consistent (a running total, not conflicting figures) |
| Cost per role, v2 design: LLM ≈€13, OCR €5–15, people data ≈€60–80/300 profiles, Prospeo ≈€2, search ≈€5 → "About €100 to €120 all-in" | call brief §3 | `call_brief_2026-09-10.md` | `v2_proposal.md:57` states **"about €100"** (rounder, slightly lower than the "€100 to €120" range) — minor rounding inconsistency, not a real conflict |
| Placement fee: €14k–20k, 18% of €80k–110k | call brief §3, radar_design_draft, v2_proposal | `call_brief_2026-09-10.md`; `radar_design_draft_for_panel.md`; `v2_proposal.md:57` | Consistent |
| Gaia Talent: 5 people (Keith MD, Isadora senior consultant, Gian, Eva, Diana), B Corp | radar design draft | `radar_design_draft_for_panel.md:5` | Only stated once; not cross-checked elsewhere |
| POC "Shortlist Check" re-check of the 13 Aug names against the 10 Sep brief: 0 of 13 pass; 10/13 over the seniority ceiling; 5/13 pattern-guess emails, 1 with none | PLAN.md | `deliverables/gaia_poc_check/PLAN.md` | Consistent with, and a restatement of, the `call_brief_2026-09-10.md` contactability figures |

## 6. Contradictions / errors found

1. **"50 sent" vs 13 delivered.** The call brief itself flags that no
   artifact supports a figure of 50 candidates sent, while every tracked
   file (dossier, CSV, pool maps, HANDOFF) says 13. Origin of "50" is not in
   the repo — presumably something said live on a call, not evidenced here.
   (`call_brief_2026-09-10.md:17`)
2. **Pat Brady's location: Belfast vs Cork.** The original call brief and
   `RUNBOOK_monday_delivery.md`/`v2_proposal.md` said "Brady (Horganlynch
   Belfast)"; a 2026-09-11 correction (now propagated into the files
   directly) establishes he is Horganlynch's Cork office per the Aug
   dossier text and the current data cache, with only a Belfast *project*
   named. This was a live-in-place edit during this session — treat the
   current file text as authoritative, the "Belfast" claim as a documented
   error that briefly existed in three deliverables.
3. **"Steph" vs "Maddie".** As detailed in §2: earlier 2026-09-10 documents
   used "Steph" as a real person's name (the developer who built the
   screener) distinct from "Maddie" (the screener/tool). A 2026-09-11
   operator correction, now applied throughout, holds that no person named
   Steph exists — "Steph" was a mis-transcription of "Maddie" in the Fathom
   transcript — and Maddie is both the developer and (per the same
   documents) the name used for the screener she built. The repo does not
   fully disambiguate whether "Maddie" the tool is literally named for
   Maddie the person, or whether earlier documents' "screener called
   Maddie" language is itself imprecise.
4. **Spend cap: EUR 22 vs EUR 26.50.** Commit `57cbac1` (2026-09-10)
   introduces the cumulative spend cap and states it as "EUR 22"; the
   current code (`core/config.py:134`) and the 2026-09-11 session handoff
   both give EUR 26.50. Most likely explanation is the cap was raised
   later the same day/session, but no single commit message documents that
   specific change from 22→26.5, so it reads as a minor undocumented drift
   rather than a clean audit trail.
5. **Git history omits the actual project start.** As noted in §0, no
   commit documents the initial build (HANDOFF.md's "session 4", the intake
   of the TOBIN/AtkinsRéalis brief, or anything before 2026-08-27). The
   entire 20 Aug deliverable and pipeline first appear, already complete,
   in a commit whose stated purpose is unrelated (a model-pricing sweep).
6. **€100–120 vs "about €100" per-role cost.** `call_brief_2026-09-10.md`
   gives a itemised range summing to "€100 to €120 all-in"; `v2_proposal.md`
   rounds this to "about €100." Not materially conflicting, but not
   identical either.
