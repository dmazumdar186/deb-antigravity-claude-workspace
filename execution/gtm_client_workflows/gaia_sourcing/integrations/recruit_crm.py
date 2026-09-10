"""
Recruit CRM REST adapter -- Gaia Talent's ATS (client promise 2026-09-10:
"sourced candidates land in the CRM so consultants and Maddie [their inbound
screening agent] take over").

FACT-CHECK LOG (WebFetch/WebSearch against docs.recruitcrm.io,
help.recruitcrm.io, endgrate.com, pipedream.com; 2026-09-10). Read this before
trusting any endpoint below -- the docs site (docs.recruitcrm.io) is a
Stoplight single-page app, and a plain HTML fetch of it only ever returns the
page's <title>, never the rendered schema. Everything here that says VERIFIED
was confirmed some other way; everything that says ASSUMED was not, and is
the first thing to check against a real account before this client's first
live run.

VERIFIED
--------
- Base URL `https://api.recruitcrm.io/v1`. Two independent checks: (a) a
  direct WebFetch of `https://api.recruitcrm.io/v1` returned HTTP 401
  Unauthorized -- the path exists and is auth-gated, not a 404; (b)
  endgrate.com's worked example
  (endgrate.com/blog/using-the-recruit-crm-api-to-get-contacts-...) shows a
  live `GET https://api.recruitcrm.io/v1/contacts`.
- Auth header: `Authorization: Bearer <token>` (endgrate.com example;
  corroborated by help.recruitcrm.io/en/articles/4411980-recruit-crm-api-
  documentation, which also states the token is Business-plan-or-higher,
  Account-Owner-only, generated under Admin Settings -> API, and must be kept
  server-side).
- `GET /v1/jobs` lists every job regardless of status/archive state;
  `GET /v1/jobs/search` takes a `job_status` query parameter (WebSearch
  synthesis of help.recruitcrm.io/en/articles/11142291-commonly-used-api-
  endpoints-for-careers-page-part-1).
- Candidate creation switches to `multipart/form-data` "if you want to
  upload any file" (WebSearch synthesis of the docs.recruitcrm.io "Creates a
  new candidate" page); a JSON-only create/update uses
  `Content-Type: application/json`. This client never uploads a file, so it
  always sends JSON.
- Endpoint EXISTENCE (page titles resolved live on docs.recruitcrm.io/docs/
  rcrm-api-reference/, 2026-09-10): "Creates a new candidate", "Search for
  candidates", "Find candidate by slug", "Assign Candidate", "Get Job
  Associated Fields", "Creates a new task". Their exact HTTP verb / URL path
  / request-body field names could NOT be read from the rendered SPA.

ASSUMED -- treat a first live run as a contract test, not a known-good call
-------------------------------------------------------------------------
- `POST /v1/candidates` creates a candidate; `PUT /v1/candidates/{slug}`
  edits one; `GET /v1/candidates/search?email=...` (or `?linkedin_url=...`)
  finds one for dedupe. Response shape assumed to be `{"data": [...]}` for a
  list and to carry a `slug` identifying field on each record.
- Candidate JSON field names (`first_name`, `last_name`, `email`, `position`,
  `current_organization`, `city`, `candidate_source`, `linkedin_url`) follow
  Recruit CRM's documented UI field *labels*; the exact JSON keys were not
  read from a rendered schema. `card_to_payload` is the ONE place these are
  spelled, specifically so a wrong key is a one-line fix.
- `attach_to_job`'s shape (`POST /v1/candidates/{slug}/assign`, body
  `{"job_slug": ..., "status": ...}`) is a best guess from the endpoint's
  name; its existence is verified, its contract is not.
- There is no confirmed "add note to candidate" endpoint at all.
  `POST /v1/candidates/{slug}/notes` with `{"note": text}` is this client's
  best guess, flagged NOT_VERIFIED in `add_note`'s docstring.

Given how much of the contract is ASSUMED, `live=False` (dry-run + audit
log) is the hard default below, every write funnels through one small
`_write` method so the cap/audit/dry-run logic lives in exactly one place,
and every payload is built by one function per resource (`card_to_payload`,
`evidence_note`) so a wrong field name is a one-line fix rather than a
rewrite. I7 (Prodcraft never contacts candidates) is not at stake here: this
module writes CRM RECORDS, it never emails or messages a candidate.
"""

