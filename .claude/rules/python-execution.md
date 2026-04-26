---
paths:
  - "execution/**/*.py"
---

# Python Execution Script Rules

- Every script must have a module-level docstring with these exact fields:
  ```
  description: One-line description
  inputs: CLI args, env vars, or interactive prompts
  outputs: Files written, API calls made, or stdout produced
  ```
- Load environment variables at the top: `from dotenv import load_dotenv; load_dotenv()`
- Never hardcode API keys, paths, or credentials — always read from `.env`
- Use `argparse` for CLI arguments; use `input()` only for interactive scripts
- Wrap all API calls in try/except and print meaningful error messages
- Validate all outputs before writing to disk — never write `None` to a PDF
- Use `pathlib.Path` for file paths, not raw strings
- Place intermediate files in `.tmp/` — never commit them
- Run `python execution/generate_registry.py` after adding or modifying any script
- Default Python invocation on Windows: `py execution/{category}/{script}.py`
