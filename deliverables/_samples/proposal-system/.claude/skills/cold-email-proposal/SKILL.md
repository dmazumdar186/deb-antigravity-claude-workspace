---
name: cold-email-proposal
description: Build and deploy a standard cold email lead-gen proposal for a new client. Use when the user says "cold email proposal for <client>", "new cold email proposal", or has a discovery/kickoff call to turn into a signable cold-email proposal.
---

# Cold Email Proposal

One standard proposal for the cold-email offer. Per client about 8 fields change; every
term, risk disclosure and legal sentence is generated from the standard.

**Read first:** `STANDARD_TERMS.md`. Those terms are fixed; do not re-ask the user about
billing dates, refunds, notice periods, the tool-cost markup, or the risk disclosures.

## Files

| File | Role |
|---|---|
| `clients/<slug>.json` | The only per-client file. Copy `clients/_TEMPLATE.json`. |
| `clients/_demo-example.json` | A worked example of the content voice. |
| `tool_costs.json` | Shared tool prices. Update here, never per client. |
| `template_coldemail.html` | The 9-page template. Rarely edited. |
| `build_coldemail.py` | Renders pricing and the agreement from `pricing.model`. |

## Steps

### 1. Intake: ask only what varies, in ONE batch

1. **Client**: company, contact name, title.
2. **Niche and what they sell**, and rough deal size (drives the commission examples).
3. **Payment terms**: `commission_only` or `retainer_plus_commission`? The percentage, the
   retainer amount if any, and any step-up trigger.
4. **LinkedIn**: their Sales Navigator account (`client_account`) or a funded seat on the
   owner's side (`my_account`)?
5. **Where the list comes from** for this niche.

Do not ask about a setup fee unless the user raises it.

### 2. Check tool prices are not stale

Read `last_verified` in `tool_costs.json`. If it is older than about 60 days, list the
prices and ask the user to confirm them before the proposal goes out.

### 3. Write the client config

Copy `clients/_TEMPLATE.json` to `clients/<slug>.json`. Fill client, project, `pricing`,
`linkedin_option`, and the `content` block (problems, system_steps, targets, funnel,
timeline, next_steps) written for this niche in the client's language. Keep the `sender`
block as it is in the template. Leave `company_slug: null` on the first build.

### 4. Build

```bash
python3 build_coldemail.py clients/<slug>.json
```

The build refuses to write if any placeholder is unfilled. Save the generated slug back into
the config as `company_slug` so redeploys keep the same URL.

### 5. Deploy and verify

```bash
vercel deploy --prod --yes
```

Load `<base_url>/<slug>` (`base_url` is in `settings.json`) and confirm: it returns 200, no
`{{` remains, the pricing table matches what the user said, and the commission examples do
the right arithmetic. A build that ran is not proof; a page that renders correctly is.

## Adding a pricing model

Both models live in `render_pricing()` in `build_coldemail.py`. A third model is one new
branch there: the table row, the agreement sentence and the commission term all come from
that one function so they cannot drift apart.
