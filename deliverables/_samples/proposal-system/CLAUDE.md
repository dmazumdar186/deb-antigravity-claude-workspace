# Proposal System

Signable, payable, tracked HTML proposals deployed to the owner's Vercel project.
Read `README.md` first; `COLDEMAIL_README.md` and `STANDARD_TERMS.md` for the cold-email type.

- Use the skills in `.claude/skills/`: `create-proposal` (generic) and `cold-email-proposal`.
- The public site address is `base_url` in `settings.json`.
- Never put secrets in this folder. The Telegram token and chat id live in Vercel env vars.
- Never delete a `public/<slug>/` folder: each deploy uploads all of `public/`, so removing
  one takes that client's live proposal down.
- A build that ran is not proof. After deploying, load the live URL and check that no `{{`
  remains and the prices match what was agreed.
