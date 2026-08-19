"""
Anthropic client wrapper with cache-aware cost accounting and a hard ceiling.

Two rules from ~/.claude/rules/ are load-bearing here:

- python-hardening rule 4: pricing must carry all four token classes
  (input / cache_write / cache_read / output). Flat-rate accounting
  over-estimates 5-10x under prompt caching and would trip the cost ceiling
  spuriously.
- currency-eur: every figure that reaches the operator is in EUR. The
  provider bills in USD, so conversion happens at the reporting boundary
  and the USD original is kept alongside for reconciliation.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path
from typing import Any, Optional

import anthropic

from .config import CONFIG, PRICING, USD_TO_EUR, secret

_LOCK = threading.Lock()
_CLIENT: Optional[anthropic.Anthropic] = None


class CostCeilingExceeded(RuntimeError):
    """Raised when a run would exceed CONFIG.max_cost_eur.

    Deliberately fatal: SPEC.md section 14 wants the run to hard-fail rather
    than silently spend through a retry loop at 3am.
    """


class CostTracker:
    def __init__(self, ceiling_eur: float, log_path: Optional[Path] = None):
        self.ceiling_eur = ceiling_eur
        self.log_path = log_path
        self.total_usd = 0.0
        self.calls = 0
        self._lock = threading.Lock()

    def record(self, model: str, usage: Any, label: str = "") -> float:
        price = PRICING.get(model)
        if price is None:
            # Unknown model: charge at the most expensive known rate rather
            # than silently costing zero, so the ceiling still bites.
            price = max(PRICING.values(), key=lambda p: p["output"])

        inp = getattr(usage, "input_tokens", 0) or 0
        out = getattr(usage, "output_tokens", 0) or 0
        c_read = getattr(usage, "cache_read_input_tokens", 0) or 0
        c_write = getattr(usage, "cache_creation_input_tokens", 0) or 0

        usd = (
            inp * price["input"]
            + out * price["output"]
            + c_read * price["cache_read"]
            + c_write * price["cache_write"]
        ) / 1_000_000

        with self._lock:
            self.total_usd += usd
            self.calls += 1
            total_eur = self.total_usd * USD_TO_EUR
            if self.log_path is not None:
                self.log_path.parent.mkdir(parents=True, exist_ok=True)
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(
                        json.dumps(
                            {
                                "ts": time.time(),
                                "label": label,
                                "model": model,
                                "input_tokens": inp,
                                "output_tokens": out,
                                "cache_read_tokens": c_read,
                                "cache_write_tokens": c_write,
                                "cost_eur": round(usd * USD_TO_EUR, 6),
                                "cumulative_eur": round(total_eur, 4),
                            }
                        )
                        + "\n"
                    )

        if total_eur > self.ceiling_eur:
            raise CostCeilingExceeded(
                "Run cost EUR "
                + format(total_eur, ".2f")
                + " exceeded the ceiling of EUR "
                + format(self.ceiling_eur, ".2f")
                + ". Raise RunConfig.max_cost_eur deliberately, or fix the loop."
            )
        return usd * USD_TO_EUR

    @property
    def total_eur(self) -> float:
        return self.total_usd * USD_TO_EUR

    def summary(self) -> dict:
        return {
            "calls": self.calls,
            "cost_eur": round(self.total_eur, 4),
            "ceiling_eur": self.ceiling_eur,
        }


TRACKER = CostTracker(CONFIG.max_cost_eur, CONFIG.run_dir / "logs" / "costs.jsonl")


def client() -> anthropic.Anthropic:
    global _CLIENT
    with _LOCK:
        if _CLIENT is None:
            _CLIENT = anthropic.Anthropic(api_key=secret("ANTHROPIC_API_KEY"))
    return _CLIENT


def call_tool(
    model: str,
    system: str,
    user: str,
    tool: dict,
    label: str = "",
    max_tokens: int = 8000,
    temperature: float = 0.0,
    max_retries: int = 3,
) -> Optional[dict]:
    """Structured-output call via forced tool use.

    Returns the tool input dict, or None if the model declined to call the
    tool. Never free-text-then-parse (SPEC.md section 4).
    """
    tool_name = tool["name"]
    last_err: Optional[Exception] = None

    for attempt in range(max_retries):
        try:
            resp = client().messages.create(
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                tools=[tool],
                tool_choice={"type": "tool", "name": tool_name},
                messages=[{"role": "user", "content": user}],
            )
        except anthropic.RateLimitError as exc:
            last_err = exc
            time.sleep(2 ** attempt * 3)
            continue
        except anthropic.APIStatusError as exc:
            last_err = exc
            if getattr(exc, "status_code", 0) in (500, 502, 503, 529):
                time.sleep(2 ** attempt * 2)
                continue
            raise
        except Exception as exc:
            last_err = exc
            time.sleep(2 ** attempt)
            continue

        TRACKER.record(model, resp.usage, label=label)
        for block in resp.content:
            if getattr(block, "type", "") == "tool_use" and block.name == tool_name:
                return dict(block.input)
        # Model returned prose instead of a tool call. Not retryable in a
        # useful way -- surfaced as None so the caller drops the item rather
        # than fabricating a result.
        return None

    if last_err is not None:
        raise RuntimeError(
            "LLM call '" + label + "' failed after "
            + str(max_retries) + " attempts: " + repr(last_err)
        )
    return None
