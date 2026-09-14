# Keith's lens on the Shortlist Check — questions, objections, trust risks

Grounded only in: PLAN.md, transcript_2026-09-10_fathom.md, monday_send.md, check_results.json, recruit_crm_capabilities_2026-09.md, v2_proposal.md. Banned words enforced throughout (never used on anything Keith reads): AI, LLM, model, platform, pipeline, automated, system, agent.

---

## 1. The 12 questions/objections, ordered by deal-killing likelihood

### Q1. "Julia's email this morning already gives me 0-100 match scores over 800 million profiles. Why do I need to pay you for the same thing?"
**Answer:** Recruit CRM's own pages describe one holistic score with no documented way to enforce a hard rule like "must be chartered" or "must live in County X" — a non-qualifier is down-weighted, not removed (`recruit_crm_capabilities_2026-09.md` §3, §"What a verification layer could add" item 1). A score tells you how similar a person looks to the brief. The check tells you whether they actually clear it — grade, residence, chartership — and shows you the sentence that proves or fails it, with the link. (`v2_proposal.md` "What Gaia has today"; day-2 note in `PLAN.md` item 7: "a score says how similar, a check says whether, and why.")

### Q2. "Is this actually a value add, or is this another AI headspace thing taking us from our ABCs?" (his own words, repeated)
**Answer:** It ran on your own August 13 names, offline, for zero cost (`PLAN.md` "The demo that costs nothing"), and it told you what you already knew by eye: none of the 13 clear a Senior Engineer ceiling, and none has a residence statement. That is not a new headspace — it is your own read, checked name by name with the receipt attached. (`PLAN.md` lines 33-40; `check_results.json` summary: pass 0, near_miss 2, out 11.)

### Q3. "Last time you sent me 13 names and every one was wrong. What's different this time?"
**Answer:** Your written feedback was "too senior, some not in Ireland" (`monday_send.md` line 5, `transcript_2026-09-10_fathom.md` line 7). The check now applies a ceiling as well as a floor on seniority, and only a direct statement of residence counts — a firm's Irish office or an Irish project no longer does. Run again under those two rules, the same August 13 stay at 0 pass, which matches your own judgment; the corrected search under the wider pool returned 471 checked / 2 delivered for structural and 65 checked / 0 delivered for the Cork role. Two real names, not thirteen maybes. (`monday_send.md` lines 21, 30-45.)

### Q4. "Maddie already flags anyone over 60 and gets them on a call. What does this do that she doesn't?"
**Answer:** Maddie's screener catches people who apply to you (`transcript_2026-09-10_fathom.md` line 9, `v2_proposal.md` "What Gaia has today"). The check finds and proves people who never applied — the ones a consultant is about to cold-call — before the call gets made, so the four emails your team wrote in August go to people who could actually be placed, not four who could never clear the brief. (`PLAN.md` line 49: "4 emails written to 4 people who could never be placed on that brief.")

### Q5. "How much is this going to cost me?"
**Answer:** The August demonstration cost nothing — offline, zero spend (`PLAN.md` line 33: "offline, zero model spend"). The corrected campaign to date cost EUR 25.69 total, about EUR 13 per delivered card at this pool size, against a placement fee of EUR 14k-20k (`v2_proposal.md` "The corrected cut" and "Build timeline"). No price is quoted in Monday's email by design — that conversation happens on the follow-up call (`monday_send.md` line 7, `PLAN.md` decision (c)).

### Q6. "You're telling me two consultancies produced zero candidates for Cork. What good is that to me?"
**Answer:** 65 people were checked for the Cork role and none cleared every rule on the public record reachable for free — the honest number, not a padded one. Reaching five needs a licensed people-data source, which is a separate paid step not taken without your say-so (`monday_send.md` line 45; `v2_proposal.md` "The corrected cut" and "Not in scope, deliberately"). That is the same honesty test you're applying to the score email this morning — it counts what it rejected and says why, rather than showing you a shortlist that quietly excludes the losers.

### Q7. "Who's Pat Brady, and why does the corrected list say Cork when the brief I got said Belfast?"
**Answer:** Pat Brady is Horganlynch, Cork — the August dossier itself says he joined Horganlynch's Cork office in 1990 and only names a Belfast project; the cache reads his location as Cork (`monday_send.md` line 5). On the check, he's OUT for Director grade anyway — a firm's Irish office is not the same as a statement of where he lives (`check_results.json` row for Pat Brady: failed on both `located_ie` and `seniority_ceiling`).

