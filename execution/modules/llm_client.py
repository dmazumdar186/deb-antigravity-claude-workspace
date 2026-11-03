"""
llm_client.py
description: LLM wrapper. Claude models run on the operator's Claude subscription via the
             Claude Code CLI (opus-5-5/medium -> fable-5-1/low -> sonnet-5-5/high on usage
             limits); every other model goes to OpenRouter (OpenAI-compatible API).
inputs: model, system prompt, user message, max_tokens; env CLAUDE_VIA (subscription|openrouter,
        default subscription), OPENROUTER_API_KEY (non-Claude or escape hatch), LLM_BUDGET_USD.
outputs: Text response string; one JSONL row per call in .tmp/llm_ledger.jsonl.
"""

import json
import logging
import os
import shutil
import subprocess
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

logger = logging.getLogger(__name__)

# Cached clients keyed by base_url. Round-2 plan-skeptic Issue B: a bare
# singleton silently routes calls to whichever base_url was registered first.
# A dict keyed on base_url lets OR and Z.AI-direct coexist without cross-talk.
_clients: dict[str, object] = {}

MAX_RETRIES = 2
BASE_DELAY = 1.0

_OR_BASE_URL = "https://openrouter.ai/api/v1"

# Operator order 2026-09-21 (later): every Fable model runs at effort `low`,
# no `medium` anywhere, unless a caller passes `effort=` explicitly for a task.
# 2026-10-06: Jev-routed tiers — Sonnet 5.5 (bulk) and Opus 5.5 (standard) are
# tier targets again; all three families run at `low`. Haiku stays banned.
# OpenRouter carries it as `reasoning: {"effort": ...}`.
DEFAULT_EFFORT: dict[str, str] = {
    "anthropic/claude-fable-5.1": "low",
    "anthropic/claude-opus-5.5": "low",
    "anthropic/claude-sonnet-5.5": "low",
}


def default_effort(model: str) -> str | None:
    """Effort for a model id per the workspace rule; None when the rule has no opinion."""
    m = model.lower()
    if "claude-fable" in m:
        return DEFAULT_EFFORT["anthropic/claude-fable-5.1"]
    if "claude-opus" in m:
        return DEFAULT_EFFORT["anthropic/claude-opus-5.5"]
    if "claude-sonnet" in m:
        return DEFAULT_EFFORT["anthropic/claude-sonnet-5.5"]
    return None


_LEDGER_PATH = Path(__file__).resolve().parents[2] / ".tmp" / "llm_ledger.jsonl"

# USD per 1M tokens (input, output). Approximate; ledger cost_usd preferred.
# Used only when OpenRouter's response carries no usage.cost, so the budget
# guard still trips. Unknown models assume the dearest tier (fail-closed).
# Published Anthropic list prices (claude-api skill table, cached 2026-10-06).
PRICE_TABLE: dict[str, tuple[float, float]] = {
    "anthropic/claude-fable-5.1": (10.00, 50.00),
    "anthropic/claude-opus-5.5": (4.00, 20.00),
    "anthropic/claude-sonnet-5.5": (2.00, 10.00),
}
_DEAREST = max(PRICE_TABLE.values())

# Cumulative spend (USD) for this process, across all calls.
_spent_usd: float = 0.0


class LLMBudgetExceeded(RuntimeError):
    """Raised before a call once this process has spent >= its LLM budget."""


def _budget(budget_usd: float | None) -> float:
    if budget_usd is not None:
        return float(budget_usd)
    raw = os.environ.get("LLM_BUDGET_USD", "")
    try:
        return float(raw) if raw else 5.0
    except ValueError:
        return 5.0


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    pin, pout = PRICE_TABLE.get(model, _DEAREST)
    return (prompt_tokens * pin + completion_tokens * pout) / 1_000_000


def _record(model: str, base_url: str, resp: object, latency_ms: int) -> None:
    """Update the process spend counter and append one ledger row. Never raises."""
    global _spent_usd
    usage = getattr(resp, "usage", None)
    pt = int(getattr(usage, "prompt_tokens", 0) or 0)
    ct = int(getattr(usage, "completion_tokens", 0) or 0)
    cost = getattr(usage, "cost", None)
    if cost is None and isinstance(getattr(usage, "model_extra", None), dict):
        cost = usage.model_extra.get("cost")
    try:
        cost = float(cost) if cost is not None else None
    except (TypeError, ValueError):
        cost = None
    _spent_usd += cost if cost is not None else _estimate_cost(model, pt, ct)
    try:
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "caller": os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "",
            "model": model,
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "base_url_host": urlparse(base_url).hostname,
        }
        _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception as exc:  # ledger must never break a call
        logger.debug("ledger write failed: %s", exc)


