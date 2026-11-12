"""Workspace brain — lessons from past mistakes, auto-loaded so they are not repeated.

description: Stores one short behavioural lesson per file in .claude/brain/lessons/ and wires them
             into every session through hooks, at a bounded token cost:
               SessionStart     -> core lessons (strength >= 3, <= CORE_MAX_CHARS) + maintenance flags
               UserPromptSubmit -> top lessons whose triggers match the prompt (offline keyword
                                   scoring, <= PROMPT_MAX_CHARS, each lesson once per session) and a
                                   capture reminder when the prompt reads like an operator correction
               Stop             -> blocks once if the assistant admitted a miss this turn and did not
                                   record it (add / repeat), so the lesson is captured automatically
             Learning loop: `add` checks the nearest lessons for duplicate / contradiction (Jev when a
             key is set, lexical otherwise); `repeat` strengthens a lesson that was missed again
             (strength >= 3 joins the core); `lint` dedupes, decays and finds conflicts.
inputs: hook JSON on stdin (session_id, prompt, transcript_path, stop_hook_active);
        .claude/brain/lessons/*.md; env OPENROUTER_API_KEY (optional, Jev conflict checks);
        env BRAIN_DIR / BRAIN_TODAY / BRAIN_TMP (tests).
outputs: hook JSON on stdout; lesson files; .tmp/brain_sessions/<session>.json (dedupe state);
         .tmp/jev_ledger.jsonl rows (caller=brain).

Usage:
    python3 execution/infrastructure/brain.py status | list [--all] | core
    python3 execution/infrastructure/brain.py search "reply to les about the evidence pdf"
    python3 execution/infrastructure/brain.py add --rule "..." --why "..." --triggers "a, b" \
        [--scope all] [--source <sha|path>] [--strength 2] [--date YYYY-MM-DD] [--force] [--dry-run]
    python3 execution/infrastructure/brain.py repeat <id> | archive <id> | restore <id>
    python3 execution/infrastructure/brain.py supersede <old_id> <new_id>
    python3 execution/infrastructure/brain.py lint [--deep] [--apply]
    python3 execution/infrastructure/brain.py hook-start|hook-prompt|hook-stop   # stdin = hook JSON

Directive: directives/infrastructure/brain.md. Fails open in every hook mode (exit 0, no output).
"""

from __future__ import annotations

import argparse
import hashlib
import datetime as dt
import json
import os
import re
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
CORE_MIN_STRENGTH = 3
CORE_MAX_ITEMS = 12
CORE_MAX_CHARS = 2200
PROMPT_TOP_K = 3
PROMPT_MAX_CHARS = 900
PROMPT_MIN_SCORE = 3.5
MAX_ACTIVE = 120
DECAY_DAYS = 180
DEEP_EVERY_DAYS = 7
DEEP_FLOOR = 0.04   # Jev judges paraphrases; lexical overlap only picks which pairs to ask about
ADD_FLOOR = 0.06
RULE_MAX = 240
WHY_MAX = 240
SCOPES = ("all", "outward", "client", "gtm", "site", "code", "infra", "video", "mobile")
FIELDS = (
    "id",
    "triggers",
    "scope",
    "strength",
    "status",
    "created",
    "confirmed",
    "source",
    "supersedes",
)
CAPTURE_CMD = "python3 execution/infrastructure/brain.py"

STOP = set(
    """a an the and or but if then else of to in on at by for with from into onto over under is are
was were be been being do does did done have has had this that these those it its as not no yes you your
we our i me my they them their he she his her can could should would will shall may might must just only
also very more most less than so such any all each every some what which who whom whose when where why
how about after before again out up down off here there now new use using used get got make made want
need please thanks thank okay ok let lets go going one two""".split()
)

CORRECTION_RE = re.compile(
    r"\b(why did(n'?t| not)? you|you (missed|forgot|ignored|skipped|didn'?t|did not|failed|broke|overcomplicated)|"
    r"not what i asked|i (already )?told you|as i (said|told you)|again[,!. ]+(the same|same) (mistake|issue|problem)|"
    r"same mistake|nice catch|that'?s wrong|this is wrong|you were supposed to|should have (run|checked|asked|used)|"
    r"repeat(ing|ed)? (the|this|that) mistake|over-?complicat)",
    re.I,
)
ADMISSION_RE = re.compile(
    r"\b(my mistake|my bad|i overlooked|nice catch|good catch|i should have (run|checked|asked|verified|tested|read|used)|"
    r"i overcomplicated|i over-?built|i over-?engineered|i failed to|i was wrong|that was wrong of me|"
    r"i missed (that|this|it|the)|i apologi[sz]e for)\b",
    re.I,
)
QUOTED_RE = re.compile(r"\"[^\"\n]{0,400}\"|“[^”\n]{0,400}”|^>.*$|```.*?```", re.M | re.S)
BRAIN_CMD_RE = re.compile(r"brain\.py\"?\s+(add|repeat|supersede|restore)\b")


def today() -> dt.date:
    env = os.environ.get("BRAIN_TODAY", "")
    return dt.date.fromisoformat(env) if env else dt.date.today()


def brain_dir() -> Path:
    return Path(os.environ.get("BRAIN_DIR") or ROOT / ".claude" / "brain")


def tmp_dir() -> Path:
    return Path(os.environ.get("BRAIN_TMP") or ROOT / ".tmp")


def words(text: str) -> list[str]:
    return [
        w for w in re.findall(r"[a-z0-9][a-z0-9'+#.-]*[a-z0-9]|[a-z0-9]", text.lower())
    ]


def stem(w: str) -> str:
    """Fold plurals so 'cold emails' matches the trigger 'cold email' (not 'les'/'less'/'access')."""
    if len(w) > 4 and w.endswith("ies"):
        return w[:-3] + "y"
    if len(w) > 3 and w.endswith("s") and not w.endswith(("ss", "us", "is")):
        return w[:-1]
    return w


def norm(text: str) -> str:
    return " " + " ".join(stem(w) for w in words(text)) + " "


def content_words(text: str) -> set[str]:
    return {w for w in words(text) if len(w) > 2 and w not in STOP}


