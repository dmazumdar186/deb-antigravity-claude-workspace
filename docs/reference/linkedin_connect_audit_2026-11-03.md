# LinkedIn connect — breakdown audit (2026-11-03)

## Timeline (from the 20:00 report emails)

| Date | Sent | Note |
|---|---|---|
| 10-23 | 14, then 25 | first live days |
| 10-25 | 25 | |
| 10-28 | 25 | runbook v1.2, weekly cap removed (`4f7edab6`, 07:29) |
| **10-29 (Thu)** | **25** | last full day |
| **10-30 (Fri)** | **0** | breakdown starts |
| 10-31 | no email | (20:00 task sends nothing when no run happened) |
| 11-01 | 0 | |
| 11-02 | 7 | 12:00 slot: 7 sent, 8th click denied; 18:00 slot: first click denied |
| 11-03 | 0 | 09:00 and 12:00: first click denied (now on Sonnet 5.5) |

## The delta

**Nothing in our system changed between the last good run (10-29) and the first failed run (10-30).**
- Script last changed 10-28 07:29; it ran fine on 10-28 and 10-29.
- Commits on `main` between 10-28 08:00 and 10-31 touch only unrelated notes (ASSET Voyages, Jev router on 10-28 13:58 — also before the good 10-29 run).
- The task runbook (v1.2, 10-28), model (Opus until 11-02), permission mode (Auto) and folder access were the same on 10-29 and 10-30.
- `.claude/settings.json` moved to `defaultMode: auto` on 10-22 (`8a551c48`) — *before* the job existed; it ran in Auto mode for six good days.

**What every failed run reports:** the desktop app's automatic permission check (the "Auto" mode
reviewer) denied the click that sends the invitation, category **"Real-World Transactions"**. Seen on
Opus 5.5 (11-02) and Sonnet 5.5 (11-03) — the model is not a factor. It is intermittent (7 passed on
11-02 before the 8th was denied), which is the signature of a per-action judgement, not a broken config.

**Conclusion:** the change came from outside the workspace — the app's safety reviewer started treating
"send a LinkedIn invitation on the user's behalf" as a real-world transaction around 10-30 (most likely an
app or policy update; we cannot see the app's version history from here). There is no commit to revert.
The only in-app setting that restores pre-10-30 behaviour is the task's **"Skip all approvals"** mode.

## Architecture review — why this system keeps needing patches

1. **Wrong layer for the work.** The workspace rule is: judgement in the model, deterministic steps in
   scripts. Here an AI agent performs the deterministic part — open URL, click More → Connect → Send — one
   reviewed tool call at a time (22–62 turns, up to 18 min per run). Every change to models, prompts,
   permission modes or the app's safety reviewer lands directly on the critical path. A fixed script that
   clicks has none of those dependencies.
2. **Too many moving parts.** 3 device-bound slot tasks + 1 cloud report task + Drive as the only state
   transport + a script re-downloaded from `main` on every run + a version-override rule + lock and alias
   files. Each is a separate failure point, and any commit to `main` changes production behaviour with no
   release step.
3. **Silent failure.** A blocked day produced an ordinary "(0 sent)" email and a task status of
   SUCCEEDED. It ran broken for three days (10-30 → 11-01) before anyone noticed. Workspace rule
   (`automation-boundaries.md`) requires failures to be loud; this job's design made a failure look like a
   quiet day.
4. **Config edited by many sessions, no change log.** Runbook v1.0 → v1.1 → v1.2, model Opus → Sonnet
   (11-03), schedule edits — each in a different session, recorded only in the task itself.

## Design fixes (proposed, not yet built — operator decision)

- **A. Restore today:** set the three slots to "Skip all approvals", run them in a Chrome profile logged
  in to LinkedIn only (limits what a malicious page could reach without the reviewer).
- **B. Durable:** move the clicking into a deterministic script on the laptop (Windows Task Scheduler,
  attaches to the LinkedIn-only Chrome profile, same pacing and stop rules: captcha, limit, restriction →
  stop). No AI per click, no safety-reviewer dependency, no subscription allowance used. AI only for
  exceptions. Same LinkedIn-automation risk as today, no more.
- **C. Loud failure:** "0 sent while the plan had people to do" → `BLOCKED` in the 20:00 email subject
  and a push alert. (Changes the report's subject line → needs operator's word.)
- **D. Pin the version:** slots run a tagged release of the script, not whatever is on `main`.
