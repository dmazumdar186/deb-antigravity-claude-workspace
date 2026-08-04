# workspace_heartbeat

Daily health probe of every deployed project in the workspace. Closes the two systemic patterns identified in `HARDENING_BACKLOG_WORKSPACE_2026-08-04.md`:

- **Pattern A** (untracked deployed artifacts) — probed by asserting the live URL returns real content, not a stale fallback.
- **Pattern B** ("shipped" claims surviving month-long silence — job_search_v2 34d, anthropic_watch 52d, prodcraft_autopilot 43d) — probed by the `freshness_field` in each project's `/health` JSON.

Three surfaces in one folder:

| File | Runs where | What it does |
|---|---|---|
| `src/index.js` + `wrangler.toml` | Cloudflare Worker, scheduled daily at 06:00 UTC | Live-URL probes of every project in `manifest.json`. Persists reports to KV; posts to Telegram if degraded. |
| `../freshness_monitor.py` | Locally + pre-push hook + weekly report | Reads the SAME manifest, computes git-log + run-log freshness. |
| `../weekly_hardening_report.py` | Locally (or GH Actions weekly) | Regenerates the workspace HARDENING report each Monday: SAST + freshness + shipped-claim commit sampling + untracked-Pages-Functions scan. |

The `manifest.json` in this directory is the single source of truth. Both the Worker and the Python scripts read it.

---

## Install / trigger

### 1. Local (no infra) — freshness monitor + weekly report

Already usable:

```bash
py execution/infrastructure/freshness_monitor.py --format human
py execution/infrastructure/freshness_monitor.py --format json  --level info
py execution/infrastructure/weekly_hardening_report.py
```

The pre-push hook (`.githooks/pre-push`, wired in Phase 1) auto-invokes freshness in WARN mode. Enable once per clone:

```bash
git config core.hooksPath .githooks
```

### 2. Cloudflare Worker (needs operator approval to deploy)

```bash
cd execution/infrastructure/workspace_heartbeat

# Create the KV namespace the Worker persists reports to.
npx wrangler kv namespace create HEARTBEAT_KV
# copy the returned id into wrangler.toml under [[kv_namespaces]] id = "..."

# Optional secrets — omit to disable Telegram alerts.
npx wrangler secret put TELEGRAM_BOT_TOKEN
npx wrangler secret put TELEGRAM_CHAT_ID

# Required secret — gates POST /run so anyone can't force-run the pipeline.
npx wrangler secret put PROBE_SECRET

# Inline the current manifest.json into wrangler.toml's MANIFEST_JSON var.
# Idempotent — safe to re-run before every deploy.
py inline_manifest.py

# Deploy.
npx wrangler deploy
```

After deploy:

```bash
# Manual fire (secret required):
curl -X POST https://workspace-heartbeat.<subdomain>.workers.dev/run \
  -H "X-Probe-Secret: <PROBE_SECRET>"

# Read latest report (no auth needed):
curl https://workspace-heartbeat.<subdomain>.workers.dev/latest

# Worker self-check:
curl https://workspace-heartbeat.<subdomain>.workers.dev/health
```

The scheduled trigger fires daily at 06:00 UTC (per `[triggers] crons = ["0 6 * * *"]`).

### 3. Weekly report on GitHub Actions (optional)

Add a workflow like:

```yaml
# .github/workflows/weekly_hardening_report.yml
on:
  schedule:
    - cron: "0 7 * * 1"   # Monday 07:00 UTC
  workflow_dispatch:
jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "3.14" }
      - run: py -3 execution/infrastructure/weekly_hardening_report.py
      - uses: actions/upload-artifact@v4
        with:
          name: hardening-report
          path: HARDENING_BACKLOG_WORKSPACE_*.md
```

(Not committed here — operator decides when to enable CI.)

---

## The manifest

Each project entry declares:

| Field | Meaning |
|---|---|
| `slug` | Short id used in reports and alerts. |
| `type` | `cron_worker` / `cron_gh_actions` / `pages_site` / `interactive_only`. |
| `probe_url` | Live URL the Worker will `fetch()`. `null` for `interactive_only`. |
| `probe_expected_status` | HTTP status that means "alive" (default 200). |
| `freshness_field` | Name of a timestamp field inside the probe JSON (e.g. `kv_last_write`). |
| `freshness_threshold_hours` | If probe-payload timestamp is older than this, the project is DEGRADED. |
| `git_path` | Repo-relative path used by `freshness_monitor.py` for `git log -1`. |
| `run_log_path` | Optional path to a JSONL run log; last line's timestamp is a second freshness signal. |
| `notes` | Human hint — placeholder URLs, caveats, "confirm this". |

Defaults for `freshness_threshold_hours`:

| Cadence | Threshold |
|---|---|
| daily cron | 25h |
| weekly cron | 192h (8d) |
| monthly cron | 768h (32d) |
| interactive-only | 1440h (60d) |

Update the manifest, re-run `inline_manifest.py`, redeploy. No code change needed.

---

## Blockers / owed

- **KV namespace id** — needs `wrangler kv namespace create HEARTBEAT_KV` and paste into `wrangler.toml`. Operator action.
- **Telegram secrets** — optional. Without them, degraded runs write to KV only (`GET /latest`).
- **`PROBE_SECRET`** — required before deploy; blocks `POST /run` from strangers.
- **Placeholder URLs in `manifest.json`** — a few `<subdomain>` / `debanjan186.workers.dev` guesses need operator verification. `freshness_monitor.py` uses local `git_path` and doesn't care; the Worker probes will just return `PROBE_ERROR` until the URL is correct.
- **`gh_repo` for `job_search_v2`** — the manifest guesses `dmazumdar186/job_search_v2`; correct if the actual GH username differs.

---

## Rollback

Worker: `npx wrangler delete workspace-heartbeat` (keep the KV namespace — it holds report history).

Pre-push hook: `git config --unset core.hooksPath` (or edit `.githooks/pre-push` to remove the freshness section).

Weekly report: it just writes a Markdown file at the workspace root; delete the file if unwanted.
