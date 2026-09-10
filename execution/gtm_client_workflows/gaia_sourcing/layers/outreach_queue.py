"""
Outreach approval state machine (RADAR_CONTRACTS.md section E).

    draft -> pending_approval -> approved       -> marked_sent
                               -> rejected
                 pending_approval -> rejected

(2026-09-10: `pending_approval -> rejected` added -- a consultant rejecting
BEFORE ever approving is the common path in practice, not the exception the
original diagram's literal reading implied. See "Ambiguity resolved" below.)

Any transition not in that diagram raises `InvalidTransition`. This is a
record-keeping layer, not a sending layer: `mark_sent` records that a human
sent something OUTSIDE this pipeline (I7: Prodcraft/this codebase never
contacts a candidate) -- it has no side effect beyond writing the state and
the audit line. Nothing in this module, or anywhere in this package, makes an
outbound send call.

Persistence: one JSON object per campaign at
`run/<campaign_id>/outreach_queue.json`, keyed by draft_id. Every transition
ALSO appends one line to `logs/outreach_audit.jsonl` with a timestamp and the
acting user -- a second, append-only trail that survives even if the queue
file itself were ever hand-edited or corrupted.

Ambiguity resolved (documented per task instructions): RADAR_CONTRACTS.md
names the transition functions as `approve`, `reject`, `mark_sent` but the
diagram implies a fourth step (draft -> pending_approval) with no named
function. Added `submit_for_approval(draft_id, by)` for that step rather than
collapsing draft straight to pending_approval inside `create_draft`, so the
"a draft was written" and "a human/process put it up for approval" audit
events stay distinguishable.

2026-09-10 update: the diagram's literal `approved -> marked_sent | rejected`
reading (only `approved` can transition to `rejected`) was implemented first,
but real usage surfaced the far more common path -- a consultant rejects a
draft BEFORE ever approving it, while it still sits in `pending_approval`.
Forcing a reject through `approved` first would misrecord every one of those
as a momentary approval that never happened. `pending_approval -> rejected`
is now also allowed via `reject()`; `approved -> rejected` still works
unchanged. This is exactly the one-line `_TRANSITIONS` addition the original
note anticipated, not a redesign.

Opt-out (RADAR_CONTRACTS.md section E: "Checked at draft creation and at
sync") is enforced in `create_draft` -- a hit raises `OptedOut` and nothing is
queued. The CRM-sync half of that same check lives in
`integrations.recruit_crm.sync_delivery` (a separate owned surface).
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.config import CONFIG, PKG_ROOT
from ..core.contracts import ContactRecord, Person
from . import optout

DEFAULT_AUDIT_PATH = PKG_ROOT / "logs" / "outreach_audit.jsonl"

# The whole state machine, mechanically checkable: `to_state in
# _TRANSITIONS[from_state]` is the entire validity rule.
_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"pending_approval"},
    "pending_approval": {"approved", "rejected"},
    "approved": {"marked_sent", "rejected"},
    "marked_sent": set(),
    "rejected": set(),
}

_LOCK = threading.Lock()


class InvalidTransition(RuntimeError):
    """Attempted a state change not in the diagram above."""


class OptedOut(RuntimeError):
    """create_draft refused: the person is on the opt-out registry."""


@dataclass
class QueueEntry:
    draft_id: str
    person_id: str
    role_id: str
    state: str = "draft"
    history: list[dict] = field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _queue_path(campaign_id: Optional[str] = None, queue_path: Optional[Path] = None) -> Path:
    if queue_path:
        return Path(queue_path)
    cid = campaign_id or CONFIG.campaign_id
    d = PKG_ROOT / "run" / cid
    d.mkdir(parents=True, exist_ok=True)
    return d / "outreach_queue.json"


def _audit(record: dict, audit_path: Optional[Path] = None) -> None:
    p = Path(audit_path) if audit_path else DEFAULT_AUDIT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")


def _load_locked(path: Path) -> dict[str, dict]:
    """Lock-free read -- callers already hold `_LOCK` (see `_transition`).
    A bare `_load`/`_save` pair around a read-modify-write is not atomic:
    two threads calling `_transition` on the same draft can both read the
    same `current` state, both pass the allowed-transition check, and one
    write clobbers the other's, silently dropping a state change. `get()`
    and `create_draft` use this too, each under their own `_LOCK` hold.
    """
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        # A half-written queue file must fail closed (treat as empty, so the
        # next write recreates it cleanly) rather than crash every stage that
        # touches the queue.
        print("[outreach_queue] " + str(path) + " is not valid JSON -- treating as empty")
        return {}


def _save_locked(path: Path, data: dict[str, dict]) -> None:
    """Lock-free write -- callers already hold `_LOCK`. Writes via a temp
    file + os.replace so a crash or a concurrent reader never observes a
    half-written queue file (os.replace is atomic on POSIX and Windows)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp-" + str(os.getpid()))
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    os.replace(tmp, path)


