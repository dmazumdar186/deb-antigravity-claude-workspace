# Ask GreenJobs Worker (stub)

Phase-2 backend for the "Ask GreenJobs" panel. Not deployed by the demo; the
page runs a local TF-IDF matcher today and swaps to `POST /ask` on launch.

```bash
cd execution/gtm_client_workflows/greenjobs_redesign/worker
npx -y wrangler@4 secret put OPENROUTER_API_KEY   # key lives only here
npx -y wrangler@4 deploy
```

Contract: `prompt.md`. Model: `MODEL` var in `wrangler.toml` (GLM-5.3 or Kimi
K3 via OpenRouter). Rate limit per IP per minute; dataset read from the static
site's `data/jobs.json`, so there is one source of truth.
