# GreenJobs: review of Keith's team's answers (16 Nov 2026)

Internal. Not for sending. Sources:
- Diana's 11 Nov email, forwarded by Keith on 16 Nov.
- Rashieda's 10 Nov answers.
- A live public DNS and site check run today.
- The offline test run today: 131 Worker tests and 28 import tests pass.
- Three reviewers: a DNS and site check, a delivery and data review, and a client, money and legal review.

## 0. The one thing that outranks everything

On 9 Nov the email told Keith: "the build starts once the contract is signed and the first month is paid", with the switch on 3 Dec.

The operator's residence-permit file from 10 Nov says the opposite:
- `titre_sejour_entrepreneur_2026-11-10/business_plan_ProdCraft.md:150`: "aucune prestation n'est réalisée ni facturée avant la délivrance du titre".
- `INTERNE_sources_et_points_a_verifier.md` item 2: "Aucune facturation avant l'autorisation d'exercer".
- The letter of intent, which Keith would sign, says: "No work has been carried out or invoiced to date … starting from the date of his authorisation."

The current card is "passeport talent – salarié qualifié", valid to 5 Mar 2027, so the new permit almost certainly comes after 6 Dec.

**Until a French immigration lawyer confirms a lawful way to be paid before then, do not send an invoice or a contract that starts paid work.** Whether a route like portage salarial is allowed is UNVERIFIED and is a question for the lawyer.

## 1. What each answer means

| Q | Answer | Firm? | What it changes |
|---|---|---|---|
| 1 Domains | "Not sure", but posting by sector goes to another site automatically | Weak | Live DNS shows all 8 network sites (conservation, ecology, environmental, renewable, wind, solar, waste, water) point to the same Strategies host as greenjobs.co.uk. They go dark on 6 Dec. Their DNS is at GoDaddy/123 Reg. |
| 2 DNS | greenjobs.ie at Hosting Ireland; greenjobs.co.uk at LetsHost; the others at 123 Reg. Diana has "almost all" access | Firm | Live: .ie nameservers are webhostingireland, .co.uk nameservers are dnsireland (SOA letshost). A bare domain on Cloudflare Pages needs Cloudflare nameservers, so runbook path A is the only path. Path B leaves the bare domain dead after 6 Dec. |
| 3 Email | Hosting Ireland | Firm | Live: MX for both domains is Hosting Ireland (.co.uk uses `mail.greenjobs.co.uk` → jade.webhostingireland.ie). Both SPF records include `spf.strategiesuk.net`; clean that up after 6 Dec. Copy every record from the host's zone export, not from `dig`. |
| 4 Exports | Diana and Rashieda, through the admin on the GreenJobs domains | Firm | The export login dies at the DNS switch. "Members profile data" only runs outside 09:00–17:00 UTC. |
| 5 Retention | "Not sure" | Non-answer | Keith (the controller) must decide in writing. Our 2 years is only a suggestion. Candidate import waits. |
| 6 Posting | Mostly Rashieda; CHM Recruit and Mattinson Partnership post themselves (contracts to Jan 2027) | Firm | Those two lose self-posting on 3 Dec. Staff post for them, and they need notice. |
| 7 Tools | Broadbean "in the past, not sure now" | Weak | Check whether any live job came from a feed. If one still feeds, it stops silently. |
| 8 Applications | Per client: an email or an ATS link | Firm | Per-job apply mode is needed (0.5 day). |
| 9 Volumes | ~15 new jobs a month; employers 1,616 UK / 418 IE; live jobs 105 / 133; candidates 147,681 / 30,097 | Mostly | Live today: 78 UK / 145 IE, mostly Gaia Talent's own jobs. Posting volume is higher than "15". The alert subscriber count is missing. |
| 10 Payments | None online; invoices and Revolut | Firm | Online payment is out of scope; quote it later. |
| 11 Analytics | Doesn't know how; logos OK "I suppose"; asked about AuthorityLabs | Weak | We already hold the GA4 IDs (G-ZQPJGM484J IE, G-ZFW03XQE2N UK; the sector sites have their own). Search Console can be re-verified by DNS. Get a one-line written OK on logos from Keith. |
| 12 Signer | Keith | Firm | The legal entity is not confirmed: GreenJobs Ltd (named on the sites and in the letter) or Gaia Talent Ltd (the payer). |

8 of the 12 are firm (67%).

## 2. Misses and contradictions found