# ---------------------------------------------------------------------------------------------
@dataclass
class Lesson:
    id: str
    rule: str
    why: str = ""
    triggers: list[str] = field(default_factory=list)
    scope: str = "all"
    strength: int = 1
    status: str = "active"
    created: str = ""
    confirmed: str = ""
    source: str = ""
    supersedes: list[str] = field(default_factory=list)
    path: Path | None = None

    @property
    def terms(self) -> set[str]:
        return content_words(self.rule + " " + " ".join(self.triggers))

    def render(self) -> str:
        meta = {
            "id": self.id,
            "triggers": ", ".join(self.triggers),
            "scope": self.scope,
            "strength": str(self.strength),
            "status": self.status,
            "created": self.created,
            "confirmed": self.confirmed,
            "source": self.source,
            "supersedes": ", ".join(self.supersedes),
        }
        head = "\n".join(f"{k}: {meta[k]}".rstrip() for k in FIELDS)
        body = self.rule.strip() + (
            "\n\nWhy: " + self.why.strip() if self.why.strip() else ""
        )
        return f"---\n{head}\n---\n{body}\n"


def _split_list(val: str) -> list[str]:
    return [t.strip().lower() for t in val.split(",") if t.strip()]


def parse(text: str, path: Path | None = None) -> Lesson:
    m = re.match(r"﻿?---\s*\n(.*?)\n---\s*\n(.*)", text, re.S)
    if not m:
        raise ValueError("missing --- frontmatter ---")
    meta: dict[str, str] = {}
    for line in m.group(1).splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip().lower()] = v.strip()
    body = m.group(2).strip()
    why = ""
    wm = re.search(r"^\s*Why:\s*(.+)$", body, re.M | re.S)
    if wm:
        why = " ".join(wm.group(1).split())
        body = body[: wm.start()].strip()
    rule = " ".join(body.split())
    if not meta.get("id") or not rule:
        raise ValueError("id and rule are required")
    try:
        strength = int(meta.get("strength", "1") or 1)
    except ValueError:
        strength = 1
    return Lesson(
        id=meta["id"],
        rule=rule,
        why=why,
        triggers=_split_list(meta.get("triggers", "")),
        scope=meta.get("scope", "all") or "all",
        strength=max(1, min(5, strength)),
        status=meta.get("status", "active") or "active",
        created=meta.get("created", ""),
        confirmed=meta.get("confirmed", "") or meta.get("created", ""),
        source=meta.get("source", ""),
        supersedes=_split_list(meta.get("supersedes", "")),
        path=path,
    )


def load(include_archive: bool = False) -> tuple[list[Lesson], list[str]]:
    """Return (lessons, errors). Bad files are reported, never fatal."""
    out: list[Lesson] = []
    errors: list[str] = []
    dirs = [brain_dir() / "lessons"] + (
        [brain_dir() / "archive"] if include_archive else []
    )
    for d in dirs:
        if not d.is_dir():
            continue
        for p in sorted(d.glob("*.md")):
            try:
                les = parse(p.read_text(encoding="utf-8"), p)
                if les.id != p.stem:
                    errors.append(f"{p.name}: id '{les.id}' != filename")
                out.append(les)
            except (OSError, ValueError, UnicodeDecodeError) as exc:
                errors.append(f"{p.name}: {exc}")
    return out, errors


def active(lessons: list[Lesson]) -> list[Lesson]:
    return [x for x in lessons if x.status == "active"]


ID_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,99}$")


def save(les: Lesson) -> Path:
    if not ID_RE.match(les.id):
        raise ValueError(f"invalid lesson id {les.id!r} (allowed: a-z 0-9 -)")
    sub = "lessons" if les.status == "active" else "archive"
    target = brain_dir() / sub / f"{les.id}.md"
    if not target.resolve().is_relative_to(brain_dir().resolve()):
        raise ValueError("path traversal")
    target.parent.mkdir(parents=True, exist_ok=True)
    tmp = target.with_suffix(".md.tmp")
    tmp.write_text(les.render(), encoding="utf-8", newline="\n")
    os.replace(tmp, target)
    if les.path and les.path.resolve() != target.resolve() and les.path.exists():
        les.path.unlink()
    les.path = target
    return target


def find(lesson_id: str, include_archive: bool = True) -> Lesson | None:
    lessons, _ = load(include_archive)
    return next((x for x in lessons if x.id == lesson_id), None)


# ---------------------------------------------------------------------------------------------
# retrieval
def score(les: Lesson, prompt_norm: str, prompt_terms: set[str]) -> float:
    hits = 0.0
    for t in les.triggers:
        tn = norm(t)
        if tn.strip() and tn in prompt_norm:
            hits += 4.0 if " " in tn.strip() else 2.0
    if hits == 0:
        return 0.0
    overlap = len(content_words(les.rule) & prompt_terms)
    return hits + min(2.0, 0.5 * overlap) + 0.25 * les.strength


def retrieve(
    prompt: str,
    lessons: list[Lesson],
    exclude: set[str] | None = None,
    top_k: int = PROMPT_TOP_K,
    min_score: float = PROMPT_MIN_SCORE,
) -> list[tuple[float, Lesson]]:
    pn, pt = norm(prompt), content_words(prompt)
    scored = [
        (score(x, pn, pt), x) for x in active(lessons) if x.id not in (exclude or set())
    ]
    scored = [s for s in scored if s[0] >= min_score]
    scored.sort(key=lambda s: (-s[0], -s[1].strength, s[1].id))
    return scored[:top_k]


JEV_PICK_CUT = 0.6
JEV_PICK_TIMEOUT_S = 3.5
JEV_DAILY_USD_CAP = 0.25


def _spend_file() -> Path:
    return tmp_dir() / f"brain_jev_spend_{today().isoformat()}.txt"


def _spent_today() -> float:
    try:
        return float(_spend_file().read_text(encoding="utf-8").strip() or 0)
    except (OSError, ValueError):
        return 0.0


_SPEND_LOCK = threading.Lock()


