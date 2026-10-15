# GLM / Kimi log — MISB v3 cover backdrop

Payload: public visual brief only (city names, colours, API spec). No PII, no client data.

| when | model | round | prompt tok | completion tok | cost | output | wall | generation id |
|---|---|---|---|---|---|---|---|---|
| 2026-10-15 14:59 | z-ai/glm-5.3 | initial | 784 | 8707 | $0.02561546 | 4986 B | 72s | gen-1792076313-paaEp6iG5a1tupiJSVty |

Review (hand): one round, no regeneration needed. Checks passed: only global `window.MISBBackdrop`; no fetch/XHR/eval/Function/console; mulberry32 seeded; ResizeObserver + visibilitychange; reduced-motion static frame; API init/setProgress/render/pause/resume/destroy. Hand tweak after visual pass: line/river alphas ×2 and dot radius 1.1→1.4 px (too faint on #0b1a2b). Total spend: $0.026 (one call, 72 s).
