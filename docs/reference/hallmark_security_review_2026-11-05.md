# Hallmark security review (2026-11-05)

Target: https://github.com/Nutlope/hallmark @ `407fa689f4a276f2fd389208d271d0fef08f5058` (v2.0.0, MIT), path `skills/hallmark/`.
Method: `skill-inspector` workflow. SkillSpector is not installed in the cloud container (static line incomplete; not installed per the skill's "no silent installs" rule). Manual source-aware review instead: every script grepped for network, `child_process`, fs writes, env reads, dynamic import, `eval`; SKILL.md and all `references/*.md` read or scanned for injection, install, settings, credential and spend instructions. No target script was executed before review.

## Verdict: SAFE-WITH-EXCLUSIONS (skill-inspector label: CAUTION)

No malicious, obfuscated or exfiltrating code. No telemetry. No credential reads beyond the opt-in `TOGETHER_API_KEY`. Risks are spend, settings persistence and self-modification, all in files excluded from the vendored copy.

## Findings (paths relative to `skills/hallmark/`)

| # | Sev | File:line | Finding | Disposition |
|---|---|---|---|---|
| 1 | HIGH (spend) | `scripts/imagegen.mjs:6,60,71` | POSTs prompts to `https://api.together.xyz/v1/images/generations` (FLUX.1.1-pro, paid) with `TOGETHER_API_KEY`. | Excluded. |
| 2 | HIGH (spend) | `references/flow.md:101`, `references/comp.md:3,27` | The comp step "fires only when `TOGETHER_API_KEY` is set" — i.e. automatically on key presence, no per-run approval (Codex row at `flow.md:114` asks approval, Claude row does not). | Neutralised by the override block in vendored `SKILL.md`; script absent. |
| 3 | MED (persistence) | `scripts/install-hook.mjs:14-16,56,68` | Rewrites `./.claude/settings.json` or `~/.claude/settings.json` to add a PostToolUse hook (atomic, idempotent, `--remove` exists). | Excluded; settings untouched. |
| 4 | LOW | `scripts/lint-hook.mjs:3,31` | The hook body: `execFileSync(node, sloplint)` on the edited file, returns additionalContext. Benign, but injects text into every Write/Edit turn on matching files. | Excluded with #3. |
| 5 | MED | `scripts/install.mjs:16-17,64,73,82` | Copies into `~/.claude/skills`, `~/.agents`, `~/.config/opencode`; `rmSync(recursive, force)` of prior install dirs. | Excluded. |
| 6 | LOW (self-modify) | `scripts/picture.mjs:59,68,69` | Writes theme `.jpg` and rewrites theme `.md` inside the skill, then rebuilds the index. Maintainer tool. | Excluded. |
| 7 | LOW | `scripts/capture.mjs:43`, `sloplint-render.mjs:118` | `execSync('npm root -g')` (fixed string, no input) to locate a global puppeteer. | Kept; benign. |
| 8 | LOW (supply chain) | `scripts/sloplint-render.mjs:112-113` | Resolves `puppeteer`/`puppeteer-core` from `process.cwd()` first, then `HALLMARK_PUPPETEER`. A planted `node_modules` in cwd would be loaded under `--render`. | Kept; run from a trusted cwd. Render tier inert anyway (no puppeteer installed). |
| 9 | LOW (network, opt-in) | `scripts/theme.mjs:407-418` | `photos --save` downloads from Wikimedia only (URL prefix asserted `https://upload.wikimedia.org/`, image content-type checked, 60 s timeout, 429 retry). Free. | Kept. |
| 10 | LOW (writes) | `scripts/sloplint.mjs:4173,4373,4400-4403`; `sloplint-render.mjs:82-85,281,323`; `theme.mjs:72,97,152` | Writes only `.hallmark/` (cwd or beside the target) on `--before`/`--render`/`--kept`; theme log + salt in project `.hallmark/`; `theme.mjs index` rewrites `references/themes/index.json`. Static sloplint writes nothing (verified: no files appeared under `deliverables/`). | Kept; documented in VENDORED.md. |
| 11 | INFO (prompt) | `SKILL.md:14`; `flow.md:117` | Branding line "Powered by Together AI"; advises offering `npm i -g puppeteer-core`; "no parallel tool calls"; one AskUserQuestion round. No instructions to bypass safety, read secrets, hide actions or contact third parties. Font/CDN URLs in references are Google Fonts, Fontshare, simpleicons (normal page assets). | Override block: no unasked installs, workspace rules win. |
| 12 | INFO (trigger) | `SKILL.md:3` | Description (252 chars) triggers on any "build or design something new", overlapping `/site-redesign`. | Shortened to 238 chars and scoped. |

`.github/workflows/verify.yml` runs only the repo's own tests; no secrets used. `agents/openai.yaml` sets Codex implicit invocation (not vendored).

## Vendored set
`SKILL.md` (2 local edits), `LICENSE`, `references/` (md + 50 theme jpg), `scripts/{sloplint,sloplint-render,theme,capture}.mjs`, `scripts/photos.json`. See `.claude/skills/hallmark/VENDORED.md`.
