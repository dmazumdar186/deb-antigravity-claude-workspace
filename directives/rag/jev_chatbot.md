# Jev Chatbot (zero LLM calls)

## Purpose

A narrow chatbot that never calls a language model. Every step is a Jev typed decision
(TypeSafe via OpenRouter Decisions API) and every answer is a verbatim passage from the corpus,
with its `file:lines` source. RoboNuggets "19 Jev use cases", #16: "which lesson teaches X?"
answered in real time from a list of pre-transcribed videos. Fits transcripts, company docs,
directives, FAQs.

## When to invoke

- "Make a chatbot over <folder>"
- "Ask the directives bot <question>"
- Any quick lookup bot where the answer already exists word-for-word in a document set.

Operator copy-paste prompts:

```
Make a chatbot over <folder> (directives/rag/jev_chatbot.md) and serve it on port 8765.
Ask the directives bot <question> with jev_chatbot --dir directives --ask "<question>".
```

### Zero-LLM bot vs adding a generator

- **Zero-LLM is enough** when users want to be *pointed at* the right passage: lesson finders,
  "where is the SOP for X", policy lookups, FAQ bots. No hallucination is possible, answers
  are auditable, cost is ~$0.005 per question.
- **Add a generator** (`directives/rag/rag_chatbot.md`) when the answer must combine several
  passages, compute something, reformat, or speak in a persona. Use this bot's retrieval as
  the generator's context so citations stay exact.

## Inputs

- `--dir path` (corpus), `--ext md,txt`, `--name "the X docs"` (used in canned replies).
- One mode: `--ask "question"`, `--repl` (`/quit` exits), or `--serve --port 8765`.
- `--min-prob 0.35`, `--json`. env `OPENROUTER_API_KEY` (or `OPENROUTER_API_TOKEN` /
  `OPENROUTER_API_TOEKN`).

## Process

1. Intent: one tiny `choice` call (greeting / question_about_corpus / out_of_scope / clarify).
   Non-question intents get the canned line from `CANNED` (top of the script) and stop.
2. Retrieval: `jev_find.find` two-stage batched `choice` over the chunk index (headings
   prefixed with the file stem), best chunk per file, in no-abstain mode (`abstain_below=0`;
   if a batch picks `none`, its best real option still competes in stage 2).
3. Answer: one more `choice` over the winning chunk's sentences keeps the best 2-3, verbatim, in
   original order. Next two hits become "Was this it? Other matches: ...".
4. Top probability < `--min-prob` -> "I'm not sure -- closest I have is ..." plus candidates.

## Outputs

- `Answer(kind, text, source, probability, alternatives, cost, latency_ms)` (importable
  `JevChatbot(dir).ask(q)`), CLI text/JSON, or the chat UI at `http://127.0.0.1:<port>/`
  (`POST /ask {"question": ...}` returns the Answer JSON).
- Session log `.tmp/jev_chat_log.jsonl`; ledger `.tmp/jev_ledger.jsonl` (caller `jev_chatbot`).
- Chunk cache `<dir>/.jev_chat_index.json` keyed on file mtimes (delete to force a rebuild).

## Exit Criteria (declarative)

- `python3 -m pytest tests/test_jev_chatbot.py tests/test_jev_find.py -q` green.
- An in-scope question returns `kind=answer` with a source; "what's the weather" returns
  `out_of_scope`.

## Scripts (Layer 3)

- `execution/rag/jev_chatbot.py` (bot, CLI, stdlib HTTP server bound to 127.0.0.1)
- `execution/rag/jev_chatbot_ui.html` (single-page chat UI, no CDN)
- `execution/rag/jev_find.py` (chunker + two-stage retrieval, reused)
- `tests/test_jev_chatbot.py` (offline)

## Latency and cost (measured 2026-10-07, corpus = directives/, 1,599 chunks)

- In-scope question: ~66 calls, ~6 s, ~$0.005. Out-of-scope / greeting: 1 call, ~0.5 s,
  ~$0.00002. Latency is dominated by stage 1 (64 batches, 8 workers); a smaller corpus or
  `workers=16` is faster.

## Edge cases

- Jev down / no key: intent fails open to question_about_corpus; retrieval errors return
  `kind=error` with the reason.
- Stage-1 batches often prefer `none` on a big corpus; that is why the bot runs no-abstain and
  gates on the final probability instead.
- Stage-2 probabilities are relative across winners, so `p` is "best of what exists", not
  absolute truth; keep `--min-prob` at 0.35+.
- Server reads at most 64 KB per request and binds 127.0.0.1 only; do not expose it publicly.

## Changelog

- 2026-10-07: created (RoboNuggets #16). Added `abstain_below` param to `jev_find.find`
  (default unchanged) so the bot can run without batch abstention.
