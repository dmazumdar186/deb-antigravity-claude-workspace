# Directives — Category Map

Reference moved out of CLAUDE.md (token-economy sweep 2026-09-01). Read this before creating any new directive or execution script. The same `{category}` subfolders exist under both `directives/` and `execution/`.

| Category | Purpose |
|----------|---------|
| `lead_sourcing/` | Finding leads — local business scrapers, Google Maps, Instagram, Apollo, Exa |
| `enrichment/` | Adding data to leads — email finding, verification, contact enrichment, domain checks |
| `personalization/` | Cold email copy & delivery — personalization, foundational copy, Instantly, GHL |
| `gtm_icp_filters/` | ICP research, lead qualification, signal scoring, filtering, buying signals |
| `gtm_client_workflows/` | Client-specific GTM pipelines (agent_gtm, bret_gtm, ecommerce_gtm) |
| `custom_scrapers/` | Generic scraping tools — Skool, browser automation, sitemap parser, Perplexity, SearXNG |
| `infrastructure/` | VPS deployment, Cloudflare workers, LLM hosting, fine-tuning, backup scripts |
| `content/` | Text processing — humanizer, PDF generation, diagrams, spam checker |
| `image_generation/` | Thumbnail creation, image assets |
| `video/` | Video analysis, YouTube downloads, transcripts, channel research |
| `personal_workflows/` | Personal automations — morning briefing, iMessage, email categorizer |
| `n8n_workflows/` | n8n workflow builder, API, dynamic generators |
| `crm_and_pm/` | CRM & project management — ClickUp, Typeform |
| `google/` | Google Workspace integrations (Gmail, Calendar, Meet, Sheets, Docs) |
| `rag/` | Retrieval-augmented generation, conversation memory |
| `subagent/` | Internal agent workflows (note_taker, documenter, reviewer) |
| `mobile_apps/` | Mobile app development — Expo + RN scaffolding, EAS Build, TestFlight/Play deploy |

**Shared modules** (`execution/modules/` only — no directive equivalent):

| Module | Purpose |
|--------|---------|
| `modules/sources/` | Lead source connectors (Apollo, Exa, Google Maps, CSV import) |
| `modules/scrapers/` | Web scrapers (BBB, Yelp, Yellow Pages, LinkedIn, Reddit, etc.) |
| `modules/enrichers/` | Enrichment plugins (Apollo, Clay, contact, minimal) |
| `modules/personalizers/` | Personalization strategies (full, light, none) |
| `modules/outputs/` | Output formatters (Instantly, SmartLead, CSV) |
| `modules/foundational_copy/` | Voice-of-customer research and copy generation |

## Creating new directives/scripts

```
□ Directive: directives/{category}/{name}.md
□ Script: execution/{category}/{name}.py
□ Both use the same {category} subfolder — snake_case names
□ Only create a new category if you have 3+ related files that don't fit existing ones (ask first)
□ Update directives/subagent/documenter.md mapping table if adding new script
```