def _load(path: Path) -> dict[str, dict]:
    with _LOCK:
        return _load_locked(path)


def _save(path: Path, data: dict[str, dict]) -> None:
    with _LOCK:
        _save_locked(path, data)


def create_draft(
    person: Person,
    contact: Optional[ContactRecord],
    role_id: str,
    draft_id: Optional[str] = None,
    campaign_id: Optional[str] = None,
    queue_path: Optional[Path] = None,
    audit_path: Optional[Path] = None,
) -> QueueEntry:
    """Queue one draft in state 'draft'. Refuses (`OptedOut`) if the person
    matches any entry in the opt-out registry -- checked here, not after.
    """
    hit = optout.is_opted_out(person=person, contact=contact)
    if hit is not None:
        _audit(
            {
                "ts": _now_iso(), "event": "draft_blocked_optout",
                "person_id": person.person_id, "role_id": role_id,
                "reason": hit.reason,
            },
            audit_path,
        )
        raise OptedOut(
            person.person_id + " is on the opt-out registry (" + hit.reason + ")"
        )

    did = draft_id or (person.person_id + ":" + role_id)
    path = _queue_path(campaign_id, queue_path)
    entry = QueueEntry(draft_id=did, person_id=person.person_id, role_id=role_id)
    with _LOCK:
        data = _load_locked(path)
        data[did] = asdict(entry)
        _save_locked(path, data)
    _audit(
        {
            "ts": _now_iso(), "event": "created", "draft_id": did,
            "person_id": person.person_id, "role_id": role_id, "by": "system",
        },
        audit_path,
    )
    return entry


def _transition(
    draft_id: str,
    to_state: str,
    by: str,
    extra: Optional[dict] = None,
    campaign_id: Optional[str] = None,
    queue_path: Optional[Path] = None,
    audit_path: Optional[Path] = None,
) -> dict:
    path = _queue_path(campaign_id, queue_path)
    with _LOCK:
        data = _load_locked(path)
        row = data.get(draft_id)
        if row is None:
            raise KeyError("no queued draft: " + draft_id)

        current = row.get("state", "draft")
        allowed = _TRANSITIONS.get(current, set())
        if to_state not in allowed:
            raise InvalidTransition(
                draft_id + ": cannot go " + current + " -> " + to_state
                + " (allowed from " + current + ": "
                + (", ".join(sorted(allowed)) or "nothing, terminal state") + ")"
            )

        event = {"ts": _now_iso(), "from": current, "to": to_state, "by": by}
        if extra:
            event.update(extra)
        row.setdefault("history", []).append(event)
        row["state"] = to_state
        data[draft_id] = row
        _save_locked(path, data)
    _audit({"draft_id": draft_id, **event}, audit_path)
    return row


def submit_for_approval(draft_id: str, by: str, **kw) -> dict:
    """draft -> pending_approval. Not named in RADAR_CONTRACTS.md's function
    list; added for the transition its own diagram implies. See module
    docstring's "Ambiguity resolved" note.
    """
    return _transition(draft_id, "pending_approval", by, **kw)


def approve(draft_id: str, by: str, **kw) -> dict:
    """pending_approval -> approved."""
    return _transition(draft_id, "approved", by, **kw)


def reject(draft_id: str, by: str, reason: str, **kw) -> dict:
    """approved -> rejected, or pending_approval -> rejected (a consultant
    rejecting before ever approving -- see module docstring's 2026-09-10
    update)."""
    return _transition(draft_id, "rejected", by, extra={"reason": reason}, **kw)


def mark_sent(draft_id: str, by: str, channel: str, **kw) -> dict:
    """approved -> marked_sent. Records that a human sent this OUTSIDE the
    pipeline. This call makes no outbound contact of any kind.
    """
    return _transition(draft_id, "marked_sent", by, extra={"channel": channel}, **kw)


def get(
    draft_id: str,
    campaign_id: Optional[str] = None,
    queue_path: Optional[Path] = None,
) -> Optional[dict]:
    """Read-only lookup, for tests and for a future console view."""
    return _load(_queue_path(campaign_id, queue_path)).get(draft_id)
