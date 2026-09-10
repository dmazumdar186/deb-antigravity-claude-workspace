# Keith Molony call brief — Thu 10 Sep 2026, 17:00, 15 minutes

Panel-revised (customer POV, engineering rigor, Saraev automation doctrine, offer design, adversarial/compliance). Single deliverable for the operator to read before dialling.

## 0. Five facts to have memorised

| Fact | Number | Source |
|---|---|---|
| Delivered 20 Aug | 13 candidates: 10 of 10 Senior Structural Engineer, 3 of 5 Transport Major Projects Manager (Cork) | dossier, HANDOFF §1 |
| Grade of the 10 Role 1 candidates | 6 titled Director, 4 titled Associate Director. All ten. Role 2: Archer and Sutton Director, Healy title not stated | live dossier titles, candidates.json |
| Not resident in Ireland | 4 named: Taskov, Petho, Penco (Barrett Mahony London), Brady (Horganlynch Belfast) | dossier text |
| Contactability | 5 of 13 emails were inferred, never verified; 1 had none; 11 of 13 flagged low movability by our own tool; recommended first channel was LinkedIn, Keith emailed | dossier |
| Role 2 pool | 21 assessed, 4 passed all gates, 3 delivered, 4 near-misses at Jacobs missing only chartership evidence, 4 client-side (TII, CIÉ, Iarnród Éireann) deliberately parked | pool_map_role2 |

Note on "50 sent": no artifact in the workspace supports 50; every file says 13. Use 13 on the call.

## 1. Why it went wrong, in Keith's words

1. Too senior: our seniority filter was a floor (8 and 10 years minimum) with no ceiling, and it treated a Director title as proof of experience. Ten out of ten Role 1 candidates are Director or Associate Director.
2. Not in Ireland: our residence filter accepted "worked on an Irish scheme" as proof of living in Ireland. That let three London-based and one Belfast-based engineer through.
3. Underneath both: the sources we searched (consultancy leadership pages, oral-hearing expert witnesses) are senior by construction. Filters fix the list we had; reaching 8 to 15-year engineers needs a second source layer (licensed people-data plus the Engineers Ireland register).
4. Outreach: four emails to a director-heavy list, several to inferred addresses, is not a test of the approach. Ask whether the three silent ones bounced or opened.

Say first, verbatim: "You were right on both. Both were filter settings; here is exactly why." Never say AI, platform, system, automated, or 2.3x. Say the filter, the list, corrected, verified, checked by hand.

## 2. The 15 minutes

0 to 2: acknowledge. The two facts above, four names for the location miss. No defence.

2 to 8: brief questions. Write answers straight into the Brief Controls page.
1. Seniority ceiling for Senior Structural Engineer: Senior Engineer only, or Principal/Associate acceptable? Years band? Salary band for the role (this is the real ceiling proxy).
2. Ireland rule: resident in the Republic only? For the Cork role, what commute radius? Returning-diaspora relocators yes or no? Northern Ireland no?
3. Chartership: hard requirement, or "working towards" acceptable?
4. Employers to target and to avoid, beyond AtkinsRéalis and TOBIN.
5. Why would a candidate move: what is the pull for this role (project, hybrid, salary), and who else is approaching them? This is what makes a candidate placeable.
6. Which one or two live roles matter most this month (site lists Senior Civil Engineer Roads and Transport, Dublin; Principal EIA Consultant, Cork; Senior Flood Risk Consultant, Meath; Senior Resident Engineer, Louth).
Not on the call (follow-up email): who sends and which LinkedIn seats; whether the three silent emails bounced; ATS for CSV import.

8 to 11: Brief Controls, under two minutes. Set the ceiling and the Ireland rule to his answers on his own 13 candidates and let him watch the London and Belfast four and the Director names drop. Then show the "missed by one" list: those are the first people the corrected run re-examines. Do not tour the interface.

11 to 15: one offer, one close.
Offer: "You'll have a corrected shortlist, Senior Engineer grade only, verified Ireland residence, verified contact, in your inbox by Saturday 17:00, at no cost."
Honesty clause (adversarial lens): "Role 1 is a filter re-run and lands in hours. Role 2 needs new sources, not new filters: the pool only ever had four who passed everything. I'll send the Role 1 correction plus a best-effort Role 2 update and tell you exactly how many converted."
Guarantee: "If it is not a clear improvement on seniority and location, you owe nothing and we stop here."
Close: "Can I send it to this address by Saturday 5pm, and can we take 20 minutes Monday to go through it together?" Book the Monday slot on the call.

Objections, one line each:
- "We use LinkedIn Recruiter." Recruiter finds who is visible; this finds who is chartered and grade-matched but not job-hunting. Different layer, not a replacement.
- "My consultants won't use it." They never touch it: a CSV into your ATS, and the note goes from a named consultant's own LinkedIn seat.
- "You're one person." That is why the corrected list costs nothing to test. You are committing 48 hours, not headcount.
- GDPR: every candidate gets the Article 14 notice with the source cited; it is already live. Add, if asked: the notice currently sits on our domain, not Gaia's; fixable, not yet fixed. Any LinkedIn message goes from your own seat under your name; we never send.

## 3. What to build: Gaia sourcing v2

