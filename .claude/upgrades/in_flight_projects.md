# In-Flight Projects — Deep Upgrade Audit (2026-06-11)

Deep audit of Rosy Origami (Phase 0 shipped, Phases 1+ pending) and Remotion (v1 shipped) — both actively being built, so upgrade ROI is highest if applied now.

---

## Top 5 high-impact upgrades

1. **Rosy Origami — Dynamic Workflow for multi-tenant / multi-source ingest** (Phase 1 and beyond). The newsletter pipeline fans out per source (IG/YT/News) and will fan out per tenant in Phase 4. This is a textbook `ultracode:` candidate. Save as `.claude/workflows/rosy-ingest.md` when Phase 1 adds a second tenant. Current single-tenant, single-run shape does NOT yet warrant a workflow — the trigger is Phase 4 (multi-tenant batch run).

2. **Rosy Origami — Exit Criteria block missing from directive**. The directive `directives/content/rosy_origami_composer.md` is fully imperative (10-step numbered sequence). It has no `## Exit Criteria` section. Adding one costs 15 minutes and makes "is this newsletter done?" a verifiable predicate rather than "did the script exit 0?"

3. **Rosy Origami — `--mode` flag absent; `--tier` is a partial substitute but diverges from workspace template**. The directive exposes `--tier gemini|default|premium` which maps to models, but this is a custom flag — the workspace template uses `--mode cheap|balanced|premium`. The mismatch means `generate_demo.py` cannot be swapped out generically by the harness. Rename to `--mode` and map to the same `MODE_TO_MODEL` routing table as `_TEMPLATE.py`.

4. **Rosy Origami — directive/code sync gap**. The directive's `Tools/Scripts` table lists 8 files (`humanize.py`, `render.py`, `fetchers/ig_api.py`, `fetchers/ig_manual.py`, `fetchers/yt.py`, `fetchers/news.py`) that do NOT exist as standalone files — they were inlined into `generate_demo.py` and `composer.py`. The memory acknowledges this gap. At Phase 1 refactor, either create the listed files or update the directive table to match what actually exists.

5. **Remotion — visual quality validation gap**. The `/remotion` skill and all four directives have no step that verifies the rendered output looks correct. The only visual check is "toggle the checkered-background button in Studio" (alpha confirm) and a single-frame PNG smoke test. There is no assertion on: frame brightness, 3D scene visibility, color correctness, or composition layout. Per the product-quality-skeptic memory, this is non-negotiable for user-facing artifacts. Add a frame-inspection step with a PIL-based brightness/non-blank assertion to `remotion_bootstrap.md` and the smoke-test.

---

## Rosy Origami

### Current state (from memory)
2026-05-28: Phase 0 shipped and tested. 54/54 tests pass. First real GIO Paris newsletter generated end-to-end. Gemini 2.5-flash-lite, free tier, $0 cost. Key gaps acknowledged in memory: humanizer subprocess not wired, Figma mockup not started, Meta Graph API deferred, directive Tools/Scripts table out of sync with reality. Phase 1 = deploy for GIO + parallel outreach to second org.

### Files audited
- Directives: `directives/content/rosy_origami_composer.md` (114 lines)
- Execution scripts:
  - `execution/content/rosy_origami/generate_demo.py` (~350 lines estimated)
  - `execution/content/rosy_origami/composer.py` (~180+ lines)
  - `execution/content/rosy_origami/fetchers/ig_instaloader.py` (~148 lines)
  - `execution/content/rosy_origami/templates/cultural_community.yaml`
  - `execution/content/rosy_origami/tenants/gio_paris.yaml`
- Notes: none (`./claude/notes/directives/content/` and `./claude/notes/execution/content/` have no rosy_origami entries)

### Per-axis scorecard

