# Workspace Activity Log (append-only)

Chronological one-line entries appended after every directive/execution edit by the
`note-taker` sub-agent (defined at `.claude/agents/note-taker.md`). Newer entries at
the bottom. Never edit historical entries — they're a frozen record of what was
known at that point in time.

Format:
`## [YYYY-MM-DD HH:MM] {tag} {subject}`

Tags (single, lowercase): `learned`, `pattern`, `constraint`, `preference`, `technical`, `incident`.

The companion `.claude/notes/general.md` (and topic files under `.claude/notes/`)
hold the durable distilled knowledge. `log.md` is the raw chronological feed.

---

## [2026-06-11 00:00] pattern Workspace upgrade Phase 4 seeded the log file (Karpathy llm-wiki append-only pattern). Future entries appended by note-taker sub-agent.