Principle: the brief is a first-class, structured object Keith sets; every source and gate serves it. Keep everything that worked: verbatim-quote evidence trail (0.9% drop rate), deterministic gates, honest pool map, Art. 14 notice, sub-€1 LLM cost per run, 550+ tests.

Brief Contract (confirmed back in writing before any search): seniority band (min years, max years, max grade, excluded titles, salary band); location rule (Republic only, county list, direct residence evidence required, relocation flag, NI flag); chartership requirement and accepted registers; target and off-limits employers; sender and channel; delivery cadence.

| Stage | Was | Becomes |
|---|---|---|
| Brief | hand-written spec | Brief Contract with seniority band and location rule; CLI overrides; composition guard that refuses to deliver a list whose grades or locations violate the brief (the one-line check that would have caught this) |
| Sources | oral hearings, consultancy bio pages | plus licensed structured people data (PeopleDataLabs or Crustdata, Apollo as a cheap test) for the 8 to 15-year grade; Engineers Ireland Find-a-member, IStructE and ICE directories for chartership (converts the four Jacobs near-misses). No scraping; Proxycurl died in a LinkedIn lawsuit in July 2025 |
| Gates | seniority floor; scheme-based residence | seniority ceiling (grade ladder plus max years); direct residence evidence; county lists; relocation flag |
| Contact | inferred addresses shipped | verified or catch-all only; inferred demoted to "needs lookup"; LinkedIn URL resolved for every delivered card |
| Movability | LLM guess, mostly unknown | tenure from job-history dates where the data exists, LLM fallback marked unknown otherwise; a ranking hint, never a silent drop |
| Outreach | LLM-drafted, agency voice | human-approved template pool with four fuzzy variables (project they gave evidence on, scheme, firm, chartership year), under 400 characters for LinkedIn, sent by a named Gaia consultant from their own seat, email only to verified addresses, one follow-up at day 7 |
| Feedback | none | 100% review of every delivered candidate by Keith's team (thumbs and reason); thresholds only retuned against a frozen labelled eval set of the 158 Role 1 profiles, never from five thumbs |
| Delivery | static dossier | dossier with Brief Controls and CSV; no auto-notification of bad news, a human delivers it |
| Ops | none | error channel (service / environment / error / count) into Gaia's Slack or WhatsApp; self-healing note after three repeats |

Maturity: a skill Deb runs per role (rungs A and B). Gaia self-triggering it is a later step, after the gates prove themselves without review.

Cost per role with paid APIs: LLM ≈ €13 (Sonnet extraction ≈ €4, Fable judge and messages ≈ €9), OCR €5 to 15, people data ≈ €60 to 80 for 300 profiles, Prospeo ≈ €2, search ≈ €5. About €100 to €120 all-in against a placement fee of €14k to €20k (18% of €80k to €110k). Tooling cost is not the constraint; precision and reply rate are.

Verify before promising: run one €10 live query on PDL, Crustdata and Apollo for "chartered engineer, Cork" and count structured hits. Check Engineers Ireland Find-a-member terms before automating. Write a legitimate-interest assessment for licensed people data; say on the call it is pilot scope, not something warranted today.

## 4. Proposal rungs (follow-up email only, after the corrected list lands)

A. Corrected shortlist, free, Saturday 17:00. Sample of 5 within 24 hours for thumbs, full list at 48 hours. Dossier, CSV, Brief Controls.
B. Pilot, 30 days, 3 live roles. Small fixed fee (suggested €1,500 to €2,500, under 15% of one placement) with the success metric stated up front (10 approved candidates and 2 first conversations per role) and no fee if missed. Success-linked beats flat monthly for a five-person agency.
C. Own it, only after B works: build fee (suggested €6k to €9k), APIs at cost (about €100 per role), optional €200 to €300 per month maintenance, hosted under a Gaia domain, code owned by Gaia, no per-seat fees. Not raised on this call.

## 5. Demo: before, during, after

Before (now): Brief Controls page, the 13 real candidates plus the pool map, live ceiling and Ireland controls, per-candidate reasons, missed-by-one list. Private link.
During: set his answers live; the drop-outs are the proof. Copy the Brief Contract text from the page into the follow-up email.
After: (1) tonight, on the operator's Windows machine where the cached extract lives, re-run the gate stage with the new thresholds (offline, no API cost) and re-render; (2) tomorrow, with API keys, the Engineers Ireland lookup on the four Jacobs near-misses and a first licensed people-data pull for the right grade; (3) Saturday, dossier v2 with Brief Controls and CSV, plus a one-paragraph honest count per role.

Blockers the operator must clear: laptop access in the next 48 hours (cache is local, not in git); API balances (Anthropic was at €0 on 20 Aug; OpenRouter ~$2; Prospeo 1,992 credits); ~€100 for people-data and register lookups.

## 6. Honest gaps
- No repo artifact supports "50 sent"; the delivered set was 13.
- People-data coverage of Irish chartered engineers is unverified until the €10 test.
- Engineers Ireland register scrapeability and terms unverified.
- Role 2 cannot reach 5 by filtering; it needs the new sources.
- Lawful-basis write-up for licensed people data not yet done.
- The Article 14 notice sits on a prodcraft domain.
