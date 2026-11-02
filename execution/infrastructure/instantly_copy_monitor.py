"""Instantly A/B copy monitor: Jev pre-launch gate, weekly scorer drift check, daily family-pooled variant pruning, scorecard ledger and AI evals.

description: Automated Instantly A/B copy monitor -- Jev gate for spun copy, weekly Jev-vs-reply-rate drift check, daily family-pooled role scoring that disables complaint/loser roles, scorecard ledger, and idempotency/consistency evals
inputs: CLI subcommand gate --copy <json> | validate [--record] | monitor [--live] [--detail] | eval [--copy <json>] [--record]; --config (default execution/infrastructure/instantly_copy_tests.json); env INSTANTLY_API_KEY, OPENROUTER_API_KEY (via jev_client)
outputs: Markdown report on stdout + .tmp/copy_monitor/report_<date>.md (monitor) / validate_<date>.md / eval_<date>.md; one JSON line appended to docs/metrics/instantly_copy_monitor_ledger.jsonl per monitor --live / validate --record / eval --record run; monitor --live PATCHes campaign sequences (v_disabled)

Usage:
    python3 execution/infrastructure/instantly_copy_monitor.py gate --copy execution/infrastructure/instantly_copy_variants.json
    python3 execution/infrastructure/instantly_copy_monitor.py validate [--record]
    python3 execution/infrastructure/instantly_copy_monitor.py monitor             # dry run
    python3 execution/infrastructure/instantly_copy_monitor.py monitor --detail    # + per-campaign tables
    python3 execution/infrastructure/instantly_copy_monitor.py monitor --live      # applies changes
    python3 execution/infrastructure/instantly_copy_monitor.py eval [--record]     # E1-E5, read-only

Arguments:
    - --copy: JSON file -- list of {"id","subject","body"} with Instantly spintax ({{RANDOM | a | b}}, {{a|b}})
    - --config: JSON -- {"tag_ids": [...], "tests": [{"campaign_id","name","family","started","roles","baseline_sent"}]}
    - --live: monitor only -- apply at most one role disable per family (default is dry run)
    - --detail: monitor only -- also print the per-campaign variant tables
    - --record: validate / eval -- append a ledger line (the scheduled run); monitor writes one only with --live

Writes:
    - stdout + .tmp/copy_monitor/<kind>_<YYYY-MM-DD>.md
    - docs/metrics/instantly_copy_monitor_ledger.jsonl (append-only; monitor --live, validate/eval --record)
    - exit 0 OK; exit 1 gate/eval failure; exit 2 Instantly / Jev API failure or malformed config/copy JSON

Env vars used:
    - INSTANTLY_API_KEY -- Instantly v2 bearer key
    - OPENROUTER_API_KEY -- Jev (read by execution/modules/jev_client.py)

Modes:
    No LLM tier choice: every judgement here is a Jev call (typesafe/jev-1.13), not a chat model.

See also: directives/infrastructure/instantly_copy_monitor.md
"""
from __future__ import annotations

import argparse
import copy
import datetime as dt
import difflib
import html
import json
import os
import random
import re
import statistics
import sys
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

import requests

try:  # local runs read .env; cloud sessions get secrets from the environment
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:  # optional dependency
    pass

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from execution.modules import jev_client as jev  # noqa: E402, RUF100

BASE_URL = "https://api.instantly.ai/api/v2"
# urllib's default UA is 403'd by Instantly's edge; send a real one.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) instantly-copy-monitor/1.0"
DEFAULT_CONFIG = ROOT / "execution" / "infrastructure" / "instantly_copy_tests.json"
DEFAULT_COPY = ROOT / "execution" / "infrastructure" / "instantly_copy_variants.json"
LABEL_FIXTURE = ROOT / "tests" / "fixtures" / "instantly_reply_labels.json"
LEDGER = ROOT / "docs" / "metrics" / "instantly_copy_monitor_ledger.jsonl"
OUT_DIR = ROOT / ".tmp" / "copy_monitor"

# ---- thresholds (directive: decision rules) ------------------------------------------
GATE_RENDERS = 20
GATE_SEED = 7
GATE_MEAN_HUMAN = 0.55
GATE_MIN_HUMAN = 0.40
GATE_MAX_AI_TELLS = 0.40

COMPLAINT_MIN_SENT = 150        # operator order 2026-11-02 (was 200)
COMPLAINT_MAX_RATE = 0.0075
DECISION_MIN_SENT = 180         # operator order 2026-11-02 (was 400); per pooled arm since test start
LOSER_MIN_SENT = DECISION_MIN_SENT
LOSER_MIN_POSITIVES = 5
LOSER_BEST_P = 0.90
LOSER_WORST_P = 0.05
MC_DRAWS = 20_000
MC_SEED = 7

LOW_CONF = 0.6
EMAILS_GAP_S = 3.2          # /emails is limited to 20 req/min
RETRY_429_S = 20.0
MAX_429_RETRIES = 4         # retries on 429 and on 500/502/503/504 (same backoff)
RETRY_STATUSES = (429, 500, 502, 503, 504)
MAX_PAGES = 200
# Reply attribution (thread lookups on /emails): at 3.2 s each, 75 lookups ~ 4 min.
MAX_THREAD_LOOKUPS = 75

VALIDATE_MIN_CONTACTED = 150
VALIDATE_RENDERS = 5
VALIDATE_WARN_HUMAN = 0.2

INBOX_MIN_SENT = 100
INBOX_MAX_BOUNCE = 0.04

# ---- evals ------------------------------------------------------------------------------
EVAL_AGREEMENT = 0.95
EVAL_ACCURACY = 0.80
EVAL_GATE_SEEDS = (7, 11, 13)
EVAL_GATE_MAX_STD = 0.03

HUMAN_KINDS = ("interested", "not_interested", "unsubscribe_or_complaint", "other")
# Automatic replies prove the message reached a live mailbox: the inbox-placement proxy.
AUTO_KINDS = ("out_of_office", "ticket_autoresponder", "challenge_response", "left_company")
METRIC_KEYS = ("sent", "positive", "human", "unsub", "auto")
# Roles that are not "new copy" when computing uplift.
BASE_ROLES = ("control", "old", "legacy")
ROLE_ORDER = ("control", "old", "legacy", "B", "C", "new")


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


class ApiError(RuntimeError):
    """Instantly or Jev failure -> exit 2."""


class ConfigError(ValueError):
    """Unreadable or malformed config / copy JSON -> clear message, exit 2."""


def load_json(path: str | Path, what: str) -> Any:
    """Read a JSON file; any read/parse failure becomes a one-line ConfigError (no traceback)."""
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ConfigError(f"{what} not found: {path}") from exc
    except (OSError, UnicodeDecodeError) as exc:
        raise ConfigError(f"{what} unreadable: {path}: {exc.__class__.__name__}") from exc
    except ValueError as exc:  # json.JSONDecodeError
        raise ConfigError(f"{what} is not valid JSON: {path}: {exc}") from exc


def load_config(path: str | Path) -> dict[str, Any]:
    cfg = load_json(path, "config")
    if not isinstance(cfg, dict) or not isinstance(cfg.get("tests", []), list):
        raise ConfigError(f"config must be a JSON object with a 'tests' list: {path}")
    return cfg


@dataclass
class RunStats:
    """Technical counters for the ledger. Updated only from the main thread."""
    jev_calls: int = 0
    jev_cost_usd: float = 0.0
    jev_errors: int = 0
    replies: int = 0
    low_conf: int = 0
    api_retries: int = 0
    api_errors: int = 0
    replies_pre_test: int = 0       # excluded: answer an outbound sent before the test started
    replies_unattributed: int = 0   # excluded: answering outbound could not be determined
    thread_lookups: int = 0

    def reset(self) -> None:
        for k, v in asdict(RunStats()).items():
            setattr(self, k, v)


STATS = RunStats()


# ======================================================================================
# Copy rendering (spintax + merge fields)
# ======================================================================================

# Case-sensitive, per the copy lab's convention; any other {{word}} renders as its de-camelCased name.
MERGE_VALUES = {
    "firstName": "Mark", "companyName": "Northbridge", "location": "Dallas",
    "Location": "Lyon", "sendingAccountFirstName": "Deb",
}
_MERGE_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")
_RANDOM_RE = re.compile(r"\{\{\s*RANDOM\s*\|([^{}]*?)\}\}")
# Bare {{a|b}} spintax; never a RANDOM block (else "RANDOM" becomes an option once the inner spin resolves).
_BARE_SPIN_RE = re.compile(r"\{\{(?!\s*RANDOM\s*\|)([^{}|]*\|[^{}]*)\}\}")


def neutral_placeholder(name: str) -> str:
    """Unknown merge field -> neutral words so the sentence stays grammatical: boothSize -> "booth size"."""
    words = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name.split(".")[-1]).replace("_", " ")
    return re.sub(r"\s+", " ", words).strip().lower()


def html_to_text(s: str) -> str:
    """Instantly bodies are HTML (<div>, <br />). Render to what a reader sees."""
    s = re.sub(r"(?i)<br\s*/?>", "\n", s or "")
    s = re.sub(r"(?i)</(div|p|li)>", "\n", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s).replace("\xa0", " ")
    s = re.sub(r"[ \t]+\n", "\n", s)
    return re.sub(r"\n{3,}", "\n\n", s).strip()


