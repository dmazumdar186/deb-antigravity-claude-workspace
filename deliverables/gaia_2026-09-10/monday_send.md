# Monday send — Keith Molony, Gaia Talent (Mon 14 Sep 2026, before 17:00)

Two things the operator sends: the email (§1) and the Loom it links to (§2, script).
Facts come from `deliverables/gaia_2026-09-14/` (campaign `gaia-2026-09-14`) and the runbook §1c.
Words never used with Keith: AI, platform, system, automated, 2.3x. Say: the filter, the list, corrected, verified, checked by hand.
No price in this email; the follow-up call does that.

Before sending, fill the two placeholders: `{LOOM_URL}` and, if a Monday call slot was booked on Thursday, the time in the last line.

## 1. Email

**To:** Keith Molony
**Subject:** Corrected shortlist — Senior Structural (Dublin/Limerick/Galway) and Transport (Cork)

Keith,

As promised on Thursday. Three links, one short video, then the honest numbers.

- Corrected shortlist: https://claude.ai/code/artifact/16f9282e-e30e-4a4b-b6e2-624d836a7e80
- Brief Controls (your 20 August list with the two filters you can set yourself): https://claude.ai/code/artifact/3d47597e-04bd-42ec-bb15-ce6126b93703
- The page for Steph, on where this hands over to Maddie and Recruit CRM: https://claude.ai/code/artifact/bc97d901-68da-4a96-9888-538dd8c65eed
- Loom, 5 minutes: {LOOM_URL}

Could you forward the third link to Steph? It is written for her.

**Where the corrected list stands**

Senior Structural Engineer: 471 people checked, 2 delivered against the 10 asked for. Alicia Joyce at CSEA and John Alcaras at Arcadis. Both are Senior Engineer grade, both chartered with Engineers Ireland, both with a direct statement in their own words that they are based in Dublin. The quote is on the card.

Transport Major Projects Manager, Cork: 65 checked, 0 delivered against the 5 asked for.

I would rather send you two right names than ten wrong ones again, so that is what this is. The rules now doing the cutting:

- Residence: only a statement of where the person lives counts ("based in Dublin", "Location: County Meath"). Working on an Irish scheme, or a firm's Irish office, no longer counts. The London and Belfast four from 20 August fall out on this rule.
- Seniority: a ceiling as well as a floor, read from the title and from what their employer says about them. Head of Design, Associate, Director and above are out.
- Chartership: CEng plus Engineers Ireland (MIEI/FIEI) needed. MIEI alone, or ICE/IStructE alone, does not pass.
- Contact: verified or labelled. Alicia has no verified email, so her card says "none, call the firm" rather than a guessed address.

The near-misses are listed under each role. For the structural role: 14 people missing only residence evidence, 9 missing only chartership evidence. Those are the first people re-examined once the two questions below are answered.

The Cork role cannot reach five by filtering. The pool we searched (consultancy leadership pages, oral-hearing witnesses) is senior by construction. Reaching Cork-based transport leads at the right grade needs a licensed people-data source, which is a separate, paid step I have not taken without your say-so.

**Two questions, one line each, and one for Steph**

1. Seniority ceiling for the structural role: Senior Engineer only, or is Principal / Associate acceptable? A salary band answers this best.
2. Ireland rule: resident in the Republic only? For Cork, what commute radius, and are returning relocators in or out?
3. For Steph: which Recruit CRM plan are you on? API access needs Business or above. On Pro, the hand-off runs through Zapier or the CSV import, which is fine, just a different wire.

Reply with the three answers and I will re-cut the list the same day, no charge. If it is not a clear improvement on seniority and location, you owe nothing and we stop here.

Talk Monday {TIME} if the slot still works, otherwise say when.

Deb

---

## 2. Loom script (target 4:30, hard cap 5:00)

