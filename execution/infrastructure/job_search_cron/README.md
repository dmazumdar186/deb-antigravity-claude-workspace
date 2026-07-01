# job-search-cron — external CF cron trigger

**Purpose.** Fire the GitHub Actions `job_search_daily.yml` workflow every
morning at 09:15 Paris via Cloudflare Cron Triggers. Independent of GitHub
Actions scheduling → immune to GH cron drops.

**Why we need this.** 2026-07-01 audit exposed GitHub Actions dropping
scheduled workflows silently:
- 2026-06-30 → 0 scheduled runs (only manual dispatches)
- 2026-06-29 → 4h41m delay
- 2026-06-27 / 2026-06-26 → failed

The in-repo watchdog (`.github/workflows/job_search_watchdog.yml`) is the
first line of defense (24 hourly fires vs. GH). This Worker is the second
line: even if GH Actions is entirely degraded, this Worker fires from CF's
edge with a documented 99.9% SLA.

## One-time deploy

```powershell
cd execution/infrastructure/job_search_cron

# 1. Log into CF (opens browser, one-time).
wrangler login

# 2. Store your GH PAT as a Worker secret. Needs `workflow` scope on the
#    dmazumdar186/deb-antigravity-claude-workspace repo. Generate at
#    https://github.com/settings/tokens/new?scopes=workflow
wrangler secret put GITHUB_PAT

# 3. (Optional) Store a shared secret so the /?secret=X manual fetch works.
wrangler secret put WORKER_SECRET

# 4. Deploy.
wrangler deploy
```

Wrangler will print the Worker URL. The cron will fire on the next scheduled
minute automatically; no additional configuration.

## Verify the deploy

```powershell
# Wait for the next scheduled fire, then check:
gh run list --workflow=job_search_daily.yml --limit 3

# Or trigger manually via HTTP:
curl "https://job-search-cron.<subdomain>.workers.dev/?secret=<WORKER_SECRET>"
```

You should see a fresh `workflow_dispatch` run appear in `gh run list`.

## Revert

```powershell
wrangler delete job-search-cron
```

The workspace still functions after revert — the in-repo scheduled crons
(4/day) and hourly watchdog remain as the fallback.

## Rotate the PAT

```powershell
wrangler secret put GITHUB_PAT   # overwrites
```

No redeploy needed.