def render(s: str, rng: random.Random) -> str:
    """Resolve spintax innermost-first and fill merge fields with plausible values.

    Merge fields are filled FIRST so `{{RANDOM | Hi {{firstName}} | Hey}}` resolves (the
    prototype filled them after the spintax loop, so nested spins were silently deleted).
    """
    s = _MERGE_RE.sub(lambda m: MERGE_VALUES.get(m.group(1), neutral_placeholder(m.group(1))), s or "")
    prev = None
    while prev != s:
        prev = s
        s = _RANDOM_RE.sub(lambda m: rng.choice(m.group(1).split("|")).strip(), s)
        s = _BARE_SPIN_RE.sub(lambda m: rng.choice(m.group(1).split("|")).strip(), s)
    s = re.sub(r"\{\{[^{}]*\}\}", "", s)
    return html_to_text(s)


# ======================================================================================
# Jev questions
# ======================================================================================

Q_GATE = {
    "human": jev.noul(
        "Reading this cold email, would a busy business owner believe a real person typed it personally to them (not a template, not AI-generated)?",
        "true when it reads like a real individual wrote it by hand: natural, a little informal, specific, imperfect",
        "false when it reads templated, mail-merged, corporate, or AI-written (polished tricolons, buzzwords, em dashes, generic flattery)"),
    "ai_tells": jev.noul(
        "Does this email contain tell-tale signs of AI or mass-template writing?",
        "true when it has AI/template tells: buzzwords (leverage, streamline, unlock), symmetrical lists of three, em dashes, generic praise, merge-field-shaped subject lines",
        "false when no such tells are present"),
}
Q_VALIDATE = dict(Q_GATE)
Q_VALIDATE.update({
    "reply": jev.score(
        "How likely is the right prospect (the ICP named in the email) to reply to this cold email?",
        ["would ignore or delete", "unlikely to reply", "might reply", "likely to reply", "very likely to reply"]),
    "value": jev.score(
        "How fast and clearly does the email show the prospect a specific valuable outcome with believable proof?",
        ["no clear value", "vague value", "clear value, weak proof", "clear value with specific proof", "irresistible, specific, low-risk offer"]),
    "subject_open": jev.score(
        "How likely is this subject line to get opened by a busy prospect without feeling like spam or bait?",
        ["spammy or bait", "generic", "neutral", "intriguing and personal", "must-open, feels like a colleague wrote it"]),
})

Q_KIND = {
    "kind": jev.choice(
        "Classify this reply received to a cold email campaign.",
        {
            "interested": "a human who wants to talk, asks for details, pricing or a call, or refers to the right colleague",
            "not_interested": "a human who declines: no thanks, not a fit, not now, already have someone",
            "unsubscribe_or_complaint": "asks to be removed, unsubscribed, deleted or not contacted again, or complains about spam",
            "out_of_office": "automatic out-of-office, vacation or leave reply",
            "left_company": "says the person has left the company or this mailbox is no longer monitored",
            "ticket_autoresponder": "helpdesk ticket or generic 'we received your message' auto-acknowledgement",
            "bounce_ndr": "delivery failure, non-delivery report or mailer-daemon message",
            "challenge_response": "sender-verification challenge asking to confirm you are a real sender",
            "other": "a human reply that fits none of the above (wrong person, who are you, unrelated question)",
        }),
}


def answer_value(r: jev.JevResult, key: str, questions: dict[str, dict[str, Any]]) -> float:
    """noul keys -> r.noul, score keys -> r.score."""
    return r.noul(key) if questions[key]["type"] == "noul" else r.score(key)


# ======================================================================================
# Pure decision logic (unit-tested in tests/test_instantly_copy_monitor.py)
# ======================================================================================

def gate_verdict(human: list[float], ai_tells: list[float]) -> dict[str, Any]:
    """PASS iff mean human >= 0.55 AND min human >= 0.40 AND mean ai_tells <= 0.40."""
    if not human or not ai_tells:
        return {"pass": False, "mean_human": 0.0, "min_human": 0.0, "mean_ai": 1.0}
    mh, mn, ma = sum(human) / len(human), min(human), sum(ai_tells) / len(ai_tells)
    ok = mh >= GATE_MEAN_HUMAN and mn >= GATE_MIN_HUMAN and ma <= GATE_MAX_AI_TELLS
    return {"pass": ok, "mean_human": mh, "min_human": mn, "mean_ai": ma}


def _avg_ranks(v: list[float]) -> list[float]:
    order = sorted(range(len(v)), key=lambda i: v[i])
    ranks = [0.0] * len(v)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2.0
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float:
    """Spearman rho with average ranks for ties (Pearson on ranks). 0.0 when undefined."""
    n = len(x)
    if n < 2 or n != len(y):
        return 0.0
    rx, ry = _avg_ranks(x), _avg_ranks(y)
    mx, my = sum(rx) / n, sum(ry) / n
    cov = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    vx = sum((a - mx) ** 2 for a in rx)
    vy = sum((b - my) ** 2 for b in ry)
    if vx == 0 or vy == 0:
        return 0.0
    return cov / (vx * vy) ** 0.5


def parse_step_key(s: Any) -> tuple[int, int, int] | None:
    """Instantly email `step` = "seq_step_variant", e.g. "0_0_1" -> (0, 0, 1)."""
    parts = str(s or "").split("_")
    if len(parts) != 3:
        return None
    try:
        return int(parts[0]), int(parts[1]), int(parts[2])
    except ValueError:
        return None


def effective_kind(kind: str, conf: float) -> tuple[str, bool]:
    """Return (kind used for counting, low_conf). Low-confidence `interested` counts as `other`."""
    low = conf < LOW_CONF
    if low and kind == "interested":
        return "other", True
    return (kind or "other"), low


def _empty_cell() -> dict[str, int]:
    return {k: 0 for k in METRIC_KEYS}


def aggregate_metrics(step_rows: list[dict[str, Any]], replies: list[dict[str, Any]],
                      baseline: dict[str, int] | None = None) -> dict[int, dict[int, dict[str, int]]]:
    """Merge analytics/steps rows with classified replies -> {step: {variant: {sent, positive, human, unsub, auto}}}.

    analytics/steps is called WITHOUT start_date: `sent` is lifetime either way, and with
    start_date == the day the variants were created it omits the new variants' rows entirely
    (verified 2026-11-02). The config stores `baseline_sent` {"step_variant": sent-at-test-start};
    it is subtracted (floor 0) so a control arm with months of history is compared on the same
    window as new arms.

    `replies` items: {"step": "0_s_v", "kind": <effective kind>}. Only sequence 0 counts.
    """
    out: dict[int, dict[int, dict[str, int]]] = {}

    def cell(s: int, v: int) -> dict[str, int]:
        return out.setdefault(s, {}).setdefault(v, _empty_cell())

    for row in step_rows:
        try:
            s, v = int(row.get("step")), int(row.get("variant"))
        except (TypeError, ValueError):
            continue
        cell(s, v)["sent"] += int(row.get("sent") or 0)
    for key, base in (baseline or {}).items():
        try:
            s, v = (int(x) for x in key.split("_"))
        except ValueError:
            continue
        if s in out and v in out[s]:
            out[s][v]["sent"] = max(0, out[s][v]["sent"] - int(base))
    for rep in replies:
        key = parse_step_key(rep.get("step"))
        if key is None or key[0] != 0:
            continue
        c = cell(key[1], key[2])
        kind = rep.get("kind")
        if kind == "interested":
            c["positive"] += 1
        if kind == "unsubscribe_or_complaint":
            c["unsub"] += 1
        if kind in HUMAN_KINDS:
            c["human"] += 1
        if kind in AUTO_KINDS:
            c["auto"] += 1
    return out


def p_best(arms: list[tuple[int, int]], draws: int = MC_DRAWS, seed: int = MC_SEED) -> list[float]:
    """P(arm is best) under Beta(1+k, 1+n-k) posteriors, Monte Carlo with a fixed seed."""
    if not arms:
        return []
    if len(arms) == 1:
        return [1.0]
    rng = random.Random(seed)
    params = [(1 + max(0, min(k, n)), 1 + max(0, n - max(0, min(k, n)))) for k, n in arms]
    wins = [0] * len(arms)
    for _ in range(draws):
        samples = [rng.betavariate(a, b) for a, b in params]
        wins[max(range(len(samples)), key=samples.__getitem__)] += 1
    return [w / draws for w in wins]


def step_metric(cells: dict[Any, dict[str, int]], arms: list[Any]) -> tuple[str, list[tuple[int, int]]]:
    """Positive replies, or (human - unsub, floor 0) when the step has < 5 positives in total."""
    total_pos = sum(cells.get(v, {}).get("positive", 0) for v in arms)
    if total_pos >= LOSER_MIN_POSITIVES:
        return "positive", [(cells.get(v, {}).get("positive", 0), cells.get(v, {}).get("sent", 0)) for v in arms]
    out = []
    for v in arms:
        c = cells.get(v, {})
        out.append((max(0, c.get("human", 0) - c.get("unsub", 0)), c.get("sent", 0)))
    return "human-unsub", out


