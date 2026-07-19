# Legitimate Interest Assessment (LIA) — self_outbound_v2

**Data controller**: Debanjan Mazumdar, sole proprietor operating as **ProdCraft AI Studio** (prodcraft.fyi), Paris, France.
**Contact**: debolshop@gmail.com
**Date of assessment**: 2026-07-19
**Reviewed**: [pending operator signature — sign at bottom]
**Legal basis claimed**: GDPR Article 6(1)(f) — Legitimate Interest, combined with French LCEN L34-5 for B2B professional-address cold outreach.

---

## 1. Purpose test — why we are processing this data

**Processing activity**: sending outbound cold email to publicly-listed professional email addresses of French seed-stage founders, SMB agency owners, and heads of product-ops, with the purpose of offering fractional AI product-management + build services (ProdCraft AI Studio).

**Business need**: as a solo founder-operator, cold outbound is one of two viable customer acquisition channels for a fractional-services offer (the other being warm referrals, which have a hard ceiling at solo scale). Without cold outbound, ProdCraft cannot reach its target €5-30k MRR band within a viable timeframe.

**Necessity**: the processing is genuinely necessary to reach the target ICP — inbound marketing at solo-scale takes 12-24 months to compound; cold outbound at 30-mailbox scale reaches the same population in weeks.

**Alternatives considered and rejected**:
- Consent-based (opt-in) email lists: not viable for cold prospecting; the whole point is to reach unknown-to-us prospects.
- Paid ads: cost-prohibitive at target CPA for fractional-services offer (~€5-15k/mo × 3-month LTV).
- Warm-referral-only: rejected — hard ceiling at solo network size.

---

## 2. Necessity test — is this processing proportionate?

**Data collected per lead**:
- First name, last name (public, from LinkedIn / company website)
- Professional email address (derived via AnymailFinder + Million Verifier from company domain — see Section 4 Safeguards)
- Job title, company name (public)
- LinkedIn URL (public)
- Location: Paris / Île-de-France (public, from LinkedIn)

**Data NOT collected**:
- Personal phone numbers, home addresses, non-professional email addresses
- Any special-category data (health, political opinions, religion, sexual orientation, biometric)
- Financial data
- Data on family members, minors, or non-professional relationships

**Retention**: raw sourced-lead data retained for 12 months from date of first outbound touch. Suppression list (unsubscribes, negative replies, bounces) retained **indefinitely** to prevent recontacting anyone who has previously opted out.

**Data minimization**: only professional identifiers necessary to compose a role-relevant cold email. No enrichment beyond what's required to personalize the opening line (specific role + company signal).

**Proportionality**: single outbound touch + one follow-up if no reply, then permanent suppression. Not a nurture sequence. Not repeated contact.

---

## 3. Balancing test — legitimate interest vs data subject rights

### 3.1 Nature of the interest
**Ours**: pursuing customer acquisition for a legitimate business offering fractional AI product-management services to French SMBs. B2B commercial outreach is CNIL-permitted under LCEN L34-5 without prior consent for professional addresses (verified against CNIL 2023 doctrine + Overloop 2026 guidance).

**Theirs**: right not to be contacted for commercial purposes without a prior relationship; right to be forgotten; right to object.

### 3.2 Impact on recipients
- Low: one email (max two, if no reply), professional context, role-relevant offering
- Recipient always has 1-click unsubscribe, honored within 24 hours by the Cloudflare Worker suppression pipeline
- No cross-channel harassment: email-only, no phone follow-up, no LinkedIn DM chase, no ad-retargeting

### 3.3 Reasonable expectations
Professional email addresses on B2B platforms (LinkedIn, company websites) are, in French legal and cultural context, subject to commercial outreach for role-relevant offers. Recipients expect occasional B2B commercial email in exchange for maintaining a public professional presence.

### 3.4 Safeguards (see Section 4)

### 3.5 Conclusion of balancing test
**Legitimate interest prevails**, PROVIDED all Section 4 safeguards are operational at the time of send. If any safeguard is degraded or missing, sending stops until restored.

---

## 4. Safeguards operational at the time of send

