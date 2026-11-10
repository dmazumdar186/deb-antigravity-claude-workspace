# Directive: Always-on VPS for the self-hosted tools (Hetzner CX43)

Workspace-local SOP for turning a fresh Hetzner CX43 into an always-on host for FreeLLMAPI, OpenSEO, OpenCode, VoiceStudio, OpenBot and PentAGI, driven afterwards by Claude Code Remote Control. Sizing and provider choice: `docs/reference/vps_scope_2026-11-09.md`. Per-tool SOPs: `freellmapi.md`, `open_seo.md`, `opencode.md`, `voicestudio.md`, `openbot.md`, `pentagi.md`.

> **Status: on hold (2026-11-10).** Operator set a 0€ spend limit; do not create a paid server. See `docs/reference/vps_scope_2026-11-09.md`.

## Goal

One paste (cloud-init) in the Hetzner web console builds the whole box with zero terminal work; one command in the Hetzner browser console (`vps-finish-setup`) does the only two human logins (Tailscale, Claude). After that, Claude operates the box.

## Inputs

- Hetzner Cloud account with a payment method; a Tailscale account (free personal plan); the Claude account.
- **No secrets in the cloud-init.** Tool keys are entered later in each tool's dashboard or `.env` on the box.

## Tools / scripts

- `execution/infrastructure/vps_cloud_init.yaml` — paste into "Cloud config". Creates user `deb` (sudo, docker), no public SSH, ufw (tailscale0 only), 8 GB swap, Docker CE + compose, Node 22, Tailscale, gh, Claude Code (npm, user prefix), uv + SkillSpector, clones this repo to `/home/deb/workspace`, installs `deb-tools-install.service` (started) and `claude-remote-control.service` (not enabled).
- `execution/infrastructure/vps_install_tools.sh` — runs the six `setup_*.sh` scripts in order; per-tool logs `/var/log/deb-tools/<tool>.log`, table `/var/log/deb-tools/summary.txt`; marker `/var/lib/deb-tools/installed` only when all succeed. `--dry-run`, `--force`.
- `execution/infrastructure/vps_finish_setup.sh` (`/usr/local/bin/vps-finish-setup`) — Tailscale up, Claude login, workspace trust, enable Remote Control, `tailscale serve` per UI, status. `--dry-run`.
- Test: `python3 -m pytest -q tests/test_vps_cloud_init.py` (offline).

## Steps (operator, browser only)

1. Hetzner Console → create a project → **Add Server**.
2. Location **NBG1** (Nuremberg) or **HEL1** (Helsinki). Image **Ubuntu 24.04**. Type **Shared vCPU → x86 → CX43**. Networking **IPv4 + IPv6**.
3. SSH key: none needed (root password arrives by email; break-glass only). If no email arrives, use the server's **Rescue → Reset root password** button in the Hetzner Console (unverified that the emailed password survives custom cloud config).
4. **Firewalls** → create one whose only inbound rule is **UDP 41641** (lets Tailscale connect directly instead of via relays) and attach it.
5. **Cloud config** → paste the whole of `vps_cloud_init.yaml` → **Create & Buy**.
6. Wait ~10 min. Open the server's **Console** (top-right `>_`), log in as `root` with the emailed password (you may be forced to set a new one).
7. Run `vps-finish-setup` (if "command not found", setup is still running: `cloud-init status --wait`, then retry). Click the Tailscale link on your phone; open the Claude link, sign in, paste the code back.
8. Phone: install the Tailscale app, sign in with the **same** account. The script prints the tailnet URLs.
9. From here, Claude (Remote Control session `hetzner-cx43`) does the rest, including OpenBot's email-code login.

## Outputs

- `hetzner-cx43` visible in the Claude app via Remote Control (`claude-remote-control.service`).
- Tailnet-only HTTPS: `:3001` FreeLLMAPI, `:3011` OpenSEO, `:3900` VoiceStudio, `:8443` PentAGI. Every service stays bound to `127.0.0.1`; nothing is public.
- `/var/log/deb-tools/summary.txt` with one OK/FAIL row per tool.

## Edge cases / learnings

- **"Unavailable" in Hetzner:** stock varies per location; try the other of NBG1/HEL1 (or FSN1). Fallback provider in the scope doc.
- **Logs:** `/var/log/cloud-init-output.log`, `/var/log/deb-vps-bootstrap.log` (failed bootstrap steps are also printed on the console and in `/etc/motd`).
- **Re-run the tool install:** `rm /var/lib/deb-tools/installed && systemctl start deb-tools-install` (follow with `journalctl -fu deb-tools-install`). The first run is long: VoiceStudio images are ~17 GB.
- **Re-run the finish step:** `vps-finish-setup` is idempotent; every step skips if already done.
- **Tailscale HTTPS certificates** must be enabled in the Tailscale admin console (DNS → HTTPS Certificates) for `tailscale serve --https`; the script warns per port if not.
- **No public SSH by design.** Hetzner Cloud Firewall allows only UDP 41641 (Tailscale) and ufw only allows `tailscale0` + 41641/udp; SSH in via `tailscale ssh deb@hetzner-cx43` or the web console.
- **Claude is effectively root on this box.** User `deb` has `NOPASSWD:ALL` sudo and Remote Control runs with `--permission-mode auto`, so anything you ask the Remote Control session to do can change the whole server. Intentional (no-HITL operation); keep nothing else of value on this box and never reuse its credentials.
- **Unattended upgrades** reboot at 04:30 server time when needed; the tool containers and Remote Control come back on their own (unverified until the first reboot).
- **Cost:** CX43 €16.49/mo excl. VAT (read 2026-11-09), plus paid APIs (DataForSEO, model providers).
- **PentAGI:** only scan targets you own or have written permission for; Hetzner's AUP prohibits unauthorized scanning. **OpenBot** is PolyForm Noncommercial.
- **Unverified pieces (check on first boot):** `claude auth login` / `claude auth status` in a plain console (fallback: `sudo -iu deb claude` then `/login`); credentials path `/home/deb/.claude/.credentials.json` (the Remote Control unit's ConditionPathExists); trust key `projects[<path>].hasTrustDialogAccepted` in `~/.claude.json`; `claude remote-control --name --permission-mode auto` running unattended under systemd.
