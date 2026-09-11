# Getting API keys: PeopleDataLabs, Crustdata, Apollo.io

Written 2026-09-10 for the Radar `sources/pdl.py` / `sources/crustdata.py` /
`sources/apollo.py` plugins. Sources cited inline; anything the automated
fetch could not confirm is marked **UNVERIFIED** rather than guessed.

Once a key is obtained, put it in the workspace `.env` (never commit it) as
the exact env var name each module reads:

```
PDL_API_KEY=...
CRUSTDATA_API_KEY=...
APOLLO_API_KEY=...
```

---

## PeopleDataLabs (PDL)

1. **Sign up**: `https://www.peopledatalabs.com/signup` redirects to
   `https://dashboard.peopledatalabs.com/signup` (Auth0-backed login/signup
   flow). Verified live via fetch 2026-09-10 (308 redirect observed).
2. **Free credits**: **UNVERIFIED**. The signup page is behind an
   authentication redirect the automated fetcher could not render past, and
   `docs.peopledatalabs.com/docs/authentication` explicitly states API keys
   are issued via account manager / `support@peopledatalabs.com` contact
   rather than instant self-service in the docs' own text — but the
   dashboard signup flow is self-service per its URL shape. Confirm the
   current free-tier credit count in-dashboard after signing up; PDL has
   publicly advertised a small free trial credit allotment in the past, but
   no exact number could be confirmed from the docs pages reachable today.
3. **Where the key lives**: not directly confirmed by an automated fetch
   (the dashboard requires a login session). Standard PDL practice, per
   `docs.peopledatalabs.com/docs/authentication`, is an **API Keys** section
   of the dashboard once logged in at `dashboard.peopledatalabs.com`; the
   key is used as the `X-Api-Key` request header (confirmed,
   `docs.peopledatalabs.com/docs/quickstart-person-search-api`, fetched
   2026-09-10).
4. **Plan needed for Person Search**: **UNVERIFIED** exact tier name.
   `docs.peopledatalabs.com/docs/reference-person-search-api` confirms
   Search is billed "per record retrieved" and a distinct rate limit
   ("10 requests/minute" default) applies, implying it is available beyond
   a pure free tier, but the docs pages reachable today did not render a
   pricing/plan table (`docs.peopledatalabs.com/docs/pricing` redirects to
   `www.peopledatalabs.com/pricing`, which returned only its page title to
   the fetcher — likely client-side rendered).
5. **Test command** (requires `PDL_API_KEY` set):
   ```
   cd execution
   python3 -m gtm_client_workflows.gaia_sourcing.run --coverage-test pdl --niche structural
   ```
   Fails loudly with a `ProviderNotConfigured` message (naming this file) if
   the key is absent.

Docs read: `docs.peopledatalabs.com/docs/{authentication,
reference-person-search-api, input-parameters-person-search-api,
quickstart-person-search-api, reference-person-enrichment-api, fields}`,
`www.peopledatalabs.com/pricing`, `dashboard.peopledatalabs.com/signup` — all
fetched 2026-09-10.

---

## Crustdata

1. **Sign up**: `https://app.crustdata.com/auth/login` (confirmed live via
   fetch of `crustdata.com`, 2026-09-10) — the same login screen handles new
   sign-ups.
2. **Free credits**: Crustdata's marketing page states a **"Free sandbox
   key, full API, MCP server and skill templates"** are available to
   developers via that login/"Start building" flow (verbatim phrase seen on
   `crustdata.com`, fetched 2026-09-10). The exact sandbox credit allotment
   is **UNVERIFIED** — not stated on the page reached.
3. **Where the key lives**: sign in at `app.crustdata.com`; API key
   management is referenced generally by their docs
   (`docs.crustdata.com`) but the specific dashboard menu path is
   **UNVERIFIED** (the docs' dedicated authentication page did not render
   content to the automated fetcher on 2026-09-10 -- likely
   client-rendered). Every API call needs three headers, confirmed from
   `docs.crustdata.com/person-docs/search/introduction`:
   `Authorization: Bearer <key>`, `x-api-version: 2025-11-01`,
   `content-type: application/json`.
4. **Plan needed for people search**: **UNVERIFIED** exact plan/tier name.
   The docs describe "credit-based usage tiers" and "monthly and annual
   payment plans" generically; Person Search itself is billed per the docs
   as "0.03 credits per result returned" (confirmed,
   `docs.crustdata.com/person-docs/search/introduction`), which is
   consistent with it being available on the free sandbox key at low
   volume, but that is an inference, not a confirmed plan-gating statement.
