# Objections — the operator's call sheet

Prepared 2026-09-13 for the follow-up call with Keith Molony (Gaia Talent
Ltd), from a seven-lens review of the repo (Keith, Isadora, Maddie, the end
client TOBIN/AtkinsRéalis, a sceptical CFO, an Irish data-protection
solicitor, a Recruit CRM salesperson). Every number below is traced to a
repo file; where a lens invented a figure, it is dropped or marked "not in
repo" rather than repeated here as fact.

Sources cited inline: `PLAN.md`, `transcript_2026-09-10_fathom.md`,
`check_results.json`, `recruit_crm_capabilities_2026-09.md`, `keith_copy.md`,
and the four lens files (`lens_keith.md`, `lens_team.md`, `lens_money.md`,
`lens_law.md`).

---

## 0. The one-paragraph value case, in Keith's words

You said the August list was too senior and that some weren't in Ireland —
you were right on both, and now every name on the list carries the exact
sentence and the link that proves it, or the exact reason it's out, so
you're never handed thirteen maybes to call through again. (`lens_keith.md`
§3, grounded in `monday_send.md` lines 5, 21; `check_results.json` per-row
`one_line`/`evidence`; `PLAN.md` line 7.)

---

## 1. Questions Keith will ask

Merged and de-duplicated across all four lenses, ordered by deal risk
(highest first — the ones that can end the call if answered badly).

**Q1. "Julia's email this morning already gives me 0-100 match scores over
800 million profiles. Why do I need to pay you for the same thing?"**
Recruit CRM's own pages describe one holistic score with no documented way
to enforce a hard rule like "must be chartered" or "must live in County X"
— a non-qualifier is down-weighted, not removed. A score tells you how
similar a person looks to the brief; the check tells you whether they
actually clear it, and shows the sentence that proves or fails it, with the
link.
*Source: `recruit_crm_capabilities_2026-09.md` §3; `PLAN.md` item 7; `lens_keith.md` Q1.*

**Q2. "Last time you sent me 13 names and every one was wrong. What's
different this time?"**
Your written feedback was "too senior, some not in Ireland." The check now
applies a ceiling as well as a floor on seniority, and only a direct
statement of residence counts — a firm's Irish office or an Irish project
no longer does. Run again under those two rules, the same August 13 stay at
0 pass, which matches your own judgment.
*Source: `monday_send.md` line 5; `transcript_2026-09-10_fathom.md` line 7; `check_results.json` summary.*

**Q3. "Is this actually a value add, or is this another AI headspace thing
taking us from our ABCs?" (his own words, repeated)**
It ran on your own August 13 names, offline, for zero cost, and told you
what you already knew by eye: none of the 13 clear a Senior Engineer
ceiling, and none has a residence statement. That's not a new headspace —
it's your own read, checked name by name with the receipt attached.
*Source: `PLAN.md` "The demo that costs nothing"; `check_results.json` summary (pass 0, near_miss 2, out 11 on the original 13).*

**Q4. "Maddie already flags anyone over 60 and gets them on a call. What
does this do that she doesn't?"**
Maddie's screener catches people who apply to you. The check finds and
proves people who never applied — the ones a consultant is about to
cold-call — before the call gets made, so the emails your team wrote in
August go to people who could actually be placed, not to people who could
never clear the brief.
*Source: `transcript_2026-09-10_fathom.md` line 9; `PLAN.md` line 49; `lens_keith.md` Q4.*

**Q5. "How does this get onto my desk day to day — another page to check,
another login?"**
No new page for daily use. It lands as a field in the candidate record you
already look at — a "Shortlist Check" column reading PASS / NEAR MISS /
OUT / NOT CHECKED plus one line, with a note carrying the quotes and links
behind it. The one-page check stays only as the document that made the
pitch.
*Source: `PLAN.md` Day 2 decision (a).*

**Q6. "Who's Pat Brady, and why does the corrected list say Cork when the
brief I got said Belfast?"**
Pat Brady is Horganlynch, Cork — the August dossier itself says he joined
Horganlynch's Cork office in 1990 and only names a Belfast project; the
cache reads his location as Cork. On the check, he's OUT for Director grade
anyway — a firm's Irish office is not the same as a statement of where he
lives.
*Source: `monday_send.md` line 5; `check_results.json` row for Pat Brady (failed `located_ie` and `seniority_ceiling`).*

