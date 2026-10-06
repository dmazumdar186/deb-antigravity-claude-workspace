"""Shared Jev client — TypeSafe's System One decision model via OpenRouter's Decisions API.

description: One-call typed decisions (noul / choice / score) from Jev through OpenRouter.
             Batches many questions over one `state`, fails open on any error, and reports
             cost from the response `usage` block. Used by the Jev router hook, the skill
             picker, the email gate and the note linker (directives/infrastructure/jev.md).
inputs: env OPENROUTER_API_KEY (also accepts OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN);
        state (str | dict | list), questions dict in Decisions-API shape.
outputs: JevResult(answers, cost_usd, input_tokens, model, latency_ms, error). `answers` is
         `{}` and `error` is set when the call fails — callers must treat that as "no opinion".

API reference: POST https://openrouter.ai/api/alpha/decisions, model `typesafe/jev-1.13`
(alias `~typesafe/jev-latest`), 32k-token context (state + questions), input-only billing
($0.042 / MTok on 2026-10-06), output free. Chat-completion SDKs cannot talk to it.
"""
from __future__ import annotations

import json
import os
import sys
import time
from dataclasses import dataclass, field
from typing import Any

import requests

JEV_ENDPOINT = "https://openrouter.ai/api/alpha/decisions"
JEV_MODEL = "typesafe/jev-1.13"
JEV_MODEL_LATEST = "~typesafe/jev-latest"
JEV_CONTEXT_TOKENS = 32_000
# ~4 chars per token; keep a margin for the questions block.
JEV_MAX_STATE_CHARS = 100_000
DEFAULT_TIMEOUT_S = 8.0
_KEY_VARS = ("OPENROUTER_API_KEY", "OPENROUTER_API_TOKEN", "OPENROUTER_API_TOEKN")


@dataclass
class JevResult:
    answers: dict[str, Any] = field(default_factory=dict)
    cost_usd: float = 0.0
    input_tokens: int = 0
    model: str = ""
    latency_ms: int = 0
    error: str | None = None

    @property
    def ok(self) -> bool:
        return self.error is None and bool(self.answers)

    # Typed accessors -- every one returns a safe default when the answer is missing or malformed.
    def _field(self, name: str, key: str, default: Any) -> Any:
        a = self.answers.get(name) or {}
        val = a.get(key, default)
        if isinstance(default, float):
            try:
                return float(val)
            except (TypeError, ValueError):
                return default
        return str(val) if val is not None else default

    def noul(self, name: str, default: float = 0.0) -> float:
        return self._field(name, "noul", default)

    def choice(self, name: str, default: str = "") -> str:
        return self._field(name, "choice", default)

    def confidence(self, name: str, default: float = 0.0) -> float:
        return self._field(name, "confidence", default)

    def probabilities(self, name: str) -> dict[str, float]:
        a = self.answers.get(name) or {}
        out: dict[str, float] = {}
        for k, v in (a.get("probabilities") or {}).items():
            try:
                out[str(k)] = float(v)
            except (TypeError, ValueError):
                continue
        return out

    def score(self, name: str, default: float = 0.0) -> float:
        return self._field(name, "score", default)


def api_key() -> str:
    """Return the OpenRouter key from the first set env var (empty string if none)."""
    for var in _KEY_VARS:
        val = os.environ.get(var, "").strip()
        if val:
            return val
    return ""


def available() -> bool:
    return bool(api_key())


# ---- question builders (keep call sites readable) -------------------------------------

def noul(instructions: str, true: str, false: str) -> dict[str, Any]:
    return {"type": "noul", "instructions": instructions, "criteria": {"true": true, "false": false}}


def choice(instructions: str, options: dict[str, str]) -> dict[str, Any]:
    """`options` maps option key -> one-line description. Add a `none` key when abstaining is valid."""
    return {"type": "choice", "instructions": instructions, "criteria": dict(options)}


def score(instructions: str, levels: list[str]) -> dict[str, Any]:
    """`levels` is the ordered scale, lowest first; the answer is a float index into it."""
    return {"type": "score", "instructions": instructions, "criteria": list(levels)}


# ---- the call ---------------------------------------------------------------------------