| Axis | Score | Evidence | Recommended upgrade |
|---|---|---|---|
| 1. Dynamic Workflow | MAYBE | Current: single-tenant, single-run. Phase 4 will be multi-tenant batch. The fan-out trigger (>5 parallel tasks) is not yet met for Phase 0–1 GIO sandbox. However, within a single newsletter run, the 6 section LLM calls are already sequential with throttle sleeps — a mild candidate for async batching. Real Dynamic Workflow case arrives at Phase 4 multi-tenant. | Save `.claude/workflows/rosy-ingest.md` at Phase 4. For now, note the pattern in the directive. |
| 2. Declarative exit criteria | HIT | The directive has a `## Steps` section (10 imperative steps: "1. Load tenant config", "2. Validate voice profile", ...) and a robust `## Edge Cases` section, but NO `## Exit Criteria` block in the `_TEMPLATE.md` format. Done is currently "script exits 0." | Add an `## Exit Criteria` block: (a) output HTML file exists at `.tmp/rosy_origami/{slug}/newsletter_<date>.html`, (b) file size > 5 KB (not empty render), (c) `.meta.json` has `flagged_dates == []` (or manual review noted), (d) section count >= 3 (non-empty newsletter). |
| 3. `--mode` flag | HIT | `generate_demo.py` exposes `--tier gemini\|default\|premium` but NOT `--mode cheap\|balanced\|premium`. This diverges from the workspace `_TEMPLATE.py` convention. The mapping is equivalent conceptually but inconsistent in flag naming and model table. | Rename `--tier` to `--mode`. Map: `gemini` → `cheap`, `default` → `balanced`, `premium` → `premium`. Update directive flag table. |
| 4. Sub-agent opportunity | MAYBE | The directive's orchestration steps (1–10) are currently executed in one monolithic script. For Phase 3 (web app), separating fetch, compose, render into independently callable sub-agents would help. For Phase 0–1, the script is small enough that a single sub-agent handles it fine. | No immediate action needed. Flag in Phase 3 plan: decompose `generate_demo.py` into fetch/compose/render agents. |
| 5. Python hardening | PARTIAL | subprocess.run in `call_humanizer()` (generate_demo.py:208–227): encoding="utf-8", errors="replace" present — PASS. `except Exception as e` in `fetchers/ig_instaloader.py:87`: has a print log line — PASS (per rule #5, bare swallow is forbidden but a log+continue is acceptable). No threading / ThreadPoolExecutor found — no Lock needed. No LLM-derived path inputs to filesystem — N/A. No Claude pricing table (uses Gemini) — N/A. One potential issue: `composer.py` calls `resp.text or ""` without checking for None before strip — safe since `or ""` guards it, but fragile if Gemini SDK changes return type. | Minor: add a null-guard comment on `resp.text` line in `composer.py`. The `except Exception + log` in ig_instaloader is acceptable. |
| 6. Note capture | HIT (missing) | No `.claude/notes/directives/content/rosy_origami/` or `.claude/notes/execution/content/rosy_origami/` files exist. Memory captures the important facts (per-shortcode vs. profile-level instaloader, Gemini model name discrepancy, 13s throttle sleep, humanizer not wired) but these are in the project memory file, not the notes system that the CLAUDE.md auto-lookup protocol checks. | Create `.claude/notes/execution/content/rosy_origami/composer.md` and `.../generate_demo.md` with the key gotchas (Gemini 2.5-flash-lite model name, 5 RPM throttle, instaloader per-shortcode workaround, humanizer not wired). |
| 7. Agent Team candidate | N/A | Phase 0–1 is single-tenant, sequential. No peer coordination pattern. Phase 4 (multi-tenant parallel) could use Agent Teams if tenants have conflicting scheduling needs. | Re-evaluate at Phase 4. Not now. |
| 8. Canary/health | MAYBE | Phase 0 is a CLI script — no canary needed (per global CLAUDE.md: skip for CLI scripts run manually). Phase 3 deploys a Next.js web app + CF Worker — at that point, the canary rule kicks in: add `/api/health` endpoint to the Worker returning tenant-list, Gemini credit status, last-run timestamp. | Flag in Phase 3 plan: Day 1 of CF Worker scaffolding must include `/api/health`. |
| 9. 4-persona product thinking | HIT (missing) | The directive reads as Builder-only. It is deeply implementor-focused (step sequences, API limits, edge cases) with no Head of Product ("why does a community editor trust this output?"), no Designer ("what does the email look like in Mailchimp mobile preview?"), no Skeptic ("what happens when GIO goes quiet for 2 months and we have 3 posts?"). The product-quality-skeptic feedback memory flags this as a non-negotiable axis for user-facing artifacts. | Add a `## Product Considerations` section to the directive with 3 sub-sections: UX (what does the editor see?), Trust (how does the editor know content is accurate?), Edge behavior (what happens with thin content pools?). |
| 10. Visual quality + User Agency | HIT (missing) | No QA step verifies the HTML email renders acceptably in a mail client. No user-agency step shows the editor what to do if a section is wrong. The `## Steps` ends at "write outputs to `.tmp/`" with no "human review" step. The hallucination guard writes to `.meta.json` but there is no step that surfaces it to the editor as an actionable list. | Add a Step 11: "Open `.meta.json` flagged_dates list and print it as a human-readable review checklist before claiming done." Add Step 12: "Preview HTML in browser — confirm it does not render as blank or broken." |

### Recommended upgrade path

**Immediately (Phase 0 final cleanup, before Phase 1 pitch):** Add the `## Exit Criteria` block to the directive (Axis 2), rename `--tier` to `--mode` in generate_demo.py and the directive flag table (Axis 3), and create the two notes files capturing instaloader and Gemini model gotchas (Axis 6). These are 3 mechanical changes that cost less than an hour and make the system more robust for the handoff to GIO.

**At Phase 1 (deploy + second org outreach):** Add the `## Product Considerations` section to the directive (Axis 9) and wire the hallucination-flag review checklist into the script's stdout output (Axis 10 — the `.meta.json` already exists, just surface it). This is the phase where a real editor sees the output for the first time, so user-agency gaps hurt most.

**At Phase 3 (web app scaffolding):** Add `/api/health` to the CF Worker on Day 1 (Axis 8). Plan the fetch/compose/render decomposition for sub-agent delegation (Axis 4). Draft the `.claude/workflows/rosy-ingest.md` Dynamic Workflow file to be ready for Phase 4 (Axis 1).

---

## Remotion

### Current state (from memory)
2026-06-10: `/remotion` skill shipped. Preflight + new sub-commands. Overlay on official `--three` template. Alpha smoke-test (single-frame PNG) verified. Render wrapper Python script deferred to v1.1. Skeptic-caught bugs included: wrong `--template three` syntax, smoke-test asserting alpha on the wrong composition, Root.tsx overwrite ambiguity.

### Files audited
- Directives:
  - `directives/video/remotion_authoring.md` (241 lines)
  - `directives/video/remotion_three.md` (220 lines)
  - `directives/video/remotion_render.md` (136 lines)
  - `directives/video/remotion_bootstrap.md` (197 lines)
- Execution scripts:
  - `execution/video/remotion_bootstrap.py` (563 lines)
- Skill: `.claude/skills/remotion/SKILL.md` (250 lines)
- Notes: none (`./claude/notes/directives/video/` has no remotion entries)

### Per-axis scorecard

| Axis | Score | Evidence | Recommended upgrade |
|---|---|---|---|
| 1. Dynamic Workflow | N/A | Remotion renders are sequential per composition — frame rendering is local CPU-bound work, not fan-out to sub-agents. Lambda parallel render exists (Remotion's own cloud infrastructure) but is explicitly deferred to v2 (requires company license). There is no fan-out pattern in the current scope. | N/A for v1. Note in v2 planning: if the user ever renders N variants (different color grades, different durations), that's a `ultracode:` candidate. |
| 2. Declarative exit criteria | PARTIAL | `remotion_authoring.md` and `remotion_three.md` have strong steps sections but no formal `## Exit Criteria` block. `remotion_bootstrap.md` is the closest — it ends with "Bootstrap complete for '{slug}'" and lists 3 next steps. None of the directives define a verifiable "done" predicate. `remotion_render.md` is the weakest: Step 1 says "confirm alpha before rendering" but this is a manual visual step, not a verifiable assertion. | Add `## Exit Criteria` to `remotion_render.md`: (a) `out/{slug}.{ext}` exists, (b) file size > 0 bytes, (c) `ffprobe out/{slug}.mov` returns duration > 0 (verify the file is a valid video, not a corrupt render). |
| 3. `--mode` flag | N/A | Remotion is a CLI tool wrapping `npx remotion render`. There is no LLM call in `remotion_bootstrap.py` and no model selection needed. The render quality analog is `--crf` (H.264 quality) and `--prores-profile` (codec), which are already documented in `remotion_render.md`. | N/A. When `remotion_render.py` is built in v1.1, expose `--quality draft|standard|archival` mapping to crf=28/18/0 and prores-profile=proxy/4444. That IS a `--mode`-analog worth adding. |
| 4. Sub-agent for bootstrap | MAYBE | Bootstrap is already a Python script (`remotion_bootstrap.py`, 563 LOC). The skill calls it as a single subprocess step. There is no sub-agent delegation in the skill. However, bootstrap is a one-time linear operation (create-video → npm install → junction → overlay → registry). It does not benefit from sub-agents given it is already async (runs as a background subprocess). The 10-minute timeout for npm install is the real constraint, not agent structure. | No sub-agent needed for bootstrap. When v1.1 adds a `remotion_render.py`, that script should be invoked via a sub-agent (render is slow + the skill should not block the main context for 3+ minutes). |
| 5. Python hardening | PASS | `remotion_bootstrap.py` implements all 5 hardening rules: (1) Every `subprocess.run` uses `encoding="utf-8", errors="replace"` — verified at lines 82–96 (`run_cmd` wrapper), 264, 359, 456. (2) `threading.Lock()` guards registry writes at `_REGISTRY_LOCK` (line 43) and `write_registry_atomic()` (line 108). (3) Slug path-traversal guard at `validate_slug()` — resolves candidate and checks `is_relative_to(PROJECTS_DIR.resolve())`. (4) No Claude pricing table needed (no LLM calls). (5) No bare `except Exception: pass` found — the one bare-ish exception is `OSError` in `write_registry_atomic`'s finally block (line 123) which has a comment explaining it is safe. Full PASS. | None needed. This is the reference implementation for the workspace. |
| 6. Note capture | HIT (missing) | No `.claude/notes/directives/video/` entries for remotion. The important gotchas (wrong `--template three` syntax, `--yes` flag requirement, `useFrame` vs `useCurrentFrame()` in headless render, `layout="none"` on Sequences, `gl={{ alpha: true }}` on ThreeCanvas) are embedded in the directives themselves and in the project memory, but not in the notes system. | Create `.claude/notes/directives/video/remotion_three.md` with the 4 R3F headless-render gotchas. These are the bugs that will re-surface when a new Remotion project is started months from now. |
| 7. Agent Team candidate | N/A | Remotion is a single-user sequential authoring + render pipeline. No peer coordination pattern. N/A. | N/A. |
| 8. Canary/health | N/A | Remotion is a local CLI tool. No deployed service. Per global CLAUDE.md canary rules: skip for CLI tools run manually. | N/A. Note for v2: if Lambda render is ever added, that becomes a deployed service and needs `/api/health`. |
| 9. Visual quality validation | HIT (missing) | This is the most significant gap. The smoke-test protocol (in `remotion_bootstrap.md` Step 6, referenced in the directive) uses a single-frame PNG export and a Python check in SKILL.md. The SKILL.md Step 3 says "Confirm the junction target exists" and "Confirm registry entry written" but has NO instruction to open the rendered frame and verify it is not blank/black/corrupted. The `remotion_render.md` Step 1 says "toggle the checkered-background button" but this is a manual human step — there is no automated visual assertion. Per `feedback_product_quality_skeptic.md`: visual quality validation is non-negotiable for user-facing artifacts. | Add to `remotion_bootstrap.md` Step 6 (after PNG export): "Run `py -c \"from PIL import Image; img=Image.open('out/alpha_test.png'); pixels=list(img.getdata()); assert any(p[3]>0 for p in pixels), 'render is fully transparent — blank output'; print('visual check PASS')\"` to assert the frame has non-zero pixels." Also add to `remotion_render.md` Step 5: "After render, verify file size via `Get-Item out/{slug}.mov` — alert if < 1 MB (suspiciously small for a video)." |
| 10. `--mode` analog for render quality | MAYBE | `remotion_render.md` documents three render presets (ProRes 4444, WebM-alpha, H.264) as separate manual CLI commands. There is no unified `--quality` flag to pick one. When `remotion_render.py` is built in v1.1, this is the right time to expose a quality enum. | Defer to v1.1 `remotion_render.py`. Flag in v1.1 roadmap: `--preset overlay-prores|overlay-webm|final` (maps to the three existing manual command sets). |

### Recommended upgrade path

**Immediately (v1 maintenance):** Add the visual quality check to `remotion_bootstrap.md` (PIL brightness assertion on the smoke-test PNG — Axis 9). Create `.claude/notes/directives/video/remotion_three.md` with the 4 R3F headless-render gotchas (Axis 6). Both are documentation-only changes, zero code risk.

**At v1.1 (when `remotion_render.py` is built):** Add `## Exit Criteria` to `remotion_render.md` with file-size and ffprobe duration assertion (Axis 2). Expose `--preset overlay-prores|overlay-webm|final` flag in the render wrapper (Axis 3 analog). Run the render wrapper as a sub-agent from the skill so the main context is not blocked (Axis 4).

---

## Cross-project pattern

Both projects share a **directive/code sync gap**: as implementation evolves during rapid Phase 0 iteration, the directive's `Tools/Scripts` table drifts from what actually exists on disk. Rosy Origami lists 8 files that were inlined elsewhere; Remotion's directives predate the bootstrap script's npm install step discovery. The workspace already has a Documenter agent pattern (`directives/subagent/documenter.md`) to address this, but it was not invoked after every Phase 0 delta. The workspace-level pattern to establish: after any session that changes code without updating the directive, the session should end with a Documenter agent call as a non-optional cleanup step. This is already in CLAUDE.md ("After updating any script in `execution/`, spawn a sub-agent to sync directives") but it is being skipped under time pressure. Consider wiring it as a `post-edit` hook rather than a voluntary step.
