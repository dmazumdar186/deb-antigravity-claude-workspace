# Cold Email Proposal

One template for every cold-email lead-gen client. Per client you edit one JSON file; the
pricing table, commission examples, risk disclosures and agreement paragraph are generated,
so the contract text cannot contradict the price table.

The standing terms are in `STANDARD_TERMS.md`. They are the original author's terms and are
a starting point: read them and change them to yours before the first real send.

## Files

| File | Role |
|---|---|
| `clients/<slug>.json` | The only per-client file. Copy `clients/_TEMPLATE.json`. |
| `clients/_demo-example.json` | A filled-in fictional example to copy the voice from. |
| `tool_costs.json` | Shared tool prices + `last_verified` date. Update here, never per client. |
| `template_coldemail.html` | The 9-page template. |
| `build_coldemail.py` | Renders pricing, commission examples and the agreement from `pricing.model`. |

## Build

```bash
python3 build_coldemail.py clients/<slug>.json
```

```bash
vercel deploy --prod --yes
```

The first build mints a random slug. Save it back into the config as `company_slug` so
redeploys keep the same URL.

## Pricing models

Set `pricing.model`:

- `commission_only`: a percentage of each closed deal, no retainer.
- `retainer_plus_commission`: monthly retainer plus a percentage, with an optional step-up.

Both live in `render_pricing()` in `build_coldemail.py`. A third model is one new branch there.

## Page map

1. Cover · 2. The Problem · 3. The System + Targets · 4. Tech Stack · 5. Investment
6. Setup & Roadmap · 7. What to Expect · 8. Next Steps · 9. Agreement + signature

Page 7 carries the honest risk disclosures: mailbox burnout, platform rule changes,
subscription price drift, LinkedIn account risk, and the billing terms in plain English.

## Where the terms are written (change all three together)

1. `STANDARD_TERMS.md`: the reference list.
2. `template_coldemail.html`: the "What to Expect" page and the tools footnote.
3. `build_coldemail.py`: `render_pricing()`, `render_linkedin()`, the `AGREEMENT_BODY`
   paragraph in `main()`, and `CONVERSION_MARKUP` (the +3% on tool costs).

## Before every send

- `last_verified` in `tool_costs.json` older than about 60 days: re-check the prices first.
- Load the deployed page. No `{{` anywhere, pricing matches what was agreed, commission
  arithmetic is right.
