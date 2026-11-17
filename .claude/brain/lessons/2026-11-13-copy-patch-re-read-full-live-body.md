---
id: 2026-11-13-copy-patch-re-read-full-live-body
triggers: instantly, patch, campaign copy, sequence edit, placeholder, append, ps
scope: all
strength: 2
status: active
created: 2026-11-13
confirmed: 2026-11-13
source: 4d300fb5131db6906c6bc82aa6625fc73222cfaa instantly P.S. fix: wrap bare-text bodies so PATCH keeps them
supersedes:
---
After any copy PATCH, re-read the full live body and check the original text survived, not just that the new text landed.

Why: 2026-11-13 adding a P.S. to Instantly drafts erased their bare-text 'do not activate' placeholder; the verify only checked the P.S. marker.