**Q7. "Chartership — how do you actually check that, and can I trust it?"**
Chartership requires CEng plus Engineers Ireland (MIEI or FIEI), stated in
a public source — a different body's chartership alone doesn't pass. On
your own August names, Mark Petho and Philip Penco were marked OUT partly
for this: chartered elsewhere, no Engineers Ireland evidence found. The
Engineers Ireland register itself isn't used directly yet — terms of use
are unverified — so today it's evidenced from the person's own
post-nominals and their employer's page, and the card says which.
*Source: `check_results.json` rows for Petho, Penco; `PLAN.md` "Open for day 2" item 4.*

**Q8. "Does this touch or slow down Maddie's screen in any way?"**
No. The check writes a candidate at the "Sourced" stage; Maddie's
screener's trigger stays on the stage it already uses. This still needs
confirming with Maddie that a sourced candidate doesn't fire her inbound
flow twice — that's an open item, not yet resolved.
*Source: `PLAN.md` "Open for day 2" item 5, and Day 2 decision (a).*

**Q9. "How much is this going to cost me?"**
The August demonstration cost nothing — offline, zero spend. The corrected
campaign to date cost EUR 25.69 in total for 536 people assessed, under
five cents a name, against a placement fee of EUR 14k-20k. Do not say "per
delivered card" (25.69 over 2 sounds like EUR 13 a name and is the wrong
denominator). No price is quoted
in Monday's email by design — that conversation happens on the follow-up
call.
*Source: `PLAN.md` line 33; `v2_proposal.md` "The corrected cut"; `PLAN.md` decision (c).*

**Q10. "You're telling me two consultancies produced zero candidates for
Cork. What good is that to me?"**
65 people were checked for the Cork role and none cleared every rule on the
public record reachable for free — the honest number, not a padded one.
Reaching five needs a licensed people-data source, a separate paid step not
taken without your say-so.
*Source: `monday_send.md` line 45; `v2_proposal.md` "The corrected cut", "Not in scope, deliberately".*

**Q11. "You said 5 working days to wire this in — what does that actually
involve, and what do you need from me?"**
Wiring to your Recruit CRM account, your job slugs, and a named
consultant's own sending seat — 3 to 5 working days as said on the call.
Needed from you: the seniority ceiling for the structural role, the
residence rule for Cork, and which Recruit CRM plan you're on (API access
needs Business or above; on Pro it runs through Zapier or CSV import).
*Source: `v2_proposal.md` "Build timeline"; `monday_send.md` "Two questions, one for Maddie".*

**Q12. "If I say yes and it doesn't actually improve on what I got in
August, what happens?"**
"Reply with the three answers and I will re-cut the list the same day, no
charge. If it is not a clear improvement on seniority and location, you owe
nothing and we stop here."
*Source: `monday_send.md` line 53.*

---

## 2. Maddie's questions and answers

Technical, precise, honest about limits.

**"Does a sourced candidate at 'Sourced' double-fire my inbound
trigger?"** Not answered, only flagged — that's a promise to fix it if it's
a problem, not evidence it isn't one. Real answer: unknown until she names
her trigger's actual listen-condition (stage change vs. reply event vs.
CV-arrival webhook). *Open item, `PLAN.md` item 5.*

**"Is 'verified' verified, or just the model said so and nobody
checked?"** Verified means character-for-character substring match against
a cached document by `validator.py`, deterministic, never model-based,
logged with a published drop rate (0.9% on the live campaign). It does NOT
verify the underlying fact is true or current — see next.

**"What happens when a firm's people page is stale — do I get a
confidently wrong PASS?"** Not handled and not claimed to be. The check
verifies the quote exists on the cached page, not that the page is current.
This is a genuine gap, not overclaimed, but it is also not yet disclosed on
Maddie's own page as a limit — worth adding next to "Honest limits."

**"Could I build this myself in a weekend?"** The quote-matching validator
alone — yes. The full stack — discovery/search-scoping, the typed gate
engine, CLI override plumbing, the dry-run CRM adapter with dedupe, over a
thousand tests plus a 41-check acceptance gate — is multi-week engineering.

**"Is the CRM write live or will it silently corrupt my dashboard's
data?"** Dry-run only, hard-coded default; live mode requires an explicit
key and flag, capped at 50 writes/run. No live run has happened yet — this
is a design guarantee, unverified against her real account.

**"Does this ever put an email address in front of a consultant with more
confidence than you actually have?"** No, by design. The check never
writes an email address at all — only a contact label (verified /
catch-all / guess / none), status goes in the note instead.

