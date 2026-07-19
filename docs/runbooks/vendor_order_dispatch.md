# Operator Dispatch — Vendor Orders (D-8, 2026-07-19)

**Total monthly cost**: ~€126/mo mailboxes + ~€89/mo Instantly (existing sub) = ~€215/mo
**Setup time**: 20-30 min including payment on both vendors
**Vendors**: Primeforge (25 mbx, primary) + Litemail Pro (5 mbx, backup) — Nick Abraham rotation model

---

## Prerequisite

Complete domain purchases first (`docs/runbooks/domain_purchase_dispatch.md`). You need 10 domain names in hand before ordering mailboxes.

---

## Order 1 — Primeforge (25 mailboxes on 8 domains)

**Rationale**: Tier S per Phase 3 vendor research. InboxKit 30-mbx / 3-month test = 80% inbox placement. Documented case study of 69 mailboxes / 23 domains running clean for 6 months. Real Google Workspace, full admin ownership from day 1, transferable.

**URL**: https://www.primeforge.ai/pricing

**Login/signup**:
- Use debolshop@gmail.com (or the admin email you're comfortable long-term)
- Enable 2FA immediately

**Configuration (in order form)**:
- Product: **Google Workspace mailboxes** (NOT MS365 — MS 2026 crackdown makes it risky for cold outbound; GWS is default)
- Domains: enter 8 of your 10 registered domains. Best split:
  - 3 domains from Cloudflare Registrar
  - 3 from Namecheap
  - 2 from Porkbun
- Mailboxes per domain: 3
- Total: 24 mailboxes... but we want 25 — add 1 extra on the primary domain (4 mailboxes on it, 3 each on the rest)
- Sender name: **Debanjan Mazumdar** on ALL mailboxes (Nick's identity-consistency rule)
- Sender first names: use "Debanjan" for all — do NOT fragment identity
- Sender emails (choose format): `debanjan@[domain]`, `debanjan.m@[domain]`, `hello@[domain]` — vary format across domains to avoid pattern-matching. Do NOT use "sales", "info", or "marketing" — those trigger spam filters
- Pre-warmed: **YES** (this is why we're paying Primeforge over DIY Google Workspace)
- Warmup pool: their internal (you'll add Instantly bundled after connect)

**Payment**:
- ~€92/mo mailboxes + ~€9/mo domain hosting = ~€101/mo
- Enter credit card. Confirm subscription frequency = monthly (NOT annual — keep flexibility for month 1)

**Post-order**:
- You'll receive a handoff email within 24-48h with GWS admin credentials for each of 8 domains
- Complete 2FA + recovery email on each admin console (10 min per domain × 8 = ~80 min real work — plan a lunch for this)

---

## Order 2 — Litemail Pro (5 mailboxes on 2 domains)

**Rationale**: Tier S per Phase 3 research (with caveat: thin independent review base). Backup vendor for decorrelation risk. If Primeforge has an incident (SURBL, Google policy shift), Pool B keeps sending.

**URL**: https://litemail.ai/pre-warmup

**Login/signup**:
- Use debolshop@gmail.com (same admin email)
- Enable 2FA

**Configuration**:
- Product: **Pro tier, Google Workspace pre-warmed** (NOT the Starter/Growth fresh-mailbox tiers)
- Domains: the remaining 2 of your 10 registered domains. Best split:
  - 1 domain from a registrar NOT used for Primeforge Order 1 (registrar diversification)
  - 1 more from the third registrar
- Mailboxes per domain: 3 → wait, we want 5 total. So: 3 on one domain, 2 on the other.
  - Actually: reduce to 5 total, split 3+2 across the 2 domains
- Sender name: **Debanjan Mazumdar** on ALL mailboxes (identity consistency)
- Sender emails: same format variation rule as Primeforge
- Pre-warmed: YES, 4-12 weeks warmup history

**Payment**:
- ~€23/mo mailboxes + ~€2/mo domain hosting = ~€25/mo
- Enter credit card. Monthly billing.

**Post-order**:
- Handoff email within 24-48h with GWS admin credentials
- 2FA + recovery on 2 more admin consoles (~20 min)

---

## Order 3 (optional — depends on Instantly UI check)

**Warmforge (Salesforge, $2/slot for 10 slots = $20/mo = ~€18/mo)** — only needed if the plan's Section 2 warmup strategy (Option A) is confirmed. Alternative: use Instantly's bundled warmup for the first 20 mailboxes and don't buy Warmforge — the remaining 10 mailboxes rely on Primeforge's own internal pool.

**Decision rule**:
- If mail-tester scores on all 30 mailboxes come back ≥8 after D-4 vetting → skip Warmforge, save €18/mo
- If any mailbox scores drop <8 within week 1 → buy Warmforge to bolster warmup on the failing ones

**URL if needed**: https://www.warmforge.ai/pricing

**Configuration**: 10 slots, monthly billing. No domains or mailboxes needed — it plugs into existing IMAP/SMTP.

---

## Post-vendor-order verification

Once both vendors deliver:

```bash
# From Instantly UI:
# 1. Settings → Email Accounts → Connect Account
# 2. For EACH mailbox, click "Connect" → paste the OAuth credentials from vendor handoff email
# 3. Verify each shows "Connected" + green warmup slider = ON

# From this workspace:
# Confirm all 30 mailboxes visible in Instantly dashboard
```

Total time for this whole vendor-order flow:
- Ordering: 15 min
- Vendors provisioning: 24-48h (async wait)
- OAuth to Instantly + 2FA on 10 GWS admin consoles: 100 min
- **Total operator active time: ~115 min**

---

## Rollback

- **Primeforge**: cancel anytime (no annual commitment). Domain transfer available (full ownership). If canceled within 7 days: request full refund per Primeforge ToS.
- **Litemail Pro**: same terms.
- **Warmforge**: pay-as-you-go, cancel anytime.
- **Do NOT** cancel Instantly Hyper Growth before month end — 30-day notice required per Instantly ToS.

If you decide 30 mailboxes is too much after 2 weeks:
- Retire 15 (keep 15 at ~€60/mo mailboxes = €150/mo total)
- Retire 20 (keep 10 at ~€40/mo mailboxes = €130/mo total)
- Cancel all 30 (revert to 1-mailbox baseline = €90/mo Instantly only)

Any of these is a clean downgrade with no data lock-in (unlike Instantly DFY which we specifically avoided).
