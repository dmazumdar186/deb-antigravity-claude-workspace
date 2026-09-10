"""
description: Live re-cut + local approval recording for the Gaia radar console.
  Two POST endpoints deployed to Modal: /recut re-runs the deterministic gate
  layer in memory against a brief override (RADAR_CONTRACTS.md section G),
  /approve appends an operator's approve/reject click to an audit JSONL.
inputs: HTTP POST JSON bodies (see RECUT_SCHEMA / APPROVE_SCHEMA below);
  cached run/<campaign_id>/extract.json and validate.json, read from a Modal
  Volume when deployed or from the package's local run/ directory otherwise.
outputs: run/<campaign_id>/recuts/<uuid>.json (audit copy of a /recut result);
  appended lines in run/<campaign_id>/approvals.jsonl (one per /approve call).

Read-only against extract.json/validate.json: never writes them, never calls
run.py's acquire_run_lock (RADAR_CONTRACTS.md section G: "never touches stage
files, never takes the run lock"). No LLM call anywhere in this module --
`recut()` is pure deterministic Python over the same gates.py the main
pipeline uses, so a re-cut costs EUR 0 and returns in milliseconds.

-- Storage: Modal Volume vs. a mounted/local run dir -----------------------
Deployed (`modal deploy execution/gtm_client_workflows/gaia_sourcing/
execution/modal_radar.py`), stage files are read from a Modal Volume named
"gaia-radar-run", mounted at /data/run inside the container -- one volume
shared by every campaign, one subdirectory per campaign_id. Populate it once
per run with `modal volume put gaia-radar-run run/<campaign_id>
<campaign_id>` from a machine that has the real `run/` tree (or wire a
small sync step into run.py's own stages once RADAR_CONTRACTS section E/F
land -- not done here, see the note in _run_dir_for).

Running locally (no Modal container, e.g. `python -c "from ... import
modal_radar; ..."` or these tests), /data/run does not exist, so
`_run_dir_for` falls back to this package's own `run/<campaign_id>/`
directory -- the same RUN_DIR every other stage in run.py reads and writes.
Both paths converge on the same two functions (`recut_handler`,
`approve_handler`); only the storage root differs.

-- Testing without Modal installed -----------------------------------------
`modal` is imported lazily inside a try/except at module load. Everything
importable and testable (recut(), recut_handler, approve_handler) has zero
dependency on the `modal` package; only the two `@app.function` / endpoint
definitions at the bottom need it, and they are skipped entirely (with
`app = None`) when the import fails -- exactly what tests/test_modal_radar.py
relies on.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from ..core.config import PKG_ROOT
from ..core.contracts import JobSpec, Person, ValidatedClaim
from ..layers import gates as gates_layer
from ..roles import ROLES

try:
    import modal

    _HAVE_MODAL = True
except ImportError:
    modal = None  # type: ignore[assignment]
    _HAVE_MODAL = False


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
        except Exception:
            # A malformed cached claim degrades that one claim, never the
            # whole re-cut -- same containment principle as run.py's
            # run_all() for the equivalent per-item failure.
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

    A future integration point once layers/outreach_queue.py and the run.py
    `--stage console` wiring land: the pipeline could push a fresh extract/
    validate snapshot into the volume at the end of `gate` so a live re-cut
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
        print("modal_radar: could not read " + str(path) + ": " + repr(exc))
        return None


# ---------------------------------------------------------------------------
# Handlers -- plain functions, importable and testable without Modal.
# ---------------------------------------------------------------------------


def recut_handler(payload: dict) -> dict:
    campaign_id = payload.get("campaign_id")
    role_id = payload.get("role_id")
    overrides = payload.get("brief_overrides") or {}
    if not campaign_id or not role_id:
        return {"error": "campaign_id and role_id are required"}
    spec = ROLES.get(role_id)
    if spec is None:
        return {"error": "unknown role_id: " + str(role_id)}

    run_dir = _run_dir_for(campaign_id)
    extract = _load_json(run_dir / "extract.json")
    validate = _load_json(run_dir / "validate.json")
    if extract is None or validate is None:
        return {
            "error": "extract.json/validate.json not found for campaign "
            + str(campaign_id) + " under " + str(run_dir)
        }

    result = recut(extract, validate, spec, overrides)
    recut_id = str(uuid.uuid4())
    out = {"recut_id": recut_id, **result}

    recuts_dir = run_dir / "recuts"
    try:
        recuts_dir.mkdir(parents=True, exist_ok=True)
        (recuts_dir / (recut_id + ".json")).write_text(
            json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        if _HAVE_MODAL and modal is not None:
            try:
                _get_volume().commit()
            except Exception as exc:
                print("modal_radar: volume commit failed (non-fatal): " + repr(exc))
    except OSError as exc:
        # A read-only or full filesystem must not fail the HTTP response --
        # the caller still gets a correct re-cut result even if the audit
        # copy fails to persist. Logged, never swallowed silently.
        print("modal_radar: could not persist recut record: " + repr(exc))

    return out


_VALID_APPROVE_ACTIONS = {"approve", "reject", "approved", "rejected"}


def approve_handler(payload: dict) -> dict:
    """Append one operator decision to run/<c>/approvals.jsonl.

    Direct JSONL append rather than the real approval state machine
    (draft -> pending_approval -> approved -> marked_sent | rejected)
    described in RADAR_CONTRACTS.md section E, because layers/
    outreach_queue.py -- the eventual owner of that state machine -- had not
    landed at the time this file was written (it is being built concurrently
    by another workstream, per this session's ownership split). Once it
    exists, it should read this file (or this endpoint should call into it
    directly) rather than the two living in parallel indefinitely.
    """
    campaign_id = payload.get("campaign_id")
    draft_id = payload.get("draft_id")
    action = payload.get("action")
    by = payload.get("by") or "unknown"
    if not campaign_id or not draft_id:
        return {"error": "campaign_id and draft_id are required"}
    if action not in _VALID_APPROVE_ACTIONS:
        return {"error": "action must be one of " + ", ".join(sorted(_VALID_APPROVE_ACTIONS))}

    run_dir = _run_dir_for(campaign_id)
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
        if _HAVE_MODAL and modal is not None:
            try:
                _get_volume().commit()
            except Exception as exc:
                print("modal_radar: volume commit failed (non-fatal): " + repr(exc))
    except OSError as exc:
        return {"error": "could not write approvals.jsonl: " + repr(exc)}

    return {"status": "recorded", **record}


# ---------------------------------------------------------------------------
# Modal app -- only defined when `modal` actually imported. Deploy with:
#   modal deploy execution/gtm_client_workflows/gaia_sourcing/execution/modal_radar.py
# Secrets/volumes needed: none for secrets (this module reads no API keys --
# it is pure deterministic Python over cached stage files); one Volume,
# "gaia-radar-run" (created automatically on first deploy via
# create_if_missing=True), populated per campaign as described above.
# ---------------------------------------------------------------------------

app = None

if _HAVE_MODAL:
    app = modal.App("gaia-radar")
    _image = modal.Image.debian_slim(python_version="3.12").pip_install(
        "pydantic>=2", "fastapi"
    )
    _volume = modal.Volume.from_name("gaia-radar-run", create_if_missing=True)

    def _get_volume():
        return _volume

    @app.function(image=_image, volumes={"/data/run": _volume}, timeout=30)
    @modal.fastapi_endpoint(method="POST")
    def recut_endpoint(payload: dict) -> dict:
        return recut_handler(payload)

    @app.function(image=_image, volumes={"/data/run": _volume}, timeout=30)
    @modal.fastapi_endpoint(method="POST")
    def approve_endpoint(payload: dict) -> dict:
        return approve_handler(payload)
else:

    def _get_volume():  # pragma: no cover -- only reachable if _HAVE_MODAL flips at runtime
        raise RuntimeError("modal is not installed")