from __future__ import annotations

import json
import threading
import time
from dataclasses import dataclass, field as dataclass_field
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..core.config import PKG_ROOT, PRIVACY_NOTICE_URL, secret
from ..core.contracts import CandidateCard, ContactRecord, MovabilitySignal

DEFAULT_BASE_URL = "https://api.recruitcrm.io/v1"
DEFAULT_AUDIT_PATH = PKG_ROOT / "logs" / "recruit_crm_audit.jsonl"
MAX_WRITES_PER_RUN = 50
_MAX_RETRIES = 3
_DEFAULT_TIMEOUT_S = 30


class RecruitCRMError(RuntimeError):
    """A live call failed after retries, or returned an unrecoverable status."""


class WriteCapExceeded(RuntimeError):
    """The run has attempted more than MAX_WRITES_PER_RUN writes.

    Deliberately the same shape as core.providers.CostCeilingExceeded: it must
    NOT be caught by sync_delivery's per-item containment. A cap that a
    contained-per-item loop quietly retries around is not a cap.
    """


class NoDedupeKey(RuntimeError):
    """Refused a live write because there is nothing to dedupe this person on.

    Raised only when `live=True`. In dry-run there is no real write to
    protect against duplicating, so the guardrail does not apply -- the
    intended write is still logged to the audit file for review.
    """


@dataclass
class SyncReport:
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0
    lines: list[str] = dataclass_field(default_factory=list)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _retry_after_seconds(resp: Any) -> Optional[float]:
    headers = getattr(resp, "headers", None) or {}
    try:
        value = headers.get("Retry-After")
    except AttributeError:
        value = None
    if not value:
        return None
    try:
        return max(0.0, float(value))
    except (TypeError, ValueError):
        return None  # non-numeric Retry-After (an HTTP-date) -- fall back to backoff


def _split_name(full_name: str) -> tuple[str, str]:
    parts = [p for p in (full_name or "").split() if p]
    if len(parts) < 2:
        return (full_name or "").strip(), ""
    return parts[0], parts[-1]


# ---------------------------------------------------------------------------
# Payload builders -- the ONE place field names are spelled (see ASSUMED
# above). A wrong key found against a real account is a one-line fix here.
# ---------------------------------------------------------------------------


def card_to_payload(
    card: CandidateCard, contact: ContactRecord, source: str = "Prodcraft sourcing"
) -> dict:
    """Map a delivered candidate to a Recruit CRM candidate payload.

    Email is included ONLY when the status is verified/catch_all (I5: never
    hand the ATS an address labelled with more confidence than we have in
    it). A pattern_guess or missing email is omitted from the payload
    entirely and the status is put in the note instead (evidence_note),
    where a human reads it before ever sending to it.
    """
    first, last = _split_name(card.full_name)
    payload: dict[str, Any] = {
        "first_name": first,
        "last_name": last,
        "position": card.current_title,
        "current_organization": card.current_employer,
        "city": card.location,
        "candidate_source": source,
    }
    if contact.linkedin_url:
        payload["linkedin_url"] = str(contact.linkedin_url)
    if contact.email_status in ("verified", "catch_all") and contact.email:
        payload["email"] = contact.email
    return {k: v for k, v in payload.items() if v not in (None, "")}