5. **Test command** (requires `CRUSTDATA_API_KEY` set):
   ```
   cd execution
   python3 -m gtm_client_workflows.gaia_sourcing.run --coverage-test crustdata --niche structural
   ```
   Fails loudly with a `ProviderNotConfigured` message (naming this file) if
   the key is absent.

Docs read: `crustdata.com`, `docs.crustdata.com`,
`docs.crustdata.com/person-docs/search/introduction`,
`docs.crustdata.com/person-docs/enrichment/reference`,
`docs.crustdata.com/docs/pricing` (did not render) — all fetched 2026-09-10.

---

## Apollo.io

1. **Sign up**: `https://www.apollo.io` (general marketing site) → account
   creation flow. Free-plan existence confirmed indirectly: Apollo's own
   rate-limit documentation
   (`docs.apollo.io/reference/rate-limits`, fetched 2026-09-10) names a
   **"Free"** plan tier explicitly (with its own, lower, rate-limit row), so
   a no-cost tier exists; the exact signup URL/flow and any free credit
   count on that tier are **UNVERIFIED** — `www.apollo.io/pricing` returned
   only a page title to the fetcher (mentioned "50 credits" in passing for
   what reads as a trial context, but not attributably to a specific plan).
2. **Where the key lives**: confirmed. `docs.apollo.io/docs/create-api-key`
   states: **"Launch Apollo and click Settings > Integrations > API
   Keys."** (verbatim, fetched 2026-09-10).
3. **Plan needed for People Search / People Enrichment API access**:
   **UNVERIFIED** exact tier. Apollo's own docs state generically that
   *"Access to Apollo API depends on your Apollo plan"*
   (`docs.apollo.io/docs/create-api-key`, fetched 2026-09-10) without
   naming the minimum tier; the Free plan does appear in the rate-limits
   table for both Search and Enrichment endpoint categories (50/min,
   200/hr, 600/day for Free-tier search — see
   `docs.apollo.io/reference/rate-limits`), which suggests at least some
   API access exists on Free, but whether People Search/Enrichment
   specifically requires a paid seat is not stated on the pages reached.
4. **Auth header**: confirmed, `x-api-key: <APOLLO_API_KEY>` on every
   request (`docs.apollo.io/reference/authentication`, fetched 2026-09-10).
5. **Test command** (requires `APOLLO_API_KEY` set):
   ```
   cd execution
   python3 -m gtm_client_workflows.gaia_sourcing.run --coverage-test apollo --niche structural
   ```
   Fails loudly with a `ProviderNotConfigured` message (naming this file) if
   the key is absent.

Docs read: `docs.apollo.io/reference/{people-enrichment, rate-limits,
authentication}`, `docs.apollo.io/docs/create-api-key`,
`www.apollo.io/product/enrich`, `www.apollo.io/pricing` (did not render) —
all fetched 2026-09-10.

**Note on the People Search endpoint specifically**: `sources/apollo.py`
calls `POST /v1/mixed_people/search`, which is Apollo's long-published
public search endpoint, but this exact reference page 404'd for the
automated fetcher on 2026-09-10 under both guessed slugs
(`/reference/people-search`, `/reference/search-for-people`). The endpoint
path, auth, and base URL are shared with the confirmed People Enrichment
endpoint (same `api.apollo.io/api/v1` base, same `x-api-key` header), so
this is treated as a documented-elsewhere path rather than a guess, but it
is flagged **ASSUMED** in `sources/apollo.py`'s own module docstring — treat
the first live `--coverage-test apollo` run as a contract check on the
response shape (`people`/`contacts` array + `pagination` object), the same
way `integrations/recruit_crm.py` already treats its own unresolved payload
shapes per HANDOFF.md's 2026-09-10 entry.

---

## Overall coverage-test go/no-go

Per RADAR_CONTRACTS.md §A: `run.py --coverage-test <provider> --niche
structural|transport` builds a query ("chartered engineer" + niche terms,
Ireland counties), fetches one page (limit 50), and prints matched / with
title / with employer / with dates / with city / cost plus a go/no-go line
(≥ 40 of the 50 matched need title+employer+dates to call the provider a
viable source for that niche).
