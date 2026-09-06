# Your daily job digest

This sets up a free, automated email that lands in your inbox every morning
with new job postings that match what you're looking for — filtered and
ranked, not a raw firehose. It runs on your own GitHub account, uses your own
email, and costs nothing to run.

You don't need to know how to code. You do need [Claude Code](https://claude.com/claude-code)
installed, and about 15 minutes.

## 1. Install the skill

You should have a `job-digest-skill.zip` file. Unzip it into your Claude Code
skills folder:

**Windows:**
1. Right-click `job-digest-skill.zip` → **Extract All...**
2. Move the extracted `job-digest` folder into `%USERPROFILE%\.claude\skills\`
   (paste that path into File Explorer's address bar), so you end up with
   `C:\Users\<you>\.claude\skills\job-digest\SKILL.md`.

**macOS:**
1. Double-click `job-digest-skill.zip` to unzip it (or `unzip job-digest-skill.zip`
   in Terminal).
2. Move the extracted `job-digest` folder into `~/.claude/skills/`:
   ```
   mkdir -p ~/.claude/skills
   mv job-digest ~/.claude/skills/
   ```
   so you end up with `~/.claude/skills/job-digest/SKILL.md`.

Once it's in place, restart Claude Code (or start a new session) in any
folder, and you can say things like "set up my job digest."

## 2. Run the setup interview

In Claude Code, type:

```
/job-digest setup
```

Claude will ask you a series of questions:

- Your name and email
- The job title(s) you want alerts for (up to 3), and any other titles that
  mean the same job (e.g. "Sales Manager" / "Regional Sales Manager")
- Which countries to search (pick from a list)
- Optional: specific cities, if you don't want the whole country
- Whether you're open to remote jobs
- What contract types you'll accept (permanent, fixed-term, freelance)
- A few sentences about your experience and what you're looking for — this
  is what teaches the system to judge whether a job is a good fit for you
- Your key skills
- What time of day you want the email, and your timezone
- Whether you also want results logged to a Google Sheet

At the end, it writes a `profile.yaml` file with your answers.

## 3. Create a private GitHub repository

Create a new **private** repository on GitHub (call it anything, e.g.
`my-job-digest`) and push your `profile.yaml` into it. The `/job-digest deploy`
step below also adds a `.gitignore` (from the skill's `gitignore_snippet.txt`)
before anything else is committed, so secrets and local run output never get
staged by accident.

## 4. Create your secrets

In your new repo: **Settings → Secrets and variables → Actions → New repository secret**.

### Mandatory

| Secret name | What it is |
|---|---|
| `GMAIL_SMTP_USER` | Your Gmail address |
| `GMAIL_SMTP_APP_PASSWORD` | A 16-character Gmail **App Password** (not your regular password) |

To create an App Password: turn on **2-Step Verification** on your Google
account, then go to **https://myaccount.google.com/apppasswords**, create a
new one for "Mail", and paste the 16-character code as the secret value.

### Optional — if you enabled the Google Sheet

| Secret name | What it is |
|---|---|
| `GOOGLE_SERVICE_ACCOUNT_JSON_B64` | A Google service account key, base64-encoded |
| `SHEETS_SPREADSHEET_ID` | The ID from your Google Sheet's URL |

To get a service account key: in [Google Cloud Console](https://console.cloud.google.com/),
create a project → enable the **Google Sheets API** → create a **Service
Account** → create a JSON key for it → share your target Google Sheet with
that service account's email address (as **Editor**). Then base64-encode the
JSON file (`base64 -w0 service_account.json` on Mac/Linux, or ask Claude Code
to do it for you) and paste the result as the secret value.

### Optional — better ranking, still free

| Secret name | What it is |
|---|---|
| `GEMINI_API_KEY` | A free-tier key from https://aistudio.google.com/apikey |

### Optional — even better ranking, costs money per API call

| Secret name | What it is |
|---|---|
| `ANTHROPIC_API_KEY` | An API key from https://console.anthropic.com/settings/keys |

**Important:** a Claude.ai subscription (Pro, Max, etc.) does **not** give you
an `ANTHROPIC_API_KEY`. The API is billed separately, per token. If you skip
this secret, the digest still works fine — it just uses the free heuristic
and/or Gemini ranking instead.

## 5. Generate and push the workflow

Back in Claude Code:

```
/job-digest deploy
```

This generates `.github/workflows/job_digest.yml` from your `profile.yaml`
and commits it. Push it to GitHub.

## 6. Run it once by hand

In your GitHub repo: **Actions → job-digest → Run workflow**. Leave the
"dry_run" box unchecked, and run it. Within a few minutes you should get an
email.

## What the email looks like

Subject: `Job digest · 12 new · Sales Manager · FR, DE · 2026-09-06`

The body groups jobs into three tiers:

- **Tier A — top match**: apply now
- **Tier B — promising**: worth a look
- **Tier C — weak fit**: skim only

Each row shows the job title (linked), company, location, contract type,
source, and a one-line explanation of why it was ranked that way. At the
bottom: a summary of the run (how many jobs were fetched, filtered, and kept)
and a link to your Google Sheet, if you enabled one.

## Changing your roles or countries later

Edit `profile.yaml` directly, or re-run:

```
/job-digest setup
```

If you changed `digest.hour_local` or `digest.timezone`, also re-run
`/job-digest deploy` to regenerate the workflow's schedule.

## Troubleshooting

The daily run can fail for a few different reasons. If it does, GitHub opens
an issue in your repo automatically — the "Exit-code hint" line in that issue
tells you which of these applies:

| Symptom / exit hint | What it means | Fix |
|---|---|---|
| exit 3 — acceptance gate failed | The results didn't look like your profile (e.g. wrong titles/locations sneaking in) | Check your `profile.yaml` roles/countries are specific enough; re-run `setup` if unsure |
| exit 5 — SMTP auth failed | Your Gmail App Password stopped working | Generate a new one at https://myaccount.google.com/apppasswords and update the `GMAIL_SMTP_APP_PASSWORD` secret |
| exit 6 — sheet write failed | The Google Sheet couldn't be written to | Check the service account still has Editor access on the sheet, and that `SHEETS_SPREADSHEET_ID` is correct |
| No email at all, no issue opened | The workflow itself may not have run | Check the **Actions** tab for a red X; GitHub sometimes delays or drops scheduled runs — the workflow fires twice a day, ~40 minutes apart, to cover this |
| Email arrives with 0 jobs every day | Your role titles or countries may be too narrow | Add synonyms to your roles, or widen your country/city list, via `setup` |

## Cost

Free. The mandatory pieces (GitHub Actions, Gmail SMTP, the heuristic
ranker) have no cost. The optional keys (`GEMINI_API_KEY`, `ANTHROPIC_API_KEY`)
are yours, on your own accounts, and only cost anything if you choose to add
the Anthropic one.
