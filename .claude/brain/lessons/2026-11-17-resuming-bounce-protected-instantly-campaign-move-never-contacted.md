---
id: 2026-11-17-resuming-bounce-protected-instantly-campaign-move-never-contacted
triggers: bounce protection, resume campaign, paused high bounce, instantly, resume, unpause, bounce, bounces, paused
scope: all
strength: 2
status: active
created: 2026-11-17
confirmed: 2026-11-17
source: 6b5b92e2f36f SF bounce re-pause fix via holding list 2026-11-17 (lesson-add commit)
supersedes:
---
Before resuming a bounce-protected Instantly campaign, move its never-contacted unverified leads to a holding list so only follow-ups to delivered addresses send.

Why: 2026-11-17: resumed SF campaign re-paused within hours; the resume sent only new unverified leads (7.4% bounce)
