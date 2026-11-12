---
id: 2026-11-11-playwright-classify-full-error
triggers: playwright, click timeout, linkedin connect, browser automation, retry, scraper
scope: code
strength: 2
status: active
created: 2026-11-11
confirmed: 2026-11-11
source: fe4a55d
supersedes:
---
Classify Playwright failures on the full error text, and give block-shaped and UI-shaped failures separate retry ceilings.

Why: One retry streak for every cause stopped linkedin_connect 2026-11-06 and 2026-11-10; a 600-char trim hid the intercept line (RCA 2026-11-11).
