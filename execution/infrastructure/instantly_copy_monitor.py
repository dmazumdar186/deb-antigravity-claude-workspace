"""Instantly A/B copy monitor: Jev pre-launch gate, weekly scorer drift check, daily variant pruning.

description: Automated Instantly A/B copy monitor -- Jev gate for spun copy, weekly Jev-vs-reply-rate drift check, daily per-variant scoring that disables complaint/loser variants
inputs: CLI subcommand gate --copy <json> | validate | monitor [--live]; --config (default execution/infrastructure/instantly_copy_tests.json); env INSTANTLY_API_KEY, OPENROUTER_API_KEY (via jev_client)
outputs: Markdown report on stdout + .tmp/copy_monitor/report_<date>.md (monitor) / validate_<date>.md (validate); monitor --live PATCHes campaign sequences (v_disabled)

Usage:
    python3 execution/infrastructure/instantly_copy_monitor.py gate --copy .tmp/copy_lab/new_copy.json
    python3 execution/infrastructure/instantly_copy_monitor.py validate
    python3 execution/infrastructure/instantly_copy_monitor.py monitor            # dry run
    python3 execution/infrastructure/instantly_copy_monitor.py monitor --live     # applies changes

Arguments:
    - --copy: JSON file -- list of {"id","subject","body"} with Instantly spintax ({{RANDOM | a | b}}, {{a|b}})
    - --config: JSON -- {"tag_ids": [...], "tests": [{"campaign_id","name","family","started","control_variant"}]}
    - --live: monitor only -- apply at most one variant disable per campaign (default is dry run)

Writes:
    - stdout + .tmp/copy_monitor/report_<YYYY-MM-DD>.md -- per-campaign variant table, actions, inbox alerts
    - exit 0 OK; exit 1 gate failure; exit 2 Instantly / Jev API failure

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
import html
import json
import os
import random
import re
import sys
import time
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
from execution.modules import jev_client as jev

BASE_URL = "https://api.instantly.ai/api/v2"
# urllib's default UA is 403'd by Instantly's edge; send a real one.
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) instantly-copy-monitor/1.0"
DEFAULT_CONFIG = ROOT / "execution" / "infrastructure" / "instantly_copy_tests.json"
OUT_DIR = ROOT / ".tmp" / "copy_monitor"

# ---- thresholds (directive: decision rules) ------------------------------------------
GATE_RENDERS = 20
GATE_SEED = 7
GATE_MEAN_HUMAN = 0.55
GATE_MIN_HUMAN = 0.40
GATE_MAX_AI_TELLS = 0.40

COMPLAINT_MIN_SENT = 200
COMPLAINT_MAX_RATE = 0.0075
LOSER_MIN_SENT = 400
LOSER_MIN_POSITIVES = 5
LOSER_BEST_P = 0.90
LOSER_WORST_P = 0.05
MC_DRAWS = 20_000
MC_SEED = 7

LOW_CONF = 0.6
EMAILS_GAP_S = 3.2          # /emails is limited to 20 req/min
RETRY_429_S = 20.0
MAX_429_RETRIES = 4

VALIDATE_MIN_CONTACTED = 150
VALIDATE_RENDERS = 5
VALIDATE_WARN_HUMAN = 0.2

INBOX_MIN_SENT = 100
INBOX_MAX_BOUNCE = 0.04

HUMAN_KINDS = ("interested", "not_interested", "unsubscribe_or_complaint", "other")


def utc_today() -> dt.date:
    return dt.datetime.now(dt.timezone.utc).date()


class ApiError(RuntimeError):
    """Instantly or Jev failure -> exit 2."""


# ======================================================================================
# Copy rendering (spintax + merge fields)
# ======================================================================================

# Case-sensitive, per the copy lab's convention; any other {{word}} renders as "".
MERGE_VALUES = {
    "firstName": "Mark", "companyName": "Northbridge", "location": "Dallas",
    "Location": "Lyon", "sendingAccountFirstName": "Deb",
}
_MERGE_RE = re.compile(r"\{\{\s*([A-Za-z_][\w.]*)\s*\}\}")
_RANDOM_RE = re.compile(r"\{\{\s*RANDOM\s*\|([^{}]*?)\}\}")
# Bare {{a|b}} spintax; never a RANDOM block (else "RANDOM" becomes an option once the inner spin resolves).
_BARE_SPIN_RE = re.compile(r"\{\{(?!\s*RANDOM\s*\|)([^{}|]*\|[^{}]*)\}\}")


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
    s = _MERGE_RE.sub(lambda m: MERGE_VALUES.get(m.group(1), ""), s or "")
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


def aggregate_metrics(step_rows: list[dict[str, Any]], replies: list[dict[str, Any]]) -> dict[int, dict[int, dict[str, int]]]:
    """Merge analytics/steps rows with classified replies -> {step: {variant: {sent, positive, human, unsub}}}.

    `replies` items: {"step": "0_s_v", "kind": <effective kind>}. Only sequence 0 counts.
    """
    out: dict[int, dict[int, dict[str, int]]] = {}

    def cell(s: int, v: int) -> dict[str, int]:
        return out.setdefault(s, {}).setdefault(v, {"sent": 0, "positive": 0, "human": 0, "unsub": 0})

    for row in step_rows:
        try:
            s, v = int(row.get("step")), int(row.get("variant"))
        except (TypeError, ValueError):
            continue
        cell(s, v)["sent"] += int(row.get("sent") or 0)
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


def step_metric(cells: dict[int, dict[str, int]], arms: list[int]) -> tuple[str, list[tuple[int, int]]]:
    """Positive replies, or (human - unsub, floor 0) when the step has < 5 positives in total."""
    total_pos = sum(cells.get(v, {}).get("positive", 0) for v in arms)
    if total_pos >= LOSER_MIN_POSITIVES:
        return "positive", [(cells.get(v, {}).get("positive", 0), cells.get(v, {}).get("sent", 0)) for v in arms]
    out = []
    for v in arms:
        c = cells.get(v, {})
        out.append((max(0, c.get("human", 0) - c.get("unsub", 0)), c.get("sent", 0)))
    return "human-unsub", out


def decide_campaign(variant_state: dict[int, list[bool]], metrics: dict[int, dict[int, dict[str, int]]]) -> dict[str, Any]:
    """Pure decision for one campaign.

    variant_state: {step_index: [v_disabled per variant]} from sequences[0].
    Returns {"pbest": {(step, v): p}, "action": {...} | None, "held": [str]}.
    At most ONE action; complaints beat losers; the last active arm of a step is never disabled.
    """
    pbest: dict[tuple[int, int], float] = {}
    complaint: list[dict[str, Any]] = []
    loser: list[dict[str, Any]] = []
    held: list[str] = []
    for s in sorted(variant_state):
        active = [v for v, dis in enumerate(variant_state[s]) if not dis]
        cells = metrics.get(s, {})
        # P(best) only over arms that have sent: an unsent arm's flat prior would read as the
        # favourite. When the loser rule is eligible (all arms >= 400 sent) this is every active arm.
        measured = [v for v in active if cells.get(v, {}).get("sent", 0) > 0]
        metric, ps = "", []
        if len(measured) >= 2:
            metric, arms = step_metric(cells, measured)
            ps = p_best(arms)
            for v, p in zip(measured, ps):
                pbest[(s, v)] = p
        # Safety: complaint rate.
        for v in active:
            c = cells.get(v, {})
            sent, unsub = c.get("sent", 0), c.get("unsub", 0)
            if sent >= COMPLAINT_MIN_SENT and unsub / sent > COMPLAINT_MAX_RATE:
                if len(active) <= 1:
                    held.append(f"step {s + 1} variant {letter(v)}: complaint rate {unsub / sent:.2%} but it is the last active arm")
                else:
                    complaint.append({"step": s, "variant": v, "reason": "complaints", "rate": unsub / sent,
                                      "detail": f"{unsub}/{sent} unsub/complaints = {unsub / sent:.2%}"})
        # Winner/loser.
        eligible = len(active) >= 2 and all(cells.get(v, {}).get("sent", 0) >= LOSER_MIN_SENT for v in active)
        if eligible and max(ps) >= LOSER_BEST_P and min(ps) <= LOSER_WORST_P:
            i = min(range(len(ps)), key=ps.__getitem__)
            loser.append({"step": s, "variant": measured[i], "reason": "loser", "p": ps[i],
                          "detail": f"P(best) {ps[i]:.2f} on {metric}; leader {max(ps):.2f}"})
    action = None
    if complaint:
        action = max(complaint, key=lambda a: a["rate"])
    elif loser:
        action = min(loser, key=lambda a: a["p"])
    return {"pbest": pbest, "action": action, "held": held}


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


# ======================================================================================
# Instantly client
# ======================================================================================

class Instantly:
    def __init__(self, key: str) -> None:
        self.s = requests.Session()
        self.s.headers.update({"Authorization": f"Bearer {key}", "User-Agent": USER_AGENT,
                               "Accept": "application/json"})
        self._last_emails = 0.0

    def _req(self, method: str, path: str, *, params: Any = None, body: Any = None) -> Any:
        for attempt in range(MAX_429_RETRIES + 1):
            try:
                r = self.s.request(method, f"{BASE_URL}{path}", params=params, json=body, timeout=60)
            except requests.RequestException as exc:
                raise ApiError(f"{method} {path}: {exc.__class__.__name__}") from exc
            if r.status_code == 429 and attempt < MAX_429_RETRIES:
                time.sleep(RETRY_429_S)
                continue
            if r.status_code >= 400:
                raise ApiError(f"{method} {path}: HTTP {r.status_code} {r.text[:200]}")
            try:
                return r.json()
            except ValueError as exc:
                raise ApiError(f"{method} {path}: non-JSON response") from exc
        raise ApiError(f"{method} {path}: rate-limited")

    def get(self, path: str, params: Any = None) -> Any:
        return self._req("GET", path, params=params)

    def campaign(self, cid: str) -> dict[str, Any]:
        return self.get(f"/campaigns/{cid}")

    def patch_sequences(self, cid: str, sequences: list[dict[str, Any]]) -> Any:
        return self._req("PATCH", f"/campaigns/{cid}", body={"sequences": sequences})

    def step_analytics(self, cid: str, start: str) -> list[dict[str, Any]]:
        res = self.get("/campaigns/analytics/steps", {"campaign_id": cid, "start_date": start})
        return res if isinstance(res, list) else []

    def received_emails(self, cid: str, started: str) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        after = None
        while True:
            wait = EMAILS_GAP_S - (time.monotonic() - self._last_emails)
            if wait > 0:
                time.sleep(wait)
            params = {"campaign_id": cid, "email_type": "received", "limit": 100,
                      "min_timestamp_created": f"{started}T00:00:00.000Z"}
            if after:
                params["starting_after"] = after
            res = self.get("/emails", params)
            self._last_emails = time.monotonic()
            items = res.get("items") or []
            out.extend(i for i in items if i.get("ue_type") == 2 and str(i.get("timestamp_email") or "")[:10] >= started)
            after = res.get("next_starting_after")
            if not items or not after:
                return out

    def paged(self, path: str, params: dict[str, Any]) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        after = None
        for _ in range(200):
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


def instantly_client() -> Instantly:
    key = os.environ.get("INSTANTLY_API_KEY", "").strip()
    if not key:
        raise ApiError("INSTANTLY_API_KEY not set")
    return Instantly(key)


# ======================================================================================
# Subcommands
# ======================================================================================

def _jev_scores(states: list[dict[str, str]], questions: dict[str, dict[str, Any]]) -> list[jev.JevResult]:
    if not jev.available():
        raise ApiError("no OpenRouter key for Jev")
    rs = jev.decide_many(states, questions, workers=8)
    retry = [i for i, r in enumerate(rs) if r.error]
    if retry:
        again = jev.decide_many([states[i] for i in retry], questions, workers=4)
        for i, r in zip(retry, again):
            rs[i] = r
    return rs


def cmd_gate(args: argparse.Namespace) -> int:
    copies = json.loads(Path(args.copy).read_text(encoding="utf-8"))
    if not isinstance(copies, list):
        raise SystemExit("--copy must be a JSON list of {id, subject, body}")
    any_fail = False
    for c in copies:
        rng = random.Random(GATE_SEED)
        states = [{"subject": render(c.get("subject") or "(follow-up, same thread)", rng),
                   "body": render(c.get("body") or "", rng)} for _ in range(GATE_RENDERS)]
        rs = _jev_scores(states, Q_GATE)
        good = [(st, r) for st, r in zip(states, rs) if not r.error]
        if not good:
            raise ApiError(f"Jev returned no answers for copy {c.get('id')}")
        human = [r.noul("human") for _, r in good]
        ai = [r.noul("ai_tells") for _, r in good]
        v = gate_verdict(human, ai)
        any_fail |= not v["pass"]
        worst_state, worst_r = min(good, key=lambda g: g[1].noul("human"))
        print(f"## {c.get('id')}: {'PASS' if v['pass'] else 'FAIL'}")
        print(f"human mean {v['mean_human']:.2f} (>= {GATE_MEAN_HUMAN}) | human min {v['min_human']:.2f} "
              f"(>= {GATE_MIN_HUMAN}) | ai_tells mean {v['mean_ai']:.2f} (<= {GATE_MAX_AI_TELLS}) | renders {len(good)}")
        print(f"\nLowest-scoring render (human {worst_r.noul('human'):.2f}, ai_tells {worst_r.noul('ai_tells'):.2f}):")
        print(f"Subject: {worst_state['subject']}\n\n{worst_state['body']}\n")
    return 1 if any_fail else 0


def cmd_validate(args: argparse.Namespace) -> int:
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
    cost = 0.0
    for r in rows:
        rng = random.Random(GATE_SEED)
        states = [{"subject": render(r["subject"] or "(follow-up, same thread)", rng), "body": render(r["body"], rng)}
                  for _ in range(VALIDATE_RENDERS)]
        rs = _jev_scores(states, Q_VALIDATE)
        cost += sum(x.cost_usd or 0 for x in rs)
        good = [x for x in rs if not x.error]
        if not good:
            continue
        res_rows.append(dict(r, **{k: sum(answer_value(x, k, Q_VALIDATE) for x in good) / len(good) for k in Q_VALIDATE}))
    rr = [x["rr"] for x in res_rows]
    corr = {k: spearman([x[k] for x in res_rows], rr) for k in Q_VALIDATE}
    lines = [f"# Jev copy-scorer validation {utc_today().isoformat()}", "",
             f"Campaigns scored: {len(res_rows)} (>= {VALIDATE_MIN_CONTACTED} contacted, step 1 variant A). Jev cost ${cost:.4f}.", "",
             "| Question | Spearman vs reply rate |", "|---|---|"]
    lines += [f"| {k} | {corr[k]:+.2f} |" for k in Q_VALIDATE]
    if corr["human"] < VALIDATE_WARN_HUMAN:
        lines += ["", (f"**WARNING:** `human` Spearman {corr['human']:.2f} < {VALIDATE_WARN_HUMAN}: the gate's main "
                       "signal no longer tracks reply rate. Re-check the gate thresholds before trusting it.")]
    report = "\n".join(lines) + "\n"
    print(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"validate_{utc_today().isoformat()}.md").write_text(report, encoding="utf-8")
    return 0


def classify_replies(emails: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not emails:
        return []
    states = []
    for e in emails:
        body = e.get("body") or {}
        text = body.get("text") if isinstance(body, dict) else str(body)
        if not text and isinstance(body, dict) and body.get("html"):
            text = html_to_text(body["html"])
        text = strip_quoted(text or e.get("content_preview") or "")[:2000]
        states.append({"from": e.get("from_address_email"), "subject": e.get("subject"), "reply": text})
    rs = _jev_scores(states, Q_KIND)
    if any(r.error for r in rs):
        raise ApiError(f"Jev failed to classify {sum(1 for r in rs if r.error)} of {len(rs)} replies")
    out = []
    for e, r in zip(emails, rs):
        kind, low = effective_kind(r.choice("kind", "other"), r.confidence("kind"))
        out.append({"step": e.get("step"), "kind": kind, "low_conf": low})
    return out


def campaign_section(api: Instantly, test: dict[str, Any], live: bool) -> list[str]:
    cid, started = test["campaign_id"], test["started"]
    name = test.get("name") or cid
    camp = api.campaign(cid)
    lines = [f"## {name} ({cid[:8]})", ""]
    if camp.get("status") != 1:
        return lines + [f"Status {camp.get('status')} (not active): skipped.", ""]
    sequences = camp.get("sequences") or []
    state = variant_state_of(sequences)
    step_rows = api.step_analytics(cid, started)
    replies = classify_replies(api.received_emails(cid, started))
    metrics = aggregate_metrics(step_rows, replies)
    decision = decide_campaign(state, metrics)
    control = test.get("control_variant")
    lines += ["| Step | Variant | Active | Sent | Positive | Human | Unsub | P(best) |",
              "|---|---|---|---|---|---|---|---|"]
    for s in sorted(state):
        for v, dis in enumerate(state[s]):
            c = metrics.get(s, {}).get(v, {})
            p = decision["pbest"].get((s, v))
            tag = letter(v) + (" (control)" if s == 0 and v == control else "")
            lines.append(f"| {s + 1} | {tag} | {'no' if dis else 'yes'} | {c.get('sent', 0)} | {c.get('positive', 0)} | "
                         f"{c.get('human', 0)} | {c.get('unsub', 0)} | {'-' if p is None else f'{p:.2f}'} |")
    lines += ["", "**Actions**", ""]
    act = decision["action"]
    if act is None:
        lines.append("- No changes")
    else:
        what = f"step {act['step'] + 1} variant {letter(act['variant'])} ({act['reason']}: {act['detail']})"
        if not live:
            lines.append(f"- Would disable {what} [dry run]")
        else:
            new_seq = apply_disable(sequences, act["step"], act["variant"])
            why = "change not confirmed on re-read"
            try:
                api.patch_sequences(cid, new_seq)
                after = api.campaign(cid).get("sequences") or []
                ok = after == new_seq or variant_state_of(after) == variant_state_of(new_seq)
            except ApiError as exc:
                ok, why = False, str(exc)
            lines.append(f"- Disabled {what}" if ok else f"- FAILED to disable {what}: {why}")
    lines += [f"- Held: {h}" for h in decision["held"]]
    return lines + [""]


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


def cmd_monitor(args: argparse.Namespace) -> int:
    cfg = json.loads(Path(args.config).read_text(encoding="utf-8"))
    api = instantly_client()
    today = utc_today().isoformat()
    lines = [f"# Copy monitor {today}{'' if args.live else ' (dry run)'}", ""]
    tests = cfg.get("tests") or []
    if not tests:
        lines += ["No tests configured.", ""]
    for t in tests:
        lines += campaign_section(api, t, args.live)
    lines += inbox_section(api, cfg.get("tag_ids") or [])
    report = "\n".join(lines) + "\n"
    print(report)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"report_{today}.md").write_text(report, encoding="utf-8")
    return 0


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Instantly A/B copy monitor (gate / validate / monitor).")
    p.add_argument("--config", default=str(DEFAULT_CONFIG), help="Tests config JSON (default: committed config).")
    sub = p.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gate", help="Pre-launch Jev gate for spun copy.")
    g.add_argument("--copy", required=True, help="JSON list of {id, subject, body}.")
    sub.add_parser("validate", help="Weekly Jev-vs-reply-rate drift check.")
    m = sub.add_parser("monitor", help="Daily variant scoring; dry run unless --live.")
    m.add_argument("--live", action="store_true", help="Apply changes (PATCH Instantly).")
    for sp in (g, m):
        sp.add_argument("--config", default=argparse.SUPPRESS, help="Same as the top-level --config.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    handlers = {"gate": cmd_gate, "validate": cmd_validate, "monitor": cmd_monitor}
    try:
        return handlers[args.cmd](args)
    except ApiError as exc:
        print(f"API failure: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