def decide_arms(state: dict[int, dict[Any, bool]], metrics: dict[int, dict[Any, dict[str, int]]],
                label: Callable[[Any], str] = str) -> dict[str, Any]:
    """Pure decision over arms keyed by any hashable (variant index or pooled role name).

    state: {step: {arm: disabled}}. Returns {"pbest": {(step, arm): p}, "candidates": [...],
    "action": candidates[0] | None, "held": [str]}. Candidates are ordered complaints first
    (highest rate), then losers (lowest P(best)). The last active arm of a step is never a candidate.
    """
    pbest: dict[tuple[int, Any], float] = {}
    complaint: list[dict[str, Any]] = []
    loser: list[dict[str, Any]] = []
    held: list[str] = []
    for s in sorted(state):
        active = [k for k, dis in state[s].items() if not dis]
        cells = metrics.get(s, {})
        # P(best) only over arms that have sent: an unsent arm's flat prior would read as the
        # favourite. When the loser rule is eligible (all arms >= 180 sent) this is every active arm.
        measured = [k for k in active if cells.get(k, {}).get("sent", 0) > 0]
        metric, ps = "", []
        if len(measured) >= 2:
            metric, arms = step_metric(cells, measured)
            ps = p_best(arms)
            for k, p in zip(measured, ps):
                pbest[(s, k)] = p
        for k in active:
            c = cells.get(k, {})
            sent, unsub = c.get("sent", 0), c.get("unsub", 0)
            if sent >= COMPLAINT_MIN_SENT and unsub / sent > COMPLAINT_MAX_RATE:
                if len(active) <= 1:
                    held.append(f"step {s + 1} {label(k)}: complaint rate {unsub / sent:.2%} but it is the last active arm")
                else:
                    complaint.append({"step": s, "arm": k, "reason": "complaints", "rate": unsub / sent,
                                      "detail": f"{unsub}/{sent} unsub/complaints = {unsub / sent:.2%}"})
        eligible = len(active) >= 2 and all(cells.get(k, {}).get("sent", 0) >= DECISION_MIN_SENT for k in active)
        if eligible and ps and max(ps) >= LOSER_BEST_P and min(ps) <= LOSER_WORST_P:
            i = min(range(len(ps)), key=ps.__getitem__)
            loser.append({"step": s, "arm": measured[i], "reason": "loser", "p": ps[i],
                          "detail": f"P(best) {ps[i]:.2f} on {metric}; leader {max(ps):.2f}"})
    candidates = sorted(complaint, key=lambda a: -a["rate"]) + sorted(loser, key=lambda a: a["p"])
    return {"pbest": pbest, "candidates": candidates, "action": candidates[0] if candidates else None, "held": held}


def decide_campaign(variant_state: dict[int, list[bool]], metrics: dict[int, dict[int, dict[str, int]]]) -> dict[str, Any]:
    """Per-campaign decision (variant arms). Used for --detail tables and kept for back-compat."""
    d = decide_arms({s: dict(enumerate(flags)) for s, flags in variant_state.items()}, metrics,
                    lambda v: f"variant {letter(v)}")
    for a in d["candidates"]:
        a["variant"] = a["arm"]
    return d


def letter(v: int) -> str:
    return chr(ord("A") + v) if 0 <= v < 26 else str(v)


def apply_disable(sequences: list[dict[str, Any]], step: int, variant: int) -> list[dict[str, Any]]:
    """Deep copy of sequences with only sequences[0].steps[step].variants[variant].v_disabled = True."""
    new = copy.deepcopy(sequences)
    new[0]["steps"][step]["variants"][variant]["v_disabled"] = True
    return new


def variant_state_of(sequences: list[dict[str, Any]]) -> dict[int, list[bool]]:
    steps = (sequences or [{}])[0].get("steps") or []
    return {i: [bool(v.get("v_disabled")) for v in (st.get("variants") or [])] for i, st in enumerate(steps)}