**"What's the actual cost and where's the ceiling if something runs
away?"** Per-name: EUR 0.00 pool match, 0.02–0.05 discovery, 0.05–0.15
extraction, optional 0.12 second opinion. Per-run and cumulative ceilings
are enforced in code with a loud stop on hit, but the ceiling values
themselves aren't stated in the docs — she may push on this.

**"Chartership check — Engineers Ireland register, scraped?"** No,
explicitly not automated: terms of use are unverified, so it's evidenced
from post-nominals and the employer's page today, and the card says which.
This is disclosed, not overclaimed.

**"How does a claim's confidence tier actually gate anything?"** Enforced
in code — only `confidence = direct` claims can satisfy a hard gate;
inferred claims are shown but never pass anything.

**"Where's the seam if I want to swap in my own scoring instead of
PASS/NEAR_MISS/OUT?"** Not designed for that today — the check emits a
fixed four-state vocabulary mapped 1:1 to CRM fields; there's no documented
schema version she could target from her own code yet.

*Places the Maddie notes overclaim or are vague (fix before her page is
finalised): (1) cache staleness is never stated as a limit on her page —
add it to "Honest limits"; (2) the "screener's trigger... unchanged" line
reads more confident on her page than the internal plan, which still lists
the double-fire question as open — align the two; (3) "the endpoint is a
thin wrapper" implies an HTTP endpoint exists — it doesn't; only JSON, CSV,
and CRM-note paths are built.*

---

## 3. Isadora's questions

**"Does this mean fewer wrong calls for me?"** For the specific failure
mode it targets, yes: the August list was 0/13 pass under Keith's own
brief, and that count is now visible before she dials. It does not reduce
wrong calls caused by anything the gates don't check.

**"Does it slow me down?"** No new page — a "Shortlist Check" field and
one-line note land directly in the candidate record she already opens.

**"What do I do with a NEAR MISS — call or skip?"** The card carries the
actual failing margin in plain language (e.g. "1 year over"), but no
worked convention for what that margin typically means for placeability —
that's a real gap, left to her judgement with no guidance supplied.

**"What if it rejects someone I know is right?"** No override or "trust
the human" path exists in the two consultant-facing artifacts today. A
real, unaddressed workflow gap — a name she vouches for personally has
nowhere to record that.

**"When a client gets sent the wrong CV, who's on the hook — me, Maddie,
or the check?"** Not answered anywhere in the four documents. Worth an
explicit accountability line before go-live: a PASS is Prodcraft's claim;
sending it to the client is the consultant's decision.

**"Does it tell me who to call first?"** No — it's a gate, not a scorer.
It narrows the pool; she still sequences her own day.

**"Will it ever contact a candidate for me?"** No — strictly no automated
sends from this stage, consistent across every document reviewed.

*Two things missing for Isadora: (1) no override/vouch mechanism; (2) no
guidance on what a NEAR_MISS margin means for callability.*

---

## 4. The end client's and the accountant's questions

### TOBIN / AtkinsRéalis (end client)

The repo has no direct TOBIN quote — only Keith's own framing, which is the
proxy used here. Five questions a client would ask if told "every name is
checked against the public record before we call":

1. "Checked against which public sources, and what happens when the
   evidence is silent?" — the gate treats silence as fail by default;
   that's a real, statable design choice.
2. "How many names did you reject to get here, and why?" — answerable
   today from the by-rule breakdown.
3. "Is chartership checked against the actual register, or the person's
   own claim?" — honestly, the person's own post-nominals and employer
   page today; register terms are unverified.
4. "What's your false-positive rate once we've interviewed them?" — **not
   in the repo.** No post-hire audit trail exists yet.
5. "Does this replace your consultants' judgment?" — no; the check gates
   before the call, a consultant still decides.

### The value model (for the accountant)

**Placement fee at risk.** EUR 14-20k (18% of EUR 80-110k). The check's
own per-role operating cost is roughly EUR 100-120 — a >100x ratio on cost
alone, before counting time saved.
*Source: `lens_money.md` §B(1); `call_brief_2026-09-10.md` §3.*

**Consultant hours, at 5 / 10 / 15 minutes per name** (`eval/time_value.py`,
`names_per_week` = 40, `hourly_cost_eur` = 45):

| minutes/check | hours/week | EUR/week | EUR/month |
|---|---|---|---|
| 5 min | 3.33 | 150.00 | 650.00 |
| 10 min | 6.67 | 300.00 | 1,300.00 |
| 15 min (assumed default) | 10.00 | 450.00 | 1,950.00 |

