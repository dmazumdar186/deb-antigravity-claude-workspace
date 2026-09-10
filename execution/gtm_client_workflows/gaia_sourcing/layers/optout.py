"""
Opt-out registry (RADAR_CONTRACTS.md section E).

`logs/optout.jsonl` -- one JSON object per opt-out event: person_id, email,
linkedin_url, reason, at, source. Matching on ANY of the three identifiers is
the whole point: a candidate might reply from a personal address that never
appears on their CRM record, or opt out via LinkedIn after being contacted by
email -- either one must block every channel, not just the one it arrived on.

Nothing here sends anything or drafts anything. This module only answers
"has this person told us to stop" and records it when they do.

I7-adjacent note: `optout_from_reply` is the ONE bridge from
`layers/replies.ReplyVerdict` into this registry, and it lives here, not in
layers/replies.py, so replies.py stays a pure classifier with zero registry
side effects (RADAR_CONTRACTS.md I3: deterministic code decides; a classifier
that also writes state on the side is a much harder thing to reason about
under I3 than "classify" and "record" being two separate calls a caller makes
in sequence).
"""

from __future__ import annotations

import json
import threading
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from ..core.config import PKG_ROOT
from ..core.contracts import ContactRecord, Person, ReplyVerdict

DEFAULT_OPTOUT_PATH = PKG_ROOT / "logs" / "optout.jsonl"

_LOCK = threading.Lock()


@dataclass
class OptOut:
    person_id: Optional[str]
    email: Optional[str]
    linkedin_url: Optional[str]
    reason: str
    at: str
    source: str


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _norm(value: Optional[str]) -> Optional[str]:
    """Case- and whitespace-insensitive match key. An email or a LinkedIn URL
    that differs only in case must still hit the same opt-out row.
    """
    if isinstance(value, str) and value.strip():
        return value.strip().lower()
    return None


def add_optout(
    person_id: Optional[str] = None,
    email: Optional[str] = None,
    linkedin_url: Optional[str] = None,
    reason: str = "",
    source: str = "manual",
    path: Optional[Path] = None,
) -> OptOut:
    """Append one opt-out event. Requires at least one identifier -- an
    opt-out entry that matches nothing can never block anything, so refusing
    it here is cheaper than debugging a "why didn't this block?" later.
    """
    if not (person_id or email or linkedin_url):
        raise ValueError(
            "add_optout needs at least one of person_id/email/linkedin_url"
        )
    record = OptOut(
        person_id=person_id,
        email=_norm(email),
        linkedin_url=_norm(linkedin_url),
        reason=reason,
        at=_now_iso(),
        source=source,
    )
    p = Path(path) if path else DEFAULT_OPTOUT_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    with _LOCK:
        with p.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(asdict(record), ensure_ascii=False) + "\n")
    return record


def _load_all(path: Optional[Path] = None) -> list[dict]:
    p = Path(path) if path else DEFAULT_OPTOUT_PATH
    if not p.exists():
        return []
    out: list[dict] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            # One corrupt line (a truncated write from a crashed process)
            # must not take the whole opt-out check down -- that would fail
            # OPEN on the exact file whose entire job is to fail closed.
            print("[optout] skipping unparseable line in " + str(p))
            continue
    return out


def load_registry(path: Optional[Path] = None) -> list[dict]:
    """Public alias of `_load_all`, for a caller that wants to load the
    registry ONCE and pass it into several `is_opted_out(rows=...)` calls
    (e.g. integrations.recruit_crm.sync_delivery) instead of re-reading the
    file once per candidate.
    """
    return _load_all(path)


def is_opted_out(
    person: Optional[Person] = None,
    contact: Optional[ContactRecord] = None,
    person_id: Optional[str] = None,
    path: Optional[Path] = None,
    rows: Optional[list[dict]] = None,
) -> Optional[OptOut]:
    """RADAR_CONTRACTS.md section E signature: `is_opted_out(person,
    contact) -> Optional[OptOut]`, keyed on any of person_id/email/
    linkedin_url. `person_id` is accepted as an extra optional keyword for
    callers that only have a bare id (e.g. integrations.recruit_crm.
    sync_delivery, which works off CandidateCard + ContactRecord, not a full
    Person) -- it is folded into the same lookup, never a separate code path.

    `rows`, when given, is used INSTEAD of re-reading the registry file --
    for a caller (integrations.recruit_crm.sync_delivery) that checks many
    candidates in one batch and would otherwise re-read and re-parse the same
    JSONL file once per candidate. Pass `load_registry(path)`'s result.
    """
    pid = person_id or getattr(person, "person_id", None)
    email = _norm(getattr(contact, "email", None))
    li_raw = getattr(contact, "linkedin_url", None) or getattr(person, "linkedin_url", None)
    linkedin = _norm(str(li_raw) if li_raw is not None else None)
    if not (pid or email or linkedin):
        return None
    for row in (rows if rows is not None else _load_all(path)):
        if pid and row.get("person_id") == pid:
            return OptOut(**row)
        if email and row.get("email") == email:
            return OptOut(**row)
        if linkedin and row.get("linkedin_url") == linkedin:
            return OptOut(**row)
    return None


def optout_from_reply(
    person_id: str,
    contact: Optional[ContactRecord],
    verdict: ReplyVerdict,
    path: Optional[Path] = None,
) -> Optional[OptOut]:
    """Called by run.py (or a test) after `layers.replies.classify_reply`
    returns a verdict with `opt_out=True`. Never called from within
    layers/replies.py itself -- see module docstring.

    A no-op (returns None, writes nothing) when the verdict did not set
    opt_out, so a caller can pass every verdict through unconditionally
    without an `if verdict.opt_out:` guard of its own.
    """
    if not verdict.opt_out:
        return None
    email = getattr(contact, "email", None) if contact else None
    linkedin_url = getattr(contact, "linkedin_url", None) if contact else None
    return add_optout(
        person_id=person_id,
        email=str(email) if email else None,
        linkedin_url=str(linkedin_url) if linkedin_url else None,
        reason="reply: " + verdict.label + " (\"" + verdict.evidence + "\")",
        source="reply_classifier",
        path=path,
    )
