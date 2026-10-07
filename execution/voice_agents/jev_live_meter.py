"""Live meeting meter: sort every sentence, as it is said, with Jev.

description: Feeds a live or recorded conversation sentence by sentence to Jev (ONE call per
             sentence, last 2 sentences as context) and sorts each into decision, action item,
             risk/blocker, question, commitment, factual claim, objection or small talk. Vague
             factual claims get a [check] marker (the BS-meter part). Prints one colour-coded
             line per sentence in spoken order and writes a rolling markdown recap.
             Directive: directives/voice_agents/jev_live_meter.md
inputs: exactly one source: --stdin (one utterance per line), --transcript path (.srt/.vtt/
        .json/plain with optional "[mm:ss] Speaker: text"; --replay sleeps per timestamps,
        --speed 10 goes faster) or --watch path (tail a growing captions file, 0.5 s poll;
        --idle-exit N stops after N idle seconds). --all, --no-color, --recap-every 60,
        --recap path, --workers 4, --dry-run. env OPENROUTER_API_KEY (or _TOKEN/_TOEKN).
outputs: stdout lines "[mm:ss] KIND(conf) text"; recap markdown (default
         .tmp/meeting_recap.md) every --recap-every s and at end; ledger row in
         .tmp/jev_ledger.jsonl (caller "jev_live_meter": sentences, cost_usd, p50_ms).
"""
from __future__ import annotations

import argparse
import re
import statistics
import sys
import threading
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterator, TextIO

from dotenv import load_dotenv

load_dotenv()

_ROOT = Path(__file__).resolve().parents[2]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from execution.modules import jev_client  # noqa: E402
from execution.video.jev_clip_finder import _CUE, _clean, _ts, parse_cues, parse_json  # noqa: E402

KINDS = {
    "decision": "a decision is made or agreed (we will go with X, agreed, let's do Y)",
    "action_item": "a task someone must do next (send, schedule, prepare, follow up)",
    "risk_or_blocker": "a risk, blocker, dependency or concern that could stop progress",
    "question": "a genuine question asked of the other party",
    "commitment_or_promise": "a promise or guarantee about outcomes, dates or performance",
    "factual_claim": "a statement of fact, number or result presented as true",
    "objection": "pushback, hesitation or disagreement (price, timing, fit)",
    "small_talk": "greetings, pleasantries, filler, acknowledgements",
}
CLAIM_LEVELS = ["unverifiable or vague", "general but plausible",
                "specific and checkable", "specific, checkable and sourced"]
QUESTIONS = {
    "kind": jev_client.choice("What is this sentence (the 'sentence' field) doing in the meeting?", KINDS),
    "owner_mentioned": jev_client.noul(
        "Does the sentence name or assign a specific person (including 'I' or 'you') as responsible?",
        "a specific person is named or assigned", "no specific owner"),
    "needs_followup": jev_client.noul(
        "Does this sentence create something someone must follow up on after the meeting?",
        "needs follow-up", "no follow-up needed"),
    "claim_confidence": jev_client.score(
        "If the sentence makes a factual claim, how specific and verifiable is it?", CLAIM_LEVELS),
}
BUCKETS = {"decision": "Decisions", "action_item": "Action items", "risk_or_blocker": "Risks",
           "objection": "Risks", "question": "Open questions", "commitment_or_promise": "Action items"}
SECTIONS = ["Decisions", "Action items", "Risks", "Open questions", "Claims to verify"]
COLORS = {"decision": "32", "action_item": "36", "risk_or_blocker": "31", "objection": "35",
          "question": "33", "commitment_or_promise": "34", "factual_claim": "37", "small_talk": "90"}
_LINE = re.compile(r"^\s*(?:\[((?:\d+:)?\d+:\d+(?:\.\d+)?)\])?\s*(?:([A-Z][\w .'-]{0,30}?):\s+)?(.*)$")
_SPLIT = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=[A-Z0-9\"'])")


# ---- parsing -----------------------------------------------------------------------------

def mmss(t: float | None) -> str:
    t = max(0.0, t or 0.0)
    return f"{int(t // 60):02d}:{int(t % 60):02d}"


def parse_line(line: str) -> dict[str, Any] | None:
    """`[mm:ss] Speaker: text` with timestamp and speaker optional."""
    m = _LINE.match(line.rstrip("\r\n"))
    if not m or not m.group(3).strip():
        return None
    return {"start": _ts(m.group(1)) if m.group(1) else None,
            "speaker": (m.group(2) or "").strip(), "text": _clean(m.group(3))}


def split_sentences(text: str, max_words: int = 40) -> list[str]:
    out: list[str] = []
    for s in _SPLIT.split(text.strip()):
        words = s.split()
        while len(words) > max_words:  # run-on caption with no punctuation
            out.append(" ".join(words[:max_words]))
            words = words[max_words:]
        if words:
            out.append(" ".join(words))
    return out


