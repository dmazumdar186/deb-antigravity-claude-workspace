"""
L-recut -- pure, deterministic re-cut logic for the Gaia radar console
(RADAR_CONTRACTS.md section G). Lives in the package (not under `execution/`)
specifically so this module never imports `modal`: `execution/modal_radar.py`
at the workspace's execution root is a thin wrapper around the two handlers
below, deployed with `modal deploy execution/modal_radar.py`.

No LLM call anywhere in this module -- `recut()` is pure deterministic Python
over the same `layers/gates.py` the main pipeline uses, so a re-cut costs
EUR 0 and returns in milliseconds. Read-only against extract.json/
validate.json: never writes them, never calls run.py's acquire_run_lock
("never touches stage files, never takes the run lock").

-- Storage: Modal Volume vs. a mounted/local run dir -----------------------
Deployed, stage files are read from a Modal Volume named "gaia-radar-run",
mounted at /data/run inside the container -- one volume shared by every
campaign, one subdirectory per campaign_id. Populate it once per run with
`modal volume put gaia-radar-run run/<campaign_id> <campaign_id>` from a
machine that has the real `run/` tree (or wire a small sync step into
run.py's own stages once that lands -- not done here, see the note in
`_run_dir_for`).

Running locally (no Modal container), /data/run does not exist, so
`_run_dir_for` falls back to this package's own `run/<campaign_id>/`
directory -- the same RUN_DIR every other stage in run.py reads and writes.

`approve_handler` does a direct JSONL append rather than the real approval
state machine in `layers/outreach_queue.py` (draft -> pending_approval ->
approved -> marked_sent | rejected), because this endpoint predates that
state machine landing and needs to keep working against whatever the console
already wired up. Once the console calls into outreach_queue.py directly,
this should read/write through that module instead of living in parallel
indefinitely.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator

from ..core.config import PKG_ROOT, secret
from ..core.contracts import JobSpec, Person, ValidatedClaim
from ..roles import ROLES
from . import gates as gates_layer

# ---------------------------------------------------------------------------
# Endpoint auth -- a shared-secret header, checked in a pure function so the
# test suite exercises it without Modal or a real HTTP request.
#
# Deploy-time setup (this endpoint has no other secrets, see the module and
# execution/modal_radar.py docstrings):
#   modal secret create radar-endpoint-token RADAR_ENDPOINT_TOKEN=<value>
# and attach that secret to the Modal function(s) in execution/modal_radar.py.
#
# If RADAR_ENDPOINT_TOKEN is unset (locally or on Modal), BOTH endpoints
# refuse every request -- a live re-cut/approve endpoint with no configured
# token is not "open", it is a misconfiguration, and failing loudly here is
# cheaper than a silent open write endpoint.
# ---------------------------------------------------------------------------

_AUTH_HEADER = "x-radar-token"


def _check_auth(headers: Optional[dict]) -> Optional[dict]:
    """Return an error dict on auth failure, else None."""
    expected = secret("RADAR_ENDPOINT_TOKEN", required=False)
    if not expected:
        return {"error": "endpoint token not configured"}
    headers = headers or {}
    got = None
    for k, v in headers.items():
        if isinstance(k, str) and k.lower() == _AUTH_HEADER:
            got = v
            break
    if got != expected:
        return {"error": "invalid or missing X-Radar-Token"}
    return None


# ---------------------------------------------------------------------------
# campaign_id / role_id validation -- python-hardening rule 3 (LLM/external-
# supplied path components must be format-checked AND containment-checked
# before ever touching the filesystem). These ids end up as path segments in
# `_run_dir_for`, so both checks apply even though the regex alone already
# excludes "/" and therefore ".." traversal and absolute paths.
# ---------------------------------------------------------------------------

_ID_RE = re.compile(r"[A-Za-z0-9._-]{1,64}")


def _valid_id(value: object) -> bool:
    if not isinstance(value, str) or not _ID_RE.fullmatch(value):
        return False
    roots = [PKG_ROOT / "run", Path(os.environ.get("GAIA_RADAR_VOLUME_PATH", "/data/run"))]
    for root in roots:
        try:
            candidate = (root / value).resolve()
            if not candidate.is_relative_to(root.resolve()):
                return False
        except (OSError, ValueError):
            return False
    return True


# ---------------------------------------------------------------------------
# brief_overrides validation -- a pydantic model so a malformed override
# returns {"error": ...} rather than an unhandled exception/traceback.
# ---------------------------------------------------------------------------


class BriefOverrides(BaseModel):
    max_grade: Optional[str] = None
    max_years: Optional[int] = None
    min_years: Optional[int] = None
    counties: list[str] = Field(default_factory=list)
    strict_location: bool = False

    @field_validator("max_grade")
    @classmethod
    def _grade_is_known(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and v not in gates_layer._GRADE_ORDER:
            raise ValueError(
                "max_grade must be one of " + ", ".join(gates_layer._GRADE_ORDER)
                + " or null"
            )
        return v

# ---------------------------------------------------------------------------
# Pure function: no I/O, no LLM, cost 0. Both the endpoint and the tests call
# this directly (RADAR_CONTRACTS.md section G).
# ---------------------------------------------------------------------------


def _apply_overrides(spec: JobSpec, overrides: dict) -> JobSpec:
    """Return a COPY of `spec` with `overrides` folded into its hard_gates.

    Never mutates `spec` itself, and therefore never mutates a module-level
    JobSpec such as roles.ROLE1/ROLE2 -- unlike run.py's
    `_apply_brief_overrides`, which deliberately mutates ROLE1/ROLE2 in
    place because it runs before the real pipeline stages. A live re-cut
    endpoint serving concurrent requests for different hypothetical briefs
    cannot share that mutation without one request's override leaking into
    another's result.
    """
    spec = spec.model_copy(deep=True)
    counties = overrides.get("counties")
    for gate in spec.hard_gates:
        if gate.check == "seniority_ceiling":
            if overrides.get("max_grade"):
                gate.params["max_grade"] = overrides["max_grade"]
            if overrides.get("max_years") is not None:
                gate.params["max_years"] = overrides["max_years"]
        elif gate.check == "seniority_years":
            if overrides.get("min_years") is not None:
                gate.params["min_years"] = overrides["min_years"]
        elif gate.check == "located_ie":
            if counties is not None:
                gate.params["counties"] = list(counties)
            if overrides.get("strict_location"):
                gate.params["require_direct_evidence"] = True
                gate.params["treat_unknown_as"] = "fail"

    # Keep spec.seniority_band / spec.location_rule in lockstep with the
    # hard_gates params just edited above. gates.py's individual gate checks
    # (check_seniority, check_located_ie) only ever read hard_gates params,
    # but layers.gates.composition_violations and eval/scorecard's judge of
    # the delivered set read spec.seniority_band/spec.location_rule directly
    # (RADAR_CONTRACTS.md) -- leaving those two fields on the old brief while
    # the gates ran the overridden one means a re-cut's own "did this violate
    # the brief" check judges against a brief the re-cut never actually used.
    if spec.seniority_band is not None:
        band_updates: dict = {}
        if overrides.get("max_grade"):
            band_updates["max_grade"] = overrides["max_grade"]
        if overrides.get("max_years") is not None:
            band_updates["max_years"] = overrides["max_years"]
        if overrides.get("min_years") is not None:
            band_updates["min_years"] = overrides["min_years"]
        if band_updates:
            spec.seniority_band = spec.seniority_band.model_copy(update=band_updates)
    if spec.location_rule is not None:
        loc_updates: dict = {}
        if counties is not None:
            loc_updates["counties"] = list(counties)
        if overrides.get("strict_location"):
            loc_updates["require_direct_evidence"] = True
            loc_updates["treat_unknown_as"] = "fail"
        if loc_updates:
            spec.location_rule = spec.location_rule.model_copy(update=loc_updates)
    return spec


def recut(extract: dict, validate: dict, spec: JobSpec, overrides: dict) -> dict:
    """Re-run the L7 gate layer in memory for `spec.role_id`, overridden.

    `extract` / `validate` are exactly stage_extract's and stage_validate's
    saved dicts (persons/claims, claims/stats) -- the same shape run.py
    writes to run/<c>/extract.json and validate.json. Deterministic: same
    inputs, same overrides, same output, every time.

    Returns {"survivors": [...], "excluded": [...], "per_gate_counts": {...}}.
    The endpoint wraps this with a "recut_id" and persists an audit copy;
    this function itself writes nothing.
    """
    working_spec = _apply_overrides(spec, overrides or {})
    role_id = spec.role_id

    persons_raw: dict = extract.get("persons", {}) or {}
    claims_raw: list = validate.get("claims", []) or []

    by_person: dict[str, list[ValidatedClaim]] = {}
    for c in claims_raw:
        pid = c.get("subject_person_id")
        if pid not in persons_raw:
            continue
        try:
            by_person.setdefault(pid, []).append(ValidatedClaim(**c))
        except Exception as exc:
            # A malformed cached claim degrades that one claim, never the
            # whole re-cut -- same containment principle as run.py's
            # run_all() for the equivalent per-item failure.
            print("recut: skipping malformed cached claim for " + str(pid)
                  + ": " + repr(exc)[:120])
            continue

    survivors: list[dict] = []
    excluded: list[dict] = []
    per_gate_counts: dict[str, int] = {}
    person_fields = set(Person.model_fields)

    for pid, rec in persons_raw.items():
        if rec.get("role_id") != role_id:
            continue
        try:
            person = Person(**{k: v for k, v in rec.items() if k in person_fields})
        except Exception:
            continue
        pclaims = by_person.get(pid, [])
        results = gates_layer.run_gates(person, pclaims, working_spec)
        tier = gates_layer.assign_tier(pclaims, results, working_spec)
        failed = [r.gate_id for r in results if not r.passed]
        for gate_id in failed:
            per_gate_counts[gate_id] = per_gate_counts.get(gate_id, 0) + 1
        if tier == "EXCLUDED":
            excluded.append({"person_id": pid, "gates_failed": failed})
        else:
            survivors.append({
                "person_id": pid,
                "full_name": rec.get("full_name", pid),
                "tier": tier,
            })

    return {
        "survivors": survivors,
        "excluded": excluded,
        "per_gate_counts": per_gate_counts,
    }


# ---------------------------------------------------------------------------
# Storage root
# ---------------------------------------------------------------------------


def _run_dir_for(campaign_id: str) -> Path:
    """Modal Volume mount when present (deployed), else this package's run/.

    A future integration point once the pipeline pushes a fresh extract/
    validate snapshot into the volume at the end of `gate`, so a live re-cut
    never serves data staler than the last local run. Not built here --
    this endpoint only reads whatever is already in the volume or the local
    run/ directory.
    """
    volume_root = Path(os.environ.get("GAIA_RADAR_VOLUME_PATH", "/data/run"))
    candidate = volume_root / campaign_id
    if candidate.exists():
        return candidate
    return PKG_ROOT / "run" / campaign_id


def _load_json(path: Path) -> Optional[dict]:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as exc:
        print("recut: could not read " + str(path) + ": " + repr(exc))
        return None


# ---------------------------------------------------------------------------
# Handlers -- plain functions, importable and testable without Modal. The
# thin Modal wrapper (execution/modal_radar.py) does nothing more than route
# an HTTP POST body into these.
# ---------------------------------------------------------------------------


def recut_handler(
    payload: dict, headers: Optional[dict] = None, run_dir: Optional[Path] = None,
) -> dict:
    auth_err = _check_auth(headers)
    if auth_err is not None:
        return auth_err

    campaign_id = payload.get("campaign_id")
    role_id = payload.get("role_id")
    if not campaign_id or not role_id:
        return {"error": "campaign_id and role_id are required"}
    if not _valid_id(campaign_id):
        return {"error": "invalid campaign_id"}
    if not _valid_id(role_id):
        return {"error": "invalid role_id"}

    raw_overrides = payload.get("brief_overrides") or {}
    try:
        overrides = BriefOverrides(**raw_overrides).model_dump()
    except Exception as exc:
        return {"error": "invalid brief_overrides: " + str(exc)[:300]}

    spec = ROLES.get(role_id)
    if spec is None:
        return {"error": "unknown role_id: " + str(role_id)}

    effective_run_dir = run_dir if run_dir is not None else _run_dir_for(campaign_id)
    extract = _load_json(effective_run_dir / "extract.json")
    validate = _load_json(effective_run_dir / "validate.json")
    if extract is None or validate is None:
        # Never echo the resolved path back in the response body -- this is
        # an operator-facing tool, but it is still an HTTP endpoint, and a
        # resolved filesystem path is not something an error body should
        # leak.
        return {
            "error": "extract.json/validate.json not found for campaign "
            + str(campaign_id)
        }

    result = recut(extract, validate, spec, overrides)
    import uuid

    recut_id = str(uuid.uuid4())
    out = {"recut_id": recut_id, **result}

    recuts_dir = effective_run_dir / "recuts"
    try:
        recuts_dir.mkdir(parents=True, exist_ok=True)
        (recuts_dir / (recut_id + ".json")).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
        )
    except OSError as exc:
        # A read-only or full filesystem must not fail the HTTP response --
        # the caller still gets a correct re-cut result even if the audit
        # copy fails to persist. Logged, never swallowed silently.
        print("recut: could not persist recut record: " + repr(exc))

    return out


_VALID_APPROVE_ACTIONS = {"approve", "reject", "approved", "rejected"}


def approve_handler(
    payload: dict, headers: Optional[dict] = None, run_dir: Optional[Path] = None,
) -> dict:
    """Append one operator decision to run/<c>/approvals.jsonl.

    See module docstring -- a direct JSONL append rather than routing
    through `layers/outreach_queue.py`'s state machine, kept only until the
    console calls into that module directly.
    """
    auth_err = _check_auth(headers)
    if auth_err is not None:
        return auth_err

    campaign_id = payload.get("campaign_id")
    draft_id = payload.get("draft_id")
    action = payload.get("action")
    by = payload.get("by") or "unknown"
    if not campaign_id or not draft_id:
        return {"error": "campaign_id and draft_id are required"}
    if not _valid_id(campaign_id):
        return {"error": "invalid campaign_id"}
    if action not in _VALID_APPROVE_ACTIONS:
        return {"error": "action must be one of " + ", ".join(sorted(_VALID_APPROVE_ACTIONS))}

    run_dir = run_dir if run_dir is not None else _run_dir_for(campaign_id)
    record = {
        "draft_id": draft_id,
        "campaign_id": campaign_id,
        "by": by,
        "action": action,
        "at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        run_dir.mkdir(parents=True, exist_ok=True)
        with (run_dir / "approvals.jsonl").open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record, ensure_ascii=False) + "\n")
    except OSError as exc:
        return {"error": "could not write approvals.jsonl: " + repr(exc)}

    return {"status": "recorded", **record}