**`minutes_per_manual_check = 15` is an unconfirmed assumption** — Keith
gave no figure; the honest range is EUR 650-1,950/month, not a single
number, until he sets it. *(PLAN.md Day 2 decision (b): the minutes
question is deliberately not asked in Monday's email, asked live on the
follow-up call instead.)*

**The August list's own cost.** 13 names, 0 pass today's brief, 4 emails
written to people who could never be placed (`emails_written` is itself an
editable assumption sourced from the operator's own note, not a logged
field — flag this if pressed). At the 15-minute assumption: 3.25 consultant
hours (EUR 146); at 5 minutes: 1.08 hours (EUR 49).

---

## 5. The legal points

Marked per the law lens's own scale: **SETTLED** / **JUDGEMENT CALL** /
**ASK A LAWYER**.

1. **Lawful basis (Art. 6(1)(f), legitimate interest) — JUDGEMENT CALL,
   leaning settled.** Reasonably strong for public professional data, but
   there is no written Legitimate Interest Assessment on file yet. Gap to
   close before scaling: write the one-page LIA.
2. **Article 14 notice timing — SETTLED that a notice exists; JUDGEMENT
   CALL on timing** for names marked OUT and never contacted. The
   generally-published privacy notice is the right shape of answer but
   sits on a `.pages.dev` staging domain, not yet a stable branded URL —
   fix before this scales.
3. **Retention of cached page copies — JUDGEMENT CALL.** A staleness
   concept exists (governs whether evidence is fresh enough to act on) but
   no retention/deletion period is implemented — gap to close so the
   privacy notice's retention promise isn't a false statement.
4. **A "rejected, reason: grade" verdict about a named person — JUDGEMENT
   CALL.** Not Art. 22 automated decision-making (a human consultant
   always sits between the verdict and any contact). The sharper risk is
   Art. 5(1)(d) accuracy — mitigated by verbatim quote-matching, a
   published drop rate, and OCR-confusion handling, which is the actual
   answer to an accuracy challenge.
5. **Right to object / erasure — SETTLED, well-built.** The opt-out
   registry matches on person_id, email, or LinkedIn URL, checked at draft
   creation and at sync. Open item: confirm opt-out also purges already-
   cached evidence, or the "we will erase your details" promise overstates
   what the code does.
6. **An Bord Pleanála oral-hearing text reused as recruitment evidence —
   JUDGEMENT CALL, ASK A LAWYER if it scales.** Public record, but a new
   purpose from the one it was submitted for; a reasonably compatible
   re-use, not risk-free.
7. **LinkedIn — SETTLED risk, and the design mostly gets it right, with
   one open exception.** LinkedIn's terms prohibit copying profile text by
   any means, including manual copying. The original 13-name run cited
   zero LinkedIn URLs as evidence — firm pages and planning PDFs only, the
   right answer for that run. **The two delivered cards (Alicia Joyce,
   John Alcaras) do cite LinkedIn URLs and quote LinkedIn text as
   evidence** (location, chartership, and employer quotes both trace to
   `ie.linkedin.com` and `linkedin.com` posts) — this is a policy question
   for the operator to resolve with a lawyer before scaling, not something
   the Keith page itself states or needs to change. Recommend: keep
   LinkedIn to a URL reference for contact resolution going forward; any
   quoted LinkedIn text needs its own sign-off.
8. **Engineers Ireland register terms — confirmed unverified,** matches
   the repo's own flag. Correct interim posture: don't scrape it; use the
   weaker-but-safe post-nominal/employer-page signal and say which.
9. **DSAR survivability — JUDGEMENT CALL, already close to right.** The
   CRM note already carries the verdict, every rule failed with its
   reason, quotes with sources, the contact label, and the Art. 14 notice
   text — a genuinely strong DSAR artifact.

---

## 6. The competitor's attacks, counters, and open concessions

From the Recruit CRM salesperson lens — what a rep would say to keep the
renewal, with the honest counter and the concession Deb should make openly.

1. **"We already have verified emails via the Chrome extension."** Counter:
   no method or accuracy rate disclosed on their side; the check never
   claims better contact data, only honest labelling of confidence.
2. **"Our AI matching already scores 0-100 — same thing."** Counter: a
   similarity score, not a hard rule. Concede: for a large loose funnel, a
   ranked score is faster to skim than pass/fail with citations.