# ---------------------------------------------------------------------------
# Claude via the operator's subscription (Claude Code CLI). Operator decision
# 2026-11-03: Claude calls never go to OpenRouter. Chain order is the operator's;
# a tier is left only when it hits a usage limit. One place to edit.
# ---------------------------------------------------------------------------
CLAUDE_CHAIN: tuple[tuple[str, str], ...] = (
    ("claude-opus-5-5", "medium"),
    ("claude-fable-5-1", "low"),
    ("claude-sonnet-5-5", "high"),
)
CLAUDE_CLI_TIMEOUT_S = 600

_LIMIT_MARKERS = (
    "usage limit", "limit reached", "hit your limit", "rate limit",
    "quota", "overloaded", "529", "429",
)
_exhausted: set[str] = set()  # tiers that hit a limit; sticky for this process
_exhausted_lock = threading.Lock()


class ClaudeLimitReached(RuntimeError):
    """Every tier of CLAUDE_CHAIN hit its subscription usage limit."""


def is_claude_model(model: str) -> bool:
    return "claude" in (model or "").lower()


def _claude_via_subscription(model: str) -> bool:
    return is_claude_model(model) and os.environ.get("CLAUDE_VIA", "subscription").lower() != "openrouter"


def _is_limit_error(text: str) -> bool:
    t = (text or "").lower()
    return any(m in t for m in _LIMIT_MARKERS)


def _claude_binary() -> str:
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError(
            "Claude Code CLI not found on PATH. Install Claude Code and log in (`claude` then /login) "
            "so scripts can use the subscription, or set CLAUDE_VIA=openrouter to bill OpenRouter."
        )
    return exe


def _record_subscription(model: str, effort: str, data: dict, latency_ms: int) -> None:
    """Ledger row for a subscription call. No money spent, so _spent_usd is untouched."""
    try:
        usage = data.get("usage") or {}
        row = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "caller": os.path.basename(sys.argv[0]) if sys.argv and sys.argv[0] else "",
            "model": model,
            "effort": effort,
            "billing": "subscription",
            "prompt_tokens": int(usage.get("input_tokens", 0) or 0),
            "completion_tokens": int(usage.get("output_tokens", 0) or 0),
            "cost_usd": None,
            "notional_usd": data.get("total_cost_usd"),
            "latency_ms": latency_ms,
            "base_url_host": "claude-code-cli",
        }
        _LEDGER_PATH.parent.mkdir(parents=True, exist_ok=True)
        with _LEDGER_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(row) + "\n")
    except Exception as exc:  # ledger must never break a call
        logger.debug("ledger write failed: %s", exc)


