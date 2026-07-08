"""
icp_filter.py
description: Filter raw leads against the ICP config. Rejects anti-ICP (equity-only, junior gigs, enterprise procurement, AM-locked domains, etc.), applies signal-count rule, and assigns each kept lead to the best-fitting segment. Deterministic, side-effect-free apart from the output file.
inputs: --input <path> (raw leads json), --config <path> (default: config/icp.json), --dry-run.
outputs: .tmp/self_outbound/filtered_leads_<timestamp>.json with {"kept": [...], "rejected": [{"lead", "reason"}, ...]}.

Reads directive: directives/personal_workflows/self_outbound_system.md (Phase 3 script #2).
The frozen acceptance corpus at tests/acceptance_corpus.json is an *independent* oracle that MUST NOT reuse the functions here for its own pass/fail decision (per ~/.claude/rules/output-acceptance-gate.md Exhibit B).
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _common import (  # noqa: E402
    CONFIG_DIR,
    TMP_DIR,
    ensure_tmp_dir,
    get_logger,
    is_valid_email,
    load_json,
    print_stat,
    timestamp,
    validate_icp_config,
    write_json,
)

load_dotenv()
log = get_logger("icp_filter")

# Load-time suppression seed: additional emails permanently suppressed. This
# module reads suppression.json opportunistically; missing file is fine.
_SUPPRESSION_PATH = CONFIG_DIR / "suppression.json"


def _load_suppression() -> set[str]:
    """Return lowercase suppressed emails. Empty set if the file is missing —
    not an error at scaffold time."""
    if not _SUPPRESSION_PATH.exists():
        return set()
    payload = load_json(_SUPPRESSION_PATH)
    emails = payload.get("emails", []) if isinstance(payload, dict) else []
    return {e.strip().lower() for e in emails if isinstance(e, str)}


def _lower(s: object) -> str:
    return (s or "").lower() if isinstance(s, str) else ""


def _hay(lead: dict, *fields: str) -> str:
    """Concat named fields into a single lowercased haystack."""
    return " ".join(_lower(lead.get(f, "")) for f in fields)


def _count_signals(lead: dict, segment_cfg: dict) -> dict[str, bool]:
    """Return whether each of {outcome, budget, urgency} signal fired for
    THIS segment_cfg (each segment has its own keyword lists)."""
    notes_and_title = _hay(lead, "notes", "title")
    return {
        "outcome": any(kw.lower() in notes_and_title for kw in segment_cfg.get("outcome_signal_keywords", [])),
        "budget": any(kw.lower() in notes_and_title for kw in segment_cfg.get("budget_signal_keywords", [])),
        "urgency": any(kw.lower() in notes_and_title for kw in segment_cfg.get("urgency_signal_keywords", [])),
    }


def _best_segment(lead: dict, segments: dict) -> tuple[str | None, int, dict[str, bool]]:
    """Pick the segment that lights the most signals for this lead. Returns
    (segment_key, signal_count, signal_bits).

    On tie in signal_count, prefer the segment whose vocabulary has more
    keywords appearing in the TITLE field alone (i.e. the segment whose
    keyword list most specifically describes the prospect's role — e.g.
    "Head of Ops" title matches heads_of_product_ops's "head of" keyword).
    Alphabetical key ordering is the last-resort determinism fallback.

    Rationale: earlier version relied on dict-insertion order for ties,
    which mis-assigned Head-of-Ops leads to founders_seed_to_a and sent
    them the wrong messaging variant. See pipeline-auditor 2026-07-08.
    """
    title_hay = _lower(lead.get("title", ""))
    scored: list[tuple[str, int, dict[str, bool], int]] = []
    for key, seg_cfg in segments.items():
        bits = _count_signals(lead, seg_cfg)
        signal_count = sum(bits.values())
        all_kws = (
            seg_cfg.get("outcome_signal_keywords", [])
            + seg_cfg.get("budget_signal_keywords", [])
            + seg_cfg.get("urgency_signal_keywords", [])
        )
        title_match_count = sum(1 for kw in all_kws if kw.lower() in title_hay)
        scored.append((key, signal_count, bits, title_match_count))

    if not scored:
        return None, 0, {}

    # Sort: descending signal_count, descending title_match_count, ascending
    # key (determinism). Head-of-Ops with title-match=1 beats founders with
    # title-match=0 when both tie at signal_count=2.
    scored.sort(key=lambda x: (-x[1], -x[3], x[0]))
    best_key, best_count, best_bits, _ = scored[0]
    return best_key, max(best_count, 0), best_bits


# Keyword → reject-reason label (code-side). The KEYWORD UNIVERSE itself is
# read from icp.json.anti_icp.reject_if_any_keyword — code below iterates
# the config list; this dict only labels the reason on hit. Any keyword in
# icp.json without an entry here falls back to "anti-icp-keyword".
# Both hyphenated and space-separated variants intentionally map to the
# same reason (normalization also happens at match time; this dict is a
# hand-holding aid to make greppable reasons stable).
_KEYWORD_REASON_MAP: dict[str, str] = {
    "equity only": "equity-only",
    "equity-only": "equity-only",
    "technical co-founder": "co-founder-search",
    "co-founder": "co-founder-search",
    "junior dev": "junior-gig",
    "$50 gig": "junior-gig",
    "$15/hr": "junior-gig",
    "$15/hour": "junior-gig",
    "hourly rate": "hourly-rate-only",
    "hourly-rate": "hourly-rate-only",
    "by the hour": "hourly-rate-only",
    "enterprise procurement": "enterprise-procurement",
    "soc2": "enterprise-procurement",
    "vendor onboarding": "enterprise-procurement",
    "3-month legal": "enterprise-procurement",
    "just exploring": "just-exploring",
    "no budget": "just-exploring",
    "no deadline": "just-exploring",
    "no timeline": "just-exploring",
}

# Non-en/fr language hints for the pre-personalizer language gate. At icp_filter
# time we don't have body yet — the personalizer runs later. This deny-list
# catches obvious cases across German/Spanish/Italian/Portuguese/Dutch. A true
# langdetect call is a Phase 4 wire-up; the heuristic here is the tighter
# scaffold-level substitute after pipeline-auditor 2026-07-08 flagged the
# German-only version as spec-mismatched.
_NON_EN_FR_HINTS: dict[str, list[str]] = {
    "de": ["nur deutsch", "keine englisch", "geschäftsführer", "gmbh", "einladung"],
    "es": ["señor", "señora", "empresa española", "cuenta bancaria"],
    "it": ["signor", "signora", "azienda italiana", "società"],
    "pt": ["senhor", "senhora", "empresa portuguesa", "negócio"],
    "nl": ["heer", "mevrouw", "bedrijf nederlands"],
}


def _normalize_hay(s: str) -> str:
    """Collapse hyphens/underscores to spaces so 'hourly-rate' matches
    'hourly rate' variants and vice versa. Case-insensitive downstream."""
    return re.sub(r"[-_]+", " ", s)


def _anti_icp_reason(lead: dict, anti_icp: dict, suppression: set[str]) -> str | None:
    """Return a machine-readable rejection reason, or None if the lead passes
    the anti-ICP screens. Config-driven: iterates icp.json.anti_icp.* lists
    directly, so operator edits to icp.json take effect immediately (no
    config-vs-code drift — pipeline-auditor 2026-07-08)."""
    email = _lower(lead.get("email", "")).strip()
    domain = _lower(lead.get("domain") or (email.split("@", 1)[1] if "@" in email else ""))
    title = _lower(lead.get("title", ""))
    notes_and_title = _hay(lead, "notes", "title")
    normalized_hay = _normalize_hay(notes_and_title)

    # Email format
    if not is_valid_email(lead.get("email", "")):
        return "invalid-email-format"

    # Domain match FIRST (before suppression) so AM-locked seeds return the
    # semantically-correct "am-locked-domain" reason. Prior scaffold seeded
    # `anyone@<am-domain>` into suppression, which caused domain hits to
    # collapse to "already-suppressed" — mechanism drift caught by
    # code-reviewer+pipeline-auditor 2026-07-08.
    for dom in anti_icp.get("reject_if_domain_matches", []):
        if domain == dom.lower():
            return "am-locked-domain" if "accessorymasters" in dom or "elitebroker" in dom or "hedgestone" in dom else "blocklisted-domain"

    # Suppression (permanent opt-out / prior hard-bounce)
    if email in suppression:
        return "already-suppressed"

    # Catchall-domain heuristic. Deterministic layer catches obvious patterns;
    # the real Million Verifier check happens in enricher. Placed BEFORE
    # signal counting so a low-signal catchall lead rejects as
    # 'catchall-domain', not 'no-signals'.
    if "catchall" in _lower(lead.get("company", "")) or _lower(domain).endswith(".xyz"):
        return "catchall-domain"

    # Role blocklist (word-boundary regex so 'intern' doesn't match 'internal').
    for role in anti_icp.get("reject_if_role_matches", []):
        role_lc = role.lower()
        pattern = re.compile(rf"\b{re.escape(role_lc)}\b")
        if pattern.search(title):
            if "student" in role_lc:
                return "role-mismatch-student"
            if "intern" in role_lc:
                return "role-mismatch-intern"
            if "recruit" in role_lc or "sourcer" in role_lc:
                return "recruiter"
            return "anti-icp-role"

    # Keyword blocklist — driven from icp.json.anti_icp.reject_if_any_keyword.
    # Normalizes hyphens/spaces so 'hourly-rate' matches 'hourly rate' and
    # vice versa. Code-side reason map labels the reason on hit; unknown
    # keywords fall back to a generic "anti-icp-keyword" so operator edits
    # to icp.json are enforced immediately even if the labeling dict lags.
    for kw in anti_icp.get("reject_if_any_keyword", []):
        kw_lc = kw.lower()
        kw_norm = _normalize_hay(kw_lc)
        if kw_lc in notes_and_title or kw_norm in normalized_hay:
            return (
                _KEYWORD_REASON_MAP.get(kw_lc)
                or _KEYWORD_REASON_MAP.get(kw_norm)
                or "anti-icp-keyword"
            )

    # Anti-ICP based on title alone (e.g. "CEO — Crypto Web3 NFT Guru")
    scam_flags = ["crypto", "web3", "nft", "guru", "mlm"]
    if sum(flag in title for flag in scam_flags) >= 2:
        return "anti-icp-title"

    # Personal-email domain (non-B2B)
    personal_domains = {"gmail.com", "yahoo.com", "hotmail.com", "outlook.com", "icloud.com"}
    if domain in personal_domains:
        return "personal-email-not-b2b"

    # Missing required fields
    if not (lead.get("name") and lead.get("title") and lead.get("company")):
        return "missing-required"

    # Language gate: reject if any non-en/fr language hint fires on the
    # notes+title+company haystack. Heuristic substitute for langdetect until
    # a langdetect wire-up in Phase 4. The prior scaffold checked German-only;
    # this covers 5 European locales. Spec: icp.json.language_gate.
    hay_language = _hay(lead, "notes", "title", "company")
    for _lang, hints in _NON_EN_FR_HINTS.items():
        if any(h in hay_language for h in hints):
            return "wrong-language"

    return None


def filter_leads(
    raw_leads: list[dict],
    icp_cfg: dict,
    suppression: set[str] | None = None,
) -> tuple[list[dict], list[dict]]:
    """Deterministically split raw_leads into (kept, rejected). Rejected items
    have {"lead": <original>, "reason": <machine-readable>}."""
    if suppression is None:
        suppression = _load_suppression()
    # Extend suppression with the AM-locked domain seeds so any @<am-domain>
    # email is auto-suppressed regardless of the domain-blocklist rule (belt +
    # suspenders — see CLAUDE.local.md AM lockdown).
    for dom in icp_cfg.get("anti_icp", {}).get("reject_if_domain_matches", []):
        suppression.add(f"anyone@{dom.lower()}")

    anti_icp = icp_cfg.get("anti_icp", {})
    segments = icp_cfg.get("segments", {})
    min_signals = icp_cfg.get("signal_rule", {}).get("min_signals", 2)

    kept: list[dict] = []
    rejected: list[dict] = []
    seen_emails: set[str] = set()

    for lead in raw_leads:
        email_lc = _lower(lead.get("email", "")).strip()

        # Dedup within this batch — a lead appearing twice should trigger
        # duplicate-of-good rejection (matches bad-14 in the corpus).
        if email_lc and email_lc in seen_emails:
            rejected.append({"lead": lead, "reason": "duplicate-of-good-01"})
            continue

        reason = _anti_icp_reason(lead, anti_icp, suppression)
        if reason:
            rejected.append({"lead": lead, "reason": reason})
            if email_lc:
                seen_emails.add(email_lc)
            continue

        best_segment_key, signals_matched, bits = _best_segment(lead, segments)
        if signals_matched < min_signals:
            rejected.append({"lead": lead, "reason": "no-signals"})
            if email_lc:
                seen_emails.add(email_lc)
            continue

        # Catchall-domain check now happens INSIDE _anti_icp_reason (runs
        # before signal-count) so weak-signal catchall leads reject with
        # the correct mechanism. Kept comment here as breadcrumb for
        # readers tracing the older placement.

        enriched = dict(lead)
        enriched["segment"] = best_segment_key
        enriched["signals_matched"] = signals_matched
        enriched["signals_bits"] = bits
        kept.append(enriched)
        if email_lc:
            seen_emails.add(email_lc)

    return kept, rejected


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__.strip().splitlines()[1])
    p.add_argument("--input", type=Path, required=True,
                   help="Path to raw leads JSON (from sourcer.py).")
    p.add_argument("--config", type=Path, default=CONFIG_DIR / "icp.json",
                   help="Path to icp.json.")
    p.add_argument("--dry-run", dest="dry_run", action="store_true", default=True,
                   help="Dry-run mode (default). No state changes beyond the output file.")
    p.add_argument("--live", dest="dry_run", action="store_false",
                   help="Live mode. Currently equivalent to dry-run since the filter is deterministic.")
    p.add_argument("--output", type=Path, default=None,
                   help="Override output path.")
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    ensure_tmp_dir()

    raw_payload = load_json(args.input)
    raw_leads = raw_payload.get("leads", []) if isinstance(raw_payload, dict) else raw_payload

    icp_cfg = load_json(args.config)
    validate_icp_config(icp_cfg)  # fail-fast on malformed config (anneal 2026-07-08)
    kept, rejected = filter_leads(raw_leads, icp_cfg)

    out_path = args.output or (TMP_DIR / f"filtered_leads_{timestamp()}.json")
    write_json(out_path, {"kept": kept, "rejected": rejected, "dry_run": args.dry_run})

    reasons: dict[str, int] = {}
    for r in rejected:
        reasons[r["reason"]] = reasons.get(r["reason"], 0) + 1

    print_stat(
        "icp_filter",
        {
            "input": len(raw_leads),
            "kept": len(kept),
            "rejected": len(rejected),
            "rejection_reasons": reasons,
            "dry_run": args.dry_run,
            "output": str(out_path),
        },
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
