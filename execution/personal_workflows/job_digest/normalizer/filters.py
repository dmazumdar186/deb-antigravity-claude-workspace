"""
description: Profile-driven filters for job_digest, implementing exactly the
    "Filters" section of directives/personal_workflows/job_digest.md: title,
    exclude (title substrings + companies), location+city (via registry aliases),
    contract, language.
inputs: list[NormalizedJob], profile_schema.Profile
outputs: (kept: list[NormalizedJob], stats: dict[str, int]) — stats counts drops
    per reason so run.py / cli.py can report why a job never reached the digest.

No literals from any one country/candidate live here — every rule reads from
Profile and registry.py. Language detection is a lightweight stopword heuristic
(en/fr/de/nl only, no new dependency) rather than langdetect (the operator's
internal job pipeline's choice) because job_digest ships to strangers' machines
and must not require an
extra pip install beyond requirements.txt.
"""

from __future__ import annotations

import logging
import re
import unicodedata

from .. import registry
from ..contracts import ContractType, NormalizedJob, RemoteMode
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.normalizer.filters")

# ContractType enum -> the Profile "contracts" literal that accepts it.
# INTERNSHIP has no entry: it is always dropped, regardless of profile.contracts.
_CONTRACT_LABELS: dict[ContractType, str] = {
    ContractType.CDI: "permanent",
    ContractType.CDD: "fixed_term",
    ContractType.FREELANCE: "freelance",
}


def _fold(s: str) -> str:
    """Lowercase + strip diacritics (café -> cafe) for accent-insensitive matching."""
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    return s.lower()


def _phrase_regex(phrase: str) -> re.Pattern[str]:
    """Word-boundary regex for a (possibly multi-word) phrase, folded text.

    \b only fires between a word char and a non-word char, so a phrase that
    itself starts/ends with a non-word character (C++, C#, .NET) can never
    satisfy a leading/trailing \b against any text — the boundary is dropped
    on whichever end the phrase already supplies a non-word character for.
    """
    folded = _fold(phrase).strip()
    escaped = re.escape(folded)
    # Allow flexible whitespace between words (multiple spaces, tabs) in the target text.
    escaped = escaped.replace(r"\ ", r"\s+")
    leading = r"\b" if folded[:1].isalnum() or folded[:1] == "_" else ""
    trailing = r"\b" if folded[-1:].isalnum() or folded[-1:] == "_" else ""
    return re.compile(rf"{leading}{escaped}{trailing}")


def _title_keeps(title: str, keywords: list[str]) -> bool:
    folded_title = _fold(title)
    for kw in keywords:
        if not kw or not kw.strip():
            continue
        if _phrase_regex(kw).search(folded_title):
            return True
    return False


def _exclude_hits(title: str, company: str, exclude_titles: list[str], exclude_companies: list[str]) -> bool:
    folded_title = _fold(title)
    folded_company = _fold(company)
    for sub in exclude_titles:
        if sub and _fold(sub) in folded_title:
            return True
    for sub in exclude_companies:
        if sub and _fold(sub) in folded_company:
            return True
    return False


def _location_keeps(job: NormalizedJob, profile: Profile) -> bool:
    """See directives/personal_workflows/job_digest.md — Filters — location.

    A city in profile.locations.cities constrains only the country it
    actually belongs to (via registry.country_for_city/CITY_COUNTRY/
    CITY_ALIASES) — with countries [FR, DE] and cities ["Paris"], a German
    job is not required to be in Paris; it only needs to match the DE country
    alias.

    N1: a matched country with no city of its own in the profile's list must
    NOT be constrained just because some OTHER selected country's city
    couldn't be attributed to it — e.g. countries=[FR, DE], cities=
    ["Strasbourg"] must not drop every German job just because "Strasbourg"
    isn't a German city. So: if at least one profile city is attributable to
    some SELECTED country, each selected country is constrained only by the
    cities attributed to it (none attributed -> that country is left
    unconstrained). The old "constrains every country" fallback applies only
    when NO profile city could be attributed to any selected country (we then
    have no better signal than to require a literal match against the whole
    city list, whichever country the job is in).
    """
    loc = (job.location or "").strip()
    if not loc or loc.lower() == "unknown":
        # Unknown/empty location -> keep (filters never reject on missing data;
        # the ranker scores it 0.6 for location_fit instead — see heuristic.py).
        return True

    # Country/city matching reads the LOCATION string only — the description
    # snippet is free text that can name any country in passing ("customers
    # across India") without the job actually being located there. Remote
    # detection already ran on the full location+description text inside
    # normalizer/normalize.py._detect_remote and is captured in
    # job.remote_mode, so the snippet still influences remote_ok jobs, just
    # not through this function.
    is_remote = job.remote_mode == RemoteMode.REMOTE
    remote_ok = profile.locations.remote_ok

    matched_country = next((c for c in profile.countries if c.matches(loc)), None)

    base_keep = matched_country is not None or (remote_ok and is_remote)
    if not base_keep:
        return False

    cities = profile.locations.cities
    if not cities:
        return True

    # cities set: additionally require a city match OR remote.
    if remote_ok and is_remote:
        return True

    # matched_country is guaranteed non-None here: base_keep was true and the
    # remote branch above didn't return, so it must have been the country match.
    selected_isos = {c.iso2 for c in profile.countries}
    attributed: dict[str, list[str]] = {}
    for city in cities:
        owner = registry.country_for_city(city)
        if owner is not None and owner.iso2 in selected_isos:
            attributed.setdefault(owner.iso2, []).append(city)

    if attributed:
        constrained_cities = attributed.get(matched_country.iso2)
        if not constrained_cities:
            # This country has no attributable city of its own, but at least
            # one OTHER selected country does -> leave this country
            # unconstrained rather than requiring a match against a city list
            # that names a different country entirely.
            return True
    else:
        # No profile city could be attributed to any selected country -> no
        # better signal than the old global behaviour: every city constrains
        # every country.
        constrained_cities = cities

    for city in constrained_cities:
        if registry.city_matches(city, loc):
            return True
    return False


