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
