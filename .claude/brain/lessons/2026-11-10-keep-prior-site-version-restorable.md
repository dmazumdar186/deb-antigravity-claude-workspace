---
id: 2026-11-10-keep-prior-site-version-restorable
triggers: redesign, new version, deploy, live site, jeevana, client site, alias
scope: site
strength: 2
status: active
created: 2026-11-10
confirmed: 2026-11-10
source: 6f69463
supersedes:
---
When a new version replaces a live client site, keep the previous deploy id and source commit recorded so a rollback is one command.

Why: Jeevana 2026-11-10: the client preferred v5.1 over v6 and the v4 alias was rolled back.