def sequence_diff(before: Any, after: Any, path: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    """Paths where two JSON values differ (missing key vs False counts as a difference)."""
    if isinstance(before, dict) and isinstance(after, dict):
        out: list[tuple[Any, ...]] = []
        for k in sorted(set(before) | set(after), key=str):
            if k not in before or k not in after:
                out.append(path + (k,))
            else:
                out += sequence_diff(before[k], after[k], path + (k,))
        return out
    if isinstance(before, list) and isinstance(after, list) and len(before) == len(after):
        out = []
        for i, (a, b) in enumerate(zip(before, after)):
            out += sequence_diff(a, b, path + (i,))
        return out
    return [] if before == after else [path]


# ---- family pooling -------------------------------------------------------------------

def campaign_roles(test: dict[str, Any], state: dict[int, list[bool]] | None = None) -> dict[int, dict[str, int]]:
    """{step: {role: variant}} from the config; without `roles`, each variant is its own role ("vA")."""
    roles = test.get("roles")
    if roles:
        return {int(s): {str(r): int(v) for r, v in m.items()} for s, m in roles.items()}
    return {s: {f"v{letter(v)}": v for v in range(len(flags))} for s, flags in (state or {}).items()}


def _role_sort_key(role: str) -> tuple[int, str]:
    return (ROLE_ORDER.index(role) if role in ROLE_ORDER else len(ROLE_ORDER), role)


def pool_family(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool member metrics by (step, role).

    members: [{"name", "roles": {step: {role: v}}, "state": {step: [disabled]}, "metrics": {step: {v: cell}}}].
    Returns {"cells": {step: {role: cell + n + active}}, "state": {step: {role: disabled_everywhere}}}.
    A role mapped to a variant index the campaign does not have is ignored for that campaign.
    """
    cells: dict[int, dict[str, dict[str, int]]] = {}
    for m in members:
        for s, rmap in sorted(m["roles"].items()):
            flags = m["state"].get(s)
            if flags is None:
                continue
            for role, v in rmap.items():
                if not 0 <= v < len(flags):
                    continue
                c = cells.setdefault(s, {}).setdefault(role, dict(_empty_cell(), n=0, active=0))
                c["n"] += 1
                c["active"] += 0 if flags[v] else 1
                src = m["metrics"].get(s, {}).get(v, {})
                for k in METRIC_KEYS:
                    c[k] += int(src.get(k, 0))
    cells = {s: dict(sorted(r.items(), key=lambda kv: _role_sort_key(kv[0]))) for s, r in sorted(cells.items())}
    state = {s: {role: c["active"] == 0 for role, c in r.items()} for s, r in cells.items()}
    return {"cells": cells, "state": state}


def plan_role_disable(members: list[dict[str, Any]], step: int, role: str) -> dict[str, list[Any]]:
    """Which campaigns get the role disabled. Never leaves a campaign step with zero active variants."""
    targets, held, already = [], [], []
    for m in members:
        v = m["roles"].get(step, {}).get(role)
        flags = m["state"].get(step)
        if v is None or flags is None or not 0 <= v < len(flags):
            continue
        if flags[v]:
            already.append(m["name"])
        elif not any(not dis for i, dis in enumerate(flags) if i != v):
            held.append(m["name"])
        else:
            targets.append({"campaign_id": m["campaign_id"], "name": m["name"], "variant": v})
    return {"targets": targets, "held": held, "already": already}


def decide_family(members: list[dict[str, Any]]) -> dict[str, Any]:
    """Pool, decide on roles, and plan the (single) role change for the family.

    A candidate whose plan has no campaign to change (all already off or all held) is not an
    action; it is reported as held and the next candidate is considered.
    """
    pool = pool_family(members)
    d = decide_arms(pool["state"], pool["cells"], lambda r: f"role {r}")
    action, plan = None, None
    held = list(d["held"])
    for cand in d["candidates"]:
        p = plan_role_disable(members, cand["step"], cand["arm"])
        if p["targets"]:
            action, plan = cand, p
            break
        held.append(f"step {cand['step'] + 1} role {cand['arm']} ({cand['reason']}): no campaign can disable it "
                    f"(held in {len(p['held'])}, already off in {len(p['already'])})")
    if plan:
        held += [f"{n}: step {action['step'] + 1} role {action['arm']} is its last active variant" for n in plan["held"]]
    return {"pool": pool, "pbest": d["pbest"], "action": action, "plan": plan, "held": held}


# ---- apply (live) ---------------------------------------------------------------------

def apply_role_disable(api: Any, plan: dict[str, list[Any]], step: int) -> list[dict[str, Any]]:
    """PATCH each target campaign (fresh GET first, so concurrent copy edits are never reverted), re-GET verify."""
    out = []
    for t in plan["targets"]:
        cid, v = t["campaign_id"], t["variant"]
        try:
            seq = api.campaign(cid).get("sequences") or []
            flags = variant_state_of(seq).get(step, [])
            if not 0 <= v < len(flags):
                out.append(dict(t, status="failed", why="variant missing on re-read"))
                continue
            if flags[v]:
                out.append(dict(t, status="already", why="already disabled"))
                continue
            if not any(not dis for i, dis in enumerate(flags) if i != v):
                out.append(dict(t, status="held", why="last active variant on re-read"))
                continue
            new = apply_disable(seq, step, v)
            api.patch_sequences(cid, new)
            after = api.campaign(cid).get("sequences") or []
            ok = variant_state_of(after) == variant_state_of(new)
            out.append(dict(t, status="disabled" if ok else "failed", why="" if ok else "change not confirmed on re-read"))
        except ApiError as exc:
            out.append(dict(t, status="failed", why=str(exc)))
        except (KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
            # Malformed campaign payload for this target only: report it and keep going.
            out.append(dict(t, status="failed", why=f"unexpected campaign shape: {exc.__class__.__name__}: {exc}"))
    return out


def flag_inboxes(daily_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Sum per inbox; flag sent >= 100 and bounced/sent > 4%."""
    tot: dict[str, dict[str, int]] = {}
    for r in daily_rows:
        t = tot.setdefault(str(r.get("email_account") or ""), {"sent": 0, "bounced": 0})
        t["sent"] += int(r.get("sent") or 0)
        t["bounced"] += int(r.get("bounced") or 0)
    out = []
    for email, t in sorted(tot.items()):
        if email and t["sent"] >= INBOX_MIN_SENT and t["bounced"] / t["sent"] > INBOX_MAX_BOUNCE:
            out.append({"email": email, "sent": t["sent"], "bounced": t["bounced"], "rate": t["bounced"] / t["sent"]})
    return out


def strip_quoted(text: str) -> str:
    """Drop the quoted original below a reply so Jev judges only the prospect's words."""
    lines = []
    for line in (text or "").splitlines():
        ls = line.strip()
        if ls.startswith((">", "-----Original Message")) or re.match(r"^On .{5,200}wrote:\s*$", ls) \
                or re.match(r"^From:\s.+", ls):
            break
        lines.append(line)
    return "\n".join(lines).strip()


def _parse_ts(s: Any) -> dt.datetime | None:
    try:
        t = dt.datetime.fromisoformat(str(s or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return t if t.tzinfo else t.replace(tzinfo=dt.timezone.utc)


def outbound_for(reply: dict[str, Any], thread_sent: list[dict[str, Any]]) -> dt.datetime | None:
    """Send time of the outbound email a reply answers: latest sent email (ue_type 1) in the thread
    with the reply's `step` key, sent at or before the reply. None when it cannot be determined."""
    r_ts, step = _parse_ts(reply.get("timestamp_email")), reply.get("step")
    best = None
    for e in thread_sent:
        if e.get("ue_type") not in (1, None) or e.get("step") != step:
            continue
        ts = _parse_ts(e.get("timestamp_email"))
        if ts is None or (r_ts is not None and ts > r_ts):
            continue
        if best is None or ts > best:
            best = ts
    return best


def attribute_replies(emails: list[dict[str, Any]], started: str, baseline: dict[str, Any] | None,
                      thread_sent: Callable[[str], list[dict[str, Any]] | None]
                      ) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Keep only replies to outbound emails sent on/after `started` (the window `sent` is measured on).

    Only the control/old slots had pre-test sends, so counting every reply received since `started`
    would credit them with replies to old sends. A slot with no pre-test sends (`baseline_sent` 0 or
    absent while the test has a baseline) is post-test by construction: no lookup. Other replies
    look up their thread's sent emails via `thread_sent(thread_id)`; the caller caches per thread
    and bounds the calls, returning None once its budget is spent. A reply with no step, no thread,
    no matching outbound, or past the budget is excluded and counted as `unattributed`.
    Returns (kept emails, {"pre_test": n, "unattributed": n}).
    """
    start = dt.datetime.fromisoformat(started).replace(tzinfo=dt.timezone.utc)
    kept: list[dict[str, Any]] = []
    counts = {"pre_test": 0, "unattributed": 0}
    for e in emails:
        key = parse_step_key(e.get("step"))
        if key is None:
            counts["unattributed"] += 1
            continue
        if baseline is not None and int(baseline.get(f"{key[1]}_{key[2]}") or 0) == 0:
            kept.append(e)
            continue
        tid = e.get("thread_id")
        thread = thread_sent(tid) if tid else None
        sent_at = outbound_for(e, thread) if thread is not None else None
        if sent_at is None:
            counts["unattributed"] += 1
        elif sent_at >= start:
            kept.append(e)
        else:
            counts["pre_test"] += 1
    return kept, counts


# ======================================================================================
# Scorecard + ledger (pure parts unit-tested)
# ======================================================================================

def _rate(k: int, n: int) -> float | None:
    return k / n if n else None


def role_block(cells: dict[str, dict[str, int]]) -> dict[str, Any]:
    """Step-1 (index 0) role block: per-role rates, best-new-vs-control uplift and P(new beats control)."""
    roles = {r: {"sent": c["sent"], "positive_rate": _rate(c["positive"], c["sent"]),
                 "human_rate": _rate(c["human"], c["sent"]), "unsub_rate": _rate(c["unsub"], c["sent"]),
                 "auto_rate": _rate(c["auto"], c["sent"])} for r, c in cells.items()}
    total_pos = sum(c["positive"] for c in cells.values())
    metric = "positive" if total_pos >= LOSER_MIN_POSITIVES else "human"
    new = [r for r, c in cells.items() if r not in BASE_ROLES and c["sent"] > 0]
    ctrl = cells.get("control") or cells.get("old")
    best, uplift, p_new = None, None, None
    if new:
        best = max(new, key=lambda r: (cells[r][metric] / cells[r]["sent"], r))
    if best and ctrl and ctrl["sent"] > 0:
        cr = ctrl[metric] / ctrl["sent"]
        br = cells[best][metric] / cells[best]["sent"]
        uplift = (br / cr - 1.0) if cr > 0 else None
        p_new = p_best([(cells[best][metric], cells[best]["sent"]), (ctrl[metric], ctrl["sent"])])[0]
    return {"roles": roles, "best_new_role": best, "uplift_metric": metric,
            "best_new_vs_control_uplift": uplift, "p_new_beats_control": p_new}


def _sum_cells(cells_list: list[dict[str, int]]) -> dict[str, int]:
    out = _empty_cell()
    for c in cells_list:
        for k in METRIC_KEYS:
            out[k] += int(c.get(k, 0))
    return out


OVERALL_LABEL = "cross-family (reporting only)"


def ledger_row(families: dict[str, dict[str, Any]], run_seconds: float, *, live: bool, today: dt.date,
               started: list[str], decisions: int, stats: RunStats) -> dict[str, Any]:
    """One monitor ledger line. `families`: {name: {"pool": pool_family(...), "campaigns": n}}.

    `overall` pools step-1 roles by name ACROSS families (control of one family with control of
    another); it feeds the scorecard only and never a decision, so it carries OVERALL_LABEL.
    """
    fam_out: dict[str, Any] = {}
    overall_step0: dict[str, list[dict[str, int]]] = {}
    all_cells: list[dict[str, int]] = []
    for name, f in families.items():
        step0 = f["pool"]["cells"].get(0, {})
        fam_out[name] = dict(role_block(step0), campaigns=f["campaigns"])
        for r, c in step0.items():
            overall_step0.setdefault(r, []).append(c)
        for s_cells in f["pool"]["cells"].values():
            all_cells += list(s_cells.values())
    overall = role_block({r: _sum_cells(cs) for r, cs in sorted(overall_step0.items(), key=lambda kv: _role_sort_key(kv[0]))})
    overall["totals"] = _sum_cells(all_cells)
    overall["label"] = OVERALL_LABEL
    first = min(started) if started else today.isoformat()
    return {
        "type": "monitor", "date": today.isoformat(), "live": live, "run_seconds": round(run_seconds, 1),
        "families": fam_out, "overall": overall,
        "technical": {
            "jev_calls": stats.jev_calls, "jev_cost_usd": round(stats.jev_cost_usd, 6), "jev_errors": stats.jev_errors,
            "jev_low_conf_share": (stats.low_conf / stats.replies) if stats.replies else 0.0,
            "api_retries": stats.api_retries, "api_errors": stats.api_errors, "decisions_made": decisions,
            "replies_pre_test": stats.replies_pre_test, "replies_unattributed": stats.replies_unattributed,
            "days_since_start": (today - dt.date.fromisoformat(first)).days,
        },
    }


# (key, label, op, target, kind) -- kind drives formatting: pct | rel | count | sec | rho
SCORECARD = [
    ("pos_rate_best_new", "Positive reply rate, step 1 best new role", ">=", 0.010, "pct"),
    ("uplift", "Uplift best new vs control (relative, cross-family, reporting only)", ">", 0.0, "rel"),
    ("unsub_rate", "Unsub/complaint rate", "<=", 0.005, "pct"),
    ("auto_rate", "Auto-reply (OOO) rate, inbox proxy", ">=", 0.008, "pct"),
    ("jev_low_conf_share", "Jev low-confidence share", "<=", 0.15, "pct"),
    ("jev_errors", "Jev errors", "<=", 0, "count"),
    ("api_errors", "Instantly API errors", "<=", 0, "count"),
    ("spearman_human", "Human-score Spearman (latest validate)", ">=", 0.25, "rho"),
    ("run_seconds", "Run time", "<=", 600, "sec"),
]


def scorecard_values(row: dict[str, Any] | None, validate_row: dict[str, Any] | None) -> dict[str, float | None]:
    """Scorecard metric values from a monitor ledger row (+ the validate row in force). None = not measurable."""
    vals: dict[str, float | None] = {k: None for k, *_ in SCORECARD}
    if row:
        ov = row.get("overall") or {}
        new_rates = [r["positive_rate"] for name, r in (ov.get("roles") or {}).items()
                     if name not in BASE_ROLES and r.get("sent") and r.get("positive_rate") is not None]
        vals["pos_rate_best_new"] = max(new_rates) if new_rates else None
        vals["uplift"] = ov.get("best_new_vs_control_uplift")
        tot = ov.get("totals") or {}
        vals["unsub_rate"] = _rate(tot.get("unsub", 0), tot.get("sent", 0))
        vals["auto_rate"] = _rate(tot.get("auto", 0), tot.get("sent", 0))
        tech = row.get("technical") or {}
        for k in ("jev_low_conf_share", "jev_errors", "api_errors"):
            vals[k] = tech.get(k)
        vals["run_seconds"] = row.get("run_seconds")
    if validate_row:
        vals["spearman_human"] = (validate_row.get("spearman") or {}).get("human")
    return vals


def metric_met(op: str, value: float | None, target: float) -> bool | None:
    if value is None:
        return None
    return {">=": value >= target, ">": value > target, "<=": value <= target}[op]


BUSINESS_METRICS = ("pos_rate_best_new", "uplift", "unsub_rate", "auto_rate")
GRADE_MIN_MEASURABLE = 7


def grade(share: float) -> str:
    """A >= 90%, B >= 75%, C >= 60%, D >= 40%, else F."""
    for g, lo in (("A", 0.90), ("B", 0.75), ("C", 0.60), ("D", 0.40)):
        if share >= lo:
            return g
    return "F"


def scorecard_grade(met: int, measurable: int, business_measurable: int) -> str:
    """Letter grade only with >= 1 measurable business metric AND >= 7/9 measurable; else "n/a (k/9 measurable)".

    Dropping n/a metrics from the denominator alone graded a no-data day "A" on 5/9 technical targets.
    """
    if business_measurable < 1 or measurable < GRADE_MIN_MEASURABLE:
        return f"n/a ({measurable}/{len(SCORECARD)} measurable)"
    return grade(met / measurable)


def nearest_row(rows: list[dict[str, Any]], today: dt.date, lo: int = 6, hi: int = 8) -> dict[str, Any] | None:
    """Live monitor row dated lo..hi days before today, nearest to the midpoint (later wins a tie; last line of a day wins).

    Only `type: monitor` rows with `live: true` count: a dry run is not a baseline.
    """
    mid = (lo + hi) / 2
    best, best_key = None, None
    for r in rows:
        if r.get("type") != "monitor" or r.get("live") is not True or r.get("error"):
            continue
        try:
            age = (today - dt.date.fromisoformat(str(r.get("date")))).days
        except ValueError:
            continue
        if lo <= age <= hi:
            key = (abs(age - mid), age)
            if best_key is None or key <= best_key:
                best, best_key = r, key
    return best


def latest_row(rows: list[dict[str, Any]], typ: str, on_or_before: str | None = None) -> dict[str, Any] | None:
    out = None
    for r in rows:
        if r.get("type") == typ and not r.get("error") and (on_or_before is None or str(r.get("date")) <= on_or_before):
            out = r
    return out


def _fmt(kind: str, v: float | None, delta: bool = False) -> str:
    if v is None:
        return "n/a"
    sign = "+" if delta and v >= 0 else ""
    if kind == "pct":
        return f"{sign}{v * 100:.2f} pp" if delta else f"{v:.2%}"
    if kind == "rel":
        return f"{sign}{v * 100:.1f} pp" if delta else f"{v:+.1%}"
    if kind == "rho":
        return f"{sign}{v:.2f}" if delta else f"{v:+.2f}"
    if kind == "sec":
        return f"{sign}{v:.0f} s"
    return f"{sign}{v:g}"


def scorecard_lines(row: dict[str, Any], history: list[dict[str, Any]], today: dt.date) -> tuple[list[str], str]:
    """Markdown scorecard + grade. Δ is vs the monitor row 6-8 days back (else n/a)."""
    vals = scorecard_values(row, latest_row(history, "validate"))
    old = nearest_row(history, today)
    old_vals = scorecard_values(old, latest_row(history, "validate", str(old.get("date"))) if old else None) if old else {}
    lines = ["## Scorecard", "", "| Metric | Target | Today | Δ vs ~7 days ago | Status |", "|---|---|---|---|---|"]
    met = measurable = business = 0
    for key, label, op, target, kind in SCORECARD:
        v = vals.get(key)
        ok = metric_met(op, v, target)
        o = old_vals.get(key) if old_vals else None
        d = (v - o) if (v is not None and o is not None) else None
        if ok is not None:
            measurable += 1
            met += int(ok)
            business += int(key in BUSINESS_METRICS)
        status = "n/a" if ok is None else ("✅" if ok else "⚠️")
        lines.append(f"| {label} | {op} {_fmt(kind, target)} | {_fmt(kind, v)} | {_fmt(kind, d, delta=True)} | {status} |")
    g = scorecard_grade(met, measurable, business)
    lines += ["", f"**Grade {g}** ({met}/{measurable} measurable targets met)", ""]
    return lines, g


def load_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return rows
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except ValueError:
            print(f"ledger: skipped malformed line in {path.name}", file=sys.stderr)
            continue
        if isinstance(obj, dict):
            rows.append(obj)
    return rows


def append_ledger(row: dict[str, Any], path: Path = LEDGER) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    row = dict(row, ts=int(time.time()))
    with path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


# ======================================================================================
# Instantly client
# ======================================================================================

class Instantly:
    def __init__(self, key: str) -> None:
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT,
                               "Accept": "application/json"})
        self._last_emails = 0.0
        self._threads: dict[str, list[dict[str, Any]]] = {}
        self.thread_budget = MAX_THREAD_LOOKUPS

    def _req(self, method: str, path: str, *, params: Any = None, body: Any = None) -> Any:
        for attempt in range(MAX_429_RETRIES + 1):
            try:
                r = self.s.request(method, f"{BASE_URL}{path}", params=params, json=body, timeout=60)
            except requests.RequestException as exc:
                STATS.api_errors += 1
                raise ApiError(f"{method} {path}: {exc.__class__.__name__}") from exc
            if r.status_code in RETRY_STATUSES and attempt < MAX_429_RETRIES:
                STATS.api_retries += 1
                time.sleep(RETRY_429_S)
                continue
            if r.status_code >= 400:
                STATS.api_errors += 1
                raise ApiError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
            try:
                return r.json()
            except ValueError as exc:
                STATS.api_errors += 1
                raise ApiError(f"{method} {path}: non-JSON response") from exc
        STATS.api_errors += 1
        raise ApiError(f"{method} {path}: retries exhausted")

    def get(self, path: str, params: Any = None) -> Any:
        return self._req("GET", path, params=params)

    def campaign(self, cid: str) -> dict[str, Any]:
        return self.get(f"/campaigns/{cid}")

    def patch_sequences(self, cid: str, sequences: list[dict[str, Any]]) -> Any:
        return self._req("PATCH", f"/campaigns/{cid}", body={"sequences": sequences})

    def step_analytics(self, cid: str) -> list[dict[str, Any]]:
        """Lifetime per-(step, variant) rows. NO start_date: with start_date == the day the variants
        were created, Instantly omits the new variants' rows entirely (verified 2026-11-02)."""
        res = self.get("/campaigns/analytics/steps", {"campaign_id": cid})
        return res if isinstance(res, list) else []

    def _emails_get(self, params: dict[str, Any]) -> Any:
        """GET /emails honouring its 20 req/min limit."""
        wait = EMAILS_GAP_S - (time.monotonic() - self._last_emails)
        if wait > 0:
            time.sleep(wait)
        try:
            return self.get("/emails", params)
        finally:
            self._last_emails = time.monotonic()

    def received_emails(self, cid: str, started: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        after, seen = None, set()
        for _ in range(MAX_PAGES):
            params = {"campaign_id": cid, "email_type": "received", "limit": 100,
                      "min_timestamp_created": f"{started}T00:00:00.000Z"}
            if after:
                params["starting_after"] = after
            res = self._emails_get(params)
            items = res.get("items") or []
            out.extend(i for i in items if i.get("ue_type") == 2 and str(i.get("timestamp_email") or "")[:10] >= started)
            after = res.get("next_starting_after")
            if not items or not after or after in seen:
                break
            seen.add(after)
        return out

    def thread_sent(self, thread_id: str) -> list[dict[str, Any]] | None:
        """Sent emails of one thread (cached per thread). None once the per-client lookup budget is spent."""
        if thread_id in self._threads:
            return self._threads[thread_id]
        if self.thread_budget <= 0:
            return None
        self.thread_budget -= 1
        STATS.thread_lookups += 1
        res = self._emails_get({"search": f"thread:{thread_id}", "email_type": "sent", "limit": 100})
        items = [i for i in (res.get("items") or []) if isinstance(i, dict)]
        self._threads[thread_id] = items
        return items

    def paged(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        after = None
        for _ in range(MAX_PAGES):
            p = dict(params, limit=100)
            if after:
                p["starting_after"] = after
            res = self.get(path, p)
            items = res.get("items") or []
            out.extend(items)
            after = res.get("next_starting_after")
            if not items or not after:
                break
        return out


class MockInstantly:
    """In-memory stand-in for the apply path (E3 eval and unit tests). Records every PATCH body."""

    def __init__(self, campaigns: dict[str, dict[str, Any]]) -> None:
        self.campaigns = copy.deepcopy(campaigns)
        self.patches: list[tuple[str, list[dict[str, Any]]]] = []

    def campaign(self, cid: str) -> dict[str, Any]:
        return copy.deepcopy(self.campaigns[cid])

    def patch_sequences(self, cid: str, sequences: list[dict[str, Any]]) -> dict[str, Any]:
        self.patches.append((cid, copy.deepcopy(sequences)))
        self.campaigns[cid]["sequences"] = copy.deepcopy(sequences)
        return {"id": cid}


def instantly_client() -> Instantly:
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        raise ApiError("INSTANTLY_API_KEY not set")
    return Instantly(key)


# ======================================================================================
# Jev helpers
# ======================================================================================

def _jev_scores(states: list[dict[str, str]], questions: dict[str, dict[str, Any]]) -> list[jev.JevResult]:
    if not jev.available():
        raise ApiError("no OpenRouter key for Jev")
    rs = jev.decide_many(states, questions, workers=8)
    STATS.jev_calls += len(rs)
    STATS.jev_cost_usd += sum(r.cost_usd or 0 for r in rs)
    retry = [i for i, r in enumerate(rs) if r.error]
    STATS.jev_errors += len(retry)
    if retry:
        again = jev.decide_many([states[i] for i in retry], questions, workers=4)
        STATS.jev_calls += len(again)
        STATS.jev_cost_usd += sum(r.cost_usd or 0 for r in again)
        STATS.jev_errors += sum(1 for r in again if r.error)
        for i, r in zip(retry, again):
            rs[i] = r
    return rs


def gate_copies(copies: list[dict[str, Any]], seed: int = GATE_SEED, renders: int = GATE_RENDERS) -> list[dict[str, Any]]:
    """Render each copy `renders` times (one Random(seed) per copy), score all renders in one Jev batch."""
    states, owner = [], []
    for i, c in enumerate(copies):
        rng = random.Random(seed)
        for _ in range(renders):
            states.append({"subject": render(c.get("subject") or "(follow-up, same thread)", rng),
                           "body": render(c.get("body") or "", rng)})
            owner.append(i)
    rs = _jev_scores(states, Q_GATE)
    out = []
    for i, c in enumerate(copies):
        good = [(st, r) for st, r, o in zip(states, rs, owner) if o == i and not r.error]
        if not good:
            raise ApiError(f"Jev returned no answers for copy {c.get('id')}")
        v = gate_verdict([r.noul("human") for _, r in good], [r.noul("ai_tells") for _, r in good])
        worst_state, worst_r = min(good, key=lambda g: g[1].noul("human"))
        out.append(dict(v, id=c.get("id"), renders=len(good), worst_state=worst_state,
                        worst_human=worst_r.noul("human"), worst_ai=worst_r.noul("ai_tells")))
    return out


def reply_text(e: dict[str, Any]) -> str:
    body = e.get("body") or {}
    text = body.get("text") if isinstance(body, dict) else str(body)
    if not text and isinstance(body, dict) and body.get("html"):
        text = html_to_text(body["html"])
    return strip_quoted(text or e.get("content_preview") or "")[:2000]


def classify_replies(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Jev `kind` per received email -> [{"step", "kind" (effective), "raw_kind", "low_conf"}]."""
    if not emails:
        return []
    states = [{k: v for k, v in (("from", e.get("from_address_email")), ("subject", e.get("subject")),
                                 ("reply", reply_text(e))) if v} for e in emails]
    rs = _jev_scores(states, Q_KIND)
    if any(r.error for r in rs):
        raise ApiError(f"Jev failed to classify {sum(1 for r in rs if r.error)} of {len(rs)} replies")
    out = []
    for e, r in zip(emails, rs):
        raw = r.choice("kind", "other")
        kind, low = effective_kind(raw, r.confidence("kind"))
        out.append({"step": e.get("step"), "kind": kind, "raw_kind": raw, "low_conf": low})
    STATS.replies += len(out)
    STATS.low_conf += sum(1 for x in out if x["low_conf"])
    return out


# ======================================================================================
# Snapshot -> classification -> pooled decision -> report
# ======================================================================================

def fetch_snapshot(api: Instantly, tests: list[dict[str, Any]]) -> dict[str, Any]:
    """Every Instantly input for one run (campaigns, step analytics, received emails)."""
    camps: dict[str, Any] = {}
    for t in tests:
        cid = t["campaign_id"]
        c = api.campaign(cid)
        entry: dict[str, Any] = {"status": c.get("status"), "sequences": c.get("sequences") or []}
        if c.get("status") == 1:
            entry["step_rows"] = api.step_analytics(cid)
            received = api.received_emails(cid, t["started"])
            entry["emails"], entry["attribution"] = attribute_replies(
                received, t["started"], t.get("baseline_sent"), api.thread_sent)
            STATS.replies_pre_test += entry["attribution"]["pre_test"]
            STATS.replies_unattributed += entry["attribution"]["unattributed"]
        camps[cid] = entry
    return {"tests": tests, "campaigns": camps}


def classify_snapshot(snap: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    """One Jev batch over every campaign's received emails -> {campaign_id: replies}."""
    flat, owner = [], []
    for cid, c in snap["campaigns"].items():
        for e in c.get("emails") or []:
            flat.append(e)
            owner.append(cid)
    labels = classify_replies(flat)
    out: dict[str, list[dict[str, Any]]] = {cid: [] for cid in snap["campaigns"]}
    for cid, lab in zip(owner, labels):
        out[cid].append(lab)
    return out


def compute(snap: dict[str, Any], replies: dict[str, list[dict[str, Any]]]) -> dict[str, Any]:
    """Pure: snapshot + classified replies -> {"families": {name: {...}}, "started": [...]}. Families in config order."""
    families: dict[str, dict[str, Any]] = {}
    for t in snap["tests"]:
        fam = families.setdefault(t.get("family") or t["campaign_id"],
                                  {"members": [], "skipped": [], "warnings": [], "unattributed": 0})
        c = snap["campaigns"].get(t["campaign_id"]) or {}
        name = t.get("name") or t["campaign_id"]
        if c.get("status") != 1:
            fam["skipped"].append(f"{name} (status {c.get('status')})")
            continue
        if not t.get("baseline_sent"):
            fam["warnings"].append(f"{name}: no baseline_sent, sends are lifetime totals (not windowed to the test)")
        fam["unattributed"] += int((c.get("attribution") or {}).get("unattributed", 0))
        state = variant_state_of(c.get("sequences") or [])
        fam["members"].append({
            "campaign_id": t["campaign_id"], "name": name, "roles": campaign_roles(t, state), "state": state,
            "metrics": aggregate_metrics(c.get("step_rows") or [], replies.get(t["campaign_id"]) or [], t.get("baseline_sent")),
        })
    for f in families.values():
        f["decision"] = decide_family(f["members"]) if f["members"] else None
    return {"families": families, "started": sorted({t["started"] for t in snap["tests"] if t.get("started")})}


def actions_of(result: dict[str, Any]) -> list[tuple[Any, ...]]:
    """Comparable action list: (family, step, role, reason, sorted target campaign ids)."""
    out = []
    for name, f in result["families"].items():
        d = f.get("decision")
        if d and d["action"]:
            a = d["action"]
            out.append((name, a["step"], a["arm"], a["reason"], tuple(sorted(t["campaign_id"] for t in d["plan"]["targets"]))))
    return out


def detail_lines(m: dict[str, Any]) -> list[str]:
    d = decide_campaign(m["state"], m["metrics"])
    lines = [f"#### {m['name']} ({m['campaign_id'][:8]})", "",
             "| Step | Variant | Role | Active | Sent | Positive | Human | Unsub | Auto | P(best) |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for s in sorted(m["state"]):
        inv = {v: r for r, v in m["roles"].get(s, {}).items()}
        for v, dis in enumerate(m["state"][s]):
            c = m["metrics"].get(s, {}).get(v, {})
            p = d["pbest"].get((s, v))
            lines.append(f"| {s + 1} | {letter(v)} | {inv.get(v, '-')} | {'no' if dis else 'yes'} | {c.get('sent', 0)} | "
                         f"{c.get('positive', 0)} | {c.get('human', 0)} | {c.get('unsub', 0)} | {c.get('auto', 0)} | "
                         f"{'-' if p is None else f'{p:.2f}'} |")
    return lines + [""]


def family_lines(name: str, f: dict[str, Any], *, live: bool, outcomes: list[dict[str, Any]] | None = None,
                 detail: bool = False) -> list[str]:
    members, d = f["members"], f.get("decision")
    lines = [f"## Family: {name} ({len(members)} active campaign{'s' if len(members) != 1 else ''})", ""]
    if f["skipped"]:
        lines += [f"Skipped (not active): {', '.join(f['skipped'])}", ""]
    for w in f.get("warnings") or []:
        lines.append(f"- Warning: {w}")
    if f.get("warnings"):
        lines.append("")
    if not d:
        return lines + ["No active campaigns.", ""]
    total = len(members)
    lines += ["| Step | Role | Campaigns | Sent | Positive | Human | Unsub | Auto | P(best) | Active in |",
              "|---|---|---|---|---|---|---|---|---|---|"]
    for s, roles in d["pool"]["cells"].items():
        for role, c in roles.items():
            p = d["pbest"].get((s, role))
            lines.append(f"| {s + 1} | {role} | {c['n']} | {c['sent']} | {c['positive']} | {c['human']} | {c['unsub']} | "
                         f"{c['auto']} | {'-' if p is None else f'{p:.2f}'} | {c['active']}/{c['n']} |")
    if f.get("unattributed"):
        lines += ["", f"Unattributed replies (excluded from counts): {f['unattributed']}"]
    lines += ["", "**Actions**", ""]
    a = d["action"]
    if a is None:
        lines.append("- No changes")
    else:
        what = f"step {a['step'] + 1} role {a['arm']} ({a['reason']}: {a['detail']})"
        n = len(d["plan"]["targets"])
        if not live or outcomes is None:
            lines.append(f"- Would disable {what} in {n}/{total} campaigns [dry run]")
        else:
            ok = [o for o in outcomes if o["status"] in ("disabled", "already")]
            lines.append(f"- Disabled {what} in {len(ok)}/{total} campaigns")
            lines += [f"- FAILED: {o['name']}: {o['why']}" for o in outcomes if o["status"] == "failed"]
            lines += [f"- Held: {o['name']}: {o['why']}" for o in outcomes if o["status"] == "held"]
    lines += [f"- Held: {h}" for h in d["held"]]
    lines.append("")
    if detail:
        lines += ["### Per-campaign detail", ""]
        for m in members:
            lines += detail_lines(m)
    return lines


def report_body(result: dict[str, Any], *, live: bool, outcomes: dict[str, list[dict[str, Any]]] | None = None,
                detail: bool = False) -> list[str]:
    lines: list[str] = []
    if not result["families"]:
        return ["No tests configured.", ""]
    for name, f in result["families"].items():
        lines += family_lines(name, f, live=live, outcomes=(outcomes or {}).get(name), detail=detail)
    return lines


def inbox_section(api: Instantly, tag_ids: list[str]) -> list[str]:
    emails: list[str] = []
    for tag in tag_ids:
        for a in api.paged("/accounts", {"tag_ids": tag}):
            if a.get("email") and a["email"] not in emails:
                emails.append(a["email"])
    today = utc_today()
    rows: list[dict[str, Any]] = []
    for i in range(0, len(emails), 25):
        res = api.get("/accounts/analytics/daily", {"emails": emails[i:i + 25],
                                                    "start_date": (today - dt.timedelta(days=7)).isoformat(),
                                                    "end_date": today.isoformat()})
        rows.extend(res if isinstance(res, list) else [])
    flags = flag_inboxes(rows)
    lines = ["## Inbox alerts (last 7 days)", ""]
    if not flags:
        return lines + [f"- None ({len(emails)} inboxes checked)"]
    return lines + [f"- {f['email']}: {f['bounced']}/{f['sent']} bounced = {f['rate']:.1%}" for f in flags]


def _write_out(kind: str, text: str) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{kind}_{utc_today().isoformat()}.md").write_text(text, encoding="utf-8")


def _technical_only(today: dt.date, err: str, run_seconds: float) -> dict[str, Any]:
    return {"type": "monitor", "date": today.isoformat(), "error": err[:200], "run_seconds": round(run_seconds, 1),
            "technical": {"jev_calls": STATS.jev_calls, "jev_cost_usd": round(STATS.jev_cost_usd, 6),
                          "jev_errors": STATS.jev_errors, "api_retries": STATS.api_retries, "api_errors": STATS.api_errors}}


# ======================================================================================
# Subcommands
# ======================================================================================

def _load_copies(path: str | Path) -> list[dict[str, Any]]:
    copies = load_json(path, "copy file")
    if not isinstance(copies, list) or not all(isinstance(c, dict) for c in copies):
        raise ConfigError(f"copy file must be a JSON list of {{id, subject, body}}: {path}")
    return copies


def cmd_gate(args: argparse.Namespace) -> int:
    results = gate_copies(_load_copies(args.copy))
    for v in results:
        print(f"## {v['id']}: {'PASS' if v['pass'] else 'FAIL'}")
        print(f"human mean {v['mean_human']:.2f} (>= {GATE_MEAN_HUMAN}) | human min {v['min_human']:.2f} "
              f"(>= {GATE_MIN_HUMAN}) | ai_tells mean {v['mean_ai']:.2f} (<= {GATE_MAX_AI_TELLS}) | renders {v['renders']}")
        print(f"\nLowest-scoring render (human {v['worst_human']:.2f}, ai_tells {v['worst_ai']:.2f}):")
        print(f"Subject: {v['worst_state']['subject']}\n\n{v['worst_state']['body']}\n")
    return 0 if all(v["pass"] for v in results) else 1


def cmd_validate(args: argparse.Namespace) -> int:
    STATS.reset()
    api = instantly_client()
    camps = api.paged("/campaigns", {})
    by_id = {c["id"]: c for c in camps if c.get("id")}
    ids = list(by_id)
    analytics: dict[str, dict[str, Any]] = {}
    for i in range(0, len(ids), 50):
        res = api.get("/campaigns/analytics", {"ids": ids[i:i + 50]})
        for a in res if isinstance(res, list) else []:
            analytics[a.get("campaign_id")] = a
    rows = []
    for cid, a in analytics.items():
        contacted = a.get("new_leads_contacted_count") or a.get("contacted_count") or 0
        c = by_id.get(cid) or {}
        try:
            v0 = c["sequences"][0]["steps"][0]["variants"][0]
        except (KeyError, IndexError, TypeError):
            continue
        if contacted >= VALIDATE_MIN_CONTACTED:
            rows.append({"name": c.get("name", cid), "rr": 100.0 * (a.get("reply_count_unique") or 0) / contacted,
                         "subject": v0.get("subject"), "body": v0.get("body")})
    res_rows = []
    for r in rows:
        rng = random.Random(GATE_SEED)
        states = [{"subject": render(r["subject"] or "(follow-up, same thread)", rng), "body": render(r["body"], rng)}
                  for _ in range(VALIDATE_RENDERS)]
        rs = _jev_scores(states, Q_VALIDATE)
        good = [x for x in rs if not x.error]
        if not good:
            continue
        res_rows.append(dict(r, **{k: sum(answer_value(x, k, Q_VALIDATE) for x in good) / len(good) for k in Q_VALIDATE}))
    rr = [x["rr"] for x in res_rows]
    corr = {k: spearman([x[k] for x in res_rows], rr) for k in Q_VALIDATE}
    lines = [f"# Jev copy-scorer validation {utc_today().isoformat()}", "",
             (f"Campaigns scored: {len(res_rows)} (>= {VALIDATE_MIN_CONTACTED} contacted, step 1 variant A). "
              f"Jev cost ${STATS.jev_cost_usd:.4f}."), "",
             "| Question | Spearman vs reply rate |", "|---|---|"]
    lines += [f"| {k} | {corr[k]:+.2f} |" for k in Q_VALIDATE]
    if corr["human"] < VALIDATE_WARN_HUMAN:
        lines += ["", (f"**WARNING:** `human` Spearman {corr['human']:.2f} < {VALIDATE_WARN_HUMAN}: the gate's main "
                       "signal no longer tracks reply rate. Re-check the gate thresholds before trusting it.")]
    report = "\n".join(lines) + "\n"
    print(report)
    _write_out("validate", report)
    if args.record:
        append_ledger({"type": "validate", "date": utc_today().isoformat(), "record": True, "campaigns": len(res_rows),
                       "spearman": {k: round(v, 4) for k, v in corr.items()},
                       "jev_cost_usd": round(STATS.jev_cost_usd, 6), "jev_errors": STATS.jev_errors})
    return 0


def run_monitor(api: Instantly, cfg: dict[str, Any], *, live: bool, detail: bool) -> tuple[list[str], dict[str, Any]]:
    """One full monitor pass -> (report lines without scorecard/inbox, result)."""
    snap = fetch_snapshot(api, cfg.get("tests") or [])
    result = compute(snap, classify_snapshot(snap))
    outcomes: dict[str, list[dict[str, Any]]] = {}
    if live:
        for name, f in result["families"].items():
            d = f.get("decision")
            if d and d["action"]:
                outcomes[name] = apply_role_disable(api, d["plan"], d["action"]["step"])
    return report_body(result, live=live, outcomes=outcomes, detail=detail), result


def cmd_monitor(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    STATS.reset()
    cfg = load_config(args.config)
    today = utc_today()
    try:
        return _monitor_once(args, cfg, today, t0)
    except Exception as exc:
        # Any failure (API or a bug): a live run leaves a technical-only ledger line, then the
        # exception propagates (ApiError -> exit 2; anything else -> traceback, non-zero exit).
        if args.live:
            append_ledger(_technical_only(today, f"{exc.__class__.__name__}: {exc}", time.monotonic() - t0))
        raise


def _monitor_once(args: argparse.Namespace, cfg: dict[str, Any], today: dt.date, t0: float) -> int:
    api = instantly_client()
    body, result = run_monitor(api, cfg, live=args.live, detail=args.detail)
    inbox = inbox_section(api, cfg.get("tag_ids") or [])
    run_seconds = time.monotonic() - t0
    fams = {n: {"pool": f["decision"]["pool"], "campaigns": len(f["members"])}
            for n, f in result["families"].items() if f.get("decision")}
    row = ledger_row(fams, run_seconds, live=args.live, today=today, started=result["started"],
                     decisions=len(actions_of(result)), stats=STATS)
    score, g = scorecard_lines(row, load_ledger(), today)
    row["grade"] = g
    lines = [f"# Copy monitor {today.isoformat()}{'' if args.live else ' (dry run)'}", ""] + score + body + inbox
    report = "\n".join(lines) + "\n"
    print(report)
    _write_out("report", report)
    if args.live:  # dry runs never touch the ledger (they would pollute the Δ-7d baseline)
        append_ledger(row)
    return 0


# ---- eval -------------------------------------------------------------------------------

def eval_apply_idempotency() -> tuple[bool, str]:
    """E3 (offline): decide -> apply on a mock -> re-decide; idempotent, minimal PATCH bodies, never a dead step."""
    def seq(n_vars: list[int], disabled: set[tuple[int, int]]) -> list[dict[str, Any]]:
        steps = []
        for s, n in enumerate(n_vars):
            steps.append({"type": "email", "delay": 2, "variants": [
                {"subject": f"s{s}v{v}", "body": f"<div>body {s}.{v}</div>",
                 **({"v_disabled": True} if (s, v) in disabled else {})} for v in range(n)]})
        return [{"steps": steps}]

    std = {0: {"control": 0, "B": 1, "C": 2}, 1: {"old": 0, "new": 1}, 2: {"old": 0, "new": 1}}
    gb = {0: {"control": 0, "legacy": 1, "B": 2, "C": 3}, 1: {"old": 0, "legacy": 1, "new": 2}, 2: {"old": 0, "legacy": 1, "new": 2}}
    camps = {
        "c1": {"status": 1, "sequences": seq([3, 2, 2], set())},
        "c2": {"status": 1, "sequences": seq([3, 2, 2], set())},
        "c3": {"status": 1, "sequences": seq([4, 3, 3], {(0, 1), (1, 1), (2, 1)})},
        "c4": {"status": 1, "sequences": seq([3, 2, 2], {(0, 0), (0, 1)})},   # C is c4's last active arm
    }
    roles = {"c1": std, "c2": std, "c3": gb, "c4": std}

    def metrics_for(cid: str) -> dict[int, dict[int, dict[str, int]]]:
        r = roles[cid][0]
        cells = {r["control"]: {"sent": 300, "positive": 6, "human": 10, "unsub": 0, "auto": 3},
                 r["B"]: {"sent": 300, "positive": 12, "human": 15, "unsub": 0, "auto": 3},
                 r["C"]: {"sent": 300, "positive": 0, "human": 2, "unsub": 0, "auto": 3}}
        return {0: cells}

    def members(api: MockInstantly) -> list[dict[str, Any]]:
        out = []
        for cid in camps:
            st = variant_state_of(api.campaign(cid)["sequences"])
            out.append({"campaign_id": cid, "name": cid, "roles": roles[cid], "state": st, "metrics": metrics_for(cid)})
        return out

    api = MockInstantly(camps)
    before = {cid: api.campaign(cid)["sequences"] for cid in camps}
    problems: list[str] = []
    d1 = decide_family(members(api))
    a = d1["action"]
    if not a or (a["step"], a["arm"]) != (0, "C"):
        return False, f"expected step 1 role C loser, got {a}"
    if sorted(t["campaign_id"] for t in d1["plan"]["targets"]) != ["c1", "c2", "c3"] or d1["plan"]["held"] != ["c4"]:
        problems.append(f"plan wrong: {d1['plan']}")
    outs = apply_role_disable(api, d1["plan"], 0)
    if [o["status"] for o in outs] != ["disabled"] * 3:
        problems.append(f"apply statuses {[o['status'] for o in outs]}")
    for cid, body in api.patches:
        v = roles[cid][0]["C"]
        diff = sequence_diff(before[cid], body)
        if diff != [(0, "steps", 0, "variants", v, "v_disabled")]:
            problems.append(f"{cid} PATCH body differs beyond the target flag: {diff}")
    n_patches = len(api.patches)
    state_once = {cid: variant_state_of(api.campaign(cid)["sequences"]) for cid in camps}
    d2 = decide_family(members(api))
    if d2["action"] and (d2["action"]["step"], d2["action"]["arm"]) == (0, "C"):
        problems.append("re-decide proposed role C again")
    again = apply_role_disable(api, plan_role_disable(members(api), 0, "C"), 0)
    if again or len(api.patches) != n_patches:
        problems.append("second apply was not a no-op")
    if {cid: variant_state_of(api.campaign(cid)["sequences"]) for cid in camps} != state_once:
        problems.append("state after applying twice != after once")
    for cid in camps:
        for s, flags in variant_state_of(api.campaign(cid)["sequences"]).items():
            if flags and all(flags):
                problems.append(f"{cid} step {s + 1} has no active variant")
    ok = not problems
    return ok, ("3 PATCHes, 1 held (last arm), re-decide no-op, bodies minimal" if ok else "; ".join(problems))


def _agreement(runs: list[list[str]]) -> float:
    if not runs or not runs[0]:
        return 1.0
    return sum(1 for labels in zip(*runs) if len(set(labels)) == 1) / len(runs[0])


def cmd_eval(args: argparse.Namespace) -> int:
    t0 = time.monotonic()
    STATS.reset()
    cfg = load_config(args.config)
    tests = cfg.get("tests") or []
    api = instantly_client()
    res: dict[str, dict[str, Any]] = {}

    # E1: same snapshot, classification + aggregation + decision twice.
    snap = fetch_snapshot(api, tests)
    r1, r2 = classify_snapshot(snap), classify_snapshot(snap)
    c1, c2 = compute(snap, r1), compute(snap, r2)
    rep1 = report_body(c1, live=False, detail=True)
    rep2 = report_body(c2, live=False, detail=True)
    n_mail = sum(len(v) for v in r1.values())
    e1 = actions_of(c1) == actions_of(c2) and rep1 == rep2
    res["E1"] = {"pass": e1, "emails": n_mail, "actions": len(actions_of(c1)),
                 "detail": f"{n_mail} emails, {len(actions_of(c1))} actions, report {'identical' if rep1 == rep2 else 'DIFFERS'}"}

    # E2: two full dry-run passes back to back.
    p1, res1 = run_monitor(api, cfg, live=False, detail=False)
    p2, res2 = run_monitor(api, cfg, live=False, detail=False)
    tdiff = [ln for ln in difflib.unified_diff(p1, p2, lineterm="", n=0) if ln[:1] in "+-" and ln[:3] not in ("+++", "---")]
    e2 = actions_of(res1) == actions_of(res2)
    res["E2"] = {"pass": e2, "actions": len(actions_of(res1)), "table_lines_changed": len(tdiff),
                 "detail": f"actions {'identical' if e2 else 'DIFFER'} ({len(actions_of(res1))}); "
                           f"{len(tdiff)} table lines changed (sends moving)"}

    # E3: offline apply idempotency.
    ok3, why3 = eval_apply_idempotency()
    res["E3"] = {"pass": ok3, "detail": why3}

    # E4: classification consistency (live + labelled fixture, 3 runs) and fixture accuracy.
    fixture = json.loads(LABEL_FIXTURE.read_text(encoding="utf-8"))
    fx_emails = [{"step": None, "body": {"text": f["preview"]}} for f in fixture]
    r3 = classify_snapshot(snap)
    live_runs = [[x["raw_kind"] for cid in snap["campaigns"] for x in r[cid]] for r in (r1, r2, r3)]
    fx_runs = [[x["raw_kind"] for x in classify_replies(fx_emails)] for _ in range(3)]
    agree = _agreement([lr + fr for lr, fr in zip(live_runs, fx_runs)])
    acc = sum(1 for got, f in zip(fx_runs[0], fixture) if got == f["kind"]) / len(fixture)
    res["E4"] = {"pass": agree >= EVAL_AGREEMENT and acc >= EVAL_ACCURACY, "agreement": round(agree, 4),
                 "accuracy": round(acc, 4), "n_live": len(live_runs[0]), "n_fixture": len(fixture),
                 "detail": f"agreement {agree:.3f} (>= {EVAL_AGREEMENT}) over {len(live_runs[0])} live + "
                           f"{len(fixture)} fixture; accuracy {acc:.3f} (>= {EVAL_ACCURACY})"}

    # E5: gate stability across seeds.
    copies = _load_copies(args.copy)
    by_seed = [gate_copies(copies, seed=s) for s in EVAL_GATE_SEEDS]
    flips, worst_std, worst_id = [], 0.0, ""
    for i, c in enumerate(copies):
        verdicts = {r[i]["pass"] for r in by_seed}
        if len(verdicts) > 1:
            flips.append(c.get("id"))
        sd = statistics.pstdev([r[i]["mean_human"] for r in by_seed])
        if sd > worst_std:
            worst_std, worst_id = sd, str(c.get("id"))
    n_pass = sum(1 for v in by_seed[0] if v["pass"])
    res["E5"] = {"pass": not flips and worst_std <= EVAL_GATE_MAX_STD, "flips": flips, "max_std": round(worst_std, 4),
                 "detail": f"{len(copies)} copies, {n_pass} PASS on seed {EVAL_GATE_SEEDS[0]}; verdict flips {flips or 'none'}; "
                           f"max mean-human std {worst_std:.3f} ({worst_id}) (<= {EVAL_GATE_MAX_STD})"}

    lines = [f"# Copy monitor evals {utc_today().isoformat()}", "", "| Eval | Result | Detail |", "|---|---|---|"]
    names = {"E1": "Decision determinism (same snapshot)", "E2": "Re-run stability (2 dry runs)",
             "E3": "Apply idempotency (mock)", "E4": "Reply-classification consistency + accuracy",
             "E5": "Gate stability (3 seeds)"}
    lines += [f"| {k} {names[k]} | {'PASS' if v['pass'] else 'FAIL'} | {v['detail']} |" for k, v in res.items()]
    run_s = time.monotonic() - t0
    lines += ["", (f"Jev calls {STATS.jev_calls}, cost ${STATS.jev_cost_usd:.4f}, errors {STATS.jev_errors}; "
                   f"API retries {STATS.api_retries}; {run_s:.0f} s"), ""]
    report = "\n".join(lines) + "\n"
    print(report)
    _write_out("eval", report)
    if args.record:
        append_ledger({"type": "eval", "date": utc_today().isoformat(), "record": True, "run_seconds": round(run_s, 1),
                       "results": {k: {kk: vv for kk, vv in v.items() if kk != "detail"} for k, v in res.items()},
                       "jev_calls": STATS.jev_calls, "jev_cost_usd": round(STATS.jev_cost_usd, 6),
                       "jev_errors": STATS.jev_errors, "api_retries": STATS.api_retries, "api_errors": STATS.api_errors})
    return 0 if all(v["pass"] for v in res.values()) else 1


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Instantly A/B copy monitor (gate / validate / monitor / eval).")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Tests config JSON (default: committed config).")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="Pre-launch Jev gate for spun copy.")
    g.add_argument("--copy", required=True, help="JSON list of {id, subject, body}.")
    v = sub.add_parser("validate", help="Weekly Jev-vs-reply-rate drift check.")
    v.add_argument("--record", action="store_true", help="Append a ledger line (scheduled run).")
    m = sub.add_parser("monitor", help="Daily family-pooled scoring; dry run unless --live.")
    m.add_argument("--live", action="store_true", help="Apply changes (PATCH Instantly).")
    m.add_argument("--detail", action="store_true", help="Also print per-campaign variant tables.")
    e = sub.add_parser("eval", help="E1-E5 idempotency/consistency evals (read-only).")
    e.add_argument("--copy", default=str(DEFAULT_COPY), help="Copy file for the E5 gate-stability eval.")
    e.add_argument("--record", action="store_true", help="Append a ledger line (scheduled run).")
    for sp in (g, v, m, e):
        sp.add_argument("--config", default=argparse.SUPPRESS, help="Same as the top-level --config.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handlers = {"gate": cmd_gate, "validate": cmd_validate, "monitor": cmd_monitor, "eval": cmd_eval}
    try:
        return handlers[args.cmd](args)
    except ApiError as exc:
        print(f"API failure: {exc}", file=sys.stderr)
        return 2
    except ConfigError as exc:
        print(f"Config error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
