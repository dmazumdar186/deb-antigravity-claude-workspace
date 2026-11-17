---
id: 2026-11-14-never-hand-operator-preview-release-link
triggers: preview, link, release, qa, human eye, review, mobile, android, gate, ship
scope: all
strength: 2
status: active
created: 2026-11-14
confirmed: 2026-11-14
source: c46820893d8a jeevana revamp: stale CSS hid ornaments on phones after preview was sent
supersedes:
---
Never hand the operator a preview or release link until an independent human-eye review of the FINAL build passes on Android, iPhone and laptop, scrolling the whole page in a fresh browser; builder self-tests are not that gate.

Why: Jeevana revamp 2026-11-14: I sent the preview after the builder's fix round without re-running the eye gate; the operator found the Nataraja missing on Android and asked what QA did.
