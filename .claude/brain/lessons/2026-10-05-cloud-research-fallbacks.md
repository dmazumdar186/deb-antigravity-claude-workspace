---
id: 2026-10-05-cloud-research-fallbacks
triggers: research, firecrawl, tavily, youtube transcript, wikipedia, web search, cloud
scope: infra
strength: 1
status: active
created: 2026-10-05
confirmed: 2026-10-06
source: .claude/notes/general.md
supersedes:
---
In cloud, fall back to WebSearch and the Wikipedia API (~20 s apart) when Firecrawl/Tavily 401, and ask the operator to paste YouTube transcripts.

Why: 2026-10-05 Firecrawl and Tavily returned 401; 2026-10-06 YouTube transcripts hit a bot wall in the container.
