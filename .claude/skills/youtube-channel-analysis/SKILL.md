---
name: youtube-channel-analysis
description: Full-stack YouTube channel and market analysis. Use when evaluating course/video opportunities, competitive positioning, or content strategy decisions combining YouTube, Google Trends, and Studio analytics.
allowed-tools: Read, Grep, Glob, Bash
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# YouTube Whole-Channel Analysis

## Purpose

Produce a comprehensive, multi-source analysis of a YouTube channel's market position, competitive landscape, and content opportunities. The output is a research report that separates hype from durable trends and identifies the highest-ROI content investments.

## Why This Exists

No single data source tells the full story:
- **YouTube view counts** can't distinguish hype bubbles from platform trends (Clawdbot at 164K looks like the agentic course at 140K -- but one is a bubble and one is evergreen)
- **Google Trends** can't tell you what YOUR channel captures (Claude Code at 83/100 demand, but you might only capture 0.6% of it)
- **YouTube Studio** can't tell you whether a topic is growing or dying externally (your n8n search views look massive, but the trend is declining)

The three-layer validation (market demand via Google Trends, competitive landscape via YouTube browsing, own-channel performance via Studio) produces high-conviction recommendations that any single source would miss.

## Inputs

1. **Channel to analyze** -- the target YouTube channel URL
2. **Topic space** -- the broad category (e.g., "AI automation," "web development," "finance")
3. **Candidate topics** -- specific course/video ideas to evaluate (can be generated during research)
4. **YouTube Studio access** -- the channel owner needs to provide:
   - Traffic source summary (Content tab -> all videos -> traffic sources)
   - Top videos by views (last 28 days) with avg view duration
   - YouTube search terms CSV export (Traffic Source -> YouTube Search -> drill in -> export)

## Outputs

1. **YouTube Strategy Report** (`active/youtube-strategy/reports/YYYY-MM-DD_report-slug.md`) -- analysis-first strategy doc with scored recommendations
2. **Google Doc** -- automatically created from the report via `.claude/skills/youtube-channel-analysis/md_to_gdoc.py`
3. **Raw data** (`active/youtube-strategy/research/YYYY-MM-DD_raw-data.md`) -- all raw data collected during browsing
4. **YouTube Studio exports** (`active/youtube-strategy/stats/STARTDATE_ENDDATE_type.zip`) -- CSV exports from Studio

### File naming convention
All files use `YYYY-MM-DD_descriptive-slug` format for chronological sorting and context.

## Process

### Phase 1: YouTube Browsing -- Channel & Competitor Data

**Tool:** Chrome DevTools MCP (browse YouTube directly)

**Steps:**

1. **Analyze the target channel:**
   - Navigate to `youtube.com/@{channel}/videos` and sort by Popular
   - Record: subscriber count, total videos, upload frequency
   - Capture top 25 videos by views (title, views, age)
   - Capture last 2 weeks of uploads (title, views, age)
   - Note patterns: what formats work, what titles work, dollar amounts, course lengths

2. **Analyze 5-8 competitors:**
   - For each competitor: navigate to their channel, sort by Popular
   - Record: subscriber count, total videos, top 10 videos, recent uploads
   - Note their angle, audience overlap, threat level
   - **Critical:** Verify subscriber counts yourself -- LLM-generated reports are frequently wrong by 2-5x

3. **Search YouTube for topic gaps:**
   - Search each candidate topic (e.g., "claude code full course")
   - Note: how many results exist, their view counts, their ages
   - Identify supply-demand mismatches (high search interest, few quality results)

4. **Record everything** in `active/youtube_raw_data.md`

**JavaScript snippets for data extraction:**

Channel stats:
```javascript
() => {
  const text = document.body.innerText;
  const subMatch = text.match(/(\d+[\.\d]*[KMB]?\s*subscribers)/i);
  const vidMatch = text.match(/(\d+[\.\d]*[KMB]?\s*videos)/i);
  return { subscribers: subMatch ? subMatch[0] : null, videos: vidMatch ? vidMatch[0] : null };
}
```

