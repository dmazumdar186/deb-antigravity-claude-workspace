---
name: casualize-names
description: Convert formal names to casual versions for cold email personalization. Use when preparing leads for outreach, casualizing company names, first names, or city names.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Casualize Names Workflow

This workflow converts formal names (first names, company names, cities) to casual, friendly versions suitable for cold email copy. It processes all three fields in a single API call for efficiency.

**Prerequisite**: Leads should already be scraped and uploaded to a Google Sheet. See [scrape_leads.md](scrape_leads.md) for the full lead generation workflow.

## 1. Gather Information
Ask the user for:
- **Google Sheet URL**: The URL of the sheet containing the leads (must have first_name, company_name, and city columns).

## 2. Execute Casualization

```bash
python3 -u .claude/skills/casualize-names/casualize_batch.py "GOOGLE_SHEET_URL"
```

**Options:**
- Add `--overwrite` flag to re-process existing casual names

**How it works:**
1. Processes records in batches of 50 (first_name, company_name, city together)
2. Uses 5 parallel workers to send batches simultaneously
3. Claude AI converts all three fields in one API call (3x faster than separate calls)
4. Returns JSON with casualized versions for all fields
5. Automatic retry with exponential backoff for rate limits
6. Batch updates Google Sheet with results
7. Only processes rows with emails

**Expected speed**: ~30-40 records/sec (3,000 records ~ 90 seconds vs 600-900 seconds for separate calls)
**Actual performance**: 3,684 records in 105 seconds = 35 records/sec

## 3. Casualization Rules

### First Names
- Use most common, widely-accepted nicknames (e.g., "William" -> "Will", "Jennifer" -> "Jen")
- If no common nickname exists, keep original
- Keep it professional

**Examples:**
- "William" -> "Will"
- "Jennifer" -> "Jen"
- "Michael" -> "Mike"
- "Elizabeth" -> "Liz"
- "John" -> "John" (already casual)

### Company Names
- Remove "The" at the beginning
- Remove legal suffixes (LLC, Inc, Corp, Ltd, etc.)
- Remove generic words: Realty, Real Estate, Group, Healthcare, Solutions, Services, Associates, Company, Family, Center, Clinic
- Keep core brand name + industry identifier only if brand alone is too generic
- Use "you guys" as fallback for overly generic names

**Examples:**
- "Keller Williams Realty Inc" -> "Keller Williams"
- "Berkshire Hathaway Homeservices" -> "Berkshire Hathaway"
- "The Teal Umbrella Family Dental Healthcare" -> "Teal Umbrella"
- "Realtor" -> "you guys" (too generic)

### City Names
- Use common local nicknames and abbreviations that locals use
- If no common nickname exists, keep original
- Make it feel natural and friendly

**Examples:**
- "San Francisco" -> "SF"
- "Philadelphia" -> "Philly"
- "New York" -> "NYC"
- "Los Angeles" -> "LA"
- "Washington" -> "DC"
- "Boston" -> "Boston" (already casual)

## 4. Results

The script will:
- Create three new columns: "casual_first_name", "casual_company_name", "casual_city_name"
- Populate all three casual fields for each row with email in one pass
- Skip rows without emails (no need for casual names)

**Note**: Use `-u` flag for unbuffered output to see real-time progress.

## 5. Legacy Scripts

For backwards compatibility, individual casualization scripts still exist:
- `active/execution/casualize_first_names_batch.py` (legacy, removed)
- `active/execution/casualize_company_names_batch.py` (legacy, removed)
- `active/execution/casualize_city_names_batch.py` (legacy, removed)

However, `casualize_batch.py` is 3x faster and should be used for all new workflows.
