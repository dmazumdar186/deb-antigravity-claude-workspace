# Briefing: GreenJobs in plain words (20 Nov 2026)

This is for Debanjan. It says what is going on, what we decided and why, what is built, what is next, and how we will know it works. The legal and money side is yours and is not covered here.

---

## 1. The situation in one paragraph

Keith's company, Gaia Talent, owns two job websites: greenjobs.ie (Ireland) and greenjobs.co.uk (UK), plus 8 small "sector" websites, such as windjobsuk.com and solarjobsuk.com. All of them run on an old system from a company called Strategies. **Strategies switches them off on Sunday 6 December 2026.** If nothing replaces them by then, all 10 websites go dark and the data inside them (jobs, employers, candidates) becomes hard to get back. Our job is to move everything to a new home before that date. We aim to switch on Thursday 3 December, which leaves a day to fix problems.

## 2. Who is involved on their side

- **Keith**: the boss. He signs.
- **Diana**: finance administrator. She holds the logins for the domain names. She is not technical.
- **Rashieda**: posts the jobs.
- **Two client companies, CHM Recruit and Mattinson Partnership**, post their own jobs today. Their contracts run to January 2027, so they must still be able to post after the switch.

## 3. The most important thing we found

Gaia posts each job twice, by hand. It goes up once on Gaia's own website (gaiatalent.com) and is typed again on GreenJobs: **81 of Gaia's 83 jobs are on both.** That is wasted staff time every week. We built a robot that reads Gaia's website and puts the jobs on GreenJobs automatically, so Rashieda posts once.

## 4. The big decision: buy the website, build the automation

**Before (the old plan):** we would write the whole job website ourselves.

**What the 12-person advisory panel found when we tested that plan:**
- A job posted by staff never actually appeared on the website. The link between the two was never built.
- The "Apply" buttons pointed to the old Strategies pages, which die on 6 December.
- It would have given staff *more* work, not less: about 20 hours a month against about 14 today. These are estimates.
- Only Debanjan could ever fix it.

**Now (the new plan):** rent a ready-made job-board website, Cavuno, which costs about $39–79 a month per board, and build only what is special to GreenJobs around it:

| Ready-made (Cavuno does it) | Built by us (our automation) |
|---|---|
| Job pages, search and apply buttons that work on phones | The robot that copies Gaia's jobs automatically |
| Employers posting their own jobs (CHM and Mattinson keep doing this) | Moving the old data from Strategies into the new site |
| Job alert emails to candidates | Forwarding the 8 sector websites to the right job lists |
| Google for Jobs listing | Moving the 10 domain names safely, without breaking email |
| Exporting everything if Keith ever wants to leave | A daily health check and a weekly 5-line report to Keith |

**Why buy:** it already works, it is cheaper to run, anyone can maintain it, and it is ready in days rather than weeks. With 13 days left, that matters most.

**The catch, and how we handle it:**
- Cavuno stores data in the US. That is legal under standard EU contract clauses (plus the UK version for UK data). We also keep the data that goes there small: applications go straight to each employer's own email or link, and we **do not** upload the ~178,000 old candidate records. Those stay in a private archive that GreenJobs owns.
- Job alert subscribers must re-confirm. We will lose some, but this is the safe position under privacy law.

**The test before we commit (Mon 23 – Tue 24 Nov, free 14-day trial, no card):** 8 checks must pass. They include: applying works on a phone, Gaia's jobs arrive without duplicates, alerts arrive, the sender email passes spam checks, and a full export works. If any check fails, we fall back to finishing our own build, and that must pass its full test by Mon 30 Nov.

## 5. No calls, no passwords

Diana never has to join a call or send us passwords:

- **Domain names.** She gets a one-page guide per company (Hosting Ireland, Lets Host, 123 Reg) with exact values to copy and paste, and a date for each step. A robot watches the public internet every 10 minutes and emails her "done, checked" when a domain has moved.
- **Old data.** Once the paperwork is signed, she sends one Strategies login once, through a link that self-destructs. Our robot downloads everything at night and puts it in GreenJobs' own storage. Then the password is changed.

