"""
description: Deterministic (no-API-key) ranker for job_digest, driven entirely by
    Profile — no personal data or per-candidate literals in code. This is the
    rung that ALWAYS runs (rung 1 of ranker/rank.py); Gemini and Anthropic are
    optional refinements on top of it.
inputs: list[NormalizedJob] (post-filter), profile_schema.Profile
outputs: list[RankedJob], 1:1 with the input jobs, ranker_model="heuristic-v1"

Ported from the operator's internal job pipeline's ranker heuristic
(_profile_aware_heuristic), generalized to read role titles/synonyms, screening
skills/must_have/nice_to_have, contracts, and location from Profile + registry
instead of a hand-authored operator config file.
"""

from __future__ import annotations

import logging
import unicodedata

from .. import registry
from ..contracts import ContractType, JobTier, NormalizedJob, RankedJob, RemoteMode
from ..profile_schema import Profile, Role

logger = logging.getLogger("job_digest.ranker.heuristic")

RUBRIC_VERSION = "heuristic-v1"
RANKER_MODEL = "heuristic-v1"

DIMENSION_WEIGHTS = {
    "title_fit": 0.30,
    "skill_overlap": 0.30,
    "contract_fit": 0.15,
    "seniority_fit": 0.10,
    "location_fit": 0.15,
}
_HARD_ZERO_DIMS = ("title_fit", "contract_fit", "location_fit")

TIER_THRESHOLDS = (("A", 0.75), ("B", 0.50), ("C", 0.25))

_CONTRACT_LABELS: dict[ContractType, str] = {
    ContractType.CDI: "permanent",
    ContractType.CDD: "fixed_term",
    ContractType.FREELANCE: "freelance",
}

_SENIOR_TOKENS = (
    "senior", "lead", "principal", "head ", "head of", "director",
    "staff", "vp ", "vp of", "chief", "fractional",
)
_JUNIOR_TOKENS = (
    "junior", "intern", "stagiaire", "alternance", "trainee",
    "graduate", "apprenti",
)


def _fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def combine(dims: dict[str, float]) -> float:
    """Weighted arithmetic mean of the five dimensions, with the hard-zero rule:
    if title_fit, contract_fit, or location_fit is exactly 0, the final score is
    0 regardless of the others (a strong skill match cannot rescue the wrong
    role, wrong contract, or wrong country).
    """
    if any(float(dims.get(d, 0.0)) == 0.0 for d in _HARD_ZERO_DIMS):
        return 0.0
    total = 0.0
    for key, weight in DIMENSION_WEIGHTS.items():
        total += weight * max(0.0, min(1.0, float(dims.get(key, 0.0))))
    return round(total, 4)


def tier_for(score: float) -> JobTier:
    for tier_name, threshold in TIER_THRESHOLDS:
        if score >= threshold:
            return JobTier(tier_name)
    return JobTier.SKIP


def _title_score(title_folded: str, titles: list[str]) -> float:
    best = 0.0
    for t in titles:
        tl = _fold(t)
        if not tl:
            continue
        if tl in title_folded:
            return 1.0
        tokens = [w for w in tl.split() if len(w) > 2]
        if tokens and all(w in title_folded for w in tokens):
            best = max(best, 0.9)
            continue
        title_words = {w for w in title_folded.split() if len(w) > 2}
        overlap = len({w for w in tokens} & title_words)
        if overlap >= 2:
            best = max(best, 0.7)
        elif overlap == 1:
            best = max(best, 0.4)
    return best


def _best_matching_role(title_folded: str, roles: list[Role]) -> tuple[Role | None, float]:
    best_role: Role | None = None
    best_score = 0.0
    for role in roles:
        score = _title_score(title_folded, role.all_titles)
        if score > best_score:
            best_score = score
            best_role = role
    return best_role, best_score


def _skill_overlap(haystack: str, profile: Profile) -> tuple[float, list[str]]:
    matched: list[str] = []
    weight = 0.0
    for name in profile.screening.skills:
        folded = _fold(name)
        if folded and folded in haystack:
            matched.append(name)
            weight += 1.0
    for name in profile.screening.nice_to_have:
        folded = _fold(name)
        if folded and folded in haystack:
            matched.append(name)
            weight += 0.5
    return min(1.0, weight / 8.0), matched[:12]


def _must_have_present(haystack: str, profile: Profile) -> bool:
    must_have = profile.screening.must_have
    if not must_have:
        return True
    return any(_fold(m) in haystack for m in must_have if m)


def _contract_fit(job: NormalizedJob, profile: Profile) -> float:
    ct = job.contract_type
    if ct == ContractType.INTERNSHIP:
        return 0.0
    if ct == ContractType.UNKNOWN:
        return 0.6
    label = _CONTRACT_LABELS.get(ct)
    if label is None:
        return 0.6
    return 1.0 if label in profile.contracts else 0.2


