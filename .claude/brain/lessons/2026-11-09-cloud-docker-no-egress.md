---
id: 2026-11-09-cloud-docker-no-egress
triggers: docker, container, dockerd, image pull, cloud session, compose
scope: infra
strength: 1
status: active
created: 2026-11-09
confirmed: 2026-11-09
source: .claude/notes/general.md
supersedes:
---
In cloud sessions, expect Docker containers to have no usable egress and pull images via mirror.gcr.io; check disk (~27 GB) before large images.

Why: 2026-11-09: TLS interception broke container egress, Docker Hub hit 429, and one image was 17.3 GB.
