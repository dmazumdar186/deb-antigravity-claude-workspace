# Accessory Masters — GTM Pipeline Master Directive

## Goal
Run the end-to-end cold email pipeline for Accessory Masters: source business leads, find and verify emails, generate personalized openers, upload to Instantly.ai, detect replies, classify positive/negative/neutral, route positive leads to GoHighLevel CRM, and notify the team via Slack.

## When to Use
- **Daily**: Run the sourcing-to-upload pipeline for new leads
- **Every 30 min**: Reply polling (via cron or manual trigger)
- **Weekly**: Report generation (not yet automated — Block 3 deliverable)
- **On demand**: Run a single stage to debug or re-process

## Inputs

### Environment Variables
| Variable | Purpose | Source |
|----------|---------|--------|
| `SERPER_API_KEY` | Google Maps scraping | Client provides (May 1) |
| `PROSPEO_API_KEY` | B2B lead database | Client provides (May 1) |
| `ANYMAILFINDER_API_KEY` | Email finder | Client provides (May 1) |
| `MILLION_VERIFIER_API_KEY` | Email verification | Client provides (May 1) |
| `ANTHROPIC_API_KEY` | AI openers + reply classification | Already in .env |
| `INSTANTLY_API_KEY` | Lead upload + reply polling | Already in .env |
| `GHL_API_KEY` | CRM contact/opportunity creation | Client provides (May 1) |
| `SLACK_WEBHOOK_URL` | Positive reply notifications | Configure after Slack channel created |

### Config Files
- `config/accessory_masters.json` — ICP, geography, thresholds, API URLs, pipeline settings
- `config/tone.json` — AI opener voice, tone, examples, never-say list

## Tools/Scripts

### Subsystem Directives
| Directive | Covers |
|-----------|--------|
| `directives/lead_sourcing/google_maps_sourcing.md` | Serper.dev Maps API + Prospeo fallback |
| `directives/enrichment/email_find_verify.md` | AnymailFinder + Million Verifier |
| `directives/personalization/cold_email_sequences.md` | Claude AI opener generation |
| `directives/infrastructure/domain_inbox_management.md` | Domains, inboxes, warmup (Bryce's domain) |

### Execution Scripts
| Script | Purpose |
|--------|---------|
| `execution/lead_sourcing/serper_maps_scraper.py` | Google Maps sourcing via Serper.dev |
| `execution/lead_sourcing/prospeo_leads.py` | Prospeo B2B sourcing |
| `execution/enrichment/anymailfinder_lookup.py` | Email finder |
| `execution/enrichment/million_verifier.py` | Email verifier |
| `execution/personalization/ai_opener_generator.py` | AI opener generation |
| `execution/gtm_client_workflows/accessory_masters_pipeline.py` | Master orchestration |

### Shared Modules
| Module | Purpose |
|--------|---------|
| `execution/modules/pipeline_utils.py` | Retry logic, dedup, lead I/O, config loading, logging |

### PRD
| Document | Purpose |
|----------|---------|
| `directives/gtm_client_workflows/accessory_masters_prd.md` | Full project requirements, timeline, roles, tech stack |

## Outputs
- `.tmp/serper_leads.json` — raw sourced leads
- `.tmp/prospeo_leads.json` — Prospeo leads (B2B niches)
- `.tmp/enriched_leads.json` — leads with owner emails
- `.tmp/verified_leads.json` — leads with verified emails
- `.tmp/personalized_leads.json` — leads with AI openers (final)
- `.tmp/instantly_upload.csv` — CSV formatted for Instantly bulk upload
- `.tmp/pipeline_state.json` — checkpoint state for resume
- `.tmp/pipeline.log` — execution log
- Leads uploaded to Instantly.ai campaign via API
- Positive replies routed to GoHighLevel (contacts + opportunities)
- Slack notifications for positive replies

## Steps — Full Pipeline (Daily)

1. Run the full pipeline with mock data (testing):
   ```
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --mock
   ```

2. Run the full pipeline with real API keys:
   ```
   py execution/gtm_client_workflows/accessory_masters_pipeline.py
   ```

3. Run a specific stage only:
   ```
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage source --mock
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage enrich
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage verify
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage personalize
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --stage upload
   ```

4. Force re-run (ignore checkpoint state):
   ```
   py execution/gtm_client_workflows/accessory_masters_pipeline.py --force --mock
   ```

## Steps — Individual Scripts (for debugging)

5. Source leads from Google Maps:
   ```
   py execution/lead_sourcing/serper_maps_scraper.py --query "car wash Houston TX" --mock
   py execution/lead_sourcing/serper_maps_scraper.py --config config/accessory_masters.json
   ```

6. Source B2B leads from Prospeo:
   ```
   py execution/lead_sourcing/prospeo_leads.py --company "Houston Manufacturing" --mock
   ```

7. Find emails:
   ```
   py execution/enrichment/anymailfinder_lookup.py --input .tmp/serper_leads.json --mock
   ```

8. Verify emails:
   ```
   py execution/enrichment/million_verifier.py --input .tmp/enriched_leads.json --mock
   ```

9. Generate openers:
   ```
   py execution/personalization/ai_opener_generator.py --input .tmp/verified_leads.json --mock
   ```

## Steps — Reply Polling (Every 30 min)

10. Poll for new replies, classify, and route:
    ```
    py execution/gtm_client_workflows/accessory_masters_pipeline.py --poll-replies --mock
    ```

## Data Flow
```
Serper Maps API                  Prospeo API
      |                               |
      v                               v
serper_maps_scraper.py          prospeo_leads.py
      |                               |
      +---------- merge + dedup ------+
                      |
                      v
           .tmp/serper_leads.json
                      |
                      v
          anymailfinder_lookup.py
                      |
                      v
          .tmp/enriched_leads.json
                      |
                      v
            million_verifier.py
                      |
                      v
          .tmp/verified_leads.json
                      |
                      v
          ai_opener_generator.py
                      |
                      v
        .tmp/personalized_leads.json
                      |
                      v
         Instantly.ai API upload
                      |
                      v (async, 30-min polling)
         Reply detection + AI classification
                      |
              +-------+-------+
              |               |
          positive        negative/neutral
              |               |
              v               v
      GHL contact +       log only
      opportunity +
      Slack notification
```

## Edge Cases
- **Pipeline crash mid-stage**: Re-run the pipeline. Checkpoint resume skips completed stages. Use `--force` to re-run everything.
- **API key missing**: Pipeline logs which key is missing and exits with clear instructions.
- **Config not finalized**: Use defaults in config file (10 niches from PRD, Houston + suburbs). Update when client provides final ICP/tone inputs.
- **Instantly campaign_id not set**: Pipeline completes up to personalization but skips upload. Logs a warning.
- **GHL pipeline_id/stage_id not set**: Reply routing logs a warning and skips opportunity creation. Contact creation still works.
- **No verified leads after enrichment**: Normal for some batches. Pipeline continues but there's nothing to personalize or upload.

## Changelog
| Date | Change |
|------|--------|
| 2026-04-29 | Created — initial master directive covering full pipeline |
