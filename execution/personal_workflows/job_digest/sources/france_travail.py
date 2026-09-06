"""
description: France Travail "Offres d'emploi v2" official REST API source adapter for
    job_digest. Adapted from the operator's internal job pipeline, generalized off profile.keywords
    (one query per keyword) and made a no-secrets-no-crash source: missing OAuth
    credentials return [] with a logged warning instead of raising.
inputs:
  - profile: Profile — one search query per profile.keywords entry
  - country: registry.Country | None — ignored; this source is only wired for FR in
    registry.py, so it is always called for a France-scoped profile
  - env: FRANCE_TRAVAIL_CLIENT_ID, FRANCE_TRAVAIL_CLIENT_SECRET (OAuth2 client_credentials)
  - dry: bool — when True, returns SourceJob rows from fixtures/france_travail.jsonl,
    no network
outputs:
  - list[SourceJob]

Endpoints (per https://francetravail.io docs, "Offres d'emploi v2"):
  - Token: POST https://entreprise.francetravail.fr/connexion/oauth2/access_token?realm=/partenaire
  - Search: GET https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search
"""

from __future__ import annotations

import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .. import registry
from ..contracts import JobSource, SourceJob
from ..profile_schema import Profile

logger = logging.getLogger("job_digest.sources.france_travail")

_FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"

TOKEN_URL = "https://entreprise.francetravail.fr/connexion/oauth2/access_token"
TOKEN_REALM = "/partenaire"
SEARCH_URL = "https://api.francetravail.io/partenaire/offresdemploi/v2/offres/search"
SCOPE = "api_offresdemploiv2 o2dsoffre"

MAX_PAGES = 3
PAGE_SIZE = 50
POSTED_WITHIN_DAYS = 1
POLITE_DELAY_S = 1.0


class FranceTravailAuthError(RuntimeError):
    """Raised when OAuth2 credentials are rejected by the token endpoint."""


def _get_credentials() -> tuple[str, str] | None:
    client_id = os.environ.get("FRANCE_TRAVAIL_CLIENT_ID", "").strip()
    client_secret = os.environ.get("FRANCE_TRAVAIL_CLIENT_SECRET", "").strip()
    if not client_id or not client_secret:
        return None
    return client_id, client_secret


def _get_access_token(client: httpx.Client, client_id: str, client_secret: str) -> str:
    r = client.post(
        TOKEN_URL,
        params={"realm": TOKEN_REALM},
        data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
            "scope": SCOPE,
        },
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=15.0,
    )
    if r.status_code != 200:
        # Never echo the response body — it can carry partial credential
        # detail and would land in a friend's public Actions log.
        raise FranceTravailAuthError(f"Token endpoint returned {r.status_code}")
    body = r.json()
    token = body.get("access_token")
    if not token:
        raise FranceTravailAuthError("Token endpoint returned no access_token")
    return token


def _parse_offer(offer: dict) -> SourceJob | None:
    try:
        offer_id = str(offer["id"])
        title = offer.get("intitule") or ""
        company = (offer.get("entreprise") or {}).get("nom") or "Confidential"

        lieu = offer.get("lieuTravail") or {}
        location_raw = lieu.get("libelle") or ""

        description = (offer.get("description") or "")[:2000]
        contract_raw = offer.get("typeContratLibelle") or offer.get("typeContrat") or ""
        posted_str = offer.get("dateCreation") or offer.get("dateActualisation") or ""
        posted_at = None
        if posted_str:
            try:
                posted_at = datetime.fromisoformat(posted_str.replace("Z", "+00:00"))
                if posted_at.tzinfo is None:
                    # France Travail's dateCreation/dateActualisation are
                    # local French-time strings with no offset when they
                    # don't carry a trailing "Z" — treat as UTC rather than
                    # leaving them naive (matches every other source adapter;
                    # a naive datetime can't be compared against the
                    # timezone-aware cutoffs in notifier/sheet.py).
                    posted_at = posted_at.replace(tzinfo=timezone.utc)
            except ValueError:
                posted_at = None

        origine = offer.get("origineOffre") or {}
        url = origine.get("urlOrigine") or f"https://candidat.francetravail.fr/offres/recherche/detail/{offer_id}"

        return SourceJob(
            source=JobSource.FRANCE_TRAVAIL,
            source_id=offer_id,
            url=url,
            title=title,
            company=company,
            location_raw=location_raw,
            description_snippet=description,
            posted_at=posted_at,
            contract_type_raw=contract_raw,
        )
    except (KeyError, ValueError, TypeError) as exc:
        logger.warning("france_travail: skip offer (parse error): %s", exc)
        return None


