# Installed skill library

46 skills installed from `~/Downloads/skills-20260819T192521Z-1-001/skills`
into `.claude/skills/`. 32 run as-is; 14 need a value only you can supply.

`{{USER_NAME}}` was filled in automatically (51 occurrences), as was the
face-swap subject in `recreate-thumbnails`. Nothing else was guessed at.

Two things deliberately left alone:

- `{{ACCOUNT}}` is a runtime filename variable the Gmail scripts expand
  per account (`token_{{ACCOUNT}}.json`). It is not a gap.
- The `Demo Library Skill` banner in each file *documents* the placeholder
  syntax. Substituting inside it would rewrite the instructions telling a
  reader what to fill in, so those 92 mentions were skipped.

## Needs a value before first run

| Skill | What to set |
|---|---|
| `course-slideshow` | `{{USERNAME}}` — GitHub username (repo URL) |
| `create-proposal` | `{{COMPANY_NAME}}` — company name for proposal footers |
| `gmail` | the example.com addresses<br>`{{GCP_PROJECT_ID}}` — Google Cloud project holding the OAuth client |
| `gmaps-leads` | `{{SHEET_ID}}` — target Google Sheet ID |
| `inbox-cleaner` | the example.com addresses |
| `instantly-autoreply` | `{{SHEET_ID}}` — target Google Sheet ID |
| `linkedin-response` | `{{COMMUNITY_NAME}}` — community display name |
| `modal-deploy` | `{{MODAL_WORKSPACE}}` — Modal workspace slug |
| `multi-agent-chrome` | the example.com addresses |
| `outline-generator` | `{{COMMUNITY_NAME}}` — community display name<br>`{{COMMUNITY_SLUG}}` — community URL slug |
| `welcome-email` | the example.com addresses |
| `wework-booking` | `{{WEWORK_LOCATION}}` — WeWork location name<br>`{{WEWORK_ADDRESS}}` — WeWork street address<br>`{{WEWORK_CITY}}` — WeWork city<br>`{{WEWORK_COUNTRY}}` — WeWork country<br>`{{WEWORK_STATE}}` — WeWork state/region<br>the example.com addresses<br>`{{WEWORK_DEVICE_ID}}` — WeWork device ID from the app<br>`{{WEWORK_LOCATION_ID}}` — WeWork location ID<br>`{{WEWORK_SPACE_ID_NUM}}` — WeWork numeric space ID<br>`{{WEWORK_SPACE_UUID}}` — WeWork space UUID<br>`{{WEWORK_TIMEZONE_IANA}}` — IANA timezone (Europe/Paris)<br>`{{WEWORK_TIMEZONE_WIN}}` — Windows timezone name<br>`{{WEWORK_USER_UUID}}` — WeWork user UUID |
| `youtube-channel-analysis` | the example.com addresses |
| `youtube-tracker` | `{{GITHUB_USER}}` — GitHub username |

`wework-booking` is the heaviest: every UUID is specific to one person's
WeWork account and building, so it is effectively a template rather than a
working skill until you capture your own from a booking request.

## Runs as-is

`add-webhook`, `agent-review`, `algorithmic-art`, `browser-stealth`, `casualize-names`, `classify-leads`, `cross-niche-outliers`, `design-website`, `diagram-generator`, `excalidraw-flowchart`, `generate-report`, `gmail-inbox`, `gmail-label`, `instantly-campaigns`, `internationalize-metadata`, `literature-research`, `local-server`, `model-chat`, `onboarding-kickoff`, `pan-3d-transition`, `prompt-contract`, `recreate-thumbnails`, `reverse-prompt`, `scrape-leads`, `stochastic-multi-agent-consensus`, `thumbnail-generator`, `title-variants`, `upwork-apply`, `video-edit`, `video-to-action`, `x-search`, `youtube-outliers`

## Merged, not overwritten

These three already existed here. The incoming body is the fuller text and
was taken; the existing frontmatter was kept because it carries
`user_invocable: true`, which the incoming files lack and the slash commands
need. `allowed-tools` is the union of both — which is how `agent-review`
gained `Task`, the one tool a skill about spawning sub-agents should have.

- `agent-review`
- `prompt-contract`
- `reverse-prompt`

## Carrying an AM lockdown banner

These reference credentials `CLAUDE.local.md` puts off-limits. Installed and
usable against non-AM work; each now says so at the top of its own
instructions, where it gets read at the moment of use rather than only in a
file loaded at session start.

- `add-webhook` — INSTANTLY_API_KEY / GHL_API_KEY
- `gmaps-leads` — ANYMAILFINDER_API_KEY / MILLION_VERIFIER_API_KEY
- `instantly-autoreply` — INSTANTLY_API_KEY
- `instantly-campaigns` — INSTANTLY_API_KEY
- `modal-deploy` — INSTANTLY_API_KEY / GHL_API_KEY
- `scrape-leads` — ANYMAILFINDER_API_KEY / MILLION_VERIFIER_API_KEY

## Rollback

```
git checkout .claude/skills
```

The eight skills that were already here — `_template`, `firecrawl`,
`humanizer`, `impeccable`, `mobile-app`, `remotion`, `test-suite`,
`youtube-video-analyzer` — were untouched.
