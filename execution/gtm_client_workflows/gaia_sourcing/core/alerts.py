"""
Error-channel minimum bar (RADAR_CONTRACTS.md section E;
.claude/rules/automation-boundaries.md "Error-channel minimum bar").

`alert(service, environment, error, count)` posts the FIXED shape
`{service, environment, error, count, at}` to whatever webhook URL is named
by `CONFIG.alert_webhook_env` (default `ALERT_WEBHOOK_URL`), via
`core.cache.post_json` -- the one sanctioned HTTP helper, so this stays
inside the "all HTTP goes through core/cache.py" rule at the top of
RADAR_CONTRACTS.md.

Two things this function must never do:
  1. Raise into the pipeline. An alerting helper that can bring down an
     unattended run over its OWN failure (missing env var, dead webhook,
     network error) is worse than no alerting at all -- it turns "one
     candidate's enrichment failed" into "the whole run died reporting that
     one candidate's enrichment failed".
  2. Send silently when the webhook is not configured. Absence of
     ALERT_WEBHOOK_URL is a normal, expected state before an operator wires
     one up -- so it degrades to a log line, not an exception.

`run.py --alert-test` (wired by another agent this round) should call
`alert("gaia_sourcing", "<campaign or CLI env>", "test alert", 1)` and print
whether it posted -- see this package's HANDOFF.md for the flag.
"""

from __future__ import annotations

from datetime import datetime, timezone

from .cache import post_json
from .config import CONFIG, secret


def alert(service: str, environment: str, error: str, count: int = 1) -> bool:
    """Post one alert. Returns True if the webhook accepted it (2xx),
    False on any other outcome -- including "no webhook configured", which
    is logged rather than raised.
    """
    url = secret(CONFIG.alert_webhook_env, required=False)
    if not url:
        print(
            "[alerts] " + CONFIG.alert_webhook_env + " not set -- alert NOT "
            "sent: " + service + "/" + environment + "/" + error
            + " x" + str(count)
        )
        return False

    payload = {
        "service": service,
        "environment": environment,
        "error": error,
        "count": count,
        "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }

    try:
        ok, status = post_json(url, payload, timeout=10)
    except Exception as exc:
        # post_json itself never raises (see its docstring), but this helper
        # must survive even a genuinely unexpected failure inside it -- an
        # alert must not be the thing that takes an unattended run down.
        print("[alerts] post_json raised unexpectedly: " + repr(exc)[:160])
        return False

    if not ok:
        print(
            "[alerts] webhook post failed (status " + str(status) + "): "
            + service + "/" + environment + "/" + error
        )
    return ok
