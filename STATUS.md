# Workspace Status

> Live status page reads this file. Edit anytime; mobile reload picks it up immediately.
> Last updated: 2026-06-15 morning

## CV Optimizer — local CLI is the production path

The local CLI (`execution/personal_workflows/cv_optimizer_local/cli.py`) passed the front-door synthetic 5 consecutive times this morning and is now the recommended way to produce optimized CVs.

**Front-door synthetic results (5/5 PASS):**
- Run 1: 195.0s, ATS 92
- Run 2: 187.6s, ATS 88
- Run 3: 206.3s, ATS 91
- Run 4: 151.2s, ATS 91
- Run 5: 104.5s, ATS 93

Mean 169s, range 105-206s, well under the 360s cap. Every run surfaced GitHub-sourced projects (Anneal, YouTube Video Analyzer) and produced HTML + A4 PDF + PNG artifacts. Sample PNG visually inspected: recruiter-scannable layout, ATS pill, profile box, projects section populated.

**Why local CLI replaced the Worker:**
- Uses operator's Claude subscription via `claude --print`. Zero per-call cost. Bounded only by Claude subscription rate limits (not the free-tier 250/day quota that broke the Worker for 16h/day).
- Architectural correction: a single-user career tool didn't need a SaaS shape. It needs a local tool that leverages the existing paid subscription.
- The Worker at cv-optimizer.pages.dev stays alive as a demo URL but is no longer the production path.

**How to use:**
```bash
py execution/personal_workflows/cv_optimizer_local/cli.py \
  --cv path/to/your_cv.pdf \
  --jd-text-file path/to/jd.txt \
  --out-dir .tmp/my_run/
```

Outputs in --out-dir: `cvspec.json`, `cv.html`, `cv.pdf` (A4), `cv.png`, `run.log`.

## New always-active workspace rules (installed today)

1. `~/.claude/rules/front-door-synthetic.md` — every project with a user surface needs an end-to-end synthetic; 5 consecutive PASS before claiming "ready"; failing synthetic must lead every status report.
2. `~/.claude/rules/learnings-loop.md` — when a class-of-mistake surfaces, write the lesson into `~/.claude/rules/` before session close. Promise to operator: "you will not have to teach me the same lesson twice."

Both are referenced from the new TOP-OF-MIND RULES section in `~/.claude/CLAUDE.md`.

## Outstanding work

- **Workspace hardening triage**: apply the new rules to every existing project. ~10 projects in `personal_workflows/` alone (cv_builder, cv_optimizer_agent, anthropic_watch, job_tracker_pm_france, job_search_sheet, self_outbound_system, etc.) need their own front-door synthetics and DoD pass. Proposed but not started — awaiting operator go.
- **Worker (cv-optimizer.pages.dev)**: deprecated to demo-URL status. Could be retired entirely after operator confirms they're using the local CLI.
- **Remote control Layer 3 verification**: the desktop shortcut exists with correct properties but end-to-end (double-click → URL prints → phone connects) was not tested. Requires operator interaction.

## Live endpoints

- Local CLI: `execution/personal_workflows/cv_optimizer_local/cli.py`
- Worker (demo only): https://cv-optimizer.pages.dev
- Mobile status: https://cv-optimizer.pages.dev/status

## Recent commits

- (this commit) — local CV optimizer CLI + front-door synthetic + 2 new workspace rules
- `31f34ef` test(cv_optimizer_v2): dependability audit 42/42 + fingerprint CRLF fix
- `20f075e` feat(cv_optimizer_v2): pivot to Gemini 2.5 Flash + remote control shortcut
- `80d52af` feat: mobile status page + Sonnet 4.6 upgrade + remote-control directive