def _contract_keeps(job: NormalizedJob, profile: Profile) -> bool:
    ct = job.contract_type
    if ct == ContractType.INTERNSHIP:
        return False
    if ct == ContractType.UNKNOWN:
        return True
    label = _CONTRACT_LABELS.get(ct)
    if label is None:
        return True
    return label in profile.contracts


# ---- lightweight language heuristic (en/fr/de/nl only) ----

_STOPWORDS: dict[str, frozenset[str]] = {
    "en": frozenset({
        "the", "and", "for", "with", "you", "our", "are", "will", "your",
        "have", "this", "that", "team", "role", "work", "experience", "skills",
        "join", "about", "years",
    }),
    "fr": frozenset({
        "le", "la", "les", "des", "une", "vous", "nous", "pour", "avec", "est",
        "sont", "notre", "votre", "poste", "equipe", "experience", "mission",
        "competences", "annees",
    }),
    "de": frozenset({
        "und", "der", "die", "das", "mit", "fur", "sie", "ein", "eine", "wir",
        "unser", "unsere", "team", "erfahrung", "kenntnisse", "jahre",
        "stelle",
    }),
    "nl": frozenset({
        "de", "het", "een", "van", "voor", "met", "wij", "onze", "jij", "je",
        "team", "ervaring", "vaardigheden", "functie", "jaar",
    }),
}

_MIN_SIGNAL_HITS = 2  # below this, treat as undetectable -> keep


def _detect_language(title: str, description_snippet: str) -> str | None:
    """Return the best-guess ISO 639-1 code among en/fr/de/nl, or None if the
    sample carries too few stopword hits to call it (undetectable -> caller keeps).
    """
    sample = f" {_fold(title)} {_fold(description_snippet[:400])} "
    tokens = re.findall(r"[a-z]+", sample)
    if not tokens:
        return None
    token_set_padded = f" {' '.join(tokens)} "

    scores: dict[str, int] = {}
    for lang, words in _STOPWORDS.items():
        hits = sum(1 for w in words if f" {w} " in token_set_padded)
        scores[lang] = hits

    best_lang = max(scores, key=lambda lg: scores[lg])
    if scores[best_lang] < _MIN_SIGNAL_HITS:
        return None
    return best_lang


def _language_keeps(job: NormalizedJob, profile: Profile) -> bool:
    lang = _detect_language(job.title, job.description_snippet)
    if lang is None:
        return True  # undetectable -> keep
    languages = profile.languages
    if not languages:
        # H3: an empty/unset languages list means "no language filter", not
        # "reject every detectable language" — profile_schema._fill_defaults
        # normally derives this from countries, but stay defensive here too.
        return True
    return lang in languages


def apply_filters(jobs: list[NormalizedJob], profile: Profile) -> tuple[list[NormalizedJob], dict[str, int]]:
    """Apply title, exclude, location+city, contract, and language filters in order.

    Returns (kept, stats) where stats counts drops per reason plus 'requested'/'kept'.
    A job is evaluated against every gate in order and dropped at the first gate
    it fails (so stats reflect the actual reason, not double-counted).
    """
    stats: dict[str, int] = {
        "requested": len(jobs),
        "dropped_title": 0,
        "dropped_exclude": 0,
        "dropped_location": 0,
        "dropped_contract": 0,
        "dropped_language": 0,
        "kept": 0,
    }
    keywords = profile.keywords
    exclude_titles = profile.exclude.title_substrings
    exclude_companies = profile.exclude.companies

    kept: list[NormalizedJob] = []
    for job in jobs:
        if not _title_keeps(job.title, keywords):
            stats["dropped_title"] += 1
            continue
        if _exclude_hits(job.title, job.company, exclude_titles, exclude_companies):
            stats["dropped_exclude"] += 1
            continue
        if not _location_keeps(job, profile):
            stats["dropped_location"] += 1
            continue
        if not _contract_keeps(job, profile):
            stats["dropped_contract"] += 1
            continue
        if not _language_keeps(job, profile):
            stats["dropped_language"] += 1
            continue
        kept.append(job)

    stats["kept"] = len(kept)
    logger.info("apply_filters: %s", stats)
    return kept, stats
