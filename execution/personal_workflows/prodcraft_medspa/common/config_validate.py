"""
config_validate.py
description: Centralised validation for the pipeline's `config` table keys, run once after config
    load (scripts/run_metro.py) so a mistyped value (queue_pick="rnadom", min_score=10 below the
    skip-bucket floor, ...) fails loudly at startup instead of silently degrading a run days later.
inputs: validate_config(cfg: dict) -> list[str] problem messages; assert_valid_config(cfg) raises
    ValueError listing every problem (does nothing when cfg is valid). Keys absent or None from
    `cfg` are treated as "not configured" (the caller's own get_config default applies elsewhere)
    and are never flagged — this module only validates values that ARE set.
outputs: N/A (pure functions; no I/O, no Store access — the caller assembles `cfg` from
    Store.get_config() calls first, e.g. scripts/run_metro.py's build_validation_cfg()).
"""

from __future__ import annotations

from typing import Any

ALLOWED_QUEUE_PICK = frozenset({"random", "score"})
ALLOWED_EMAIL_POLICY = frozenset({"deliverable_only", "allow_unverified"})
ALLOWED_PREVIEW_PUBLISH_MODE = frozenset({"r2", "local"})

# skip-bucket sites (audit/scoring.py: total < 25) must never be emailed — CONTRACTS.md scoring
# table's bucket thresholds. 100 is the scoring ceiling (score() can never exceed it).
MIN_SCORE_FLOOR = 25
MIN_SCORE_CEILING = 100

PHASE0_CAP_MIN = 1
PHASE0_CAP_MAX = 50

PHASE0_WARMUP_DAYS_MIN = 0
PHASE0_WARMUP_DAYS_MAX = 60
PHASE0_WARMUP_DAYS_DEFAULT = 14

PHASE0_WARMUP_START_CAP_MIN = 1
PHASE0_WARMUP_START_CAP_DEFAULT = 2


def _is_bool(value: Any) -> bool:
    return isinstance(value, bool)


def _is_int(value: Any) -> bool:
    # bool is an int subclass in Python — exclude it explicitly so a stray True/False silently
    # passing an "is this an int" check isn't a trap later (e.g. phase0.cap = True).
    return isinstance(value, int) and not isinstance(value, bool)


def validate_config(cfg: dict) -> list[str]:
    """Returns a list of human-readable problem strings; empty means the config is valid. Never
    raises — see assert_valid_config() for the fail-loud wrapper."""
    problems: list[str] = []
    cfg = cfg or {}

    queue_pick = cfg.get("queue_pick")
    if queue_pick is not None and queue_pick not in ALLOWED_QUEUE_PICK:
        problems.append(f"queue_pick must be one of {sorted(ALLOWED_QUEUE_PICK)}, got {queue_pick!r}")

    email_policy = cfg.get("email_policy")
    if email_policy is not None and email_policy not in ALLOWED_EMAIL_POLICY:
        problems.append(f"email_policy must be one of {sorted(ALLOWED_EMAIL_POLICY)}, got {email_policy!r}")

    preview_publish_mode = cfg.get("preview_publish_mode")
    if preview_publish_mode is not None and preview_publish_mode not in ALLOWED_PREVIEW_PUBLISH_MODE:
        problems.append(
            f"preview_publish_mode must be one of {sorted(ALLOWED_PREVIEW_PUBLISH_MODE)}, "
            f"got {preview_publish_mode!r}"
        )

    min_score = cfg.get("min_score")
    if min_score is not None and (not _is_int(min_score) or not (MIN_SCORE_FLOOR <= min_score <= MIN_SCORE_CEILING)):
        problems.append(
            f"min_score must be an int in [{MIN_SCORE_FLOOR}, {MIN_SCORE_CEILING}] "
            f"(floor {MIN_SCORE_FLOOR}: skip-bucket sites must never be emailed), got {min_score!r}"
        )

    live_send_confirmed = cfg.get("live_send_confirmed")
    if live_send_confirmed is not None and not _is_bool(live_send_confirmed):
        problems.append(f"live_send_confirmed must be a bool, got {live_send_confirmed!r}")

    auto_approve_previews = cfg.get("auto_approve_previews")
    if auto_approve_previews is not None and not _is_bool(auto_approve_previews):
        problems.append(f"auto_approve_previews must be a bool, got {auto_approve_previews!r}")

    preview_host_suffix = cfg.get("preview_host_suffix")
    if preview_host_suffix is not None and (
        not isinstance(preview_host_suffix, str) or not preview_host_suffix.startswith(".")
    ):
        problems.append(f"preview_host_suffix must be a string starting with '.', got {preview_host_suffix!r}")

    phase0 = cfg.get("phase0")
    if phase0 is not None:
        if not isinstance(phase0, dict):
            problems.append(f"phase0 must be an object, got {type(phase0).__name__}")
        else:
            cap = phase0.get("cap")
            if cap is not None and (not _is_int(cap) or not (PHASE0_CAP_MIN <= cap <= PHASE0_CAP_MAX)):
                problems.append(f"phase0.cap must be an int in [{PHASE0_CAP_MIN}, {PHASE0_CAP_MAX}], got {cap!r}")

            warmup_days = phase0.get("warmup_days")
            if warmup_days is not None and (
                not _is_int(warmup_days) or not (PHASE0_WARMUP_DAYS_MIN <= warmup_days <= PHASE0_WARMUP_DAYS_MAX)
            ):
                problems.append(
                    f"phase0.warmup_days must be an int in [{PHASE0_WARMUP_DAYS_MIN}, {PHASE0_WARMUP_DAYS_MAX}] "
                    f"(default {PHASE0_WARMUP_DAYS_DEFAULT}), got {warmup_days!r}"
                )

            queue_pick_until_passed = phase0.get("queue_pick_until_passed")
            if queue_pick_until_passed is not None and queue_pick_until_passed not in ALLOWED_QUEUE_PICK:
                problems.append(
                    f"phase0.queue_pick_until_passed must be one of {sorted(ALLOWED_QUEUE_PICK)}, "
                    f"got {queue_pick_until_passed!r}"
                )

            warmup_start_cap = phase0.get("warmup_start_cap")
            if warmup_start_cap is not None:
                # Upper bound is phase0.cap when that's itself a valid int (the spec's "1..cap"
                # ties it to the queue cap), else the global phase0.cap ceiling.
                upper = cap if _is_int(cap) else PHASE0_CAP_MAX
                if not _is_int(warmup_start_cap) or not (PHASE0_WARMUP_START_CAP_MIN <= warmup_start_cap <= upper):
                    problems.append(
                        f"phase0.warmup_start_cap must be an int in [{PHASE0_WARMUP_START_CAP_MIN}, {upper}] "
                        f"(default {PHASE0_WARMUP_START_CAP_DEFAULT}), got {warmup_start_cap!r}"
                    )

    return problems


def assert_valid_config(cfg: dict) -> None:
    """Raises ValueError listing every problem found by validate_config(); no-op when valid."""
    problems = validate_config(cfg)
    if problems:
        raise ValueError("invalid config:\n  - " + "\n  - ".join(problems))