## 6. What is already built (all tested, all saved)

| Piece | What it does | Status |
|---|---|---|
| Data importer | Reads Strategies' exact column names (from Diana's 19 Nov files) | 219 tests pass |
| Apply by email or link | Each job sends applicants to its own email or website | Built |
| Gaia job robot | Copies Gaia's jobs, matches categories, spots duplicates | Built, measured |
| Domain map | Every record for all 10 domains, found from public sources | Done |
| Old-to-new address map | ~1,200 old web addresses mapped so Google traffic is not lost | Done, gaps listed |

## 7. How we know it works (measurements)

Every number is checked by a script, never by an AI judging itself. Debanjan gets a daily status page; Keith gets a 5-line weekly email.

| We measure | Good enough means |
|---|---|
| Nothing lost in the move (jobs, employers, applications) | 100% arrived |
| Old web addresses still lead somewhere | 99% or more |
| All 10 websites up | 99.5% of the time |
| Email still works on every domain | No change, test email arrives |
| A new job appears on the site | Within 15 minutes |
| Gaia jobs arrive by robot, not by hand | 95% or more |
| Staff time per month | Under 4 hours (about 14 today, estimated) |
| Applications reach the employer | 99% or more |
| Alerts only to people who said yes | Zero mistakes, ever |
| Jobs show up on Google for Jobs | 100% |
| Google search traffic recovers | 90% of before, by week 6 |

**The AI parts** are checked against a hand-labelled answer sheet.

- **Job type:** an independent second checker agreed 82 of 83 times. Confirmed.
- **Sector and region:** cannot be measured honestly yet, because GreenJobs has no fixed list of sectors to check against. Until that list exists, the robot suggests a sector and Rashieda confirms it with one click.
- **Duplicate spotting:** 99% precision and 95% recall on 101 duplicate pairs. That is too few pairs to prove the bar with confidence, so any pair the robot is unsure about also goes to Rashieda.

## 8. How the work was checked

1. **12-person advisory panel:**
   - Karpathy, Cherny, Dario and Daniela Amodei, Anthropic research, Hormozi, Saraev, Sutskever, Murati, Brockman and Hassabis;
   - plus Steve Jobs for simplicity and usability.
   - All four groups said the old plan needed changing.
2. **Gaia's own leadership lens (CEO, CTO, CDO, CPO):** both pairs said "approve with changes". Their changes are in this plan, including the data-protection rules and the weekly email to Keith.
3. **Red-team gate on every email that leaves:** four independent reviewers (counterparty, facts, downside, reputation) must all pass.
4. **Independent second checker** on the AI measurements.

## 9. What is next, in order

| When | What |
|---|---|
| Fri 20 Nov | Reply to Diana, once it passes the red-team gate |
| Mon 23 – Tue 24 Nov | Cavuno trial: 8 checks. Buy or build decided by Tue 24 |
| Wed 25 Nov | Diana's guides go out. CHM and Mattinson get their own posting accounts |
| Thu 26 – Fri 27 Nov | Test site complete. Domain records copied. Keith checks the test site |
| Mon 30 Nov – Tue 1 Dec | Domains move (websites unchanged; email checked first) |
| Wed 2 Dec | Final data download. Go or no-go |
| Thu 3 Dec | Switch. Every site tested. Sector sites forward |
| Fri 4 Dec | Last day to switch back to Strategies if needed |
| Sun 6 Dec | Strategies switches off. We are already moved |

## 10. What only you can do

1. **Sign up for the Cavuno free trial** with your ProdCraft email. The verification email goes to an inbox this workspace cannot read, and no card is needed.
2. **The contract and the data agreement with Keith.** The data download cannot start before they are signed. A signature after about 1 December puts some data at risk.
