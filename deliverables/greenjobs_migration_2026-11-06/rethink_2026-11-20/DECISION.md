# GreenJobs: decision (v2, 2026-11-20)

v1 (buy a hosted job board, Cavuno) is **withdrawn**. The operator's ruling: the site we designed in September won the contract, and Keith will not pay for a third-party service. **The boards we built are the product.** The panel findings still stand; they now apply to fixing our own build.

## Decision

**The build:** the GreenJobs site we designed, live on Keith's domains, running on Cloudflare in GreenJobs' own account. Platform costs are as proposed (Cloudflare ~$5 and Resend ~$20 a month at cost; Proposal:148-151). No new third-party product.

**Claim → Objection → Resolution:**
- **Claim:** finish our own build.
- **Objection:** panels B and D found three defects:
  - a job posted in the console never reached the board;
  - Apply buttons pointed to Strategies;
  - only one person can maintain it.
- **Resolution (amend, keep the build):**
  1. **Job pages are rendered by the Worker straight from the database (D1).** A post is live within minutes and there is no rebuild pipeline. Everything else stays as the static designed site. A parity test keeps the job pages identical in design to the static build.
  2. **One frozen taxonomy file** (sectors, regions, job types) drives the console dropdowns, rendering, filters and the import classifier. This also makes eval E1 measurable.
  3. **Apply per job:** by email (on-site form) or by the client's own link. This is already built.
  4. **Staff console fixes:** post to IE, UK or both in one form; every field editable; close asks to confirm; a closed job can be reopened.
  5. **Gaia job feed:** a standalone sync script (writes a feed file and a review queue), **not wired to the board**. It is offered to Keith as a time saver and was not promised (RECORD P13).
  6. **CHM Recruit and Mattinson:** staff post for them from 3 Dec, and they are told by 25 Nov (REVIEW:21). Employer logins are phase 2 (Plan:31), built behind a flag, **off** (RECORD P11).
  7. **Data minimisation.** Live jobs and employers are imported. Alert subscribers are imported only where consent allows, and they re-confirm. Candidate records Keith chooses to keep are imported, consent-gated and minimised (RECORD P5a; Keith decides retention in writing). Everything else goes to GreenJobs' own raw archive.
  8. **About 1,200 old URLs** get 301 redirects. Forwarding config for the 8 sector domains is prepared but out of scope until Keith answers (RECORD P12).
  9. **Maintainability:** directives, runbook and tests in the repo, and a status page any operator can read.

**Promise list:** deliverables/engagement_record_2026-11-20/RECORD.md v4 (P1–P29) governs scope. Where this file disagrees, the record wins.

## The gate (replaces the Cavuno trial)

The end-to-end test must pass by **Mon 30 Nov**:
- post → visible on the board within 15 minutes → apply delivered → close → 410;
- old URLs redirect;
- the uptime and email probes are green;
- job alerts: sign-up, confirmation and digest work on staging;
- every step passes in the release pipeline on staging before any promote.

Sector-domain forwards are excluded from the gate: they are out of scope until Keith answers (RECORD P12).

Keith signs off on the test site by **Fri 27 Nov**.

## Client asks: written, asynchronous, no calls (unchanged)

1. A per-registrar click guide for Diana. The DNS watcher confirms each step by email.
2. A recovery address is added first.
3. One sector domain moves first as a rehearsal.
4. Zone files are downloaded by Diana with a guide.
5. Strategies exports, after the DPA: one dedicated login sent through a one-time link. The export bot downloads overnight, and the password is reset afterwards.
6. Keith decides retention in writing.

## Metrics

M1–M11 and E1–E3 as in SYNTHESIS §4, with the CPO and CDO additions. Graded by scripts. The operator gets a daily status page; Keith gets a 5-line weekly email.

## Needs the operator

1. The contract and DPA with Keith. The data downloads wait on them.
2. Nothing else. The Cavuno trial is cancelled.

## Keith pack schedule (plan of record, 20 Nov)

- Default dates for Keith's answers, each set before the step that depends on it:
  - Tue 24 Nov: who opens the Cloudflare and Resend accounts, and who sends the CHM/Mattinson notices.
  - Wed 25 Nov: candidate records, sector sites (default: forward), logos.
  - Fri 27 Nov: the 11 change-list inputs, the CRM, test-site sign-off.
- Change-list inputs received after go-live are applied within two business days (Proposal:140).
- Jobs posted on Strategies up to the switch are not lost: a final jobs-only export and import runs on Thu 3 Dec immediately before the web records switch. The full export still finishes on Wed 2 Dec. Advertisers therefore need no posting freeze or cut-off hour.
