"""
description: Live re-cut + local approval recording for the Gaia radar console.
  Two POST endpoints deployed to Modal: /recut re-runs the deterministic gate
  layer in memory against a brief override (RADAR_CONTRACTS.md section G),
  /approve appends an operator's approve/reject click to an audit JSONL. This
  file is a THIN WRAPPER -- all the real logic (`recut`, `recut_handler`,
  `approve_handler`) lives in `gtm_client_workflows.gaia_sourcing.layers.recut`,
  which never imports `modal`, so the package's test suite and every other
  consumer of that logic can run with zero dependency on the `modal` package.
inputs: HTTP POST JSON bodies (see recut_handler/approve_handler in
  layers/recut.py); cached run/<campaign_id>/extract.json and validate.json,
  read from a Modal Volume when deployed or from the package's local run/
  directory otherwise.
outputs: run/<campaign_id>/recuts/<uuid>.json (audit copy of a /recut result);
  appended lines in run/<campaign_id>/approvals.jsonl (one per /approve call).

Deploy:  modal deploy execution/modal_radar.py
Volume:  "gaia-radar-run" (created automatically on first deploy via
  create_if_missing=True), populated per campaign with
  `modal volume put gaia-radar-run run/<campaign_id> <campaign_id>` from a
  machine that has the real `run/` tree. No secrets needed -- this module
  reads no API keys, it is pure deterministic Python over cached stage files.

-- Import path note ---------------------------------------------------------
This file lives at the workspace's execution root (the convention for Modal
entrypoints -- see directives/add_webhook.md, execution/webhooks.json), a
sibling of the `gtm_client_workflows` namespace package. The `modal` CLI (and
`python -m pytest` run from this directory, per this package's own test
suite) puts this file's own directory on `sys.path`, which is exactly what
makes `import gtm_client_workflows...` work below without an explicit
sys.path hack -- the same mechanism this repo already relies on for every
other `gtm_client_workflows.*` import under `execution/`.

Testing without Modal installed: `modal` is imported lazily inside a
try/except at module load. Everything importable and testable (recut(),
recut_handler, approve_handler) lives in layers/recut.py with zero dependency
on the `modal` package; only the two `@app.function` / endpoint definitions
below need it, and they are skipped entirely (with `app = None`) when the
import fails -- exactly what tests/test_modal_radar.py relies on.
"""

from __future__ import annotations

from gtm_client_workflows.gaia_sourcing.layers.recut import (
    _apply_overrides,
    _load_json,
    _run_dir_for,
    _VALID_APPROVE_ACTIONS,
    approve_handler,
    recut,
)

try:
    import modal

    _HAVE_MODAL = True
except ImportError:
    modal = None  # type: ignore[assignment]
    _HAVE_MODAL = False


# ---------------------------------------------------------------------------
# Modal app -- only defined when `modal` actually imported. Deploy with:
#   modal deploy execution/modal_radar.py
# Secrets/volumes needed: none for secrets; one Volume, "gaia-radar-run"
# (created automatically on first deploy via create_if_missing=True),
# populated per campaign as described in the module docstring above.
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

    def _recut_handler_with_commit(payload: dict) -> dict:
        """Wraps layers.recut.recut_handler with the volume commit the pure
        handler cannot do itself (it has no modal dependency at all).
        """
        from gtm_client_workflows.gaia_sourcing.layers import recut as recut_mod

        out = recut_mod.recut_handler(payload)
        try:
            _get_volume().commit()
        except Exception as exc:
            print("modal_radar: volume commit failed (non-fatal): " + repr(exc))
        return out

    def _approve_handler_with_commit(payload: dict) -> dict:
        from gtm_client_workflows.gaia_sourcing.layers import recut as recut_mod

        out = recut_mod.approve_handler(payload)
        try:
            _get_volume().commit()
        except Exception as exc:
            print("modal_radar: volume commit failed (non-fatal): " + repr(exc))
        return out

    @app.function(image=_image, volumes={"/data/run": _volume}, timeout=30)
    @modal.fastapi_endpoint(method="POST")
    def recut_endpoint(payload: dict) -> dict:
        return _recut_handler_with_commit(payload)

    @app.function(image=_image, volumes={"/data/run": _volume}, timeout=30)
    @modal.fastapi_endpoint(method="POST")
    def approve_endpoint(payload: dict) -> dict:
        return _approve_handler_with_commit(payload)
else:

    def _get_volume():  # pragma: no cover -- only reachable if _HAVE_MODAL flips at runtime
        raise RuntimeError("modal is not installed")