def _claude_cli_completion(system: str, user: str, timeout: int = CLAUDE_CLI_TIMEOUT_S) -> str:
    """Run one prompt down CLAUDE_CHAIN on the subscription. Returns the result text.

    Moves to the next tier only on a usage/rate/quota/overload error and marks
    that tier exhausted for the rest of the process. Any other failure raises.
    """
    exe = _claude_binary()
    for model, effort in CLAUDE_CHAIN:
        with _exhausted_lock:
            if model in _exhausted:
                continue
        # Prompt goes via stdin: a positional prompt after `--tools ""` is eaten.
        # `--setting-sources ""` + `--strict-mcp-config` keep workspace hooks,
        # plugins and MCP servers out of script calls. `--bare` is NOT used: it
        # skips the subscription login.
        cmd = [
            exe, "-p",
            "--model", model,
            "--effort", effort,
            "--output-format", "json",
            "--no-session-persistence",
            "--setting-sources", "",
            "--strict-mcp-config",
            "--tools", "",
            "--system-prompt", system,
        ]
        t0 = time.monotonic()
        try:
            proc = subprocess.run(
                cmd, input=user, capture_output=True, text=True,
                encoding="utf-8", errors="replace", timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(f"Claude CLI timed out after {timeout}s on {model}") from exc
        latency_ms = int((time.monotonic() - t0) * 1000)
        out = (proc.stdout or "").strip()
        try:
            data = json.loads(out)
        except json.JSONDecodeError:
            data = None
        if not isinstance(data, dict):
            blob = f"{out}\n{proc.stderr or ''}"
            if _is_limit_error(blob):
                logger.warning("Claude tier %s hit a usage limit; moving down the chain", model)
                with _exhausted_lock:
                    _exhausted.add(model)
                continue
            raise RuntimeError(
                f"Claude CLI returned no JSON (exit {proc.returncode}) on {model}: {blob.strip()[:300]}"
            )
        if data.get("is_error") or proc.returncode != 0:
            msg = str(data.get("result") or data.get("subtype") or "") + " " + (proc.stderr or "")
            if _is_limit_error(msg):
                logger.warning("Claude tier %s hit a usage limit; moving down the chain", model)
                with _exhausted_lock:
                    _exhausted.add(model)
                continue
            raise RuntimeError(f"Claude CLI error on {model}: {msg.strip()[:300]}")
        _record_subscription(model, effort, data, latency_ms)
        return str(data.get("result") or "").strip()
    raise ClaudeLimitReached(
        "All Claude subscription tiers are at their usage limit "
        f"({', '.join(m for m, _ in CLAUDE_CHAIN)}). Wait for the limit to reset, "
        "or set CLAUDE_VIA=openrouter to pay per call."
    )


def _get_client(base_url: str = _OR_BASE_URL):
    if base_url not in _clients:
        from openai import OpenAI

        # Cloud sessions expose the key as OPENROUTER_API_TOEKN (sic); jev_client
        # already reads both. Found 2026-11-03: every cloud call failed here.
        api_key = os.environ.get("OPENROUTER_API_KEY") or os.environ.get("OPENROUTER_API_TOEKN", "")
        if not api_key:
            raise RuntimeError("OPENROUTER_API_KEY (or OPENROUTER_API_TOEKN) not set")
        _clients[base_url] = OpenAI(api_key=api_key, base_url=base_url)
    return _clients[base_url]


def chat_completion(
    system: str,
    user_message: str,
    # Operator audit 2026-11-03: unspecified calls are per-row work, so the
    # default is the bulk tier (Sonnet 5.5, effort low). Fable/Opus only when a
    # caller passes model= explicitly. Haiku stays banned.
    model: str = "anthropic/claude-sonnet-5.5",
    max_tokens: int = 150,
    base_url: str = _OR_BASE_URL,
    effort: str | None = None,
    budget_usd: float | None = None,
) -> str:
    """Single-turn chat completion.

    Claude models (any id containing "claude") run on the subscription via the
    Claude Code CLI chain unless CLAUDE_VIA=openrouter; the chain picks the
    model, not `model`. Everything else goes to OpenRouter (or Z.AI-direct if
    base_url is overridden), retrying on rate limit / server errors."""
    if _claude_via_subscription(model):
        # max_tokens/effort cannot be passed to the CLI (no flag; effort is the
        # chain's). Ignored on this path. No $ budget check: no money is spent.
        return _claude_cli_completion(system, user_message)
    from openai import APIStatusError, RateLimitError

    budget = _budget(budget_usd)
    if _spent_usd >= budget:
        raise LLMBudgetExceeded(
            f"LLM budget exhausted: spent ${_spent_usd:.4f} >= ${budget:.2f} this process "
            "(set LLM_BUDGET_USD or pass budget_usd= to change)"
        )
    client = _get_client(base_url)
    last_exc = None
    # Disable reasoning/thinking for Z.AI GLM models — they default to "thinking
    # mode" which burns the entire output budget on internal reasoning before
    # emitting a single visible token. On long creative outputs this manifests
    # as `content=None` + `finish_reason='length'`. The OR-canonical way to
    # opt out is `reasoning: { enabled: false }` via extra_body.
    extra: dict | None = None
    if model.lower().startswith("z-ai/"):
        extra = {"reasoning": {"enabled": False}}
    resolved_effort = effort or default_effort(model)
    if resolved_effort is not None:
        extra = {"reasoning": {"effort": resolved_effort}}
    # Ask OpenRouter to return per-call cost in usage.cost (ledger + guard).
    # Only sent to OpenRouter; other base_urls may reject the unknown field.
    if base_url == _OR_BASE_URL:
        extra = {**(extra or {}), "usage": {"include": True}}
    for attempt in range(MAX_RETRIES + 1):
        try:
            create_kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "messages": [
                    {"role": "system", "content": system},
                    {"role": "user", "content": user_message},
                ],
            }
            if extra is not None:
                create_kwargs["extra_body"] = extra
            t0 = time.monotonic()
            resp = client.chat.completions.create(**create_kwargs)
            _record(model, base_url, resp, int((time.monotonic() - t0) * 1000))
            # Defensive extraction: some providers (notably GLM via OR on long
            # outputs) can return message.content=None alongside a non-empty
            # finish_reason. Treat empty as empty rather than AttributeError.
            if not resp.choices:
                return ""
            msg = resp.choices[0].message
            content = getattr(msg, "content", None) or ""
            finish = getattr(resp.choices[0], "finish_reason", None)
            if not content and finish:
                logger.warning("Empty content from %s, finish_reason=%r", model, finish)
            return content.strip()
        except RateLimitError as e:
            last_exc = e
            if attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning("Rate limited (attempt %d/%d), retrying in %.1fs", attempt + 1, MAX_RETRIES + 1, delay)
                time.sleep(delay)
        except APIStatusError as e:
            # Billing errors (402) and other 4xx never retry; only 429 and 5xx do.
            last_exc = e
            if e.status_code >= 500 and attempt < MAX_RETRIES:
                delay = BASE_DELAY * (2 ** attempt)
                logger.warning("Server error %d (attempt %d/%d), retrying in %.1fs", e.status_code, attempt + 1, MAX_RETRIES + 1, delay)
                time.sleep(delay)
            else:
                raise
    if last_exc is None:
        raise RuntimeError("chat_completion exhausted retries with no exception captured")
    raise last_exc
