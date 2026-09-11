# Gaia Sourcing v2 — outbound sourcing that feeds Maddie and Recruit CRM

For Keith Molony and Steph (Gaia Talent). From Debanjan Mazumdar, Prodcraft. Delivery promised: Monday 14 Sep 2026, 17:00, link plus Loom.

## What Gaia has today, and where this sits

Maddie is inbound. A CV arrives in Gmail, Maddie scores it against live jobs, invites anyone over 60 to a screening call, and writes the candidate with notes into Recruit CRM. It handles the people who come to you.

This system is outbound. It finds the chartered, grade-matched, Ireland-based engineers who never applied, proves each one with a quote from a public document, checks their contact details, and drops them into Recruit CRM as candidates on the job, so Isadora or Maddie takes over from there. Together they cover both halves of a search.

Recruit CRM's own AI sourcing (800 million external profiles, 0 to 100 match scores) is a search over a licensed profile database. This is a different layer: it reads what people wrote and said on the record (oral-hearing witness statements, firm bio pages, professional registers), so a card carries evidence, not a similarity score, and it applies your brief as hard rules, not a ranking.

## What went wrong on 20 August, and what changed

You said the list was too senior and some were not in Ireland. Both were filter settings.
- The seniority filter had a floor (8 years) and no ceiling, and it treated a Director title as proof of experience. All 10 Senior Structural Engineer cards were Director or Associate Director.
- The Ireland filter accepted "worked on an Irish scheme" as proof of living in Ireland. That let three London-based and one Belfast-based engineer through.
Both are now brief settings you set per role: a seniority band (grade ceiling and years) and a residence rule (Republic only, county list, relocation yes or no). A final check refuses to deliver a list whose titles or locations break the brief. The re-cut of your own 13 under a Senior Engineer ceiling is at the Brief Controls link: none of the 13 survive, which is exactly your read of the list.

## How it runs, per role