def _fetch_query(client: httpx.Client, token: str, query: str) -> list[SourceJob]:
    now_utc = datetime.now(timezone.utc)
    since = (now_utc - timedelta(days=POSTED_WITHIN_DAYS)).strftime("%Y-%m-%dT%H:%M:%SZ")
    until = now_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
    headers = {"Authorization": f"Bearer {token}", "Accept": "application/json"}
    jobs: list[SourceJob] = []

    for page_num in range(MAX_PAGES):
        start = page_num * PAGE_SIZE
        end = start + PAGE_SIZE - 1
        params = {
            "motsCles": query,
            "range": f"{start}-{end}",
            "minCreationDate": since,
            "maxCreationDate": until,
        }
        try:
            r = client.get(SEARCH_URL, params=params, headers=headers)
        except httpx.HTTPError as exc:
            logger.warning("france_travail: HTTP error on page %d for %r: %s — stopping", page_num, query, exc)
            break

        if r.status_code == 204:
            break
        if r.status_code == 429:
            logger.warning("france_travail: 429 rate-limited on page %d — returning %d so far", page_num, len(jobs))
            break
        if r.status_code >= 500:
            logger.warning("france_travail: %d on page %d — returning %d so far", r.status_code, page_num, len(jobs))
            break
        if r.status_code not in (200, 206):
            logger.warning("france_travail: unexpected %d on page %d", r.status_code, page_num)
            break

        try:
            body = r.json()
        except (ValueError, json.JSONDecodeError) as exc:
            logger.warning("france_travail: 200 OK but non-JSON body on page %d: %s", page_num, exc)
            break
        offers = body.get("resultats") or []
        if not offers:
            break

        for offer in offers:
            parsed = _parse_offer(offer)
            if parsed is not None:
                jobs.append(parsed)

        if len(offers) < PAGE_SIZE:
            break
        time.sleep(POLITE_DELAY_S)

    return jobs


def fetch(profile: Profile, country: "registry.Country | None", *, dry: bool = False) -> list[SourceJob]:
    """Search France Travail once per profile keyword. Returns [] with a logged
    warning when FRANCE_TRAVAIL_CLIENT_ID/SECRET are absent — never raises for
    missing secrets, since a friend may not have registered for this source."""
    if dry:
        return _load_fixture()

    creds = _get_credentials()
    if creds is None:
        logger.warning(
            "france_travail: FRANCE_TRAVAIL_CLIENT_ID/SECRET not set — skipping this source. "
            "Register at https://francetravail.io to enable it."
        )
        return []
    client_id, client_secret = creds

    all_jobs: list[SourceJob] = []
    with httpx.Client(timeout=20.0) as client:
        try:
            token = _get_access_token(client, client_id, client_secret)
        except FranceTravailAuthError as exc:
            logger.warning("france_travail: auth failure — %s. Skipping source.", exc)
            return []
        for query in profile.keywords:
            jobs = _fetch_query(client, token, query)
            logger.info("france_travail[%s] -> %d jobs", query, len(jobs))
            all_jobs.extend(jobs)
    return all_jobs


def _load_fixture() -> list[SourceJob]:
    path = _FIXTURES_DIR / "france_travail.jsonl"
    if not path.exists():
        logger.warning("france_travail: dry-mode fixture missing at %s — returning []", path)
        return []
    out: list[SourceJob] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line:
            out.append(SourceJob.model_validate_json(line))
    return out
