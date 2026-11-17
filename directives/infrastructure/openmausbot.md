# OpenMausBot (and the Apinex verdict)

## Goal

OpenMausBot (github.com/milind-soni/OpenMausBot, Apache-2.0, npm `openmausbot`) is an open-source
alternative to xAI's Grok Bot. Each chat is a named bot (a persistent agent) running on CLIs we already
have (`claude`, `codex`, `grok`). The bots sit in a chat app, delegate to each other, and can be driven
headless from scripts. This directive records the 2026-11-17 evaluation and how to run it.

## When to invoke

- The operator wants a standing team of persona bots (e.g. writer + skeptic, or a client-facing bot
  per client) that stay running between sessions and are reachable from a phone.
- A multi-bot job must run unattended from a script or CI (`openmausbot run ... --export DIR`).
- NOT for one-off work inside Claude Code: sub-agents and Workflows already cover that at lower cost.

## Inputs

- Node >= 24 (cloud has 22: `npm i node@24` locally and run `node_modules/.bin/node`).
- An engine: the logged-in `claude` CLI is picked up automatically (no key needed).
- A team file: `execution/infrastructure/openmausbot/outreach_lab_team.yaml` (Lead as Chief + Skeptic).

## Tools/Scripts

- npm `openmausbot` CLI (pinned 0.1.166); team file `execution/infrastructure/openmausbot/outreach_lab_team.yaml`.
- `execution/infrastructure/openmausbot/client_bots.py`: one bot per client (see Per-client bots).

## Steps

1. Start the local server. 2. Apply the team file. 3. Run one job with `--export`.

```bash
openmausbot serve --port 8799 --data-dir .tmp/omb --label eval &   # 127.0.0.1 only by default
openmausbot team apply execution/infrastructure/openmausbot/outreach_lab_team.yaml
openmausbot run Lead "<job>" --timeout 8m --export .tmp/omb_job
```
(cloud: set `NO_PROXY=127.0.0.1,localhost`; avoid `--noproxy '*'`, which the redteam hook rejects.)

## Outputs

- Final reply on stdout. JSON progress events go to stderr. `--export DIR` writes `job.json`, `manifest.json`
  and a transcript per bot (md + json).

## Measured 2026-11-17 (cloud container, v0.1.166)

- Install: `npm i node@24 openmausbot`, 10 s, 11 packages. Server up in under 10 s.
- `team apply` created 1 team + 2 bots. A second apply printed `No changes.`, so it is idempotent.
- Job "70-word cold email to a dental clinic": Lead drafted, sent it to Skeptic, revised, and finished in 17 s
  on claude-sonnet-5-5 at effort low (exit 0, 2 transcripts). Output stayed within the brief and invented
  no figures. It still uses `[Clinic Name]` placeholders, so it needs the real input row.

## Edge Cases

- Defaults are permissive: a new bot starts at `approval: full`. Always set `approval` and `computer`
  in the team file. Headless runs with `computer: auto` can stall on a question.
- PostHog analytics exist (Settings → General → Usage analytics); they are documented as excluding
  keys, names and content. Turn them off in the desktop app.
- Optional paid paths: trial credit, MausBot Cloud (boat.dev boxes), ModelGo sponsor, `--tunnel` via
  accounts.openmausbot.com. None fire without a login or key. Do not enable them without a budget guard.
- The decision-model router defaults to Jev (`OMB_JEV_API_KEY`, or OpenRouter as fallback). Not yet tested with our key.
- Very fast release cadence (several releases a day). Pin the version (`openmausbot@0.1.166`) in any script.

## Per-client bots (`client_bots.py`)

One bot per evidenced client. Each sits in its own team ("Client: <name>") and runs on
`claude/claude-opus-5-5` at effort low, `approval: ask`, `computer: off` (the bot sees only its brief).

1. Roster: `execution/infrastructure/openmausbot/clients.json` (slug, name, status client|prospect|internal,
   evidence quote + source line, soul_file). Only `client` rows get a bot; `--include-prospects` adds prospects.
2. Briefs: `clients/<slug>.md`, ≤ 3,500 chars of source-traced facts, ending in the fixed Rules block
   (no invented facts, never name another client, draft only, signature).
3. `python3 execution/infrastructure/openmausbot/client_bots.py`: validate + write `client_team.json` (offline).
   `--plan` = `team apply --dry-run`; `--apply` applies; `--cli <cmd>` if `openmausbot` is not on PATH.
4. Gates (exit 2 + reason): empty roster, > 50 bots, no evidence, duplicate, missing/escaping soul file,
   soul < 300 chars or > 24 KB, missing Rules block, any email other than debanjan@prodcraft.fyi,
   phone numbers, secret-like tokens (sk-, sk_live_, AKIA, ghp_, AIza, xox), and a soul naming another client
   by any word of its name or any `aliases` entry (contact people, brands, domains), accent-insensitive
   Keep `aliases` current when a client gains a contact. Tests: `python3 tests/test_openmausbot_client_bots.py` (23 cases).
5. To add a client: add the roster row + brief, re-run with `--apply`. Re-runs are no-ops when nothing changed.

Measured 2026-11-17: 4 client bots (Accessory Masters, Gaia Talent / GreenJobs, Jeevana Yoga, Yoga avec
Jitendra) applied; a re-apply printed `No changes.`. Probes: the Gaia bot answered status from its brief and
refused to compare with another client. The Jitendra bot refused to invent visitor/revenue numbers.

**Known leak:** OpenMausBot shows every bot the workspace roster, so a bot can name another client's *bot*
(the Gaia bot said "the Accessory Masters assistant"). Fine while Debanjan is the only user. **Never pair a
client (`pair --client`, `access add`) into this workspace.** Client-facing access needs one workspace per
client (`openmausbot fleet create`), which has not been built.

## Apinex (apinex.bond): rejected, do not use

Evidence from the live site, 2026-11-17: Claude Opus 5.5 at $0.50/1M and "free" Claude 4.6 tiers
(far below the provider's own price), crypto-only top-ups (NOWPayments), XP/leaderboard/"Pass"
gamification, a white-label resale kit (APInexGate), Yandex Metrika tracking, no named company,
and terms/privacy pages that render no text. Every prompt would pass through an unknown operator,
and below-cost frontier access usually means abused or resold accounts. It conflicts with spend
discipline (Claude calls go through the subscription) and with confidentiality of client data. No account was created.
