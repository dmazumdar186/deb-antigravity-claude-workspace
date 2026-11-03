# Handover setup (one time, ~30 minutes, screen-share)

Done by **Debanjan (operator)** together with **Jitendra** on a call. After step 6, the operator never touches the live site again: every **Save** Jitendra makes in Pages CMS goes to his GitHub repo, and his Cloudflare Pages project publishes it by itself.

Before the call, Jitendra needs: his GitHub login (`kumarjitendra`), his email inbox open, his GoDaddy login, his phone (for codes).

Order matters. The domain can only be attached to one Pages project at a time, so the operator detaches it (step 3d) only after Jitendra's DNS zone is Active and right before Jitendra attaches it. Expected downtime: a few minutes.

---

## 1. Repository: create, push, transfer (operator, 5 min)

1. Operator, on https://github.com/new: owner `dmazumdar186`, name `yogaavecjitendra`, **Private**, do NOT add a README, .gitignore or licence. **Create repository**.
2. From the workspace checkout, push the handover branch as `main` of the new repo:
   ```bash
   cd deb-antigravity-claude-workspace
   git fetch origin handover/yogaavecjitendra
   git push https://github.com/dmazumdar186/yogaavecjitendra.git origin/handover/yogaavecjitendra:refs/heads/main
   ```
3. Check on GitHub: the repo root shows `README.md`, `LISEZMOI.md`, `.pages.yml`, `src/`, `public/`.
4. Repo **Settings** → **General** → scroll to **Danger Zone** → **Transfer ownership** → **Choose an owner**: `kumarjitendra` → type the repo name to confirm → **I understand, transfer this repository**.
5. Jitendra opens the email "dmazumdar186 wants to transfer yogaavecjitendra to you" → **Accept transfer**. Check that https://github.com/kumarjitendra/yogaavecjitendra opens for him.

## 2. Jitendra's Cloudflare Pages project (Jitendra clicks, 10 min)

1. https://dash.cloudflare.com/sign-up → email + password → confirm the email. Free plan.
2. Left menu **Workers & Pages** → **Create** → tab **Pages** → **Connect to Git** (the "Import an existing Git repository" option).
3. **Connect GitHub** → GitHub asks to install the Cloudflare app → **Only select repositories** → `yogaavecjitendra` → **Install & Authorize**.
4. Pick `kumarjitendra/yogaavecjitendra` → **Begin setup**.
5. Settings:
   - **Project name**: `yogaavecjitendra` (matches `name` in `wrangler.toml`).
   - **Production branch**: `main`
   - **Framework preset**: **Astro**
   - **Build command**: `npm run build`
   - **Build output directory**: `dist`
   - **Root directory**: leave empty
   - **Environment variables** → **Add variable**: `NODE_VERSION` = `22` (Astro 5 needs Node 18.20.8+ / 20.3+ / 22; pin it so a future image change does not break the build).
6. **Save and Deploy**. Wait for the green "Success" (2 to 4 min).
7. Open `https://yogaavecjitendra.pages.dev` (the exact URL is shown at the top of the project). Check home, FR/EN switch, the corporate section, logos, reviews, gallery.

## 3. Move the domain to Jitendra's Cloudflare (20 min including waiting)

### 3a. Add the zone in Jitendra's account
1. In Jitendra's Cloudflare: **Account home** → **Add a domain** (or **Onboard a domain**) → `yogaavecjitendra.fr` → keep **Quick scan for DNS records** → **Continue** → plan **Free** → **Continue**.
2. On the DNS review screen: **delete** any imported `A`, `AAAA` or `CNAME` records for `yogaavecjitendra.fr` and `www` (Pages creates its own in 3e). Make sure the records in the table below exist; add any that are missing (**Add record**).
3. **Continue to activation**. Note the **2 nameservers** Cloudflare shows (format `xxx.ns.cloudflare.com`).

**Records in the current zone (read on 2026-11-03 from the operator account):**

| Type | Name | Content | Recreate? |
|---|---|---|---|
| CNAME | `@` | `yoga-jitendra.pages.dev` | **No**: replaced by the custom domain in 3e |
| CNAME | `www` | `yoga-jitendra.pages.dev` | **No**: replaced by the custom domain in 3e |
| TXT | `@` | `google-site-verification=rTgu-QYAoMktGuGmx3efjhA83EfySNoB6ppRGsYDSmA` | **Yes** (Google Search Console ownership) |
| TXT | `_dmarc` | `v=DMARC1; p=quarantine; adkim=r; aspf=r; rua=mailto:dmarc_rua@onsecureserver.net;` | **Yes** (email anti-spoofing policy) |
| CNAME | `_domainconnect` | `_domainconnect.gd.domaincontrol.com` (DNS only) | Optional (GoDaddy helper, harmless) |

There are **no MX records**: the domain receives no email, so nothing about mail breaks. DNSSEC is **disabled** on the current zone, so changing nameservers is safe (no DS record to remove at GoDaddy).