def load_utterances(path: Path) -> list[dict[str, Any]]:
    raw = path.read_text(encoding="utf-8", errors="replace")
    if path.suffix.lower() == ".json":
        segs = [{"start": s["start"], "speaker": "", "text": s["text"]} for s in parse_json(raw)]
    elif path.suffix.lower() in (".srt", ".vtt") or _CUE.search(raw):
        segs = []
        for s in parse_cues(raw):
            u = parse_line(s["text"]) or {"speaker": "", "text": s["text"]}
            segs.append({"start": s["start"], "speaker": u["speaker"], "text": u["text"]})
    else:
        segs = [u for u in (parse_line(ln) for ln in raw.splitlines()) if u]
    return segs


def tail_lines(path: Path, stop: threading.Event, poll_s: float = 0.5,
               idle_exit_s: float = 0.0) -> Iterator[str]:
    """Yield complete new lines appended to `path` (created later is fine) until `stop`."""
    pos, buf, last = 0, "", time.monotonic()
    while not stop.is_set():
        got = False
        if path.exists():
            with open(path, "r", encoding="utf-8", errors="replace") as fh:
                fh.seek(pos)
                chunk = fh.read()
                pos = fh.tell()
            if chunk:
                got = True
                buf += chunk
                *lines, buf = buf.split("\n")
                yield from (ln for ln in lines if ln.strip())
        now = time.monotonic()
        if got:
            last = now
        elif idle_exit_s and now - last >= idle_exit_s:
            break
        stop.wait(poll_s)
    if buf.strip():
        yield buf


# ---- classification ----------------------------------------------------------------------

def classify_sentence(text: str, context: list[str] | None = None, *,
                      decide: Callable[..., jev_client.JevResult] | None = None) -> dict[str, Any]:
    """One Jev call -> {kind, conf, owner, followup, claim, check, cost_usd, latency_ms, error}."""
    fn = decide or jev_client.decide
    res = fn({"sentence": text, "previous_sentences": list(context or [])[-2:]}, QUESTIONS)
    kind = res.choice("kind", "small_talk") if res.ok else "small_talk"
    claim = res.score("claim_confidence", 0.0)
    return {"kind": kind, "conf": res.confidence("kind", 0.0), "owner": res.noul("owner_mentioned") >= 0.5,
            "followup": res.noul("needs_followup") >= 0.5, "claim": claim,
            "check": kind == "factual_claim" and claim <= 1.0, "cost_usd": res.cost_usd,
            "latency_ms": res.latency_ms, "error": res.error}


def bucket_for(row: dict[str, Any]) -> str | None:
    if row.get("check"):
        return "Claims to verify"
    return BUCKETS.get(row.get("kind", ""))


def recap_markdown(rows: list[dict[str, Any]], title: str = "Meeting recap") -> str:
    groups: dict[str, list[str]] = {s: [] for s in SECTIONS}
    for r in rows:
        b = bucket_for(r)
        if not b:
            continue
        who = f" **{r['speaker']}**:" if r.get("speaker") else ""
        owner = " _(owner named)_" if b == "Action items" and r.get("owner") else ""
        groups[b].append(f"- [{mmss(r.get('t'))}]{who} {r['text']}{owner}")
    out = [f"# {title}", "", f"_{len(rows)} sentences_", ""]
    for s in SECTIONS:
        out += [f"## {s}", ""] + (groups[s] or ["- none"]) + [""]
    return "\n".join(out)


