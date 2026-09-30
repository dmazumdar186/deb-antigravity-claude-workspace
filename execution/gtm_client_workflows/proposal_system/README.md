# proposal_system

Editable, tracked client proposals. Modelled on the reference system in
`deliverables/_samples/proposal-system/` (Siva's Vercel + Telegram build) with two changes
requested by the operator: the primary output is a **DOCX** the operator can paste into a
Google Doc and edit, and hosting/tracking runs on **Cloudflare Workers** (workspace standing
order: Cloudflare only) instead of Vercel.

| File | Role |
|---|---|
| `proposals/<slug>.json` | One file per proposal: parties, dates, and an ordered list of blocks (`h1`, `h2`, `h3`, `p`, `note`, `bullets`, `numbered`, `table`, `kv`, `signature`, `pagebreak`). `**bold**` is the only inline markup. |
| `build_proposal.py` | Renders `out/<slug>/<slug>.docx` (Arial, plain styling, Google-Docs friendly), `.html` (tracked web copy) and `.md` (paste-ready). Refuses unknown block types and ragged tables. |
| `publish_proposal.py` | Uploads the HTML to the Worker's KV and prints the tracked URL; `--opens` lists opens; `--delete` removes. |
| `worker/` | Cloudflare Worker `proposal-tracker`: `GET /p/<slug>` serves the proposal, `GET /o/<slug>.gif` is an open pixel, `POST /api/track` accepts `{slug, client, event, extra}` exactly like the reference `api/track.js`. Every human open sends a Telegram message (city, country, device, open count, time). Bots, link previewers, `?me=1` and refreshes within 60 s are logged but not pushed. |

## Section order (same as the reference template)

Cover → 01 The Situation → 02 What It Is Costing You (four problems) → 03 What You Get (four benefits) → 04 Scope of Work (phases, throughout, out of scope, client inputs) → Timeline → 05 Service Levels → 06 Investment (milestone table, recurring, add-ons, totals, payment terms) → Related Systems → 07 Agreement and Terms → signature block.

## Build

```bash
python3 execution/gtm_client_workflows/proposal_system/build_proposal.py greenjobs-keith-v1 \
  --track-url https://<worker>/api/track --pixel-url https://<worker>/o/greenjobs-keith-v1.gif
```

## Deployed 2026-09-30 at https://proposal-tracker.debanjan186.workers.dev (KV 9e6b1a42…). To redeploy

```bash
cd execution/gtm_client_workflows/proposal_system/worker
wrangler kv namespace create PROPOSALS        # paste id into wrangler.toml
wrangler secret put TELEGRAM_BOT_TOKEN
wrangler secret put TELEGRAM_CHAT_ID
wrangler secret put PUBLISH_SECRET
wrangler deploy
```

Then `PROPOSAL_WORKER_URL=https://proposal-tracker.debanjan186.workers.dev PROPOSAL_PUBLISH_SECRET=... python3 publish_proposal.py greenjobs-keith-v1`.
Health: `GET /health`. The Google Doc itself cannot fire a webhook on open; send Keith the `/p/<slug>` link (or embed the pixel URL as a linked image in the Doc) to get the Telegram ping.
