# Handover of yogaavecjitendra.fr to Jitendra — operator checklist

Goal: Jitendra owns and edits the site alone. Nothing stays on your accounts. ~45 min total, 15 of them on the 8 pm call.

## Current state (verified 2026-10-14)

- Site source lives in this monorepo at `execution/personal_workflows/yoga_jitendra_site/`.
- Cloudflare Pages project `yoga-jitendra` (your CF account) is Git-connected to **this monorepo**, `main`, root dir = that folder. Every push to `main` redeploys his site.
- Domain `yogaavecjitendra.fr`: **registrant is Jitendra** (his email + phone at the registry), bought via GoDaddy, expires 2028-07-08. Nameservers point to a zone in **your** Cloudflare account.
- Dashboard, KV, review sync Worker, GBP/GSC OAuth: all on your accounts. These are **not** handed over; they die with the switch.

## What is already built for the handover

- `.pages.yml` — Pages CMS config. Jitendra edits photos, videos and all text at https://app.pagescms.org with a GitHub login. No code.
- `HANDOVER/export_standalone_repo.sh` — produces a clean standalone copy: no dashboard, no tests, no KV binding, reviews frozen to `reviews-seed.json`. Build verified green (Astro static, 18 MB dist).
- `HANDOVER/README_JITENDRA.md` — his plain-language manual; becomes `README.md` of the new repo.
- Orphan branch **`handover/yogaavecjitendra`** in this repo = the exported standalone site, ready to push to a new repo.

## Before the call (10 min, you)

1. Create an empty public repo on GitHub named `yogaavecjitendra` (no README). Then:
   ```bash
   git fetch origin handover/yogaavecjitendra
   git push https://github.com/dmazumdar186/yogaavecjitendra.git origin/handover/yogaavecjitendra:main
   ```
2. GitHub → that repo → Settings → Collaborators → add Jitendra's GitHub username (he creates the account on the call if he has none; ask him beforehand to sign up at github.com with jitendranitrr13@gmail.com).
3. Ask him to also sign up at https://dash.cloudflare.com (free) with the same email before the call.

## On the call (15 min, screen-share, he clicks)

1. **Cloudflare, his account** → Workers & Pages → Create → Pages → Connect to Git → authorise GitHub → pick `yogaavecjitendra` → Build command `npm run build`, output `dist`, add env var `NODE_VERSION` = `22` → Save and Deploy. Wait ~2 min, open the `*.pages.dev` preview to show it works.
2. **Cloudflare, his account** → Add a domain → `yogaavecjitendra.fr` → Free plan → it shows two nameservers. He opens **GoDaddy** → My Domains → yogaavecjitendra.fr → Nameservers → Change → paste the two. (Propagation up to 24 h, usually minutes.)
3. **Cloudflare, his account** → the Pages project → Custom domains → add `yogaavecjitendra.fr` and `www.yogaavecjitendra.fr`.
4. **Pages CMS** → https://app.pagescms.org → Sign in with GitHub → open `yogaavecjitendra` → change one photo together → Save → show it live 2 min later. That is the whole lesson. Point him at README.md in the repo.
5. GitHub → repo → Settings → Danger Zone → **Transfer ownership** to his username. He accepts via email. Now he owns code, hosting and domain.

## After the call (5 min, you, once his site is live on his account)

1. Your Cloudflare → Pages project `yoga-jitendra` → Custom domains → remove both; then delete the project.
2. Your Cloudflare → zone `yogaavecjitendra.fr` → Overview → Remove site from Cloudflare.
3. Worker `yoga-jitendra-cron`: `npx wrangler delete` from `execution/infrastructure/yoga_jitendra_cron/` (or leave it; it only burns free-tier quota).
4. Optional: Google Business Profile → add his Google account as Primary owner, then remove yourself.
5. Optional cleanup in this repo: delete `execution/personal_workflows/yoga_jitendra_site/` and the cron Worker folder in a later commit.

## What he loses (say it once, then it is his problem)

Analytics dashboard, automatic Google-review sync, newsletter sign-ups, the on-site review form. The site itself, every photo, text and the WhatsApp booking path keep working. If he wants any of those back, any developer can read the repo.
