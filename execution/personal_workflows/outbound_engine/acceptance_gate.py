"""Output-acceptance gate for drafted outbound rows (SPEC G1/G4/G5/G7).

Hard-fail, corpus-backed, asserts on the OUTPUT a recipient would read. Per
~/.claude/rules/output-acceptance-gate.md: this is the last Stage-1 step and the
run exits non-zero on ANY junk row. Reasons are explicit codes so the frozen
corpus can assert the exact violation.

Reason codes: deliverability, icp_fit, geo_exclude, hook_specificity,
max_body_words, max_links, spam_words, unsubscribe, language.

No network, no LLM (langdetect optional). Deterministic and independent of the
sourcing/personalisation logic so it does not share their blind spots.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field

# True spam-trigger tokens (distinct from the voice never_say list).
SPAM_WORDS = [
    "act now", "100% guaranteed", "guaranteed", "free!!", "click here",
    "limited time", "risk-free", "earn $", "$$$", "buy now", "order now",
    "congratulations", "you have been selected", "winner",
]

# Generic openers that prove the email was NOT personalised.
GENERIC_PHRASES = [
    "i noticed you're in", "i noticed you are in", "thought i'd reach out",
    "thought i would reach out", "we help companies", "hope this email finds you",
    "quick question", "i wanted to reach out", "to whom it may concern",
]

_STOP = {"with", "your", "that", "this", "from", "have", "they", "them",
         "into", "onto", "some", "keeps", "need", "needs", "uses", "role"}

_LINK_RE = re.compile(r"https?://", re.IGNORECASE)
_WORD_RE = re.compile(r"[a-z0-9\-]+")


@dataclass
class GateResult:
    ok: bool
    reasons: list = field(default_factory=list)
    lead_id: str = ""


def _significant(text: str) -> set:
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 3 and w not in _STOP}


def _detect_lang(body: str):
    """Return ISO lang or None if undetectable / langdetect unavailable."""
    words = body.split()
    if len(words) < 8:
        return None  # too short to trust (output-acceptance-gate Exhibit-B lesson)
    try:
        from langdetect import detect  # type: ignore
        return detect(body)
    except Exception:
        return None


def check_row(row: dict, config: dict) -> GateResult:
    reasons: list = []
    prospect = row.get("prospect", {})
    body = str(row.get("email_body", ""))
    body_l = body.lower()
    icp = config.get("icp", {})

    # --- G2/G3 deliverability: only 'valid' emails may ship ---
    if str(row.get("verification", "unknown")).lower() != "valid":
        reasons.append("deliverability")

    # --- G7 geo exclusion (Canada) - checked before icp geo so reason is clean ---
    geo = str(prospect.get("geo", "")).upper()
    excluded_geos = [g.upper() for g in config.get("geo_exclude", [])]
    haystack = " ".join(str(prospect.get(k, "")) for k in ("domain", "email", "company", "geo")).lower()
    exclude_terms = [t.lower() for t in config.get("geo_exclude_terms", [])]
    geo_excluded = geo in excluded_geos or any(term in haystack for term in exclude_terms)
    if geo_excluded:
        reasons.append("geo_exclude")

    # --- G1 ICP fit (title + size + industry; geo handled above) ---
    title = str(prospect.get("title", "")).lower()
    targets = [t.lower() for t in icp.get("titles_target", [])]
    title_ok = any(t == title or t in title for t in targets)
    lo, hi = (icp.get("employee_range") or [0, 10**9])
    emp = prospect.get("employees")
    size_ok = isinstance(emp, (int, float)) and lo <= emp <= hi
    industry = str(prospect.get("industry", "")).lower()
    inds = [i.lower() for i in icp.get("industries_include", [])]
    industry_ok = any(i in industry or industry in i for i in inds) if industry else False
    geo_include_ok = geo_excluded or geo in [g.upper() for g in icp.get("geos_include", [])]
    if not (title_ok and size_ok and industry_ok and geo_include_ok):
        # Only attribute to icp_fit when the failure isn't purely the geo exclusion.
        if not (geo_excluded and title_ok and size_ok and industry_ok):
            reasons.append("icp_fit")

    # --- G4 hook specificity: references the real signal, not generic ---
    detail = str(row.get("signal", {}).get("detail", ""))
    sig_words = _significant(detail)
    overlap = sum(1 for w in sig_words if w in body_l)
    is_generic = any(p in body_l for p in GENERIC_PHRASES)
    if is_generic or overlap < 2:
        reasons.append("hook_specificity")

    # --- G4 length ---
    max_words = config.get("max_body_words", 60)
    if len(body.split()) > max_words:
        reasons.append("max_body_words")

    # --- G4 links ---
    max_links = config.get("max_links", 2)
    if len(_LINK_RE.findall(body)) > max_links:
        reasons.append("max_links")

    # --- G4 spam words ---
    if any(w in body_l for w in SPAM_WORDS):
        reasons.append("spam_words")

    # --- G7 unsubscribe mechanism present ---
    token = str(row.get("unsubscribe_token", "")).strip()
    has_unsub_marker = "unsubscribe" in body_l or "{{unsub}}" in body_l
    if not token or not has_unsub_marker:
        reasons.append("unsubscribe")

    # --- G4 language EN/FR (optional; only when detectable) ---
    lang = _detect_lang(body)
    if lang is not None and lang not in ("en", "fr"):
        reasons.append("language")

    return GateResult(ok=len(reasons) == 0, reasons=reasons, lead_id=str(row.get("id", "")))


def run_gate(rows: list, config: dict) -> dict:
    """Evaluate a batch. `ok` is True only if EVERY row passes (hard-fail semantics)."""
    failures = []
    passed = 0
    for row in rows:
        res = check_row(row, config)
        if res.ok:
            passed += 1
        else:
            failures.append({"id": res.lead_id or row.get("id", ""), "reasons": res.reasons})
    total = len(rows)
    return {
        "total": total,
        "passed": passed,
        "failed": len(failures),
        "ok": len(failures) == 0,
        "failures": failures,
    }
