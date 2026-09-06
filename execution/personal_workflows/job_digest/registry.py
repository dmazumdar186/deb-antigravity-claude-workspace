"""
description: Static country registry for job_digest — the only place per-country facts live.
inputs: none (pure data); imported by profile_schema, sources, filters, templates
outputs: COUNTRIES dict keyed by ISO2, plus helper lookups.

Add a country = add one entry here. Every field must be filled; the profile
validator rejects any country code not present. `linkedin_geo_id` values marked
verified=False have not yet been confirmed against a live guest-API response
(see directives/personal_workflows/job_digest.md, edge cases).
"""
from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field


def _fold(s: str) -> str:
    """Lowercase + strip diacritics so 'Île-de-France' matches 'ile-de-france'."""
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(ch for ch in s if not unicodedata.combining(ch)).lower()


_US_STATE_RE = re.compile(
    r",\s*(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|DC)"
    r"(?:\s*,\s*(?:United States|USA|US))?\s*(?:\(|$)"
)


@dataclass(frozen=True)
class Country:
    iso2: str
    name: str
    linkedin_geo_id: str
    languages: tuple[str, ...]          # ISO 639-1, first = primary
    timezone: str                       # IANA, default digest tz for this country
    sources: tuple[str, ...]            # source names enabled when this country is selected
    aliases: tuple[str, ...] = field(default_factory=tuple)  # strings that identify this country in location text
    verified: bool = False              # linkedin_geo_id confirmed live
    location_regex: re.Pattern[str] | None = None  # extra structural match on the raw location string

    def matches(self, location: str, extra_text: str = "") -> bool:
        """True if `location` (or `extra_text`) names this country.

        Aliases match on word boundaries after accent folding, so 'uk' never
        matches inside 'Lukas' and 'Île-de-France' matches 'ile-de-france'.
        `location_regex`, when set, is applied to the raw location only.
        """
        hay = _fold(f"{location} {extra_text}")
        for alias in self.aliases:
            a = re.escape(_fold(alias))
            if re.search(rf"(?<![a-z0-9]){a}(?![a-z0-9])", hay):
                return True
        if self.location_regex is not None and self.location_regex.search(location or ""):
            return True
        return False


_GLOBAL_REMOTE = ("remoteok", "weworkremotely")

COUNTRIES: dict[str, Country] = {
    "FR": Country("FR", "France", "105015875", ("fr", "en"), "Europe/Paris",
                  ("linkedin_guest_api", "france_travail", "wttj_algolia", "hellowork") + _GLOBAL_REMOTE,
                  ("france", "paris", "île-de-france", "ile-de-france", "lyon", "marseille", "toulouse", "bordeaux", "nantes", "lille"), verified=True),
    "DE": Country("DE", "Germany", "101282230", ("de", "en"), "Europe/Berlin",
                  ("linkedin_guest_api", "wttj_algolia") + _GLOBAL_REMOTE,
                  ("germany", "deutschland", "berlin", "munich", "münchen", "hamburg", "frankfurt", "köln", "cologne", "stuttgart", "düsseldorf"), verified=True),
    "AT": Country("AT", "Austria", "103883259", ("de", "en"), "Europe/Vienna",
                  ("linkedin_guest_api", "wttj_algolia") + _GLOBAL_REMOTE,
                  ("austria", "österreich", "vienna", "wien", "graz", "linz", "salzburg"), verified=True),
    "BE": Country("BE", "Belgium", "100565514", ("fr", "nl", "en"), "Europe/Brussels",
                  ("linkedin_guest_api", "wttj_algolia") + _GLOBAL_REMOTE,
                  ("belgium", "belgique", "belgië", "brussels", "bruxelles", "antwerp", "ghent", "gent"), verified=True),
    "NL": Country("NL", "Netherlands", "102890719", ("nl", "en"), "Europe/Amsterdam",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("netherlands", "nederland", "amsterdam", "rotterdam", "utrecht", "eindhoven", "the hague", "den haag"), verified=True),
    "GB": Country("GB", "United Kingdom", "101165590", ("en",), "Europe/London",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("united kingdom", "uk", "england", "scotland", "wales", "london", "manchester", "edinburgh", "birmingham"), verified=True),
    "CH": Country("CH", "Switzerland", "106693272", ("de", "fr", "en"), "Europe/Zurich",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("switzerland", "schweiz", "suisse", "zurich", "zürich", "geneva", "genève", "basel", "lausanne", "bern"), verified=True),
    "IN": Country("IN", "India", "102713980", ("en",), "Asia/Kolkata",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("india", "bengaluru", "bangalore", "mumbai", "delhi", "gurugram", "gurgaon", "noida", "hyderabad", "chennai", "pune", "kolkata"), verified=True),
    "SG": Country("SG", "Singapore", "102454443", ("en",), "Asia/Singapore",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("singapore",), verified=True),
    "CA": Country("CA", "Canada", "101174742", ("en", "fr"), "America/Toronto",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("canada", "toronto", "montreal", "montréal", "vancouver", "ottawa", "calgary", "quebec", "québec"), verified=True),
    "US": Country("US", "United States", "103644278", ("en",), "America/New_York",
                  ("linkedin_guest_api",) + _GLOBAL_REMOTE,
                  ("united states", "usa", "u.s.", "u.s.a.", "new york", "san francisco", "seattle", "austin", "boston", "chicago", "los angeles",
                   "california", "texas", "florida", "washington", "illinois", "massachusetts", "colorado", "georgia", "virginia", "north carolina", "new jersey", "pennsylvania", "arizona", "ohio", "michigan", "minnesota", "oregon", "utah"),
                  location_regex=_US_STATE_RE),
}

