"""Jev chatbot: a narrow Q&A bot over a folder of docs that never generates text.

description: RoboNuggets "19 Jev use cases" #16. Every decision is a Jev typed call; every
             answer is a verbatim passage from the corpus. Per question: (1) one tiny `choice`
             call routes intent (greeting / question_about_corpus / out_of_scope / clarify);
             greeting, out_of_scope and clarify get canned lines. (2) Retrieval reuses
             jev_find.find (two-stage batched `choice`) over a chunk index cached in memory and
             on disk at <dir>/.jev_chat_index.json, keyed on file mtimes. (3) One more `choice`
             over the winning chunk's sentences keeps the best 2-3 sentences (verbatim, in
             original order). Top probability < --min-prob gives "I'm not sure" + candidates.
             Directive: directives/rag/jev_chatbot.md
inputs: --dir path (corpus); --ext md,txt; one of --ask "question" | --repl | --serve
        [--port 8765]; --min-prob 0.35; --json. env OPENROUTER_API_KEY (or
        OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: answer text + source file:lines + probability + alternatives (stdout, JSON, or the
         HTTP chat UI at http://127.0.0.1:<port>/ with POST /ask); session log
         .tmp/jev_chat_log.jsonl; ledger row .tmp/jev_ledger.jsonl (caller "jev_chatbot").
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import time
from dataclasses import asdict, dataclass, field
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402
from execution.rag import jev_find  # noqa: E402

CANNED: dict[str, str] = {
    "greeting": "Hi! Ask me anything about {corpus} and I'll point you at the exact passage.",
    "out_of_scope": "I only know about {corpus}. Try asking something covered there.",
    "clarify": "Could you say a bit more about what you're looking for in {corpus}?",
    "unsure": "I'm not sure -- closest I have is {source}:",
    "no_match": "I couldn't find anything about that in {corpus}.",
    "alternatives": "Was this it? Other matches: ",
    "error": "Jev is unavailable right now ({error}).",
}
INTENTS = {
    "greeting": "a greeting, thanks or small talk with no real question",
    "question_about_corpus": "a question or lookup that the knowledge base ({corpus}) could answer",
    "out_of_scope": "a question about something unrelated to {corpus} (weather, news, general trivia)",
    "clarify": "too vague or too short to know what is being asked",
}
MIN_PROB = 0.35
INDEX_NAME = ".jev_chat_index.json"
LOG_PATH = _ROOT / ".tmp" / "jev_chat_log.jsonl"
LEDGER_PATH = _ROOT / ".tmp" / "jev_ledger.jsonl"
UI_PATH = Path(__file__).with_name("jev_chatbot_ui.html")
_LOG_LOCK = threading.Lock()


@dataclass
class Answer:
    kind: str  # greeting | out_of_scope | clarify | answer | unsure | no_match | error
    text: str
    source: str = ""
    probability: float = 0.0
    alternatives: list[dict[str, Any]] = field(default_factory=list)
    cost: float = 0.0
    latency_ms: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _src(h: dict[str, Any]) -> str:
    return f"{h['file']}:{h['line_start']}-{h['line_end']}"


class JevChatbot:
    def __init__(self, corpus_dir: str | os.PathLike[str], ext: tuple[str, ...] = ("md", "txt"),
                 *, min_prob: float = MIN_PROB, name: str | None = None, workers: int = 8,
                 log_path: Path | None = LOG_PATH, ledger_path: Path | None = LEDGER_PATH) -> None:
        self.dir = Path(corpus_dir).resolve()
        if not self.dir.is_dir():
            raise ValueError(f"corpus dir not found: {corpus_dir}")
        self.ext = tuple(e.lstrip(".") for e in ext)
        self.min_prob = min_prob
        self.name = name or f"the {self.dir.name} docs"
        self.workers = workers
        self.log_path = log_path
        self.ledger_path = ledger_path
        self._lock = threading.Lock()
        self._chunks: list[dict[str, Any]] | None = None
        self._key: dict[str, float] | None = None
        self.index_builds = 0  # how many times chunks were rebuilt from source (tests)

    # ---- index ---------------------------------------------------------------------------
    def _files(self) -> list[Path]:
        out: set[Path] = set()
        for e in self.ext:
            for p in self.dir.rglob(f"*.{e}"):
                if p.is_file() and not any(part.startswith(".") or part == "node_modules"
                                           for part in p.relative_to(self.dir).parts):
                    out.add(p)
        return sorted(out)

    def _mtimes(self) -> dict[str, float]:
        return {p.relative_to(self.dir).as_posix(): p.stat().st_mtime for p in self._files()}

    def chunks(self) -> list[dict[str, Any]]:
        """Chunk index, cached in memory and on disk; rebuilt when any file mtime changes."""
        with self._lock:
            key = self._mtimes()
            if self._chunks is not None and key == self._key:
                return self._chunks
            idx = self.dir / INDEX_NAME
            if idx.is_file():
                try:
                    data = json.loads(idx.read_text(encoding="utf-8"))
                    if data.get("mtimes") == key and data.get("ext") == list(self.ext):
                        self._chunks, self._key = data["chunks"], key
                        return self._chunks
                except (OSError, ValueError, KeyError) as exc:
                    print(f"jev_chatbot: ignoring bad index: {exc}", file=sys.stderr)
            # Prefix the heading with the file stem so previews carry the doc's topic.
            self._chunks = [dict(c, heading=f"{Path(c['file']).stem}: {c.get('heading', '')}".rstrip(": "))
                            for c in jev_find.dir_chunks(self.dir, list(self.ext))]
            self._key = key
            self.index_builds += 1
            try:
                idx.write_text(json.dumps({"ext": list(self.ext), "mtimes": key,
                                           "chunks": self._chunks}), encoding="utf-8")
            except OSError as exc:
                print(f"jev_chatbot: could not write index: {exc}", file=sys.stderr)
            return self._chunks

    # ---- answer --------------------------------------------------------------------------
    def _fmt(self, key: str, **kw: Any) -> str:
        return CANNED[key].format(corpus=self.name, **kw)

    def _intent(self, q: str) -> tuple[str, jev_client.JevResult]:
        opts = {k: v.format(corpus=self.name) for k, v in INTENTS.items()}
        r = jev_client.decide({"task": f"route a chat message for a bot that only knows {self.name}",
                               "message": q},
                              {"intent": jev_client.choice("What kind of message is this?", opts)})
        intent = r.choice("intent") if r.ok else "question_about_corpus"
        return (intent if intent in INTENTS else "question_about_corpus"), r

    def _trim(self, q: str, text: str) -> tuple[str, jev_client.JevResult | None]:
        sents = [s.strip() for s in jev_find._SENT_RE.split(text) if s.strip()]
        if len(sents) <= 3:
            return text, None
        r = jev_client.decide({"task": "pick the sentences that answer the question", "question": q},
                              {"sent": jev_client.choice("Which sentence best answers the question?",
                                                         {str(k): s[:300] for k, s in enumerate(sents)})})
        probs = r.probabilities("sent") if r.ok else {}
        if not probs:
            return text, r
        best = sorted((k for k in probs if k.isdigit() and int(k) < len(sents)),
                      key=lambda k: -probs[k])
        if not best:
            return text, r
        top = int(best[0])
        keep = {top} | {int(k) for k in best[1:3] if probs[k] >= 0.15}
        if len(keep) == 1:  # add the neighbour so the answer reads as a passage
            keep.add(top + 1 if top + 1 < len(sents) else top - 1)
        return " ".join(sents[i] for i in sorted(keep)), r

    def ask(self, question: str) -> Answer:
        t0 = time.perf_counter()
        q = (question or "").strip()[:2000]
        cost = 0.0
        calls = 0
        if not q:
            ans = Answer("clarify", self._fmt("clarify"))
        else:
            intent, r = self._intent(q)
            cost += r.cost_usd
            calls += 1
            if intent != "question_about_corpus":
                ans = Answer(intent, self._fmt(intent))
            else:
                res = jev_find.find(q, self.chunks(), top=3, workers=self.workers,
                                    per_file=True, mark_sentence=False,
                                    abstain_below=0.0)
                cost += res["summary"]["cost_usd"]
                calls += res["summary"]["calls"]
                hits = res["hits"]
                alts = [{"source": _src(h), "heading": h.get("heading", ""),
                         "probability": h["probability"]} for h in hits[1:3]]
                if not hits:
                    errs = res["summary"]["errors"]
                    ans = (Answer("error", self._fmt("error", error=errs[0][:80])) if errs
                           else Answer("no_match", self._fmt("no_match")))
                elif hits[0]["probability"] < self.min_prob:
                    h = hits[0]
                    alts = [{"source": _src(x), "heading": x.get("heading", ""),
                             "probability": x["probability"]} for x in hits[1:3]]
                    ans = Answer("unsure", self._fmt("unsure", source=_src(h)) + " " + h["text"][:300],
                                 _src(h), h["probability"], alts)
                else:
                    h = hits[0]
                    text, tr = self._trim(q, h["text"])
                    if tr is not None:
                        cost += tr.cost_usd
                        calls += 1
                    ans = Answer("answer", text, _src(h), h["probability"], alts)
        ans.cost = round(cost, 6)
        ans.latency_ms = int((time.perf_counter() - t0) * 1000)
        self._log(q, ans, calls)
        return ans

    def _log(self, q: str, ans: Answer, calls: int) -> None:
        row = {"ts": time.strftime("%Y-%m-%dT%H:%M:%S"), "corpus": str(self.dir), "question": q,
               **ans.to_dict()}
        if self.log_path is not None:
            try:
                with _LOG_LOCK:
                    self.log_path.parent.mkdir(parents=True, exist_ok=True)
                    with open(self.log_path, "a", encoding="utf-8") as fh:
                        fh.write(json.dumps(row) + "\n")
            except OSError as exc:
                print(f"jev_chatbot: log write failed: {exc}", file=sys.stderr)
        if self.ledger_path is not None:
            jev_client.append_ledger({"caller": "jev_chatbot", "calls": calls, "cost_usd": ans.cost,
                                      "latency_ms": ans.latency_ms, "kind": ans.kind},
                                     self.ledger_path)


def render(a: Answer) -> str:
    out = [a.text]
    if a.source:
        out.append(f"  -- {a.source}  p={a.probability:.2f}")
    if a.alternatives:
        out.append("  " + CANNED["alternatives"] + "; ".join(
            f"{x['source']} ({x['probability']:.2f})" for x in a.alternatives))
    out.append(f"  [{a.kind}, {a.latency_ms} ms, ${a.cost:.6f}]")
    return "\n".join(out)


# ---- HTTP server -----------------------------------------------------------------------------
def make_server(bot: JevChatbot, port: int = 8765) -> ThreadingHTTPServer:
    """Build (not start) a localhost-only chat server. port=0 picks an ephemeral port."""
    ui = UI_PATH.read_bytes() if UI_PATH.is_file() else b"<h1>jev_chatbot_ui.html missing</h1>"

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, fmt: str, *args: Any) -> None:  # quiet
            return

        def _send(self, code: int, body: bytes, ctype: str) -> None:
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self) -> None:  # noqa: N802
            if self.path in ("/", "/index.html"):
                self._send(200, ui, "text/html; charset=utf-8")
            else:
                self._send(404, b"not found", "text/plain")

        def do_POST(self) -> None:  # noqa: N802
            if self.path != "/ask":
                self._send(404, b"not found", "text/plain")
                return
            try:
                n = min(int(self.headers.get("Content-Length", "0")), 65536)
                q = str(json.loads(self.rfile.read(n).decode("utf-8") or "{}").get("question", ""))
            except (ValueError, UnicodeDecodeError, AttributeError):
                self._send(400, b'{"error":"bad json"}', "application/json")
                return
            body = json.dumps(bot.ask(q).to_dict()).encode("utf-8")
            self._send(200, body, "application/json")

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Zero-LLM chatbot over a folder (Jev only).")
    ap.add_argument("--dir", required=True)
    ap.add_argument("--ext", default="md,txt")
    ap.add_argument("--min-prob", type=float, default=MIN_PROB)
    ap.add_argument("--name", default=None, help="corpus name used in canned replies")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--ask")
    g.add_argument("--repl", action="store_true")
    g.add_argument("--serve", action="store_true")
    ap.add_argument("--port", type=int, default=8765)
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args(argv)
    if not jev_client.available():
        print("jev_chatbot: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2
    bot = JevChatbot(a.dir, tuple(e for e in a.ext.split(",") if e), min_prob=a.min_prob, name=a.name)
    show = (lambda x: print(json.dumps(x.to_dict(), indent=2))) if a.json else (lambda x: print(render(x)))
    if a.ask:
        show(bot.ask(a.ask))
        return 0
    if a.repl:
        bot.chunks()
        print(f"jev_chatbot over {bot.dir} -- /quit to exit")
        while True:
            try:
                q = input("> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if q in ("/quit", "/exit"):
                break
            if q:
                show(bot.ask(q))
        return 0
    bot.chunks()
    srv = make_server(bot, a.port)
    print(f"jev_chatbot serving {bot.dir} on http://127.0.0.1:{srv.server_address[1]}/")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        srv.server_close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