### 3b. Point GoDaddy at Jitendra's nameservers
1. https://www.godaddy.com → sign in (Jitendra) → **My Products** → next to `yogaavecjitendra.fr` click **DNS** (or **Manage DNS**).
2. Tab **Nameservers** → **Change Nameservers** → **I'll use my own nameservers**.
3. Replace the current two (`guy.ns.cloudflare.com`, `vera.ns.cloudflare.com`) with the 2 from 3a → **Save** → confirm.
4. The live site keeps working during propagation (the old zone still serves it).

### 3c. Wait for "Active"
In Jitendra's Cloudflare, the domain page → **Check nameservers now**. Usually 5 to 30 minutes for `.fr`; Cloudflare also emails him when it is Active. Do not continue until it says **Active**.

### 3d. Operator detaches the domain (operator, 1 min)
From the workspace, with the operator's `CLOUDFLARE_API_TOKEN` / `CLOUDFLARE_ACCOUNT_ID`:
```bash
python3 execution/personal_workflows/yoga_jitendra_site/scripts/handover_cutover.py --status
python3 execution/personal_workflows/yoga_jitendra_site/scripts/handover_cutover.py           # dry run
python3 execution/personal_workflows/yoga_jitendra_site/scripts/handover_cutover.py --apply
```
`--apply` removes `yogaavecjitendra.fr` and `www.yogaavecjitendra.fr` from the operator's `yoga-jitendra` Pages project and turns off its production and preview deployments, so workspace pushes no longer publish anything.

### 3e. Jitendra attaches the domain (immediately after 3d)
1. His Pages project → **Custom domains** → **Set up a custom domain** → `yogaavecjitendra.fr` → **Continue** → **Activate domain**.
2. Again for `www.yogaavecjitendra.fr`.
3. Wait for both to show **Active** (1 to 10 min). Open https://yogaavecjitendra.fr and https://www.yogaavecjitendra.fr.

### 3f. Operator cleanup (later, only after GoDaddy shows his nameservers)
Operator's Cloudflare → `yogaavecjitendra.fr` → **Overview** → **Remove site from Cloudflare**. Optionally delete the `yoga-jitendra` Pages project and the `yoga-jitendra-cron` Worker once the new site has run fine for a week.

## 4. Pages CMS (Jitendra clicks, 5 min)

1. https://app.pagescms.org → **Sign in with GitHub** → authorize Pages CMS.
2. Pages CMS asks to install its GitHub app: **Install** → account `kumarjitendra` → **Only select repositories** → `yogaavecjitendra` → **Install**. (If not asked: https://github.com/apps/pages-cms → **Configure**.)
3. Back in Pages CMS, the project list shows `kumarjitendra/yogaavecjitendra` → open it, branch `main`.
4. **Media** now appears in the left menu, with all the content pages under it.
5. Test together: change one word in **Home page (French)** → **Save** → wait 3 minutes → see it on https://yogaavecjitendra.fr → change it back.

## 5. OPTIONAL: features that need Cloudflare storage

The public site is complete without this. Only these extras need it: the private statistics dashboard (`/dashboard/`), the "leave a review" form, and the newsletter box. Without it they show nothing or a polite error; nothing else breaks.

1. Jitendra's Cloudflare → **Storage & Databases** → **KV** → **Create** namespace `DASHBOARD_KV`; copy its ID.
2. On GitHub, edit `wrangler.toml` in his repo and add (this file manages bindings; the dashboard binding UI is read-only while it exists):
   ```toml
   [[kv_namespaces]]
   binding = "DASHBOARD_KV"
   id = "<the ID from step 1>"
   ```
3. Pages project → **Settings** → **Variables and Secrets** → add secret `DASHBOARD_PASS` (dashboard login name is `jitendra`), and `TURNSTILE_SECRET` if the review form's anti-spam is wanted.
4. **Deployments** → **Retry deployment**. Details: `docs/DASHBOARD_ACTIVATION.md`. Exported data to import is in `data/kv/`.

## 6. Done checklist

- [ ] `github.com/kumarjitendra/yogaavecjitendra` exists, owned by Jitendra; operator no longer listed as owner.
- [ ] Jitendra's Pages project builds green from `main`.
- [ ] GoDaddy nameservers = Jitendra's 2 Cloudflare nameservers; zone **Active** in his account.
- [ ] TXT `google-site-verification` and `_dmarc` present in his zone.
- [ ] `handover_cutover.py --status` shows no custom domains and deploys disabled on `yoga-jitendra`.
- [ ] `yogaavecjitendra.fr` and `www` show **Active** in his Pages project; both URLs load over https.
- [ ] Pages CMS: he can open the project, sees **Media**, a test **Save** went live by itself.
- [ ] Jitendra knows where `README.md` / `LISEZMOI.md` are and has his 3 logins + GoDaddy written down.
- [ ] GoDaddy **Auto-renew** on (expires July 2028).
- [ ] Operator removed the zone from his own Cloudflare (step 3f).