1. **Permit vs upfront payment.** See §0.
2. **The €1,500 Q1 payment is missing** from the 9 Nov email. The letter of intent reads as €1,500 first and then €600 a month, which is not the LinkedIn deal (€600 a month from now, plus €1,500 in Q1).
3. **Entity.** GreenJobs Ltd vs Gaia Talent Ltd, on the contract, the DPA and the invoice.
4. **Diana cc'd `dmazumdar@teamprodcraft.com`.** Five working days were lost. Then the 16 Nov 16:42 email asked for questions 1, 2, 7 and 12, which were already answered.
5. **The 8 network sites are not in the plan** (the decision table said "quote separately"). Advertisers are sold "displayed on all relevant network websites … for up to 6 weeks" (brief.md). They break on 6 Dec unless the domains at least redirect.
6. **Alerts and the weekly newsletter are paid advertiser features,** and the plan promised "job alert emails" on 3 Dec. Yet they come first in the trim order.
7. **Path B in the runbook does not work** for the bare domains. Path A means moving nameservers, which touches email.
8. **The profile export has a time window** (outside 09:00–17:00 UTC), and Diana is the Finance Administrator. Exporting about 178k candidates by hand is a capacity risk.
9. **No real CSV has been seen.** The import headers are guesses (IMPORT_MAPPING.md:7).
10. **The letter of intent says "no work carried out",** but an offline build pack exists. Ask the lawyer whether unpaid preparation counts.
11. **conservationjobsuk.com already has a TLS certificate mismatch.** This was there before us, but tell Keith.
12. **The brain eval for 2026-11-13 is WARN** (dead_lesson, goalposts_moved, live_precision_kw_floor, possible_overfit). Not fixed in this session.

## 3. Scores

| Area | Score | Basis |
|---|---|---|
| Information from Keith | 67/100 | 8 of 12 answers firm |
| Code | 75/100 | 159/159 tests pass offline; nothing deployed; no real CSV; alerts and network redirects not built |
| Access | 5/100 | No DNS, registrar, admin or Cloudflare login in hand |
| Contract, DPA, legal | 5/100 | Nothing sent; permit conflict open; entity open |
| Data safety | 15/100 | Zero exports done; the archive window closes at the DNS switch |
| Time | 40/100 | About 12 working days left (17 Nov – 2 Dec) against an MVP estimate of 18–22, partly offset by the build pack |
| **Overall: both boards switched safely on 3 Dec** | **35/100** | The delivery reviewer said 40 without the permit issue; the permit issue takes off 5 |

If the permit question is cleared and signature, DPA, logins and a first export sample are in by **Fri 20 Nov**, overall rises to about 65. Mon 23 Nov is the absolute latest. After that, 3 Dec is the floor only: jobs, staff console, applications to an inbox, and a raw archive.

## 4. Upfront payment

- Confidence that asking for payment today is right: **15%**.
- Probability Keith pays €600 within 3 working days if asked now: about 35% (estimate).
- Conditions before asking:
  1. The lawyer confirms in writing a lawful way to be paid.
  2. The legal entity is confirmed.
  3. One contract carries both terms (€600 a month and €1,500 in Q1).
  4. Scope is written: the 2 boards; the 8 network sites as redirects or quoted separately.
  5. The DPA has been sent.
  6. The letter of intent is corrected or dropped.
- Once all six hold, asking is right (about 80%), and Keith's chance of paying rises to roughly 60–70%. He has already given notice and needs the switch.

## 5. Negative scenarios (probability, then tripwire date)

1. **Network sites go dark.** High. Tripwire Wed 25 Nov.
2. **Signature slips.** Medium-high. Tripwire Fri 20 Nov.
3. **Export incomplete, data lost for good.** Medium-high. Tripwire Fri 27 Nov.
4. **Real headers break the import.** Medium. Tripwire: the first sample, Fri 20 Nov.
5. **Mail outage on the nameserver move.** Medium-low, but high impact. Tripwire: zone export, Thu 26 Nov.
6. **Bare domain down.** Medium. Tripwire Mon 30 Nov.
7. **Self-posters or a hidden feed stop silently.** Medium-high. Tripwire Wed 25 Nov.
8. **Alerts trimmed or landing in spam.** High. Tripwire Fri 27 Nov.
9. **The permit blocks paid work before 6 Dec.** Unknown until the lawyer answers. The fallback is Keith asking Strategies for a short extension, which he must request this week.
