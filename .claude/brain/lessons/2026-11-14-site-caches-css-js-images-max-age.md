---
id: 2026-11-14-site-caches-css-js-images-max-age
triggers: cache, css, deploy, preview, cloudflare pages, _headers, max-age, stale, mobile, jeevana
scope: all
strength: 2
status: active
created: 2026-11-14
confirmed: 2026-11-14
source: c46820893d8a jeevana revamp: content-hash versioned CSS/JS URLs after stale 1h cache
supersedes:
---
When a site caches CSS/JS/images (max-age), version every asset URL with a content hash (?v=sha) on each deploy, and never reuse a file name for changed image content.

Why: Jeevana revamp 2026-11-14: styles.css cached 1h under the same URL; the owner's Android kept stale CSS and saw no Nataraja or papyrus scroll.