Video grid data (from channel videos page):
```javascript
() => {
  const videos = document.querySelectorAll('ytd-rich-item-renderer, ytd-grid-video-renderer');
  return Array.from(videos).slice(0, 25).map(v => ({
    title: v.querySelector('#video-title')?.textContent?.trim(),
    views: v.querySelector('#metadata-line span')?.textContent?.trim(),
    age: v.querySelectorAll('#metadata-line span')[1]?.textContent?.trim()
  }));
}
```

### Phase 2: Google Trends -- Trend Durability Analysis

**Tool:** Chrome DevTools MCP (browse Google Trends)

**Purpose:** Classify each topic as Platform Trend, Emerging Durable, Hype Bubble, or Declining/Dead.

**Steps:**

1. **Run comparison groups** (max 5 terms per comparison on Google Trends):

   Group by relevance. Example groups for AI automation space:
   - Group 1: `n8n` vs `Claude Code` vs `Make.com` vs `AI agents`
   - Group 2: `Clawdbot` vs `agentic workflows` vs `vibe coding` vs `MCP server`
   - Group 3: `voice AI agent` vs `AI automation` vs `AI automation agency` vs `RAG tutorial`
   - Group 4: `Cursor AI` vs `Claude Code` vs `Copilot AI` vs `Lovable AI`
   - Group 5: `AI lead generation` vs `AI cold email` vs `AI web scraping` vs `build SaaS with AI`

2. **For each comparison:**
   - Navigate to Google Trends with 12-month timeframe, Web Search
   - Extract the time-series table data
   - Re-run with YouTube Search as the source (different dropdown)
   - For suspected hype bubbles: re-run with 90-day timeframe + daily granularity

3. **Extract table data** using JavaScript:
   ```javascript
   () => {
     const rows = document.querySelectorAll('table tr');
     const data = [];
     rows.forEach(row => {
       const cells = row.querySelectorAll('td, th');
       if (cells.length >= 5) {
         const vals = Array.from(cells).map(c => c.textContent.trim());
         data.push(vals);
       }
     });
     return data;
   }
   ```

4. **Classify each topic:**

   | Pattern | Classification | Content Strategy |
   |---------|---------------|-----------------|
   | Steady growth over 6+ months, no crash after spikes | **Platform Trend** | Build definitive long-form courses |
   | Consistent growth 3-6 months, moderate volume, no bubble shape | **Emerging Durable** | Position early with comprehensive content |
   | Near-vertical spike, 50%+ decline within 2 weeks | **Hype Bubble** | React with short videos, never invest course time |
   | Spike then settle to a lower baseline (not zero) | **Spike-then-Settle** | Single video, not a full course |
   | Peaked months ago, declining, no recovery | **Declining/Dead** | Harvest existing content, don't create new |

5. **Key Google Trends URL patterns:**
   - Web search, 12 months: `https://trends.google.com/trends/explore?date=today%2012-m&q={term1},{term2}&hl=en`
   - YouTube search, 12 months: `https://trends.google.com/trends/explore?date=today%2012-m&gprop=youtube&q={term1},{term2}&hl=en`
   - 90-day daily granularity: `https://trends.google.com/trends/explore?date=today%203-m&q={term1},{term2}&hl=en`

### Phase 3: YouTube Studio Analytics -- Own-Channel Data

**Tool:** User-provided data (screenshots, CSV exports, or pasted summaries)

**What to request from the channel owner:**

1. **Traffic source summary** (last 28 days):
   - Path: YouTube Studio -> Content -> select "All videos" -> Traffic sources
   - Need: impressions, CTR, views, avg duration per source (browse, search, suggested, direct, channel pages, external)

2. **Top videos by views** (last 28 days):
   - Path: YouTube Studio -> Content -> sort by views
   - Need: video title, views, avg view duration, retention %, video length
   - Important: distinguish 28-day views from lifetime totals