- ✅ **Working unsubscribe link** on every email (Instantly-managed, verified before campaign flip)
- ✅ **1-click opt-out** processed within 24 hours via the Cloudflare Worker suppression pipeline into `config/suppression.json` — the pipeline hard-fails the send if the target email is in the suppression list
- ✅ **Sender identity accurate**: real name (Debanjan Mazumdar), real business (ProdCraft AI Studio), reachable inbox
- ✅ **Sender address in French format** compliant with LCEN L33-4-1 (mailbox address = clear identification)
- ✅ **Postal address** included in email footer per CNIL guidance (Paris address)
- ✅ **Reason for contact** clear in the email body (fractional AI PM services offered to their role)
- ✅ **No dark patterns** in unsubscribe flow (single-click, no confirmation-then-uncheck-boxes, no login required)
- ✅ **Retention limits enforced**: 12-month max for sourced-lead data; indefinite for suppression list only
- ✅ **Data breach notification procedure**: CNIL notified within 72h if suppression list or lead data is exposed
- ✅ **Vendor DPA in place**: Instantly ToS + Primeforge + Litemail ToS acknowledged (US-region data processing acceptable for B2B professional addresses under GDPR Chapter V standard contractual clauses)
- ✅ **Data-subject-request response procedure**: DSR requests to debolshop@gmail.com answered within 30 days per GDPR Art. 12
- ✅ **CNIL response playbook** in `docs/legal/cnil_response_playbook.md`
- ✅ **Audit trail**: every send logged with timestamp, mailbox used, personalization variables, delivery status. Retention 12 months.

---

## 5. Review triggers

This LIA must be re-reviewed and updated when ANY of the following occur:
- CNIL issues new guidance on B2B cold-email cold-outreach practices
- Scale changes materially (e.g., 30 mailboxes → 100+ mailboxes; ICP change)
- Any recipient files a formal complaint with CNIL
- Any DSR request cites GDPR Article 21 (right to object)
- Any French court ruling narrows LCEN L34-5 B2B carve-out
- Any change to the vendor stack that alters data-processing jurisdiction

Automatic re-review: **every 12 months** minimum, on the anniversary of first send.

---

## 6. Retention & deletion schedule

| Data class | Retention period | Deletion trigger |
|---|---|---|
| Sourced-lead raw records (LinkedIn scrape via Apify) | 12 months from first outbound touch | Automatic monthly cron |
| Personalization variables (per-lead) | 12 months | Same |
| Send log (timestamp, mailbox, delivery status) | 12 months | Same |
| Reply / positive-reply data | 24 months (for CRM purposes) | Manual quarterly review |
| Suppression list (unsubscribes, bounces, complaints) | **Indefinite** | Never — must persist to prevent re-contact |
| CNIL complaint response evidence | 5 years (statute of limitations) | Manual review |

---

## 7. Data subject rights honored

- **Right to information** (Art. 13-14): served via privacy notice at `prodcraft.fyi/privacy` linked from every email footer
- **Right of access** (Art. 15): DSR to debolshop@gmail.com, response within 30 days
- **Right to rectification** (Art. 16): same channel
- **Right to erasure / to be forgotten** (Art. 17): unsubscribe link processes this instantly; DSR channel for full erasure requests
- **Right to restriction** (Art. 18): DSR channel
- **Right to data portability** (Art. 20): DSR channel — exported as JSON on request
- **Right to object** (Art. 21): unsubscribe link is the primary channel; DSR for edge cases

---

## 8. Signature

By signing below, I confirm this LIA reflects my understanding of the legitimate interest basis, the balancing test, and the safeguards, and I take responsibility for the processing described.

**Signed**: __________________________________ (Debanjan Mazumdar)
**Date**: _______________
**Role**: Sole proprietor, ProdCraft AI Studio
**Address**: [Operator to fill Paris business address here — same as email footer]

---

## Sources / references
- CNIL guidance on B2B cold email (2023): https://www.cnil.fr/fr/spam-b2b
- LCEN L34-5 French Post & Electronic Communications Code
- GDPR Art. 6(1)(f), Art. 21, Art. 12-22
- Overloop B2B FR cold email 2026 guide: https://overloop.com/fr/blog/b2b-cold-email-france-cnil-rgpd
- Prospeo GDPR cold email B2B: https://prospeo.io/s/gdpr-cold-email-b2b
