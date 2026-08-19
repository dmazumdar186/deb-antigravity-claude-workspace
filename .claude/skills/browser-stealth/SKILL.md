---
name: browser-stealth
description: Stealth browsing that bypasses bot detection. Use when sites block normal Chrome DevTools MCP (Cloudflare, CAPTCHA, anti-bot). Invoke with /browser-stealth or when a site returns a bot challenge.
allowed-tools: Read, Bash, Glob, Grep
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Browser Stealth Skill

Use the `chrome-stealth` MCP server (not `chrome-devtools`) for sites that block automated browsers.

## Quick Reference

| Detection Level | What To Use |
|----------------|-------------|
| None / basic | Default `chrome-devtools` MCP (already has anti-automation args) |
| Medium (Cloudflare JS challenge, basic fingerprinting) | `chrome-stealth` MCP + initScript |
| Hard (Cloudflare Turnstile, DataDome, PerimeterX) | `chrome-stealth` MCP + initScript + emulate |

## Setup

Two MCP servers are configured globally in `~/.claude.json`:

1. **`chrome-devtools`** — standard MCP with `--disable-blink-features=AutomationControlled` and other anti-detection Chrome args
2. **`chrome-stealth`** — same package with `--stealth` flag (uses `puppeteer-extra-plugin-stealth` internally)

## Usage

### Step 1: Use the `chrome-stealth` MCP tools

All tools are prefixed with `mcp__chrome-stealth__` instead of `mcp__chrome-devtools__`. They work identically.

### Step 2: Set realistic emulation on first use

```
mcp__chrome-stealth__emulate:
  userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
  viewport: "1920x1080x2"
```

### Step 3: Use initScript on every navigate_page call

Read the initScript from this skill directory and pass it:

```
initScript = Read(".claude/skills/browser-stealth/stealth_init.js")

mcp__chrome-stealth__navigate_page:
  url: "https://target-site.com"
  initScript: <contents of stealth_init.js>
```

The initScript patches: `navigator.webdriver`, `window.chrome`, `navigator.plugins`, `navigator.languages`, `navigator.permissions`, WebGL vendor/renderer, canvas fingerprint noise, AudioContext noise, `window.outerWidth/Height`, `navigator.connection`.

### Step 4: For maximum stealth, add delays

Don't navigate instantly between pages. Add 2-5s human-like delays between actions.

## What Each Layer Does

### Layer 1: Chrome Args (always active)
- `--disable-blink-features=AutomationControlled` — removes `navigator.webdriver=true`
- `--disable-infobars` — removes "Chrome is being controlled" bar
- `--window-size=1920,1080` — realistic viewport
- `--lang=en-US` — consistent language

### Layer 2: initScript Patches (`stealth_init.js`)
- Patches JS APIs that headless/automated Chrome leaves fingerprints on
- Must be passed on every `navigate_page` call (doesn't persist across navigations)

### Layer 3: `--stealth` Flag
- Integrates `puppeteer-extra-plugin-stealth` at the Puppeteer level
- Patches CDP protocol-level detection vectors that JS can't fix
- Handles `Runtime.enable` detection, console timing attacks, isolated world leakage

## Limitations

- **TLS fingerprint**: Not an issue — real Chrome binary handles TLS, matches genuine Chrome JA3/JA4
- **CDP `Runtime.enable` detection**: `--stealth` mitigates this but very aggressive anti-bot (DataDome, Shape Security) may still detect it
- **CAPTCHAs**: Stealth helps avoid triggering them but cannot solve them. If a CAPTCHA appears, notify the user.
- **Rate limiting**: Stealth doesn't help with IP-based rate limits. Use proxies for that.

## Troubleshooting

### "Browser already running" error
Kill stale Chrome: `pkill -f chrome-devtools-mcp` or find the process holding `~/.cache/chrome-devtools-mcp/chrome-profile`

### Site still detecting bot
1. Check if initScript was passed (it doesn't persist — must be on every navigate_page)
2. Verify user agent via `mcp__chrome-stealth__evaluate_script` → `navigator.userAgent`
3. Try adding more delay between actions
4. Some sites (banking, ticketing) use server-side behavioral analysis — no browser-level fix for that
