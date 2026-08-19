---
name: stochastic-multi-agent-consensus
description: >
  Spawn N agents with the same prompt (slight framing variations) to independently analyze a problem, then aggregate results by consensus. Use for decision-making, ranking options, strategic analysis, or any problem where you want to filter hallucinations and surface high-variance ideas. Triggers on "consensus", "poll agents", "stochastic consensus", "spawn N agents to analyze", "multi-agent vote", or /stochastic-multi-agent-consensus. Also triggers on phrases like "what do 10 agents think", "get multiple opinions", or "poll on [topic]".
allowed-tools: Read, Grep, Glob, Bash, Task, Write, Edit
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Stochastic Multi-Agent Consensus

Spawn N agents (default 10) with identical context and near-identical prompts. Each independently analyzes and produces a structured response. Aggregate by finding consensus (mode), divergences (splits), and outliers (unique ideas).

**Why this works:** Exploits stochastic variation in LLM outputs. Like polling 10 experts instead of asking one. The mode filters out hallucinations and individual biases. Divergences reveal genuine judgment calls. Outliers surface creative ideas a single run would miss.

## Execution

### 1. Parse the request

Extract from the user's message:
- **Problem/question** to analyze
- **Agent count N** — default 10. User can override ("spawn 5 agents", "poll 20 agents")
- **Output format** — what each agent should produce (rankings, recommendations, yes/no decisions, scores, etc.)
- **Options list** (if applicable) — predefined options to rank/evaluate, or let agents generate their own

If the problem is vague, ask the user to sharpen it. N agents on a fuzzy prompt wastes tokens.

### 2. Design the structured output schema

Before spawning, define what each agent must return. This MUST be structured enough to aggregate. Examples:

- **Ranking task**: "Rank these 5 options from best to worst. Output as a numbered list 1-5."
- **Open recommendation**: "Propose your top 3 recommendations. For each: name, one-sentence rationale, confidence score 1-10."
- **Binary decision**: "Should we do X? Answer YES or NO, then give your top 3 reasons."
- **Scoring task**: "Score each option 1-10 on [criteria]. Output as `Option: Score`."

The schema must produce outputs that can be mechanically compared across agents.

### 3. Generate framing variations

Create N slightly different prompts. The core problem and output schema stay identical — only the framing/priming varies. This ensures stochastic diversity without changing the actual task.

Variation strategies (cycle through these):
1. **Neutral baseline**: "Analyze the following problem objectively."
2. **Risk-averse**: "You are a conservative analyst who weighs downside risks heavily."
3. **Growth-oriented**: "You are an aggressive strategist who optimizes for upside potential."
4. **Contrarian**: "Challenge conventional wisdom. What does everyone else get wrong here?"
5. **First-principles**: "Reason from first principles. Ignore what's conventional or popular."
6. **User-empathy**: "Think from the end-user/customer perspective. What matters most to them?"
7. **Resource-constrained**: "Assume limited time and budget. What's the highest-leverage move?"
8. **Long-term**: "Optimize for the 5-year outcome, not the 90-day outcome."
9. **Data-driven**: "Focus only on what's measurable and provable. Ignore intuition."
10. **Systems thinker**: "Map the second and third-order effects. What cascades from each choice?"

For N > 10, cycle back through. For N < 10, pick the first N.

### 4. Spawn all N agents in parallel

Use the Task tool to spawn all N agents simultaneously.

Config for each:
- `subagent_type: "general-purpose"`
- `model: "sonnet"` (cost-efficient — each agent does focused analysis, not deep research)
- `mode: "bypassPermissions"`

#### Agent prompt template

```
{framing_variation}

PROBLEM:
{problem}

{context — any relevant background, data, constraints the user provided}

{output_schema}

Be specific and concrete. Give real recommendations, not vague advice. If you're uncertain about something, say so explicitly with a confidence level.

Write your response directly — do not write to any files.
```

**Important**: Agents return their output directly (not to files). This keeps aggregation simple.

### 5. Aggregate results

Once all N agents have returned, perform mechanical aggregation:

#### For ranking tasks:
- Assign points: 1st place = N points, 2nd = N-1, etc.
- Sum points across all agents for each option
- Report final ranking by total points

#### For recommendation tasks:
- Group similar recommendations (fuzzy match on name/concept)
- Count how many agents proposed each recommendation
- Categorize:
  - **Consensus** (7+/N agree): High-confidence recommendations
  - **Divergence** (4-6/N): Genuine judgment calls — flag for user decision
  - **Outlier** (1-3/N): High-variance ideas — potentially creative, potentially noise

#### For scoring tasks:
- Calculate mean, median, and standard deviation per option
- Flag options with high variance (std dev > 2) — agents disagree here

#### For binary decisions:
- Count YES vs NO
- Report the split and summarize the strongest arguments from each side

### 6. Write the aggregation report

Write to `active/consensus/consensus_report.md`:

```markdown
# Stochastic Multi-Agent Consensus Report

**Problem**: {problem}
**Agents**: {N}
**Date**: {date}

## Consensus (agreed by {X}+/{N} agents)
{Items most agents converged on — these are your safe bets}

## Divergences (split {X}/{Y})
{Items where agents disagreed roughly evenly — these are genuine judgment calls that need human decision}

## Outliers (proposed by 1-{Z} agents)
{Unique ideas from individual agents — high variance, potentially high value. Flag which framing produced them.}

## Raw Rankings / Scores
{Full aggregation table}

## Individual Agent Responses
{Summary of each agent's response with their framing variation noted}
```

### 7. Deliver results

Present to the user:
- **One-paragraph summary** of the consensus finding
- **Top 3 consensus items** (what most agents agreed on)
- **Top divergence** (the most interesting split — where human judgment is needed)
- **Most interesting outlier** (the creative idea worth considering)
- File path to full report

## Configuration

| Parameter | Default | Description |
|-----------|---------|-------------|
| N | 10 | Number of agents to spawn |
| model | sonnet | Model for each agent (sonnet for cost, opus for depth) |
| output | ranking | Output type: ranking, recommendation, score, binary |

User can override any of these: "poll 5 opus agents on..." or "score these options with 15 agents".

## Cost considerations

- 10 sonnet agents is cheap (~$0.30-0.50 total for a focused analysis)
- 10 opus agents is expensive (~$3-5 total) — only use when the user explicitly requests opus or the problem requires deep reasoning
- Default to sonnet unless told otherwise
- For binary yes/no decisions, 5 agents is usually sufficient

## Edge cases

- **N < 3**: Warn the user that consensus requires at least 3 agents. Minimum 3.
- **Ambiguous problem**: Ask user to clarify before spawning. Don't burn N * tokens on vagueness.
- **All agents agree**: Great — high confidence. Report consensus and note the unanimity.
- **No consensus (even split)**: Report the split honestly. This IS the finding — the problem genuinely has no dominant answer. Surface the strongest arguments from each side.
- **Existing report**: Check `active/consensus/` for existing files. Overwrite without asking (these are ephemeral analysis artifacts, not persistent data).
- **Agent failure**: If an agent returns garbage or fails, exclude it from aggregation and note the effective N.

## Output files

| File | Description |
|------|-------------|
| `active/consensus/consensus_report.md` | Full aggregation report |

Previous reports are overwritten — these are ephemeral analysis tools, not archives.
