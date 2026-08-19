---
name: multi-agent-chrome
description: Orchestrate parallel browser automation using multiple Chrome DevTools MCP instances. Use when a task requires doing the same browser action across many targets simultaneously (e.g., submitting contact forms, filling applications, scraping pages that need JS rendering). Spin up 1-5 parallel Chrome agents.
allowed-tools: Read, Write, Edit, Bash, Grep, Glob
---
> **Demo Library Skill** — This skill is from a demo library. Some configuration values use placeholders (e.g. `{{USER_NAME}}`, `{{COMMUNITY_ID}}`). If something doesn't work, check for placeholder values and replace them with your own information first.

# Multi-Agent Chrome Orchestrator

Spin up 1-5 parallel Claude Code agents, each with its own Chrome browser, to do browser tasks concurrently.

## When to Use

- Submitting contact forms across a list of websites
- Filling out applications on multiple platforms
- Scraping JS-rendered pages that need real browser interaction
- Any repetitive browser task where doing it sequentially is too slow

## Architecture

```
Business workspace (orchestrator)
├── .claude/skills/multi-agent-chrome/
│   ├── launch_chrome.sh           # Spawns Chrome instances on ports 9223-9227
│   ├── kill_chrome.sh             # Tears down all Chrome instances
├── active/multi-chrome-agent/
│   ├── chat.md                    # Shared coordination file
│   ├── chrome-agent-1/            # Workspace for Agent 1
│   │   ├── .mcp.json              # Chrome DevTools on port 9223
│   │   └── CLAUDE.md              # Agent behavior instructions
│   ├── chrome-agent-2/            # Port 9224
│   ├── chrome-agent-3/            # Port 9225
│   ├── chrome-agent-4/            # Port 9226
│   └── chrome-agent-5/            # Port 9227
```

## Step-by-Step Orchestration

### 1. Determine how many agents are needed

Look at the task. If there are 10 contact forms to fill, 3-5 agents is good. If there are 3, use 2-3. Don't over-provision.

### 2. Launch Chrome instances

```bash
bash .claude/skills/multi-agent-chrome/launch_chrome.sh [COUNT]
```

This spawns `COUNT` Chrome instances on ports 9223+. Wait for the "READY" confirmation for each.

### 3. Reset the chat file

Clear the chat file and write task assignments:

```markdown
# Multi-Chrome Agent Chat

## Orchestrator
[2026-03-05 14:30] Launching 3 agents for contact form submission.

### Agent 1 Tasks
1. Go to https://example1.com/contact -> fill name: "Debanjan Mazumdar", email: "your-email@example.com", message: "Hi, I'm interested in..."
2. Go to https://example2.com/contact -> same form fill

### Agent 2 Tasks
1. Go to https://example3.com/contact -> fill form
2. Go to https://example4.com/contact -> fill form

### Agent 3 Tasks
1. Go to https://example5.com/contact -> fill form
2. Go to https://example6.com/contact -> fill form

## Agent 1

## Agent 2

## Agent 3
```

### 4. Spawn Claude Code agents

For each agent, open a new terminal and run:

```bash
cd /path/to/your/workspace/active/multi-chrome-agent/chrome-agent-N && claude
```

Where N is 1-5. Each agent will:
- Pick up its CLAUDE.md (browser worker instructions)
- Connect to its Chrome instance via its local .mcp.json
- Read chat.md for its task assignments
- Execute tasks and report status back to chat.md

**Programmatic launch via osascript:** Claude Code blocks nested sessions via the `CLAUDECODE` env var. To launch agents programmatically from within an existing session, use `osascript` with `env -u` to strip the blocking env vars:

```bash
for i in 1 2 3 4 5; do
    osascript -e "tell application \"Terminal\" to do script \"cd /path/to/your/workspace/active/multi-chrome-agent/chrome-agent-$i && env -u CLAUDECODE -u CLAUDE_CODE_ENTRYPOINT -u CLAUDE_AGENT_SDK_VERSION -u CLAUDE_CODE_ENABLE_SDK_FILE_CHECKPOINTING -u CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS claude --dangerously-skip-permissions -p 'You are Agent $i. Read /path/to/your/workspace/active/multi-chrome-agent/chat.md, find your tasks under Agent $i, and execute them. Use Chrome DevTools MCP to browse websites, search listings, and collect data. Write your findings as a markdown table back to chat.md under the Agent $i section. Mark yourself as [WORKING] while active and [DONE] when finished.'\""
    sleep 2
done
```

This opens separate Terminal.app windows, each running an independent Claude Code session with its own Chrome DevTools MCP.

**Manual fallback:** If osascript doesn't work, tell the user to open N terminal tabs:

```
Tab 1: cd ~/your-workspace/active/multi-chrome-agent/chrome-agent-1 && claude
Tab 2: cd ~/your-workspace/active/multi-chrome-agent/chrome-agent-2 && claude
...
```

### 5. Monitor progress

Read the chat file periodically to check agent status:

```bash
cat /path/to/your/workspace/active/multi-chrome-agent/chat.md
```

Look for `[DONE]`, `[ERROR]`, or `[WORKING]` tags from each agent.

### 6. Tear down

When all agents report `[DONE]`:

```bash
bash .claude/skills/multi-agent-chrome/kill_chrome.sh
```

## Chat Protocol

Agents communicate via the shared chat.md file:

| Tag | Meaning |
|-----|---------|
| `[WORKING]` | Agent is actively processing a task |
| `[DONE]` | Agent completed all assigned tasks |
| `[ERROR]` | Agent hit a blocker (CAPTCHA, timeout, etc.) |
| `[WAITING]` | Agent is idle, waiting for new tasks |

## Port Map

| Agent | Chrome Port | Workspace |
|-------|------------|-----------|
| 1 | 9223 | chrome-agent-1/ |
| 2 | 9224 | chrome-agent-2/ |
| 3 | 9225 | chrome-agent-3/ |
| 4 | 9226 | chrome-agent-4/ |
| 5 | 9227 | chrome-agent-5/ |

Port 9222 is reserved for the main (non-parallel) Chrome DevTools MCP.

## Edge Cases

- **CAPTCHA:** Agent reports `[ERROR] CAPTCHA on https://...` in chat. Orchestrator can reassign or skip.
- **Rate limiting:** If a site blocks after N requests, spread URLs across more agents so each hits the site fewer times.
- **Login required:** Pre-authenticate in each Chrome instance before assigning tasks, or include login steps in the task list.
- **Long-running tasks:** Agents check chat.md every 30s. If the orchestrator needs to abort, write `[ABORT]` in the Orchestrator section.