### Q8. "Does this touch or slow down Maddie's screen in any way?"
**Answer:** No. The check writes a candidate at the "Sourced" stage; Maddie's screener's trigger stays on the stage it already uses. This still needs confirming with Maddie that a sourced candidate doesn't fire her inbound flow twice — that's an open item, not yet resolved (`PLAN.md` "Open for day 2" item 5, and decision (a): "Nothing of ours is drawn on Maddie's screen; her dashboard shows the field like any other.")

### Q9. "How does this get onto my desk day to day — another page to check, another login?"
**Answer:** No new page for daily use. It lands as a field in the candidate record you already look at — a "Shortlist Check" column reading PASS / NEAR MISS / OUT / NOT CHECKED plus one line, with a note carrying the quotes and links behind it. The one-page check stays only as the document that made the pitch. (`PLAN.md` decision (a).)

### Q10. "Chartership — how do you actually check that, and can I trust it?"
**Answer:** Chartership requires CEng plus Engineers Ireland (MIEI or FIEI), stated in a public source — a chartership with a different body (IStructE, ICE) alone does not pass. On your own August names, Mark Petho and Philip Penco were marked OUT partly for exactly this: chartered elsewhere, no Engineers Ireland evidence found (`check_results.json` rows for Petho, Penco). The Engineers Ireland register itself isn't yet used directly — terms of use are unverified — so today it's evidenced from the person's post-nominals and their employer's own page, and the card says which (`PLAN.md` "Open for day 2" item 4).

### Q11. "You said 5 working days to wire this in — what does that actually involve, and what do you need from me?"
**Answer:** Wiring to your Recruit CRM account, your job slugs, and a named consultant's own sending seat — 3 to 5 working days as said on the call (`v2_proposal.md` "Build timeline"). What's needed from you: the seniority ceiling for the structural role (Senior Engineer only, or Principal/Associate too — a salary band answers it best), the residence rule for Cork (commute radius, relocators in or out), and which Recruit CRM plan you're on, since API access needs Business or above — on Pro it runs through Zapier or CSV import instead (`monday_send.md` "Two questions, one for Maddie").

### Q12. "If I say yes and it doesn't actually improve on what I got in August, what happens?"
**Answer:** "Reply with the three answers and I will re-cut the list the same day, no charge. If it is not a clear improvement on seniority and location, you owe nothing and we stop here." (`monday_send.md` line 53.)

---

## 2. Three things on the current check page/email that would make Keith trust it LESS

1. **The email's own line: "471 people checked, 2 delivered against the 10 asked for."** Read cold by a recruiter who is not techie, this reads as a 0.4% hit rate — it can land as "you looked at 471 people and found me two," which sounds like the tool is bad at its job rather than honest about the brief being narrow. Nothing in the source material softens this framing for a first-time reader; it needs the spoken context ("I'd rather send you two right names than ten wrong ones") to land as a strength rather than a confession. (`monday_send.md` line 34.)

2. **"Both are now brief settings you set per role" (v2_proposal.md, "What went wrong" section) sitting next to "A final check refuses to deliver a list whose titles or locations break the brief."** To Keith, "settings" and "a final check" that "refuses to deliver" sounds exactly like a black box overriding a recruiter's judgment call — a decision made for him, not with him — which is the opposite of "not a techie guy, give me plain words." (`v2_proposal.md` line 18.)

3. **The Cork section's honesty ("65 checked, 0 delivered... the pool has no Cork-based, chartered transport lead on the public record we can reach for free") paired immediately with "reaching five needs a licensed people-data source... I have not taken without your say-so."** Read fast, that's an unprompted upsell attached directly to a zero-result outcome — it can look like the failure is being used to sell a second paid step, which undercuts the "I would rather send you two right names than ten wrong ones" trust move made one paragraph earlier. (`monday_send.md` lines 34, 45; `v2_proposal.md` "Not in scope, deliberately.")

---

## 3. The single sentence that would make Keith say yes

"You said the August list was too senior and some weren't in Ireland — you were right on both, and now every name on the list carries the exact sentence and the link that proves it, or the exact reason it's out, so you're never handed thirteen maybes to call through again." (Grounded in `monday_send.md` lines 5, 21; `check_results.json` per-row `one_line` + `evidence`/`source_url` structure; `PLAN.md` line 7.)
