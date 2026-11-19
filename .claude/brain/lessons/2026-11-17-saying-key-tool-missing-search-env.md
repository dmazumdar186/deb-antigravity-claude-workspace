---
id: 2026-11-17-saying-key-tool-missing-search-env
triggers: missing key, need api key, verifier, reoon, millionverifier, credential not set
scope: all
strength: 3
status: active
created: 2026-11-17
confirmed: 2026-11-17
source: 2d4b46ad749d key declared missing before searching by function 2026-11-17 (lesson-add commit)
supersedes:
---
Before saying a key or tool is missing, search env var names and execution/ by function (verify, enrich, send), not by one vendor name.

Why: 2026-11-17: asked for a MillionVerifier key while REOON_TOKEN and reoon_verify.py existed (grep was vendor-named), then opened the reply with 'You were right' (that half is CLAUDE.md debate protocol, always loaded; trimmed from this rule 2026-11-18)
