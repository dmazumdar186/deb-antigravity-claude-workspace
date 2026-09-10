"""
eval/outcomes.py -- outreach outcome tracking (RADAR_CONTRACTS.md section F).

Deterministic bookkeeping only (I3, RADAR_CONTRACTS.md top rule -- no LLM
call anywhere in this module): `record_outcome` appends one line to
`logs/outcomes.jsonl`, `weekly_report` aggregates reply/conversation rate
per template and per movability bucket, and `template_weights` turns that
aggregate into rotation weights.

Ties to `.claude/rules/automation-boundaries.md`'s template-pool rule:
customer-facing message automation draws from a pre-approved,
human-written template pool; fuzzy variables fill slots; the pool itself
stays human-authored. `template_weights` changes ONLY how often the
rotation picks an EXISTING template id -- it never generates, edits, or
retires template text, and it never returns a weight of exactly 0 (a
template with zero weight is, in effect, silently withdrawn -- that is a
human call, not this function's).
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional, Sequence

from pydantic import BaseModel, Field

OutcomeEvent = Literal[
    "draft", "approved", "sent", "reply", "conversation", "interview",
    "placement", "opt_out",
]
MovabilityBucket = Literal["high", "medium", "low", "unknown"]

PKG_ROOT = Path(__file__).resolve().parents[1]
OUTCOMES_LOG = PKG_ROOT / "logs" / "outcomes.jsonl"

_WRITE_LOCK = threading.Lock()


class Outcome(BaseModel):
    person_id: str
    template_id: str
    movability_bucket: MovabilityBucket
    event: OutcomeEvent
    at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    by: str = ""


def record_outcome(
    person_id: str,
    template_id: str,
    movability_bucket: str,
    event: str,
    at: Optional[datetime] = None,
    by: str = "",
    path: Path = OUTCOMES_LOG,
) -> Outcome:
    """Append one outcome event. Never mutates or removes a prior line --
    the log is the audit trail `weekly_report` reads back from scratch."""
    outcome = Outcome(
        person_id=person_id,
        template_id=template_id,
        movability_bucket=movability_bucket,
        event=event,
        at=at or datetime.now(timezone.utc),
        by=by,
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    with _WRITE_LOCK:
        with path.open("a", encoding="utf-8") as fh:
            fh.write(outcome.model_dump_json() + "\n")
    return outcome


def load_outcomes(path: Path = OUTCOMES_LOG) -> list[Outcome]:
    if not path.exists():
        return []
    out: list[Outcome] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            out.append(Outcome(**json.loads(line)))
        except Exception:
            # A malformed line must not take down reporting for every other
            # row already logged; it is simply not counted.
            continue
    return out


_CONVERSATION_EVENTS = {"conversation", "interview", "placement"}


def _rates(rows: Sequence[Outcome], keyfn) -> dict[str, dict]:
    sent: dict[str, int] = {}
    replies: dict[str, int] = {}
    conversations: dict[str, int] = {}
    for o in rows:
        k = keyfn(o)
        if o.event == "sent":
            sent[k] = sent.get(k, 0) + 1
        elif o.event == "reply":
            replies[k] = replies.get(k, 0) + 1
        elif o.event in _CONVERSATION_EVENTS:
            conversations[k] = conversations.get(k, 0) + 1

    out: dict[str, dict] = {}
    for k, n_sent in sent.items():
        out[k] = {
            "sent": n_sent,
            "reply_rate": replies.get(k, 0) / n_sent,
            "conversation_rate": conversations.get(k, 0) / n_sent,
        }
    # A key with replies/conversations logged but no "sent" row is
    # incomplete data (a message that was never marked sent cannot have a
    # rate against it) -- surfaced with null rates rather than silently
    # dropped or divided by zero.
    for k in set(replies) | set(conversations):
        out.setdefault(k, {"sent": 0, "reply_rate": None, "conversation_rate": None})
    return out


def weekly_report(
    path: Path = OUTCOMES_LOG, outcomes: Optional[list[Outcome]] = None
) -> dict:
    """Reply and conversation rate per template_id and per movability_bucket.

    Rate denominators are "sent" counts (you cannot reply to a message that
    was never sent). `outcomes` lets a caller pass an already-loaded list
    (tests; `template_weights` below) instead of re-reading the log file.
    """
    rows = outcomes if outcomes is not None else load_outcomes(path)
    return {
        "by_template_id": _rates(rows, lambda o: o.template_id),
        "by_movability_bucket": _rates(rows, lambda o: o.movability_bucket),
    }


MIN_TEMPLATE_WEIGHT = 0.1
MAX_TEMPLATE_WEIGHT = 1.0


def template_weights(
    template_ids: Sequence[str],
    path: Path = OUTCOMES_LOG,
    outcomes: Optional[list[Outcome]] = None,
) -> dict[str, float]:
    """Rotation weights for an existing, human-authored template pool.

    Bounded to [MIN_TEMPLATE_WEIGHT, MAX_TEMPLATE_WEIGHT] and never zero --
    a zero weight is a de facto retirement of a template, which is a human
    editorial call this function does not make. A template with no "sent"
    history yet gets the neutral top weight, so a newly added template is
    not starved before it has ever had a chance to be sent. Weight scales on
    conversation_rate (0.7) then reply_rate (0.3) as a tiebreaker, because
    a conversation is the outcome that actually matters and a reply alone
    can be a polite no.
    """
    if not template_ids:
        return {}
    report = weekly_report(path, outcomes)["by_template_id"]
    weights: dict[str, float] = {}
    for tid in template_ids:
        stats = report.get(tid)
        if stats is None or stats.get("sent", 0) == 0:
            weights[tid] = MAX_TEMPLATE_WEIGHT
            continue
        score = (stats["conversation_rate"] or 0.0) * 0.7 + (stats["reply_rate"] or 0.0) * 0.3
        weight = MIN_TEMPLATE_WEIGHT + score * (MAX_TEMPLATE_WEIGHT - MIN_TEMPLATE_WEIGHT)
        weights[tid] = max(MIN_TEMPLATE_WEIGHT, min(MAX_TEMPLATE_WEIGHT, weight))
    return weights
