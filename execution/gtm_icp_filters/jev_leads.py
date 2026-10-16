"""Qualify, enrich-check and route B2B leads with Jev (TypeSafe decisions via OpenRouter).

description: One script, nine lead-pipeline scenarios, ONE Jev call per row each:
             qualify (ICP fit + 0-100 jev_fit, reach-out, persona -> go/hold/skip), signals
             (funding, hiring, new budget owner -> contact/watch/none), hygiene (clean/fix/drop),
             suppress (customer/competitor -> suppress/allow), replies (cold-email reply intent),
             inbound (form-fill routing), diff (what changed since a snapshot -> contact/ignore),
             factcheck (draft first line vs facts -> send/fix/block) and message_score (draft ->
             send/revise). Decision rules are deterministic code over Jev's typed answers;
             low-confidence rows are flagged jev_review. Directive: directives/gtm_icp_filters/jev_leads.md
inputs: <scenario> --input CSV|JSON list of dicts; --icp profile JSON
        (execution/gtm_icp_filters/icp_profiles/_template.json); --output (default
        .tmp/jev_leads_<scenario>.json); --csv-out; --md; --min-confidence (0.6); --workers (8);
        --limit; --dry-run; --validate labels.csv (id,label) [--validate-question NAME];
        --snapshot prev.csv|json (diff only); --only-pass (csv-out keeps go/contact/sales/send);
        --fields a,b,c (columns sent to Jev; default per-scenario allowlist; denylist always dropped);
        --cache PATH (default .tmp/jev_leads_cache.json; "none" disables).
        env OPENROUTER_API_KEY (or OPENROUTER_API_TOKEN / OPENROUTER_API_TOEKN).
outputs: JSON {summary, rows, validation}; optional CSV (input cols + jev_*) and markdown top-25
         table; stdout summary; answer cache file; ledger row in .tmp/jev_ledger.jsonl (caller "jev_leads").
         Exit 0 ok, 1 bad input, 2 missing OpenRouter key (unless --dry-run).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

load_dotenv()

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from execution.modules import jev_client  # noqa: E402
from execution.modules.jev_client import choice, noul, score  # noqa: E402

# Bump whenever any question wording, option set or state shape changes (invalidates the cache).
QUESTION_VERSION = "2"
SCENARIOS = ("qualify", "signals", "hygiene", "suppress", "replies", "inbound", "diff",
             "factcheck", "message_score")
DEFAULT_MIN_CONFIDENCE = 0.6
MAX_FIELD_CHARS = 1200
PASS_DECISIONS = {"go", "contact", "sales", "send"}
DEFAULT_CACHE = WORKSPACE / ".tmp" / "jev_leads_cache.json"
DEFAULT_PERSONAS = {
    "economic_buyer": "senior leader who owns the budget for this purchase",
    "champion": "hands-on manager who would push for the purchase internally",
    "user": "individual contributor who would use the product day to day",
}
DEFAULT_FIT_WEIGHTS = {"role_fit": 0.35, "likely_buyer": 0.3, "company_fit": 0.25, "seniority": 0.1}
DEFAULT_FIT_CUTOFFS = {"go": 70, "hold": 45}
CONTEXT_FIELDS = {
    "qualify": ("offer", "icp", "personas", "exclusions", "timing"),
    "signals": ("offer", "icp", "signals"),
    "hygiene": (),
    "suppress": ("customers", "competitors", "exclusions"),
    "replies": ("offer",),
    "inbound": ("offer", "icp", "competitors"),
    "diff": ("offer", "icp", "personas"),
    "factcheck": (),
    "message_score": ("offer",),
}
ID_KEYS = ("id", "email", "lead_id")

# ---- PII: what may leave the machine ------------------------------------------------------
_LEAD_FIELDS = ("first_name", "name", "title", "company", "industry", "company_size", "website_summary",
                "website", "domain", "location", "seniority", "department", "job_posts", "news",
                "previous_title", "previous_company")
_MSG_FIELDS = ("subject", "body", "message", "from", "from_domain", "form_fields", "source",
               "title", "company")
DEFAULT_FIELDS: dict[str, tuple[str, ...]] = {
    "qualify": _LEAD_FIELDS, "signals": _LEAD_FIELDS, "suppress": _LEAD_FIELDS, "diff": _LEAD_FIELDS,
    "hygiene": ("first_name", "last_name", "name", "company", "title", "email"),
    "replies": _MSG_FIELDS, "inbound": _MSG_FIELDS,
    "factcheck": _LEAD_FIELDS + ("draft",), "message_score": _LEAD_FIELDS + ("draft",),
}
# Never sent, even if named in --fields. linkedin_url is used locally for diff matching only.
DENY_FIELDS = frozenset({"phone", "mobile", "address", "street", "notes", "linkedin_url", "linkedin"})
# Person identity left out of the cache key so same title+company+context shares one answer.
_IDENTITY_FIELDS = ("name", "first_name", "last_name", "email")
_ANON_CACHE = {"qualify", "suppress", "signals"}


# ---- inputs ------------------------------------------------------------------------------

def load_rows(path: Path) -> list[dict[str, Any]]:
    """CSV or JSON list of dicts (a dict with a 'leads'/'rows' list is accepted too)."""
    if path.suffix.lower() == ".csv":
        with open(path, encoding="utf-8-sig", newline="") as fh:
            return [dict(r) for r in csv.DictReader(fh)]
    with open(path, encoding="utf-8-sig") as fh:
        data = json.load(fh)
    if isinstance(data, dict):
        if not any(isinstance(data.get(k), list) for k in ("leads", "rows")):
            raise ValueError("JSON object input needs a 'leads' or 'rows' list")
        data = data.get("leads") if isinstance(data.get("leads"), list) else data["rows"]
    if not isinstance(data, list):
        raise ValueError("input must be a JSON list or CSV")
    return [r for r in data if isinstance(r, dict)]


def load_icp(path: Path | None) -> dict[str, Any]:
    if path is None:
        return {}
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)
    if not isinstance(data, dict):
        raise ValueError("ICP profile must be a JSON object")
    return data


def row_id(row: dict[str, Any], idx: int) -> str:
    for k in ID_KEYS:
        v = row.get(k)
        if v not in (None, ""):
            return str(v).strip()
    return str(idx)


def _clean_fields(row: dict[str, Any], allow: tuple[str, ...] | None = None) -> dict[str, Any]:
    out: dict[str, Any] = {}
    for k, v in row.items():
        if k is None or v is None or str(k).startswith("_") or str(k).startswith("jev_"):
            continue
        k = str(k)
        if k.lower() in DENY_FIELDS or (allow is not None and k not in allow):
            continue
        if isinstance(v, (dict, list)):
            v = json.dumps(v, ensure_ascii=False, default=str)
        s = v if isinstance(v, (int, float, bool)) else str(v).strip()
        if s == "":
            continue
        out[k] = s[:MAX_FIELD_CHARS] if isinstance(s, str) else s
    return out


def fingerprint(row: dict[str, Any]) -> str:
    return "|".join(" ".join(str(row.get(k) or "").lower().split()) for k in ("name", "company", "title"))


_KEY_FIELDS = ("email", "id", "linkedin", "linkedin_url", "name")


def _person_keys(row: dict[str, Any]) -> list[str]:
    """Every identity key available for a row: email, id, linkedin, normalised name."""
    keys = []
    for k in _KEY_FIELDS:
        v = " ".join(str(row.get(k) or "").strip().lower().split())
        if k.startswith("linkedin"):
            v = v.rstrip("/").split("?")[0]
            k = "linkedin"
        if v:
            keys.append(f"{k}:{v}")
    return keys


def diff_rows(rows: list[dict[str, Any]], snapshot: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keep new rows and rows whose fingerprint changed; attach the old row under `_old`."""
    prev: dict[str, dict[str, Any]] = {}
    for r in snapshot:
        for k in _person_keys(r):
            prev.setdefault(k, r)
    out = []
    for r in rows:
        old = next((prev[k] for k in _person_keys(r) if k in prev), None)
        if old is None:
            out.append({**r, "_old": None, "jev_diff": "new"})
        elif fingerprint(old) != fingerprint(r):
            out.append({**r, "_old": old, "jev_diff": "changed"})
    return out


