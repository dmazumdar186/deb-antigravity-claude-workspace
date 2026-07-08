# Legitimate Interest Assessment (LIA) — Self-Outbound v2

**Effective:** 2026-07-08. Reviewed by operator every 12 months minimum. Kept on file per GDPR/CNIL requirement for B2B cold email using legitimate-interest basis.

## Controller

- **Name:** Debanjan Mazumdar (dba ProdCraft)
- **Address:** TO_FILL_IN_PHASE_1 (must be a real physical postal address, appears in every outbound email footer)
- **Contact:** debolshop@gmail.com

## Purpose test — legitimate interest identified

The controller has a legitimate business interest in identifying and initiating first contact with B2B decision-makers (Founders, Heads of Product/Ops, Agency Owners) who have public-facing indicators of needing AI product-engineering services. The interest is commercial (client acquisition) and lawful.

## Necessity test — is direct outreach necessary?

Direct email outreach to publicly-listed business contacts is necessary because:
1. The prospect's job function makes them the correct decision-maker for the service offered.
2. No other channel reliably reaches this ICP at the scale needed (LinkedIn DM open rates are lower; cold call is more intrusive; ad targeting doesn't reach the specific individual).
3. The volume (20/day, 600/month) is proportionate to a solo operator's capacity, not a mass-broadcast pattern.

## Balancing test — the prospect's rights and interests

- **Data used:** only publicly-listed business email address, name, title, company. No personal data outside professional context. No special-category data.
- **Reasonable expectation:** decision-makers at businesses reasonably expect to receive relevant B2B service pitches to their business email.
- **Impact:** minimal — one email, unsubscribe available in every message, follow-up capped at 2 messages, immediate suppression on opt-out.
- **Safeguards implemented:**
  1. Unsubscribe link in every email (Instantly-tracked).
  2. Physical postal address in every email footer.
  3. Opt-out honored automatically (`suppression.json`, minimum 30-day retention).
  4. Explicit "reply STOP" pattern also honored via reply classifier's `negative` bucket.
  5. Anti-ICP filter rejects roles unlikely to want the offer (recruiters, students, interns).
  6. Language gate: emails only to prospects with public content in EN or FR (the operator's working languages).
  7. Domain suppression: never contact prospects from operator's client / lockdown domains (AM lockdown).

## Data retention

- Contacted prospects: retained in campaign log for 12 months, then archived.
- Suppressed prospects: retained indefinitely on suppression list (regulatory floor 30 days).
- Reply content: retained 24 months for follow-up / audit trail, then deleted.

## Rights the prospect has

- Right to object (unsubscribe link + reply STOP): honored immediately, permanent suppression.
- Right to access: prospect may email debolshop@gmail.com to request all data held.
- Right to erasure: honored on request, though suppression record (email address only) must be retained per anti-spam obligations.
- Right to lodge complaint with CNIL (data.gouv.fr / cnil.fr).

## Outcome

Legitimate-interest basis is **valid** for this outreach subject to the safeguards above. Reviewed by operator on 2026-07-08. Next review: 2027-07-08.
