# GreenJobs handover, explained with a shop (20 Nov 2026)

Written as a colleague handing the project to a non-technical successor. Each idea comes with an everyday picture.

## The story in one picture

GreenJobs is a **job-ads shop**. Employers pay to put their job ads in its window, and job seekers walk past, read the ads and apply.

- The shop has **two main branches**: greenjobs.ie for Ireland and greenjobs.co.uk for the UK.
- It also has **8 small kiosks**, one per sector: wind, solar, ecology and so on. Each kiosk shows only its sector's ads.
- The owner is **Keith** (Gaia Talent, a recruitment agency).
- Two people run the shop day to day:
  - **Diana** keeps the keys and the paperwork.
  - **Rashieda** pins up the ads.

All of it sits in a **rented shopping centre called Strategies**. Strategies has given notice: **the lease ends on Sunday 6 December**. On that day the doors close, the lights go off, and anything left in the back office is gone.

**Our job is to move the whole shop to a new building before 6 December, without losing a single ad, customer record or letter.** We plan to move on **Thursday 3 December**, which keeps Friday as a spare day.

## The pieces, and what each one is in real life

| Technical word | Real-world picture |
|---|---|
| Domain (greenjobs.ie) | The shop's **street address**, the name people type |
| DNS / nameservers | The **post office's address book**, which says "greenjobs.ie is at building X". Moving means changing that line in the book. |
| Registrar (Hosting Ireland, LetsHost, 123 Reg) | The **office where the address is registered** and renewed each year. Diana has those keys. |
| Email records (MX) | The **"deliver letters here" instruction** in the same address book. Change the book carelessly and letters to info@ get lost. That is why email gets copied first. |
| Data exports | The **filing cabinets in the back office**: jobs, employers, applications and candidate files. The cabinet key only works while we are still in the old building. |
| DPA (data agreement) | The **signed rule sheet** for handling other people's private files. We may not touch the candidate cabinets until it is signed. |
| Sector sites | The **8 kiosks**. After the move they become signposts that point to the right aisle in the main shop. |
| Redirects | **"We've moved" signs** on every old door (about 1,200 old addresses), so Google and returning visitors land in the right place. |

## What we found that matters most

**Gaia writes every ad twice, by hand.** It pins each job in its own shop window (gaiatalent.com), then Rashieda walks over and copies it by hand into the GreenJobs window. **81 of Gaia's 83 jobs are in both windows.**

We built a **photocopier robot** that watches Gaia's window and copies each new ad into GreenJobs automatically, so Rashieda writes it once. When the robot is not sure which aisle (sector) an ad belongs in, it leaves a sticky note and Rashieda confirms it with one click.

## The big decision: rent a ready-fitted unit, don't build from bricks

- **The first plan** was to build the new shop ourselves, brick by brick: our own website code. When our advisory panel inspected it, they found:
  - the "post an ad" desk was not connected to the shop window (ads never appeared);
  - the "Apply" buttons still pointed to the old shopping centre, which closes on 6 Dec;
  - staff would have had *more* work, not less;
  - only one person (Debanjan) could ever repair it.
- **The new plan** is to rent a **ready-fitted shop unit**, Cavuno, a ready-made job-board service, like a franchise kiosk that comes with shelves, tills and lights already working. It costs about $39–79 a month per branch. We then build only what is special to GreenJobs around it:
  - the photocopier robot;
  - moving the filing cabinets;
  - the "we've moved" signs;
  - changing the post-office address book safely;
  - a daily check that the doors are open.
- **Why rent:**
  - it already works;
  - anyone can maintain it;
  - employers (CHM Recruit, Mattinson) keep putting up their own ads;
  - job alerts already exist;
  - the client can take all their data out and leave at any time.

  With 13 days left, a fitted unit is far safer than building from bricks.
- **The catch:** the unit's landlord keeps its storeroom in the US. That is legal with the standard EU contract clauses, and we keep very little private data there anyway. Applications go straight to each employer's own email or link, and the 178,000 old candidate files go into a locked archive that GreenJobs owns. They are not moved into the new shop.

## Why the Cavuno trial matters, and why only you can start it

The trial is a **test drive before signing the lease**. Cavuno gives 14 days free, no card. On Mon 23 – Tue 24 Nov we use it to run **8 checks**:

1. Does "Apply" work on a phone?
2. Do Gaia's ads arrive without duplicates?
3. Do both branches and a kiosk signpost work?
4. Do job alerts arrive?
5. Does email from the shop avoid spam folders?
6. Can we take all the data out again?
7. What is the real price at GreenJobs' size?
8. Is the data agreement in hand?

All 8 pass → we rent it. Any fails → we fall back to finishing our own build, which must pass its own full test by Mon 30 Nov.

**Why you:** signing up sends a "confirm your email" message, and it goes to your ProdCraft inbox, which this workspace cannot read. It takes two minutes and needs no card. Use the ProdCraft address for the trial only. When we buy, the real account is opened **in GreenJobs' name and paid by Keith**, so the client owns its shop and we are only the fitters.

## How Diana is involved, without calls or passwords

- **No calls, no passwords.** Diana gets a short written guide per registrar: "click here, paste this, by this date". She does it when she is free. A robot then checks the public address book every 10 minutes and emails her "done, checked".
- **The filing cabinets.** After the data agreement is signed, she sends one Strategies key, once, through a self-destructing link. A robot empties the cabinets overnight into GreenJobs' own storage, and then the key is changed.

## How we keep ourselves honest

| Check | The picture |
|---|---|
| **12-person advisory panel** (Karpathy, the Amodeis, Hormozi, Steve Jobs and others) | Outside advisers who walk the shop floor and say what is wrong. All of them said the first plan needed changing. |
| **Gaia's CEO / CTO / data officer / product owner lenses** | The client's own management checking the plan from their side. They said "approve, with changes", and those changes are in. |
| **Four-reviewer red team** on every client email | Four editors proofread every letter before it is posted: is it true, is it fair to the reader, what could go wrong, how does it look? Today's reply to Diana took 10 rounds. The lesson: answer only what was asked. |
| **Daily dashboard** | **11 gauges with a pass mark each**, checked by machines, never by the AI judging itself. Among them: doors open (sites up), letters delivered (email works), nothing lost in the move, new ads visible within 15 minutes, staff hours under 4 a month. Keith gets a 5-line weekly note. |

## The calendar

| When | What happens |
|---|---|
| Mon 23 – Tue 24 Nov | Test drive. Rent or build decided by Tuesday |
| Wed 25 Nov | Diana's guides go out. CHM and Mattinson get their own posting logins |
| Thu 26 – Fri 27 Nov | New shop fitted and stocked. Keith walks round the test shop |
| Mon 30 Nov – Tue 1 Dec | Post-office address book changes. Old shop still open; letters checked first |
| Wed 2 Dec | Last emptying of the cabinets. Go or no-go |
| Thu 3 Dec | Move day. Every branch and kiosk tested |
| Fri 4 Dec | Last day we can move back if something breaks |
| Sun 6 Dec | Old shopping centre closes. We are already out |

## What only the boss (Debanjan) does

1. Starts the Cavuno test drive: sign up with the ProdCraft email.
2. Signs the lease and the private-files rule sheet with Keith: the contract and the DPA. The cabinets cannot be emptied until then, so a signature after about 1 December puts some files at risk.
