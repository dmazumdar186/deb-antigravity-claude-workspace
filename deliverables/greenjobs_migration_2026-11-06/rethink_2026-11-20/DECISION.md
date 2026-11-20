# GreenJobs: decision after the 12-lens panel and the Gaia executive lens (2026-11-20)

Inputs:
- panels A–D, all voting AMEND;
- exec_CEO_CPO.md and exec_CTO_CDO.md, both APPROVE WITH CHANGES;
- RESEARCH_options.md and CAVUNO_MUSTHAVES.md.

The CTO/CDO lens corrected SYNTHESIS §2: the gate now asks for a lawful transfer, not EU-only residency.

## Decision: buy the board, build the automation around it

**Claim:** run both boards on Cavuno, a hosted job board. ProdCraft builds and runs everything around it so the staff touch as little as possible.

**Objection:**
- Hosting is in the US, and AI sub-processors sit in China and Singapore (CAVUNO_MUSTHAVES §5).
- The sector sites cannot be filtered views of a board (§3).
- Alerts are weekly only, and imported subscribers must re-confirm (§2).
- Apply-by-email and expiry are not documented as import fields (§4).

**Resolution (keep, amended):**
- **Candidate data barely enters Cavuno.** Applications go to each job's own email or ATS link. Only consented alert subscribers are imported, and they re-confirm (double opt-in is good GDPR practice). The ~178k legacy candidate records are never imported (CDO).
- **The transfer is covered by Cavuno's Article 28 DPA with SCCs.** We add the UK Addendum and disclose it in the privacy notice. Keith decides with that in writing.
- **The sector domains** stay in Cloudflare as 301 redirects to filtered job lists on greenjobs.co.uk. This is the same as the custom plan, so it is no worse.
- **The custom build stops as the main path.** Reusable parts are kept:
  - the import mapper on the real headers;
  - the redirect map;
  - the DNS inventory;
  - the Gaia feed sync.

## Why not the custom build

Panels B and D found three defects:
- a job posted in the console never reaches the board;
- the apply buttons die on 6 Dec;
- only one person can maintain it.

Fixing all that in 13 days, on top of employer self-posting, alerts and the network sites, carries more risk than configuring a product. Panel D also estimates more staff hours for the custom build than for today.

## The gate: Cavuno 14-day trial (Starter, no card), Mon 23 – Tue 24 Nov

Pass all of these, or fall back to fixing the custom build (deadline: end-to-end test green by Mon 30 Nov):
1. A job imported from our CSV with an apply URL, and one with an apply email, both work on a phone.
2. Our `feed.xml` (Gaia sync output) is polled, maps correctly, and does not duplicate jobs already on the board.
3. Two boards on test domains, plus a 301 from a sector domain to a filtered list.
4. An alert subscriber import, the confirmation email, and the weekly digest received.
5. The mail sender domain (Basic plan) passes SPF and DKIM alongside the existing `-all` records.
6. A full export of the trial board works (the exit test).
7. Price at the real alert-subscriber count. Today: Starter $39/mo per board, Basic $79/mo per board billed yearly.
8. The DPA, SCCs and UK Addendum are in hand.

## Client asks: written, asynchronous, no calls

1. Diana: a nameserver click guide per registrar. Our watcher confirms each domain by email.
2. A recovery address on another domain is added first.
3. One sector domain moves first as a rehearsal.
4. Zone export: the hosts' own zone files are needed after all (CTO). Diana downloads them with a click guide; we never take her login for this.
5. Strategies exports, after the DPA: a dedicated Strategies login is sent once through a one-time secret link. The bot downloads everything outside 09:00–17:00 UTC into GreenJobs' own storage. The password is reset after the run, and there is no personal data in logs.
6. Keith decides retention and the archive destroy date in writing.

## Metrics

Metrics M1–M11 and evals E1–E3 as in SYNTHESIS §4, with these changes:
- **M9:** compute it by joining the "Jobs By Email" export to the registration export on CandidatePK.
- **E2:** report the Wilson 95% lower bound, not a point figure on 100 pairs.
- **Added (CPO):**
  - applications per job;
  - alerts sent and opened;
  - expired jobs still showing;
  - live duplicates.
- **Added (CDO):**
  - fields migrated ÷ fields exported (minimisation);
  - erasure requests closed within 30 days;
  - archive access log entries;
  - unsubscribes carried over.

Reporting:
- The operator gets a daily status page.
- Keith gets a 5-line weekly email: red items, applications, alerts sent, staff hours, next step.

## Needs the operator

1. Sign up for the Cavuno trial with a ProdCraft address. The email verification goes to an inbox this session cannot read. No card is needed.
2. Do not send the 20 Nov reply to Diana. It proposed calls; an asynchronous version follows through /redteam.
