# General Notes

Cross-cutting learnings that apply across the whole workspace.
Format: `- [tag] Subject: Detail.`
Tags: [preference] [technical] [learned] [pattern] [constraint]

---

- [technical] reportlab on Windows: Must use `TTFont` to register Arial for Unicode support before using it in any style — `pdfmetrics.registerFont(TTFont('Arial', 'Arial.ttf'))`. Plain string font names fail silently.
- [technical] reportlab table widths: Always specify explicit `colWidths` — auto-sizing breaks on Windows due to DPI differences vs. macOS.
- [learned] cv_optimizer_agent: Output validation is critical — Gemini (and Anthropic) APIs return `None` on edge-case inputs. Guard every `response.content` access before indexing.
- [learned] cv_optimizer_agent: PDF text extraction via `pdfplumber` sometimes returns empty strings for scanned PDFs. Add a fallback prompt asking user to paste text.
- [constraint] Windows paths: Hook scripts receive paths with both `/` and `\\`. Always check for both separators — use `[[ "$PATH" == *"dir/"* ]] || [[ "$PATH" == *"dir\\"* ]]`.
- [constraint] Python on Windows: Use `py` command (not `python3`) to invoke Python 3.14 via the Windows Python Launcher. `python3` may not be on PATH.
- [pattern] Registry format: Each execution script must have a module-level docstring with `description:`, `inputs:`, and `outputs:` fields for `generate_registry.py` to pick them up correctly.
- [preference] Terse output: Skip trailing summaries after completing tasks. User reads the diff. Lead with the result.
- [technical] .env loading: Use `python-dotenv` with `load_dotenv()` at top of every script. Never hardcode keys.
- [learned] MCP servers: Keys must be in .env and referenced as env vars in .mcp.json using `${VAR_NAME}` syntax. Never commit API keys to .mcp.json directly.
- [pattern] Sub-agent delegation: Heavy file reads and code exploration go to sub-agents to protect main context. Main context handles decisions and routing only.
- [pattern] Shareable automations: build as an isolated fork driven by a validated profile file plus a per-user GitHub Actions workflow; the operator pays nothing at runtime and the personal cron is untouched (see job_digest).
- [preference] Autonomy (2026-09-06): the operator does not run commands or gates by hand — Claude runs them (tests, packagers, dispatches, live probes) and only asks when every available option is exhausted. "Commit to memory" = write it to .claude/notes.
- [learned] gaia_sourcing (2026-09-10): a hard-gate floor with no ceiling is a bug the client finds first — every delivered Role 1 card was Director grade. Every brief-level filter now needs both bounds and a delivery composition guard that refuses a list whose titles/locations break the brief.
- [process] Client feedback authority: check the recorded feedback in commit messages (e.g. a626381 "too senior, some not in Ireland") before "correcting" it from a call transcript — a Fathom transcript mis-transcribed a name (Steph for Maddie), and "over 60" in a client's words was a match score, not an age. 2026-09-11.
- [pattern] Offline --check on cached persons is the zero-spend demo path for expensive pipelines; assert spend is 0.00 before and after the run to confirm no live calls fired. 2026-09-11.
