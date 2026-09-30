# Standard Terms (cold email proposals)

The terms the cold-email template generates for every client. These are the original
author's defaults. **Edit them to your own terms** and mirror each change in
`template_coldemail.html` and `build_coldemail.py` (see `COLDEMAIL_README.md`).

## Business terms

- Billing starts on the signature date, not the 1st of the month.
- Charged upfront, at the start of each cycle.
- Cancellation: 30 days' written notice. Anything already paid is not refunded.
- Commission is invoiced when the client signs the deal with their customer, not when they
  collect payment.
- All tool subscriptions belong to the client, in their name, billed to them directly.
- Tool costs are billed at cost +3% (currency conversion and payment processing), stated as
  a footnote under the tools table.
- Response time: one business day. Positive replies are handed over as they land.
- No setup fee by default. Set `setup_fee` in a client config to charge one.

## Pricing models

| Model | Shape |
|---|---|
| `commission_only` | A percentage of each closed deal, no retainer. |
| `retainer_plus_commission` | Monthly fee plus a smaller percentage, optional step-up trigger. |

Default attribution: any deal where the first meeting was booked through our outreach.

## Risk disclosures (the "What to Expect" page)

1. **LinkedIn account risk.** Prospecting on the client's Sales Navigator account can get it
   restricted. They accept that, or they fund a seat on your side and you carry the risk.
2. **Subscription prices move.** Vendor pricing is outside your control.
3. **Platform policy shifts.** Sending limits and rules change; cost adapts with them.
4. **Mailboxes degrade.** Replacement is a certainty, and the replacement cost is the client's.
5. **Strategy changes can move cost either way.**

## Fixed content in every proposal

- The client owns all infrastructure. No lock-in.
- View-only CRM access requested, to track the lead journey.
- Out of scope: closing calls and proposals to the client's own prospects.
