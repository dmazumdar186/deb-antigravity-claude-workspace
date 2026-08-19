---
name: x-search
description: Search X/Twitter for cutting-edge discussions, trends, and techniques using Grok API. Use when researching what people are talking about on X, finding trending AI techniques, discovering novel strategies, or monitoring real-time discourse on any topic.
allowed-tools: Read, Grep, Glob, Bash, Write
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# X Search — Grok-Powered Twitter Research

Research topics on X (Twitter) via xAI's Grok API. Two modes with different cost/depth tradeoffs.

## When to Use

- User wants to know what people are discussing on X/Twitter about a topic
- Researching cutting-edge techniques, strategies, or trends
- Finding specific tweets, threads, or accounts discussing a topic
- Monitoring discourse around a product, tool, or concept
- Gathering social proof or community sentiment

## Modes

### Broad Mode (~$0.01/query)
Uses Grok chat completions. Grok synthesizes from its knowledge of X — cites accounts, paraphrases posts. Fast, cheap, good for topic discovery and getting an overview.

```bash
.venv/bin/python .claude/skills/x-search/x_search_research.py broad -q "What are people on X saying about AI agent prompting strategies?"
```

### Deep Mode (~$0.02-0.05/query)
Uses Grok Responses API with `x_search` tool. Returns actual tweets with citation URLs. Supports date filtering and handle filtering. Use when you need real tweets and links.

```bash
.venv/bin/python .claude/skills/x-search/x_search_research.py deep -q "AI agent prompting strategies" --from-date 2026-02-01
```

### Options

| Flag | Description |
|------|-------------|
| `-q` / `--query` | Single query string |
| `-f` / `--queries-file` | JSON file with list of queries (for batch) |
| `-o` / `--output` | Output file path (JSON) |
| `--from-date` | Start date filter `YYYY-MM-DD` (deep only) |
| `--to-date` | End date filter `YYYY-MM-DD` (deep only) |
| `--handles` | Filter to specific X handles (deep only, max 10) |

## Batch Queries

For multiple queries, create a JSON file with a list of strings and use `-f`:

```bash
echo '["query 1", "query 2", "query 3"]' > /tmp/queries.json
.venv/bin/python .claude/skills/x-search/x_search_research.py broad -f /tmp/queries.json -o active/research/x_results.json
```

Broad mode: 1s delay between queries. Deep mode: 2s delay.

## Workflow

### Quick Topic Scan
1. Run broad mode to understand the landscape
2. Identify promising threads/accounts
3. Run deep mode with date filtering or handle filtering to get actual tweets

### Comprehensive Research
1. Run broad mode with 3-5 angle queries
2. Extract mentioned accounts from broad results
3. Run deep mode filtered to those accounts for actual tweets
4. Compile findings into a research doc

## Examples

```bash
# What's trending in AI agents right now
.venv/bin/python .claude/skills/x-search/x_search_research.py broad -q "What are the most discussed AI agent techniques on X in the last week? Include specific accounts and posts."

# Find actual tweets about a technique
.venv/bin/python .claude/skills/x-search/x_search_research.py deep -q "multi-agent consensus OR stochastic agents" --from-date 2026-02-01

# Monitor specific accounts
.venv/bin/python .claude/skills/x-search/x_search_research.py deep -q "AI agents" --handles IndyDevDan mcaborsh yanndine --from-date 2026-03-01

# Batch research with output
.venv/bin/python .claude/skills/x-search/x_search_research.py deep -f queries.json -o active/research/x_deep_results.json --from-date 2026-02-15
```

## Environment

Requires `XAI_API_KEY` in `.env` (xAI API key for Grok access).

## Output

- Broad: Plain text synthesis with account mentions
- Deep: Text + citation URLs + cost breakdown
- Batch: JSON file with all results

All outputs go to `active/` directory when saving files.

## Cost

| Mode | Per Query | Batch of 10 |
|------|-----------|-------------|
| Broad | ~$0.01 | ~$0.10 |
| Deep | ~$0.02-0.05 | ~$0.20-0.50 |