def evidence_note(
    card: CandidateCard,
    contact: ContactRecord,
    movability: Optional[MovabilitySignal],
    collected_date: Optional[date] = None,
) -> str:
    """Plain-text note: tier, gates, top-3 evidence, email status, movability,
    and the fixed Art. 14 line (I6 -- injected verbatim, never generated).
    """
    lines = [
        "Sourced by Prodcraft for " + card.role_id + " -- Tier " + card.tier + ".",
        "",
        "Gate results:",
    ]
    for g in card.evaluation.gates:
        line = "  - " + g.gate_id + ": " + ("PASS" if g.passed else "FAIL")
        if g.note:
            line += " (" + g.note + ")"
        lines.append(line)

    lines.append("")
    lines.append("Top evidence:")
    if card.claims:
        for c in card.claims[:3]:
            lines.append(
                '  - [' + c.dimension + '] "' + c.evidence_quote.strip()
                + '" -- ' + str(c.source_url)
            )
    else:
        lines.append("  - (no verified claims on file)")

    lines.append("")
    email_bit = "Email status: " + contact.email_status
    if contact.email:
        email_bit += " (" + contact.email + ")"
    lines.append(email_bit)

    if movability is not None:
        lines.append(
            "Movability: " + movability.assessment + " -- "
            + (movability.rationale or "no rationale recorded")
        )
    else:
        lines.append("Movability: not assessed.")

    lines.append("")
    lines.append(
        "Art. 14 notice: " + PRIVACY_NOTICE_URL + " -- collected "
        + (collected_date or date.today()).isoformat()
        + " from public sources; outreach must include it."
    )
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------


