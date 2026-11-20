# Panel C: offer, honesty, operations (2026-11-20)

Blind review. Start position: the plan is wrong until shown otherwise. Paths are relative to `deliverables/greenjobs_migration_2026-11-06/`. Contract, payment and legal terms are out of scope.

## Lens 1: Alex Hormozi (offer and value)

1. **The offer is a downgrade sold at a new price.** On 3 Dec Keith gets the same boards with fewer features: no self-posting for CHM and Mattinson (REVIEW:21), no candidate or employer logins (transition_plan.html:31), and alerts first in the trim order (transition_plan.html:33). His dream outcome is "zero downtime and no lost data" plus less hassle (FEASIBILITY:29). Today the plan gives him more hassle.
2. **Time to value is zero until 3 Dec.** Nothing is deployed (FACTS:41). Put a live test site in front of him this week.
3. **What would make it a no-brainer:**
   - (a) Post once. Pull Gaia's jobs from gaiatalent.com (WordPress jobs post type, FACTS:22) so Rashieda stops double posting. First confirm the overlap (FACTS:23).
   - (b) Keep the 8 network sites alive as sector views of the same database. Advertisers are paying for this today (FACTS:21).
   - (c) Send alerts from day one, because they are a paid feature (FACTS:20).
   - (d) We run the exports ourselves.

## Lens 2: Dario Amodei (honesty and exposure)

1. **The plan promises "job alert emails" on 3 Dec (transition_plan.html:30), then trims them first (:33).** The alerts are sold to advertisers (REVIEW:34). Say plainly that alerts are at risk, or commit to them and trim something else.
2. **The 8 network sites go dark on 6 Dec (REVIEW:33).** The plan only offers to "quote separately" (transition_plan.html:37). Keith has not been told that a sales promise to his employers will break.
3. **The client has not seen the real odds.** Internally the odds are 40/100 (REVIEW:90), access is 5/100 and data safety is 15/100 (REVIEW:86,88). The email still uses dates that have already slipped (EMAIL:11; REVIEW:43).
4. **Data protection.**
   - The interim rule is "download everything as a raw archive" (REVIEW:20). That covers about 178k candidates (FACTS:17), against Strategies' own retention warning (thread:12).
   - Members data carries `Consent` and `Marketing` fields (FACTS:34). Alerts must go only to people where Marketing is yes, and that is a build-time filter.
   - Nothing personal moves before the DPA is signed.

## Lens 3: Daniela Amodei (operations, people, trust)

1. **I count about 14 asks on Diana and Rashieda.**
   - 12 questions (transition_plan.html:37-48).
   - 6 exports × 2 sites, in batches (FACTS:33). The profile export only runs outside 09:00-17:00 UTC (REVIEW:19).
   - Header samples (REVIEW:47).
   - 3 registrar logins through a password manager that Diana does not know how to use (SOURCE_diana:7), with login codes relayed from the info@ inboxes (FACTS:29).
   - A Cloudflare account and a storage account (REVIEW:48; transition_plan.html:33).
   - Test-site sign-off (:22).
   - The final export and a 17:00 posting freeze (REVIEW:53).
   - A console test on switch day (CUTOVER_RUNBOOK:92).
   - Posting for CHM and Mattinson (REVIEW:21).
   - Candidate password resets later (FEASIBILITY:100).
2. **Diana is a non-technical finance administrator (FACTS:12).** Every step that needs her is a single point of failure (REVIEW:77-78).
3. **Trust was damaged when her answers were sent to the wrong inbox and she was asked them again (REVIEW:35).** Ask her for fewer things, and schedule them, instead of asking her to do more.

## VERDICT: AMEND

Keep the tested build. Change who carries the work: our team, not hers.

## The 5 changes that most cut client staff hours

1. **We run every export.** Diana logs in once on a screen-share. We script the batches and run the profile export outside 09:00-17:00 UTC. The files land in storage owned by GreenJobs.
2. **One 60-minute DNS session replaces the password-manager ask.** Diana logs in and reads the codes aloud, and we make the changes. Nameserver and web switches go in a second scheduled slot.
3. **Gaia's jobs are imported automatically from gaiatalent.com.** This applies once double posting is confirmed. It is the largest recurring saving.
4. **CHM and Mattinson get their own console logins through Cloudflare Access.** This removes their posting from Rashieda's plate and keeps their contracts whole.
5. **All live jobs are imported automatically and the freeze is cut to hours.** Network domains forward to sector pages and alerts send to Marketing = yes subscribers, with no staff action.

## Claim → Objection → Resolution

- **Claim:** for €600 a month we do the migration, and staff give one call and one sign-off.
- **Objection:** the logins and codes are Diana's, and holding admin access before a DPA widens our exposure.
- **Resolution:** amend. Two scheduled screen-share sessions, the DPA first, and candidate data held in a raw archive only until Keith decides retention.
