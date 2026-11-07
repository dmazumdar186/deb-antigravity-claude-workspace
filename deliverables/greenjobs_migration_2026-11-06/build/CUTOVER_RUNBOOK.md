# GreenJobs DNS and mail cut-over runbook

Written 2026-11-07. Internal. Applies to greenjobs.ie and greenjobs.co.uk (apex and www, plus any subdomain found
in the inventory). Times are Irish / UK time (GMT in December, same as UTC).

Hard facts: Strategies' contract ends Sun 6 Dec 2026. Changing DNS cuts access to the old sites, so the final
export runs **before** DNS moves. DNS is not managed by Strategies; who holds it is the answer to Q2. Mailbox host
is the answer to Q3.

Command convention: lines marked **[READ-ONLY]** only query. Lines marked **[OPERATOR CHANGE]** change live
state; only the operator runs them, and only after the step above passes. `D` is the domain under test
(`greenjobs.ie` or `greenjobs.co.uk`); run every check for both.

## 0. Two paths (decided by the answer to Q2)

| | Path A: nameservers move to Cloudflare (preferred) | Path B: nameservers stay at the current DNS host |
|---|---|---|
| Zone | Added to GreenJobs' Cloudflare account; every record recreated there before the NS change | Records edited at the current host |
| Web records | Pages custom domains on apex and www; Worker routes on the same hosts | `www` CNAME to the Pages project `*.pages.dev`; apex by ALIAS/ANAME/flattening if the host supports it, otherwise apex forwards to www at the host |
| Worker | Routes on the board hosts (`/api/*`, `/admin/*`) | Reached through the Pages project (service binding) or its `workers.dev` host with `ALLOWED_ORIGINS`; decide at build |
| Access | Self-hosted app on `D/admin*` | Confirm Access covers the hostname actually used for `/admin/` |
| Rollback | Restore the saved web records in Cloudflare (NS stay; fastest) | Restore the saved web records at the current host |
| Extra risk | NS change itself (registrar step, propagation) | Depends on the host's UI and TTL limits |

In path A the nameserver change happens at T-3 (Mon 30 Nov) with **every record still pointing at Strategies
and the current mail host**. Only the web records change on switch day. This splits the two risks.

## 1. Before switch day

### T-7, Thu 26 Nov

- [ ] Export the current zone file for both domains from the DNS host and store it in GreenJobs' storage
      (not git). Owner: DNS holder (Q2) with us. If the host has no export, screenshot every record page.
- [ ] Inventory every record into a table (type, name, value, TTL): A, AAAA, CNAME, MX, TXT (SPF, DKIM, DMARC,
      Google / Microsoft / other verification), CAA, SRV, and every subdomain. Cross-check with: **[READ-ONLY]**
      ```
      for t in A AAAA CNAME MX TXT CAA NS SOA; do echo "== $t"; dig +short $t D; dig +short $t www.D; done
      dig +short TXT _dmarc.D
      dig +short TXT google._domainkey.D        # selector names come from the zone export, try each one found
      ```
- [ ] Record Strategies' current web values (apex A, www A/CNAME) as the **rollback values**. Two people check them.
- [ ] Note the current TTLs. Note who can change records and how fast (phone number for switch day).

### Fri 27 Nov

- [ ] Staging sign-off by Keith on the test address. No sign-off on an item: it moves to phase 2.
- [ ] Path A: zone created in GreenJobs' Cloudflare account; every inventoried record recreated **exactly**,
      MX / SPF / DKIM / DMARC first. Proxy off (DNS only) on every mail-related and verification record.
- [ ] Diff the Cloudflare zone against the export. **[READ-ONLY]**
      `dig +short MX D @<cloudflare-ns>` vs `dig +short MX D` (repeat per record type).

### T-3, Mon 30 Nov (path A only)

- [ ] **[OPERATOR CHANGE]** Registrar: set nameservers to the Cloudflare pair for the zone.
- [ ] Verify mail before anything else: **[READ-ONLY]** `dig +short NS D`, `dig +short MX D @1.1.1.1`,
      `dig +short MX D @8.8.8.8`, `dig +short TXT D`.
- [ ] Send a real test mail from an outside account to info@D and reply from info@D. Both arrive. Check the
      received headers show SPF and DKIM pass.
- [ ] Web still serves Strategies: `curl -sI https://www.D/` **[READ-ONLY]** shows the old server.

### T-2, Tue 1 Dec (48 h before)

- [ ] **[OPERATOR CHANGE]** Lower TTL to 300 s on apex and www web records (both paths).
- [ ] Do **not** lower or touch MX in the web switch. MX keeps its value and TTL.
- [ ] If Resend sends from the domain (`MAIL_PROVIDER=resend` for applications, and alerts if kept):
      **[OPERATOR CHANGE]** add Resend's DKIM / SPF / return-path records on a sender subdomain such as
      `mail.greenjobs.ie` / `mail.greenjobs.co.uk`. The apex SPF record for the mailboxes is not edited.
      Verify in Resend; send a test to our own inbox.
- [ ] 301 map loaded on staging; spot check 20 old ASP URLs per site (list from the 22 Sep scrape).

### T-1, Wed 2 Dec

- [ ] Final delta export from Strategies "Download Reports" (Strategies still reachable), per site, all five
      types. Stored in GreenJobs' storage only.
- [ ] Validator dry-run on the delta (`strategies_import.py ... --report`), then emit SQL outside the repo and
      **[OPERATOR CHANGE]** apply to production D1. Re-run shows zero new rows (`import_batches`).