1. Brief. Title, grade band, years band, counties, chartership, target and off-limits firms, salary band. Confirmed back in writing before any search.
2. Find. Public evidence sources (An Coimisiún Pleanála oral hearings, consultancy bio pages, Engineers Ireland and IStructE registers) plus a licensed people-data source for the grade LinkedIn holds and bio pages do not.
3. Prove. Every claim on a card is a verbatim quote, checked character by character against the cached source. A claim that fails the check is dropped, and the drop rate is published (0.9% last run).
4. Gate. Deterministic rules only: chartered, resident, discipline, seniority floor and ceiling, not at the client. A model never decides a tier.
5. Contact. Email verified through Prospeo; only verified or catch-all addresses are used. Inferred addresses are labelled, never sent to. LinkedIn URL resolved per card.
6. Draft. A short LinkedIn note and a short email from a human-approved template pool, filled with the project they gave evidence on, the scheme, the firm. Under 400 characters. Sent by a named Gaia consultant from their own seat, never by us.
7. Reply. A candidate's reply is classified at once (interested, not now, no, question, out of office, bounce), the next step is set (book a call, snooze 90 days, close, consultant answers), and a note lands on the candidate in Recruit CRM. An opt-out closes the record and is honoured.
8. Sync. Each delivered candidate is created in Recruit CRM (deduplicated by email or LinkedIn URL, never overwriting a consultant's data) with source "Prodcraft sourcing", attached to the job, with an evidence note and the Article 14 notice date. From here Maddie can invite them to a screening call exactly as she does for applicants.

## Guardrails (fail-safe by default)

- Nothing sends on its own. Drafts go to a consultant; the CRM sync runs in dry-run unless a live flag is set, and every intended write is logged first.
- Brief lock. A list that breaks the seniority or location brief cannot be delivered.
- Evidence lock. No quote, no claim. Off-limits firms (AtkinsRéalis, TOBIN) are blocked everywhere.
- Contact honesty. Verified, catch-all, inferred and none are never merged.
- Cost ceiling per run and per campaign, enforced in code before every model call. Corrected campaign to date: €25.69.
- Privacy. Article 14 notice is a fixed text, injected on every draft, with the source of the data named. Licensed data providers only; no scraping through fake accounts.
- Change log. Any threshold change is a command-line flag, logged with the run, so a list can always be traced to the brief it was cut against.

## What lands on Monday 17:00

- Link: the sourcing dossier (same format as before) with Brief Controls, corrected for Senior Engineer grade and Ireland residence, for the two original roles, plus a CSV.
- Loom: how it runs, how the brief settings work, and how a candidate lands in Recruit CRM.
- This page, for Steph: where the hand-off to Maddie sits, and the Recruit CRM fields and endpoints used.
- An honest count: how many candidates survived per role and why. Role 2 (Cork) never had more than four who passed every gate; reaching five is a source question, not a filter question, and the page will say so.

## The corrected cut, as it stands (11 September)

- Senior Structural Engineer: 471 people assessed from 58 Irish consultancy directories, 25 oral-hearing witness statements and 103 search-snippet discoveries; 2 of 10 passed every hard gate with direct evidence and are delivered (Alicia Joyce, CSEA; John Alcaras, Arcadis). 14 more miss only on residence evidence (their firm pages do not say where they sit), 9 miss only on chartership evidence. Each is named in the pool map so you can tell us which to verify.
- Transport Major Projects Manager (Cork): 65 assessed, 0 of 5. The pool has no Cork-based, chartered transport lead on the public record we can reach for free. Reaching five needs a licensed people-data source; we say so rather than pad.
- What changed since 20 August: the seniority ceiling and the strict Republic-of-Ireland residence rule now run as hard gates; an office address or a project location no longer counts as where someone lives; chartership means Engineers Ireland (CEng MIEI/FIEI), not ICE or IStructE alone.
- Model spend for the whole corrected campaign: EUR 25.69, about EUR 13 per delivered card at this pool size; the per-role running cost below assumes a pool three to five times larger.

## Build timeline if you go ahead

Working pipeline exists (1,086 automated tests plus a 41-check acceptance gate on every delivery). Recruit CRM sync, reply classification and the brief settings are built. Wiring to your Recruit CRM account, your job slugs and a named-consultant sender takes 3 to 5 working days, as said on the call. Running cost per role is about €100 in data and model calls, against a placement fee of €14k to €20k.

## What Steph needs to know about the Recruit CRM hand-off

- API access is on Recruit CRM's Business plan and above, not Pro. If Gaia is on Pro, the sync runs through Zapier's Recruit CRM app (new candidate, assign to job) until an upgrade, or the CSV import stays the hand-off.
- The API key is generated by the account owner in Admin Settings and sent as an Authorization header. Rate limit is 60 requests a minute for accounts with up to 6 licences; the sync stays well under it.
- Fields written: first and last name, email (verified or catch-all only), current title, employer, city, LinkedIn URL, a "Source" value of "Prodcraft sourcing", a tag per campaign, one note with the evidence quotes and the Article 14 notice date, and assignment to the job. Existing candidates are matched on email or LinkedIn URL and never overwritten.
- Native webhooks (candidate created, stage changed) are on Enterprise; not needed for v1.
- Maddie's trigger stays hers: a sourced candidate who replies "interested" is set to a stage you choose, and Maddie or Isadora takes it from there.

## The tools Keith mentioned, and where this differs

- Recruit CRM AI sourcing: natural-language search over a licensed database of 800 million profiles with a match score, one-click import, on credits. A search over profiles; no evidence quotes, no chartership check, no outbound drafts or reply handling on its marketing pages (to be confirmed with Recruit CRM). This system reads what the person actually wrote or said on the record and applies the brief as hard rules.
- Wiggli: ATS plus AI sourcing over 850 million people, contact waterfall across 14 data sources, Hunter plan €140 a month for up to 5 users. Irish coverage unpublished. Worth a trial search if Gaia wants a second database source; it does not replace evidence or gating.
- Lusha and enrichment tools: Keith's own read ("they enrich but don't have the data") matches the published European coverage picture. Compliance note: Italy's regulator fined Lusha €2 million in July 2026, rejecting "legitimate interest" for enrichment data. Sourcing from public records with a named source and an Article 14 notice is the safer basis, and it is how this system already works.
- InMail: response rates have fallen from 10 to 15% toward 3 to 8%, and LinkedIn cut open InMail sends to under 100 a month in late 2025. That is why the drafts here are short, evidence-specific, sent from a named consultant, and email goes only to verified addresses.

## Not in scope, deliberately

- No AI voice calls, no automated sends: Maddie and your consultants own every conversation.
- No replacement of Recruit CRM or LinkedIn Recruiter; this feeds the first and reduces reliance on the second.
- No claim of a reply rate. The pilot counts replies; it does not promise them.
