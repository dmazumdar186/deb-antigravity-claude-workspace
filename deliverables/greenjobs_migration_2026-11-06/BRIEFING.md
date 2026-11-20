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

## 4. The big decision: our own site, fixed

**The site we designed in September won the contract and is the product.** Keith will not pay for a third-party service, so there is none. It runs on Cloudflare's free tier, in GreenJobs' own account.

**What the 12-person advisory panel found in our build, and the fix:**

| Defect | Fix |
|---|---|
| A job posted by staff never appeared on the website | Job pages are now read straight from the database, so a post is live within minutes |
| Apply buttons pointed to the old Strategies pages | Each job applies by its own email or its own link |
| Staff typed each job once per board; fields could not be edited | One form for both boards, every field editable, a closed job can be reopened |
| Only Debanjan could maintain it | Written instructions, tests and a status page |

**What we add around it:**
- Gaia's jobs copied in automatically;
- CHM and Mattinson posting through their own logins;
- 1,200 old addresses redirected;
- the 8 sector sites forwarding to filtered lists;
- daily health checks.

**Private data:** only live jobs and employers go into the new site. Alert subscribers go in only with consent, and they re-confirm. Old candidates and applications go to GreenJobs' own locked archive.

**The final check, by Mon 30 Nov:**
- our end-to-end test passes: post, visible within 15 minutes, apply delivered, close;
- old addresses redirect;
- all sector sites forward;
- uptime and email checks are green.

Keith checks the test site by Fri 27 Nov.

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
| Mon 23 – Tue 24 Nov | Build fixes finished; test site up for Keith |
| Wed 25 Nov | Diana's guides go out. CHM and Mattinson get their own posting accounts |
| Thu 26 – Fri 27 Nov | Test site complete. Domain records copied. Keith checks the test site |
| Mon 30 Nov – Tue 1 Dec | Domains move (websites unchanged; email checked first) |
| Wed 2 Dec | Final data download. Go or no-go |
| Thu 3 Dec | Switch. Every site tested. Sector sites forward |
| Fri 4 Dec | Last day to switch back to Strategies if needed |
| Sun 6 Dec | Strategies switches off. We are already moved |

## 10. What only you can do

1. **The contract and the data agreement with Keith.** The data download cannot start before they are signed. A signature after about 1 December puts some data at risk.
