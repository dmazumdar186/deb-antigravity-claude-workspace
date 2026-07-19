# Dashboard V0.01 activation guide

**Status when this file was written:** committed as `2572e60`, NOT pushed, NOT deployed. Cloudflare Access NOT configured. `DASHBOARD_KV` binding NOT created. `PUBLIC_CF_WA_TOKEN` env var NOT set. Front-door synthetic against LIVE URL has NEVER run.

Per the workspace `front-door-synthetic.md` rule: **do not describe this as "live", "shipped", or "ready" until 5 consecutive LIVE-day synthetic runs pass**. Until then, the correct wording is `LIVE-PROBATIONARY: day 0 of 5`.

---

## Owner steps — ~15 minutes end-to-end

### 1. Cloudflare Web Analytics token (~2 min)

Cloudflare dashboard → **Analytics & Logs → Web Analytics → Add a site** for `yogaavecjitendra.fr`. Copy the generated site token.

In the Pages project settings → **Settings → Environment variables → Production** → add:

```
PUBLIC_CF_WA_TOKEN = <the-token-from-cf-web-analytics>
```

Save. This unblocks the "Conversation" hero tile from showing perpetual `⏳`.

### 2. `DASHBOARD_KV` namespace + binding (~3 min)

Cloudflare dashboard → **Workers & Pages → KV → Create namespace** named `DASHBOARD_KV`.

Then in the Pages project settings → **Settings → Functions → KV namespace bindings** → add:

```
Variable name: DASHBOARD_KV
KV namespace:  DASHBOARD_KV (the one you just created)
```

Save. This unblocks the monthly self-report form.

### 3. Cloudflare Access application (~5 min)

Cloudflare Zero Trust dashboard → **Access → Applications → Add an application → Self-hosted**.

- **Application name:** `Yoga avec Jitendra — internal dashboard`
- **Session duration:** 30 days
- **Application domain:** `yogaavecjitendra.fr`
- **Path:** `/dashboard/*` (add a second application row for `/api/*` with the same policy)
- **Identity providers:** One-time PIN (email magic link) — enabled by default
- **Policy → Include:** Emails →
  - `debolshop@gmail.com`
  - `jitendranitrr13@gmail.com`

Save. Unauthenticated visitors to `/dashboard/` or `/api/self-report` now get a magic-link login page.

### 4. Deploy + smoke-test (~5 min)

```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space/execution/personal_workflows/yoga_jitendra_site"
npm run build
npx wrangler pages deploy dist --project-name=yoga-jitendra --branch=main
```

Then open `https://yogaavecjitendra.fr/dashboard/` in a private tab. Confirm:
- Magic-link login prompt appears (CF Access is enforcing).
- After email verification: dashboard loads with 3 ⏳ hero tiles, funnel with zeros, milestone strip, next-move card, self-report tile ("Log your first month"), provenance footer.
- Log a test month from `/dashboard/self-report/` → confirm the tile updates on reload.

If any step fails: rollback is one command below.

---

## WhatsApp message to Jitendra (English or bilingual)

Use whichever version fits the moment. Both are ready to paste.

### English

> Namaste Jitendra, I built a small private dashboard for the website so you can see, in one glance, how many people are finding you on Google and how many are messaging you from the site. It's just for you and me — you'll get a login link by email the first time you open it.
>
> Here: https://yogaavecjitendra.fr/dashboard/
>
> First real numbers land next week (Google takes a few days to publish). Once a month, if you can, please tap "Log this month" and enter three quick numbers (new students, recurring, avg per session). That's the piece that lets the dashboard show your actual value over time.
>
> No rush — just have a look when you can and let me know what you'd want to see more of. 🙏

### French

> Namaste Jitendra, j'ai construit un petit tableau de bord privé pour le site, pour que tu voies d'un coup d'œil combien de personnes te trouvent sur Google et combien t'écrivent depuis le site. C'est juste pour toi et moi — tu recevras un lien de connexion par email la première fois.
>
> Ici : https://yogaavecjitendra.fr/dashboard/
>
> Les premiers chiffres réels arrivent la semaine prochaine (Google met quelques jours à publier). Une fois par mois, si tu peux, clique sur "Log this month" et entre trois chiffres rapides (nouveaux élèves, réguliers, moyenne par séance). C'est ça qui permet au tableau de bord de montrer ta vraie valeur dans le temps.
>
> Pas d'urgence — jette un œil quand tu peux et dis-moi ce que tu voudrais voir de plus. 🙏

---

## Rollback (~2 min)

```bash
cd "c:/Users/deban/OneDrive/Documents/AntiGravity Project Space"
git revert 2572e60 447617f    # revert both dashboard commits
git push origin main
cd execution/personal_workflows/yoga_jitendra_site
npm run build
npx wrangler pages deploy dist --project-name=yoga-jitendra --branch=main
```

Then in the CF dashboard: disable the Access application, delete the `DASHBOARD_KV` binding (namespace can stay, cost is €0). The dashboard URL then 404s cleanly.

---

## LIVE-PROBATIONARY day counter

Add a row here each day you run the front-door synthetic against the LIVE URL and it passes.

- Day 0 / 5: not yet run (site not deployed with dashboard as of this file)
- Day 1 / 5: —
- Day 2 / 5: —
- Day 3 / 5: —
- Day 4 / 5: —
- Day 5 / 5: — dashboard is now LIVE per the workspace front-door-synthetic rule.
