---
id: 2026-11-17-instantly-campaigns-active-sending-check-account
triggers: instantly not sending, campaigns stuck, zero sent, slow ramp
scope: all
strength: 2
status: active
created: 2026-11-17
confirmed: 2026-11-17
source:
supersedes:
---
When Instantly campaigns are active but not sending, check account enable_slow_ramp, account daily sends and campaign not_sending_status before changing campaign settings.

Why: 2026-11-17: 8 Deb_16 Oct campaigns sent 0 for a week because 9 inboxes were ramping at +2/day, read as a disaster