class Meter:
    """Classifies sentences in a worker pool; prints and records them strictly in spoken order."""

    def __init__(self, *, out: TextIO = sys.stdout, color: bool = True, show_all: bool = False,
                 workers: int = 4, dry_run: bool = False, decide: Callable[..., Any] | None = None) -> None:
        self.out, self.color, self.show_all, self.dry_run, self.decide = out, color, show_all, dry_run, decide
        self.pool = ThreadPoolExecutor(max_workers=max(1, workers))
        self.lock = threading.Lock()
        self.emit_lock = threading.RLock()  # serialises ordered draining across worker callbacks
        self.pending: deque[tuple[dict[str, Any], Future]] = deque()
        self.context: deque[str] = deque(maxlen=2)
        self.rows: list[dict[str, Any]] = []
        self.latencies: list[int] = []
        self.cost = 0.0
        self.errors = 0

    def feed(self, utt: dict[str, Any], t: float | None = None) -> None:
        start = utt.get("start") if utt.get("start") is not None else t
        for s in split_sentences(utt["text"]):
            base = {"t": start, "speaker": utt.get("speaker", ""), "text": s}
            if self.dry_run:
                self._emit({**base, "kind": "-", "conf": 0.0, "check": False})
                continue
            ctx = list(self.context)
            self.context.append(s)
            fut = self.pool.submit(classify_sentence, s, ctx, decide=self.decide)
            with self.emit_lock:
                self.pending.append((base, fut))
            fut.add_done_callback(lambda _f: self.drain(block=False))
        self.drain(block=False)

    def drain(self, block: bool) -> None:
        with self.emit_lock:
            while self.pending and (block or self.pending[0][1].done()):
                base, fut = self.pending.popleft()
                try:
                    res = fut.result()
                except Exception as exc:  # a throwing classifier must never stall the live feed
                    print(f"jev_live_meter: classify failed: {exc}", file=sys.stderr)
                    res = {"kind": "small_talk", "conf": 0.0, "owner": False, "followup": False,
                           "claim": 0.0, "check": False, "cost_usd": 0.0, "latency_ms": 0, "error": str(exc)}
                self._finish(base, res)

    def _finish(self, base: dict[str, Any], res: dict[str, Any]) -> None:
        row = {**base, **res}
        with self.lock:
            self.cost += row["cost_usd"]
            if row["error"]:
                self.errors += 1
            else:
                self.latencies.append(row["latency_ms"])
        self._emit(row)

    def _emit(self, row: dict[str, Any]) -> None:
        with self.lock:
            self.rows.append(row)
        if row["kind"] == "small_talk" and not self.show_all:
            return
        label = f"{row['kind'].upper()}({row['conf']:.2f})"
        if self.color and row["kind"] in COLORS:
            label = f"\033[{COLORS[row['kind']]}m{label}\033[0m"
        check = (" \033[41m[check]\033[0m" if self.color else " [check]") if row.get("check") else ""
        who = f"{row['speaker']}: " if row.get("speaker") else ""
        print(f"[{mmss(row['t'])}] {label}{check} {who}{row['text']}", file=self.out, flush=True)

    def write_recap(self, path: Path) -> None:
        with self.lock:
            rows = list(self.rows)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(recap_markdown(rows), encoding="utf-8")

    def close(self) -> dict[str, Any]:
        self.pool.shutdown(wait=True)
        self.drain(block=True)
        with self.lock:
            p50 = int(statistics.median(self.latencies)) if self.latencies else 0
            return {"sentences": len(self.rows), "cost_usd": round(self.cost, 6), "p50_ms": p50,
                    "errors": self.errors}


# ---- CLI ---------------------------------------------------------------------------------

def _source(a: argparse.Namespace, stop: threading.Event) -> Iterator[dict[str, Any]]:
    if a.transcript:
        utts = load_utterances(a.transcript)
        t0, first = time.monotonic(), next((u["start"] for u in utts if u["start"] is not None), 0.0)
        for u in utts:
            if a.replay and u["start"] is not None:
                wait = (u["start"] - first) / a.speed - (time.monotonic() - t0)
                if wait > 0:
                    time.sleep(wait)
            yield u
        return
    lines: Iterator[str] = sys.stdin if a.stdin else tail_lines(a.watch, stop, 0.5, a.idle_exit)
    for ln in lines:
        u = parse_line(ln)
        if u:
            yield u


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--stdin", action="store_true")
    src.add_argument("--transcript", type=Path)
    src.add_argument("--watch", type=Path)
    ap.add_argument("--replay", action="store_true")
    ap.add_argument("--speed", type=float, default=1.0)
    ap.add_argument("--idle-exit", type=float, default=0.0)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--no-color", action="store_true")
    ap.add_argument("--recap-every", type=float, default=60.0)
    ap.add_argument("--recap", type=Path, default=_ROOT / ".tmp" / "meeting_recap.md")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args(argv)
    if a.transcript and not a.transcript.is_file():
        print(f"error: transcript not found: {a.transcript}", file=sys.stderr)
        return 2
    if a.speed <= 0:
        print("error: --speed must be > 0", file=sys.stderr)
        return 2
    if not a.dry_run and not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    meter = Meter(color=not a.no_color, show_all=a.all or a.dry_run, workers=a.workers, dry_run=a.dry_run)
    stop = threading.Event()
    t0 = last_recap = time.monotonic()
    try:
        for u in _source(a, stop):
            meter.feed(u, t=time.monotonic() - t0)
            if time.monotonic() - last_recap >= a.recap_every:
                meter.write_recap(a.recap)
                last_recap = time.monotonic()
    except KeyboardInterrupt:
        stop.set()
    stats = meter.close()
    meter.write_recap(a.recap)
    print(f"\n{stats['sentences']} sentences | cost ${stats['cost_usd']:.4f} | p50 {stats['p50_ms']} ms"
          f" | errors {stats['errors']} | recap -> {a.recap}")
    if not a.dry_run:
        jev_client.append_ledger({"caller": "jev_live_meter", **stats})
    return 0


if __name__ == "__main__":
    sys.exit(main())