def _add_spend(usd: float) -> None:
    # Locked read-modify-write: the eval replays jev_pick on 8 threads; unlocked, updates were lost and
    # a 48-call run recorded spend 0.0 (2026-11-12). Cross-process races remain possible but rare.
    with _SPEND_LOCK:
        p = _spend_file()
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f"{_spent_today() + usd:.6f}", encoding="utf-8")


def jev_pick(prompt: str, lessons: list[Lesson], exclude: set[str]) -> dict[str, float]:
    """Semantic recall for one prompt: {lesson_id: p} for every lesson Jev rates relevant (one call).
    {} when Jev is off (/jev off), unavailable, over the daily cap, slow or failing -> keywords only."""
    pool = [x for x in active(lessons) if x.id not in exclude]
    if not pool or not _jev_enabled() or _spent_today() >= JEV_DAILY_USD_CAP:
        return {}
    try:
        sys.path.insert(0, str(ROOT))
        from execution.modules import jev_client as jev  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 — optional dependency; keyword path still runs
        print(f"brain jev_pick import: {exc}", file=sys.stderr)
        return {}
    if not jev.available():
        return {}
    qs = {
        f"l{i}": jev.noul(
            f"Lesson: {x.rule} -- Does following this lesson matter for doing the operator_prompt's task correctly?",
            "the task touches what the lesson governs, so ignoring it could repeat the mistake",
            "the lesson is about a different kind of work than this prompt",
        )
        for i, x in enumerate(pool[:120])
    }
    try:
        r = jev.decide({"operator_prompt": prompt[:4000]}, qs, timeout_s=JEV_PICK_TIMEOUT_S)
    except Exception as exc:  # noqa: BLE001 — never block a prompt on recall
        print(f"brain jev_pick: {exc}", file=sys.stderr)
        return {}
    if r.error:
        return {}
    try:
        _add_spend(float(r.cost_usd or 0))
        jev.append_ledger({"caller": "brain_pick", "cost": r.cost_usd}, tmp_dir() / "jev_ledger.jsonl")
    except Exception as exc:  # noqa: BLE001 — telemetry only
        print(f"brain jev_pick ledger: {exc}", file=sys.stderr)
    return {x.id: round(r.noul(f"l{i}"), 3) for i, x in enumerate(pool[:120]) if r.noul(f"l{i}") >= JEV_PICK_CUT}


def retrieve_hybrid(prompt: str, lessons: list[Lesson], exclude: set[str] | None = None,
                    use_jev: bool = True, picks: dict[str, float] | None = None) -> list[tuple[str, Lesson]]:
    """Keyword hits + Jev picks, at most PROMPT_TOP_K. Returns (source, lesson); source is
    kw | jev | both. Agreement ranks first, then Jev probability, then keyword score."""
    exclude = exclude or set()
    kw = {x.id: (sc, x) for sc, x in retrieve(prompt, lessons, exclude=exclude, top_k=PROMPT_TOP_K * 2)}
    if picks is None:
        picks = jev_pick(prompt, lessons, exclude) if use_jev else {}
    by_id = {x.id: x for x in active(lessons)}
    ids = set(kw) | {i for i in picks if i in by_id}
    def rank(i: str) -> tuple:
        return (-(i in kw and i in picks), -picks.get(i, 0.0), -(kw[i][0] if i in kw else 0.0), i)
    out = []
    for i in sorted(ids, key=rank)[:PROMPT_TOP_K]:
        src = "both" if i in kw and i in picks else ("kw" if i in kw else "jev")
        out.append((src, by_id[i]))
    return out


def core(lessons: list[Lesson]) -> list[Lesson]:
    pool = [x for x in active(lessons) if x.strength >= CORE_MIN_STRENGTH]
    pool.sort(key=lambda x: (-x.strength, x.confirmed or x.created), reverse=False)
    pool.sort(
        key=lambda x: -x.strength
    )  # stable: strongest first, then oldest-confirmed
    chosen: list[Lesson] = []
    used = 0
    for x in pool:
        line = len(x.rule) + len(x.id) + 6
        if len(chosen) >= CORE_MAX_ITEMS or used + line > CORE_MAX_CHARS:
            break
        chosen.append(x)
        used += line
    return chosen


def bullet(x: Lesson) -> str:
    return f"- {x.rule} [{x.id}]"


# ---------------------------------------------------------------------------------------------
# similarity / maintenance
def similarity(a: Lesson, b: Lesson) -> float:
    ta, tb = a.terms, b.terms
    return len(ta & tb) / len(ta | tb) if ta and tb else 0.0


def neighbours(
    new: Lesson, lessons: list[Lesson], k: int = 3, floor: float = 0.12
) -> list[tuple[float, Lesson]]:
    sims = [(similarity(new, x), x) for x in active(lessons) if x.id != new.id]
    sims = [s for s in sims if s[0] >= floor]
    sims.sort(key=lambda s: -s[0])
    return sims[:k]


def jev_relations(new: Lesson, others: list[Lesson]) -> dict[str, tuple[str, float]]:
    """{other_id: (relation, confidence)} via one Jev call; {} when Jev is unavailable or fails."""
    if not others:
        return {}
    try:
        sys.path.insert(0, str(ROOT))
        from execution.modules import jev_client as jev  # noqa: PLC0415
    except Exception:  # noqa: BLE001 — optional dependency; lexical path takes over
        return {}
    if not jev.available():
        return {}
    opts = {
        "duplicate": "says the same thing; following one means following the other",
        "contradicts": "following one would break the other (incompatible instructions)",
        "refines": "same topic; one narrows, extends or updates the other without contradicting it",
        "unrelated": "different topic or compatible guidance",
    }
    state = {"new_lesson": new.rule}
    qs = {}
    for i, o in enumerate(others):
        state[f"existing_{i}"] = o.rule
        qs[f"rel_{i}"] = jev.choice(
            f"How does new_lesson relate to existing_{i}?", opts
        )
    try:
        r = jev.decide(state, qs, timeout_s=8)
    except Exception:  # noqa: BLE001
        return {}
    if r.error:
        return {}
    try:
        jev.append_ledger(
            {"caller": "brain", "cost": r.cost_usd}, tmp_dir() / "jev_ledger.jsonl"
        )
    except Exception:  # noqa: BLE001
        pass
    return {
        o.id: (r.choice(f"rel_{i}"), r.confidence(f"rel_{i}"))
        for i, o in enumerate(others)
    }


