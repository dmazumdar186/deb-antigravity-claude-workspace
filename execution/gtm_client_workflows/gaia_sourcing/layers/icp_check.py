"""
ICP sample check -- RADAR_CONTRACTS.md section D.

Spot-checks a batch against the existing, already-computed gate results
(SPEC.md I3: no LLM judgement here either -- this reads gates.py's verdicts,
it never re-derives them). Deterministic seeded sampling means the same
batch + seed always draws the same 20 people, so a RETRY verdict is
reproducible while someone tightens a filter.

`icp_check` itself is pure and does not print -- the "round N: ..." log line
is `icp_check_from_gate_json`'s job, because a "round" is a retry concept
that only exists once something is looping over `icp_check` calls, and
RADAR_CONTRACTS.md's signature for `icp_check` carries no round number.
run.py's `--icp-check` CLI wiring is NOT part of this build (run.py is owned
by another agent this round) -- `icp_check_from_gate_json` is the seam that
wiring will call.
"""

from __future__ import annotations

import json
import math
import random
from pathlib import Path
from typing import Callable, Optional

from ..core.contracts import Evaluation, GateResult, IcpSample, IcpVerdict

# Human-readable next step per gate_id, keyed to the gate_ids layers/gates.py
# actually emits (see _CHECKS in layers/gates.py). A gate_id this module has
# never seen still gets a generic suggestion rather than a KeyError -- a new
# gate landing in gates.py must not crash the ICP check.
_FILTER_SUGGESTIONS = {
    "chartered": "loosen or add corroborating sources for chartership",
    "located_ie": "widen the accepted counties",
    "discipline": "tighten discipline terms",
    "seniority_years": "lower the years/grade threshold",
    "seniority_ceiling": "raise the max_grade/max_years ceiling",
    "not_client": "review the client-side exclusion list",
}


def _suggestion_for(gate_id: str) -> str:
    return _FILTER_SUGGESTIONS.get(gate_id, "review the '" + gate_id + "' gate")


def _failed_gates(evaluation: Evaluation) -> list[str]:
    return [g.gate_id for g in evaluation.gates if not g.passed]


def icp_check(
    batch_persons: list[str],
    evaluations: dict[str, Evaluation],
    sample_n: int = 20,
    min_match: int = 15,
    seed: int = 0,
) -> IcpVerdict:
    """Deterministically sample `sample_n` persons from `batch_persons` and
    judge each against the gate results already recorded for them.

    A person "matches" when their recorded tier is not EXCLUDED -- i.e. every
    hard gate for their role already passed. Missing a person from
    `evaluations` entirely counts as a non-match with a synthetic
    "not_evaluated" failed gate, rather than raising, because a batch drifting
    out of sync with gate.json is exactly the kind of thing this check exists
    to surface.
    """
    population = sorted(set(batch_persons))

    # A population this small cannot support the sample size the caller
    # asked for, and treating it like a normal sample buries that fact --
    # "matched 2/3, verdict RETRY" reads as "this batch is bad" when the real
    # problem is "there is nothing meaningful to check yet". Below 5 people,
    # the check refuses to render a PASS/RETRY verdict at all.
    if len(population) < 5:
        return IcpVerdict(
            batch_id="seed-" + str(seed),
            sampled=len(population),
            matched=0,
            threshold=min_match,
            verdict="INSUFFICIENT_SAMPLE",
            filter_delta="population is only " + str(len(population))
            + " -- too small to sample meaningfully (minimum 5)",
            samples=[],
        )

    n = min(sample_n, len(population))
    sample = random.Random(seed).sample(population, n) if n else []

    samples: list[IcpSample] = []
    matched = 0
    for pid in sample:
        ev = evaluations.get(pid)
        if ev is None:
            samples.append(IcpSample(person_id=pid, passed=False,
                                      failed_gates=["not_evaluated"]))
            continue
        failed = _failed_gates(ev)
        passed = ev.tier != "EXCLUDED" and not failed
        if passed:
            matched += 1
        samples.append(IcpSample(person_id=pid, passed=passed, failed_gates=failed))

    # Scale the pass bar to the sample actually drawn: `min_match` is
    # calibrated for a full `sample_n`-person sample, so a smaller batch
    # (population < sample_n) drawing fewer than `sample_n` people must not
    # be held to the full-size threshold -- that would make a small but
    # otherwise-healthy batch fail RETRY purely on arithmetic.
    effective_min = min(min_match, math.ceil(min_match / sample_n * len(samples)))
    verdict = "PASS" if matched >= effective_min else "RETRY"

    # filter_delta: the most common failed gate across the sample, tie broken
    # by gate_id for determinism.
    counts: dict[str, int] = {}
    for s in samples:
        for g in s.failed_gates:
            counts[g] = counts.get(g, 0) + 1
    if counts:
        top_gate = max(sorted(counts), key=lambda g: counts[g])
        delta = (
            _suggestion_for(top_gate) + ": " + str(counts[top_gate]) + "/"
            + str(len(samples)) + " failed " + top_gate
        )
    else:
        delta = "no failed gates in sample; no filter change suggested"

    return IcpVerdict(
        batch_id="seed-" + str(seed),
        sampled=len(samples),
        matched=matched,
        threshold=min_match,
        verdict=verdict,
        filter_delta=delta,
        samples=samples,
    )


def _load_evaluations(gate_json: dict) -> dict[str, Evaluation]:
    """gate.json's shape, per run.py's stage_gate: {person_id: {role_id,
    tier, gates: [GateResult dict, ...], n_claims, client_side}}."""
    out: dict[str, Evaluation] = {}
    for pid, rec in gate_json.items():
        out[pid] = Evaluation(
            person_id=pid,
            role_id=rec.get("role_id", ""),
            tier=rec.get("tier", "EXCLUDED"),
            gates=[GateResult(**g) for g in rec.get("gates", [])],
        )
    return out


def icp_check_from_gate_json(
    path: str | Path,
    sample_n: int = 20,
    min_match: int = 15,
    seed: int = 0,
    max_rounds: int = 3,
    log: Optional[Callable[[str], None]] = print,
) -> IcpVerdict:
    """Load a gate.json (run.py's `save("gate", out)` output), then run
    icp_check in rounds until it PASSes or `max_rounds` is exhausted --
    logging one line per round in the exact format RADAR_CONTRACTS.md
    section D specifies:

        round N: sampled 20, matched M/20, verdict PASS|RETRY, filter delta: <...>

    Each round after the first draws a different seeded sample (seed + round
    index) so a RETRY round is not just re-checking the same 20 people. The
    round loop stops as soon as one round PASSes; otherwise it returns the
    final round's verdict after `max_rounds` attempts.
    """
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    evaluations = _load_evaluations(data)
    batch_persons = list(data.keys())

    verdict: Optional[IcpVerdict] = None
    for round_num in range(1, max_rounds + 1):
        verdict = icp_check(
            batch_persons, evaluations,
            sample_n=sample_n, min_match=min_match, seed=seed + round_num - 1,
        )
        line = (
            "round " + str(round_num) + ": sampled " + str(verdict.sampled)
            + ", matched " + str(verdict.matched) + "/" + str(verdict.sampled)
            + ", verdict " + verdict.verdict
            + ", filter delta: " + verdict.filter_delta
        )
        if log is not None:
            log(line)
        if verdict.verdict == "PASS":
            break
    assert verdict is not None  # max_rounds >= 1 guaranteed by caller contract
    return verdict
