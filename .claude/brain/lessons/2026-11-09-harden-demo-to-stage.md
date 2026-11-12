---
id: 2026-11-09-harden-demo-to-stage
triggers: demo, prototype, sandbox, security, rfp, poc, concept
scope: client
strength: 2
status: active
created: 2026-11-09
confirmed: 2026-11-09
source: deliverables/asset_voyages_rfp_2026-10-28/30_Postmortem_Lost_to_voyagedemo.md
supersedes:
---
Spend demo effort on what the buyer sees (pages, journeys, instant first click); keep production security work (sandboxes, write caps, key schemes) for the paid build.

Why: Asset Voyages 2026-11-09: ~24 h went into per-browser sandboxes and HKDF keys the buyer never saw; the demo needed boot instructions.