# ---- questions / state -------------------------------------------------------------------

_SENIORITY = [  # ic, manager, director, vp, c_level (cookbook recipe 01 wording)
    "An individual contributor who does the work and does not manage people or a budget",
    "A manager or team lead who runs a team and influences what that team buys",
    "A director or head of department who owns the budget for their function",
    "A vice president who owns the budget for their function",
    "A founder, owner, partner or C-level executive who makes final buying decisions",
]


def _budget_qs(cur: str, prev: str) -> dict[str, dict[str, Any]]:
    """Cookbook recipe 02 timing questions; `cur`/`prev` name the state paths."""
    return {
        "new_budget_owner": noul(f"Does the role in `{cur}` own a budget for `context.offer` that the role "
                                 f"in `{prev}` did not?",
                                 true="The new role runs the function that would buy this, and the old role did not",
                                 false="Buying power for this is unchanged, lower, or was already there before"),
        "current_role_buys": noul(f"Is the role in `{cur}` one whose holder decides whether to buy `context.offer`?",
                                  true="They run sales, revenue, growth or the whole company, so they would "
                                       "own this decision",
                                  false="Their function does not buy this, even if the role is senior"),
    }


def build_questions(scenario: str, icp: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if scenario == "qualify":
        personas = dict(icp.get("personas") or DEFAULT_PERSONAS)
        personas["none"] = "this person matches none of the buyer personas"
        return {
            "icp_fit": score("How well does this lead match the ideal customer profile in the context?",
                             ["no_fit", "weak_fit", "good_fit", "strong_fit"]),
            "reach_out": noul("Should we contact this lead now, given the ICP, offer, exclusions and timing?",
                              true="a good prospect we should contact now",
                              false="excluded, off-ICP, bad timing or otherwise not worth contacting now"),
            "persona": choice("Which buyer persona does this person fit?", personas),
            "timing_ok": noul("Is now a reasonable time to reach out, per the timing guidance?",
                              true="nothing suggests now is a bad time",
                              false="a timing rule says wait (holiday, fundraise, just churned ...)"),
            "enough_context": noul("Are there enough facts about this lead to write a personalised first line?",
                                   true="specific facts about the person or company are present",
                                   false="only generic fields; a personalised line would be guesswork"),
            "role_fit": noul("How closely does the role in `lead.title` match the buyers described in "
                             "`context.personas`, given what is sold in `context.offer`?",
                             true="The role is one of the target roles, or works inside the target function and "
                                  "deals with the problem day to day",
                             false="The role has nothing to do with the target roles, or sits in a neighbouring "
                                   "function and would only hear about the problem second-hand"),
            "likely_buyer": noul("Would the person in this role plausibly take part in deciding whether to buy "
                                 "what is described in `context.offer`?",
                                 true="They own, approve or strongly influence this kind of purchase",
                                 false="They would not be involved in this kind of purchase, or they match "
                                       "`context.exclusions`"),
            "company_fit": noul("Judging from `lead.company` and, if given, the company description, does the "
                                "company match `context.icp`?",
                                true="The company is recognisably the kind of company described as a target",
                                false="The company is recognisably outside the target, matches "
                                      "`context.exclusions`, or the information does not reveal what it does"),
            "seniority": score("How senior is the role in `lead.title`?", list(_SENIORITY)),
        }
    if scenario == "signals":
        sig = icp.get("signals") or {}
        return {
            "funding_recent": noul("Did the company raise funding recently?",
                                   true=sig.get("funding", "raised a round in the last 6 months"),
                                   false="no recent funding mentioned"),
            "hiring_outbound": noul("Is the company hiring for outbound / prospect-facing roles?",
                                    true=sig.get("hiring", "hiring SDRs, AEs or sales development leaders"),
                                    false="no such hiring, or only non-prospecting roles"),
            **_budget_qs("lead.title", "lead.previous_title"),
            "signal_strength": score("Overall, how strong are the buying signals for contacting this lead now?",
                                     ["none", "weak", "moderate", "strong"]),
        }
    if scenario == "hygiene":
        return {
            "first_name_clean": noul("Is the first name a clean, correctly-cased human first name?",
                                     true="a usable first name as-is",
                                     false="missing, an initial, all caps, emoji, title or junk"),
            "company_name_clean": noul("Is the company name clean enough to use in an email?",
                                       true="usable as-is (no Inc/LLC clutter, no junk)",
                                       false="missing, legal suffixes, all caps, a URL or junk"),
            "title_is_person_title": noul("Is the title a real job title held by a person?",
                                          true="a real job title",
                                          false="missing, a company tagline, a sentence or junk"),
            "email_looks_work": noul("Does the email look like a work address at the company?",
                                     true="a work domain matching the company",
                                     false="missing, free-mail, role inbox or mismatched domain"),
            "row_usable": noul("Is this row usable for outreach at all?",
                               true="enough valid data to contact a real person",
                               false="junk, test or empty row"),
        }
    if scenario == "suppress":
        return {
            "relation": choice("What is this lead's relationship to us, given the customer list and competitor description?", {
                "customer": "an existing customer on the list (or the same company)",
                "competitor": "a competitor or works for one",
                "partner": "a partner, reseller or integration partner",
                "vendor": "a vendor or supplier of ours",
                "bad_actor": "abusive, fraudulent or previously asked never to be contacted",
                "none": "no special relationship; a normal prospect",
            }),
            "do_not_contact": noul("Should we never contact this lead (suppression list or exclusions)?",
                                   true="matches a customer, competitor, exclusion or do-not-contact rule",
                                   false="fine to contact"),
        }
    if scenario == "replies":
        return {
            "intent": choice("What is the intent of this reply to our cold email?", {
                "interested": "positive, wants to learn more",
                "meeting_requested": "asks for or agrees to a call/meeting",
                "question": "asks a question before deciding",
                "not_now": "maybe later, bad timing",
                "referral": "Points us to a different person who handles this",
                "objection": "Engages but pushes back on price, fit, timing or an existing vendor",
                "not_interested": "declines",
                "unsubscribe": "asks to be removed or stop emailing",
                "wrong_person": "not the right contact and names no one else",
                "out_of_office": "auto-reply: away or on leave",
                "bounce": "delivery failure or mailbox does not exist",
                "competitor": "sender is a competitor or pitching their own offer",
                "none": "none of the above or unreadable",
            }),
            "sentiment": score("What is the sentiment of this reply?", ["negative", "neutral", "positive"]),
            "needs_human": noul("Does this reply need a human to answer?",
                                true="a person should read and respond",
                                false="can be handled automatically or ignored"),
            "remove_request": noul("Does the reply ask, in any wording, to stop being contacted or to be removed "
                                   "from the list?",
                                   true="Any request to stop, remove, unsubscribe or not be contacted again",
                                   false="No request to stop contact"),
        }
    if scenario == "inbound":
        return {
            "real_buyer": noul("Is this inbound from a real potential buyer of our offer?",
                               true="a genuine prospect with a plausible need",
                               false="student, job seeker, vendor pitch, spam or tyre-kicker"),
            "spam": noul("Is this spam or junk?", true="spam, bot or junk", false="a real message"),
            "competitor": noul("Is this from a competitor?", true="a competitor or their agent", false="not a competitor"),
            "urgency": score("How urgent is this inbound?", ["low", "medium", "high"]),
            "budget_signal": noul("Does the message signal budget or buying authority?",
                                  true="mentions budget, timeline, team size or decision power",
                                  false="no budget or authority signal"),
            "route": choice("Where should this inbound go?", {
                "sales": "a qualified buyer; route to sales now",
                "nurture": "real but early or small; add to nurture",
                "ignore": "spam, competitor, job seeker or irrelevant",
                "none": "cannot tell",
            }),
        }
    if scenario == "diff":
        return {
            "change_type": choice("Compare the role in `lead.old` with the role in `lead.new`. "
                                  "What kind of change is this?", {
                "new_company": "moved to a different company",
                "promotion_same_company": "more senior title at the same company",
                "lateral_move": "different title at a similar level",
                "left_buying_function": "moved out of the role that buys our offer",
                "same_job_reworded": "The same job and employer written differently, such as an abbreviation "
                                     "being spelled out or a team name added",
                "none": "no meaningful change or a brand-new record",
            }),
            **_budget_qs("lead.new", "lead.old"),
            "now_worth_contacting": noul("Given the change and our ICP, is this person now worth contacting?",
                                         true="the change makes outreach timely and relevant",
                                         false="not worth contacting because of this change"),
        }
    if scenario == "factcheck":
        return {
            "supported": choice("Do the facts that `first_line` relies on appear in `source`? Ignore greetings "
                                "and well-wishes; judge only the factual claim.", {
                "supported": "The source states or clearly implies the claim",
                "contradicted": "The source says something that conflicts with the claim",
                "unsupported": "The source does not mention it; the claim may be invented",
            }),
            "sounds_creepy": noul("Does `first_line` bring up the recipient's private life?",
                                  true="Mentions health, illness, family members, children, relationships, "
                                       "religion or other personal matters, even if the person shared them publicly",
                                  false="Refers only to their job, company, industry or professional achievements"),
        }
    if scenario == "message_score":
        return {
            "about_them": score("How much is `message` about `prospect` and their situation, rather than about "
                                "the sender?", [
                "Entirely about the sender, their product or their company",
                "Mostly about the sender, with a generic nod to the prospect's industry or role",
                "Refers to something specific about the prospect, but most of the message is the pitch",
                "Built around something specific to the prospect, with the offer secondary",
            ]),
            "pitches_first_line": noul("Does the first sentence of `message` pitch a product, service or meeting?",
                                       true="the first sentence pitches", false="the first sentence does not pitch"),
            "reads_as_template": noul("Would `prospect` recognise `message` as a mass template sent to many people?",
                                      true="Generic flattery, merge-field phrasing, or lines that could be sent "
                                           "to anyone",
                                      false="Could only have been written to this person"),
            "clear_ask": noul("Does `message` end with one clear, low-effort question or request?",
                              true="ends with one clear, low-effort ask",
                              false="no ask, several asks, or a high-effort ask"),
        }
    raise ValueError(f"unknown scenario: {scenario}")


def row_state(row: dict[str, Any], scenario: str, icp: dict[str, Any],
              fields: tuple[str, ...] | None = None) -> dict[str, Any]:
    allow = fields if fields is not None else DEFAULT_FIELDS[scenario]
    ctx = {k: icp[k] for k in CONTEXT_FIELDS[scenario] if icp.get(k)}
    state: dict[str, Any] = {}
    if ctx:
        state["context"] = ctx
    if scenario == "diff":
        old = row.get("_old")
        state["lead"] = {"new": _clean_fields(row, allow), "old": _clean_fields(old, allow) if old else None}
    elif scenario in ("factcheck", "message_score"):
        lead = _clean_fields(row, allow)
        draft = lead.pop("draft", "")
        if scenario == "factcheck":
            state.update({"first_line": draft, "source": lead})
        else:
            state.update({"message": draft, "prospect": lead})
    else:
        state["lead"] = _clean_fields(row, allow)
    return state


# ---- cache -------------------------------------------------------------------------------

def cache_key(state: dict[str, Any], scenario: str) -> str:
    st = state
    if scenario in _ANON_CACHE and isinstance(state.get("lead"), dict):
        st = {**state, "lead": {k: v for k, v in state["lead"].items() if k not in _IDENTITY_FIELDS}}
    ctx_hash = hashlib.sha1(json.dumps(st.get("context") or {}, sort_keys=True, default=str)
                            .encode("utf-8")).hexdigest()
    body = json.dumps({k: v for k, v in st.items() if k != "context"}, sort_keys=True, default=str)
    raw = f"{scenario}|{QUESTION_VERSION}|{ctx_hash}|{body}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()


def load_cache(path: Path | None) -> dict[str, Any]:
    if path is None or not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        print(f"warning: cache unreadable, starting empty: {exc}", file=sys.stderr)
        return {}
    return data if isinstance(data, dict) else {}


def save_cache(path: Path | None, cache: dict[str, Any]) -> None:
    if path is None:
        return
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    except OSError as exc:  # cache is an optimisation; a failed write must not fail the run
        print(f"warning: cache write skipped: {exc}", file=sys.stderr)


def run_with_cache(states: list[dict[str, Any]], qs: dict[str, dict[str, Any]], scenario: str,
                   cache: dict[str, Any] | None, workers: int) -> tuple[list[jev_client.JevResult], list[bool]]:
    """Call Jev only for states without a cached answer set; one call per unique key."""
    keys = [cache_key(s, scenario) for s in states]
    results: list[jev_client.JevResult | None] = [None] * len(states)
    hits = [False] * len(states)
    todo: dict[str, int] = {}
    for i, k in enumerate(keys):
        if cache is not None and k in cache:
            results[i] = jev_client.JevResult(answers=dict(cache[k]["answers"]), model=cache[k].get("model", ""))
            hits[i] = True
        else:
            todo.setdefault(k, i)
    idx = list(todo.values())
    fresh = jev_client.decide_many([states[i] for i in idx], qs, workers=workers) if idx else []
    by_key: dict[str, jev_client.JevResult] = {}
    for i, res in zip(idx, fresh):
        results[i] = res
        by_key[keys[i]] = res
        if cache is not None and res.ok and all(q in res.answers for q in qs):
            cache[keys[i]] = {"answers": res.answers, "model": res.model}
    for i, r in enumerate(results):
        if r is None:  # duplicate key within this run: reuse the first call's answers at no cost
            src = by_key[keys[i]]
            results[i] = jev_client.JevResult(answers=dict(src.answers), model=src.model, error=src.error)
            hits[i] = src.ok
    return [r for r in results if r is not None], hits


# ---- decisions ---------------------------------------------------------------------------

def _choice_conf(res: jev_client.JevResult, q: str) -> float:
    c = res.confidence(q)
    if not c:
        c = res.probabilities(q).get(res.choice(q), 0.0)
    return c


def _fit(out: dict[str, Any], icp: dict[str, Any]) -> int:
    w = {**DEFAULT_FIT_WEIGHTS, **(icp.get("fit_weights") or {})}
    parts = {"role_fit": out["jev_role_fit"], "likely_buyer": out["jev_likely_buyer"],
             "company_fit": out["jev_company_fit"], "seniority": out["jev_seniority"] / 4}
    total = sum(float(w.get(k, 0)) for k in parts)
    if total <= 0:
        return 0
    return round(100 * sum(float(w.get(k, 0)) * v for k, v in parts.items()) / total)


def decide_row(res: jev_client.JevResult, scenario: str, qs: dict[str, dict[str, Any]],
               minc: float, icp: dict[str, Any] | None = None) -> dict[str, Any]:
    """Return jev_* columns for one row."""
    icp = icp or {}
    out: dict[str, Any] = {}
    if not res.ok:
        for q in qs:
            out[f"jev_{q}"] = None
            if qs[q]["type"] == "choice":
                out[f"jev_{q}_conf"] = 0.0
        if scenario == "qualify":
            out["jev_fit"] = None
        out.update({"jev_decision": "error", "jev_confidence": 0.0, "jev_review": True,
                    "jev_error": res.error or "no answers"})
        return out
    missing = [q for q in qs if q not in res.answers]
    confs = []
    for q, spec in qs.items():
        t = spec["type"]
        if t == "choice":
            c = _choice_conf(res, q)
            confs.append(c)
            out[f"jev_{q}"] = res.choice(q)
            out[f"jev_{q}_conf"] = round(c, 4)
        elif t == "noul":
            out[f"jev_{q}"] = round(res.noul(q), 4)
        else:
            out[f"jev_{q}"] = round(res.score(q), 4)
    conf = min(confs) if confs else 1.0
    g = lambda q: out[f"jev_{q}"]  # noqa: E731
    miss = conf < minc
    if scenario == "qualify":
        fit = _fit(out, icp)
        out["jev_fit"] = fit
        cut = {**DEFAULT_FIT_CUTOFFS, **(icp.get("fit_cutoffs") or {})}
        if g("reach_out") >= minc and g("icp_fit") >= 2 and g("persona") != "none" \
                and out["jev_persona_conf"] >= minc and fit >= cut["go"]:
            d = "go"
        elif (g("reach_out") < 0.3 or g("icp_fit") < 1) and fit < cut["hold"]:
            d = "skip"
        else:
            d = "hold"
    elif scenario == "signals":
        nouls = [g(q) for q in ("funding_recent", "hiring_outbound", "new_budget_owner", "current_role_buys")]
        s = g("signal_strength")
        if s >= 2 and any(v >= minc for v in nouls):
            d = "contact"
        elif 1 <= s < 2:
            d = "watch"
        else:
            d = "none"
    elif scenario == "hygiene":
        flags = [g(q) for q in ("first_name_clean", "company_name_clean", "title_is_person_title",
                                "email_looks_work")]
        if g("row_usable") < 0.5:
            d = "drop"
        elif any(v < minc for v in flags):
            d = "fix"
        else:
            d = "clean"
    elif scenario == "suppress":
        rel_hit = g("relation") in {"customer", "competitor", "bad_actor"} and out["jev_relation_conf"] >= minc
        d = "suppress" if g("do_not_contact") >= minc or rel_hit else "allow"
    elif scenario == "replies":
        if g("remove_request") >= minc:
            d = "unsubscribe"
        else:
            d = "review" if out["jev_intent_conf"] < minc else g("intent")
    elif scenario == "inbound":
        d = "review" if out["jev_route_conf"] < minc else g("route")
    elif scenario == "diff":
        buys = g("new_budget_owner") >= minc or g("current_role_buys") >= minc
        d = "contact" if buys and g("change_type") not in {"same_job_reworded", "none"} else "ignore"
    elif scenario == "factcheck":
        if g("supported") == "contradicted" or g("sounds_creepy") >= minc:
            d = "block"
        elif g("supported") == "supported" and out["jev_supported_conf"] >= minc and g("sounds_creepy") < 0.5:
            d = "send"
        else:
            d = "fix"
    else:  # message_score
        good = (g("about_them") >= 2 and g("pitches_first_line") < 0.5 and g("reads_as_template") < 0.5
                and g("clear_ask") >= minc)
        d = "send" if good else "revise"
    err = f"partial_answer:{','.join(missing)}" if missing else ""
    out.update({"jev_decision": d, "jev_confidence": round(conf, 4),
                "jev_review": bool(miss or missing or d in ("review", "hold")), "jev_error": err})
    return out


def apply_results(rows: list[dict[str, Any]], results: list[jev_client.JevResult], scenario: str,
                  minc: float, icp: dict[str, Any] | None = None,
                  cached: list[bool] | None = None) -> list[dict[str, Any]]:
    qs = build_questions(scenario, icp or {})
    out = []
    for i, (row, res) in enumerate(zip(rows, results)):
        base = {k: v for k, v in row.items() if k not in ("_old",)}
        if row.get("_old"):
            base["_old_fingerprint"] = fingerprint(row["_old"])
        base.setdefault("id", row_id(row, i))
        base.update(decide_row(res, scenario, qs, minc, icp))
        hit = bool(cached and cached[i])
        base["jev_cached"] = hit
        base["jev_cost_usd"] = 0.0 if hit else res.cost_usd
        out.append(base)
    return out


def fake_results(n: int, qs: dict[str, dict[str, Any]]) -> list[jev_client.JevResult]:
    """Deterministic offline answers for --dry-run (first non-none option, high noul, top score)."""
    answers: dict[str, Any] = {}
    for q, spec in qs.items():
        if spec["type"] == "choice":
            opt = next((k for k in spec["criteria"] if k != "none"), "none")
            answers[q] = {"choice": opt, "confidence": 0.9, "probabilities": {opt: 0.9}}
        elif spec["type"] == "noul":
            answers[q] = {"noul": 0.8}
        else:
            answers[q] = {"score": float(len(spec["criteria"]) - 1)}
    return [jev_client.JevResult(answers=dict(answers), model="dry-run") for _ in range(n)]


# ---- validation / io ---------------------------------------------------------------------

def validate(rows: list[dict[str, Any]], labels_path: Path, question: str = "decision") -> dict[str, Any]:
    with open(labels_path, encoding="utf-8-sig", newline="") as fh:
        labels = {str(r["id"]).strip(): str(r["label"]).strip() for r in csv.DictReader(fh) if r.get("id")}
    col = f"jev_{question}"
    scored = correct = 0
    mismatches = []
    for i, r in enumerate(rows):
        truth = labels.get(str(r.get("id")))
        if truth is None:
            truth = labels.get(str(i))
        if truth is None:
            continue
        scored += 1
        got = str(r.get(col) if r.get(col) is not None else "")
        if got == truth:
            correct += 1
        else:
            mismatches.append({"id": r.get("id"), "expected": truth, "got": got,
                               "confidence": r.get("jev_confidence")})
    if not scored:
        print(f"warning: validate scored 0 rows ({len(labels)} labels, none matched an id or row index)",
              file=sys.stderr)
    return {"question": question, "scored": scored, "correct": correct,
            "accuracy": round(correct / scored, 4) if scored else 0.0, "mismatches": mismatches}


def write_csv(rows: list[dict[str, Any]], path: Path) -> None:
    cols: list[str] = []
    for r in rows:
        for k in r:
            if k not in cols and not k.startswith("_"):
                cols.append(k)
    cols = [c for c in cols if not c.startswith("jev_")] + [c for c in cols if c.startswith("jev_")]
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def write_md(rows: list[dict[str, Any]], path: Path, scenario: str) -> None:
    has_fit = any(r.get("jev_fit") is not None for r in rows)
    if has_fit:
        rows = sorted(rows, key=lambda r: r.get("jev_fit") if r.get("jev_fit") is not None else -1, reverse=True)
    fit_h, fit_s = (" fit |", "---|") if has_fit else ("", "")
    lines = [f"# jev_leads: {scenario}", "",
             f"| id | name | company | decision |{fit_h} confidence | review |",
             f"|---|---|---|---|{fit_s}---|---|"]
    for r in rows[:25]:
        fit = f" {r.get('jev_fit')} |" if has_fit else ""
        lines.append(f"| {r.get('id', '')} | {r.get('name', '')} | {r.get('company', '')} | "
                     f"{r.get('jev_decision')} |{fit} {r.get('jev_confidence')} | {r.get('jev_review')} |")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---- CLI ---------------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("scenario", choices=SCENARIOS)
    ap.add_argument("--input", required=True)
    ap.add_argument("--icp")
    ap.add_argument("--output")
    ap.add_argument("--csv-out")
    ap.add_argument("--md")
    ap.add_argument("--min-confidence", type=float, default=DEFAULT_MIN_CONFIDENCE)
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--validate", help="CSV id,label")
    ap.add_argument("--validate-question", default="decision")
    ap.add_argument("--snapshot", help="previous export (diff only)")
    ap.add_argument("--only-pass", action="store_true", help="csv-out keeps decision in go/contact/sales/send")
    ap.add_argument("--fields", help="comma list of lead columns sent to Jev (denylist always dropped)")
    ap.add_argument("--cache", default=str(DEFAULT_CACHE), help='answer cache JSON; "none" disables')
    args = ap.parse_args(argv)
    s = args.scenario
    fields = tuple(f.strip() for f in args.fields.split(",") if f.strip()) if args.fields else None
    cache_path = None if args.cache.lower() in ("", "none", "off") else Path(args.cache)

    try:
        rows = load_rows(Path(args.input))
        icp = load_icp(Path(args.icp) if args.icp else None)
        if s == "diff":
            if not args.snapshot:
                raise ValueError("diff needs --snapshot")
            rows = diff_rows(rows, load_rows(Path(args.snapshot)))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    if args.limit > 0:
        rows = rows[: args.limit]
    for i, r in enumerate(rows):
        r.setdefault("id", row_id(r, i))

    if not args.dry_run and not jev_client.available():
        print("error: no OpenRouter key (set OPENROUTER_API_KEY)", file=sys.stderr)
        return 2

    qs = build_questions(s, icp)
    states = [row_state(r, s, icp, fields) for r in rows]
    t0 = time.perf_counter()
    cached: list[bool] = [False] * len(rows)
    if args.dry_run:
        print(json.dumps({"scenario": s, "rows": len(rows), "first_state": states[0] if states else None,
                          "questions": qs}, indent=2, ensure_ascii=False, default=str))
        results = fake_results(len(rows), qs)
    else:
        cache = load_cache(cache_path) if cache_path else None
        results, cached = run_with_cache(states, qs, s, cache, args.workers) if states else ([], [])
        if cache is not None:
            save_cache(cache_path, cache)
    wall = round(time.perf_counter() - t0, 2)
    out_rows = apply_results(rows, results, s, args.min_confidence, icp, cached)

    errors = sum(1 for r in out_rows if r["jev_decision"] == "error")
    partial = sum(1 for r in out_rows if str(r["jev_error"]).startswith("partial_answer"))
    cost = round(sum(float(r.get("jev_cost_usd") or 0) for r in out_rows), 6)
    model = next((res.model for res in results if res.model), "")
    summary = {"scenario": s, "rows": len(out_rows),
               "decisions": dict(Counter(r["jev_decision"] for r in out_rows)),
               "cost_usd": cost, "wall_s": wall, "errors": errors, "partial": partial, "model": model,
               "review": sum(1 for r in out_rows if r["jev_review"]),
               "cache_hits": sum(1 for c in cached if c), "dry_run": args.dry_run}
    validation = None
    if args.validate:
        try:
            validation = validate(out_rows, Path(args.validate), args.validate_question)
        except (OSError, KeyError) as exc:
            print(f"error: validate: {exc}", file=sys.stderr)
            return 1

    out_path = Path(args.output) if args.output else WORKSPACE / ".tmp" / f"jev_leads_{s}.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps({"summary": summary, "rows": out_rows, "validation": validation},
                                   indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    if args.csv_out:
        keep = [r for r in out_rows if r["jev_decision"] in PASS_DECISIONS] if args.only_pass else out_rows
        write_csv(keep, Path(args.csv_out))
    if args.md:
        write_md(out_rows, Path(args.md), s)

    print(f"{s}: {len(out_rows)} rows in {wall} s for ${cost:.5f} ({errors} errors, {partial} partial, "
          f"{summary['review']} review, {summary['cache_hits']} cache hits)")
    print("  decisions: " + ", ".join(f"{k}={v}" for k, v in sorted(summary["decisions"].items())))
    if validation:
        print(f"  validation ({validation['question']}): {validation['correct']}/{validation['scored']} "
              f"= {validation['accuracy']:.1%}")
        for m in validation["mismatches"]:
            print(f"    id={m['id']} expected={m['expected']} got={m['got']}")
    print(f"  wrote {out_path}")
    if not args.dry_run:
        jev_client.append_ledger({"caller": "jev_leads", "scenario": s, "items": len(out_rows),
                                  "cost_usd": cost, "wall_s": wall, "errors": errors,
                                  "cache_hits": summary["cache_hits"]},
                                 path=WORKSPACE / ".tmp" / "jev_ledger.jsonl")
    return 0


if __name__ == "__main__":
    sys.exit(main())
