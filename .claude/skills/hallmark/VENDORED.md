# Hallmark — vendored third-party skill

- Source: https://github.com/Nutlope/hallmark (path `skills/hallmark/`), MIT (`LICENSE` kept), v2.0.0
- Commit: `407fa689f4a276f2fd389208d271d0fef08f5058`
- Vendored: 2026-11-05. Security review: `docs/reference/hallmark_security_review_2026-11-05.md` (SAFE-WITH-EXCLUSIONS).
- Used by: `/site-redesign` (Hallmark plan at research; `scripts/hallmark_gate.mjs` before review and deploy).

## Kept
`SKILL.md`, `LICENSE`, all of `references/` (incl. 50 theme `.jpg` previews, ~5 MB: SKILL.md Steps 3–4 look at
`references/themes/<slug>.jpg` by path when dealing a theme; workspace rule: only a worker Reads them),
`scripts/sloplint.mjs`, `scripts/sloplint-render.mjs`, `scripts/theme.mjs`, `scripts/capture.mjs`, `scripts/photos.json`.

## Excluded (and why)
| File | Why |
|---|---|
| `scripts/imagegen.mjs` | Paid Together AI image generation (`api.together.xyz`, FLUX 1.1 pro); upstream auto-fires the comp step whenever `TOGETHER_API_KEY` is set. Spend needs operator word + budget guard + ledger. |
| `scripts/install-hook.mjs`, `scripts/lint-hook.mjs` | Write a PostToolUse hook into `./.claude/settings.json` or `~/.claude/settings.json`. Settings are operator-owned. |
| `scripts/install.mjs` | Copies into `~/.claude/skills`, `~/.agents`, `~/.config/opencode` and `rm -rf`s prior copies. Not how this workspace installs skills. |
| `scripts/picture.mjs` | Maintainer tool: rewrites the skill's own theme `.md`/`.jpg` files. |
| `scripts/refcheck.mjs`, `*.test.mjs`, `scripts/fixtures/` | Upstream CI self-checks; not needed at runtime. |
| `agents/openai.yaml`, `.claude-plugin/`, `site/`, `eval/`, `docs/`, README, ROADMAP | Other harnesses, marketing site, model eval harness. |

## Local edits (only these)
1. `description:` shortened 252 → 238 chars (workspace cap ~250) and narrowed so it does not take over
   client concept builds (those route through `/site-redesign`).
2. A "Workspace overrides" block after the intro in `SKILL.md`: no comp/imagegen, no hook, render tier
   needs `puppeteer-core` (not installed; never `npm i` unasked), theme pictures via workers only,
   no-HITL and parallel-call rules win.

Runtime notes: static `sloplint.mjs` writes nothing. `--before`/`--render` write `.hallmark/` (cwd or
next to the target); `theme.mjs` writes `.hallmark/log.json` + `salt` in the project and fetches
Wikimedia only with `photos --save`.

## Update procedure
1. Clone upstream into an empty dir under `/tmp`; do not run anything in it.
2. `git diff 407fa68..<new>` over `skills/hallmark/`; re-run the skill-inspector review on changed scripts
   (grep `fetch|child_process|writeFileSync|homedir|process.env`), and re-read SKILL.md/references for new
   instructions (network, installs, settings, auto-fire spend).
3. Copy only the kept files over this folder; re-apply the two local edits; update the SHA/date above.
4. `node .claude/skills/hallmark/scripts/sloplint.mjs <fixture html> --json` from `/tmp` must return JSON.