class RecruitCRMClient:
    """Fail-safe by default: `live=False` logs every intended write to a
    JSONL audit file and sends nothing. Reads (dedupe lookups, list_jobs) go
    through `session` in either mode, so dry-run tests can exercise the full
    dedupe/patch logic against a fake session with no API key at all.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
        live: bool = False,
        session: Any = None,
        audit_path: Optional[Path] = None,
        max_writes_per_run: int = MAX_WRITES_PER_RUN,
        request_timeout_s: int = _DEFAULT_TIMEOUT_S,
        max_retries: int = _MAX_RETRIES,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.live = live
        self.max_writes_per_run = max_writes_per_run
        self.request_timeout_s = request_timeout_s
        self.max_retries = max_retries
        self.audit_path = Path(audit_path) if audit_path else DEFAULT_AUDIT_PATH
        self.audit_path.parent.mkdir(parents=True, exist_ok=True)

        self._writes_this_run = 0
        self._lock = threading.Lock()

        self._api_key: Optional[str] = None
        if live:
            key = (api_key or secret("RECRUIT_CRM_API_KEY", required=False) or "").strip()
            if not key:
                raise RuntimeError(
                    "RecruitCRMClient(live=True) requires a non-empty "
                    "RECRUIT_CRM_API_KEY (env or .env). Refusing to start "
                    "live with no credential rather than silently falling "
                    "back to dry-run."
                )
            self._api_key = key  # never logged, never printed, never audited

        self._session = session
        if self._session is None and live:
            import requests

            self._session = requests.Session()

    # -- transport -----------------------------------------------------------

    def _audit(self, record: dict) -> None:
        with self._lock:
            with self.audit_path.open("a", encoding="utf-8") as fh:
                fh.write(json.dumps(record, ensure_ascii=False, default=str) + "\n")

    def _http(
        self, method: str, path: str, *, params: Optional[dict] = None,
        json_body: Optional[dict] = None,
    ) -> Optional[dict]:
        """One real (or faked-in-tests) HTTP round trip. Returns parsed JSON
        or None. Retries 429/5xx up to `max_retries` times, honouring
        Retry-After; every attempt's status lands in the audit file.
        """
        if self._session is None:
            self._audit({
                "ts": _now_iso(), "kind": "skipped_no_session", "method": method,
                "path": path,
            })
            return None

        url = self.base_url + path
        headers = {"Accept": "application/json"}
        if self._api_key:
            headers["Authorization"] = "Bearer " + self._api_key
        if json_body is not None:
            headers["Content-Type"] = "application/json"

        last_exc: Optional[Exception] = None
        for attempt in range(self.max_retries + 1):
            try:
                resp = self._session.request(
                    method, url, headers=headers, params=params, json=json_body,
                    timeout=self.request_timeout_s,
                )
            except Exception as exc:  # network error -- retried, not swallowed
                last_exc = exc
                if attempt >= self.max_retries:
                    raise RecruitCRMError(
                        method + " " + path + " failed: " + repr(exc)
                    ) from exc
                time.sleep(min(30, 2 ** attempt))
                continue

            status = getattr(resp, "status_code", None)
            self._audit({
                "ts": _now_iso(), "kind": "response", "method": method,
                "path": path, "status": status, "attempt": attempt,
            })

            if status in (429, 500, 502, 503):
                if attempt >= self.max_retries:
                    raise RecruitCRMError(
                        method + " " + path + " failed after retries: HTTP "
                        + str(status)
                    )
                delay = _retry_after_seconds(resp)
                if delay is None:
                    delay = min(60, 2 ** attempt * 3)
                time.sleep(delay)
                continue

            if isinstance(status, int) and status >= 400:
                raise RecruitCRMError(
                    method + " " + path + " -> HTTP " + str(status) + ": "
                    + str(getattr(resp, "text", ""))[:300]
                )

            try:
                return resp.json()
            except Exception:
                return None

        raise RecruitCRMError(method + " " + path + " failed: " + repr(last_exc))

    def _check_and_count_write(self) -> None:
        with self._lock:
            self._writes_this_run += 1
            if self._writes_this_run > self.max_writes_per_run:
                raise WriteCapExceeded(
                    "This run has attempted " + str(self._writes_this_run)
                    + " writes, over the cap of " + str(self.max_writes_per_run)
                    + ". Raise max_writes_per_run deliberately, or find the "
                    "loop that is spending it."
                )

    def _write(
        self, kind: str, method: str, path: str, payload: dict, idempotency_key: str,
    ) -> Optional[dict]:
        """Every create/update/note/attach funnels through here.

        In dry-run this is the ENTIRE effect: one audit line, no network call.
        The write cap counts attempts in both modes, so `--live-crm` and a
        dry-run rehearsal exercise the identical cap behaviour.
        """
        self._check_and_count_write()
        if not self.live:
            self._audit({
                "ts": _now_iso(), "kind": kind, "method": method, "path": path,
                "idempotency_key": idempotency_key, "payload": payload,
                "dry_run": True,
            })
            return None
        return self._http(method, path, json_body=payload)

    # -- reads -----------------------------------------------------------

    def find_candidate(
        self, email: Optional[str] = None, linkedin_url: Optional[str] = None,
    ) -> Optional[dict]:
        """Dedupe lookup. Returns the first match, or None. ASSUMED endpoint
        shape -- see module docstring.
        """
        if not email and not linkedin_url:
            return None
        params: dict[str, str] = {}
        if email:
            params["email"] = email
        if linkedin_url:
            params["linkedin_url"] = linkedin_url
        data = self._http("GET", "/candidates/search", params=params)
        if not isinstance(data, dict):
            return None
        rows = data.get("data")
        if not rows:
            return None
        return rows[0]

    def list_jobs(self) -> list[dict]:
        data = self._http("GET", "/jobs")
        if not isinstance(data, dict):
            return []
        return list(data.get("data") or [])

    # -- writes -----------------------------------------------------------

    def upsert_candidate(
        self, card: CandidateCard, contact: ContactRecord, evidence_summary: str = "",
    ) -> dict:
        """Create if absent; if present, fill only EMPTY fields (never
        overwrite a consultant's own edits -- I5-adjacent honesty rule
        extended to the CRM: our guess must never clobber their fact).

        Returns `{"action": "created"|"updated"|"skipped", "candidate_id":
        ...}`. `candidate_id` is None in dry-run (nothing was actually
        created, so there is nothing real to chain add_note/attach_to_job
        onto -- sync_delivery relies on this to skip those follow-on calls).
        """
        has_email = contact.email_status in ("verified", "catch_all") and bool(contact.email)
        has_linkedin = bool(contact.linkedin_url)
        if self.live and not has_email and not has_linkedin:
            raise NoDedupeKey(
                card.full_name + ": no verified/catch-all email and no "
                "LinkedIn URL -- nothing to dedupe on, refusing to write live."
            )

        idem = (
            (contact.email if has_email else None)
            or (str(contact.linkedin_url) if has_linkedin else None)
            or card.person_id
        )

        existing = self.find_candidate(
            email=contact.email if has_email else None,
            linkedin_url=str(contact.linkedin_url) if has_linkedin else None,
        )

        if existing:
            slug = existing.get("slug") or existing.get("id")
            full_payload = card_to_payload(card, contact)
            patch = {k: v for k, v in full_payload.items() if not existing.get(k)}
            if patch:
                self._write("update", "PUT", "/candidates/" + str(slug), patch, idem)
                action = "updated"
            else:
                action = "skipped"  # already has every field we would send
            return {"action": action, "candidate_id": slug, "patched_fields": list(patch)}

        payload = card_to_payload(card, contact)
        result = self._write("create", "POST", "/candidates", payload, idem)
        candidate_id = None
        if isinstance(result, dict):
            candidate_id = result.get("slug") or result.get("id")
        return {"action": "created", "candidate_id": candidate_id, "payload": payload}

    def add_note(self, candidate_id: str, text: str) -> Optional[dict]:
        """NOT_VERIFIED endpoint shape -- see module docstring."""
        return self._write(
            "note", "POST", "/candidates/" + str(candidate_id) + "/notes",
            {"note": text}, candidate_id,
        )

    def attach_to_job(
        self, candidate_id: str, job_id: str, stage: Optional[str] = None,
    ) -> Optional[dict]:
        """NOT_VERIFIED endpoint shape -- see module docstring."""
        payload: dict[str, Any] = {"job_slug": job_id}
        if stage:
            payload["status"] = stage
        return self._write(
            "attach", "POST", "/candidates/" + str(candidate_id) + "/assign",
            payload, candidate_id,
        )


# ---------------------------------------------------------------------------
# Batch entry point
# ---------------------------------------------------------------------------


def sync_delivery(
    cards: list[CandidateCard],
    contacts: dict[str, ContactRecord],
    movability: dict[str, MovabilitySignal],
    client: RecruitCRMClient,
    job_ids: dict[str, str],
) -> SyncReport:
    """Push the delivered shortlist to Recruit CRM. Contains failures per
    candidate (I-parallel to run.run_all) EXCEPT WriteCapExceeded, which must
    propagate -- the same shape as core.providers.CostCeilingExceeded, for
    the same reason: a cap that gets quietly retried around one candidate at
    a time is not a cap.
    """
    report = SyncReport()
    for card in cards:
        contact = contacts.get(card.person_id)
        if contact is None:
            report.skipped += 1
            report.lines.append(card.full_name + ": skipped (no contact record)")
            continue

        mov = movability.get(card.person_id)
        try:
            result = client.upsert_candidate(card, contact)
        except NoDedupeKey as exc:
            report.skipped += 1
            report.lines.append(card.full_name + ": skipped (" + str(exc) + ")")
            continue
        except WriteCapExceeded:
            raise
        except Exception as exc:
            report.errors += 1
            report.lines.append(card.full_name + ": ERROR " + repr(exc)[:160])
            continue

        action = result.get("action", "skipped")
        if action == "created":
            report.created += 1
        elif action == "updated":
            report.updated += 1
        else:
            report.skipped += 1
        candidate_id = result.get("candidate_id")
        report.lines.append(
            card.full_name + ": " + action
            + (" (" + str(candidate_id) + ")" if candidate_id else "")
        )

        if candidate_id:
            try:
                client.add_note(candidate_id, evidence_note(card, contact, mov))
            except WriteCapExceeded:
                raise
            except Exception as exc:
                report.lines.append(
                    card.full_name + ": note failed (" + repr(exc)[:120] + ")"
                )

            job_id = job_ids.get(card.role_id)
            if not job_id:
                report.lines.append(
                    card.full_name + ": no Recruit CRM job id configured for "
                    + card.role_id + "; attach_to_job skipped"
                )
            else:
                try:
                    client.attach_to_job(candidate_id, job_id)
                except WriteCapExceeded:
                    raise
                except Exception as exc:
                    report.lines.append(
                        card.full_name + ": attach_to_job failed ("
                        + repr(exc)[:120] + ")"
                    )
        elif not client.live:
            report.lines.append(
                card.full_name + ": dry-run -- note/attach not attempted "
                "(no real candidate_id to chain onto; see the audit log for "
                "the intended create payload)"
            )

    return report