- [ ] Freeze: from 17:00, staff post on the new console only (on staging hostnames). Old board content is frozen.
- [ ] Production Pages deploy built from production D1; `robots.txt` allows crawling; sitemap absolute.
- [ ] Go/no-go call at 17:00 against §3.

## 2. Switch day, Thu 3 Dec

| Time | Step | Owner | Verify |
|---|---|---|---|
| 08:30 | Re-check rollback values and mail baseline | Us | **[READ-ONLY]** `dig +short MX D`, `dig +short A D`, `dig +short CNAME www.D` match the T-7 inventory |
| 08:45 | Last delta check: any applications on Strategies since T-1? Export them if so | Keith's exporter + us | Count noted |
| 09:00 | **[OPERATOR CHANGE]** Worker vars to live: `DRY_RUN="0"`, `LIVE_CONFIRM="send-applications"`; confirm `APPLY_INBOX_IE/UK`, `MAIL_FROM` | Operator | `wrangler deployments list` shows the new version |
| 09:10 | **[OPERATOR CHANGE]** Switch web records for greenjobs.ie (apex + www) to Pages | DNS holder / operator | **[READ-ONLY]** `dig +short A D @1.1.1.1`, `dig +short CNAME www.D @8.8.8.8` |
| 09:20 | Web check IE | Us | **[READ-ONLY]** `curl -sI https://D/`, `curl -sI https://www.D/` give 200 or one 301 to the canonical host; valid TLS |
| 09:30 | 301 spot check IE | Us | **[READ-ONLY]** `curl -sI https://www.D/for-employers.asp` and 20 more from the map return `301` with the right `location:` |
| 09:40 | End-to-end application IE: apply to a test job with a small PDF from an outside address | Us | Mail arrives in the IE inbox; row in D1 with `delivery_status='sent'`; CV in R2 |
| 09:50 | Console check IE: staff post, edit, close a test job | Keith's poster | Job appears after the next rebuild (≤ 5 min cron + build); closed job refuses apply |
| 10:00 | Mail check IE: real test mail in and out of info@D | Us + Keith | Arrives; **[READ-ONLY]** `dig +short MX D` unchanged |
| 10:15 | Repeat 09:10 to 10:00 for greenjobs.co.uk | Same | Same |
| 11:30 | GA4 real-time shows hits on both IDs (G-ZQPJGM484J IE, G-ZFW03XQE2N UK) | Us | Real-time view |
| 11:45 | Search Console: resubmit `sitemap.xml` for both properties; inspect 3 job URLs | Us (access per Q11) | Sitemap status "Success" |
| 12:00 | Go/no-go confirmation | Debanjan + Keith | §3 criteria, written in the thread |
| 16:00 | Afternoon re-check of every row above | Us | Same results |

## 3. Go / no-go criteria

Go only if all are true:

1. Both domains, apex and www, serve the new boards over valid TLS from at least two public resolvers.
2. Every live job from D1 is on the board; count matches `GET /api/export/jobs?site=` for each site.
3. One end-to-end application per site reached the right inbox, with the CV.
4. Staff posted, edited and closed a job through the console on each site.
5. MX, SPF, DKIM and DMARC are byte-identical to the T-7 inventory; test mail flows both ways.
6. 20 of 20 spot-checked old URLs per site return 301 to the right page.
7. No `delivery_status='failed'` rows that are not explained.

## 4. Rollback

**Trigger (any one):** a floor item fails and cannot be fixed within 2 hours; applications are lost or misrouted;
a board is down for more than 30 minutes; mail is affected in any way.

**Window:** Strategies switches off on Sun 6 Dec, so the last rollback decision is **Fri 4 Dec 17:00**. After that
we fix forward.

**Steps:**

1. **[OPERATOR CHANGE]** Restore the saved web records (apex and www) to Strategies' values from the T-7 inventory.
   Path A: in the Cloudflare zone. Path B: at the current host. TTL stays 300 s.
2. **[OPERATOR CHANGE]** Worker `DRY_RUN="1"` so nothing sends from the new stack.
3. Verify: **[READ-ONLY]** `dig +short A D @1.1.1.1`, `curl -sI https://www.D/` shows the old server.
4. Mail: nothing to do. MX was never changed during the web switch.
5. Export any applications that reached the new stack during the switch and forward them to the inbox.
6. Tell Keith the cause and the new switch time, still before Fri 4 Dec 17:00 if possible.

**Rehearsal:** rollback is rehearsed once on staging (switch `staging.` record to a placeholder and back) before T-2,
with times recorded.

## 5. Post-switch daily checks (10 working days)

Fri 4 Dec, Mon 7 to Fri 11 Dec, Mon 14 to Thu 17 Dec. Each day, both sites, report failures the same day:

- [ ] **[READ-ONLY]** `dig +short MX D`, `dig +short A D`, `curl -sI https://www.D/`.
- [ ] Live job count per site matches D1.
- [ ] Applications in the last 24 h: all `sent`; any `failed` resent and explained.
- [ ] Last Pages deploy succeeded; no publish pending for more than 15 minutes.
- [ ] 5 random old URLs still 301.
- [ ] Search Console: coverage and Google for Jobs errors; GA4 traffic in line with the day before.
- [ ] After Sun 6 Dec: TTL raised back to the original values (**[OPERATOR CHANGE]**, Mon 7 Dec).
