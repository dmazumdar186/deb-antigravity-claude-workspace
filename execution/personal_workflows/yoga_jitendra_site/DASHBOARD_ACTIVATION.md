# Dashboard V0.1 — activation guide

**Status as of 2026-07-21 (V0.1 code shipped, deploy pending):**

- ✅ Code committed locally: Worker at `execution/infrastructure/yoga_jitendra_cron/` (9 files) + Pages Function `/api/dashboard-data` + `/wa-out` proxy + 3 ApexCharts components + `dashboard.astro` hydration + acceptance gate extended + `tests/front_door_dashboard.sh` synthetic.
- ✅ Acceptance gate `py tests/acceptance_dashboard.py` PASSING.
- ❌ NOT pushed to origin yet (per operator workflow — user pushes).
- ❌ Not deployed to production — deploy commands below need owner-side secrets first.
- ⚠️ Auth remains **HTTP Basic** (interim). Same privacy effect as CF Access; migration deferred to V0.5.

**LIVE-PROBATIONARY reset:** shipping V0.1 resets the day counter per `~/.claude/rules/front-door-synthetic.md`. Once deployed, the front-door synthetic must pass 5 consecutive days before V0.1 can be called "live." Current counter: **day 0 of 5.**

---

## V0.1 owner setup — ~30-45 minutes end-to-end

Follow in order. All commands run from the workspace root unless noted.

### Step 1 — Google Cloud OAuth Client (~10 min)

