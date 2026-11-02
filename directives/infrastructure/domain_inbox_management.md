# Domain & Inbox Management

## Goal
Document the infrastructure layer for the Accessory Masters cold email system: domain purchasing, DNS configuration, inbox provisioning, warmup management, and domain rotation. This is primarily Bryce's domain but documented here so the pipeline builder understands the constraints and dependencies.

## When to Use
Reference when onboarding new team members, when inbox capacity changes, when domains need rotation (month 3-6), or when debugging deliverability issues.

## Inputs
- No script inputs — this is an operational SOP, not an automated script
- References Bryce's infrastructure decisions and timelines

## Tools/Scripts
- Instantly.ai — sending platform, campaign management, warmup (managed by Bryce)
- GoDaddy — domain registration (managed by Bryce)
- Inboxology — inbox provisioning, Google + Microsoft accounts (managed by Bryce)
- Cloudflare Workers — backend automation hosting, $5/month (deployed by Debanjan)

## Outputs
- 10 sending domains with SPF, DKIM, DMARC configured
- 32 inboxes (Google + Microsoft, ~50/50 split) connected to Instantly
- Warmup completed after 3-week cycle (started ~April 28, ready ~May 18)
- 1 pre-warmed test domain + 5 inboxes for system validation ($50/month, cancelable)

## Steps
1. Bryce purchases 10 sending domains on GoDaddy (~$11 each, ~$110 total)
2. Bryce purchases 1 separate website domain (NOT a sending domain)
3. Bryce configures DNS records for each sending domain: SPF, DKIM, DMARC
4. Bryce provisions 32 inboxes via Inboxology (~$112/month, Google + Microsoft mix)
5. Bryce connects all inboxes to Instantly.ai
6. Warmup begins automatically in Instantly (3-week cycle)
7. Bryce buys 1 pre-warmed test domain + 5 inboxes via Instantly ($50/month) for validation phase
8. Bryce creates test campaign in Instantly (targeting restaurants, non-core industry)
9. Pipeline pushes test leads to the test campaign via `POST /api/v2/leads`
10. After validation: Bryce creates real ICP campaigns, assigns warmed inboxes
11. Pipeline pushes real leads to real campaigns (~800/day across 32 inboxes)
12. Monitor deliverability via Instantly analytics + dashboard

## Edge Cases
- **Domain burn rate**: Sending domains degrade over 3-6 months of heavy sending. Plan to rotate domains at month 3-6. Bryce handles purchasing replacements and DNS setup.
- **Inbox warmup timeline**: 3 weeks minimum. Cannot send real campaigns before warmup completes (~May 18). Pre-warmed test inboxes allow system validation before then.
- **Google vs Microsoft split**: ~50/50 improves deliverability diversity. Google inboxes tend to have better deliverability to Gmail recipients; Microsoft to Outlook. Bryce decides exact split.
- **Instantly plan requirement**: Hyper Growth plan needed for reply webhooks. If on a lower plan, pipeline uses polling (every 30 min) instead of webhooks. Both architectures are supported.
- **Cloudflare Workers vs DNS**: The $5/month plan is for Workers (serverless functions), not just DNS/CDN. Make sure the account has Workers enabled.
- **Pre-warmed test cancellation**: Cancel the $50/month test domain + inboxes after Milestone 1 validation is complete (~1 month).
- **Sending volume per inbox**: ~25 emails/inbox/day to maintain reputation. 32 inboxes x 25 = 800/day target.

## Exit Criteria

<!-- TODO: tighten these predicates next time this directive is touched — it is an operational SOP with no executable script, so automated assertions aren't available -->
- All 10 sending domains have SPF, DKIM, and DMARC records configured — confirmed by running each domain through MXToolbox DMARC check and receiving a `PASS` result.
- All 32 inboxes appear as `active` in Instantly.ai and are assigned to at least one campaign.
- Instantly.ai warmup dashboard shows all 32 inboxes have completed ≥ 21 days of warmup (warmup start date ≤ today − 21 days).
- A test push of one lead to the pre-warmed campaign via `POST /api/v2/leads` returns HTTP 200 with a lead ID (no `401` or `422`).
- The `$50/month` pre-warmed test domain subscription is cancelled after Milestone 1 validation (no active test domain in Instantly billing).

## Changelog
| Date | Change |
|------|--------|
| 2026-04-29 | Created — initial infrastructure SOP for Accessory Masters |