def days_since(iso: str) -> int:
    try:
        return (today() - dt.date.fromisoformat(iso)).days
    except ValueError:
        return 0


def lint(
    lessons: list[Lesson], errors: list[str], deep: bool = False
) -> dict[str, Any]:
    act = active(lessons)
    report: dict[str, Any] = {
        "errors": list(errors),
        "duplicates": [],
        "conflicts": [],
        "decay": [],
        "over_cap": [],
        "fixes": [],
    }
    for x in act:
        if len(x.rule) > RULE_MAX:
            report["errors"].append(f"{x.id}: rule {len(x.rule)} chars > {RULE_MAX}")
        if not x.triggers:
            report["errors"].append(f"{x.id}: no triggers (never retrieved per prompt)")
        if x.scope not in SCOPES:
            report["errors"].append(f"{x.id}: unknown scope '{x.scope}'")
    for i, a in enumerate(act):
        for b in act[i + 1 :]:
            s = similarity(a, b)
            if s >= 0.5:
                report["duplicates"].append((a.id, b.id, round(s, 2), "lex"))
    for x in act:
        if x.strength <= 1 and days_since(x.confirmed or x.created) > DECAY_DAYS:
            report["decay"].append(x.id)
    if len(act) > MAX_ACTIVE:
        ranked = sorted(act, key=lambda x: (x.strength, x.confirmed or x.created))
        report["over_cap"] = [x.id for x in ranked[: len(act) - MAX_ACTIVE]]
    if deep:
        pairs: list[tuple[Lesson, list[Lesson]]] = []
        seen: set[tuple[str, str]] = set()
        for x in act:
            near = []
            for _, o in neighbours(x, act, k=3, floor=DEEP_FLOOR):
                key = tuple(sorted((x.id, o.id)))
                if key not in seen:
                    seen.add(key)
                    near.append(o)
            if near:
                pairs.append((x, near))
        from concurrent.futures import ThreadPoolExecutor  # noqa: PLC0415

        with ThreadPoolExecutor(max_workers=8) as pool:  # results returned, no shared state mutated
            results = list(pool.map(lambda p: (p[0], jev_relations(p[0], p[1])), pairs))
        report["jev_checked"] = sum(len(r) for _, r in results)
        for x, rels in results:
            for oid, (rel, conf) in rels.items():
                if conf >= 0.7 and rel in ("duplicate", "contradicts"):
                    key = "duplicates" if rel == "duplicate" else "conflicts"
                    report[key].append((x.id, oid, round(conf, 2), "jev"))
    return report


def apply_lint(report: dict[str, Any]) -> list[str]:
    done: list[str] = []
    for lid in report["decay"] + report["over_cap"]:
        les = find(lid, include_archive=False)
        if les and les.status == "active":
            les.status = "archived"
            save(les)
            done.append(f"archived {lid}")
    for a, b, val, how in report["duplicates"]:
        if how == "lex" and val < 0.7:  # weak lexical overlap is reported, never auto-merged
            continue
        la, lb = find(a, False), find(b, False)
        if not la or not lb or la.status != "active" or lb.status != "active":
            continue
        keep, drop = sorted(
            (la, lb), key=lambda x: (-x.strength, -(len(x.triggers)), x.id)
        )
        keep.strength = min(5, max(keep.strength, drop.strength))
        keep.triggers = sorted(set(keep.triggers) | set(drop.triggers))[:12]
        keep.supersedes = sorted(set(keep.supersedes) | {drop.id})
        keep.confirmed = max(keep.confirmed, drop.confirmed)
        drop.status = "archived"
        save(keep)
        save(drop)
        done.append(f"merged {drop.id} -> {keep.id}")
    return done