Screen setup before recording: three tabs in this order: Brief Controls, corrected shortlist, v2 page. A terminal at `execution/` with `GAIA_CAMPAIGN_ID=gaia-2026-09-14` exported and font large enough to read. Camera on, small. No intro slide.

### Step 1 (0:00–0:45) — "You were right on both"

On screen: Brief Controls, untouched, showing the 20 August 13.

Say: "Keith, you said two things on Thursday and both were right. First, the list was too senior: ten out of ten on the structural role were Director or Associate Director. That was our filter, it had a floor and no ceiling, and it treated a Director title as proof of experience. Second, four were not in Ireland: Taskov, Petho, Penco in London, Brady in Belfast. That filter accepted 'worked on an Irish scheme' as living in Ireland. Both were settings. Here is what changed."

### Step 2 (0:45–1:45) — Brief Controls, the re-cut

On screen: Brief Controls. Set the seniority ceiling to Senior Engineer. Then set the Ireland rule to Republic only, direct evidence required.

Say: "This is your 20 August list with the two rules as controls. Ceiling to Senior Engineer." (Watch the Director and Associate Director names drop.) "Ireland rule to Republic, direct evidence." (Watch the London and Belfast four drop.) "What's left is the 'missed by one' list: each name and the single thing it was missing. You can set these yourself; nothing here needs me."

Do not tour the interface. Two control changes, then move on.

### Step 3 (1:45–2:45) — The corrected dossier

On screen: corrected shortlist tab. Scroll to the banner counts, then open Alicia Joyce's card, then John Alcaras's card, then the near-miss list, then the CSV link.

Say: "The corrected run. Structural role: 471 checked, two delivered. Alicia Joyce at CSEA, John Alcaras at Arcadis. On each card the first two lines are the evidence: the residence quote and the chartership quote, verbatim, with the source. Alicia has no verified email, so the card says so and says call the firm; no guessed addresses this time. Cork role: 65 checked, zero delivered. I am not going to pad that. Below the cards, the near-misses: 14 short only on residence evidence, 9 short only on chartership. The CSV is the same rows for your ATS."

### Step 4 (2:45–3:45) — The hand-off

On screen: terminal. Run the dry-run sync, then the reply classifier. Then switch to the v2 page, section "What Steph needs to know".

```
python3 -m gtm_client_workflows.gaia_sourcing.run --stage sync_crm
python3 -m gtm_client_workflows.gaia_sourcing.run --classify-reply "Thanks, not looking right now"
```

Say: "This is where it meets Recruit CRM. Dry-run first: each delivered card becomes a candidate on the job, deduplicated on email or LinkedIn URL, never overwriting a consultant's data, with the evidence note and the Article 14 notice date. A reply comes back and gets classified: interested, not now, no, question, bounce. 'Not now' snoozes 90 days and writes a note. 'Interested' sets the stage you choose, and Maddie or Isadora take it from there, exactly as they do for applicants. Nothing sends on its own; a named consultant sends from their own seat. The page for Steph has the fields and endpoints."

### Step 5 (3:45–4:30) — What I need from you

On screen: back to Brief Controls, cursor on the two controls.

Say: "Three lines back from you. One: seniority ceiling for the structural role, Senior Engineer only, or Principal and Associate too; a salary band is the cleanest answer. Two: the Ireland rule, Republic only, and for Cork the commute radius and whether relocators count. Three, for Steph: which Recruit CRM plan you are on, because API access starts at Business. And if you tell me which two live roles matter most this month, those run next. That's it. Thanks Keith."

Stop recording. Paste the link into `{LOOM_URL}` above.

### Recording notes

- If the terminal is not available on the recording machine, skip the two commands and show the audit-log excerpt in the v2 page instead; the words in Step 4 still hold.
- Do not say Saturday. Thursday's call promised Saturday 17:00; the handoff moved it to Monday 17:00. If it comes up: "took the extra day to check both cards by hand."
- Lead image for the email if a client wants one: Alicia Joyce's card (residence and chartership quotes visible).
