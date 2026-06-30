# RAG Chatbot (Chatbase-pattern skeleton)

## Goal

Ship a custom-knowledge chatbot for any business in under a day: ingest their content (URLs, PDFs, raw text) into a local vector store, then expose a chat CLI / endpoint that answers questions grounded in their content. Free-tier path uses Gemini for embeddings + chat. Designed to be the cheapest possible MVP so the operator can pitch "done-for-you RAG bot" to coaching / info-product / support clients and only spin up paid infra (Pinecone, OpenAI, Cloudflare Vectorize) once a paying client signs.

This is the workspace's answer to **Chatbase / Sider / Chatbot.com**, whose freelancer-resale rate per the 2026-06-25 LinkedIn backlog is $300-$5,000 per bot.

## When to use this

- A coaching, info-product, or B2B-services client wants 24/7 customer support trained on their FAQs/docs/courses.
- A creator wants a "talk to my YouTube channel" or "talk to my book" experience.
- The operator needs a quick demo for a discovery call ("here's what we'd ship").

## Inputs

### CLI flags — `ingest.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--source <path-or-url>` | (required) | Path to a file (.txt, .md, .pdf) OR an http(s) URL. Repeat for multiple. |
| `--store <name>` | `default` | Store name. Maps to `execution/rag/stores/{name}.json`. |
| `--chunk-size <n>` | `500` | Target chunk size in characters before merging short paragraphs. |
| `--reset` | off | Wipe the store before ingesting (otherwise append). |

### CLI flags — `chat.py`

| Flag | Default | Description |
|------|---------|-------------|
| `--store <name>` | `default` | Which ingested store to query. |
| `--question <str>` | (none) | Single-shot question. If omitted, drops into interactive REPL. |
| `--top-k <n>` | `4` | Number of chunks to retrieve as context. |
| `--max-tokens <n>` | `512` | Max output tokens for the chat response. |

### Environment variables

| Var | Required? | Purpose |
|-----|-----------|---------|
| `GEMINI_API_KEY` | **Required for free path** | Used for both `text-embedding-004` (1500 RPM free) and `gemini-2.5-flash` chat (250 RPD free) |
| `OPENROUTER_API_KEY` | Optional fallback | Future-paid path; not used by default |

## Tools / Scripts

| File | Purpose |
|------|---------|
| `execution/rag/ingest.py` | Read sources -> chunk -> Gemini embed -> persist JSON store |
| `execution/rag/chat.py` | Load store -> embed query -> top-k cosine -> Gemini chat |
| `execution/rag/__init__.py` | Empty module marker |
| `execution/rag/stores/{name}.json` | Per-client vector store (gitignored when client-specific) |
| `tests/front_door_rag_chatbot.sh` | End-to-end fixture test |
| `tests/fixtures/rag/sample.md` | Tiny corpus for the fixture test |

### Dependencies

```
pip install google-genai python-dotenv numpy pypdf beautifulsoup4 requests
```

All free / OSS. `numpy` is for cosine similarity; no vector DB needed at this scale (<10k chunks fits in RAM trivially).

## Outputs

- `ingest.py` writes `execution/rag/stores/{name}.json` and prints chunk count + token estimate to stderr.
- `chat.py` prints the answer to stdout; cited chunks + retrieval scores go to stderr.

## Steps (operator playbook for a new client)

1. **Collect sources.** Ask the client for URLs, PDFs, FAQ docs, course transcripts. Drop them in `.tmp/{client-slug}/`.
2. **Ingest.** `py execution/rag/ingest.py --store {client-slug} --source .tmp/{client-slug}/faq.pdf --source https://client.com/about`. Repeat per source.
3. **Smoke-test.** `py execution/rag/chat.py --store {client-slug} --question "What do you do?"` — verify the answer cites real content.
4. **Iterate.** Adjust `--chunk-size`; if answers feel shallow, raise `--top-k`.
5. **Hand off.** For a demo, screen-share the REPL. For production, wrap `chat.py`'s core function in a tiny FastAPI / Cloudflare Worker (see "Productization path" below).
6. **Bill.** Free-tier suffices for ~250 chat calls / day. Once the client exceeds that or wants always-on, quote paid infra (Cloudflare Vectorize + Workers, or Pinecone + a dedicated Worker) as a Phase 2 line item.

## Productization path (when a client pays)

Three escalation tiers, only spun up after sign-off:

1. **Tier 1 (free, dev/demo)**: this skeleton. Local JSON store, manual ingest, CLI chat.
2. **Tier 2 (~$5-20/mo, low-traffic prod)**: ship the chat function as a Cloudflare Worker (free 100k req/day) with the JSON store as a KV value. Front-end = a 200-line static site.
3. **Tier 3 (~$50+/mo, real traffic)**: migrate the vector store to Cloudflare Vectorize (free tier 30M queries / mo as of 2026) or Pinecone Starter. Add per-conversation memory in D1.

Each tier shares the same retrieval + chat function — only the storage layer changes.

## Edge Cases

| Case | Behavior |
|------|---------|
| Source URL returns non-200 | Log warning, skip that source, continue with others. Exit 0 if at least one source ingested. |
| PDF has no extractable text (scanned image) | Log warning, skip. No OCR in v1 (would need tesseract — defer). |
| Empty corpus passed to `chat.py` | Exit non-zero with clear message "no store at {path}; run ingest.py first". |
| Gemini rate limit hit during ingest | Sleep 5s and retry once; on second failure, persist what's done and exit non-zero with chunk count. |
| `GEMINI_API_KEY` missing | Exit non-zero with the exact .env line to add. |
| Question with zero retrieved chunks above 0.3 cosine | Answer with "I don't have information about that in {client}'s content" — never hallucinate. |
| Store file corrupted / unreadable | Exit non-zero, suggest `--reset` to rebuild. |
| Chunk longer than embedding model's 2048-token cap | Hard-split at 2000 chars before embedding. |

## Exit Criteria

- `py execution/rag/ingest.py --source tests/fixtures/rag/sample.md --store smoke --reset` exits 0 and creates `execution/rag/stores/smoke.json` with at least 3 chunks.
- `py execution/rag/chat.py --store smoke --question "What is the founder's name?"` exits 0 and stdout contains the fixture-known answer.
- `bash tests/front_door_rag_chatbot.sh` exits 0 (the end-to-end smoke).
- A `GEMINI_API_KEY` missing run exits non-zero with the exact .env line in stderr.

## Honest gaps (panel-pass)

- **No live demo deployed.** Skeleton only — Tier 2/3 productization stubs are described, not built.
- **No multi-tenant store separation.** Stores are per-name; a single careless `--store default` would mix two clients' content. Per-client store discipline is operator's responsibility.
- **No conversation memory.** Each `chat.py` call is single-shot. Adding history would be a thin extension (append last N turns to user prompt) — left out of v1 to keep the skeleton lean.
- **No content-source citations in the answer.** Retrieved chunk text is logged to stderr only. Inlining "(source: filename.pdf, p. 3)" in the answer is the obvious next polish step.
- **Not benchmarked vs Chatbase.** We have no head-to-head retrieval-quality numbers. Before pitching, the operator should ingest one realistic corpus (e.g. their own ProdCraft transcripts) and sanity-check that answers are grounded.
