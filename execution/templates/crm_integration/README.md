# CRM Integration Template

A production-grade template for **bidirectional CRM sync + webhook receive** with
the workspace's audit-stack discipline baked in from day 1.

Scaffold a new tenant integration with:

```powershell
py execution/templates/scaffold_crm_integration.py \
    --slug acme_hubspot \
    --provider hubspot \
    --destination google_sheet
```

That copies this template to
`execution/gtm_client_workflows/acme_hubspot/`, wires the correct adapter,
seeds a config file, and prints next steps.

---

## When to use this template

You need this when:
- A client asks for **records to flow both ways** between their CRM and your system of record
  (Google Sheet, Postgres, KV, another CRM).
- Records must **stay in sync in near-real-time** — webhook receive is required,
  not just a daily poll.
- You want the sync to be **auditable, resumable, and rate-limit-safe** — not a
  best-effort script.

You don't need this when:
- You need a one-shot export from a CRM. Use a per-provider CLI + `pandas` instead.
- You need >20 provider connectors with schema discovery. Use Airbyte / Meltano
  (see [prior-art pass](#prior-art-pass) below).
- The client uses a CRM not listed in [Provider matrix](#provider-matrix). Add an
  adapter (see [Adding a provider](#adding-a-provider)).

---

## Prior-art pass

Per `~/.claude/rules/prior-art-first.md`, before shipping this template I checked
what already exists in the CRM sync space:

- **Airbyte / Meltano / Singer taps** — the industry standard for open-source CRM
  ELT. Massive footprint (Docker + Temporal + Postgres + Minio for Airbyte; Python
  + Meltano CLI + Singer spec for Meltano). Both cover 200+ connectors with schema
  discovery and incremental state. **Overkill for personal-scale / single-tenant
  client work**; installing and maintaining Airbyte for one HubSpot ↔ Sheet sync
  is a full ops project by itself.
- **Fivetran / Stitch / Hevo** — SaaS, proprietary. Not applicable.
- **Provider-native SDKs** — `hubspot-api-client`, `pyairtable`,
  `pipedrive-python`, `clickup-python`. These are the right building blocks for a
  lightweight adapter, but they don't give you: state persistence, dedup, rate-limit
  math, webhook signature verification, bidirectional conflict resolution, or an
  audit gate.
- **n8n / Zapier / Make** — GUI-based, per-record cost, not versionable in git.
  Fine for a client's ad-hoc automation, wrong for a repeatable client-work
  template.

**Recommended architecture**: a thin Python driver with a Singer-inspired
`Adapter` interface (list/get/create/update/subscribe_webhook), a JSON state
file for incremental watermarks, KV-backed idempotency sentinels, and a CF
Worker for webhook receive. **Crib from Singer's stream+state pattern; do NOT
crib from Airbyte's Docker footprint.** Provider SDK if it exists; hand-rolled
`httpx` client if not.

That is what this template implements.

---

## Provider matrix

| Provider   | Adapter                    | SDK dep                  | Webhook signature scheme         | Rate limit (default plan) |
|------------|----------------------------|--------------------------|----------------------------------|---------------------------|
| HubSpot    | `provider_adapters/hubspot.py`   | `hubspot-api-client`     | v3 signature (SHA-256 HMAC)      | 100 req / 10 s            |
| Pipedrive  | `provider_adapters/pipedrive.py` | `httpx` (no official SDK)| Basic auth on webhook URL        | 20 req / 2 s              |
| Attio      | `provider_adapters/attio.py`     | `httpx`                  | HMAC-SHA256, header `x-attio-sig`| 200 req / min             |
| ClickUp    | `provider_adapters/clickup.py`   | `httpx`                  | HMAC-SHA256, header `X-Signature`| 100 req / min per token   |
| Airtable   | `provider_adapters/airtable.py`  | `pyairtable`             | MAC (Airtable webhooks API v0)   | 5 req / s per base        |

Rate limits are approximate defaults — confirm against your tenant's plan in
`config/tenant.example.json`.

---

## Adding a provider

1. Copy `provider_adapters/base.py` to `provider_adapters/<name>.py`.
2. Implement the six methods: `list_records`, `get_record`, `create_record`,
   `update_record`, `subscribe_webhook`, `verify_webhook_signature`.
3. Add a rate-limit config in the class (`REQUESTS_PER_WINDOW`,
   `WINDOW_SECONDS`).
4. Register the adapter name in `provider_adapters/__init__.py`.
5. Add a fixture in `tests/fixtures/<name>_record.json`.
6. Add unit tests in `tests/unit/test_mapping.py` for the record shape.
7. Update the [Provider matrix](#provider-matrix) table above.

---

## Onboarding a new tenant

1. Scaffold from this template with `scaffold_crm_integration.py`.
2. Fill in `config/tenant.<slug>.json` (copy from `tenant.example.json`).
3. Add credentials to `.env` — never inline them in the config file.
4. Run `py sync.py --tenant <slug> --dry-run` to preflight-check config
   + rate limits + destination reachability.
5. Run `py sync.py --tenant <slug>` for the first real pull.
6. Deploy the webhook receiver: `wrangler deploy` from the tenant directory.
7. Subscribe the webhook via `py sync.py --tenant <slug> --subscribe-webhook`.
8. Verify with `bash tests/front_door_crm.sh <deployed-url> <secret>`.

---

## Running locally

```powershell
# Preflight — no external mutations, prints would_* counters
py execution/templates/crm_integration/sync.py --tenant example --dry-run

# Full sync
py execution/templates/crm_integration/sync.py --tenant example

# Sync only new records since last watermark (default; --full-refresh overrides)
py execution/templates/crm_integration/sync.py --tenant example --incremental
```

---

## Deploying the webhook Worker

```powershell
cd <tenant-dir>
wrangler kv:namespace create WEBHOOK_DEDUP
# Copy the resulting namespace ID into wrangler.toml
wrangler secret put WEBHOOK_SECRET
wrangler deploy
```

---

## Monitoring drift

Every sync run writes a JSONL line to `.tmp/crm_sync_runs/<tenant>.jsonl` with:

```json
{"ts": "2026-08-04T12:34:56Z", "tenant": "acme",
 "records_fetched": 42, "records_created": 3, "records_updated": 5,
 "records_skipped_dedup": 34, "errors": 0, "elapsed_ms": 4217,
 "watermark_before": "2026-08-04T11:00:00Z",
 "watermark_after":  "2026-08-04T12:34:52Z",
 "cost_eur_estimate": 0.0}
```

The `HARDENING.md` template lists the queries to run against that log to spot
drift (silent zeros, watermark stall, error spikes).

---

## Costs (EUR)

- Sync driver is **€0** unless the destination is a paid API (Postgres, ClickHouse).
- CF Worker for webhook receive is **€0** under Workers Free (100k req/day).
- KV dedup entries: **€0** under KV Free (1k writes/day).
- If a provider SDK calls the CRM, that's the tenant's CRM-plan quota — this
  template does not add cost on top.
- No LLM calls in the default path. Optional field-mapping suggester (behind
  `--suggest-mapping` flag) uses Gemini 2.5 Flash (free tier) per
  `~/.claude/rules/model-tier.md`.

---

## Rule compliance

- **`front-door-synthetic.md`** — `tests/front_door_crm.sh` hits the deployed
  webhook URL with a signed test event and asserts KV dedup appears.
- **`output-acceptance-gate.md`** — `tests/acceptance_crm_sync.py` hits a real
  sandbox CRM and does a round-trip create → sync → verify → delete. Hard-fails
  on drift.
- **`live-artifact-acceptance.md`** — `tests/front_door_crm.sh` asserts the
  deployed `webhook_receiver.ts` is git-tracked before treating the URL as
  green.
- **`prior-art-first.md`** — see [Prior-art pass](#prior-art-pass) above.
- **`python-hardening.md`** — subprocess calls include
  `encoding="utf-8", errors="replace"`; threading around parallel pagination
  uses `threading.Lock`; provider-response paths are validated before write.
- **`model-tier.md`** — optional LLM path defaults to Gemini 2.5 Flash.
- **`currency-eur.md`** — cost fields use `cost_eur_estimate`.
- **`always-parallelize.md`** — pagination pages fetch in parallel via
  `ThreadPoolExecutor` (bounded by rate-limit math in the adapter).

---

## Files

| File / dir                           | Purpose                                                   |
|--------------------------------------|-----------------------------------------------------------|
| `sync.py`                            | Bidirectional sync driver (CLI entrypoint)                |
| `mapping.py`                         | Pure record-shape transforms (unit-testable)              |
| `webhook_receiver.ts`                | CF Worker Function: verify signature, dedup, dispatch     |
| `wrangler.toml.example`              | Worker config, KV binding, secrets refs                   |
| `provider_adapters/`                 | Pluggable adapter classes per CRM                         |
| `destinations/`                      | Where synced records land (Sheet / JSONL / KV / DB)       |
| `config/tenant.example.json`         | Per-tenant config (env var refs, mappings, quotas)        |
| `config/schema.py`                   | Config validation (fail-fast at boot)                     |
| `tests/unit/`                        | Pure-function tests (fast)                                |
| `tests/integration/test_sync_dry_run.py` | Sync driver against a fixture provider                |
| `tests/acceptance_crm_sync.py`       | Real sandbox CRM round-trip                               |
| `tests/front_door_crm.sh`            | Deployed webhook probe                                    |
| `.github/workflows/ci.yml`           | Unit + integration on push; acceptance gated on env flag  |
| `HARDENING.md`                       | Per-tenant hardening ledger                               |
| `HANDOFF.md`                         | Handoff template                                          |
| `.env.example`                       | Required env vars                                         |

---

## Not installed by default (see `requirements.txt`)

- `hubspot-api-client`, `pyairtable`, `clickup-python`, `pipedrive-python`,
  `httpx`, `python-dotenv`, `pydantic`, `google-api-python-client`.

`pip install -r requirements.txt` takes >2 min for the full set. Install only
the adapters your tenant needs.