def _seniority_fit(haystack: str, role: Role | None) -> float:
    target = role.seniority if role else "any"
    if target == "any":
        return 1.0
    if any(t in haystack for t in _JUNIOR_TOKENS):
        return 1.0 if target == "junior" else 0.0
    if any(t in haystack for t in _SENIOR_TOKENS):
        return 1.0 if target in ("senior", "lead") else 0.6
    return 0.6


def _location_fit(job: NormalizedJob, profile: Profile) -> float:
    """Score location fit. City match beats country-only match beats remote:
    - 1.0: matches one of the profile's cities (registry.city_matches).
    - 0.8: matches a selected country that has no city constrained to it.
    - 0.7: matches a selected country, but the profile's own city(ies) for
      that country did not match (e.g. wants Paris specifically, got Lyon).
    - 1.0: remote and remote_ok, when no country/city matched.
    - 0.0: none of the above.
    """
    loc = (job.location or "").strip()
    if not loc or loc.lower() == "unknown":
        return 0.6

    haystack = f"{loc} {job.description_snippet[:300]}"
    is_remote = job.remote_mode == RemoteMode.REMOTE
    remote_ok = profile.locations.remote_ok
    cities = profile.locations.cities

    if cities:
        for city in cities:
            if registry.city_matches(city, haystack):
                return 1.0

    matched_country = next((c for c in profile.countries if c.matches(loc, job.description_snippet[:300])), None)
    if matched_country is not None:
        country_cities = [
            city for city in cities
            if (owner := registry.country_for_city(city)) is not None and owner.iso2 == matched_country.iso2
        ]
        return 0.7 if country_cities else 0.8

    if remote_ok and is_remote:
        return 1.0
    return 0.0


def score_one(job: NormalizedJob, profile: Profile) -> tuple[RankedJob, bool]:
    """Score one job. Returns (RankedJob, must_have_missing) — the flag is
    surfaced separately so score_heuristic can batch-warn without re-parsing
    the reasoning string.
    """
    title_folded = _fold(job.title)
    desc_folded = _fold(job.description_snippet)
    haystack = f"{title_folded} {desc_folded}"

    role, title_fit = _best_matching_role(title_folded, profile.roles)

    skill_overlap, matched = _skill_overlap(haystack, profile)
    must_have_missing = not _must_have_present(haystack, profile)
    if must_have_missing:
        # A (often truncated) snippet lacking the must-have keyword is weak
        # evidence, not proof — the full posting may still mention it. Penalize
        # skill_overlap instead of hard-zeroing title_fit (that used to
        # silently SKIP every job whose snippet happened to be truncated
        # before the must-have keyword).
        skill_overlap *= 0.5

    contract_fit = _contract_fit(job, profile)
    seniority_fit = _seniority_fit(haystack, role)
    location_fit = _location_fit(job, profile)

    dims = {
        "title_fit": title_fit,
        "skill_overlap": skill_overlap,
        "contract_fit": contract_fit,
        "seniority_fit": seniority_fit,
        "location_fit": location_fit,
    }
    final_score = combine(dims)
    tier = tier_for(final_score)

    dim_str = " ".join(f"{k.split('_')[0]}={v:.2f}" for k, v in dims.items())
    matched_str = ", ".join(matched[:8]) if matched else "none"
    reasoning = f"{dim_str} | matched: {matched_str}"
    if must_have_missing:
        reasoning += " | must_have_missing"
    reasoning += " | heuristic-only pass"

    return RankedJob(
        content_hash=job.content_hash,
        score=final_score,
        tier=tier,
        reasoning=reasoning[:800],
        rubric_version=RUBRIC_VERSION,
        ranker_model=RANKER_MODEL,
    ), must_have_missing


_MUST_HAVE_WARN_RATIO = 0.80


def score_heuristic(jobs: list[NormalizedJob], profile: Profile) -> list[RankedJob]:
    """Score every job with the deterministic heuristic. Always succeeds — no
    network calls, no API keys, so this is the guaranteed rung of ranker/rank.py.
    """
    scored = [score_one(job, profile) for job in jobs]
    ranked = [rj for rj, _ in scored]
    missing_count = sum(1 for _, missing in scored if missing)

    by_tier: dict[str, int] = {}
    for rj in ranked:
        by_tier[rj.tier.value] = by_tier.get(rj.tier.value, 0) + 1
    logger.info("score_heuristic: %d jobs -> %s", len(ranked), by_tier)

    if jobs and (missing_count / len(jobs)) > _MUST_HAVE_WARN_RATIO:
        logger.warning(
            "score_heuristic: must_have penalized %d/%d (%.0f%%) jobs in this batch — "
            "check profile.screening.must_have against actual snippet lengths",
            missing_count, len(jobs), 100.0 * missing_count / len(jobs),
        )
    return ranked
