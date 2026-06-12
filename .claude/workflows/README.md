# Dynamic Workflows

Reusable orchestration scripts triggered by the `ultracode:` keyword. Each `.md` file in this directory documents one workflow that Claude can write a JavaScript orchestration script for.

## When to use

Use a Dynamic Workflow when ALL of these are true:
- The job fans out to >5 parallel sub-agents (e.g. enriching 200 leads, scraping 50 sites, multi-source research).
- Each sub-task is independent (no cross-talk needed).
- Total runtime > 5 minutes (workflows run in the background so the main session stays responsive).
- The output is structured (CSV row, JSON object, Sheet row, etc.).

Use a single sub-agent (`Agent(...)`) instead when:
- Fewer than 5 parallel sub-tasks.
- The job needs the orchestrator's context (e.g. tight back-and-forth).
- Total runtime < 5 minutes.

Use Agent Teams when:
- The job needs persistent peer-to-peer coordination (teammates messaging each other, claiming tasks from a shared list).
- Multiple long-running sessions, each with their own context.
- Useful for multi-hypothesis research, parallel module development, "two teams competing on the same problem."

**Autoresearch loop (4th tier)**: when the work is propose → deploy → measure → mutate against an objective metric, see `.claude/workflows/autoresearch.md`. Distinct from anneal (which is propose → audit → fix → re-audit against a static checklist) — autoresearch optimizes a live business metric, anneal optimizes code quality.

## How to trigger

Prefix any prompt with `ultracode:` — Claude writes the orchestration script, runs it in the background, you see progress events, and the result is saved.

Examples:
- `ultracode: enrich every lead in leads.csv with Apollo + Exa, dedupe, write to Sheet "Enriched Leads"`
- `ultracode: scrape the top 20 results for "AI accounting software 2026" and produce a competitive matrix`

Or set the session default: `/effort ultracode`.

## How to save a workflow

After a successful `ultracode:` run, save it as a reusable `/command`:
- Save the script + prompt template as a new `.md` file in this directory.
- Use the format: name, description, input schema, prompt template. See `_template.md`.

## Reference

- Official docs: https://code.claude.com/docs/en/workflows
- Bundled command: `/deep-research` (fan-out web search with adversarial voting on claims).
- Concurrency cap: 16 simultaneous, 1000 total per run.
- Resumable within the session.
