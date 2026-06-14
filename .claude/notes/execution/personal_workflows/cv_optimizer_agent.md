# Notes: execution/personal_workflows/cv_optimizer_agent.py

- [pattern] Canonical repo: the **public Streamlit + Gemini version** at `github.com/dmazumdar186/cv-optimizer-agent` is the canonical product. The workspace copy (`execution/personal_workflows/cv_optimizer_agent.py`) is a **legacy/reference CLI** kept for local use. Do not treat the two as in-sync — they diverged when the project pivoted from CLI→Streamlit.
- [constraint] Workspace copy uses `reportlab` + `pdfplumber` + Anthropic direct (no Gemini path). Public repo uses Streamlit UI + Gemini free tier as the primary LLM. If updating LLM logic, update the public repo; if updating PDF layout, the workspace copy is the right place.
- [technical] Model is now selected via `--mode {cheap,balanced,premium}` flag (added 2026-06-12). cheap → `claude-sonnet-4-6`; balanced/premium → `claude-opus-4-7`. Default: balanced.
- [technical] LLM-derived output paths (`cv_opt_{company}_{lastname}.pdf`, `cover_letter_{company}_{lastname}.pdf`) are boundary-checked via `resolve().is_relative_to(TMP.resolve())` before any write. Added 2026-06-12 per hardening rule 3.
- [learned] `_slugify()` strips Windows-illegal chars and limits to 80 chars — safe for filenames. The boundary check is an extra guard for path-traversal via unexpected LLM-supplied names (e.g. `../../` after slug normalization).
- [constraint] `run_analysis()` uses `max_tokens=16000` — large structured tool output. On cheap/Sonnet tier, response quality may be lower for complex CVs. Prefer balanced/premium for production use.
