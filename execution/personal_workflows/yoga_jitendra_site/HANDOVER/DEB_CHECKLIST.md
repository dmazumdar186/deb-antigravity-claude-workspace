# End-of-contract handover of yogaavecjitendra.fr to Jitendra

Goal: he gets everything (code, data, hosting, domain, Google properties, docs, ad creatives); nothing stays on your accounts. ~50 min total, 15 of them on the 8 pm call.

## Current state (verified 2026-10-14)

- Site source: `execution/personal_workflows/yoga_jitendra_site/` in this monorepo. Cloudflare Pages project `yoga-jitendra` (your account) builds it from `main`.
- Domain `yogaavecjitendra.fr`: registrant is already **Jitendra** (GoDaddy, expires 2028-07-08). Nameservers point at a zone in your Cloudflare.
- His data in your Cloudflare KV namespace: approved + pending reviews, newsletter subscribers, monthly self-reports, dashboard rollups, ~1000 WhatsApp-tap events.
- Google Business Profile and Search Console are owned by debolshop@gmail.com.

## What the handover kit contains (already built and verified)

- Orphan branch **`handover/yogaavecjitendra`** = the complete standalone repo: site with dashboard, API functions, tests, every doc (`docs/`), the cron Worker (`cron/`), the 16 ad creatives (`deliverables/ads/`), the project history, the Pages CMS editor config (`.pages.yml`), his manual as `README.md`, and all 15 approved reviews baked into the site. Build verified green. Only your KV namespace id, your OAuth secrets and the old default login name were removed.
- `HANDOVER/export_standalone_repo.sh` regenerates it; `HANDOVER/dump_kv.py` dumps his KV data.

## Before the call (15 min, you, local machine)

1. Dump all his data (subscriber emails included, so it runs locally, not in the cloud session):
   ```bash
   cd execution/personal_workflows/yoga_jitendra_site
   python3 HANDOVER/dump_kv.py .tmp/kv_dump
   bash HANDOVER/export_standalone_repo.sh .tmp/handover .tmp/kv_dump
   ```
2. Create an empty **private** repo on GitHub named `yogaavecjitendra` (private: it holds subscriber emails). Push the export:
   ```bash
   cd .tmp/handover && git init -b main && git add -A && git commit -m "Yoga Avec Jitendra — full handover" \
     && git push https://github.com/dmazumdar186/yogaavecjitendra.git main
   ```
   (If you skip step 1, push the ready branch instead: `git push https://github.com/dmazumdar186/yogaavecjitendra.git origin/handover/yogaavecjitendra:main`. It has the reviews but not the subscriber/event data.)
3. Send him `HANDOVER/WHATSAPP_REPLY.md` so he creates GitHub + Cloudflare accounts with jitendranitrr13@gmail.com before 8 pm.

## On the call (15 min, screen-share, he clicks)

1. GitHub → your repo → Settings → Collaborators → add his username (temporary, so Cloudflare can see it).
2. **His Cloudflare** → Workers & Pages → Create → Pages → Connect to Git → `yogaavecjitendra` → build command `npm run build`, output `dist`, env var `NODE_VERSION`=`22` → Save and Deploy. ~2 min; open the preview URL.
3. **His Cloudflare** → Add a domain → `yogaavecjitendra.fr` → Free → copy the two nameservers → he opens GoDaddy → My Domains → Nameservers → paste. Then Pages project → Custom domains → add `yogaavecjitendra.fr` and `www.yogaavecjitendra.fr`.
4. **Pages CMS** → https://app.pagescms.org → Sign in with GitHub → open the repo → change one photo together → Save → live 2 min later. Show him `README.md`.
5. Optional, only if he wants the private dashboard + review form + newsletter (3 min): his Cloudflare → Workers & Pages → KV → Create namespace `yogaavecjitendra` → Pages project → Settings → Bindings → KV `DASHBOARD_KV` → that namespace; Settings → Variables and Secrets → add secret `DASHBOARD_PASS` (he picks it). Login name is `jitendra`. Redeploy. Reviews/subscribers from `data/kv/` can be re-imported by any developer later; the site already shows all reviews without it.
6. GitHub → repo → Settings → Danger Zone → **Transfer ownership** → his username. He accepts via email. Done: he owns code, data, hosting, domain.

## After the call (10 min, you)

1. **Google Business Profile** → business.google.com → Yoga Avec Jitendra → Business Profile settings → People and access → Add → jitendranitrr13@gmail.com → **Primary owner**. He accepts (email). Then remove yourself.
2. **Search Console** → property `yogaavecjitendra.fr` → Settings → Users and permissions → Add user → his email → Owner. Then remove yourself. (Bing Webmaster and Ahrefs, if still active: same, or just let them lapse.)
3. **Your Cloudflare**: Pages `yoga-jitendra` → Custom domains → remove both → delete project. Zone `yogaavecjitendra.fr` → Overview → Remove site. Worker `yoga-jitendra-cron` → delete (`npx wrangler delete` in `execution/infrastructure/yoga_jitendra_cron/`). KV namespace `4cdf5cdb…` → delete (after step 1 of "Before the call" ran).
4. **Google Cloud** OAuth app used for GBP/GSC review sync: Credentials → delete the OAuth client; remove `YOGA_CRON_WORKER_SECRET` and any GBP/GSC refresh tokens from `.env`.
5. This repo: delete `execution/personal_workflows/yoga_jitendra_site/`, `execution/infrastructure/yoga_jitendra_cron/`, `deliverables/ad_creative/yoga_jitendra/`, `directives/personal_workflows/yoga_jitendra_site.md`, `tests/acceptance_yoga_jitendra.py` and the `handover/yogaavecjitendra` branch once his repo is confirmed pushed. Leave the `HANDOFF_*yoga_jitendra*.md` files or move them to `docs/reference/`; your call.

## What to tell him once, in writing

The site, all photos, both languages, WhatsApp booking and all reviews work with zero setup. The dashboard, review form, newsletter and automatic Google-review sync are included in the repo but need the optional step 5 and, for the cron Worker, a developer (`cron/` has a README-level wrangler.toml and the code). Any web developer can take it from the repo. Domain renewal is at GoDaddy, in his name, July 2028.
