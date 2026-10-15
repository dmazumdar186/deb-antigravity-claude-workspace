# Site redesign concepts — prospectus renderer (SOP)

## Goal
Turn a prospect's URL into a live, sellable concept site plus a pitch page, built as a designed
document (scroll-scrubbed cover, signature scroll object, command deck) — the MISB v3 standard
(2026-10-15). The SOP itself is the skill: `.claude/skills/site-redesign/SKILL.md`; mechanics in
`reference/concept_recipe.md`; rules in `reference/build_rules.md`. Static single-column pages
(MISB v2 shape) are banned.

## Inputs
- Target URL or brand, language, prospect name, theme hints.
- Env: `CLOUDFLARE_API_TOKEN`, `CLOUDFLARE_ACCOUNT_ID`, `OPENROUTER_API_KEY` (alias
  `OPENROUTER_API_TOEKN`), optional `HF_API_TOKEN` (Kling via Higgsfield).
- Chromium at `/opt/pw-browsers`, Playwright at `/opt/node-tools` or `/tmp/pwtest`, ffmpeg.

## Scripts (`.claude/skills/site-redesign/scripts/`)
| Script | Does |
|---|---|
| `measure_live.mjs <url>` | desktop/mobile scrollHeight, viewports, links, words as JSON |
| `gen_backdrop.py --brand --palette --motif --out` | GLM 5.3 → 5.2 → Kimi K3 canvas module; public facts only; cost log |
| `render_hero_video.mjs --site --url` | deterministic cover → hero.mp4/webm + portrait + poster + hero.json |
| `functional_template.mjs` | 29-assertion Playwright suite; set selector constants, keep names |
| `site_check.mjs --site` | desktop/Pixel 7/iPhone 13/reduced-motion gate |
| `deploy.sh <dir> <slug>-redesign <pitch>/` | Cloudflare Pages deploy + live md5 check |
Kling footage: `execution/gtm_client_workflows/greenjobs_redesign/generate_hero_footage.py`
(estimate first, `--go` to spend).

## Outputs
`deliverables/<slug>_redesign_<date>/{site,research,screens,HANDOFF.md}`; live
`https://<slug>-redesign.pages.dev/` + `/for-<name>/`; commit on branch and `main`.

## Process
Research → brief (template) → one build worker → functional + site_check → two reviewer rounds on
PNGs (SHIP required) → deploy → HANDOFF → commit/push → reply with links and outreach message.

## Edge cases
- **403 sites** (Akamai): `WebSearch site:`, Wikipedia API (space ~20 s), press; Wayback blocked.
- **No `HF_API_TOKEN`**: self-render the hero video; keep `hero.json ready:true`; note the Kling slot.
- **OpenRouter credit / model down**: chain falls to GLM 5.2 then Kimi K3; if all fail, write the
  backdrop by hand to the same API and log "manual" in `glm_log.md`.
- **Sandbox cannot open `*.pages.dev`**: verify on identical local files, compare live CSS md5.
- **Fonts only render live**: judge layout, not type, in sandbox screenshots.
- **Mid-animation screenshots** lie (counters off by one): wait for settle before capturing.
- Never send names, emails, phones or client data to GLM/Kimi; reject arguments containing them.