# City aliases: local-language / anglicized name variants for cities that
# commonly appear under either spelling in job postings (H4). Keys and tuple
# values are folded (lowercase, diacritics stripped) — expand_city() does the
# folding for callers, so entries here must already be fold-normalized.
CITY_ALIASES: dict[str, tuple[str, ...]] = {
    "munich": ("munich", "munchen"),
    "munchen": ("munich", "munchen"),
    "cologne": ("cologne", "koln"),
    "koln": ("cologne", "koln"),
    "vienna": ("vienna", "wien"),
    "wien": ("vienna", "wien"),
    "brussels": ("brussels", "bruxelles", "brussel"),
    "bruxelles": ("brussels", "bruxelles", "brussel"),
    "brussel": ("brussels", "bruxelles", "brussel"),
    "geneva": ("geneva", "geneve", "genf"),
    "geneve": ("geneva", "geneve", "genf"),
    "genf": ("geneva", "geneve", "genf"),
    "zurich": ("zurich",),
    "lyon": ("lyon",),
    "milan": ("milan", "milano"),
    "milano": ("milan", "milano"),
    "bengaluru": ("bengaluru", "bangalore"),
    "bangalore": ("bengaluru", "bangalore"),
    "mumbai": ("mumbai", "bombay"),
    "bombay": ("mumbai", "bombay"),
    "delhi": ("delhi", "new delhi"),
    "new delhi": ("delhi", "new delhi"),
    "gurugram": ("gurugram", "gurgaon"),
    "gurgaon": ("gurugram", "gurgaon"),
    "montreal": ("montreal",),
    "quebec": ("quebec",),
    "the hague": ("the hague", "den haag"),
    "den haag": ("the hague", "den haag"),
    "frankfurt": ("frankfurt", "frankfurt am main"),
    "frankfurt am main": ("frankfurt", "frankfurt am main"),
    "lisbon": ("lisbon", "lisboa"),
    "lisboa": ("lisbon", "lisboa"),
}


def expand_city(city: str) -> tuple[str, ...]:
    """Return the folded alias set for `city`, always including the folded
    input itself even when it has no registered aliases.
    """
    folded = _fold(city).strip()
    aliases = CITY_ALIASES.get(folded)
    if aliases:
        return tuple(dict.fromkeys((folded, *aliases)))
    return (folded,) if folded else ()


def city_matches(city: str, text: str) -> bool:
    """True if any alias of `city` appears in `text` on word boundaries
    (accent-folded). Shared by filters._location_keeps and ranker/heuristic.py
    so both use identical city-matching logic.
    """
    hay = _fold(text or "")
    for alias in expand_city(city):
        a = re.escape(alias)
        if re.search(rf"(?<![a-z0-9]){a}(?![a-z0-9])", hay):
            return True
    return False


def country_for_city(city: str) -> "Country | None":
    """Return the single registry Country whose `aliases` name this city
    (matched via its CITY_ALIASES expansion), or None if no country's alias
    list mentions it. Used by filters._location_keeps so a city constrains
    only the country it actually belongs to.
    """
    city_aliases = set(expand_city(city))
    if not city_aliases:
        return None
    for country in COUNTRIES.values():
        country_aliases = {_fold(a) for a in country.aliases}
        if city_aliases & country_aliases:
            return country
    return None


SUPPORTED_ISO2: tuple[str, ...] = tuple(COUNTRIES)


def get(iso2: str) -> Country:
    try:
        return COUNTRIES[iso2.upper()]
    except KeyError:
        raise KeyError(f"unsupported country {iso2!r}; supported: {', '.join(SUPPORTED_ISO2)}") from None


def sources_for(iso2_list: list[str]) -> list[str]:
    """Union of enabled sources across selected countries, order-stable."""
    out: list[str] = []
    for c in iso2_list:
        for s in get(c).sources:
            if s not in out:
                out.append(s)
    return out


def languages_for(iso2_list: list[str]) -> list[str]:
    out: list[str] = []
    for c in iso2_list:
        for lang in get(c).languages:
            if lang not in out:
                out.append(lang)
    return out