def read_state() -> dict[str, Any]:
    try:
        return json.loads((brain_dir() / "state.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def write_state(st: dict[str, Any]) -> None:
    p = brain_dir() / "state.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(
        json.dumps(st, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )


# ---------------------------------------------------------------------------------------------
# session state (per-session dedupe of injected lessons)
def _session_file(session_id: str) -> Path:
    safe = re.sub(r"[^A-Za-z0-9_-]", "", session_id or "nosession")[:80] or "nosession"
    return tmp_dir() / "brain_sessions" / f"{safe}.json"


def session_get(session_id: str) -> dict[str, Any]:
    try:
        return json.loads(_session_file(session_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {"injected": [], "nudges": 0}


def session_put(session_id: str, st: dict[str, Any]) -> None:
    p = _session_file(session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st), encoding="utf-8")
    cutoff = time.time() - 14 * 86400
    for old in p.parent.glob("*.json"):
        try:
            if old.stat().st_mtime < cutoff:
                old.unlink()
        except OSError:  # stale dedupe file vanished or locked: skipping it is harmless
            continue


# ---------------------------------------------------------------------------------------------
# hooks
def _ctx(event: str, text: str) -> str:
    return json.dumps(
        {"hookSpecificOutput": {"hookEventName": event, "additionalContext": text}}
    )


def hook_start(payload: dict[str, Any]) -> str:
    lessons, errors = load()
    act = active(lessons)
    if not act and not errors:
        return ""
    chosen = core(lessons)
    lines = [
        f"## Brain: {len(act)} lessons from past mistakes (core below; matching ones auto-inject per prompt)",
        "Obey these; copy the relevant ones into sub-agent briefs.",
    ]
    lines += [bullet(x) for x in chosen]
    lines.append(
        f"Capture: when the operator corrects you or you admit a miss, fix it, then record it: "
        f'`{CAPTURE_CMD} add --rule "<imperative>" --why "<incident, date>" --triggers "<words>"` '
        f"(or `repeat <id>` if a lesson already covered it). Commit `.claude/brain/` with the work."
    )
    rep = lint(lessons, errors)
    issues = (
        len(rep["errors"])
        + len(rep["duplicates"])
        + len(rep["decay"])
        + len(rep["over_cap"])
    )
    last_deep = read_state().get("last_deep", "")
    deep_due = not last_deep or days_since(last_deep) >= DEEP_EVERY_DAYS
    if issues or deep_due:
        why = f"{issues} issue(s)" if issues else "weekly conflict check due"
        lines.append(
            f"Brain upkeep ({why}): run `{CAPTURE_CMD} lint --deep --apply`, resolve any conflict "
            f"with `supersede`, commit. Do it in a background sub-agent; do not mention it unless it fails."
        )
    lines += eval_lines()
    session_put(
        str(payload.get("session_id") or ""),
        {"injected": [x.id for x in chosen], "nudges": 0},
    )
    return _ctx("SessionStart", "\n".join(lines))


EVAL_EVERY_DAYS = 7
EVAL_OVERDUE_DAYS = 9


def eval_lines() -> list[str]:
    """Weekly self-evaluation (brain_eval.py): due / overdue flags, and a non-PASS verdict surfaced to the
    operator. The verdict is read from the hash-chained history, never recomputed or softened here."""
    hist = brain_dir() / "eval" / "history.jsonl"
    last: dict[str, Any] = {}
    try:
        rows = [ln for ln in hist.read_text(encoding="utf-8").splitlines() if ln.strip()]
        last = json.loads(rows[-1]) if rows else {}
    except (OSError, ValueError):
        last = {}
    out: list[str] = []
    age = days_since(last["date"]) if last.get("date") else 10_000
    cmd = "python3 execution/infrastructure/brain_eval.py run --label"
    if age >= EVAL_OVERDUE_DAYS and last:
        out.append(f"Brain eval OVERDUE ({age} days since {last['date']}): run `{cmd}` in a background worker, commit "
                   f".claude/brain/eval/, and tell the operator in one line that it was overdue.")
    elif age >= EVAL_EVERY_DAYS:
        out.append(f"Brain eval due: run `{cmd}` in a background worker and commit .claude/brain/eval/.")
    verdict = str(last.get("verdict", ""))
    if verdict == "PASS-PARTIAL" and age <= 1:
        out.append(f"Brain eval {last.get('date')}: PASS-PARTIAL (some KPIs unmeasured: "
                   f"{', '.join(c for c in last.get('codes', []) if c != 'dead_lesson')[:120]}). "
                   f"Tell the operator in one line in your first reply.")
    if verdict in ("WARN", "FAIL"):
        codes = ", ".join(last.get("codes", [])[:4])
        out.append(f"Brain eval {last.get('date')}: {verdict} ({codes}). Tell the operator in one line in your first "
                   f"reply and fix the top fault line (report: .claude/brain/eval/reports/{last.get('date')}.md).")
    return out


_MACHINE_MARKERS = ("<task-notification", "<agent-message", "[SYSTEM NOTIFICATION", "<system-reminder",
                    "[Subagent hand-back]", "<webhook-payload", "<wake ", "<child-session-event")


def _machine_turn(prompt: str) -> bool:
    """Background-agent reports, task notifications and webhooks are not operator prompts."""
    head = prompt.lstrip()[:400]
    return head.startswith("<") or any(m in head for m in _MACHINE_MARKERS)


def hook_prompt(payload: dict[str, Any]) -> str:
    prompt = str(payload.get("prompt") or "")
    sid = str(payload.get("session_id") or "")
    if len(prompt.strip()) < 12 or _machine_turn(prompt):
        st = session_get(sid)
        if st.get("turn"):
            st["turn"] = None  # a machine turn must not inherit the previous prompt's evidence
            session_put(sid, st)
        return ""
    st = session_get(sid)
    lessons, _ = load()
    hits = retrieve_hybrid(prompt, lessons, exclude=set(st.get("injected", [])))
    sources = {x.id: src for src, x in hits}
    lines: list[str] = []
    used = 0
    for _, x in hits:
        b = bullet(x)
        if used + len(b) > PROMPT_MAX_CHARS:
            break
        lines.append(b)
        used += len(b)
    out: list[str] = []
    if lines:
        out.append("Brain — lessons that apply to this prompt:\n" + "\n".join(lines))
        st["injected"] = list(
            dict.fromkeys(
                st.get("injected", [])
                + [ln.rsplit("[", 1)[1].rstrip("]") for ln in lines]
            )
        )
    if CORRECTION_RE.search(prompt):
        out.append(
            f"Brain: this reads like an operator correction. Verify against the source first; if it is a "
            f"real miss, fix it, then `{CAPTURE_CMD} add ...` (or `repeat <id>` if a lesson above already "
            f"said so). No apology; state the rule you are adopting."
        )
        st["corrected"] = True
    # Evidence for the weekly eval (brain_eval.py): kept in .tmp only; the Stop hook distils it
    # into a text-free observation row. Lesson ids are snapshotted so a lesson written during this
    # turn is never counted as "already known".
    st["turns"] = int(st.get("turns", 0)) + 1
    st["turn"] = {
        "prompt": prompt[:2000],
        # counter suffix: the same prompt sent twice is two turns, logged twice
        "sha": hashlib.sha256(prompt.encode("utf-8")).hexdigest()[:12] + f"-{int(st.get('turns', 0)) + 1}",
        "injected": [ln.rsplit("[", 1)[1].rstrip("]") for ln in lines],
        "sources": {i: sources.get(i, "kw") for i in [ln.rsplit("[", 1)[1].rstrip("]") for ln in lines]},
        "correction": bool(CORRECTION_RE.search(prompt)),
        "known": [x.id for x in active(lessons)],
        "seen": list(st.get("injected", [])),
    }
    session_put(sid, st)
    if not out:
        return ""
    return _ctx("UserPromptSubmit", "\n".join(out))


def _turn_messages(transcript_path: str, max_bytes: int = 3_000_000) -> tuple[str, str]:
    """Return (assistant_text, tool_commands) for the current turn (since the last real user prompt)."""
    p = Path(transcript_path)
    size = p.stat().st_size
    with p.open("rb") as fh:
        if size > max_bytes:
            fh.seek(size - max_bytes)
        raw = fh.read().decode("utf-8", "replace")
    rows = []
    for line in raw.splitlines():
        try:
            rows.append(json.loads(line))
        except ValueError:
            continue
    start = 0
    for i, r in enumerate(rows):
        msg = r.get("message") or {}
        if r.get("type") == "user" and msg.get("role") == "user":
            content = msg.get("content")
            is_tool_result = isinstance(content, list) and any(
                isinstance(c, dict) and c.get("type") == "tool_result" for c in content
            )
            if not is_tool_result:
                start = i
    texts, cmds = [], []
    for r in rows[start:]:
        msg = r.get("message") or {}
        if msg.get("role") != "assistant":
            continue
        content = msg.get("content")
        if isinstance(content, str):
            texts.append(content)
            continue
        for c in content or []:
            if not isinstance(c, dict):
                continue
            if c.get("type") == "text":
                texts.append(str(c.get("text", "")))
            elif c.get("type") == "tool_use":
                cmds.append(json.dumps(c.get("input", {})))
    return "\n".join(texts), "\n".join(cmds)


def _jev_enabled() -> bool:
    """Respect `/jev off` (confidential work): no prompt text leaves the machine when it is off."""
    try:
        state = json.loads((ROOT / ".claude" / "jev" / "state.json").read_text(encoding="utf-8"))
        return bool(state.get("enabled", True))
    except (OSError, ValueError):
        return True


def judge_turn(prompt: str, injected: list[Lesson], known: list[Lesson], correction: bool) -> dict[str, Any]:
    """Independent judge (Jev) for one turn: is each injected lesson relevant, and did an existing
    lesson already cover the operator's correction? {} when Jev is unavailable, off, or fails."""
    if not _jev_enabled() or not (injected or (correction and known)):
        return {}
    try:
        sys.path.insert(0, str(ROOT))
        from execution.modules import jev_client as jev  # noqa: PLC0415
    except Exception as exc:  # noqa: BLE001 — optional dependency
        print(f"brain judge: jev import failed: {exc}", file=sys.stderr)
        return {}
    if not jev.available():
        return {}
    qs: dict[str, Any] = {}
    for i, x in enumerate(injected):
        qs[f"rel_{i}"] = jev.noul(
            f"Lesson: {x.rule} -- Does following this lesson matter for doing the operator_prompt's task correctly?",
            "the task touches what the lesson governs, so ignoring it could repeat the mistake",
            "the lesson is about a different kind of work than this prompt",
        )
    if correction and known:
        menu = {x.id: x.rule[:200] for x in known[:100]}
        menu["none"] = "no existing lesson covers what the operator is correcting"
        qs["covered"] = jev.choice(
            "The operator_prompt corrects the assistant. Which existing lesson, if followed, would have prevented this miss?",
            menu,
        )
    try:
        r = jev.decide({"operator_prompt": prompt[:4000]}, qs, timeout_s=6)
    except Exception as exc:  # noqa: BLE001 — judging is advisory; never break the Stop hook
        print(f"brain judge: {exc}", file=sys.stderr)
        return {}
    if r.error:
        return {}
    try:
        jev.append_ledger({"caller": "brain_judge", "cost": r.cost_usd}, tmp_dir() / "jev_ledger.jsonl")
    except Exception as exc:  # noqa: BLE001 — telemetry only
        print(f"brain judge ledger: {exc}", file=sys.stderr)
    out: dict[str, Any] = {"relevance": {x.id: round(r.noul(f"rel_{i}"), 3) for i, x in enumerate(injected)}}
    if "covered" in qs:
        out["covered_by"] = r.choice("covered")
        out["covered_p"] = round(r.confidence("covered"), 3)
    return out


def obs_dir() -> Path:
    return brain_dir() / "eval" / "observations"


def log_observation(sid: str, st: dict[str, Any], admitted: bool, recorded: bool) -> None:
    """Append one text-free evidence row for this turn (once per turn). Committed with the work so the
    weekly eval survives ephemeral cloud containers. Never stores prompt text."""
    turn = st.get("turn") or {}
    injected_ids = list(turn.get("injected", []))
    correction = bool(turn.get("correction"))
    if not (injected_ids or correction or admitted):
        return
    key = f"{turn.get('sha', 'none')}:{len(st.get('logged', []))}"
    if turn.get("sha") and turn.get("sha") in st.get("logged", []):
        return
    lessons, _ = load()
    by_id = {x.id: x for x in lessons}
    known = [by_id[i] for i in turn.get("known", []) if i in by_id]
    sources = dict(turn.get("sources") or {})
    # Independence: Jev never grades a lesson Jev itself picked; only keyword picks are judged live.
    judged_ids = [i for i in injected_ids if i in by_id and sources.get(i, "kw") == "kw"]
    verdict = judge_turn(str(turn.get("prompt", "")), [by_id[i] for i in judged_ids], known, correction)
    covered = verdict.get("covered_by")
    seen = set(turn.get("seen", [])) | set(injected_ids)
    row = {
        "v": 1, "date": today().isoformat(), "sid": re.sub(r"[^A-Za-z0-9]", "", sid)[:8],
        "turn": turn.get("sha", key), "injected": injected_ids, "sources": sources, "correction": correction,
        "admitted": admitted, "recorded": recorded, "judged": bool(verdict),
        "relevance": verdict.get("relevance", {}),
        "covered_by": covered if covered and covered != "none" else None,
        "covered_p": verdict.get("covered_p"),
        "covered_was_shown": bool(covered and covered in seen),
    }
    d = obs_dir()
    d.mkdir(parents=True, exist_ok=True)
    with (d / f"{row['date']}-{row['sid'] or 'nosession'}.jsonl").open("a", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")
    if turn.get("sha"):
        st["logged"] = (st.get("logged", []) + [turn["sha"]])[-200:]


def hook_stop(payload: dict[str, Any]) -> str:
    tp = str(payload.get("transcript_path") or "")
    if not tp or not Path(tp).is_file():
        return ""
    sid = str(payload.get("session_id") or "")
    st = session_get(sid)
    text, cmds = _turn_messages(tp)
    text = QUOTED_RE.sub(" ", text)  # quoted client words / code are not the assistant's admission
    admitted = bool(ADMISSION_RE.search(text))
    recorded = bool(BRAIN_CMD_RE.search(cmds) or BRAIN_CMD_RE.search(text))
    nudge = admitted and not recorded and not payload.get("stop_hook_active") and int(st.get("nudges", 0)) < 3
    if not nudge:
        try:
            log_observation(sid, st, admitted, recorded)
        except Exception as exc:  # noqa: BLE001 — evidence logging must never break the session
            print(f"brain observation: {exc}", file=sys.stderr)
        session_put(sid, st)
        return ""
    st["nudges"] = int(st.get("nudges", 0)) + 1
    session_put(sid, st)
    reason = (
        f"Brain capture: you admitted a miss this turn but did not record it. Run "
        f'`{CAPTURE_CMD} search "<topic>"`; if a lesson already covered it run `repeat <id>`, else '
        f'`add --rule "<one imperative line>" --why "<what happened, date>" --triggers "<4-8 words a '
        f"future prompt would contain>\"`. If it was not a real miss, reply 'no lesson' in one line."
    )
    return json.dumps({"decision": "block", "reason": reason})


# ---------------------------------------------------------------------------------------------
# commands
def slug(text: str, n: int = 6) -> str:
    ws = [w for w in words(text) if w not in STOP and re.match(r"^[a-z0-9-]+$", w)][:n]
    return "-".join(ws) or "lesson"


def cmd_add(a: argparse.Namespace) -> int:
    date = a.date or today().isoformat()
    rule = " ".join(a.rule.split())
    if len(rule) > RULE_MAX:
        print(
            f"refused: rule is {len(rule)} chars; keep it one imperative line <= {RULE_MAX}."
        )
        return 2
    triggers = _split_list(a.triggers)
    if not triggers:
        print("refused: give --triggers (4-8 words a future prompt would contain).")
        return 2
    if a.scope not in SCOPES:
        print(f"refused: --scope must be one of {', '.join(SCOPES)}")
        return 2
    lid = a.id or f"{date}-{slug(rule)}"
    if not ID_RE.match(lid):
        print("refused: --id may contain only a-z, 0-9 and '-' (max 100 chars).")
        return 2
    lessons, _ = load(include_archive=True)
    if any(x.id == lid for x in lessons):
        lid = f"{lid}-{sum(1 for x in lessons if x.id.startswith(lid)) + 1}"
    new = Lesson(
        id=lid,
        rule=rule,
        why=" ".join((a.why or "").split())[:WHY_MAX],
        triggers=triggers[:12],
        scope=a.scope,
        strength=max(1, min(5, a.strength)),
        created=date,
        confirmed=date,
        source=a.source or "",
    )
    near = [] if a.force else neighbours(new, lessons, floor=ADD_FLOOR)
    rels = jev_relations(new, [o for _, o in near]) if near else {}
    for sim, o in near:
        rel, conf = rels.get(o.id, ("", 0.0))
        if (rel == "duplicate" and conf >= 0.7) or sim >= 0.6:
            if a.dry_run:
                print(f"[dry-run] duplicate of {o.id} -> would strengthen it instead")
                return 0
            o.strength = min(5, o.strength + 1)
            o.confirmed = date
            o.triggers = sorted(set(o.triggers) | set(triggers))[:12]
            save(o)
            print(
                f"duplicate of {o.id} -> strengthened it to {o.strength} (no new file). "
                f"{'Now in core.' if o.strength >= CORE_MIN_STRENGTH else ''}".strip()
            )
            return 0
    blockers = []
    for sim, o in near:
        rel, conf = rels.get(o.id, ("", 0.0))
        if rel == "contradicts" and conf >= 0.7 and o.id not in a.supersede:
            blockers.append(f"  contradicts {o.id} (jev {conf:.2f}, strength {o.strength}): {o.rule[:160]}")
        elif rel == "refines" and conf >= 0.8 and not a.force:
            blockers.append(f"  restates {o.id} (jev refines {conf:.2f}): {o.rule[:160]}")
    if blockers:
        print("not added:")
        print("\n".join(blockers))
        print(
            "  If the old rule is wrong now, re-run with `--supersede <old_id>` (needs evidence newer than its source). "
            "If yours restates it, run `repeat <old_id> --why ...` instead; `--force` only for a genuinely new angle."
        )
        return 3
    if a.dry_run:
        print(f"[dry-run] would write {lid}")
        print(new.render())
        return 0
    for old_id in a.supersede:
        old = find(old_id, include_archive=False)
        if old:
            old.status = "archived"
            save(old)
            new.supersedes = sorted(set(new.supersedes) | {old.id})
            new.strength = max(new.strength, old.strength)
            print(f"  superseded {old.id} (archived; `restore {old.id}` undoes)")
    path = save(new)
    print(f"added {lid} -> {path.relative_to(ROOT) if path.is_relative_to(ROOT) else path}")
    for sim, o in near:
        if o.id in a.supersede:
            continue
        rel, conf = rels.get(o.id, ("", 0.0))
        tag = f"jev: {rel} {conf:.2f}" if rel else f"sim {sim:.2f}"
        print(f"  near {o.id} ({tag}): {o.rule[:140]}")
    if near and not rels:
        print("  Jev unavailable: check the near lessons yourself; `supersede <old> <new>` if one is outdated.")
    return 0


def cmd_repeat(a: argparse.Namespace) -> int:
    les = find(a.id)
    if not les:
        print(f"no lesson {a.id}")
        return 2
    les.strength = min(5, les.strength + 1)
    les.confirmed = today().isoformat()
    les.status = "active"
    if a.why:
        les.why = (les.why + f" Repeated {les.confirmed}: {a.why}")[-WHY_MAX * 2 :]
    save(les)
    print(
        f"{les.id} strength -> {les.strength}{' (core: loads every session)' if les.strength >= CORE_MIN_STRENGTH else ''}"
    )
    return 0


def cmd_set_status(a: argparse.Namespace, status: str) -> int:
    les = find(a.id)
    if not les:
        print(f"no lesson {a.id}")
        return 2
    les.status = status
    if status == "active":
        les.confirmed = today().isoformat()
        for other in active(load()[0]):
            if les.id in other.supersedes:
                other.supersedes = [x for x in other.supersedes if x != les.id]
                save(other)
    save(les)
    print(f"{les.id} -> {status}")
    return 0


def cmd_supersede(a: argparse.Namespace) -> int:
    old, new = find(a.old), find(a.new)
    if not old or not new:
        print("both ids must exist")
        return 2
    old.status = "archived"
    new.supersedes = sorted(set(new.supersedes) | {old.id})
    new.strength = max(new.strength, old.strength)
    save(old)
    save(new)
    print(f"{old.id} archived, superseded by {new.id} (strength {new.strength})")
    return 0


def cmd_lint(a: argparse.Namespace) -> int:
    lessons, errors = load()
    rep = lint(lessons, errors, deep=a.deep)
    if a.apply:
        rep["fixes"] = apply_lint(rep)
    if a.deep:
        st = read_state()
        st["last_deep"] = today().isoformat()
        write_state(st)
    act = active(lessons)
    if a.deep:
        n = rep.get("jev_checked", 0)
        print(
            f"jev pair checks: {n}" + ("" if n else " (Jev unavailable: lexical only)")
        )
    print(
        f"active {len(act)}  core {len(core(lessons))}  core chars "
        f"{sum(len(bullet(x)) for x in core(lessons))}/{CORE_MAX_CHARS}"
    )
    for k in ("errors", "duplicates", "conflicts", "decay", "over_cap", "fixes"):
        if rep[k]:
            print(f"{k}:")
            for item in rep[k]:
                print(f"  {item}")
    if rep["conflicts"]:
        print(
            "Resolve each conflict: keep the newer/operator-ordered rule -> `supersede <old> <new>`."
        )
    return 1 if rep["errors"] else 0


def cmd_search(a: argparse.Namespace) -> int:
    lessons, _ = load()
    hits = retrieve(a.text, lessons, top_k=a.k, min_score=0.1)
    if not hits:
        q = content_words(a.text)
        hits = sorted(
            ((len(q & x.terms) / 1.0, x) for x in active(lessons) if q & x.terms),
            key=lambda s: -s[0],
        )[: a.k]
    for s, x in hits:
        print(f"{s:5.2f}  {x.id}  (s{x.strength})  {x.rule}")
    if not hits:
        print("no matching lesson")
    return 0


def cmd_list(a: argparse.Namespace) -> int:
    lessons, errors = load(include_archive=a.all)
    for x in sorted(lessons, key=lambda x: (-x.strength, x.id)):
        print(f"s{x.strength} {x.status[:3]} {x.scope:<7} {x.id}: {x.rule}")
    for e in errors:
        print(f"ERROR {e}")
    return 0


def cmd_status(_: argparse.Namespace) -> int:
    lessons, errors = load(include_archive=True)
    act = active(lessons)
    c = core(lessons)
    print(
        f"brain: {len(act)} active, {len(lessons) - len(act)} archived, {len(errors)} bad files"
    )
    print(
        f"core (every session): {len(c)} lessons, {sum(len(bullet(x)) for x in c)} chars "
        f"(cap {CORE_MAX_CHARS}); per-prompt cap {PROMPT_TOP_K} lessons / {PROMPT_MAX_CHARS} chars"
    )
    print(f"last deep check: {read_state().get('last_deep', 'never')}")
    return 0


def main(argv: list[str]) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if argv and argv[0] in ("hook-start", "hook-prompt", "hook-stop"):
        try:
            payload = json.loads(sys.stdin.read() or "{}")
            fn = {
                "hook-start": hook_start,
                "hook-prompt": hook_prompt,
                "hook-stop": hook_stop,
            }[argv[0]]
            sys.stdout.write(fn(payload if isinstance(payload, dict) else {}))
        except Exception as exc:  # noqa: BLE001 — a hook must never block or break a session
            print(f"brain {argv[0]}: {exc}", file=sys.stderr)
        return 0
    ap = argparse.ArgumentParser(
        prog="brain.py", description="Workspace brain: lessons from past mistakes."
    )
    sub = ap.add_subparsers(dest="cmd")
    sub.add_parser("status")
    sub.add_parser("core")
    p = sub.add_parser("list")
    p.add_argument("--all", action="store_true")
    p = sub.add_parser("search")
    p.add_argument("text")
    p.add_argument("-k", type=int, default=5)
    p = sub.add_parser("add")
    p.add_argument("--rule", required=True)
    p.add_argument("--why", default="")
    p.add_argument("--triggers", required=True)
    p.add_argument("--scope", default="all")
    p.add_argument("--source", default="")
    p.add_argument("--strength", type=int, default=2)
    p.add_argument("--date", default="")
    p.add_argument("--id", default="")
    p.add_argument(
        "--force", action="store_true", help="skip duplicate/conflict checks"
    )
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--supersede", action="append", default=[], help="archive this lesson id (repeatable)")
    for name in ("repeat", "archive", "restore"):
        p = sub.add_parser(name)
        p.add_argument("id")
        if name == "repeat":
            p.add_argument("--why", default="")
    p = sub.add_parser("supersede")
    p.add_argument("old")
    p.add_argument("new")
    p = sub.add_parser("lint")
    p.add_argument(
        "--deep",
        action="store_true",
        help="Jev duplicate/contradiction scan over near pairs",
    )
    p.add_argument(
        "--apply",
        action="store_true",
        help="archive decayed/over-cap, merge duplicates",
    )
    a = ap.parse_args(argv)
    if a.cmd == "core":
        lessons, _ = load()
        print("\n".join(bullet(x) for x in core(lessons)) or "(no core lessons)")
        return 0
    handlers = {
        "status": cmd_status,
        "list": cmd_list,
        "search": cmd_search,
        "add": cmd_add,
        "repeat": cmd_repeat,
        "supersede": cmd_supersede,
        "lint": cmd_lint,
        "archive": lambda x: cmd_set_status(x, "archived"),
        "restore": lambda x: cmd_set_status(x, "active"),
    }
    if a.cmd not in handlers:
        ap.print_help()
        return 0
    return handlers[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
