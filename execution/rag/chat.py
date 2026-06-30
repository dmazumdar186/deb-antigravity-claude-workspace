"""
description: Chat against a RAG store ingested by execution/rag/ingest.py. Free path:
             Gemini text-embedding-004 for the query embedding + gemini-2.5-flash for
             the answer. Single-shot via --question, or interactive REPL otherwise.
inputs:
  - --store <name>         Store name; reads from execution/rag/stores/{name}.json. Default: "default".
  - --question <str>       Single question. Omit to drop into REPL.
  - --top-k <n>            Number of chunks to retrieve. Default: 4.
  - --max-tokens <n>       Max output tokens. Default: 512.
  - --min-score <float>    Cosine threshold; below this -> "I don't have info" reply. Default: 0.30.
  - Env: GEMINI_API_KEY (required, free tier).
outputs:
  - Stdout: the answer text.
  - Stderr: retrieved chunks (truncated) + cosine scores.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
from pathlib import Path

# Fix Unicode crash on Windows cp1252 before any other output
try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 - reconfigure is best-effort; some streams don't support it
    pass

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s | %(message)s", stream=sys.stderr)
log = logging.getLogger("rag.chat")

STORES_DIR = Path(__file__).resolve().parent / "stores"
EMBED_MODEL = "gemini-embedding-001"
CHAT_MODEL = "gemini-2.5-flash"

SYSTEM_PROMPT = (
    "You answer questions strictly using the CONTEXT chunks supplied below. "
    "If the CONTEXT does not contain the answer, reply: \"I don't have that information in the provided content.\" "
    "Never invent facts. Quote phrasing from the CONTEXT when relevant. Be concise."
)


def _store_path(name: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_.-]", "_", name)
    if not safe:
        raise ValueError(f"invalid store name: {name}")
    return STORES_DIR / f"{safe}.json"


def _load_store(path: Path) -> list[dict]:
    if not path.exists():
        log.error("No store at %s. Run: py execution/rag/ingest.py --source <path-or-url> --store %s",
                  path, path.stem)
        raise SystemExit(2)
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        log.error("Store %s is corrupted: %s. Re-run ingest with --reset.", path, exc)
        raise SystemExit(2)


def _gemini_client():
    api_key = os.environ.get("GEMINI_API_KEY", "")
    if not api_key:
        log.error("GEMINI_API_KEY not set. Add to .env:\n  GEMINI_API_KEY=your_key_here")
        raise SystemExit(2)
    from google import genai

    return genai.Client(api_key=api_key)


def _embed_query(client, query: str) -> list[float]:
    resp = client.models.embed_content(model=EMBED_MODEL, contents=query)
    if hasattr(resp, "embeddings") and resp.embeddings:
        return list(resp.embeddings[0].values)
    if hasattr(resp, "embedding"):
        return list(resp.embedding.values)
    raise RuntimeError(f"Unexpected embed response shape: {type(resp)}")


def _cosine_top_k(query_vec: list[float], chunks: list[dict], k: int) -> list[tuple[float, dict]]:
    try:
        import numpy as np
    except ImportError:
        log.error("numpy not installed. Run: pip install numpy")
        raise SystemExit(2)
    q = np.asarray(query_vec, dtype="float32")
    q_norm = q / (np.linalg.norm(q) + 1e-9)
    mat = np.asarray([c["embedding"] for c in chunks], dtype="float32")
    mat_norms = mat / (np.linalg.norm(mat, axis=1, keepdims=True) + 1e-9)
    scores = mat_norms @ q_norm
    top_idx = np.argsort(-scores)[:k]
    return [(float(scores[i]), chunks[i]) for i in top_idx]


def _answer(client, question: str, retrieved: list[tuple[float, dict]], max_tokens: int) -> str:
    context_blocks = []
    for i, (score, chunk) in enumerate(retrieved, 1):
        context_blocks.append(
            f"[CHUNK {i} | score={score:.3f} | source={chunk.get('source', 'unknown')}]\n{chunk['text']}"
        )
    user_prompt = "CONTEXT:\n\n" + "\n\n---\n\n".join(context_blocks) + f"\n\nQUESTION: {question}"

    from google.genai import types as gtypes

    try:
        resp = client.models.generate_content(
            model=CHAT_MODEL,
            contents=user_prompt,
            config=gtypes.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                max_output_tokens=max_tokens,
                temperature=0.2,
            ),
        )
    except Exception as exc:  # noqa: BLE001 - surface API errors with redaction
        msg = str(exc)
        if "AIza" in msg:
            msg = "[redacted credentials]"
        raise SystemExit(f"Gemini chat call failed: {msg[:300]}")

    # google-genai returns .text or a candidates list — prefer .text when present
    text = getattr(resp, "text", None)
    if text:
        return text.strip()
    cands = getattr(resp, "candidates", None) or []
    for cand in cands:
        for part in getattr(getattr(cand, "content", None), "parts", []) or []:
            t = getattr(part, "text", None)
            if t:
                return t.strip()
    return ""


def _single_turn(client, store: list[dict], question: str,
                 top_k: int, max_tokens: int, min_score: float) -> str:
    qvec = _embed_query(client, question)
    retrieved = _cosine_top_k(qvec, store, top_k)
    log.info("Retrieved %d chunks. Top score: %.3f.", len(retrieved),
             retrieved[0][0] if retrieved else 0.0)
    for i, (score, chunk) in enumerate(retrieved, 1):
        preview = chunk["text"][:120].replace("\n", " ")
        log.info("  #%d  %.3f  %s  %s...", i, score, chunk.get("source", "?")[:40], preview)

    if not retrieved or retrieved[0][0] < min_score:
        return "I don't have that information in the provided content."
    return _answer(client, question, retrieved, max_tokens)


def main() -> int:
    parser = argparse.ArgumentParser(description="Chat against a RAG store.")
    parser.add_argument("--store", default="default")
    parser.add_argument("--question", default=None, help="Single-shot question; omit for REPL.")
    parser.add_argument("--top-k", type=int, default=4)
    parser.add_argument("--max-tokens", type=int, default=512)
    parser.add_argument("--min-score", type=float, default=0.30)
    args = parser.parse_args()

    store_path = _store_path(args.store)
    store = _load_store(store_path)
    if not store:
        log.error("Store %s is empty.", store_path)
        return 1
    log.info("Loaded %d chunks from %s.", len(store), store_path.name)

    client = _gemini_client()

    if args.question:
        answer = _single_turn(client, store, args.question, args.top_k, args.max_tokens, args.min_score)
        print(answer)
        return 0

    # REPL
    print("RAG chat — store: {} ({} chunks). Ctrl+C to exit.".format(store_path.name, len(store)))
    try:
        while True:
            try:
                q = input("\n> ").strip()
            except EOFError:
                break
            if not q:
                continue
            answer = _single_turn(client, store, q, args.top_k, args.max_tokens, args.min_score)
            print("\n" + answer)
    except KeyboardInterrupt:
        print("")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
