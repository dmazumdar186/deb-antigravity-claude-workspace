---
name: create-proposal
description: Create and deploy a client proposal as a signable, payable, tracked HTML page on the owner's Vercel site. Invoke when the user says "new proposal", "send a proposal to", "build a proposal for", or pastes a kickoff/discovery call transcript. For the cold-email lead-gen offer (commission/retainer terms) use cold-email-proposal instead; this one is for custom consulting/project proposals with a Stripe payment link.
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
---

# Proposal Creator

Generates a signable HTML proposal hosted on Vercel, with an HTML5 canvas e-signature, a
Stripe payment button, and Telegram notifications on open / view / pay-click / sign.

Work from the project root (the folder holding `build.py`). The site address is `base_url`
in `settings.json`. If `settings.json` still holds the placeholder address, or `vercel link`
has never been run, walk the user through the one-time setup in `README.md` first.

## Step 1: Gather inputs

Extract from the user's message (ask ONE clarifying question if something critical is missing):

| Field | Example |
|---|---|
| Client name | Jane Smith |
| Client title | COO |
| Client company | Acme Corp |
| Project pitch | "Fix their onboarding + churn" |
| Pricing | "$6K/mo x 3 months" or "$20K total, split 3 ways" |
| Stripe payment link | `https://buy.stripe.com/...` |

Optional: website URL (for tone), pain points they mentioned, outcomes discussed.

## Step 2: Research (optional)

If a website was given, fetch it once to inform tone and framing. Do not over-research.

## Step 3: Write config.json

Build a complete config matching `config.example.json`. Take the `sender` block from
`config.example.json` (the owner's details). Write the content yourself:

- **4 problems** (~50 words each): specific, tied to business impact, "you" language
- **4 benefits** (~50 words each): concrete outcomes, numbers where possible
- **Scope**: 3 monthly milestones + "Throughout" + "Out of scope"
- **Investment**: 3 monthly payments summing to the total
- **Agreement body** + **ROI statement**

Rules: no em dashes, no generic filler, everything ties back to money. Set
`company_slug_base` to a URL-safe lowercase slug (e.g. `acme-corp`); the build appends a
6-character random suffix and saves the final slug back into the config.

Keep a copy of each client's config (e.g. `configs/<slug>.json`) so it can be rebuilt later.

## Step 4: Build, deploy, verify

```bash
python3 build.py
vercel deploy --prod --yes
```

The proposal lives at `<base_url>/<slug>`. Fetch that URL, confirm it returns 200 and that
no `{{` remains in the page. Return the URL with a one-line summary (client, total, any
assumptions made).

## Do not ask

- Do not ask about terminal commands, deployment, or file paths. Execute.
- Deploy to production: always `--prod --yes`.
- Do not show the JSON config unless asked.

## Ask only when

- The Stripe payment URL is missing
- Pricing is ambiguous ($6K over 3 months, or $6K/mo x 3?)
- The client company name is missing

## Never

- Delete or overwrite another client's `public/<slug>/` folder: every deploy uploads all of
  `public/`, so a removed folder takes that live proposal down.
- Write the Telegram token or any other secret into a file here. They live in Vercel env vars.