3. **YouTube search terms CSV export:**
   - Path: YouTube Studio -> Analytics -> Content -> Traffic source: YouTube search -> "See More" -> Export (top-right)
   - This gives 500 search terms with views, avg duration, watch time
   - **This is the most actionable data in the entire analysis**

4. **Optional but valuable:**
   - Retention curves for long-form courses (where people drop off)
   - Per-video traffic source breakdown
   - Revenue data per video (if monetized)

**How to analyze the search terms CSV:**

1. **Cluster by topic** -- group all variants of each topic together:
   - e.g., "n8n full course" + "n8n tutorial" + "n8n" + "n8n automation" = n8n cluster
   - Sum views within each cluster
   - Calculate % of total search views

2. **Identify gaps** -- compare clusters against Google Trends demand:
   - High Trends demand + low Studio capture = opportunity (make content)
   - High Trends demand + high Studio capture = protect (don't cannibalize)
   - Low Trends demand + high Studio capture = brand asset (maintain)
   - Low Trends demand + low Studio capture = ignore

3. **Watch-time analysis** -- rank videos by estimated watch-minutes, not raw views:
   - Watch-minutes = views x avg view duration
   - Long-form courses often generate more watch-time than viral shorts despite fewer views
   - YouTube optimizes for watch time, so this reveals true algorithmic value

### Phase 4: Synthesis & Scoring

**Combine all three data sources into a 4-dimension scoring framework:**

For each candidate course/topic:

| Factor | Score | How to assess |
|--------|-------|--------------|
| **Search Demand** | 1-5 | Google Trends volume + trajectory + YouTube Search volume + Studio search capture |
| **Algorithmic Amplification** | 1-5 | Browse features performance, view/sub ratios across creators, evidence of algorithmic push |
| **Fit** | 1-5 | Channel's existing audience, brand alignment, creator expertise |
| **ROI** | 1-5 | Competitive gap (does a definitive course exist?), monetization potential, production effort vs expected return |

**Total = Search Demand + Algorithmic Amplification + Fit + ROI (max 20)**

Tier the recommendations:
- **Tier 1 (16-20):** Highest-impact, do these first
- **Tier 2 (13-15):** Strong ROI, do after Tier 1
- **Tier 3 (9-12):** Strategic / opportunistic
- **Tier 4 (5-8):** Low priority, only if resources permit

**Per-course evidence tables:** Each scored recommendation MUST include a Factor | Evidence table with specific data points, not just a score. Example format:

```
#### 1. Course Name
**Score: 18/20** (Search: 4 | Algorithm: 5 | Fit: 5 | ROI: 4)

| Factor | Evidence |
|--------|---------|
| **Search Demand (4)** | Specific data: Trends number, Studio search views, growth trajectory. |
| **Algorithmic Amplification (5)** | Browse %, view/sub ratios, daily views impact evidence. |
| **Fit (5)** | Brand alignment evidence, existing content performance. |
| **ROI (4)** | Competitive gap, expected views based on course performance model, risks. |
```

### Phase 5: Report Assembly

**Title format:** "YouTube Strategy Report — Month DD, YYYY" (no "Prepared for" line).

**Tone:** Analytical, narrative-driven, consultant perspective. It's fine to hedge when the data is ambiguous — say "likely declining" or "appears to be plateauing" when that's the honest read. Write as a YouTube consultant delivering analysis, not a data analyst dumping tables. Stats should be woven into prose to support arguments, not front-loaded.

**Table discipline:** Use tables sparingly — only where structured comparison is genuinely clearer than prose (gap analysis, scoring breakdowns). Massive raw-data tables belong in appendices or raw data files, not the strategy doc.

Write the final report with these sections:

1. **The Big Picture** -- 2-3 sentences framing the channel's current competitive position and what to do with it. Set the strategic context.

2. **What's Working Right Now** -- Narrative analysis of the channel's strongest assets and why they're working. Weave in specific numbers (views, watch-time, revenue, subs) as evidence within prose. Cover: top-performing content, algorithmic tailwinds, format advantages, structural moats.

3. **Competitive Landscape** -- Place this EARLY (not buried at the end). Brief summary table (subs, growth/wk, threat level) then 1-2 paragraph deep-dives per significant competitor. Focus on: what they're doing, what the risk is, how to defend. Include view/sub ratios where relevant to show algorithmic push.

4. **The Search Pipeline: Where the Gaps Are** -- Gap analysis table cross-referencing Google Trends demand vs Studio capture (Term | Trends Demand | Your Capture | Signal). This is the most actionable table in the report. Follow with narrative interpretation of the most important gaps and crossovers.

5. **Trend Classification** -- Categorize topics into Platform Trends, Stable High-Volume, Spike-then-Settle, Declining, No Urgency. Brief prose per category — what it means for production decisions.

6. **Course Recommendations** -- Scored recommendations with 4-dimension scores. Each gets a Factor | Evidence table (see Phase 4). Include: realistic expectations (search views vs algorithmic views), format, title, sequencing rationale. Be honest about modest search pipelines vs algorithmic upside.

7. **Sequencing** -- "This week" + phased timeline. Concise, with reasoning for ordering.

8. **Key Strategic Insights** -- 6-10 numbered insights that synthesize multiple data sources. Each should reveal something only visible through cross-referencing. Be opinionated and actionable.

### Phase 6: Google Doc Creation

After saving the markdown report, create a Google Doc:

```bash
python3 .claude/skills/youtube-channel-analysis/md_to_gdoc.py "active/youtube-strategy/reports/YYYY-MM-DD_report-slug.md"
```

Uses `gws` CLI under the hood — no Python Google API dependencies needed. Creates a formatted Google Doc under your-email@example.com with Inter font, headings, bold/italic, bullets, numbered lists, native tables with bold headers, and paragraph spacing. No horizontal rule dividers.

To update an existing doc instead of creating new:
```bash
python3 .claude/skills/youtube-channel-analysis/md_to_gdoc.py "report.md" --update DOC_ID
```

## Edge Cases & Lessons Learned

- **Subscriber counts from LLMs are unreliable.** Always verify by browsing the channel directly. Reports have been wrong by 2-5x.
- **28-day Studio views != lifetime views.** Always clarify which is being used. A course with 60K 28-day views might have 140K lifetime.
- **"Agentic workflows" trap:** Terms you invent can perform well via algorithm/audience but have zero search volume. Always check Google Trends before assuming a term has organic search demand.
- **Hype bubble timing:** A course takes 2-4 weeks to produce. A hype bubble peaks in 1-2 weeks. By the time a course is done, the bubble has popped. React to bubbles with short videos; build courses for platform trends.
- **YouTube Search != Web Search on Google Trends.** Some terms are huge on web but tiny on YouTube (e.g., voice AI agent: 2 on web, 69 on YouTube). Always check both.
- **Watch-time > views for algorithmic value.** A 6-hour course with 60K views can generate more watch-time than a viral short with 164K views. YouTube's algorithm rewards the course.
- **The "24 views" pattern:** When Google Trends shows high demand for a term but your Studio shows near-zero capture, you've found an untapped search pipeline. This is the highest-signal gap in the entire analysis.

## Files

- `.claude/skills/youtube-channel-analysis/md_to_gdoc.py` -- Markdown-to-Google-Doc converter via `gws` CLI (reusable across all skills)
- `active/youtube-strategy/reports/` -- Finished analysis reports (markdown + auto-generated Google Docs)
- `active/youtube-strategy/research/` -- Working files, raw data, diagrams
- `active/youtube-strategy/stats/` -- YouTube Studio CSV exports

## Versioning

Reports are dated (`YYYY-MM-DD_slug.md`), not versioned (v1, v2). Each analysis round produces a new dated report. Previous reports stay for historical comparison.
