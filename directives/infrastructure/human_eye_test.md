# Human-eye test (release gate)

**Goal.** No product change reaches a client without every automated tier green AND a reviewer having looked at a screenshot of every page, state, viewport and theme, AND a functional walk, AND the panel. Skill: `.claude/skills/human-eye-test/SKILL.md`.

**Inputs.** Built product served locally; shot plan JSON (`tests/<product>/human_eye_plan.json`); change list.
**Tools.** `execution/infrastructure/human_eye_shots.cjs` (screenshot matrix + DOM health index), the product's `run_all.py`, `layout.test.mjs`, panel roster.
**Outputs.** `.tmp/human_eye/<run>/` PNGs + `index.json`; `<product>/research/qa_<date>/human_eye_verdict.md`.
**Edge cases.** Chromium behind the proxy cannot open the public host (TLS): always test the identical local build. Playwright lives at `/opt/node22/lib/node_modules` in cloud sessions (`NODE_PATH`). The harness exits 1 on any console error, failed request, overflow, clipped control or h1 count ≠ 1: treat as a defect list, not noise. Reviewer agents must be given ≤ 40 images each or they skim.
**History.** 2026-09-29: created after the owner found four layout defects a 99%-coverage build had missed; first run on the GreenJobs employers-page changes (Premium-only table, full-JD preview).
