# Remote control & mobile monitoring for this workspace

Three layers — pick what fits the moment.

## Layer 1: Read-only mobile status (zero setup, always works)

**URL**: https://cv-optimizer.pages.dev/status

Bookmark on phone home screen. Shows:
- Worker `/api/health` (status, version, prompt+schema fingerprint, secrets present)
- Live `STATUS.md` rendered from the GitHub `main` branch (auto-updates within a minute of any push)
- Last 5 commits with messages and timestamps
- Refreshes every 60s when foregrounded; manual refresh button

Use cases: "Is the last deploy healthy?", "What were we doing?", "Did the eval pass?"

To update what mobile sees: edit `STATUS.md` at workspace root, commit, push. Within ~30s, mobile reload picks it up.

## Layer 2: Drive Claude Code from a phone browser (Claude Code Web)

**URL**: https://claude.ai/code (on phone browser, signed in with same Anthropic account as the laptop CLI)

Behaviour: a Claude Code chat that runs entirely in the cloud. No file access to this workspace by default — it can answer questions, plan, write code in its own scratch area, but cannot directly edit files in `c:\Users\deban\OneDrive\Documents\AntiGravity Project Space`.

Use cases: "Continue the plan we wrote", "Draft a new directive", "Read my repo on GitHub and propose changes" (it can do gh CLI + GitHub MCP if added).

To make it touch this workspace, push your changes via git first; the web session reads the public repo at `github.com/dmazumdar186/deb-antigravity-claude-workspace`.

## Layer 3: Phone drives the laptop's local Claude session (Remote Control)

This is the only path that gives a phone **write access to local files**.

**Setup (one-time, requires the laptop available):**

A desktop shortcut named **"Claude Remote Control"** has been installed on the Desktop. Double-click it. A real `cmd.exe` window opens (the only reliable way to give Claude the interactive tty it needs on Windows — subprocess redirection from another shell collapses to print-mode and fails). After a few seconds, the window prints a URL like `https://claude.ai/code/remote/<token>` plus a QR code. On the phone, scan the QR or open the URL on a phone signed into the same Anthropic account — you'll see a chat that drives the laptop session.

To re-create the shortcut (e.g. after profile reset, new machine), run inline PowerShell or the helper at `execution/personal_workflows/remote_control_mobile/install_shortcut.ps1`.

Manual command (if you ever need it):

```powershell
claude --remote-control "AntiGravity-CV-Optimizer"
```

**Launch helper** (PowerShell, persists across logout — see `execution/personal_workflows/remote_control_mobile/launch.ps1`):

```powershell
& "<workspace>\execution\personal_workflows\remote_control_mobile\launch.ps1"
```

That script:
1. Kills any prior `claude --remote-control` session of the same name.
2. Spawns a new one detached, redirects stdout to a log file.
3. Tails the log for the connection URL and prints it (so you can copy to phone immediately).
4. Optionally posts the URL to a Telegram chat (if `TELEGRAM_BOT_TOKEN` + `TELEGRAM_CHAT_ID` are in env) — phone gets a notification with the URL.

**Behaviour:**

- The laptop session stays alive as long as the laptop is on and unlocked. Sleeping/closing the lid will pause it.
- Phone sends a message → laptop session executes (with full file/tool access) → phone sees the response.
- Multiple devices can attach to the same named session.

**Known limits (2026-06-14):**

- Backgrounding via `cmd.exe /c start` doesn't work reliably on Windows; the launcher uses PowerShell `Start-Process -RedirectStandardOutput` instead.
- If the laptop is on battery and sleeps, the session pauses; ensure power adapter is connected.
- Cloudflare Tunnels / Tailscale not required — the CLI handles the relay.

## Choosing the right layer

| Situation | Layer |
|---|---|
| Just want to see "is it healthy / what's the eval rate" | 1 (status page) |
| Want to chat-plan a new directive from couch / coffee | 2 (Claude Code Web) |
| Need to run a deploy / commit / file edit from phone | 3 (Remote Control) |

## Outstanding items

- Layer 3 launch script (`execution/personal_workflows/remote_control_mobile/launch.ps1`) needs operator verification — the Windows console behaviour for detached `claude --remote-control` was unreliable when first tested 2026-06-14. Confirm URL extraction works end-to-end before treating Layer 3 as production-ready.
- Telegram notification path (optional in the launcher) needs `TELEGRAM_BOT_TOKEN` provisioning. Defer to when user has time.

## Exit Criteria

- Layer 1: `STATUS.md` edits propagate to `https://cv-optimizer.pages.dev/status` within 60s (manual mobile reload).
- Layer 2: claude.ai/code accepts a phone-issued prompt and returns a coherent reply for this workspace (signed into same Anthropic account).
- Layer 3: double-clicking the desktop shortcut opens a real cmd.exe console, `claude --remote-control` prints a connection URL within 30s, the URL opens on phone, and a phone-issued prompt executes a file edit + commit on the laptop. **Not yet verified.**

## Related

- Layer 1 status page source: `execution/personal_workflows/cv_optimizer_v2/web/status.html`
- Editable status text: `STATUS.md` at workspace root
- `directives/infrastructure/canary_monitoring.md` covers external uptime probes (complementary, not a replacement for this).
