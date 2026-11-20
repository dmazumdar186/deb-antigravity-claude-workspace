# Executive lens: Gaia Talent CTO + CDO (2026-11-20)

Internal. Client-side review of SYNTHESIS.md, which we assume is wrong until shown otherwise. Abbreviations: S = SYNTHESIS.md, F = FACTS.md, R = RESEARCH_options.md, PA = panel_A.md, PB = panel_B.md, H = ../build/import/REAL_HEADERS_2026-11-19.json, Z = ../build/dns/ZONE_INVENTORY_2026-11-20.md.

## CTO (ranked)

1. **The gate fails by design.** Must-have 5 asks for EU-only residency (S:44), but Cavuno's DPA already says it does not offer it (R:9). As written, the spike can only end in "fix custom". Restate it as "a lawful transfer: SCCs plus the UK Addendum, a TIA, and EU hosting where offered".
2. **Must-have 4 is half-false.** Cavuno "candidates not importable" (R:9, R:22) conflicts with "import Consent=yes candidates" (S:67). Add these to the gate:
   - an alert price at the real subscriber count (caps of 1k/5k/15k, R:9; count unknown, F:20) inside €600 (F:8);
   - 301s for the old ASP paths in front of the vendor;
   - SPF/DKIM for vendor mail;
   - a trial CSV export, re-imported to prove the exit route.
3. **Fallback timing.** If the spike fails on 23 Nov, the custom path needs a Worker rewrite (S:58-62) while the post-to-board loop is still unbuilt (PB:10-18). Eight working days to 3 Dec.
4. **Mail.** SPF is `-all` and includes Strategies (Z:33, Z:44), so the new sender must be added before the switch. `mail.greenjobs.co.uk` A must be copied (Z:189). The scan only probed guessed DKIM selectors (Z:162), so "zone export not asked" (S:75) is unsafe: ask for it. Use Path B for greenjobs.ie (PB:95). Logins have a circular dependency (PB:39-41): add a recovery address off-domain. Move one sector domain first as a canary.
5. **Exit.** The Cloudflare, registrar and vendor accounts must be owned by Gaia. Write a one-page handover so the work survives if the supplier disappears (PB:63-65).

## CDO (ranked)

1. **Minimise before migrating.** Do not move:
   - Members profile data (H:64);
   - historic Job Applications, which hold `Name` and `CandEmail` (H:188-195);
   - CV references (H:60);
   - home address and phone fields (H:47-56);
   - fax numbers.

   Drop candidates whose `LastLoggedIn` is older than the agreed retention period. Define what `Consent` means before using it as the import key (H:62).
2. **Transfers.** About 148k of the ~178k records are UK (F:17). Needed:
   - Gaia to ProdCraft: an Art. 28 DPA;
   - Gaia to Cavuno: SCCs Module 2 + the UK IDTA Addendum, a TIA, a sub-processor list, 72h breach notice, deletion on exit, and an audit right.
3. **Export bot.** Use a dedicated Strategies user if one exists. Diana rotates the password right after the run. The bot runs from an EU egress, keeps no credential on disk and writes no PII to logs.
4. **Raw archive.** "GreenJobs' own storage" (S:67) is unspecified. It needs EU location, encryption, a named access list, an access log and a destroy date. Retention cannot stay open past go-live.
5. **Metrics.**
   - M1 (S:87) checks fidelity, not lawfulness or encoding: add Irish fada and Windows-1252 checks.
   - M9 (S:95) checks only the `Marketing` flag. It needs a join to `JobsByEmail` (H:173), which has no `Marketing` column, and must honour Strategies unsubscribes.
   - E1-E3 (S:103-105) cover jobs only, and 100 pairs is too few to prove 99% precision.
   - Missing: a minimisation ratio, erasure propagation (target ≤30 days, all systems), an audit log of access, retention purges executed, and suppression-list carry-over.

## VERDICT: APPROVE WITH CHANGES

1. Rewrite the spike gate. Residency becomes a lawful transfer; add alert-cap pricing, 301s, mail authentication and an exit test; candidates are not imported.
2. Before any export: sign the Art. 28 DPA, set the minimisation schema and decide retention. Set up the archive with a destroy date and an access log.
3. Make DNS mail-safe: get the zone export, update SPF, use Path B for .ie, add off-domain login recovery, and move a canary domain first. Add four data metrics: minimisation, erasure, access log and retention purge.
