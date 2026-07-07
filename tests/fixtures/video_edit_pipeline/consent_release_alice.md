# Likeness release (test fixture — NOT a real release)

**This file exists solely as a test fixture** for `tests/acceptance_video_edit_pipeline.py`.
It is NOT a real legal release. Do NOT use as a template — the real template ships in
Phase 4 at `directives/gtm_client_workflows/likeness_release_template.md`.

Subject: Alice Test-Fixture
Date: 2026-07-07
Purpose: exercise the consent-verified file-existence + hash-log gate.

The pipeline's consent gate is presence-only; it does not parse this content. That
is by design (operator attests fitness at invocation time). The gate logs SHA + mtime
so post-hoc audit can catch stale-release reuse.