def decide(
    state: str | dict[str, Any] | list[Any],
    questions: dict[str, dict[str, Any]],
    *,
    model: str = JEV_MODEL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    session_id: str | None = None,
) -> JevResult:
    """Ask Jev every question in `questions` about `state` in ONE request.

    Fails open: any exception, HTTP error or malformed body returns a JevResult with
    `error` set and empty answers. Never raises. State longer than JEV_MAX_STATE_CHARS
    is truncated (strings) so the 32k context is not blown.
    """
    key = api_key()
    if not key:
        return JevResult(error="no OpenRouter key (set OPENROUTER_API_KEY)")
    if not questions:
        return JevResult(error="no questions")
    if isinstance(state, str) and len(state) > JEV_MAX_STATE_CHARS:
        state = state[:JEV_MAX_STATE_CHARS]
    body: dict[str, Any] = {"model": model, "state": state, "questions": questions}
    if session_id:
        body["session_id"] = session_id[:256]
    t0 = time.perf_counter()
    try:
        resp = requests.post(
            JEV_ENDPOINT,
            headers={
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://github.com/dmazumdar186/deb-antigravity-claude-workspace",
                "X-Title": "deb-antigravity-claude-workspace",
            },
            data=json.dumps(body),
            timeout=timeout_s,
        )
    except requests.RequestException as exc:
        return JevResult(error=f"request failed: {exc.__class__.__name__}: {exc}",
                         latency_ms=int((time.perf_counter() - t0) * 1000))
    latency = int((time.perf_counter() - t0) * 1000)
    if resp.status_code != 200:
        return JevResult(error=f"HTTP {resp.status_code}: {resp.text[:300]}", latency_ms=latency)
    try:
        data = resp.json()
    except ValueError:
        return JevResult(error="non-JSON response", latency_ms=latency)
    answers = data.get("answers")
    if not isinstance(answers, dict):
        return JevResult(error=f"no answers in response: {str(data)[:300]}", latency_ms=latency)
    usage = data.get("usage") or {}
    return JevResult(
        answers=answers,
        cost_usd=float(usage.get("cost", 0.0) or 0.0),
        input_tokens=int(usage.get("input_tokens", 0) or 0),
        model=str(data.get("model", model)),
        latency_ms=latency,
    )


def decide_many(
    states: list[str | dict[str, Any]],
    questions: dict[str, dict[str, Any]],
    *,
    model: str = JEV_MODEL,
    timeout_s: float = DEFAULT_TIMEOUT_S,
    workers: int = 8,
) -> list[JevResult]:
    """Same questions over many states, in parallel threads. Order is preserved.

    Jev answers in ~100-500 ms, so a 100-item batch finishes in about a second with 8 workers.
    """
    from concurrent.futures import ThreadPoolExecutor

    def _one(s: str | dict[str, Any]) -> JevResult:
        return decide(s, questions, model=model, timeout_s=timeout_s)

    with ThreadPoolExecutor(max_workers=max(1, workers)) as pool:
        return list(pool.map(_one, states))


def append_ledger(entry: dict[str, Any], path: str | os.PathLike[str] = ".tmp/jev_ledger.jsonl") -> None:
    """Append one usage row (cost, tokens, latency, caller) for `jev status`. Never raises."""
    try:
        p = os.fspath(path)
        os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
        entry = {"ts": int(time.time()), **entry}
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, ensure_ascii=False) + "\n")
    except OSError as exc:  # ledger is best-effort telemetry; never fail the caller
        print(f"jev ledger write skipped: {exc}", file=sys.stderr)


if __name__ == "__main__":  # smoke test: python3 execution/modules/jev_client.py
    r = decide(
        {"prompt": "find the file path where the jev router script lives"},
        {
            "tier": choice("How much model capacity does this request need?", {
                "tiny": "greeting or one-line follow-up",
                "bulk": "mechanical search, reformat, lookup",
                "standard": "routine coding or writing",
                "hard": "architecture, subtle debugging, judgement",
            }),
            "is_question": noul("Is the user asking a question?", "ends in a question or asks for info", "gives an instruction"),
        },
    )
    print(json.dumps(r.__dict__, indent=2))
