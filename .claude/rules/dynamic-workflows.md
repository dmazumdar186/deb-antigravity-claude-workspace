---
paths:
  - ".claude/workflows/**"
---

# Dynamic Workflows — Authoring Rules

Loaded automatically when editing any file under `.claude/workflows/`.

## Mandatory frontmatter keys

Every workflow `.md` must declare:
- `name`: kebab-case slug.
- `description`: one-line summary (input → output).
- `inputs`: list of `<name>: <type> — <description>`.
- `outputs`: same shape.

See `.claude/workflows/_template.md` for the canonical structure.

## When to write a workflow

Workflows are reusable orchestration recipes. Write one when:
- The job repeats across multiple inputs (e.g. enrich each row, scrape each URL).
- The fan-out exceeds 5 parallel sub-tasks.
- The orchestration is non-trivial (sequence, dedupe, merge).

Don't write a workflow for one-shot tasks — a regular sub-agent or `execution/` script is cheaper.

## Cost guards

- Default worker model: `claude-haiku-4-5` (orchestration, not deep reasoning).
- Set a `cost_cap` field if the workflow can plausibly spend > $1 per run.
- Always include a `--dry-run` mode in the underlying execution scripts (returns `would_*` counts).
- For any paid-API workflow on Accessory Masters credentials: STOP. AM is locked (`CLAUDE.local.md`).

## Concurrency safety

- Max 16 concurrent workers (Anthropic-imposed cap).
- If workers share a filesystem output dir, use the Python threading-locks pattern from `.claude/rules/python-hardening.md`.
- If workers write to the same Google Sheet, batch the appends — don't append per-worker.

## Saving as a reusable `/command`

After a successful `ultracode:` run, prompt: "save this as a reusable workflow?"
Persist the prompt template + script signature to `.claude/workflows/<slug>.md` so future invocations of `/<slug>` are deterministic.

## Reference

- Official docs: https://code.claude.com/docs/en/workflows
- Bundled example: `/deep-research`
