# Operator Dispatch — Domain Purchase (D-8, 2026-07-19)

**Total budget**: ~€120 one-time (10 domains × ~€12 each)
**Time**: 15-20 min including payment
**Goal**: 10 secondary domains for cold outbound, spread across 3 registrars for diversification

---

## Step 1 — decide the domain-naming pattern

Pick ONE of these two patterns (both pass Nick Saraev's discovery-call defensibility test — random-throwaway names like `growthclub.io` are NOT acceptable):

### Option A — brand-adjacent (recommended)
Clear signal that these are ProdCraft-owned. Risk: if flagged, cross-contamination to main brand.

Suggested names:
- `prodcraft-outreach.com`
- `prodcraft-studio.com`
- `prodcraft.co`
- `prodcraft.io`
- `prodcraft-ai.net`
- `hi-prodcraft.com`
- `talk-prodcraft.co`
- `hire-prodcraft.io`
- `prodcraft-labs.net`
- `prodcraft-team.com`

### Option B — you-adjacent
Names tied to Debanjan, but not brand-tied. Middle ground.

Suggested names:
- `mazumdar.io`
- `debanjan.co`
- `debanjan-mazumdar.com`
- `mazumdar-consulting.com`
- `debanjan-ai.net`
- `mazumdar-ai.com`
- `debanjan-labs.co`
- `paris-product-ai.com`
- `senior-fractional-ai.io`
- `mazumdar-studio.net`

**Recommendation**: Option A. Coherent branding trumps main-domain protection at 30-mailbox scale (risk to `prodcraft.fyi` is low if bounce/spam thresholds are enforced).

---

## Step 2 — split across 3 registrars

**Cart 1: Cloudflare Registrar** (at-cost pricing, best deal)
- 4 domains: pick 4 from your chosen list
- URL: https://dash.cloudflare.com/?to=/:account/domains/register
- Login with your Cloudflare account (same as api-proxy Worker if you have one)
- Add each domain to cart
- Payment: on file OR enter card

**Cart 2: Namecheap** (registrar diversification #2)
- 3 domains: pick 3 more from your chosen list
- URL: https://www.namecheap.com
- Login or sign up (email OTP)
- Add each domain via search
- Enable WHOIS privacy on all (free at Namecheap)
- Payment: enter card

**Cart 3: Porkbun** (registrar diversification #3)
- 3 domains: pick the final 3 from your chosen list
- URL: https://porkbun.com
- Login or sign up (email OTP)
- Add each domain via search
- Enable WHOIS privacy on all (free at Porkbun)
- Payment: enter card

---

## Step 3 — configure DNS on each domain

**DEFER THIS**. Primeforge and Litemail will configure DNS (SPF/DKIM/DMARC/MX) automatically once you assign the domains to them in Step 4 of the vendor dispatch.

If DNS is not configured by them within 24h of order, come back and set:
- MX: their instructions (Google Workspace MX records)
- TXT SPF: `v=spf1 include:_spf.google.com ~all` (Google Workspace default)
- TXT DKIM: their instructions (unique per mailbox tenant)
- TXT DMARC: `v=DMARC1; p=none; rua=mailto:debolshop+dmarc@gmail.com` (start with none; move to quarantine after 30 days)

---

## Step 4 — verify all 10 domains registered

Once all carts checkout:

```bash
# Verify each domain's registrar
for domain in prodcraft-outreach.com prodcraft-studio.com prodcraft.co prodcraft.io \
              prodcraft-ai.net hi-prodcraft.com talk-prodcraft.co hire-prodcraft.io \
              prodcraft-labs.net prodcraft-team.com; do
  whois "$domain" | grep -E "Registrar|Registered On" | head -3
  echo "---"
done
```

Expected: 4 Cloudflare, 3 Namecheap, 3 Porkbun. Total spend: ~€120.

---

## Step 5 — hand off to Claude

Once all 10 domains are registered, tell Claude:
- Which domain names you actually bought (may differ from suggestions)
- Which are on Cloudflare / Namecheap / Porkbun
- Any DNS management access tokens needed to point them at Google Workspace

Claude will then coordinate the DNS-to-vendor-mailboxes handoff.

---

## Rollback

If you change your mind mid-cart:
- Cloudflare Registrar: no refund policy on new domains (annual commitment)
- Namecheap: 30-day money-back on some TLDs, not all
- Porkbun: no refund policy on new domains

**Do not commit until you've decided on domain names.** If in doubt, buy 3 from Cloudflare first as a smoke test, then complete the rest after you see them provisioned.
