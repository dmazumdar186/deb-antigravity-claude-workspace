# Proposal System

A self-hosted PandaDoc replacement. It turns a JSON file into a signable, payable, tracked
HTML proposal and hosts it on your own Vercel project at an unguessable URL like
`https://proposals.yourcompany.com/acme-corp-k9f2mz`. No subscriptions, no vendor lock-in.

What the client sees:

- A branded multi-page proposal (cover, problems, scope, pricing, agreement)
- A draw-your-signature box (HTML5 canvas), printed name, and an "I agree" checkbox
- **Accept & Send**: one click generates the signed PDF and delivers it to your Telegram
- **Download Signed PDF**: their own copy
- An optional **Pay** button that opens your Stripe Payment Link
- Buttons stay disabled until signature + name + checkbox are all filled

What you get: a Telegram message when the proposal is first opened, viewed again, paid, and
signed (with city/country and time), plus the signed PDF itself.

There are two proposal types in this folder:

| Type | Use it for | Build command | Docs |
|---|---|---|---|
| **Generic** | Any consulting / project proposal, 3 monthly payments | `python3 build.py` | this file |
| **Cold email** | A cold-email lead-gen offer (commission or retainer) | `python3 build_coldemail.py clients/<slug>.json` | `COLDEMAIL_README.md` |

If you only need the generic one, ignore `build_coldemail.py`, `template_coldemail.html`,
`tool_costs.json`, `clients/` and `STANDARD_TERMS.md`.

---

## One-time setup (about 20 minutes)

You need: Python 3, Node.js, a Vercel account, a Telegram account. A Stripe account only if
you want the Pay button. No API keys ship in this folder; you create your own below.

### 1. Make it yours

| What | Where |
|---|---|
| Your name, title, company, email | the `sender` block in `config.example.json`, `clients/_TEMPLATE.json`, `clients/_demo-example.json` |
| Your logo | replace `public/assets/logo.png` (square PNG, 512x512 works) |
| Landing page name | `public/index.html` ("Your Company Proposals") |
| Your site address | `base_url` in `settings.json` |
| Brand colour | `--accent` near the top of `template.html` and `template_coldemail.html` |
| Tool prices and links (cold email only) | `tool_costs.json` |
| Your contract terms (cold email only) | `STANDARD_TERMS.md`, then the matching text in `template_coldemail.html` and `build_coldemail.py` |

Currency is `$` and is written into the templates and build scripts. Search for `$` there if
you bill in another currency.

### 2. Deploy to Vercel

```bash
npm i -g vercel
```

```bash
vercel login
```

Run this inside the folder. Accept the defaults; it creates a new Vercel project:

```bash
vercel link
```

```bash
vercel deploy --prod --yes
```

Check which Vercel plan allows commercial use before sending client proposals from it.

### 3. Telegram notifications

1. In Telegram, message **@BotFather**, send `/newbot`, and copy the bot token it gives you.
2. Send any message to your new bot.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the
   number at `result[0].message.chat.id`. That is your chat id.
4. Store both on Vercel (never in a file in this folder):

```bash
vercel env add TELEGRAM_BOT_TOKEN production
```

```bash
vercel env add TELEGRAM_CHAT_ID production
```

5. Redeploy so the functions pick them up:

```bash
vercel deploy --prod --yes
```

Until these are set, proposals still work but you get no notifications and no signed PDF.
Set them before sending a real proposal.

### 4. Custom domain (optional)

Add a domain or subdomain (for example `proposals.yourcompany.com`) in the Vercel dashboard
under Project > Settings > Domains and create the DNS record it shows you. Put the same
address in `settings.json`. Without it, use the `*.vercel.app` production address.

### 5. Stripe (optional)

Create a Payment Link in Stripe and paste its URL into `payment.stripe_url` in the proposal
config. Nothing else to configure.

### 6. Test it

```bash
python3 build.py config.example.json --open
```

Sign the demo proposal in your browser, deploy, open the live URL, and confirm the Telegram
messages and the signed PDF arrive.

---

## Making a proposal

### With Claude Code (the intended way)

Open this folder in Claude Code and say:

> New proposal for Acme Corp, Jane Smith is the COO, $6K/mo for 3 months, they need help
> with X and Y, Stripe link: https://buy.stripe.com/...

The `create-proposal` skill in `.claude/skills/` writes the config, builds, deploys, and
returns the live URL. For the cold-email offer, say "cold email proposal for Acme" and the
`cold-email-proposal` skill runs instead.

### By hand

```bash
cp config.example.json config.json
```

Edit `config.json`, then:

```bash
python3 build.py
```

```bash
vercel deploy --prod --yes
```

The proposal is live at `<base_url>/<slug>`.

---

## Things to know

- **Every deploy uploads the whole `public/` folder.** A proposal stays live only while its
  `public/<slug>/` folder exists. Delete the folder and the next deploy takes that client's
  link down. Keep this folder backed up (a private git repo is ideal).
- **The slug is the password.** Each new build adds 6 random characters so the URL cannot be
  guessed. The slug is saved back into the config, so rebuilding keeps the same URL.
- **One `config.json` at a time** for generic proposals. Keep a copy per client (for example
  `configs/acme.json`) and build with `python3 build.py configs/acme.json`.
- **Signed PDFs over about 4 MB** are downloaded on the client's side instead of being sent
  to Telegram (Vercel's request size limit).
- **The signature is a drawn image plus a typed name and a checkbox.** Decide with your own
  legal advice whether that is enough for your contracts.
- The page analytics script (`/_vercel/insights/script.js`) only works if you enable Web
  Analytics in the Vercel dashboard. It is harmless if you don't.

## Files

| File | Purpose |
|---|---|
| `template.html` | Generic proposal template with `{{PLACEHOLDERS}}`, design, signature, PDF export, tracking |
| `build.py` | Fills `template.html` from a config, writes `public/<slug>/index.html` |
| `config.example.json` | Full example config (fictional "Northwind Coffee Co.") |
| `config.json` | Your working config (gitignored) |
| `template_coldemail.html`, `build_coldemail.py`, `tool_costs.json`, `clients/` | The cold-email proposal type |
| `api/track.js` | Vercel function: open / view / pay / sign events to Telegram |
| `api/submit.js` | Vercel function: delivers the signed PDF to Telegram |
| `public/index.html` | Landing page at the site root |
| `public/assets/logo.png` | Your logo |
| `settings.json` | Your site address |
| `vercel.json` | Clean URLs |
| `.claude/skills/` | The two Claude Code skills |

## Tracking events

| Event | Trigger |
|---|---|
| `opened` | First page load (per browser, 24h window) |
| `viewed` | Later reloads |
| `pay_clicked` | Pay button clicked |
| `signed` | Accept & Send or Download succeeded |
