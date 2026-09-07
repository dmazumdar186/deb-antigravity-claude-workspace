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


# Direct folded-city-name -> ISO2 lookup (H4 follow-up). Covers cities that
# have no distinct alias variant (so never made it into CITY_ALIASES) but are
# still needed for country_for_city() to attribute a profile city correctly —
# e.g. "Strasbourg" (FR) or "Nice" (FR) never needed a spelling alias, so they
# were absent from Country.aliases too, which made country_for_city() return
# None for them and, per N1, incorrectly treated them as "unattributable"
# (constraining every selected country instead of just France). Keys here are
# already fold-normalized (lowercase, diacritics stripped); values are ISO2
# codes from COUNTRIES. country_for_city() consults this dict first, then
# falls back to CITY_ALIASES/Country.aliases, then None.
CITY_COUNTRY: dict[str, str] = {
    # --- FR ---
    "paris": "FR", "marseille": "FR", "lyon": "FR", "toulouse": "FR", "nice": "FR",
    "nantes": "FR", "strasbourg": "FR", "montpellier": "FR", "bordeaux": "FR",
    "lille": "FR", "rennes": "FR", "reims": "FR", "toulon": "FR", "saint-etienne": "FR",
    "le havre": "FR", "grenoble": "FR", "dijon": "FR", "angers": "FR", "nimes": "FR",
    "villeurbanne": "FR", "clermont-ferrand": "FR", "aix-en-provence": "FR", "brest": "FR",
    "limoges": "FR", "tours": "FR", "amiens": "FR", "metz": "FR", "besancon": "FR",
    "perpignan": "FR", "orleans": "FR", "mulhouse": "FR", "caen": "FR", "rouen": "FR",
    "nancy": "FR", "avignon": "FR", "versailles": "FR", "ile-de-france": "FR",
    # --- DE ---
    "berlin": "DE", "hamburg": "DE", "munich": "DE", "munchen": "DE", "cologne": "DE",
    "koln": "DE", "frankfurt": "DE", "frankfurt am main": "DE", "stuttgart": "DE",
    "dusseldorf": "DE", "leipzig": "DE", "dortmund": "DE", "essen": "DE", "bremen": "DE",
    "dresden": "DE", "hannover": "DE", "nurnberg": "DE", "nuremberg": "DE", "duisburg": "DE",
    "bochum": "DE", "wuppertal": "DE", "bielefeld": "DE", "bonn": "DE", "munster": "DE",
    "mannheim": "DE", "karlsruhe": "DE", "wiesbaden": "DE", "augsburg": "DE",
    "gelsenkirchen": "DE", "monchengladbach": "DE", "braunschweig": "DE", "chemnitz": "DE",
    "kiel": "DE", "aachen": "DE", "halle": "DE", "magdeburg": "DE", "freiburg": "DE",
    "krefeld": "DE", "lubeck": "DE", "mainz": "DE", "rostock": "DE", "kassel": "DE",
    "potsdam": "DE",
    # --- AT ---
    "vienna": "AT", "wien": "AT", "graz": "AT", "linz": "AT", "salzburg": "AT",
    "innsbruck": "AT", "klagenfurt": "AT", "villach": "AT", "wels": "AT",
    "sankt polten": "AT", "dornbirn": "AT", "wiener neustadt": "AT", "steyr": "AT",
    "feldkirch": "AT", "bregenz": "AT", "leonding": "AT", "klosterneuburg": "AT",
    "baden": "AT", "wolfsberg": "AT", "leoben": "AT", "krems": "AT", "traun": "AT",
    "amstetten": "AT", "lustenau": "AT", "kapfenberg": "AT", "hallein": "AT",
    "kufstein": "AT",
    # --- BE ---
    "brussels": "BE", "bruxelles": "BE", "brussel": "BE", "antwerp": "BE", "ghent": "BE",
    "gent": "BE", "charleroi": "BE", "liege": "BE", "bruges": "BE", "brugge": "BE",
    "namur": "BE", "leuven": "BE", "mons": "BE", "aalst": "BE", "mechelen": "BE",
    "la louviere": "BE", "kortrijk": "BE", "hasselt": "BE", "sint-niklaas": "BE",
    "ostend": "BE", "oostende": "BE", "tournai": "BE", "genk": "BE", "seraing": "BE",
    "roeselare": "BE", "verviers": "BE", "mouscron": "BE", "beveren": "BE",
    "dendermonde": "BE", "beringen": "BE",
    # --- NL ---
    "amsterdam": "NL", "rotterdam": "NL", "the hague": "NL", "den haag": "NL",
    "utrecht": "NL", "eindhoven": "NL", "groningen": "NL", "tilburg": "NL",
    "almere": "NL", "breda": "NL", "nijmegen": "NL", "enschede": "NL", "haarlem": "NL",
    "arnhem": "NL", "zaanstad": "NL", "amersfoort": "NL", "apeldoorn": "NL",
    "hoofddorp": "NL", "maastricht": "NL", "leiden": "NL", "dordrecht": "NL",
    "zoetermeer": "NL", "zwolle": "NL", "deventer": "NL", "delft": "NL", "alkmaar": "NL",
    # --- GB ---
    "london": "GB", "manchester": "GB", "birmingham": "GB", "leeds": "GB",
    "glasgow": "GB", "edinburgh": "GB", "liverpool": "GB", "bristol": "GB",
    "sheffield": "GB", "newcastle": "GB", "belfast": "GB", "nottingham": "GB",
    "cardiff": "GB", "leicester": "GB", "coventry": "GB", "bradford": "GB",
    "southampton": "GB", "reading": "GB", "derby": "GB", "plymouth": "GB",
    "wolverhampton": "GB", "aberdeen": "GB", "cambridge": "GB", "oxford": "GB",
    "york": "GB", "brighton": "GB",
    # --- CH ---
    "zurich": "CH", "geneva": "CH", "geneve": "CH", "genf": "CH", "basel": "CH",
    "lausanne": "CH", "bern": "CH", "winterthur": "CH", "lucerne": "CH", "luzern": "CH",
    "st. gallen": "CH", "st gallen": "CH", "lugano": "CH", "biel": "CH", "thun": "CH",
    "koniz": "CH", "la chaux-de-fonds": "CH", "fribourg": "CH", "schaffhausen": "CH",
    "chur": "CH", "vernier": "CH", "neuchatel": "CH", "uster": "CH", "sion": "CH",
    "emmen": "CH", "zug": "CH", "yverdon": "CH", "baar": "CH", "rapperswil": "CH",
    # --- IN ---
    "bengaluru": "IN", "bangalore": "IN", "mumbai": "IN", "bombay": "IN",
    "delhi": "IN", "new delhi": "IN", "hyderabad": "IN", "chennai": "IN",
    "kolkata": "IN", "pune": "IN", "ahmedabad": "IN", "jaipur": "IN", "surat": "IN",
    "lucknow": "IN", "kanpur": "IN", "nagpur": "IN", "indore": "IN", "thane": "IN",
    "bhopal": "IN", "visakhapatnam": "IN", "patna": "IN", "vadodara": "IN",
    "gurugram": "IN", "gurgaon": "IN", "noida": "IN", "coimbatore": "IN",
    "kochi": "IN", "chandigarh": "IN", "nashik": "IN",
    # --- SG (city-state: major planning areas stand in for "regional capitals") ---
    "singapore": "SG", "woodlands": "SG", "jurong east": "SG", "jurong west": "SG",
    "tampines": "SG", "bishan": "SG", "ang mo kio": "SG", "bedok": "SG",
    "clementi": "SG", "hougang": "SG", "punggol": "SG", "sengkang": "SG",
    "yishun": "SG", "toa payoh": "SG", "bukit timah": "SG", "pasir ris": "SG",
    "choa chu kang": "SG", "sembawang": "SG", "serangoon": "SG", "queenstown": "SG",
    "novena": "SG", "marine parade": "SG", "kallang": "SG", "geylang": "SG",
    "bukit batok": "SG", "bukit panjang": "SG", "bukit merah": "SG",
    # --- CA ---
    "toronto": "CA", "montreal": "CA", "vancouver": "CA", "calgary": "CA",
    "edmonton": "CA", "ottawa": "CA", "winnipeg": "CA", "quebec": "CA",
    "quebec city": "CA", "hamilton": "CA", "kitchener": "CA", "victoria": "CA",
    "halifax": "CA", "oshawa": "CA", "windsor": "CA", "saskatoon": "CA",
    "regina": "CA", "st. john's": "CA", "st johns": "CA", "barrie": "CA",
    "kelowna": "CA", "abbotsford": "CA", "sherbrooke": "CA", "trois-rivieres": "CA",
    "guelph": "CA", "kingston": "CA", "thunder bay": "CA",
    # --- US ---
    "new york": "US", "los angeles": "US", "chicago": "US", "houston": "US",
    "phoenix": "US", "philadelphia": "US", "san antonio": "US", "san diego": "US",
    "dallas": "US", "san jose": "US", "austin": "US", "jacksonville": "US",
    "fort worth": "US", "columbus": "US", "charlotte": "US", "san francisco": "US",
    "indianapolis": "US", "seattle": "US", "denver": "US", "washington": "US",
    "boston": "US", "el paso": "US", "nashville": "US", "detroit": "US",
    "portland": "US", "memphis": "US", "oklahoma city": "US", "las vegas": "US",
    "louisville": "US", "baltimore": "US", "milwaukee": "US", "albuquerque": "US",
    "tucson": "US", "fresno": "US", "sacramento": "US", "atlanta": "US",
    "miami": "US",
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
    """Return the registry Country this city belongs to, or None if it can't
    be attributed to any. Consults CITY_COUNTRY first (the broad direct
    lookup — N1), then falls back to matching against each Country's
    `aliases` (matched via the city's CITY_ALIASES expansion, for city names
    that were already registered as country aliases before CITY_COUNTRY
    existed), then None. Used by filters._location_keeps and
    ranker/heuristic._location_fit so a city constrains only the country it
    actually belongs to.
    """
    folded = _fold(city).strip()
    if not folded:
        return None

    iso2 = CITY_COUNTRY.get(folded)
    if iso2 is not None:
        return COUNTRIES.get(iso2)

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