3. **"Just add a custom field — you don't need a whole product."** Counter
   — and Deb's strongest, most honest point: the check's whole output IS
   custom fields; Recruit CRM holds the container, it doesn't verify
   anything. Not competing capability, a target integration surface.
4. **"Your consultant can check LinkedIn in 2 minutes — why pay?"** Counter:
   the value isn't a faster LinkedIn glance, it's the parts consultants
   currently skip (chartership register, residence evidence, verbatim
   quote). Concede: "2 minutes" undersells a thorough check either way.
5. **"This is a one-man shop — what happens when he disappears?"** **Deb's
   weakest ground — concede it plainly.** No SLA, no support team, no
   redundancy. Runs offline against a cache and produces static files; the
   honest pricing answer is a project/consulting engagement with source
   delivery, not a subscription Keith bets his pipeline on.
6. **"Credits are cheaper than a consulting engagement."** Fair,
   not-fully-answerable point if Keith has spare Recruit CRM credits — the
   honest counter is that credits alone wouldn't have caught the August
   list's problem, which the record already proves.
7. **"We're GDPR compliant — you don't need someone else's compliance
   layer."** True but platform-level, not sourcing-methodology-level.
   Needs one plain sentence to Keith, not a compliance lecture.
8. **"Our sequences already handle replies."** Confirmed absence of reply
   classification on their side — but this is a v2/outbound feature, not
   part of the Shortlist Check POC. Don't let Keith conflate the two.

---

## 7. Recommended pricing shape, with reasoning

**Success-linked pilot pricing (per-role, 30-day pilot, small fixed fee, no
fee if the stated outcome is missed)** — not a flat monthly fee.

Reasoning, from the repo's own call brief: a five-person agency will accept
an outcome-gated small fee but not an unconditional fixed cost. This is
the shape already offered in the call brief's proposal rung B (EUR
1,500-2,500, under 15% of one placement fee, "no fee if missed"). The
per-niche-per-month shape (Radar spec) and the own-it/build-fee rung are
later-stage options, explicitly separate from the check itself.
*Source: `lens_money.md` §B(4); `radar_final_spec.md`; `PLAN.md` open item 6.*

---

## 8. Things on the current page that erode trust — and the fix status

From the lenses' own review of the page/email copy:

1. **"471 people checked, 2 delivered" reads as a 0.4% hit rate to a
   first-time reader** — can land as "the tool is bad at its job" rather
   than "the brief was narrow." **Fix status: not made on the Keith page**
   (the check page itself doesn't carry this ratio; it's an email-copy
   risk for Monday's send, flagged here for the operator to soften live on
   the call, not a page-render change).
2. **"Settings" language next to "a final check refuses to deliver"** can
   read as a black box overriding a recruiter's judgment. **Fix status:
   not on the Keith page** (the check page never uses "refuses to deliver"
   language; this is a `v2_proposal.md` copy risk, flagged for the
   operator's live framing, not a code change).
3. **The Cork zero-result paired immediately with the paid-upsell
   mention** can look like the failure is being used to sell a second
   step. **Fix status: not on the Keith page** (out of scope for this
   page's copy; the check page never mentions the Cork/licensed-data
   upsell at all).
4. **Staleness of the cache is never disclosed as a limit anywhere
   consultant-facing.** **Fix made on the Keith page**: the new "Questions
   you will have" section states plainly that "a person can change firms
   or be promoted after that date, so the date checked travels with the
   proof rather than being hidden."
5. **No score-versus-check line existed on the page before Day 2.** **Fix
   made**: the new "Why proof, not a score" section states it in four
   short paragraphs, with the "0 of 13" figure computed from the real
   data, not hardcoded.
6. **No answer for "what does a NEAR MISS mean for callability" anywhere
   Isadora-facing.** **Fix status: not made** on the Keith page (this is a
   consultant-workflow gap, correctly scoped to Isadora's own tooling —
   the CRM note — rather than the pitch document; flagged in §3 above for
   a separate fix).
7. **No override/vouch mechanism for a consultant who personally knows a
   rejected name.** **Fix status: not made**, correctly scoped as a future
   CRM-workflow feature, not a Keith-page copy fix.

---

## 9. The yes-sentence

"You said the August list was too senior and some weren't in Ireland — you
were right on both, and now every name on the list carries the exact
sentence and the link that proves it, or the exact reason it's out, so
you're never handed thirteen maybes to call through again."
*(`keith_copy.md` verdict framing; `monday_send.md` lines 5, 21;
`check_results.json` per-row evidence contract; `PLAN.md` line 7.)*
