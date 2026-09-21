# prodcraft-preview-host

Cloudflare Worker serving med-spa concept previews from R2 on wildcard
`*.preview.prodcraft.fyi` hosts. See `../../CONTRACTS.md` for the full contract.

## One-time setup

```bash
npm install
npx wrangler r2 bucket create prodcraft-previews
npx wrangler kv namespace create META
# paste the returned id into wrangler.toml's [[kv_namespaces]] block
npx wrangler secret put SUPABASE_URL
npx wrangler secret put SUPABASE_SERVICE_KEY
npx wrangler secret put REMOVE_WEBHOOK_SECRET
npm run deploy
```

## DNS

Add a wildcard CNAME `*.preview` -> this zone's target, proxied (orange
cloud), on the `prodcraft.fyi` zone. The Worker route
`*.preview.prodcraft.fyi/*` picks up all matching requests.

## How the Python side publishes

`preview/build_preview.py` uploads the built static site straight to R2 via
the S3-compatible API under `previews/{slug}-{suffix}/`, then calls
`POST /api/publish` (bearer `REMOVE_WEBHOOK_SECRET`) with
`{host, expires_at, business_id, preview_id}` to arm the host in KV.
`POST /api/extend` renews `expires_at`; `GET /api/meta?host=` reads it back.