1. Open [console.cloud.google.com](https://console.cloud.google.com) → select or create a project (name it e.g. `yoga-jitendra-dashboard`).
2. **APIs & Services → Library**:
   - Enable **Google Search Console API**
   - Enable **Business Profile Performance API** (optional; V0.1 ships without GBP if this or step 2b lags — see plan §7.2b)
3. **APIs & Services → OAuth consent screen** → configure:
   - User Type: **External**
   - Publishing status: **Testing** (keep it here — production verification is a follow-up per plan §7.2a)
   - App name: `Yoga avec Jitendra Dashboard`
   - Add **Test users**: `debolshop@gmail.com` and `jitendranitrr13@gmail.com`
   - Scopes: `webmasters.readonly` + `business.manage`
4. **APIs & Services → Credentials → Create Credentials → OAuth 2.0 Client ID**:
   - Type: **Desktop app** (simpler than Web — no redirect URI to configure)
   - Name: `yoga-jitendra-cron`
   - Download the JSON, save as `execution/personal_workflows/yoga_jitendra_site/scripts/credentials.json` (already `.gitignored`).

### Step 2 — Bing Webmaster Tools API key (~2 min)

1. Sign in at [www.bing.com/webmasters](https://www.bing.com/webmasters) with the account that owns the yogaavecjitendra.fr verification.
2. **Settings → API access** → **Generate** → copy the API key.

### Step 3 — Google Business Profile API access (async, days-to-weeks)

Per plan §7.2b: new Google Cloud projects start at **zero quota** for the GBP Performance API. This step is done in parallel with everything else; V0.1 ships without GBP if it lags.

1. Follow [developers.google.com/my-business](https://developers.google.com/my-business/content/basic-setup) → **Get an access token** section → submit the access request form.
2. When approved (days-to-weeks, may be denied), obtain the Location ID for the yogaavecjitendra.fr Location and note it.

### Step 4 — Cloudflare Analytics API token (~3 min)

1. Cloudflare dashboard → **My Profile → API Tokens → Create Token**.
2. Use the **Custom token** template with:
   - Permissions: **Zone → Analytics → Read** on the yogaavecjitendra.fr zone; **Account → Account Analytics → Read** on your account.
3. Also note your **Account ID** (top of any dashboard page, right sidebar).

### Step 5 — Get Google refresh tokens (~5 min)

```powershell
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/personal_workflows/yoga_jitendra_site/scripts"
py -m pip install google-auth-oauthlib
py get_google_refresh_token.py
```

Two browser windows will open in sequence. Sign in with `debolshop@gmail.com` and approve. The script prints copy-paste-ready `wrangler secret put` commands with the refresh tokens.

**Note:** these refresh tokens expire after 7 days (Testing-status OAuth app policy per plan §7.2a — you approved Option A). Re-run this script every ~6 days.

### Step 6 — Paste Worker secrets (~5 min)

Run each command in sequence. Wrangler prompts for the value (paste + Enter):

```powershell
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/infrastructure/yoga_jitendra_cron"
npx wrangler secret put GOOGLE_CLIENT_ID
npx wrangler secret put GOOGLE_CLIENT_SECRET
npx wrangler secret put GOOGLE_REFRESH_TOKEN_GSC
# If GBP is approved (Step 3):
npx wrangler secret put GOOGLE_REFRESH_TOKEN_GBP
# Then update wrangler.toml [vars] GBP_LOCATION_ID with the Location resource name.
npx wrangler secret put BING_API_KEY
npx wrangler secret put CF_ANALYTICS_TOKEN
npx wrangler secret put CF_ACCOUNT_ID
# WORKER_SECRET gates the /run manual-trigger endpoint; generate a random 32-char string.
npx wrangler secret put WORKER_SECRET
```

**Note:** `wrangler secret put` writes to the Worker's secret store; the Pages project uses a separate store (`wrangler pages secret put`). Don't confuse the two.

### Step 7 — Deploy the Worker (~2 min)

```powershell
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/infrastructure/yoga_jitendra_cron"
npx wrangler deploy
```

Verify secrets are all set:

```powershell
curl https://yoga-jitendra-cron.<your-subdomain>.workers.dev/health
```

Expected: `secrets_missing: []` (or just `GOOGLE_REFRESH_TOKEN_GBP` if GBP is still pending).

### Step 8 — Bootstrap the first pipeline run (~2 min)

Don't wait until tomorrow morning's cron. Manually fire the pipeline once now to populate KV:

```powershell
curl -X POST -H "X-Worker-Secret: <the-WORKER_SECRET-you-set>" https://yoga-jitendra-cron.<your-subdomain>.workers.dev/run
```

Expected response: `{ ok: true, sources: [...], aggregation: {...} }` with at least 3 of 4 sources showing `status: "healthy"`.

### Step 9 — Redeploy Pages with V0.1 frontend (~5 min)

```powershell
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/personal_workflows/yoga_jitendra_site"
npm install     # picks up the new apexcharts dependency
npm run build
npx wrangler pages deploy dist --project-name=yoga-jitendra --branch=main
```

### Step 10 — Smoke test (~5 min)

Open [https://yogaavecjitendra.fr/dashboard/](https://yogaavecjitendra.fr/dashboard/) in a private tab. Verify:

- Basic-Auth prompt appears; log in with `debanjan` + `DASHBOARD_PASS`.
- Dashboard loads with **real numbers** on the hero tiles (not ⏳ pills).
- The three range pills (7 days / 30 days / Since launch) are clickable and swap values + re-render the line chart.
- Time-series line chart shows impressions + clicks + WA-taps.
- Donut chart shows click share by source.
- Sparklines under each hero-tile number.

Run the front-door synthetic against production:

```powershell
$env:DASHBOARD_PASS="<your-password>"
bash "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/personal_workflows/yoga_jitendra_site/tests/front_door_dashboard.sh"
```

Expected: **ALL PASS**. Increment the LIVE-PROBATIONARY day counter below.

---

## Rollback (~5 min)

If V0.1 needs to come off:

```powershell
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
git revert <v01-commit-sha>
git push origin main
cd execution/personal_workflows/yoga_jitendra_site
npm run build
npx wrangler pages deploy dist --project-name=yoga-jitendra --branch=main
cd ../../../infrastructure/yoga_jitendra_cron
npx wrangler delete   # removes the Worker; KV namespace stays
```

Dashboard reverts to V0.01 static-JSON behavior. `DASHBOARD_KV` retains any accumulated snapshots (harmless, €0).

---

## WhatsApp message to Jitendra (send after Step 10 passes)

### English

> Namaste Jitendra, the dashboard now shows real numbers. Google search, Bing, Cloudflare analytics and WhatsApp taps update every morning at 6am Paris time. You can click "Last 7 days", "Last 30 days" or "Since launch" to change the view. Have a look when you can:
>
> https://yogaavecjitendra.fr/dashboard/
>
> First real numbers land in the next 24-48h once Google publishes. The monthly self-report is still there — three numbers, thirty seconds, once a month. 🙏

### French

> Namaste Jitendra, le tableau de bord affiche maintenant de vrais chiffres. Google, Bing, Cloudflare et les taps WhatsApp se mettent à jour tous les matins à 6h heure de Paris. Tu peux cliquer sur "7 derniers jours", "30 derniers jours" ou "Depuis le lancement" pour changer la vue. Jette un œil quand tu peux :
>
> https://yogaavecjitendra.fr/dashboard/
>
> Les premiers vrais chiffres arrivent dans 24-48h une fois que Google les publie. Le rapport mensuel reste là — trois chiffres, trente secondes, une fois par mois. 🙏

---

## LIVE-PROBATIONARY day counter (V0.1)

Add a row after each day the front-door synthetic passes against the live URL. Counter resets on any FAIL.

- Day 0 / 5: not yet deployed (this file was written 2026-07-21).
- Day 1 / 5: —
- Day 2 / 5: —
- Day 3 / 5: —
- Day 4 / 5: —
- Day 5 / 5: — V0.1 is now LIVE per the front-door-synthetic rule.

---

## What V0.1 does NOT include (V0.5+ owed work)

- Cloudflare Access migration (Basic Auth stays).
- Drill-down click on hero tiles (top queries / top pages breakdown).
- Custom hover tooltips on charts.
- Email digest.
- Value-in-EUR narrative section (V1.0).
- Multi-language dashboard.
- Real-time updates (V0.1 is daily-cadence).
- CF WA custom events for WA-taps (the `/wa-out` proxy is primary; custom events layered in only after a Phase-0 spike confirms free-tier availability).
