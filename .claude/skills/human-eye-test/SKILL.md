---
name: human-eye-test
description: Release gate that ends with eyes on pixels. Runs every automated tier, then screenshots every page/state/viewport/theme, has reviewer agents READ each image against a defect checklist, walks the product as a user, runs the panel, and writes a verdict with evidence. Triggers on "human eye test", "release gate", "are we sure it works", /human-eye-test.
allowed-tools: Read, Grep, Glob, Bash, Edit, Write, Agent
user_invocable: true
---

# Human-eye test — the release gate

Born 2026-09-29 after a 99%-coverage build shipped four layout defects a client saw in
ten minutes. Code coverage measures lines, not what a person sees. Nothing is "done"
until a screenshot of every state has been looked at and the verdict file exists.

## Inputs
- A built, served product (static site, app, dashboard). For GreenJobs: build with
  `build_site.py`, serve with `python3 -m http.server <port> --directory <site>`.
- A shot plan JSON (see `execution/infrastructure/human_eye_shots.cjs` header). Keep one per
  product under `tests/<product>/human_eye_plan.json`; add a page/state the moment it is built.
- The change list under test (commit range or feature names).

## Tiers, in order. A failure in any tier stops the run; no verdict without all seven.
1. **Automated.** Unit, integration, contract, SAST, regression: the product's `run_all.py`
   (or equivalent). Record the check count. Smoke: every public URL returns 200.
2. **Layout regression.** Geometry + contrast + pixel-diff suite (`layout.test.mjs` pattern:
   overflow, chip anatomy, aligned rows, table cells, no overlapping text, no clipped controls,
   button heights, contrast, console clean, ≤1.5% pixel drift vs committed baseline).
3. **Screenshot matrix.** `node execution/infrastructure/human_eye_shots.cjs --plan <plan> --base <url> --out .tmp/human_eye/<run>`
   over every page × state (dialogs open, forms filled with the example, filters applied,
   map view, empty state, closed role) × viewports (1440, 1024, 390) × themes (light, dark)
   × reduced-motion where motion exists. Motion: three frames 700 ms apart of every animated
   element; any pop, blank, or jump is a defect.
4. **Human-eye review.** Spawn reviewer agents (one per edition/section, ≤ 40 images each)
   that `Read` EVERY PNG and log per image: PASS or a defect row (severity P1/P2/P3, element,
   what a picky client would say, suggested fix). Checklist: alignment, wrapping and orphaned
   dots, uniform tile/button heights, clipped or overlapping text, placeholder or developer
   voice, two-authors feel, empty states, contrast, dark-theme regressions, anything unfinished.
   DOM checks are not a substitute; the agent must look at the pixels.
5. **Functional walk.** As each persona (jobseeker, employer, admin): every action end to end
   with the real data path (search → filter → reload → save → apply link resolves; post → preview →
   submit shows no false success; edition/theme switches persist). Log every oddity.
6. **Panel.** Every lens in `.claude/memory/panel_roster.md` on the delta (a scoped
   3-lens run — UX, honesty, rigor — is allowed for a change under ~50 lines; a release takes all).
7. **Verdict.** Write `<product>/research/qa_<date>/human_eye_verdict.md`: tier results with
   counts, every defect found with screenshot filename and status (fixed / open / accepted-why),
   pages × states × viewports covered, honest gaps (what could not be exercised). Only then may
   the message to the client be drafted. The words "done", "all good", "100%" never appear
   without this file.

## Fix loop
Defects go back to implementers with the screenshot name; the fixer re-runs tiers 2–4 for the
affected pages, refreshes the layout baseline only for pages it changed and says so. A second
independent human-eye review runs after every fix round. Two clean rounds in a row = release.

## Anti-patterns this skill exists to prevent
- Claiming coverage from line counts.
- Verifying a visual change by DOM queries alone.
- Shipping a change to one edition/locale only (every change is verified on all editions).
- Skipping the panel for "small" UI changes (the carousel grid, 2026-09-28).
- Reporting a test tier as PASS when it was SKIPPED (skips print SKIP and fail the gate).
